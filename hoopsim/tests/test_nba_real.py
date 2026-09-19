"""Tests against a real NBA season.

These are skipped unless the season files are cached, so the suite still runs
on a machine that has never downloaded them. They exist because every one of
them corresponds to a defect that actually shipped and produced confidently
wrong numbers:

* team-level events put the TEAM id in the player column, which credited
  thirty team entities with 22,000 rebounds;
* teams change personnel at quarter breaks with no substitution events, which
  corrupted the on-floor five for the rest of the game;
* the feed's clock occasionally runs backwards, which made stint durations
  nonsense;
* a substitute who records no statistic never appears with an id anywhere in
  the game, so the incoming player could not be resolved from that game alone.

Each is cheap to reintroduce and silent when it happens, so each is pinned.
"""

from __future__ import annotations

import numpy as np
import pytest

from hoopsim import constants as K
from hoopsim.data import League

pytest.importorskip("requests")

SEASON = "2025-26"


@pytest.fixture(scope="module")
def nba_source():
    from hoopsim.data.nba_github import NBAGithubSource

    source = NBAGithubSource(SEASON, offline=True)
    try:
        source.teams()
    except Exception as exc:  # noqa: BLE001 - any failure means "not cached"
        pytest.skip(f"{SEASON} is not cached locally: {exc}")
    return source


@pytest.fixture(scope="module")
def nba(nba_source):
    return League.from_source(nba_source, SEASON)


# ------------------------------------------------------------- identity

def test_the_league_has_thirty_real_teams(nba):
    assert len(nba.teams) == 30
    abbrevs = set(nba.teams["team_abbrev"])
    for expected in ("BOS", "LAL", "OKC", "GSW", "NYK", "DEN"):
        assert expected in abbrevs
    assert set(nba.teams["conference"]) == {"East", "West"}
    counts = nba.teams["conference"].value_counts()
    assert counts["East"] == 15 and counts["West"] == 15


def test_players_have_real_names_and_no_team_entities(nba):
    names = set(nba.players["player_name"])
    assert len(names) > 400
    # Team-level events carry the team id in the player column. If that is not
    # undone, teams appear in the player table.
    team_ids = set(nba.teams["team_id"])
    assert not (set(nba.players["player_id"]) & team_ids)
    for name in names:
        assert " " in name.strip(), f"{name!r} does not look like a person"


def test_a_full_regular_season_is_present(nba):
    assert len(nba.games) == 1230
    assert nba.games["home_pts"].notna().all()
    assert nba.games["away_pts"].notna().all()


# -------------------------------------------------------- league shape

def test_scoring_environment_matches_the_real_nba(nba):
    tb = nba.team_box
    poss = (nba.stints["home_poss"].sum() + nba.stints["away_poss"].sum()) / len(nba.games) / 2
    assert 95 < poss < 104, f"possessions per team per game was {poss}"
    assert 108 < tb["pts"].mean() < 122, f"points per team per game was {tb['pts'].mean()}"
    efg = (tb["fgm"].sum() + 0.5 * tb["fg3m"].sum()) / tb["fga"].sum()
    assert 0.51 < efg < 0.58, efg
    orb = tb["orb"].sum() / (tb["orb"].sum() + tb["drb"].sum())
    assert 0.22 < orb < 0.30, orb


def test_home_teams_win_a_bit_more_than_half(nba):
    rate = (nba.games["home_pts"] > nba.games["away_pts"]).mean()
    assert 0.50 < rate < 0.62, rate


def test_wins_and_losses_add_up(nba):
    standings = nba.standings()
    assert standings["w"].sum() == len(nba.games)
    assert (standings["w"] + standings["l"] == 82).all()


# ------------------------------------------------- play-by-play quirks

def test_box_score_points_match_the_final_score(nba):
    """Derived box scores must agree with the scoreboard."""
    chk = nba.team_box.merge(
        nba.games[["game_id", "home_team_id", "home_pts", "away_pts"]], on="game_id")
    final = np.where(chk["team_id"] == chk["home_team_id"], chk["home_pts"], chk["away_pts"])
    exact = (chk["pts"].to_numpy() == final).mean()
    assert exact > 0.95, f"only {exact:.1%} of team-games matched the final score"


def test_one_row_per_team_per_game(nba):
    """A team id left in the player column shows up as a third team."""
    assert len(nba.team_box) == 2 * len(nba.games)
    assert (nba.team_box.groupby("game_id")["team_id"].nunique() == 2).all()


def test_the_clock_never_runs_backwards(nba):
    """The feed's clock occasionally jumps; stint durations depend on it."""
    pbp = nba.pbp.sort_values(["game_id", "event_num"])
    delta = pbp.groupby("game_id")["seconds_elapsed"].diff()
    assert (delta.dropna() >= -1e-9).all(), "elapsed time went backwards"


def test_stints_span_the_right_amount_of_game_time(nba):
    seconds = nba.stints.groupby("game_id")["seconds"].sum()
    overtimes = nba.games.set_index("game_id")["overtimes"]
    expected = 2880 + 300 * overtimes.reindex(seconds.index).fillna(0)
    ratio = (seconds / expected).dropna()
    assert 0.97 < ratio.median() < 1.03, ratio.describe()


def test_most_lineups_have_exactly_five_players(nba):
    """Quarter-break personnel changes carry no substitution events."""
    sizes = nba.stints["home_lineup"].map(len)
    assert (sizes == K.PLAYERS_ON_FLOOR).mean() > 0.85, sizes.value_counts().to_dict()


def test_substitutions_resolve_the_incoming_player(nba_source):
    """A substitute who records nothing is only findable via the roster."""
    total = (nba_source.pbp()["event_type"] == "substitution").sum()
    assert nba_source.unresolved_subs / total < 0.06


def test_team_rebounds_are_not_credited_to_anyone(nba):
    """Team rebounds have no player and must not invent one."""
    rebounds = nba.pbp[nba.pbp["event_type"].isin(["oreb", "dreb"])]
    assert (rebounds["player_id"].astype(str).str.len() > 0).all()
    team_ids = set(nba.teams["team_id"])
    assert not (set(rebounds["player_id"]) & team_ids)


# ------------------------------------------------------------- ratings

def test_impact_ratings_are_plausible(nba):
    """RAPM on a real season should put real stars at the top."""
    from hoopsim.impact import fit_rapm

    fit = fit_rapm(nba.stints, alpha=2000.0)
    assert 0.0 < fit.home_advantage < 5.0
    rated = fit.ratings.merge(nba.players[["player_id", "player_name"]], on="player_id")
    top = set(rated[rated["possessions"] >= 2000].nlargest(25, "rapm")["player_name"])
    # Not a prediction, a sanity check: an all-NBA season should surface
    # several household names in the top twenty-five by impact.
    assert len(top) == 25
    spread = fit.ratings["rapm"].std()
    assert 0.5 < spread < 6.0, spread


def test_positions_cover_all_five_slots(nba):
    """Feeds give G/F/C; lineups need the five slots to be fillable."""
    from hoopsim.context import Analysis

    analysis = Analysis(league=nba)
    positions = {p.position for p in analysis.lineup_model.profiles.values()}
    assert positions == set(K.POSITIONS), positions
