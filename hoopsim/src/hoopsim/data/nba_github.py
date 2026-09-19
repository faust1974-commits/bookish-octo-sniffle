"""Real NBA data, from public season dumps on GitHub.

`stats.nba.com` is unreachable from many sandboxed environments, and it is slow
and rate-limited even when it is reachable -- a full season of play-by-play is
about 1,230 separate requests. This source sidesteps both problems by reading
season dumps that someone else has already collected and published:

    https://github.com/shufinskiy/nba_data

One compressed file per season, fetched from `raw.githubusercontent.com`,
cached locally forever because a finished season never changes. A season loads
in seconds rather than a quarter of an hour.

Two files per season are used:

* ``nbastatsv3_YYYY`` -- the play-by-play event log.
* ``matchups_YYYY``   -- used only for its identity columns, which is where the
  real player names, positions, jersey numbers and team names come from, plus
  the schedule's home and away assignment.

Three quirks of the v3 play-by-play format are handled here, each of which
silently corrupts the data if missed:

1. Free throw rows carry no result field. Made or missed is only knowable from
   the description text.
2. Steals and blocks arrive as rows with an *empty* action type; they are
   identifiable only by their description.
3. A substitution row names the incoming player in text, not by id, and last
   names collide. Oklahoma City rostered two players who both render as
   "J. Williams", so initials are not enough either. The incoming player is
   resolved by tracking who is actually on the floor.
"""

from __future__ import annotations

import io
import re
import tarfile
from pathlib import Path

import numpy as np
import pandas as pd

from ..config import Config, default_config
from .source import DataSource

BASE_URL = "https://raw.githubusercontent.com/shufinskiy/nba_data/main/datasets"

#: Season label -> the dataset's year key. "2025-26" is the 2025 file.
def season_key(season: str) -> int:
    """'2025-26' -> 2025. Also accepts a bare year."""
    text = str(season).strip()
    if "-" in text:
        return int(text.split("-")[0])
    return int(text)


def season_label(key: int) -> str:
    return f"{key}-{str(key + 1)[-2:]}"


_SUB_RE = re.compile(r"SUB:\s*(?P<incoming>.+?)\s+FOR\s+(?P<outgoing>.+?)\s*$", re.I)
_CLOCK_RE = re.compile(r"PT(?P<m>\d+)M(?P<s>[\d.]+)S")

#: Regulation and overtime period lengths, in seconds.
_REGULATION_PERIOD = 12 * 60
_OVERTIME_PERIOD = 5 * 60


class NBADataUnavailable(RuntimeError):
    """Raised when a season's files cannot be fetched or found in the cache."""


def _clock_to_seconds_remaining(clock: str) -> float:
    """'PT11M36.00S' -> 696.0 seconds left in the period."""
    match = _CLOCK_RE.match(str(clock))
    if not match:
        return 0.0
    return float(match.group("m")) * 60 + float(match.group("s"))


def _seconds_elapsed(period: int, clock: str) -> float:
    """Seconds since tip-off, across regulation and overtime periods."""
    remaining = _clock_to_seconds_remaining(clock)
    if period <= 4:
        before = (period - 1) * _REGULATION_PERIOD
        length = _REGULATION_PERIOD
    else:
        before = 4 * _REGULATION_PERIOD + (period - 5) * _OVERTIME_PERIOD
        length = _OVERTIME_PERIOD
    return before + (length - remaining)


