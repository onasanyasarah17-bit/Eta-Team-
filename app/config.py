"""
Application configuration module.

Follows 12-factor app principles: environment-based configuration.
All sensitive settings come from environment variables, never hardcoded.

AWS Credentials flow:
1. boto3 uses the default credential provider chain
2. On EC2, boto3 detects IAM Role attached to instance
3. No explicit credentials needed - IAM Role handles authentication
4. No aws configure required
"""

import os


class Config:
    """Base configuration with sensible defaults."""

    # Flask
    FLASK_ENV: str = os.getenv("FLASK_ENV", "development")
    DEBUG: bool = FLASK_ENV == "development"
    TESTING: bool = False
    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")

    # Server
    PORT: int = int(os.getenv("PORT", 5000))
    HOST: str = os.getenv("HOST", "0.0.0.0")

    # AWS Configuration
    # boto3 will automatically detect IAM Role on EC2
    # No explicit credentials needed - they come from the IAM Role
    AWS_REGION: str = os.getenv("AWS_REGION", "eu-north-1")

    # DynamoDB Table
    DYNAMODB_TABLE_NAME: str = os.getenv("DYNAMODB_TABLE_NAME", "secure-employees")

    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


class DevelopmentConfig(Config):
    """Development configuration."""

    FLASK_ENV = "development"
    DEBUG = True
    LOG_LEVEL = "DEBUG"


class ProductionConfig(Config):
    """Production configuration."""

    FLASK_ENV = "production"
    DEBUG = False
    LOG_LEVEL = "INFO"
    # In production, SECRET_KEY MUST be set via environment variable
    SECRET_KEY: str = os.getenv("SECRET_KEY")


class TestingConfig(Config):
    """Testing configuration."""

    FLASK_ENV = "testing"
    TESTING = True
    DEBUG = True
    DYNAMODB_TABLE_NAME = "test-secure-employees"
    LOG_LEVEL = "DEBUG"


def get_config(env: str | None = None) -> type[Config]:
    """
    Get configuration class based on environment.

    Args:
        env: Environment name. Defaults to FLASK_ENV.

    Returns:
        Configuration class

    Raises:
        ValueError: If environment is invalid
    """
    environment = (env or os.getenv("FLASK_ENV", "development")).lower()

    config_map: dict[str, type[Config]] = {
        "development": DevelopmentConfig,
        "dev": DevelopmentConfig,
        "production": ProductionConfig,
        "prod": ProductionConfig,
        "testing": TestingConfig,
        "test": TestingConfig,
    }

    if environment not in config_map:
        raise ValueError(
            f"Invalid environment: {environment}. "
            f"Must be one of: {', '.join(config_map.keys())}"
        )

    return config_map[environment]
