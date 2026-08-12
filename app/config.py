import os
from datetime import datetime, timezone
from pathlib import Path

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parent.parent
VERSION = "1.3.150"
DEFAULT_LISTEN_PORT = 18787
WHATS_NEW = [
    "Polityka discovery — off / na żądanie (zalecane) / harmonogram / pasywne ARP / legacy adaptive. Domyślnie na żądanie: skan ręczny „Skanuj sieć”, bez ciągłego TCP w tle",
    "Harmonogram — jeden pełny cykl IPS-friendly dziennie (NETDASH_DISCOVERY_SCHEDULE=03:00) lub co N godzin",
    "Pasywne discovery — odczyt tablicy ARP co ~10 min, bez skanu portów (przyjazne SEP)",
    "Tryb IPS-friendly (stealth) — skan rozkłada porty jednego hosta w czasie (1 port/raz, losowa kolejność, odstęp z jitterem), więc nie wyzwala blokad IPS/Symantec SEP („blokuje ruch z IP…”). Domyślnie włączony: NETDASH_IPS_FRIENDLY, NETDASH_PORTS_PER_HOST_DELAY, NETDASH_PORT_PARALLEL_PER_HOST",
    "Ustawienia → Automatyczne discovery — przełącznik wyłączenia skanowania w tle (ręczne dodawanie serwisów nadal działa)",
    "Kafelek Brain — link „Otwórz dashboard” (URL z ustawień statystyk, widoczny gdy Brain online)",
    "Auto-usuwanie nieaktywnych serwisów — NETDASH_STALE_REMOVE_DAYS lub Ustawienia → Skanowanie",
    "Dwa tryby skanu: automatyczny (w tle, throttled) vs ręczny (przycisk) — NETDASH_AUTO_DISCOVERY_ALL_PORTS",
    "Wykrywanie serwisów na dowolnym porcie — NETDASH_SCAN_ALL_PORTS sonduje żywe hosty po ~190 portach usług",
    "Kafelek Sieć: latency łącza (Cloudflare/Google) zamiast donuta kategorii; WAN pokazuje miasto i kraj",
    "Sejf API: klucze nie nakładają się już w wąskim widgecie; notatki jako czytelne wiersze",
    "Zatrzymanie skanu sieci (przycisk Zatrzymaj) + flaga kraju WAN i czytelny podgląd klucza",
    "Kafelek Sieć — LAN/brama/CIDR, WAN IP + ISP/kraj (GeoIP), wykresy (sparkline + donut)",
    "Przycisk Aktualizuj teraz przez Watchtower HTTP API — bez docker.sock w panelu (bezpieczne na QNAP)",
    "Kafelek Brain (opcjonalny) — statystyki wiedzy z endpointu /stats; domyślnie wyłączony",
    "Watermark marek/ikon na wszystkich kafelkach — także przypiętych i emoji",
    "Hardening bezpieczeństwa: limit prób logowania (brute-force)",
    "Hasło zmienione w UI nie jest już nadpisywane przy restarcie",
    "Swagger /docs domyślnie wyłączony (NETDASH_DOCS_ENABLED=true by włączyć)",
    "Migracja JWT na PyJWT + guard SSRF na metadane chmurowe",
]
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
    scan_safe_concurrency: int = 2
    scan_safe_max_hosts: int = 16
    scan_max_hosts: int = 256
    scan_batch_delay: float = 0.4
    scan_batch_size: int = 4
    scan_chunk_size: int = 4
    scan_max_duration: float = 600.0
    scan_safe_max_duration: float = 180.0
    scan_inter_chunk_delay: float = 3.0
    # Safe mode: reject /24 and wider (NETDASH_SCAN_SAFE_BLOCK_WIDE=false to allow auto-shrink).
    scan_safe_min_prefix: int = 28
    scan_safe_max_prefix: int = 28
    scan_safe_max_subnets: int = 1
    scan_safe_block_wide: bool = True
    scan_safe_anchor: str | None = None
    default_admin_user: str = "admin"
    default_admin_password: str = "changeme"
    # Sync admin password from NETDASH_DEFAULT_ADMIN_PASSWORD on every container start (homelab default)
    sync_admin_password: bool = True
    # One-time recovery on startup — remove env after login (see deploy/qnap/README.md)
    reset_admin_password: str | None = None
    # Override auto-detected /24 when running in Docker bridge (e.g. 192.168.1.0/24)
    scan_cidr: str | None = None
    # Disable built-in LAN scan (QNAP dashboard) — use remote discovery agent instead
    scan_disabled: bool = False
    # Probe every LIVE host on the full service-port list (scanner.SERVICE_PORTS) so services
    # on non-standard ports are auto-discovered. Heavier but stays safe (only live hosts).
    scan_all_ports: bool = False
    # Background auto-discovery: gradual all-port probe on live hosts only (throttled batches).
    auto_discovery_all_ports: bool = False
    # Weak profile: scan two /28 chunks per cycle (heavier — off by default on 2 GB hosts).
    weak_dual_chunk: bool = False
    # Master kill switch for all background discovery schedulers (adaptive + ARP).
    discovery_enabled: bool = True
    # Startup MAC/icon enrichment pings many hosts — disable on ultra-safe / low-memory deploys.
    startup_enrich_enabled: bool = True
    # Auto-discovery: never scan a full /24 (or wider) in one cycle — rotate /28 chunks.
    auto_discovery_always_chunk: bool = True
    auto_discovery_chunk_prefix: int = 28
    # Manual scan hard limits — apply even when NETDASH_SCAN_SAFE_MODE=false (stability).
    manual_scan_max_hosts: int = 128
    manual_scan_min_prefix: int = 24
    manual_scan_warn_prefix: int = 24
    manual_scan_max_concurrency: int = 32
    manual_scan_batch_delay: float = 0.15
    # local = manual TCP scan; adaptive = tiered ping→ARP→ports (default QNAP);
    # arp = legacy background arp-scan; remote = deploy/agent
    discovery_mode: str = "local"
    # Primary discovery policy (preferred over discovery_mode): off | on_demand | scheduled | passive | adaptive
    discovery_policy: str | None = None
    # Scheduled mode: daily time UTC (03:00) or interval (24h, 6h)
    discovery_schedule: str = "03:00"
    # Passive mode: seconds between ARP table reads (default 10 min)
    passive_interval: int = 600
    # Hardware profile for adaptive discovery: auto|weak|normal|strong
    discovery_profile: str = "auto"
    # Override adaptive cycle interval (seconds); profile default if unset
    discovery_interval: int | None = None
    # Light port probe on new/stale hosts in adaptive mode
    discovery_port_probe: bool = True
    discovery_port_max_hosts: int = 5
    # Background ARP cycle interval (seconds) when discovery_mode=arp
    arp_interval: int = 300
    # Light port probe for newly seen ARP hosts only (one host at a time)
    arp_probe_new_hosts: bool = True
    arp_probe_delay: float = 2.0
    arp_probe_max_hosts: int = 3
    # LAN interface for arp-scan (-I); auto-detect via `ip route get` when unset
    arp_iface: str | None = None
    # Comma-separated IPs always probed each cycle (e.g. homelab servers)
    arp_extra_hosts: str | None = None
    # Defer first health pass to background (None = auto: true when scan_safe_mode)
    startup_health_defer: bool | None = None
    # Seconds before first health check when defer enabled (None = 30 safe / 5 normal)
    startup_health_defer_seconds: int | None = None
    # Consecutive failed health probes before marking a port service offline (anti-flap).
    health_offline_after_failures: int = 2
    # Delete offline auto-discovered services after N days (0 = disabled). UI overrides when > 0.
    stale_remove_days: int = 0
    # Seconds before first adaptive/ARP discovery cycle (portal ready first)
    discovery_startup_delay: int = 60
    # Ping/TCP sweep when arp-scan returns 0 hosts
    arp_ping_fallback: bool = True
    arp_ping_max_hosts: int = 128
    arp_ping_delay: float = 0.1
    # HttpOnly session cookie Secure flag — false for plain HTTP homelab (default).
    cookie_secure: bool = False
    # Expose Swagger /docs, /redoc, /openapi.json — off by default (info disclosure on host network).
    docs_enabled: bool = False
    # Mask real LAN IP in /api/network (for README screenshots only)
    demo_mode: bool = False
    # Seed example/demo services on first boot when the DB is empty (NETDASH_SEED_DEMO=true)
    seed_demo: bool = False
    # Optional in-container update apply (requires docker.sock mount — see docs/QNAP.md)
    update_apply_enabled: bool = False
    docker_image: str = GHCR_IMAGE
    docker_image_tag: str = "latest"
    container_name: str = "netdash"
    docker_socket: str = "/var/run/docker.sock"
    # QNAP compose.full.yml sets this so the portal can show Watchtower auto-update status
    watchtower_enabled: bool = False
    watchtower_poll_interval: int = 3600
    # Trigger an immediate update via Watchtower's HTTP API (safer than mounting docker.sock
    # into the portal). When set, "Update now" POSTs here instead of using the socket.
    watchtower_api_url: str = ""
    watchtower_api_token: str = ""
    # Network info tile: WAN/GeoIP lookup via ip-api.com. Tile is opt-in in Settings.
    network_wan_lookup: bool = True
    # IPS-friendly (stealth) scanning — ON by default. Endpoint IPS (Symantec SEP, Windows
    # firewall port-scan detection, etc.) block a source IP when it hits many DISTINCT ports on
    # the SAME host within a short window. NetDash's biggest trigger is probing ~190 service
    # ports on one live host within seconds. When enabled, each host's ports are probed with
    # limited per-host parallelism, in randomized order, with a jittered delay between probes —
    # so no single host ever sees a burst of many ports. Cross-host parallelism is unaffected.
    ips_friendly: bool = True
    # Max simultaneous port probes to a SINGLE host (1 = strictly one connection at a time).
    port_parallel_per_host: int = 1
    # Delay (seconds) between consecutive port probes to the SAME host (jittered, see below).
    ports_per_host_delay: float = 0.3
    # Extra random jitter (0..N s) added to each same-host probe delay — hides a fixed rate.
    ports_per_host_jitter: float = 0.2
    # Randomize the order a host's ports are probed (sequential 22,23,25… sweeps are easy to flag).
    scan_randomize_ports: bool = True

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

    @field_validator("docs_enabled", mode="before")
    @classmethod
    def _docs_enabled(cls, v: object) -> bool:
        if v is None or (isinstance(v, str) and not v.strip()):
            return False
        if isinstance(v, str):
            return v.strip().lower() in ("true", "1", "yes", "on")
        return bool(v)

    @field_validator("seed_demo", mode="before")
    @classmethod
    def _seed_demo(cls, v: object) -> bool:
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

    @field_validator("scan_disabled", mode="before")
    @classmethod
    def _scan_disabled(cls, v: object) -> bool:
        if v is None or (isinstance(v, str) and not v.strip()):
            return False
        if isinstance(v, str):
            return v.strip().lower() in ("true", "1", "yes", "on")
        return bool(v)

    @field_validator("scan_all_ports", mode="before")
    @classmethod
    def _scan_all_ports(cls, v: object) -> bool:
        if v is None or (isinstance(v, str) and not v.strip()):
            return False
        if isinstance(v, str):
            return v.strip().lower() in ("true", "1", "yes", "on")
        return bool(v)

    @field_validator("auto_discovery_all_ports", mode="before")
    @classmethod
    def _auto_discovery_all_ports(cls, v: object) -> bool:
        if v is None or (isinstance(v, str) and not v.strip()):
            return False
        if isinstance(v, str):
            return v.strip().lower() in ("true", "1", "yes", "on")
        return bool(v)

    @field_validator("weak_dual_chunk", mode="before")
    @classmethod
    def _weak_dual_chunk(cls, v: object) -> bool:
        if v is None or (isinstance(v, str) and not v.strip()):
            return False
        if isinstance(v, str):
            return v.strip().lower() in ("true", "1", "yes", "on")
        return bool(v)

    @field_validator("discovery_enabled", mode="before")
    @classmethod
    def _discovery_enabled(cls, v: object) -> bool:
        if v is None or (isinstance(v, str) and not v.strip()):
            return True
        if isinstance(v, str):
            return v.strip().lower() in ("true", "1", "yes", "on")
        return bool(v)

    @field_validator("startup_enrich_enabled", mode="before")
    @classmethod
    def _startup_enrich_enabled(cls, v: object) -> bool:
        if v is None or (isinstance(v, str) and not v.strip()):
            return True
        if isinstance(v, str):
            return v.strip().lower() in ("true", "1", "yes", "on")
        return bool(v)

    @field_validator("auto_discovery_always_chunk", mode="before")
    @classmethod
    def _auto_discovery_always_chunk(cls, v: object) -> bool:
        if v is None or (isinstance(v, str) and not v.strip()):
            return True
        if isinstance(v, str):
            return v.strip().lower() in ("true", "1", "yes", "on")
        return bool(v)

    @field_validator("auto_discovery_chunk_prefix", mode="before")
    @classmethod
    def _auto_discovery_chunk_prefix(cls, v: object) -> int:
        if v is None or (isinstance(v, str) and not v.strip()):
            return 28
        return max(24, min(30, int(v)))

    @field_validator("manual_scan_max_hosts", mode="before")
    @classmethod
    def _manual_scan_max_hosts(cls, v: object) -> int:
        if v is None or (isinstance(v, str) and not v.strip()):
            return 128
        return max(8, int(v))

    @field_validator("manual_scan_min_prefix", mode="before")
    @classmethod
    def _manual_scan_min_prefix(cls, v: object) -> int:
        if v is None or (isinstance(v, str) and not v.strip()):
            return 24
        return max(16, min(32, int(v)))

    @field_validator("manual_scan_warn_prefix", mode="before")
    @classmethod
    def _manual_scan_warn_prefix(cls, v: object) -> int:
        if v is None or (isinstance(v, str) and not v.strip()):
            return 24
        return max(16, min(32, int(v)))

    @field_validator("manual_scan_max_concurrency", mode="before")
    @classmethod
    def _manual_scan_max_concurrency(cls, v: object) -> int:
        if v is None or (isinstance(v, str) and not v.strip()):
            return 32
        return max(4, int(v))

    @field_validator("manual_scan_batch_delay", mode="before")
    @classmethod
    def _manual_scan_batch_delay(cls, v: object) -> float:
        if v is None or (isinstance(v, str) and not v.strip()):
            return 0.15
        return max(0.05, float(v))

    @field_validator("discovery_mode", mode="before")
    @classmethod
    def _discovery_mode(cls, v: object) -> str:
        if v is None or (isinstance(v, str) and not v.strip()):
            return "local"
        mode = str(v).strip().lower()
        return mode if mode in ("local", "remote", "arp", "adaptive") else "local"

    @field_validator("discovery_policy", mode="before")
    @classmethod
    def _discovery_policy(cls, v: object) -> str | None:
        if v is None or (isinstance(v, str) and not v.strip()):
            return None
        from app.discovery_policy import normalize_policy

        return normalize_policy(str(v))

    @field_validator("discovery_schedule", mode="before")
    @classmethod
    def _discovery_schedule(cls, v: object) -> str:
        if v is None or (isinstance(v, str) and not v.strip()):
            return "03:00"
        return str(v).strip()

    @field_validator("passive_interval", mode="before")
    @classmethod
    def _passive_interval(cls, v: object) -> int:
        if v is None or (isinstance(v, str) and not v.strip()):
            return 600
        return max(300, int(v))

    @field_validator("discovery_profile", mode="before")
    @classmethod
    def _discovery_profile(cls, v: object) -> str:
        if v is None or (isinstance(v, str) and not v.strip()):
            return "auto"
        profile = str(v).strip().lower()
        return profile if profile in ("auto", "weak", "normal", "strong") else "auto"

    @field_validator("discovery_interval", mode="before")
    @classmethod
    def _discovery_interval(cls, v: object) -> int | None:
        if v is None or (isinstance(v, str) and not v.strip()):
            return None
        return max(60, int(v))

    @field_validator("discovery_port_probe", mode="before")
    @classmethod
    def _discovery_port_probe(cls, v: object) -> bool:
        if v is None or (isinstance(v, str) and not v.strip()):
            return True
        if isinstance(v, str):
            return v.strip().lower() in ("true", "1", "yes", "on")
        return bool(v)

    @field_validator("discovery_port_max_hosts", mode="before")
    @classmethod
    def _discovery_port_max_hosts(cls, v: object) -> int:
        if v is None or (isinstance(v, str) and not v.strip()):
            return 5
        return max(1, int(v))

    @field_validator("arp_interval", mode="before")
    @classmethod
    def _arp_interval(cls, v: object) -> int:
        if v is None or (isinstance(v, str) and not v.strip()):
            return 300
        return max(60, int(v))

    @field_validator("arp_probe_new_hosts", mode="before")
    @classmethod
    def _arp_probe_new_hosts(cls, v: object) -> bool:
        if v is None or (isinstance(v, str) and not v.strip()):
            return True
        if isinstance(v, str):
            return v.strip().lower() in ("true", "1", "yes", "on")
        return bool(v)

    @field_validator("startup_health_defer", mode="before")
    @classmethod
    def _startup_health_defer(cls, v: object) -> bool | None:
        if v is None or (isinstance(v, str) and not v.strip()):
            return None
        if isinstance(v, str):
            return v.strip().lower() in ("true", "1", "yes", "on")
        return bool(v)

    @field_validator("startup_health_defer_seconds", mode="before")
    @classmethod
    def _startup_health_defer_seconds(cls, v: object) -> int | None:
        if v is None or (isinstance(v, str) and not v.strip()):
            return None
        return max(0, int(v))

    @field_validator("health_offline_after_failures", mode="before")
    @classmethod
    def _health_offline_after_failures(cls, v: object) -> int:
        if v is None or (isinstance(v, str) and not v.strip()):
            return 2
        return max(1, int(v))

    @field_validator("stale_remove_days", mode="before")
    @classmethod
    def _stale_remove_days(cls, v: object) -> int:
        if v is None or (isinstance(v, str) and not v.strip()):
            return 0
        return max(0, min(365, int(v)))

    @field_validator("discovery_startup_delay", mode="before")
    @classmethod
    def _discovery_startup_delay(cls, v: object) -> int:
        if v is None or (isinstance(v, str) and not v.strip()):
            return 60
        return max(0, int(v))

    @field_validator("arp_ping_fallback", mode="before")
    @classmethod
    def _arp_ping_fallback(cls, v: object) -> bool:
        if v is None or (isinstance(v, str) and not v.strip()):
            return True
        if isinstance(v, str):
            return v.strip().lower() in ("true", "1", "yes", "on")
        return bool(v)

    @field_validator("arp_ping_max_hosts", mode="before")
    @classmethod
    def _arp_ping_max_hosts(cls, v: object) -> int:
        if v is None or (isinstance(v, str) and not v.strip()):
            return 128
        return max(8, int(v))

    @field_validator("arp_ping_delay", mode="before")
    @classmethod
    def _arp_ping_delay(cls, v: object) -> float:
        if v is None or (isinstance(v, str) and not v.strip()):
            return 0.1
        return max(0.05, float(v))

    @field_validator("scan_safe_block_wide", mode="before")
    @classmethod
    def _scan_safe_block_wide(cls, v: object) -> bool:
        if v is None or (isinstance(v, str) and not v.strip()):
            return True
        if isinstance(v, str):
            return v.strip().lower() in ("true", "1", "yes", "on")
        return bool(v)

    @field_validator("scan_chunk_size", mode="before")
    @classmethod
    def _scan_chunk_size(cls, v: object) -> int:
        if v is None or (isinstance(v, str) and not v.strip()):
            return 4
        return int(v)

    @field_validator("ips_friendly", mode="before")
    @classmethod
    def _ips_friendly(cls, v: object) -> bool:
        if v is None or (isinstance(v, str) and not v.strip()):
            return True
        if isinstance(v, str):
            return v.strip().lower() in ("true", "1", "yes", "on")
        return bool(v)

    @field_validator("scan_randomize_ports", mode="before")
    @classmethod
    def _scan_randomize_ports(cls, v: object) -> bool:
        if v is None or (isinstance(v, str) and not v.strip()):
            return True
        if isinstance(v, str):
            return v.strip().lower() in ("true", "1", "yes", "on")
        return bool(v)

    @field_validator("port_parallel_per_host", mode="before")
    @classmethod
    def _port_parallel_per_host(cls, v: object) -> int:
        if v is None or (isinstance(v, str) and not v.strip()):
            return 1
        return max(1, int(v))

    @field_validator("ports_per_host_delay", mode="before")
    @classmethod
    def _ports_per_host_delay(cls, v: object) -> float:
        if v is None or (isinstance(v, str) and not v.strip()):
            return 0.3
        return max(0.0, float(v))

    @field_validator("ports_per_host_jitter", mode="before")
    @classmethod
    def _ports_per_host_jitter(cls, v: object) -> float:
        if v is None or (isinstance(v, str) and not v.strip()):
            return 0.2
        return max(0.0, float(v))

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
        if self.scan_safe_mode:
            chunk = max(1, self.scan_chunk_size)
            self.scan_batch_size = chunk
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
        base = self.scan_safe_concurrency if self.scan_safe_mode else self.scan_concurrency
        if not self.scan_safe_mode:
            return min(base, self.manual_scan_max_concurrency)
        return base

    @property
    def effective_scan_max_hosts(self) -> int:
        return self.scan_safe_max_hosts if self.scan_safe_mode else self.scan_max_hosts

    @property
    def effective_port_parallel_per_host(self) -> int:
        """Concurrent probes allowed to a single host. IPS-friendly caps this (default 1);
        when disabled, fall back to broad concurrency so behaviour matches pre-1.3.149."""
        if not self.ips_friendly:
            return max(1, self.effective_scan_concurrency)
        return max(1, self.port_parallel_per_host)

    @property
    def effective_ports_per_host_delay(self) -> float:
        """Delay between consecutive probes to the same host — 0 when IPS-friendly is off."""
        if not self.ips_friendly:
            return 0.0
        return max(0.0, self.ports_per_host_delay)

    @property
    def effective_scan_max_duration(self) -> float:
        return self.scan_safe_max_duration if self.scan_safe_mode else self.scan_max_duration

    @property
    def resource_profile(self) -> str:
        """Runtime scan intensity: safe (default) or normal (NETDASH_SCAN_SAFE_MODE=false)."""
        return "safe" if self.scan_safe_mode else "normal"

    @property
    def effective_discovery_mode(self) -> str:
        if self.scan_disabled:
            return "remote"
        policy = self.effective_discovery_policy
        if policy == "adaptive":
            return "adaptive"
        if policy == "passive":
            return "arp"
        if policy in ("off", "on_demand", "scheduled"):
            return "local"
        return self.discovery_mode

    @property
    def effective_discovery_policy(self) -> str:
        from app.discovery_policy import resolve_discovery_policy
        from app.discovery_runtime import get_app_discovery_policy

        policy = resolve_discovery_policy(get_app_discovery_policy())
        if policy == "off":
            return "off"
        if not self.effective_discovery_enabled and policy in ("scheduled", "passive", "adaptive"):
            return "off"
        return policy

    @property
    def discovery_env_locked(self) -> bool:
        """True when NETDASH_DISCOVERY_ENABLED or NETDASH_DISCOVERY_POLICY is set in env."""
        from app.discovery_policy import policy_env_locked

        raw = os.environ.get("NETDASH_DISCOVERY_ENABLED")
        return (raw is not None and bool(str(raw).strip())) or policy_env_locked()

    @property
    def effective_discovery_enabled(self) -> bool:
        """Honour NETDASH_DISCOVERY_ENABLED env; UI/DB toggle; auto-off on <~2.1 GB RAM when unset."""
        raw = os.environ.get("NETDASH_DISCOVERY_ENABLED")
        if raw is not None and str(raw).strip():
            return str(raw).strip().lower() in ("true", "1", "yes", "on")
        from app.discovery_runtime import get_app_discovery_enabled

        app_pref = get_app_discovery_enabled()
        if app_pref is not None and not app_pref:
            return False
        if not self.discovery_enabled:
            return False
        try:
            with open("/proc/meminfo", encoding="utf-8") as fh:
                for line in fh:
                    if line.startswith("MemTotal:"):
                        mem_kb = int(line.split()[1])
                        if mem_kb < 2_100_000:
                            return False
                        break
        except OSError:
            pass
        return True

    @property
    def adaptive_discovery_enabled(self) -> bool:
        return (
            self.effective_discovery_enabled
            and not self.scan_disabled
            and self.effective_discovery_policy == "adaptive"
        )

    @property
    def arp_discovery_enabled(self) -> bool:
        return (
            self.effective_discovery_enabled
            and not self.scan_disabled
            and self.discovery_mode == "arp"
            and self.effective_discovery_policy not in ("passive", "scheduled", "on_demand", "off")
        )

    @property
    def passive_discovery_enabled(self) -> bool:
        return (
            self.effective_discovery_enabled
            and not self.scan_disabled
            and self.effective_discovery_policy == "passive"
        )

    @property
    def scheduled_discovery_enabled(self) -> bool:
        return (
            self.effective_discovery_enabled
            and not self.scan_disabled
            and self.effective_discovery_policy == "scheduled"
        )

    @property
    def on_demand_discovery(self) -> bool:
        return self.effective_discovery_policy == "on_demand"

    @property
    def auto_discovery_enabled(self) -> bool:
        return (
            self.adaptive_discovery_enabled
            or self.arp_discovery_enabled
            or self.passive_discovery_enabled
            or self.scheduled_discovery_enabled
        )

    @property
    def effective_startup_health_defer(self) -> bool:
        if self.startup_health_defer is not None:
            return self.startup_health_defer
        return self.scan_safe_mode

    @property
    def effective_startup_health_defer_seconds(self) -> int:
        if self.startup_health_defer_seconds is not None:
            return self.startup_health_defer_seconds
        return 90 if self.scan_safe_mode else 5

    @property
    def effective_discovery_startup_delay(self) -> int:
        if self.discovery_startup_delay != 60:
            return self.discovery_startup_delay
        return 180 if self.scan_safe_mode else 60

    @property
    def effective_startup_enrich_enabled(self) -> bool:
        if not self.startup_enrich_enabled:
            return False
        return self.effective_discovery_enabled

    @property
    def health_check_concurrency(self) -> int:
        return 2 if self.scan_safe_mode else 10

    @property
    def scan_identify_concurrency(self) -> int:
        return 2 if self.scan_safe_mode else 20

    @property
    def effective_scan_batch_size(self) -> int:
        if self.scan_safe_mode:
            return max(1, self.scan_chunk_size)
        return self.scan_batch_size


settings = Settings()