class NBAGithubSource(DataSource):
    """A real NBA season, loaded from published dumps.

    Parameters
    ----------
    season:
        Season label such as "2025-26".
    cfg:
        Configuration, used for the cache directory.
    offline:
        Fail rather than download if a season is not already cached.
    """

    name = "nba-github"
    provides_pbp = True
    provides_shot_locations = True
    provides_tracking = False

    def __init__(self, season: str = "2025-26", cfg: Config | None = None,
                 *, offline: bool = False) -> None:
        self.cfg = cfg or default_config()
        self.season = season_label(season_key(season))
        self.key = season_key(season)
        self.offline = offline
        self._pbp_raw: pd.DataFrame | None = None
        self._identity: pd.DataFrame | None = None
        self._games: pd.DataFrame | None = None
        self._pbp: pd.DataFrame | None = None
        self.unresolved_subs = 0

    # -- fetching -----------------------------------------------------------

    def _cache_path(self, dataset: str) -> Path:
        root = self.cfg.ensure_cache() / "nba-github"
        root.mkdir(parents=True, exist_ok=True)
        return root / f"{dataset}_{self.key}.csv"

    def _load_dataset(self, dataset: str, usecols=None) -> pd.DataFrame:
        """Fetch one season file, extract the CSV, and cache it."""
        cached = self._cache_path(dataset)
        if cached.exists():
            return pd.read_csv(cached, low_memory=False, usecols=usecols)
        if self.offline:
            raise NBADataUnavailable(
                f"offline: {cached} is not cached. Run once with network access."
            )

        try:
            import requests
        except ImportError as exc:  # pragma: no cover
            raise NBADataUnavailable("the `requests` package is required") from exc

        url = f"{BASE_URL}/{dataset}_{self.key}.tar.xz"
        try:
            response = requests.get(url, timeout=300)
        except requests.RequestException as exc:
            raise NBADataUnavailable(f"could not fetch {url}: {exc}") from exc
        if response.status_code == 404:
            raise NBADataUnavailable(
                f"{dataset} is not published for {self.season}. "
                "The most recent completed season is usually the newest available."
            )
        if response.status_code != 200:
            raise NBADataUnavailable(f"{url} returned {response.status_code}")

        with tarfile.open(fileobj=io.BytesIO(response.content), mode="r:xz") as tar:
            member = next((m for m in tar.getmembers() if m.name.endswith(".csv")), None)
            if member is None:
                raise NBADataUnavailable(f"{url} contained no CSV")
            extracted = tar.extractfile(member)
            if extracted is None:
                raise NBADataUnavailable(f"{url} member could not be read")
            cached.write_bytes(extracted.read())
        return pd.read_csv(cached, low_memory=False, usecols=usecols)

    # -- identity -----------------------------------------------------------

    def _load_identity(self) -> pd.DataFrame:
        """Player directory: real names, positions, teams. From the matchups file."""
        if self._identity is not None:
            return self._identity
        raw = self._load_dataset("matchups", usecols=[
            "game_id", "home_team_id", "away_team_id", "team_id", "team_name",
            "team_city", "team_tricode", "person_id", "first_name", "family_name",
            "position", "jersey_num",
        ])
        raw["person_id"] = raw["person_id"].astype("int64").astype(str)
        raw["team_id"] = raw["team_id"].astype("int64").astype(str)
        self._identity = raw
        return raw

    def teams(self, season: str | None = None) -> pd.DataFrame:
        ident = self._load_identity()
        teams = ident.drop_duplicates("team_id")[
            ["team_id", "team_tricode", "team_city", "team_name"]].copy()
        teams["team_name"] = teams["team_city"].str.strip() + " " + teams["team_name"].str.strip()
        teams["team_abbrev"] = teams["team_tricode"]
        teams["season"] = self.season
        teams["conference"] = teams["team_id"].map(CONFERENCE_BY_TEAM_ID).fillna("Unknown")
        teams["division"] = ""
        return teams[["team_id", "team_name", "team_abbrev", "season",
                      "conference", "division"]].reset_index(drop=True)

    def players(self, season: str | None = None) -> pd.DataFrame:
        ident = self._load_identity()
        rows = ident.drop_duplicates(["person_id", "team_id"]).copy()
        # A player's team is the one he appears for most often, so mid-season
        # trades resolve to where he actually spent the season.
        counts = (ident.groupby(["person_id", "team_id"]).size()
                  .rename("n").reset_index()
                  .sort_values("n", ascending=False)
                  .drop_duplicates("person_id"))
        primary = dict(zip(counts["person_id"], counts["team_id"]))

        rows = rows.drop_duplicates("person_id").copy()
        rows["team_id"] = rows["person_id"].map(primary)
        name = (rows["first_name"].fillna("").str.strip() + " "
                + rows["family_name"].fillna("").str.strip()).str.strip()

        # Position is only recorded for some players; fill the rest from the
        # coarse G/F/C the feed gives, then refine with play style downstream.
        known = (ident.dropna(subset=["position"])
                 .groupby("person_id")["position"]
                 .agg(lambda s: s.mode().iloc[0]))
        coarse = rows["person_id"].map(known)

        out = pd.DataFrame({
            "player_id": rows["person_id"].to_numpy(),
            "player_name": name.to_numpy(),
            "season": self.season,
            "team_id": rows["team_id"].to_numpy(),
            "age": np.nan,
            "position": coarse.map(COARSE_TO_SLOT).fillna("SF").to_numpy(),
            "position_raw": coarse.to_numpy(),
            "jersey": rows["jersey_num"].to_numpy(),
            "height_in": np.nan,
            "weight_lb": np.nan,
            "experience": np.nan,
        })
        return out.reset_index(drop=True)

    # -- schedule -----------------------------------------------------------

    def games(self, season: str | None = None,
              season_type: str = "Regular Season") -> pd.DataFrame:
        if self._games is not None:
            return self._games.copy()
        ident = self._load_identity()
        schedule = ident.drop_duplicates("game_id")[
            ["game_id", "home_team_id", "away_team_id"]].copy()
        schedule["game_id"] = schedule["game_id"].astype("int64").astype(str)
        schedule["home_team_id"] = schedule["home_team_id"].astype("int64").astype(str)
        schedule["away_team_id"] = schedule["away_team_id"].astype("int64").astype(str)

        raw = self._load_raw_pbp()
        # The maximum, not the last row: scores only climb, and the feed's
        # occasional out-of-order row would otherwise be read as the final.
        finals = (raw.dropna(subset=["scoreHome", "scoreAway"])
                  .groupby("gameId")
                  .agg(home_pts=("scoreHome", "max"),
                       away_pts=("scoreAway", "max"),
                       periods=("period", "max")))
        finals.index = finals.index.astype(str)

        out = schedule.merge(finals, left_on="game_id", right_index=True, how="left")
        out["season"] = self.season
        out["season_type"] = season_type
        out["overtimes"] = (out["periods"].fillna(4) - 4).clip(lower=0).astype(float)
        # The dumps carry no calendar date, so games are ordered by their id,
        # which the NBA assigns chronologically within a season.
        out = out.sort_values("game_id").reset_index(drop=True)
        opening = pd.Timestamp(f"{self.key}-10-21")
        out["game_date"] = opening + pd.to_timedelta(
            np.arange(len(out)) // 6, unit="D")
        self._games = out[["game_id", "season", "game_date", "home_team_id",
                           "away_team_id", "home_pts", "away_pts", "overtimes",
                           "season_type"]]
        return self._games.copy()

    # -- play-by-play -------------------------------------------------------

    def _load_raw_pbp(self) -> pd.DataFrame:
        if self._pbp_raw is None:
            self._pbp_raw = self._load_dataset("nbastatsv3")
        return self._pbp_raw

    def pbp(self, season: str | None = None, game_ids=None) -> pd.DataFrame:
        if self._pbp is None:
            self._pbp = self._normalize_pbp()
        out = self._pbp
        if game_ids is not None:
            out = out[out["game_id"].isin(set(game_ids))]
        return out.copy()

    def _name_lookup(self) -> dict:
        """(team_id, normalized name) -> list of player ids, for substitutions."""
        ident = self._load_identity().drop_duplicates(["person_id", "team_id"])
        lookup: dict[tuple[str, str], list[str]] = {}
        for r in ident.itertuples(index=False):
            family = str(r.family_name or "").strip()
            first = str(r.first_name or "").strip()
            if not family:
                continue
            keys = {family.lower()}
            if first:
                keys.add(f"{first[0]}. {family}".lower())
                keys.add(f"{first[0]}.{family}".lower())
            for key in keys:
                lookup.setdefault((str(r.team_id), key), []).append(str(r.person_id))
        return lookup

    def _starters_by_game(self) -> dict:
        """Exact starting fives, straight from the feed.

        The matchups file only fills its `position` column for players who
        started, which makes it an authoritative record of the opening five.
        That beats inferring starters from the event log, and it anchors
        substitution tracking so a single bad resolution cannot cascade.
        """
        ident = self._load_identity()
        starters = ident.dropna(subset=["position"]).drop_duplicates(
            ["game_id", "person_id"])
        out: dict[tuple[str, str], set] = {}
        for r in starters.itertuples(index=False):
            key = (str(r.game_id), str(r.team_id))
            out.setdefault(key, set()).add(str(r.person_id))
        return out

    def _normalize_pbp(self) -> pd.DataFrame:
        """Convert the v3 event log into the canonical schema."""
        raw = self._load_raw_pbp()
        games = self.games().set_index("game_id")
        feed_starters = self._starters_by_game()
        season_names = self._name_lookup()

        raw = raw.copy()
        raw["gameId"] = raw["gameId"].astype(str)
        raw["teamId"] = raw["teamId"].fillna(0).astype("int64").astype(str)
        raw["personId"] = raw["personId"].fillna(0).astype("int64").astype(str)
        for col in ("description", "actionType", "subType", "playerName", "playerNameI"):
            raw[col] = raw[col].fillna("")
        raw = raw.sort_values(["gameId", "actionNumber"])

        # Team-level events -- team rebounds, team turnovers, timeouts -- put
        # the TEAM id in the personId column and leave teamId as 0. Left alone,
        # thirty team entities get treated as players and credited with 22,000
        # rebounds between them. Swap them back: the team owns the event and
        # nobody is charged with it.
        team_ids = set(self.teams()["team_id"])
        is_team_event = raw["personId"].isin(team_ids)
        raw.loc[is_team_event, "teamId"] = raw.loc[is_team_event, "personId"]
        raw.loc[is_team_event, "personId"] = "0"

        rows: list[dict] = []
        unresolved = 0
        broken_lineups = 0

        for game_id, game in raw.groupby("gameId", sort=False):
            if game_id not in games.index:
                continue
            home_id = str(games.loc[game_id, "home_team_id"])
            away_id = str(games.loc[game_id, "away_team_id"])

            # Names as this game itself spells them. Pairs observed here are
            # the precise source -- both the short and initialled forms appear
            # beside an id -- but they only cover players who recorded a
            # statistic. A substitute who comes in and does nothing measurable
            # never appears, so the season roster backs them up.
            local: dict[tuple[str, str], set] = {}
            for r in game.itertuples(index=False):
                if r.personId == "0" or not r.teamId:
                    continue
                for form in (r.playerName, r.playerNameI):
                    if form:
                        local.setdefault((r.teamId, _norm(form)), set()).add(r.personId)

            on_floor = {
                home_id: set(feed_starters.get((game_id, home_id), set())),
                away_id: set(feed_starters.get((game_id, away_id), set())),
            }
            # Fall back to inference only where the feed gave us nothing.
            for team in (home_id, away_id):
                if len(on_floor[team]) != 5:
                    on_floor[team] = _infer_opening_five(game, team)

            # Opening five for every period, not just the first. Teams change
            # personnel at quarter breaks with no substitution events, so the
            # floor has to be re-anchored or the tracking drifts for the rest
            # of the game.
            period_five = _period_opening_fives(game)

            last_missed_team: str | None = None
            home_score = away_score = 0.0
            current_period = int(game["period"].iloc[0])

            for r in game.itertuples(index=False):
                if int(r.period) != current_period:
                    current_period = int(r.period)
                    for team in (home_id, away_id):
                        fresh = period_five.get((team, current_period))
                        if fresh and len(fresh) == 5:
                            on_floor[team] = set(fresh)
                action = r.actionType
                desc = r.description
                team = r.teamId
                actor = r.personId if r.personId != "0" else ""
                second = ""
                points = 0.0
                etype = None

                if action == "Made Shot":
                    etype = "made_3" if r.shotValue == 3 else "made_2"
                    points = float(r.shotValue or 2)
                    assist = re.search(r"\(([^)]+?)\s+\d+\s+AST\)", desc)
                    if assist:
                        second = _resolve(local, season_names, team, assist.group(1),
                                          on_floor.get(team, set()),
                                          want_on_floor=True) or ""
                    last_missed_team = None
                elif action == "Missed Shot":
                    etype = "missed_3" if r.shotValue == 3 else "missed_2"
                    last_missed_team = team
                elif action == "Free Throw":
                    made = "MISS" not in desc.upper()
                    etype = "made_ft" if made else "missed_ft"
                    points = 1.0 if made else 0.0
                    last_missed_team = None if made else team
                elif action == "Rebound":
                    if not actor:
                        continue          # team rebound: unusable for lineups
                    etype = "oreb" if (last_missed_team and team == last_missed_team) else "dreb"
                    last_missed_team = None
                elif action == "Turnover":
                    etype = "turnover"
                    last_missed_team = None
                elif action == "Foul":
                    etype = "foul"
                elif action == "Substitution":
                    match = _SUB_RE.search(desc)
                    incoming = ""
                    if match:
                        incoming = _resolve(local, season_names, team,
                                            match.group("incoming"),
                                            on_floor.get(team, set()),
                                            want_on_floor=False) or ""
                    if not incoming:
                        unresolved += 1
                    etype = "substitution"
                    second = incoming
                    if team in on_floor:
                        on_floor[team].discard(actor)
                        if incoming:
                            on_floor[team].add(incoming)
                        if len(on_floor[team]) != 5:
                            broken_lineups += 1
                            on_floor[team] = _repair(on_floor[team], local, team,
                                                     actor, incoming)
                elif action == "period":
                    etype = "period_start" if r.subType == "start" else "period_end"
                    team = ""
                    actor = ""
                elif action == "Jump Ball":
                    etype = "jump_ball"
                elif action == "Timeout":
                    etype = "timeout"
                elif action == "":
                    # Steals and blocks arrive with no action type at all.
                    upper = desc.upper()
                    if "STEAL" in upper:
                        etype = "steal"
                    elif "BLOCK" in upper or "BLK" in upper:
                        etype = "block"
                    else:
                        continue
                else:
                    continue

                if pd.notna(r.scoreHome):
                    home_score = float(r.scoreHome)
                if pd.notna(r.scoreAway):
                    away_score = float(r.scoreAway)

                rows.append({
                    "game_id": game_id,
                    "event_num": int(r.actionNumber),
                    "period": int(r.period),
                    "seconds_elapsed": _seconds_elapsed(int(r.period), r.clock),
                    "event_type": etype,
                    "team_id": team,
                    "player_id": actor,
                    "player2_id": second,
                    "home_score": home_score,
                    "away_score": away_score,
                    "points": points,
                    "shot_distance": float(r.shotDistance) if pd.notna(r.shotDistance) else np.nan,
                    "shot_x": float(r.xLegacy) if pd.notna(r.xLegacy) else np.nan,
                    "shot_y": float(r.yLegacy) if pd.notna(r.yLegacy) else np.nan,
                    "shot_zone": str(r.subType) or None,
                })

        self.unresolved_subs = unresolved
        self.broken_lineups = broken_lineups
        out = pd.DataFrame(rows)
        if out.empty:
            return out

        # The feed's clock occasionally runs backwards -- a few thousand rows
        # across a season carry a timestamp from earlier in the period. A
        # negative elapsed time makes a stint's duration nonsense, so hold the
        # clock at its high-water mark within each game rather than let it
        # jump back.
        out = out.sort_values(["game_id", "event_num"]).reset_index(drop=True)
        out["seconds_elapsed"] = out.groupby("game_id")["seconds_elapsed"].cummax()

        meta = self.games()[["game_id", "home_team_id", "away_team_id"]]
        return out.merge(meta, on="game_id", how="left")

    def starting_lineups(self, season: str | None = None) -> dict:
        """Opening fives, straight from the feed. See `_starters_by_game`."""
        return self._starters_by_game()

    def box(self, season: str | None = None,
            season_type: str = "Regular Season") -> pd.DataFrame:
        from .pbp import box_from_pbp

        return box_from_pbp(self.pbp(), self.games(), self.players())


def _norm(text: str) -> str:
    return str(text or "").strip().lower()


def _norm_person(row) -> str:
    return _norm(getattr(row, "playerName", "") or "")


def _resolve(local: dict, season: dict, team_id: str, name: str, on_floor: set,
             *, want_on_floor: bool) -> str | None:
    """Turn a name from a description into a player id.

    Two lookups, tried in order. `local` maps (team, name) to the ids seen
    under that name *in this game*, which is the precise source because both
    the short form ("Williams") and the initialled form ("K. Williams")
    appear beside an id. But it only covers players who recorded something,
    so a substitute who came in and did nothing measurable is missing from it
    -- `season` is the full team roster and fills those in.

    Where a name is still ambiguous (Oklahoma City rostered two players who
    both render as "J. Williams") the floor decides: an incoming substitute
    cannot already be out there, and an assisting player must be.
    """
    key = (str(team_id), _norm(name))
    candidates = sorted(local.get(key) or ())
    if not candidates:
        candidates = sorted(season.get(key) or ())
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]
    if want_on_floor:
        present = [c for c in candidates if c in on_floor]
        return present[0] if present else candidates[0]
    absent = [c for c in candidates if c not in on_floor]
    return absent[0] if absent else candidates[0]


