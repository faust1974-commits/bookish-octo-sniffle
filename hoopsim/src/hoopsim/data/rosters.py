"""Who is on which team *today*.

Performance data and roster membership answer two different questions, and
conflating them is the single easiest way to make this tool confidently wrong.
A season dump tells you what a player did and who he did it for; it cannot
tell you that he was traded in July. Rebuilt from a season dump alone, a
lineup tool shows last season's teams -- Giannis in Milwaukee, Herro in Miami
-- months after both moved.

So roster membership comes from its own feed, refreshed on its own clock:
ESPN's daily team-roster scrape, mirrored as one small file per season by
`sportsdataverse/hoopR-nba-data`. It carries every player under contract,
including rookies and veterans who missed all of last season, plus the age
and listed position the season dumps leave blank.

The two feeds share no player id, so they are joined on a normalised name.
That is the weak link, and it is handled explicitly: ambiguous keys are
refused rather than guessed, and every unmatched player is reported instead
of silently dropped.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date

import pandas as pd

from ..config import Config, default_config
from . import cache

#: One parquet per season, refreshed daily by the upstream scraper.
ROSTER_URL = ("https://raw.githubusercontent.com/sportsdataverse/hoopR-nba-data"
              "/main/nba/rosters/parquet/rosters_{year}.parquet")

#: Rosters churn daily -- signings, waivers, two-way call-ups. Six hours keeps
#: a rebuild from re-downloading while staying same-day fresh.
ROSTER_TTL_SECONDS = 6 * 3600

#: ESPN's abbreviations differ from the NBA's tricodes for eight teams.
ESPN_TO_TRICODE = {
    "UTAH": "UTA", "WSH": "WAS", "NO": "NOP", "SA": "SAS",
    "GS": "GSW", "NY": "NYK", "PHX": "PHX", "BKN": "BKN",
}

#: ESPN's position labels, mapped to the five slots the lineup model uses.
ESPN_POSITION = {
    "PG": "PG", "SG": "SG", "SF": "SF", "PF": "PF", "C": "C",
    "G": "SG", "F": "SF", "GF": "SF", "FG": "SF", "FC": "PF", "CF": "C",
}

_SUFFIXES = re.compile(r"\b(jr|sr|ii|iii|iv|v)\b")


def name_key(name: str) -> str:
    """A name reduced to what two feeds can agree on.

    Accents, punctuation, generational suffixes and hyphenation all vary
    between sources; none of them distinguish two actual players.
    """
    text = unicodedata.normalize("NFKD", str(name))
    text = text.encode("ascii", "ignore").decode("ascii").lower()
    text = text.replace(".", "").replace("'", "").replace("`", "")
    text = text.replace("-", " ")
    text = _SUFFIXES.sub(" ", text)
    return " ".join(text.split())


def roster_season_year(season: str) -> int:
    """`2026-27` -> 2027, the end year the upstream files are keyed by."""
    head = int(str(season).split("-")[0])
    return head + 1


def current_season(today: date | None = None) -> str:
    """The season now being played or assembled.

    The NBA league year turns over on 1 July: from then on, the roster that
    matters is the one for the season about to start, not the one just
    finished.
    """
    today = today or date.today()
    start = today.year if today.month >= 7 else today.year - 1
    return f"{start}-{str(start + 1)[2:]}"


@dataclass
class RosterReport:
    """What the join did, in numbers -- so a bad join cannot pass unnoticed."""

    season: str
    roster_players: int = 0
    matched: int = 0
    fallback: int = 0
    no_data: int = 0
    dropped: int = 0
    ambiguous: list = field(default_factory=list)
    off_roster: list = field(default_factory=list)

    def summary(self) -> str:
        return (f"{self.season} rosters: {self.roster_players} players, "
                f"{self.matched} with current-season data, "
                f"{self.fallback} from the prior season, "
                f"{self.no_data} with no NBA record yet, "
                f"{self.dropped} last-season players no longer rostered")


def fetch(season: str | None = None, cfg: Config | None = None,
          *, refresh: bool = False) -> pd.DataFrame:
    """Today's rosters for `season`, cached for a few hours.

    Returns one row per rostered player with the columns the rest of the
    pipeline needs: `name_key`, `team_abbrev`, `position`, `age`,
    `experience`, `jersey`, `status`.
    """
    season = season or current_season()
    cfg = cfg or default_config()
    year = roster_season_year(season)
    key = cache.cache_key("espn-rosters", year=year)

    if not refresh:
        cached = cache.read(key, cfg, ttl=ROSTER_TTL_SECONDS)
        if cached is not None:
            return cached

    url = ROSTER_URL.format(year=year)
    try:
        raw = pd.read_parquet(url)
    except Exception as exc:  # network, 404 for a season not yet published
        stale = cache.read(key, cfg, ttl=-1)
        if stale is not None:
            return stale
        raise RosterUnavailable(
            f"could not fetch {season} rosters from {url}: {exc}") from exc

    frame = _normalise(raw, season)
    cache.write(key, frame, cfg)
    return frame


class RosterUnavailable(RuntimeError):
    """No roster feed for the requested season, and nothing cached."""


def _normalise(raw: pd.DataFrame, season: str) -> pd.DataFrame:
    tricode = raw["team_abbreviation"].astype(str).str.upper()
    position = (raw["position_abbreviation"].astype(str).str.upper()
                .map(ESPN_POSITION))

    out = pd.DataFrame({
        "espn_id": raw["athlete_id"].astype(str),
        "player_name": raw["full_name"].astype(str).str.strip(),
        "name_key": raw["full_name"].map(name_key),
        "team_abbrev": tricode.map(lambda t: ESPN_TO_TRICODE.get(t, t)),
        "position": position.fillna("SF"),
        "position_raw": raw["position_abbreviation"].astype(str),
        "age": pd.to_numeric(raw["age"], errors="coerce"),
        "experience": pd.to_numeric(raw["experience_years"], errors="coerce"),
        "jersey": raw["jersey"].astype(str),
        "status": raw.get("status_name", pd.Series("Active", index=raw.index)),
        "season": season,
    })
    # A player appearing twice (a mid-scrape move) would double a team's
    # roster; keep the first listing and let the next refresh settle it.
    return out.drop_duplicates("name_key").reset_index(drop=True)


def _lookup(frame: pd.DataFrame, name_col: str) -> tuple[dict, list]:
    """Map name_key -> row index, refusing keys that match two players."""
    keys = frame[name_col].map(name_key)
    counts = keys.value_counts()
    ambiguous = sorted(counts[counts > 1].index.tolist())
    unique = {k: i for k, i in zip(keys, frame.index) if counts[k] == 1}
    return unique, ambiguous


def apply_rosters(players: pd.DataFrame, teams: pd.DataFrame,
                  rosters: pd.DataFrame, *,
                  fallback: pd.DataFrame | None = None,
                  ) -> tuple[pd.DataFrame, RosterReport]:
    """Rebuild the player table around who is actually on a roster today.

    `players` is the current-season metric table, `fallback` an optional
    prior-season table used for players who did not appear last season at all
    -- a serious injury absence would otherwise erase a starter. Every row
    that comes back carries `data_season`, naming where its numbers came from,
    and `has_data`, so the interface can say so rather than imply a projection
    it cannot make.
    """
    report = RosterReport(season=str(rosters["season"].iloc[0]),
                          roster_players=len(rosters))

    tricode_to_id = dict(zip(teams["team_abbrev"], teams["team_id"]))
    missing_codes = sorted(set(rosters["team_abbrev"]) - set(tricode_to_id))
    if missing_codes:
        raise ValueError(f"roster teams not in the league: {missing_codes}")

    primary, amb_primary = _lookup(players, "player_name")
    report.ambiguous = amb_primary
    secondary, _ = ({}, [])
    if fallback is not None and not fallback.empty:
        secondary, _ = _lookup(fallback, "player_name")

    current_season_label = str(players["season"].iloc[0]) if len(players) else ""
    fallback_label = (str(fallback["season"].iloc[0])
                      if fallback is not None and len(fallback) else "")

    rows = []
    for r in rosters.itertuples(index=False):
        key = r.name_key
        if key in primary:
            row = players.loc[primary[key]].to_dict()
            row["data_season"] = current_season_label
            row["has_data"] = True
            report.matched += 1
        elif key in secondary:
            row = fallback.loc[secondary[key]].to_dict()
            row["data_season"] = fallback_label
            row["has_data"] = True
            report.fallback += 1
        else:
            row = {c: pd.NA for c in players.columns}
            row["data_season"] = ""
            row["has_data"] = False
            report.no_data += 1

        # Roster truth wins over anything the season dump inferred.
        row["player_id"] = row.get("player_id") if row.get("has_data") else f"espn-{r.espn_id}"
        row["player_name"] = r.player_name
        row["team_id"] = tricode_to_id[r.team_abbrev]
        row["team_abbrev"] = r.team_abbrev
        row["season"] = r.season
        row["age"] = r.age
        row["experience"] = r.experience
        row["jersey"] = r.jersey
        row["roster_position"] = r.position
        rows.append(row)

    out = pd.DataFrame(rows)
    # Two roster entries can point at the same historical player only through
    # a name collision, which `_lookup` already refuses; assert it anyway.
    dupes = out["player_id"].duplicated()
    if dupes.any():
        raise ValueError(f"duplicate player ids after join: "
                         f"{out.loc[dupes, 'player_name'].tolist()}")

    on_roster = set(rosters["name_key"])
    gone = players[~players["player_name"].map(name_key).isin(on_roster)]
    report.dropped = len(gone)
    report.off_roster = gone["player_name"].tolist()
    return out.reset_index(drop=True), report
