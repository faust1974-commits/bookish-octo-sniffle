"""Lineup evaluation and swapping.

The naive approach to "what happens if I put these five on the floor" is to
look up the unit's observed net rating. That fails because most five-man units
have almost no sample: a unit with 40 possessions carries a standard error
around 18 points per 100, so its observed rating is mostly noise.

So this models lineup value instead of reading it off the sample. A lineup's
rating is built from:

1. **Additive impact.** Each player's offensive and defensive value, from RAPM
   where play-by-play is available and from the box model otherwise. This is
   most of the answer.
2. **Usage redistribution.** Five players' usage must total one possession.
   Compressing or stretching to fit costs efficiency, asymmetrically. See
   `impact.usage`.
3. **Fit.** Spacing, rim pressure, playmaking, rebounding and rim protection.
   Lineups that are strong across these are worth more than the sum of their
   parts; the effect is real but much smaller than the additive term, and the
   weights are deliberately modest.
4. **Coverage gaps.** A lineup with nobody who can protect the rim, or nobody
   who can create a shot, is penalised. This is what actually distinguishes a
   sensible five from five good players who cannot function together.

Every component is reported separately, so you can always see *why* a lineup
grades where it does rather than being handed a number.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations

import numpy as np
import pandas as pd

from .. import constants as K
from .usage import UsageProfile, redistribute_usage

SKILLS = ["spacing", "rim_pressure", "playmaking", "rebounding", "rim_protection"]


@dataclass
class PlayerProfile:
    """Everything the lineup model needs about one player."""

    player_id: str
    name: str = ""
    position: str = "SF"
    minutes: float = 0.0
    off_impact: float = 0.0        # points per 100 vs league average
    def_impact: float = 0.0        # positive is good defence
    usage: float = 0.20
    ts_pct: float = 0.560
    spacing: float = 0.0           # standardised skill scores
    rim_pressure: float = 0.0
    playmaking: float = 0.0
    rebounding: float = 0.0
    rim_protection: float = 0.0

    @property
    def total_impact(self) -> float:
        return self.off_impact + self.def_impact

    def usage_profile(self) -> UsageProfile:
        return UsageProfile(self.player_id, self.usage, self.ts_pct, self.minutes)


@dataclass
class LineupEvaluation:
    """A lineup's projected rating with the full component breakdown."""

    players: list[str]
    names: list[str]
    off_rating: float
    def_rating: float
    net_rating: float
    additive_off: float
    additive_def: float
    usage_effect: float
    fit_bonus: float
    coverage_penalty: float
    fit_detail: dict = field(default_factory=dict)
    usage_table: pd.DataFrame | None = None

    def explain(self) -> str:
        """A readable account of where the number came from."""
        lines = [
            f"Lineup: {', '.join(self.names or self.players)}",
            f"  Projected net rating        {self.net_rating:+7.2f} per 100",
            f"    offensive rating          {self.off_rating:7.2f}",
            f"    defensive rating          {self.def_rating:7.2f}",
            "",
            f"  additive offence            {self.additive_off:+7.2f}",
            f"  additive defence            {self.additive_def:+7.2f}",
            f"  usage redistribution        {self.usage_effect:+7.2f}",
            f"  fit bonus                   {self.fit_bonus:+7.2f}",
            f"  coverage penalty            {-self.coverage_penalty:+7.2f}",
        ]
        if self.fit_detail:
            lines.append("")
            lines.append("  fit detail (points per 100):")
            for k, v in self.fit_detail.items():
                lines.append(f"    {k:<24s}    {v:+7.2f}")
        return "\n".join(lines)


