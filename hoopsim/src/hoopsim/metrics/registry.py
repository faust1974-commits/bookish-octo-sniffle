"""A catalogue of every metric the system computes.

Used by the CLI (`hoopsim metrics`), the web UI's column picker, and anywhere
a number needs a label, a description or a sensible display format. Keeping it
in one place means a metric cannot be added without being documented.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Metric:
    key: str
    label: str
    description: str
    kind: str            # "count" | "rate" | "pct" | "rating" | "composite"
    scope: str           # "player" | "team" | "both"
    higher_is_better: bool = True
    fmt: str = "{:.1f}"
    family: str = "misc"


def _m(key, label, desc, kind, scope, family, *, hib=True, fmt="{:.1f}"):
    return Metric(key, label, desc, kind, scope, hib, fmt, family)


METRICS: dict[str, Metric] = {m.key: m for m in [
    # -- volume ------------------------------------------------------------
    _m("pts", "Points", "Points scored.", "count", "both", "volume"),
    _m("ast", "Assists", "Passes leading directly to a made field goal.", "count", "both", "volume"),
    _m("trb", "Rebounds", "Offensive plus defensive rebounds.", "count", "both", "volume"),
    _m("stl", "Steals", "Possessions taken from the offence.", "count", "both", "volume"),
    _m("blk", "Blocks", "Shots blocked.", "count", "both", "volume"),
    _m("tov", "Turnovers", "Possessions given away.", "count", "both", "volume", hib=False),
    _m("min", "Minutes", "Minutes played.", "count", "both", "volume"),

    # -- shooting ----------------------------------------------------------
    _m("ts_pct", "TS%", "True shooting: points per shooting possession, counting "
       "threes and free throws correctly. The single best shooting summary.",
       "pct", "both", "shooting", fmt="{:.3f}"),
    _m("efg_pct", "eFG%", "Effective field goal %: field goal % with a three "
       "counted as 1.5 makes. Excludes free throws.", "pct", "both", "shooting", fmt="{:.3f}"),
    _m("fg_pct", "FG%", "Field goals made over attempted.", "pct", "both", "shooting", fmt="{:.3f}"),
    _m("fg3_pct", "3P%", "Three pointers made over attempted. Needs ~750 "
       "attempts before it is more signal than noise.", "pct", "both", "shooting", fmt="{:.3f}"),
    _m("ft_pct", "FT%", "Free throws made over attempted.", "pct", "both", "shooting", fmt="{:.3f}"),
    _m("fg3a_rate", "3PAr", "Share of field goal attempts taken from three.",
       "rate", "both", "shooting", fmt="{:.3f}"),
    _m("ft_rate", "FTr", "Free throw attempts per field goal attempt. Measures "
       "how often a player gets to the line.", "rate", "both", "shooting", fmt="{:.3f}"),
    _m("pts_per_shot", "PPS", "Points per field goal attempt.", "rate", "both",
       "shooting", fmt="{:.2f}"),

    # -- involvement -------------------------------------------------------
    _m("usage_rate", "USG%", "Share of team possessions a player ends while on "
       "the floor, by shooting, getting fouled, or turning it over.",
       "rate", "player", "involvement", fmt="{:.3f}"),
    _m("ast_rate", "AST%", "Share of teammates' made field goals a player "
       "assisted while on the floor.", "rate", "player", "involvement", fmt="{:.3f}"),
    _m("tov_rate", "TOV%", "Turnovers per possession used.", "rate", "both",
       "involvement", hib=False, fmt="{:.3f}"),
    _m("ast_to_tov", "AST/TO", "Assists per turnover.", "rate", "player",
       "involvement", fmt="{:.2f}"),
    _m("orb_rate", "ORB%", "Share of available offensive rebounds grabbed.",
       "rate", "both", "involvement", fmt="{:.3f}"),
    _m("drb_rate", "DRB%", "Share of available defensive rebounds grabbed.",
       "rate", "both", "involvement", fmt="{:.3f}"),
    _m("trb_rate", "TRB%", "Share of all available rebounds grabbed.", "rate",
       "both", "involvement", fmt="{:.3f}"),
    _m("stl_rate", "STL%", "Opponent possessions ended by this player's steal.",
       "rate", "player", "involvement", fmt="{:.3f}"),
    _m("blk_rate", "BLK%", "Opponent two-point attempts blocked.", "rate",
       "player", "involvement", fmt="{:.3f}"),

    # -- composite ---------------------------------------------------------
    _m("per", "PER", "Player Efficiency Rating: Hollinger's per-minute box "
       "summary, pace-adjusted so the league average is 15. Rewards volume "
       "scoring and barely sees defence.", "composite", "player", "composite"),
    _m("game_score_per_game", "GmSc", "Hollinger's Game Score per game: a "
       "single-game value summary on a points-like scale.", "composite",
       "player", "composite"),
    _m("ws", "WS", "Win Shares: wins credited to a player, offence plus "
       "defence.", "composite", "player", "composite", fmt="{:.1f}"),
    _m("ws_per_48", "WS/48", "Win shares per 48 minutes. League average is "
       "about .100.", "composite", "player", "composite", fmt="{:.3f}"),
    _m("ows", "OWS", "Offensive win shares.", "composite", "player", "composite"),
    _m("dws", "DWS", "Defensive win shares.", "composite", "player", "composite"),
    _m("box_impact", "BoxImpact", "Points per 100 possessions above an average "
       "player, estimated from the box score alone. A transparent, re-fittable "
       "model -- not Basketball-Reference's BPM.", "rating", "player",
       "impact", fmt="{:+.1f}"),
    _m("box_impact_vorp", "VORP-style", "Box impact over replacement level, "
       "scaled by playing time. A volume measure of value.", "composite",
       "player", "impact", fmt="{:.1f}"),

    # -- individual ratings ------------------------------------------------
    _m("off_rating", "ORtg", "Points produced per 100 individual possessions.",
       "rating", "both", "efficiency"),
    _m("def_rating", "DRtg", "Points allowed per 100 possessions.", "rating",
       "both", "efficiency", hib=False),
    _m("net_rating", "NetRtg", "Offensive rating minus defensive rating.",
       "rating", "team", "efficiency", fmt="{:+.1f}"),
    _m("stop_pct", "Stop%", "Share of defensive possessions a player ended with "
       "a stop.", "rate", "player", "efficiency", fmt="{:.3f}"),

    # -- impact (play-by-play) --------------------------------------------
    _m("on_off_net", "On/Off", "Team net rating with the player on the floor "
       "minus with him off it. Heavily confounded by who he plays with.",
       "rating", "player", "impact", fmt="{:+.1f}"),
    _m("on_net", "OnNet", "Team net rating while the player is on the floor.",
       "rating", "player", "impact", fmt="{:+.1f}"),
    _m("rapm", "RAPM", "Regularized adjusted plus-minus: impact per 100 "
       "possessions after solving out every teammate and opponent. The best "
       "box-free impact estimate, and it needs multiple seasons to settle.",
       "rating", "player", "impact", fmt="{:+.1f}"),
    _m("rapm_off", "O-RAPM", "Offensive half of RAPM.", "rating", "player",
       "impact", fmt="{:+.1f}"),
    _m("rapm_def", "D-RAPM", "Defensive half of RAPM. Positive is good.",
       "rating", "player", "impact", fmt="{:+.1f}"),

    # -- team --------------------------------------------------------------
    _m("pace", "Pace", "Possessions per 48 minutes.", "rating", "team", "team"),
    _m("adj_off_rating", "AdjORtg", "Offensive rating adjusted for the quality "
       "of defences faced.", "rating", "team", "team"),
    _m("adj_def_rating", "AdjDRtg", "Defensive rating adjusted for the quality "
       "of offences faced.", "rating", "team", "team", hib=False),
    _m("adj_net_rating", "AdjNet", "Schedule-adjusted net rating. The best "
       "single measure of team strength.", "rating", "team", "team", fmt="{:+.1f}"),
    _m("srs", "SRS", "Simple Rating System: margin of victory plus strength of "
       "schedule, in points.", "rating", "team", "team", fmt="{:+.1f}"),
    _m("sos", "SOS", "Strength of schedule, in points of opponent quality.",
       "rating", "team", "team", fmt="{:+.1f}"),
    _m("pythag_win_pct", "Pythag", "Win percentage implied by points scored and "
       "allowed.", "pct", "team", "team", fmt="{:.3f}"),
    _m("luck", "Luck", "Actual wins minus Pythagorean wins. Regresses hard.",
       "composite", "team", "team", fmt="{:+.1f}"),
]}


def get(key: str) -> Metric | None:
    return METRICS.get(key)


def by_family(family: str) -> list[Metric]:
    return [m for m in METRICS.values() if m.family == family]


def families() -> list[str]:
    seen: list[str] = []
    for m in METRICS.values():
        if m.family not in seen:
            seen.append(m.family)
    return seen


def for_scope(scope: str) -> list[Metric]:
    return [m for m in METRICS.values() if m.scope in (scope, "both")]


def format_value(key: str, value) -> str:
    metric = METRICS.get(key)
    if metric is None or value is None:
        return "" if value is None else str(value)
    try:
        return metric.fmt.format(float(value))
    except (TypeError, ValueError):
        return str(value)
