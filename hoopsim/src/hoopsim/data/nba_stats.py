"""Adapter for stats.nba.com.

Notes on this endpoint, learned the hard way by everyone who has used it:

* It is undocumented and unsupported. Payload shapes change without notice.
* It requires a full browser-like header set. Without `Referer` and a real
  `User-Agent` it returns 403 or hangs forever.
* It rate-limits aggressively and, rather than returning 429, will start
  returning empty result sets. Hence the mandatory inter-request delay.
* Play-by-play is one request per game (~1,230 per season), so a full season
  pull takes roughly fifteen minutes on a cold cache. Completed seasons never
  change, so cached play-by-play is kept permanently.

If this host is blocked on your network, use `SyntheticSource` for development
or supply exports through `CSVSource`.
"""

from __future__ import annotations

import time

import numpy as np
import pandas as pd

from .. import constants as K
from ..config import Config, default_config
from . import cache
from .source import DataSource

BASE = "https://stats.nba.com/stats"

HEADERS = {
    "Host": "stats.nba.com",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Referer": "https://www.nba.com/",
    "Origin": "https://www.nba.com",
    "x-nba-stats-origin": "stats",
    "x-nba-stats-token": "true",
}

# EVENTMSGTYPE values in playbyplayv2.
_MSG_MADE_SHOT = 1
_MSG_MISSED_SHOT = 2
_MSG_FREE_THROW = 3
_MSG_REBOUND = 4
_MSG_TURNOVER = 5
_MSG_FOUL = 6
_MSG_SUBSTITUTION = 8
_MSG_TIMEOUT = 9
_MSG_JUMP_BALL = 10
_MSG_PERIOD_BEGIN = 12
_MSG_PERIOD_END = 13


class NBAStatsFetchError(RuntimeError):
    """Raised when the endpoint cannot be reached or returns nothing usable."""


def season_string(start_year: int) -> str:
    """2024 -> '2024-25'."""
    return f"{start_year}-{str(start_year + 1)[-2:]}"


