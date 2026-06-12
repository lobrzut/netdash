import os
from datetime import datetime, timezone
from pathlib import Path

from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parent.parent
VERSION = "1.3.77"
DEFAULT_LISTEN_PORT = 18787
FORBIDDEN_LISTEN_PORT = 8787  # Readarr — never bind here
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


def resolve_listen_port() -> int:
    """Resolve HTTP listen port; ignore stale QNAP CS NETDASH_PORT=8787."""
    listen = os.environ.get("NETDASH_LISTEN_PORT", "").strip()
    if listen:
        return int(listen)

    legacy = os.environ.get("NETDASH_PORT", "").strip()
    if legacy:
        port = int(legacy)
        if port == FORBIDDEN_LISTEN_PORT:
            return DEFAULT_LISTEN_PORT
        return port

    return DEFAULT_LISTEN_PORT


class Settings(BaseSettings):
    secret_key: str = "CHANGE-ME-set-NETDASH_SECRET_KEY-in-env"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7
    database_url: str = f"sqlite+aiosqlite:///{DATA_DIR / 'netdash.db'}"
    scan_timeout: float = 0.8
    http_timeout: float = 3.0
    scan_concurrency: int = 80
    default_admin_user: str = "admin"
    default_admin_password: str = "changeme"
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

    class Config:
        env_prefix = "NETDASH_"

    @property
    def port(self) -> int:
        return resolve_listen_port()


settings = Settings()
