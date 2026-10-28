"""Concrete game-specific Profile implementations, plus shared Octo bootstrap.

API endpoints and the original game-specific keys come from the GPL-licensed
GkmasObjectManager and IdolyPrideObjectManager source repositories.
"""

from __future__ import annotations

from hashlib import md5, sha256
from json import loads
from pathlib import Path
from urllib.parse import urljoin

import requests
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.padding import PKCS7
from google.protobuf.message import DecodeError

from ..core import Catalog
from ._octodb import pdbytes2dict


def _decrypt(data: bytes, key: bytes, iv: bytes) -> bytes:
    # Same AES-CBC + PKCS7 scheme as both original manifests/decrypt.py modules.
    dec = Cipher(algorithms.AES(key), modes.CBC(iv)).decryptor()
    unpad = PKCS7(128).unpadder()
    return unpad.update(dec.update(data) + dec.finalize()) + unpad.finalize()


class _OctoProfile:
    """Shared implementation, not a second public Profile type.

    The two games share the protobuf schema but NOT their online AES framing.
    """

    name: str
    app_id: int
    api_server: str
    api_version: int
    api_key: str
    octocache_key: bytes
    octocache_iv: bytes

    def __init__(self, *, session: requests.Session | None = None, api_version: int | None = None):
        self.session = session or requests.Session()
        if api_version is not None:
            self.api_version = api_version
        self._catalog: Catalog | None = None

    @property
    def api_url(self) -> str:
        return urljoin(self.api_server, f"v2/pub/a/{self.app_id}/v/{self.api_version}/list/")

    def _download_catalog(self, base_revision: int = 0) -> bytes:
        url = urljoin(self.api_url, str(base_revision))
        headers = {
            "Accept": f"application/x-protobuf,x-octo-app/{self.app_id}",
            "X-OCTO-KEY": self.api_key,
        }
        response = self.session.get(url, headers=headers, timeout=60)
        response.raise_for_status()
        return response.content

    def _decode_online(self, encrypted: bytes) -> bytes:
        raise NotImplementedError

    def get_catalog(self, *, refresh: bool = False) -> Catalog:
        if self._catalog is None or refresh:
            encoded = self._download_catalog()
            document = pdbytes2dict(self._decode_online(encoded))
            self._catalog = Catalog.from_octo(self, document)
        return self._catalog

    def fetch_catalog(self) -> Catalog:
        return self.get_catalog(refresh=True)

    def load_catalog(self, source: str | Path) -> Catalog:
        """Read JSON, raw Octo ProtoDB, or encrypted local octocacheevai.

        Intentionally excludes historical catalog revisions and diff patching.
        """
        raw = Path(source).read_bytes()
        try:
            document = loads(raw)
        except (ValueError, UnicodeDecodeError):
            try:
                document = pdbytes2dict(raw)
                if "urlFormat" not in document:
                    raise DecodeError("missing urlFormat")
            except (DecodeError, ValueError):
                decoded = _decrypt(raw, self.octocache_key, self.octocache_iv)
                document = pdbytes2dict(decoded[16:])  # legacy octocache MD5 prefix
        self._catalog = Catalog.from_octo(self, document)
        return self._catalog


class GkmasProfile(_OctoProfile):
    """Gakuen Idolmaster. Mobile is default; `pc=True` uses the DMM catalog."""

    name = "gakumas"
    app_id = 400
    api_server = "https://api.asset.game-gakuen-idolmaster.jp/"
    api_version = 205100
    api_key = "0jv0wsohnnsigttbfigushbtl3a8m7l5"
    octocache_key = md5(b"1nuv9td1bw1udefk").digest()
    octocache_iv = md5(b"LvAUtf+tnz").digest()

    def __init__(self, *, pc: bool = False, session=None, api_version=None):
        self.pc = pc
        super().__init__(
            session=session, api_version=api_version if api_version is not None else (705100 if pc else 205100)
        )

    def _decode_online(self, encrypted: bytes) -> bytes:
        if len(encrypted) < 32:
            raise ValueError("Gakumas catalog response too short")
        key = sha256((b"x5HFaJCJywDyuButLM0f" if self.pc else b"eSquJySjayO5OLLVgdTd")).digest()
        return _decrypt(encrypted[16:], key, encrypted[:16])


class IdolyPrideProfile(_OctoProfile):
    """IDOLY PRIDE."""

    name = "idoly_pride"
    app_id = 212
    api_server = "https://api.octo-cloud.com/"
    api_version = 205051
    api_key = "xop8c3tqrl8dcgij6mc9y4yf5o7btknt"
    octocache_key = md5(b"zkfuuwgc4eoxlaew").digest()
    octocache_iv = md5(b"LvAUtf+tnz").digest()
    online_key = bytes.fromhex("aa8a30926db9d49410360d0a99aa735d035638dfc09ef99fb575d9c91a8f6cdc")
    online_iv = bytes.fromhex("9ce1286f5481bb3d92eb8529bc35962c")

    def _decode_online(self, encrypted: bytes) -> bytes:
        decoded = _decrypt(encrypted, self.online_key, self.online_iv)
        return decoded[16:]  # IDOLY PRIDE prefix is encrypted with the payload


GakmasProfile = GkmasProfile  # Friendly spelling for public discoverability.

__all__ = ["GkmasProfile", "GakmasProfile", "IdolyPrideProfile"]
