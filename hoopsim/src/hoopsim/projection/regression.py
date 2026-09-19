"""Regression to the mean, done properly.

The wrong way to regress a rate is to shrink everything by a fixed fraction.
The right way weights the observation by how much of it there is, against a
prior, using the rate's own stabilization point -- the sample size at which
the observation deserves half the weight.

Those points differ enormously. Free throw percentage settles after about 250
attempts. Three-point percentage needs roughly 750, which is more than most
players take in a season -- which is exactly why single-season three-point
percentage is such a poor predictor of the next season's.

    weight = n / (n + stabilization)
    estimate = weight * observed + (1 - weight) * prior

The prior should be the best guess *before* seeing this sample: a positional
average, a career rate, or a projection from other skills.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .. import constants as K


def shrink(observed, sample_size, prior, stabilization: float) -> np.ndarray:
    """Empirical Bayes shrinkage of an observed rate toward a prior."""
    observed = np.asarray(observed, dtype=float)
    sample_size = np.asarray(sample_size, dtype=float)
    prior = np.asarray(prior, dtype=float)
    weight = sample_size / (sample_size + float(stabilization))
    weight = np.where(np.isfinite(weight), weight, 0.0)
    filled = np.where(np.isfinite(observed), observed, prior)
    return weight * filled + (1.0 - weight) * prior


def shrink_stat(df: pd.DataFrame, stat: str, sample_col: str,
                *, prior: float | pd.Series | None = None,
                stabilization: float | None = None,
                out_column: str | None = None) -> pd.DataFrame:
    """Shrink one column of a frame, using the registered stabilization point."""
    if stabilization is None:
        stabilization = K.STABILIZATION_POINTS.get(stat, K.STABILIZATION_DEFAULT)
    if prior is None:
        values = df[stat].to_numpy(dtype=float)
        weights = df[sample_col].to_numpy(dtype=float)
        mask = np.isfinite(values) & np.isfinite(weights) & (weights > 0)
        prior = float(np.average(values[mask], weights=weights[mask])) if mask.any() else np.nan
    out = df.copy()
    out[out_column or f"{stat}_shrunk"] = shrink(
        out[stat], out[sample_col], prior, stabilization
    )
    return out


def stabilization_point(stat: str) -> float:
    return K.STABILIZATION_POINTS.get(stat, K.STABILIZATION_DEFAULT)


def reliability(sample_size, stat: str) -> np.ndarray:
    """Share of an observation that survives shrinkage. 0 = pure noise."""
    n = np.asarray(sample_size, dtype=float)
    s = stabilization_point(stat)
    return n / (n + s)


def weighted_history(values: list[float], weights: list[float] | None = None,
                     *, halflife: float = 1.4) -> float:
    """Blend several seasons, weighting recent ones more.

    `values` are ordered oldest to newest. A halflife of 1.4 seasons is the
    usual choice: last season carries roughly twice the weight of the one
    before it.
    """
    values = np.asarray(values, dtype=float)
    if values.size == 0:
        return np.nan
    age = np.arange(len(values) - 1, -1, -1, dtype=float)
    decay = np.power(0.5, age / halflife)
    if weights is not None:
        decay = decay * np.asarray(weights, dtype=float)
    mask = np.isfinite(values) & (decay > 0)
    if not mask.any():
        return np.nan
    return float(np.average(values[mask], weights=decay[mask]))
