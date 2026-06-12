import re

from sqlalchemy import select

from app.arp_scan import batch_lookup_macs, lookup_mac_for_ip
from app.database import async_session
from app.icons import resolve_brand_icon
from app.models import Service
from app.scanner import LOGIN_KNOWN_SERVICES, LOGIN_TITLE_RE, _fallback_service_name, is_http_error_name
from app.url_utils import sanitize_service_url, should_strip_login_gated_icon_url

LOGIN_NAME_RE = re.compile(
    r"login|sign\s*in|authorization|authenticate|zaloguj|portal|grafana|portainer|"
    r"plex|jellyfin|nextcloud|gitlab|proxmox|unifi|code-server|admin|dashboard",
    re.IGNORECASE,
)

DEVICE_CATEGORY = "Urządzenie"
HOST_ONLY_PORT = 0


def infer_has_login(name: str, description: str | None, url: str) -> bool:
    if name in LOGIN_KNOWN_SERVICES:
        return True
    hay = f"{name} {description or ''} {url}"
    return bool(LOGIN_TITLE_RE.search(hay) or LOGIN_NAME_RE.search(hay))


def should_auto_wol(service: Service) -> bool:
    return service.category == DEVICE_CATEGORY or service.port == HOST_ONLY_PORT


def _repair_http_error_name(service: Service) -> bool:
    """Fix services whose display name was set to an HTTP error page title."""
    if not is_http_error_name(service.name):
        return False
    err = service.name[:128]
    if not service.health_detail:
        service.health_detail = err
    brand_icon = resolve_brand_icon(service.name, service.description)
    if brand_icon and service.description:
        for known in LOGIN_KNOWN_SERVICES:
            if known.lower() in (service.description or "").lower():
                service.name = known
                return True
    service.name = _fallback_service_name(service.host, service.port, "")
    return True


async def enrich_mac_addresses(*, auto_wol: bool = True) -> int:
    """Batch-ping hosts, read ARP table, assign MACs (optionally enable WoL for devices)."""
    updated = 0
    async with async_session() as db:
        result = await db.execute(select(Service))
        services = result.scalars().all()
        hosts = sorted({svc.host for svc in services if not svc.mac_address and svc.host})
        if not hosts:
            return 0

        mac_map = await batch_lookup_macs(hosts)
        for svc in services:
            if svc.mac_address or not svc.host:
                continue
            mac = mac_map.get(svc.host)
            if not mac:
                continue
            svc.mac_address = mac
            if auto_wol and should_auto_wol(svc) and not svc.wol_enabled:
                svc.wol_enabled = True
            updated += 1
        await db.commit()
    return updated


async def enrich_all_services() -> int:
    updated = 0
    mac_cache: dict[str, str | None] = {}
    async with async_session() as db:
        result = await db.execute(select(Service))
        for svc in result.scalars().all():
            changed = False
            if _repair_http_error_name(svc):
                changed = True
            safe_url = sanitize_service_url(svc.url)
            if safe_url and svc.url != safe_url:
                svc.url = safe_url
                changed = True
            icon = resolve_brand_icon(svc.name, svc.description, svc.url)
            if should_strip_login_gated_icon_url(svc.icon_url, svc.url, has_login=svc.has_login):
                replacement = icon or None
                if svc.icon_url != replacement:
                    svc.icon_url = replacement
                    changed = True
            elif icon and svc.icon_url != icon:
                svc.icon_url = icon
                changed = True
            login = infer_has_login(svc.name, svc.description, svc.url)
            if svc.has_login != login:
                svc.has_login = login
                changed = True
            if not svc.mac_address and svc.host:
                if svc.host not in mac_cache:
                    mac_cache[svc.host] = await lookup_mac_for_ip(svc.host)
                mac = mac_cache[svc.host]
                if mac:
                    svc.mac_address = mac
                    changed = True
                    if should_auto_wol(svc) and not svc.wol_enabled:
                        svc.wol_enabled = True
                        changed = True
            if changed:
                updated += 1
        await db.commit()
    return updated
