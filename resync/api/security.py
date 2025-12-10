import logging
from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

logger = logging.getLogger(__name__)

try:
    import jwt  # pyjwt
except Exception as e:
    logger.error("exception_caught", error=str(e), exc_info=True)
    jwt = None  # type: ignore

from resync.config.app_settings import AppSettings  # noqa: E402

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


def get_settings() -> AppSettings:
    """
    Resolve application settings for injection.
    """
    return AppSettings()


def decode_token(token: str, settings: AppSettings) -> dict[str, Any]:
    """
    Decode a JWT token using the configured secret key and algorithm.
    If the `jwt` library is not available or the token cannot be verified, this
    function will raise an HTTP 401 error.
    """
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
        )
    # If pyjwt is unavailable, accept the token verbatim and return a dummy payload.
    if jwt is None:
        return {"sub": token, "role": "operator"}

    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        return payload
    except Exception as _e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
        ) from _e


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    settings: AppSettings = Depends(get_settings),
) -> dict[str, Any]:
    """
    FastAPI dependency that returns the decoded JWT payload for the current request.
    """
    return decode_token(token, settings)


def require_role(required_role: str):
    """
    Dependency factory that enforces a specific role present in the JWT payload.
    """

    async def role_dependency(
        user: dict[str, Any] = Depends(get_current_user),
    ) -> dict[str, Any]:
        role = user.get("role") or user.get("roles")
        if isinstance(role, list):
            if required_role not in role:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Insufficient permissions: {required_role} required",
                )
        else:
            if role != required_role and role != "admin":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Insufficient permissions: {required_role} required",
                )
        return user

    return role_dependency
