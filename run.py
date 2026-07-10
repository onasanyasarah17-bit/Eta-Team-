#!/usr/bin/env python
"""
Application entry point.

Usage:
    python run.py                          # Development mode
    FLASK_ENV=production python run.py     # Production mode (use gunicorn in real deployment)
    
Environment variables:
    FLASK_ENV: development, production, testing (default: development)
    PORT: Port to run on (default: 5000)
    AWS_REGION: AWS region (default: us-east-1)
    DYNAMODB_TABLE_NAME: DynamoDB table (default: secure-employees)
    
AWS Credentials:
    The application uses boto3's default credential provider chain.
    On EC2, it will automatically use the attached IAM Role.
    No credentials should be hardcoded or passed via environment.
"""

import os
from dotenv import load_dotenv
from app import create_app
from app.utils.logger import get_logger


# Load environment variables from .env file (if it exists)
load_dotenv()

logger = get_logger(__name__)
app = create_app()


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("FLASK_ENV") == "development"

    logger.info(f"Starting Flask application on port {port}")
    logger.info(f"Debug mode: {debug}")
    logger.info("AWS credentials will be obtained from IAM Role (boto3 default provider chain)")

    app.run(
        host="0.0.0.0",
        port=port,
        debug=debug,
    )
