import os
from dataclasses import dataclass


@dataclass
class AppSettings:
    """
    Application settings for the read‑only TWS integration.

    Environment variables are used to override default values when present.
    """

    tws_host: str = os.getenv("TWS_HOST", "localhost")
    tws_port: int = int(os.getenv("TWS_PORT", "8080"))
    tws_username: str = os.getenv("TWS_USERNAME", "admin")
    tws_password: str = os.getenv("TWS_PASSWORD", "admin")
    tws_engine_name: str = os.getenv("TWS_ENGINE_NAME", "ENGINE")
    tws_engine_owner: str = os.getenv("TWS_ENGINE_OWNER", "owner")
    jwt_secret_key: str = os.getenv("JWT_SECRET_KEY", "change-me")
    jwt_algorithm: str = os.getenv("JWT_ALGORITHM", "HS256")
