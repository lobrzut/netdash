"""Wake-on-LAN and Sleep-on-LAN magic packet helpers (GPTWOL-inspired)."""

import re
import socket

MAC_RE = re.compile(r"^([0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}$")


def normalize_mac(mac: str) -> str:
    cleaned = mac.strip().replace("-", ":").upper()
    if not MAC_RE.match(cleaned):
        raise ValueError("Nieprawidłowy adres MAC (oczekiwany format AA:BB:CC:DD:EE:FF)")
    return cleaned


def _mac_bytes(mac: str, *, reverse: bool = False) -> bytes:
    parts = normalize_mac(mac).split(":")
    raw = bytes(int(part, 16) for part in parts)
    return raw[::-1] if reverse else raw


def build_magic_packet(mac: str, *, sleep: bool = False) -> bytes:
    """Build standard (WOL) or reversed-MAC (SOL) magic packet."""
    mac_raw = _mac_bytes(mac, reverse=sleep)
    return b"\xff" * 6 + mac_raw * 16


def send_magic_packet(
    mac: str,
    *,
    broadcast_ip: str = "255.255.255.255",
    port: int = 9,
    sleep: bool = False,
) -> None:
    packet = build_magic_packet(mac, sleep=sleep)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.sendto(packet, (broadcast_ip, port))
