import os
from datetime import datetime, timezone
from pathlib import Path

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parent.parent
VERSION = "1.3.105"
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
SECRET_FILE = DATA_DIR / ".secret"
SECRET_KEY_PLACEHOLDER = "CHANGE-ME-set-NETDASH_SECRET_KEY-in-env"


def _read_secret_file() -> str | None:
    try:
        if SECRET_FILE.is_file():
            key = SECRET_FILE.read_text(encoding="utf-8").strip()
            if len(key) >= 16:
                return key
    except OSError:
        pass
    return None


def _is_placeholder_secret(key: str | None) -> bool:
    normalized = (key or "").strip()
    return not normalized or normalized == SECRET_KEY_PLACEHOLDER


def _persist_secret_file(key: str) -> None:
    if _is_placeholder_secret(key) or len(key.strip()) < 16:
        return
    try:
        SECRET_FILE.parent.mkdir(parents=True, exist_ok=True)
        SECRET_FILE.write_text(key.strip(), encoding="utf-8")
        if hasattr(os, "chmod"):
            os.chmod(SECRET_FILE, 0o600)
    except OSError:
        pass


def resolve_listen_port() -> int:
    """Resolve HTTP listen port from NETDASH_LISTEN_PORT only (NETDASH_PORT ignored)."""
    listen = os.environ.get("NETDASH_LISTEN_PORT", "").strip()
    port = int(listen) if listen else DEFAULT_LISTEN_PORT
    if port == FORBIDDEN_LISTEN_PORT:
        return DEFAULT_LISTEN_PORT
    return port


class Settings(BaseSettings):
    secret_key: str = SECRET_KEY_PLACEHOLDER
    secret_key_from_file: bool = False
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7
    database_url: str = f"sqlite+aiosqlite:///{DATA_DIR / 'netdash.db'}"
    scan_timeout: float = 0.8
    http_timeout: float = 3.0
    scan_concurrency: int = 80
    # Weak homelab hardware (RPi, old PC, NAS, N100): gentler scan — ON by default everywhere
    scan_safe_mode: bool = True
    scan_safe_concurrency: int = 8
    scan_safe_max_hosts: int = 64
    scan_max_hosts: int = 256
    scan_batch_delay: float = 0.08
    scan_batch_size: int = 16
    scan_max_duration: float = 600.0
    scan_safe_max_duration: float = 300.0
    default_admin_user: str = "admin"
    default_admin_password: str = "changeme"
    # Sync admin password from NETDASH_DEFAULT_ADMIN_PASSWORD on every container start (homelab default)
    sync_admin_password: bool = True
    # One-time recovery on startup — remove env after login (see deploy/qnap/README.md)
    reset_admin_password: str | None = None
    # Override auto-detected /24 when running in Docker bridge (e.g. 192.168.1.0/24)
    scan_cidr: str | None = None
    # HttpOnly session cookie Secure flag — false for plain HTTP homelab (default).
    cookie_secure: bool = False
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

    @field_validator("default_admin_password", mode="before")
    @classmethod
    def _default_admin_password(cls, v: object) -> str:
        if v is None or (isinstance(v, str) and not v.strip()):
            return "changeme"
        return str(v).strip()

    @field_validator("default_admin_user", mode="before")
    @classmethod
    def _default_admin_user(cls, v: object) -> str:
        if v is None or (isinstance(v, str) and not v.strip()):
            return "admin"
        return str(v).strip()

    @field_validator("cookie_secure", mode="before")
    @classmethod
    def _cookie_secure(cls, v: object) -> bool:
        if v is None or (isinstance(v, str) and not v.strip()):
            return False
        if isinstance(v, str):
            return v.strip().lower() in ("true", "1", "yes", "on")
        return bool(v)

    @field_validator("scan_safe_mode", mode="before")
    @classmethod
    def _scan_safe_mode(cls, v: object) -> bool:
        if v is None or (isinstance(v, str) and not v.strip()):
            return True
        if isinstance(v, str):
            return v.strip().lower() in ("true", "1", "yes", "on")
        return bool(v)

    @field_validator("sync_admin_password", mode="before")
    @classmethod
    def _sync_admin_password(cls, v: object) -> bool:
        if v is None or (isinstance(v, str) and not v.strip()):
            return True
        if isinstance(v, str):
            return v.strip().lower() in ("true", "1", "yes", "on")
        return bool(v)

    @field_validator("secret_key", mode="before")
    @classmethod
    def _secret_key(cls, v: object) -> str:
        file_key = _read_secret_file()
        if file_key:
            return file_key
        if v is None or (isinstance(v, str) and not v.strip()):
            return SECRET_KEY_PLACEHOLDER
        return str(v).strip()

    @model_validator(mode="after")
    def _finalize_secret_key(self) -> "Settings":
        file_key = _read_secret_file()
        if file_key:
            self.secret_key = file_key
            self.secret_key_from_file = True
        elif not _is_placeholder_secret(self.secret_key):
            _persist_secret_file(self.secret_key)
        return self

    @property
    def port(self) -> int:
        return resolve_listen_port()

    @property
    def secret_key_configured(self) -> bool:
        return not _is_placeholder_secret(self.secret_key) and len((self.secret_key or "").strip()) >= 16

    @property
    def secret_key_stable(self) -> bool:
        return self.secret_key_from_file and SECRET_FILE.is_file()

    @property
    def effective_scan_concurrency(self) -> int:
        return self.scan_safe_concurrency if self.scan_safe_mode else self.scan_concurrency

    @property
    def effective_scan_max_hosts(self) -> int:
        return self.scan_safe_max_hosts if self.scan_safe_mode else self.scan_max_hosts

    @property
    def effective_scan_max_duration(self) -> float:
        return self.scan_safe_max_duration if self.scan_safe_mode else self.scan_max_duration

    @property
    def resource_profile(self) -> str:
        """Runtime scan intensity: safe (default) or normal (NETDASH_SCAN_SAFE_MODE=false)."""
        return "safe" if self.scan_safe_mode else "normal"

    @property
    def health_check_concurrency(self) -> int:
        return 6 if self.scan_safe_mode else 10


settings = Settings()
