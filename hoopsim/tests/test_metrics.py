"""Metric definitions have identities that must hold. These check them."""

import numpy as np
import pytest

from hoopsim import constants as K
from hoopsim import metrics as M
from hoopsim.metrics.normalize import ALL_MODES, NormalizeError, normalize
from hoopsim.metrics.possessions import estimate_possessions, pace


@pytest.fixture(scope="module")
def player_metrics(analysis):
    return analysis.players


@pytest.fixture(scope="module")
def totals(analysis):
    return analysis.league_totals


def _weighted_mean(frame, column):
    v = frame[column].to_numpy(dtype=float)
    w = frame["min"].to_numpy(dtype=float)
    ok = np.isfinite(v) & (w > 0)
    return float(np.average(v[ok], weights=w[ok]))


def test_per_is_normalised_to_fifteen(player_metrics):
    """PER is defined so that the minutes-weighted league average is exactly 15."""
    assert _weighted_mean(player_metrics, "per") == pytest.approx(15.0, abs=0.01)


def test_defensive_rating_averages_to_league_offensive_rating(player_metrics, totals):
    """Every point scored is a point allowed, so the two must agree league-wide."""
    assert _weighted_mean(player_metrics, "def_rating") == pytest.approx(
        totals["off_rating"], abs=1.0)


def test_win_shares_per_48_averages_about_point_one(player_metrics):
    assert _weighted_mean(player_metrics, "ws_per_48") == pytest.approx(0.100, abs=0.025)


def test_total_win_shares_approximate_total_wins(analysis):
    total_ws = analysis.players["ws"].sum()
    total_wins = analysis.league.standings()["w"].sum()
    assert total_ws == pytest.approx(total_wins, rel=0.15)


def test_usage_rates_sum_to_one_per_team(player_metrics):
    """Every possession is ended by exactly one player."""
    for team, group in player_metrics.groupby("team_id"):
        share = (group["usage_rate"] * group["min"]).sum() / (group["tm_min"].iloc[0] / 5)
        assert share == pytest.approx(1.0, abs=0.02), f"{team} usage summed to {share}"


def test_true_shooting_matches_its_definition(player_metrics):
    df = player_metrics[player_metrics["fga"] > 100]
    manual = df["pts"] / (2 * (df["fga"] + K.FT_POSSESSION_COEF * df["fta"]))
    assert np.allclose(df["ts_pct"], manual)


def test_effective_fg_counts_a_three_as_one_and_a_half(player_metrics):
    df = player_metrics[player_metrics["fga"] > 100]
    manual = (df["fgm"] + 0.5 * df["fg3m"]) / df["fga"]
    assert np.allclose(df["efg_pct"], manual)


def test_possession_estimate_matches_the_formula():
    est = estimate_possessions(fga=85, fta=20, orb=10, tov=14)
    assert est == pytest.approx(85 + 0.44 * 20 - 10 + 14)


def test_exact_possessions_are_close_to_the_box_estimate(league):
    """The 0.44 formula is an approximation; it should still land within a few percent."""
    from hoopsim.metrics.possessions import exact_possessions, team_possessions

    exact = exact_possessions(league.stints).groupby("team_id")["poss"].sum()
    estimated = team_possessions(league.team_box).groupby("team_id")["poss"].sum()
    ratio = (estimated / exact).dropna()
    assert (ratio.between(0.93, 1.07)).all(), ratio.describe()


def test_pace_is_possessions_per_48_minutes():
    assert pace(100.0, 240.0) == pytest.approx(100.0)
    assert pace(50.0, 120.0) == pytest.approx(100.0)


@pytest.mark.parametrize("mode", ALL_MODES)
def test_every_rate_basis_produces_finite_numbers(player_metrics, mode):
    df = player_metrics[player_metrics["min"] > 200]
    out = normalize(df, mode)
    assert np.isfinite(out["pts"]).all(), f"{mode} produced non-finite points"
    assert out.attrs["per_mode"] == mode


