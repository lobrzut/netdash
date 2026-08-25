"""i18n guards.

Two regressions this catches:

1. Copy that names QNAP. QNAP is deprecated (see DEPRECATION-QNAP.md) and the
   recommended deploy is a Proxmox VM with Dockge, so a user on the recommended
   path was being told to go fix things on a NAS they do not own. Until 1.3.165
   the update dialog was literally titled "Manual update (QNAP)".
2. A key referenced from the UI that no longer exists in the base catalogue —
   which renders as a raw key, or as nothing at all, in the user's face.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
I18N = ROOT / "app" / "static" / "i18n"
LANGS = ("en", "pl", "de", "uk")

KEY_IN_JS = re.compile(r"\bt\('([A-Za-z0-9_.]+)'")
KEY_IN_HTML = re.compile(r'data-i18n(?:-placeholder|-title)?="([A-Za-z0-9_.]+)"')


def _catalogue(lang: str) -> dict[str, str]:
    return json.loads((I18N / f"{lang}.json").read_text(encoding="utf-8"))


def test_catalogues_are_valid_json() -> None:
    for lang in LANGS:
        assert _catalogue(lang), f"{lang}.json is empty or unparseable"


def test_no_copy_names_the_deprecated_nas_platform() -> None:
    offenders: list[str] = []
    for lang in LANGS:
        for key, value in _catalogue(lang).items():
            if "qnap" in str(value).lower() or "qnap" in key.lower():
                offenders.append(f"{lang}:{key}")
    assert not offenders, (
        "QNAP is deprecated and Dockge is the recommended deploy; user-facing copy "
        f"must not name it: {offenders}"
    )


def test_every_key_the_ui_asks_for_exists_in_the_base_catalogue() -> None:
    js = (ROOT / "app" / "static" / "app.js").read_text(encoding="utf-8")
    html = (ROOT / "app" / "static" / "index.html").read_text(encoding="utf-8")
    used = set(KEY_IN_JS.findall(js)) | set(KEY_IN_HTML.findall(html))
    assert len(used) > 100, "key extraction broke — it found suspiciously few keys"

    missing = sorted(used - set(_catalogue("en")))
    assert not missing, f"UI references keys absent from en.json: {missing}"


def test_scan_warning_key_is_platform_neutral() -> None:
    """Renamed from scan.qnapSafeWarning in 1.3.165.

    The banner fires on safe-mode + docker-bridge + no-full-CIDR, which is a
    low-resource condition, not a QNAP detection.
    """
    for lang in LANGS:
        catalogue = _catalogue(lang)
        assert "scan.qnapSafeWarning" not in catalogue, f"{lang}.json kept the old key"
        assert "scan.lowResourceSafeWarning" in catalogue, f"{lang}.json lost the renamed key"
