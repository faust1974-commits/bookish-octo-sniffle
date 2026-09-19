"""HTTP server for the browser interface.

Built on the standard library rather than a web framework, deliberately: the
whole point of this tool is that you can run it without assembling a stack.
`pip install hoopsim` and `hoopsim serve` is the entire setup.

The league is loaded once at startup and held in memory. Every expensive
derived layer -- stints, RAPM, the lineup model -- is computed lazily by
`Analysis` and cached, so the first request that needs one pays for it and the
rest are immediate.
"""

from __future__ import annotations

import json
import math
import mimetypes
import threading
import traceback
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import numpy as np
import pandas as pd

from . import __version__
from .context import Analysis

def _find_web_root() -> Path:
    """Locate the static files, however the package happens to be installed."""
    here = Path(__file__).resolve()
    candidates = [
        here.parent / "web",                    # packaged inside hoopsim/
        here.parent.parent.parent / "web",      # running from a source checkout
        Path.cwd() / "web",
    ]
    for candidate in candidates:
        if (candidate / "index.html").is_file():
            return candidate
    return candidates[1]


WEB_ROOT = _find_web_root()


def _clean(value):
    """Make numpy and pandas values JSON-serialisable, NaN included."""
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        f = float(value)
        return None if (math.isnan(f) or math.isinf(f)) else round(f, 6)
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, (frozenset, set, tuple)):
        return [_clean(v) for v in value]
    if isinstance(value, (list,)):
        return [_clean(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _clean(v) for k, v in value.items()}
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    if isinstance(value, (np.ndarray,)):
        return [_clean(v) for v in value.tolist()]
    return value


def _records(frame: pd.DataFrame, limit: int | None = None) -> list[dict]:
    if frame is None or len(frame) == 0:
        return []
    if limit:
        frame = frame.head(limit)
    return [{k: _clean(v) for k, v in row.items()} for row in frame.to_dict("records")]


class ApiError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


class Api:
    """The analysis, wrapped in JSON endpoints."""

    def __init__(self, analysis: Analysis):
        self.analysis = analysis
        self._lock = threading.Lock()

    # -- endpoints ----------------------------------------------------------

    def state(self, _query) -> dict:
        a = self.analysis
        teams = a.league.teams[["team_id", "team_name", "team_abbrev", "conference"]]
        model = a.lineup_model
        players = []
        for pid, p in model.profiles.items():
            players.append({
                "player_id": pid, "name": p.name, "position": p.position,
                "team_id": str(a.league.player_index.loc[pid, "team_id"])
                if pid in a.league.player_index.index else "",
                "minutes": round(p.minutes, 1),
                "off_impact": round(p.off_impact, 2),
                "def_impact": round(p.def_impact, 2),
                "impact": round(p.total_impact, 2),
                "usage": round(p.usage, 4),
                "ts_pct": round(p.ts_pct, 4),
                "spacing": round(p.spacing, 2),
                "rim_pressure": round(p.rim_pressure, 2),
                "playmaking": round(p.playmaking, 2),
                "rebounding": round(p.rebounding, 2),
                "rim_protection": round(p.rim_protection, 2),
            })
        from .metrics.normalize import ALL_MODES
        from .splits import available

        return {
            "version": __version__,
            "season": a.league.season,
            "source": a.league.source.name,
            "has_pbp": a.league.has_pbp,
            "league_off_rating": round(model.league_off_rating, 2),
            "teams": _records(teams),
            "players": players,
            "per_modes": ALL_MODES,
            "verticals": [{"key": d.key, "label": d.label, "level": d.level,
                           "description": d.description} for d in available()],
        }

    def players(self, query) -> dict:
        from .metrics.normalize import normalize

        per = query.get("per", ["per_36"])[0]
        min_minutes = float(query.get("min_minutes", ["250"])[0])
        team = query.get("team", [None])[0]
        df = self.analysis.players
        df = df[df["min"] >= min_minutes]
        if team:
            df = df[df["team_id"] == team]
        df = normalize(df, per)
        cols = ["player_id", "player_name", "team_id", "position", "games", "min",
                "pts", "trb", "ast", "stl", "blk", "tov", "ts_pct", "efg_pct",
                "fg3_pct", "usage_rate", "ast_rate", "trb_rate", "per", "ws",
                "ws_per_48", "box_impact", "off_rating", "def_rating"]
        cols = [c for c in cols if c in df.columns]
        return {"per_mode": per, "rows": _records(df[cols].sort_values(
            "box_impact", ascending=False), limit=600)}

    def teams(self, _query) -> dict:
        cols = ["team_id", "team_abbrev", "team_name", "conference", "w", "l",
                "win_pct", "pace", "off_rating", "def_rating", "net_rating",
                "adj_off_rating", "adj_def_rating", "adj_net_rating", "srs", "sos",
                "pythag_win_pct", "luck", "off_efg_pct", "off_tov_rate",
                "off_orb_rate", "off_ft_rate", "def_efg_pct", "def_tov_rate",
                "def_drb_rate", "def_ft_rate"]
        df = self.analysis.teams
        return {"rows": _records(df[[c for c in cols if c in df.columns]])}

    def rapm(self, query) -> dict:
        a = self.analysis
        if a.rapm is None:
            raise ApiError("RAPM needs play-by-play data, which this source has none of", 409)
        min_poss = float(query.get("min_possessions", ["300"])[0])
        df = a.rapm.ratings.merge(
            a.league.players.drop_duplicates("player_id")[
                ["player_id", "player_name", "position", "team_id"]],
            on="player_id", how="left")
        df = df[df["possessions"] >= min_poss]
        return {
            "home_advantage": round(a.rapm.home_advantage, 3),
            "alpha": a.rapm.alpha,
            "rows": _records(df.sort_values("rapm", ascending=False), limit=600),
        }

    def evaluate(self, body) -> dict:
        players = body.get("players") or []
        if len(players) != 5:
            raise ApiError("a lineup is exactly five players")
        opponent = body.get("opponent") or None
        try:
            ev = self.analysis.lineup_model.evaluate(players, opponent=opponent)
        except (KeyError, ValueError) as exc:
            raise ApiError(str(exc)) from exc
        return self._evaluation_payload(ev)

    def swap(self, body) -> dict:
        players = body.get("players") or []
        out_p, in_p = body.get("out"), body.get("in")
        if len(players) != 5 or not out_p or not in_p:
            raise ApiError("need five players plus `out` and `in`")
        try:
            result = self.analysis.lineup_model.swap(players, out_p, in_p)
        except (KeyError, ValueError) as exc:
            raise ApiError(str(exc)) from exc
        return {
            "out_player": result.out_player, "in_player": result.in_player,
            "out_name": result.out_name, "in_name": result.in_name,
            "net_change": round(result.net_change, 3),
            "before": self._evaluation_payload(result.before),
            "after": self._evaluation_payload(result.after),
            "usage_shifts": _records(result.usage_shifts),
        }

    def best_lineups(self, query) -> dict:
        team = query.get("team", [None])[0]
        if not team:
            raise ApiError("`team` is required")
        pool_size = int(query.get("pool", ["10"])[0])
        top = int(query.get("top", ["12"])[0])
        pool = self.analysis.roster_profiles(team, top=pool_size)
        if len(pool) < 5:
            raise ApiError("not enough players with profiles on that team", 409)
        best = self.analysis.lineup_model.best_lineups(pool, top=top)
        return {"rows": _records(best)}

    def best_replacement(self, body) -> dict:
        players = body.get("players") or []
        out_p = body.get("out")
        if len(players) != 5 or not out_p:
            raise ApiError("need five players plus `out`")
        candidates = body.get("candidates")
        try:
            rows = self.analysis.lineup_model.best_replacement(
                players, out_p, candidates=candidates, top=int(body.get("top", 12)))
        except (KeyError, ValueError) as exc:
            raise ApiError(str(exc)) from exc
        return {"rows": _records(rows)}

    def rotation(self, query) -> dict:
        from .projection import RotationConstraints, optimize_rotation

        team = query.get("team", [None])[0]
        if not team:
            raise ApiError("`team` is required")
        pool = self.analysis.roster_profiles(team, top=int(query.get("pool", ["10"])[0]))
        cons = RotationConstraints(
            max_minutes_per_player=float(query.get("max_minutes", ["36"])[0]),
            max_players=int(query.get("max_players", ["9"])[0]))
        result = optimize_rotation(self.analysis.lineup_model, pool, cons,
                                   iterations=int(query.get("iterations", ["40"])[0]))
        model = self.analysis.lineup_model
        return {
            "net_rating": round(result["net_rating"], 3),
            "off_rating": round(result["off_rating"], 3),
            "def_rating": round(result["def_rating"], 3),
            "minutes": [{"player_id": p, "name": model.profiles[p].name,
                         "minutes": round(float(m), 1),
                         "impact": round(model.profiles[p].total_impact, 2)}
                        for p, m in result["minutes"].items()],
            "segments": _records(result["segments"]),
        }

    def splits(self, query) -> dict:
        from .splits import DIMENSIONS

        key = query.get("dimension", [None])[0]
        dim = DIMENSIONS.get(key)
        if dim is None:
            raise ApiError(f"unknown vertical {key!r}")
        team = query.get("team", [None])[0]
        player = query.get("player", [None])[0]
        per = query.get("per", ["per_36"])[0]
        engine = self.analysis.splits
        try:
            if dim.level == "possession":
                frame = engine.lineup_split(key)
            elif player:
                frame = engine.player_split(key, player_id=player, per_mode=per)
            else:
                frame = engine.team_split(key, team_id=team)
        except ValueError as exc:
            raise ApiError(str(exc), 409) from exc
        return {"dimension": key, "label": dim.label, "level": dim.level,
                "rows": _records(frame)}

    def game(self, body) -> dict:
        from .sim import simulate_from_ratings, win_probability

        home, away = body.get("home"), body.get("away")
        if not home or not away:
            raise ApiError("`home` and `away` are required")
        if home == away:
            raise ApiError("a team cannot play itself")
        ratings = self.analysis.team_ratings()
        hr, ar = ratings.get(home, 0.0), ratings.get(away, 0.0)
        sims = int(body.get("sims", 20000))
        result = simulate_from_ratings(hr, ar, n_sims=sims, seed=7)
        summary = {k: _clean(v) for k, v in result.summary().items()}
        margins = result.margins
        hist, edges = np.histogram(margins, bins=41, range=(-50, 50))
        return {
            "home": home, "away": away,
            "home_rating": round(hr, 2), "away_rating": round(ar, 2),
            "closed_form_win_prob": round(float(win_probability(hr, ar)), 4),
            "summary": summary,
            "quantiles": _records(result.quantiles()),
            "margin_histogram": {"counts": [int(c) for c in hist],
                                 "edges": [float(e) for e in edges]},
        }

    def season(self, body) -> dict:
        from .sim import simulate_season

        a = self.analysis
        ratings = a.team_ratings()
        conferences = dict(zip(a.league.teams["team_id"], a.league.teams["conference"]))
        games = a.league.games.assign(home_pts=np.nan, away_pts=np.nan)
        result = simulate_season(games, ratings, n_sims=int(body.get("sims", 1500)),
                                 conferences=conferences, seed=11)
        names = a.league.teams[["team_id", "team_abbrev", "team_name", "conference"]]
        wins = result.wins.merge(names, on="team_id", how="left")
        payload = {"wins": _records(wins)}
        if result.playoffs is not None:
            payload["playoffs"] = _records(
                result.playoffs.merge(names[["team_id", "team_abbrev", "team_name"]],
                                      on="team_id", how="left"))
        return payload

    def projections(self, _query) -> dict:
        df = self.analysis.projections
        return {"rows": _records(df.sort_values("impact", ascending=False), limit=600)}

    # -- helpers ------------------------------------------------------------

    @staticmethod
    def _evaluation_payload(ev) -> dict:
        return {
            "players": ev.players,
            "names": ev.names,
            "off_rating": round(ev.off_rating, 3),
            "def_rating": round(ev.def_rating, 3),
            "net_rating": round(ev.net_rating, 3),
            "additive_off": round(ev.additive_off, 3),
            "additive_def": round(ev.additive_def, 3),
            "usage_effect": round(ev.usage_effect, 3),
            "fit_bonus": round(ev.fit_bonus, 3),
            "coverage_penalty": round(ev.coverage_penalty, 3),
            "fit_detail": {k: round(v, 3) for k, v in (ev.fit_detail or {}).items()},
            "usage_table": _records(ev.usage_table) if ev.usage_table is not None else [],
            "explain": ev.explain(),
        }


GET_ROUTES = {
    "/api/state": "state",
    "/api/players": "players",
    "/api/teams": "teams",
    "/api/rapm": "rapm",
    "/api/best-lineups": "best_lineups",
    "/api/rotation": "rotation",
    "/api/splits": "splits",
    "/api/projections": "projections",
}
POST_ROUTES = {
    "/api/lineup/evaluate": "evaluate",
    "/api/lineup/swap": "swap",
    "/api/lineup/best-replacement": "best_replacement",
    "/api/game": "game",
    "/api/season": "season",
}


class Handler(BaseHTTPRequestHandler):
    server_version = f"hoopsim/{__version__}"
    api: Api = None            # set via partial

    def log_message(self, fmt, *args):  # pragma: no cover - quieter output
        return

    # -- plumbing -----------------------------------------------------------

    def _send_json(self, payload, status: int = 200) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path: Path) -> None:
        if not path.is_file():
            self._send_json({"error": "not found"}, 404)
            return
        data = path.read_bytes()
        ctype, _ = mimetypes.guess_type(str(path))
        self.send_response(200)
        self.send_header("Content-Type", ctype or "application/octet-stream")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _dispatch(self, routes, arg):
        parsed = urlparse(self.path)
        name = routes.get(parsed.path)
        if name is None:
            return False
        try:
            with self.api._lock:
                payload = getattr(self.api, name)(arg)
            self._send_json(payload)
        except ApiError as exc:
            self._send_json({"error": str(exc)}, exc.status)
        except Exception as exc:  # pragma: no cover - surface real errors
            traceback.print_exc()
            self._send_json({"error": f"{type(exc).__name__}: {exc}"}, 500)
        return True

    def do_GET(self):  # noqa: N802
        parsed = urlparse(self.path)
        if self._dispatch(GET_ROUTES, parse_qs(parsed.query)):
            return
        rel = parsed.path.lstrip("/") or "index.html"
        candidate = (WEB_ROOT / rel).resolve()
        if WEB_ROOT.resolve() not in candidate.parents and candidate != WEB_ROOT.resolve():
            self._send_json({"error": "forbidden"}, 403)
            return
        self._send_file(candidate)

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            body = json.loads(raw or b"{}")
        except json.JSONDecodeError:
            self._send_json({"error": "request body is not valid JSON"}, 400)
            return
        if not self._dispatch(POST_ROUTES, body):
            self._send_json({"error": "not found"}, 404)


