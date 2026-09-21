"""One object that ties the whole system together.

Loading a league, computing metrics, fitting RAPM and building a lineup model
are four steps that almost always happen together and in that order. This
wires them up once, lazily, so the CLI, the API and a notebook all get the
same objects without repeating the setup -- and so expensive steps (RAPM,
stint building) happen at most once per session.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import cached_property

import pandas as pd

from . import constants as K
from .data import League


@dataclass
class Analysis:
    """A loaded league with every derived layer available on demand."""

    league: League
    rapm_alpha: float = K.RAPM_DEFAULT_ALPHA
    rapm_prior_weight: float = K.RAPM_PRIOR_WEIGHT
    min_minutes: float = 100.0
    _overrides: dict = field(default_factory=dict, repr=False)

    # -- construction -------------------------------------------------------

    @classmethod
    def synthetic(cls, *, n_teams: int = 30, games_per_team: int = 82,
                  season: str = "2024-25", seed: int = 20251001, **kwargs) -> "Analysis":
        from .data import SyntheticSource

        source = SyntheticSource(n_teams=n_teams, games_per_team=games_per_team,
                                 season=season, seed=seed)
        return cls(league=League.from_source(source, season), **kwargs)

    @classmethod
    def from_nba(cls, season: str, *, season_type: str = "Regular Season",
                 with_pbp: bool = True, offline: bool = False, **kwargs) -> "Analysis":
        from .data.nba_stats import NBAStatsSource

        source = NBAStatsSource(offline=offline)
        return cls(league=League.from_source(source, season, season_type,
                                             with_pbp=with_pbp), **kwargs)

    @classmethod
    def from_nba_github(cls, season: str = "2025-26", *, offline: bool = False,
                        **kwargs) -> "Analysis":
        """Load a real NBA season from the published GitHub dumps.

        This is the fast, reliable path to real data: one compressed file per
        season instead of 1,230 rate-limited requests, and it works from
        environments where stats.nba.com is blocked.
        """
        from .data.nba_github import NBAGithubSource

        source = NBAGithubSource(season, offline=offline)
        return cls(league=League.from_source(source, source.season), **kwargs)

    @classmethod
    def from_csv(cls, directory, season: str, **kwargs) -> "Analysis":
        from .data import CSVSource

        source = CSVSource(directory)
        return cls(league=League.from_source(source, season), **kwargs)

    # -- derived layers -----------------------------------------------------

    @cached_property
    def team_totals(self) -> pd.DataFrame:
        from .metrics import team_totals

        return team_totals(self.league.team_box)

    @cached_property
    def league_totals(self) -> dict:
        from .metrics import league_totals

        return league_totals(self.team_totals)

    @cached_property
    def players(self) -> pd.DataFrame:
        """Full player metric table: every box metric, plus possessions."""
        from .metrics import add_player_possessions, player_season
        from .metrics.box import add_all

        # One row per player, not one per player-team: a mid-season trade
        # must not split a career into halves that each look like a bench guy.
        base = player_season(self.league, combine_stints=True)
        out = add_all(base, self.league_totals, self._overrides.get("box_impact_coefs"))
        return add_player_possessions(out)

    @cached_property
    def teams(self) -> pd.DataFrame:
        from .metrics.team import team_summary

        return team_summary(self.league)

    @cached_property
    def rapm(self):
        from .impact import fit_rapm

        if not self.league.has_pbp:
            return None

        # Shrink toward each player's box-score estimate rather than toward
        # league-average. A season of possessions cannot separate teammates
        # who are almost always on the floor together; the box score can,
        # because it is measured per player rather than per lineup. Measured
        # out of sample, this is worth more than any other single change:
        # R^2 0.344 -> 0.383 at the same penalty.
        #
        # The prior is built from the *built-in* box coefficients. If it used
        # refitted ones it would be fitted against RAPM, which is fitted
        # against it -- so `refit_box_impact` deliberately leaves this fit
        # alone once it has been computed.
        prior = None
        if self.rapm_prior_weight:
            box = self.players
            if "box_impact" in box.columns:
                prior = box.set_index("player_id")["box_impact"].dropna()
        return fit_rapm(self.league.stints, alpha=self.rapm_alpha,
                        prior=prior, prior_weight=self.rapm_prior_weight)

    @cached_property
    def lineup_model(self):
        from .impact import LineupModel

        ratings = self.rapm.ratings if self.rapm is not None else None
        return LineupModel.from_league(self.league, self.players, ratings,
                                       min_minutes=self.min_minutes)

    @cached_property
    def splits(self):
        from .splits import SplitEngine

        return SplitEngine(self.league)

    @cached_property
    def projections(self) -> pd.DataFrame:
        from .projection import project_players

        history = self.players.copy()
        if "season" not in history.columns:
            history["season"] = self.league.season
        return project_players(history, target_season="next").projections

    # -- convenience --------------------------------------------------------

    def refit_box_impact(self) -> dict:
        """Refit the box impact model against RAPM and apply it everywhere.

        The built-in coefficients are a prior. Once there is play-by-play to
        fit against, this replaces them with coefficients calibrated to the
        league actually loaded, which is a large accuracy gain.
        """
        from .impact import fit_box_impact

        if self.rapm is None:
            raise ValueError("refitting the box model needs RAPM, which needs play-by-play")
        coefs = fit_box_impact(self.players, self.rapm.ratings, target_column="rapm")
        self._overrides["box_impact_coefs"] = {
            k: v for k, v in coefs.items() if not k.startswith("_")
        }
        # Invalidate everything downstream of the player table.
        for attr in ("players", "lineup_model", "projections"):
            self.__dict__.pop(attr, None)
        return coefs

    def team_ratings(self, *, regression: float = 0.25) -> dict[str, float]:
        from .sim import project_ratings_from_metrics

        return project_ratings_from_metrics(self.teams, regression=regression)

    def roster_profiles(self, team_id: str, top: int = 10) -> list[str]:
        """The team's rotation, as player ids the lineup model knows about."""
        roster = self.league.roster(team_id)
        known = [p for p in roster["player_id"] if p in self.lineup_model.profiles]
        return known[:top]

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return f"<Analysis {self.league!r}>"
