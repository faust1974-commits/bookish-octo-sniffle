"""Runtime configuration: cache location, rate limits, league selection."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _default_cache_dir() -> Path:
    env = os.environ.get("HOOPSIM_CACHE")
    if env:
        return Path(env).expanduser()
    return Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "hoopsim"


@dataclass
class Config:
    """Global settings. Construct once and pass down, or use `default_config()`."""

    cache_dir: Path = field(default_factory=_default_cache_dir)

    # stats.nba.com is an undocumented endpoint that rate-limits aggressively
    # and will silently start returning empty payloads if hammered.
    request_delay_seconds: float = 0.62
    request_timeout_seconds: float = 30.0
    max_retries: int = 4
    retry_backoff_seconds: float = 2.0

    # Cache entries older than this are refetched. Completed seasons never
    # change, so the loader overrides this to "forever" for historical data.
    cache_ttl_seconds: float = 6 * 60 * 60

    league: str = "nba"
    random_seed: int = 20251001

    def ensure_cache(self) -> Path:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        return self.cache_dir


_DEFAULT: Config | None = None


def default_config() -> Config:
    global _DEFAULT
    if _DEFAULT is None:
        _DEFAULT = Config()
    return _DEFAULT


def set_default_config(cfg: Config) -> None:
    global _DEFAULT
    _DEFAULT = cfg
