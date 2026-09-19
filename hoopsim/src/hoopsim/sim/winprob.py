"""Closed-form win probability.

Fast, analytic, and good enough for most purposes. A projected margin plus a
standard deviation is a complete probabilistic forecast of a basketball game,
and the whole model reduces to two numbers:

    margin = (home rating - away rating) + home advantage + rest adjustment
    P(home win) = Phi(margin / sigma)

Everything else -- possession simulation, player projections, lineup models --
exists to produce a better `margin`. Sigma is close to fixed at about 13
points and there is very little any model can do about it; basketball is a
high-variance sport and honest forecasts say so.

The in-game function is separate, because as the clock runs the relevant
variance is the variance of the *remaining* possessions, not the whole game.
"""

from __future__ import annotations

import numpy as np
from scipy import stats

from .. import constants as K


def rest_adjustment(rest_days) -> np.ndarray:
    """Points of margin from days of rest. Back-to-backs cost the most."""
    rest = np.asarray(rest_days, dtype=float)
    out = np.full(rest.shape, K.REST_ADJUSTMENT_DEFAULT, dtype=float)
    for days, value in K.REST_ADJUSTMENT.items():
        out = np.where(rest == days, value, out)
    return out


def projected_margin(home_rating, away_rating, *,
                     home_advantage: float = K.DEFAULT_HOME_ADVANTAGE,
                     home_rest=None, away_rest=None,
                     neutral_site: bool = False) -> np.ndarray:
    """Expected home margin, in points.

    Ratings are net ratings in points per 100 possessions. They are used
    directly as points of margin, which assumes a roughly 100-possession game;
    pass pace-scaled ratings if that matters for your use.
    """
    margin = np.asarray(home_rating, dtype=float) - np.asarray(away_rating, dtype=float)
    if not neutral_site:
        margin = margin + home_advantage
    if home_rest is not None:
        margin = margin + rest_adjustment(home_rest)
    if away_rest is not None:
        margin = margin - rest_adjustment(away_rest)
    return margin


def margin_to_win_prob(margin, *, sd: float = K.GAME_MARGIN_SD) -> np.ndarray:
    """Probability the favourite wins, given an expected margin."""
    return stats.norm.cdf(np.asarray(margin, dtype=float) / sd)


def win_probability(home_rating, away_rating, **kwargs) -> np.ndarray:
    """Probability the home team wins."""
    sd = kwargs.pop("sd", K.GAME_MARGIN_SD)
    return margin_to_win_prob(projected_margin(home_rating, away_rating, **kwargs), sd=sd)


def win_prob_to_margin(prob, *, sd: float = K.GAME_MARGIN_SD) -> np.ndarray:
    """Invert a win probability back into an expected margin."""
    return stats.norm.ppf(np.clip(np.asarray(prob, dtype=float), 1e-9, 1 - 1e-9)) * sd


def projected_scores(home_rating, away_rating, *, pace: float = K.LEAGUE_DEFAULTS["pace"],
                     league_rating: float = K.LEAGUE_DEFAULTS["off_rating"],
                     **kwargs) -> tuple[np.ndarray, np.ndarray]:
    """Expected points for each team, not just the margin.

    Splits the projected margin evenly around the expected total, which is
    what pace and the league scoring environment determine.
    """
    margin = projected_margin(home_rating, away_rating, **kwargs)
    expected_total = 2.0 * pace * league_rating / 100.0
    home = expected_total / 2.0 + margin / 2.0
    away = expected_total / 2.0 - margin / 2.0
    return home, away


def cover_probability(margin, spread, *, sd: float = K.GAME_MARGIN_SD) -> np.ndarray:
    """Probability the home team beats a given spread.

    `spread` is stated from the home team's perspective in the usual sign
    convention: -6.5 means the home team is favoured by 6.5.
    """
    margin = np.asarray(margin, dtype=float)
    spread = np.asarray(spread, dtype=float)
    return stats.norm.cdf((margin + spread) / sd)


def over_probability(expected_total, line, *, sd: float = 16.0) -> np.ndarray:
    """Probability a game's combined score exceeds a line.

    Total variance is larger than margin variance because shared pace does not
    cancel in a sum the way it does in a difference.
    """
    return 1.0 - stats.norm.cdf((np.asarray(line, dtype=float)
                                 - np.asarray(expected_total, dtype=float)) / sd)


def live_win_probability(margin, seconds_remaining, *,
                         possession: int = 0,
                         pace: float = K.LEAGUE_DEFAULTS["pace"],
                         pre_game_margin: float = 0.0) -> np.ndarray:
    """In-game win probability from score, clock and possession.

    The variance that matters is the variance of the possessions still to be
    played, which shrinks as the clock runs. `possession` is +1 if the team
    whose margin is given has the ball, -1 if not, 0 if unknown.
    """
    margin = np.asarray(margin, dtype=float)
    seconds = np.clip(np.asarray(seconds_remaining, dtype=float), 0.0, None)

    possessions_left = pace * 2.0 * seconds / (K.MINUTES_PER_GAME * 60.0)
    # Points per possession has a standard deviation near 1.03; scale it up by
    # the number of possessions each side still has.
    sd = np.sqrt(np.maximum(possessions_left, 1e-6)) * 1.03
    sd = np.maximum(sd, 0.75)

    # Carry a fraction of the pre-game expectation, decaying as the game runs.
    weight = possessions_left / (pace * 2.0)
    expected = margin + pre_game_margin * weight + float(possession) * 0.55

    prob = stats.norm.cdf(expected / sd)
    # A finished game is decided.
    return np.where(seconds <= 0, (margin > 0).astype(float) + 0.5 * (margin == 0), prob)


def series_win_probability(game_prob, *, games: int = 7,
                           home_pattern: str = "2-2-1-1-1",
                           home_prob: float | None = None,
                           away_prob: float | None = None) -> float:
    """Probability of winning a best-of-N series.

    With `home_prob` and `away_prob` the home-court pattern is respected,
    which matters: a team that is 60% at home and 45% on the road is not the
    same as one that is 52.5% everywhere.
    """
    needed = games // 2 + 1
    if home_prob is None or away_prob is None:
        p = float(game_prob)
        home_prob = away_prob = p

    pattern = _home_pattern(home_pattern, games)
    memo: dict = {}

    def recurse(idx: int, wins: int, losses: int) -> float:
        if wins >= needed:
            return 1.0
        if losses >= needed:
            return 0.0
        key = (idx, wins, losses)
        if key in memo:
            return memo[key]
        p = home_prob if pattern[idx] else away_prob
        out = p * recurse(idx + 1, wins + 1, losses) + (1 - p) * recurse(idx + 1, wins, losses + 1)
        memo[key] = out
        return out

    return float(recurse(0, 0, 0))


def _home_pattern(pattern: str, games: int) -> list[bool]:
    """Expand '2-2-1-1-1' into a per-game home/away flag list."""
    blocks = [int(x) for x in pattern.split("-")]
    flags: list[bool] = []
    at_home = True
    for block in blocks:
        flags.extend([at_home] * block)
        at_home = not at_home
    while len(flags) < games:
        flags.append(flags[-1] if flags else True)
    return flags[:games]
