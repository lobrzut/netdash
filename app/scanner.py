import asyncio
import ipaddress
import platform
import re
import socket
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse
from typing import Awaitable, Callable

import httpx

from app.config import settings
from app.icons import resolve_brand_icon, resolve_icon_url
from app.url_utils import ensure_str, sanitize_service_url

WEB_PORTS = [
    80, 81, 443, 3000, 4000, 4200, 4443, 5000, 5001, 8000, 8008,
    8080, 8081, 8443, 8888, 9000, 9090, 9443, 6443, 8787, 18787,
]

# Desktop / OS-revealing ports scanned in default mode (alongside WEB_PORTS).
HOST_DISCOVERY_PORTS = [22, 445, 3389, 5900]
DEFAULT_HOST_SCAN_PORTS = "22,445,3389,5900"
HOST_ONLY_PORT = 0

OS_PORT_HINTS: dict[int, str] = {
    22: "Linux/macOS (SSH)",
    445: "Windows (SMB)",
    3389: "Windows (RDP)",
    5900: "VNC (zdalny pulpit)",
}

HTTPS_PORTS = {443, 8443, 9443, 6443, 4443}
HTTP_FIRST_PORTS = {80, 81, 8080, 8081, 8000, 8008, 3000, 5000, 5001, 8888, 9000, 9090, 8787, 18787, 4000, 4200}

TLS_MISMATCH_RE = re.compile(
    r"plain HTTP request was sent to HTTPS|"
    r"client sent an HTTP request to an HTTPS server|"
    r"The plain HTTP request was sent to HTTPS|"
    r"HTTPS port|"
    r"SSL handshake|"
    r"Bad Request</title>",
    re.IGNORECASE,
)

GENERIC_TITLES = {
    "400 bad request", "bad request", "403 forbidden", "forbidden",
    "401 unauthorized", "401 authorization required", "authorization required",
    "unauthorized", "404 not found", "not found",
    "error", "login", "sign in",
}

HTTP_ERROR_TITLE_RE = re.compile(
    r"^\d{3}\s+(?:authorization|unauthorized|forbidden|not\s+found|bad\s+request|"
    r"internal\s+server|service\s+unavailable|gateway|error)",
    re.IGNORECASE,
)

COMMON_PORTS = [
    21, 22, 23, 25, 53, 80, 81, 88, 110, 135, 139, 143, 443, 445,
    465, 587, 993, 995, 1433, 1521, 1883, 2049, 3000, 3306, 3389,
    4000, 4200, 4443, 5000, 5001, 5432, 5672, 5900, 6379, 6443,
    8000, 8008, 8080, 8081, 8443, 8888, 9000, 9090, 9200, 9443,
    10000, 27017, 8787, 18787,
]

NOISE_PORTS = {135, 139, 445, 110, 143, 993, 995, 587, 465, 25, 23}

PORT_SIGNATURES: dict[int, tuple[str, str, str]] = {
    21: ("FTP", "ftp", "Pliki"),
    22: ("SSH", "terminal", "Zdalny dostęp"),
    23: ("Telnet", "terminal", "Zdalny dostęp"),
    25: ("SMTP", "mail", "Poczta"),
    53: ("DNS", "dns", "Sieć"),
    80: ("HTTP", "globe", "Web"),
    443: ("HTTPS", "lock", "Web"),
    445: ("SMB", "folder", "Pliki"),
    3000: ("Node.js / Dev", "code", "Development"),
    3306: ("MySQL", "database", "Baza danych"),
    3389: ("RDP", "monitor", "Zdalny dostęp"),
    5900: ("VNC", "monitor", "Zdalny dostęp"),
    4200: ("Angular Dev", "code", "Development"),
    5000: ("Flask / API", "api", "API"),
    5432: ("PostgreSQL", "database", "Baza danych"),
    5672: ("RabbitMQ", "queue", "Kolejka"),
    6379: ("Redis", "database", "Cache"),
    8000: ("HTTP Alt", "globe", "Web"),
    8080: ("HTTP Proxy", "globe", "Web"),
    8443: ("HTTPS Alt", "lock", "Web"),
    9000: ("Portainer / Sonar", "docker", "DevOps"),
    9090: ("Prometheus", "chart", "Monitoring"),
    9200: ("Elasticsearch", "search", "Baza danych"),
    27017: ("MongoDB", "database", "Baza danych"),
    8787: ("NetDash (legacy)", "dashboard", "Dashboard"),
    18787: ("NetDash", "dashboard", "Dashboard"),
}

