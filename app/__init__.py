"""
Flask application factory.

Creates and configures the Flask app with all components.
Uses dependency injection for testability.

Security notes:
- No credentials hardcoded
- IAM Role credentials handled by boto3
- Configuration from environment variables
- Centralized logging with request IDs
"""

from __future__ import annotations

import time
import uuid

from flask import Flask, g, jsonify, request
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.proxy_fix import ProxyFix

from app.config import get_config
from app.services.dynamodb_service import DynamoDBService
from app.utils.errors import error_payload
from app.utils.logger import get_logger, setup_logging


logger = get_logger(__name__)


def create_app(config_name: str | None = None) -> Flask:
    """
    Create and configure Flask application.

    Args:
        config_name: Configuration name (development, production, testing)
                    Defaults to FLASK_ENV environment variable

    Returns:
        Configured Flask application instance
    """
    config_class = get_config(config_name)
    config = config_class()
    if config_class.__name__ == "ProductionConfig" and not config.SECRET_KEY:
        raise ValueError(
            "SECRET_KEY must be set in production via environment variable"
        )

    setup_logging(
        log_level=config.LOG_LEVEL,
        log_file=config.LOG_FILE,
        format_string=config.LOG_FORMAT,
        json_logs=config.LOG_JSON,
    )

    logger.info("Creating Flask app in %s mode", config.FLASK_ENV)

    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config)

    if config.TRUST_PROXY:
        # One hop: Application Load Balancer terminates TLS and forwards proto/host
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
        logger.info("ProxyFix enabled for reverse-proxy / ALB headers")

    dynamodb_service = DynamoDBService(
        table_name=config.DYNAMODB_TABLE_NAME,
        region=config.AWS_REGION,
    )
    app.dynamodb_service = dynamodb_service

    logger.info("DynamoDB Table: %s", config.DYNAMODB_TABLE_NAME)
    logger.info("AWS Region: %s", config.AWS_REGION)
    logger.info("Flask env: %s", config.FLASK_ENV)

    _register_blueprints(app)
    _register_error_handlers(app)
    _register_health_check(app)
    _register_request_logging(app)

    logger.info("Flask app created successfully")
    return app


def _register_blueprints(app: Flask) -> None:
    """Register Flask blueprints for routes."""
    from app.routes.web import web_bp
    from app.routes.api import api_bp

    app.register_blueprint(web_bp)
    app.register_blueprint(api_bp)

    logger.info("Blueprints registered")


def _register_error_handlers(app: Flask) -> None:
    """Register error handlers for HTTP and unexpected errors."""

    @app.errorhandler(400)
    def bad_request(error):
        description = getattr(error, "description", None) or "Bad request"
        return (
            jsonify(error_payload("BadRequest", description)),
            400,
        )

    @app.errorhandler(404)
    def not_found(error):
        return (
            jsonify(error_payload("NotFound", "Resource not found")),
            404,
        )

    @app.errorhandler(405)
    def method_not_allowed(error):
        return (
            jsonify(error_payload("MethodNotAllowed", "Method not allowed")),
            405,
        )

    @app.errorhandler(500)
    def internal_error(error):
        logger.error("Internal server error: %s", error)
        return (
            jsonify(
                error_payload(
                    "InternalServerError",
                    "An unexpected error occurred",
                )
            ),
            500,
        )

    @app.errorhandler(Exception)
    def unhandled_exception(error):
        if isinstance(error, HTTPException):
            code = error.code or 500
            name = (error.name or "HTTPError").replace(" ", "")
            return (
                jsonify(
                    error_payload(
                        name,
                        error.description or "Request failed",
                    )
                ),
                code,
            )

        logger.exception("Unhandled exception on %s %s", request.method, request.path)
        return (
            jsonify(
                error_payload(
                    "InternalServerError",
                    "An unexpected error occurred",
                )
            ),
            500,
        )

    logger.info("Error handlers registered")


def _register_health_check(app: Flask) -> None:
    """Register liveness, readiness, and combined health endpoints."""

    def _readiness_payload():
        db_status = app.dynamodb_service.check_connectivity()
        connected = bool(db_status.get("connected"))
        payload = {
            "status": "healthy" if connected else "degraded",
            "database": "connected" if connected else "disconnected",
            "authentication": "IAM Role",
            "table": db_status.get("table"),
            "region": db_status.get("region"),
            "error": db_status.get("error"),
        }
        request_id = getattr(g, "request_id", None)
        if request_id:
            payload["request_id"] = request_id
        status_code = 200 if connected else 503
        return payload, status_code

    @app.route("/health/live", methods=["GET"])
    def liveness():
        """Process is up — no dependency checks (ALB/target group friendly)."""
        payload = {"status": "alive"}
        request_id = getattr(g, "request_id", None)
        if request_id:
            payload["request_id"] = request_id
        return jsonify(payload), 200

    @app.route("/health/ready", methods=["GET"])
    def readiness():
        """Ready to serve traffic only when DynamoDB is reachable."""
        payload, status_code = _readiness_payload()
        return jsonify(payload), status_code

    @app.route("/health", methods=["GET"])
    def health_check():
        """
        Combined health check used by demos and operators.

        Returns 503 when DynamoDB is unreachable so load balancers can drain.
        """
        payload, status_code = _readiness_payload()
        return jsonify(payload), status_code

    logger.info("Health check endpoints registered")


def _register_request_logging(app: Flask) -> None:
    """
    Attach request IDs and log request start/finish without bodies or headers.
    """

    @app.before_request
    def start_request():
        incoming = request.headers.get("X-Request-ID", "").strip()
        g.request_id = incoming or str(uuid.uuid4())
        g.request_started_at = time.perf_counter()
        logger.info(
            "Incoming request: %s %s",
            request.method,
            request.path,
            extra={
                "request_id": g.request_id,
                "method": request.method,
                "path": request.path,
                "remote_addr": request.remote_addr,
            },
        )

    @app.after_request
    def finish_request(response):
        started = getattr(g, "request_started_at", None)
        duration_ms = None
        if started is not None:
            duration_ms = round((time.perf_counter() - started) * 1000, 2)

        request_id = getattr(g, "request_id", None)
        if request_id:
            response.headers["X-Request-ID"] = request_id

        logger.info(
            "Completed request: %s %s -> %s",
            request.method,
            request.path,
            response.status_code,
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.path,
                "status": response.status_code,
                "duration_ms": duration_ms,
                "remote_addr": request.remote_addr,
            },
        )
        return response

    logger.info("Request logging registered")
