"""JWT access-token verification.

Per ADR-013 the agentcook FastAPI runtime is a **verifier only** —
issuing access/refresh tokens is the responsibility of agentcook-java.
Both services share one secret (HS256, dev default identical on both
sides) or the Java side's public key (RS256).

Two dependencies:

- :func:`get_current_user` — honours ``AGENTCOOK_AUTH_MODE``:
  ``required`` → a valid token is mandatory; ``optional`` → a valid
  token is used if present, otherwise the caller is the shared
  ``anonymous`` user (dev / demo); ``disabled`` → always anonymous.
  A token that is *present but invalid* is always rejected — silently
  downgrading a bad token to anonymous would hide auth bugs.
- :func:`verify_access_token` — always requires a token unless auth is
  disabled (used by the memory/admin surfaces).

Wire format (frontend-conventions §7.6): ``Authorization: Bearer <jwt>``;
failures return the canonical ``{code, message, detail}`` envelope.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import jwt
from fastapi import Depends, Header, HTTPException, Request, status

from agentcook_app.config import Settings
from agentcook_app.schemas import ErrorEnvelope

ANONYMOUS_USER_ID = "anonymous"
ADMIN_SCOPES = frozenset({"admin", "agent:admin"})


@dataclass(frozen=True, slots=True)
class UserContext:
    """Authenticated principal extracted from a verified JWT."""

    user_id: str
    scopes: frozenset[str]
    raw_claims: dict[str, Any] = field(default_factory=dict)
    anonymous: bool = False
    token: str | None = None

    @property
    def is_admin(self) -> bool:
        return bool(self.scopes & ADMIN_SCOPES)


def _unauthorized(code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=ErrorEnvelope(code=code, message=message).model_dump(),
        headers={"WWW-Authenticate": "Bearer"},
    )


def _settings(request: Request) -> Settings:
    return request.app.state.container.settings


def _anonymous() -> UserContext:
    return UserContext(user_id=ANONYMOUS_USER_ID, scopes=frozenset(), anonymous=True)


def decode_token(token: str, settings: Settings) -> UserContext:
    key = settings.jwt_public_key or settings.jwt_secret
    options: dict[str, Any] = {"require": ["exp", "sub"]}
    try:
        claims = jwt.decode(
            token,
            key=key,
            algorithms=[settings.jwt_algorithm],
            issuer=settings.jwt_issuer,
            options=options,
        )
    except jwt.ExpiredSignatureError:
        raise _unauthorized("AUTH_TOKEN_EXPIRED", "Access token has expired.") from None
    except jwt.InvalidTokenError as exc:
        raise _unauthorized("AUTH_INVALID_TOKEN", f"Invalid token: {exc}") from exc
    if claims.get("typ") == "refresh" or claims.get("token_type") == "refresh":
        raise _unauthorized("AUTH_INVALID_TOKEN", "Refresh tokens cannot be used as access tokens.")

    scopes_raw = claims.get("scopes") or claims.get("scope") or ""
    scopes = frozenset(scopes_raw.split()) if isinstance(scopes_raw, str) else frozenset(scopes_raw)
    roles = claims.get("roles")
    if isinstance(roles, list):
        scopes = scopes | {str(r).lower() for r in roles}
    return UserContext(user_id=str(claims["sub"]), scopes=scopes, raw_claims=claims, token=token)


def _bearer(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise _unauthorized("AUTH_MISSING_TOKEN", "Authorization header must be 'Bearer <token>'.")
    return token.strip()


async def get_current_user(
    request: Request,
    authorization: str | None = Header(default=None),
) -> UserContext:
    """Caller identity according to the configured auth mode."""
    settings = _settings(request)
    if settings.auth_mode == "disabled":
        return _anonymous()
    token = _bearer(authorization)
    if token is None:
        if settings.auth_mode == "optional":
            return _anonymous()
        raise _unauthorized("AUTH_MISSING_TOKEN", "Missing Bearer token.")
    return decode_token(token, settings)


async def verify_access_token(
    request: Request,
    authorization: str | None = Header(default=None),
) -> UserContext:
    """Strict variant: a valid token is required unless auth is disabled."""
    settings = _settings(request)
    if settings.auth_mode == "disabled":
        return _anonymous()
    token = _bearer(authorization)
    if token is None:
        raise _unauthorized("AUTH_MISSING_TOKEN", "Missing Bearer token.")
    return decode_token(token, settings)


def require_scope(required: str):  # noqa: ANN201 — FastAPI dependency factory
    """Dependency factory enforcing a single scope on an endpoint."""

    async def _check(user: UserContext = Depends(verify_access_token)) -> UserContext:
        if required not in user.scopes and not user.is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=ErrorEnvelope(
                    code="AUTH_FORBIDDEN",
                    message=f"Scope {required!r} required.",
                ).model_dump(),
            )
        return user

    return _check


__all__ = [
    "ANONYMOUS_USER_ID",
    "UserContext",
    "decode_token",
    "get_current_user",
    "require_scope",
    "verify_access_token",
]
