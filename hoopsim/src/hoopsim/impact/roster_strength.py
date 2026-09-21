"""Team strength from the players on the roster, not from last season's wins.

A team's record is a fact about the team that played those games. The moment
a roster changes -- a trade, a signing, a lineup the user drags together by
hand -- that record stops describing it. Simulating Miami on last season's
net rating after Giannis arrives answers a question nobody asked.

So strength is rebuilt from the roster: project each player's minutes, weight
his offensive and defensive impact by the share of the floor he occupies, and
sum. Five players are on the floor at once, so a player taking a third of the
available minutes contributes five thirds of his per-100 impact.

The raw sum is biased -- impacts are measured against an average *player*
while a team is measured against an average *team*, and the two baselines do
not coincide -- so the result is calibrated against the league it came from
by ordinary least squares. `calibrate()` fits that line; the fit is reported
rather than assumed, and `tests/test_roster_strength.py` fails if it decays.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .. import constants as K

#: No player is projected for more of the game than this, however many
#: minutes he played last season. Nobody averages 40 over a season.
MAX_MINUTES_PER_GAME = 36.0

#: Team minutes available in a regulation game: five players, 48 minutes.
TEAM_MINUTES = float(K.PLAYERS_ON_FLOOR) * 48.0


def project_minutes(minutes_per_game: np.ndarray) -> np.ndarray:
    """Split 240 team-minutes across a roster, in proportion to last year.

    Capped per player and renormalised, so a roster of five iron men and a
    roster of twelve part-timers both add to a full game.
    """
    mpg = np.asarray(minutes_per_game, dtype=float)
    mpg = np.where(np.isfinite(mpg) & (mpg > 0), mpg, 0.0)
    if mpg.sum() <= 0:
        return np.zeros_like(mpg)

    out = mpg * (TEAM_MINUTES / mpg.sum())

    # A short roster cannot cover the game under the cap -- seven players at
    # 36 minutes is 252, six is only 216. Where the cap is arithmetically
    # infeasible it is dropped rather than quietly returning a team that
    # plays four and a half men, which would read as a terrible team instead
    # of a short one.
    if (out > 0).sum() * MAX_MINUTES_PER_GAME < TEAM_MINUTES:
        return out

    # Capping frees minutes that have to land somewhere, so redistribute to
    # the uncapped players and repeat until it settles.
    for _ in range(12):
        over = out > MAX_MINUTES_PER_GAME
        if not over.any():
            break
        spare = float((out[over] - MAX_MINUTES_PER_GAME).sum())
        out[over] = MAX_MINUTES_PER_GAME
        room = ~over & (out > 0)
        if not room.any():
            break
        out[room] += spare * (out[room] / out[room].sum())
    return out


def raw_strength(frame: pd.DataFrame, minutes: np.ndarray | None = None,
                 replacement: tuple[float, float] = (0.0, 0.0),
                 ) -> tuple[float, float]:
    """Uncalibrated (offense, defense) for one roster, in points per 100.

    `frame` needs `off_impact`, `def_impact`, `min` and `games`.

    `minutes` is a hand-set rotation. Last season's minutes are a guess, and
    a poor one as soon as a player changes team or role, so a caller who
    knows better can say so.

    Minutes nobody is assigned are not free: sit a star down and somebody
    plays those minutes, and that somebody is the end of the bench. They are
    charged at `replacement` rather than handed to the remaining starters,
    which would make benching a team's best player nearly costless.
    """
    if frame.empty:
        return 0.0, 0.0
    if minutes is None:
        games = frame["games"].to_numpy(dtype=float)
        mpg = np.divide(frame["min"].to_numpy(dtype=float), games,
                        out=np.zeros(len(frame)), where=games > 0)
        allocated = project_minutes(mpg)
    else:
        allocated = np.asarray(minutes, dtype=float)
    allocated = np.where(np.isfinite(allocated) & (allocated > 0), allocated, 0.0)

    total = float(allocated.sum())
    if total <= 0:
        return 0.0, 0.0

    scale = TEAM_MINUTES / total if total > TEAM_MINUTES else 1.0
    shortfall = max(0.0, TEAM_MINUTES - total)

    share = allocated * scale / TEAM_MINUTES * K.PLAYERS_ON_FLOOR
    off = float(np.nansum(share * frame["off_impact"].to_numpy(dtype=float)))
    dfn = float(np.nansum(share * frame["def_impact"].to_numpy(dtype=float)))

    spare = shortfall / TEAM_MINUTES * K.PLAYERS_ON_FLOOR
    return off + spare * replacement[0], dfn + spare * replacement[1]


def calibrate(players: pd.DataFrame, team_ratings: pd.DataFrame) -> dict:
    """Fit raw roster strength onto the league's own observed net ratings.

    Returns the slope and intercept, plus the R^2 and residual spread so a
    caller can see how much of a team's season the roster actually explains.
    """
    rows = []
    for team_id, roster in players.groupby("team_id"):
        off, dfn = raw_strength(roster)
        rows.append({"team_id": team_id, "raw_off": off, "raw_def": dfn,
                     "raw_net": off + dfn})
    raw = pd.DataFrame(rows).merge(
        team_ratings[["team_id", "net_rating"]], on="team_id", how="inner")
    if len(raw) < 3:
        raise ValueError("need at least three teams to calibrate")

    x = raw["raw_net"].to_numpy(dtype=float)
    y = raw["net_rating"].to_numpy(dtype=float)
    slope, intercept = np.polyfit(x, y, 1)
    fitted = slope * x + intercept
    ss_res = float(((y - fitted) ** 2).sum())
    ss_tot = float(((y - y.mean()) ** 2).sum())

    return {
        "slope": float(slope),
        "intercept": float(intercept),
        "r_squared": 1.0 - ss_res / ss_tot if ss_tot else 0.0,
        "residual_sd": float(np.sqrt(ss_res / len(raw))),
        "n_teams": int(len(raw)),
    }


def team_strength(frame: pd.DataFrame, calibration: dict,
                  minutes: np.ndarray | None = None,
                  replacement: tuple[float, float] = (0.0, 0.0)) -> dict:
    """Calibrated offense, defense and net for one roster.

    The calibration is fitted on net rating, so the slope applies to both
    halves and the intercept -- a whole-team offset -- is split between them
    in the direction each one runs: a point of offense and a point of defence
    are both a point of net rating, but they have opposite signs on the
    scoreboard.
    """
    off, dfn = raw_strength(frame, minutes, replacement)
    slope = calibration["slope"]
    half = calibration["intercept"] / 2.0
    return {
        "off": slope * off + half,
        "def": slope * dfn + half,
        "net": slope * (off + dfn) + calibration["intercept"],
        "raw_off": off,
        "raw_def": dfn,
    }
