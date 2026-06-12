"""ARP-based device discovery (GPTWOL-inspired, scapy-free)."""

from __future__ import annotations

import asyncio
import ipaddress
import os
import platform
import re
import socket
import subprocess
from dataclasses import dataclass

from app.scanner import get_local_ip, get_local_network, parse_cidr

MAC_RE = re.compile(r"([0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}")
WINDOWS_ARP_RE = re.compile(
    r"^\s*(\d+\.\d+\.\d+\.\d+)\s+([0-9a-fA-F-]{2}(?:-[0-9a-fA-F-]{2}){5})\s+",
    re.MULTILINE,
)
UNIX_ARP_RE = re.compile(
    r"^\s*(\d+\.\d+\.\d+\.\d+)\s+0x[0-9a-f]+\s+([0-9a-f:]{17})\s+",
    re.MULTILINE,
)
IP_NEIGH_RE = re.compile(
    r"^(\d+\.\d+\.\d+\.\d+)\s+dev\s+\S+\s+(?:lladdr\s+)?([0-9a-f:]{17})(?:\s|$)",
    re.MULTILINE,
)
IPCONFIG_MAC_RE = re.compile(
    r"(?:Physical Address|Adres fizyczny).*?:\s*([0-9A-Fa-f\-]{17})",
    re.IGNORECASE,
)
IPCONFIG_IPV4_RE = re.compile(
    r"(?:IPv4 Address|Adres IPv4).*?:\s*(\d+\.\d+\.\d+\.\d+)",
    re.IGNORECASE,
)

PING_ATTEMPTS = 3


@dataclass
class ArpDevice:
    ip: str
    mac: str
    hostname: str | None = None


def _normalize_mac(mac: str) -> str:
    return mac.replace("-", ":").upper()


def _is_valid_mac(mac: str) -> bool:
    parts = mac.split(":")
    if len(parts) != 6:
        return False
    return all(len(p) == 2 and int(p, 16) >= 0 for p in parts)


def _parse_arp_table(output: str) -> dict[str, str]:
    entries: dict[str, str] = {}
    for pattern in (WINDOWS_ARP_RE, UNIX_ARP_RE, IP_NEIGH_RE):
        for match in pattern.finditer(output):
            ip, mac = match.group(1), _normalize_mac(match.group(2))
            if ip.startswith("224.") or ip.startswith("239.") or ip.endswith(".255"):
                continue
            if not _is_valid_mac(mac) or mac == "FF:FF:FF:FF:FF:FF":
                continue
            entries[ip] = mac
    if entries:
        return entries

    for line in output.splitlines():
        mac_match = MAC_RE.search(line)
        if not mac_match:
            continue
        ip_match = re.search(r"\b(\d{1,3}(?:\.\d{1,3}){3})\b", line)
        if not ip_match:
            continue
        ip = ip_match.group(1)
        mac = _normalize_mac(mac_match.group(0))
        if _is_valid_mac(mac) and mac != "FF:FF:FF:FF:FF:FF":
            entries[ip] = mac
    return entries


