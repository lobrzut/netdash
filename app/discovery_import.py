"""Merge remote discovery agent payloads into the services database."""

from __future__ import annotations

import ipaddress
import logging
import re
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enrich import should_auto_wol
from app.models import AppSettings, Service
from app.scanner import HOST_ONLY_PORT, PORT_SIGNATURES, _create_host_only_service
from app.schemas import DiscoveryHostEntry, DiscoveryImportResult
from app.wol import normalize_mac

logger = logging.getLogger("netdash")

_IP_RE = re.compile(r"^\d{1,3}(?:\.\d{1,3}){3}$")


def _ip_in_any_cidr(ip: str, cidrs: list[str]) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
        for cidr in cidrs:
            if addr in ipaddress.ip_network(cidr.strip(), strict=False):
                return True
    except ValueError:
        pass
    return False


def _valid_ip(ip: str) -> bool:
    if not _IP_RE.match(ip):
        return False
    try:
        return all(0 <= int(p) <= 255 for p in ip.split("."))
    except ValueError:
        return False


def _host_display_name(entry: DiscoveryHostEntry) -> str:
    if entry.hostname and entry.hostname.strip():
        short = entry.hostname.strip().split(".")[0]
        return short or entry.hostname.strip()
    return entry.ip


async def _find_services_for_host(db: AsyncSession, ip: str, mac: str | None) -> list[Service]:
    result = await db.execute(select(Service).where(Service.host == ip))
    matches = list(result.scalars().all())
    if matches:
        return matches
    if mac:
        result = await db.execute(select(Service).where(Service.mac_address == mac))
        return list(result.scalars().all())
    return []


def _pick_host_only(services: list[Service]) -> Service | None:
    for svc in services:
        if svc.port == HOST_ONLY_PORT or svc.protocol == "host":
            return svc
    return services[0] if services else None


def _is_host_only_service(svc: Service) -> bool:
    """Host discovery status applies only to host-only rows, not HTTP/TCP services."""
    return svc.port == HOST_ONLY_PORT or svc.protocol == "host"


async def _upsert_host_entry(
    db: AsyncSession,
    entry: DiscoveryHostEntry,
    now: datetime,
) -> tuple[bool, bool]:
    """Returns (created, updated)."""
    ip = entry.ip.strip()
    mac = normalize_mac(entry.mac) if entry.mac else None
    online = entry.online is not False
    display = _host_display_name(entry)

    existing = await _find_services_for_host(db, ip, mac)
    host_svc = _pick_host_only(existing)
    created = False
    updated = False

    if host_svc:
        if host_svc.host != ip:
            host_svc.host = ip
            updated = True
        if mac and (not host_svc.mac_address or host_svc.mac_address != mac):
            host_svc.mac_address = mac
            updated = True
        if not host_svc.customized and display and host_svc.name != display:
            host_svc.name = display
            updated = True
        host_svc.is_online = online
        host_svc.last_seen = now
        host_svc.last_checked = now
        if mac and should_auto_wol(host_svc) and not host_svc.wol_enabled:
            host_svc.wol_enabled = True
            updated = True
    else:
        template = _create_host_only_service(ip)
        db.add(
            Service(
                name=display if display != ip else template.name,
                url=template.url,
                host=ip,
                port=HOST_ONLY_PORT,
                protocol=template.protocol,
                category=template.category,
                icon=template.icon,
                description=template.description,
                auto_discovered=True,
                has_login=False,
                is_online=online,
                last_seen=now,
                last_checked=now,
                mac_address=mac,
                wol_enabled=bool(mac),
            )
        )
        created = True

    if entry.ports:
        for port_entry in entry.ports:
            port = port_entry.port
            if port < 1 or port > 65535:
                continue
            port_matches = [s for s in existing if s.port == port]
            if port_matches:
                svc = port_matches[0]
                if svc.host != ip:
                    svc.host = ip
                    updated = True
                svc.last_seen = now
                # Port services: is_online comes from health checks only.
                continue
            base = PORT_SIGNATURES.get(port, (port_entry.service or f"Port {port}", "plug", "Inne"))
            name = port_entry.service or base[0]
            protocol = "https" if port in {443, 8443, 9443} else "http" if port in {80, 8080, 8000} else "tcp"
            url = f"{protocol}://{ip}:{port}" if protocol != "tcp" else f"tcp://{ip}:{port}"
            if protocol == "https" and port == 443:
                url = f"https://{ip}"
            elif protocol == "http" and port == 80:
                url = f"http://{ip}"
            db.add(
                Service(
                    name=name,
                    url=url,
                    host=ip,
                    port=port,
                    protocol=protocol,
                    category=base[2],
                    icon=base[1],
                    description=f"Wykryto przez agenta zdalnego (port {port})",
                    auto_discovered=True,
                    is_online=True,
                    last_seen=now,
                    mac_address=mac,
                )
            )
            created = True

    return created, updated


async def import_discovery_hosts(
    db: AsyncSession,
    hosts: list[DiscoveryHostEntry],
    *,
    source: str,
    source_hostname: str | None,
    mark_missing_offline: bool,
    offline_scope_cidrs: list[str] | None = None,
) -> DiscoveryImportResult:
    now = datetime.now(timezone.utc)
    seen_ips: set[str] = set()
    created = 0
    updated = 0
    skipped = 0

    for entry in hosts:
        ip = (entry.ip or "").strip()
        if not _valid_ip(ip):
            skipped += 1
            continue
        seen_ips.add(ip)
        was_created, was_updated = await _upsert_host_entry(db, entry, now)
        if was_created:
            created += 1
        elif was_updated:
            updated += 1

    marked_offline = 0
    if mark_missing_offline and seen_ips:
        result = await db.execute(
            select(Service).where(
                Service.auto_discovered.is_(True),
                Service.protocol == "host",
                Service.port == HOST_ONLY_PORT,
            )
        )
        for svc in result.scalars().all():
            if not _is_host_only_service(svc):
                continue
            if svc.host in seen_ips:
                continue
            if offline_scope_cidrs and not _ip_in_any_cidr(svc.host, offline_scope_cidrs):
                continue
            if svc.is_online:
                svc.is_online = False
                svc.last_checked = now
                marked_offline += 1

    app_settings = (await db.execute(select(AppSettings).limit(1))).scalar_one_or_none()
    if app_settings is None:
        app_settings = AppSettings()
        db.add(app_settings)
    label = source_hostname or source
    app_settings.discovery_last_import_at = now
    app_settings.discovery_last_import_source = label[:128]
    app_settings.discovery_last_import_hosts = len(seen_ips)

    await db.commit()

    logger.info(
        "Discovery import source=%s hostname=%s hosts=%s created=%s updated=%s offline=%s skipped=%s",
        source,
        source_hostname,
        len(seen_ips),
        created,
        updated,
        marked_offline,
        skipped,
    )

    return DiscoveryImportResult(
        ok=True,
        source=source,
        source_hostname=source_hostname,
        hosts_received=len(hosts),
        hosts_imported=len(seen_ips),
        created=created,
        updated=updated,
        marked_offline=marked_offline,
        skipped=skipped,
        imported_at=now,
    )