def serve(*, host: str = "127.0.0.1", port: int = 8000, source: str = "synthetic",
          season: str = "2024-25", teams: int = 30, games: int = 30,
          seed: int = 20251001, directory: str | None = None,
          offline: bool = False, analysis: Analysis | None = None) -> None:
    """Load a league and serve the browser interface until interrupted."""
    if analysis is None:
        print(f"loading {source} data ...", flush=True)
        if source == "synthetic":
            analysis = Analysis.synthetic(n_teams=teams, games_per_team=games,
                                          season=season, seed=seed)
        elif source == "nba":
            analysis = Analysis.from_nba(season, offline=offline)
        elif source == "csv":
            if not directory:
                raise SystemExit("--directory is required with --source csv")
            analysis = Analysis.from_csv(directory, season)
        else:
            raise SystemExit(f"unknown source {source!r}")

    api = Api(analysis)
    print("warming the lineup model ...", flush=True)
    api.state({})            # forces stints, RAPM and profiles up front

    handler = partial(Handler)
    handler.api = api
    Handler.api = api
    httpd = ThreadingHTTPServer((host, port), Handler)
    print(f"\n  hoopsim {__version__} -- {analysis.league!r}")
    print(f"  open http://{host}:{port}/  (ctrl-c to stop)\n", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:  # pragma: no cover
        print("\nstopping")
    finally:
        httpd.server_close()
