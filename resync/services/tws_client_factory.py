from functools import lru_cache

from fastapi import Depends

from resync.config.app_settings import AppSettings
from resync.services.tws_service import OptimizedTWSClient


@lru_cache
def _build_client(settings: AppSettings) -> OptimizedTWSClient:
    """
    Instantiate a singleton OptimizedTWSClient using the provided settings.
    """
    base_url = f"http://{settings.tws_host}:{settings.tws_port}"
    return OptimizedTWSClient(
        base_url=base_url,
        username=settings.tws_username,
        password=settings.tws_password,
        engine_name=settings.tws_engine_name,
        engine_owner=settings.tws_engine_owner,
    )


def get_tws_client(
    settings: AppSettings = Depends(lambda: AppSettings()),
) -> OptimizedTWSClient:
    """
    FastAPI dependency that returns the singleton TWS client.

    Since `AppSettings` is a dataclass and not compatible with FastAPI's dependency
    injection by default, we provide a lambda wrapper that instantiates it.
    """
    return _build_client(settings)
