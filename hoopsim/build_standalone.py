"""Build a single self-contained HTML file: no install, no server, no terminal.

Double-click the result and it opens in a browser with the full interactive
lineup tool. Everything -- the data, the styles, the calculation engine -- is
inlined into one file you can email, drop on a desktop, or keep in a folder.

The browser cannot run Python, so the lineup arithmetic is re-implemented in
JavaScript (`web/engine.js`). That is a real risk: a silent divergence would
make the file confidently wrong. Two things guard against it.

First, every tunable number is exported from `constants.py` into the payload
rather than retyped in JavaScript, so there is one source of truth.

Second, `tests/test_standalone.py` runs the JavaScript engine under node and
compares it against the Python engine lineup by lineup, to six decimal places.
If they drift, the test fails.

    python build_standalone.py --out hoopsim.html
    python build_standalone.py --source nba --season 2024-25 --out nba.html
"""

from __future__ import annotations

import argparse
import json
import math
from datetime import date
from pathlib import Path

import numpy as np

from hoopsim import __version__, constants as K
from hoopsim.context import Analysis

WEB = Path(__file__).resolve().parent / "web"

#: A few rules that only the standalone build needs, appended to styles.css.
STANDALONE_CSS = """
.intro { background: var(--surface-2); border-left: 3px solid var(--accent);
  padding: 10px 14px; border-radius: 6px; margin-bottom: 14px; font-size: 14px; }
.intro p { margin: 0 0 6px; }
.intro p:last-child { margin-bottom: 0; }
.provenance { color: var(--muted); font-size: 12px; margin-top: 24px;
  border-top: 1px solid var(--border); padding-top: 12px; }
.empty { color: var(--muted); font-size: 14px; padding: 18px 0; text-align: center; }
"""

#: Counting stats the browser can put on any rate basis.
COUNT_COLUMNS = [
    "pts", "fgm", "fga", "fg3m", "fg3a", "ftm", "fta", "orb", "drb", "trb",
    "ast", "stl", "blk", "tov", "pf",
]

#: Rate metrics, carried as-is because they do not scale with a denominator.
RATE_COLUMNS = [
    "ts_pct", "efg_pct", "fg_pct", "fg3_pct", "ft_pct", "fg3a_rate", "ft_rate",
    "usage_rate", "ast_rate", "tov_rate", "orb_rate", "drb_rate", "trb_rate",
    "stl_rate", "blk_rate", "per", "ws", "ws_per_48", "ows", "dws",
    "box_impact", "off_rating", "def_rating", "game_score_per_game",
]

TEAM_COLUMNS = [
    "team_id", "team_abbrev", "team_name", "conference", "w", "l", "win_pct",
    "pace", "off_rating", "def_rating", "net_rating", "adj_off_rating",
    "adj_def_rating", "adj_net_rating", "srs", "sos", "pythag_win_pct", "luck",
    "off_efg_pct", "off_tov_rate", "off_orb_rate", "off_ft_rate",
    "def_efg_pct", "def_tov_rate", "def_drb_rate", "def_ft_rate",
]


#: Precision for exported numbers. This is not cosmetic: the browser engine
#: recomputes ratings from these values, so rounding here shows up as drift
#: against the Python engine. tests/test_standalone.py compares the two to
#: 1e-4, which these digits comfortably clear while keeping the file small.
MODEL_DIGITS = 6      # anything the lineup model reads
COUNT_DIGITS = 2      # counting stats, which are whole numbers anyway
DENOM_DIGITS = 3      # minutes and possessions, the rate denominators


def _clean(value, digits: int = 4):
    """JSON-safe, and rounded so the file does not carry useless precision."""
    if value is None:
        return None
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, (np.integer, int)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        f = float(value)
        return None if (math.isnan(f) or math.isinf(f)) else round(f, digits)
    return str(value)