def _read_arp_table() -> dict[str, str]:
    system = platform.system().lower()
    entries: dict[str, str] = {}
    try:
        if system == "windows":
            result = subprocess.run(
                ["arp", "-a"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            if result.returncode == 0 and result.stdout:
                entries.update(_parse_arp_table(result.stdout))
        else:
            for cmd in (["ip", "neigh", "show"], ["arp", "-an"]):
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=10,
                    check=False,
                )
                if result.returncode == 0 and result.stdout:
                    entries.update(_parse_arp_table(result.stdout))
    except (OSError, subprocess.TimeoutExpired):
        pass
    return entries


def _parse_ipconfig_mac(text: str, ip: str) -> str | None:
    current_mac: str | None = None
    for line in text.splitlines():
        mac_match = IPCONFIG_MAC_RE.search(line)
        if mac_match:
            current_mac = _normalize_mac(mac_match.group(1))
            continue
        ipv4_match = IPCONFIG_IPV4_RE.search(line)
        if ipv4_match and ipv4_match.group(1) == ip and current_mac:
            if _is_valid_mac(current_mac) and current_mac != "00:00:00:00:00:00":
                return current_mac
    return None


def _windows_interface_mac(ip: str) -> str | None:
    try:
        result = subprocess.run(
            ["ipconfig", "/all"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
            encoding="cp852",
            errors="replace",
        )
        if result.returncode == 0 and result.stdout:
            return _parse_ipconfig_mac(result.stdout, ip)
    except (OSError, subprocess.TimeoutExpired):
        pass
    return None


def _linux_interface_mac(ip: str) -> str | None:
    try:
        result = subprocess.run(
            ["ip", "-4", "addr", "show"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if result.returncode == 0 and result.stdout:
            current_mac: str | None = None
            for line in result.stdout.splitlines():
                link_match = re.search(r"link/ether\s+([0-9a-f:]+)", line, re.IGNORECASE)
                if link_match:
                    current_mac = _normalize_mac(link_match.group(1))
                    continue
                inet_match = re.search(rf"\binet\s+{re.escape(ip)}/", line)
                if inet_match and current_mac and _is_valid_mac(current_mac):
                    if current_mac != "00:00:00:00:00:00":
                        return current_mac
    except (OSError, subprocess.TimeoutExpired):
        pass

    try:
        for iface in os.listdir("/sys/class/net"):
            if iface == "lo":
                continue
            addr_path = f"/sys/class/net/{iface}/address"
            try:
                with open(addr_path, encoding="utf-8") as fh:
                    mac = _normalize_mac(fh.read().strip())
                if not _is_valid_mac(mac) or mac == "00:00:00:00:00:00":
                    continue
                result = subprocess.run(
                    ["ip", "-4", "addr", "show", "dev", iface],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    check=False,
                )
                if result.returncode == 0 and f"inet {ip}/" in result.stdout:
                    return mac
            except OSError:
                continue
    except OSError:
        pass
    return None


def _get_local_mac_for_ip(ip: str) -> str | None:
    """MAC from local network interface — ARP table never lists the host's own IP."""
    local_ip = get_local_ip()
    if ip not in (local_ip, "127.0.0.1"):
        return None
    target = local_ip if ip == "127.0.0.1" else ip
    system = platform.system().lower()
    if system == "windows":
        return _windows_interface_mac(target)
    return _linux_interface_mac(target)


async def _ping_host(host: str) -> None:
    system = platform.system().lower()
    try:
        if system == "windows":
            proc = await asyncio.create_subprocess_exec(
                "ping", "-n", "1", "-w", "300", host,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
        else:
            proc = await asyncio.create_subprocess_exec(
                "ping", "-c", "1", "-W", "1", host,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
        await asyncio.wait_for(proc.wait(), timeout=2.0)
    except (OSError, asyncio.TimeoutError):
        pass


async def _ping_sweep(hosts: list[str], *, concurrency: int = 64) -> None:
    sem = asyncio.Semaphore(concurrency)

    async def _one(host: str) -> None:
        async with sem:
            await _ping_host(host)

    await asyncio.gather(*(_one(h) for h in hosts))


def _resolve_hostname(ip: str) -> str | None:
    try:
        name, _, _ = socket.gethostbyaddr(ip)
        return name if name and name != ip else None
    except (socket.herror, socket.gaierror, OSError):
        return None


async def batch_lookup_macs(ips: list[str]) -> dict[str, str]:
    """Ping hosts in batch, then read ARP table once for all requested IPs."""
    unique: list[str] = []
    seen: set[str] = set()
    for ip in ips:
        try:
            ipaddress.ip_address(ip)
        except ValueError:
            continue
        if ip not in seen:
            seen.add(ip)
            unique.append(ip)

    results: dict[str, str] = {}
    entries = await asyncio.to_thread(_read_arp_table)

    for ip in unique:
        local_mac = await asyncio.to_thread(_get_local_mac_for_ip, ip)
        if local_mac:
            results[ip] = local_mac
        elif ip in entries:
            results[ip] = entries[ip]

    missing = [ip for ip in unique if ip not in results]
    if not missing:
        return results

    await _ping_sweep(missing)
    await asyncio.sleep(0.5)
    entries = await asyncio.to_thread(_read_arp_table)
    for ip in missing:
        if ip in entries:
            results[ip] = entries[ip]

    still_missing = [ip for ip in missing if ip not in results]
    for ip in still_missing:
        for _ in range(PING_ATTEMPTS):
            await _ping_host(ip)
            await asyncio.sleep(0.25)
        entries = await asyncio.to_thread(_read_arp_table)
        if ip in entries:
            results[ip] = entries[ip]

    return results


async def lookup_mac_for_ip(ip: str, *, ping_first: bool = True) -> str | None:
    """Read local ARP table for one IP; ping first to populate cache when missing."""
    try:
        ipaddress.ip_address(ip)
    except ValueError:
        return None

    local_mac = await asyncio.to_thread(_get_local_mac_for_ip, ip)
    if local_mac:
        return local_mac

    entries = await asyncio.to_thread(_read_arp_table)
    if ip in entries:
        return entries[ip]

    if not ping_first:
        return None

    for _ in range(PING_ATTEMPTS):
        await _ping_host(ip)
        await asyncio.sleep(0.25)

    entries = await asyncio.to_thread(_read_arp_table)
    return entries.get(ip)


def read_arp_hosts_in_cidr(cidr: str) -> list[str]:
    """IPs from system ARP/neighbor table that fall inside the given CIDR."""
    try:
        network = ipaddress.ip_network(cidr.strip(), strict=False)
    except ValueError:
        return []
    hosts: list[str] = []
    for ip in _read_arp_table():
        try:
            if ipaddress.ip_address(ip) in network:
                hosts.append(ip)
        except ValueError:
            continue
    return sorted(hosts)


async def scan_arp_network(cidr: str | None = None) -> list[ArpDevice]:
    """Ping-sweep local subnet then read system ARP table."""
    network = cidr or get_local_network()
    try:
        ipaddress.ip_network(network, strict=False)
    except ValueError as exc:
        raise ValueError(f"Nieprawidłowy CIDR: {network}") from exc

    hosts = parse_cidr(network)
    await _ping_sweep(hosts)
    await asyncio.sleep(0.5)
    entries = await asyncio.to_thread(_read_arp_table)

    local_ip = get_local_ip()
    local_mac = _get_local_mac_for_ip(local_ip)
    if local_mac:
        entries.setdefault(local_ip, local_mac)

    network_obj = ipaddress.ip_network(network, strict=False)
    devices: list[ArpDevice] = []
    for ip, mac in sorted(entries.items()):
        try:
            if ipaddress.ip_address(ip) not in network_obj:
                continue
        except ValueError:
            continue
        devices.append(ArpDevice(ip=ip, mac=mac, hostname=_resolve_hostname(ip)))
    return devices
