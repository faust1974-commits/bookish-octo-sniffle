"""Possession-level Monte Carlo game simulation.

The analytic model in `winprob` gives you a win probability. This gives you a
*distribution*: final scores, margins, and (optionally) player box scores,
with the full shape rather than a mean and a sigma assumed to be normal.

You need that whenever the question is about a tail or a threshold -- player
props, totals, "how often does this team get blown out", the chance a lineup
change swings a specific game.

Rather than simulating individual events, each possession draws from a
categorical points distribution whose scoring frequency is tilted to hit the
lineup's projected offensive rating. That is far faster than event simulation
and reproduces the right mean and the right variance, which is what matters.

Two parameters deserve attention.

`efficiency_shock_sd` handles the fact that real teams have good and bad
nights as a unit -- shooting variance is correlated across teammates within a
game. It inflates each team's score variance but cancels out of the margin,
exactly as shared pace does.

`mean_reversion` handles something less obvious and more important. Points per
possession has a standard deviation near 1.2, so 99 independent possessions
per side would give a margin standard deviation around 18 points. Real NBA
margins vary by about 13.5. The difference is that basketball games are
self-correcting: leading teams slow down and run clock, trailing teams push,
and coaches empty the bench once a game is decided. That feedback pulls the
margin back toward zero and removes roughly a third of its variance. Without
modelling it, a possession-level simulator disagrees with any sensibly
calibrated closed-form model, and both cannot be right.

Because the feedback is sequential, the simulation runs in chunks: possessions
within a chunk are drawn at once, and the running margin adjusts each team's
efficiency for the next chunk.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .. import constants as K

#: Points scored on a possession, and how often, in a league-average setting.
#: The conditional shape is held fixed; only the frequency of scoring moves.
POSSESSION_OUTCOMES = np.array([0, 1, 2, 3, 4], dtype=float)
POSSESSION_BASE_PROBS = np.array([0.470, 0.042, 0.279, 0.187, 0.022])


def _base_mean() -> float:
    return float(np.dot(POSSESSION_OUTCOMES, POSSESSION_BASE_PROBS))


def possession_distribution(target_ppp) -> np.ndarray:
    """Points-per-possession distribution tilted to a target mean.

    Scales how often a possession scores at all, leaving the mix of 2s, 3s and
    free throws alone. That keeps the variance realistic instead of inflating
    it to hit a mean.

    Accepts a scalar or an array of target means; an array returns one row of
    probabilities per entry.
    """
    target = np.atleast_1d(np.asarray(target_ppp, dtype=float))
    base_score_prob = 1.0 - POSSESSION_BASE_PROBS[0]
    conditional_mean = _base_mean() / base_score_prob
    needed = np.clip(target / conditional_mean, 0.05, 0.95)

    probs = np.tile(POSSESSION_BASE_PROBS, (len(target), 1))
    probs[:, 1:] *= (needed / base_score_prob)[:, None]
    probs[:, 0] = 1.0 - probs[:, 1:].sum(axis=1)
    return probs[0] if np.ndim(target_ppp) == 0 else probs


@dataclass
class GameSimResult:
    """Outcome distribution of a simulated matchup."""

    home_scores: np.ndarray
    away_scores: np.ndarray
    home_team: str = "home"
    away_team: str = "away"
    n_sims: int = 0
    player_box: pd.DataFrame | None = None

    @property
    def margins(self) -> np.ndarray:
        return self.home_scores - self.away_scores

    @property
    def home_win_prob(self) -> float:
        margins = self.margins
        return float((margins > 0).mean() + 0.5 * (margins == 0).mean())

    @property
    def totals(self) -> np.ndarray:
        return self.home_scores + self.away_scores

    def summary(self) -> dict:
        m = self.margins
        return {
            "home_team": self.home_team,
            "away_team": self.away_team,
            "n_sims": self.n_sims,
            "home_win_prob": self.home_win_prob,
            "mean_home_score": float(self.home_scores.mean()),
            "mean_away_score": float(self.away_scores.mean()),
            "mean_margin": float(m.mean()),
            "margin_sd": float(m.std()),
            "median_total": float(np.median(self.totals)),
            "total_sd": float(self.totals.std()),
            "spread": -float(np.median(m)),
            "home_cover_own_median": 0.5,
        }

    def quantiles(self, qs=(0.05, 0.25, 0.5, 0.75, 0.95)) -> pd.DataFrame:
        def label(q: float) -> str:
            pct = q * 100
            return "median" if abs(q - 0.5) < 1e-9 else f"{pct:g}th pct"

        return pd.DataFrame({
            "quantile": [label(q) for q in qs],
            "home_score": np.quantile(self.home_scores, qs),
            "away_score": np.quantile(self.away_scores, qs),
            "margin": np.quantile(self.margins, qs),
            "total": np.quantile(self.totals, qs),
        })

    def prob_margin_over(self, threshold: float) -> float:
        return float((self.margins > threshold).mean())

    def prob_total_over(self, threshold: float) -> float:
        return float((self.totals > threshold).mean())


def simulate_game(home_off_rating: float, home_def_rating: float,
                  away_off_rating: float, away_def_rating: float,
                  *, n_sims: int = 10_000,
                  pace: float = K.LEAGUE_DEFAULTS["pace"],
                  pace_sd: float = 3.5,
                  league_rating: float = K.LEAGUE_DEFAULTS["off_rating"],
                  home_advantage: float = K.DEFAULT_HOME_ADVANTAGE,
                  efficiency_shock_sd: float = 2.5,
                  mean_reversion: float = K.GAME_MEAN_REVERSION,
                  chunks: int = 8,
                  home_team: str = "home", away_team: str = "away",
                  seed: int | None = None) -> GameSimResult:
    """Simulate a matchup possession by possession, many times.

    Ratings are points per 100 possessions. The two teams' offensive ratings
    are combined with the opposing defences through the standard relation:
    expected efficiency is the offence plus the defence minus the league mean.
    """
    rng = np.random.default_rng(seed)

    home_ppp = (home_off_rating + away_def_rating - league_rating) / 100.0
    away_ppp = (away_off_rating + home_def_rating - league_rating) / 100.0
    home_ppp += home_advantage / 2.0 / 100.0
    away_ppp -= home_advantage / 2.0 / 100.0

    # Pace is shared by both teams within a game, which is what correlates
    # their scores; it cancels out of the margin, as it should.
    possessions = np.maximum(
        60, np.round(rng.normal(pace, pace_sd, size=n_sims))
    ).astype(int)

    home_shock = rng.normal(0.0, efficiency_shock_sd, size=n_sims) / 100.0
    away_shock = rng.normal(0.0, efficiency_shock_sd, size=n_sims) / 100.0

    max_poss = int(possessions.max())
    chunk_edges = np.linspace(0, 1.0, chunks + 1)

    home_scores = np.zeros(n_sims)
    away_scores = np.zeros(n_sims)
    drawn = np.zeros(n_sims, dtype=int)

    for c in range(chunks):
        start = np.floor(possessions * chunk_edges[c]).astype(int)
        end = np.floor(possessions * chunk_edges[c + 1]).astype(int)
        length = np.maximum(0, end - start)
        if length.max() == 0:
            continue
        width = int(length.max())
        live = np.arange(width)[None, :] < length[:, None]

        # Self-correction: whoever is ahead eases off, whoever is behind
        # pushes. Scaled by how much of the game is left, since a lead late is
        # protected harder than a lead early.
        #
        # Critically, this corrects the deviation from the margin the two
        # teams' ratings *predict*, not the raw score. Pulling the raw margin
        # toward zero would compress real differences in team strength and the
        # simulator would stop agreeing with its own ratings.
        expected_margin = (home_ppp - away_ppp) * drawn
        deviation = (home_scores - away_scores) - expected_margin
        remaining = 1.0 - chunk_edges[c]
        adjust = mean_reversion * deviation / 100.0 * remaining

        for scores, ppp, shock, sign in ((home_scores, home_ppp, home_shock, -1.0),
                                         (away_scores, away_ppp, away_shock, 1.0)):
            means = np.clip(ppp + shock + sign * adjust, 0.55, 1.75)
            cdf = np.cumsum(possession_distribution(means), axis=1)
            draws = rng.random((n_sims, width))
            # Inverse-CDF sampling: count how many cut points each draw exceeds.
            outcome = (draws[:, :, None] >= cdf[:, None, :]).sum(axis=2)
            points = POSSESSION_OUTCOMES[np.clip(outcome, 0, len(POSSESSION_OUTCOMES) - 1)]
            scores += np.where(live, points, 0.0).sum(axis=1)
        drawn += length

    return GameSimResult(home_scores=home_scores, away_scores=away_scores,
                         home_team=home_team, away_team=away_team, n_sims=n_sims)


def simulate_matchup(model, home_lineup, away_lineup, **kwargs) -> GameSimResult:
    """Simulate a game between two specific five-man units.

    Handy for "what does this lineup change do to our chances tonight" --
    evaluate both lineups with the lineup model, then simulate.
    """
    home_eval = model.evaluate(list(home_lineup), detail=False)
    away_eval = model.evaluate(list(away_lineup), detail=False)
    return simulate_game(
        home_eval.off_rating, home_eval.def_rating,
        away_eval.off_rating, away_eval.def_rating,
        league_rating=model.league_off_rating, **kwargs,
    )


def simulate_from_ratings(home_net: float, away_net: float,
                          *, league_rating: float = K.LEAGUE_DEFAULTS["off_rating"],
                          **kwargs) -> GameSimResult:
    """Simulate from net ratings alone, splitting them evenly across ends."""
    return simulate_game(
        league_rating + home_net / 2.0, league_rating - home_net / 2.0,
        league_rating + away_net / 2.0, league_rating - away_net / 2.0,
        league_rating=league_rating, **kwargs,
    )
