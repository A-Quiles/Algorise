"""Dependencias compartidas de la API (autenticación)."""

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.security import decode_access_token

_bearer = HTTPBearer(auto_error=True)


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(_bearer)) -> str:
    """Valida el token Bearer y devuelve el username. Protege los endpoints privados."""
    username = decode_access_token(credentials.credentials)
    if username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o caducado.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return username
