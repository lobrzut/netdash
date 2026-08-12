import asyncio
import ipaddress
import logging
import platform
import random
import re
import socket
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse
from typing import Awaitable, Callable

import httpx

from app.config import settings
from app.icons import resolve_brand_icon, resolve_icon_url, resolve_port_brand_icon

logger = logging.getLogger("netdash")
from app.url_utils import ensure_str, sanitize_service_url

WEB_PORTS = [
    80, 81, 443, 3000, 4000, 4200, 4443, 5000, 5001, 8000, 8006, 8008,
    8080, 8081, 8443, 8888, 9000, 9090, 9443, 6443, 8787, 18787,
]

# Safe mode: minimal ports — QNAP kernel can OOM/crash on TCP floods even with container mem_limit.
# Include QNAP DSM/admin (5000/5001, 8080/8081), file shares (873 rsync, 2049 NFS), and common apps (8787).
SAFE_WEB_PORTS = [80, 443, 5000, 5001, 8006, 8080, 8081, 873, 2049, 8787, 18787]

# Primary TCP discovery ports — Tier 1 adaptive discovery (any open = host live).
TCP_DISCOVERY_PRIMARY_PORTS = [22, 80, 443, 8006, 8080, 8081, 3000, 5000, 5001, 8000, 8443, 9000, 18787]

# Optional bonus probe for NETDASH_ARP_EXTRA_HOSTS (not required for discovery).
EXTRA_HOST_PROBE_PORTS = list(TCP_DISCOVERY_PRIMARY_PORTS)

# Desktop / OS-revealing ports scanned in default mode (alongside WEB_PORTS).
HOST_DISCOVERY_PORTS = [22, 445, 3389, 5900]
DEFAULT_HOST_SCAN_PORTS = "22,445,3389,5900"
# Ports probed when ICMP ping is blocked (common in Docker without usable NET_RAW).
TCP_DISCOVERY_PORTS = [80, 443, 22, 445, 8080, 5000, 8000, 8006, 8443]
SAFE_TCP_DISCOVERY_PORTS = [80, 443, 8006]
SAFE_HOST_DISCOVERY_PORTS = [22]
HOST_ONLY_PORT = 0

OS_PORT_HINTS: dict[int, str] = {
    22: "Linux/macOS (SSH)",
    445: "Windows (SMB)",
    3389: "Windows (RDP)",
    5900: "VNC (zdalny pulpit)",
}

HTTPS_PORTS = {443, 8443, 9443, 6443, 4443, 8006, 5001}
HTTP_FIRST_PORTS = {
    80, 81, 8080, 8081, 8000, 8008, 3000, 5000, 5001, 8888, 9000, 9090, 8787, 18787,
    4000, 4200, 2283, 5055, 6363, 6767, 7878, 8096, 8123, 8191, 8334, 8686, 8989,
    9117, 9696, 32400,
}

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

# Curated middle set for manual "popular ports" / NETDASH_SCAN_PORT_PROFILE=popular.
# Homelab media/*arr, NAS, DB, VPN — NOT 1-65535. Used when full_scan=true (even in safe mode)
# with IPS-friendly per-host delays. Default safe scans still use SAFE_WEB_PORTS only.
POPULAR_HOMELAB_PORTS = [
    22, 80, 443, 873, 1194, 1883, 2049, 2283, 3000, 3306, 3389, 5000, 5001, 5055,
    5432, 5672, 5900, 6363, 6379, 6767, 7878, 8000, 8006, 8080, 8081, 8096, 8123,
    8191, 8334, 8443, 8686, 8787, 8989, 9000, 9090, 9117, 9443, 9696, 15672, 18787,
    27017, 32400, 51820,
]

# NETDASH_SCAN_ALL_PORTS=true / profile=all_listed: once a host is found live, probe it on
# this comprehensive service-port list so services on non-standard ports get discovered too.
# Only live hosts are probed this deeply (a few dozen), so it stays safe under the usual
# throttling — unlike a 1-65535 sweep of the whole /24, which would flood the NAS / IPS.
SERVICE_PORTS = [
    21, 22, 23, 25, 53, 67, 69, 80, 81, 88, 110, 111, 123, 135, 139, 143, 161, 389,
    443, 445, 465, 502, 515, 548, 554, 587, 631, 636, 873, 902, 993, 995, 1080, 1194,
    1234, 1400, 1433, 1521, 1880, 1883, 2049, 2052, 2082, 2083, 2086, 2087, 2095, 2096,
    2222, 2283, 2375, 2376, 2379, 2483, 3000, 3001, 3002, 3128, 3260, 3306, 3389, 3478,
    3493, 4000, 4040, 4200, 4433, 4443, 4444, 4533, 4567, 5000, 5001, 5006, 5044, 5055,
    5060, 5076, 5173, 5201, 5222, 5280, 5299, 5353, 5432, 5601, 5672, 5683, 5800, 5900,
    5901, 5984, 6052, 6363, 6379, 6443, 6767, 6789, 6881, 7000, 7001, 7070, 7100, 7359,
    7474, 7575, 7777, 7878, 8000, 8001, 8006, 8007, 8008, 8009, 8010, 8042, 8069, 8080,
    8081, 8082, 8083, 8085, 8086, 8088, 8089, 8090, 8091, 8095, 8096, 8112, 8118, 8123,
    8125, 8181, 8191, 8200, 8222, 8266, 8333, 8334, 8384, 8443, 8500, 8501, 8554, 8581,
    8585, 8686, 8765, 8786, 8787, 8800, 8810, 8843, 8880, 8888, 8920, 8989, 9000, 9001,
    9002, 9003, 9090, 9091, 9092, 9093, 9100, 9117, 9119, 9200, 9292, 9443, 9696, 9981,
    9999, 10000, 11211, 13378, 15672, 18787, 19132, 19999, 20000, 25565, 27017, 32400,
    37777, 49152, 51820, 61208,
]