@dataclass
class SwapResult:
    """Before and after for a single substitution."""

    out_player: str
    in_player: str
    out_name: str
    in_name: str
    before: LineupEvaluation
    after: LineupEvaluation
    usage_shifts: pd.DataFrame

    @property
    def net_change(self) -> float:
        return self.after.net_rating - self.before.net_rating

    def explain(self) -> str:
        parts = [
            f"Swap: OUT {self.out_name or self.out_player}  ->  IN {self.in_name or self.in_player}",
            f"  net rating {self.before.net_rating:+.2f}  ->  {self.after.net_rating:+.2f}"
            f"   ({self.net_change:+.2f})",
            f"  offence    {self.before.off_rating:.2f}  ->  {self.after.off_rating:.2f}",
            f"  defence    {self.before.def_rating:.2f}  ->  {self.after.def_rating:.2f}",
            "",
            "  usage absorbed by remaining players:",
        ]
        shifts = self.usage_shifts
        for r in shifts.itertuples(index=False):
            if r.player_id in (self.out_player, self.in_player):
                continue
            if abs(r.usage_shift) < 1e-6:
                continue
            parts.append(
                f"    {r.player_id:<10s} usage {r.usage_shift:+.3f}"
                f"   TS% {r.ts_shift:+.4f}   pts/100 {r.pts_per_100_shift:+.2f}"
            )
        return "\n".join(parts)


