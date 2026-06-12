from datetime import datetime, timedelta, timezone

from fastapi import Cookie, Depends, HTTPException, Request, status
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
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


def set_auth_cookie(response, request: Request, token: str) -> None:
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
    token = session_token or legacy_token or _extract_bearer_token(request)
    if not token:
        raise credentials_error
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        username: str | None = payload.get("sub")
        if username is None:
            raise credentials_error
    except JWTError:
        raise credentials_error

    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if user is None:
        raise credentials_error
    return user
