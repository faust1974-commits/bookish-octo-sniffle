"""The fixture list a projected record is built on.

A rating says how good a team is; a record says what that is worth, and the
schedule is the difference. These tests pin the parsing, because a schedule
that quietly loses games would produce a record that looks fine and is
wrong.
"""

from __future__ import annotations

import pandas as pd
import pytest

from hoopsim.data import schedule as S


def _raw(rows):
    return pd.DataFrame(rows, columns=[
        "home_abbreviation", "away_abbreviation", "game_date",
        "season_type", "neutral_site"])


def test_only_the_regular_season_counts():
    raw = _raw([
        ["MIA", "BOS", "2026-10-20", S.REGULAR_SEASON, False],
        ["MIA", "BOS", "2026-10-05", 1, False],            # preseason
        ["MIA", "BOS", "2027-04-20", 3, False],            # playoffs
    ])
    out = S._normalise(raw, "2026-27")
    assert len(out) == 1
    assert out["date"].iloc[0] == "2026-10-20"


def test_espn_codes_become_nba_tricodes():
    # The schedule feed and the play-by-play feed spell eight teams
    # differently; an unmapped code would silently drop those games.
    raw = _raw([
        ["UTAH", "NO", "2026-11-01", S.REGULAR_SEASON, False],
        ["GS", "WSH", "2026-11-02", S.REGULAR_SEASON, False],
    ])
    out = S._normalise(raw, "2026-27")
    assert list(out["home"]) == ["UTA", "GSW"]
    assert list(out["away"]) == ["NOP", "WAS"]


def test_a_team_cannot_play_itself():
    raw = _raw([
        ["MIA", "MIA", "2026-12-25", S.REGULAR_SEASON, False],   # placeholder
        ["MIA", "BOS", "2026-12-26", S.REGULAR_SEASON, False],
    ])
    out = S._normalise(raw, "2026-27")
    assert len(out) == 1
    assert out["away"].iloc[0] == "BOS"


def test_games_come_back_in_date_order():
    raw = _raw([
        ["MIA", "BOS", "2026-12-26", S.REGULAR_SEASON, False],
        ["NYK", "PHI", "2026-10-20", S.REGULAR_SEASON, False],
        ["LAL", "GS", "2026-11-15", S.REGULAR_SEASON, False],
    ])
    out = S._normalise(raw, "2026-27")
    assert list(out["date"]) == sorted(out["date"])
    assert out["date"].iloc[0] == "2026-10-20"


def test_every_team_is_counted_home_and_away():
    raw = _raw([
        ["MIA", "BOS", "2026-10-20", S.REGULAR_SEASON, False],
        ["BOS", "MIA", "2026-10-22", S.REGULAR_SEASON, False],
        ["MIA", "NYK", "2026-10-24", S.REGULAR_SEASON, False],
    ])
    counts = S.games_per_team(S._normalise(raw, "2026-27"))
    assert counts["MIA"] == 3      # two home, one away
    assert counts["BOS"] == 2
    assert counts["NYK"] == 1
