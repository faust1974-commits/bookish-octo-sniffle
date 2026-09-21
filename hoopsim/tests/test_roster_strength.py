"""Team strength rebuilt from whoever is on the roster.

The point of this module is that a team's record stops describing it the
moment the roster changes. These tests pin the arithmetic that makes the
replacement honest: minutes that add to a full game, impact weighted by
share of the floor, and a calibration that is fitted rather than guessed.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from hoopsim import constants as K
from hoopsim.impact.roster_strength import (
    MAX_MINUTES_PER_GAME, TEAM_MINUTES, calibrate, project_minutes,
    raw_strength, team_strength,
)


def _roster(rows):
    return pd.DataFrame(rows, columns=["off_impact", "def_impact", "min", "games"])


def test_minutes_always_add_up_to_a_whole_game():
    for mpg in ([38, 36, 34, 30, 28, 22, 18, 14, 10, 6],
                [40] * 5, [40] * 6, [40] * 7, [30], [20] * 15):
        out = project_minutes(np.array(mpg, dtype=float))
        assert out.sum() == pytest.approx(TEAM_MINUTES), mpg


def test_the_cap_binds_when_the_roster_is_deep_enough_to_honour_it():
    out = project_minutes(np.array([48, 48, 48, 30, 20, 20, 20, 20, 20], dtype=float))
    assert out.max() == pytest.approx(MAX_MINUTES_PER_GAME)
    assert out.sum() == pytest.approx(TEAM_MINUTES)


def test_the_cap_is_dropped_when_it_cannot_be_met():
    # Six players at 36 is 216 minutes of a 240-minute game. Honouring the
    # cap would field four and a half men and read as a terrible team rather
    # than a short one.
    out = project_minutes(np.array([40] * 6, dtype=float))
    assert out.sum() == pytest.approx(TEAM_MINUTES)
    assert out.max() > MAX_MINUTES_PER_GAME


def test_minutes_keep_their_ordering():
    out = project_minutes(np.array([10, 30, 20], dtype=float))
    assert out[1] > out[2] > out[0]


def test_a_roster_of_nobody_is_zero_not_a_crash():
    assert project_minutes(np.array([0.0, 0.0])).sum() == 0.0
    assert project_minutes(np.array([np.nan, -5.0])).sum() == 0.0
    assert raw_strength(_roster([])) == (0.0, 0.0)


def test_average_players_make_an_average_team():
    # Impact is measured against an average player, so a roster of them has
    # to come out at zero -- any other answer is a baseline error.
    roster = _roster([[0.0, 0.0, 2000.0, 80]] * 10)
    off, dfn = raw_strength(roster)
    assert off == pytest.approx(0.0)
    assert dfn == pytest.approx(0.0)


def test_five_identical_players_contribute_their_whole_impact():
    # Five players splitting every minute equally: the team is exactly what
    # one of them is, five times over on the floor at once.
    roster = _roster([[2.0, 1.0, 2000.0, 80]] * 5)
    off, dfn = raw_strength(roster)
    assert off == pytest.approx(2.0 * K.PLAYERS_ON_FLOOR)
    assert dfn == pytest.approx(1.0 * K.PLAYERS_ON_FLOOR)


def test_a_star_who_plays_more_counts_for_more():
    star_heavy = _roster([[6.0, 2.0, 2900.0, 80]] + [[-1.0, 0.0, 1200.0, 80]] * 9)
    star_light = _roster([[6.0, 2.0, 600.0, 80]] + [[-1.0, 0.0, 1200.0, 80]] * 9)
    assert raw_strength(star_heavy)[0] > raw_strength(star_light)[0]


def test_bringing_in_a_better_player_cannot_make_a_team_worse():
    base = [[1.0, 0.5, 2000.0, 80]] * 8
    worse = _roster(base + [[-3.0, -2.0, 2000.0, 80]])
    better = _roster(base + [[+4.0, +3.0, 2000.0, 80]])
    assert raw_strength(better)[0] > raw_strength(worse)[0]
    assert raw_strength(better)[1] > raw_strength(worse)[1]


def test_calibration_is_a_fit_not_a_guess():
    rng = np.random.default_rng(7)
    players, ratings = [], []
    for t in range(12):
        quality = rng.normal(0, 1.2)
        for _ in range(10):
            players.append({"team_id": f"t{t}",
                            "off_impact": quality + rng.normal(0, 0.4),
                            "def_impact": quality * 0.5 + rng.normal(0, 0.4),
                            "min": 1800.0, "games": 75})
        ratings.append({"team_id": f"t{t}", "net_rating": 7.5 * quality + 1.0})
    cal = calibrate(pd.DataFrame(players), pd.DataFrame(ratings))

    assert cal["n_teams"] == 12
    assert cal["r_squared"] > 0.8          # a real relationship, recovered
    assert cal["residual_sd"] >= 0.0
    assert np.isfinite(cal["slope"]) and np.isfinite(cal["intercept"])


def test_calibration_needs_a_league():
    with pytest.raises(ValueError, match="at least three teams"):
        calibrate(pd.DataFrame([{"team_id": "a", "off_impact": 1.0,
                                 "def_impact": 1.0, "min": 100.0, "games": 10}]),
                  pd.DataFrame([{"team_id": "a", "net_rating": 1.0}]))


def test_offence_and_defence_sum_to_the_net():
    # Whatever the calibration does to the halves, they must still add to the
    # whole, or the interface shows three numbers that contradict each other.
    cal = {"slope": 0.6, "intercept": -1.4, "r_squared": 0.8, "residual_sd": 2.0,
           "n_teams": 30}
    roster = _roster([[3.0, 1.0, 2400.0, 80]] * 5 + [[-1.0, -0.5, 900.0, 70]] * 5)
    s = team_strength(roster, cal)
    assert s["off"] + s["def"] == pytest.approx(s["net"])


def test_calibration_scales_the_answer():
    cal_flat = {"slope": 0.0, "intercept": 0.0, "r_squared": 0.0,
                "residual_sd": 0.0, "n_teams": 30}
    roster = _roster([[5.0, 3.0, 2400.0, 80]] * 8)
    assert team_strength(roster, cal_flat)["net"] == pytest.approx(0.0)


# -- hand-set rotations -----------------------------------------------------

def test_a_hand_set_rotation_overrides_last_season():
    roster = _roster([[4.0, 2.0, 2400.0, 80], [0.0, 0.0, 2400.0, 80]])
    # Last season says they split the minutes; the caller says otherwise.
    heavy_star = raw_strength(roster, np.array([200.0, 40.0]), (0.0, 0.0))
    heavy_scrub = raw_strength(roster, np.array([40.0, 200.0]), (0.0, 0.0))
    assert heavy_star[0] > heavy_scrub[0]


def test_unassigned_minutes_go_to_a_replacement_player():
    # Benching the best player must actually cost something. Spreading his
    # minutes over the rest of the starters would make it nearly free.
    roster = _roster([[6.0, 3.0, 2400.0, 80]] + [[1.0, 0.5, 2000.0, 80]] * 4)
    full = raw_strength(roster, np.array([48.0, 48.0, 48.0, 48.0, 48.0]),
                        (-0.4, -0.3))
    benched = raw_strength(roster, np.array([0.0, 48.0, 48.0, 48.0, 48.0]),
                           (-0.4, -0.3))
    assert benched[0] < full[0]
    assert benched[1] < full[1]
    # And the drop is real, not a rounding artefact.
    assert full[0] - benched[0] > 1.0


def test_over_assigned_minutes_are_scaled_back_not_counted_twice():
    roster = _roster([[3.0, 1.0, 2000.0, 80]] * 5)
    exact = raw_strength(roster, np.array([48.0] * 5), (-0.4, -0.3))
    doubled = raw_strength(roster, np.array([96.0] * 5), (-0.4, -0.3))
    # Doubling everyone's minutes describes the same team, not one twice as good.
    assert doubled[0] == pytest.approx(exact[0], abs=1e-9)


def test_replacement_only_fills_what_is_missing():
    roster = _roster([[2.0, 1.0, 2000.0, 80]] * 5)
    none_missing = raw_strength(roster, np.array([48.0] * 5), (-5.0, -5.0))
    half_missing = raw_strength(roster, np.array([24.0] * 5), (-5.0, -5.0))
    # With nobody missing the replacement level cannot matter at all.
    assert none_missing == pytest.approx(raw_strength(
        roster, np.array([48.0] * 5), (0.0, 0.0)))
    assert half_missing[0] < none_missing[0]
