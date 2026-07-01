import asyncio
import logging
import re
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import Depends, FastAPI, File, HTTPException, Query, Request, Response, UploadFile, status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import (
    AUTH_COOKIE_LEGACY,
    AUTH_COOKIE_NAME,
    clear_auth_cookie,
    create_access_token,
    get_current_user,
    hash_password,
    login_client_key,
    login_lockout_seconds,
    register_failed_login,
    reset_login_attempts,
    set_auth_cookie,
    verify_password,
)
from app.config import BASE_DIR, BUILD_DATE, DATA_DIR, GITHUB_REPO, GHCR_IMAGE, VERSION, WHATS_NEW, settings
from app.discovery_runtime import set_app_discovery_enabled
from app.docker_update import (
    pull_and_restart,
    trigger_watchtower_update,
    update_apply_available,
    watchtower_update_available,
)
from app.updates import fetch_latest_release, is_newer_version, normalize_version
from app.database import Base, async_session, engine, get_db
from app.enrich import enrich_all_services, enrich_mac_addresses, enrich_service_icons, should_auto_wol
from app.health import check_all_services, effective_stale_remove_days, purge_stale_services
from app.homer_import import parse_homer_config
from app.models import DEFAULT_ABOUT_PROJECT, ApiKey, AppSettings, Note, ScanJob, Service, User
from app.vault import decrypt_secret, encrypt_secret, mask_secret
from app.url_utils import brain_dashboard_url, sanitize_service_url
from app.scanner import (
    expand_cidrs_for_safe_mode,
    validate_manual_scan_cidrs,
    DiscoveredService,
    ScanError,
    _fallback_service_name,
    build_local_host_service,
    format_cidr_list,
    get_default_gateway,
    get_detected_cidrs,
    get_local_ip,
    get_local_network,
    icmp_ping_available,
    is_http_error_name,
    is_likely_docker_bridge,
    normalize_scan_cidr_list,
    resolve_scan_cidrs,
    parse_host_scan_ports,
    scan_networks,
    suggest_service_identity,
)
from app.arp_scan import lookup_mac_for_ip, scan_arp_network
from app.arp_discovery import (
    get_arp_discovery_status,
    run_arp_discovery_cycle,
    start_arp_discovery_scheduler,
    stop_arp_discovery_scheduler,
)
_DISCOVERY_PIPELINE_AVAILABLE = True
try:
    from app.discovery_pipeline import (
        get_discovery_pipeline_status,
        run_discovery_cycle,
        start_discovery_scheduler,
        stop_discovery_scheduler,
    )
except ModuleNotFoundError:
    _DISCOVERY_PIPELINE_AVAILABLE = False

    async def stop_discovery_scheduler() -> None:
        return None

    async def run_discovery_cycle() -> int:
        return 0

    def start_discovery_scheduler() -> None:
        logging.getLogger("netdash").error(
            "discovery_pipeline module missing from image — adaptive discovery disabled; "
            "upgrade to ghcr.io/lobrzut/netdash:1.3.121+ or set NETDASH_DISCOVERY_MODE=arp"
        )

    def get_discovery_pipeline_status() -> dict:
        return {
            "enabled": False,
            "available": False,
            "mode": "adaptive",
            "last_error": "discovery_pipeline module missing from image — upgrade to v1.3.121+",
        }
from app.wol import normalize_mac, send_magic_packet
from app.discovery_import import import_discovery_hosts
from app.schemas import (
    BACKUP_FORMAT,
    BACKUP_FORMAT_VERSION,
    ApiKeyCreate,
    ApiKeyOut,
    ApiKeyReveal,
    ApiKeyUpdate,
    AppSettingsOut,
    AppSettingsUpdate,
    SettingsBackupApiKey,
    SettingsBackupNote,
    SettingsBackupOut,
    SettingsBackupService,
    SettingsImportRequest,
    ArpDeviceOut,
    ArpLookupOut,
    ArpScanRequest,
    DiscoveryImportRequest,
    DiscoveryImportResult,
    HomerImportResult,
    LoginRequest,
    PasswordChangeRequest,
    NetworkDiagnostics,
    NetworkInfo,
    NoteCreate,
    NoteOut,
    NoteUpdate,
    PowerActionResult,
    ScanRequest,
    ScanStatus,
    ScanUiAttemptRequest,
    ServiceCreate,
    ServiceIdentifyRequest,
    IconUploadResponse,
    ServiceIdentifyResponse,
    ServiceIdentifySuggestion,
    ServiceOut,
    ServiceUpdate,
    Token,
    UpdateApplyOut,
    UpdateCheckOut,
    UserMe,
)

scan_tasks: dict[int, asyncio.Task] = {}
health_task: asyncio.Task | None = None
logger = logging.getLogger("netdash")

UPLOADS_DIR = DATA_DIR / "uploads"
ICONS_DIR = UPLOADS_DIR / "icons"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
ICONS_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_IMAGE_TYPES = {
    "image/png": ".png",
    "image/svg+xml": ".svg",
    "image/webp": ".webp",
    "image/jpeg": ".jpg",
    "image/gif": ".gif",
}
IMAGE_EXT_BY_SUFFIX = {".png", ".svg", ".webp", ".jpg", ".jpeg", ".gif"}
ALLOWED_ICON_TYPES = {k: v for k, v in ALLOWED_IMAGE_TYPES.items() if k != "image/gif"}
ICON_EXT_BY_SUFFIX = IMAGE_EXT_BY_SUFFIX - {".gif"}
MAX_LOGO_SIZE = 2 * 1024 * 1024
MAX_ICON_SIZE = 2 * 1024 * 1024

PHASE_LABELS = {
    "ping": "Wykrywanie aktywnych hostów",
    "ports": "Skanowanie portów",
    "identify": "Identyfikacja serwisów",
}


def _sanitize_custom_css(css: str | None) -> str | None:
    if not css:
        return None
    cleaned = re.sub(r"(?is)<\s*script[^>]*>.*?<\s*/\s*script\s*>", "", css)
    cleaned = re.sub(r"(?is)@import\s+[^;]+;?", "", cleaned)
    cleaned = re.sub(r"(?i)javascript\s*:", "", cleaned)
    cleaned = re.sub(r"(?i)expression\s*\(", "", cleaned)
    return cleaned.strip() or None


def _migrate_db(sync_conn):
    from sqlalchemy import inspect, text

    inspector = inspect(sync_conn)
    tables = inspector.get_table_names()

    if "scan_jobs" in tables:
        columns = {col["name"] for col in inspector.get_columns("scan_jobs")}
        for name, ddl in [
            ("progress_phase", "VARCHAR(32) DEFAULT ''"),
            ("progress_current", "INTEGER DEFAULT 0"),
            ("progress_total", "INTEGER DEFAULT 0"),
            ("error_message", "VARCHAR(512)"),
        ]:
            if name not in columns:
                sync_conn.execute(text(f"ALTER TABLE scan_jobs ADD COLUMN {name} {ddl}"))

    if "services" in tables:
        columns = {col["name"] for col in inspector.get_columns("services")}
        if "has_login" not in columns:
            sync_conn.execute(text("ALTER TABLE services ADD COLUMN has_login BOOLEAN DEFAULT 0"))
        if "icon_url" not in columns:
            sync_conn.execute(text("ALTER TABLE services ADD COLUMN icon_url VARCHAR(512)"))
        service_migrations = [
            ("is_online", "BOOLEAN DEFAULT 1"),
            ("health_fail_streak", "INTEGER DEFAULT 0"),
            ("health_detail", "VARCHAR(128)"),
            ("last_checked", "DATETIME"),
            ("service_notes", "TEXT"),
            ("mac_address", "VARCHAR(17)"),
            ("wol_enabled", "BOOLEAN DEFAULT 0"),
            ("wol_port", "INTEGER"),
            ("sol_port", "INTEGER"),
            ("broadcast_ip", "VARCHAR(64)"),
        ]
        for name, ddl in service_migrations:
            if name not in columns:
                sync_conn.execute(text(f"ALTER TABLE services ADD COLUMN {name} {ddl}"))
        if "customized" not in columns:
            sync_conn.execute(text("ALTER TABLE services ADD COLUMN customized BOOLEAN DEFAULT 0"))

    if "app_settings" in tables:
        columns = {col["name"] for col in inspector.get_columns("app_settings")}
        settings_migrations = [
            ("theme", "VARCHAR(16) DEFAULT 'midnight'"),
            ("language", "VARCHAR(8) DEFAULT 'pl'"),
            ("author_name", "VARCHAR(64) DEFAULT 'lobrzut'"),
            ("author_bio", "TEXT DEFAULT ''"),
            ("author_url", "VARCHAR(256) DEFAULT ''"),
            ("about_project", "TEXT DEFAULT ''"),
            ("footer_text", "VARCHAR(256) DEFAULT ''"),
            ("scan_cidr_default", "VARCHAR(64)"),
            ("full_scan_default", "BOOLEAN DEFAULT 0"),
            ("host_scan_ports", "VARCHAR(128) DEFAULT '22,445,3389,5900'"),
            ("host_only_entries", "BOOLEAN DEFAULT 1"),
            ("show_vault", "BOOLEAN DEFAULT 1"),
            ("show_notes", "BOOLEAN DEFAULT 1"),
            ("show_about", "BOOLEAN DEFAULT 0"),
            ("show_clock", "BOOLEAN DEFAULT 1"),
            ("show_stats", "BOOLEAN DEFAULT 1"),
            ("services_columns", "VARCHAR(16) DEFAULT 'normal'"),
            ("show_category_filters", "BOOLEAN DEFAULT 1"),
            ("show_service_urls", "BOOLEAN DEFAULT 1"),
            ("show_ports", "BOOLEAN DEFAULT 1"),
            ("services_grouped", "BOOLEAN DEFAULT 1"),
            ("default_access_filter", "VARCHAR(16) DEFAULT 'all'"),
            ("card_style", "VARCHAR(16) DEFAULT 'detailed'"),
            ("pinned_card_size", "VARCHAR(16) DEFAULT 'medium'"),
            ("custom_css", "TEXT"),
            ("favicon_url", "VARCHAR(512)"),
            ("use_custom_logo", "BOOLEAN DEFAULT 0"),
            ("custom_logo_url", "VARCHAR(512)"),
            ("wol_broadcast_ip", "VARCHAR(64) DEFAULT '255.255.255.255'"),
            ("wol_port", "INTEGER DEFAULT 9"),
            ("sol_port", "INTEGER DEFAULT 9"),
            ("arp_scan_enabled", "BOOLEAN DEFAULT 1"),
            ("health_check_enabled", "BOOLEAN DEFAULT 1"),
            ("health_check_interval", "INTEGER DEFAULT 60"),
            ("gptwol_url", "VARCHAR(256)"),
            ("stale_remove_days", "INTEGER DEFAULT 0"),
            ("discovery_enabled", "BOOLEAN DEFAULT 1"),
            ("discovery_last_import_at", "DATETIME"),
            ("discovery_last_import_source", "VARCHAR(128)"),
            ("discovery_last_import_hosts", "INTEGER"),
            ("admin_password_user_set", "BOOLEAN DEFAULT 0"),
            ("show_brain", "BOOLEAN DEFAULT 0"),
            ("brain_stats_url", "VARCHAR(256)"),
            ("show_network", "BOOLEAN DEFAULT 0"),
        ]
        for name, ddl in settings_migrations:
            if name not in columns:
                sync_conn.execute(text(f"ALTER TABLE app_settings ADD COLUMN {name} {ddl}"))