def _period_opening_fives(game: pd.DataFrame) -> dict:
    """Opening five per (team, period), read straight off the raw rows.

    `personId` is exact on both ordinary events and substitution rows (where
    it names the outgoing player), so this needs no name matching: within a
    period, a player who acts or is substituted out before he is ever
    substituted in was on the floor when the period began.
    """
    out: dict[tuple[str, int], set] = {}
    for period, chunk in game.groupby("period", sort=True):
        seen_in: dict[str, set] = {}
        starters: dict[str, list] = {}
        for r in chunk.itertuples(index=False):
            team = r.teamId
            if not team or team == "0":
                continue
            seen_in.setdefault(team, set())
            starters.setdefault(team, [])
            if r.actionType == "Substitution":
                match = _SUB_RE.search(r.description)
                if match:
                    seen_in[team].add(_norm(match.group("incoming")))
                if r.personId != "0":
                    if (_norm(r.playerName) not in seen_in[team]
                            and _norm(r.playerNameI) not in seen_in[team]
                            and r.personId not in starters[team]):
                        starters[team].append(r.personId)
                continue
            if r.actionType in ("period", "Timeout"):
                continue
            if r.personId == "0":
                continue
            if (_norm(r.playerName) not in seen_in[team]
                    and _norm(r.playerNameI) not in seen_in[team]
                    and r.personId not in starters[team]):
                starters[team].append(r.personId)
        for team, found in starters.items():
            out[(team, int(period))] = set(found[:5])
    return out