HTTP_TITLE_RE = re.compile(r"<title[^>]*>([^<]+)</title>", re.IGNORECASE)
SERVER_RE = re.compile(r"server:\s*([^\r\n]+)", re.IGNORECASE)

SERVER_HINTS: list[tuple[str, str, str, str]] = [
    (r"nginx", "Nginx", "nginx", "Web"),
    (r"apache", "Apache", "apache", "Web"),
    (r"cloudflare", "Cloudflare", "cloud", "CDN"),
    (r"microsoft-iis", "IIS", "windows", "Web"),
    (r"caddy", "Caddy", "caddy", "Web"),
    (r"traefik", "Traefik", "traefik", "DevOps"),
    (r"gunicorn", "Gunicorn", "python", "API"),
    (r"uvicorn", "Uvicorn/FastAPI", "python", "API"),
    (r"openresty", "OpenResty", "nginx", "Web"),
]

TITLE_HINTS: list[tuple[str, str, str, str]] = [
    (r"portainer", "Portainer", "docker", "DevOps"),
    (r"grafana", "Grafana", "chart", "Monitoring"),
    (r"prometheus", "Prometheus", "chart", "Monitoring"),
    (r"home\s*assistant", "Home Assistant", "home", "Smart Home"),
    (r"plex", "Plex", "play", "Media"),
    (r"jellyfin", "Jellyfin", "play", "Media"),
    (r"sonarr", "Sonarr", "tv", "Media"),
    (r"radarr", "Radarr", "film", "Media"),
    (r"readarr", "Readarr", "doc", "Media"),
    (r"lidarr", "Lidarr", "play", "Media"),
    (r"prowlarr", "Prowlarr", "search", "Media"),
    (r"transmission", "Transmission", "download", "Media"),
    (r"qbittorrent", "qBittorrent", "download", "Media"),
    (r"nextcloud", "Nextcloud", "cloud", "Pliki"),
    (r"synology", "Synology DSM", "nas", "NAS"),
    (r"truenas", "TrueNAS", "nas", "NAS"),
    (r"qnap|qts|quts", "QNAP", "nas", "NAS"),
    (r"unraid", "Unraid", "nas", "NAS"),
    (r"open\s*media\s*vault|\bomv\b", "OpenMediaVault", "nas", "NAS"),
    (r"unifi", "UniFi", "wifi", "Sieć"),
    (r"opnsense", "OPNsense", "router", "Sieć"),
    (r"pfsense", "pfSense", "router", "Sieć"),
    (r"router", "Router", "router", "Sieć"),
    (r"openwrt", "OpenWrt", "router", "Sieć"),
    (r"gitlab", "GitLab", "git", "DevOps"),
    (r"github", "GitHub Enterprise", "git", "DevOps"),
    (r"gitea", "Gitea", "git", "DevOps"),
    (r"jenkins", "Jenkins", "ci", "DevOps"),
    (r"vault", "HashiCorp Vault", "lock", "Bezpieczeństwo"),
    (r"minio", "MinIO", "storage", "Storage"),
    (r"phpmyadmin", "phpMyAdmin", "database", "Baza danych"),
    (r"adminer", "Adminer", "database", "Baza danych"),
    (r"pgadmin", "pgAdmin", "database", "Baza danych"),
    (r"vaultwarden", "Vaultwarden", "lock", "Bezpieczeństwo"),
    (r"bitwarden", "Bitwarden", "lock", "Bezpieczeństwo"),
    (r"immich", "Immich", "photo", "Media"),
    (r"paperless", "Paperless", "doc", "Dokumenty"),
    (r"homer", "Homer", "dashboard", "Dashboard"),
    (r"netdash", "NetDash", "dashboard", "Dashboard"),
    (r"pi-hole", "Pi-hole", "shield", "Sieć"),
    (r"pihole", "Pi-hole", "shield", "Sieć"),
    (r"adguard", "AdGuard", "shield", "Sieć"),
    (r"n8n", "n8n", "workflow", "Automatyzacja"),
    (r"homebridge", "Homebridge", "home", "Smart Home"),
    (r"esphome", "ESPHome", "home", "Smart Home"),
    (r"zigbee2mqtt|zigbee", "Zigbee2MQTT", "home", "Smart Home"),
    (r"proxmox", "Proxmox", "server", "DevOps"),
    (r"uptime\s*kuma", "Uptime Kuma", "chart", "Monitoring"),
    (r"frigate", "Frigate", "home", "Smart Home"),
    (r"audiobookshelf", "Audiobookshelf", "play", "Media"),
    (r"photoprism", "PhotoPrism", "photo", "Media"),
    (r"mosquitto", "Eclipse Mosquitto", "mqtt", "Automatyzacja"),
    (r"code-server", "code-server", "code", "Development"),
    (r"ollama", "Ollama", "ai", "AI"),
    (r"openwebui", "Open WebUI", "ai", "AI"),
    (r"comfyui", "ComfyUI", "ai", "AI"),
    (r"stable\s*diffusion", "Stable Diffusion", "ai", "AI"),
]

