"""The splits engine must cut the data without losing or duplicating any of it."""

import numpy as np
import pytest

from hoopsim.splits import DIMENSIONS, SplitEngine, available


@pytest.fixture(scope="module")
def engine(league):
    return SplitEngine(league)


def test_every_registered_vertical_is_documented():
    assert len(DIMENSIONS) >= 10
    for key, dim in DIMENSIONS.items():
        assert dim.key == key
        assert dim.label.strip() and dim.description.strip(), key
        assert dim.level in ("game", "possession")


@pytest.mark.parametrize("key", [d.key for d in available("game")])
def test_game_level_verticals_partition_the_season(engine, key, league):
    """Every team-game lands in exactly one bucket, and none are lost."""
    out = engine.team_split(key)
    assert len(out) > 0
    assert out["games"].sum() >= len(league.games)      # both teams counted
    assert out["off_rating"].between(80, 150).all(), key
    assert not out["bucket"].duplicated().any()


@pytest.mark.parametrize("key", [d.key for d in available("possession")])
def test_possession_verticals_account_for_every_possession(engine, key, league):
    out = engine.lineup_split(key)
    assert len(out) > 0
    total = league.stints["home_poss"].sum() + league.stints["away_poss"].sum()
    assert out["possessions"].sum() == pytest.approx(total)


def test_home_and_away_split_evenly(engine, league):
    out = engine.team_split("home_away").set_index("bucket")
    assert out.loc["home", "games"] == out.loc["away", "games"] == len(league.games)
    assert out.loc["home", "margin"] == pytest.approx(-out.loc["away", "margin"], abs=1e-6)


def test_opponent_quality_split_is_monotone(engine):
    """Teams do better against worse opponents. If not, the split is broken."""
    out = engine.team_split("opponent_tier").set_index("bucket")
    ordered = ["vs top quartile", "vs above average", "vs below average", "vs bottom quartile"]
    present = [b for b in ordered if b in out.index]
    margins = [out.loc[b, "margin"] for b in present]
    assert margins == sorted(margins), dict(zip(present, margins))


def test_team_split_can_be_narrowed_to_one_team(engine, league):
    team = league.teams["team_id"].iloc[0]
    out = engine.team_split("home_away", team_id=team)
    played = (league.games["home_team_id"] == team).sum() + \
             (league.games["away_team_id"] == team).sum()
    assert out["games"].sum() == played


def test_player_split_respects_the_rate_basis(engine, league):
    team = league.teams["team_id"].iloc[0]
    pid = league.roster(team)["player_id"].iloc[0]
    per36 = engine.player_split("home_away", player_id=pid, per_mode="per_36")
    per24 = engine.player_split("home_away", player_id=pid, per_mode="per_24")
    merged = per36.merge(per24, on="bucket", suffixes=("_36", "_24"))
    assert np.allclose(merged["pts_36"], merged["pts_24"] * 1.5)


def test_cross_split_covers_the_grid(engine, league):
    grid = engine.cross_split("rest", "home_away")
    assert grid["games"].sum() == 2 * len(league.games)
    assert grid["off_rating"].between(80, 150).all()


def test_with_without_reports_all_three_shared_states(engine, league):
    team = league.teams["team_id"].iloc[0]
    roster = league.roster(team)["player_id"]
    out = engine.with_without(roster.iloc[0], teammate_id=roster.iloc[1])
    assert set(out["state"]) <= {"both_on", "a_only", "b_only"}
    assert (out["poss"] > 0).all()
    assert out["net_rating"].notna().all()


def test_single_player_with_without_returns_one_row(engine, league):
    team = league.teams["team_id"].iloc[0]
    pid = league.roster(team)["player_id"].iloc[0]
    out = engine.with_without(pid)
    assert len(out) == 1
    assert out["player_id"].iloc[0] == pid


def test_garbage_time_is_a_small_slice(engine):
    out = engine.lineup_split("garbage_time").set_index("bucket")
    if "garbage time" in out.index:
        share = out.loc["garbage time", "possessions"] / out["possessions"].sum()
        assert share < 0.12, f"garbage time was {share:.1%} of possessions"


def test_clutch_is_a_small_slice(engine):
    out = engine.lineup_split("clutch").set_index("bucket")
    if "clutch" in out.index:
        share = out.loc["clutch", "possessions"] / out["possessions"].sum()
        assert share < 0.15


def test_unknown_vertical_is_rejected(engine):
    with pytest.raises(KeyError, match="unknown vertical"):
        engine.team_split("not_a_thing")


def test_using_a_vertical_at_the_wrong_level_is_rejected(engine):
    with pytest.raises(ValueError, match="possession-level"):
        engine.team_split("clutch")
    with pytest.raises(ValueError, match="game-level"):
        engine.lineup_split("rest")


def test_possession_verticals_require_play_by_play(source):
    from hoopsim.data import League

    lg = League.from_source(source, "2024-25", with_pbp=False)
    with pytest.raises(ValueError, match="play-by-play"):
        SplitEngine(lg).lineup_split("clutch")
