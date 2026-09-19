"""Impact models: RAPM, on/off, usage redistribution, lineup evaluation."""

import numpy as np
import pytest

from hoopsim import constants as K
from hoopsim import impact as I
from hoopsim.impact.lineup import LineupModel, PlayerProfile
from hoopsim.impact.usage import UsageProfile, redistribute_usage, ts_delta


# ----------------------------------------------------------------- usage

def test_usage_shares_always_total_one_possession():
    """Five players on the floor end exactly one possession between them."""
    for base in ([0.32, 0.22, 0.18, 0.16, 0.12], [0.10, 0.10, 0.10, 0.10, 0.10],
                 [0.40, 0.35, 0.30, 0.25, 0.20], [0.20] * 5):
        profiles = [UsageProfile(f"P{i}", u, 0.56) for i, u in enumerate(base)]
        out = redistribute_usage(profiles)
        assert out["adjusted_usage"].sum() == pytest.approx(1.0, abs=1e-6), base


def test_absorbing_usage_costs_efficiency_and_shedding_gains_it():
    assert ts_delta(0.20, 0.28) < 0, "taking on usage must cost efficiency"
    assert ts_delta(0.28, 0.20) > 0, "shedding usage must gain efficiency"
    assert ts_delta(0.20, 0.20) == pytest.approx(0.0)


def test_the_usage_curve_is_asymmetric():
    """Players lose more from absorbing usage than they gain from shedding it."""
    cost = abs(ts_delta(0.20, 0.28))
    gain = abs(ts_delta(0.20, 0.12))
    assert cost > gain


def test_higher_usage_players_absorb_more_of_the_slack():
    profiles = [UsageProfile("big", 0.28, 0.58), UsageProfile("mid", 0.18, 0.56),
                UsageProfile("low", 0.10, 0.54), UsageProfile("low2", 0.10, 0.54),
                UsageProfile("low3", 0.10, 0.54)]
    out = redistribute_usage(profiles).set_index("player_id")
    assert out.loc["big", "usage_change"] > out.loc["mid", "usage_change"]
    assert out.loc["mid", "usage_change"] > out.loc["low", "usage_change"]


def test_removing_a_high_usage_player_costs_the_others_real_efficiency():
    """The error a naive per-36 extrapolation makes, quantified."""
    others = [UsageProfile("A", 0.22, 0.575), UsageProfile("B", 0.18, 0.560),
              UsageProfile("C", 0.16, 0.545), UsageProfile("D", 0.12, 0.590)]
    with_star = redistribute_usage([UsageProfile("STAR", 0.32, 0.610)] + others)
    without = redistribute_usage(others + [UsageProfile("BENCH", 0.14, 0.545)])

    before = with_star.set_index("player_id").loc[list("ABCD"), "pts_per_100_effect"].sum()
    after = without.set_index("player_id").loc[list("ABCD"), "pts_per_100_effect"].sum()
    assert after - before < -2.0, "absorbing a star's load must cost at least two points"
    for pid in "ABCD":
        assert without.set_index("player_id").loc[pid, "usage_change"] > 0


def test_usage_stays_within_plausible_bounds():
    profiles = [UsageProfile(f"P{i}", 0.05, 0.56) for i in range(5)]
    out = redistribute_usage(profiles)
    assert out["adjusted_usage"].between(0.0, 0.45).all()


# ------------------------------------------------------------------ RAPM

def test_rapm_recovers_ground_truth(big_league):
    """The point of RAPM: does it find the players who actually helped?"""
    fit = I.fit_rapm(big_league.stints, alpha=2000.0)
    truth = big_league.source.ground_truth().set_index("player_id")
    merged = fit.ratings.join(truth[["true_total_impact"]], on="player_id").dropna()
    merged = merged[merged["possessions"] >= 500]
    r = np.corrcoef(merged["rapm"], merged["true_total_impact"])[0, 1]
    assert r > 0.4, f"RAPM correlated only {r:.3f} with the truth"


def test_rapm_recovers_home_court_advantage(big_league):
    """An independent check: the solver should find a parameter it was never told."""
    fit = I.fit_rapm(big_league.stints, alpha=2000.0)
    assert 0.5 < fit.home_advantage < 5.0, fit.home_advantage