ProgressCallback = Callable[[str, int, int], Awaitable[None]]
ServiceCallback = Callable[["DiscoveredService"], Awaitable[None]]


LOGIN_TITLE_RE = re.compile(
    r"login|log\s*in|sign\s*in|sign-in|zaloguj|"
    r"authorization required|authenticate|authentication|"
    r"please log|session|portal|dashboard login|admin login",
    re.IGNORECASE,
)
LOGIN_PATH_RE = re.compile(r"/(login|signin|sign-in|auth|sso|session)(/|$)", re.IGNORECASE)
PASSWORD_FIELD_RE = re.compile(
    r'<input[^>]+type=["\']password["\']|type=["\']password["\'][^>]*>|<input[^>]+name=["\']password["\']',
    re.IGNORECASE,
)

LOGIN_KNOWN_SERVICES = {
    "Grafana", "Portainer", "Prometheus", "Home Assistant", "Plex", "Jellyfin",
    "Sonarr", "Radarr", "Prowlarr", "Nextcloud", "Synology DSM", "TrueNAS",
    "QNAP", "Unraid", "OpenMediaVault",
    "UniFi", "GitLab", "GitHub Enterprise", "Gitea", "Jenkins", "HashiCorp Vault",
    "Vaultwarden", "Bitwarden", "Immich", "Paperless", "Pi-hole", "AdGuard",
    "n8n", "Homebridge", "ESPHome", "Zigbee2MQTT", "OPNsense", "pfSense",
    "Proxmox", "Uptime Kuma", "Frigate", "code-server", "Ollama", "Open WebUI",
    "phpMyAdmin", "Adminer", "pgAdmin", "NetDash", "Homer", "qBittorrent",
    "Transmission", "MinIO",
}

SERVICE_HINT_TAGS: dict[str, list[str]] = {
    "QNAP": ["nas", "storage", "qts"],
    "Synology DSM": ["nas", "storage", "dsm"],
    "TrueNAS": ["nas", "storage", "zfs"],
    "OpenMediaVault": ["nas", "storage", "omv"],
    "Unraid": ["nas", "docker", "storage"],
    "OPNsense": ["firewall", "router", "network"],
    "pfSense": ["firewall", "router", "network"],
    "Zigbee2MQTT": ["smarthome", "zigbee", "mqtt"],
    "ESPHome": ["smarthome", "iot"],
    "Uptime Kuma": ["monitoring", "uptime"],
}

SERVICE_HINT_NOTES: dict[str, str] = {
    "QNAP": "Panel zarządzania NAS (QTS/QuTS hero).",
    "Synology DSM": "Panel zarządzania NAS Synology (DSM).",
    "TrueNAS": "Panel zarządzania pamięcią masową TrueNAS.",
    "OpenMediaVault": "Panel zarządzania NAS OpenMediaVault.",
    "Unraid": "Panel serwera Unraid z usługami Docker/VM.",
    "OPNsense": "Panel firewall/router OPNsense.",
    "pfSense": "Panel firewall/router pfSense.",
}


@dataclass
class DiscoveredService:
    host: str
    port: int
    name: str
    url: str
    protocol: str
    category: str
    icon: str
    description: str | None = None
    has_login: bool = False
    icon_url: str | None = None
    health_detail: str | None = None


def get_local_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def is_running_in_docker() -> bool:
    if Path("/.dockerenv").exists():
        return True
    try:
        cgroup = Path("/proc/1/cgroup").read_text(encoding="utf-8", errors="ignore")
        return "docker" in cgroup or "containerd" in cgroup or "kubepods" in cgroup
    except OSError:
        return False


