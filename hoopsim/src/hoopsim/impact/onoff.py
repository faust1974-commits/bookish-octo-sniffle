"""On/off splits and lineup-level ratings.

On/off is the most intuitive impact number and the most misleading. A player's
on/off differential mixes his own value with the quality of whoever replaces
him and whoever he plays alongside. A good bench makes a starter look worse; a
terrible backup makes him look like an MVP. It is reported here because it is
genuinely informative as a *description* of what happened, and because the gap
between a player's on/off and his RAPM is itself diagnostic. It should not be
used as an impact estimate on its own.
"""

from __future__ import annotations

from collections import defaultdict

import numpy as np
import pandas as pd

from .. import constants as K


def _accumulate(stints: pd.DataFrame, exclude_garbage: bool):
    df = stints
    if exclude_garbage and "garbage_time" in df.columns:
        df = df[~df["garbage_time"].astype(bool)]
    return df


def on_off(stints: pd.DataFrame, *, exclude_garbage: bool = True) -> pd.DataFrame:
    """Team net rating with each player on the floor versus off it.

    Returns one row per player with on-court offensive, defensive and net
    rating, the same off-court, the differential, and possession counts so you
    can see how much of the split is noise.
    """
    df = _accumulate(stints, exclude_garbage)

    # Team-level totals, to derive "off court" by subtraction.
    team_tot: dict[str, dict] = defaultdict(
        lambda: {"off_pts": 0.0, "off_poss": 0.0, "def_pts": 0.0, "def_poss": 0.0}
    )
    on: dict[tuple[str, str], dict] = defaultdict(
        lambda: {"off_pts": 0.0, "off_poss": 0.0, "def_pts": 0.0, "def_poss": 0.0}
    )

    for r in df.itertuples(index=False):
        for team, lineup, opp_lineup, pts, poss, opp_pts, opp_poss in (
            (r.home_team_id, r.home_lineup, r.away_lineup, r.home_pts, r.home_poss,
             r.away_pts, r.away_poss),
            (r.away_team_id, r.away_lineup, r.home_lineup, r.away_pts, r.away_poss,
             r.home_pts, r.home_poss),
        ):
            t = team_tot[team]
            t["off_pts"] += pts
            t["off_poss"] += poss
            t["def_pts"] += opp_pts
            t["def_poss"] += opp_poss
            for pid in lineup:
                slot = on[(pid, team)]
                slot["off_pts"] += pts
                slot["off_poss"] += poss
                slot["def_pts"] += opp_pts
                slot["def_poss"] += opp_poss

    rows = []
    for (pid, team), slot in on.items():
        t = team_tot[team]
        off_poss_off = t["off_poss"] - slot["off_poss"]
        def_poss_off = t["def_poss"] - slot["def_poss"]
        on_ortg = 100.0 * slot["off_pts"] / slot["off_poss"] if slot["off_poss"] else np.nan
        on_drtg = 100.0 * slot["def_pts"] / slot["def_poss"] if slot["def_poss"] else np.nan
        off_ortg = 100.0 * (t["off_pts"] - slot["off_pts"]) / off_poss_off if off_poss_off else np.nan
        off_drtg = 100.0 * (t["def_pts"] - slot["def_pts"]) / def_poss_off if def_poss_off else np.nan
        rows.append({
            "player_id": pid,
            "team_id": team,
            "on_poss": slot["off_poss"],
            "off_poss": off_poss_off,
            "on_off_rating": on_ortg,
            "on_def_rating": on_drtg,
            "on_net": on_ortg - on_drtg,
            "off_off_rating": off_ortg,
            "off_def_rating": off_drtg,
            "off_net": off_ortg - off_drtg,
        })
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    out["on_off_net"] = out["on_net"] - out["off_net"]
    return out.sort_values("on_off_net", ascending=False).reset_index(drop=True)


