"""The data-source adapter interface.

Implement this once per feed. Everything downstream consumes the canonical
frames defined in `schema.py`, so swapping stats.nba.com for a paid feed or a
directory of CSVs is a one-class change with no effect on the models.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd


class DataSource(ABC):
    """A provider of canonical basketball frames for one or more seasons."""

    #: Human-readable name, surfaced in CLI output and provenance metadata.
    name: str = "abstract"

    #: What this source can actually supply. Downstream code checks these
    #: instead of discovering a capability gap through an exception.
    provides_pbp: bool = False
    provides_shot_locations: bool = False
    provides_tracking: bool = False

    @abstractmethod
    def teams(self, season: str) -> pd.DataFrame:
        """Canonical `teams` frame."""

    @abstractmethod
    def players(self, season: str) -> pd.DataFrame:
        """Canonical `players` frame."""

    @abstractmethod
    def games(self, season: str, season_type: str = "Regular Season") -> pd.DataFrame:
        """Canonical `games` frame."""

    @abstractmethod
    def box(self, season: str, season_type: str = "Regular Season") -> pd.DataFrame:
        """Canonical `box` frame (player-game)."""

    def team_box(self, season: str, season_type: str = "Regular Season") -> pd.DataFrame:
        """Canonical `team_box` frame.

        The default aggregates the player box scores, which is correct for
        every counting stat. Sources that expose team totals directly (and so
        capture team rebounds and team turnovers) should override this.
        """
        from .loaders import aggregate_team_box

        return aggregate_team_box(self.box(season, season_type))

    def starting_lineups(self, season: str | None = None) -> dict | None:
        """Known opening fives, keyed by (game_id, team_id).

        Return None when the feed does not record them, in which case starters
        are inferred from the event log. Supplying them is strictly better: a
        wrong opening five poisons every stint in the game that follows.
        """
        return None

    def pbp(self, season: str, game_ids=None) -> pd.DataFrame:
        """Canonical `pbp` frame. Only meaningful when provides_pbp is True."""
        raise NotImplementedError(
            f"{self.name} does not provide play-by-play data. Lineup-level "
            "analysis (on/off, RAPM, 5-man units, lineup swapping) requires it."
        )

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        caps = [n for n, v in (
            ("pbp", self.provides_pbp),
            ("shots", self.provides_shot_locations),
            ("tracking", self.provides_tracking),
        ) if v]
        return f"<{type(self).__name__} name={self.name!r} provides={caps or ['box']}>"
