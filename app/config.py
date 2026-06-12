import os
from datetime import datetime, timezone
from pathlib import Path

from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parent.parent
VERSION = "1.3.73"
DEFAULT_PORT = 18787
GITHUB_REPO = "https://github.com/lobrzut/netdash"
GHCR_IMAGE = "ghcr.io/lobrzut/netdash"


def _get_build_date() -> str:
    env = os.environ.get("NETDASH_BUILD_DATE", "").strip()
    if env:
        return env
    try:
        import subprocess

        result = subprocess.run(
            ["git", "-C", str(BASE_DIR), "log", "-1", "--format=%cs"],
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except Exception:
        pass
    try:
        latest = 0.0
        app_dir = BASE_DIR / "app"
        if app_dir.is_dir():
            for path in app_dir.rglob("*"):
                if path.is_file():
                    latest = max(latest, path.stat().st_mtime)
        if latest:
            return datetime.fromtimestamp(latest, tz=timezone.utc).strftime("%Y-%m-%d")
    except OSError:
        pass
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
    # Optional in-container update apply (requires docker.sock mount — see docs/QNAP.md)
    update_apply_enabled: bool = False
    docker_image: str = GHCR_IMAGE
    docker_image_tag: str = "latest"
    container_name: str = "netdash"
    docker_socket: str = "/var/run/docker.sock"
    # Listen port (avoid 8787 — conflicts with Readarr in *arr homelabs)
    port: int = DEFAULT_PORT

    class Config:
        env_prefix = "NETDASH_"


settings = Settings()