class NBAStatsSource(DataSource):
    """Live loader for stats.nba.com, with an on-disk cache."""

    name = "stats.nba.com"
    provides_pbp = True
    provides_shot_locations = True
    provides_tracking = False

    def __init__(self, cfg: Config | None = None, *, offline: bool = False) -> None:
        self.cfg = cfg or default_config()
        self.offline = offline
        self._last_request = 0.0
        self._session = None

    # -- transport ----------------------------------------------------------

    def _get_session(self):
        if self._session is None:
            try:
                import requests
            except ImportError as exc:  # pragma: no cover
                raise NBAStatsFetchError(
                    "The `requests` package is required for live NBA data. "
                    "Install it, or use SyntheticSource / CSVSource."
                ) from exc
            self._session = requests.Session()
            self._session.headers.update(HEADERS)
        return self._session

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request
        wait = self.cfg.request_delay_seconds - elapsed
        if wait > 0:
            time.sleep(wait)
        self._last_request = time.monotonic()

    def _request(self, endpoint: str, params: dict) -> dict:
        import requests

        session = self._get_session()
        last_exc: Exception | None = None
        for attempt in range(self.cfg.max_retries):
            self._throttle()
            try:
                resp = session.get(
                    f"{BASE}/{endpoint}",
                    params=params,
                    timeout=self.cfg.request_timeout_seconds,
                )
                if resp.status_code == 200:
                    return resp.json()
                if resp.status_code in (429, 502, 503, 504):
                    last_exc = NBAStatsFetchError(
                        f"{endpoint} returned {resp.status_code}")
                else:
                    raise NBAStatsFetchError(
                        f"{endpoint} returned {resp.status_code}: {resp.text[:200]}"
                    )
            except (requests.RequestException, ValueError) as exc:
                last_exc = exc
            time.sleep(self.cfg.retry_backoff_seconds * (2 ** attempt))
        raise NBAStatsFetchError(
            f"{endpoint} failed after {self.cfg.max_retries} attempts: {last_exc}"
        )

    @staticmethod
    def _result_frame(payload: dict, index: int = 0) -> pd.DataFrame:
        sets = payload.get("resultSets") or payload.get("resultSet")
        if isinstance(sets, dict):
            sets = [sets]
        if not sets or index >= len(sets):
            return pd.DataFrame()
        rs = sets[index]
        return pd.DataFrame(rs.get("rowSet", []), columns=rs.get("headers", []))

    def _cached(self, namespace: str, endpoint: str, params: dict,
                *, permanent: bool = False) -> pd.DataFrame:
        key = cache.cache_key(namespace, **params)
        ttl = -1.0 if permanent else None
        hit = cache.read(key, self.cfg, ttl=ttl)
        if hit is not None:
            return hit
        if self.offline:
            raise NBAStatsFetchError(
                f"offline mode: no cached data for {namespace} {params}"
            )
        frame = self._result_frame(self._request(endpoint, params))
        cache.write(key, frame, self.cfg)
        return frame

    # -- canonical frames ---------------------------------------------------

    def teams(self, season: str) -> pd.DataFrame:
        raw = self._cached("nba-teams", "leaguedashteamstats", {
            "Season": season, "SeasonType": "Regular Season", "LeagueID": "00",
            "MeasureType": "Base", "PerMode": "Totals", "PaceAdjust": "N",
            "PlusMinus": "N", "Rank": "N", "Outcome": "", "Location": "",
            "Month": "0", "SeasonSegment": "", "DateFrom": "", "DateTo": "",
            "OpponentTeamID": "0", "VsConference": "", "VsDivision": "",
            "TeamID": "0", "Conference": "", "Division": "", "GameSegment": "",
            "Period": "0", "LastNGames": "0", "ShotClockRange": "", "PORound": "0",
            "TwoWay": "0",
        }, permanent=True)
        if raw.empty:
            raise NBAStatsFetchError("team list came back empty (rate limited?)")
        out = pd.DataFrame({
            "team_id": raw["TEAM_ID"].astype(str),
            "team_name": raw["TEAM_NAME"].astype(str),
            "team_abbrev": raw.get("TEAM_ABBREVIATION", raw["TEAM_NAME"]).astype(str),
            "season": season,
        })
        out["conference"] = out["team_id"].map(_CONFERENCE_BY_TEAM_ID).fillna("Unknown")
        out["division"] = ""
        return out

    def players(self, season: str) -> pd.DataFrame:
        # `playerindex` is the only single-call endpoint that carries position.
        raw = self._cached("nba-playerindex", "playerindex", {
            "College": "", "Country": "", "DraftPick": "", "DraftRound": "",
            "DraftYear": "", "Height": "", "Historical": "0", "LeagueID": "00",
            "Season": season, "SeasonType": "Regular Season", "TeamID": "0",
            "Weight": "",
        }, permanent=True)
        if raw.empty:
            raise NBAStatsFetchError("player index came back empty")
        name = (raw["PLAYER_FIRST_NAME"].astype(str) + " " +
                raw["PLAYER_LAST_NAME"].astype(str))
        out = pd.DataFrame({
            "player_id": raw["PERSON_ID"].astype(str),
            "player_name": name,
            "season": season,
            "team_id": raw["TEAM_ID"].astype(str),
            "age": pd.NA,
            "position": raw.get("POSITION", pd.Series([""] * len(raw))).astype(str),
            "height_in": raw.get("HEIGHT", pd.Series([""] * len(raw))).map(_height_to_inches),
            "weight_lb": pd.to_numeric(raw.get("WEIGHT"), errors="coerce"),
            "experience": pd.NA,
        })
        out["position"] = out["position"].map(_normalize_position)

        # Age comes from the bio endpoint, which is one more call.
        try:
            bio = self._cached("nba-bio", "leaguedashplayerbiostats", {
                "LeagueID": "00", "Season": season, "SeasonType": "Regular Season",
                "PerMode": "PerGame", "College": "", "Conference": "", "Country": "",
                "DateFrom": "", "DateTo": "", "Division": "", "DraftPick": "",
                "DraftYear": "", "GameScope": "", "GameSegment": "", "Height": "",
                "LastNGames": "0", "Location": "", "Month": "0", "OpponentTeamID": "0",
                "Outcome": "", "PORound": "0", "Period": "0", "PlayerExperience": "",
                "PlayerPosition": "", "SeasonSegment": "", "ShotClockRange": "",
                "StarterBench": "", "TeamID": "0", "VsConference": "",
                "VsDivision": "", "Weight": "",
            }, permanent=True)
            if not bio.empty:
                ages = bio[["PLAYER_ID", "AGE"]].copy()
                ages["PLAYER_ID"] = ages["PLAYER_ID"].astype(str)
                out = out.drop(columns=["age"]).merge(
                    ages.rename(columns={"PLAYER_ID": "player_id", "AGE": "age"}),
                    on="player_id", how="left",
                )
        except NBAStatsFetchError:
            out["age"] = np.nan
        return out

    def games(self, season: str, season_type: str = "Regular Season") -> pd.DataFrame:
        raw = self._cached("nba-teamgamelog", "leaguegamelog", {
            "Counter": "1000", "DateFrom": "", "DateTo": "", "Direction": "ASC",
            "LeagueID": "00", "PlayerOrTeam": "T", "Season": season,
            "SeasonType": season_type, "Sorter": "DATE",
        }, permanent=True)
        if raw.empty:
            raise NBAStatsFetchError(f"team game log empty for {season}")
        raw = raw.copy()
        raw["TEAM_ID"] = raw["TEAM_ID"].astype(str)
        raw["GAME_ID"] = raw["GAME_ID"].astype(str)
        raw["is_home"] = ~raw["MATCHUP"].str.contains("@", na=False)

        home = raw[raw["is_home"]][["GAME_ID", "GAME_DATE", "TEAM_ID", "PTS"]]
        away = raw[~raw["is_home"]][["GAME_ID", "TEAM_ID", "PTS"]]
        merged = home.merge(away, on="GAME_ID", suffixes=("_home", "_away"))
        return pd.DataFrame({
            "game_id": merged["GAME_ID"],
            "season": season,
            "game_date": pd.to_datetime(merged["GAME_DATE"]),
            "home_team_id": merged["TEAM_ID_home"],
            "away_team_id": merged["TEAM_ID_away"],
            "home_pts": pd.to_numeric(merged["PTS_home"], errors="coerce"),
            "away_pts": pd.to_numeric(merged["PTS_away"], errors="coerce"),
            "overtimes": 0.0,
            "season_type": season_type,
        })

    def box(self, season: str, season_type: str = "Regular Season") -> pd.DataFrame:
        raw = self._cached("nba-playergamelog", "leaguegamelog", {
            "Counter": "1000", "DateFrom": "", "DateTo": "", "Direction": "ASC",
            "LeagueID": "00", "PlayerOrTeam": "P", "Season": season,
            "SeasonType": season_type, "Sorter": "DATE",
        }, permanent=True)
        if raw.empty:
            raise NBAStatsFetchError(f"player game log empty for {season}")
        games = self.games(season, season_type)
        home_map = games.set_index("game_id")["home_team_id"].to_dict()
        away_map = games.set_index("game_id")["away_team_id"].to_dict()

        gid = raw["GAME_ID"].astype(str)
        tid = raw["TEAM_ID"].astype(str)
        is_home = gid.map(home_map) == tid
        out = pd.DataFrame({
            "game_id": gid,
            "player_id": raw["PLAYER_ID"].astype(str),
            "team_id": tid,
            "opponent_team_id": np.where(is_home, gid.map(away_map), gid.map(home_map)),
            "season": season,
            "is_home": is_home,
            "started": False,     # not in the game log; boxscoretraditionalv2 has it
            "min": pd.to_numeric(raw["MIN"], errors="coerce").fillna(0.0),
            "fgm": pd.to_numeric(raw["FGM"], errors="coerce"),
            "fga": pd.to_numeric(raw["FGA"], errors="coerce"),
            "fg3m": pd.to_numeric(raw["FG3M"], errors="coerce"),
            "fg3a": pd.to_numeric(raw["FG3A"], errors="coerce"),
            "ftm": pd.to_numeric(raw["FTM"], errors="coerce"),
            "fta": pd.to_numeric(raw["FTA"], errors="coerce"),
            "orb": pd.to_numeric(raw["OREB"], errors="coerce"),
            "drb": pd.to_numeric(raw["DREB"], errors="coerce"),
            "ast": pd.to_numeric(raw["AST"], errors="coerce"),
            "stl": pd.to_numeric(raw["STL"], errors="coerce"),
            "blk": pd.to_numeric(raw["BLK"], errors="coerce"),
            "tov": pd.to_numeric(raw["TOV"], errors="coerce"),
            "pf": pd.to_numeric(raw["PF"], errors="coerce"),
            "pts": pd.to_numeric(raw["PTS"], errors="coerce"),
            "plus_minus": pd.to_numeric(raw.get("PLUS_MINUS"), errors="coerce"),
        })
        return out

    def pbp(self, season: str, game_ids=None) -> pd.DataFrame:
        """Fetch and normalize play-by-play. One request per game.

        This is the expensive call. Pass `game_ids` to limit it; results are
        cached permanently per game, so a second run costs nothing.
        """
        if game_ids is None:
            game_ids = list(self.games(season)["game_id"])
        games = self.games(season).set_index("game_id")

        frames = []
        for gid in game_ids:
            raw = self._cached(f"nba-pbp-{gid}", "playbyplayv2", {
                "GameID": gid, "StartPeriod": "1", "EndPeriod": "14",
            }, permanent=True)
            if raw.empty:
                continue
            home_id = str(games.loc[gid, "home_team_id"]) if gid in games.index else None
            away_id = str(games.loc[gid, "away_team_id"]) if gid in games.index else None
            frames.append(normalize_pbp(raw, gid, home_id, away_id))
        if not frames:
            return pd.DataFrame()
        return pd.concat(frames, ignore_index=True)


