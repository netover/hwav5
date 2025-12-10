
"""
Core configuration for FastAPI application
"""

from pathlib import Path

from pydantic import SecretStr, field_validator
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
    secret_key: SecretStr = SecretStr("CHANGE_ME_IN_PRODUCTION_USE_ENV_VAR")
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # Redis settings
    redis_url: str = "redis://localhost:6379"
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0

    # TWS settings (Trading Workstation) - Use SecretStr for sensitive data
    tws_host: str = "localhost"
    tws_port: int = 31111
    tws_user: str = "twsuser"
    tws_password: SecretStr = SecretStr("twspass")

    # Proxy settings for corporate environments
    use_system_proxy: bool = False

    # File upload settings - Use absolute path in production
    upload_dir: Path = Path("uploads")
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

    @field_validator("secret_key")
    @classmethod
    def validate_secret_key(cls, v: SecretStr, info) -> SecretStr:
        """Ensure secret_key is not default in production."""
        # Access other field values via info.data
        env = info.data.get("environment", "development")
        if env == "production" and "CHANGE_ME" in v.get_secret_value():
            raise ValueError(
                "SECRET_KEY must be set via environment variable in production. "
                "Set the SECRET_KEY environment variable to a secure random string."
            )
        return v

    @field_validator("upload_dir")
    @classmethod
    def validate_upload_dir(cls, v: Path, info) -> Path:
        """Warn if upload_dir is relative in production."""
        env = info.data.get("environment", "development")
        if env == "production" and not v.is_absolute():
            import warnings
            warnings.warn(
                f"upload_dir '{v}' is relative. In production, use an absolute path "
                "or mount a persistent volume to avoid data loss.",
                UserWarning,
                stacklevel=2,
            )
        return v

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)


# Global settings instance
settings = Settings()
