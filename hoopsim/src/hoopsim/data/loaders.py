"""High-level loading: the `League` object everything else consumes."""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import cached_property

import numpy as np
import pandas as pd

from .. import constants as K
from .source import DataSource

_SUM_COLS = [
    "fgm", "fga", "fg3m", "fg3a", "ftm", "fta", "orb", "drb",
    "ast", "stl", "blk", "tov", "pf", "pts",
]


def aggregate_team_box(box: pd.DataFrame) -> pd.DataFrame:
    """Sum a player box score up to team-game rows."""
    keys = ["game_id", "team_id", "opponent_team_id", "season", "is_home"]
    keys = [k for k in keys if k in box.columns]
    agg = {c: "sum" for c in _SUM_COLS if c in box.columns}
    agg["min"] = "sum"
    out = box.groupby(keys, as_index=False).agg(agg)
    # Team minutes should total 240 per regulation game; report them in the
    # familiar per-team form rather than the player sum.
    return out


def add_rest(games: pd.DataFrame) -> pd.DataFrame:
    """Add home_rest_days / away_rest_days from the schedule.

    Rest is days since that team's previous game. The first game of a season
    is given 3 days (treated as fully rested).
    """
    long = pd.concat([
        games[["game_id", "game_date", "home_team_id"]].rename(
            columns={"home_team_id": "team_id"}).assign(side="home"),
        games[["game_id", "game_date", "away_team_id"]].rename(
            columns={"away_team_id": "team_id"}).assign(side="away"),
    ], ignore_index=True)
    long = long.sort_values(["team_id", "game_date"])
    long["prev"] = long.groupby("team_id")["game_date"].shift(1)
    long["rest"] = (long["game_date"] - long["prev"]).dt.days - 1
    long["rest"] = long["rest"].fillna(3.0).clip(lower=0.0)

    home = long[long["side"] == "home"][["game_id", "rest"]].rename(
        columns={"rest": "home_rest_days"})
    away = long[long["side"] == "away"][["game_id", "rest"]].rename(
        columns={"rest": "away_rest_days"})
    return games.merge(home, on="game_id", how="left").merge(away, on="game_id", how="left")


@dataclass
class League:
    """Everything loaded for one season, with derived frames computed lazily.

    This is the object the metric, impact, projection and simulation layers
    take. Construct it with `League.from_source(...)`.
    """

    source: DataSource
    season: str
    teams: pd.DataFrame
    players: pd.DataFrame
    games: pd.DataFrame
    box: pd.DataFrame
    _pbp: pd.DataFrame | None = field(default=None, repr=False)
    _stints: pd.DataFrame | None = field(default=None, repr=False)

    @classmethod
    def from_source(cls, source: DataSource, season: str,
                    season_type: str = "Regular Season",
                    with_pbp: bool | None = None) -> "League":
        teams = source.teams(season)
        players = source.players(season)
        games = add_rest(source.games(season, season_type))
        box = source.box(season, season_type)
        pbp = None
        if with_pbp is None:
            with_pbp = source.provides_pbp
        if with_pbp:
            if not source.provides_pbp:
                raise ValueError(f"{source.name} cannot supply play-by-play data")
            pbp = source.pbp(season)
        return cls(source=source, season=season, teams=teams, players=players,
                   games=games, box=box, _pbp=pbp)

    # -- derived frames -----------------------------------------------------

    @property
    def has_pbp(self) -> bool:
        return self._pbp is not None and not self._pbp.empty

    @property
    def pbp(self) -> pd.DataFrame:
        if self._pbp is None:
            raise ValueError(
                "This League was loaded without play-by-play. Lineup-level "
                "analysis needs it: reload with with_pbp=True from a source "
                "that provides it."
            )
        return self._pbp

    @property
    def stints(self) -> pd.DataFrame:
        if self._stints is None:
            from .pbp import build_stints

            self._stints = build_stints(self.pbp, self.games)
        return self._stints

    @cached_property
    def team_box(self) -> pd.DataFrame:
        return aggregate_team_box(self.box)

    @cached_property
    def player_index(self) -> pd.DataFrame:
        """player_id -> name, team, position, age. One row per player."""
        return self.players.drop_duplicates("player_id").set_index("player_id")

    @cached_property
    def team_index(self) -> pd.DataFrame:
        return self.teams.drop_duplicates("team_id").set_index("team_id")

    def player_name(self, player_id: str) -> str:
        try:
            return str(self.player_index.loc[player_id, "player_name"])
        except KeyError:
            return str(player_id)

    def team_name(self, team_id: str) -> str:
        try:
            return str(self.team_index.loc[team_id, "team_name"])
        except KeyError:
            return str(team_id)

    def roster(self, team_id: str) -> pd.DataFrame:
        """Players on a team, ordered by minutes played."""
        mins = (self.box[self.box["team_id"] == team_id]
                .groupby("player_id", as_index=False)
                .agg(min=("min", "sum"), games=("game_id", "nunique")))
        out = mins.merge(
            self.players[["player_id", "player_name", "position", "age"]],
            on="player_id", how="left",
        )
        return out.sort_values("min", ascending=False).reset_index(drop=True)

    def standings(self) -> pd.DataFrame:
        """Wins, losses, point differential and rank per team."""
        g = self.games.dropna(subset=["home_pts", "away_pts"])
        rows = []
        for _, r in g.iterrows():
            hw = r["home_pts"] > r["away_pts"]
            rows.append({"team_id": r["home_team_id"], "w": int(hw), "l": int(not hw),
                         "pf": r["home_pts"], "pa": r["away_pts"]})
            rows.append({"team_id": r["away_team_id"], "w": int(not hw), "l": int(hw),
                         "pf": r["away_pts"], "pa": r["home_pts"]})
        out = pd.DataFrame(rows).groupby("team_id", as_index=False).sum()
        out["games"] = out["w"] + out["l"]
        out["win_pct"] = out["w"] / out["games"].replace(0, np.nan)
        out["point_diff"] = (out["pf"] - out["pa"]) / out["games"].replace(0, np.nan)
        out = out.merge(self.teams[["team_id", "team_name", "team_abbrev", "conference"]],
                        on="team_id", how="left")
        return out.sort_values("win_pct", ascending=False).reset_index(drop=True)

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return (f"<League season={self.season!r} source={self.source.name!r} "
                f"teams={len(self.teams)} players={len(self.players)} "
                f"games={len(self.games)} pbp={'yes' if self.has_pbp else 'no'}>")
