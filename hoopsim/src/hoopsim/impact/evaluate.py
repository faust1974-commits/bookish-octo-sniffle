"""Score a player-rating model by the job it is actually asked to do.

A rating model is easy to fool yourself about. Fit it, look at the top of
the list, recognise the names, call it good. That is how a model that rates
a backup centre seventh in the league survives.

The obvious defence -- held-out prediction error on individual stints --
turns out to be useless here. A stint is a handful of possessions, its
margin per 100 is dominated by noise, and every model tried on 2025-26
landed between 63.6 and 64.0 points of RMSE. The instrument cannot read the
difference.

Aggregating fixes it. Take a season's ratings, apply them to the *next*
season's rosters, and ask how much of how those teams actually turned out
is explained. The noise cancels over a season, the test is genuinely out of
sample, and it spans real roster turnover -- which is the situation the
tool is used in, not a hypothetical.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .roster_strength import raw_strength


def score_against_season(ratings: pd.DataFrame,
                         later_players: pd.DataFrame,
                         later_teams: pd.DataFrame,
                         *, off_col: str = "rapm_off",
                         def_col: str = "rapm_def") -> dict:
    """How well do these ratings explain a later season's team results?

    Parameters
    ----------
    ratings:
        One row per player with `player_id` and the two side columns. Any
        player missing from it is treated as league-average, which is the
        honest encoding of "this model has never seen him".
    later_players:
        The later season's `player_id`, `team_id`, `min` and `games` -- who
        actually played where, and how much.
    later_teams:
        The later season's `team_id` and `net_rating`, the thing to explain.

    Returns the R^2, the residual spread in points per 100, and what share
    of the later season's minutes the model had a rating for.
    """
    rated = ratings.set_index("player_id")
    frame = later_players.dropna(subset=["team_id", "min", "games"]).copy()
    if frame.empty:
        raise ValueError("no players in the later season to score against")

    frame["off_impact"] = frame["player_id"].map(rated[off_col]).fillna(0.0)
    frame["def_impact"] = frame["player_id"].map(rated[def_col]).fillna(0.0)

    known = frame["player_id"].isin(rated.index)
    minutes = frame["min"].to_numpy(dtype=float)
    coverage = (float(minutes[known.to_numpy()].sum()) / float(minutes.sum())
                if minutes.sum() else 0.0)

    rows = []
    for team_id, roster in frame.groupby("team_id"):
        off, dfn = raw_strength(roster)
        rows.append({"team_id": team_id, "raw_net": off + dfn})
    merged = pd.DataFrame(rows).merge(
        later_teams[["team_id", "net_rating"]], on="team_id", how="inner")
    if len(merged) < 3:
        raise ValueError("need at least three teams in common to score")

    x = merged["raw_net"].to_numpy(dtype=float)
    y = merged["net_rating"].to_numpy(dtype=float)
    # The scale is free -- roster strength is calibrated downstream -- so the
    # question is only how much of the variance the ordering explains.
    slope, intercept = np.polyfit(x, y, 1)
    resid = y - (slope * x + intercept)
    ss_tot = float(((y - y.mean()) ** 2).sum())

    return {
        "r_squared": 1.0 - float((resid ** 2).sum()) / ss_tot if ss_tot else 0.0,
        "rmse": float(np.sqrt((resid ** 2).mean())),
        "slope": float(slope),
        "intercept": float(intercept),
        "n_teams": int(len(merged)),
        "minute_coverage": coverage,
    }