PORT_SIGNATURES: dict[int, tuple[str, str, str]] = {
    21: ("FTP", "ftp", "Pliki"),
    22: ("SSH", "terminal", "Zdalny dostęp"),
    23: ("Telnet", "terminal", "Zdalny dostęp"),
    25: ("SMTP", "mail", "Poczta"),
    53: ("DNS", "dns", "Sieć"),
    80: ("HTTP", "globe", "Web"),
    443: ("HTTPS", "lock", "Web"),
    445: ("SMB", "folder", "Pliki"),
    873: ("Rsync", "sync", "Pliki"),
    111: ("RPC / Portmapper", "network", "Sieć"),
    139: ("NetBIOS", "network", "Sieć"),
    2049: ("NFS", "folder", "Pliki"),
    49152: ("QNAP (dynamic)", "nas", "NAS"),
    515: ("Drukarka (LPD)", "printer", "Drukarki"),
    554: ("Kamera (RTSP)", "camera", "Kamery"),
    631: ("Drukarka (IPP)", "printer", "Drukarki"),
    9100: ("Drukarka (RAW)", "printer", "Drukarki"),
    3000: ("Node.js / Dev", "code", "Development"),
    3306: ("MySQL", "database", "Baza danych"),
    3389: ("RDP", "monitor", "Zdalny dostęp"),
    5900: ("VNC", "monitor", "Zdalny dostęp"),
    4200: ("Angular Dev", "code", "Development"),
    5000: ("QNAP HTTP", "nas", "NAS"),
    5001: ("QNAP HTTPS", "nas", "NAS"),
    8081: ("QNAP HTTPS Alt", "nas", "NAS"),
    5432: ("PostgreSQL", "database", "Baza danych"),
    5672: ("RabbitMQ", "queue", "Kolejka"),
    6379: ("Redis", "database", "Cache"),
    8000: ("HTTP Alt", "globe", "Web"),
    8006: ("Proxmox VE", "proxmox", "DevOps"),
    8080: ("QNAP / HTTP Alt", "nas", "NAS"),
    8443: ("HTTPS Alt", "lock", "Web"),
    9000: ("Portainer / Sonar", "docker", "DevOps"),
    9090: ("Prometheus", "chart", "Monitoring"),
    9200: ("Elasticsearch", "search", "Baza danych"),
    27017: ("MongoDB", "database", "Baza danych"),
    2283: ("Immich", "photo", "Media"),
    5055: ("Overseerr", "play", "Media"),
    6363: ("qBittorrent", "download", "Media"),
    6767: ("Bazarr", "tv", "Media"),
    7878: ("Radarr", "film", "Media"),
    8096: ("Jellyfin", "play", "Media"),
    8123: ("Home Assistant", "home", "Smart Home"),
    8191: ("FlareSolverr", "shield", "Media"),
    8334: ("HTTP Alt", "globe", "Web"),
    8686: ("Lidarr", "play", "Media"),
    8989: ("Sonarr", "tv", "Media"),
    9117: ("Jackett", "search", "Media"),
    9443: ("Portainer HTTPS", "docker", "DevOps"),
    9696: ("Prowlarr", "search", "Media"),
    15672: ("RabbitMQ Mgmt", "queue", "Kolejka"),
    32400: ("Plex", "play", "Media"),
    51820: ("WireGuard", "lock", "Sieć"),
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
    (r"mesh\s*central|meshcentral", "MeshCentral", "monitor", "Zdalny dostęp"),
    (r"guacamole", "Apache Guacamole", "monitor", "Zdalny dostęp"),
    (r"anydesk", "AnyDesk", "monitor", "Zdalny dostęp"),
    (r"teamviewer", "TeamViewer", "monitor", "Zdalny dostęp"),
    (r"rustdesk", "RustDesk", "monitor", "Zdalny dostęp"),
    (r"nomachine|no\s*machine", "NoMachine", "monitor", "Zdalny dostęp"),
    (r"kasm", "Kasm Workspaces", "monitor", "Zdalny dostęp"),
    (r"\bxrdp\b|\brdp\b", "RDP", "monitor", "Zdalny dostęp"),
    (r"drukark|\bprinter\b|laserjet|officejet|deskjet", "Drukarka", "printer", "Drukarki"),
    (r"\bkamera\b|\bcamera\b|\bcctv\b|\bnvr\b|hikvision|reolink|dahua|amcrest|foscam|ipcam", "Kamera", "camera", "Kamery"),
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


class ScanError(Exception):
    """User-facing scan failure (permission, missing CIDR, timeout)."""

    def __init__(self, message: str, *, code: str = "scan_failed"):
        super().__init__(message)
        self.code = code


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


def get_default_gateway() -> str | None:
    """Best-effort default gateway IP: parse `ip route`, else fall back to the .1 of the LAN."""
    import shutil
    import subprocess

    if shutil.which("ip"):
        try:
            proc = subprocess.run(
                ["ip", "route", "get", "1.1.1.1"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            match = re.search(r"\bvia\s+(\d{1,3}(?:\.\d{1,3}){3})", proc.stdout or "")
            if match:
                return match.group(1)
        except OSError:
            pass
    try:
        net = ipaddress.ip_network(f"{get_local_ip()}/24", strict=False)
        return str(net.network_address + 1)
    except ValueError:
        return None


def is_running_in_docker() -> bool:
    if Path("/.dockerenv").exists():
        return True
    try:
        cgroup = Path("/proc/1/cgroup").read_text(encoding="utf-8", errors="ignore")
        return "docker" in cgroup or "containerd" in cgroup or "kubepods" in cgroup
    except OSError:
        return False


DOCKER_INTERNAL_NET = ipaddress.ip_network("172.16.0.0/12")


def is_docker_bridge_ip(ip: str) -> bool:
    try:
        return ipaddress.ip_address(ip) in DOCKER_INTERNAL_NET
    except ValueError:
        return False


def is_docker_internal_cidr(cidr: str) -> bool:
    """True when CIDR is Docker bridge range (172.16–172.31), not user LAN."""
    try:
        return ipaddress.ip_network(cidr.strip(), strict=False).subnet_of(DOCKER_INTERNAL_NET)
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


def get_detected_cidrs(scan_cidr_default: str | None = None) -> list[str]:
    """CIDR options for scan UI: env/settings first, then auto /24+/28."""
    cidrs: list[str] = []
    seen: set[str] = set()
    docker_br = is_likely_docker_bridge()

    def add(text: str | None) -> None:
        if not text or not text.strip():
            return
        for cidr in parse_scan_cidrs(text):
            if cidr not in seen:
                seen.add(cidr)
                cidrs.append(cidr)

    # Prefer configured LAN CIDR (user intent) over auto-detected /28 around host IP.
    if settings.scan_cidr:
        add(settings.scan_cidr)
    if scan_cidr_default:
        add(scan_cidr_default)
    try:
        local_ip = get_local_ip()
        auto24 = str(ipaddress.ip_network(f"{local_ip}/24", strict=False))
        auto28 = str(ipaddress.ip_network(f"{local_ip}/28", strict=False))
        if not docker_br or not is_docker_internal_cidr(auto24):
            add(auto24)
            add(auto28)
    except (OSError, ValueError):
        pass
    if not cidrs:
        add("192.168.1.0/24" if settings.manual_scan_allow_full_cidr else "192.168.1.144/28")
        if settings.manual_scan_allow_full_cidr:
            add("192.168.1.144/28")
    # Legacy: when full manual CIDR is disabled, safe mode hides wide presets from the dropdown.
    if settings.scan_safe_mode and not settings.manual_scan_allow_full_cidr:
        min_pfx = settings.scan_safe_min_prefix
        narrow = [
            c for c in cidrs
            if ipaddress.ip_network(c, strict=False).prefixlen >= min_pfx
        ]
        if narrow:
            return narrow
    return cidrs


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
    env_cidrs = parse_scan_cidrs(settings.scan_cidr) if settings.scan_cidr else []
    settings_cidrs = parse_scan_cidrs(scan_cidr_default) if scan_cidr_default else []

    if cidr and cidr.strip():
        requested = parse_scan_cidrs(cidr)
        # UI often sends Docker 172.x when env LAN CIDR is configured — ignore wrong subnet.
        if (
            is_likely_docker_bridge()
            and requested
            and all(is_docker_internal_cidr(c) for c in requested)
            and (env_cidrs or settings_cidrs)
        ):
            fallback = env_cidrs or settings_cidrs
            logger.warning(
                "Ignoring Docker-internal CIDR from client (%s), using LAN CIDR %s",
                format_cidr_list(requested),
                format_cidr_list(fallback),
            )
            return fallback
        return requested
    if settings_cidrs:
        return settings_cidrs
    if env_cidrs:
        return env_cidrs
    return [get_local_network()]


def resolve_scan_cidr(
    cidr: str | None = None,
    scan_cidr_default: str | None = None,
) -> str:
    return format_cidr_list(resolve_scan_cidrs(cidr, scan_cidr_default))


def _safe_mode_anchor_ip(network: ipaddress.IPv4Network | ipaddress.IPv6Network) -> ipaddress.IPv4Address | ipaddress.IPv6Address:
    """Pick anchor inside network for safe-mode /28 chunk selection (DHCP-heavy range)."""
    if settings.scan_safe_anchor:
        try:
            ip = ipaddress.ip_address(settings.scan_safe_anchor.strip())
            if ip in network:
                return ip
        except ValueError:
            pass
    local_ip = get_local_ip()
    try:
        ip = ipaddress.ip_address(local_ip)
        if ip in network:
            return ip
    except ValueError:
        pass
    # Typical homelab DHCP block (.100–.200): bias toward .144 in a /24.
    try:
        offset = min(144, max(1, int(network.num_addresses) - 16))
        candidate = network.network_address + offset
        if candidate in network:
            return candidate
    except (ValueError, TypeError):
        pass
    return network.network_address + 1


def safe_mode_scan_cidrs(cidr: str) -> list[str]:
    """Split a wide CIDR into ≤N small subnets for safe mode (limits RAM on NAS)."""
    if not settings.scan_safe_mode:
        return [cidr]
    network = ipaddress.ip_network(cidr.strip(), strict=False)
    max_pfx = settings.scan_safe_max_prefix
    if network.prefixlen >= max_pfx:
        return [str(network)]
    chunks = list(network.subnets(new_prefix=max_pfx))
    if not chunks:
        return [str(network)]
    anchor = _safe_mode_anchor_ip(network)
    primary_idx = 0
    for i, chunk in enumerate(chunks):
        if anchor in chunk:
            primary_idx = i
            break
    max_chunks = max(1, settings.scan_safe_max_subnets)
    half = max_chunks // 2
    start = max(0, primary_idx - half)
    end = min(len(chunks), start + max_chunks)
    start = max(0, end - max_chunks)
    selected = [str(chunks[i]) for i in range(start, end)]
    if len(selected) < len(chunks):
        logger.info(
            "Safe mode: narrowed %s to %s (anchor=%s, max_subnets=%s)",
            cidr,
            format_cidr_list(selected),
            anchor,
            max_chunks,
        )
    return selected


def expand_cidrs_for_safe_mode(cidrs: list[str], *, for_manual: bool = False) -> list[str]:
    """Expand each CIDR into safe-mode chunks; dedupe preserving order.

    Manual scans with NETDASH_MANUAL_SCAN_ALLOW_FULL_CIDR keep the user-selected range.
    Background discovery still chunks to /28 when auto-shrink is enabled.
    """
    if for_manual and settings.manual_scan_allow_full_cidr:
        return cidrs
    if not settings.scan_safe_mode or settings.scan_safe_block_wide:
        return cidrs
    expanded: list[str] = []
    seen: set[str] = set()
    for cidr in cidrs:
        for sub in safe_mode_scan_cidrs(cidr):
            if sub not in seen:
                seen.add(sub)
                expanded.append(sub)
    return expanded


def chunk_cidrs_for_manual_work(cidrs: list[str], *, prefix: int | None = None) -> list[str]:
    """Split wide manual CIDRs into sequential /28 (or prefix) work units — full coverage.

    One manual job still represents the user-selected range (e.g. /24), but work is done
    chunk-by-chunk so the event loop can serve /api/health between chunks.
    """
    if not settings.manual_scan_internal_chunk:
        return list(cidrs)
    pfx = prefix if prefix is not None else settings.manual_scan_work_chunk_prefix
    pfx = max(24, min(30, int(pfx)))
    out: list[str] = []
    seen: set[str] = set()
    for cidr in cidrs:
        try:
            network = ipaddress.ip_network(cidr.strip(), strict=False)
        except ValueError:
            if cidr not in seen:
                seen.add(cidr)
                out.append(cidr)
            continue
        if network.prefixlen >= pfx:
            pieces = [str(network)]
        else:
            pieces = [str(c) for c in network.subnets(new_prefix=pfx)]
        for piece in pieces:
            if piece not in seen:
                seen.add(piece)
                out.append(piece)
    return out or list(cidrs)


def compute_manual_scan_timeout(cidrs: list[str]) -> float:
    """Scaled wall-clock timeout for a manual scan covering ``cidrs``."""
    return settings.manual_scan_timeout_for_hosts(count_hosts_in_cidrs(cidrs))


def validate_cidrs_for_safe_mode(cidrs: list[str], *, for_manual: bool = False) -> None:
    """Reject wide-CIDR scans that can crash weak NAS hosts (QNAP).

    Intentional manual scans may skip this when manual_scan_allow_full_cidr is on.
    """
    if for_manual and settings.manual_scan_allow_full_cidr:
        return
    if not settings.scan_safe_mode:
        return
    min_pfx = settings.scan_safe_min_prefix
    for cidr in cidrs:
        network = ipaddress.ip_network(cidr.strip(), strict=False)
        if network.prefixlen < min_pfx:
            raise ScanError(
                f"Tryb bezpieczny: zakres {cidr} jest zbyt szeroki (max /{min_pfx}, np. 192.168.1.144/28). "
                "Skan /24 może zawiesić cały QNAP — użyj Opcje skanu z węższym CIDR "
                "lub NETDASH_SCAN_SAFE_MODE=false / NETDASH_MANUAL_SCAN_ALLOW_FULL_CIDR=true.",
                code="cidr_too_wide",
            )


def count_hosts_in_cidrs(cidrs: list[str]) -> int:
    total = 0
    for cidr in cidrs:
        network = ipaddress.ip_network(cidr.strip(), strict=False)
        total += max(0, int(network.num_addresses) - 2)
    return total


def cidr_min_prefix(cidr: str) -> int:
    return ipaddress.ip_network(cidr.strip(), strict=False).prefixlen


def is_wide_cidr(cidr: str, *, warn_prefix: int | None = None) -> bool:
    pfx = warn_prefix if warn_prefix is not None else settings.manual_scan_warn_prefix
    return cidr_min_prefix(cidr) < pfx


def validate_manual_scan_cidrs(cidrs: list[str]) -> None:
    """Hard limits for user-triggered manual scans — always enforced."""
    if not cidrs:
        raise ScanError("Nie podano sieci do skanowania.", code="cidr_missing")
    min_pfx = settings.manual_scan_min_prefix
    for cidr in cidrs:
        network = ipaddress.ip_network(cidr.strip(), strict=False)
        if network.prefixlen < min_pfx:
            raise ScanError(
                f"Skan ręczny: zakres {cidr} jest zbyt szeroki (min /{min_pfx}). "
                f"Użyj mniejszego CIDR (np. /28).",
                code="manual_cidr_too_wide",
            )
    validate_cidrs_for_safe_mode(cidrs, for_manual=True)
    host_count = count_hosts_in_cidrs(cidrs)
    cap = settings.effective_manual_scan_max_hosts
    if host_count > cap:
        raise ScanError(
            f"Skan ręczny: {host_count} hostów przekracza limit {cap}. "
            f"Zawęź CIDR (np. /28) lub zwiększ NETDASH_MANUAL_SCAN_MAX_HOSTS.",
            code="manual_too_many_hosts",
        )


def effective_manual_scan_max_hosts() -> int:
    return settings.effective_manual_scan_max_hosts


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


def _create_host_only_service(host: str, *, display_name: str | None = None) -> DiscoveredService:
    local_ip = get_local_ip()
    if host == local_ip:
        return build_local_host_service()
    display = display_name if display_name is not None else _resolve_display_name(host)
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


async def _create_host_only_service_async(host: str) -> DiscoveredService:
    """Reverse-DNS off the event loop so long scans don't freeze /api/health."""
    local_ip = get_local_ip()
    if host == local_ip:
        return build_local_host_service()
    display = await asyncio.to_thread(_resolve_display_name, host)
    return _create_host_only_service(host, display_name=display)


def parse_cidr(cidr: str, *, max_hosts: int | None = None, manual_scan: bool = False) -> list[str]:
    network = ipaddress.ip_network(cidr.strip(), strict=False)
    hosts = [str(host) for host in network.hosts()]
    if max_hosts is not None:
        cap = max_hosts
    elif manual_scan:
        cap = settings.effective_manual_scan_max_hosts
    else:
        cap = settings.effective_scan_max_hosts
    if len(hosts) > cap:
        hosts = hosts[:cap]
    return hosts


async def _scan_batch_pause(done: int) -> None:
    # Always yield so FastAPI can serve /api/health during long manual scans.
    await asyncio.sleep(0)
    if not settings.scan_safe_mode:
        return
    batch = settings.effective_scan_batch_size
    if done > 0 and done % batch == 0:
        await asyncio.sleep(settings.scan_batch_delay)


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


async def icmp_ping_available() -> bool:
    """False when container cannot use ICMP (missing NET_RAW or ping blocked)."""
    if platform.system().lower() == "windows":
        probes = ["127.0.0.1"]
    else:
        probes = ["127.0.0.1", "8.8.8.8", "1.1.1.1"]
    for host in probes:
        if await _ping_host(host):
            return True
    return False


def _discovery_extras(cidr: str) -> set[str]:
    local_ip = get_local_ip()
    extra = {"127.0.0.1", local_ip}
    try:
        network = ipaddress.ip_network(cidr.strip(), strict=False)
        extra.add(str(network.network_address + 1))
    except ValueError:
        pass
    return extra


async def discover_live_hosts_tcp(
    cidr: str,
    ports: list[int] | None = None,
    progress_callback: ProgressCallback | None = None,
    *,
    manual_scan: bool = False,
) -> set[str]:
    """Find hosts with at least one open TCP port — fallback when ping is blocked."""
    if ports is None:
        probe_ports = SAFE_TCP_DISCOVERY_PORTS if settings.scan_safe_mode else TCP_DISCOVERY_PORTS
    else:
        probe_ports = ports
    candidates = parse_cidr(cidr, manual_scan=manual_scan)
    live = _discovery_extras(cidr)
    total = len(candidates) * len(probe_ports)
    done = 0
    sem = asyncio.Semaphore(settings.effective_scan_concurrency)

    async def probe_host(host: str) -> str | None:
        nonlocal done
        for port in probe_ports:
            if await _check_port(host, port, sem):
                done += 1
                await _scan_batch_pause(done)
                if progress_callback and done % 40 == 0:
                    await progress_callback("ping", done, total)
                return host
            done += 1
            await _scan_batch_pause(done)
            if progress_callback and done % 40 == 0:
                await progress_callback("ping", done, total)
        return None

    # Safe mode / manual: tiny batches — parallel TCP probes can saturate QNAP + starve API.
    if settings.scan_safe_mode or manual_scan:
        batch = max(1, settings.effective_scan_concurrency if not manual_scan else min(2, settings.effective_scan_concurrency))
        results: list[str | None] = []
        for i in range(0, len(candidates), batch):
            chunk = candidates[i : i + batch]
            results.extend(await asyncio.gather(*(probe_host(host) for host in chunk)))
            await asyncio.sleep(settings.scan_batch_delay if settings.scan_safe_mode else 0.05)
            await asyncio.sleep(0)
    else:
        results = await asyncio.gather(*(probe_host(host) for host in candidates))
    for host in results:
        if host:
            live.add(host)
    if progress_callback:
        await progress_callback("ping", total, total)
    return live


async def discover_live_hosts(
    cidr: str,
    progress_callback: ProgressCallback | None = None,
    *,
    tcp_fallback: bool = True,
    manual_scan: bool = False,
) -> list[str]:
    candidates = parse_cidr(cidr, manual_scan=manual_scan)
    extra = _discovery_extras(cidr)
    icmp_ok = await icmp_ping_available()

    ping_sem = settings.effective_scan_concurrency if settings.scan_safe_mode else 32
    sem = asyncio.Semaphore(ping_sem)
    live: set[str] = set(extra)
    total = len(candidates)
    done = 0

    if icmp_ok:
        async def ping_one(host: str):
            nonlocal done
            async with sem:
                if await _ping_host(host):
                    live.add(host)
            done += 1
            await _scan_batch_pause(done)
            if progress_callback and done % 20 == 0:
                await progress_callback("ping", done, total)

        if settings.scan_safe_mode or manual_scan:
            batch = max(1, min(2, settings.effective_scan_concurrency) if manual_scan else settings.effective_scan_concurrency)
            for i in range(0, len(candidates), batch):
                chunk = candidates[i : i + batch]
                await asyncio.gather(*(ping_one(host) for host in chunk))
                await asyncio.sleep(settings.scan_batch_delay if settings.scan_safe_mode else 0.05)
                await asyncio.sleep(0)
        else:
            await asyncio.gather(*(ping_one(host) for host in candidates))
        if progress_callback:
            await progress_callback("ping", total, total)
    elif progress_callback:
        await progress_callback("ping", 0, total)

    # Docker: ping often fails even with correct CIDR — TCP sweep entire subnet.
    ping_only_hosts = len(live - extra)
    # Normal mode / intentional manual scan: TCP-sweep so hosts that block ICMP are found.
    # Background safe mode keeps conservative ping-first behaviour.
    use_tcp = tcp_fallback and (
        manual_scan
        or not settings.scan_safe_mode
        or not icmp_ok
        or ping_only_hosts <= 1
    )
    if use_tcp:
        tcp_live = await discover_live_hosts_tcp(
            cidr, progress_callback=progress_callback, manual_scan=manual_scan
        )
        live.update(tcp_live)

    return sorted(live)


async def discover_live_hosts_quick(
    cidr: str,
    *,
    extra_hosts: list[str] | None = None,
    progress_callback: ProgressCallback | None = None,
) -> list[str]:
    """Lightweight discovery: gateway, ARP table, known hosts, first /28 — for NAS/Docker bridge."""
    network = ipaddress.ip_network(cidr.strip(), strict=False)
    seeds: set[str] = set(_discovery_extras(cidr))
    seeds.add(str(network.network_address + 1))
    if network.num_addresses > 2:
        seeds.add(str(network.broadcast_address - 1))

    seed_cap = settings.effective_scan_max_hosts
    for host in parse_cidr(cidr, max_hosts=seed_cap):
        seeds.add(host)

    if extra_hosts:
        for host in extra_hosts:
            try:
                if ipaddress.ip_address(host) in network:
                    seeds.add(host)
            except ValueError:
                continue

    if not settings.scan_safe_mode:
        try:
            from app.arp_scan import read_arp_hosts_in_cidr

            for host in await asyncio.to_thread(read_arp_hosts_in_cidr, cidr):
                seeds.add(host)
        except Exception:
            pass

    seed_list = sorted(seeds)
    total = len(seed_list)
    if progress_callback:
        await progress_callback("ping", 0, total)

    icmp_ok = await icmp_ping_available()
    live: set[str] = set(seeds)
    done = 0
    sem = asyncio.Semaphore(max(4, settings.effective_scan_concurrency))

    if extra_hosts:
        for host in extra_hosts:
            for port in EXTRA_HOST_PROBE_PORTS:
                if await _check_port_raw(host, port):
                    live.add(host)
                    break
            await asyncio.sleep(0)

    if icmp_ok:
        async def ping_one(host: str) -> None:
            nonlocal done
            async with sem:
                if await _ping_host(host):
                    live.add(host)
            done += 1
            if progress_callback:
                await progress_callback("ping", done, total)

        batch = max(4, settings.effective_scan_concurrency)
        for i in range(0, len(seed_list), batch):
            await asyncio.gather(*(ping_one(host) for host in seed_list[i : i + batch]))
            await asyncio.sleep(settings.scan_batch_delay)
    elif progress_callback:
        await progress_callback("ping", 0, total)

    ping_found = sum(1 for h in seed_list if h in live and h not in _discovery_extras(cidr))
    if not icmp_ok or ping_found <= 1:
        probe_ports = SAFE_TCP_DISCOVERY_PORTS if settings.scan_safe_mode else TCP_DISCOVERY_PORTS
        tcp_sem = asyncio.Semaphore(settings.effective_scan_concurrency)
        done = 0
        for host in seed_list:
            for port in probe_ports:
                if await _check_port(host, port, tcp_sem):
                    live.add(host)
                    break
                done += 1
                await _scan_batch_pause(done)
            done += 1
            if progress_callback:
                await progress_callback("ping", min(done, total), total)
            if settings.scan_safe_mode:
                await asyncio.sleep(settings.scan_batch_delay)

    if progress_callback:
        await progress_callback("ping", total, total)
    logger.info("Quick scan discovery: %s live host(s) in %s (seeds=%s)", len(live), cidr, len(seed_list))
    return sorted(live)


async def _check_port_raw(host: str, port: int) -> bool:
    """Single TCP-connect probe with no concurrency gate (caller controls pacing)."""
    try:
        conn = asyncio.open_connection(host, port)
        _, writer = await asyncio.wait_for(conn, timeout=settings.scan_timeout)
        writer.close()
        await writer.wait_closed()
        return True
    except (asyncio.TimeoutError, OSError, ConnectionRefusedError):
        return False


async def _check_port(host: str, port: int, sem: asyncio.Semaphore) -> bool:
    async with sem:
        return await _check_port_raw(host, port)


async def _probe_host_ports(
    host: str,
    ports: list[int],
    *,
    global_sem: asyncio.Semaphore | None = None,
    stop_on_first: bool = False,
) -> list[int]:
    """Probe `ports` on ONE host without tripping endpoint IPS (Symantec SEP etc.).

    In IPS-friendly mode (default) a host's ports are checked with limited per-host
    parallelism (NETDASH_PORT_PARALLEL_PER_HOST, default 1), in randomized order
    (NETDASH_SCAN_RANDOMIZE_PORTS), with a jittered delay between probes
    (NETDASH_PORTS_PER_HOST_DELAY + NETDASH_PORTS_PER_HOST_JITTER). This spreads a
    host's port probes over time so an IPS never sees a burst of many DISTINCT ports
    from us and blocks NetDash's source IP as a "port scan".

    Cross-host parallelism is controlled by the caller — many hosts can still be
    probed at once, each one gently. `global_sem`, when given, caps total in-flight
    connections. `stop_on_first` returns as soon as one open port is found (host
    liveness checks) and always probes serially.
    """
    if not ports:
        return []
    order = list(dict.fromkeys(ports))
    if settings.ips_friendly and settings.scan_randomize_ports:
        random.shuffle(order)

    per_host = max(1, settings.effective_port_parallel_per_host)
    delay = settings.effective_ports_per_host_delay
    jitter = settings.ports_per_host_jitter if settings.ips_friendly else 0.0
    host_sem = asyncio.Semaphore(per_host)
    found: list[int] = []
    stop = asyncio.Event()

    async def probe(port: int) -> None:
        if stop_on_first and stop.is_set():
            return
        async with host_sem:
            if stop_on_first and stop.is_set():
                return
            if delay > 0:
                await asyncio.sleep(delay + (random.random() * jitter if jitter > 0 else 0.0))
            ok = (
                await _check_port(host, port, global_sem)
                if global_sem is not None
                else await _check_port_raw(host, port)
            )
            if ok:
                found.append(port)
                if stop_on_first:
                    stop.set()

    if per_host <= 1 or stop_on_first:
        for port in order:
            if stop_on_first and stop.is_set():
                break
            await probe(port)
    else:
        await asyncio.gather(*(probe(port) for port in order))
    return found


def tcp_port_open_sync(ip: str, port: int, *, timeout: float | None = None) -> str:
    """Sync TCP probe — returns 'open', 'refused', or 'timeout'."""
    probe_timeout = timeout if timeout is not None else min(settings.scan_timeout, 1.5)
    try:
        with socket.create_connection((ip, port), timeout=probe_timeout):
            return "open"
    except ConnectionRefusedError:
        return "refused"
    except TimeoutError:
        return "timeout"
    except OSError as exc:
        if exc.errno in {111, 61}:  # ECONNREFUSED (Linux/macOS)
            return "refused"
        return "timeout"


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
    icon_url = resolve_icon_url(name, title, canonical, body, has_login=has_login, port=port)

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
    http_worthy = port in WEB_PORTS or port in HTTP_FIRST_PORTS or port in HTTPS_PORTS
    if http_worthy:
        probed = await _probe_http(host, port)
        if probed:
            return probed

    name, icon, category = _base_from_port(port)
    if port in HTTPS_PORTS:
        protocol, url = "https", _build_url(host, port, "https")
    elif http_worthy:
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
        icon_url=resolve_brand_icon(name) or resolve_port_brand_icon(port),
        description=f"Wykryto otwarty port {port}",
    )
    return _apply_os_hint(service)


def resolve_manual_scan_ports(
    *,
    full_scan: bool = False,
    host_scan_ports: list[int] | None = None,
) -> list[int]:
    """Pick TCP ports for a manual / on-demand network scan.

    Profiles (NETDASH_SCAN_PORT_PROFILE):
      - safe (default): SAFE_WEB_PORTS + host ports — IPS-friendly minimum
      - popular: POPULAR_HOMELAB_PORTS (media/*arr/homelab) — still curated, not 1-65535
      - all_listed: SERVICE_PORTS (~190 curated) — same as NETDASH_SCAN_ALL_PORTS=true

    full_scan=True (UI „Popularne porty”) selects popular unless scan_all_ports / all_listed
    already forces the full curated list. Never sweeps 1-65535.
    """
    profile = (settings.scan_port_profile or "safe").strip().lower()
    if settings.scan_safe_mode:
        default_extra = SAFE_HOST_DISCOVERY_PORTS
    else:
        default_extra = HOST_DISCOVERY_PORTS
    extra = host_scan_ports if host_scan_ports is not None else default_extra

    use_all_listed = settings.scan_all_ports or profile == "all_listed"
    use_popular = full_scan or profile == "popular"

    if use_all_listed:
        return sorted(set(SERVICE_PORTS + extra))
    if use_popular:
        return sorted(set(POPULAR_HOMELAB_PORTS + extra))
    if settings.scan_safe_mode:
        return sorted(set(SAFE_WEB_PORTS + extra))
    return sorted(set(WEB_PORTS + extra))


async def scan_network(
    cidr: str,
    *,
    full_scan: bool = False,
    quick_scan: bool = False,
    known_hosts: list[str] | None = None,
    host_scan_ports: list[int] | None = None,
    host_only_entries: bool = True,
    progress_callback: ProgressCallback | None = None,
    service_callback: ServiceCallback | None = None,
    manual_scan: bool = False,
) -> list[DiscoveredService]:
    ports = resolve_manual_scan_ports(full_scan=full_scan, host_scan_ports=host_scan_ports)
    if progress_callback:
        await progress_callback("ping", 0, 1)
    # Intentional manual scan must cover the selected CIDR — never the 16-host quick seed path.
    if quick_scan and not manual_scan:
        live_hosts = await discover_live_hosts_quick(
            cidr,
            extra_hosts=known_hosts,
            progress_callback=progress_callback,
        )
    else:
        live_hosts = await discover_live_hosts(
            cidr, progress_callback, manual_scan=manual_scan
        )

    if progress_callback:
        await progress_callback("ports", 0, len(live_hosts) * len(ports))

    sem = asyncio.Semaphore(settings.effective_scan_concurrency)
    open_ports: list[tuple[str, int]] = []
    total = len(live_hosts) * len(ports)
    done = 0

    # IPS-friendly: probe each host's ports gently (spread over time / limited per-host
    # parallelism) instead of firing every (host, port) pair at once. The old host-major
    # gather slammed the first live host with dozens of distinct ports simultaneously —
    # exactly what Symantec SEP & co. flag as a port scan.
    async def scan_host(host: str) -> None:
        nonlocal done
        found = await _probe_host_ports(host, ports, global_sem=sem)
        for port in found:
            open_ports.append((host, port))
        done += len(ports)
        await _scan_batch_pause(done)
        if progress_callback:
            await progress_callback("ports", min(done, total), total)
        await asyncio.sleep(0)

    # Manual + safe mode: always sequential hosts so API stays responsive on /24.
    if settings.scan_safe_mode or manual_scan:
        for host in live_hosts:
            await scan_host(host)
            delay = settings.scan_batch_delay if settings.scan_safe_mode else settings.manual_scan_batch_delay
            if delay:
                await asyncio.sleep(delay)
            await asyncio.sleep(0)
    else:
        host_sem = asyncio.Semaphore(max(1, settings.effective_scan_concurrency))
        inter_host_delay = settings.manual_scan_batch_delay if manual_scan else 0.0

        async def scan_host_guarded(host: str) -> None:
            async with host_sem:
                await scan_host(host)
                if inter_host_delay:
                    await asyncio.sleep(inter_host_delay)

        await asyncio.gather(*(scan_host_guarded(host) for host in live_hosts))
    if progress_callback:
        await progress_callback("ports", total, total)

    identify_sem = asyncio.Semaphore(settings.scan_identify_concurrency)
    unique: dict[tuple[str, int], DiscoveredService] = {}

    async def identify(host: str, port: int):
        async with identify_sem:
            service = await _identify_service(host, port)
            if full_scan or _is_dashboard_worthy(service):
                service = _apply_os_hint(service)
                unique[(host, port)] = service
                if service_callback:
                    await service_callback(service)
            await asyncio.sleep(0)

    if progress_callback:
        await progress_callback("identify", 0, len(open_ports))
    # Identify in small batches so HTTP probes don't starve the event loop.
    identify_batch = max(1, settings.scan_identify_concurrency)
    for i in range(0, len(open_ports), identify_batch):
        batch = open_ports[i : i + identify_batch]
        await asyncio.gather(*(identify(host, port) for host, port in batch))
        if progress_callback:
            await progress_callback("identify", min(i + len(batch), len(open_ports)), len(open_ports))
        await asyncio.sleep(0)
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
                else await _create_host_only_service_async(host)
            )
            unique[(host, HOST_ONLY_PORT)] = service
            if service_callback:
                await service_callback(service)
            await asyncio.sleep(0)

    return list(unique.values())


async def scan_networks(
    cidrs: list[str],
    *,
    full_scan: bool = False,
    quick_scan: bool = False,
    known_hosts: list[str] | None = None,
    host_scan_ports: list[int] | None = None,
    host_only_entries: bool = True,
    progress_callback: ProgressCallback | None = None,
    service_callback: ServiceCallback | None = None,
    manual_scan: bool = False,
) -> list[DiscoveredService]:
    unique: dict[tuple[str, int], DiscoveredService] = {}
    if manual_scan and settings.manual_scan_allow_full_cidr and settings.manual_scan_internal_chunk:
        # Keep full user range as one job, but work /28 chunks so API stays responsive.
        base = expand_cidrs_for_safe_mode(cidrs, for_manual=True)
        scan_cidrs = chunk_cidrs_for_manual_work(base)
        if len(scan_cidrs) > 1:
            logger.info(
                "Manual scan: splitting %s into %s work chunk(s) (/%s)",
                format_cidr_list(base),
                len(scan_cidrs),
                settings.manual_scan_work_chunk_prefix,
            )
    else:
        scan_cidrs = expand_cidrs_for_safe_mode(cidrs, for_manual=manual_scan)

    chunk_count = len(scan_cidrs)
    for idx, cidr in enumerate(scan_cidrs):
        if idx > 0:
            pause = settings.scan_inter_chunk_delay if settings.scan_safe_mode else 0.5
            await asyncio.sleep(pause)
            await asyncio.sleep(0)

        # Remap per-chunk progress onto a stable overall bar (chunk-major).
        async def chunk_progress(phase: str, current: int, total: int, _idx=idx) -> None:
            if not progress_callback:
                return
            # Encode chunk index in totals so UI % advances across the full /24.
            overall_total = max(1, chunk_count * max(1, total))
            overall_current = _idx * max(1, total) + min(current, max(1, total))
            await progress_callback(phase, overall_current, overall_total)

        discovered = await scan_network(
            cidr,
            full_scan=full_scan,
            quick_scan=quick_scan,
            known_hosts=known_hosts,
            host_scan_ports=host_scan_ports,
            host_only_entries=host_only_entries,
            progress_callback=chunk_progress if progress_callback else None,
            service_callback=service_callback,
            manual_scan=manual_scan,
        )
        for service in discovered:
            unique[(service.host, service.port)] = service
    return list(unique.values())