async def _get_or_create_settings(db: AsyncSession) -> AppSettings:
    result = await db.execute(select(AppSettings).limit(1))
    app_settings = result.scalar_one_or_none()
    if app_settings is None:
        scan_default = normalize_scan_cidr_list(settings.scan_cidr) if settings.scan_cidr else None
        app_settings = AppSettings(
            about_project=DEFAULT_ABOUT_PROJECT,
            scan_cidr_default=scan_default,
            stale_remove_days=max(0, settings.stale_remove_days),
        )
        db.add(app_settings)
        await db.commit()
        await db.refresh(app_settings)
    else:
        changed = False
        if not app_settings.about_project:
            app_settings.about_project = DEFAULT_ABOUT_PROJECT
            changed = True
        layout = app_settings.pinned_card_size
        if layout in ("large", None, ""):
            app_settings.pinned_card_size = "classic"
            changed = True
        elif layout == "normal":
            app_settings.pinned_card_size = "medium"
            changed = True
        elif layout == "compact":
            pass
        elif layout not in ("classic", "classic-sm", "medium", "compact", "compact-big"):
            app_settings.pinned_card_size = "medium"
            changed = True
        if not app_settings.scan_cidr_default and settings.scan_cidr:
            app_settings.scan_cidr_default = normalize_scan_cidr_list(settings.scan_cidr)
            changed = True
        if changed:
            await db.commit()
            await db.refresh(app_settings)
    _sync_discovery_runtime_from_db(app_settings)
    return app_settings


def _sync_discovery_runtime_from_db(app_settings: AppSettings) -> None:
    set_app_discovery_enabled(app_settings.discovery_enabled)


def _settings_to_out(app_settings: AppSettings) -> AppSettingsOut:
    out = AppSettingsOut.model_validate(app_settings)
    return out.model_copy(
        update={
            "discovery_env_locked": settings.discovery_env_locked,
            "discovery_effective": settings.effective_discovery_enabled,
        }
    )


async def _apply_discovery_schedulers() -> None:
    """Start/stop background discovery after a runtime settings change (no restart)."""
    if not settings.effective_discovery_enabled:
        await stop_discovery_scheduler()
        await stop_arp_discovery_scheduler()
        return
    if settings.adaptive_discovery_enabled:
        await stop_arp_discovery_scheduler()
        start_discovery_scheduler()
    elif settings.arp_discovery_enabled:
        await stop_discovery_scheduler()
        start_arp_discovery_scheduler()


async def _ensure_local_host_service() -> None:
    """Register this machine as a device card even when ping-to-self fails on Windows."""
    item = build_local_host_service()
    await _upsert_service(item)
    async with async_session() as db:
        result = await db.execute(select(Service).where(Service.protocol == "host"))
        changed = False
        for svc in result.scalars():
            if svc.url.startswith("host://"):
                svc.url = "#"
                changed = True
        if changed:
            await db.commit()


async def _sanitize_stored_urls() -> None:
    """Fix URLs corrupted with Python bytes repr (e.g. ?b'next=%2F')."""
    async with async_session() as db:
        result = await db.execute(select(Service))
        changed = False
        for svc in result.scalars().all():
            clean = sanitize_service_url(svc.url)
            if clean and svc.url != clean:
                svc.url = clean
                changed = True
        if changed:
            await db.commit()


async def _admin_password_user_set(db: AsyncSession) -> bool:
    """True once the admin changed their password in-app — env sync must not clobber it."""
    try:
        result = await db.execute(select(AppSettings.admin_password_user_set).limit(1))
        return bool(result.scalar_one_or_none())
    except Exception:
        return False


async def _sync_admin_password_from_env(db: AsyncSession) -> dict[str, object]:
    """Homelab post-deploy login: ensure admin exists and password matches settings on start."""
    username = settings.default_admin_user
    password = settings.default_admin_password
    status: dict[str, object] = {
        "username": username,
        "sync_enabled": settings.sync_admin_password,
        "admin_exists": False,
        "password_synced": False,
        "password_matches": False,
    }
    if not settings.sync_admin_password:
        result = await db.execute(select(User).where(func.lower(User.username) == username.lower()))
        user = result.scalar_one_or_none()
        status["admin_exists"] = user is not None
        if user and verify_password(password, user.password_hash):
            status["password_matches"] = True
        return status

    result = await db.execute(select(User).where(func.lower(User.username) == username.lower()))
    user = result.scalar_one_or_none()
    if user is None:
        db.add(User(username=username, password_hash=hash_password(password)))
        await db.commit()
        status["admin_exists"] = True
        status["password_synced"] = True
        status["password_matches"] = True
        logger.info(
            "Admin user %r created with default password (change in Settings after login)",
            username,
        )
        return status

    status["admin_exists"] = True
    if verify_password(password, user.password_hash):
        status["password_matches"] = True
        return status

    if await _admin_password_user_set(db):
        status["user_managed"] = True
        logger.info(
            "Admin password changed in-app for %r — skipping env sync "
            "(use NETDASH_RESET_ADMIN_PASSWORD to override)",
            username,
        )
        return status

    user.password_hash = hash_password(password)
    await db.commit()
    status["password_synced"] = True
    status["password_matches"] = True
    logger.info(
        "Admin password synced to default for %r (change in Settings after login)",
        username,
    )
    return status


async def _admin_ready(db: AsyncSession) -> bool:
    """True when default admin exists and password matches configured default (if sync enabled)."""
    username = settings.default_admin_user
    password = settings.default_admin_password
    result = await db.execute(select(User).where(func.lower(User.username) == username.lower()))
    user = result.scalar_one_or_none()
    if user is None:
        return False
    if settings.sync_admin_password:
        return verify_password(password, user.password_hash)
    return True


def _log_admin_startup_status(status: dict[str, object], ready: bool) -> None:
    logger.info(
        "Admin bootstrap: user=%r exists=%s sync_enabled=%s password_synced=%s password_matches=%s admin_ready=%s",
        status.get("username"),
        status.get("admin_exists"),
        status.get("sync_enabled"),
        status.get("password_synced"),
        status.get("password_matches"),
        ready,
    )
    if not settings.secret_key_configured:
        logger.warning(
            "NETDASH_SECRET_KEY is missing or too short — sessions may fail; "
            "set NETDASH_SECRET_KEY or rely on entrypoint auto-generation in /app/data/.secret",
        )
    if (
        settings.sync_admin_password
        and settings.default_admin_password == "changeme"
        and not status.get("user_managed")
    ):
        logger.warning(
            "SECURITY: admin password is the default 'changeme' with sync enabled — "
            "set NETDASH_DEFAULT_ADMIN_PASSWORD to a strong value (reachable on host network).",
        )


async def _maybe_reset_admin_password(db: AsyncSession) -> None:
    """One-time homelab recovery: NETDASH_RESET_ADMIN_PASSWORD on next start (remove env after)."""
    new_password = (settings.reset_admin_password or "").strip()
    if not new_password:
        return
    result = await db.execute(select(User).where(User.username == settings.default_admin_user))
    user = result.scalar_one_or_none()
    if user is None:
        logger.warning(
            "NETDASH_RESET_ADMIN_PASSWORD set but user %r not found — skipping",
            settings.default_admin_user,
        )
        return
    user.password_hash = hash_password(new_password)
    await db.commit()
    logger.warning(
        "Admin password reset for %r via NETDASH_RESET_ADMIN_PASSWORD — remove env var after login",
        settings.default_admin_user,
    )


async def _maybe_seed_demo(db: AsyncSession) -> None:
    """Seed example services on a fresh DB when NETDASH_SEED_DEMO=true (opt-in)."""
    if not settings.seed_demo:
        return
    result = await db.execute(select(func.count()).select_from(Service))
    if (result.scalar_one() or 0) > 0:
        return
    try:
        from scripts.seed_demo_data import DEMO_KEYS, DEMO_NOTES, DEMO_SERVICES
    except Exception:
        logger.warning("NETDASH_SEED_DEMO set but demo data could not be imported")
        return
    for svc in DEMO_SERVICES:
        db.add(Service(**svc))
    for key in DEMO_KEYS:
        secret = key["secret"]
        db.add(
            ApiKey(
                name=key["name"],
                secret_encrypted=encrypt_secret(secret),
                secret_hint=secret[-4:] if len(secret) >= 4 else secret,
                service=key["service"],
                username=key.get("username"),
                notes=key.get("notes"),
                pinned=key.get("pinned", False),
            )
        )
    for note in DEMO_NOTES:
        db.add(Note(**note))
    await db.commit()
    logger.info(
        "Seeded %s demo services (NETDASH_SEED_DEMO) — remove with scripts/cleanup_demo_data.py --apply",
        len(DEMO_SERVICES),
    )


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_migrate_db)

    async with async_session() as db:
        admin_status = await _sync_admin_password_from_env(db)
        result = await db.execute(select(func.count()).select_from(User))
        if (result.scalar_one() or 0) == 0:
            db.add(
                User(
                    username=settings.default_admin_user,
                    password_hash=hash_password(settings.default_admin_password),
                )
            )
            await db.commit()
            admin_status["admin_exists"] = True
            admin_status["password_matches"] = True
        await _maybe_reset_admin_password(db)
        await _get_or_create_settings(db)
        await _maybe_seed_demo(db)
        _log_admin_startup_status(admin_status, await _admin_ready(db))

    await _ensure_local_host_service()
    await _sanitize_stored_urls()
    await _cancel_stale_scan_jobs()


async def _deferred_startup_enrich():
    """MAC/icon enrichment can ping 100+ hosts — run after portal is up."""
    if not settings.effective_startup_enrich_enabled:
        logger.info("Startup enrich skipped (NETDASH_STARTUP_ENRICH_ENABLED=false or discovery off)")
        return
    await asyncio.sleep(5)
    try:
        mac_count = await enrich_mac_addresses()
        svc_count = await enrich_all_services()
        icon_count = await enrich_service_icons(limit=150)
        logger.info(
            "Startup enrich completed (%s MAC, %s metadata, %s icons)",
            mac_count,
            svc_count,
            icon_count,
        )
    except Exception:
        logger.exception("Startup enrich failed")


