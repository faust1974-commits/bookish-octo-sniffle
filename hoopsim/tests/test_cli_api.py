"""The CLI and the HTTP API are the surfaces people actually touch."""

import json

import pytest

from hoopsim.api import Api, ApiError
from hoopsim.cli import build_parser, main


# ------------------------------------------------------------------- CLI

SMALL = ["--teams", "6", "--games", "8", "--seed", "3"]


@pytest.mark.parametrize("argv", [
    ["metrics"],
    ["teams"] + SMALL,
    ["players"] + SMALL + ["--min-minutes", "50", "--top", "5"],
    ["players"] + SMALL + ["--per", "per_100", "--min-minutes", "50", "--top", "5"],
    ["rapm"] + SMALL + ["--min-possessions", "50", "--top", "5"],
    ["project"] + SMALL + ["--top", "5"],
    ["splits", "list"] + SMALL,
    ["splits", "rest"] + SMALL,
    ["splits", "clutch"] + SMALL,
    ["best-lineups", "--team", "T00", "--pool", "7", "--top", "3"] + SMALL,
    ["game", "--home", "T00", "--away", "T01", "--sims", "500"] + SMALL,
    ["season", "--sims", "40", "--from-scratch"] + SMALL,
])
def test_cli_commands_succeed(argv, capsys):
    assert main(argv) == 0
    out = capsys.readouterr().out
    assert out.strip(), f"{argv[0]} produced no output"


def test_cli_lineup_and_swap_accept_names_and_ids(capsys):
    from hoopsim.context import Analysis

    a = Analysis.synthetic(n_teams=6, games_per_team=8, seed=3)
    pool = a.roster_profiles(a.league.teams["team_id"].iloc[0], top=6)
    assert main(["lineup"] + SMALL + pool[:5]) == 0
    assert "net rating" in capsys.readouterr().out

    name = a.league.player_name(pool[0])
    assert main(["swap"] + SMALL + pool[:5] + ["--out", name, "--in", pool[5]]) == 0
    assert "Swap" in capsys.readouterr().out


def test_cli_reports_unknown_players_clearly(capsys):
    with pytest.raises(SystemExit, match="no player matching"):
        main(["lineup"] + SMALL + ["nobody", "P0001", "P0002", "P0003", "P0004"])


def test_cli_reports_unknown_teams_clearly():
    with pytest.raises(SystemExit, match="no team matching"):
        main(["best-lineups", "--team", "Narnia"] + SMALL)


def test_cli_rejects_an_unknown_vertical(capsys):
    with pytest.raises(SystemExit, match="unknown vertical"):
        main(["splits", "phase_of_the_moon"] + SMALL)


def test_cli_surfaces_errors_rather_than_tracebacks(capsys, monkeypatch):
    """An unexpected failure should print one line and exit non-zero."""
    from hoopsim import cli

    def boom(_args):
        raise RuntimeError("something broke")

    monkeypatch.setattr(cli, "cmd_teams", boom)
    # The parser binds cmd_teams at build time, so rebuild it under the patch.
    monkeypatch.setattr(cli, "build_parser", _parser_with(cli, "teams", boom))

    assert cli.main(["teams"] + SMALL) == 1
    captured = capsys.readouterr()
    assert "something broke" in captured.err
    assert "Traceback" not in captured.err


def _parser_with(cli_module, command, func):
    """Return a build_parser that swaps one command's handler."""
    original = cli_module.build_parser

    def build():
        parser = original()
        sub = next(a for a in parser._actions if hasattr(a, "choices") and a.choices)
        sub.choices[command].set_defaults(func=func)
        return parser

    return build


def test_parser_exposes_every_command():
    parser = build_parser()
    sub = next(a for a in parser._actions if hasattr(a, "choices") and a.choices)
    expected = {"demo", "players", "teams", "rapm", "lineup", "swap", "best-lineups",
                "rotation", "splits", "project", "game", "season", "metrics", "serve"}
    assert expected <= set(sub.choices)


# ------------------------------------------------------------------- API

@pytest.fixture(scope="module")
def api(analysis):
    return Api(analysis)


def test_state_describes_the_league(api, analysis):
    state = api.state({})
    assert state["season"] == analysis.league.season
    assert state["has_pbp"] is True
    assert len(state["teams"]) == len(analysis.league.teams)
    assert len(state["players"]) > 0
    assert len(state["per_modes"]) == 8
    assert len(state["verticals"]) >= 10
    for p in state["players"]:
        assert {"player_id", "name", "position", "impact", "usage"} <= set(p)


def test_every_payload_is_json_serialisable(api, analysis):
    """NaN and numpy types must not reach the browser."""
    team = analysis.league.teams["team_id"].iloc[0]
    five = api.analysis.roster_profiles(team, top=6)
    payloads = [
        api.state({}), api.teams({}), api.players({"per": ["per_36"]}),
        api.rapm({"min_possessions": ["50"]}),
        api.splits({"dimension": ["rest"]}),
        api.splits({"dimension": ["clutch"]}),
        api.best_lineups({"team": [team], "pool": ["7"], "top": ["3"]}),
        api.evaluate({"players": five[:5]}),
        api.swap({"players": five[:5], "out": five[0], "in": five[5]}),
        api.projections({}),
    ]
    for payload in payloads:
        text = json.dumps(payload)
        assert "NaN" not in text and "Infinity" not in text


def test_evaluate_rejects_a_bad_lineup(api):
    with pytest.raises(ApiError, match="exactly five"):
        api.evaluate({"players": ["a", "b"]})
    with pytest.raises(ApiError):
        api.evaluate({"players": ["a", "b", "c", "d", "e"]})


def test_swap_payload_carries_before_after_and_shifts(api, analysis):
    team = analysis.league.teams["team_id"].iloc[0]
    five = api.analysis.roster_profiles(team, top=6)
    out = api.swap({"players": five[:5], "out": five[0], "in": five[5]})
    assert out["net_change"] == pytest.approx(
        out["after"]["net_rating"] - out["before"]["net_rating"], abs=1e-6)
    assert len(out["usage_shifts"]) >= 5


def test_game_payload_has_a_histogram_and_both_models(api, analysis):
    teams = analysis.league.teams["team_id"].tolist()
    out = api.game({"home": teams[0], "away": teams[1], "sims": 2000})
    assert 0.0 <= out["summary"]["home_win_prob"] <= 1.0
    assert 0.0 <= out["closed_form_win_prob"] <= 1.0
    assert len(out["margin_histogram"]["counts"]) == 41
    assert len(out["margin_histogram"]["edges"]) == 42


def test_game_rejects_a_team_playing_itself(api, analysis):
    team = analysis.league.teams["team_id"].iloc[0]
    with pytest.raises(ApiError, match="cannot play itself"):
        api.game({"home": team, "away": team})


def test_unknown_vertical_raises_an_api_error(api):
    with pytest.raises(ApiError, match="unknown vertical"):
        api.splits({"dimension": ["nope"]})


def test_best_lineups_requires_a_team(api):
    with pytest.raises(ApiError, match="team"):
        api.best_lineups({})


def test_web_assets_are_found_and_complete():
    from hoopsim.api import WEB_ROOT

    for name in ("index.html", "app.js", "styles.css"):
        assert (WEB_ROOT / name).is_file(), f"{name} missing from {WEB_ROOT}"
