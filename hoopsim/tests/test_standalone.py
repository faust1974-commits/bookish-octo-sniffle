"""The standalone file must give the same answers as the Python engine.

The browser cannot run Python, so `web/engine.js` re-implements the lineup
model. That is a genuine hazard: if the two drift, the double-clickable file
becomes confidently wrong and nothing would notice.

So these tests run the JavaScript under node and compare it against the Python
engine number by number. If someone changes a formula on one side only, this
fails.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from build_standalone import build_payload, render  # noqa: E402

NODE = shutil.which("node")
requires_node = pytest.mark.skipif(NODE is None, reason="node is not installed")

TOLERANCE = 1e-6


@pytest.fixture(scope="module")
def payload(analysis):
    return build_payload(analysis, splits=True)


def _run_node(payload: dict, script: str, tmp_path: Path):
    """Evaluate `script` with the engine and payload in scope."""
    data_file = tmp_path / "payload.json"
    data_file.write_text(json.dumps(payload), encoding="utf-8")
    runner = tmp_path / "run.js"
    # Load the engine exactly as the browser does -- execute the script, then
    # read the global it defines. Using require() here would test a path the
    # browser never takes (and the repo is ESM, so it would not even work).
    runner.write_text(
        "const fs = require('fs');\n"
        "new Function(fs.readFileSync(%s, 'utf8'))();\n"
        "const E = globalThis.HoopsimEngine;\n"
        "if (!E) throw new Error('engine.js did not define HoopsimEngine');\n"
        "const D = JSON.parse(fs.readFileSync(%s, 'utf8'));\n"
        "D.playersById = {};\n"
        "for (const p of D.players) D.playersById[p.player_id] = p;\n"
        "const K = D.constants;\n"
        "%s\n" % (
            json.dumps(str(ROOT / "web" / "engine.js")),
            json.dumps(str(data_file)),
            script,
        ),
        encoding="utf-8",
    )
    proc = subprocess.run([NODE, str(runner)], capture_output=True, text=True, timeout=120)
    if proc.returncode != 0:
        raise AssertionError(f"node failed:\n{proc.stderr}")
    return json.loads(proc.stdout)


def _sample_lineups(analysis, n: int = 6):
    """A spread of lineups: starters, bench, and mixes, across teams."""
    out = []
    for team in analysis.league.teams["team_id"].head(3):
        pool = analysis.roster_profiles(team, top=10)
        if len(pool) >= 10:
            out.append(pool[:5])
            out.append(pool[5:10])
            out.append([pool[0], pool[2], pool[4], pool[6], pool[8]])
    return out[:n]


# ---------------------------------------------------------------- parity

@requires_node
def test_lineup_ratings_match_python_exactly(analysis, payload, tmp_path):
    lineups = _sample_lineups(analysis)
    assert lineups, "no lineups to compare"

    script = (
        "const lineups = %s;\n"
        "const out = lineups.map(l => {\n"
        "  const ev = E.evaluateLineup(D, l);\n"
        "  return {net: ev.net_rating, off: ev.off_rating, def: ev.def_rating,\n"
        "          aoff: ev.additive_off, adef: ev.additive_def,\n"
        "          usage: ev.usage_effect, fit: ev.fit_bonus,\n"
        "          cov: ev.coverage_penalty};\n"
        "});\n"
        "console.log(JSON.stringify(out));" % json.dumps(lineups)
    )
    js = _run_node(payload, script, tmp_path)

    model = analysis.lineup_model
    for lineup, got in zip(lineups, js):
        ev = model.evaluate(lineup)
        for label, py, mine in (
            ("net_rating", ev.net_rating, got["net"]),
            ("off_rating", ev.off_rating, got["off"]),
            ("def_rating", ev.def_rating, got["def"]),
            ("additive_off", ev.additive_off, got["aoff"]),
            ("additive_def", ev.additive_def, got["adef"]),
            ("usage_effect", ev.usage_effect, got["usage"]),
            ("fit_bonus", ev.fit_bonus, got["fit"]),
            ("coverage_penalty", ev.coverage_penalty, got["cov"]),
        ):
            assert abs(py - mine) < 1e-4, (
                f"{label} drifted for {lineup}: python {py!r} vs javascript {mine!r}"
            )


@requires_node
def test_usage_redistribution_matches_python_exactly(analysis, payload, tmp_path):
    """The headline calculation. If this drifts, the file misleads people."""
    lineups = _sample_lineups(analysis, n=4)
    script = (
        "const lineups = %s;\n"
        "const out = lineups.map(l => E.evaluateLineup(D, l).usage_table.map(r => ({\n"
        "  id: r.player_id, usage: r.adjusted_usage, ts: r.adjusted_ts_pct,\n"
        "  effect: r.pts_per_100_effect})));\n"
        "console.log(JSON.stringify(out));" % json.dumps(lineups)
    )
    js = _run_node(payload, script, tmp_path)

    model = analysis.lineup_model
    for lineup, rows in zip(lineups, js):
        table = model.evaluate(lineup).usage_table.set_index("player_id")
        assert abs(sum(r["usage"] for r in rows) - 1.0) < 1e-6
        for row in rows:
            py = table.loc[row["id"]]
            assert abs(float(py["adjusted_usage"]) - row["usage"]) < TOLERANCE
            assert abs(float(py["adjusted_ts_pct"]) - row["ts"]) < TOLERANCE
            assert abs(float(py["pts_per_100_effect"]) - row["effect"]) < 1e-5


@requires_node
def test_swap_results_match_python_exactly(analysis, payload, tmp_path):
    team = analysis.league.teams["team_id"].iloc[0]
    pool = analysis.roster_profiles(team, top=8)
    five, sixth = pool[:5], pool[5]

    script = (
        "const r = E.swapPlayer(D, %s, %s, %s);\n"
        "console.log(JSON.stringify({change: r.net_change,\n"
        "  before: r.before.net_rating, after: r.after.net_rating}));"
        % (json.dumps(five), json.dumps(five[0]), json.dumps(sixth))
    )
    js = _run_node(payload, script, tmp_path)
    py = analysis.lineup_model.swap(five, five[0], sixth)
    assert abs(py.net_change - js["change"]) < 1e-4
    assert abs(py.before.net_rating - js["before"]) < 1e-4
    assert abs(py.after.net_rating - js["after"]) < 1e-4


@requires_node
def test_position_viability_matches_python(analysis, payload, tmp_path):
    lineups = _sample_lineups(analysis)
    script = (
        "console.log(JSON.stringify(%s.map(l => E.positionsViable(D, l))));"
        % json.dumps(lineups)
    )
    js = _run_node(payload, script, tmp_path)
    for lineup, got in zip(lineups, js):
        assert analysis.lineup_model.positions_viable(lineup) == got, lineup


@requires_node
def test_rate_bases_match_python(analysis, payload, tmp_path):
    from hoopsim.metrics.normalize import ALL_MODES, normalize

    ids = [p["player_id"] for p in payload["players"][:8]]
    modes = [m for m in ALL_MODES]
    script = (
        "const ids = %s, modes = %s;\n"
        "const out = {};\n"
        "for (const m of modes) out[m] = ids.map(i => E.normalize(D, D.playersById[i], m));\n"
        "console.log(JSON.stringify(out));" % (json.dumps(ids), json.dumps(modes))
    )
    js = _run_node(payload, script, tmp_path)

    metrics = analysis.players.set_index("player_id")
    for mode in modes:
        py = normalize(metrics.loc[ids].reset_index(), mode).set_index("player_id")
        for i, pid in enumerate(ids):
            for col in ("pts", "ast", "trb"):
                expected = float(py.loc[pid, col])
                actual = js[mode][i][col]
                assert abs(expected - actual) < 1e-3, f"{mode}/{col} for {pid}"


@requires_node
def test_win_probability_matches_python(payload, tmp_path):
    from hoopsim.sim import win_probability

    pairs = [[0, 0], [8, -1], [-3, 7], [12, -6], [2, -2]]
    script = (
        "console.log(JSON.stringify(%s.map(p => E.winProbability(K, p[0], p[1]))));"
        % json.dumps(pairs)
    )
    js = _run_node(payload, script, tmp_path)
    for (home, away), got in zip(pairs, js):
        assert abs(float(win_probability(home, away)) - got) < 1e-5


@requires_node
def test_simulation_is_reproducible_and_sane(payload, tmp_path):
    """Not a parity test -- different RNGs -- but it must land in the right place."""
    script = (
        "const a = E.simulateGame(D, 8, -1, 4000, 42);\n"
        "const b = E.simulateGame(D, 8, -1, 4000, 42);\n"
        "console.log(JSON.stringify({p: a.home_win_prob, same: a.home_win_prob === b.home_win_prob,\n"
        "  margin: a.mean_margin, sd: a.margin_sd,\n"
        "  analytic: E.winProbability(K, 8, -1)}));"
    )
    js = _run_node(payload, script, tmp_path)
    assert js["same"], "the same seed must reproduce the same simulation"
    assert abs(js["p"] - js["analytic"]) < 0.05, (js["p"], js["analytic"])
    assert 10.0 < js["margin"] < 13.0, js["margin"]
    assert 11.0 < js["sd"] < 16.0, js["sd"]


# ------------------------------------------------------------ the file

def test_payload_carries_constants_rather_than_duplicating_them(payload):
    """The JavaScript must read tunables from here, not hold its own copies."""
    from hoopsim import constants as K

    c = payload["constants"]
    assert c["usage_efficiency_slope"] == K.USAGE_EFFICIENCY_SLOPE
    assert c["usage_absorption_exponent"] == K.USAGE_ABSORPTION_EXPONENT
    assert c["redundancy_penalty"] == K.LINEUP_REDUNDANCY_PENALTY
    assert c["redundancy_threshold"] == K.LINEUP_REDUNDANCY_THRESHOLD
    assert c["game_margin_sd"] == K.GAME_MARGIN_SD
    assert c["home_advantage"] == K.DEFAULT_HOME_ADVANTAGE
    assert c["fit_weights"] == dict(K.LINEUP_FIT_WEIGHTS)
    assert c["coverage_thresholds"] == dict(K.LINEUP_COVERAGE_THRESHOLDS)
    assert c["players_on_floor"] == K.PLAYERS_ON_FLOOR


def test_engine_does_not_hardcode_tunables():
    """A literal in engine.js would be a copy that can silently go stale."""
    source = (ROOT / "web" / "engine.js").read_text(encoding="utf-8")
    from hoopsim import constants as K

    for value in (K.USAGE_EFFICIENCY_SLOPE, K.USAGE_ABSORPTION_EXPONENT,
                  K.LINEUP_REDUNDANCY_PENALTY, K.GAME_MARGIN_SD,
                  K.DEFAULT_HOME_ADVANTAGE):
        assert repr(value) not in source, (
            f"{value} is hardcoded in engine.js; read it from the payload instead"
        )


def test_rendered_file_is_self_contained(payload, tmp_path):
    html = render(payload)
    assert "/*__HOOPSIM_" not in html, "a template marker was left unfilled"
    assert "HoopsimEngine" in html and "window.__HOOPSIM__" in html
    # Nothing may be fetched at view time: no network of any kind.
    for pattern in ("src=\"http", "href=\"http", "fetch(", "XMLHttpRequest",
                    "import(", "<link "):
        assert pattern not in html, f"standalone file references {pattern}"
    out = tmp_path / "hoopsim.html"
    out.write_text(html, encoding="utf-8")
    assert out.stat().st_size < 8 * 1024 * 1024


def test_data_cannot_break_out_of_its_script_tag(analysis):
    """A '</script>' inside the data would end the tag early and break the page."""
    payload = build_payload(analysis, splits=False)
    payload["players"][0]["name"] = "</script><script>alert(1)</script>"
    html = render(payload)
    assert "</script><script>alert(1)" not in html
    assert "<\\/script>" in html
