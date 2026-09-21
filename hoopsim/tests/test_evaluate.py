"""Scoring a rating model against a later season.

The metric this module replaces -- held-out error on individual stints --
could not tell any two models apart on real data, because a stint is mostly
noise. These tests pin the replacement: that it rewards a model which knows
something, that it is not fooled by scale, and that it says out loud how
much of the league it had never seen.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from hoopsim.impact.evaluate import score_against_season


def _league(quality, seed=3, per_team=10):
    """A league where team strength really is the sum of its players."""
    rng = np.random.default_rng(seed)
    ratings, players, teams = [], [], []
    for i, q in enumerate(quality):
        tid = f"t{i}"
        for j in range(per_team):
            pid = f"p{i}_{j}"
            ratings.append({"player_id": pid, "rapm_off": q / 2 + rng.normal(0, .05),
                            "rapm_def": q / 2 + rng.normal(0, .05)})
            players.append({"player_id": pid, "team_id": tid,
                            "min": 1800.0, "games": 75})
        teams.append({"team_id": tid, "net_rating": 5.0 * q})
    return (pd.DataFrame(ratings), pd.DataFrame(players), pd.DataFrame(teams))


def test_a_model_that_knows_the_league_scores_well():
    ratings, players, teams = _league([1.5, 0.8, 0.0, -0.7, -1.4, 0.3])
    out = score_against_season(ratings, players, teams)
    assert out["r_squared"] > 0.95
    assert out["n_teams"] == 6
    assert out["minute_coverage"] == pytest.approx(1.0)


def test_a_model_that_knows_nothing_scores_badly():
    ratings, players, teams = _league([1.5, 0.8, 0.0, -0.7, -1.4, 0.3])
    rng = np.random.default_rng(0)
    ratings["rapm_off"] = rng.normal(0, 1, len(ratings))
    ratings["rapm_def"] = rng.normal(0, 1, len(ratings))
    assert score_against_season(ratings, players, teams)["r_squared"] < 0.6


def test_scale_does_not_matter_only_ordering():
    # Roster strength is calibrated downstream, so a model that is right
    # about the ranking but wrong about the units must not be penalised.
    ratings, players, teams = _league([1.2, 0.5, -0.3, -1.1, 0.9, -0.6])
    base = score_against_season(ratings, players, teams)
    scaled = ratings.copy()
    scaled[["rapm_off", "rapm_def"]] *= 17.0
    out = score_against_season(scaled, players, teams)
    assert out["r_squared"] == pytest.approx(base["r_squared"], abs=1e-9)
    assert out["slope"] != pytest.approx(base["slope"])


def test_unknown_players_are_average_and_counted():
    ratings, players, teams = _league([1.0, 0.4, -0.4, -1.0])
    # Half the league is a stranger to this model; it must say so rather
    # than quietly scoring as if it knew everyone.
    seen = ratings.iloc[: len(ratings) // 2]
    out = score_against_season(seen, players, teams)
    assert 0.4 < out["minute_coverage"] < 0.6
    assert np.isfinite(out["r_squared"])


def test_it_refuses_to_score_on_too_little():
    ratings, players, teams = _league([1.0, -1.0])
    with pytest.raises(ValueError, match="at least three teams"):
        score_against_season(ratings, players, teams)
    with pytest.raises(ValueError, match="no players"):
        score_against_season(ratings, players.iloc[:0], teams)
