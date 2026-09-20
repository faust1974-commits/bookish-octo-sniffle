"""The roster join is the seam between two feeds that share no player id.

Every test here pins a way the join could go wrong quietly: a name that
matches two players, a team code only one feed uses, a star who missed a
season, a player who has left the league. None of these raise on their own --
they just produce a roster that looks plausible and is wrong.
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from hoopsim.data import rosters


def _teams():
    return pd.DataFrame({
        "team_id": ["1610612737", "1610612748", "1610612749", "1610612762"],
        "team_abbrev": ["ATL", "MIA", "MIL", "UTA"],
        "team_name": ["Atlanta Hawks", "Miami Heat", "Milwaukee Bucks", "Utah Jazz"],
    })


def _players():
    return pd.DataFrame({
        "player_id": ["1", "2", "3"],
        "player_name": ["Giannis Antetokounmpo", "Tyler Herro", "Retired Guy"],
        "season": ["2025-26"] * 3,
        "team_id": ["1610612749", "1610612748", "1610612737"],
        "min": [2400.0, 2100.0, 900.0],
        "impact": [7.5, 1.2, -1.0],
    })


def _roster(rows):
    frame = pd.DataFrame(rows)
    frame["name_key"] = frame["player_name"].map(rosters.name_key)
    frame["season"] = "2026-27"
    for col, default in (("espn_id", "x"), ("position", "SF"),
                         ("age", 30.0), ("experience", 5.0), ("jersey", "0")):
        if col not in frame:
            frame[col] = default
    return frame


def test_name_key_ignores_what_feeds_disagree_about():
    # Accents, punctuation, suffixes and hyphens vary by source; none of them
    # tell two players apart.
    assert rosters.name_key("Nikola Jokić") == rosters.name_key("Nikola Jokic")
    assert rosters.name_key("Jaren Jackson Jr.") == rosters.name_key("Jaren Jackson")
    assert rosters.name_key("Karl-Anthony Towns") == rosters.name_key("Karl Anthony Towns")
    assert rosters.name_key("  De'Aaron  Fox ") == rosters.name_key("DeAaron Fox")
    # ...and it must not merge two different players.
    assert rosters.name_key("Jalen Williams") != rosters.name_key("Jaylin Williams")


def test_league_year_turns_over_on_july_1():
    # In September the roster that matters is the coming season's, not the
    # one that just ended -- the whole bug this module exists to fix.
    assert rosters.current_season(date(2026, 9, 20)) == "2026-27"
    assert rosters.current_season(date(2026, 7, 1)) == "2026-27"
    assert rosters.current_season(date(2026, 6, 30)) == "2025-26"
    assert rosters.current_season(date(2026, 3, 1)) == "2025-26"
    assert rosters.roster_season_year("2026-27") == 2027


def test_trade_moves_the_player_not_the_numbers():
    roster = _roster([
        {"player_name": "Giannis Antetokounmpo", "team_abbrev": "MIA"},
        {"player_name": "Tyler Herro", "team_abbrev": "MIL"},
    ])
    out, report = rosters.apply_rosters(_players(), _teams(), roster)

    giannis = out.set_index("player_name").loc["Giannis Antetokounmpo"]
    assert giannis["team_abbrev"] == "MIA"
    assert giannis["team_id"] == "1610612748"
    # His production is still his production; only the jersey changed.
    assert giannis["impact"] == 7.5
    assert giannis["min"] == 2400.0
    assert report.matched == 2


def test_player_off_every_roster_is_dropped_and_counted():
    roster = _roster([{"player_name": "Tyler Herro", "team_abbrev": "MIA"}])
    out, report = rosters.apply_rosters(_players(), _teams(), roster)
    assert "Retired Guy" not in set(out["player_name"])
    assert report.dropped == 2
    assert "Retired Guy" in report.off_roster


def test_missed_season_falls_back_to_the_prior_one():
    # A player who tore an achilles and sat out all of last season has no
    # current-season row. Without a fallback he vanishes from his own team.
    fallback = pd.DataFrame({
        "player_id": ["9"], "player_name": ["Tyrese Haliburton"],
        "season": ["2024-25"], "team_id": ["1610612737"],
        "min": [2300.0], "impact": [4.4],
    })
    roster = _roster([{"player_name": "Tyrese Haliburton", "team_abbrev": "ATL"}])
    out, report = rosters.apply_rosters(_players(), _teams(), roster,
                                        fallback=fallback)
    row = out.iloc[0]
    assert row["impact"] == 4.4
    assert row["data_season"] == "2024-25"   # labelled, not passed off as current
    assert row["has_data"]
    assert report.fallback == 1 and report.matched == 0


def test_rookie_is_carried_as_unknown_not_invented():
    roster = _roster([{"player_name": "Kingston Flemings", "team_abbrev": "ATL",
                       "experience": 0.0, "age": 19.0}])
    out, report = rosters.apply_rosters(_players(), _teams(), roster)
    row = out.iloc[0]
    assert not row["has_data"]
    assert row["data_season"] == ""
    assert pd.isna(row["impact"])           # no number beats a made-up number
    assert row["team_abbrev"] == "ATL"      # but he is on the roster
    assert report.no_data == 1


def test_roster_is_the_authority_on_team_age_and_position():
    roster = _roster([{"player_name": "Tyler Herro", "team_abbrev": "MIL",
                       "age": 26.0, "position": "PG"}])
    out, _ = rosters.apply_rosters(_players(), _teams(), roster)
    row = out.iloc[0]
    assert row["age"] == 26.0
    assert row["roster_position"] == "PG"
    assert row["team_abbrev"] == "MIL"


def test_two_players_one_name_is_refused_rather_than_guessed():
    players = pd.DataFrame({
        "player_id": ["1", "2"],
        "player_name": ["Marcus Morris Sr.", "Marcus Morris"],
        "season": ["2025-26"] * 2,
        "team_id": ["1610612737"] * 2,
        "min": [1000.0, 500.0], "impact": [1.0, -2.0],
    })
    roster = _roster([{"player_name": "Marcus Morris", "team_abbrev": "ATL"}])
    out, report = rosters.apply_rosters(players, _teams(), roster)
    # Both historical rows reduce to the same key, so neither is claimed.
    assert report.ambiguous == ["marcus morris"]
    assert not out.iloc[0]["has_data"]


def test_unknown_team_code_is_an_error_not_a_silent_drop():
    roster = _roster([{"player_name": "Tyler Herro", "team_abbrev": "XYZ"}])
    with pytest.raises(ValueError, match="not in the league"):
        rosters.apply_rosters(_players(), _teams(), roster)


def test_espn_team_codes_map_onto_nba_tricodes():
    # Eight teams are abbreviated differently by the two feeds; an unmapped
    # code would raise above, so this is the guard that keeps it from ever
    # getting that far.
    for espn, nba in rosters.ESPN_TO_TRICODE.items():
        assert len(nba) == 3
    assert rosters.ESPN_TO_TRICODE["UTAH"] == "UTA"
    assert rosters.ESPN_TO_TRICODE["WSH"] == "WAS"
    assert rosters.ESPN_TO_TRICODE["NO"] == "NOP"
    assert rosters.ESPN_TO_TRICODE["GS"] == "GSW"
