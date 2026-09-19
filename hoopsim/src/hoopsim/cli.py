"""Command line interface.

    hoopsim demo                     a full tour on synthetic data
    hoopsim players --per per_36     the player metric table
    hoopsim teams                    team efficiency and four factors
    hoopsim rapm                     impact ratings from play-by-play
    hoopsim lineup P1 P2 P3 P4 P5    evaluate a five-man unit
    hoopsim swap --out X --in Y      what one substitution does
    hoopsim best-lineups --team T    search a rotation for the best fives
    hoopsim rotation --team T        optimise minutes
    hoopsim splits rest              any vertical
    hoopsim project                  next-season player projections
    hoopsim game --home A --away B   simulate a matchup
    hoopsim season                   season, playoff and title odds
    hoopsim metrics                  the metric catalogue
    hoopsim serve                    the browser interface

Every command takes `--source synthetic|nba|csv`. The NBA source needs network
access to stats.nba.com; synthetic always works and is the default.
"""

from __future__ import annotations

import argparse
import sys

import numpy as np
import pandas as pd

from . import __version__, constants as K
from .context import Analysis


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

def _print(frame: pd.DataFrame, *, floatfmt: str = "{:.3f}", max_rows: int = 40) -> None:
    if frame is None or len(frame) == 0:
        print("  (no rows)")
        return
    with pd.option_context("display.width", 200, "display.max_columns", 60,
                           "display.float_format", floatfmt.format):
        print(frame.head(max_rows).to_string(index=False))
    if len(frame) > max_rows:
        print(f"  ... {len(frame) - max_rows} more rows")


def _header(text: str) -> None:
    print(f"\n{text}")
    print("-" * len(text))


def _load(args) -> Analysis:
    if args.source == "synthetic":
        return Analysis.synthetic(n_teams=args.teams, games_per_team=args.games,
                                  season=args.season, seed=args.seed)
    if args.source == "nba":
        return Analysis.from_nba(args.season, with_pbp=not args.no_pbp,
                                 offline=args.offline)
    if args.source == "csv":
        if not args.directory:
            raise SystemExit("--directory is required with --source csv")
        return Analysis.from_csv(args.directory, args.season)
    raise SystemExit(f"unknown source {args.source!r}")


def _resolve_players(analysis: Analysis, tokens: list[str]) -> list[str]:
    """Accept player ids or names (case-insensitive, partial match)."""
    index = analysis.league.player_index
    by_name = {str(n).lower(): pid for pid, n in index["player_name"].items()}
    out = []
    for token in tokens:
        if token in index.index:
            out.append(token)
            continue
        low = token.lower()
        if low in by_name:
            out.append(by_name[low])
            continue
        matches = [pid for name, pid in by_name.items() if low in name]
        if len(matches) == 1:
            out.append(matches[0])
        elif not matches:
            raise SystemExit(f"no player matching {token!r}")
        else:
            names = ", ".join(sorted(analysis.league.player_name(m) for m in matches)[:8])
            raise SystemExit(f"{token!r} matches several players: {names}")
    return out


def _resolve_team(analysis: Analysis, token: str) -> str:
    teams = analysis.league.teams
    for col in ("team_id", "team_abbrev", "team_name"):
        if col in teams.columns:
            hit = teams[teams[col].astype(str).str.lower() == token.lower()]
            if len(hit) == 1:
                return str(hit["team_id"].iloc[0])
    hit = teams[teams["team_name"].astype(str).str.lower().str.contains(token.lower())]
    if len(hit) == 1:
        return str(hit["team_id"].iloc[0])
    raise SystemExit(f"no team matching {token!r}")


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_players(args) -> None:
    from .metrics.normalize import normalize

    a = _load(args)
    df = a.players
    if args.refit and a.league.has_pbp:
        a.refit_box_impact()
        df = a.players
    df = df[df["min"] >= args.min_minutes]
    if args.team:
        df = df[df["team_id"] == _resolve_team(a, args.team)]
    df = normalize(df, args.per)

    cols = ["player_name", "position", "games", "min", "pts", "trb", "ast",
            "ts_pct", "usage_rate", "per", "ws", "ws_per_48", "box_impact"]
    cols = [c for c in cols if c in df.columns]
    _header(f"Player metrics ({args.per}, minimum {args.min_minutes:g} minutes)")
    _print(df.nlargest(args.top, args.sort if args.sort in df.columns else "box_impact")[cols],
           max_rows=args.top)


