from fastapi import Header, HTTPException, status
from .config import settings


async def verify_action_api_key(
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
) -> None:
    expected = settings.action_api_key

    # Opción 1: compatibilidad con X-API-Key
    if x_api_key and x_api_key == expected:
        return

    # Opción 2: compatibilidad con Authorization: Bearer <token>
    if authorization:
        parts = authorization.strip().split(" ", 1)
        if len(parts) == 2:
            scheme, token = parts
            if scheme.lower() == "bearer" and token == expected:
                return

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Missing or invalid API key.",
    )