class LineupModel:
    """Projects five-man unit ratings and evaluates substitutions."""

    def __init__(self, profiles: dict[str, PlayerProfile], *,
                 league_off_rating: float = K.LEAGUE_DEFAULTS["off_rating"],
                 fit_weights: dict | None = None,
                 coverage_thresholds: dict | None = None):
        self.profiles = profiles
        self.league_off_rating = float(league_off_rating)
        self.fit_weights = dict(K.LINEUP_FIT_WEIGHTS if fit_weights is None else fit_weights)
        self.coverage_thresholds = dict(
            K.LINEUP_COVERAGE_THRESHOLDS if coverage_thresholds is None
            else coverage_thresholds
        )

    # -- construction -------------------------------------------------------

    @classmethod
    def from_league(cls, league, player_metrics: pd.DataFrame,
                    rapm: pd.DataFrame | None = None,
                    *, impact_column: str = "box_impact",
                    min_minutes: float = 50.0) -> "LineupModel":
        """Build profiles from computed metrics, preferring RAPM for impact.

        `player_metrics` is the frame from `metrics.box.add_all`. If `rapm` is
        supplied its offensive and defensive splits are used for the additive
        term, which is strictly better than a box estimate wherever there are
        enough possessions.
        """
        df = player_metrics[player_metrics["min"] >= min_minutes].copy()
        skills = compute_skill_scores(df)
        df = df.merge(skills, on="player_id", how="left")

        impact_map = {}
        if rapm is not None and not rapm.empty:
            for r in rapm.itertuples(index=False):
                impact_map[r.player_id] = (float(r.rapm_off), float(r.rapm_def))

        if {"team_id", "tm_pts", "tm_poss"} <= set(df.columns):
            team_level = df.drop_duplicates("team_id")
            total_pts = float(np.nansum(team_level["tm_pts"]))
            total_poss = float(np.nansum(team_level["tm_poss"]))
            league_ortg = (100.0 * total_pts / total_poss if total_poss > 0
                           else K.LEAGUE_DEFAULTS["off_rating"])
        else:
            league_ortg = K.LEAGUE_DEFAULTS["off_rating"]

        profiles: dict[str, PlayerProfile] = {}
        for r in df.itertuples(index=False):
            pid = r.player_id
            if pid in impact_map:
                off_i, def_i = impact_map[pid]
            else:
                total = float(getattr(r, impact_column, 0.0) or 0.0)
                # Without a split, assume the usual two-thirds offence tilt.
                off_i, def_i = total * 0.65, total * 0.35
            profiles[pid] = PlayerProfile(
                player_id=pid,
                name=str(getattr(r, "player_name", "") or pid),
                position=str(getattr(r, "position", "SF") or "SF"),
                minutes=float(getattr(r, "min", 0.0) or 0.0),
                off_impact=off_i,
                def_impact=def_i,
                usage=float(np.clip(getattr(r, "usage_rate", 0.20) or 0.20, 0.05, 0.45)),
                ts_pct=float(np.clip(getattr(r, "ts_pct", 0.56) or 0.56, 0.35, 0.78)),
                **{s: float(getattr(r, s, 0.0) or 0.0) for s in SKILLS},
            )
        return cls(profiles, league_off_rating=league_ortg)

    # -- evaluation ---------------------------------------------------------

    def _require(self, player_ids) -> list[PlayerProfile]:
        missing = [p for p in player_ids if p not in self.profiles]
        if missing:
            raise KeyError(f"no profile for player(s): {missing}")
        return [self.profiles[p] for p in player_ids]

    def evaluate(self, player_ids, *, opponent: list[str] | None = None,
                 detail: bool = True) -> LineupEvaluation:
        """Project a five-man unit's offensive, defensive and net rating."""
        player_ids = list(player_ids)
        if len(player_ids) != K.PLAYERS_ON_FLOOR:
            raise ValueError(
                f"a lineup is {K.PLAYERS_ON_FLOOR} players, got {len(player_ids)}"
            )
        if len(set(player_ids)) != len(player_ids):
            raise ValueError("a lineup cannot contain the same player twice")
        squad = self._require(player_ids)

        additive_off = float(sum(p.off_impact for p in squad))
        additive_def = float(sum(p.def_impact for p in squad))

        usage_table = redistribute_usage([p.usage_profile() for p in squad])
        usage_effect = float(usage_table["pts_per_100_effect"].sum())

        fit_detail = {}
        fit_bonus = 0.0
        for skill in SKILLS:
            values = np.array([getattr(p, skill) for p in squad], dtype=float)
            weight = self.fit_weights.get(skill, 0.0)
            contribution = weight * float(values.mean())
            fit_detail[skill] = contribution
            fit_bonus += contribution

        coverage_penalty = self._coverage_penalty(squad)

        # Redundancy: five players who all want the ball are worth less than
        # their parts. Concentration of usage is already priced by the
        # redistribution above; this prices concentration of *creation*.
        playmaking = np.array([p.playmaking for p in squad], dtype=float)
        creation_spread = float(playmaking.std())
        redundancy = 0.0
        if creation_spread < K.LINEUP_REDUNDANCY_THRESHOLD:
            redundancy = K.LINEUP_REDUNDANCY_PENALTY * (
                K.LINEUP_REDUNDANCY_THRESHOLD - creation_spread)
        coverage_penalty += redundancy
        fit_detail["redundancy"] = -redundancy

        off_rating = (self.league_off_rating + additive_off + usage_effect
                      + fit_bonus - coverage_penalty)
        def_rating = self.league_off_rating - additive_def
        if opponent is not None:
            opp = self._require(list(opponent))
            # Facing a specific opponent, our offence is met by their defence
            # and vice versa.
            off_rating -= float(sum(p.def_impact for p in opp))
            def_rating += float(sum(p.off_impact for p in opp))

        return LineupEvaluation(
            players=player_ids,
            names=[p.name for p in squad],
            off_rating=off_rating,
            def_rating=def_rating,
            net_rating=off_rating - def_rating,
            additive_off=additive_off,
            additive_def=additive_def,
            usage_effect=usage_effect,
            fit_bonus=fit_bonus,
            coverage_penalty=coverage_penalty,
            fit_detail=fit_detail if detail else {},
            usage_table=usage_table if detail else None,
        )

    def _coverage_penalty(self, squad: list[PlayerProfile]) -> float:
        """Charge a lineup for skills nobody on it provides."""
        penalty = 0.0
        for skill, threshold in self.coverage_thresholds.items():
            best = max(getattr(p, skill) for p in squad)
            if best < threshold:
                weight = self.fit_weights.get(skill, 1.0)
                penalty += weight * (threshold - best) * 1.5
        return float(penalty)

    # -- swapping -----------------------------------------------------------

    def swap(self, player_ids, out_player: str, in_player: str,
             *, opponent: list[str] | None = None) -> SwapResult:
        """Replace one player and report the full consequence."""
        player_ids = list(player_ids)
        if out_player not in player_ids:
            raise ValueError(f"{out_player!r} is not in this lineup")
        if in_player in player_ids:
            raise ValueError(f"{in_player!r} is already in this lineup")
        after_ids = [in_player if p == out_player else p for p in player_ids]

        before = self.evaluate(player_ids, opponent=opponent)
        after = self.evaluate(after_ids, opponent=opponent)

        shifts = before.usage_table[["player_id", "adjusted_usage", "adjusted_ts_pct",
                                     "pts_per_100_effect"]].merge(
            after.usage_table[["player_id", "adjusted_usage", "adjusted_ts_pct",
                               "pts_per_100_effect"]],
            on="player_id", how="outer", suffixes=("_before", "_after"))
        shifts["usage_shift"] = (shifts["adjusted_usage_after"].fillna(0.0)
                                 - shifts["adjusted_usage_before"].fillna(0.0))
        shifts["ts_shift"] = (shifts["adjusted_ts_pct_after"]
                              - shifts["adjusted_ts_pct_before"])
        shifts["pts_per_100_shift"] = (shifts["pts_per_100_effect_after"].fillna(0.0)
                                       - shifts["pts_per_100_effect_before"].fillna(0.0))

        return SwapResult(
            out_player=out_player, in_player=in_player,
            out_name=self.profiles[out_player].name,
            in_name=self.profiles[in_player].name,
            before=before, after=after, usage_shifts=shifts,
        )

    def best_replacement(self, player_ids, out_player: str,
                         candidates: list[str] | None = None,
                         *, top: int = 10,
                         opponent: list[str] | None = None) -> pd.DataFrame:
        """Rank every candidate who could take one player's place."""
        player_ids = list(player_ids)
        pool = candidates if candidates is not None else list(self.profiles)
        # Callers routinely build pools by concatenating lists, so dedupe
        # here rather than returning the same candidate several times.
        pool = list(dict.fromkeys(p for p in pool if p not in player_ids))
        rows = []
        base = self.evaluate(player_ids, opponent=opponent, detail=False)
        for cand in pool:
            after_ids = [cand if p == out_player else p for p in player_ids]
            try:
                ev = self.evaluate(after_ids, opponent=opponent, detail=False)
            except KeyError:
                continue
            rows.append({
                "in_player": cand,
                "in_name": self.profiles[cand].name,
                "position": self.profiles[cand].position,
                "net_rating": ev.net_rating,
                "net_change": ev.net_rating - base.net_rating,
                "off_rating": ev.off_rating,
                "def_rating": ev.def_rating,
                "usage_effect": ev.usage_effect,
            })
        out = pd.DataFrame(rows)
        if out.empty:
            return out
        return out.nlargest(top, "net_change").reset_index(drop=True)

    def best_lineups(self, candidates: list[str], *, top: int = 10,
                     opponent: list[str] | None = None,
                     require_positions: bool = True,
                     max_combinations: int = 200_000) -> pd.DataFrame:
        """Search a candidate pool for the best five-man units.

        With ten candidates this is 252 combinations; with fifteen it is 3,003.
        `max_combinations` guards against passing a whole league by accident.
        """
        candidates = list(dict.fromkeys(c for c in candidates if c in self.profiles))
        n = len(candidates)
        if n < K.PLAYERS_ON_FLOOR:
            raise ValueError(f"need at least {K.PLAYERS_ON_FLOOR} candidates, got {n}")
        from math import comb

        total = comb(n, K.PLAYERS_ON_FLOOR)
        if total > max_combinations:
            raise ValueError(
                f"{total:,} combinations exceeds max_combinations={max_combinations:,}. "
                "Narrow the candidate pool or raise the limit."
            )

        rows = []
        for combo in combinations(candidates, K.PLAYERS_ON_FLOOR):
            if require_positions and not self.positions_viable(combo):
                continue
            ev = self.evaluate(list(combo), opponent=opponent, detail=False)
            rows.append({
                "players": list(combo),
                "names": [self.profiles[p].name for p in combo],
                "net_rating": ev.net_rating,
                "off_rating": ev.off_rating,
                "def_rating": ev.def_rating,
                "usage_effect": ev.usage_effect,
                "fit_bonus": ev.fit_bonus,
                "coverage_penalty": ev.coverage_penalty,
            })
        out = pd.DataFrame(rows)
        if out.empty:
            return out
        return out.nlargest(top, "net_rating").reset_index(drop=True)

    def positions_viable(self, player_ids) -> bool:
        """Can these five cover the five positions, allowing for versatility?

        Solved as a bipartite matching rather than by counting nominal
        positions, so a lineup of three players who can all slide between
        two spots is judged correctly.
        """
        slots = list(K.POSITIONS)
        players = [self.profiles[p] for p in player_ids]
        covers = [set(K.POSITION_COVERAGE.get(p.position, [p.position])) for p in players]

        assigned: dict[int, int] = {}

        def try_assign(i: int, seen: set[int]) -> bool:
            for s_idx, slot in enumerate(slots):
                if slot in covers[i] and s_idx not in seen:
                    seen.add(s_idx)
                    if s_idx not in assigned or try_assign(assigned[s_idx], seen):
                        assigned[s_idx] = i
                        return True
            return False

        for i in range(len(players)):
            if not try_assign(i, set()):
                return False
        return True


