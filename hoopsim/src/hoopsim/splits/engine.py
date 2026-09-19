"""The splits engine: every vertical, on one interface.

"Across every available vertical" means being able to cut any metric by any
dimension without writing new code each time. So dimensions are declared once,
as functions that tag a row with a bucket, and the engine applies any of them
to team, player or lineup data.

Dimensions come in two families. Game-level ones (home and away, days of rest,
month, opponent quality, win or loss) only need the schedule and box scores.
Possession-level ones (quarter, clutch, score state, garbage time) need
play-by-play, and the engine says so rather than failing obscurely.

Adding a vertical is one registration call, not a new module.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
import pandas as pd

from .. import constants as K


@dataclass(frozen=True)
class Dimension:
    """One way of cutting the data."""

    key: str
    label: str
    description: str
    level: str                     # "game" or "possession"
    tagger: Callable               # frame -> Series of bucket labels
    order: tuple | None = None     # preferred display order


DIMENSIONS: dict[str, Dimension] = {}


def register(dimension: Dimension) -> Dimension:
    DIMENSIONS[dimension.key] = dimension
    return dimension


def available(level: str | None = None) -> list[Dimension]:
    return [d for d in DIMENSIONS.values() if level is None or d.level == level]


# ---------------------------------------------------------------------------
# Game-level dimensions
# ---------------------------------------------------------------------------

def _tag_home_away(df: pd.DataFrame) -> pd.Series:
    return np.where(df["is_home"].astype(bool), "home", "away")


def _tag_rest(df: pd.DataFrame) -> pd.Series:
    rest = df["rest_days"].fillna(2).to_numpy(dtype=float)
    out = np.full(len(rest), "3+ days", dtype=object)
    out[rest <= 0] = "back-to-back"
    out[rest == 1] = "1 day"
    out[rest == 2] = "2 days"
    return pd.Series(out, index=df.index)


def _tag_b2b(df: pd.DataFrame) -> pd.Series:
    rest = df["rest_days"].fillna(2).to_numpy(dtype=float)
    return pd.Series(np.where(rest <= 0, "second night of a back-to-back", "rested"),
                     index=df.index)


def _tag_month(df: pd.DataFrame) -> pd.Series:
    return pd.to_datetime(df["game_date"]).dt.strftime("%Y-%m")


def _tag_opponent_tier(df: pd.DataFrame) -> pd.Series:
    rating = df["opponent_rating"].to_numpy(dtype=float)
    finite = rating[np.isfinite(rating)]
    if finite.size < 4:
        return pd.Series(["all"] * len(df), index=df.index)
    cuts = np.quantile(finite, [0.25, 0.5, 0.75])
    labels = np.array(["vs bottom quartile", "vs below average",
                       "vs above average", "vs top quartile"], dtype=object)
    idx = np.digitize(rating, cuts)
    return pd.Series(labels[np.clip(idx, 0, 3)], index=df.index)


def _tag_result(df: pd.DataFrame) -> pd.Series:
    return pd.Series(np.where(df["won"].astype(bool), "wins", "losses"), index=df.index)


def _tag_margin_bucket(df: pd.DataFrame) -> pd.Series:
    m = df["margin"].to_numpy(dtype=float)
    out = np.full(len(m), "close (within 5)", dtype=object)
    out[m > 5] = "comfortable win"
    out[m > 15] = "blowout win"
    out[m < -5] = "comfortable loss"
    out[m < -15] = "blowout loss"
    return pd.Series(out, index=df.index)


for _d in [
    Dimension("home_away", "Home / Away", "Venue.", "game", _tag_home_away,
              ("home", "away")),
    Dimension("rest", "Days of rest", "Days since the team's previous game.",
              "game", _tag_rest, ("back-to-back", "1 day", "2 days", "3+ days")),
    Dimension("back_to_back", "Back-to-back", "Second night of a back-to-back "
              "versus everything else.", "game", _tag_b2b),
    Dimension("month", "Month", "Calendar month, for in-season trend.", "game", _tag_month),
    Dimension("opponent_tier", "Opponent quality", "Quartile of opponent net "
              "rating faced.", "game", _tag_opponent_tier,
              ("vs top quartile", "vs above average", "vs below average", "vs bottom quartile")),
    Dimension("result", "Win / Loss", "Splits by outcome. Descriptive only -- "
              "these are consequences, not causes.", "game", _tag_result, ("wins", "losses")),
    Dimension("margin", "Game margin", "How the game went, in buckets.", "game",
              _tag_margin_bucket),
]:
    register(_d)


# ---------------------------------------------------------------------------
# Possession-level dimensions
# ---------------------------------------------------------------------------

def _tag_period(df: pd.DataFrame) -> pd.Series:
    period = df["period"].to_numpy(dtype=int)
    return pd.Series(np.where(period <= 4, "Q" + period.astype(str), "OT"), index=df.index)


def _tag_half(df: pd.DataFrame) -> pd.Series:
    return pd.Series(np.where(df["period"].to_numpy(dtype=int) <= 2,
                              "first half", "second half"), index=df.index)


def _tag_garbage(df: pd.DataFrame) -> pd.Series:
    return pd.Series(np.where(df["garbage_time"].astype(bool),
                              "garbage time", "competitive"), index=df.index)


def _tag_clutch(df: pd.DataFrame) -> pd.Series:
    """Last five minutes with the score within five points."""
    late = (df["period"].to_numpy(dtype=int) >= 4) & \
           (df["end_seconds"].to_numpy(dtype=float) >=
            (df["period"].to_numpy(dtype=float) * 720.0 - K.CLUTCH_SECONDS_REMAINING))
    close = np.abs(df["home_pts_running"].to_numpy(dtype=float)
                   - df["away_pts_running"].to_numpy(dtype=float)) <= K.CLUTCH_MARGIN
    return pd.Series(np.where(late & close, "clutch", "non-clutch"), index=df.index)


for _d in [
    Dimension("period", "Quarter", "Which period the possession was played in.",
              "possession", _tag_period, ("Q1", "Q2", "Q3", "Q4", "OT")),
    Dimension("half", "Half", "First or second half.", "possession", _tag_half,
              ("first half", "second half")),
    Dimension("garbage_time", "Garbage time", "Possessions played after the game "
              "was decided. Usually worth excluding, not analysing.",
              "possession", _tag_garbage, ("competitive", "garbage time")),
    Dimension("clutch", "Clutch", "Last five minutes, score within five. The "
              "samples are tiny and almost everything here regresses to the "
              "player's overall rate.", "possession", _tag_clutch,
              ("clutch", "non-clutch")),
]:
    register(_d)


# ---------------------------------------------------------------------------
# The engine
# ---------------------------------------------------------------------------

class SplitEngine:
    """Cuts a league's data by any registered dimension."""

    def __init__(self, league):
        self.league = league
        self._game_context: pd.DataFrame | None = None

    # -- context ------------------------------------------------------------

    def game_context(self) -> pd.DataFrame:
        """One row per team-game, carrying everything the taggers need."""
        if self._game_context is not None:
            return self._game_context
        lg = self.league
        games = lg.games
        rows = []
        for r in games.itertuples(index=False):
            for team, opp, pts, opp_pts, home, rest in (
                (r.home_team_id, r.away_team_id, r.home_pts, r.away_pts, True,
                 getattr(r, "home_rest_days", np.nan)),
                (r.away_team_id, r.home_team_id, r.away_pts, r.home_pts, False,
                 getattr(r, "away_rest_days", np.nan)),
            ):
                rows.append({
                    "game_id": r.game_id, "game_date": r.game_date,
                    "team_id": team, "opponent_team_id": opp,
                    "is_home": home, "rest_days": rest,
                    "pts": pts, "opp_pts": opp_pts,
                    "margin": (pts - opp_pts) if pd.notna(pts) else np.nan,
                    "won": bool(pts > opp_pts) if pd.notna(pts) else False,
                })
        ctx = pd.DataFrame(rows)

        # Opponent strength, for the opponent-quality vertical.
        standings = lg.standings().set_index("team_id")["point_diff"]
        ctx["opponent_rating"] = ctx["opponent_team_id"].map(standings)
        self._game_context = ctx
        return ctx

    def stint_context(self) -> pd.DataFrame:
        """Stints with running scores attached, for possession-level splits."""
        stints = self.league.stints.copy()
        if stints.empty:
            return stints
        stints = stints.sort_values(["game_id", "stint_id"])
        stints["home_pts_running"] = stints.groupby("game_id")["home_pts"].cumsum()
        stints["away_pts_running"] = stints.groupby("game_id")["away_pts"].cumsum()
        return stints

    # -- splitting ----------------------------------------------------------

    def team_split(self, dimension: str, *, team_id: str | None = None) -> pd.DataFrame:
        """Team efficiency within each bucket of a game-level dimension."""
        dim = self._require(dimension, "game")
        ctx = self.game_context()
        if team_id is not None:
            ctx = ctx[ctx["team_id"] == team_id]
        if ctx.empty:
            return pd.DataFrame()
        ctx = ctx.assign(bucket=dim.tagger(ctx))

        box = self.league.team_box.merge(
            ctx[["game_id", "team_id", "bucket", "won", "margin"]],
            on=["game_id", "team_id"], how="inner")
        from ..metrics.possessions import estimate_possessions

        box["poss"] = estimate_possessions(box["fga"], box["fta"], box["orb"], box["tov"])
        grouped = box.groupby("bucket", as_index=False).agg(
            games=("game_id", "nunique"), pts=("pts", "sum"), poss=("poss", "sum"),
            fgm=("fgm", "sum"), fga=("fga", "sum"), fg3m=("fg3m", "sum"),
            fg3a=("fg3a", "sum"), ftm=("ftm", "sum"), fta=("fta", "sum"),
            orb=("orb", "sum"), drb=("drb", "sum"), ast=("ast", "sum"),
            tov=("tov", "sum"), wins=("won", "sum"), margin=("margin", "mean"),
            minutes=("min", "sum"),
        )
        grouped["off_rating"] = 100.0 * grouped["pts"] / grouped["poss"]
        grouped["efg_pct"] = (grouped["fgm"] + 0.5 * grouped["fg3m"]) / grouped["fga"]
        grouped["ts_pct"] = grouped["pts"] / (2 * (grouped["fga"] + 0.44 * grouped["fta"]))
        grouped["tov_rate"] = grouped["tov"] / grouped["poss"]
        grouped["fg3a_rate"] = grouped["fg3a"] / grouped["fga"]
        grouped["ft_rate"] = grouped["fta"] / grouped["fga"]
        grouped["pace"] = 48.0 * grouped["poss"] / (grouped["minutes"] / 5.0)
        grouped["win_pct"] = grouped["wins"] / grouped["games"]
        return self._order(grouped, dim)

    def player_split(self, dimension: str, *, player_id: str | None = None,
                     per_mode: str = "per_36", min_minutes: float = 0.0) -> pd.DataFrame:
        """Player production within each bucket of a game-level dimension."""
        dim = self._require(dimension, "game")
        ctx = self.game_context().assign(bucket=lambda d: dim.tagger(d))
        box = self.league.box.merge(ctx[["game_id", "team_id", "bucket"]],
                                    on=["game_id", "team_id"], how="inner")
        if player_id is not None:
            box = box[box["player_id"] == player_id]
        if box.empty:
            return pd.DataFrame()

        from ..metrics.aggregate import player_totals
        from ..metrics.box import add_shooting
        from ..metrics.normalize import normalize

        totals = player_totals(box, by=("player_id", "bucket"))
        totals = add_shooting(totals)
        totals = totals[totals["min"] >= min_minutes]
        rated = normalize(totals, per_mode)
        rated["per_mode"] = per_mode
        if "player_name" in self.league.players.columns:
            names = self.league.players.drop_duplicates("player_id")[["player_id", "player_name"]]
            rated = rated.merge(names, on="player_id", how="left")
        return self._order(rated, dim)

    def lineup_split(self, dimension: str) -> pd.DataFrame:
        """Team efficiency within each bucket of a possession-level dimension."""
        dim = self._require(dimension, "possession")
        if not self.league.has_pbp:
            raise ValueError(
                f"the {dimension!r} vertical needs play-by-play data; this "
                "league was loaded without it"
            )
        stints = self.stint_context()
        if stints.empty:
            return pd.DataFrame()
        stints = stints.assign(bucket=dim.tagger(stints))
        rows = []
        for bucket, g in stints.groupby("bucket"):
            home_poss, away_poss = g["home_poss"].sum(), g["away_poss"].sum()
            rows.append({
                "bucket": bucket,
                "possessions": home_poss + away_poss,
                "stints": len(g),
                "minutes": g["seconds"].sum() / 60.0,
                "home_off_rating": 100.0 * g["home_pts"].sum() / home_poss if home_poss else np.nan,
                "away_off_rating": 100.0 * g["away_pts"].sum() / away_poss if away_poss else np.nan,
                "points_per_100": 100.0 * (g["home_pts"].sum() + g["away_pts"].sum())
                / (home_poss + away_poss) if (home_poss + away_poss) else np.nan,
                "home_margin_per_100": 100.0 * (g["home_pts"].sum() / home_poss
                                                - g["away_pts"].sum() / away_poss)
                if home_poss and away_poss else np.nan,
            })
        return self._order(pd.DataFrame(rows), dim)

    def with_without(self, player_id: str, *, teammate_id: str | None = None) -> pd.DataFrame:
        """A team's efficiency with and without a player (or a pair) on the floor."""
        from ..impact.onoff import on_off, pair_on_off

        if not self.league.has_pbp:
            raise ValueError("with/without splits need play-by-play data")
        if teammate_id:
            return pair_on_off(self.league.stints, player_id, teammate_id)
        table = on_off(self.league.stints)
        return table[table["player_id"] == player_id]

    def cross_split(self, dimension_a: str, dimension_b: str) -> pd.DataFrame:
        """Two game-level verticals at once, as a grid."""
        dim_a = self._require(dimension_a, "game")
        dim_b = self._require(dimension_b, "game")
        ctx = self.game_context()
        ctx = ctx.assign(bucket_a=dim_a.tagger(ctx), bucket_b=dim_b.tagger(ctx))
        from ..metrics.possessions import estimate_possessions

        box = self.league.team_box.merge(
            ctx[["game_id", "team_id", "bucket_a", "bucket_b", "won"]],
            on=["game_id", "team_id"], how="inner")
        box["poss"] = estimate_possessions(box["fga"], box["fta"], box["orb"], box["tov"])
        grouped = box.groupby(["bucket_a", "bucket_b"], as_index=False).agg(
            games=("game_id", "nunique"), pts=("pts", "sum"), poss=("poss", "sum"),
            wins=("won", "sum"))
        grouped["off_rating"] = 100.0 * grouped["pts"] / grouped["poss"]
        grouped["win_pct"] = grouped["wins"] / grouped["games"]
        return grouped

    # -- helpers ------------------------------------------------------------

    @staticmethod
    def _require(key: str, level: str) -> Dimension:
        dim = DIMENSIONS.get(key)
        if dim is None:
            raise KeyError(f"unknown vertical {key!r}; known: {sorted(DIMENSIONS)}")
        if dim.level != level:
            raise ValueError(
                f"{key!r} is a {dim.level}-level vertical; use "
                f"{'lineup_split' if dim.level == 'possession' else 'team_split'}()"
            )
        return dim

    @staticmethod
    def _order(frame: pd.DataFrame, dim: Dimension) -> pd.DataFrame:
        if frame.empty or dim.order is None or "bucket" not in frame.columns:
            return frame.reset_index(drop=True)
        rank = {b: i for i, b in enumerate(dim.order)}
        frame = frame.copy()
        frame["_rank"] = frame["bucket"].map(rank).fillna(len(rank))
        return frame.sort_values("_rank").drop(columns="_rank").reset_index(drop=True)