def is_docker_bridge_ip(ip: str) -> bool:
    try:
        return ipaddress.ip_address(ip) in ipaddress.ip_network("172.16.0.0/12")
    except ValueError:
        return False


def is_likely_docker_bridge() -> bool:
    """True when container sees Docker bridge IP instead of host LAN."""
    if not is_running_in_docker():
        return False
    return is_docker_bridge_ip(get_local_ip())


def get_local_network() -> str:
    if settings.scan_cidr:
        return settings.scan_cidr.strip()
    try:
        local_ip = get_local_ip()
        network = ipaddress.ip_network(f"{local_ip}/24", strict=False)
        return str(network)
    except (OSError, ValueError):
        return "192.168.1.0/24"


def parse_scan_cidrs(text: str) -> list[str]:
    """Parse comma/newline/semicolon separated CIDR list."""
    if not text or not text.strip():
        return []
    parts = re.split(r"[\s,;]+", text.strip())
    cidrs: list[str] = []
    seen: set[str] = set()
    for part in parts:
        part = part.strip()
        if not part:
            continue
        try:
            network = ipaddress.ip_network(part, strict=False)
            cidr_str = str(network)
        except ValueError as exc:
            raise ValueError(f"Nieprawidłowy CIDR: {part}") from exc
        if cidr_str not in seen:
            seen.add(cidr_str)
            cidrs.append(cidr_str)
    return cidrs


def normalize_scan_cidr_list(text: str | None) -> str | None:
    if not text or not text.strip():
        return None
    cidrs = parse_scan_cidrs(text)
    return ", ".join(cidrs) if cidrs else None


def format_cidr_list(cidrs: list[str]) -> str:
    return ", ".join(cidrs)


def resolve_scan_cidrs(
    cidr: str | None = None,
    scan_cidr_default: str | None = None,
) -> list[str]:
    if cidr and cidr.strip():
        return parse_scan_cidrs(cidr)
    if scan_cidr_default and scan_cidr_default.strip():
        return parse_scan_cidrs(scan_cidr_default)
    return [get_local_network()]


def resolve_scan_cidr(
    cidr: str | None = None,
    scan_cidr_default: str | None = None,
) -> str:
    return format_cidr_list(resolve_scan_cidrs(cidr, scan_cidr_default))


def parse_host_scan_ports(ports_str: str | None) -> list[int]:
    if not ports_str:
        return list(HOST_DISCOVERY_PORTS)
    ports: list[int] = []
    for part in ports_str.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            port = int(part)
            if 1 <= port <= 65535:
                ports.append(port)
        except ValueError:
            continue
    return sorted(set(ports)) if ports else list(HOST_DISCOVERY_PORTS)


def _resolve_display_name(host: str) -> str:
    try:
        name, _, _ = socket.gethostbyaddr(host)
        if name and name != host:
            short = name.split(".")[0]
            return short if short else name
    except (socket.herror, socket.gaierror, OSError):
        pass
    return host


def _apply_os_hint(service: DiscoveredService) -> DiscoveredService:
    hint = OS_PORT_HINTS.get(service.port)
    if not hint:
        return service
    suffix = f"Prawdopodobnie: {hint}"
    if service.description:
        if hint not in service.description:
            service.description = f"{service.description} · {hint}"
    else:
        service.description = suffix
    return service


def _local_hostname() -> str:
    try:
        name = socket.gethostname().split(".")[0].strip()
        if name:
            return name
    except OSError:
        pass
    return "Ten komputer"


def build_local_host_service() -> DiscoveredService:
    local_ip = get_local_ip()
    return DiscoveredService(
        host=local_ip,
        port=HOST_ONLY_PORT,
        name=_local_hostname(),
        url="#",
        protocol="host",
        category="Urządzenie",
        icon="monitor",
        icon_url=None,
        description="Ten komputer (NetDash działa tutaj)",
    )


def _create_host_only_service(host: str) -> DiscoveredService:
    local_ip = get_local_ip()
    if host == local_ip:
        return build_local_host_service()
    display = _resolve_display_name(host)
    name = display if display != host else f"Urządzenie {host}"
    return DiscoveredService(
        host=host,
        port=HOST_ONLY_PORT,
        name=name,
        url="#",
        protocol="host",
        category="Urządzenie",
        icon="monitor",
        icon_url=None,
        description="Wykryto przez ping — brak otwartych portów usługowych",
    )