def lineup_ratings(stints: pd.DataFrame, *, min_possessions: float = 25.0,
                   exclude_garbage: bool = True) -> pd.DataFrame:
    """Observed offensive, defensive and net rating for each five-man unit.

    Read the possession column before reading anything else. A unit with 40
    possessions has a standard error around 18 points per 100, so almost every
    extreme lineup rating in a season is noise. `impact.lineup` models unit
    quality instead of reading it off the sample, which is what you should use
    for decisions.
    """
    df = _accumulate(stints, exclude_garbage)
    acc: dict[tuple[str, frozenset], dict] = defaultdict(
        lambda: {"pts": 0.0, "poss": 0.0, "opp_pts": 0.0, "opp_poss": 0.0, "seconds": 0.0}
    )
    for r in df.itertuples(index=False):
        for team, lineup, pts, poss, opp_pts, opp_poss in (
            (r.home_team_id, r.home_lineup, r.home_pts, r.home_poss, r.away_pts, r.away_poss),
            (r.away_team_id, r.away_lineup, r.away_pts, r.away_poss, r.home_pts, r.home_poss),
        ):
            slot = acc[(team, lineup)]
            slot["pts"] += pts
            slot["poss"] += poss
            slot["opp_pts"] += opp_pts
            slot["opp_poss"] += opp_poss
            slot["seconds"] += getattr(r, "seconds", 0.0)

    rows = []
    for (team, lineup), slot in acc.items():
        if slot["poss"] < min_possessions:
            continue
        ortg = 100.0 * slot["pts"] / slot["poss"] if slot["poss"] else np.nan
        drtg = 100.0 * slot["opp_pts"] / slot["opp_poss"] if slot["opp_poss"] else np.nan
        rows.append({
            "team_id": team,
            "lineup": lineup,
            "players": sorted(lineup),
            "poss": slot["poss"],
            "minutes": slot["seconds"] / 60.0,
            "off_rating": ortg,
            "def_rating": drtg,
            "net_rating": ortg - drtg,
        })
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    # Standard error of a net rating estimate, so the noise is visible in the
    # same table as the number.
    out["net_rating_se"] = 100.0 * np.sqrt(2.0) * 1.05 / np.sqrt(out["poss"])
    return out.sort_values("net_rating", ascending=False).reset_index(drop=True)


def pair_on_off(stints: pd.DataFrame, player_a: str, player_b: str,
                *, exclude_garbage: bool = True) -> pd.DataFrame:
    """Net rating in the four states of two players being on or off together.

    This is how you actually answer "do these two work together" -- the
    both-on cell against the one-on cells, with possession counts attached.
    """
    df = _accumulate(stints, exclude_garbage)
    cells = {k: {"pts": 0.0, "poss": 0.0, "opp_pts": 0.0, "opp_poss": 0.0}
             for k in ("both_on", "a_only", "b_only", "both_off")}
    for r in df.itertuples(index=False):
        for lineup, pts, poss, opp_pts, opp_poss in (
            (r.home_lineup, r.home_pts, r.home_poss, r.away_pts, r.away_poss),
            (r.away_lineup, r.away_pts, r.away_poss, r.home_pts, r.home_poss),
        ):
            a, b = player_a in lineup, player_b in lineup
            # Only count possessions for the team that could field both.
            if not (a or b):
                continue
            key = "both_on" if a and b else ("a_only" if a else "b_only")
            cells[key]["pts"] += pts
            cells[key]["poss"] += poss
            cells[key]["opp_pts"] += opp_pts
            cells[key]["opp_poss"] += opp_poss

    rows = []
    for key, slot in cells.items():
        if slot["poss"] == 0:
            continue
        ortg = 100.0 * slot["pts"] / slot["poss"]
        drtg = 100.0 * slot["opp_pts"] / slot["opp_poss"] if slot["opp_poss"] else np.nan
        rows.append({"state": key, "poss": slot["poss"], "off_rating": ortg,
                     "def_rating": drtg, "net_rating": ortg - drtg})
    return pd.DataFrame(rows)
