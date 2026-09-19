"""Rate normalization: per-36, per-24, per-100, per-75 and friends.

The denominator you pick changes who looks good, so this module makes the
choice explicit and reversible rather than baking one basis into the metrics.

Three separate ideas, often confused:

* **Rate basis** -- per game, per 36 minutes, per 100 possessions. Answers
  "how much, per unit of opportunity".
* **Pace adjustment** -- removes the effect of playing for a fast or slow
  team. A per-36 number on a fast team is inflated; a per-100 number already
  handles this, which is why per-100 and per-75 are preferred for cross-team
  comparison.
* **Era / league adjustment** -- expresses a number relative to its own
  season's baseline, so 1998 and 2025 are comparable.

Per-75 deserves a note: it is per-100's better-behaved cousin. 75 possessions
is roughly what a heavy-minutes starter actually plays, so per-75 numbers land
close to the per-game figures people have intuition for, while keeping the
pace-independence of a per-possession basis.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .. import constants as K

#: Counting stats that can be put on a rate basis. Anything not in this list
#: (a percentage, a rating, a rank) is passed through untouched.
COUNTING_STATS = [
    "pts", "fgm", "fga", "fg2m", "fg2a", "fg3m", "fg3a", "ftm", "fta",
    "orb", "drb", "trb", "ast", "stl", "blk", "tov", "pf",
    "points_produced", "scoring_poss", "individual_poss",
    "game_score_total", "ows", "dws", "ws",
]

ALL_MODES = ["totals", "per_game", "per_24", "per_36", "per_40", "per_48",
             "per_75", "per_100"]


class NormalizeError(ValueError):
    pass


def available_modes() -> list[str]:
    return list(ALL_MODES)


def describe_mode(mode: str) -> str:
    return {
        "totals": "Season totals, no denominator.",
        "per_game": "Divided by games played. Mixes production with playing time.",
        "per_24": "Per 24 minutes -- half a game. Useful for bench roles.",
        "per_36": "Per 36 minutes. The conventional starter's workload.",
        "per_40": "Per 40 minutes. NCAA and FIBA regulation length.",
        "per_48": "Per 48 minutes. A full NBA game; inflates everything.",
        "per_75": "Per 75 possessions. Pace-independent and close to per-game scale.",
        "per_100": "Per 100 possessions. Pace-independent, the Oliver standard.",
    }.get(mode, "Unknown mode.")


def _denominator(df: pd.DataFrame, mode: str, *, min_col: str, poss_col: str,
                 games_col: str) -> tuple[np.ndarray, float]:
    """Return (denominator, basis) so that rate = value * basis / denominator."""
    if mode == "totals":
        return np.ones(len(df)), 1.0
    if mode == "per_game":
        if games_col not in df.columns:
            raise NormalizeError(f"per_game needs a {games_col!r} column")
        return df[games_col].to_numpy(dtype=float), 1.0
    if mode in K.PER_MINUTE_BASES and K.PER_MINUTE_BASES[mode] is not None:
        if min_col not in df.columns:
            raise NormalizeError(f"{mode} needs a {min_col!r} column")
        return df[min_col].to_numpy(dtype=float), float(K.PER_MINUTE_BASES[mode])
    if mode in K.PER_POSSESSION_BASES:
        if poss_col not in df.columns:
            raise NormalizeError(
                f"{mode} needs a {poss_col!r} column. Add it with "
                "`metrics.possessions.player_possessions` (players) or "
                "`team_possessions` (teams)."
            )
        return df[poss_col].to_numpy(dtype=float), float(K.PER_POSSESSION_BASES[mode])
    raise NormalizeError(f"unknown mode {mode!r}; choose from {ALL_MODES}")


def normalize(df: pd.DataFrame, mode: str = K.DEFAULT_PER_MODE, *,
              columns: list[str] | None = None,
              min_col: str = "min", poss_col: str = "poss",
              games_col: str = "games",
              suffix: str = "") -> pd.DataFrame:
    """Put counting stats on a rate basis.

    Columns that are not counting stats are left alone, so it is safe to pass
    a full metric frame. With `suffix`, rate columns are added alongside the
    originals instead of replacing them.
    """
    if mode not in ALL_MODES:
        raise NormalizeError(f"unknown mode {mode!r}; choose from {ALL_MODES}")
    out = df.copy()
    if columns is None:
        columns = [c for c in COUNTING_STATS if c in out.columns]
    else:
        missing = [c for c in columns if c not in out.columns]
        if missing:
            raise NormalizeError(f"columns not present: {missing}")

    denom, basis = _denominator(out, mode, min_col=min_col, poss_col=poss_col,
                               games_col=games_col)
    with np.errstate(divide="ignore", invalid="ignore"):
        for c in columns:
            values = out[c].to_numpy(dtype=float)
            rated = np.where(denom > 0, values * basis / denom, np.nan)
            out[f"{c}{suffix}"] = rated
    out.attrs["per_mode"] = mode
    return out


def add_player_possessions(df: pd.DataFrame, *, min_col: str = "min",
                           team_poss_col: str = "tm_poss",
                           team_min_col: str = "tm_min") -> pd.DataFrame:
    """Add `poss`: the team possessions a player was on the floor for."""
    out = df.copy()
    with np.errstate(divide="ignore", invalid="ignore"):
        out["poss"] = np.where(
            out[team_min_col] > 0,
            out[team_poss_col] * out[min_col] * K.PLAYERS_ON_FLOOR / out[team_min_col],
            np.nan,
        )
    return out


def pace_adjust(df: pd.DataFrame, columns: list[str], *,
                team_pace_col: str = "tm_pace",
                league_pace: float | None = None) -> pd.DataFrame:
    """Scale per-minute rates to a common pace.

    Only meaningful for per-minute bases. Per-100 and per-75 numbers are
    already pace-independent, and applying this to them double-counts.
    """
    out = df.copy()
    if league_pace is None:
        league_pace = float(np.nanmean(out[team_pace_col]))
    ratio = league_pace / out[team_pace_col].to_numpy(dtype=float)
    for c in columns:
        out[c] = out[c].to_numpy(dtype=float) * ratio
    out.attrs["pace_adjusted_to"] = league_pace
    return out


def era_adjust(df: pd.DataFrame, columns: list[str], *, by: str = "season",
               method: str = "zscore", suffix: str = "_z",
               weight_col: str | None = "min") -> pd.DataFrame:
    """Express columns relative to their own season's distribution.

    `zscore` gives standard deviations above the (optionally minutes-weighted)
    league mean. `index` gives a ratio to the league mean, scaled to 100, which
    reads more naturally for rate stats.
    """
    if by not in df.columns:
        raise NormalizeError(f"era_adjust needs a {by!r} column")
    out = df.copy()
    for c in columns:
        result = np.full(len(out), np.nan)
        for _, group_idx in out.groupby(by, sort=False).groups.items():
            pos = out.index.get_indexer(group_idx)
            values = out.loc[group_idx, c].to_numpy(dtype=float)
            weights = (out.loc[group_idx, weight_col].to_numpy(dtype=float)
                       if weight_col and weight_col in out.columns
                       else np.ones(len(values)))
            mask = np.isfinite(values) & np.isfinite(weights) & (weights > 0)
            if not mask.any():
                continue
            mean = float(np.average(values[mask], weights=weights[mask]))
            if method == "zscore":
                var = float(np.average((values[mask] - mean) ** 2, weights=weights[mask]))
                sd = np.sqrt(var)
                result[pos] = (values - mean) / sd if sd > 0 else 0.0
            elif method == "index":
                result[pos] = 100.0 * values / mean if mean else np.nan
            else:
                raise NormalizeError(f"unknown method {method!r}")
        out[f"{c}{suffix}"] = result
    return out


def percentile_rank(df: pd.DataFrame, columns: list[str], *,
                    by: str | None = None, suffix: str = "_pctile",
                    minimum_minutes: float | None = None,
                    min_col: str = "min") -> pd.DataFrame:
    """Percentile rank within the league (or within each `by` group).

    With `minimum_minutes`, players below the threshold are excluded from the
    ranking population but still receive a rank against it -- which is what you
    want, since a 40-minute sample should not dilute the distribution.
    """
    out = df.copy()
    eligible = (out[min_col] >= minimum_minutes) if minimum_minutes else pd.Series(True, index=out.index)
    groups = out.groupby(by, sort=False).groups if by else {None: out.index}
    for c in columns:
        result = np.full(len(out), np.nan)
        for _, idx in groups.items():
            pos = out.index.get_indexer(idx)
            values = out.loc[idx, c].to_numpy(dtype=float)
            pool = out.loc[idx, c][eligible.loc[idx]].to_numpy(dtype=float)
            pool = pool[np.isfinite(pool)]
            if pool.size == 0:
                continue
            ranks = np.searchsorted(np.sort(pool), values, side="right") / pool.size
            result[pos] = np.where(np.isfinite(values), 100.0 * ranks, np.nan)
        out[f"{c}{suffix}"] = result
    return out