def parse_cidr(cidr: str) -> list[str]:
    network = ipaddress.ip_network(cidr.strip(), strict=False)
    hosts = [str(host) for host in network.hosts()]
    if len(hosts) > 1024:
        hosts = hosts[:1024]
    return hosts


async def _ping_host(host: str) -> bool:
    if host in ("127.0.0.1", "localhost"):
        return True
    if host == get_local_ip():
        return True
    if platform.system().lower() == "windows":
        cmd = ["ping", "-n", "1", "-w", "400", host]
    else:
        cmd = ["ping", "-c", "1", "-W", "1", host]
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await asyncio.wait_for(proc.wait(), timeout=2)
        return proc.returncode == 0
    except (asyncio.TimeoutError, OSError):
        return False


async def discover_live_hosts(cidr: str, progress_callback: ProgressCallback | None = None) -> list[str]:
    candidates = parse_cidr(cidr)
    local_ip = get_local_ip()
    extra = {"127.0.0.1", local_ip}
    try:
        network = ipaddress.ip_network(cidr.strip(), strict=False)
        extra.add(str(network.network_address + 1))
    except ValueError:
        pass

    sem = asyncio.Semaphore(32)
    live: set[str] = set(extra)
    total = len(candidates)
    done = 0

    async def ping_one(host: str):
        nonlocal done
        async with sem:
            if await _ping_host(host):
                live.add(host)
        done += 1
        if progress_callback and done % 20 == 0:
            await progress_callback("ping", done, total)

    await asyncio.gather(*(ping_one(host) for host in candidates))
    if progress_callback:
        await progress_callback("ping", total, total)
    return sorted(live)


async def _check_port(host: str, port: int, sem: asyncio.Semaphore) -> bool:
    async with sem:
        try:
            conn = asyncio.open_connection(host, port)
            _, writer = await asyncio.wait_for(conn, timeout=settings.scan_timeout)
            writer.close()
            await writer.wait_closed()
            return True
        except (asyncio.TimeoutError, OSError, ConnectionRefusedError):
            return False


def _match_hints(text: str, hints: list[tuple[str, str, str, str]]) -> tuple[str, str, str] | None:
    lowered = text.lower()
    for pattern, name, icon, category in hints:
        if re.search(pattern, lowered):
            return name, icon, category
    return None


