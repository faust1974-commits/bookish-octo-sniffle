"""The build step that rebuilds the payload around today's rosters.

`tests/test_rosters.py` pins the join itself. These pin what the build does
with the result: that a player with no NBA record gets a labelled placeholder
rather than a silent zero, and that the payload stays JSON-clean.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import build_standalone as B  # noqa: E402
from hoopsim.data import rosters as R  # noqa: E402


def _entries():
    return [
        {"player_id": "1", "name": "Giannis Antetokounmpo", "team_id": "1610612749",
         "position": "PF", "impact": 7.5, "off_impact": 5.0, "def_impact": 2.5,
         "usage": 0.33, "ts_pct": 0.62, "min": 2400.0, "spacing": 0.1,
         "rim_pressure": 1.4, "playmaking": 0.6, "rebounding": 1.1,
         "rim_protection": 0.7},
        {"player_id": "2", "name": "Tyler Herro", "team_id": "1610612748",
         "position": "SG", "impact": 1.2, "off_impact": 1.6, "def_impact": -0.4,
         "usage": 0.28, "ts_pct": 0.58, "min": 2100.0, "spacing": 1.2,
         "rim_pressure": 0.1, "playmaking": 0.4, "rebounding": -0.3,
         "rim_protection": -0.6},
        {"player_id": "3", "name": "Bench Body", "team_id": "1610612748",
         "position": "C", "impact": -3.1, "off_impact": -1.8, "def_impact": -1.3,
         "usage": 0.14, "ts_pct": 0.51, "min": 600.0, "spacing": -0.9,
         "rim_pressure": 0.2, "playmaking": -0.5, "rebounding": 0.8,
         "rim_protection": 0.9},
    ]


def test_replacement_profile_is_the_bottom_of_the_rotation():
    profile = B._replacement_profile(_entries())
    rated = [e["impact"] for e in _entries() if e["min"] >= 500]
    # It must be a real observed impact, not an invented one, and it must sit
    # at the bottom -- an unknown player is not an average player.
    assert profile["impact"] in rated
    assert profile["impact"] == min(rated)
    assert profile["off_impact"] + profile["def_impact"] == pytest.approx(
        profile["impact"], abs=1e-6)
    for skill in B.UNKNOWN_SKILLS:
        assert profile[skill] == 0.0


def test_replacement_profile_survives_an_empty_league():
    # Never raise on a thin or synthetic league; fall back to a stated prior.
    assert B._replacement_profile([])["impact"] == -2.0
    assert B._replacement_profile([{"min": 10, "impact": 4.0}])["impact"] == -2.0


def test_payload_stays_json_clean_through_the_join():
    # pandas fills a missing row with NaN, and `json.dumps(allow_nan=False)`
    # -- which the build uses -- would then fail. Every gap must come back as
    # a real null.
    teams = pd.DataFrame({
        "team_id": ["1610612748", "1610612749"],
        "team_abbrev": ["MIA", "MIL"],
        "team_name": ["Miami Heat", "Milwaukee Bucks"],
    })
    roster = pd.DataFrame({
        "espn_id": ["a", "b", "c"],
        "player_name": ["Giannis Antetokounmpo", "Tyler Herro", "Rookie Kid"],
        "team_abbrev": ["MIA", "MIL", "MIL"],
        "position": ["PF", "SG", "PG"],
        "age": [31.0, 26.0, 19.0],
        "experience": [13.0, 7.0, 0.0],
        "jersey": ["34", "14", "3"],
        "season": ["2026-27"] * 3,
    })
    roster["name_key"] = roster["player_name"].map(R.name_key)

    current = pd.DataFrame(_entries()).rename(columns={"name": "player_name"})
    current["season"] = "2025-26"
    joined, report = R.apply_rosters(current, teams, roster)

    unknown = B._replacement_profile(_entries())
    out = []
    for row in joined.to_dict("records"):
        entry = {k: (None if B._is_missing(v) else v) for k, v in row.items()}
        entry["name"] = entry.pop("player_name")
        if not entry.get("has_data"):
            entry.update(unknown)
            entry["unrated"] = True
        out.append(entry)

    json.dumps(out, allow_nan=False)  # the assertion is that this returns

    by_name = {e["name"]: e for e in out}
    assert by_name["Giannis Antetokounmpo"]["team_id"] == "1610612748"  # traded
    assert by_name["Giannis Antetokounmpo"]["impact"] == 7.5            # unchanged
    assert by_name["Rookie Kid"]["unrated"] is True
    assert by_name["Rookie Kid"]["impact"] == unknown["impact"]
    assert "Bench Body" not in by_name                                  # off roster
    assert report.dropped == 1


# -- traded players ---------------------------------------------------------

def _stint_box():
    """A player traded after 40 games, plus a teammate who never moved."""
    rows = []
    for g in range(40):   # UTA
        rows.append({"game_id": f"u{g}", "player_id": "p1", "team_id": "UTA",
                     "min": 30.0, "fga": 15.0, "fgm": 7.0, "fg3a": 5.0,
                     "fg3m": 2.0, "fta": 4.0, "ftm": 3.0, "orb": 1.0,
                     "drb": 4.0, "ast": 5.0, "stl": 1.0, "blk": 0.0,
                     "tov": 3.0, "pf": 2.0, "pts": 19.0, "started": 1})
    for g in range(20):   # LAL
        rows.append({"game_id": f"l{g}", "player_id": "p1", "team_id": "LAL",
                     "min": 24.0, "fga": 10.0, "fgm": 5.0, "fg3a": 4.0,
                     "fg3m": 2.0, "fta": 2.0, "ftm": 2.0, "orb": 0.0,
                     "drb": 3.0, "ast": 4.0, "stl": 1.0, "blk": 0.0,
                     "tov": 2.0, "pf": 2.0, "pts": 14.0, "started": 1})
    return pd.DataFrame(rows)


def test_a_traded_player_is_one_season_not_two_half_seasons():
    from hoopsim.metrics.aggregate import player_totals

    box = _stint_box()
    stints = player_totals(box, by=["player_id", "team_id"])
    season = player_totals(box, by=["player_id"])

    assert len(stints) == 2 and len(season) == 1
    # The bug this guards: keyed on player id, the last stint wins and 1,200
    # minutes of basketball become 480.
    assert season["min"].iloc[0] == pytest.approx(40 * 30.0 + 20 * 24.0)
    assert season["min"].iloc[0] > stints["min"].max()
    assert season["pts"].iloc[0] == pytest.approx(40 * 19.0 + 20 * 14.0)
    assert season["games"].iloc[0] == 60


def test_team_context_is_blended_by_where_the_minutes_were_played():
    from hoopsim.metrics.aggregate import blend_team_context, player_totals

    stints = player_totals(_stint_box(), by=["player_id", "team_id"])
    teams = pd.DataFrame({"team_id": ["UTA", "LAL"],
                          "tm_poss": [8000.0, 4000.0],
                          "tm_pace": [100.0, 94.0]})
    out = blend_team_context(stints, teams)

    assert len(out) == 1
    uta_min, lal_min = 40 * 30.0, 20 * 24.0
    w = uta_min / (uta_min + lal_min)
    # Not a plain average of the two teams -- weighted by where he played.
    assert out["tm_pace"].iloc[0] == pytest.approx(w * 100.0 + (1 - w) * 94.0)
    assert out["tm_poss"].iloc[0] == pytest.approx(w * 8000.0 + (1 - w) * 4000.0)
    assert out["tm_pace"].iloc[0] != pytest.approx(97.0)
    # His team is the one he played the most for.
    assert out["team_id"].iloc[0] == "UTA"


def test_blending_survives_a_player_with_no_recorded_minutes():
    from hoopsim.metrics.aggregate import blend_team_context

    stints = pd.DataFrame({"player_id": ["p9", "p9"], "team_id": ["UTA", "LAL"],
                           "min": [0.0, 0.0]})
    teams = pd.DataFrame({"team_id": ["UTA", "LAL"], "tm_pace": [100.0, 94.0]})
    out = blend_team_context(stints, teams)
    # Equal weights rather than a divide-by-zero NaN that poisons every rate.
    assert out["tm_pace"].iloc[0] == pytest.approx(97.0)


def test_clean_refuses_a_multi_row_lookup():
    # The silent failure this guards: `metrics.loc[pid]` for a player with two
    # team rows returns a Series, `str()` turns it into a multi-line string,
    # and the payload ships valid JSON full of "player_id\n1626145    ..." --
    # which is exactly what the first real build published.
    assert B._clean(3.14159, 2) == 3.14
    assert B._clean(None) is None
    assert B._clean("PG") == "PG"
    with pytest.raises(TypeError, match="expected one value per field"):
        B._clean(pd.Series([1.0, 2.0], index=["a", "b"]))
    with pytest.raises(TypeError, match="expected one value per field"):
        B._clean([1.0, 2.0])


# -- how much to trust a rating ---------------------------------------------

def test_uncertainty_says_where_the_rating_came_from():
    from hoopsim import constants as K

    entries = [
        {"name": "Star", "impact": 5.0, "rapm_poss": 9000.0},
        {"name": "Rotation", "impact": 1.0, "rapm_poss": 4000.0},
        {"name": "Deep bench", "impact": 4.5, "rapm_poss": 400.0},
        {"name": "Never played", "impact": -2.0, "rapm_poss": 0.0},
    ]
    out = {e["name"]: e for e in B.add_uncertainty(entries, K.RAPM_DEFAULT_ALPHA)}

    # The share of a rating that play-by-play actually drove rises with
    # possessions -- that is the whole point of the disclosure.
    assert (out["Star"]["pbp_share"] > out["Rotation"]["pbp_share"]
            > out["Deep bench"]["pbp_share"] > out["Never played"]["pbp_share"])
    assert out["Never played"]["pbp_share"] == 0.0

    # A bench player's rating is mostly his box score, so it is the least
    # certain -- even though his number looks as confident as anyone's.
    assert out["Deep bench"]["impact_se"] > out["Star"]["impact_se"]
    for e in out.values():
        assert e["impact_se"] > 0


def test_a_player_with_no_record_has_no_error_bar_at_all():
    profile = B._replacement_profile([
        {"min": 2000.0, "impact": 2.0}, {"min": 1500.0, "impact": -1.0}])
    # Not "very uncertain" -- unmeasured. An error bar would imply a
    # measurement was taken.
    assert profile["impact_se"] is None
    assert profile["pbp_share"] == 0.0


def test_error_bars_scale_with_how_noisy_the_league_is():
    from hoopsim import constants as K

    tight = [{"impact": v, "rapm_poss": 500.0} for v in (0.1, -0.1, 0.2, -0.2)]
    wide = [{"impact": v, "rapm_poss": 500.0} for v in (6.0, -6.0, 4.0, -4.0)]
    a = B.add_uncertainty(tight, K.RAPM_DEFAULT_ALPHA)[0]["impact_se"]
    b = B.add_uncertainty(wide, K.RAPM_DEFAULT_ALPHA)[0]["impact_se"]
    # The prior's error is a share of the spread it has to explain, so a
    # league where ratings vary more has wider bars on its guesses.
    assert b > a
