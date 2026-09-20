"""Build the aggregated frames the metric formulas need.

Almost every advanced box-score metric needs team context -- a player's usage
rate depends on his team's field goal attempts while he was on the floor, his
rebound rate on the opponent's misses. So aggregation is not just a groupby:
it has to carry team totals, opponent totals and league totals alongside each
player's own line.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .. import constants as K
from .possessions import estimate_possessions, pace

PLAYER_SUMS = [
    "min", "fgm", "fga", "fg3m", "fg3a", "ftm", "fta", "orb", "drb",
    "ast", "stl", "blk", "tov", "pf", "pts",
]


def player_totals(box: pd.DataFrame, by=("player_id", "team_id")) -> pd.DataFrame:
    """Sum a player box score to season (or any grouping) totals."""
    by = list(by)
    agg = {c: "sum" for c in PLAYER_SUMS if c in box.columns}
    out = box.groupby(by, as_index=False, dropna=False).agg(
        **{c: (c, "sum") for c in agg},
        games=("game_id", "nunique"),
    )
    if "started" in box.columns:
        starts = box.groupby(by, as_index=False, dropna=False)["started"].sum()
        starts = starts.rename(columns={"started": "starts"})
        out = out.merge(starts, on=by, how="left")
    out["fg2m"] = out["fgm"] - out["fg3m"]
    out["fg2a"] = out["fga"] - out["fg3a"]
    out["trb"] = out["orb"] + out["drb"]
    return out


def team_totals(team_box: pd.DataFrame, by=("team_id",)) -> pd.DataFrame:
    """Sum a team box score, carrying opponent totals alongside."""
    by = list(by)
    own = team_box.groupby(by, as_index=False, dropna=False).agg(
        **{c: (c, "sum") for c in PLAYER_SUMS if c in team_box.columns},
        games=("game_id", "nunique"),
    )
    own["trb"] = own["orb"] + own["drb"]

    # Opponent totals: re-key each team-game row by the opponent.
    opp_src = team_box.copy()
    opp_src["_key"] = opp_src["opponent_team_id"]
    opp = opp_src.groupby(["_key"], as_index=False, dropna=False).agg(
        **{c: (c, "sum") for c in PLAYER_SUMS if c in opp_src.columns}
    )
    opp["trb"] = opp["orb"] + opp["drb"]
    opp = opp.rename(columns={c: f"opp_{c}" for c in opp.columns if c != "_key"})
    opp = opp.rename(columns={"_key": "team_id"})

    out = own.merge(opp, on="team_id", how="left")
    out = out.rename(columns={c: f"tm_{c}" for c in PLAYER_SUMS + ["trb", "games"]
                              if c in out.columns})
    out["tm_poss"] = 0.5 * (
        estimate_possessions(out["tm_fga"], out["tm_fta"], out["tm_orb"], out["tm_tov"])
        + estimate_possessions(out["opp_fga"], out["opp_fta"], out["opp_orb"], out["opp_tov"])
    )
    out["opp_poss"] = out["tm_poss"]     # both teams use ~the same count
    out["tm_pace"] = pace(out["tm_poss"], out["tm_min"])
    out["tm_off_rating"] = 100.0 * out["tm_pts"] / out["tm_poss"]
    out["tm_def_rating"] = 100.0 * out["opp_pts"] / out["opp_poss"]
    out["tm_net_rating"] = out["tm_off_rating"] - out["tm_def_rating"]
    return out


def league_totals(team_season: pd.DataFrame) -> dict:
    """League-wide aggregates used as the baseline in PER, WS and z-scores."""
    lg = {}
    for c in PLAYER_SUMS + ["trb", "poss", "games"]:
        col = f"tm_{c}"
        if col in team_season.columns:
            lg[c] = float(team_season[col].sum())
    lg["games"] = float(team_season["tm_games"].sum()) / 2.0  # each game has two teams
    lg["fg2m"] = lg["fgm"] - lg["fg3m"]
    lg["fg2a"] = lg["fga"] - lg["fg3a"]
    lg["pts_per_poss"] = lg["pts"] / lg["poss"]
    lg["pace"] = float(np.average(team_season["tm_pace"],
                                  weights=team_season["tm_games"]))
    lg["off_rating"] = 100.0 * lg["pts_per_poss"]
    return lg


def blend_team_context(stints: pd.DataFrame, teams: pd.DataFrame) -> pd.DataFrame:
    """Collapse a traded player's stints into one season of team context.

    A player who changes teams mid-season has one row per team, and every
    per-team row carries that team's totals as the denominator for his rates.
    Summing his counting stats is easy; the denominators are the problem.

    The answer is a minutes-weighted blend: two-thirds of a season in Utah and
    one-third in Los Angeles gives a denominator two-thirds Utah's pace and
    one-third Los Angeles's -- which is, exactly, the team context he actually
    played in. His primary team is the one he played the most minutes for.
    """
    weights = stints[["player_id", "team_id", "min"]].copy()
    total = weights.groupby("player_id")["min"].transform("sum")
    # A player with zero recorded minutes across every stint would divide by
    # zero; weight his stints equally instead.
    weights["w"] = np.where(total > 0, weights["min"] / total.replace(0, np.nan), np.nan)
    weights["w"] = weights["w"].fillna(
        1.0 / weights.groupby("player_id")["team_id"].transform("count"))

    primary = (weights.sort_values(["player_id", "min"], ascending=[True, False])
               .drop_duplicates("player_id")[["player_id", "team_id"]])

    context = weights.merge(teams, on="team_id", how="left")
    value_cols = [c for c in teams.columns if c != "team_id"]
    for c in value_cols:
        context[c] = context[c] * context["w"]
    blended = context.groupby("player_id", as_index=False)[value_cols].sum()
    return blended.merge(primary, on="player_id", how="left")


def player_season(league, *, by=("player_id", "team_id"),
                  combine_stints: bool = False,
                  box: pd.DataFrame | None = None) -> pd.DataFrame:
    """Player totals joined to their team's and opponents' totals.

    This is the frame every box-score metric in `metrics.box` consumes.

    With `combine_stints`, a player traded mid-season comes back as one row
    for the whole season rather than one per team. Without it, a lineup tool
    keyed on player id silently keeps whichever stint happened to be last --
    so Tyus Jones, who played for three teams, would be rated on the 94
    minutes of one of them instead of the 1,023 he actually played.
    """
    box = league.box if box is None else box
    teams = team_totals(league.team_box)
    if combine_stints:
        stints = player_totals(box, by=["player_id", "team_id"])
        players = player_totals(box, by=["player_id"])
        out = players.merge(blend_team_context(stints, teams),
                            on="player_id", how="left")
    else:
        players = player_totals(box, by=by)
        out = players.merge(teams, on="team_id", how="left")
    # `position_raw` carries the feed's own label (often only G/F/C) so the
    # lineup model can sharpen it later; dropping it here would silently
    # disable that.
    meta_cols = [c for c in ("player_name", "position", "position_raw", "age")
                 if c in league.players.columns]
    if meta_cols:
        meta = league.players.drop_duplicates("player_id")[["player_id"] + meta_cols]
        out = out.merge(meta, on="player_id", how="left")
    return out