def test_rate_bases_scale_as_their_names_say(player_metrics):
    """per_36 must be exactly 1.5x per_24 for the same player."""
    df = player_metrics[player_metrics["min"] > 400].head(20)
    p24 = normalize(df, "per_24")["pts"].to_numpy()
    p36 = normalize(df, "per_36")["pts"].to_numpy()
    p48 = normalize(df, "per_48")["pts"].to_numpy()
    assert np.allclose(p36, p24 * 1.5)
    assert np.allclose(p48, p24 * 2.0)


def test_per_75_and_per_100_are_proportional(player_metrics):
    df = player_metrics[player_metrics["min"] > 400].head(20)
    p75 = normalize(df, "per_75")["pts"].to_numpy()
    p100 = normalize(df, "per_100")["pts"].to_numpy()
    assert np.allclose(p100, p75 * 100.0 / 75.0)


def test_totals_mode_leaves_counting_stats_alone(player_metrics):
    df = player_metrics.head(10)
    assert np.allclose(normalize(df, "totals")["pts"], df["pts"])


def test_unknown_rate_basis_is_rejected(player_metrics):
    with pytest.raises(NormalizeError, match="unknown mode"):
        normalize(player_metrics, "per_37")


def test_per_100_needs_possessions(player_metrics):
    stripped = player_metrics.drop(columns=["poss"])
    with pytest.raises(NormalizeError, match="poss"):
        normalize(stripped, "per_100")


def test_four_factors_are_between_zero_and_one(analysis):
    ff = M.team.four_factors(analysis.league.team_box)
    for col in ["off_efg_pct", "off_tov_rate", "off_orb_rate", "def_efg_pct",
                "def_tov_rate", "def_drb_rate"]:
        assert ff[col].between(0, 1).all(), col


def test_team_offensive_and_defensive_ratings_balance(analysis):
    """League-wide, points scored per 100 equals points allowed per 100."""
    teams = analysis.teams
    assert teams["off_rating"].mean() == pytest.approx(teams["def_rating"].mean(), abs=0.5)
    assert teams["net_rating"].mean() == pytest.approx(0.0, abs=0.5)


def test_adjusted_net_ratings_are_centred(analysis):
    assert analysis.teams["adj_net_rating"].mean() == pytest.approx(0.0, abs=0.5)


def test_srs_sums_to_zero(analysis):
    assert analysis.teams["srs"].mean() == pytest.approx(0.0, abs=0.01)


def test_pythagorean_beats_a_coin_flip_at_predicting_wins(analysis):
    teams = analysis.teams
    actual = teams["w"] / (teams["w"] + teams["l"])
    err = np.abs(teams["pythag_win_pct"] - actual).mean()
    assert err < 0.075, f"mean pythagorean error was {err}"


def test_pythagenpat_agrees_with_the_fixed_exponent(analysis):
    teams = analysis.teams
    diff = np.abs(teams["pythag_win_pct"] - teams["pythagenpat_win_pct"]).max()
    assert diff < 0.05


def test_era_adjustment_centres_each_season(player_metrics):
    df = player_metrics.assign(season="2024-25")
    out = M.era_adjust(df, ["ts_pct"], by="season")
    v = out["ts_pct_z"].to_numpy()
    w = out["min"].to_numpy()
    ok = np.isfinite(v) & (w > 0)
    assert float(np.average(v[ok], weights=w[ok])) == pytest.approx(0.0, abs=1e-6)


def test_percentile_ranks_span_the_range(player_metrics):
    out = M.percentile_rank(player_metrics, ["ts_pct"], minimum_minutes=200)
    ranks = out["ts_pct_pctile"].dropna()
    assert ranks.min() >= 0 and ranks.max() <= 100
    assert ranks.max() > 90 and ranks.min() < 10


def test_metric_registry_documents_everything_it_lists():
    from hoopsim.metrics import registry

    assert len(registry.METRICS) > 40
    for key, metric in registry.METRICS.items():
        assert metric.key == key
        assert metric.description.strip(), f"{key} has no description"
        assert metric.scope in ("player", "team", "both")
        assert metric.kind in ("count", "rate", "pct", "rating", "composite")