def export_constants(model) -> dict:
    """Every tunable the browser engine needs, straight from constants.py.

    Exported rather than retyped so the JavaScript cannot drift from Python.
    """
    return {
        "players_on_floor": K.PLAYERS_ON_FLOOR,
        "positions": list(K.POSITIONS),
        "position_coverage": {k: list(v) for k, v in K.POSITION_COVERAGE.items()},

        "usage_efficiency_slope": K.USAGE_EFFICIENCY_SLOPE,
        "usage_efficiency_slope_down": K.USAGE_EFFICIENCY_SLOPE_DOWN,
        "usage_curve_convexity": K.USAGE_CURVE_CONVEXITY,
        "usage_absorption_exponent": K.USAGE_ABSORPTION_EXPONENT,
        "usage_floor": K.USAGE_FLOOR,
        "usage_ceiling": K.USAGE_CEILING,

        "fit_weights": dict(model.fit_weights),
        "coverage_thresholds": dict(model.coverage_thresholds),
        "redundancy_penalty": K.LINEUP_REDUNDANCY_PENALTY,
        "redundancy_threshold": K.LINEUP_REDUNDANCY_THRESHOLD,

        "per_minute_bases": {k: v for k, v in K.PER_MINUTE_BASES.items() if v},
        "per_possession_bases": dict(K.PER_POSSESSION_BASES),

        "home_advantage": K.DEFAULT_HOME_ADVANTAGE,
        "game_margin_sd": K.GAME_MARGIN_SD,
        "rest_adjustment": {str(k): v for k, v in K.REST_ADJUSTMENT.items()},
        "rest_adjustment_default": K.REST_ADJUSTMENT_DEFAULT,
        "pace": K.LEAGUE_DEFAULTS["pace"],
        "pace_sd": 3.5,
        "efficiency_shock_sd": 2.5,
        "mean_reversion": K.GAME_MEAN_REVERSION,
        "possession_outcomes": [0, 1, 2, 3, 4],
        "possession_base_probs": [0.470, 0.042, 0.279, 0.187, 0.022],
    }


def build_payload(analysis: Analysis, *, splits: bool = True) -> dict:
    """Everything the standalone file needs, as one JSON-serialisable dict."""
    model = analysis.lineup_model
    metrics = analysis.players.set_index("player_id")
    rapm = None
    if analysis.rapm is not None:
        rapm = analysis.rapm.ratings.set_index("player_id")

    players = []
    for pid, profile in model.profiles.items():
        row = metrics.loc[pid] if pid in metrics.index else None
        entry = {
            "player_id": pid,
            "name": profile.name,
            "team_id": str(row["team_id"]) if row is not None else "",
            "position": profile.position,
            "off_impact": _clean(profile.off_impact, MODEL_DIGITS),
            "def_impact": _clean(profile.def_impact, MODEL_DIGITS),
            "impact": _clean(profile.total_impact, MODEL_DIGITS),
            "usage": _clean(profile.usage, MODEL_DIGITS),
            "ts_pct": _clean(profile.ts_pct, MODEL_DIGITS),
        }
        for skill in ("spacing", "rim_pressure", "playmaking", "rebounding",
                      "rim_protection"):
            entry[skill] = _clean(getattr(profile, skill), MODEL_DIGITS)
        if row is not None:
            entry["min"] = _clean(row.get("min"), DENOM_DIGITS)
            entry["games"] = _clean(row.get("games"), 0)
            entry["poss"] = _clean(row.get("poss"), DENOM_DIGITS)
            entry["age"] = _clean(row.get("age"), 1)
            for c in COUNT_COLUMNS:
                entry[c] = _clean(row.get(c), COUNT_DIGITS)
            for c in RATE_COLUMNS:
                if c in row.index:
                    entry[c] = _clean(row.get(c), MODEL_DIGITS)
        if rapm is not None and pid in rapm.index:
            entry["rapm"] = _clean(rapm.loc[pid, "rapm"], 3)
            entry["rapm_off"] = _clean(rapm.loc[pid, "rapm_off"], 3)
            entry["rapm_def"] = _clean(rapm.loc[pid, "rapm_def"], 3)
            entry["rapm_poss"] = _clean(rapm.loc[pid, "possessions"], 0)
        players.append(entry)

    teams_frame = analysis.teams
    teams = []
    for r in teams_frame.to_dict("records"):
        teams.append({c: _clean(r.get(c), 4) for c in TEAM_COLUMNS if c in r})

    split_data = {}
    if splits:
        from hoopsim.splits import available

        for dim in available():
            try:
                if dim.level == "possession":
                    frame = analysis.splits.lineup_split(dim.key)
                else:
                    frame = analysis.splits.team_split(dim.key)
            except (ValueError, KeyError):
                continue
            if frame is None or frame.empty:
                continue
            split_data[dim.key] = {
                "label": dim.label,
                "level": dim.level,
                "description": dim.description,
                "rows": [{k: _clean(v, 4) for k, v in row.items()}
                         for row in frame.to_dict("records")],
            }

    ratings = analysis.team_ratings()

    return {
        "meta": {
            "version": __version__,
            "season": analysis.league.season,
            "source": analysis.league.source.name,
            "generated": date.today().isoformat(),
            # Full precision: this is the baseline every offensive and
            # defensive rating is built on, so rounding it shifts them all.
            "league_off_rating": _clean(model.league_off_rating, MODEL_DIGITS),
            "has_pbp": bool(analysis.league.has_pbp),
            "n_games": int(len(analysis.league.games)),
        },
        "constants": export_constants(model),
        "count_columns": COUNT_COLUMNS,
        "players": players,
        "teams": teams,
        "splits": split_data,
        "ratings": {t: _clean(v, 3) for t, v in ratings.items()},
    }