def _height_to_inches(value) -> float:
    """'6-7' -> 79.0."""
    try:
        feet, inches = str(value).split("-")
        return float(feet) * 12 + float(inches)
    except (ValueError, AttributeError):
        return np.nan


def _normalize_position(value: str) -> str:
    """Map NBA's position strings onto the five canonical slots."""
    v = (value or "").upper().replace(" ", "")
    if not v:
        return "SF"
    mapping = {
        "G": "SG", "PG": "PG", "SG": "SG", "G-F": "SG", "GF": "SG",
        "F": "SF", "SF": "SF", "PF": "PF", "F-G": "SF", "FG": "SF",
        "F-C": "PF", "FC": "PF", "C-F": "C", "CF": "C", "C": "C",
    }
    return mapping.get(v, "SF")


def _clock_to_seconds(period: int, clock: str) -> float:
    """PCTIMESTRING ('11:32') plus period -> seconds elapsed since tip."""
    try:
        mins, secs = str(clock).split(":")
        remaining = float(mins) * 60 + float(secs)
    except (ValueError, AttributeError):
        remaining = 0.0
    if period <= 4:
        elapsed_before = (period - 1) * 12 * 60
        length = 12 * 60
    else:
        elapsed_before = 4 * 12 * 60 + (period - 5) * 5 * 60
        length = 5 * 60
    return elapsed_before + (length - remaining)


