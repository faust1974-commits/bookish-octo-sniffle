"""Calibration scoring.

A forecast that says 70% should be right about 70% of the time. Checking that
is the only way to know whether a model works, and it is the step most often
skipped -- accuracy is not the target, calibration is. A model that predicts
the favourite every time can beat a well-calibrated one on accuracy while
being useless for anything that depends on the probability itself.

Three complementary views:

* **Brier score** -- mean squared error of the probability. Lower is better;
  0.25 is what you get by always saying 50%.
* **Log loss** -- punishes confident mistakes far harder. This is the one to
  watch if the probabilities feed a decision with asymmetric costs.
* **Reliability curve** -- bucket the forecasts and compare predicted with
  observed. This is where you see *which* probabilities are miscalibrated,
  which a single number cannot tell you.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def brier_score(probabilities, outcomes) -> float:
    """Mean squared error of probabilistic forecasts. Lower is better."""
    p = np.asarray(probabilities, dtype=float)
    y = np.asarray(outcomes, dtype=float)
    mask = np.isfinite(p) & np.isfinite(y)
    return float(np.mean((p[mask] - y[mask]) ** 2))


def log_loss(probabilities, outcomes, *, eps: float = 1e-12) -> float:
    """Negative log likelihood per forecast."""
    p = np.clip(np.asarray(probabilities, dtype=float), eps, 1 - eps)
    y = np.asarray(outcomes, dtype=float)
    mask = np.isfinite(p) & np.isfinite(y)
    return float(-np.mean(y[mask] * np.log(p[mask]) + (1 - y[mask]) * np.log(1 - p[mask])))


def brier_skill_score(probabilities, outcomes, *, reference: float | None = None) -> float:
    """Brier score relative to a baseline. Positive means better than baseline.

    The default baseline is the observed base rate, which is the honest
    comparison: beating "always predict the base rate" is the minimum bar.
    """
    y = np.asarray(outcomes, dtype=float)
    ref = float(np.nanmean(y)) if reference is None else reference
    bs = brier_score(probabilities, outcomes)
    bs_ref = brier_score(np.full(len(y), ref), outcomes)
    return float(1.0 - bs / bs_ref) if bs_ref > 0 else np.nan


def reliability_curve(probabilities, outcomes, *, bins: int = 10) -> pd.DataFrame:
    """Predicted versus observed frequency, bucketed.

    A well-calibrated model sits on the diagonal. Read the `n` column before
    the others: a bucket with eleven games says nothing.
    """
    p = np.asarray(probabilities, dtype=float)
    y = np.asarray(outcomes, dtype=float)
    mask = np.isfinite(p) & np.isfinite(y)
    p, y = p[mask], y[mask]

    edges = np.linspace(0.0, 1.0, bins + 1)
    idx = np.clip(np.digitize(p, edges[1:-1], right=False), 0, bins - 1)
    rows = []
    for b in range(bins):
        sel = idx == b
        n = int(sel.sum())
        if n == 0:
            rows.append({"bin_low": edges[b], "bin_high": edges[b + 1], "n": 0,
                         "predicted": np.nan, "observed": np.nan, "gap": np.nan})
            continue
        pred = float(p[sel].mean())
        obs = float(y[sel].mean())
        rows.append({"bin_low": edges[b], "bin_high": edges[b + 1], "n": n,
                     "predicted": pred, "observed": obs, "gap": obs - pred,
                     "se": float(np.sqrt(max(obs * (1 - obs), 1e-9) / n))})
    return pd.DataFrame(rows)


def calibration_report(probabilities, outcomes, *, bins: int = 10,
                       label: str = "model") -> dict:
    """Every calibration number in one call."""
    p = np.asarray(probabilities, dtype=float)
    y = np.asarray(outcomes, dtype=float)
    curve = reliability_curve(p, y, bins=bins)
    valid = curve[curve["n"] > 0]
    weights = valid["n"] / valid["n"].sum() if len(valid) else None
    ece = float(np.average(np.abs(valid["gap"]), weights=weights)) if len(valid) else np.nan
    return {
        "label": label,
        "n": int(np.isfinite(p).sum()),
        "brier": brier_score(p, y),
        "log_loss": log_loss(p, y),
        "brier_skill": brier_skill_score(p, y),
        "expected_calibration_error": ece,
        "mean_predicted": float(np.nanmean(p)),
        "base_rate": float(np.nanmean(y)),
        "accuracy": float(np.nanmean((p >= 0.5) == (y >= 0.5))),
        "reliability": curve,
    }


def backtest_walk_forward(games: pd.DataFrame, rating_fn,
                          *, min_games: int = 100, step: int = 50,
                          home_advantage: float | None = None) -> pd.DataFrame:
    """Walk-forward backtest: predict each block from only prior games.

    This is the only honest way to evaluate a rating system. Fitting ratings on
    a whole season and then scoring predictions on that same season measures
    how well the model memorises, not how well it forecasts.

    `rating_fn` takes a frame of prior games and returns a team_id -> rating
    mapping.
    """
    from .winprob import win_probability

    games = games.dropna(subset=["home_pts", "away_pts"]).sort_values("game_date")
    games = games.reset_index(drop=True)
    rows = []
    for start in range(min_games, len(games), step):
        history = games.iloc[:start]
        block = games.iloc[start:start + step]
        if block.empty:
            break
        ratings = rating_fn(history)
        hca = home_advantage
        for r in block.itertuples(index=False):
            kwargs = {} if hca is None else {"home_advantage": hca}
            p = float(win_probability(ratings.get(r.home_team_id, 0.0),
                                      ratings.get(r.away_team_id, 0.0), **kwargs))
            rows.append({
                "game_id": r.game_id,
                "game_date": r.game_date,
                "train_games": start,
                "predicted": p,
                "outcome": 1.0 if r.home_pts > r.away_pts else 0.0,
                "margin": float(r.home_pts - r.away_pts),
            })
    return pd.DataFrame(rows)