def cmd_teams(args) -> None:
    a = _load(args)
    df = a.teams
    cols = ["team_abbrev", "conference", "w", "l", "pace", "off_rating", "def_rating",
            "net_rating", "adj_off_rating", "adj_def_rating", "adj_net_rating",
            "srs", "sos", "pythag_win_pct", "luck"]
    cols = [c for c in cols if c in df.columns]
    _header("Team efficiency")
    _print(df[cols], floatfmt="{:.2f}", max_rows=40)

    _header("Four factors")
    ff = ["team_abbrev", "off_efg_pct", "off_tov_rate", "off_orb_rate", "off_ft_rate",
          "def_efg_pct", "def_tov_rate", "def_drb_rate", "def_ft_rate"]
    _print(df[[c for c in ff if c in df.columns]], max_rows=40)


def cmd_rapm(args) -> None:
    a = _load(args)
    if a.rapm is None:
        raise SystemExit("RAPM needs play-by-play data; this source has none")
    _header(f"RAPM (alpha={a.rapm.alpha:g}, {a.rapm.n_rows:,} stint-sides)")
    print(f"  recovered home court advantage: {a.rapm.home_advantage:+.2f} per 100")
    df = a.rapm.ratings.merge(
        a.league.players.drop_duplicates("player_id")[["player_id", "player_name", "position"]],
        on="player_id", how="left")
    df = df[df["possessions"] >= args.min_possessions]
    cols = ["player_name", "position", "possessions", "rapm_off", "rapm_def", "rapm"]
    _print(df.nlargest(args.top, "rapm")[cols], floatfmt="{:.2f}", max_rows=args.top)


def cmd_lineup(args) -> None:
    a = _load(args)
    players = _resolve_players(a, args.players)
    ev = a.lineup_model.evaluate(players)
    _header("Lineup evaluation")
    print(ev.explain())
    if ev.usage_table is not None:
        _header("Usage redistribution")
        _print(ev.usage_table, floatfmt="{:.4f}")


def cmd_swap(args) -> None:
    a = _load(args)
    lineup = _resolve_players(a, args.players)
    out_p = _resolve_players(a, [args.out_player])[0]
    in_p = _resolve_players(a, [args.in_player])[0]
    result = a.lineup_model.swap(lineup, out_p, in_p)
    _header("Substitution")
    print(result.explain())
    _header("Before")
    print(result.before.explain())
    _header("After")
    print(result.after.explain())


def cmd_best_lineups(args) -> None:
    a = _load(args)
    team = _resolve_team(a, args.team)
    pool = a.roster_profiles(team, top=args.pool)
    _header(f"Best five-man units for {a.league.team_name(team)} "
            f"(from a {len(pool)}-man rotation)")
    best = a.lineup_model.best_lineups(pool, top=args.top)
    for r in best.itertuples(index=False):
        print(f"  {r.net_rating:+6.2f} net   off {r.off_rating:6.1f}  def {r.def_rating:6.1f}"
              f"  usage {r.usage_effect:+5.2f}  fit {r.fit_bonus:+5.2f}")
        print(f"          {', '.join(r.names)}")


def cmd_rotation(args) -> None:
    from .projection import RotationConstraints, optimize_rotation

    a = _load(args)
    team = _resolve_team(a, args.team)
    pool = a.roster_profiles(team, top=args.pool)
    cons = RotationConstraints(max_minutes_per_player=args.max_minutes,
                               max_players=args.max_players)
    result = optimize_rotation(a.lineup_model, pool, cons, iterations=args.iterations)
    _header(f"Optimised rotation for {a.league.team_name(team)}")
    print(f"  projected net rating {result['net_rating']:+.2f} per 100 "
          f"(offence {result['off_rating']:.1f}, defence {result['def_rating']:.1f})")
    print(f"  total minutes {result['minutes'].sum():.1f}\n")
    for pid, mins in result["minutes"].items():
        profile = a.lineup_model.profiles[pid]
        print(f"    {profile.name:<24s} {mins:5.1f} min   impact {profile.total_impact:+5.2f}")
    _header("Unit plan")
    seg = result["segments"]
    for r in seg.itertuples(index=False):
        print(f"  {r.start_minute:5.1f}'  net {r.net_rating:+6.2f}  {', '.join(r.names)}")


