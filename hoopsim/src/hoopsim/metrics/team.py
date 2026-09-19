"""Team efficiency: four factors, ratings, SRS, Pythagorean records, strength
of schedule, and opponent-adjusted ratings.

The distinction that matters here is between *observed* and *adjusted*. A
team's raw offensive rating mixes how good its offence is with how bad the
defences it faced were. `adjusted_ratings` separates the two by solving for
the offensive and defensive ratings that best explain every game in the
season simultaneously -- the same idea behind KenPom's college ratings.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .. import constants as K
from .possessions import estimate_possessions, pace


def four_factors(team_box: pd.DataFrame) -> pd.DataFrame:
    """Dean Oliver's four factors, on both offence and defence.

    Shooting, turnovers, rebounding and free throws -- in that order of
    importance -- explain nearly all of the difference between teams.
    """
    grouped = team_box.groupby("team_id", as_index=False).sum(numeric_only=True)
    opp = team_box.copy()
    opp["team_id"] = opp["opponent_team_id"]
    opp = opp.groupby("team_id", as_index=False).sum(numeric_only=True)
    opp = opp.rename(columns={c: f"opp_{c}" for c in opp.columns if c != "team_id"})
    df = grouped.merge(opp, on="team_id", how="left")

    own_poss = estimate_possessions(df["fga"], df["fta"], df["orb"], df["tov"])
    opp_poss = estimate_possessions(df["opp_fga"], df["opp_fta"], df["opp_orb"], df["opp_tov"])
    poss = 0.5 * (own_poss + opp_poss)

    out = pd.DataFrame({"team_id": df["team_id"]})
    out["poss"] = poss
    out["games"] = df["game_id"] if "game_id" in df.columns else np.nan
    out["pace"] = pace(poss, df["min"])

    out["off_efg_pct"] = (df["fgm"] + 0.5 * df["fg3m"]) / df["fga"]
    out["off_tov_rate"] = df["tov"] / poss
    out["off_orb_rate"] = df["orb"] / (df["orb"] + df["opp_drb"])
    out["off_ft_rate"] = df["fta"] / df["fga"]
    out["off_ft_made_rate"] = df["ftm"] / df["fga"]

    out["def_efg_pct"] = (df["opp_fgm"] + 0.5 * df["opp_fg3m"]) / df["opp_fga"]
    out["def_tov_rate"] = df["opp_tov"] / poss
    out["def_drb_rate"] = df["drb"] / (df["drb"] + df["opp_orb"])
    out["def_ft_rate"] = df["opp_fta"] / df["opp_fga"]

    out["off_rating"] = 100.0 * df["pts"] / poss
    out["def_rating"] = 100.0 * df["opp_pts"] / poss
    out["net_rating"] = out["off_rating"] - out["def_rating"]
    out["off_fg3a_rate"] = df["fg3a"] / df["fga"]
    out["def_fg3a_rate"] = df["opp_fg3a"] / df["opp_fga"]
    out["off_ts_pct"] = df["pts"] / (2.0 * (df["fga"] + K.FT_POSSESSION_COEF * df["fta"]))
    out["def_ts_pct"] = df["opp_pts"] / (2.0 * (df["opp_fga"] + K.FT_POSSESSION_COEF * df["opp_fta"]))
    return out


# ---------------------------------------------------------------------------
# Pythagorean expectation
# ---------------------------------------------------------------------------

def pythagorean_win_pct(points_for, points_against, *,
                        exponent: float = K.PYTHAGOREAN_EXPONENT) -> np.ndarray:
    """Expected win percentage from points scored and allowed."""
    pf = np.asarray(points_for, dtype=float)
    pa = np.asarray(points_against, dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        return pf ** exponent / (pf ** exponent + pa ** exponent)


def pythagenpat_exponent(points_for, points_against, games, *,
                         coef: float = K.PYTHAGENPAT_COEF,
                         reference: float = K.PYTHAGENPAT_REFERENCE_PPG,
                         base: float = K.PYTHAGOREAN_EXPONENT) -> np.ndarray:
    """Per-team exponent from the scoring environment.

    A fixed exponent misprices very high- and very low-scoring teams.
    Pythagenpat derives the exponent from points per game instead, anchored so
    that a league-average environment reproduces the fixed exponent exactly.
    See constants.PYTHAGENPAT_COEF for why this is not the baseball form.
    """
    pf = np.asarray(points_for, dtype=float)
    pa = np.asarray(points_against, dtype=float)
    g = np.asarray(games, dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        combined = np.where(g > 0, (pf + pa) / g, np.nan)
        return base * (combined / reference) ** coef


def pythagenpat_win_pct(points_for, points_against, games, *,
                        coef: float = K.PYTHAGENPAT_COEF) -> np.ndarray:
    exp = pythagenpat_exponent(points_for, points_against, games, coef=coef)
    return pythagorean_win_pct(points_for, points_against, exponent=exp)


# ---------------------------------------------------------------------------
# SRS and strength of schedule
# ---------------------------------------------------------------------------

def simple_rating_system(games: pd.DataFrame, teams: list[str] | None = None,
                         *, cap: float | None = None) -> pd.DataFrame:
    """Simple Rating System: margin of victory adjusted for schedule.

    Solves the linear system SRS_i = MOV_i + (average SRS of opponents faced)
    directly rather than iterating, which is exact and faster.
    """
    g = games.dropna(subset=["home_pts", "away_pts"])
    if teams is None:
        teams = sorted(set(g["home_team_id"]) | set(g["away_team_id"]))
    idx = {t: i for i, t in enumerate(teams)}
    n = len(teams)

    margins = np.zeros(n)
    counts = np.zeros(n)
    adjacency = np.zeros((n, n))

    for r in g.itertuples(index=False):
        h, a = idx[r.home_team_id], idx[r.away_team_id]
        margin = float(r.home_pts) - float(r.away_pts)
        if cap is not None:
            margin = float(np.clip(margin, -cap, cap))
        margins[h] += margin
        margins[a] -= margin
        counts[h] += 1
        counts[a] += 1
        adjacency[h, a] += 1
        adjacency[a, h] += 1

    with np.errstate(divide="ignore", invalid="ignore"):
        mov = np.where(counts > 0, margins / counts, 0.0)
        weights = np.where(counts[:, None] > 0, adjacency / counts[:, None], 0.0)

    # (I - W) * srs = mov
    a_mat = np.eye(n) - weights
    # The system is singular by one degree of freedom (adding a constant to
    # every rating is a solution), so pin the mean to zero.
    a_mat = np.vstack([a_mat, np.ones(n)])
    b_vec = np.concatenate([mov, [0.0]])
    srs, *_ = np.linalg.lstsq(a_mat, b_vec, rcond=None)

    return pd.DataFrame({
        "team_id": teams,
        "games": counts,
        "mov": mov,
        "srs": srs,
        "sos": srs - mov,
    })


# ---------------------------------------------------------------------------
# Opponent-adjusted efficiency
# ---------------------------------------------------------------------------

def adjusted_ratings(games: pd.DataFrame, team_box: pd.DataFrame,
                     *, ridge: float = 1.0,
                     home_advantage: float | None = None) -> pd.DataFrame:
    """Opponent-adjusted offensive and defensive ratings.

    Every team-game supplies one equation:

        points per 100 possessions = league mean
                                   + offence(team)
                                   - defence(opponent)
                                   + home adjustment

    Solving all of them together gives ratings on a common scale, so a team
    that scored 118 against elite defences is correctly rated above one that
    scored 118 against poor ones. `ridge` shrinks ratings toward league
    average, which matters early in a season when schedules are unbalanced.
    """
    tb = team_box.copy()
    own = estimate_possessions(tb["fga"], tb["fta"], tb["orb"], tb["tov"])
    opp_lookup = tb.set_index(["game_id", "team_id"])[["fga", "fta", "orb", "tov"]]
    opp_rows = []
    for r in tb.itertuples(index=False):
        key = (r.game_id, r.opponent_team_id)
        if key in opp_lookup.index:
            o = opp_lookup.loc[key]
            opp_rows.append(estimate_possessions(o["fga"], o["fta"], o["orb"], o["tov"]))
        else:
            opp_rows.append(np.nan)
    tb["poss"] = np.where(np.isnan(opp_rows), own, 0.5 * (own + np.asarray(opp_rows)))
    tb = tb[tb["poss"] > 0]
    tb["ortg"] = 100.0 * tb["pts"] / tb["poss"]

    teams = sorted(set(tb["team_id"]) | set(tb["opponent_team_id"]))
    idx = {t: i for i, t in enumerate(teams)}
    n = len(teams)

    rows = len(tb)
    # Columns: n offence + n defence + 1 home term.
    x = np.zeros((rows, 2 * n + 1))
    y = tb["ortg"].to_numpy(dtype=float)
    for i, r in enumerate(tb.itertuples(index=False)):
        x[i, idx[r.team_id]] = 1.0
        x[i, n + idx[r.opponent_team_id]] = -1.0
        x[i, 2 * n] = 1.0 if bool(getattr(r, "is_home", False)) else -1.0

    mean_ortg = float(np.mean(y))
    y_centered = y - mean_ortg

    penalty = np.eye(2 * n + 1) * ridge
    penalty[2 * n, 2 * n] = 0.0     # do not shrink the home term
    beta = np.linalg.solve(x.T @ x + penalty, x.T @ y_centered)

    off = beta[:n]
    dfn = beta[n:2 * n]
    home = beta[2 * n]
    # Centre both sides so they are interpretable as "points above average".
    off = off - off.mean()
    dfn = dfn - dfn.mean()

    out = pd.DataFrame({
        "team_id": teams,
        "adj_off_rating": mean_ortg + off,
        "adj_def_rating": mean_ortg - dfn,
        "adj_net_rating": off + dfn,
        "off_above_avg": off,
        "def_above_avg": dfn,
    })
    out.attrs["home_advantage_per_100"] = float(home * 2.0)
    out.attrs["league_off_rating"] = mean_ortg
    return out


def team_summary(league, *, ridge: float = 1.0) -> pd.DataFrame:
    """One row per team with raw and adjusted efficiency, record and SRS."""
    ff = four_factors(league.team_box)
    srs = simple_rating_system(league.games)
    adj = adjusted_ratings(league.games, league.team_box, ridge=ridge)
    standings = league.standings()

    out = (standings.merge(ff, on="team_id", how="left", suffixes=("", "_ff"))
                    .merge(srs.drop(columns=["games"]), on="team_id", how="left")
                    .merge(adj, on="team_id", how="left"))
    out["pythag_win_pct"] = pythagorean_win_pct(out["pf"], out["pa"])
    out["pythagenpat_win_pct"] = pythagenpat_win_pct(out["pf"], out["pa"], out["games_x"]
                                                     if "games_x" in out.columns else out["games"])
    gcol = "games_x" if "games_x" in out.columns else "games"
    out["pythag_wins"] = out["pythag_win_pct"] * out[gcol]
    out["luck"] = out["w"] - out["pythag_wins"]
    out.attrs.update(adj.attrs)
    return out.sort_values("adj_net_rating", ascending=False).reset_index(drop=True)