# ---------------------------------------------------------------------------
# Skill scores
# ---------------------------------------------------------------------------

def compute_skill_scores(player_metrics: pd.DataFrame,
                         *, min_minutes: float = 100.0) -> pd.DataFrame:
    """Derive the five fit dimensions from box-score metrics.

    Each is standardised across the qualifying population so a score of 0 is a
    league-average contributor and 1.0 is a standard deviation above.

    * **spacing** -- three-point volume weighted by accuracy. A high-volume
      35% shooter bends a defence; a 45% shooter on one attempt a game does not.
    * **rim_pressure** -- free throw rate plus two-point volume, which is the
      box-score shadow of actually attacking the basket.
    * **playmaking** -- assist rate net of turnovers.
    * **rebounding** -- total rebound rate.
    * **rim_protection** -- block rate plus defensive rebound rate.
    """
    df = player_metrics
    have = df["min"] >= min_minutes

    def z(series: pd.Series) -> np.ndarray:
        values = series.to_numpy(dtype=float)
        pool = values[have.to_numpy() & np.isfinite(values)]
        if pool.size < 2:
            return np.zeros(len(values))
        mean, sd = float(pool.mean()), float(pool.std())
        if sd <= 0:
            return np.zeros(len(values))
        return np.nan_to_num((values - mean) / sd, nan=0.0)

    fg3a_rate = df.get("fg3a_rate", pd.Series(0.0, index=df.index)).fillna(0.0)
    fg3_pct = df.get("fg3_pct", pd.Series(0.0, index=df.index)).fillna(0.0)
    # Shrink the percentage toward league average by attempt volume, so a
    # small sample cannot manufacture a spacing score.
    fg3a = df.get("fg3a", pd.Series(0.0, index=df.index)).fillna(0.0)
    lg_fg3 = K.LEAGUE_DEFAULTS["fg3_pct"]
    stab = K.STABILIZATION_POINTS["fg3_pct"]
    shrunk_fg3 = (fg3a * fg3_pct + stab * lg_fg3) / (fg3a + stab)
    spacing_raw = fg3a_rate * (shrunk_fg3 / lg_fg3)

    ft_rate = df.get("ft_rate", pd.Series(0.0, index=df.index)).fillna(0.0)
    fg2_share = 1.0 - fg3a_rate
    rim_raw = ft_rate + 0.35 * fg2_share

    ast_rate = df.get("ast_rate", pd.Series(0.0, index=df.index)).fillna(0.0)
    tov_rate = df.get("tov_rate", pd.Series(0.0, index=df.index)).fillna(0.0)
    play_raw = ast_rate - 0.5 * tov_rate

    reb_raw = df.get("trb_rate", pd.Series(0.0, index=df.index)).fillna(0.0)
    blk_rate = df.get("blk_rate", pd.Series(0.0, index=df.index)).fillna(0.0)
    drb_rate = df.get("drb_rate", pd.Series(0.0, index=df.index)).fillna(0.0)
    protect_raw = blk_rate + 0.30 * drb_rate

    return pd.DataFrame({
        "player_id": df["player_id"].to_numpy(),
        "spacing": z(spacing_raw),
        "rim_pressure": z(rim_raw),
        "playmaking": z(play_raw),
        "rebounding": z(reb_raw),
        "rim_protection": z(protect_raw),
    })
