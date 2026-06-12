import asyncio
import logging
import os
import re
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
    set_auth_cookie,
    verify_password,
)
from app.config import BASE_DIR, BUILD_DATE, DATA_DIR, GITHUB_REPO, GHCR_IMAGE, VERSION, settings
from app.docker_update import pull_and_restart, update_apply_available
from app.updates import fetch_latest_release, is_newer_version, normalize_version
from app.database import Base, async_session, engine, get_db
from app.enrich import enrich_all_services, enrich_mac_addresses, should_auto_wol
from app.health import check_all_services
from app.homer_import import parse_homer_config
from app.models import DEFAULT_ABOUT_PROJECT, ApiKey, AppSettings, Note, ScanJob, Service, User
from app.vault import decrypt_secret, encrypt_secret, mask_secret
from app.url_utils import sanitize_service_url
from app.scanner import (
    DiscoveredService,
    ScanError,
    _fallback_service_name,
    build_local_host_service,
    format_cidr_list,
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
from app.wol import normalize_mac, send_magic_packet
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
        )
        db.add(app_settings)
        await db.commit()
        await db.refresh(app_settings)
    else:
        changed = False
        if not app_settings.about_project:
            app_settings.about_project = DEFAULT_ABOUT_PROJECT
            changed = True
        if app_settings.author_bio and ("Łukasz" in app_settings.author_bio or "30+" in app_settings.author_bio):
            app_settings.author_bio = ""
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
    return app_settings


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
        _log_admin_startup_status(admin_status, await _admin_ready(db))

    await _ensure_local_host_service()
    await _sanitize_stored_urls()
    await _cancel_stale_scan_jobs()
    await enrich_mac_addresses()
    await enrich_all_services()


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


async def _health_check_loop():
    interval = 60
    while True:
        try:
            async with async_session() as db:
                settings_row = await _get_or_create_settings(db)
                interval = max(15, min(900, settings_row.health_check_interval or 60))
                enabled = settings_row.health_check_enabled
            if enabled:
                async with async_session() as db:
                    count = await check_all_services(db)
                    logger.info("Health check completed for %s services", count)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Health check loop error")
            interval = 60
        await asyncio.sleep(interval)


async def _deferred_startup_health_check():
    """Defer first health pass on weak hosts so container boot stays responsive."""
    delay = 30 if settings.scan_safe_mode else 5
    await asyncio.sleep(delay)
    try:
        async with async_session() as db:
            settings_row = await _get_or_create_settings(db)
            if settings_row.health_check_enabled:
                count = await check_all_services(db)
                logger.info("Startup health check completed for %s services (after %ss)", count, delay)
    except Exception:
        logger.exception("Startup health check failed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    global health_task
    await init_db()
    asyncio.create_task(_deferred_startup_health_check())
    health_task = asyncio.create_task(_health_check_loop())
    yield
    if health_task:
        health_task.cancel()
        try:
            await health_task
        except asyncio.CancelledError:
            pass
    for task in scan_tasks.values():
        task.cancel()


app = FastAPI(title="NetDash", description="Dashboard sieci z auto-wykrywaniem serwisów", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=BASE_DIR / "app" / "static"), name="static")
app.mount("/uploads", StaticFiles(directory=UPLOADS_DIR), name="uploads")

_STATIC_NO_CACHE = frozenset({"/static/app.js", "/static/i18n.js", "/static/style.css"})


@app.middleware("http")
async def static_no_cache_middleware(request: Request, call_next):
    response = await call_next(request)
    if request.url.path in _STATIC_NO_CACHE:
        response.headers["Cache-Control"] = "no-cache, must-revalidate"
        response.headers["Pragma"] = "no-cache"
    return response


@app.get("/")
async def index():
    return FileResponse(
        BASE_DIR / "app" / "static" / "index.html",
        headers={"Cache-Control": "no-cache, must-revalidate"},
    )


@app.get("/api/health")
async def health(db: AsyncSession = Depends(get_db)):
    return {
        "ok": True,
        "version": VERSION,
        "build_date": BUILD_DATE or None,
        "github": GITHUB_REPO,
        "ghcr_image": GHCR_IMAGE,
        "update_apply_available": update_apply_available(),
        "admin_ready": await _admin_ready(db),
        "admin_user": settings.default_admin_user,
        "sync_admin_password": settings.sync_admin_password,
        "secret_key_configured": settings.secret_key_configured,
        "secret_key_stable": settings.secret_key_stable,
        "scan_safe_mode": settings.scan_safe_mode,
        "resource_profile": settings.resource_profile,
    }


