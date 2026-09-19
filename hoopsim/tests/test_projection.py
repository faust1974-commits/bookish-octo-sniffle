"""Aging, regression to the mean, projection and rotation allocation."""

import numpy as np
import pytest

from hoopsim import constants as K
from hoopsim import projection as P


# ------------------------------------------------------------------ aging

@pytest.mark.parametrize("skill", list(K.AGING_PEAKS))
def test_every_aging_curve_peaks_at_its_peak_age(skill):
    peak = K.AGING_PEAKS[skill]
    assert P.aging_multiplier(peak, skill) == pytest.approx(1.0, abs=1e-9)
    assert P.aging_multiplier(peak - 4, skill) < 1.0
    assert P.aging_multiplier(peak + 4, skill) < 1.0


def test_shooting_ages_far_better_than_athleticism():
    """The single most important thing an aging curve must get right."""
    assert P.aging_multiplier(36, "three_point") > P.aging_multiplier(36, "steals") + 0.2
    assert P.aging_multiplier(36, "free_throw") > 0.90
    assert P.aging_multiplier(36, "scoring_volume") < 0.85


def test_rate_stats_are_not_given_a_volume_shaped_curve():
    """A 21-year-old does not shoot 60% of his eventual three point percentage."""
    assert P.aging_multiplier(21, "three_point") > 0.85
    assert P.aging_multiplier(21, "scoring_volume") < 0.80


def test_growth_is_the_steeper_side_and_the_cliff_comes_later():
    """A 22-year-old is far from his peak; a 32-year-old is still near his."""
    peak = K.AGING_PEAKS["scoring_volume"]
    assert P.aging_multiplier(peak - 5, "scoring_volume") < P.aging_multiplier(peak + 5, "scoring_volume")
    # Past the cliff age, each additional year costs more than the last.
    drop_early = (P.aging_multiplier(30, "scoring_volume")
                  - P.aging_multiplier(32, "scoring_volume"))
    drop_late = (P.aging_multiplier(36, "scoring_volume")
                 - P.aging_multiplier(38, "scoring_volume"))
    assert drop_late > drop_early


def test_aging_multipliers_stay_in_range():
    ages = np.arange(18, 45)
    for skill in K.AGING_PEAKS:
        mult = P.aging_multiplier(ages, skill)
        assert (mult > 0).all() and (mult <= 1.0).all(), skill


def test_aging_delta_composes():
    a = P.aging_delta(24, 27, "playmaking")
    b = P.aging_delta(27, 30, "playmaking")
    c = P.aging_delta(24, 30, "playmaking")
    assert float(a) * float(b) == pytest.approx(float(c))


# -------------------------------------------------------------- regression

def test_shrinkage_weights_by_sample_size():
    prior, observed = 0.365, 0.500
    small = P.shrink(observed, 50, prior, 750)
    large = P.shrink(observed, 3000, prior, 750)
    assert abs(small - prior) < abs(large - prior)
    assert prior < small < large < observed


def test_stabilization_points_are_ordered_as_the_literature_says():
    """Free throws settle fastest, three-pointers slowest."""
    assert P.stabilization_point("ft_pct") < P.stabilization_point("fg2_pct")
    assert P.stabilization_point("fg2_pct") < P.stabilization_point("fg3_pct")


def test_a_hot_three_point_season_on_few_attempts_barely_moves():
    projected = P.shrink(0.42, 120, 0.365, P.stabilization_point("fg3_pct"))
    assert 0.365 < projected < 0.385


def test_reliability_runs_from_zero_to_one():
    assert P.reliability(0, "fg3_pct") == pytest.approx(0.0)
    assert P.reliability(750, "fg3_pct") == pytest.approx(0.5)
    assert P.reliability(10 ** 7, "fg3_pct") > 0.99


def test_weighted_history_favours_recent_seasons():
    assert P.weighted_history([10.0, 20.0]) > 15.0
    assert P.weighted_history([20.0, 10.0]) < 15.0
    assert P.weighted_history([12.0, 12.0, 12.0]) == pytest.approx(12.0)


# -------------------------------------------------------------- projection

def test_projection_covers_every_player_and_regresses_the_spread(analysis):
    proj = analysis.projections
    assert len(proj) > 0
    assert proj["impact"].notna().all()
    observed = analysis.players[analysis.players["min"] >= 400]["box_impact"].std()
    assert proj["impact"].std() < observed, "projections must be tighter than observations"


def test_projection_carries_uncertainty(analysis):
    proj = analysis.projections
    assert (proj["impact_sd"] > 0).all()
    # Players with more history should be projected more confidently.
    heavy = proj[proj["history_minutes"] > proj["history_minutes"].median()]["impact_sd"].mean()
    light = proj[proj["history_minutes"] <= proj["history_minutes"].median()]["impact_sd"].mean()
    assert heavy < light


