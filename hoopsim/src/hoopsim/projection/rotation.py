"""Minutes allocation and rotation planning.

A team has exactly 240 minutes to hand out (48 minutes times five positions),
and every one of them must go to somebody. That constraint is what makes
rotation design a real optimization rather than a ranking exercise: playing
your best player more means playing someone else less, and the marginal
minute always comes from somewhere.

Three pieces here:

* `allocate_minutes` decides how many minutes each player gets, subject to
  per-player caps and a concentration setting that controls how top-heavy the
  rotation is.
* `build_rotation_plan` turns those totals into an actual sequence of five-man
  units, staggering starters against bench units the way real rotations do
  rather than substituting all five at once.
* `evaluate_rotation` and `optimize_rotation` score a plan with the lineup
  model -- so fit, usage redistribution and coverage gaps all feed back into
  how the minutes should be distributed.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .. import constants as K


@dataclass
class RotationConstraints:
    """Limits a rotation has to respect."""

    total_minutes: float = K.TEAM_MINUTES_PER_GAME       # 240
    max_minutes_per_player: float = 38.0
    min_minutes_if_used: float = 6.0
    max_players: int = 10
    #: 0 spreads minutes evenly among the rotation, 1 concentrates them on the
    #: best players up to the cap. Real NBA rotations sit around 0.6-0.75.
    concentration: float = 0.7
    #: Second night of a back-to-back: scale the cap for heavy-minutes players.
    back_to_back_cap: float | None = None


def allocate_minutes(values: dict[str, float],
                     constraints: RotationConstraints | None = None,
                     *, locked: dict[str, float] | None = None) -> pd.Series:
    """Distribute team minutes across players according to their value.

    `values` maps player_id to a value score (impact per 100, or anything
    monotone in quality). Returns minutes that sum to the team total and
    respect every cap.
    """
    c = constraints or RotationConstraints()
    locked = dict(locked or {})

    ranked = sorted(values.items(), key=lambda kv: kv[1], reverse=True)
    pool = [p for p, _ in ranked if p not in locked][: max(0, c.max_players - len(locked))]
    if not pool and not locked:
        raise ValueError("no players to allocate minutes to")

    cap = c.max_minutes_per_player
    if c.back_to_back_cap is not None:
        cap = min(cap, c.back_to_back_cap)

    remaining = c.total_minutes - sum(locked.values())
    if remaining < 0:
        raise ValueError("locked minutes already exceed the team total")

    # The caps and the roster size have to be able to cover the team's minutes
    # between them. If they cannot, say so: quietly rescaling past the cap to
    # make the total work would hand back a rotation that violates the very
    # constraint the caller set.
    capacity = len(pool) * cap + sum(locked.values())
    if capacity < c.total_minutes - 1e-6:
        raise ValueError(
            f"{len(pool)} players capped at {cap:g} minutes can cover only "
            f"{capacity:g} of the {c.total_minutes:g} team minutes. Raise "
            "max_minutes_per_player, raise max_players, or supply more candidates."
        )

    if not pool:
        return pd.Series(locked, dtype=float)

    # Blend an equal split with a value-proportional split, then respect caps
    # and redistribute whatever the caps displace.
    scores = np.array([values[p] for p in pool], dtype=float)
    scores = scores - scores.min() + 1e-6        # keep weights positive
    proportional = scores / scores.sum()
    equal = np.full(len(pool), 1.0 / len(pool))
    weights = c.concentration * proportional + (1.0 - c.concentration) * equal

    minutes = weights * remaining
    for _ in range(50):
        clipped = np.clip(minutes, 0.0, cap)
        residual = remaining - clipped.sum()
        if abs(residual) < 1e-7:
            minutes = clipped
            break
        room = (clipped < cap - 1e-9) if residual > 0 else (clipped > 1e-9)
        if not room.any():
            minutes = clipped
            break
        w = weights * room
        minutes = clipped + residual * w / w.sum()
    minutes = np.clip(minutes, 0.0, cap)

    # Drop anyone under the usable-minutes floor and give their time back.
    tiny = (minutes > 0) & (minutes < c.min_minutes_if_used)
    if tiny.any():
        freed = minutes[tiny].sum()
        minutes[tiny] = 0.0
        room = (minutes > 0) & (minutes < cap - 1e-9)
        if room.any():
            w = weights * room
            minutes = minutes + freed * w / w.sum()
            minutes = np.clip(minutes, 0.0, cap)

    out = dict(locked)
    for p, m in zip(pool, minutes):
        if m > 0:
            out[p] = float(m)

    # Final touch-up so the total lands exactly on the team budget. The
    # feasibility check above guarantees there is room to do this without
    # breaching any cap, and the residual here is a rounding artefact.
    total = sum(out.values())
    residual = c.total_minutes - total
    for _ in range(20):
        if abs(residual) < 1e-9 or not out:
            break
        room = {p: (cap - m if residual > 0 else m) for p, m in out.items()}
        available = sum(v for v in room.values() if v > 1e-12)
        if available <= 1e-12:
            break
        step = min(abs(residual), available) * (1 if residual > 0 else -1)
        for p in out:
            share = max(0.0, room[p]) / available
            out[p] = min(cap, max(0.0, out[p] + step * share))
        total = sum(out.values())
        residual = c.total_minutes - total
    return pd.Series(out, dtype=float).sort_values(ascending=False)


def build_rotation_plan(minutes: pd.Series, model=None, *,
                        segments: int = 12,
                        require_positions: bool = True,
                        seed: int = 0) -> pd.DataFrame:
    """Turn minute totals into a concrete sequence of five-man units.

    The game is cut into equal segments; each segment is filled with the five
    players who have the most minutes still owed to them, preferring lineups
    that can actually cover the five positions. That naturally staggers
    starters against bench units instead of swapping all five at a whistle.
    """
    rng = np.random.default_rng(seed)
    segment_minutes = K.MINUTES_PER_GAME / segments
    owed = {p: float(m) for p, m in minutes.items() if m > 0}
    if len(owed) < K.PLAYERS_ON_FLOOR:
        raise ValueError(
            f"need at least {K.PLAYERS_ON_FLOOR} players with minutes, got {len(owed)}"
        )

    rows = []
    for seg in range(segments):
        ranked = sorted(owed.items(), key=lambda kv: kv[1] + rng.normal(0, 0.05), reverse=True)
        chosen = [p for p, _ in ranked[:K.PLAYERS_ON_FLOOR]]

        if require_positions and model is not None and not model.positions_viable(chosen):
            # Swap in the next-best candidate that makes the five legal.
            for extra, _ in ranked[K.PLAYERS_ON_FLOOR:]:
                fixed = False
                for i in range(K.PLAYERS_ON_FLOOR):
                    trial = list(chosen)
                    trial[i] = extra
                    if model.positions_viable(trial):
                        chosen = trial
                        fixed = True
                        break
                if fixed:
                    break

        for p in chosen:
            owed[p] = max(0.0, owed[p] - segment_minutes)
        rows.append({
            "segment": seg,
            "start_minute": seg * segment_minutes,
            "minutes": segment_minutes,
            "lineup": tuple(sorted(chosen)),
        })
    return pd.DataFrame(rows)


def evaluate_rotation(plan: pd.DataFrame, model, *,
                      opponent: list[str] | None = None) -> dict:
    """Score a rotation plan with the lineup model.

    Returns the minutes-weighted team rating plus the per-unit detail, so you
    can see which segments are dragging the plan down.
    """
    detail = []
    total_minutes = float(plan["minutes"].sum())
    weighted_net = 0.0
    weighted_off = 0.0
    weighted_def = 0.0
    for r in plan.itertuples(index=False):
        ev = model.evaluate(list(r.lineup), opponent=opponent, detail=False)
        share = r.minutes / total_minutes if total_minutes else 0.0
        weighted_net += share * ev.net_rating
        weighted_off += share * ev.off_rating
        weighted_def += share * ev.def_rating
        detail.append({
            "segment": r.segment,
            "start_minute": getattr(r, "start_minute", r.segment * r.minutes),
            "minutes": r.minutes,
            "lineup": r.lineup,
            "names": [model.profiles[p].name for p in r.lineup],
            "net_rating": ev.net_rating,
            "off_rating": ev.off_rating,
            "def_rating": ev.def_rating,
            "usage_effect": ev.usage_effect,
        })
    return {
        "net_rating": weighted_net,
        "off_rating": weighted_off,
        "def_rating": weighted_def,
        "segments": pd.DataFrame(detail),
    }


def optimize_rotation(model, candidates: list[str],
                      constraints: RotationConstraints | None = None,
                      *, segments: int = 12, iterations: int = 60,
                      step_minutes: float = 2.0, seed: int = 0,
                      opponent: list[str] | None = None) -> dict:
    """Hill-climb the minutes allocation to maximise projected team rating.

    Starts from a value-proportional allocation, then repeatedly moves a small
    block of minutes between two players and keeps the move if the rotation
    scores better. This respects fit and usage effects, which a pure ranking
    of player impact cannot.
    """
    c = constraints or RotationConstraints()
    rng = np.random.default_rng(seed)
    candidates = [p for p in dict.fromkeys(candidates) if p in model.profiles]
    if len(candidates) < K.PLAYERS_ON_FLOOR:
        raise ValueError(f"need at least {K.PLAYERS_ON_FLOOR} candidates")

    values = {p: model.profiles[p].total_impact for p in candidates}
    minutes = allocate_minutes(values, c)

    def score(mins: pd.Series) -> float:
        plan = build_rotation_plan(mins, model, segments=segments, seed=seed)
        return evaluate_rotation(plan, model, opponent=opponent)["net_rating"]

    best_minutes = minutes.copy()
    best_score = score(best_minutes)
    history = [best_score]

    players = list(best_minutes.index)
    for _ in range(iterations):
        if len(players) < 2:
            break
        giver, taker = rng.choice(len(players), size=2, replace=False)
        g, t = players[giver], players[taker]
        trial = best_minutes.copy()
        move = min(step_minutes, trial.get(g, 0.0))
        if move <= 0:
            continue
        if trial.get(t, 0.0) + move > c.max_minutes_per_player:
            continue
        trial[g] = trial.get(g, 0.0) - move
        trial[t] = trial.get(t, 0.0) + move
        trial = trial[trial > 1e-9]
        if len(trial) < K.PLAYERS_ON_FLOOR:
            continue
        trial_score = score(trial)
        if trial_score > best_score:
            best_minutes, best_score = trial, trial_score
            players = list(best_minutes.index)
        history.append(best_score)

    plan = build_rotation_plan(best_minutes, model, segments=segments, seed=seed)
    result = evaluate_rotation(plan, model, opponent=opponent)
    result["minutes"] = best_minutes.sort_values(ascending=False)
    result["plan"] = plan
    result["score_history"] = history
    return result
