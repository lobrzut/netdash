"""Normalize URLs and strip Python bytes repr artifacts from stored values."""

import ipaddress
import re
from urllib.parse import unquote, urlunparse, urlparse

_BYTES_REPR_RE = re.compile(r"b'([^']*)'|b\"([^\"]*)\"")


def ensure_str(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def brain_dashboard_url(stats_url: str | None) -> str | None:
    """Derive Brain UI base URL from the configured stats endpoint (e.g. …/stats → …/)."""
    text = ensure_str(stats_url).strip()
    if not text:
        return None
    try:
        parsed = urlparse(text)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            return None
        path = parsed.path.rstrip("/")
        if path.endswith("/stats"):
            path = path[: -len("/stats")] or "/"
        return urlunparse(parsed._replace(path=path or "/", params="", query="", fragment=""))
    except Exception:
        return None


def sanitize_service_url(url: str | bytes | None) -> str:
    """Decode bytes and remove leaked b'...' fragments from query strings."""
    if url is None:
        return ""
    text = ensure_str(url).strip()
    if not text or text == "#":
        return text
    text = unquote(text)
    text = re.sub(r"\?b'([^']*)'", r"?\1", text)
    text = re.sub(r'\?b"([^"]*)"', r"?\1", text)
    text = _BYTES_REPR_RE.sub(lambda m: m.group(1) or m.group(2) or "", text)
    return text


_SAFE_ICON_HOSTS = frozenset({"cdn.simpleicons.org"})

# Cloud-metadata endpoints — never fetch these server-side (SSRF guard).
_BLOCKED_FETCH_HOSTS = frozenset({
    "169.254.169.254",          # AWS / Azure / OpenStack IMDS
    "100.100.100.200",          # Alibaba Cloud
    "metadata.google.internal",  # GCP
    "metadata.goog",
    "fd00:ec2::254",            # AWS IMDSv6
})


def is_blocked_fetch_target(url: str | None) -> bool:
    """True for URLs the server must never fetch (cloud metadata SSRF targets)."""
    host = _hostname(ensure_str(url))
    if not host:
        return False
    if host in _BLOCKED_FETCH_HOSTS:
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return str(ip) in _BLOCKED_FETCH_HOSTS


def _hostname(url: str) -> str:
    try:
        return (urlparse(url).hostname or "").lower().rstrip(".")
    except Exception:
        return ""


def is_private_or_local_host(hostname: str) -> bool:
    """True for RFC1918, loopback, link-local, and common LAN suffixes."""
    if not hostname:
        return False
    host = hostname.lower().rstrip(".")
    if host in ("localhost", "localhost.localdomain"):
        return True
    if host.endswith(".local") or host.endswith(".lan"):
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return bool(ip.is_private or ip.is_loopback or ip.is_link_local)


def is_safe_browser_icon_url(url: str | None) -> bool:
    """URLs safe to load in <img> without triggering HTTP auth dialogs."""
    if url is None:
        return False
    text = ensure_str(url).strip()
    if not text:
        return False
    if text.startswith("/") or text.startswith("data:"):
        return True
    parsed = urlparse(text)
    if parsed.scheme not in ("http", "https"):
        return False
    host = (parsed.hostname or "").lower()
    if host in _SAFE_ICON_HOSTS:
        return True
    if is_private_or_local_host(host):
        return False
    return True


_QNAP_ADMIN_PORTS = frozenset({5000, 5001})


def is_qnap_admin_url(url: str | None) -> bool:
    if not url or not str(url).strip():
        return False
    try:
        port = urlparse(str(url).strip()).port
    except Exception:
        return False
    return port in _QNAP_ADMIN_PORTS


def should_strip_login_gated_icon_url(
    icon_url: str | None,
    service_url: str | None,
    *,
    has_login: bool = False,
) -> bool:
    """True when icon_url must not be sent to the browser (auth popup risk)."""
    if not icon_url or not str(icon_url).strip():
        return False
    if is_qnap_admin_url(icon_url) or is_qnap_admin_url(service_url):
        return True
    if not is_safe_browser_icon_url(icon_url):
        return True
    if not has_login:
        return False
    icon_host = _hostname(icon_url)
    svc_host = _hostname(service_url or "")
    if icon_host and svc_host and icon_host == svc_host:
        icon_port = urlparse(icon_url).port
        svc_port = urlparse(service_url or "").port
        if icon_port == svc_port:
            return True
    return False
