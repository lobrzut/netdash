import os
from datetime import datetime, timezone
from pathlib import Path

from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parent.parent
VERSION = "1.3.22"
GITHUB_REPO = "https://github.com/lobrzut/netdash"


def _get_build_date() -> str:
    env = os.environ.get("NETDASH_BUILD_DATE", "").strip()
    if env:
        return env
    try:
        mtime = Path(__file__).stat().st_mtime
        return datetime.fromtimestamp(mtime, tz=timezone.utc).strftime("%Y-%m-%d")
    except OSError:
        return ""


BUILD_DATE = _get_build_date()
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)


class Settings(BaseSettings):
    secret_key: str = "CHANGE-ME-set-NETDASH_SECRET_KEY-in-env"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7
    database_url: str = f"sqlite+aiosqlite:///{DATA_DIR / 'netdash.db'}"
    scan_timeout: float = 0.8
    http_timeout: float = 3.0
    scan_concurrency: int = 80
    default_admin_user: str = "admin"
    default_admin_password: str = "CHANGE-ME-set-NETDASH_DEFAULT_ADMIN_PASSWORD"
    # Override auto-detected /24 when running in Docker bridge (e.g. 192.168.1.0/24)
    scan_cidr: str | None = None
    # Mask real LAN IP in /api/network (for README screenshots only)
    demo_mode: bool = False

    class Config:
        env_prefix = "NETDASH_"


settings = Settings()
