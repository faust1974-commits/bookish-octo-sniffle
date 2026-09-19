"""Play-by-play parsing: lineups, stints, possessions, minutes, box scores.

This is the module that makes lineup-level work possible. Everything that
distinguishes a real analytics system from a box-score calculator -- on/off
splits, RAPM, five-man unit ratings, lineup swapping -- depends on knowing who
was on the floor for each possession, and that is only recoverable by walking
the event log and tracking substitutions.

Possessions are counted exactly by following the ball, not estimated with the
FGA + 0.44*FTA - ORB + TOV formula. The estimator is still available in
`metrics.possessions` for box-score-only sources.
"""

from __future__ import annotations

from collections import defaultdict

import numpy as np
import pandas as pd

from .. import constants as K

# Events after which the offensive team keeps the ball.
_OFFENSE_EVENTS = {
    "made_2", "missed_2", "made_3", "missed_3", "made_ft", "missed_ft",
    "turnover", "oreb",
}
# Events recorded against the defensive team.
_DEFENSE_EVENTS = {"dreb", "steal", "block", "foul"}

_TERMINATES = {"made_2", "made_3", "turnover"}


def _is_id(value) -> bool:
    """True when `value` is a usable player or team id.

    Worth a helper rather than a bare truth test: missing ids arrive as None
    from synthetic data, as NaN once a frame has been through pandas, and as
    the empty string or the literal "0" from stats.nba.com. `if value:` is
    True for NaN, which silently invents a player who appears in every game.
    """
    if value is None:
        return False
    if isinstance(value, float) and value != value:      # NaN
        return False
    text = str(value).strip()
    return text not in ("", "0", "nan", "None", "<NA>")


class LineupError(ValueError):
    """Raised when substitutions cannot be reconciled into five-man units."""


def infer_starters(game_pbp: pd.DataFrame) -> dict[str, set[str]]:
    """Recover each team's opening five from the event log.

    A player is a starter if, before they are ever substituted *in*, they
    either record an event or are substituted *out*. This is the standard
    heuristic and it is exact whenever every starter touches the log before
    being replaced -- which in practice is nearly always, and always in
    synthetic data. Teams that still come up short are padded with the first
    players seen, and teams that come up long keep the earliest five.
    """
    seen_in: dict[str, set[str]] = defaultdict(set)
    starters: dict[str, set[str]] = defaultdict(set)
    order: dict[str, list[str]] = defaultdict(list)

    for row in game_pbp.itertuples(index=False):
        etype = row.event_type
        team = row.team_id
        if etype == "substitution":
            out_p, in_p = row.player_id, row.player2_id
            if _is_id(out_p) and out_p not in seen_in[team]:
                starters[team].add(out_p)
            if _is_id(in_p):
                seen_in[team].add(in_p)
            continue
        if etype in ("period_start", "period_end", "jump_ball", "timeout"):
            continue
        actor = row.player_id
        if _is_id(actor) and _is_id(team):
            # An actor's own team is the event team for offensive events and
            # the defensive team's own player for defensive events; either way
            # the player belongs to `team`.
            if actor not in seen_in[team]:
                starters[team].add(actor)
            if actor not in order[team]:
                order[team].append(actor)

    resolved: dict[str, set[str]] = {}
    for team, five in starters.items():
        if len(five) > K.PLAYERS_ON_FLOOR:
            ranked = [p for p in order[team] if p in five]
            ranked += [p for p in sorted(five) if p not in ranked]
            five = set(ranked[: K.PLAYERS_ON_FLOOR])
        elif len(five) < K.PLAYERS_ON_FLOOR:
            for cand in order[team]:
                if len(five) >= K.PLAYERS_ON_FLOOR:
                    break
                five.add(cand)
        resolved[team] = set(five)
    return resolved


