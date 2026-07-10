"""
Flask application factory.

Creates and configures the Flask app with all components.
Uses dependency injection for testability.

Security notes:
- No credentials hardcoded
- IAM Role credentials handled by boto3
- Configuration from environment variables
- Centralized logging
"""

from flask import Flask, current_app, jsonify, request
from app.config import get_config
from app.utils.logger import setup_logging, get_logger
from app.services.dynamodb_service import DynamoDBService


logger = get_logger(__name__)


def create_app(config_name: str | None = None) -> Flask:
    """
    Create and configure Flask application.

    Args:
        config_name: Configuration name (development, production, testing)
                    Defaults to FLASK_ENV environment variable

    Returns:
        Configured Flask application instance

    Example:
        >>> app = create_app("production")
        >>> app.run()
    """
    # Get configuration
    config_class = get_config(config_name)
    config = config_class()
    if config_class.__name__ == "ProductionConfig" and not config.SECRET_KEY:
        raise ValueError(
            "SECRET_KEY must be set in production via environment variable"
        )

    # Setup logging
    setup_logging(
        log_level=config.LOG_LEVEL,
        format_string=config.LOG_FORMAT,
    )

    logger.info(f"Creating Flask app in {config.FLASK_ENV} mode")

    # Create Flask app
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config)

    # Initialize DynamoDB service
    dynamodb_service = DynamoDBService(
        table_name=config.DYNAMODB_TABLE_NAME,
        region=config.AWS_REGION,
    )

    # Store service in app context for routes to access
    app.dynamodb_service = dynamodb_service

    logger.info(f"DynamoDB Table: {config.DYNAMODB_TABLE_NAME}")
    logger.info(f"AWS Region: {config.AWS_REGION}")
    logger.info(f"Flask env: {config.FLASK_ENV}")

    # Register blueprints
    _register_blueprints(app)

    # Register error handlers
    _register_error_handlers(app)

    # Register health check endpoint
    _register_health_check(app)

    # Register request logging
    _register_request_logging(app)

    logger.info("Flask app created successfully")
    return app


def _register_blueprints(app: Flask) -> None:
    """
    Register Flask blueprints for routes.

    Args:
        app: Flask application instance
    """
    from app.routes.web import web_bp
    from app.routes.api import api_bp

    app.register_blueprint(web_bp)
    app.register_blueprint(api_bp)

    logger.info("Blueprints registered")


def _register_error_handlers(app: Flask) -> None:
    """
    Register error handlers for common HTTP errors.

    Args:
        app: Flask application instance
    """

    @app.errorhandler(400)
    def bad_request(error):
        return (
            jsonify({"error": "Bad request", "message": str(error)}),
            400,
        )

    @app.errorhandler(404)
    def not_found(error):
        return (
            jsonify({"error": "Not found", "message": "Resource not found"}),
            404,
        )

    @app.errorhandler(500)
    def internal_error(error):
        logger.error(f"Internal server error: {error}")
        return (
            jsonify(
                {
                    "error": "Internal server error",
                    "message": "An unexpected error occurred",
                }
            ),
            500,
        )

    logger.info("Error handlers registered")


def _register_health_check(app: Flask) -> None:
    """
    Register health check endpoint.

    Args:
        app: Flask application instance
    """

    @app.route("/health", methods=["GET"])
    def health_check():
        """
        Health check endpoint.

        Returns application status and database connectivity.
        """
        db_status = current_app.dynamodb_service.check_connectivity()

        return jsonify(
            {
                "status": "healthy" if db_status["connected"] else "degraded",
                "database": ("connected" if db_status["connected"] else "disconnected"),
                "authentication": "IAM Role",
                "table": db_status.get("table"),
                "region": db_status.get("region"),
                "error": db_status.get("error"),
            }
        )

    logger.info("Health check endpoint registered")


def _register_request_logging(app: Flask) -> None:
    """
    Register lightweight request logging.

    Avoids request bodies and headers so sensitive data is not logged.
    """

    @app.before_request
    def log_request():
        logger.info("Incoming request: %s %s", request.method, request.path)

    logger.info("Request logging registered")
