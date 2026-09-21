"""The games a team actually has to play.

A rating says how good a team is. A record says what that is worth, and the
difference between the two is the schedule: 82 games against specific
opponents, half of them at home. Two teams a point apart in net rating can
finish four wins apart because one of them plays in the harder conference.

So the upcoming schedule is carried as data rather than assumed to be
uniform. It comes from the same daily-refreshed mirror as the rosters, and
it is keyed by team abbreviation because the schedule feed and the
play-by-play feed number their teams differently.
"""

from __future__ import annotations

import pandas as pd

from ..config import Config, default_config
from . import cache
from .rosters import ESPN_TO_TRICODE, roster_season_year

SCHEDULE_URL = ("https://raw.githubusercontent.com/sportsdataverse/hoopR-nba-data"
                "/main/nba/schedules/parquet/nba_schedule_{year}.parquet")

#: A published schedule barely changes; a day is plenty.
SCHEDULE_TTL_SECONDS = 24 * 3600

#: ESPN's season_type 2 is the regular season. Preseason and playoffs do not
#: belong in a projected record.
REGULAR_SEASON = 2


class ScheduleUnavailable(RuntimeError):
    """No schedule published for that season yet."""


def fetch(season: str, cfg: Config | None = None,
          *, refresh: bool = False) -> pd.DataFrame:
    """The regular-season schedule for `season`, one row per game."""
    cfg = cfg or default_config()
    year = roster_season_year(season)
    key = cache.cache_key("nba-schedule", year=year)

    if not refresh:
        cached = cache.read(key, cfg, ttl=SCHEDULE_TTL_SECONDS)
        if cached is not None:
            return cached

    url = SCHEDULE_URL.format(year=year)
    try:
        raw = pd.read_parquet(url)
    except Exception as exc:
        stale = cache.read(key, cfg, ttl=-1)
        if stale is not None:
            return stale
        raise ScheduleUnavailable(f"no schedule at {url}: {exc}") from exc

    frame = _normalise(raw, season)
    cache.write(key, frame, cfg)
    return frame


def _tri(series: pd.Series) -> pd.Series:
    code = series.astype(str).str.upper()
    return code.map(lambda c: ESPN_TO_TRICODE.get(c, c))


def _normalise(raw: pd.DataFrame, season: str) -> pd.DataFrame:
    games = raw[raw["season_type"] == REGULAR_SEASON].copy()
    out = pd.DataFrame({
        "home": _tri(games["home_abbreviation"]),
        "away": _tri(games["away_abbreviation"]),
        "date": pd.to_datetime(games["game_date"]).dt.strftime("%Y-%m-%d"),
        "neutral": games.get("neutral_site", False).astype(bool),
        "season": season,
    })
    # The feed carries an All-Star placeholder or two under real-looking
    # team codes; a game needs two actual teams to count.
    out = out[out["home"] != out["away"]]
    return out.sort_values("date").reset_index(drop=True)


def games_per_team(schedule: pd.DataFrame) -> pd.Series:
    """How many games each team is down for -- a sanity check worth running."""
    return pd.concat([schedule["home"], schedule["away"]]).value_counts()
