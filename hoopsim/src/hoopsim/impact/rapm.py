"""Regularized Adjusted Plus-Minus.

Plain plus-minus tells you what happened while a player was on the floor,
which is mostly a statement about his teammates. Adjusted plus-minus tries to
solve that out by regressing possession outcomes on who was on the floor, but
the design matrix is close to singular -- players who always play together are
mathematically indistinguishable -- so unregularized APM produces famously
absurd numbers.

Ridge regression fixes it by pulling every coefficient toward a prior. With a
zero prior that is ordinary RAPM. With a box-score prior it is the shape used
by the well-known proprietary metrics: the box score carries the estimate
where the possession data is thin, and the possession data overrides it where
there is enough of it.

Implementation notes:

* The design matrix is sparse (ten non-zeros per row out of ~900 columns), so
  it is built with scipy.sparse and solved through the normal equations. The
  Gram matrix is small and dense, which makes this exact and fast.
* Each stint contributes two rows, one per team on offence, weighted by the
  possessions actually played.
* Offence and defence are estimated separately, which is the whole point --
  a player's defensive value is not recoverable from a single net number.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import sparse

from .. import constants as K


@dataclass
class RAPMResult:
    """Fitted RAPM, with the diagnostics needed to know whether to trust it."""

    ratings: pd.DataFrame          # player_id, rapm_off, rapm_def, rapm, possessions
    home_advantage: float          # points per 100 possessions
    intercept: float               # league average offensive rating
    alpha: float
    n_rows: int
    n_players: int

    def top(self, n: int = 20, by: str = "rapm") -> pd.DataFrame:
        return self.ratings.nlargest(n, by)

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return (f"<RAPM players={self.n_players} rows={self.n_rows} "
                f"alpha={self.alpha:g} hca={self.home_advantage:+.2f}>")


def _stint_rows(stints: pd.DataFrame, *, exclude_garbage: bool,
                min_possessions: float, recency_halflife: float | None):
    """Expand stints into (offense lineup, defense lineup, rate, weight) rows."""
    df = stints
    if exclude_garbage and "garbage_time" in df.columns:
        df = df[~df["garbage_time"].astype(bool)]

    rows = []
    # Recency weighting for multi-season fits: a stint from three years ago
    # should not count as much as one from last month.
    if recency_halflife and "game_date_index" in df.columns:
        age = df["game_date_index"].max() - df["game_date_index"]
        decay = np.power(0.5, age / recency_halflife)
    else:
        decay = np.ones(len(df))

    for i, r in enumerate(df.itertuples(index=False)):
        w = float(decay[i]) if len(decay) else 1.0
        if r.home_poss >= min_possessions:
            rows.append((r.home_lineup, r.away_lineup,
                         100.0 * r.home_pts / r.home_poss, r.home_poss * w, 1.0))
        if r.away_poss >= min_possessions:
            rows.append((r.away_lineup, r.home_lineup,
                         100.0 * r.away_pts / r.away_poss, r.away_poss * w, -1.0))
    return rows


def fit_rapm(stints: pd.DataFrame, *,
             alpha: float = K.RAPM_DEFAULT_ALPHA,
             prior: pd.Series | dict | None = None,
             prior_weight: float = 1.0,
             exclude_garbage: bool = True,
             min_possessions: float = 1.0,
             recency_halflife: float | None = None) -> RAPMResult:
    """Fit offensive and defensive RAPM from a stint table.

    Parameters
    ----------
    alpha:
        Ridge penalty. Higher shrinks harder toward the prior. The default is
        a reasonable single-season NBA value; tune it with `cross_validate_alpha`.
    prior:
        Optional per-player prior rating (for example a box-score impact
        estimate), applied to both the offensive and defensive coefficients as
        a shared starting point. Players absent from the prior get zero.
    prior_weight:
        Scales how much of `alpha`'s pull goes toward the prior rather than
        toward zero. 1.0 means shrink fully toward the prior.
    """
    rows = _stint_rows(stints, exclude_garbage=exclude_garbage,
                       min_possessions=min_possessions,
                       recency_halflife=recency_halflife)
    if not rows:
        raise ValueError("no usable stints: check possession counts and the garbage-time filter")

    players = sorted({p for off, dfn, *_ in rows for p in (*off, *dfn)})
    index = {p: i for i, p in enumerate(players)}
    n = len(players)
    n_rows = len(rows)

    # Columns: [0, n) offensive coefficients, [n, 2n) defensive, 2n home term.
    data, row_idx, col_idx = [], [], []
    y = np.empty(n_rows)
    w = np.empty(n_rows)
    for i, (off, dfn, rate, weight, home_sign) in enumerate(rows):
        for p in off:
            row_idx.append(i); col_idx.append(index[p]); data.append(1.0)
        for p in dfn:
            row_idx.append(i); col_idx.append(n + index[p]); data.append(-1.0)
        row_idx.append(i); col_idx.append(2 * n); data.append(home_sign)
        y[i] = rate
        w[i] = weight

    x = sparse.csr_matrix((data, (row_idx, col_idx)), shape=(n_rows, 2 * n + 1))

    intercept = float(np.average(y, weights=w))
    y_centered = y - intercept

    sqrt_w = np.sqrt(w)
    xw = x.multiply(sqrt_w[:, None]).tocsr()
    gram = (xw.T @ xw).toarray()
    rhs = xw.T @ (y_centered * sqrt_w)

    penalty = np.full(2 * n + 1, float(alpha))
    penalty[2 * n] = 0.0          # never shrink the home-court term
    gram_reg = gram + np.diag(penalty)

    if prior is not None:
        prior_map = dict(prior) if not isinstance(prior, dict) else prior
        prior_vec = np.zeros(2 * n + 1)
        for p, i in index.items():
            value = float(prior_map.get(p, 0.0) or 0.0)
            # A player's overall prior is split across the two ends. Without
            # side-specific priors this is the honest default.
            prior_vec[i] = 0.5 * value
            prior_vec[n + i] = 0.5 * value
        rhs = rhs + prior_weight * penalty * prior_vec

    beta = np.linalg.solve(gram_reg, rhs)

    off_coef = beta[:n]
    def_coef = beta[n:2 * n]
    home = float(beta[2 * n])

    # Possessions per player, for the reliability column.
    poss = np.zeros(n)
    for off, dfn, _rate, weight, _s in rows:
        for p in off:
            poss[index[p]] += weight
        for p in dfn:
            poss[index[p]] += weight

    ratings = pd.DataFrame({
        "player_id": players,
        "rapm_off": off_coef,
        "rapm_def": def_coef,
        "rapm": off_coef + def_coef,
        "possessions": poss,
    }).sort_values("rapm", ascending=False).reset_index(drop=True)
    ratings["reliable"] = ratings["possessions"] >= K.RAPM_MIN_POSSESSIONS

    return RAPMResult(ratings=ratings, home_advantage=home * 2.0, intercept=intercept,
                      alpha=alpha, n_rows=n_rows, n_players=n)


def cross_validate_alpha(stints: pd.DataFrame,
                         alphas=(250., 500., 1000., 2000., 4000., 8000., 16000.),
                         *, folds: int = 5, seed: int = 0, **kwargs) -> pd.DataFrame:
    """Pick the ridge penalty by held-out weighted squared error.

    The right alpha depends on how many possessions you have, so it should be
    chosen, not assumed. Returns one row per candidate, best first.
    """
    rng = np.random.default_rng(seed)
    games = stints["game_id"].unique()
    assignment = rng.integers(0, folds, size=len(games))
    fold_of = dict(zip(games, assignment))
    fold_col = stints["game_id"].map(fold_of)

    results = []
    for alpha in alphas:
        errors, weights = [], []
        for f in range(folds):
            train = stints[fold_col != f]
            test = stints[fold_col == f]
            if train.empty or test.empty:
                continue
            fit = fit_rapm(train, alpha=alpha, **kwargs)
            pred_err, pred_w = _holdout_error(fit, test, **kwargs)
            errors.append(pred_err)
            weights.append(pred_w)
        if not errors:
            continue
        total_w = float(np.sum(weights))
        results.append({
            "alpha": alpha,
            "weighted_mse": float(np.sum(errors)) / total_w if total_w else np.nan,
            "folds": len(errors),
        })
    return pd.DataFrame(results).sort_values("weighted_mse").reset_index(drop=True)


def _holdout_error(fit: RAPMResult, test: pd.DataFrame, **kwargs) -> tuple[float, float]:
    off = dict(zip(fit.ratings["player_id"], fit.ratings["rapm_off"]))
    dfn = dict(zip(fit.ratings["player_id"], fit.ratings["rapm_def"]))
    rows = _stint_rows(test,
                       exclude_garbage=kwargs.get("exclude_garbage", True),
                       min_possessions=kwargs.get("min_possessions", 1.0),
                       recency_halflife=None)
    err = 0.0
    total = 0.0
    half_home = fit.home_advantage / 2.0
    for off_lineup, def_lineup, rate, weight, home_sign in rows:
        pred = (fit.intercept
                + sum(off.get(p, 0.0) for p in off_lineup)
                + sum(dfn.get(p, 0.0) for p in def_lineup)
                + home_sign * half_home)
        err += weight * (rate - pred) ** 2
        total += weight
    return err, total


# ---------------------------------------------------------------------------
# Fitting the box-score impact model
# ---------------------------------------------------------------------------

def fit_box_impact(player_metrics: pd.DataFrame, target: pd.Series | pd.DataFrame,
                   *, target_column: str = "rapm",
                   min_minutes: float = 300.0,
                   ridge: float = 1.0) -> dict:
    """Fit the coefficients of `metrics.box.add_box_impact` against a target.

    The target is normally RAPM (on real data) or the known ground truth (on
    synthetic data). The result is a coefficient dict that can be passed
    straight back into `add_box_impact`, which is how the box model gets
    calibrated to the league it is actually being used on instead of relying
    on the built-in prior.
    """
    from ..metrics.box import impact_features

    if isinstance(target, pd.DataFrame):
        if target_column not in target.columns:
            raise KeyError(f"target frame has no {target_column!r} column")
        target = target.set_index("player_id")[target_column]

    df = player_metrics[player_metrics["min"] >= min_minutes].copy()
    feats = impact_features(df)
    feature_names = [c for c in feats.columns if c != "_poss"]

    y = df["player_id"].map(target).to_numpy(dtype=float)
    x = feats[feature_names].to_numpy(dtype=float)
    weights = df["min"].to_numpy(dtype=float)

    mask = np.isfinite(y) & np.isfinite(x).all(axis=1) & (weights > 0)
    if mask.sum() < len(feature_names) + 2:
        raise ValueError(
            f"only {int(mask.sum())} usable players for {len(feature_names)} "
            "features; lower min_minutes or supply a fuller target"
        )
    x, y, weights = x[mask], y[mask], weights[mask]

    x_design = np.column_stack([np.ones(len(x)), x])
    sqrt_w = np.sqrt(weights)
    xw = x_design * sqrt_w[:, None]
    yw = y * sqrt_w
    penalty = np.eye(x_design.shape[1]) * ridge
    penalty[0, 0] = 0.0               # never penalise the intercept
    beta = np.linalg.solve(xw.T @ xw + penalty, xw.T @ yw)

    coefs = {"intercept": float(beta[0])}
    coefs.update({name: float(b) for name, b in zip(feature_names, beta[1:])})

    pred = x_design @ beta
    ss_res = float(np.sum(weights * (y - pred) ** 2))
    ss_tot = float(np.sum(weights * (y - np.average(y, weights=weights)) ** 2))
    coefs["_r_squared"] = 1.0 - ss_res / ss_tot if ss_tot else np.nan
    coefs["_n"] = int(mask.sum())
    return coefs