def suggest_service_identity(
    *,
    name: str | None = None,
    url: str | None = None,
    description: str | None = None,
    category: str | None = None,
    icon: str | None = None,
    icon_url: str | None = None,
    has_login: bool | None = None,
) -> dict[str, object]:
    """Best-effort service identification from user-provided fields."""

    raw_name = (name or "").strip()
    raw_url = (url or "").strip()
    raw_description = (description or "").strip()
    safe_url = sanitize_service_url(raw_url)
    parsed = urlparse(safe_url or raw_url)
    host = (parsed.hostname or "").strip()
    path = parsed.path or ""

    probe_text = " ".join(
        part for part in (raw_name, raw_description, safe_url, host, path, parsed.query) if part
    )
    hint = _match_hints(probe_text, TITLE_HINTS) if probe_text else None
    matched_by: list[str] = []
    heuristics: list[str] = []

    suggested_name = raw_name
    suggested_icon = (icon or "globe").lower()
    suggested_category = (category or "Inne").strip() or "Inne"

    if hint:
        suggested_name, suggested_icon, suggested_category = hint
        matched_by.append("title_or_url_signature")
        heuristics.append("signature matching against known homelab brands")
    elif raw_name:
        suggested_name = re.sub(r"\s+", " ", raw_name).strip()
        heuristics.append("input name normalization")

    normalized_url = safe_url or raw_url
    if normalized_url and normalized_url != raw_url:
        matched_by.append("url_sanitization")
        heuristics.append("URL cleanup via sanitize_service_url")

    suggested_icon_url = icon_url
    brand_icon = resolve_brand_icon(
        suggested_name,
        raw_name,
        raw_description,
        normalized_url,
        host,
    )
    if brand_icon:
        suggested_icon_url = brand_icon
        matched_by.append("brand_icon_mapping")
        heuristics.append("icon mapping from known brand slugs")

    inferred_login = bool(has_login)
    if (
        suggested_name in LOGIN_KNOWN_SERVICES
        or LOGIN_TITLE_RE.search(probe_text)
        or LOGIN_PATH_RE.search(path)
    ):
        inferred_login = True
        matched_by.append("login_inference")
        heuristics.append("login inference from known services and auth patterns")

    tags = SERVICE_HINT_TAGS.get(suggested_name, [])
    note = SERVICE_HINT_NOTES.get(suggested_name)

    suggested_description = raw_description or None
    if note and not suggested_description:
        suggested_description = note
        matched_by.append("brand_note_template")
        heuristics.append("brand-specific description template")

    suggestion = {
        "name": suggested_name or raw_name or None,
        "url": normalized_url or None,
        "category": suggested_category,
        "icon": suggested_icon,
        "icon_url": suggested_icon_url,
        "description": suggested_description,
        "has_login": inferred_login,
    }

    changed_fields: list[str] = []
    if suggestion["name"] and suggestion["name"] != (raw_name or None):
        changed_fields.append("name")
    if suggestion["url"] and suggestion["url"] != (raw_url or None):
        changed_fields.append("url")
    if suggestion["category"] and suggestion["category"] != (category or "Inne"):
        changed_fields.append("category")
    if suggestion["icon"] and suggestion["icon"] != (icon or "globe").lower():
        changed_fields.append("icon")
    if suggestion["icon_url"] != icon_url:
        changed_fields.append("icon_url")
    if suggestion["description"] != (raw_description or None):
        changed_fields.append("description")
    if bool(suggestion["has_login"]) != bool(has_login):
        changed_fields.append("has_login")

    confidence = "low"
    if "title_or_url_signature" in matched_by and "brand_icon_mapping" in matched_by:
        confidence = "high"
    elif hint or len(matched_by) >= 2:
        confidence = "medium"

    return {
        "matched": bool(hint or brand_icon),
        "confidence": confidence,
        "matched_by": sorted(set(matched_by)),
        "heuristics": heuristics,
        "changed_fields": changed_fields,
        "tags": tags,
        "note": note,
        "suggestion": suggestion,
    }


def _base_from_port(port: int) -> tuple[str, str, str]:
    return PORT_SIGNATURES.get(port, (f"Port {port}", "plug", "Inne"))


def _is_generic_title(title: str) -> bool:
    clean = re.sub(r"\s+", " ", title).strip().lower()
    if not clean:
        return True
    if clean in GENERIC_TITLES:
        return True
    if HTTP_ERROR_TITLE_RE.match(clean):
        return True
    if re.match(r"^\d{3}[\s:.\-]+", clean):
        return True
    if re.search(r"\b(401|403|404|500)\b.*\b(authorization|unauthorized|forbidden|not\s+found)\b", clean):
        return True
    if re.search(r"\b(authorization\s+required|unauthorized|forbidden|not\s+found|bad\s+request)\b", clean):
        return True
    return False


def is_http_error_name(name: str) -> bool:
    """True when a string looks like an HTTP status page title, not a service name."""
    return _is_generic_title(name)


def _fallback_service_name(host: str, port: int, name: str) -> str:
    if name and not name.startswith("Port "):
        return name
    if host:
        return f"{host}:{port}" if port else host
    return f"Service :{port}" if port else "Service"


def _schemes_for_port(port: int) -> list[str]:
    if port in HTTPS_PORTS:
        return ["https", "http"]
    if port in HTTP_FIRST_PORTS:
        return ["http", "https"]
    return ["https", "http"]


def _build_url(host: str, port: int, scheme: str) -> str:
    if (scheme == "https" and port == 443) or (scheme == "http" and port == 80):
        return f"{scheme}://{host}"
    return f"{scheme}://{host}:{port}"


def _canonical_url(host: str, port: int, response: httpx.Response) -> str:
    final = response.url
    final_port = final.port or (443 if final.scheme == "https" else 80)
    if final_port == port:
        path = ensure_str(final.path or "/")
        query = ensure_str(final.query) if final.query else ""
        if query:
            path += f"?{query}"
        base = _build_url(host, port, final.scheme)
        url = base if path == "/" else f"{base}{path}"
        return sanitize_service_url(url)
    return _build_url(host, port, final.scheme)


