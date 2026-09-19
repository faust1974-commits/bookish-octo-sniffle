"""The data layer must produce internally consistent basketball."""

import numpy as np
import pytest

from hoopsim import constants as K
from hoopsim.data import League, SyntheticSource
from hoopsim.data.pbp import _is_id, build_stints, infer_starters, minutes_from_stints


def test_team_minutes_total_240_per_regulation_game(league):
    """Five players on the floor for 48 minutes is exactly 240 team minutes."""
    merged = league.team_box.merge(league.games[["game_id", "overtimes"]], on="game_id")
    expected = K.TEAM_MINUTES_PER_GAME + merged["overtimes"] * K.MINUTES_PER_OT * 5
    assert np.allclose(merged["min"], expected, atol=0.01)


def test_box_score_points_equal_final_score(league):
    """A box score that disagrees with the scoreboard is worthless."""
    chk = league.team_box.merge(
        league.games[["game_id", "home_team_id", "home_pts", "away_pts"]], on="game_id")
    final = np.where(chk["team_id"] == chk["home_team_id"], chk["home_pts"], chk["away_pts"])
    assert np.array_equal(chk["pts"].to_numpy(), final)


def test_every_stint_has_exactly_five_players_per_side(league):
    stints = league.stints
    assert len(stints) > 0
    assert (stints["home_lineup"].map(len) == K.PLAYERS_ON_FLOOR).all()
    assert (stints["away_lineup"].map(len) == K.PLAYERS_ON_FLOOR).all()


def test_possessions_are_in_a_plausible_range(league):
    stints = league.stints
    per_team = (stints["home_poss"].sum() + stints["away_poss"].sum()) / len(league.games) / 2
    assert 90 < per_team < 108, f"possessions per team per game was {per_team}"


def test_no_null_player_ids_reach_the_box_score(league):
    """NaN is truthy; a naive check invents a player who plays every game."""
    assert league.box["player_id"].isna().sum() == 0
    assert (league.box["player_id"].astype(str) != "nan").all()
    games_per_player = league.box.groupby("player_id")["game_id"].nunique()
    assert games_per_player.max() <= len(league.games) / (len(league.teams) / 2)


@pytest.mark.parametrize("value,expected", [
    ("P0001", True), ("", False), ("0", False), (None, False),
    (float("nan"), False), ("nan", False), ("<NA>", False),
])
def test_is_id_rejects_every_flavour_of_missing(value, expected):
    assert _is_id(value) is expected


def test_generation_is_reproducible_from_the_seed():
    """A seeded simulation that does not reproduce is not a simulation."""
    a = League.from_source(SyntheticSource(n_teams=6, games_per_team=8, seed=7), "2024-25")
    b = League.from_source(SyntheticSource(n_teams=6, games_per_team=8, seed=7), "2024-25")
    assert a.team_box["pts"].sum() == b.team_box["pts"].sum()
    assert a.games["home_pts"].tolist() == b.games["home_pts"].tolist()
    assert len(a.stints) == len(b.stints)


def test_different_seeds_give_different_leagues():
    a = League.from_source(SyntheticSource(n_teams=6, games_per_team=8, seed=1), "2024-25")
    b = League.from_source(SyntheticSource(n_teams=6, games_per_team=8, seed=2), "2024-25")
    assert a.team_box["pts"].sum() != b.team_box["pts"].sum()


def test_minutes_from_stints_match_the_box_score(league):
    mins = minutes_from_stints(league.stints)
    merged = mins.merge(league.box[["game_id", "player_id", "min"]],
                        on=["game_id", "player_id"], suffixes=("_stint", "_box"))
    assert np.allclose(merged["min_stint"], merged["min_box"], atol=1e-6)


def test_infer_starters_finds_five_per_team(league):
    game_id = league.pbp["game_id"].iloc[0]
    game = league.pbp[league.pbp["game_id"] == game_id]
    starters = infer_starters(game)
    assert len(starters) == 2
    for five in starters.values():
        assert len(five) == K.PLAYERS_ON_FLOOR


def test_schedule_gives_every_team_its_games(source):
    games = source.games()
    counts = {}
    for r in games.itertuples(index=False):
        counts[r.home_team_id] = counts.get(r.home_team_id, 0) + 1
        counts[r.away_team_id] = counts.get(r.away_team_id, 0) + 1
    assert set(counts.values()) == {source.games_per_team}


def test_league_without_pbp_refuses_lineup_work(source):
    lg = League.from_source(source, "2024-25", with_pbp=False)
    assert not lg.has_pbp
    with pytest.raises(ValueError, match="play-by-play"):
        _ = lg.stints