def reconstruct_lineups(pbp: pd.DataFrame) -> pd.DataFrame:
    """Attach the on-floor five for both teams to every event.

    Returns `pbp` with added columns `home_lineup` and `away_lineup`
    (frozensets of player ids) plus `off_team_id`. Requires the games frame's
    home/away assignment, which is taken from the score columns' perspective:
    the home team is identified by the caller via `home_team_id`, so this
    function works on a pbp frame that already carries it.
    """
    if "home_team_id" not in pbp.columns:
        raise LineupError(
            "reconstruct_lineups needs home_team_id on the pbp frame; "
            "merge the games frame first or use build_stints()."
        )

    home_col: list[frozenset] = []
    away_col: list[frozenset] = []
    off_col: list[str | None] = []

    for game_id, game in pbp.groupby("game_id", sort=False):
        home_id = game["home_team_id"].iloc[0]
        away_id = game["away_team_id"].iloc[0]
        starters = infer_starters(game)
        on = {
            home_id: set(starters.get(home_id, set())),
            away_id: set(starters.get(away_id, set())),
        }
        offense: str | None = None
        for row in game.itertuples(index=False):
            etype = row.event_type
            if etype == "substitution":
                team = row.team_id
                if team in on:
                    on[team].discard(row.player_id)
                    if _is_id(row.player2_id):
                        on[team].add(row.player2_id)
            elif etype in _OFFENSE_EVENTS:
                offense = row.team_id
            elif etype in _DEFENSE_EVENTS:
                offense = away_id if row.team_id == home_id else home_id
            home_col.append(frozenset(on[home_id]))
            away_col.append(frozenset(on[away_id]))
            off_col.append(offense)

    out = pbp.copy()
    out["home_lineup"] = home_col
    out["away_lineup"] = away_col
    out["off_team_id"] = off_col
    return out


def _possession_flags(game: pd.DataFrame, home_id: str, away_id: str) -> np.ndarray:
    """Mark events that end a possession, and for which team.

    Returns an array of team ids (or None) the same length as `game`, where a
    non-null entry means "a possession by this team ended on this event".
    """
    n = len(game)
    ends: list[str | None] = [None] * n
    etypes = game["event_type"].to_numpy()
    teams = game["team_id"].to_numpy()

    for i in range(n):
        et = etypes[i]
        team = teams[i]
        if et in _TERMINATES:
            ends[i] = team
        elif et == "dreb":
            # The possession that just ended belonged to the other team.
            ends[i] = away_id if team == home_id else home_id
        elif et == "made_ft":
            # A made free throw ends the possession only if it is the last of
            # the trip. Substitutions are routinely whistled between free
            # throws, so look past them to find the real next event.
            nxt = None
            for j in range(i + 1, min(n, i + 8)):
                if etypes[j] not in ("substitution", "timeout"):
                    nxt = etypes[j]
                    break
            if nxt not in ("made_ft", "missed_ft"):
                ends[i] = team
        elif et == "period_end":
            # Whatever trip was live when the buzzer sounded is not a
            # possession; the standard treatment is to drop it.
            continue
    return np.array(ends, dtype=object)


def mark_garbage_time(game: pd.DataFrame, total_seconds: float) -> np.ndarray:
    """Boolean mask of events played in garbage time.

    Garbage time is defined by margin relative to time remaining, only inside
    the final stretch of the game, per constants.GARBAGE_TIME_*.
    """
    remaining = total_seconds - game["seconds_elapsed"].to_numpy()
    margin = np.abs(
        game["home_score"].to_numpy() - game["away_score"].to_numpy()
    )
    threshold = K.GARBAGE_TIME_MARGIN + K.GARBAGE_TIME_SLOPE * remaining
    return (remaining <= K.GARBAGE_TIME_MAX_SECONDS) & (margin > threshold)


