import logging
import time
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Cookie, Depends, HTTPException, Request, status
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
logger = logging.getLogger("netdash")
AUTH_COOKIE_NAME = "netdash_session"
AUTH_COOKIE_LEGACY = "netdash_token"


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(subject: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    return jwt.encode({"sub": subject, "exp": expire}, settings.secret_key, algorithm=settings.algorithm)


def auth_cookie_max_age() -> int:
    return int(settings.access_token_expire_minutes) * 60


def auth_cookie_secure(request: Request) -> bool:
    forwarded_proto = (request.headers.get("x-forwarded-proto") or "").split(",")[0].strip().lower()
    if forwarded_proto:
        return forwarded_proto == "https"
    return request.url.scheme == "https"


def _cookie_secure(request: Request) -> bool:
    if not settings.cookie_secure:
        return False
    return auth_cookie_secure(request)


def set_auth_cookie(response, request: Request, token: str, *, username: str | None = None) -> None:
    secure = _cookie_secure(request)
    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=token,
        max_age=auth_cookie_max_age(),
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/",
    )
    # Drop legacy cookie name after login (migration from <= v1.3.85).
    response.delete_cookie(
        key=AUTH_COOKIE_LEGACY,
        path="/",
        httponly=True,
        secure=secure,
        samesite="lax",
    )
    if username:
        logger.info("Session cookie set for user %s (path=/, secure=%s)", username, secure)


def clear_auth_cookie(response, request: Request) -> None:
    secure = _cookie_secure(request)
    for name in (AUTH_COOKIE_NAME, AUTH_COOKIE_LEGACY):
        response.delete_cookie(
            key=name,
            path="/",
            httponly=True,
            secure=secure,
            samesite="lax",
        )


def _extract_bearer_token(request: Request) -> str | None:
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.lower().startswith("bearer "):
        return auth_header[7:].strip() or None
    return None


def _candidate_auth_tokens(
    request: Request,
    session_token: str | None,
    legacy_token: str | None,
) -> list[str]:
    """Bearer first — stale HttpOnly cookie must not block valid localStorage token (QNAP F5)."""
    seen: set[str] = set()
    out: list[str] = []
    for raw in (_extract_bearer_token(request), session_token, legacy_token):
        if raw and raw not in seen:
            seen.add(raw)
            out.append(raw)
    return out


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
    session_token: str | None = Cookie(default=None, alias=AUTH_COOKIE_NAME),
    legacy_token: str | None = Cookie(default=None, alias=AUTH_COOKIE_LEGACY),
) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Nieprawidłowe dane logowania",
        headers={"WWW-Authenticate": "Bearer"},
    )
    candidates = _candidate_auth_tokens(request, session_token, legacy_token)
    if not candidates:
        if request.url.path == "/api/auth/me":
            client = request.client.host if request.client else "?"
            logger.info("GET /api/auth/me: brak cookie sesji (client=%s)", client)
        raise credentials_error

    for token in candidates:
        try:
            payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
            username: str | None = payload.get("sub")
            if username is None:
                continue
        except jwt.PyJWTError:
            continue

        result = await db.execute(select(User).where(User.username == username))
        user = result.scalar_one_or_none()
        if user is not None:
            return user

    if request.url.path == "/api/auth/me":
        logger.info("GET /api/auth/me: nieprawidłowy lub wygasły token")
    raise credentials_error


# --- In-memory brute-force guard (per process; homelab single-instance) ---
LOGIN_MAX_ATTEMPTS = 5
LOGIN_WINDOW_SECONDS = 300.0
_LOGIN_FAILURES: dict[str, list[float]] = {}


def login_client_key(request: Request, username: str) -> str:
    ip = request.client.host if request.client else "?"
    return f"{ip}:{(username or '?').lower()}"


def _prune_failures(key: str, now: float) -> list[float]:
    fails = [t for t in _LOGIN_FAILURES.get(key, []) if now - t < LOGIN_WINDOW_SECONDS]
    if fails:
        _LOGIN_FAILURES[key] = fails
    else:
        _LOGIN_FAILURES.pop(key, None)
    return fails


def login_lockout_seconds(key: str) -> int:
    """Seconds the caller must wait before the next attempt, or 0 if not locked."""
    now = time.monotonic()
    fails = _prune_failures(key, now)
    if len(fails) >= LOGIN_MAX_ATTEMPTS:
        return max(1, int(LOGIN_WINDOW_SECONDS - (now - fails[0])))
    return 0


def register_failed_login(key: str) -> None:
    now = time.monotonic()
    fails = _prune_failures(key, now)
    fails.append(now)
    _LOGIN_FAILURES[key] = fails


def reset_login_attempts(key: str) -> None:
    _LOGIN_FAILURES.pop(key, None)