def _detect_has_login(response: httpx.Response, body: str, title: str | None, service_name: str) -> bool:
    if response.status_code == 401:
        return True
    if response.headers.get("www-authenticate"):
        return True
    if title and LOGIN_TITLE_RE.search(title):
        return True
    if LOGIN_PATH_RE.search(str(response.url.path)):
        return True
    if PASSWORD_FIELD_RE.search(body):
        return True
    if service_name in LOGIN_KNOWN_SERVICES:
        return True
    if re.search(r'class=["\'][^"\']*login|id=["\']login-form|name=["\']username["\']', body, re.I):
        if PASSWORD_FIELD_RE.search(body) or re.search(r'type=["\']password', body, re.I):
            return True
    return False


def _probe_score(response: httpx.Response, body: str, title: str | None) -> int:
    if TLS_MISMATCH_RE.search(body):
        return -100
    score = 0
    if response.status_code < 400:
        score += 40
    elif response.status_code < 500:
        score += 10
    else:
        score -= 20
    if title and not _is_generic_title(title):
        score += 30
    if "text/html" in response.headers.get("content-type", ""):
        score += 10
    if response.headers.get("server"):
        score += 5
    if len(body) > 200:
        score += 5
    return score


def _parse_probe_response(host: str, port: int, response: httpx.Response) -> DiscoveredService:
    body = response.text[:8192]
    headers_text = "\n".join(f"{k}: {v}" for k, v in response.headers.items())

    title_match = HTTP_TITLE_RE.search(body)
    title = title_match.group(1).strip() if title_match else None

    name, icon, category = _base_from_port(port)
    description = None
    health_detail = None
    scheme = response.url.scheme

    if title:
        hint = _match_hints(title, TITLE_HINTS)
        if hint:
            name, icon, category = hint
        elif not _is_generic_title(title):
            name = re.sub(r"\s+", " ", title)[:80]
        else:
            body_hint = _match_hints(body, TITLE_HINTS)
            if body_hint:
                name, icon, category = body_hint
            else:
                name = _fallback_service_name(host, port, name)
        if _is_generic_title(title):
            health_detail = re.sub(r"\s+", " ", title).strip()[:128]
        description = title[:200]

    if is_http_error_name(name):
        if health_detail is None:
            health_detail = name[:128]
        name = _fallback_service_name(host, port, name)

    server_match = SERVER_RE.search(headers_text)
    if server_match:
        server_val = server_match.group(1)
        hint = _match_hints(server_val, SERVER_HINTS)
        generic = {_base_from_port(port)[0], f"Port {port}", "HTTP", "HTTPS", "HTTP Alt", "HTTPS Alt"}
        if hint and name in generic:
            name, icon, category = hint
        if not description:
            description = f"Server: {server_val[:120]}"

    has_login = _detect_has_login(response, body, title, name)
    canonical = _canonical_url(host, port, response)
    icon_url = resolve_icon_url(name, title, canonical, body)

    return DiscoveredService(
        host=host,
        port=port,
        name=name,
        url=canonical,
        protocol=scheme,
        category=category,
        icon=icon,
        icon_url=icon_url,
        description=description,
        has_login=has_login,
        health_detail=health_detail,
    )


def _is_dashboard_worthy(service: DiscoveredService) -> bool:
    if service.port == HOST_ONLY_PORT:
        return True
    if service.port in HOST_DISCOVERY_PORTS:
        return True
    if service.port in WEB_PORTS:
        return True
    if service.port in NOISE_PORTS:
        return False
    if service.category in ("Web", "API", "Development", "DevOps", "Monitoring", "Dashboard", "Media", "NAS", "Smart Home", "AI", "Automatyzacja"):
        return True
    if service.description and "Server:" in service.description:
        return True
    if service.name and not service.name.startswith("Port "):
        return True
    return service.port not in NOISE_PORTS


async def _probe_http(host: str, port: int) -> DiscoveredService | None:
    best: DiscoveredService | None = None
    best_score = -999

    async with httpx.AsyncClient(verify=False, follow_redirects=True, timeout=settings.http_timeout) as client:
        for scheme in _schemes_for_port(port):
            url = _build_url(host, port, scheme)
            try:
                response = await client.get(url, headers={"User-Agent": "NetDash/1.0 Scanner"})
                body = response.text[:8192]
                title_match = HTTP_TITLE_RE.search(body)
                title = title_match.group(1).strip() if title_match else None
                score = _probe_score(response, body, title)

                if score > best_score:
                    best_score = score
                    best = _parse_probe_response(host, port, response)

                if score >= 50:
                    return best
            except (httpx.HTTPError, asyncio.TimeoutError):
                continue

    return best if best_score > 0 else None


