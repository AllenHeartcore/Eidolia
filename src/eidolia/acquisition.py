"""Shared acquisition execution; game-specific source discovery stays in Profiles."""

from email.utils import parsedate_to_datetime
from hashlib import md5

import requests


def _mask(key: str) -> bytes:
    """Original GOM/IPOM Unity header mask (algorithm credited to MalitsPlus)."""
    key_bytes = key.removesuffix(".unity3d").encode("utf-8")
    if not key_bytes:
        raise ValueError("Empty deobfuscation key")
    mask = bytearray(len(key_bytes) * 2)
    for i, char in enumerate(key_bytes):
        mask[i * 2] = char
        mask[len(mask) - 1 - i * 2] = ~char & 0xFF
    x = 0x9B
    for b in mask:
        x = (((x & 1) << 7) | (x >> 1)) ^ b
    return bytes(b ^ x for b in mask)


def deobfuscate_bundle(data: bytes, name: str) -> bytes:
    """Deobfuscate up to 256 bytes of a Unity bundle, using the source algorithm."""
    mask = _mask(name)
    buf = bytearray(data)
    # Equivalent to GOM/IPOM's default offset=0, stream_pos=0, header_len=256.
    for i in range(min(len(buf), 256)):
        buf[i] ^= mask[i % len(mask)]
    return bytes(buf)


def acquire(asset, *, session=None) -> bytes:
    """Fetch, verify wire integrity, then normalize Unity header if necessary."""
    transport = session or getattr(asset.catalog.profile, "session", None) or requests
    response = transport.get(asset.url, stream=True, timeout=60)
    try:
        response.raise_for_status()
        parts = [chunk for chunk in response.iter_content(chunk_size=65536) if chunk]
        wire = b"".join(parts)
    finally:
        response.close()
    if len(wire) != asset.size:
        raise ValueError(f"{asset.name}: expected {asset.size} bytes, got {len(wire)}")
    expected = str(asset.info.get("md5", "")).lower()
    if expected and md5(wire).hexdigest() != expected:
        raise ValueError(f"{asset.name}: wire MD5 mismatch")
    if asset.kind == "assetbundle" and not wire.startswith((b"UnityFS", b"UnityRaw", b"UnityWeb")):
        return deobfuscate_bundle(wire, asset.raw_name)
    return wire