def build_stints(pbp: pd.DataFrame, games: pd.DataFrame) -> pd.DataFrame:
    """Collapse play-by-play into stints: spans with both lineups fixed.

    Each row records the ten players on the floor, how many possessions each
    team used, how many points each scored, and whether the span was garbage
    time. This frame is the input to on/off, RAPM and the lineup model.
    """
    gmeta = games.set_index("game_id")[["home_team_id", "away_team_id", "season"]]
    rows: list[dict] = []
    stint_id = 0

    for game_id, game in pbp.groupby("game_id", sort=False):
        if game_id not in gmeta.index:
            continue
        meta = gmeta.loc[game_id]
        home_id, away_id = meta["home_team_id"], meta["away_team_id"]
        game = game.sort_values("event_num")
        starters = infer_starters(game)
        on = {
            home_id: set(starters.get(home_id, set())),
            away_id: set(starters.get(away_id, set())),
        }
        total_seconds = float(game["seconds_elapsed"].max())
        ends = _possession_flags(game, home_id, away_id)
        garbage = mark_garbage_time(game, total_seconds)

        cur = {
            "start_seconds": 0.0,
            "period": int(game["period"].iloc[0]),
            "home_poss": 0.0, "away_poss": 0.0,
            "home_pts": 0.0, "away_pts": 0.0,
            "garbage": 0, "n": 0,
        }
        home_five = frozenset(on[home_id])
        away_five = frozenset(on[away_id])

        def flush(end_seconds: float):
            nonlocal stint_id, cur, home_five, away_five
            if cur["n"] == 0 and cur["home_poss"] == 0 and cur["away_poss"] == 0:
                return
            rows.append({
                "game_id": game_id,
                "stint_id": stint_id,
                "season": meta["season"],
                "period": cur["period"],
                "start_seconds": cur["start_seconds"],
                "end_seconds": end_seconds,
                "home_team_id": home_id,
                "away_team_id": away_id,
                "home_lineup": home_five,
                "away_lineup": away_five,
                "home_poss": cur["home_poss"],
                "away_poss": cur["away_poss"],
                "home_pts": cur["home_pts"],
                "away_pts": cur["away_pts"],
                "garbage_time": bool(cur["garbage"] > cur["n"] / 2) if cur["n"] else False,
            })
            stint_id += 1

        prev_seconds = 0.0
        for i, row in enumerate(game.itertuples(index=False)):
            if row.event_type == "substitution":
                flush(float(row.seconds_elapsed))
                team = row.team_id
                if team in on:
                    on[team].discard(row.player_id)
                    if _is_id(row.player2_id):
                        on[team].add(row.player2_id)
                home_five = frozenset(on[home_id])
                away_five = frozenset(on[away_id])
                cur = {
                    "start_seconds": float(row.seconds_elapsed),
                    "period": int(row.period),
                    "home_poss": 0.0, "away_poss": 0.0,
                    "home_pts": 0.0, "away_pts": 0.0,
                    "garbage": 0, "n": 0,
                }
                prev_seconds = float(row.seconds_elapsed)
                continue

            ending = ends[i]
            if ending == home_id:
                cur["home_poss"] += 1
            elif ending == away_id:
                cur["away_poss"] += 1
            pts = float(row.points or 0.0)
            if pts:
                if row.team_id == home_id:
                    cur["home_pts"] += pts
                else:
                    cur["away_pts"] += pts
            cur["n"] += 1
            if garbage[i]:
                cur["garbage"] += 1
            prev_seconds = float(row.seconds_elapsed)

        flush(prev_seconds)

    out = pd.DataFrame(rows)
    if out.empty:
        return out
    out["seconds"] = (out["end_seconds"] - out["start_seconds"]).clip(lower=0.0)
    return out


def minutes_from_stints(stints: pd.DataFrame) -> pd.DataFrame:
    """Player-game minutes, summed over the stints each player appeared in."""
    records: dict[tuple[str, str, str], float] = defaultdict(float)
    for row in stints.itertuples(index=False):
        secs = float(row.seconds)
        for pid in row.home_lineup:
            records[(row.game_id, pid, row.home_team_id)] += secs
        for pid in row.away_lineup:
            records[(row.game_id, pid, row.away_team_id)] += secs
    rows = [{"game_id": g, "player_id": p, "team_id": t, "min": s / 60.0}
            for (g, p, t), s in records.items()]
    return pd.DataFrame(rows)


