"""
Core configuration for FastAPI application
"""

from pathlib import Path

from pydantic import SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Default insecure values for development only
_DEFAULT_TWS_USER = "twsuser"
_DEFAULT_TWS_PASSWORD = "twspass"


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # Server settings
    server_host: str = "127.0.0.1"
    server_port: int = 8000

    # Environment
    environment: str = "development"
    debug: bool = False  # Default to False for security; set via DEBUG env var

    # Security - SECRET_KEY must be set via environment variable in production
    secret_key: SecretStr = SecretStr("CHANGE_ME_IN_PRODUCTION_USE_ENV_VAR")
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # Redis settings - Use redis_connection_url property for consistency
    redis_url: str | None = None  # Optional override
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0

    # TWS settings (HCL Workload Automation) - Use SecretStr for sensitive data
    tws_host: str = "localhost"
    tws_port: int = 31111
    tws_user: str = _DEFAULT_TWS_USER
    tws_password: SecretStr = SecretStr(_DEFAULT_TWS_PASSWORD)

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

    @property
    def redis_connection_url(self) -> str:
        """
        Get Redis connection URL with consistency guarantee.

        If redis_url is explicitly set, use it. Otherwise, build from components.
        This ensures a single source of truth for Redis connection.
        """
        if self.redis_url:
            return self.redis_url
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    @field_validator("secret_key")
    @classmethod
    def validate_secret_key(cls, v: SecretStr, info) -> SecretStr:
        """Ensure secret_key is not default in production."""
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

    @model_validator(mode="after")
    def validate_tws_credentials(self) -> "Settings":
        """Warn if using default TWS credentials in production."""
        if self.environment == "production":
            if self.tws_user == _DEFAULT_TWS_USER:
                import warnings

                warnings.warn(
                    f"TWS_USER is using default value '{_DEFAULT_TWS_USER}'. "
                    "Set TWS_USER environment variable in production.",
                    UserWarning,
                    stacklevel=2,
                )
            if self.tws_password.get_secret_value() == _DEFAULT_TWS_PASSWORD:
                import warnings

                warnings.warn(
                    "TWS_PASSWORD is using default value. "
                    "Set TWS_PASSWORD environment variable in production.",
                    UserWarning,
                    stacklevel=2,
                )
        return self

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)


# Global settings instance
settings = Settings()
