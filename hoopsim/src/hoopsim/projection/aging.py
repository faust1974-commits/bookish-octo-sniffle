"""Aging curves.

Players do not decline uniformly, and treating them as if they do is one of
the larger errors in naive projection. Athletic production -- steals, blocks,
rebounding, finishing -- peaks in the mid-twenties and falls away fast.
Shooting and passing peak later and hold much longer; plenty of players shoot
better at 34 than at 24.

So the peak age is per skill, not per player, and the curve is asymmetric:
the climb to peak is gentler than the fall from it, with a further
acceleration past the early thirties.

These are league-level curves. They describe the average player and will be
wrong for any individual, which is why the projection engine blends them with
a player's own trajectory rather than applying them blindly.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .. import constants as K


def aging_multiplier(age, skill: str = "scoring_volume", *,
                     peak: float | None = None,
                     growth: float = K.AGING_GROWTH_CURVATURE,
                     decline: float = K.AGING_DECLINE_CURVATURE,
                     floor: float = 0.25) -> np.ndarray:
    """Fraction of peak production expected at a given age.

    Returns 1.0 at the peak age for that skill and falls away on both sides.
    """
    age = np.asarray(age, dtype=float)
    if peak is None:
        peak = K.AGING_PEAKS.get(skill, K.AGING_PEAKS["scoring_volume"])
    scale = K.AGING_CURVATURE_SCALE.get(skill, K.AGING_CURVATURE_SCALE_DEFAULT)
    delta = age - peak
    curvature = np.where(delta <= 0, growth, decline) * scale
    mult = 1.0 - curvature * delta ** 2
    cliff = np.maximum(0.0, age - K.AGING_CLIFF_AGE)
    mult = mult - K.AGING_CLIFF_EXTRA * scale * cliff ** 2
    return np.clip(mult, floor, 1.0)


def aging_delta(age_from, age_to, skill: str = "scoring_volume", **kwargs) -> np.ndarray:
    """Multiplicative change in production from one age to another."""
    a = aging_multiplier(age_from, skill, **kwargs)
    b = aging_multiplier(age_to, skill, **kwargs)
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(a > 0, b / a, 1.0)


def aging_curve_table(skill: str = "scoring_volume",
                      ages=range(19, 41)) -> pd.DataFrame:
    """The whole curve for one skill, for inspection or plotting."""
    ages = np.asarray(list(ages), dtype=float)
    return pd.DataFrame({
        "age": ages,
        "multiplier": aging_multiplier(ages, skill),
        "year_over_year": np.concatenate([[np.nan], aging_delta(ages[:-1], ages[1:], skill)]),
    })


def skills() -> list[str]:
    return list(K.AGING_PEAKS)
