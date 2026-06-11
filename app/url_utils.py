"""Normalize URLs and strip Python bytes repr artifacts from stored values."""

import re
from urllib.parse import unquote

_BYTES_REPR_RE = re.compile(r"b'([^']*)'|b\"([^\"]*)\"")


def ensure_str(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


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