def render(payload: dict, *, template: Path | None = None,
           engine: Path | None = None) -> str:
    """Inline the engine and the data into the template."""
    template = template or (WEB / "standalone.html")
    engine = engine or (WEB / "engine.js")
    html = template.read_text(encoding="utf-8")

    css = (WEB / "styles.css").read_text(encoding="utf-8") + STANDALONE_CSS
    engine_js = engine.read_text(encoding="utf-8")
    app_js = (WEB / "standalone_app.js").read_text(encoding="utf-8")

    data_json = json.dumps(payload, separators=(",", ":"), allow_nan=False)
    # `</script>` inside a string literal would close the tag early.
    data_json = data_json.replace("</", "<\\/")

    for marker, replacement in (("/*__HOOPSIM_CSS__*/", css),
                                ("/*__HOOPSIM_ENGINE__*/", engine_js),
                                ("/*__HOOPSIM_APP__*/", app_js),
                                ("/*__HOOPSIM_DATA__*/", data_json)):
        if marker not in html:
            raise ValueError(f"template is missing the {marker} marker")
        html = html.replace(marker, replacement)
    return html


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Build a double-clickable single-file version of hoopsim.")
    parser.add_argument("--out", default="hoopsim.html", help="file to write")
    parser.add_argument("--source", default="synthetic",
                        choices=["synthetic", "nba", "csv"])
    parser.add_argument("--season", default="2024-25")
    parser.add_argument("--teams", type=int, default=30)
    parser.add_argument("--games", type=int, default=41)
    parser.add_argument("--seed", type=int, default=20251001)
    parser.add_argument("--directory", help="data directory, with --source csv")
    parser.add_argument("--no-splits", action="store_true")
    args = parser.parse_args(argv)

    print(f"loading {args.source} data ...", flush=True)
    if args.source == "synthetic":
        analysis = Analysis.synthetic(n_teams=args.teams, games_per_team=args.games,
                                      season=args.season, seed=args.seed)
    elif args.source == "nba":
        analysis = Analysis.from_nba(args.season)
    else:
        if not args.directory:
            raise SystemExit("--directory is required with --source csv")
        analysis = Analysis.from_csv(args.directory, args.season)

    print("computing metrics and impact ratings ...", flush=True)
    payload = build_payload(analysis, splits=not args.no_splits)

    out = Path(args.out)
    out.write_text(render(payload), encoding="utf-8")
    size = out.stat().st_size
    print(f"\nwrote {out}  ({size / 1024:.0f} KB)")
    print(f"  {len(payload['players'])} players, {len(payload['teams'])} teams, "
          f"{len(payload['splits'])} verticals")
    print("\nDouble-click it. No install, no terminal, no internet needed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
