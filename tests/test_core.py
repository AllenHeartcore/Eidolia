"""Network-free regression tests for both migrated Octo dialects."""

import hashlib
import json
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.padding import PKCS7

from eidolia import GkmasProfile, IdolyPrideProfile
from eidolia.acquisition import deobfuscate_bundle
from eidolia.codecs import convert
from eidolia.profiles._octodb import dict2pdbytes, pdbytes2dict


def encrypt(cleartext, key, iv):
    pad = PKCS7(128).padder()
    payload = pad.update(cleartext) + pad.finalize()
    enc = Cipher(algorithms.AES(key), modes.CBC(iv)).encryptor()
    return enc.update(payload) + enc.finalize()


class Response:
    def __init__(self, content, headers=None):
        self.content = content
        self.headers = headers or {}

    def raise_for_status(self):
        return None

    def iter_content(self, chunk_size):
        yield self.content[:2]
        yield self.content[2:]

    def close(self):
        pass


class Session:
    def __init__(self, manifest, asset):
        self.manifest = manifest
        self.asset = asset
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return Response(self.manifest if "/list/" in url else self.asset)


@pytest.fixture
def record():
    wire = b"UnityFS" + bytes(range(20))
    return {
        "revision": 345,
        "urlFormat": "https://cdn.example/{type}/{g}/{v}/{o}",
        "assetBundleList": [
            {
                "id": 2,
                "name": "img_saki",
                "objectName": "abc",
                "size": len(wire),
                "generation": 9999,
                "uploadVersionId": 77,
                "md5": hashlib.md5(wire).hexdigest(),
                "dependencies": [5, 7],
            }
        ],
        "resourceList": [
            {
                "id": 8,
                "name": "adv_story.txt",
                "objectName": "def",
                "size": 4,
            }
        ],
    }


def test_protobuf_roundtrip(record):
    result = pdbytes2dict(dict2pdbytes(record))
    assert result["revision"] == 345
    assert result["assetBundleList"][0]["dependencies"] == [5, 7]


@pytest.mark.parametrize("profile", ["gakumas", "gakumas_pc", "ipr"])
def test_online_profiles(record, profile, tmp_path):
    wire = b"UnityFS" + bytes(range(20))
    encoded = dict2pdbytes(record)
    if profile.startswith("gakumas"):
        pc = profile.endswith("pc")
        p = GkmasProfile(pc=pc)
        key = hashlib.sha256(b"x5HFaJCJywDyuButLM0f" if pc else b"eSquJySjayO5OLLVgdTd").digest()
        iv = bytes(range(16))
        manifest = iv + encrypt(encoded, key, iv)
    else:
        p = IdolyPrideProfile()
        manifest = encrypt(b"_" * 16 + encoded, p.online_key, p.online_iv)
    s = Session(manifest, wire)
    p.session = s
    cat = p.get_catalog()
    assert cat is p.get_catalog()
    assert len([url for url, _ in s.calls if "/list/" in url]) == 1
    assert cat.revision == 345
    asset = cat["img_saki.unity3d"]
    assert asset.kind == "assetbundle"
    assert asset.dependencies == (5, 7)
    assert asset.url == "https://cdn.example/assetbundle/9999/77/abc"
    assert cat["adv_story.txt"].url == "https://cdn.example/resources/0/0/def"
    assert len(cat.search("img_")) == 1
    assert asset.get_raw() == wire
    assert asset.download(tmp_path) == tmp_path / "img_saki.unity3d"
    assert (tmp_path / "img_saki.unity3d").read_bytes() == wire
    with pytest.raises(FileExistsError):
        asset.download(tmp_path)
    p.get_catalog(refresh=True)
    assert len([url for url, _ in s.calls if "/list/" in url]) == 2


def test_offline_load_json_and_protobuf(tmp_path, record):
    p = GkmasProfile()
    f = tmp_path / "catalog.json"
    f.write_text(json.dumps(record), encoding="utf-8")
    cat = p.load_catalog(f)
    assert cat["img_saki"].raw_name == "img_saki"
    assert cat.export_json(tmp_path / "copy.json") == tmp_path / "copy.json"
    proto = tmp_path / "db.bin"
    proto.write_bytes(dict2pdbytes(record))
    assert len(p.load_catalog(proto)) == 2


def test_encrypted_octocache(tmp_path, record):
    p = IdolyPrideProfile()
    encrypted = encrypt(b"\x00" * 16 + dict2pdbytes(record), p.octocache_key, p.octocache_iv)
    path = tmp_path / "octocacheevai"
    path.write_bytes(encrypted)
    assert p.load_catalog(path).revision == 345


def test_obfuscation_is_involution():
    plain = bytes(range(255)) + b"abcdefgh"
    obf = deobfuscate_bundle(plain, "img_actor.unity3d")
    assert obf != plain
    assert deobfuscate_bundle(obf, "img_actor") == plain


def test_cri_explicitly_unsupported(record):
    p = GkmasProfile()
    from eidolia.core import Catalog

    cat = Catalog.from_octo(p, record)
    obj = cat["adv_story.txt"]
    with pytest.raises(NotImplementedError, match="CRI"):
        convert(obj, b"AFS2" + bytes(20), "wav")