def normalize_pbp(raw: pd.DataFrame, game_id: str,
                  home_team_id: str | None, away_team_id: str | None) -> pd.DataFrame:
    """Convert one game of playbyplayv2 rows into the canonical pbp schema.

    The fiddly parts, all handled here:

    * three-pointers are only identifiable from the description text;
    * a rebound is offensive when the rebounding team is the team that missed
      the preceding shot, which requires carrying that state forward;
    * team rebounds have no PLAYER1_ID and are dropped, matching the usual
      convention for lineup work;
    * the score columns are sparse (populated only on scoring plays) and must
      be forward-filled.
    """
    raw = raw.copy()
    raw["PERIOD"] = pd.to_numeric(raw["PERIOD"], errors="coerce").fillna(1).astype(int)
    raw["EVENTMSGTYPE"] = pd.to_numeric(raw["EVENTMSGTYPE"], errors="coerce").fillna(0).astype(int)

    desc = (raw.get("HOMEDESCRIPTION").fillna("") + " " +
            raw.get("VISITORDESCRIPTION").fillna("") + " " +
            raw.get("NEUTRALDESCRIPTION").fillna("")).str.upper()

    score = raw["SCORE"].ffill().fillna("0 - 0")
    away_score = pd.to_numeric(score.str.split("-").str[0], errors="coerce").ffill().fillna(0.0)
    home_score = pd.to_numeric(score.str.split("-").str[1], errors="coerce").ffill().fillna(0.0)

    rows = []
    last_missed_team: str | None = None
    for i, r in enumerate(raw.itertuples(index=False)):
        msg = r.EVENTMSGTYPE
        d = desc.iloc[i]
        p1 = str(getattr(r, "PLAYER1_ID", "") or "")
        p2 = str(getattr(r, "PLAYER2_ID", "") or "")
        p3 = str(getattr(r, "PLAYER3_ID", "") or "")
        t1 = str(getattr(r, "PLAYER1_TEAM_ID", "") or "")
        if p1 in ("", "0"):
            p1 = ""
        if t1 in ("", "0", "nan", "None"):
            t1 = ""

        etype = None
        team = t1
        actor = p1
        second = ""
        points = 0.0

        if msg == _MSG_MADE_SHOT:
            is3 = "3PT" in d
            etype = "made_3" if is3 else "made_2"
            points = 3.0 if is3 else 2.0
            if "AST" in d and p2 not in ("", "0"):
                second = p2
            last_missed_team = None
        elif msg == _MSG_MISSED_SHOT:
            is3 = "3PT" in d
            etype = "missed_3" if is3 else "missed_2"
            last_missed_team = t1
            if "BLK" in d and p3 not in ("", "0"):
                second = p3
        elif msg == _MSG_FREE_THROW:
            made = "MISS" not in d
            etype = "made_ft" if made else "missed_ft"
            points = 1.0 if made else 0.0
            last_missed_team = None if made else t1
        elif msg == _MSG_REBOUND:
            if not p1:
                continue  # team rebound: no player, not usable for lineup work
            etype = "oreb" if (last_missed_team and t1 == last_missed_team) else "dreb"
            last_missed_team = None
        elif msg == _MSG_TURNOVER:
            etype = "turnover"
            last_missed_team = None
        elif msg == _MSG_FOUL:
            etype = "foul"
            second = p2 if p2 not in ("", "0") else ""
        elif msg == _MSG_SUBSTITUTION:
            etype = "substitution"
            actor, second = p1, p2      # PLAYER1 out, PLAYER2 in
        elif msg == _MSG_PERIOD_BEGIN:
            etype = "period_start"
            team = ""
        elif msg == _MSG_PERIOD_END:
            etype = "period_end"
            team = ""
        elif msg == _MSG_JUMP_BALL:
            etype = "jump_ball"
        elif msg == _MSG_TIMEOUT:
            etype = "timeout"
        else:
            continue

        # A blocked shot is also emitted as its own event so block counts work.
        rows.append({
            "game_id": str(game_id),
            "event_num": int(getattr(r, "EVENTNUM", i)),
            "period": int(r.PERIOD),
            "seconds_elapsed": _clock_to_seconds(int(r.PERIOD),
                                                 getattr(r, "PCTIMESTRING", "12:00")),
            "event_type": etype,
            "team_id": team,
            "player_id": actor,
            "player2_id": second,
            "home_score": float(home_score.iloc[i]),
            "away_score": float(away_score.iloc[i]),
            "points": points,
            "shot_distance": np.nan,
            "shot_x": np.nan,
            "shot_y": np.nan,
            "shot_zone": None,
        })
        if msg == _MSG_MISSED_SHOT and "BLK" in d and p3 not in ("", "0"):
            rows.append({
                "game_id": str(game_id), "event_num": int(getattr(r, "EVENTNUM", i)) + 0,
                "period": int(r.PERIOD),
                "seconds_elapsed": _clock_to_seconds(int(r.PERIOD),
                                                     getattr(r, "PCTIMESTRING", "12:00")),
                "event_type": "block",
                "team_id": str(getattr(r, "PLAYER3_TEAM_ID", "") or ""),
                "player_id": p3, "player2_id": p1,
                "home_score": float(home_score.iloc[i]),
                "away_score": float(away_score.iloc[i]),
                "points": 0.0, "shot_distance": np.nan, "shot_x": np.nan,
                "shot_y": np.nan, "shot_zone": None,
            })
        if msg == _MSG_TURNOVER and "STL" in d and p2 not in ("", "0"):
            rows.append({
                "game_id": str(game_id), "event_num": int(getattr(r, "EVENTNUM", i)),
                "period": int(r.PERIOD),
                "seconds_elapsed": _clock_to_seconds(int(r.PERIOD),
                                                     getattr(r, "PCTIMESTRING", "12:00")),
                "event_type": "steal",
                "team_id": str(getattr(r, "PLAYER2_TEAM_ID", "") or ""),
                "player_id": p2, "player2_id": p1,
                "home_score": float(home_score.iloc[i]),
                "away_score": float(away_score.iloc[i]),
                "points": 0.0, "shot_distance": np.nan, "shot_x": np.nan,
                "shot_y": np.nan, "shot_zone": None,
            })

    out = pd.DataFrame(rows)
    if not out.empty:
        out["home_team_id"] = home_team_id
        out["away_team_id"] = away_team_id
    return out


# Conference assignment is static and not exposed by leaguedashteamstats.
_CONFERENCE_BY_TEAM_ID = {
    "1610612737": "East", "1610612738": "East", "1610612751": "East",
    "1610612766": "East", "1610612741": "East", "1610612739": "East",
    "1610612765": "East", "1610612754": "East", "1610612748": "East",
    "1610612749": "East", "1610612752": "East", "1610612753": "East",
    "1610612755": "East", "1610612761": "East", "1610612764": "East",
    "1610612742": "West", "1610612743": "West", "1610612744": "West",
    "1610612745": "West", "1610612746": "West", "1610612747": "West",
    "1610612763": "West", "1610612750": "West", "1610612740": "West",
    "1610612760": "West", "1610612756": "West", "1610612757": "West",
    "1610612758": "West", "1610612759": "West", "1610612762": "West",
}
