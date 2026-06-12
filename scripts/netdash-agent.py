#!/usr/bin/env python3
"""NetDash remote discovery agent — skanuje LAN i wysyła wyniki do POST /api/discovery/import."""

from __future__ import annotations

import argparse
import ipaddress
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass

MAC_RE = re.compile(r"([0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}")
IP_NEIGH_RE = re.compile(
    r"^(\d+\.\d+\.\d+\.\d+)\s+dev\s+\S+\s+(?:lladdr\s+)?([0-9a-f:]{17})(?:\s|$)",
    re.MULTILINE,
)


@dataclass
class HostRecord:
    ip: str
    mac: str | None = None
    hostname: str | None = None
    online: bool = True


def env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name, "").strip().lower()
    if not raw:
        return default
    return raw in ("1", "true", "yes", "on")


def log(msg: str) -> None:
    print(f"[netdash-agent] {msg}", flush=True)


def normalize_mac(mac: str) -> str:
    return mac.replace("-", ":").upper()


def parse_cidr(cidr: str) -> list[str]:
    network = ipaddress.ip_network(cidr.strip(), strict=False)
    return [str(host) for host in network.hosts()]


def resolve_hostname(ip: str) -> str | None:
    try:
        name, _, _ = socket.gethostbyaddr(ip)
        return name.split(".")[0] if name else None
    except OSError:
        return None


def scan_arp_scan(cidr: str) -> list[HostRecord]:
    if not shutil.which("arp-scan"):
        return []
    cmd = [
        "arp-scan",
        cidr,
        "--interval=100",
        "--retry=1",
        "--ignoredups",
        "--quiet",
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300, check=False)
    except (subprocess.TimeoutExpired, OSError) as exc:
        log(f"arp-scan failed: {exc}")
        return []
    hosts: dict[str, HostRecord] = {}
    for line in (proc.stdout or "").splitlines():
        parts = line.split()
        if len(parts) < 2:
            continue
        ip = parts[0]
        mac_match = MAC_RE.search(line)
        if not mac_match:
            continue
        mac = normalize_mac(mac_match.group(0))
        hostname = parts[-1] if len(parts) >= 3 and not parts[-1].startswith("(") else None
        if hostname and hostname == ip:
            hostname = None
        hosts[ip] = HostRecord(ip=ip, mac=mac, hostname=hostname, online=True)
    log(f"arp-scan: {len(hosts)} host(s) in {cidr}")
    return list(hosts.values())


def scan_ip_neigh(cidr: str) -> list[HostRecord]:
    if not shutil.which("ip"):
        return []
    try:
        network = ipaddress.ip_network(cidr.strip(), strict=False)
    except ValueError:
        return []
    try:
        proc = subprocess.run(["ip", "neigh", "show"], capture_output=True, text=True, timeout=30, check=False)
    except OSError:
        return []
    hosts: dict[str, HostRecord] = {}
    for match in IP_NEIGH_RE.finditer(proc.stdout or ""):
        ip, mac = match.group(1), normalize_mac(match.group(2))
        try:
            if ipaddress.ip_address(ip) not in network:
                continue
        except ValueError:
            continue
        hosts[ip] = HostRecord(ip=ip, mac=mac, hostname=resolve_hostname(ip), online=True)
    log(f"ip neigh: {len(hosts)} host(s) in {cidr}")
    return list(hosts.values())


def ping_host(ip: str) -> bool:
    cmd = ["ping", "-c", "1", "-W", "1", ip]
    if os.name == "nt":
        cmd = ["ping", "-n", "1", "-w", "400", ip]
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=5, check=False)
        return proc.returncode == 0
    except (subprocess.TimeoutExpired, OSError):
        return False


def scan_ping_sweep(cidr: str, *, max_hosts: int = 256) -> list[HostRecord]:
    hosts: list[HostRecord] = []
    for ip in parse_cidr(cidr)[:max_hosts]:
        if ping_host(ip):
            hosts.append(HostRecord(ip=ip, mac=None, hostname=resolve_hostname(ip), online=True))
    log(f"ping sweep: {len(hosts)} host(s) in {cidr}")
    return hosts


def discover_hosts(cidr: str) -> list[HostRecord]:
    hosts = scan_arp_scan(cidr)
    if hosts:
        return hosts
    hosts = scan_ip_neigh(cidr)
    if hosts:
        return hosts
    return scan_ping_sweep(cidr)


def login_token(base_url: str, username: str, password: str) -> str:
    url = base_url.rstrip("/") + "/api/auth/login"
    payload = json.dumps({"username": username, "password": password}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json", "User-Agent": "NetDash-Agent/1.0"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    token = data.get("access_token")
    if not token:
        raise RuntimeError("Login OK but no access_token in response")
    return token


def resolve_token(base_url: str) -> str:
    token = os.environ.get("NETDASH_TOKEN", "").strip()
    if token:
        return token
    user = os.environ.get("NETDASH_USER", os.environ.get("NETDASH_USERNAME", "admin")).strip()
    password = os.environ.get("NETDASH_PASSWORD", "").strip()
    if not password:
        raise RuntimeError("Set NETDASH_TOKEN or NETDASH_USER + NETDASH_PASSWORD")
    return login_token(base_url, user, password)


def push_import(
    base_url: str,
    token: str,
    hosts: list[HostRecord],
    *,
    source: str,
    hostname: str,
    mark_missing_offline: bool,
) -> dict:
    url = base_url.rstrip("/") + "/api/discovery/import"
    body = {
        "source": source,
        "hostname": hostname,
        "mark_missing_offline": mark_missing_offline,
        "hosts": [
            {
                "ip": h.ip,
                "mac": h.mac,
                "hostname": h.hostname,
                "online": h.online,
            }
            for h in hosts
        ],
    }
    payload = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "NetDash-Agent/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Import HTTP {exc.code}: {detail}") from exc


def run_once(args: argparse.Namespace) -> int:
    base_url = os.environ.get("NETDASH_URL", "http://127.0.0.1:18787").strip()
    cidr = os.environ.get("SCAN_CIDR", "192.168.1.0/24").strip()
    source = os.environ.get("AGENT_SOURCE", "agent").strip() or "agent"
    hostname = os.environ.get("AGENT_HOSTNAME", socket.gethostname()).strip()
    mark_offline = env_bool("MARK_MISSING_OFFLINE", True)

    log(f"scan {cidr} → {base_url}")
    hosts = discover_hosts(cidr)
    if not hosts:
        log("no hosts discovered")
    token = resolve_token(base_url)
    result = push_import(
        base_url,
        token,
        hosts,
        source=source,
        hostname=hostname,
        mark_missing_offline=mark_offline,
    )
    log(
        f"import OK: imported={result.get('hosts_imported')} "
        f"created={result.get('created')} updated={result.get('updated')} "
        f"offline={result.get('marked_offline')}"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="NetDash remote discovery agent")
    parser.add_argument("--once", action="store_true", help="Single scan then exit")
    args = parser.parse_args()

    interval = int(os.environ.get("INTERVAL", "300"))
    if args.once or interval <= 0:
        try:
            return run_once(args)
        except Exception as exc:
            log(f"error: {exc}")
            return 1

    log(f"loop every {interval}s (Ctrl+C to stop)")
    while True:
        try:
            run_once(args)
        except Exception as exc:
            log(f"error: {exc}")
        time.sleep(interval)


if __name__ == "__main__":
    sys.exit(main())
