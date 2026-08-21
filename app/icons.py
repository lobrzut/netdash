import re
from urllib.parse import urljoin, urlparse

FAVICON_LINK_RE = re.compile(
    r'<link[^>]*rel=["\'](?:shortcut icon|icon|apple-touch-icon)["\'][^>]*>',
    re.IGNORECASE,
)
FAVICON_LINK_RE_ALT = re.compile(
    r'<link[^>]*href=["\']([^"\']+)["\'][^>]*rel=["\'](?:shortcut icon|icon|apple-touch-icon)["\']',
    re.IGNORECASE,
)
HREF_RE = re.compile(r'href=["\']([^"\']+)["\']', re.IGNORECASE)

# pattern → simple-icons slug (https://cdn.simpleicons.org/{slug})
BRAND_SLUGS: list[tuple[str, str]] = [
    (r"jellyfin", "jellyfin"),
    (r"plex", "plex"),
    (r"emby", "emby"),
    (r"grafana", "grafana"),
    (r"prometheus", "prometheus"),
    (r"portainer", "portainer"),
    (r"home\s*assistant", "homeassistant"),
    (r"sonarr", "sonarr"),
    (r"radarr", "radarr"),
    (r"prowlarr", "prowlarr"),
    (r"lidarr", "lidarr"),
    (r"readarr", "readarr"),
    (r"bazarr", "bazarr"),
    (r"overseerr", "overseerr"),
    (r"jackett", "jackett"),
    (r"transmission", "transmission"),
    (r"qbittorrent", "qbittorrent"),
    (r"deluge", "deluge"),
    (r"nextcloud", "nextcloud"),
    (r"synology", "synology"),
    (r"truenas", "truenas"),
    (r"qnap|qts|quts|qtas|qutscloud", "qnap"),
    (r"unraid", "unraid"),
    (r"open\s*media\s*vault|\bomv\b", "openmediavault"),
    (r"unifi", "ubiquiti"),
    (r"ubiquiti", "ubiquiti"),
    # Ubiquiti by model prefix (USW-, UDM-, USG-, UAP-, UXG, UNVR, UCK, U6-, UDR, UDW)
    (r"\busw[ -]|\budm[ -]|\busg[ -]|\buap[ -]|\buxg\b|\bunvr\b|\buck[ -]|\bu6[ -]|\budr[ -]|\budw[ -]", "ubiquiti"),
    (r"mikrotik|routeros|routerboard|\bccr\d|\bcrs\d|\bhap\b", "mikrotik"),
    (r"asuswrt|asus[- ]?merlin|\brt-a[xc]", "asus"),
    (r"opnsense", "opnsense"),
    (r"pfsense", "pfsense"),
    (r"openwrt", "openwrt"),
    (r"gitlab", "gitlab"),
    (r"github", "github"),
    (r"gitea", "gitea"),
    (r"jenkins", "jenkins"),
    (r"vault", "vault"),
    (r"minio", "minio"),
    (r"phpmyadmin", "phpmyadmin"),
    (r"pgadmin", "pgadmin"),
    (r"vaultwarden", "bitwarden"),
    (r"bitwarden", "bitwarden"),
    (r"immich", "immich"),
    (r"paperless", "paperlessngx"),
    (r"homer", "homer"),
    (r"pi-?hole", "pihole"),
    (r"adguard", "adguard"),
    (r"n8n", "n8n"),
    (r"homebridge", "homebridge"),
    (r"proxmox", "proxmox"),
    (r"mesh\s*central|meshcentral", "meshcentral"),
    (r"code-server", "visualstudiocode"),
    (r"ollama", "ollama"),
    (r"openwebui", "openai"),
    (r"comfyui", "comfyui"),
    (r"stable\s*diffusion", "stablediffusion"),
    (r"nginx", "nginx"),
    (r"apache", "apache"),
    (r"traefik", "traefik"),
    (r"caddy", "caddy"),
    (r"docker", "docker"),
    (r"kubernetes", "kubernetes"),
    (r"redis", "redis"),
    (r"mongodb", "mongodb"),
    (r"mysql", "mysql"),
    (r"mariadb", "mariadb"),
    (r"postgres", "postgresql"),
    (r"rabbitmq", "rabbitmq"),
    (r"elasticsearch", "elasticsearch"),
    (r"kibana", "kibana"),
    (r"influx", "influxdb"),
    (r"gunicorn", "gunicorn"),
    (r"fastapi|uvicorn", "fastapi"),
    (r"cloudflare", "cloudflare"),
    (r"tailscale", "tailscale"),
    (r"wireguard", "wireguard"),
    (r"mqtt", "mqtt"),
    (r"homeassistant", "homeassistant"),
    (r"frigate", "frigate"),
    (r"esphome", "esphome"),
    (r"zigbee2mqtt|zigbee", "zigbee2mqtt"),
    (r"zigbee", "zigbee"),
    (r"node-red|nodered", "nodered"),
    (r"uptime\s*kuma", "uptimekuma"),
    (r"netdata", "netdata"),
    (r"watchtower", "watchtower"),
    (r"duplicati", "duplicati"),
    (r"resilio", "resilio"),
    (r"sabnzbd", "sabnzbd"),
    (r"file\s*browser", "filebrowser"),
    (r"audiobookshelf", "audiobookshelf"),
    (r"calibre", "calibreweb"),
    (r"komga", "komga"),
    (r"navidrome", "navidrome"),
    (r"airsonic", "airsonic"),
    (r"photoprism", "photoprism"),
    (r"mealie", "mealie"),
    (r"wordpress", "wordpress"),
    (r"ghost", "ghost"),
    (r"mattermost", "mattermost"),
    (r"slack", "slack"),
    (r"discord", "discord"),
    (r"teamspeak|mumble", "teamspeak"),
    (r"pterodactyl", "pterodactyl"),
    (r"amp", "amp"),
]