def test_projected_games_respect_the_actual_season_length(analysis):
    """Inferred from the data, never assumed to be 82."""
    proj = analysis.projections
    season_length = int(proj["season_length"].iloc[0])
    assert season_length == 20
    assert proj["projected_games"].max() <= season_length
    assert proj["projected_games"].min() > 0


def test_older_players_are_projected_to_miss_more_time(analysis):
    proj = analysis.projections
    old = proj[proj["age"] >= 33]["projected_games"].mean()
    prime = proj[(proj["age"] >= 24) & (proj["age"] <= 28)]["projected_games"].mean()
    if np.isfinite(old):
        assert old <= prime


# ---------------------------------------------------------------- rotation

def test_allocated_minutes_total_exactly_240():
    values = {f"P{i}": 5.0 - i * 0.5 for i in range(12)}
    minutes = P.allocate_minutes(values)
    assert minutes.sum() == pytest.approx(K.TEAM_MINUTES_PER_GAME)


def test_no_player_exceeds_the_minutes_cap():
    values = {f"P{i}": 10.0 - i for i in range(9)}
    cons = P.RotationConstraints(max_minutes_per_player=32.0)
    minutes = P.allocate_minutes(values, cons)
    assert minutes.max() <= 32.0 + 1e-6
    assert minutes.sum() == pytest.approx(240.0)


def test_better_players_get_more_minutes():
    values = {"star": 6.0, "good": 3.0, "ok": 1.0, "meh": 0.0,
              "bad": -1.0, "worse": -2.0, "deep": -3.0, "deeper": -4.0}
    minutes = P.allocate_minutes(values, P.RotationConstraints(concentration=0.7))
    # Minutes must never increase as quality falls.
    ordered = [minutes[p] for p in sorted(values, key=values.get, reverse=True)]
    assert all(a >= b - 1e-9 for a, b in zip(ordered, ordered[1:])), ordered
    assert minutes["star"] > minutes["deeper"]


def test_impossible_minute_constraints_are_reported_not_fudged():
    """Six players capped at 38 cannot cover 240 minutes. Say so."""
    values = {f"P{i}": 1.0 for i in range(6)}
    with pytest.raises(ValueError, match="can cover only"):
        P.allocate_minutes(values, P.RotationConstraints(max_minutes_per_player=38.0))


def test_allocation_never_breaches_the_cap():
    values = {f"P{i}": 8.0 - i for i in range(10)}
    for cap in (28.0, 32.0, 36.0, 40.0):
        minutes = P.allocate_minutes(values, P.RotationConstraints(
            max_minutes_per_player=cap, max_players=10))
        assert minutes.max() <= cap + 1e-6, cap
        assert minutes.sum() == pytest.approx(240.0)


def test_concentration_controls_how_top_heavy_the_rotation_is():
    values = {f"P{i}": 6.0 - i for i in range(8)}
    flat = P.allocate_minutes(values, P.RotationConstraints(concentration=0.0))
    steep = P.allocate_minutes(values, P.RotationConstraints(concentration=1.0))
    assert steep.max() > flat.max()
    assert steep.std() > flat.std()


def test_rotation_plan_fields_five_every_segment(analysis):
    model = analysis.lineup_model
    team = analysis.league.teams["team_id"].iloc[0]
    pool = analysis.roster_profiles(team, top=9)
    minutes = P.allocate_minutes({p: model.profiles[p].total_impact for p in pool})
    plan = P.build_rotation_plan(minutes, model, segments=12)
    assert len(plan) == 12
    for lineup in plan["lineup"]:
        assert len(set(lineup)) == K.PLAYERS_ON_FLOOR
    assert plan["minutes"].sum() == pytest.approx(K.MINUTES_PER_GAME)


def test_optimising_a_rotation_does_not_make_it_worse(analysis):
    model = analysis.lineup_model
    team = analysis.league.teams["team_id"].iloc[0]
    pool = analysis.roster_profiles(team, top=9)
    cons = P.RotationConstraints(max_minutes_per_player=36.0, max_players=9)
    baseline = P.allocate_minutes({p: model.profiles[p].total_impact for p in pool}, cons)
    base_score = P.evaluate_rotation(
        P.build_rotation_plan(baseline, model, segments=10, seed=3), model)["net_rating"]
    result = P.optimize_rotation(model, pool, cons, segments=10, iterations=25, seed=3)
    assert result["net_rating"] >= base_score - 1e-9
    assert result["minutes"].sum() == pytest.approx(240.0)


def test_rotation_needs_five_players(analysis):
    with pytest.raises(ValueError, match="at least 5"):
        P.optimize_rotation(analysis.lineup_model, ["nobody"], iterations=1)