def test_ridge_shrinks_the_spread(big_league):
    """More regularisation must produce a tighter distribution, always."""
    loose = I.fit_rapm(big_league.stints, alpha=200.0).ratings["rapm"].std()
    tight = I.fit_rapm(big_league.stints, alpha=20000.0).ratings["rapm"].std()
    assert tight < loose


def test_rapm_splits_offence_and_defence(big_league):
    fit = I.fit_rapm(big_league.stints, alpha=2000.0)
    assert np.allclose(fit.ratings["rapm"],
                       fit.ratings["rapm_off"] + fit.ratings["rapm_def"])


def test_alpha_cross_validation_ranks_candidates(league):
    cv = I.cross_validate_alpha(league.stints, alphas=(500.0, 4000.0), folds=3)
    assert len(cv) == 2
    assert cv["weighted_mse"].is_monotonic_increasing
    assert cv["weighted_mse"].notna().all()


def test_fitting_the_box_model_beats_the_default_prior(big_league):
    """The built-in coefficients are a prior; fitting them should improve things."""
    from hoopsim.context import Analysis
    from hoopsim.metrics.box import add_box_impact

    a = Analysis(league=big_league)
    truth = big_league.source.ground_truth().set_index("player_id")["true_total_impact"]
    coefs = I.fit_box_impact(a.players, a.rapm.ratings, target_column="rapm")
    assert 0.0 < coefs["_r_squared"] <= 1.0

    clean = {k: v for k, v in coefs.items() if not k.startswith("_")}
    refit = add_box_impact(a.players, clean, column="fitted")
    q = refit[refit["min"] >= 400].join(truth, on="player_id").dropna(
        subset=["true_total_impact"])
    before = np.corrcoef(q["box_impact"], q["true_total_impact"])[0, 1]
    after = np.corrcoef(q["fitted"], q["true_total_impact"])[0, 1]
    assert after > before


def test_rapm_needs_stints(league):
    empty = league.stints.iloc[0:0]
    with pytest.raises(ValueError, match="no usable stints"):
        I.fit_rapm(empty)


# ----------------------------------------------------------------- on/off

def test_on_off_covers_every_rotation_player(league):
    table = I.on_off(league.stints)
    assert len(table) > 0
    assert table["on_poss"].min() > 0
    assert np.isfinite(table["on_off_net"]).all()


def test_lineup_ratings_report_their_own_uncertainty(league):
    units = I.lineup_ratings(league.stints, min_possessions=20)
    assert len(units) > 0
    assert (units["net_rating_se"] > 0).all()
    # Standard error must fall as the sample grows.
    small = units[units["poss"] < units["poss"].median()]["net_rating_se"].mean()
    large = units[units["poss"] >= units["poss"].median()]["net_rating_se"].mean()
    assert large < small


def test_pair_on_off_returns_the_shared_states(league):
    roster = league.roster(league.teams["team_id"].iloc[0])
    a, b = roster["player_id"].iloc[0], roster["player_id"].iloc[1]
    table = I.pair_on_off(league.stints, a, b)
    assert set(table["state"]) <= {"both_on", "a_only", "b_only"}
    assert (table["poss"] > 0).all()


# --------------------------------------------------------------- lineups

def _profile(pid, **kw):
    base = dict(player_id=pid, name=pid, position="SG", off_impact=2.0, def_impact=1.0,
                usage=0.20, ts_pct=0.57, spacing=0.0, rim_pressure=0.0,
                playmaking=0.0, rebounding=0.0, rim_protection=0.0)
    base.update(kw)
    return PlayerProfile(**base)


def test_lineup_rating_decomposes_into_its_parts():
    profiles = {f"P{i}": _profile(f"P{i}", position=p)
                for i, p in enumerate(K.POSITIONS)}
    model = LineupModel(profiles, league_off_rating=114.5)
    ev = model.evaluate(list(profiles))
    rebuilt = (model.league_off_rating + ev.additive_off + ev.usage_effect
               + ev.fit_bonus - ev.coverage_penalty)
    assert ev.off_rating == pytest.approx(rebuilt)
    assert ev.net_rating == pytest.approx(ev.off_rating - ev.def_rating)