async def _cancel_stale_scan_jobs() -> None:
    """Mark in-flight scan jobs failed after container restart (in-memory tasks are gone)."""
    async with async_session() as db:
        result = await db.execute(select(ScanJob).where(ScanJob.status.in_(["running", "pending"])))
        jobs = result.scalars().all()
        if not jobs:
            return
        now = datetime.now(timezone.utc)
        for job in jobs:
            job.status = "failed"
            job.error_message = "Skan przerwany — restart kontenera. Uruchom skan ponownie."
            job.finished_at = now
        await db.commit()
        logger.info("Marked %s stale scan job(s) as failed after restart", len(jobs))


def _scan_in_progress() -> bool:
    return any(not t.done() for t in scan_tasks.values())


async def _health_check_loop():
    interval = 60
    first_pass = True
    defer_secs = settings.effective_startup_health_defer_seconds if settings.effective_startup_health_defer else 0
    if defer_secs:
        logger.info("Startup health check deferred %ss (background)", defer_secs)
        await asyncio.sleep(defer_secs)
    while True:
        try:
            async with async_session() as db:
                settings_row = await _get_or_create_settings(db)
                interval = max(15, min(900, settings_row.health_check_interval or 60))
                enabled = settings_row.health_check_enabled
                stale_days = effective_stale_remove_days(settings_row.stale_remove_days or 0)
            if not _scan_in_progress():
                if enabled:
                    async with async_session() as db:
                        count = await check_all_services(db)
                        if first_pass and defer_secs:
                            logger.info(
                                "Startup health check completed for %s services (after %ss)",
                                count,
                                defer_secs,
                            )
                        else:
                            logger.info("Health check completed for %s services", count)
                if stale_days > 0:
                    async with async_session() as db:
                        removed = await purge_stale_services(db, stale_days)
                        if removed:
                            logger.info("Stale service purge removed %s entries", removed)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Health check loop error")
            interval = 60
        first_pass = False
        await asyncio.sleep(interval)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global health_task
    boot_t0 = time.monotonic()
    await init_db()
    logger.info("Database ready in %.1fs — accepting traffic", time.monotonic() - boot_t0)
    asyncio.create_task(_deferred_startup_enrich())
    health_task = asyncio.create_task(_health_check_loop())
    if settings.adaptive_discovery_enabled:
        if _DISCOVERY_PIPELINE_AVAILABLE:
            start_discovery_scheduler()
        else:
            logger.warning(
                "discovery_pipeline missing — falling back to ARP discovery scheduler (upgrade image for adaptive mode)"
            )
            start_arp_discovery_scheduler()
    elif settings.arp_discovery_enabled:
        start_arp_discovery_scheduler()
    yield
    await stop_discovery_scheduler()
    await stop_arp_discovery_scheduler()
    if health_task:
        health_task.cancel()
        try:
            await health_task
        except asyncio.CancelledError:
            pass
    for task in scan_tasks.values():
        task.cancel()


app = FastAPI(
    title="NetDash",
    description="Dashboard sieci z auto-wykrywaniem serwisów",
    lifespan=lifespan,
    # Swagger/OpenAPI off by default — avoid API-schema disclosure on host network.
    docs_url="/docs" if settings.docs_enabled else None,
    redoc_url="/redoc" if settings.docs_enabled else None,
    openapi_url="/openapi.json" if settings.docs_enabled else None,
)
app.mount("/static", StaticFiles(directory=BASE_DIR / "app" / "static"), name="static")
app.mount("/uploads", StaticFiles(directory=UPLOADS_DIR), name="uploads")

_STATIC_NO_CACHE = frozenset({"/static/app.js", "/static/i18n.js", "/static/style.css"})


@app.middleware("http")
async def static_no_cache_middleware(request: Request, call_next):
    response = await call_next(request)
    if request.url.path in _STATIC_NO_CACHE or request.url.path.startswith("/static/i18n/"):
        response.headers["Cache-Control"] = "no-cache, must-revalidate"
        response.headers["Pragma"] = "no-cache"
    return response


@app.get("/")
async def index():
    return FileResponse(
        BASE_DIR / "app" / "static" / "index.html",
        headers={"Cache-Control": "no-cache, must-revalidate"},
    )


def _watchtower_poll_hours() -> int | None:
    if not settings.watchtower_enabled:
        return None
    return max(1, round(settings.watchtower_poll_interval / 3600))


@app.get("/api/health")
async def health(db: AsyncSession = Depends(get_db)):
    app_settings = await _get_or_create_settings(db)
    return {
        "ok": True,
        "version": VERSION,
        "whats_new": WHATS_NEW,
        "build_date": BUILD_DATE or None,
        "github": GITHUB_REPO,
        "ghcr_image": GHCR_IMAGE,
        "update_apply_available": update_apply_available(),
        "watchtower_enabled": settings.watchtower_enabled,
        "watchtower_poll_hours": _watchtower_poll_hours(),
        "admin_ready": await _admin_ready(db),
        "admin_user": settings.default_admin_user,
        "sync_admin_password": settings.sync_admin_password,
        "secret_key_configured": settings.secret_key_configured,
        "secret_key_stable": settings.secret_key_stable,
        "scan_safe_mode": settings.scan_safe_mode,
        "scan_disabled": settings.scan_disabled,
        "startup_health_defer": settings.effective_startup_health_defer,
        "startup_health_defer_seconds": settings.effective_startup_health_defer_seconds,
        "discovery_startup_delay": settings.effective_discovery_startup_delay,
        "discovery_enabled": settings.effective_discovery_enabled,
        "discovery_env_locked": settings.discovery_env_locked,
        "startup_enrich_enabled": settings.effective_startup_enrich_enabled,
        "weak_dual_chunk": settings.weak_dual_chunk,
        "discovery_mode": settings.effective_discovery_mode,
        "resource_profile": settings.resource_profile,
        "scan_safe_min_prefix": settings.scan_safe_min_prefix,
        "scan_max_hosts": settings.effective_scan_max_hosts,
        "scan_chunk_size": settings.effective_scan_batch_size,
        "auto_discovery_all_ports": settings.auto_discovery_all_ports,
        "auto_discovery_always_chunk": settings.auto_discovery_always_chunk,
        "manual_scan_max_hosts": settings.manual_scan_max_hosts,
        "manual_scan_warn_prefix": settings.manual_scan_warn_prefix,
        "discovery_last_import_at": app_settings.discovery_last_import_at,
        "discovery_last_import_source": app_settings.discovery_last_import_source,
        "discovery_last_import_hosts": app_settings.discovery_last_import_hosts,
        "adaptive_discovery": get_discovery_pipeline_status() if settings.adaptive_discovery_enabled else None,
        "arp_discovery": get_arp_discovery_status() if settings.arp_discovery_enabled else None,
    }


@app.get("/api/updates/check", response_model=UpdateCheckOut)
async def check_updates(_: User = Depends(get_current_user)):
    current = normalize_version(VERSION)
    payload = UpdateCheckOut(
        current_version=current,
        github_repo=GITHUB_REPO,
        update_apply_available=update_apply_available(),
        watchtower_enabled=settings.watchtower_enabled,
        watchtower_poll_hours=_watchtower_poll_hours(),
    )
    try:
        release = await fetch_latest_release()
        latest = release.get("latest_version")
        payload.latest_version = latest
        payload.release_url = release.get("release_url")
        payload.release_notes = release.get("release_notes")
        payload.published_at = release.get("published_at")
        if latest:
            payload.update_available = is_newer_version(current, latest)
    except httpx.HTTPError as exc:
        payload.error = f"GitHub API: {exc}"
    except Exception as exc:
        payload.error = str(exc)
    return payload


@app.post("/api/updates/apply", response_model=UpdateApplyOut)
async def apply_update(_: User = Depends(get_current_user)):
    if not update_apply_available():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Aktualizacja z portalu wymaga docker.sock — bez niego użyj Watchtower lub ręcznego pull obrazu",
        )
    image = f"{settings.docker_image}:{settings.docker_image_tag}"
    if watchtower_update_available():
        try:
            await trigger_watchtower_update()
        except Exception as exc:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
        return UpdateApplyOut(
            ok=True,
            message="Zlecono aktualizację Watchtowerowi — pobierze nowy obraz i zrestartuje panel. Odśwież za chwilę.",
            image=image,
            container=settings.container_name,
        )
    try:
        result = await pull_and_restart(image, settings.container_name)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    return UpdateApplyOut(
        ok=True,
        message="Pobrano obraz i zrestartowano kontener. Odśwież stronę za chwilę.",
        image=result.get("image"),
        container=result.get("container"),
    )


@app.post("/api/auth/login", response_model=Token)
async def login(
    data: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    username = (data.username or "").strip()
    key = login_client_key(request, username)
    locked = login_lockout_seconds(key)
    if locked:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Zbyt wiele nieudanych prób logowania. Spróbuj ponownie za {locked}s.",
            headers={"Retry-After": str(locked)},
        )
    result = await db.execute(select(User).where(func.lower(User.username) == username.lower()))
    user = result.scalar_one_or_none()
    if not username or not user or not verify_password(data.password, user.password_hash):
        register_failed_login(key)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Błędny login lub hasło")
    reset_login_attempts(key)
    access_token = create_access_token(user.username)
    set_auth_cookie(response, request, access_token, username=user.username)
    return Token(access_token=access_token)


