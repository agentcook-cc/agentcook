"""JWT access-token verification.

Per ADR-013 the agentcook FastAPI runtime is a **verifier only** —
issuing access/refresh tokens is the responsibility of agentcook-java
(OAuth2 Resource Server). We accept the signing key as configuration
(symmetric HS256 for dev / public-key RS256 for prod) and surface a
``UserContext`` dependency for endpoints to consume.

B's frontend-conventions §7.6 enforces the wire format:
- ``Authorization: Bearer <access_token>`` header
- Token lifetime ~15 minutes (issued by Java; we don't enforce length)
- Refresh-token flow lives entirely in Java (we never see refresh tokens)
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import jwt
from fastapi import Depends, Header, HTTPException, status

from agentcook_app.schemas import ErrorEnvelope


@dataclass(frozen=True, slots=True)
class UserContext:
    """Authenticated principal extracted from a verified JWT.

    Only fields agentcook runtime actually needs — we don't mirror the
    Java User aggregate here (out of scope per ADR-013).
    """

    user_id: str
    scopes: frozenset[str]
    raw_claims: dict[str, Any]


def _signing_config() -> tuple[str, str]:
    """Return ``(secret_or_public_key, algorithm)`` from env.

    Dev default uses HS256 with ``AGENTCOOK_JWT_SECRET``; production
    deploys override with ``AGENTCOOK_JWT_PUBLIC_KEY`` + RS256.
    """
    if pubkey := os.environ.get("AGENTCOOK_JWT_PUBLIC_KEY"):
        return pubkey, os.environ.get("AGENTCOOK_JWT_ALG", "RS256")
    secret = os.environ.get("AGENTCOOK_JWT_SECRET", "dev-only-do-not-use-in-prod")
    return secret, os.environ.get("AGENTCOOK_JWT_ALG", "HS256")


def _unauthorized(code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=ErrorEnvelope(code=code, message=message).model_dump(),
        headers={"WWW-Authenticate": "Bearer"},
    )


async def verify_access_token(
    authorization: str | None = Header(default=None),
) -> UserContext:
    """FastAPI dependency that turns ``Authorization`` header into a ``UserContext``.

    Issues 401 with the canonical error envelope on any failure — the
    front-end (B) globally handles 401 by refreshing & retrying (§7.3).
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise _unauthorized("AUTH_MISSING_TOKEN", "Missing Bearer token.")
    token = authorization.split(None, 1)[1].strip()
    key, alg = _signing_config()
    try:
        claims = jwt.decode(
            token,
            key=key,
            algorithms=[alg],
            options={"require": ["exp", "sub"]},
        )
    except jwt.ExpiredSignatureError:
        raise _unauthorized("AUTH_TOKEN_EXPIRED", "Access token has expired.") from None
    except jwt.InvalidTokenError as exc:
        raise _unauthorized("AUTH_INVALID_TOKEN", f"Invalid token: {exc}") from exc

    scopes_raw = claims.get("scopes") or claims.get("scope") or ""
    scopes = (
        frozenset(scopes_raw.split())
        if isinstance(scopes_raw, str)
        else frozenset(scopes_raw)
    )
    return UserContext(
        user_id=str(claims["sub"]),
        scopes=scopes,
        raw_claims=claims,
    )


def require_scope(required: str):
    """Dependency factory enforcing a single scope on an endpoint."""

    async def _check(user: UserContext = Depends(verify_access_token)) -> UserContext:
        if required not in user.scopes:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=ErrorEnvelope(
                    code="AUTH_FORBIDDEN",
                    message=f"Scope {required!r} required.",
                ).model_dump(),
            )
        return user

    return _check


__all__ = ["UserContext", "require_scope", "verify_access_token"]
