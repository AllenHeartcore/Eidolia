"""Minimal P-C-A public model.

The normalization boundary intentionally keeps upstream Octo metadata intact.
There is no separate Object or Media layer.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class Profile(Protocol):
    """A game adapter. Concrete Profiles may expose further capabilities later."""

    def get_catalog(self, *, refresh: bool = False) -> "Catalog": ...


class Assets(list["Asset"]):
    """Search results with the same bulk-download convenience as legacy GOM."""

    def download(self, path: str | Path = "objects", *, overwrite: bool = False) -> list[Path]:
        return [asset.download(path, overwrite=overwrite) for asset in self]


@dataclass(slots=True)
class Catalog:
    """Normalized index of logical assets, still retaining original Octo records."""

    profile: Profile = field(repr=False)
    revision: int
    url_format: str
    entries: list["Asset"] = field(default_factory=list, repr=False)
    source: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_octo(cls, profile: Profile, document: dict[str, Any]) -> "Catalog":
        url_format = document["urlFormat"]
        cat = cls(profile, int(document["revision"]), url_format, source=document)
        for octo_kind, key in (("assetbundle", "assetBundleList"), ("resource", "resourceList")):
            for record in document.get(key, ()):
                cat.entries.append(Asset(catalog=cat, kind=octo_kind, info=dict(record)))
        return cat

    def __len__(self) -> int:
        return len(self.entries)

    def __iter__(self) -> Iterator["Asset"]:
        return iter(self.entries)

    def __getitem__(self, key: str | int) -> "Asset":
        if isinstance(key, int):
            return self.entries[key]
        matching = [item for item in self.entries if item.name == key or item.raw_name == key]
        if not matching:
            raise KeyError(key)
        if len(matching) != 1:
            raise KeyError(f"Ambiguous asset name {key!r} ({len(matching)} matches)")
        return matching[0]

    def search(self, *patterns: str, kind: str | None = None, flags: int = re.I) -> Assets:
        """Regex prefix match, preserving GOM/IPOM's `re.match` semantics."""
        regex = re.compile("|".join(f"(?:{p})" for p in patterns) if patterns else r".*", flags)
        return Assets(
            sorted(
                (a for a in self.entries if (kind is None or a.kind == kind) and regex.match(a.name)),
                key=lambda a: a.name.lower(),
            )
        )

    def export_json(self, path: str | Path) -> Path:
        """Export the *upstream* Catalog structure without information loss."""
        import json

        dst = Path(path)
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(json.dumps(self.source, indent=2, ensure_ascii=False), encoding="utf-8")
        return dst


@dataclass(slots=True)
class Asset:
    """Logical content entry. `get_raw` returns validated, deobfuscated bytes."""

    catalog: Catalog = field(repr=False)
    kind: str
    info: dict[str, Any] = field(repr=False)

    @property
    def name(self) -> str:
        name = self.raw_name
        return name if self.kind != "assetbundle" or name.endswith(".unity3d") else name + ".unity3d"

    @property
    def raw_name(self) -> str:
        return self.info["name"]

    @property
    def id(self) -> int:
        return int(self.info["id"])

    @property
    def size(self) -> int:
        return int(self.info.get("size", 0))

    @property
    def dependencies(self) -> tuple[int, ...]:
        return tuple(int(i) for i in self.info.get("dependencies", []))

    @property
    def url(self) -> str:
        """Resolve both GOM's `{o}` and IPOM's `{o},{g},{v},{type}` dialects."""
        return self.catalog.url_format.format(
            o=self.info["objectName"],
            g=self.info.get("generation", 0),
            v=self.info.get("uploadVersionId", 0),
            type="assetbundle" if self.kind == "assetbundle" else "resources",
        )

    def get_raw(self) -> bytes:
        from .acquisition import acquire

        return acquire(self)

    def download(self, path: str | Path = "objects", *, overwrite: bool = False) -> Path:
        """Download normalized bytes, optionally to a specified *file* path.

        A no-suffix path is treated as a directory for GOM-style convenience.
        """
        path = Path(path)
        dest = (path / Path(self.name).name) if not path.suffix else path
        if dest.exists() and not overwrite:
            raise FileExistsError(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(self.get_raw())
        return dest

    def export(self, format: str, path: str | Path | None = None, *, overwrite: bool = False) -> Path:
        """Small optional media conversions. No Stagecraft or CRI decoding in v0.1."""
        from .codecs import convert

        target = Path(path) if path else Path("objects") / Path(self.name).with_suffix("." + format.lstrip(".")).name
        if target.exists() and not overwrite:
            raise FileExistsError(target)
        converted = convert(self, self.get_raw(), format)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(converted)
        return target

    def __repr__(self) -> str:
        return f"<Asset {self.kind} {self.name!r} id={self.id}>"