def cmd_splits(args) -> None:
    from .splits import DIMENSIONS, available

    a = _load(args)
    if args.dimension == "list":
        _header("Available verticals")
        for d in available():
            print(f"  {d.key:<16s} [{d.level:<10s}] {d.label}")
            print(f"  {'':<16s} {d.description}")
        return
    dim = DIMENSIONS.get(args.dimension)
    if dim is None:
        raise SystemExit(f"unknown vertical {args.dimension!r}; try `hoopsim splits list`")

    team = _resolve_team(a, args.team) if args.team else None
    _header(f"{dim.label}" + (f" -- {a.league.team_name(team)}" if team else " -- league wide"))
    if dim.level == "possession":
        _print(a.splits.lineup_split(args.dimension), floatfmt="{:.1f}")
    elif args.player:
        pid = _resolve_players(a, [args.player])[0]
        print(f"  {a.league.player_name(pid)}, {args.per}")
        _print(a.splits.player_split(args.dimension, player_id=pid, per_mode=args.per))
    else:
        _print(a.splits.team_split(args.dimension, team_id=team), floatfmt="{:.3f}")


def cmd_project(args) -> None:
    a = _load(args)
    df = a.projections
    cols = ["player_name", "position", "age", "impact", "impact_sd", "usage_rate",
            "ts_pct", "fg3_pct", "minutes_per_game", "projected_games", "projected_minutes"]
    _header("Next-season projections")
    _print(df.nlargest(args.top, "impact")[[c for c in cols if c in df.columns]],
           floatfmt="{:.2f}", max_rows=args.top)


def cmd_game(args) -> None:
    from .sim import simulate_from_ratings, win_probability

    a = _load(args)
    home = _resolve_team(a, args.home)
    away = _resolve_team(a, args.away)
    ratings = a.team_ratings()
    hr, ar = ratings.get(home, 0.0), ratings.get(away, 0.0)

    _header(f"{a.league.team_name(away)} at {a.league.team_name(home)}")
    print(f"  net ratings: {a.league.team_name(home)} {hr:+.2f}, "
          f"{a.league.team_name(away)} {ar:+.2f}")
    print(f"  closed-form home win probability: {float(win_probability(hr, ar)):.4f}")

    result = simulate_from_ratings(hr, ar, n_sims=args.sims,
                                   home_team=home, away_team=away, seed=args.seed)
    summary = result.summary()
    print(f"\n  {args.sims:,} possession-level simulations")
    print(f"    home win probability   {summary['home_win_prob']:.4f}")
    print(f"    projected score        {summary['mean_home_score']:.1f} - "
          f"{summary['mean_away_score']:.1f}")
    print(f"    margin                 {summary['mean_margin']:+.2f} "
          f"(sd {summary['margin_sd']:.2f})")
    print(f"    implied spread         {summary['spread']:+.1f}")
    print(f"    projected total        {summary['median_total']:.1f}")
    _header("Outcome distribution")
    _print(result.quantiles(), floatfmt="{:.1f}")


def cmd_season(args) -> None:
    from .sim import simulate_season

    a = _load(args)
    ratings = a.team_ratings()
    conferences = dict(zip(a.league.teams["team_id"], a.league.teams["conference"]))
    games = a.league.games.assign(home_pts=np.nan, away_pts=np.nan) if args.from_scratch \
        else a.league.games
    result = simulate_season(games, ratings, n_sims=args.sims,
                             conferences=conferences, seed=args.seed)

    names = a.league.teams[["team_id", "team_abbrev", "conference"]]
    _header(f"Projected wins ({args.sims:,} simulated seasons)")
    wins = result.wins.merge(names, on="team_id", how="left")
    _print(wins[["team_abbrev", "conference", "net_rating", "mean_wins", "sd_wins",
                 "p05_wins", "p95_wins"]], floatfmt="{:.1f}", max_rows=40)
    if result.playoffs is not None:
        _header("Playoff and title odds")
        po = result.playoffs.merge(names[["team_id", "team_abbrev"]], on="team_id", how="left")
        _print(po[["team_abbrev", "conference", "playin_prob", "playoff_prob",
                   "conf_finals_prob", "finals_prob", "title_prob"]], max_rows=40)


