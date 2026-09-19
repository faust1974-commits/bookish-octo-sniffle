"""Season and playoff simulation.

Simulates a whole schedule many times to produce distributions rather than
point estimates: win totals with credible intervals, seeding probabilities,
play-in odds, playoff and title odds.

Game outcomes are drawn from the closed-form win probability rather than
simulated possession by possession. That is the right trade: for ten thousand
seasons of twelve hundred games each, the possession-level detail would cost
hours and change nothing, because only the win or loss propagates.

Seeding ties are broken by projected team strength, then deterministically by
team id so a given seed reproduces exactly. This is a deliberate
simplification and worth stating plainly: the NBA's real procedure starts with
head-to-head record, then division and conference records, and only then
reaches point differential. Applying it properly inside a simulation means
tracking every simulated head-to-head result, which is a meaningful cost for
an effect that changes a seed in a small share of seasons. If you need exact
seeding odds for a team on a tiebreak bubble, that cost is worth paying and
this is the place to add it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .. import constants as K
from .winprob import series_win_probability, win_probability


@dataclass
class SeasonSimResult:
    """Distributions over a simulated season."""

    wins: pd.DataFrame                    # per-team win distribution summary
    win_samples: np.ndarray               # (n_sims, n_teams)
    teams: list[str]
    seeds: pd.DataFrame | None = None
    playoffs: pd.DataFrame | None = None
    n_sims: int = 0
    meta: dict = field(default_factory=dict)

    def team_wins(self, team_id: str) -> np.ndarray:
        return self.win_samples[:, self.teams.index(team_id)]

    def probability_of_at_least(self, team_id: str, wins: float) -> float:
        return float((self.team_wins(team_id) >= wins).mean())


def simulate_season(games: pd.DataFrame, ratings: dict[str, float] | pd.Series,
                    *, n_sims: int = 10_000,
                    home_advantage: float = K.DEFAULT_HOME_ADVANTAGE,
                    sd: float = K.GAME_MARGIN_SD,
                    use_rest: bool = True,
                    completed: pd.DataFrame | None = None,
                    seed: int | None = None,
                    conferences: dict[str, str] | None = None,
                    simulate_playoffs: bool = True) -> SeasonSimResult:
    """Simulate a schedule `n_sims` times.

    Parameters
    ----------
    games:
        Schedule with `home_team_id` and `away_team_id`. Rows that already
        carry scores are treated as played unless `completed` says otherwise.
    ratings:
        Net rating per team, in points per 100 possessions.
    completed:
        Optional frame of already-played games, so mid-season projections
        start from the real record rather than simulating the past.
    """
    rng = np.random.default_rng(seed)
    ratings = dict(ratings)

    teams = sorted(set(games["home_team_id"]) | set(games["away_team_id"]))
    index = {t: i for i, t in enumerate(teams)}
    n_teams = len(teams)

    played = games.dropna(subset=["home_pts", "away_pts"]) if completed is None \
        else completed
    future = games[~games["game_id"].isin(set(played["game_id"]))] if len(played) else games

    # Wins already banked.
    base_wins = np.zeros(n_teams)
    for r in played.itertuples(index=False):
        if r.home_pts > r.away_pts:
            base_wins[index[r.home_team_id]] += 1
        else:
            base_wins[index[r.away_team_id]] += 1

    if future.empty:
        win_samples = np.tile(base_wins, (n_sims, 1))
        return _summarise(win_samples, teams, games, ratings, n_sims, rng,
                          conferences, simulate_playoffs, played)

    home_idx = np.array([index[t] for t in future["home_team_id"]])
    away_idx = np.array([index[t] for t in future["away_team_id"]])
    home_rating = np.array([ratings.get(t, 0.0) for t in future["home_team_id"]])
    away_rating = np.array([ratings.get(t, 0.0) for t in future["away_team_id"]])

    kwargs = {"home_advantage": home_advantage, "sd": sd}
    if use_rest and "home_rest_days" in future.columns:
        kwargs["home_rest"] = future["home_rest_days"].fillna(2).to_numpy()
        kwargs["away_rest"] = future["away_rest_days"].fillna(2).to_numpy()
    probs = np.asarray(win_probability(home_rating, away_rating, **kwargs), dtype=float)

    # One uniform per (simulation, remaining game).
    outcomes = rng.random((n_sims, len(probs))) < probs[None, :]

    win_samples = np.tile(base_wins, (n_sims, 1))
    np.add.at(win_samples.T, home_idx, outcomes.T.astype(float))
    np.add.at(win_samples.T, away_idx, (~outcomes).T.astype(float))

    return _summarise(win_samples, teams, games, ratings, n_sims, rng,
                      conferences, simulate_playoffs, played,
                      future=future, outcomes=outcomes,
                      home_idx=home_idx, away_idx=away_idx)


def _summarise(win_samples, teams, games, ratings, n_sims, rng, conferences,
               simulate_playoffs, played, *, future=None, outcomes=None,
               home_idx=None, away_idx=None) -> SeasonSimResult:
    n_teams = len(teams)
    wins = pd.DataFrame({
        "team_id": teams,
        "mean_wins": win_samples.mean(axis=0),
        "median_wins": np.median(win_samples, axis=0),
        "sd_wins": win_samples.std(axis=0),
        "p05_wins": np.percentile(win_samples, 5, axis=0),
        "p25_wins": np.percentile(win_samples, 25, axis=0),
        "p75_wins": np.percentile(win_samples, 75, axis=0),
        "p95_wins": np.percentile(win_samples, 95, axis=0),
        "net_rating": [ratings.get(t, 0.0) for t in teams],
    }).sort_values("mean_wins", ascending=False).reset_index(drop=True)

    result = SeasonSimResult(wins=wins, win_samples=win_samples, teams=teams,
                             n_sims=n_sims)
    if conferences is None or not simulate_playoffs:
        return result

    seeds, playoffs = _simulate_brackets(win_samples, teams, conferences, ratings,
                                         rng, games, played, future, outcomes,
                                         home_idx, away_idx)
    result.seeds = seeds
    result.playoffs = playoffs
    return result


def _simulate_brackets(win_samples, teams, conferences, ratings, rng, games,
                       played, future, outcomes, home_idx, away_idx):
    """Seed each simulated season and run the play-in and playoff bracket."""
    n_sims, n_teams = win_samples.shape
    conf_of = {t: conferences.get(t, "East") for t in teams}
    conf_names = sorted(set(conf_of.values()))

    seed_counts = np.zeros((n_teams, 16))
    make_playoffs = np.zeros(n_teams)
    make_playin = np.zeros(n_teams)
    conf_finals = np.zeros(n_teams)
    finals = np.zeros(n_teams)
    titles = np.zeros(n_teams)

    idx_of = {t: i for i, t in enumerate(teams)}
    # Ties on wins are broken by projected strength, then by a deterministic
    # per-team constant so a simulation is reproducible rather than dependent
    # on dictionary ordering. Both terms are far smaller than one win.
    strength = np.array([ratings.get(t, 0.0) for t in teams], dtype=float)
    tie_break = strength * 1e-4 + np.arange(len(teams), dtype=float) * 1e-9

    for s in range(n_sims):
        sim_wins = win_samples[s]
        standings = {}
        for conf in conf_names:
            members = [t for t in teams if conf_of[t] == conf]
            ranked = sorted(members,
                            key=lambda t: (sim_wins[idx_of[t]] + tie_break[idx_of[t]]),
                            reverse=True)
            standings[conf] = ranked
            for pos, t in enumerate(ranked[:16]):
                seed_counts[idx_of[t], pos] += 1

        bracket_teams = {}
        for conf in conf_names:
            ranked = standings[conf]
            top6 = ranked[:6]
            playin = ranked[6:10]
            for t in playin:
                make_playin[idx_of[t]] += 1

            if len(playin) >= 4:
                # 7 v 8: winner takes the seven seed.
                seven = _play(playin[0], playin[1], ratings, rng)
                eight_a = playin[1] if seven == playin[0] else playin[0]
                nine_ten = _play(playin[2], playin[3], ratings, rng)
                eight = _play(eight_a, nine_ten, ratings, rng)
                field = top6 + [seven, eight]
            else:
                field = (ranked[:8] + [None] * 8)[:8]
                field = [t for t in field if t is not None]
            bracket_teams[conf] = field
            for t in field:
                make_playoffs[idx_of[t]] += 1

        champions = []
        for conf in conf_names:
            field = bracket_teams[conf]
            if len(field) < 8:
                champions.append(field[0] if field else None)
                continue
            round1 = [_series(field[0], field[7], ratings, rng),
                      _series(field[3], field[4], ratings, rng),
                      _series(field[2], field[5], ratings, rng),
                      _series(field[1], field[6], ratings, rng)]
            semis = [_series(round1[0], round1[1], ratings, rng),
                     _series(round1[2], round1[3], ratings, rng)]
            for t in semis:
                conf_finals[idx_of[t]] += 1
            champ = _series(semis[0], semis[1], ratings, rng)
            champions.append(champ)

        champions = [c for c in champions if c is not None]
        for t in champions:
            finals[idx_of[t]] += 1
        if len(champions) >= 2:
            titles[idx_of[_series(champions[0], champions[1], ratings, rng)]] += 1
        elif champions:
            titles[idx_of[champions[0]]] += 1

    seeds = pd.DataFrame(seed_counts / n_sims,
                         columns=[f"seed_{i+1}" for i in range(16)])
    seeds.insert(0, "team_id", teams)

    playoffs = pd.DataFrame({
        "team_id": teams,
        "conference": [conf_of[t] for t in teams],
        "playin_prob": make_playin / n_sims,
        "playoff_prob": make_playoffs / n_sims,
        "conf_finals_prob": conf_finals / n_sims,
        "finals_prob": finals / n_sims,
        "title_prob": titles / n_sims,
    }).sort_values("title_prob", ascending=False).reset_index(drop=True)
    return seeds, playoffs


def _play(team_a: str, team_b: str, ratings, rng) -> str:
    """One neutral-ish game; the higher seed hosts."""
    p = float(win_probability(ratings.get(team_a, 0.0), ratings.get(team_b, 0.0)))
    return team_a if rng.random() < p else team_b


def _series(team_a: str, team_b: str, ratings, rng, *, games: int = 7) -> str:
    """A best-of-seven with the higher seed holding home court."""
    if team_a is None:
        return team_b
    if team_b is None:
        return team_a
    ra, rb = ratings.get(team_a, 0.0), ratings.get(team_b, 0.0)
    # team_a at home, then team_a on the road (which is one minus team_b's
    # probability of winning at home).
    home_p = float(win_probability(ra, rb))
    away_p = 1.0 - float(win_probability(rb, ra))
    p = series_win_probability(None, games=games, home_prob=home_p, away_prob=away_p)
    return team_a if rng.random() < p else team_b


def project_ratings_from_metrics(team_summary: pd.DataFrame,
                                 *, column: str = "adj_net_rating",
                                 regression: float = 0.25) -> dict[str, float]:
    """Turn measured team ratings into forward-looking ones.

    Observed ratings overstate the spread between teams, because part of what
    separates them was luck. Shrinking toward league average by about a
    quarter is the standard correction and materially improves forecasts.
    """
    values = team_summary.set_index("team_id")[column]
    mean = float(values.mean())
    return {t: float(mean + (v - mean) * (1.0 - regression)) for t, v in values.items()}
