"""Simulation: win probability, game and season Monte Carlo, calibration."""

from .calibration import (backtest_walk_forward, brier_score, brier_skill_score,
                          calibration_report, log_loss, reliability_curve)
from .game import GameSimResult, simulate_game, simulate_from_ratings, simulate_matchup
from .season import SeasonSimResult, project_ratings_from_metrics, simulate_season
from .winprob import (cover_probability, live_win_probability, margin_to_win_prob,
                      over_probability, projected_margin, projected_scores,
                      rest_adjustment, series_win_probability, win_prob_to_margin,
                      win_probability)

__all__ = [
    "win_probability", "projected_margin", "margin_to_win_prob", "win_prob_to_margin",
    "projected_scores", "cover_probability", "over_probability",
    "live_win_probability", "series_win_probability", "rest_adjustment",
    "simulate_game", "simulate_matchup", "simulate_from_ratings", "GameSimResult",
    "simulate_season", "SeasonSimResult", "project_ratings_from_metrics",
    "brier_score", "log_loss", "brier_skill_score", "reliability_curve",
    "calibration_report", "backtest_walk_forward",
]
