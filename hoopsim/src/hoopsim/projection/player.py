"""Player projection.

Projecting a player is three steps, and skipping any of them is where most
naive systems go wrong:

1. **Blend his history**, weighting recent seasons more. One season is a small
   sample for almost everything.
2. **Regress toward a prior** by sample size, using each rate's own
   stabilization point. A 42% three-point season on 120 attempts is not a
   42% shooter.
3. **Age him forward**, per skill, since shooting and athleticism decline on
   very different schedules.

The output carries an uncertainty estimate alongside every projection, because
a projection without one invites false precision -- and because the simulation
layer needs it to produce honest distributions rather than point estimates.

Availability is projected too. A player who misses thirty games is worth less
than his per-minute quality suggests, and games-missed is itself predictable
from age and history.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .. import constants as K
from .aging import aging_delta
from .regression import shrink, stabilization_point, weighted_history

#: Which aging curve applies to which projected quantity.
SKILL_MAP = {
    "usage_rate": "scoring_volume",
    "ts_pct": "scoring_efficiency",
    "fg3_pct": "three_point",
    "ft_pct": "free_throw",
    "fg3a_rate": "three_point",
    "ft_rate": "scoring_volume",
    "ast_rate": "playmaking",
    "tov_rate": "turnovers",
    "orb_rate": "rebounding",
    "drb_rate": "rebounding",
    "trb_rate": "rebounding",
    "stl_rate": "steals",
    "blk_rate": "blocks",
    "impact": "defense",
    "minutes_per_game": "minutes",
}

#: The sample-size column that governs shrinkage for each rate.
SAMPLE_MAP = {
    "usage_rate": "min",
    "ts_pct": "ts_attempts",
    "fg3_pct": "fg3a",
    "ft_pct": "fta",
    "fg3a_rate": "fga",
    "ft_rate": "fga",
    "ast_rate": "min",
    "tov_rate": "min",
    "orb_rate": "min",
    "drb_rate": "min",
    "trb_rate": "min",
    "stl_rate": "min",
    "blk_rate": "min",
}

PROJECTED_RATES = list(SAMPLE_MAP)


@dataclass
class ProjectionConfig:
    """Knobs for the projection engine."""

    halflife_seasons: float = 1.4
    #: Shrink impact estimates toward this replacement-ish baseline.
    impact_prior: float = -1.0
    impact_stabilization: float = 1800.0     # in possessions
    #: Rookies and players with no history fall back to these.
    default_age: float = 24.0
    minutes_prior: float = 16.0
    # Minutes per game is a stable quantity -- a player's role is known long
    # before his shooting is. Shrink it far less than a shooting rate.
    minutes_stabilization: float = 380.0
    #: Uncertainty floor, so nothing is projected with false confidence.
    min_impact_sd: float = 1.1
    games_prior: float = 66.0


@dataclass
class ProjectionResult:
    projections: pd.DataFrame
    config: ProjectionConfig = field(default_factory=ProjectionConfig)

    def top(self, n: int = 20, by: str = "impact") -> pd.DataFrame:
        return self.projections.nlargest(n, by)


def _positional_priors(history: pd.DataFrame, rates: list[str]) -> dict[str, pd.Series]:
    """League priors for each rate, by position, minutes-weighted."""
    priors: dict[str, pd.Series] = {}
    if "position" not in history.columns:
        return priors
    for rate in rates:
        if rate not in history.columns:
            continue
        rows = history[["position", rate, "min"]].dropna()
        if rows.empty:
            continue
        grouped = rows.groupby("position").apply(
            lambda g: np.average(g[rate], weights=g["min"]) if g["min"].sum() > 0 else np.nan,
            include_groups=False,
        )
        priors[rate] = grouped
    return priors


def project_players(history: pd.DataFrame, *,
                    target_season: str = "next",
                    impact_column: str = "box_impact",
                    config: ProjectionConfig | None = None,
                    age_column: str = "age",
                    season_length: int | None = None,
                    ages: pd.Series | dict | None = None) -> ProjectionResult:
    """Project every player in `history` forward one season.

    `history` is one or more seasons of computed player metrics, stacked, with
    `player_id`, `season`, `min` and whichever rate columns you want projected.
    Seasons must be sortable in chronological order.
    """
    cfg = config or ProjectionConfig()
    if "player_id" not in history.columns:
        raise KeyError("history needs a player_id column")
    if "season" not in history.columns:
        history = history.assign(season="current")

    if season_length is None:
        # Infer the schedule length rather than assuming 82, so the engine
        # works on partial seasons, other leagues and synthetic data.
        season_length = int(round(history.groupby("season")["games"].max().mean())) \
            if "games" in history.columns and history["games"].notna().any() else 82
        season_length = max(1, season_length)

    rates = [r for r in PROJECTED_RATES if r in history.columns]
    priors = _positional_priors(history, rates)
    league_priors = {
        r: float(np.average(history[r].dropna(),
                            weights=history.loc[history[r].notna(), "min"]))
        for r in rates
        if history[r].notna().any() and history.loc[history[r].notna(), "min"].sum() > 0
    }

    rows = []
    for pid, group in history.groupby("player_id", sort=False):
        group = group.sort_values("season")
        minutes = group["min"].to_numpy(dtype=float)
        total_minutes = float(np.nansum(minutes))
        position = str(group["position"].iloc[-1]) if "position" in group.columns else "SF"

        if ages is not None:
            age_now = float(dict(ages).get(pid, np.nan))
        elif age_column in group.columns and np.isfinite(group[age_column].iloc[-1]):
            age_now = float(group[age_column].iloc[-1])
        else:
            age_now = cfg.default_age
        if not np.isfinite(age_now):
            age_now = cfg.default_age
        age_next = age_now + 1.0

        record: dict = {
            "player_id": pid,
            "season": target_season,
            "position": position,
            "age": age_next,
            "seasons_of_history": int(group["season"].nunique()),
            "history_minutes": total_minutes,
        }
        if "player_name" in group.columns:
            record["player_name"] = group["player_name"].iloc[-1]
        if "team_id" in group.columns:
            record["team_id"] = group["team_id"].iloc[-1]

        for rate in rates:
            values = group[rate].to_numpy(dtype=float)
            blended = weighted_history(values, minutes, halflife=cfg.halflife_seasons)
            sample_col = SAMPLE_MAP[rate]
            sample = float(np.nansum(group[sample_col])) if sample_col in group.columns else total_minutes

            prior = np.nan
            if rate in priors and position in priors[rate].index:
                prior = float(priors[rate].loc[position])
            if not np.isfinite(prior):
                prior = league_priors.get(rate, np.nan)
            if not np.isfinite(prior):
                prior = blended

            regressed = float(shrink(blended, sample, prior, stabilization_point(rate)))
            aged = regressed * float(aging_delta(age_now, age_next, SKILL_MAP.get(rate, "scoring_volume")))
            record[rate] = aged
            record[f"{rate}_reliability"] = sample / (sample + stabilization_point(rate))

        # -- impact --
        if impact_column in group.columns:
            impact_values = group[impact_column].to_numpy(dtype=float)
            blended_impact = weighted_history(impact_values, minutes, halflife=cfg.halflife_seasons)
        else:
            blended_impact = np.nan
        possessions = float(np.nansum(group["poss"])) if "poss" in group.columns else total_minutes * 2.2
        regressed_impact = float(shrink(blended_impact, possessions, cfg.impact_prior,
                                        cfg.impact_stabilization))
        record["impact"] = regressed_impact * float(
            aging_delta(age_now, age_next, "defense")
        ) if regressed_impact >= 0 else regressed_impact / max(
            1e-6, float(aging_delta(age_now, age_next, "defense"))
        )
        # Uncertainty shrinks with sample and grows at the extremes of age.
        record["impact_sd"] = float(max(
            cfg.min_impact_sd,
            4.2 / np.sqrt(1.0 + possessions / 600.0)
            + 0.08 * max(0.0, age_next - 32.0)
            + 0.10 * max(0.0, 23.0 - age_next),
        ))

        # -- playing time --
        games = float(np.nansum(group["games"])) if "games" in group.columns else np.nan
        mpg_values = (group["min"] / group["games"].replace(0, np.nan)).to_numpy(dtype=float) \
            if "games" in group.columns else np.array([np.nan])
        blended_mpg = weighted_history(mpg_values, minutes, halflife=cfg.halflife_seasons)
        record["minutes_per_game"] = float(shrink(
            blended_mpg, total_minutes, cfg.minutes_prior, cfg.minutes_stabilization
        )) * float(aging_delta(age_now, age_next, "minutes"))
        record["projected_games"] = float(project_availability(
            age_next, games, group, season_length=season_length))
        record["projected_minutes"] = record["minutes_per_game"] * record["projected_games"]
        record["season_length"] = season_length
        rows.append(record)

    out = pd.DataFrame(rows)
    return ProjectionResult(projections=out.sort_values("impact", ascending=False)
                            .reset_index(drop=True), config=cfg)


def project_availability(age: float, games_played: float | None,
                         history: pd.DataFrame | None = None,
                         *, season_length: int = 82) -> float:
    """Expected games played next season.

    Availability is persistent -- players who miss time keep missing time --
    and declines with age. This is a deliberately simple model; a real one
    would use injury type and severity, which no public box-score feed carries.
    """
    base = 0.80 * season_length
    if games_played is not None and np.isfinite(games_played) and history is not None:
        seasons = max(1, int(history["season"].nunique()))
        rate = games_played / (seasons * season_length)
        # Half weight on observed availability, half on the league baseline.
        base = season_length * (0.5 * float(np.clip(rate, 0.2, 1.0)) + 0.5 * 0.80)
    age_penalty = 0.0
    if age > 30:
        age_penalty = 1.6 * (age - 30)
    if age < 21:
        age_penalty += 2.0
    return float(np.clip(base - age_penalty, 10.0, season_length))


def blend_projection_into_profiles(projections: pd.DataFrame,
                                   profiles: dict) -> dict:
    """Return lineup profiles updated with projected values.

    Lets you evaluate next season's lineups with this season's machinery.
    """
    from ..impact.lineup import PlayerProfile

    updated = dict(profiles)
    for r in projections.itertuples(index=False):
        pid = r.player_id
        existing = updated.get(pid)
        impact = float(getattr(r, "impact", 0.0) or 0.0)
        updated[pid] = PlayerProfile(
            player_id=pid,
            name=str(getattr(r, "player_name", "") or (existing.name if existing else pid)),
            position=str(getattr(r, "position", "SF") or "SF"),
            minutes=float(getattr(r, "projected_minutes", 0.0) or 0.0),
            off_impact=impact * 0.65,
            def_impact=impact * 0.35,
            usage=float(getattr(r, "usage_rate", 0.20) or 0.20),
            ts_pct=float(getattr(r, "ts_pct", 0.56) or 0.56),
            **({s: getattr(existing, s) for s in
                ("spacing", "rim_pressure", "playmaking", "rebounding", "rim_protection")}
               if existing else {}),
        )
    return updated
