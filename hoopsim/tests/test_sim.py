"""Simulation: win probability, Monte Carlo, seasons, calibration."""

import numpy as np
import pytest

from hoopsim import constants as K
from hoopsim import sim as S


# --------------------------------------------------------- win probability

def test_an_even_matchup_on_a_neutral_floor_is_a_coin_flip():
    assert float(S.win_probability(0, 0, neutral_site=True)) == pytest.approx(0.5)


def test_home_court_is_worth_something():
    assert float(S.win_probability(0, 0)) > 0.5
    assert 0.53 < float(S.win_probability(0, 0)) < 0.62


def test_win_probability_rises_with_team_quality():
    probs = [float(S.win_probability(n, 0)) for n in range(-15, 16, 5)]
    assert all(a < b for a, b in zip(probs, probs[1:]))


def test_win_probability_and_margin_invert_each_other():
    for margin in (-12.0, -3.0, 0.0, 4.5, 15.0):
        p = float(S.margin_to_win_prob(margin))
        assert float(S.win_prob_to_margin(p)) == pytest.approx(margin, abs=1e-6)


def test_back_to_backs_are_a_real_penalty():
    rested = float(S.win_probability(0, 0, home_rest=2, away_rest=2))
    tired = float(S.win_probability(0, 0, home_rest=0, away_rest=2))
    assert tired < rested


def test_projected_scores_reproduce_the_margin_and_a_sane_total():
    home, away = S.projected_scores(6.0, -2.0)
    assert float(home - away) == pytest.approx(float(S.projected_margin(6.0, -2.0)))
    assert 200 < float(home + away) < 250


def test_series_probability_beats_a_single_game_for_the_favourite():
    """A longer series gives the better team more chances to prove it."""
    single = 0.60
    assert S.series_win_probability(single, games=7) > single
    assert S.series_win_probability(0.40, games=7) < 0.40
    assert S.series_win_probability(0.50, games=7) == pytest.approx(0.5)


def test_longer_series_favour_the_better_team_more():
    assert (S.series_win_probability(0.6, games=7)
            > S.series_win_probability(0.6, games=5)
            > S.series_win_probability(0.6, games=3))


def test_home_court_pattern_matters_in_a_series():
    split = S.series_win_probability(None, home_prob=0.62, away_prob=0.44)
    flat = S.series_win_probability(0.53)
    assert split != pytest.approx(flat, abs=1e-4)
    assert 0.0 < split < 1.0


def test_live_win_probability_converges_as_the_clock_runs():
    probs = [float(S.live_win_probability(6, t, possession=1))
             for t in (2400, 1200, 600, 120, 20)]
    assert all(a < b for a, b in zip(probs, probs[1:]))
    assert probs[-1] > 0.98


def test_a_finished_game_is_decided():
    assert float(S.live_win_probability(5, 0)) == 1.0
    assert float(S.live_win_probability(-5, 0)) == 0.0


def test_cover_and_over_probabilities_move_the_right_way():
    assert float(S.cover_probability(6.0, -3.0)) > 0.5    # favoured by 3, winning by 6
    assert float(S.cover_probability(6.0, -10.0)) < 0.5
    assert float(S.over_probability(230.0, 220.0)) > 0.5
    assert float(S.over_probability(230.0, 240.0)) < 0.5


# ----------------------------------------------------------- game simulation

def test_possession_distribution_hits_its_target_mean():
    for target in (0.90, 1.05, 1.145, 1.30):
        probs = S.game.possession_distribution(target)
        assert float(np.dot(S.game.POSSESSION_OUTCOMES, probs)) == pytest.approx(target)
        assert probs.sum() == pytest.approx(1.0)
        assert (probs >= 0).all()


def test_monte_carlo_agrees_with_the_closed_form_model():
    """Two models of the same thing must give the same answer."""
    for home_net, away_net in [(0, 0), (8, -1), (-3, 7), (12, -6)]:
        result = S.simulate_from_ratings(home_net, away_net, n_sims=20000, seed=3)
        analytic = float(S.win_probability(home_net, away_net))
        assert result.home_win_prob == pytest.approx(analytic, abs=0.02), (home_net, away_net)
        assert result.margins.mean() == pytest.approx(
            float(S.projected_margin(home_net, away_net)), abs=0.6)


def test_simulated_margin_variance_matches_the_constant():
    result = S.simulate_from_ratings(0, 0, n_sims=20000, seed=5)
    assert result.margins.std() == pytest.approx(K.GAME_MARGIN_SD, abs=1.0)


def test_mean_reversion_reduces_spread_without_moving_the_mean():
    """Self-correction must compress the tails and leave the expectation alone."""
    loose = S.simulate_from_ratings(8, -2, n_sims=12000, seed=4, mean_reversion=0.0)
    tight = S.simulate_from_ratings(8, -2, n_sims=12000, seed=4, mean_reversion=2.0)
    assert tight.margins.std() < loose.margins.std()
    assert tight.margins.mean() == pytest.approx(loose.margins.mean(), abs=1.0)


def test_simulated_scores_are_correlated_within_a_game():
    """Shared pace and self-correction both push the two scores together."""
    result = S.simulate_from_ratings(0, 0, n_sims=12000, seed=6)
    r = np.corrcoef(result.home_scores, result.away_scores)[0, 1]
    assert 0.1 < r < 0.7


def test_simulation_is_reproducible_from_its_seed():
    a = S.simulate_from_ratings(4, 1, n_sims=2000, seed=11)
    b = S.simulate_from_ratings(4, 1, n_sims=2000, seed=11)
    assert np.array_equal(a.home_scores, b.home_scores)