async def _identify_service(host: str, port: int) -> DiscoveredService:
    if port in WEB_PORTS:
        probed = await _probe_http(host, port)
        if probed:
            return probed

    name, icon, category = _base_from_port(port)
    if port in HTTPS_PORTS:
        protocol, url = "https", _build_url(host, port, "https")
    elif port in WEB_PORTS:
        protocol, url = "http", _build_url(host, port, "http")
    else:
        protocol, url = "tcp", f"tcp://{host}:{port}"

    service = DiscoveredService(
        host=host,
        port=port,
        name=name,
        url=url,
        protocol=protocol,
        category=category,
        icon=icon,
        icon_url=resolve_brand_icon(name),
        description=f"Wykryto otwarty port {port}",
    )
    return _apply_os_hint(service)


async def scan_network(
    cidr: str,
    *,
    full_scan: bool = False,
    host_scan_ports: list[int] | None = None,
    host_only_entries: bool = True,
    progress_callback: ProgressCallback | None = None,
    service_callback: ServiceCallback | None = None,
) -> list[DiscoveredService]:
    if full_scan:
        ports = COMMON_PORTS
    else:
        extra = host_scan_ports if host_scan_ports is not None else HOST_DISCOVERY_PORTS
        ports = sorted(set(WEB_PORTS + extra))

    if progress_callback:
        await progress_callback("ping", 0, 1)
    live_hosts = await discover_live_hosts(cidr, progress_callback)

    if progress_callback:
        await progress_callback("ports", 0, len(live_hosts) * len(ports))

    sem = asyncio.Semaphore(settings.scan_concurrency)
    open_ports: list[tuple[str, int]] = []
    total = len(live_hosts) * len(ports)
    done = 0

    async def scan_one(host: str, port: int):
        nonlocal done
        if await _check_port(host, port, sem):
            open_ports.append((host, port))
        done += 1
        if progress_callback and done % 50 == 0:
            await progress_callback("ports", done, total)

    await asyncio.gather(*(scan_one(host, port) for host in live_hosts for port in ports))
    if progress_callback:
        await progress_callback("ports", total, total)

    identify_sem = asyncio.Semaphore(20)
    unique: dict[tuple[str, int], DiscoveredService] = {}

    async def identify(host: str, port: int):
        async with identify_sem:
            service = await _identify_service(host, port)
            if full_scan or _is_dashboard_worthy(service):
                service = _apply_os_hint(service)
                unique[(host, port)] = service
                if service_callback:
                    await service_callback(service)

    if progress_callback:
        await progress_callback("identify", 0, len(open_ports))
    await asyncio.gather(*(identify(host, port) for host, port in open_ports))
    if progress_callback:
        await progress_callback("identify", len(open_ports), len(open_ports))

    if host_only_entries:
        local_ip = get_local_ip()
        hosts_with_services = {host for host, _ in unique}
        for host in live_hosts:
            if host == "127.0.0.1" and local_ip != "127.0.0.1":
                continue
            if host in hosts_with_services and host != local_ip:
                continue
            service = (
                build_local_host_service()
                if host == local_ip
                else _create_host_only_service(host)
            )
            unique[(host, HOST_ONLY_PORT)] = service
            if service_callback:
                await service_callback(service)

    return list(unique.values())


async def scan_networks(
    cidrs: list[str],
    *,
    full_scan: bool = False,
    host_scan_ports: list[int] | None = None,
    host_only_entries: bool = True,
    progress_callback: ProgressCallback | None = None,
    service_callback: ServiceCallback | None = None,
) -> list[DiscoveredService]:
    unique: dict[tuple[str, int], DiscoveredService] = {}
    for cidr in cidrs:
        discovered = await scan_network(
            cidr,
            full_scan=full_scan,
            host_scan_ports=host_scan_ports,
            host_only_entries=host_only_entries,
            progress_callback=progress_callback,
            service_callback=service_callback,
        )
        for service in discovered:
            unique[(service.host, service.port)] = service
    return list(unique.values())
