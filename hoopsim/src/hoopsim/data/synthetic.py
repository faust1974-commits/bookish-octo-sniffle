"""A synthetic league that behaves like basketball.

This exists for two reasons. First, `stats.nba.com` is unreachable from some
environments (and rate-limits hard from all of them), so every layer of this
system needs a data source that always works. Second, synthetic data has known
ground truth: the latent player ratings that generated the games are available
for comparison, which is the only honest way to test whether RAPM, the lineup
model, or the projection engine actually recover what they claim to.

Generation runs possession by possession and emits play-by-play. Box scores are
derived from that play-by-play rather than generated alongside it, so the two
can never disagree and the PBP parser is exercised on every run.

Calibration, measured over a 30-team / 60-game league against real NBA values:

    possessions per team per game   98.9   (NBA ~99)
    offensive rating               112.7   (NBA ~114.5)
    effective field goal %          .540   (NBA ~.542)
    turnover rate                   .133   (NBA ~.128)
    offensive rebound rate          .262   (NBA ~.265)
    free throw rate                 .243   (NBA ~.238)
    home court advantage            2.3    (NBA ~2.5)
    team rating spread (SD)         5.9    (NBA ~4.5)
    raw margin SD                  17.5    (NBA ~14)

The last two are the known limitation: team strength spread runs wide and the
margin distribution has fatter tails than real basketball, because generated
players' shooting percentages are more dispersed than real ones and lineup
quality swings more between stints. Everything that depends on the shape of the
scoring environment is faithful; anything that depends on the *tails* of the
margin distribution will read slightly pessimistic on synthetic data. Use real
data before trusting a calibration result.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .. import constants as K
from .source import DataSource

_EAST = "East"
_WEST = "West"

# Mean offensive share of available rebounds implied by the skill priors above.
# Used to centre the generated offensive rebound rate on the league value.
_REBOUND_REFERENCE_SHARE = 0.42

# See _build_players: scaled so team point-differential spread matches the NBA.
_TEAM_STRENGTH_SD = 0.72

# How a player's true offensive impact is realised. Part of it shows up in his
# own box score -- he shoots better and turns it over less -- and the rest is a
# lift on the four teammates beside him, which no box score records. Splitting
# it this way is what makes box-score metrics partially (but only partially)
# recover true impact, exactly as they do in reality.
_SELF_SHARE_SHOOTING = 0.35
_SELF_SHARE_TURNOVERS = 0.10
_LIFT_SHARE = 1.0 - _SELF_SHARE_SHOOTING - _SELF_SHARE_TURNOVERS

# Converting impact points into shooting percentage: a 20%-usage player takes
# roughly 0.9 shooting possessions per possession used, worth ~2 points a make,
# so one point per 100 of self-realised impact is about 1/36th of a percentage
# point of shooting.
_PTS100_PER_SHOOT_PCT = 100.0 * 0.20 * 0.9 * 2.0
_SHOOT_PCT_PER_IMPACT = _SELF_SHARE_SHOOTING / _PTS100_PER_SHOOT_PCT
# A turnover costs about 1.14 points; a 20%-usage player has ~20 uses per 100.
_PTS100_PER_TOV_RATE = 100.0 * 0.20 * 1.14
_TOV_RATE_PER_IMPACT = _SELF_SHARE_TURNOVERS / _PTS100_PER_TOV_RATE

# Defence is mostly invisible to the box score, but steals, blocks and
# defensive rebounds carry a little signal, so they are tied weakly to it.
_STL_PER_DEF_IMPACT = 0.055
_BLK_PER_DEF_IMPACT = 0.055
_DRB_PER_DEF_IMPACT = 0.035
_AST_PER_OFF_IMPACT = 0.050

# Lineup quality `edge` is carried in points per 100 possessions throughout the
# generator. The coefficients below convert it into shot-making and ball
# security, which is how a better lineup actually scores more.
#
#   A 1 percentage-point change in field goal percentage is worth roughly
#   1.9 points per 100 possessions (~88 FGA per 100, ~2.2 points per make).
#   A 1 percentage-point change in turnover rate is worth roughly 1.14.
#
# So to deliver `edge` points per 100, route ~70% through shooting and ~25%
# through turnovers and solve for the coefficient in each.
_PTS100_PER_FG_PCT_POINT = 1.9
_PTS100_PER_TOV_PCT_POINT = 1.14
_EDGE_VIA_SHOOTING = 0.70
_EDGE_VIA_TURNOVERS = 0.25

SHOOT_EDGE_COEF = _EDGE_VIA_SHOOTING / _PTS100_PER_FG_PCT_POINT / 100.0
TOV_EDGE_COEF = _EDGE_VIA_TURNOVERS / _PTS100_PER_TOV_PCT_POINT / 100.0

# Home advantage, in points per 100 possessions, applied to whichever team has
# the ball. Half on each end sums to constants.DEFAULT_HOME_ADVANTAGE of margin.
HOME_EDGE = K.DEFAULT_HOME_ADVANTAGE / 2.0

_FIRST = [
    "Marcus", "Devin", "Tyrese", "Jalen", "Cade", "Anthony", "Darius", "Evan",
    "Franz", "Paolo", "Scottie", "Jaden", "Keegan", "Bennedict", "Shaedon",
    "Chet", "Jabari", "Walker", "Amen", "Ausar", "Dereck", "Isaiah", "Trey",
    "Malik", "Quentin", "Naz", "Herb", "Grant", "Cam", "Dante", "Moses",
    "Santi", "Julian", "Nickeil", "Gradey", "Brandin", "Jarace", "Kris",
]
_LAST = [
    "Holloway", "Barrett", "Vance", "Ortega", "Whitfield", "Kasprzak", "Nunes",
    "Adeyemi", "Sorensen", "Marchetti", "Delacroix", "Okonkwo", "Rasmussen",
    "Ferreira", "Lindqvist", "Abadi", "Stavros", "Pemberton", "Novak",
    "Ibarra", "Halvorsen", "Chukwu", "Danilov", "Moreau", "Estrada", "Bhatt",
    "Kovalenko", "Trueblood", "Ashworth", "Mbeki", "Rinaldi", "Vasquez",
    "Sandoval", "Haugen", "Petrosyan", "Iverach", "Dunleavy", "Osei",
]

_CITIES = [
    ("Atlanta", "ATL", _EAST), ("Boston", "BOS", _EAST), ("Brooklyn", "BKN", _EAST),
    ("Charlotte", "CHA", _EAST), ("Chicago", "CHI", _EAST), ("Cleveland", "CLE", _EAST),
    ("Detroit", "DET", _EAST), ("Indiana", "IND", _EAST), ("Miami", "MIA", _EAST),
    ("Milwaukee", "MIL", _EAST), ("New York", "NYK", _EAST), ("Orlando", "ORL", _EAST),
    ("Philadelphia", "PHI", _EAST), ("Toronto", "TOR", _EAST), ("Washington", "WAS", _EAST),
    ("Dallas", "DAL", _WEST), ("Denver", "DEN", _WEST), ("Golden State", "GSW", _WEST),
    ("Houston", "HOU", _WEST), ("Los Angeles", "LAL", _WEST), ("Memphis", "MEM", _WEST),
    ("Minnesota", "MIN", _WEST), ("New Orleans", "NOP", _WEST), ("Oklahoma City", "OKC", _WEST),
    ("Phoenix", "PHX", _WEST), ("Portland", "POR", _WEST), ("Sacramento", "SAC", _WEST),
    ("San Antonio", "SAS", _WEST), ("Utah", "UTA", _WEST), ("Clippers", "LAC", _WEST),
]

_NICKNAMES = [
    "Arc", "Motion", "Current", "Vanguard", "Union", "Ironworks", "Drift",
    "Signal", "Compass", "Foundry", "Lantern", "Quarry", "Tide", "Summit",
    "Meridian", "Anvil", "Cascade", "Beacon", "Forge", "Cobalt", "Harbor",
    "Aurora", "Sable", "Pioneer", "Vertex", "Basin", "Ember", "Granite",
    "Skyline", "Junction",
]


@dataclass
class PlayerLatent:
    """Ground-truth ratings that generate a player's behaviour.

    Impact terms are in points per 100 possessions relative to a league-average
    player. Tendencies are probabilities or rates. Tests compare recovered
    estimates against `off_impact` / `def_impact`.
    """

    player_id: str
    name: str
    team_id: str
    position: str
    age: float
    rotation_rank: int              # 0-4 starters, 5+ bench
    usage: float                    # target usage rate
    off_impact: float               # true offensive impact, pts/100
    def_impact: float               # true defensive impact, pts/100 (positive = good)
    fg3_pct: float
    fg2_pct: float
    ft_pct: float
    fg3a_rate: float                # share of own shots taken from three
    ft_rate: float                  # FTA per FGA
    tov_rate: float                 # turnovers per possession used
    ast_skill: float                # propensity to assist
    orb_skill: float
    drb_skill: float
    stl_skill: float
    blk_skill: float
    foul_rate: float
    minutes_target: float


def _name_pool(rng: np.random.Generator, count: int) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    while len(names) < count:
        nm = f"{rng.choice(_FIRST)} {rng.choice(_LAST)}"
        if nm in seen:
            nm = f"{nm} {chr(ord('A') + len(names) % 26)}."
        seen.add(nm)
        names.append(nm)
    return names


class SyntheticSource(DataSource):
    """Generate a self-consistent league with known ground truth.

    Parameters
    ----------
    n_teams:
        Teams in the league. Must be even.
    games_per_team:
        Regular-season games each team plays.
    roster_size:
        Players per team. The first 9-10 by rotation rank actually play.
    season:
        Season label, e.g. "2024-25".
    seed:
        RNG seed. The same seed always produces the same league.
    """

    name = "synthetic"
    provides_pbp = True
    provides_shot_locations = True
    provides_tracking = False

    def __init__(
        self,
        n_teams: int = 30,
        games_per_team: int = 82,
        roster_size: int = 14,
        season: str = "2024-25",
        seed: int = 20251001,
    ) -> None:
        if n_teams % 2:
            raise ValueError("n_teams must be even so every date pairs off cleanly")
        if n_teams > len(_CITIES):
            raise ValueError(f"n_teams must be <= {len(_CITIES)}")
        self.n_teams = n_teams
        self.games_per_team = games_per_team
        self.roster_size = roster_size
        self.season = season
        self.seed = seed
        self._rng = np.random.default_rng(seed)
        self._teams: pd.DataFrame | None = None
        self._latents: dict[str, PlayerLatent] = {}
        self._games: pd.DataFrame | None = None
        self._pbp: pd.DataFrame | None = None
        self._box: pd.DataFrame | None = None
        self._build_teams()
        self._build_players()

    # -- construction -------------------------------------------------------

    def _build_teams(self) -> None:
        rng = self._rng
        picks = _CITIES[: self.n_teams]
        nicks = list(rng.permutation(_NICKNAMES))[: self.n_teams]
        rows = []
        for i, ((city, abbrev, conf), nick) in enumerate(zip(picks, nicks)):
            rows.append({
                "team_id": f"T{i:02d}",
                "team_name": f"{city} {nick}",
                "team_abbrev": abbrev,
                "season": self.season,
                "conference": conf,
                "division": f"{conf}-{i % 3}",
            })
        self._teams = pd.DataFrame(rows)

    def _build_players(self) -> None:
        rng = self._rng
        total = self.n_teams * self.roster_size
        names = _name_pool(rng, total)

        # Pass one: draw the structural quantities.
        raw: list[dict] = []
        idx = 0
        for _, team in self._teams.iterrows():
            # Team strength shifts every player's impact, creating real spread
            # in team quality rather than 30 interchangeable rosters. A
            # team-strength unit moves roughly five points of net rating (it
            # lands on all five players on the floor), so the SD is set to put
            # league point-differential spread near the NBA's.
            team_strength = rng.normal(0.0, _TEAM_STRENGTH_SD)
            for rank in range(self.roster_size):
                rank_effect = -1.15 * rank + 3.2      # talent falls off with rank
                base = team_strength + rank_effect + rng.normal(0.0, 1.5)
                minutes = float(np.clip(34.5 - 3.05 * rank + rng.normal(0, 2.2), 0.0, 38.5))
                if rank >= 10:
                    minutes = float(np.clip(minutes * 0.35, 0.0, 12.0))
                raw.append({
                    "player_id": f"P{idx:04d}",
                    "name": names[idx],
                    "team_id": team["team_id"],
                    "position": K.POSITIONS[rank % 5],
                    "rank": rank,
                    "age": float(np.clip(rng.normal(26.4, 3.9), 19, 39)),
                    "off": base * 0.62 + rng.normal(0.0, 1.1),
                    "dfn": base * 0.38 + rng.normal(0.0, 1.3),
                    "minutes": minutes,
                })
                idx += 1

        # Pass two: centre impact on the minutes-weighted league average, so
        # zero means "a league-average player" and the ground truth is
        # directly comparable to what RAPM estimates.
        weights = np.array([r["minutes"] for r in raw], dtype=float)
        weights = np.where(weights > 0, weights, 1e-6)
        off_mean = float(np.average([r["off"] for r in raw], weights=weights))
        def_mean = float(np.average([r["dfn"] for r in raw], weights=weights))

        # Pass three: derive observable skills from the centred impacts.
        for r in raw:
            off = r["off"] - off_mean
            dfn = r["dfn"] - def_mean
            pos = r["position"]
            rank = r["rank"]
            bigness = {"PG": 0.0, "SG": 0.2, "SF": 0.45, "PF": 0.78, "C": 1.0}[pos]
            usage = float(np.clip(
                0.20 + 0.020 * off - 0.008 * rank + rng.normal(0, 0.028), 0.105, 0.365,
            ))
            shoot_bonus = _SHOOT_PCT_PER_IMPACT * off
            self._latents[r["player_id"]] = PlayerLatent(
                player_id=r["player_id"],
                name=r["name"],
                team_id=r["team_id"],
                position=pos,
                age=r["age"],
                rotation_rank=rank,
                usage=usage,
                off_impact=off,
                def_impact=dfn,
                fg3_pct=float(np.clip(
                    rng.normal(0.363 - 0.028 * bigness + shoot_bonus, 0.034), 0.20, 0.47)),
                fg2_pct=float(np.clip(
                    rng.normal(0.520 + 0.085 * bigness + shoot_bonus, 0.035), 0.36, 0.72)),
                ft_pct=float(np.clip(rng.normal(0.787 - 0.075 * bigness, 0.085), 0.42, 0.95)),
                fg3a_rate=float(np.clip(rng.normal(0.455 - 0.30 * bigness, 0.15), 0.01, 0.82)),
                ft_rate=float(np.clip(rng.normal(0.225 + 0.07 * bigness, 0.075), 0.03, 0.62)),
                tov_rate=float(np.clip(
                    rng.normal(0.118 + 0.016 * (usage - 0.20) / 0.05
                               - _TOV_RATE_PER_IMPACT * off, 0.022), 0.04, 0.24)),
                ast_skill=float(np.clip(
                    rng.normal(0.62 - 0.42 * bigness + _AST_PER_OFF_IMPACT * off, 0.20),
                    0.03, 1.55)),
                orb_skill=float(np.clip(rng.normal(0.30 + 0.95 * bigness, 0.25), 0.02, 2.1)),
                drb_skill=float(np.clip(
                    rng.normal(0.55 + 1.05 * bigness + _DRB_PER_DEF_IMPACT * dfn, 0.26),
                    0.05, 2.6)),
                stl_skill=float(np.clip(
                    rng.normal(0.95 - 0.30 * bigness + _STL_PER_DEF_IMPACT * dfn, 0.28),
                    0.10, 2.0)),
                blk_skill=float(np.clip(
                    rng.normal(0.22 + 1.25 * bigness + _BLK_PER_DEF_IMPACT * dfn, 0.31),
                    0.01, 2.6)),
                foul_rate=float(np.clip(rng.normal(0.028 + 0.012 * bigness, 0.009), 0.006, 0.065)),
                minutes_target=r["minutes"],
            )

    # -- schedule -----------------------------------------------------------

    def _build_schedule(self) -> pd.DataFrame:
        """Round-robin rotation, alternating home and away, on real dates."""
        rng = np.random.default_rng(self.seed + 7)
        ids = list(self._teams["team_id"])
        n = len(ids)
        rounds_needed = int(np.ceil(self.games_per_team / (n - 1)))
        fixtures: list[tuple[str, str]] = []
        wheel = ids[1:]
        for r in range(rounds_needed * (n - 1)):
            order = [ids[0]] + wheel
            half = n // 2
            for i in range(half):
                a, b = order[i], order[n - 1 - i]
                # Alternate home team by round so the home/away split balances.
                fixtures.append((a, b) if (r + i) % 2 == 0 else (b, a))
            wheel = wheel[1:] + wheel[:1]

        counts = {t: 0 for t in ids}
        chosen: list[tuple[str, str]] = []
        for home, away in fixtures:
            if counts[home] >= self.games_per_team or counts[away] >= self.games_per_team:
                continue
            chosen.append((home, away))
            counts[home] += 1
            counts[away] += 1

        start = pd.Timestamp(f"{int(self.season[:4])}-10-22")
        per_day = max(1, n // 4)
        rows = []
        for i, (home, away) in enumerate(chosen):
            day = start + pd.Timedelta(days=int(i // per_day) + int(rng.integers(0, 2)))
            rows.append({
                "game_id": f"G{i:05d}",
                "season": self.season,
                "game_date": day,
                "home_team_id": home,
                "away_team_id": away,
                "season_type": "Regular Season",
            })
        return pd.DataFrame(rows).sort_values("game_date").reset_index(drop=True)

    # -- game simulation ----------------------------------------------------

    def _rotation(self, team_id: str) -> list[PlayerLatent]:
        roster = [p for p in self._latents.values() if p.team_id == team_id]
        roster.sort(key=lambda p: p.rotation_rank)
        return roster

    def _unit_plan(self, roster: list[PlayerLatent], rng: np.random.Generator) -> list[list[str]]:
        """Build the sequence of five-man units a team uses across a game.

        Real rotations stagger starters against bench units rather than
        swapping all five at once, so the plan mixes starters and reserves.
        """
        playable = [p for p in roster if p.minutes_target > 4.0][:10]
        if len(playable) < 5:
            playable = roster[:5]
        starters = [p.player_id for p in playable[:5]]
        bench = [p.player_id for p in playable[5:]]
        units = [list(starters)]
        for _ in range(23):
            unit = list(starters)
            n_sub = int(rng.integers(1, min(4, len(bench)) + 1)) if bench else 0
            if n_sub:
                out_idx = rng.choice(5, size=n_sub, replace=False)
                subs = rng.choice(len(bench), size=n_sub, replace=False)
                for oi, si in zip(out_idx, subs):
                    unit[int(oi)] = bench[int(si)]
            units.append(unit)
        return units

    def _simulate_game(self, game: dict, rng: np.random.Generator) -> list[dict]:
        home_id, away_id = game["home_team_id"], game["away_team_id"]
        rosters = {home_id: self._rotation(home_id), away_id: self._rotation(away_id)}
        plans = {t: self._unit_plan(r, rng) for t, r in rosters.items()}
        on_floor = {t: list(plans[t][0]) for t in (home_id, away_id)}

        lat = self._latents
        events: list[dict] = []
        ev = 0
        score = {home_id: 0.0, away_id: 0.0}
        raw_clock = 0.0          # within-period, before rescaling
        period_origin = 0.0      # absolute seconds at the start of this period

        def emit(**kw):
            nonlocal ev
            events.append({
                "game_id": game["game_id"],
                "event_num": ev,
                "period": kw.pop("period"),
                "raw_seconds": raw_clock,
                "event_type": kw.pop("event_type"),
                "team_id": kw.pop("team_id", None),
                "player_id": kw.pop("player_id", None),
                "player2_id": kw.pop("player2_id", None),
                "home_score": score[home_id],
                "away_score": score[away_id],
                "points": kw.pop("points", 0.0),
                "shot_distance": kw.pop("shot_distance", np.nan),
                "shot_x": kw.pop("shot_x", np.nan),
                "shot_y": kw.pop("shot_y", np.nan),
                "shot_zone": kw.pop("shot_zone", None),
            })
            ev += 1

        # Pace is a joint property of the two teams.
        pace = float(np.clip(rng.normal(K.LEAGUE_DEFAULTS["pace"], 5.2), 84, 116))

        n_periods = 4
        period = 1
        while period <= n_periods:
            is_ot = period > 4
            period_length = (K.MINUTES_PER_OT if is_ot else 12.0) * 60.0
            # Possessions scale with period length; both teams get roughly the
            # same number because possessions alternate.
            # Both teams combined. Possession counts are tightly coupled
            # within a game (the teams alternate), so this takes only a small
            # jitter -- a Poisson draw here would add several points of
            # spurious variance to the final margin.
            target = pace * (period_length / (K.MINUTES_PER_GAME * 60.0)) * 2
            target = max(4, int(round(target + rng.normal(0.0, 1.2))))

            first_event = len(events)
            raw_clock = 0.0
            emit(period=period, event_type="period_start", team_id=None)

            # Substitution checkpoints inside the period, expressed as a
            # fraction of the possessions to be played. Real rotations stagger
            # rather than swapping all five at a whistle.
            checkpoints = sorted(rng.uniform(0.12, 0.92, size=3))
            plan_cursor = {home_id: (period - 1) * 3, away_id: (period - 1) * 3}
            for t in (home_id, away_id):
                idx = min(len(plans[t]) - 1, plan_cursor[t])
                self._apply_subs(on_floor, t, plans[t][idx], emit, period)

            offense = home_id if period % 2 else away_id
            completed = 0
            trips = 0
            next_cp = 0
            while completed < target and trips < target * 3:
                frac = completed / max(1, target)
                while next_cp < len(checkpoints) and frac >= checkpoints[next_cp]:
                    for t in (home_id, away_id):
                        plan_cursor[t] += 1
                        idx = min(len(plans[t]) - 1, plan_cursor[t])
                        self._apply_subs(on_floor, t, plans[t][idx], emit, period)
                    next_cp += 1

                defense = away_id if offense == home_id else home_id
                raw_clock += float(np.clip(rng.gamma(6.0, 2.35), 2.5, 24.0))
                margin = abs(score[home_id] - score[away_id])
                late = period >= 4 and completed > target * 0.55
                damping = 1.0
                if late and margin > 18:
                    damping = float(np.clip(1.0 - (margin - 18) / 25.0, 0.25, 1.0))
                nxt = self._simulate_possession(
                    offense, defense, on_floor, lat, rng, emit, period, score,
                    home_id, blowout_damping=damping,
                )
                trips += 1
                if nxt != offense:
                    completed += 1       # only a change of hands ends a possession
                offense = nxt

            emit(period=period, event_type="period_end", team_id=None)

            # Rescale this period's raw clock so the period spans exactly its
            # real length. Without this, team minutes do not sum to 240.
            span = max(1e-6, events[-1]["raw_seconds"] - events[first_event]["raw_seconds"])
            for e in events[first_event:]:
                frac = (e["raw_seconds"] - events[first_event]["raw_seconds"]) / span
                e["seconds_elapsed"] = round(period_origin + frac * period_length, 3)
            period_origin += period_length

            if period == n_periods and abs(score[home_id] - score[away_id]) < 0.5:
                n_periods += 1  # overtime
            period += 1

        for e in events:
            e.pop("raw_seconds", None)
        return events

    @staticmethod
    def _apply_subs(on_floor, team_id, target_unit, emit, period) -> None:
        current = set(on_floor[team_id])
        target = set(target_unit)
        going_out = sorted(current - target)
        coming_in = sorted(target - current)
        for out_p, in_p in zip(going_out, coming_in):
            emit(period=period, event_type="substitution", team_id=team_id,
                 player_id=out_p, player2_id=in_p)
        # Sorted, not list(target): set iteration order over strings varies
        # with Python's per-process hash seed, and the on-floor order feeds
        # the weighted draw that picks who uses each possession. Without this
        # the same seed produces different games in different processes.
        on_floor[team_id] = sorted(target)

    def _simulate_possession(
        self, offense, defense, on_floor, lat, rng, emit, period, score, home_id,
        blowout_damping: float = 1.0,
    ) -> str:
        """Play one possession. Returns the team with the ball next."""
        off_players = [lat[p] for p in on_floor[offense]]
        def_players = [lat[p] for p in on_floor[defense]]

        # Lineup-level quality shifts outcome probabilities, which is what makes
        # on/off, RAPM and the lineup model recoverable from this data.
        # Lineup quality edge in points per 100 possessions: what this offense
        # is worth against what this defense takes away.
        # Only the *lift* portion of offensive impact enters here. The rest is
        # already realised through each player's own shooting and ball
        # security, and counting it twice would inflate the league.
        edge = (_LIFT_SHARE * sum(p.off_impact for p in off_players)
                - sum(p.def_impact for p in def_players))
        # Home court advantage, split across both ends so it shows up in
        # efficiency rather than only in the final score.
        edge += HOME_EDGE if offense == home_id else -HOME_EDGE
        # Once a game is decided both benches empty, which compresses further
        # scoring differential. Without this the margin distribution has tails
        # far fatter than real basketball's.
        edge *= blowout_damping

        # Who uses the possession: usage-weighted choice.
        weights = np.array([p.usage for p in off_players], dtype=float)
        weights = weights / weights.sum()
        actor = off_players[int(rng.choice(len(off_players), p=weights))]

        # Turnover first.
        tov_p = float(np.clip(
            actor.tov_rate
            - TOV_EDGE_COEF * edge
            + 0.010 * (np.mean([p.stl_skill for p in def_players]) - 0.9),
            0.02, 0.30,
        ))
        if rng.random() < tov_p:
            emit(period=period, event_type="turnover", team_id=offense,
                 player_id=actor.player_id)
            stealer = def_players[int(rng.choice(
                len(def_players),
                p=np.array([p.stl_skill for p in def_players]) / sum(p.stl_skill for p in def_players),
            ))]
            if rng.random() < 0.52:
                emit(period=period, event_type="steal", team_id=defense,
                     player_id=stealer.player_id, player2_id=actor.player_id)
            return defense

        # Shooting foul -> free throws.
        if rng.random() < float(np.clip(actor.ft_rate * 0.40, 0.02, 0.32)):
            fouler = def_players[int(rng.choice(
                len(def_players),
                p=np.array([p.foul_rate for p in def_players]) / sum(p.foul_rate for p in def_players),
            ))]
            emit(period=period, event_type="foul", team_id=defense,
                 player_id=fouler.player_id, player2_id=actor.player_id)
            n_ft = 3 if rng.random() < 0.12 else 2
            made_last = False
            for i in range(n_ft):
                made = rng.random() < actor.ft_pct
                made_last = made
                if made:
                    score[offense] += 1
                emit(period=period, event_type="made_ft" if made else "missed_ft",
                     team_id=offense, player_id=actor.player_id,
                     points=1.0 if made else 0.0)
            if made_last:
                return defense
            return self._rebound(offense, defense, off_players, def_players, rng,
                                 emit, period)

        # Field goal attempt.
        is_three = rng.random() < actor.fg3a_rate
        base_pct = actor.fg3_pct if is_three else actor.fg2_pct
        # Defensive quality and offensive support move the make probability.
        pct = float(np.clip(base_pct + SHOOT_EDGE_COEF * edge, 0.12, 0.88))
        made = rng.random() < pct
        dist = float(np.clip(rng.normal(25.0, 2.0), 22.0, 34.0)) if is_three \
            else float(np.clip(rng.gamma(2.0, 3.2), 0.5, 21.5))
        angle = rng.uniform(0, np.pi)
        zone = ("above_break_3" if is_three and dist > 23.0 else
                "corner_3" if is_three else
                "restricted" if dist <= 4 else
                "paint" if dist <= 14 else "mid_range")
        pts = (3.0 if is_three else 2.0) if made else 0.0
        if made:
            score[offense] += pts
        etype = ("made_3" if is_three else "made_2") if made else \
                ("missed_3" if is_three else "missed_2")

        assister = None
        if made:
            helpers = [p for p in off_players if p.player_id != actor.player_id]
            ast_w = np.array([p.ast_skill for p in helpers], dtype=float)
            ast_p = float(np.clip(0.58 if is_three else 0.48, 0.05, 0.95))
            if rng.random() < ast_p and ast_w.sum() > 0:
                assister = helpers[int(rng.choice(len(helpers), p=ast_w / ast_w.sum()))].player_id

        blocker = None
        if not made and rng.random() < 0.075:
            blk_w = np.array([p.blk_skill for p in def_players], dtype=float)
            blocker = def_players[int(rng.choice(len(def_players), p=blk_w / blk_w.sum()))].player_id

        emit(period=period, event_type=etype, team_id=offense,
             player_id=actor.player_id, player2_id=assister, points=pts,
             shot_distance=dist, shot_x=dist * np.cos(angle),
             shot_y=abs(dist * np.sin(angle)), shot_zone=zone)

        if blocker:
            emit(period=period, event_type="block", team_id=defense,
                 player_id=blocker, player2_id=actor.player_id)

        if made:
            return defense
        return self._rebound(offense, defense, off_players, def_players, rng, emit, period)

    @staticmethod
    def _rebound(offense, defense, off_players, def_players, rng, emit, period) -> str:
        orb_strength = sum(p.orb_skill for p in off_players)
        drb_strength = sum(p.drb_skill for p in def_players)
        share = orb_strength / max(1e-9, orb_strength + drb_strength)
        # `share` averages _REBOUND_REFERENCE_SHARE across the league by
        # construction, so dividing by it centres the offensive rebound rate on
        # the league value while still letting good rebounding lineups beat it.
        p_orb = float(np.clip(
            K.LEAGUE_DEFAULTS["orb_rate"] * share / _REBOUND_REFERENCE_SHARE,
            0.08, 0.45,
        ))
        if rng.random() < p_orb:
            w = np.array([p.orb_skill for p in off_players], dtype=float)
            who = off_players[int(rng.choice(len(off_players), p=w / w.sum()))]
            emit(period=period, event_type="oreb", team_id=offense, player_id=who.player_id)
            return offense
        w = np.array([p.drb_skill for p in def_players], dtype=float)
        who = def_players[int(rng.choice(len(def_players), p=w / w.sum()))]
        emit(period=period, event_type="dreb", team_id=defense, player_id=who.player_id)
        return defense

    # -- public API ---------------------------------------------------------

    def _ensure_simulated(self) -> None:
        if self._pbp is not None:
            return
        schedule = self._build_schedule()
        rng = np.random.default_rng(self.seed + 11)
        all_events: list[dict] = []
        finals = []
        for row in schedule.to_dict("records"):
            events = self._simulate_game(row, rng)
            all_events.extend(events)
            last = events[-1]
            n_periods = max(e["period"] for e in events)
            finals.append({
                "game_id": row["game_id"],
                "home_pts": last["home_score"],
                "away_pts": last["away_score"],
                "overtimes": float(max(0, n_periods - 4)),
            })
        self._pbp = pd.DataFrame(all_events)
        self._games = schedule.merge(pd.DataFrame(finals), on="game_id", how="left")

    def teams(self, season: str | None = None) -> pd.DataFrame:
        return self._teams.copy()

    def players(self, season: str | None = None) -> pd.DataFrame:
        rows = [{
            "player_id": p.player_id,
            "player_name": p.name,
            "season": self.season,
            "team_id": p.team_id,
            "age": p.age,
            "position": p.position,
            "height_in": 72.0 + 4.0 * K.POSITIONS.index(p.position),
            "weight_lb": 185.0 + 12.0 * K.POSITIONS.index(p.position),
            "experience": max(0.0, p.age - 22.0),
        } for p in self._latents.values()]
        return pd.DataFrame(rows)

    def games(self, season: str | None = None, season_type: str = "Regular Season") -> pd.DataFrame:
        self._ensure_simulated()
        return self._games.copy()

    def pbp(self, season: str | None = None, game_ids=None) -> pd.DataFrame:
        self._ensure_simulated()
        out = self._pbp
        if game_ids is not None:
            out = out[out["game_id"].isin(set(game_ids))]
        return out.copy()

    def box(self, season: str | None = None, season_type: str = "Regular Season") -> pd.DataFrame:
        if self._box is None:
            from .pbp import box_from_pbp

            self._ensure_simulated()
            self._box = box_from_pbp(self._pbp, self._games, self.players())
        return self._box.copy()

    def ground_truth(self) -> pd.DataFrame:
        """The latent ratings that generated the league.

        Only synthetic sources can supply this. Tests use it to check that the
        impact models recover what actually drove the outcomes.
        """
        return pd.DataFrame([{
            "player_id": p.player_id,
            "player_name": p.name,
            "team_id": p.team_id,
            "position": p.position,
            "age": p.age,
            "rotation_rank": p.rotation_rank,
            "true_off_impact": p.off_impact,
            "true_def_impact": p.def_impact,
            "true_total_impact": p.off_impact + p.def_impact,
            "true_usage": p.usage,
            "true_fg3_pct": p.fg3_pct,
            "true_fg2_pct": p.fg2_pct,
            "true_ft_pct": p.ft_pct,
        } for p in self._latents.values()])