@app.post("/api/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(request: Request, response: Response):
    clear_auth_cookie(response, request)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get("/api/auth/me", response_model=UserMe)
async def auth_me(request: Request, response: Response, user: User = Depends(get_current_user)):
    access_token = create_access_token(user.username)
    set_auth_cookie(response, request, access_token, username=user.username)
    had_cookie = bool(request.cookies.get(AUTH_COOKIE_NAME) or request.cookies.get(AUTH_COOKIE_LEGACY))
    had_bearer = (request.headers.get("Authorization") or "").lower().startswith("bearer ")
    client = request.client.host if request.client else "?"
    logger.info(
        "GET /api/auth/me OK user=%s client=%s cookie=%s bearer=%s",
        user.username,
        client,
        had_cookie,
        had_bearer,
    )
    return UserMe(username=user.username, access_token=access_token)


@app.patch("/api/auth/password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    data: PasswordChangeRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not verify_password(data.current_password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Błędne aktualne hasło")
    user.password_hash = hash_password(data.new_password)
    # Mark password as user-managed so env sync won't revert it on the next restart.
    app_settings = await _get_or_create_settings(db)
    app_settings.admin_password_user_set = True
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get("/api/network", response_model=NetworkInfo)
async def network_info(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    if settings.demo_mode:
        return NetworkInfo(
            local_network="10.0.0.0/24",
            local_ip="10.0.0.5",
            docker_bridge=False,
            scan_cidr_configured=True,
            ping_available=True,
            scan_safe_mode=settings.scan_safe_mode,
            resource_profile=settings.resource_profile,
            detected_cidrs=["10.0.0.0/24", "10.0.0.0/28"],
            env_scan_cidr=None,
            scan_safe_min_prefix=settings.scan_safe_min_prefix,
            scan_max_hosts=settings.effective_scan_max_hosts,
            scan_chunk_size=settings.effective_scan_batch_size,
        )
    app_settings = await _get_or_create_settings(db)
    ping_ok = await icmp_ping_available()
    env_cidr = settings.scan_cidr.strip() if settings.scan_cidr else None
    adaptive = get_discovery_pipeline_status() if settings.adaptive_discovery_enabled else None
    arp = get_arp_discovery_status() if settings.arp_discovery_enabled else None
    auto_status = adaptive or arp
    return NetworkInfo(
        local_network=get_local_network(),
        local_ip=get_local_ip(),
        docker_bridge=is_likely_docker_bridge(),
        scan_cidr_configured=bool(env_cidr or app_settings.scan_cidr_default),
        ping_available=ping_ok,
        scan_safe_mode=settings.scan_safe_mode,
        scan_disabled=settings.scan_disabled,
        discovery_enabled=settings.effective_discovery_enabled,
        discovery_mode=settings.effective_discovery_mode,
        resource_profile=settings.resource_profile,
        detected_cidrs=get_detected_cidrs(app_settings.scan_cidr_default),
        env_scan_cidr=env_cidr,
        scan_safe_min_prefix=settings.scan_safe_min_prefix,
        scan_max_hosts=settings.effective_scan_max_hosts,
        scan_chunk_size=settings.effective_scan_batch_size,
        manual_scan_max_hosts=settings.manual_scan_max_hosts,
        manual_scan_warn_prefix=settings.manual_scan_warn_prefix,
        auto_discovery_all_ports=settings.auto_discovery_all_ports,
        discovery_last_import_at=app_settings.discovery_last_import_at,
        discovery_last_import_source=app_settings.discovery_last_import_source,
        discovery_last_import_hosts=app_settings.discovery_last_import_hosts,
        discovery_profile=(adaptive or {}).get("profile") if adaptive else None,
        discovery_status_line=(auto_status or {}).get("last_status_line"),
        discovery_current_tier=(auto_status or {}).get("current_tier"),
        discovery_interval_sec=(auto_status or {}).get("interval_sec"),
        discovery_chunk_index=(adaptive or {}).get("chunk_index"),
        discovery_chunk_index_secondary=(adaptive or {}).get("chunk_index_secondary"),
        discovery_chunk_total=(adaptive or {}).get("chunk_total"),
        discovery_services_found=((adaptive or {}).get("last_tiers") or {}).get("services"),
        discovery_method=(adaptive or {}).get("discovery_method"),
        arp_interval_sec=settings.arp_interval if settings.arp_discovery_enabled else None,
        arp_last_cycle_at=(auto_status or {}).get("last_cycle_at"),
        arp_last_cycle_hosts=(auto_status or {}).get("last_cycle_hosts"),
    )


async def _build_network_diagnostics(db: AsyncSession) -> NetworkDiagnostics:
    app_settings = await _get_or_create_settings(db)
    ping_ok = await icmp_ping_available()
    docker_br = is_likely_docker_bridge()
    try:
        resolved = resolve_scan_cidrs(None, app_settings.scan_cidr_default)
    except ValueError:
        resolved = []
    env_cidr = settings.scan_cidr.strip() if settings.scan_cidr else None
    settings_cidr = app_settings.scan_cidr_default or None
    scan_ready = bool(resolved) and (not docker_br or bool(env_cidr or settings_cidr))
    hints: list[str] = []
    if settings.adaptive_discovery_enabled:
        disc = get_discovery_pipeline_status()
        line = disc.get("last_status_line")
        if line:
            hints.append(f"Discovery TCP-first — {line}")
        elif disc.get("current_tier"):
            hints.append(
                f"Skan TCP w toku (tier: {disc.get('current_tier')}, profil: {disc.get('profile')})."
            )
        else:
            hints.append(
                "Discovery TCP-first — pierwszy cykl w toku. Ustaw CIDR w Ustawienia → Skanowanie. "
                "Wymaga network_mode: host."
            )
    elif settings.arp_discovery_enabled:
        arp = get_arp_discovery_status()
        if arp.get("last_cycle_at"):
            hints.append(
                f"Skan ARP aktywny — ostatni cykl wykrył {arp.get('last_cycle_hosts', 0)} hostów. "
                "Pełny skan TCP tylko w Opcje skanu (zaawansowane)."
            )
        else:
            hints.append(
                "Skan ARP aktywny — pierwszy cykl w toku (jak WatchYourLAN / Pi.Alert). "
                "Wymaga network_mode: host i cap_add: NET_RAW."
            )
    elif settings.scan_disabled:
        hints.append(
            "Lokalny skan wyłączony — opcjonalny agent zdalny (deploy/agent) na innym hoście LAN."
        )
    elif docker_br:
        hints.append(
            "Kontener w sieci Docker (bridge) — wymagany NETDASH_SCAN_CIDR lub CIDR w Ustawienia → Skanowanie."
        )
    if not ping_ok:
        hints.append("Ping ICMP niedostępny (typowe w Dockerze) — skan użyje TCP discovery.")
    if not resolved:
        hints.append("Brak CIDR — ustaw NETDASH_SCAN_CIDR w compose lub Domyślne sieci w ustawieniach.")
    elif scan_ready:
        hints.append("Skan gotowy — użyj Serwisy → Skanuj sieć.")
    return NetworkDiagnostics(
        local_network=get_local_network(),
        local_ip=get_local_ip(),
        docker_bridge=docker_br,
        ping_available=ping_ok,
        scan_cidr_env=env_cidr,
        scan_cidr_settings=settings_cidr,
        resolved_cidrs=resolved,
        scan_ready=scan_ready,
        hint=" ".join(hints),
    )


@app.post("/api/network/scan-test", response_model=NetworkDiagnostics)
async def network_scan_test(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    diag = await _build_network_diagnostics(db)
    logger.info(
        "POST /api/network/scan-test user=%s ping=%s docker_bridge=%s cidr_env=%s resolved=%s ready=%s",
        user.username,
        diag.ping_available,
        diag.docker_bridge,
        diag.scan_cidr_env,
        diag.resolved_cidrs,
        diag.scan_ready,
    )
    return diag


@app.get("/api/settings", response_model=AppSettingsOut)
async def get_settings(db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    app_settings = await _get_or_create_settings(db)
    return _settings_to_out(app_settings)


@app.patch("/api/settings", response_model=AppSettingsOut)
async def update_settings(
    data: AppSettingsUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    app_settings = await _get_or_create_settings(db)
    updates = data.model_dump(exclude_unset=True)
    if "custom_css" in updates:
        updates["custom_css"] = _sanitize_custom_css(updates["custom_css"])
    if "discovery_enabled" in updates and settings.discovery_env_locked:
        updates.pop("discovery_enabled")
    discovery_changed = "discovery_enabled" in updates
    for field, value in updates.items():
        setattr(app_settings, field, value)
    await db.commit()
    await db.refresh(app_settings)
    if discovery_changed:
        _sync_discovery_runtime_from_db(app_settings)
        await _apply_discovery_schedulers()
    return _settings_to_out(app_settings)


_brain_stats_cache: dict[str, object] = {"at": 0.0, "data": None, "url": None}


@app.get("/api/brain/stats")
async def brain_stats(db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    """Proxy + normalize the Brain knowledge-base stats JSON (server-side, cached 60s)."""
    app_settings = await _get_or_create_settings(db)
    url = (app_settings.brain_stats_url or "").strip()
    if not app_settings.show_brain or not url:
        return {"ok": False, "configured": bool(url), "error": "disabled"}

    now = time.monotonic()
    if (
        _brain_stats_cache.get("url") == url
        and _brain_stats_cache.get("data") is not None
        and now - float(_brain_stats_cache.get("at") or 0) < 60
    ):
        return _brain_stats_cache["data"]

    try:
        timeout = httpx.Timeout(4.0, connect=2.0)
        async with httpx.AsyncClient(verify=False, timeout=timeout) as client:
            resp = await client.get(url, headers={"User-Agent": "NetDash/1.0 BrainStats"})
        resp.raise_for_status()
        raw = resp.json()
        activity = raw.get("activity_7d")
        data = {
            "ok": True,
            "dashboard_url": brain_dashboard_url(url),
            "notes": int(raw.get("notes") or 0),
            "sessions": int(raw.get("sessions") or 0),
            "library_docs": int(raw.get("library_docs") or 0),
            "code_files": int(raw.get("code_files") or 0),
            "graph_nodes": int(raw.get("graph_nodes") or 0),
            "last_session_at": raw.get("last_session_at"),
            "activity_7d": [int(x) for x in activity][:14] if isinstance(activity, list) else [],
        }
    except Exception as exc:
        return {"ok": False, "configured": True, "error": str(exc)[:200]}

    _brain_stats_cache.update(at=now, data=data, url=url)
    return data


_network_info_cache: dict[str, object] = {"at": 0.0, "data": None}
_wan_info_cache: dict[str, object] = {"at": 0.0, "data": None}


async def _fetch_wan_info() -> dict | None:
    """Public IP + GeoIP via ip-api.com (free, no key). Cached ~1h; returns stale on error."""
    now = time.monotonic()
    cached = _wan_info_cache.get("data")
    if cached is not None and now - float(_wan_info_cache.get("at") or 0) < 3600:
        return cached  # type: ignore[return-value]
    try:
        timeout = httpx.Timeout(4.0, connect=2.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(
                "http://ip-api.com/json/",
                params={"fields": "status,query,isp,country,countryCode,city"},
                headers={"User-Agent": "NetDash/1.0 NetworkTile"},
            )
        resp.raise_for_status()
        raw = resp.json()
        if raw.get("status") != "success":
            return cached  # type: ignore[return-value]
        wan = {
            "ip": raw.get("query"),
            "isp": raw.get("isp"),
            "country": raw.get("country"),
            "country_code": raw.get("countryCode"),
            "city": raw.get("city"),
        }
    except Exception:
        return cached  # type: ignore[return-value]
    _wan_info_cache.update(at=now, data=wan)
    return wan


async def _tcp_latency_ms(host: str, port: int) -> int | None:
    """TCP-connect round trip in ms (works even when ICMP is blocked). None on failure."""
    start = time.monotonic()
    try:
        _, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=2.0)
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass
        return round((time.monotonic() - start) * 1000)
    except Exception:
        return None


@app.get("/api/network/info")
async def network_tile_info(db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    """LAN + WAN + activity/category stats for the optional Network tile (cached 60s)."""
    app_settings = await _get_or_create_settings(db)
    if not app_settings.show_network:
        return {"ok": False, "error": "disabled"}

    now = time.monotonic()
    cached = _network_info_cache.get("data")
    if cached is not None and now - float(_network_info_cache.get("at") or 0) < 60:
        return cached

    total = (await db.execute(select(func.count()).select_from(Service))).scalar() or 0
    online = (
        await db.execute(select(func.count()).select_from(Service).where(Service.is_online.is_(True)))
    ).scalar() or 0

    day_rows = (
        await db.execute(
            select(func.date(Service.created_at), func.count()).group_by(func.date(Service.created_at))
        )
    ).all()
    per_day = {str(d): int(n) for d, n in day_rows if d}
    today = datetime.now(timezone.utc).date()
    activity_7d = [per_day.get((today - timedelta(days=i)).isoformat(), 0) for i in range(6, -1, -1)]

    last_scan = app_settings.discovery_last_import_at
    if last_scan is None:
        last_scan = (await db.execute(select(func.max(Service.created_at)))).scalar()

    demo = settings.demo_mode
    wan = None
    latency: list[dict] = []
    if settings.network_wan_lookup:
        if demo:
            wan = {"ip": "203.0.113.7", "isp": "Example ISP", "country": "Demoland",
                   "country_code": "DE", "city": "Demo City"}
            latency = [{"name": "Cloudflare", "ms": 12}, {"name": "Google", "ms": 15}]
        else:
            wan = await _fetch_wan_info()
            targets = [("Cloudflare", "1.1.1.1", 443), ("Google", "8.8.8.8", 53)]
            results = await asyncio.gather(*[_tcp_latency_ms(h, p) for _, h, p in targets])
            latency = [{"name": targets[i][0], "ms": results[i]} for i in range(len(targets))]

    data = {
        "ok": True,
        "lan_ip": "10.0.0.5" if demo else get_local_ip(),
        "gateway": "10.0.0.1" if demo else get_default_gateway(),
        "cidr": "10.0.0.0/24" if demo else get_local_network(),
        "devices_total": int(total),
        "devices_online": int(online),
        "last_scan_at": last_scan.isoformat() if last_scan else None,
        "wan": wan,
        "activity_7d": activity_7d,
        "latency": latency,
    }
    _network_info_cache.update(at=now, data=data)
    return data


def _image_extension(
    content_type: str | None,
    filename: str | None,
    *,
    allowed_types: dict[str, str],
    allowed_suffixes: set[str],
) -> str | None:
    ct = (content_type or "").split(";")[0].strip().lower()
    if ct in allowed_types:
        return allowed_types[ct]
    if filename:
        safe_name = Path(filename).name
        suffix = Path(safe_name).suffix.lower()
        if suffix == ".jpeg":
            suffix = ".jpg"
        if suffix in allowed_suffixes:
            return suffix
    return None


def _logo_extension(content_type: str | None, filename: str | None) -> str | None:
    return _image_extension(
        content_type,
        filename,
        allowed_types=ALLOWED_IMAGE_TYPES,
        allowed_suffixes=IMAGE_EXT_BY_SUFFIX,
    )


def _icon_extension(content_type: str | None, filename: str | None) -> str | None:
    return _image_extension(
        content_type,
        filename,
        allowed_types=ALLOWED_ICON_TYPES,
        allowed_suffixes=ICON_EXT_BY_SUFFIX,
    )


@app.post("/api/settings/logo", response_model=AppSettingsOut)
async def upload_logo(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    ext = _logo_extension(file.content_type, file.filename)
    if not ext:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nieobsługiwany format. Dozwolone: PNG, SVG, WebP, JPEG, GIF.",
        )
    content = await file.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Pusty plik.")
    if len(content) > MAX_LOGO_SIZE:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Plik za duży (max 2 MB).")
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    for old in UPLOADS_DIR.glob("logo.*"):
        try:
            old.unlink()
        except OSError:
            logger.warning("Could not remove old logo %s", old)
    dest = UPLOADS_DIR / f"logo{ext}"
    dest.write_bytes(content)
    app_settings = await _get_or_create_settings(db)
    app_settings.custom_logo_url = f"/uploads/logo{ext}"
    app_settings.use_custom_logo = True
    await db.commit()
    await db.refresh(app_settings)
    return _settings_to_out(app_settings)


@app.get("/api/settings/export", response_model=SettingsBackupOut)
async def export_settings(db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    app_settings = await _get_or_create_settings(db)
    svc_result = await db.execute(select(Service).order_by(Service.name))
    key_result = await db.execute(select(ApiKey).order_by(ApiKey.name))
    note_result = await db.execute(select(Note).order_by(Note.title))

    services = [
        SettingsBackupService(
            name=s.name,
            url=s.url,
            host=s.host,
            port=s.port,
            protocol=s.protocol,
            category=s.category,
            icon=s.icon,
            icon_url=s.icon_url,
            description=s.description,
            auto_discovered=s.auto_discovered,
            has_login=s.has_login,
            pinned=s.pinned,
            service_notes=s.service_notes,
            mac_address=s.mac_address,
            wol_enabled=s.wol_enabled,
            wol_port=s.wol_port,
            sol_port=s.sol_port,
            broadcast_ip=s.broadcast_ip,
        )
        for s in svc_result.scalars().all()
    ]
    api_keys = [
        SettingsBackupApiKey(
            name=k.name,
            secret=decrypt_secret(k.secret_encrypted),
            service=k.service,
            username=k.username,
            url=k.url,
            notes=k.notes,
            pinned=k.pinned,
        )
        for k in key_result.scalars().all()
    ]
    notes = [
        SettingsBackupNote(
            title=n.title,
            content=n.content,
            color=n.color,
            pinned=n.pinned,
        )
        for n in note_result.scalars().all()
    ]

    return SettingsBackupOut(
        app_version=VERSION,
        exported_at=datetime.now(timezone.utc),
        settings=AppSettingsOut.model_validate(app_settings),
        services=services,
        api_keys=api_keys,
        notes=notes,
    )


@app.post("/api/settings/import", response_model=AppSettingsOut)
async def import_settings(
    data: SettingsImportRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    if data.format != BACKUP_FORMAT:
        raise HTTPException(status_code=400, detail="Nieprawidłowy format pliku kopii zapasowej")
    if data.format_version != BACKUP_FORMAT_VERSION:
        raise HTTPException(
            status_code=400,
            detail=f"Nieobsługiwana wersja kopii zapasowej: {data.format_version}",
        )

    app_settings = await _get_or_create_settings(db)
    settings_data = data.settings.model_dump()
    if "custom_css" in settings_data:
        settings_data["custom_css"] = _sanitize_custom_css(settings_data.get("custom_css"))
    for field, value in settings_data.items():
        setattr(app_settings, field, value)

    for key in (await db.execute(select(ApiKey))).scalars().all():
        await db.delete(key)
    for note in (await db.execute(select(Note))).scalars().all():
        await db.delete(note)
    for service in (await db.execute(select(Service))).scalars().all():
        await db.delete(service)
    await db.flush()

    for item in data.services:
        from urllib.parse import urlparse

        host = item.host
        port = item.port
        protocol = item.protocol
        if not host or port is None:
            parsed = urlparse(item.url)
            host = host or parsed.hostname or "localhost"
            port = port if port is not None else (parsed.port or (443 if parsed.scheme == "https" else 80))
            protocol = protocol or parsed.scheme or "http"
        mac = normalize_mac(item.mac_address) if item.mac_address else None
        db.add(
            Service(
                name=item.name,
                url=item.url,
                host=host,
                port=port,
                protocol=protocol,
                category=item.category,
                icon=item.icon,
                icon_url=item.icon_url,
                description=item.description,
                auto_discovered=item.auto_discovered,
                has_login=item.has_login,
                pinned=item.pinned,
                service_notes=item.service_notes,
                mac_address=mac,
                wol_enabled=item.wol_enabled,
                wol_port=item.wol_port,
                sol_port=item.sol_port,
                broadcast_ip=item.broadcast_ip,
            )
        )

    for item in data.api_keys:
        secret = item.secret
        db.add(
            ApiKey(
                name=item.name,
                service=item.service,
                secret_encrypted=encrypt_secret(secret),
                secret_hint=secret[-4:] if len(secret) >= 4 else secret,
                username=item.username,
                url=item.url,
                notes=item.notes,
                pinned=item.pinned,
            )
        )

    for item in data.notes:
        db.add(Note(**item.model_dump()))

    await db.commit()
    await db.refresh(app_settings)
    _sync_discovery_runtime_from_db(app_settings)
    await _apply_discovery_schedulers()
    return _settings_to_out(app_settings)


@app.post("/api/services/enrich")
async def enrich_services(_: User = Depends(get_current_user)):
    mac_count = await enrich_mac_addresses()
    count = await enrich_all_services()
    icon_count = await enrich_service_icons(limit=150)
    return {"updated": count + mac_count + icon_count}


@app.post("/api/services/identify", response_model=ServiceIdentifyResponse)
async def identify_service(
    data: ServiceIdentifyRequest,
    _: User = Depends(get_current_user),
):
    result = suggest_service_identity(
        name=data.name,
        url=data.url,
        description=data.description,
        category=data.category,
        icon=data.icon,
        icon_url=data.icon_url,
        has_login=data.has_login,
    )
    return ServiceIdentifyResponse(
        matched=bool(result["matched"]),
        confidence=str(result["confidence"]),
        matched_by=list(result["matched_by"]),
        heuristics=list(result["heuristics"]),
        changed_fields=list(result["changed_fields"]),
        tags=list(result["tags"]),
        note=result.get("note"),
        suggestion=ServiceIdentifySuggestion(**result["suggestion"]),
    )


@app.get("/api/services", response_model=list[ServiceOut])
async def list_services(db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    from app.icons import effective_browser_icon_url

    result = await db.execute(select(Service).order_by(Service.pinned.desc(), Service.name))
    services = result.scalars().all()
    dirty = False
    for svc in services:
        clean = sanitize_service_url(svc.url)
        if clean and svc.url != clean:
            svc.url = clean
            dirty = True
    if dirty:
        await db.commit()
    out: list[ServiceOut] = []
    for svc in services:
        row = ServiceOut.model_validate(svc)
        row.icon_url = effective_browser_icon_url(
            svc.icon_url,
            svc.url,
            has_login=svc.has_login,
            name=svc.name,
            description=svc.description,
            port=svc.port,
        )
        out.append(row)
    return out


@app.post("/api/services", response_model=ServiceOut)
async def create_service(
    data: ServiceCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    from urllib.parse import urlparse

    parsed = urlparse(data.url)
    host = parsed.hostname or "localhost"
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    service = Service(
        name=data.name,
        url=data.url,
        host=host,
        port=port,
        protocol=parsed.scheme or "http",
        category=data.category,
        icon=data.icon,
        icon_url=data.icon_url,
        description=data.description,
        auto_discovered=False,
        customized=True,
        has_login=data.has_login,
        pinned=data.pinned,
    )
    db.add(service)
    await db.commit()
    await db.refresh(service)
    return service


@app.post("/api/services/upload-icon", response_model=IconUploadResponse)
async def upload_service_icon(
    file: UploadFile = File(...),
    _: User = Depends(get_current_user),
):
    ext = _icon_extension(file.content_type, file.filename)
    if not ext:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nieobsługiwany format. Dozwolone: PNG, SVG, WebP, JPEG.",
        )
    content = await file.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Pusty plik.")
    if len(content) > MAX_ICON_SIZE:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Plik za duży (max 2 MB).")
    ICONS_DIR.mkdir(parents=True, exist_ok=True)
    dest = ICONS_DIR / f"{uuid.uuid4().hex}{ext}"
    if not dest.resolve().is_relative_to(ICONS_DIR.resolve()):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Nieprawidłowa nazwa pliku.")
    dest.write_bytes(content)
    return IconUploadResponse(url=f"/uploads/icons/{dest.name}")


@app.post("/api/services/import/homer", response_model=HomerImportResult)
async def import_homer_services(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    raw = await file.read()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid file encoding (expected UTF-8)") from exc

    try:
        parsed = parse_homer_config(text)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not parsed:
        raise HTTPException(status_code=400, detail="No importable services found in Homer config")

    from urllib.parse import urlparse

    existing = await db.execute(select(Service.url))
    known_urls = {sanitize_service_url(u).lower() for (u,) in existing.all() if u}
    created: list[Service] = []
    skipped = 0

    for item in parsed:
        url = sanitize_service_url(item["url"])
        if url.lower() in known_urls:
            skipped += 1
            continue
        parsed_url = urlparse(url)
        host = parsed_url.hostname or "localhost"
        port = parsed_url.port or (443 if parsed_url.scheme == "https" else 80)
        service = Service(
            name=item["name"],
            url=url,
            host=host,
            port=port,
            protocol=parsed_url.scheme or "http",
            category=item.get("category") or "Inne",
            icon=item.get("icon") or "globe",
            icon_url=item.get("icon_url"),
            description=item.get("description"),
            auto_discovered=False,
            customized=True,
            has_login=False,
            pinned=False,
        )
        db.add(service)
        created.append(service)
        known_urls.add(url.lower())

    await db.commit()
    for svc in created:
        await db.refresh(svc)

    return HomerImportResult(imported=len(created), skipped=skipped, services=created)


_SERVICE_CUSTOMIZE_FIELDS = frozenset(
    {"name", "url", "category", "icon", "icon_url", "description", "pinned", "has_login"}
)


@app.patch("/api/services/{service_id}", response_model=ServiceOut)
async def update_service(
    service_id: int,
    data: ServiceUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    from urllib.parse import urlparse

    result = await db.execute(select(Service).where(Service.id == service_id))
    service = result.scalar_one_or_none()
    if not service:
        raise HTTPException(status_code=404, detail="Serwis nie znaleziony")
    updates = data.model_dump(exclude_unset=True)
    if _SERVICE_CUSTOMIZE_FIELDS.intersection(updates):
        service.customized = True
    for field, value in updates.items():
        if field == "mac_address" and value:
            value = normalize_mac(value)
        setattr(service, field, value)
    if "url" in updates and updates["url"]:
        parsed = urlparse(updates["url"])
        if parsed.hostname:
            service.host = parsed.hostname
        if parsed.port:
            service.port = parsed.port
        elif parsed.scheme == "https":
            service.port = 443
        elif parsed.scheme == "http":
            service.port = 80
        if parsed.scheme:
            service.protocol = parsed.scheme
    await db.commit()
    await db.refresh(service)
    return service


@app.delete("/api/services/{service_id}")
async def delete_service(
    service_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(select(Service).where(Service.id == service_id))
    service = result.scalar_one_or_none()
    if not service:
        raise HTTPException(status_code=404, detail="Serwis nie znaleziony")
    await db.delete(service)
    await db.commit()
    return {"ok": True}


async def _upsert_service(item: DiscoveredService) -> tuple[str, int]:
    async with async_session() as db:
        existing = await db.execute(
            select(Service).where(Service.host == item.host, Service.port == item.port)
        )
        service = existing.scalar_one_or_none()
        now = datetime.now(timezone.utc)
        if service:
            if not service.customized:
                if is_http_error_name(item.name):
                    if is_http_error_name(service.name) or service.name.startswith("Port "):
                        service.name = _fallback_service_name(item.host, item.port, item.name)
                    if item.health_detail or is_http_error_name(item.name):
                        service.health_detail = (item.health_detail or item.name)[:128]
                else:
                    service.name = item.name
                    if item.health_detail:
                        service.health_detail = item.health_detail[:128]
                service.url = sanitize_service_url(item.url)
                service.protocol = item.protocol
                service.category = item.category
                service.icon = item.icon
                if item.icon_url or not service.icon_url:
                    service.icon_url = item.icon_url
                service.description = item.description
            elif item.health_detail:
                service.health_detail = item.health_detail[:128]
            service.has_login = item.has_login
            service.is_online = True
            service.last_seen = now
            service.last_checked = now
            if not service.mac_address:
                mac = await lookup_mac_for_ip(item.host)
                if mac:
                    service.mac_address = mac
        else:
            mac = await lookup_mac_for_ip(item.host)
            new_name = item.name
            if is_http_error_name(new_name):
                new_name = _fallback_service_name(item.host, item.port, new_name)
            db.add(
                Service(
                    name=new_name,
                    url=sanitize_service_url(item.url),
                    host=item.host,
                    port=item.port,
                    protocol=item.protocol,
                    category=item.category,
                    icon=item.icon,
                    icon_url=item.icon_url,
                    description=item.description,
                    auto_discovered=True,
                    has_login=item.has_login,
                    is_online=True,
                    last_checked=now,
                    health_detail=(item.health_detail or item.name)[:128] if is_http_error_name(item.name) else item.health_detail,
                    mac_address=mac,
                )
            )
        await db.commit()
    return item.host, item.port


async def _finalize_scan(seen: set[tuple[str, int]]) -> None:
    async with async_session() as db:
        app_settings = await _get_or_create_settings(db)
        result = await db.execute(select(Service))
        now = datetime.now(timezone.utc)
        stale_days = effective_stale_remove_days(app_settings.stale_remove_days or 0)

        for service in result.scalars().all():
            key = (service.host, service.port)
            if key in seen:
                continue
            # Port services keep is_online from scheduled health checks, not TCP scan presence.
            if service.protocol != "host" and service.port != 0:
                continue
            service.is_online = False
            service.last_checked = now

        await purge_stale_services(db, stale_days)
        await db.commit()


async def _update_scan_progress(job_id: int, phase: str, current: int, total: int, found: int | None = None):
    async with async_session() as db:
        result = await db.execute(select(ScanJob).where(ScanJob.id == job_id))
        job = result.scalar_one_or_none()
        if not job:
            return
        job.progress_phase = phase
        job.progress_current = current
        job.progress_total = total
        if found is not None:
            job.found_count = found
        await db.commit()


async def _collect_known_scan_hosts(db: AsyncSession) -> list[str]:
    result = await db.execute(select(Service.host))
    hosts: list[str] = []
    seen: set[str] = set()
    for (host,) in result.all():
        if not host or host in seen:
            continue
        seen.add(host)
        hosts.append(host)
    return hosts


async def _run_scan(job_id: int, cidrs: list[str], full_scan: bool = False, quick_scan: bool = False):
    cidr_label = format_cidr_list(cidrs)
    logger.info(
        "Scan %s started CIDR=%s full_scan=%s quick_scan=%s safe_mode=%s",
        job_id,
        cidr_label,
        full_scan,
        quick_scan,
        settings.scan_safe_mode,
    )
    async with async_session() as db:
        result = await db.execute(select(ScanJob).where(ScanJob.id == job_id))
        job = result.scalar_one()
        job.status = "running"
        job.started_at = datetime.now(timezone.utc)
        job.found_count = 0
        job.progress_phase = "ping"
        await db.commit()

    found_count = 0
    seen_keys: set[tuple[str, int]] = set()

    async def on_progress(phase: str, current: int, total: int):
        await _update_scan_progress(job_id, phase, current, total, found_count)

    async def on_service(item: DiscoveredService):
        nonlocal found_count
        key = await _upsert_service(item)
        seen_keys.add(key)
        found_count += 1
        await _update_scan_progress(job_id, "identify", found_count, max(found_count, 1), found_count)

    async with async_session() as db:
        app_settings = await _get_or_create_settings(db)
        host_ports = parse_host_scan_ports(app_settings.host_scan_ports)
        host_only = app_settings.host_only_entries is not False
        known_hosts = await _collect_known_scan_hosts(db)

    scan_timeout = settings.effective_scan_max_duration
    try:
        discovered = await asyncio.wait_for(
            scan_networks(
                cidrs,
                full_scan=full_scan,
                quick_scan=quick_scan,
                known_hosts=known_hosts,
                host_scan_ports=host_ports,
                host_only_entries=host_only,
                progress_callback=on_progress,
                service_callback=on_service,
                manual_scan=True,
            ),
            timeout=scan_timeout,
        )
        if host_only:
            local_key = await _upsert_service(build_local_host_service())
            seen_keys.add(local_key)
        await _finalize_scan(seen_keys)
        if not settings.scan_safe_mode:
            await enrich_mac_addresses()
        await enrich_all_services()
        await enrich_service_icons(limit=150)
        async with async_session() as db:
            result = await db.execute(select(ScanJob).where(ScanJob.id == job_id))
            job = result.scalar_one()
            job.status = "completed"
            job.found_count = len(discovered)
            job.finished_at = datetime.now(timezone.utc)
            job.progress_phase = "done"
            job.error_message = None
            if len(discovered) <= 1 and host_only:
                hints: list[str] = []
                if is_likely_docker_bridge():
                    hints.append(
                        "Kontener widzi sieć Docker, nie LAN — ustaw NETDASH_SCAN_CIDR "
                        "(np. 192.168.1.0/24) lub mapowanie portów (bridge) z NETDASH_SCAN_CIDR."
                    )
                if not await icmp_ping_available():
                    hints.append(
                        "Ping ICMP zablokowany — skan użył TCP; sprawdź CIDR i cap_add: NET_RAW."
                    )
                if not settings.scan_cidr:
                    hints.append(
                        "Brak NETDASH_SCAN_CIDR w compose — Ustawienia → Skanowanie → Domyślne sieci (CIDR)."
                    )
                if hints:
                    job.error_message = " ".join(hints)
            await db.commit()
        logger.info(
            "Scan %s completed: %s services across %s (quick=%s full=%s)",
            job_id,
            len(discovered),
            cidr_label,
            quick_scan,
            full_scan,
        )
    except asyncio.TimeoutError:
        msg = (
            f"Skanowanie przekroczyło limit czasu ({int(settings.effective_scan_max_duration)} s). "
            "Na słabym sprzęcie zostaw NETDASH_SCAN_SAFE_MODE=true, użyj mniejszego CIDR (/28) lub wyłącz pełny skan."
        )
        logger.exception("Scan %s timed out for %s", job_id, format_cidr_list(cidrs))
        async with async_session() as db:
            result = await db.execute(select(ScanJob).where(ScanJob.id == job_id))
            job = result.scalar_one()
            job.status = "failed"
            job.error_message = msg
            job.finished_at = datetime.now(timezone.utc)
            await db.commit()
    except ScanError as exc:
        logger.warning("Scan %s rejected: %s", job_id, exc)
        async with async_session() as db:
            result = await db.execute(select(ScanJob).where(ScanJob.id == job_id))
            job = result.scalar_one()
            job.status = "failed"
            job.error_message = str(exc)
            job.finished_at = datetime.now(timezone.utc)
            await db.commit()
    except PermissionError:
        msg = (
            "Brak uprawnień do ping/skanu sieci (NET_RAW). "
            "Dodaj cap_add: NET_RAW w compose lub mapuj porty (bridge) z NETDASH_SCAN_CIDR."
        )
        logger.exception("Scan %s permission error for %s", job_id, format_cidr_list(cidrs))
        async with async_session() as db:
            result = await db.execute(select(ScanJob).where(ScanJob.id == job_id))
            job = result.scalar_one()
            job.status = "failed"
            job.error_message = msg
            job.finished_at = datetime.now(timezone.utc)
            await db.commit()
    except asyncio.CancelledError:
        logger.info("Scan %s cancelled by user", job_id)
        async with async_session() as db:
            result = await db.execute(select(ScanJob).where(ScanJob.id == job_id))
            job = result.scalar_one_or_none()
            if job and job.status in ("running", "pending"):
                job.status = "cancelled"
                job.error_message = "Skan zatrzymany przez użytkownika."
                job.finished_at = datetime.now(timezone.utc)
                await db.commit()
        raise
    except Exception as exc:
        msg = f"Skanowanie nie powiodło się: {exc}"
        logger.exception("Scan %s failed for %s", job_id, format_cidr_list(cidrs))
        async with async_session() as db:
            result = await db.execute(select(ScanJob).where(ScanJob.id == job_id))
            job = result.scalar_one()
            job.status = "failed"
            job.error_message = msg[:512]
            job.finished_at = datetime.now(timezone.utc)
            await db.commit()
    finally:
        scan_tasks.pop(job_id, None)
        logger.debug("Scan %s task finished (removed from scan_tasks)", job_id)


@app.post("/api/discovery/import", response_model=DiscoveryImportResult)
async def discovery_import(
    data: DiscoveryImportRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not data.hosts:
        raise HTTPException(status_code=400, detail="Brak hostów do importu")
    source_hostname = (data.hostname or "").strip() or None
    client = request.client.host if request.client else "?"
    logger.info(
        "POST /api/discovery/import user=%s client=%s source=%s hostname=%s hosts=%s mark_offline=%s",
        user.username,
        client,
        data.source,
        source_hostname,
        len(data.hosts),
        data.mark_missing_offline,
    )
    return await import_discovery_hosts(
        db,
        data.hosts,
        source=data.source,
        source_hostname=source_hostname,
        mark_missing_offline=data.mark_missing_offline,
    )


@app.post("/api/scan/ui-attempt")
async def log_scan_ui_attempt(
    data: ScanUiAttemptRequest,
    _: User = Depends(get_current_user),
):
    logger.info(
        "UI scan attempt source=%s cidr=%s user=%s",
        data.source,
        data.cidr,
        _.username,
    )
    return {"ok": True}


@app.post("/api/scan", response_model=ScanStatus)
async def start_scan(
    data: ScanRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    logger.info("POST /api/scan body=%s user=%s", data.model_dump(), _.username)
    if settings.scan_disabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Skan lokalny wyłączony na NAS. Uruchom agenta na homelab (192.168.1.201) — "
                "skanuje /24 automatycznie. Patrz Ustawienia → Automatyczne discovery."
            ),
        )
    if any(not t.done() for t in scan_tasks.values()):
        logger.warning("POST /api/scan rejected: scan already in progress")
        raise HTTPException(status_code=409, detail="Skanowanie już trwa — poczekaj na zakończenie")

    full_scan = data.full_scan
    if settings.scan_safe_mode and full_scan:
        logger.warning("full_scan requested but scan_safe_mode=true — forcing quick scan")
        full_scan = False

    docker_br = is_likely_docker_bridge()
    quick_scan = data.quick_scan
    if quick_scan is None:
        quick_scan = settings.scan_safe_mode or docker_br
    if full_scan:
        quick_scan = False
    if settings.scan_safe_mode:
        quick_scan = True

    app_settings = await _get_or_create_settings(db)
    try:
        cidrs = resolve_scan_cidrs(data.cidr, app_settings.scan_cidr_default)
    except ValueError as exc:
        logger.warning("POST /api/scan invalid CIDR: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if is_likely_docker_bridge() and not settings.scan_cidr and not app_settings.scan_cidr_default:
        if not (data.cidr and data.cidr.strip()):
            raise HTTPException(
                status_code=400,
                detail=(
                    "Brak CIDR do skanu LAN — kontener jest w sieci Docker (172.x), nie w Twojej LAN. "
                    "Ustaw NETDASH_SCAN_CIDR=192.168.1.0/24 w compose, "
                    "lub Ustawienia → Skanowanie, lub mapowanie portów (bridge)."
                ),
            )

    if not cidrs:
        raise HTTPException(
            status_code=400,
            detail="Nie podano sieci do skanowania — ustaw CIDR w Ustawienia → Skanowanie lub NETDASH_SCAN_CIDR.",
        )

    try:
        validate_manual_scan_cidrs(cidrs)
    except ScanError as exc:
        logger.warning("POST /api/scan rejected: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    requested_label = format_cidr_list(cidrs)
    scan_cidrs = expand_cidrs_for_safe_mode(cidrs)
    cidr_label = format_cidr_list(scan_cidrs)
    safe_narrowed = settings.scan_safe_mode and cidr_label != requested_label
    if safe_narrowed:
        logger.info("Safe mode narrowed scan CIDR %s → %s", requested_label, cidr_label)
    ping_ok = await icmp_ping_available()
    if ping_ok:
        logger.info(
            "Network scan job CIDR=%s quick_scan=%s full_scan=%s safe_mode=%s concurrency=%s max_hosts=%s timeout=%ss docker_bridge=%s",
            cidr_label,
            quick_scan,
            full_scan,
            settings.scan_safe_mode,
            settings.effective_scan_concurrency,
            settings.effective_scan_max_hosts,
            int(settings.effective_scan_max_duration),
            docker_br,
        )
    else:
        logger.warning(
            "Network scan job CIDR=%s quick_scan=%s full_scan=%s safe_mode=%s docker_bridge=%s — ICMP ping unavailable, using TCP discovery",
            cidr_label,
            quick_scan,
            full_scan,
            settings.scan_safe_mode,
            docker_br,
        )

    job = ScanJob(cidr=cidr_label, status="pending")
    job_notes: list[str] = []
    if not ping_ok:
        job_notes.append(
            "Ping ICMP niedostępny na tym hoście (typowe w Dockerze) — skan użyje TCP. "
            "Upewnij się, że NETDASH_SCAN_CIDR jest poprawny i compose ma cap_add: NET_RAW."
        )
    if safe_narrowed:
        job_notes.append(
            f"Tryb bezpieczny: skan ograniczony z {requested_label} do {cidr_label}. "
            "Ustaw węższy CIDR (/28) lub limit RAM 768 MB+ przed pełnym /24."
        )
    if job_notes:
        job.error_message = " ".join(job_notes)
    db.add(job)
    await db.commit()
    await db.refresh(job)

    task = asyncio.create_task(_run_scan(job.id, scan_cidrs, full_scan, quick_scan))

    def _log_scan_task_result(t: asyncio.Task) -> None:
        scan_tasks.pop(job.id, None)
        if t.cancelled():
            logger.warning("Scan %s task cancelled", job.id)
            return
        exc = t.exception()
        if exc:
            logger.exception("Scan %s task died unexpectedly", job.id, exc_info=exc)

    task.add_done_callback(_log_scan_task_result)
    scan_tasks[job.id] = task
    logger.info("Scan job %s queued (pending → background task)", job.id)
    return job


@app.get("/api/scan/{job_id}", response_model=ScanStatus)
async def scan_status(job_id: int, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(select(ScanJob).where(ScanJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Skan nie znaleziony")
    return job


@app.post("/api/scan/{job_id}/cancel", response_model=ScanStatus)
async def cancel_scan(job_id: int, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(select(ScanJob).where(ScanJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Skan nie znaleziony")
    task = scan_tasks.get(job_id)
    if task and not task.done():
        task.cancel()
        logger.info("Scan %s cancel requested by %s", job_id, _.username)
    if job.status in ("running", "pending"):
        job.status = "cancelled"
        job.error_message = "Skan zatrzymany przez użytkownika."
        job.finished_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(job)
    return job


@app.get("/api/scans", response_model=list[ScanStatus])
async def list_scans(db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(select(ScanJob).order_by(ScanJob.created_at.desc()).limit(10))
    return result.scalars().all()


def _resolve_power_params(service: Service, app_settings: AppSettings) -> tuple[str, int, int]:
    broadcast = service.broadcast_ip or app_settings.wol_broadcast_ip or "255.255.255.255"
    wol_port = service.wol_port if service.wol_port is not None else (app_settings.wol_port or 9)
    sol_port = service.sol_port if service.sol_port is not None else (app_settings.sol_port or app_settings.wol_port or 9)
    return broadcast, wol_port, sol_port


async def _send_via_gptwol(base_url: str, mac: str, ip: str) -> bool:
    url = base_url.rstrip("/") + "/wol_or_sol_send"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(url, json={"mac": mac, "ip": ip})
            return response.status_code < 400
    except httpx.HTTPError:
        return False


@app.post("/api/services/health-check")
async def run_health_check(db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    count = await check_all_services(db)
    return {"checked": count}


@app.post("/api/services/{service_id}/wol", response_model=PowerActionResult)
async def wake_service(
    service_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(select(Service).where(Service.id == service_id))
    service = result.scalar_one_or_none()
    if not service:
        raise HTTPException(status_code=404, detail="Serwis nie znaleziony")
    if not service.wol_enabled or not service.mac_address:
        raise HTTPException(status_code=400, detail="WoL nie jest skonfigurowane dla tego serwisu")
    mac = normalize_mac(service.mac_address)
    app_settings = await _get_or_create_settings(db)

    sent = False
    if app_settings.gptwol_url:
        sent = await _send_via_gptwol(app_settings.gptwol_url, mac, service.host)
    if not sent:
        broadcast, wol_port, _ = _resolve_power_params(service, app_settings)
        try:
            send_magic_packet(mac, broadcast_ip=broadcast, port=wol_port, sleep=False)
            sent = True
        except OSError as exc:
            raise HTTPException(status_code=500, detail=f"Nie udało się wysłać pakietu WoL: {exc}") from exc

    return PowerActionResult(ok=sent, action="wol", message=f"Wysłano pakiet Wake-on-LAN do {mac}")


@app.post("/api/services/{service_id}/sleep", response_model=PowerActionResult)
async def sleep_service(
    service_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(select(Service).where(Service.id == service_id))
    service = result.scalar_one_or_none()
    if not service:
        raise HTTPException(status_code=404, detail="Serwis nie znaleziony")
    if not service.wol_enabled or not service.mac_address:
        raise HTTPException(status_code=400, detail="Sleep-on-LAN nie jest skonfigurowane dla tego serwisu")
    mac = normalize_mac(service.mac_address)
    app_settings = await _get_or_create_settings(db)

    sent = False
    if app_settings.gptwol_url:
        sent = await _send_via_gptwol(app_settings.gptwol_url, mac, service.host)
    if not sent:
        broadcast, _, sol_port = _resolve_power_params(service, app_settings)
        try:
            send_magic_packet(mac, broadcast_ip=broadcast, port=sol_port, sleep=True)
            sent = True
        except OSError as exc:
            raise HTTPException(status_code=500, detail=f"Nie udało się wysłać pakietu SOL: {exc}") from exc

    return PowerActionResult(ok=sent, action="sleep", message=f"Wysłano pakiet Sleep-on-LAN do {mac}")


@app.post("/api/discovery/cycle")
async def trigger_discovery_cycle(_: User = Depends(get_current_user)):
    """Manual trigger for adaptive discovery cycle (admin/debug)."""
    if not settings.adaptive_discovery_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Adaptive discovery nieaktywne — ustaw NETDASH_DISCOVERY_MODE=adaptive",
        )
    if not _DISCOVERY_PIPELINE_AVAILABLE:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="discovery_pipeline module missing from image — upgrade to ghcr.io/lobrzut/netdash:1.3.121+",
        )
    try:
        count = await run_discovery_cycle()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"ok": True, "hosts": count, **get_discovery_pipeline_status()}


@app.get("/api/discovery/status")
async def discovery_status(_: User = Depends(get_current_user)):
    if settings.adaptive_discovery_enabled:
        return get_discovery_pipeline_status()
    if settings.arp_discovery_enabled:
        return get_arp_discovery_status()
    return {"enabled": False, "mode": settings.effective_discovery_mode}


@app.post("/api/discovery/arp-cycle")
async def trigger_arp_discovery_cycle(_: User = Depends(get_current_user)):
    """Manual trigger for background ARP cycle (admin/debug)."""
    if not settings.arp_discovery_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="ARP discovery nieaktywne — ustaw NETDASH_DISCOVERY_MODE=arp",
        )
    try:
        count = await run_arp_discovery_cycle()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"ok": True, "hosts": count, **get_arp_discovery_status()}


@app.get("/api/discovery/arp-status")
async def arp_discovery_status(_: User = Depends(get_current_user)):
    return get_arp_discovery_status()


@app.post("/api/network/arp-scan", response_model=list[ArpDeviceOut])
async def arp_scan_network(
    data: ArpScanRequest | None = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    app_settings = await _get_or_create_settings(db)
    if app_settings.arp_scan_enabled is False:
        raise HTTPException(status_code=403, detail="Skan ARP jest wyłączony w ustawieniach")
    try:
        cidrs = resolve_scan_cidrs(data.cidr if data else None, app_settings.scan_cidr_default)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    all_devices: dict[str, ArpDeviceOut] = {}
    try:
        for cidr in cidrs:
            devices = await scan_arp_network(cidr)
            for device in devices:
                all_devices[device.ip] = ArpDeviceOut(ip=device.ip, mac=device.mac, hostname=device.hostname)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"Skan ARP nie powiódł się: {exc}") from exc

    mac_by_ip = {ip: d.mac for ip, d in all_devices.items()}
    async with async_session() as db:
        result = await db.execute(select(Service))
        for svc in result.scalars().all():
            if not svc.mac_address and svc.host in mac_by_ip:
                svc.mac_address = mac_by_ip[svc.host]
                if should_auto_wol(svc) and not svc.wol_enabled:
                    svc.wol_enabled = True
        await db.commit()

    return list(all_devices.values())


@app.get("/api/network/arp-lookup", response_model=ArpLookupOut)
async def arp_lookup(
    ip: str = Query(..., description="Adres IP do wyszukania w tabeli ARP"),
    ping: bool = Query(True, description="Wyślij pojedynczy ping, jeśli brak wpisu w ARP"),
    _: User = Depends(get_current_user),
):
    mac = await lookup_mac_for_ip(ip, ping_first=ping)
    return ArpLookupOut(ip=ip, mac=mac, found=mac is not None)


@app.get("/api/services/{service_id}/network-info", response_model=ArpLookupOut)
async def service_network_info(
    service_id: int,
    ping: bool = Query(True, description="Wyślij pojedynczy ping, jeśli brak wpisu w ARP"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(select(Service).where(Service.id == service_id))
    service = result.scalar_one_or_none()
    if not service:
        raise HTTPException(status_code=404, detail="Serwis nie znaleziony")
    mac = await lookup_mac_for_ip(service.host, ping_first=ping)
    if mac and not service.mac_address:
        service.mac_address = mac
        if should_auto_wol(service) and not service.wol_enabled:
            service.wol_enabled = True
        await db.commit()
        await db.refresh(service)
    return ArpLookupOut(ip=service.host, mac=mac, found=mac is not None)


def _key_out(key: ApiKey) -> ApiKeyOut:
    return ApiKeyOut(
        id=key.id,
        name=key.name,
        service=key.service,
        secret_masked=mask_secret(decrypt_secret(key.secret_encrypted)),
        secret_hint=key.secret_hint,
        username=key.username,
        url=key.url,
        notes=key.notes,
        pinned=key.pinned,
        created_at=key.created_at,
        updated_at=key.updated_at,
    )


@app.get("/api/keys", response_model=list[ApiKeyOut])
async def list_keys(db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(select(ApiKey).order_by(ApiKey.pinned.desc(), ApiKey.name))
    return [_key_out(key) for key in result.scalars().all()]


@app.post("/api/keys", response_model=ApiKeyOut)
async def create_key(
    data: ApiKeyCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    key = ApiKey(
        name=data.name,
        service=data.service,
        secret_encrypted=encrypt_secret(data.secret),
        secret_hint=data.secret[-4:] if len(data.secret) >= 4 else data.secret,
        username=data.username,
        url=data.url,
        notes=data.notes,
        pinned=data.pinned,
    )
    db.add(key)
    await db.commit()
    await db.refresh(key)
    return _key_out(key)


@app.patch("/api/keys/{key_id}", response_model=ApiKeyOut)
async def update_key(
    key_id: int,
    data: ApiKeyUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(select(ApiKey).where(ApiKey.id == key_id))
    key = result.scalar_one_or_none()
    if not key:
        raise HTTPException(status_code=404, detail="Klucz nie znaleziony")
    payload = data.model_dump(exclude_unset=True)
    if "secret" in payload:
        secret = payload.pop("secret")
        key.secret_encrypted = encrypt_secret(secret)
        key.secret_hint = secret[-4:] if len(secret) >= 4 else secret
    for field, value in payload.items():
        setattr(key, field, value)
    key.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(key)
    return _key_out(key)


@app.get("/api/keys/{key_id}/reveal", response_model=ApiKeyReveal)
async def reveal_key(key_id: int, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(select(ApiKey).where(ApiKey.id == key_id))
    key = result.scalar_one_or_none()
    if not key:
        raise HTTPException(status_code=404, detail="Klucz nie znaleziony")
    return ApiKeyReveal(secret=decrypt_secret(key.secret_encrypted))


@app.delete("/api/keys/{key_id}")
async def delete_key(key_id: int, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(select(ApiKey).where(ApiKey.id == key_id))
    key = result.scalar_one_or_none()
    if not key:
        raise HTTPException(status_code=404, detail="Klucz nie znaleziony")
    await db.delete(key)
    await db.commit()
    return {"ok": True}


@app.get("/api/notes", response_model=list[NoteOut])
async def list_notes(db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(select(Note).order_by(Note.pinned.desc(), Note.updated_at.desc()))
    return result.scalars().all()


@app.post("/api/notes", response_model=NoteOut)
async def create_note(
    data: NoteCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    note = Note(**data.model_dump())
    db.add(note)
    await db.commit()
    await db.refresh(note)
    return note


@app.patch("/api/notes/{note_id}", response_model=NoteOut)
async def update_note(
    note_id: int,
    data: NoteUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(select(Note).where(Note.id == note_id))
    note = result.scalar_one_or_none()
    if not note:
        raise HTTPException(status_code=404, detail="Notatka nie znaleziona")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(note, field, value)
    note.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(note)
    return note


@app.delete("/api/notes/{note_id}")
async def delete_note(note_id: int, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(select(Note).where(Note.id == note_id))
    note = result.scalar_one_or_none()
    if not note:
        raise HTTPException(status_code=404, detail="Notatka nie znaleziona")
    await db.delete(note)
    await db.commit()
    return {"ok": True}