def test_a_lineup_is_exactly_five_distinct_players():
    profiles = {f"P{i}": _profile(f"P{i}") for i in range(6)}
    model = LineupModel(profiles)
    with pytest.raises(ValueError, match="a lineup is 5 players"):
        model.evaluate(["P0", "P1", "P2"])
    with pytest.raises(ValueError, match="same player twice"):
        model.evaluate(["P0", "P0", "P1", "P2", "P3"])
    with pytest.raises(KeyError):
        model.evaluate(["P0", "P1", "P2", "P3", "NOBODY"])


def test_fit_separates_lineups_with_identical_talent():
    """Five identical players must grade below five complementary ones."""
    balanced = {f"P{i}": _profile(f"P{i}", position=p, spacing=s, playmaking=pm,
                                  rim_protection=rp, rebounding=rb)
                for i, (p, s, pm, rp, rb) in enumerate(
                    [("PG", 0.5, 1.5, -0.8, -0.6), ("SG", 1.2, 0.3, -0.7, -0.5),
                     ("SF", 0.8, 0.4, 0.0, 0.2), ("PF", 0.2, -0.4, 0.9, 1.0),
                     ("C", -0.6, -0.9, 1.8, 1.4)])}
    clones = {f"Q{i}": _profile(f"Q{i}", spacing=-0.9, playmaking=-0.8,
                                rim_protection=-1.4, rebounding=-1.2) for i in range(5)}
    good = LineupModel(balanced).evaluate(list(balanced))
    bad = LineupModel(clones).evaluate(list(clones))
    assert good.additive_off == pytest.approx(bad.additive_off)
    assert good.net_rating - bad.net_rating > 5.0
    assert bad.coverage_penalty > 0


def test_position_viability_uses_matching_not_counting():
    five_guards = {f"Q{i}": _profile(f"Q{i}", position="SG") for i in range(5)}
    assert not LineupModel(five_guards).positions_viable(list(five_guards))

    legal = {f"P{i}": _profile(f"P{i}", position=p)
             for i, p in enumerate(K.POSITIONS)}
    assert LineupModel(legal).positions_viable(list(legal))

    # Three versatile wings plus a guard and a centre can still cover five spots.
    flexible = {"a": _profile("a", position="PG"), "b": _profile("b", position="SG"),
                "c": _profile("c", position="SF"), "d": _profile("d", position="SF"),
                "e": _profile("e", position="C")}
    assert LineupModel(flexible).positions_viable(list(flexible))


def test_swapping_a_player_in_and_back_out_is_a_round_trip(analysis):
    model = analysis.lineup_model
    team = analysis.league.teams["team_id"].iloc[0]
    pool = analysis.roster_profiles(team, top=8)
    five, sixth = pool[:5], pool[5]
    first = model.swap(five, five[0], sixth)
    back = model.swap(first.after.players, sixth, five[0])
    assert back.after.net_rating == pytest.approx(first.before.net_rating, abs=1e-6)


def test_best_replacement_returns_no_duplicates(analysis):
    model = analysis.lineup_model
    team = analysis.league.teams["team_id"].iloc[0]
    pool = analysis.roster_profiles(team, top=9)
    ranked = model.best_replacement(pool[:5], pool[0], candidates=pool + pool, top=20)
    assert ranked["in_player"].is_unique
    assert ranked["net_change"].is_monotonic_decreasing


def test_best_lineups_are_ordered_and_legal(analysis):
    model = analysis.lineup_model
    team = analysis.league.teams["team_id"].iloc[0]
    pool = analysis.roster_profiles(team, top=9)
    best = model.best_lineups(pool, top=5)
    assert len(best) > 0
    assert best["net_rating"].is_monotonic_decreasing
    for players in best["players"]:
        assert len(set(players)) == 5


def test_best_lineups_guards_against_a_huge_search(analysis):
    model = analysis.lineup_model
    everyone = list(model.profiles)
    with pytest.raises(ValueError, match="combinations"):
        model.best_lineups(everyone, max_combinations=10)


def test_skill_scores_are_standardised(analysis):
    scores = I.compute_skill_scores(analysis.players)
    for col in ["spacing", "rim_pressure", "playmaking", "rebounding", "rim_protection"]:
        assert abs(scores[col].mean()) < 0.6, col
        assert 0.4 < scores[col].std() < 2.0, col
