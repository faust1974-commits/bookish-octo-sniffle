"""Load canonical frames from a directory of CSV files.

Expects files named after the canonical tables: `teams.csv`, `players.csv`,
`games.csv`, `box.csv`, and optionally `pbp.csv`. Column names must match
`schema.py`; anything missing and optional is filled with nulls.

This is the escape hatch for Kaggle dumps, paid-feed exports, or your own
scrapes -- write a small conversion script once, then everything downstream
works unchanged.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from . import schema
from .source import DataSource


class CSVSource(DataSource):
    name = "csv"

    def __init__(self, directory: str | Path) -> None:
        self.dir = Path(directory)
        if not self.dir.is_dir():
            raise FileNotFoundError(f"{self.dir} is not a directory")
        self.provides_pbp = (self.dir / "pbp.csv").exists()
        self.provides_shot_locations = False
        if self.provides_pbp:
            head = pd.read_csv(self.dir / "pbp.csv", nrows=1)
            self.provides_shot_locations = "shot_x" in head.columns

    def _read(self, stem: str, table: dict) -> pd.DataFrame:
        path = self.dir / f"{stem}.csv"
        if not path.exists():
            raise FileNotFoundError(
                f"{path} not found. CSVSource expects teams.csv, players.csv, "
                "games.csv and box.csv (pbp.csv optional)."
            )
        return schema.conform(pd.read_csv(path), table, name=stem)

    @staticmethod
    def _filter_season(frame: pd.DataFrame, season: str) -> pd.DataFrame:
        if "season" in frame.columns and frame["season"].notna().any():
            match = frame[frame["season"].astype(str) == str(season)]
            if not match.empty:
                return match
        return frame

    def teams(self, season: str) -> pd.DataFrame:
        return self._filter_season(self._read("teams", schema.TEAMS), season)

    def players(self, season: str) -> pd.DataFrame:
        return self._filter_season(self._read("players", schema.PLAYERS), season)

    def games(self, season: str, season_type: str = "Regular Season") -> pd.DataFrame:
        out = self._filter_season(self._read("games", schema.GAMES), season)
        if "season_type" in out.columns and out["season_type"].notna().any():
            sel = out[out["season_type"] == season_type]
            if not sel.empty:
                return sel
        return out

    def box(self, season: str, season_type: str = "Regular Season") -> pd.DataFrame:
        return self._filter_season(self._read("box", schema.BOX), season)

    def pbp(self, season: str, game_ids=None) -> pd.DataFrame:
        if not self.provides_pbp:
            return super().pbp(season, game_ids)
        out = self._read("pbp", schema.PBP)
        if game_ids is not None:
            out = out[out["game_id"].isin(set(game_ids))]
        return out
