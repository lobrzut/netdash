"""URL normalization for stored service URLs (strip control bytes, fix encoding)."""

import re
from urllib.parse import quote, unquote, urlparse, urlunparse

_CONTROL_BYTES_RE = re.compile(r"[\x00-\x1f\x7f]")
_WHOLE_BYTES_LITERAL_RE = re.compile(r"""^[bB](["'])(.*)\1$""", re.DOTALL)
_QUERY_BYTES_LITERAL_RE = re.compile(r"""([?&][^=&?#]+=)[bB](["'])(.*?)\2""")


def _strip_bytes_literal(value: str) -> str:
    """Normalize Python bytes-literal strings accidentally persisted as text."""
    cleaned = value.strip()
    whole_match = _WHOLE_BYTES_LITERAL_RE.match(cleaned)
    if whole_match:
        cleaned = whole_match.group(2).strip()
    return _QUERY_BYTES_LITERAL_RE.sub(r"\1\3", cleaned)


def sanitize_service_url(url: str | None) -> str:
    """Return a safe HTTP(S) URL string for httpx probes."""
    if not url:
        return ""
    cleaned = _CONTROL_BYTES_RE.sub("", str(url).strip())
    cleaned = _strip_bytes_literal(cleaned)
    if not cleaned:
        return ""
    try:
        cleaned.encode("utf-8")
    except UnicodeEncodeError:
        cleaned = cleaned.encode("utf-8", errors="replace").decode("utf-8")
    parsed = urlparse(cleaned)
    if not parsed.scheme or not parsed.netloc:
        return cleaned
    path = quote(unquote(parsed.path or "/"), safe="/:@&=+$,;~.-")
    query = quote(unquote(parsed.query), safe="/?:@&=+$,;~.-")
    return urlunparse((parsed.scheme, parsed.netloc, path, parsed.params, query, parsed.fragment))