# First-party brands shipped under /static (not on simpleicons CDN).
LOCAL_BRAND_ICONS: list[tuple[str, str]] = [
    (r"pomnia|brain-core", "/static/pomnia-icon.png"),
]


# Common homelab ports → brand icon URL (simpleicons or local static)
PORT_BRAND_ICONS: dict[int, str] = {
    8006: "https://cdn.simpleicons.org/proxmox",
    9090: "https://cdn.simpleicons.org/prometheus",
    9000: "https://cdn.simpleicons.org/portainer",
    8080: "https://cdn.simpleicons.org/qnap",
    5000: "https://cdn.simpleicons.org/docker",
    5001: "https://cdn.simpleicons.org/qnap",
    8443: "https://cdn.simpleicons.org/nginx",
    9443: "https://cdn.simpleicons.org/nginx",
    3000: "https://cdn.simpleicons.org/nodedotjs",
    3306: "https://cdn.simpleicons.org/mysql",
    5432: "https://cdn.simpleicons.org/postgresql",
    6379: "https://cdn.simpleicons.org/redis",
    5672: "https://cdn.simpleicons.org/rabbitmq",
    9200: "https://cdn.simpleicons.org/elasticsearch",
    27017: "https://cdn.simpleicons.org/mongodb",
    18787: "https://cdn.simpleicons.org/docker",
    7865: "/static/pomnia-icon.png",
    7860: "/static/pomnia-icon.png",
}

# Back-compat alias used by older call sites / docs.
PORT_BRAND_SLUGS: dict[int, str] = {
    8006: "proxmox",
    9090: "prometheus",
    9000: "portainer",
    8080: "qnap",
    5000: "docker",
    5001: "qnap",
    8443: "nginx",
    9443: "nginx",
    3000: "nodedotjs",
    3306: "mysql",
    5432: "postgresql",
    6379: "redis",
    5672: "rabbitmq",
    9200: "elasticsearch",
    27017: "mongodb",
    18787: "docker",
}


def resolve_port_brand_icon(port: int | None) -> str | None:
    if port is None:
        return None
    local = PORT_BRAND_ICONS.get(port)
    if local:
        return local
    slug = PORT_BRAND_SLUGS.get(port)
    if slug:
        return simple_icon_url(slug)
    return None


def simple_icon_url(slug: str) -> str:
    return f"https://cdn.simpleicons.org/{slug}"


def resolve_brand_icon(*texts: str | None) -> str | None:
    for text in texts:
        if not text:
            continue
        lowered = text.lower()
        for pattern, path in LOCAL_BRAND_ICONS:
            if re.search(pattern, lowered):
                return path
        for pattern, slug in BRAND_SLUGS:
            if re.search(pattern, lowered):
                return simple_icon_url(slug)
    return None


def extract_favicon_url(page_url: str, body: str) -> str | None:
    for pattern in (FAVICON_LINK_RE,):
        for match in pattern.finditer(body):
            href_match = HREF_RE.search(match.group(0))
            if href_match:
                return urljoin(page_url, href_match.group(1))

    for match in FAVICON_LINK_RE_ALT.finditer(body):
        return urljoin(page_url, match.group(1))

    base = f"{urlparse(page_url).scheme}://{urlparse(page_url).netloc}"
    return urljoin(base + "/", "favicon.ico")


def effective_browser_icon_url(
    icon_url: str | None,
    service_url: str | None,
    *,
    has_login: bool = False,
    name: str | None = None,
    description: str | None = None,
    port: int | None = None,
) -> str | None:
    """Icon URL safe for browser <img> — never homelab auth-gated favicons."""
    from app.url_utils import is_safe_browser_icon_url, should_strip_login_gated_icon_url

    if should_strip_login_gated_icon_url(icon_url, service_url, has_login=has_login):
        brand = resolve_brand_icon(name, description, service_url) or resolve_port_brand_icon(port)
        return brand
    if icon_url and is_safe_browser_icon_url(icon_url):
        return icon_url
    return (
        resolve_brand_icon(name, description, service_url)
        or resolve_port_brand_icon(port)
    )


def resolve_icon_url(
    name: str,
    title: str | None,
    page_url: str,
    body: str,
    *,
    has_login: bool = False,
    port: int | None = None,
) -> str | None:
    brand = resolve_brand_icon(name, title, page_url)
    if brand:
        return brand
    port_brand = resolve_port_brand_icon(port)
    if port_brand:
        return port_brand
    if has_login:
        return None
    if port in (5000, 5001, 8443, 9443):
        brand = resolve_brand_icon("qnap")
        if brand:
            return brand
    return extract_favicon_url(page_url, body)
