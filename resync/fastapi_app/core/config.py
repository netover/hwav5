
"""
Core configuration for FastAPI application
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # Server settings
    server_host: str = "127.0.0.1"
    server_port: int = 8000

    # Environment
    environment: str = "development"
    debug: bool = True

    # Security - SECRET_KEY must be set via environment variable in production
    secret_key: str = "CHANGE_ME_IN_PRODUCTION_USE_ENV_VAR"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # Redis settings
    redis_url: str = "redis://localhost:6379"
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0

    # TWS settings (Trading Workstation)
    tws_host: str = "localhost"
    tws_port: int = 31111
    tws_user: str = "twsuser"
    tws_password: str = "twspass"

    # File upload settings
    upload_dir: str = "uploads"
    max_file_size: int = 10 * 1024 * 1024  # 10MB
    allowed_extensions: list[str] = [".txt", ".pdf", ".docx", ".md", ".json"]

    # Rate limiting
    rate_limit_requests: int = 100
    rate_limit_window: int = 60  # seconds

    # Logging
    log_level: str = "INFO"
    structured_logging: bool = True

    # CORS settings
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:8080"]
    cors_allow_credentials: bool = True
    cors_allow_methods: list[str] = ["*"]
    cors_allow_headers: list[str] = ["*"]
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)

# Global settings instance
settings = Settings()
