"""The usage-efficiency tradeoff, and what happens when you swap a player out.

This is the module that separates a real lineup tool from a spreadsheet.

When you remove a player from a lineup, the other four do not keep their
per-36 rates. The possessions he was ending have to go somewhere, and the
players absorbing them shoot worse on the marginal possession than on their
existing ones -- a player's easiest shots are the ones he already takes. Take
a 32%-usage scorer off the floor and his four teammates each pick up roughly
eight percentage points of usage, at a real cost in efficiency.

Naive per-36 extrapolation ignores all of this and systematically overvalues
removing a high-usage player and undervalues adding one. That is the single
most common error in public lineup tools.

The curve here is linear with a quadratic penalty far from a player's
established usage, and it is asymmetric: players lose more from absorbing
usage than they gain from shedding it. The coefficients live in `constants`
and can be re-fit.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .. import constants as K


@dataclass
class UsageProfile:
    """A player's established usage and the efficiency he sustains at it."""

    player_id: str
    base_usage: float          # share of team possessions ended, 0-1
    base_ts_pct: float
    minutes: float = 0.0

    def efficiency_at(self, usage: float) -> float:
        """True shooting percentage this player would sustain at `usage`."""
        return self.base_ts_pct + ts_delta(self.base_usage, usage)


def ts_delta(base_usage: float, new_usage: float) -> float:
    """Change in true shooting percentage from moving off established usage.

    Positive when usage falls (easier shots), negative when it rises. The
    quadratic term only applies when taking on more, because the cost of
    being overextended accelerates while the benefit of being underused
    plateaus.
    """
    delta_points = (new_usage - base_usage) * 100.0     # in usage percentage points
    if delta_points >= 0:
        return -(K.USAGE_EFFICIENCY_SLOPE * delta_points
                 + K.USAGE_CURVE_CONVEXITY * delta_points ** 2)
    return -K.USAGE_EFFICIENCY_SLOPE_DOWN * delta_points


def redistribute_usage(profiles: list[UsageProfile], *,
                       target_total: float = 1.0,
                       exponent: float = K.USAGE_ABSORPTION_EXPONENT,
                       floor: float = 0.06,
                       ceiling: float = 0.42) -> pd.DataFrame:
    """Rebalance five players' usage so it sums to one possession.

    Every possession ends with exactly one player, so a lineup's usage shares
    must total 1.0. Five players whose established usages sum to 1.25 have to
    give something up; five who sum to 0.85 have to absorb.

    Absorption is not uniform. High-usage players take on a disproportionate
    share of the slack, which `exponent` controls -- at 1.0 the surplus is
    split in proportion to existing usage, above 1.0 it tilts further toward
    the primary options.

    Returns a frame with each player's base and adjusted usage, the efficiency
    consequence, and the points-per-100 impact of the adjustment.
    """
    if not profiles:
        raise ValueError("redistribute_usage needs at least one player")

    base = np.array([p.base_usage for p in profiles], dtype=float)
    total = float(base.sum())
    gap = target_total - total

    weights = np.power(np.clip(base, 1e-6, None), exponent)
    if gap >= 0:
        share = weights / weights.sum()
    else:
        # Shedding tilts the same way: the biggest usage gives up the most.
        share = weights / weights.sum()
    adjusted = base + gap * share

    # Enforce plausible bounds, then rebalance what the clipping displaced.
    for _ in range(8):
        clipped = np.clip(adjusted, floor, ceiling)
        residual = target_total - clipped.sum()
        if abs(residual) < 1e-9:
            adjusted = clipped
            break
        free = (clipped > floor + 1e-12) & (clipped < ceiling - 1e-12)
        if not free.any():
            adjusted = clipped
            break
        w = weights * free
        adjusted = clipped + residual * w / w.sum()
    adjusted = np.clip(adjusted, floor, ceiling)

    deltas = np.array([ts_delta(p.base_usage, a) for p, a in zip(profiles, adjusted)])
    new_ts = np.array([p.base_ts_pct for p in profiles]) + deltas

    # Points per 100 team possessions given up (or gained) by the adjustment.
    # A possession ended at true shooting t is worth ~2t points, so the cost is
    # the usage share times the change in 2 * TS%, times 100 possessions.
    pts_effect = adjusted * deltas * 2.0 * 100.0

    return pd.DataFrame({
        "player_id": [p.player_id for p in profiles],
        "base_usage": base,
        "adjusted_usage": adjusted,
        "usage_change": adjusted - base,
        "base_ts_pct": [p.base_ts_pct for p in profiles],
        "adjusted_ts_pct": new_ts,
        "ts_change": deltas,
        "pts_per_100_effect": pts_effect,
    })


def swap_effect(profiles_before: list[UsageProfile],
                out_player: str, incoming: UsageProfile) -> pd.DataFrame:
    """Usage and efficiency consequences of one substitution.

    Returns a frame with a row per player showing usage before and after, so
    you can see exactly who absorbs the departing player's possessions and
    what it costs them.
    """
    before = redistribute_usage(profiles_before)
    after_profiles = [p for p in profiles_before if p.player_id != out_player]
    if len(after_profiles) == len(profiles_before):
        raise ValueError(f"{out_player!r} is not in this lineup")
    after_profiles.append(incoming)
    after = redistribute_usage(after_profiles)

    merged = before[["player_id", "adjusted_usage", "adjusted_ts_pct", "pts_per_100_effect"]].merge(
        after[["player_id", "adjusted_usage", "adjusted_ts_pct", "pts_per_100_effect"]],
        on="player_id", how="outer", suffixes=("_before", "_after"),
    )
    merged["usage_shift"] = (merged["adjusted_usage_after"].fillna(0.0)
                             - merged["adjusted_usage_before"].fillna(0.0))
    merged["ts_shift"] = (merged["adjusted_ts_pct_after"]
                          - merged["adjusted_ts_pct_before"])
    merged["pts_per_100_shift"] = (merged["pts_per_100_effect_after"].fillna(0.0)
                                   - merged["pts_per_100_effect_before"].fillna(0.0))
    return merged


def profiles_from_metrics(player_metrics: pd.DataFrame,
                          player_ids: list[str] | None = None) -> dict[str, UsageProfile]:
    """Build usage profiles from a computed player metric frame."""
    needed = {"player_id", "usage_rate", "ts_pct"}
    missing = needed - set(player_metrics.columns)
    if missing:
        raise KeyError(f"profiles_from_metrics needs {sorted(missing)}")
    df = player_metrics
    if player_ids is not None:
        df = df[df["player_id"].isin(set(player_ids))]
    out: dict[str, UsageProfile] = {}
    for r in df.itertuples(index=False):
        usage = float(r.usage_rate) if np.isfinite(r.usage_rate) else 0.18
        ts = float(r.ts_pct) if np.isfinite(r.ts_pct) else K.LEAGUE_DEFAULTS["off_rating"] / 200.0
        out[r.player_id] = UsageProfile(
            player_id=r.player_id,
            base_usage=float(np.clip(usage, 0.05, 0.45)),
            base_ts_pct=float(np.clip(ts, 0.35, 0.78)),
            minutes=float(getattr(r, "min", 0.0) or 0.0),
        )
    return out
