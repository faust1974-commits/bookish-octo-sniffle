"""Canonical table schemas.

Every data source, real or synthetic, must produce these exact frames. That is
the whole point of the adapter layer: the metric, impact and simulation code
never knows or cares whether the numbers came from stats.nba.com, a CSV export,
a paid feed, or a generator.

Columns marked OPTIONAL may be absent; code that uses them must degrade
gracefully (and the `require` helper below makes that explicit).
"""

from __future__ import annotations

import pandas as pd

# ---------------------------------------------------------------------------
# Table: players  -- one row per player per season
# ---------------------------------------------------------------------------
PLAYERS = {
    "player_id": "string",
    "player_name": "string",
    "season": "string",          # "2023-24"
    "team_id": "string",
    "age": "float64",
    "position": "string",        # one of constants.POSITIONS
    "height_in": "float64",      # OPTIONAL
    "weight_lb": "float64",      # OPTIONAL
    "experience": "float64",     # OPTIONAL, seasons played
}

# ---------------------------------------------------------------------------
# Table: teams  -- one row per team per season
# ---------------------------------------------------------------------------
TEAMS = {
    "team_id": "string",
    "team_name": "string",
    "team_abbrev": "string",
    "season": "string",
    "conference": "string",      # "East" / "West"
    "division": "string",        # OPTIONAL
}

# ---------------------------------------------------------------------------
# Table: games  -- one row per game
# ---------------------------------------------------------------------------
GAMES = {
    "game_id": "string",
    "season": "string",
    "game_date": "datetime64[ns]",
    "home_team_id": "string",
    "away_team_id": "string",
    "home_pts": "float64",
    "away_pts": "float64",
    "overtimes": "float64",
    "season_type": "string",     # "Regular Season" / "Playoffs" / "Play-In"
    "home_rest_days": "float64",  # OPTIONAL, derived by loaders.add_rest
    "away_rest_days": "float64",  # OPTIONAL
}

# ---------------------------------------------------------------------------
# Table: box  -- one row per player per game (player box score)
# ---------------------------------------------------------------------------
BOX = {
    "game_id": "string",
    "player_id": "string",
    "team_id": "string",
    "opponent_team_id": "string",
    "season": "string",
    "is_home": "bool",
    "started": "bool",
    "min": "float64",
    "fgm": "float64",
    "fga": "float64",
    "fg3m": "float64",
    "fg3a": "float64",
    "ftm": "float64",
    "fta": "float64",
    "orb": "float64",
    "drb": "float64",
    "ast": "float64",
    "stl": "float64",
    "blk": "float64",
    "tov": "float64",
    "pf": "float64",
    "pts": "float64",
    "plus_minus": "float64",     # OPTIONAL
}

# ---------------------------------------------------------------------------
# Table: team_box  -- one row per team per game
# ---------------------------------------------------------------------------
TEAM_BOX = dict(BOX)
TEAM_BOX.pop("player_id")
TEAM_BOX.pop("started")

# ---------------------------------------------------------------------------
# Table: pbp  -- one row per play-by-play event
# ---------------------------------------------------------------------------
PBP = {
    "game_id": "string",
    "event_num": "int64",
    "period": "int64",
    "seconds_elapsed": "float64",   # since tip-off, cumulative across periods
    "event_type": "string",         # see EVENT_TYPES
    "team_id": "string",            # team responsible for the event
    "player_id": "string",          # primary actor
    "player2_id": "string",         # assister / stealer / fouled / sub-in
    "home_score": "float64",
    "away_score": "float64",
    "points": "float64",            # points scored on this event
    "shot_distance": "float64",     # OPTIONAL, feet
    "shot_x": "float64",            # OPTIONAL, court coordinates
    "shot_y": "float64",            # OPTIONAL
    "shot_zone": "string",          # OPTIONAL
}

EVENT_TYPES = [
    "made_2",
    "missed_2",
    "made_3",
    "missed_3",
    "made_ft",
    "missed_ft",
    "oreb",
    "dreb",
    "turnover",
    "steal",
    "block",
    "foul",
    "substitution",
    "period_start",
    "period_end",
    "jump_ball",
    "timeout",
]

SCORING_EVENTS = {"made_2", "made_3", "made_ft"}
SHOT_EVENTS = {"made_2", "missed_2", "made_3", "missed_3"}

# ---------------------------------------------------------------------------
# Table: lineups  -- one row per stint (a continuous span with 10 fixed players)
# Produced by data.pbp.build_stints, not by raw sources.
# ---------------------------------------------------------------------------
STINTS = {
    "game_id": "string",
    "stint_id": "int64",
    "season": "string",
    "period": "int64",
    "start_seconds": "float64",
    "end_seconds": "float64",
    "off_team_id": "string",
    "def_team_id": "string",
    "home_lineup": "object",     # frozenset of 5 player_ids
    "away_lineup": "object",
    "home_poss": "float64",
    "away_poss": "float64",
    "home_pts": "float64",
    "away_pts": "float64",
    "garbage_time": "bool",
}

ALL_SCHEMAS = {
    "players": PLAYERS,
    "teams": TEAMS,
    "games": GAMES,
    "box": BOX,
    "team_box": TEAM_BOX,
    "pbp": PBP,
    "stints": STINTS,
}


class SchemaError(ValueError):
    """Raised when a frame does not satisfy a canonical schema."""


def require(frame: pd.DataFrame, columns, *, name: str = "frame") -> None:
    """Assert that `frame` carries `columns`, with a message that names them."""
    missing = [c for c in columns if c not in frame.columns]
    if missing:
        raise SchemaError(
            f"{name} is missing required column(s): {', '.join(missing)}. "
            f"Present: {', '.join(map(str, frame.columns))}"
        )


def conform(frame: pd.DataFrame, schema: dict, *, name: str = "frame",
            strict: bool = False) -> pd.DataFrame:
    """Coerce `frame` to `schema` dtypes, filling absent optional columns.

    With strict=True every schema column must already be present. Otherwise
    missing columns are created as nulls, which keeps partial feeds usable.
    """
    out = frame.copy()
    for col, dtype in schema.items():
        if col not in out.columns:
            if strict:
                raise SchemaError(f"{name} is missing required column {col!r}")
            out[col] = pd.Series([pd.NA] * len(out), index=out.index)
        try:
            if dtype == "bool":
                out[col] = out[col].fillna(False).astype(bool)
            elif dtype.startswith("datetime"):
                out[col] = pd.to_datetime(out[col], errors="coerce")
            elif dtype == "object":
                pass
            elif dtype == "int64":
                out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0).astype("int64")
            elif dtype == "float64":
                out[col] = pd.to_numeric(out[col], errors="coerce").astype("float64")
            else:
                out[col] = out[col].astype("string")
        except (TypeError, ValueError) as exc:  # pragma: no cover - defensive
            raise SchemaError(f"{name}.{col} could not be cast to {dtype}: {exc}") from exc
    ordered = [c for c in schema if c in out.columns]
    extra = [c for c in out.columns if c not in schema]
    return out[ordered + extra]