def box_from_pbp(pbp: pd.DataFrame, games: pd.DataFrame,
                 players: pd.DataFrame | None = None) -> pd.DataFrame:
    """Derive the player-game box score from the event log.

    Minutes come from reconstructed stints, counting stats from the events, so
    the box score and the lineup data are guaranteed to agree.
    """
    gmeta = games.set_index("game_id")[["home_team_id", "away_team_id", "season"]]
    stints = build_stints(pbp, games)
    mins = minutes_from_stints(stints) if not stints.empty else pd.DataFrame(
        columns=["game_id", "player_id", "team_id", "min"]
    )

    counts: dict[tuple[str, str], dict] = {}

    def slot(game_id, pid, team_id):
        key = (game_id, pid)
        if key not in counts:
            counts[key] = {
                "game_id": game_id, "player_id": pid, "team_id": team_id,
                "fgm": 0.0, "fga": 0.0, "fg3m": 0.0, "fg3a": 0.0,
                "ftm": 0.0, "fta": 0.0, "orb": 0.0, "drb": 0.0, "ast": 0.0,
                "stl": 0.0, "blk": 0.0, "tov": 0.0, "pf": 0.0, "pts": 0.0,
            }
        return counts[key]

    for row in pbp.itertuples(index=False):
        et, pid, team = row.event_type, row.player_id, row.team_id
        if et == "substitution" or not _is_id(pid):
            continue
        rec = slot(row.game_id, pid, team)
        if et in ("made_2", "missed_2"):
            rec["fga"] += 1
            if et == "made_2":
                rec["fgm"] += 1
                rec["pts"] += 2
        elif et in ("made_3", "missed_3"):
            rec["fga"] += 1
            rec["fg3a"] += 1
            if et == "made_3":
                rec["fgm"] += 1
                rec["fg3m"] += 1
                rec["pts"] += 3
        elif et in ("made_ft", "missed_ft"):
            rec["fta"] += 1
            if et == "made_ft":
                rec["ftm"] += 1
                rec["pts"] += 1
        elif et == "oreb":
            rec["orb"] += 1
        elif et == "dreb":
            rec["drb"] += 1
        elif et == "turnover":
            rec["tov"] += 1
        elif et == "steal":
            rec["stl"] += 1
        elif et == "block":
            rec["blk"] += 1
        elif et == "foul":
            rec["pf"] += 1
        # Assists are credited to player2 on made field goals.
        if et in ("made_2", "made_3") and _is_id(row.player2_id):
            arec = slot(row.game_id, row.player2_id, team)
            arec["ast"] += 1

    counted = pd.DataFrame(list(counts.values()))
    if counted.empty and mins.empty:
        return counted

    # Start from who was on the floor, not from who recorded a statistic. A
    # player can play a stint without registering a single event, and building
    # the box score from the event log alone silently drops his minutes -- which
    # then makes the team fall short of 240.
    stat_cols = [c for c in counted.columns if c not in ("game_id", "player_id", "team_id")]
    box = mins[["game_id", "player_id", "team_id", "min"]].merge(
        counted.drop(columns=["team_id"], errors="ignore"),
        on=["game_id", "player_id"], how="outer",
    )
    box["min"] = box["min"].fillna(0.0)
    for col in stat_cols:
        box[col] = box[col].fillna(0.0)
    if box["team_id"].isna().any():
        # Anyone present only in the event log still needs a team.
        fallback = counted.set_index(["game_id", "player_id"])["team_id"]
        missing = box["team_id"].isna()
        keys = list(zip(box.loc[missing, "game_id"], box.loc[missing, "player_id"]))
        box.loc[missing, "team_id"] = [fallback.get(k) for k in keys]

    meta = gmeta.reset_index()
    box = box.merge(meta, on="game_id", how="left")
    box["is_home"] = box["team_id"] == box["home_team_id"]
    box["opponent_team_id"] = np.where(box["is_home"], box["away_team_id"], box["home_team_id"])
    box = box.drop(columns=["home_team_id", "away_team_id"])

    # Starters: the five with the most minutes per team-game is a proxy that
    # matches the truth in synthetic data and is close in real data. Real
    # sources supply the flag directly and should override it.
    box["_rank"] = box.groupby(["game_id", "team_id"])["min"].rank(
        ascending=False, method="first"
    )
    box["started"] = box["_rank"] <= K.PLAYERS_ON_FLOOR
    box = box.drop(columns=["_rank"])
    box["plus_minus"] = np.nan
    return box