def _infer_opening_five(game: pd.DataFrame, team_id: str) -> set:
    """Opening five from the event log, for games the feed does not cover.

    A player who acts, or is substituted out, before he is ever substituted
    in was on the floor from the tip.
    """
    subbed_in: set = set()
    starters: list[str] = []
    for r in game.itertuples(index=False):
        if r.teamId != team_id:
            continue
        if r.actionType == "Substitution":
            match = _SUB_RE.search(r.description)
            if match:
                subbed_in.add(_norm(match.group("incoming")))
        actor = r.personId
        if actor == "0":
            continue
        if _norm(r.playerName) in subbed_in or _norm(r.playerNameI) in subbed_in:
            continue
        if actor not in starters:
            starters.append(actor)
        if len(starters) == 5:
            break
    return set(starters)


def _repair(on_floor: set, local: dict, team_id: str,
            outgoing: str, incoming: str) -> set:
    """Nudge a lineup back to five after a substitution could not be applied.

    A lineup that drifts off five poisons every stint that follows, so rather
    than let the error compound this drops the least recently added player
    when the set is too large, and re-admits the outgoing player when it is
    too small and nobody came in.
    """
    floor = set(on_floor)
    if len(floor) > 5:
        for candidate in sorted(floor):
            if candidate not in (incoming,):
                floor.discard(candidate)
            if len(floor) == 5:
                break
    elif len(floor) < 5 and outgoing:
        floor.add(outgoing)
    return floor


#: Coarse feed positions mapped onto the five canonical slots. The feed only
#: distinguishes guard, forward and centre; `refine_positions` sharpens these
#: using how a player actually plays.
COARSE_TO_SLOT = {"G": "SG", "F": "SF", "C": "C", "G-F": "SG", "F-G": "SF",
                  "F-C": "PF", "C-F": "C"}

#: Conference assignment, which the dumps do not carry.
CONFERENCE_BY_TEAM_ID = {
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