def cmd_metrics(args) -> None:
    from .metrics import registry
    from .metrics.normalize import ALL_MODES, describe_mode

    _header("Rate bases")
    for mode in ALL_MODES:
        print(f"  {mode:<10s} {describe_mode(mode)}")
    for family in registry.families():
        _header(f"Metrics: {family}")
        for m in registry.by_family(family):
            print(f"  {m.key:<22s} {m.label:<12s} [{m.scope}] {m.description}")


def cmd_demo(args) -> None:
    from .sim import simulate_season, win_probability

    a = _load(args)
    print(f"\nhoopsim {__version__} -- {a.league!r}")

    _header("Team efficiency (top 8 by schedule-adjusted net rating)")
    _print(a.teams[["team_abbrev", "w", "l", "pace", "off_rating", "def_rating",
                    "adj_net_rating", "srs", "luck"]].head(8), floatfmt="{:.2f}")

    _header("Players (top 10 by box impact, per 100 possessions)")
    from .metrics.normalize import normalize

    p = normalize(a.players[a.players["min"] >= 250], "per_100")
    _print(p.nlargest(10, "box_impact")[["player_name", "position", "min", "pts",
                                         "ast", "trb", "ts_pct", "per", "box_impact"]],
           floatfmt="{:.2f}")

    if a.league.has_pbp:
        _header("RAPM (top 10)")
        r = a.rapm.ratings.merge(
            a.league.players.drop_duplicates("player_id")[["player_id", "player_name"]],
            on="player_id", how="left")
        _print(r[r["possessions"] >= 400].nlargest(10, "rapm")[
            ["player_name", "possessions", "rapm_off", "rapm_def", "rapm"]], floatfmt="{:.2f}")
        print(f"\n  home court advantage recovered from the data: "
              f"{a.rapm.home_advantage:+.2f} points per 100")

    team = a.teams["team_id"].iloc[0]
    pool = a.roster_profiles(team, top=9)
    if len(pool) >= 6:
        _header(f"Best lineups -- {a.league.team_name(team)}")
        for r in a.lineup_model.best_lineups(pool, top=3).itertuples(index=False):
            print(f"  {r.net_rating:+6.2f}  {', '.join(r.names)}")

        _header("One substitution, fully explained")
        starters = pool[:5]
        swap = a.lineup_model.swap(starters, starters[0], pool[5])
        print(swap.explain())

    _header("Splits: league-wide, by days of rest")
    _print(a.splits.team_split("rest")[["bucket", "games", "off_rating", "ts_pct",
                                        "win_pct", "margin"]])

    _header("Season simulation")
    ratings = a.team_ratings()
    conferences = dict(zip(a.league.teams["team_id"], a.league.teams["conference"]))
    result = simulate_season(a.league.games.assign(home_pts=np.nan, away_pts=np.nan),
                             ratings, n_sims=1000, conferences=conferences, seed=1)
    names = a.league.teams[["team_id", "team_abbrev"]]
    _print(result.playoffs.merge(names, on="team_id").head(6)[
        ["team_abbrev", "playoff_prob", "conf_finals_prob", "title_prob"]])
    print("\nTry `hoopsim serve` for the interactive lineup interface.")