@app.get("/api/updates/check", response_model=UpdateCheckOut)
async def check_updates(_: User = Depends(get_current_user)):
    current = normalize_version(VERSION)
    payload = UpdateCheckOut(
        current_version=current,
        github_repo=GITHUB_REPO,
        update_apply_available=update_apply_available(),
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
    if not username:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Błędny login lub hasło")
    result = await db.execute(select(User).where(func.lower(User.username) == username.lower()))
    user = result.scalar_one_or_none()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Błędny login lub hasło")
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
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get("/api/network", response_model=NetworkInfo)
async def network_info(_: User = Depends(get_current_user)):
    if settings.demo_mode:
        return NetworkInfo(
            local_network="10.0.0.0/24",
            local_ip="10.0.0.5",
            docker_bridge=False,
            scan_cidr_configured=True,
            ping_available=True,
            scan_safe_mode=settings.scan_safe_mode,
            resource_profile=settings.resource_profile,
        )
    ping_ok = await icmp_ping_available()
    return NetworkInfo(
        local_network=get_local_network(),
        local_ip=get_local_ip(),
        docker_bridge=is_likely_docker_bridge(),
        scan_cidr_configured=bool(settings.scan_cidr),
        ping_available=ping_ok,
        scan_safe_mode=settings.scan_safe_mode,
        resource_profile=settings.resource_profile,
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
    if docker_br:
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
    return await _get_or_create_settings(db)


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
    for field, value in updates.items():
        setattr(app_settings, field, value)
    await db.commit()
    await db.refresh(app_settings)
    return app_settings


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
    return app_settings


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
    return app_settings


@app.post("/api/services/enrich")
async def enrich_services(_: User = Depends(get_current_user)):
    mac_count = await enrich_mac_addresses()
    count = await enrich_all_services()
    return {"updated": count + mac_count}


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
    return services


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
        stale_days = app_settings.stale_remove_days or 0
        to_delete: list[Service] = []

        for service in result.scalars().all():
            key = (service.host, service.port)
            if key in seen:
                continue
            service.is_online = False
            service.last_checked = now
            if stale_days > 0 and service.last_seen:
                last = service.last_seen
                if last.tzinfo is None:
                    last = last.replace(tzinfo=timezone.utc)
                if now - last > timedelta(days=stale_days):
                    to_delete.append(service)

        for service in to_delete:
            await db.delete(service)

        await db.commit()
        if to_delete:
            logger.info("Removed %s stale services (older than %s days)", len(to_delete), stale_days)


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


async def _run_scan(job_id: int, cidrs: list[str], full_scan: bool = False):
    async with async_session() as db:
        result = await db.execute(select(ScanJob).where(ScanJob.id == job_id))
        job = result.scalar_one()
        job.status = "running"
        job.started_at = datetime.now(timezone.utc)
        job.found_count = 0
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

    scan_timeout = settings.effective_scan_max_duration
    try:
        discovered = await asyncio.wait_for(
            scan_networks(
                cidrs,
                full_scan=full_scan,
                host_scan_ports=host_ports,
                host_only_entries=host_only,
                progress_callback=on_progress,
                service_callback=on_service,
            ),
            timeout=scan_timeout,
        )
        if host_only:
            local_key = await _upsert_service(build_local_host_service())
            seen_keys.add(local_key)
        await _finalize_scan(seen_keys)
        await enrich_mac_addresses()
        await enrich_all_services()
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
            "Scan %s completed: %s services across %s",
            job_id,
            len(discovered),
            format_cidr_list(cidrs),
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
    except PermissionError as exc:
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


@app.post("/api/scan", response_model=ScanStatus)
async def start_scan(
    data: ScanRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    logger.info("POST /api/scan body=%s", data.model_dump())
    if any(not t.done() for t in scan_tasks.values()):
        raise HTTPException(status_code=409, detail="Skanowanie już trwa — poczekaj na zakończenie")

    full_scan = data.full_scan
    if settings.scan_safe_mode and full_scan:
        logger.warning("full_scan requested but scan_safe_mode=true — forcing quick scan")
        full_scan = False

    app_settings = await _get_or_create_settings(db)
    try:
        cidrs = resolve_scan_cidrs(data.cidr, app_settings.scan_cidr_default)
    except ValueError as exc:
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

    cidr_label = format_cidr_list(cidrs)
    ping_ok = await icmp_ping_available()
    if ping_ok:
        logger.info(
            "Network scan started CIDR=%s full_scan=%s safe_mode=%s concurrency=%s max_hosts=%s timeout=%ss",
            cidr_label,
            full_scan,
            settings.scan_safe_mode,
            settings.effective_scan_concurrency,
            settings.effective_scan_max_hosts,
            int(settings.effective_scan_max_duration),
        )
    else:
        logger.warning(
            "Network scan started CIDR=%s full_scan=%s safe_mode=%s — ICMP ping unavailable (Docker), using TCP discovery",
            cidr_label,
            full_scan,
            settings.scan_safe_mode,
        )

    job = ScanJob(cidr=cidr_label, status="pending")
    if not ping_ok:
        job.error_message = (
            "Ping ICMP niedostępny na tym hoście (typowe w Dockerze) — skan użyje TCP. "
            "Upewnij się, że NETDASH_SCAN_CIDR jest poprawny i compose ma cap_add: NET_RAW."
        )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    task = asyncio.create_task(_run_scan(job.id, cidrs, full_scan))
    scan_tasks[job.id] = task
    return job


@app.get("/api/scan/{job_id}", response_model=ScanStatus)
async def scan_status(job_id: int, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(select(ScanJob).where(ScanJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Skan nie znaleziony")
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
