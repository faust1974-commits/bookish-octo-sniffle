"""Possession estimation and pace.

Two ways to get possessions, and it matters which you use:

`estimate_possessions` applies the standard box-score formula. It is an
approximation -- the 0.44 coefficient on free throw attempts is a league-wide
average of how often a free throw ends a possession, and it is wrong for any
individual team by a possession or two per game.

`exact_possessions` counts them from the event log, by following the ball. Use
it whenever play-by-play is available, which is whenever you care about
lineups.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .. import constants as K


def estimate_possessions(fga, fta, orb, tov, *, ft_coef: float = K.FT_POSSESSION_COEF):
    """Single-team possession estimate: FGA + ft_coef*FTA - ORB + TOV."""
    return np.asarray(fga, dtype=float) + ft_coef * np.asarray(fta, dtype=float) \
        - np.asarray(orb, dtype=float) + np.asarray(tov, dtype=float)


def estimate_possessions_symmetric(team, opponent, *, ft_coef: float = K.FT_POSSESSION_COEF):
    """Oliver's symmetric estimate: average the team's and opponent's counts.

    Both teams in a game use very nearly the same number of possessions, so
    averaging the two one-sided estimates cancels much of the error. `team` and
    `opponent` are mappings (or frames) with fga/fta/orb/tov.
    """
    a = estimate_possessions(team["fga"], team["fta"], team["orb"], team["tov"], ft_coef=ft_coef)
    b = estimate_possessions(opponent["fga"], opponent["fta"], opponent["orb"],
                             opponent["tov"], ft_coef=ft_coef)
    return 0.5 * (a + b)


def team_possessions(team_box: pd.DataFrame, *, ft_coef: float = K.FT_POSSESSION_COEF) -> pd.DataFrame:
    """Add `poss` to a team-game frame using the symmetric estimate.

    Requires `opponent_team_id` so each row can find its counterpart.
    """
    needed = ["game_id", "team_id", "opponent_team_id", "fga", "fta", "orb", "tov"]
    missing = [c for c in needed if c not in team_box.columns]
    if missing:
        raise KeyError(f"team_possessions needs {missing}")

    opp = team_box[["game_id", "team_id", "fga", "fta", "orb", "tov"]].rename(
        columns={"team_id": "opponent_team_id", "fga": "opp_fga", "fta": "opp_fta",
                 "orb": "opp_orb", "tov": "opp_tov"}
    )
    merged = team_box.merge(opp, on=["game_id", "opponent_team_id"], how="left")
    own = estimate_possessions(merged["fga"], merged["fta"], merged["orb"],
                               merged["tov"], ft_coef=ft_coef)
    other = estimate_possessions(merged["opp_fga"], merged["opp_fta"],
                                 merged["opp_orb"], merged["opp_tov"], ft_coef=ft_coef)
    merged["poss"] = np.where(np.isnan(other), own, 0.5 * (own + other))
    return merged


def exact_possessions(stints: pd.DataFrame) -> pd.DataFrame:
    """Team-game possessions counted from the event log via stints."""
    home = stints.groupby(["game_id", "home_team_id"], as_index=False)["home_poss"].sum()
    home.columns = ["game_id", "team_id", "poss"]
    away = stints.groupby(["game_id", "away_team_id"], as_index=False)["away_poss"].sum()
    away.columns = ["game_id", "team_id", "poss"]
    return pd.concat([home, away], ignore_index=True)


def pace(possessions, minutes, *, period_minutes: float = K.MINUTES_PER_GAME):
    """Possessions per `period_minutes` of game time.

    `minutes` is team minutes played (240 per regulation game), which is what
    makes this correct for overtime games without special-casing them.
    """
    possessions = np.asarray(possessions, dtype=float)
    minutes = np.asarray(minutes, dtype=float)
    game_minutes = minutes / K.PLAYERS_ON_FLOOR
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(game_minutes > 0,
                        period_minutes * possessions / game_minutes,
                        np.nan)


def player_possessions(minutes, team_possessions_played, team_minutes):
    """A player's share of their team's possessions, prorated by minutes.

    This is the denominator for per-possession player rates. A player on the
    floor for 30 of a team's 240 minutes was present for 30/48 of the team's
    possessions, not 30/240.
    """
    minutes = np.asarray(minutes, dtype=float)
    team_possessions_played = np.asarray(team_possessions_played, dtype=float)
    team_minutes = np.asarray(team_minutes, dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(team_minutes > 0,
                        team_possessions_played * minutes * K.PLAYERS_ON_FLOOR / team_minutes,
                        np.nan)