def cmd_serve(args) -> None:
    from .api import serve

    serve(host=args.host, port=args.port, source=args.source, season=args.season,
          teams=args.teams, games=args.games, seed=args.seed,
          directory=args.directory, offline=args.offline)


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hoopsim",
        description="Basketball advanced metrics, lineup swapping, projection and simulation.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--version", action="version", version=f"hoopsim {__version__}")

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--source", default="synthetic",
                        choices=["synthetic", "nba", "csv"],
                        help="where the data comes from (default: synthetic)")
    common.add_argument("--season", default="2024-25", help="season label, e.g. 2023-24")
    common.add_argument("--teams", type=int, default=30, help="synthetic league size")
    common.add_argument("--games", type=int, default=30, help="synthetic games per team")
    common.add_argument("--seed", type=int, default=K.__dict__.get("SEED", 20251001))
    common.add_argument("--directory", help="data directory, with --source csv")
    common.add_argument("--no-pbp", action="store_true",
                        help="skip play-by-play (much faster, disables lineup analysis)")
    common.add_argument("--offline", action="store_true",
                        help="use only cached data, never the network")

    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("demo", parents=[common], help="a full tour of the system")
    p.set_defaults(func=cmd_demo)

    p = sub.add_parser("players", parents=[common], help="player metric table")
    p.add_argument("--per", default="per_36", help="rate basis (see `hoopsim metrics`)")
    p.add_argument("--min-minutes", type=float, default=250.0)
    p.add_argument("--sort", default="box_impact")
    p.add_argument("--top", type=int, default=25)
    p.add_argument("--team")
    p.add_argument("--refit", action="store_true",
                   help="refit the box impact model against RAPM first")
    p.set_defaults(func=cmd_players)

    p = sub.add_parser("teams", parents=[common], help="team efficiency and four factors")
    p.set_defaults(func=cmd_teams)

    p = sub.add_parser("rapm", parents=[common], help="impact ratings from play-by-play")
    p.add_argument("--top", type=int, default=25)
    p.add_argument("--min-possessions", type=float, default=500.0)
    p.set_defaults(func=cmd_rapm)

    p = sub.add_parser("lineup", parents=[common], help="evaluate a five-man unit")
    p.add_argument("players", nargs=5, help="five player ids or names")
    p.set_defaults(func=cmd_lineup)

    p = sub.add_parser("swap", parents=[common], help="what one substitution does")
    p.add_argument("players", nargs=5, help="the five currently on the floor")
    p.add_argument("--out", dest="out_player", required=True, help="player coming off")
    p.add_argument("--in", dest="in_player", required=True, help="player coming on")
    p.set_defaults(func=cmd_swap)

    p = sub.add_parser("best-lineups", parents=[common], help="search for the best fives")
    p.add_argument("--team", required=True)
    p.add_argument("--pool", type=int, default=10, help="rotation size to search")
    p.add_argument("--top", type=int, default=10)
    p.set_defaults(func=cmd_best_lineups)

    p = sub.add_parser("rotation", parents=[common], help="optimise minutes")
    p.add_argument("--team", required=True)
    p.add_argument("--pool", type=int, default=10)
    p.add_argument("--max-minutes", type=float, default=36.0)
    p.add_argument("--max-players", type=int, default=9)
    p.add_argument("--iterations", type=int, default=60)
    p.set_defaults(func=cmd_rotation)

    p = sub.add_parser("splits", parents=[common], help="any vertical")
    p.add_argument("dimension", help="a vertical, or `list` to see them all")
    p.add_argument("--team")
    p.add_argument("--player")
    p.add_argument("--per", default="per_36")
    p.set_defaults(func=cmd_splits)

    p = sub.add_parser("project", parents=[common], help="next-season projections")
    p.add_argument("--top", type=int, default=25)
    p.set_defaults(func=cmd_project)

    p = sub.add_parser("game", parents=[common], help="simulate one matchup")
    p.add_argument("--home", required=True)
    p.add_argument("--away", required=True)
    p.add_argument("--sims", type=int, default=20000)
    p.set_defaults(func=cmd_game)

    p = sub.add_parser("season", parents=[common], help="season, playoff and title odds")
    p.add_argument("--sims", type=int, default=2000)
    p.add_argument("--from-scratch", action="store_true",
                   help="ignore played games and simulate the whole season")
    p.set_defaults(func=cmd_season)

    p = sub.add_parser("metrics", parents=[common], help="the metric catalogue")
    p.set_defaults(func=cmd_metrics)

    p = sub.add_parser("serve", parents=[common], help="the browser interface")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    p.set_defaults(func=cmd_serve)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.func(args)
    except KeyboardInterrupt:  # pragma: no cover
        print("\ninterrupted", file=sys.stderr)
        return 130
    except (SystemExit, BrokenPipeError):
        raise
    except Exception as exc:  # pragma: no cover - top-level guard
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
