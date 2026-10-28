"""Eidolia: Every Stage, Every World.

Profile -> Catalog -> Asset. No application singleton required.
"""

from .core import Asset, Assets, Catalog, Profile
from .profiles import GakmasProfile, GkmasProfile, IdolyPrideProfile

__version__ = "0.1.0a0"

PROFILES = {"gakumas": GkmasProfile, "idoly_pride": IdolyPrideProfile, "ipr": IdolyPrideProfile}


def open_profile(name: str, **kwargs) -> Profile:
    """Open a configured game adapter, without initiating network requests."""
    try:
        cls = PROFILES[name.lower().replace("-", "_")]
    except KeyError as exc:
        raise ValueError(f"Unknown Eidolia profile {name!r}; available: {', '.join(PROFILES)}") from exc
    return cls(**kwargs)


__all__ = [
    "Asset",
    "Assets",
    "Catalog",
    "Profile",
    "GkmasProfile",
    "GakmasProfile",
    "IdolyPrideProfile",
    "open_profile",
]
