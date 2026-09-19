"""On-disk cache for fetched data.

Parquet when pyarrow is available, otherwise gzipped CSV. Completed seasons
never change, so cached historical data is treated as permanent by default.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

import pandas as pd

from ..config import Config, default_config

try:  # pragma: no cover - depends on environment
    import pyarrow  # noqa: F401
    _PARQUET = True
except ImportError:  # pragma: no cover
    _PARQUET = False

_SUFFIX = ".parquet" if _PARQUET else ".csv.gz"


def cache_key(namespace: str, **params) -> str:
    """Stable hash of a namespace plus keyword parameters."""
    blob = json.dumps(params, sort_keys=True, default=str)
    digest = hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in namespace)
    return f"{safe}-{digest}"


def _path(key: str, cfg: Config) -> Path:
    return cfg.ensure_cache() / f"{key}{_SUFFIX}"


def read(key: str, cfg: Config | None = None, *, ttl: float | None = None) -> pd.DataFrame | None:
    """Return the cached frame for `key`, or None on miss/expiry."""
    cfg = cfg or default_config()
    path = _path(key, cfg)
    if not path.exists():
        return None
    ttl = cfg.cache_ttl_seconds if ttl is None else ttl
    if ttl is not None and ttl >= 0:
        if time.time() - path.stat().st_mtime > ttl:
            return None
    try:
        if _PARQUET:
            return pd.read_parquet(path)
        return pd.read_csv(path, compression="gzip")
    except (OSError, ValueError):  # corrupt cache entry: treat as a miss
        return None


def write(key: str, frame: pd.DataFrame, cfg: Config | None = None) -> Path:
    cfg = cfg or default_config()
    path = _path(key, cfg)
    tmp = path.with_suffix(path.suffix + ".tmp")
    if _PARQUET:
        frame.to_parquet(tmp, index=False)
    else:
        frame.to_csv(tmp, index=False, compression="gzip")
    tmp.replace(path)
    return path


def clear(namespace: str | None = None, cfg: Config | None = None) -> int:
    """Delete cache entries. With a namespace, only that namespace's entries."""
    cfg = cfg or default_config()
    root = cfg.ensure_cache()
    pattern = f"{namespace}-*" if namespace else "*"
    removed = 0
    for path in root.glob(pattern):
        if path.is_file():
            path.unlink()
            removed += 1
    return removed