def test_quantiles_are_ordered_and_labelled():
    result = S.simulate_from_ratings(3, 0, n_sims=4000, seed=2)
    q = result.quantiles()
    assert q["margin"].is_monotonic_increasing
    assert "median" in set(q["quantile"])


def test_threshold_probabilities_are_monotone():
    result = S.simulate_from_ratings(5, 0, n_sims=8000, seed=8)
    assert result.prob_margin_over(-10) > result.prob_margin_over(0) > result.prob_margin_over(10)
    assert result.prob_total_over(200) > result.prob_total_over(240)


# --------------------------------------------------------- season simulation

@pytest.fixture(scope="module")
def season(analysis):
    ratings = analysis.team_ratings()
    conferences = dict(zip(analysis.league.teams["team_id"],
                           analysis.league.teams["conference"]))
    games = analysis.league.games.assign(home_pts=np.nan, away_pts=np.nan)
    return S.simulate_season(games, ratings, n_sims=400, conferences=conferences, seed=1)


def test_simulated_wins_add_up_to_the_games_played(season, analysis):
    assert season.wins["mean_wins"].sum() == pytest.approx(len(analysis.league.games), abs=0.5)


def test_exactly_one_champion_per_simulated_season(season):
    assert season.playoffs["title_prob"].sum() == pytest.approx(1.0, abs=1e-6)


def test_the_playoff_field_is_the_right_size(season):
    """Eight teams per conference reach the playoffs, every time."""
    n_conferences = season.playoffs["conference"].nunique()
    assert season.playoffs["playoff_prob"].sum() == pytest.approx(8 * n_conferences, abs=0.01)


def test_better_teams_have_better_odds(season):
    merged = season.playoffs.merge(season.wins[["team_id", "net_rating"]], on="team_id")
    r = np.corrcoef(merged["net_rating"], merged["title_prob"])[0, 1]
    assert r > 0.5


def test_win_projections_carry_an_interval(season):
    w = season.wins
    assert (w["p05_wins"] <= w["median_wins"]).all()
    assert (w["median_wins"] <= w["p95_wins"]).all()
    assert (w["sd_wins"] > 0).all()


def test_played_games_are_not_resimulated(analysis):
    """A mid-season projection starts from the real record."""
    ratings = analysis.team_ratings()
    result = S.simulate_season(analysis.league.games, ratings, n_sims=50,
                               simulate_playoffs=False, seed=2)
    actual = analysis.league.standings().set_index("team_id")["w"]
    projected = result.wins.set_index("team_id")["mean_wins"]
    assert np.allclose(projected.loc[actual.index], actual, atol=1e-9)


def test_rating_regression_shrinks_the_spread(analysis):
    raw = analysis.teams["adj_net_rating"].std()
    regressed = np.std(list(S.project_ratings_from_metrics(
        analysis.teams, regression=0.3).values()))
    assert regressed < raw


# ------------------------------------------------------------- calibration

def test_brier_and_log_loss_reward_being_right():
    outcomes = np.array([1, 1, 0, 0])
    good = np.array([0.9, 0.8, 0.2, 0.1])
    bad = np.array([0.1, 0.2, 0.8, 0.9])
    assert S.brier_score(good, outcomes) < S.brier_score(bad, outcomes)
    assert S.log_loss(good, outcomes) < S.log_loss(bad, outcomes)


def test_a_perfect_forecast_scores_zero():
    outcomes = np.array([1, 0, 1, 0])
    assert S.brier_score(outcomes.astype(float), outcomes) == pytest.approx(0.0)


def test_always_saying_fifty_fifty_scores_a_quarter():
    outcomes = np.array([1, 0, 1, 0, 1, 0])
    assert S.brier_score(np.full(6, 0.5), outcomes) == pytest.approx(0.25)


def test_brier_skill_is_positive_only_when_beating_the_base_rate():
    outcomes = np.array([1, 1, 1, 0, 0, 0])
    informed = np.array([0.9, 0.8, 0.7, 0.3, 0.2, 0.1])
    assert S.brier_skill_score(informed, outcomes) > 0
    assert S.brier_skill_score(np.full(6, 0.5), outcomes) == pytest.approx(0.0, abs=1e-9)


def test_reliability_curve_buckets_add_up():
    rng = np.random.default_rng(0)
    probs = rng.uniform(size=4000)
    outcomes = (rng.uniform(size=4000) < probs).astype(float)
    curve = S.reliability_curve(probs, outcomes, bins=10)
    assert curve["n"].sum() == 4000
    used = curve[curve["n"] > 50]
    assert (np.abs(used["gap"]) < 0.12).all(), used


def test_calibration_report_covers_the_basics():
    rng = np.random.default_rng(1)
    probs = rng.uniform(0.2, 0.8, size=1500)
    outcomes = (rng.uniform(size=1500) < probs).astype(float)
    report = S.calibration_report(probs, outcomes)
    assert report["n"] == 1500
    assert 0 < report["brier"] < 0.3
    assert report["expected_calibration_error"] < 0.1


def test_walk_forward_backtest_only_predicts_unseen_games(analysis):
    from hoopsim.metrics.team import adjusted_ratings

    lg = analysis.league

    def rating_fn(history):
        tb = lg.team_box[lg.team_box["game_id"].isin(set(history["game_id"]))]
        if tb.empty:
            return {}
        adj = adjusted_ratings(history, tb, ridge=8.0)
        return dict(zip(adj["team_id"], adj["adj_net_rating"]))

    bt = S.backtest_walk_forward(lg.games, rating_fn, min_games=40, step=30)
    assert len(bt) > 0
    assert bt["predicted"].between(0, 1).all()
    assert set(bt["outcome"].unique()) <= {0.0, 1.0}
    # Every prediction must be made from strictly fewer games than the block.
    assert (bt["train_games"] < len(lg.games)).all()
