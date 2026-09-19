"""Box-score derived player metrics.

Every function here takes the frame produced by `metrics.aggregate.player_season`
-- a player's totals with his team's and opponents' totals attached -- and adds
columns. They are safe to call in any order and none of them mutate the input.

On provenance, because it matters for trust:

* Shooting and rate metrics (TS%, eFG%, USG%, AST%, TOV%, rebound and defensive
  rates) are Dean Oliver's standard definitions, unchanged.
* Game Score is Hollinger's published formula.
* PER follows Hollinger's unadjusted PER (uPER) and then applies the pace and
  league normalisation that puts the league average at 15.
* Individual offensive and defensive rating follow *Basketball on Paper*.
* Win Shares follow the published marginal-offense / marginal-defense method.
* `box_impact` is NOT Basketball-Reference's BPM. It is a transparent linear
  model in the same spirit, whose coefficients are exposed and can be re-fit
  against RAPM or against known ground truth -- see `impact.fit_box_impact`.
  Calling it BPM would imply a match it does not have.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .. import constants as K


def _safe_div(num, den, fill=np.nan):
    num = np.asarray(num, dtype=float)
    den = np.asarray(den, dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        out = np.where(den != 0, num / den, fill)
    return out


# ---------------------------------------------------------------------------
# Shooting
# ---------------------------------------------------------------------------

def add_shooting(df: pd.DataFrame) -> pd.DataFrame:
    """Effective field goal %, true shooting %, and the shot-mix rates."""
    out = df.copy()
    out["efg_pct"] = _safe_div(out["fgm"] + 0.5 * out["fg3m"], out["fga"])
    out["ts_attempts"] = out["fga"] + K.FT_POSSESSION_COEF * out["fta"]
    out["ts_pct"] = _safe_div(out["pts"], 2.0 * out["ts_attempts"])
    out["fg_pct"] = _safe_div(out["fgm"], out["fga"])
    out["fg2_pct"] = _safe_div(out["fg2m"], out["fg2a"])
    out["fg3_pct"] = _safe_div(out["fg3m"], out["fg3a"])
    out["ft_pct"] = _safe_div(out["ftm"], out["fta"])
    out["fg3a_rate"] = _safe_div(out["fg3a"], out["fga"])      # 3PAr
    out["ft_rate"] = _safe_div(out["fta"], out["fga"])          # FTr
    out["pts_per_shot"] = _safe_div(out["pts"], out["fga"])
    return out


# ---------------------------------------------------------------------------
# Usage and involvement rates (Oliver)
# ---------------------------------------------------------------------------

def add_rates(df: pd.DataFrame) -> pd.DataFrame:
    """Usage, assist, turnover, rebound, steal and block rates.

    Each is the player's share of the available opportunities *while he was on
    the floor*, which is why every formula carries the (team minutes / 5)
    over (player minutes) term.
    """
    out = df.copy()
    mp = out["min"].astype(float)
    tm_mp5 = out["tm_min"].astype(float) / K.PLAYERS_ON_FLOOR
    share = _safe_div(tm_mp5, mp)          # scales a player rate to team level

    player_plays = out["fga"] + K.FT_POSSESSION_COEF * out["fta"] + out["tov"]
    team_plays = out["tm_fga"] + K.FT_POSSESSION_COEF * out["tm_fta"] + out["tm_tov"]
    out["usage_rate"] = _safe_div(player_plays * tm_mp5, mp * team_plays)

    # Share of teammates' made field goals a player assisted while on the floor.
    teammate_fgm = _safe_div(mp, tm_mp5) * out["tm_fgm"] - out["fgm"]
    out["ast_rate"] = _safe_div(out["ast"], teammate_fgm)

    out["tov_rate"] = _safe_div(out["tov"], player_plays)
    out["ast_to_tov"] = _safe_div(out["ast"], out["tov"])

    out["orb_rate"] = _safe_div(out["orb"] * tm_mp5, mp * (out["tm_orb"] + out["opp_drb"]))
    out["drb_rate"] = _safe_div(out["drb"] * tm_mp5, mp * (out["tm_drb"] + out["opp_orb"]))
    out["trb_rate"] = _safe_div(out["trb"] * tm_mp5, mp * (out["tm_trb"] + out["opp_trb"]))

    out["stl_rate"] = _safe_div(out["stl"] * tm_mp5, mp * out["opp_poss"])
    out["blk_rate"] = _safe_div(out["blk"] * tm_mp5, mp * (out["opp_fga"] - out["opp_fg3a"]))
    out["pf_rate"] = _safe_div(out["pf"] * tm_mp5, mp * out["opp_poss"])
    return out


# ---------------------------------------------------------------------------
# Game Score (Hollinger)
# ---------------------------------------------------------------------------

def game_score(df: pd.DataFrame) -> np.ndarray:
    """Hollinger's Game Score: a single-game value summary on a PER-like scale."""
    return (
        df["pts"]
        + 0.4 * df["fgm"]
        - 0.7 * df["fga"]
        - 0.4 * (df["fta"] - df["ftm"])
        + 0.7 * df["orb"]
        + 0.3 * df["drb"]
        + df["stl"]
        + 0.7 * df["ast"]
        + 0.7 * df["blk"]
        - 0.4 * df["pf"]
        - df["tov"]
    ).to_numpy()


# ---------------------------------------------------------------------------
# PER (Hollinger)
# ---------------------------------------------------------------------------

def add_per(df: pd.DataFrame, league: dict) -> pd.DataFrame:
    """Unadjusted PER, then pace- and league-normalised so the mean is 15."""
    out = df.copy()
    lg = league

    lg_fg, lg_ft, lg_fga, lg_fta = lg["fgm"], lg["ftm"], lg["fga"], lg["fta"]
    lg_ast, lg_pf, lg_pts = lg["ast"], lg["pf"], lg["pts"]
    lg_orb, lg_trb, lg_tov = lg["orb"], lg["trb"], lg["tov"]

    factor = (2.0 / 3.0) - (0.5 * (lg_ast / lg_fg)) / (2.0 * (lg_fg / lg_ft))
    vop = lg_pts / (lg_fga - lg_orb + lg_tov + K.FT_POSSESSION_COEF * lg_fta)
    drb_pct = (lg_trb - lg_orb) / lg_trb

    mp = out["min"].astype(float)
    tm_ast_fg = _safe_div(out["tm_ast"], out["tm_fgm"])

    uper = _safe_div(
        out["fg3m"]
        + (2.0 / 3.0) * out["ast"]
        + (2.0 - factor * tm_ast_fg) * out["fgm"]
        + out["ftm"] * 0.5 * (1.0 + (1.0 - tm_ast_fg) + (2.0 / 3.0) * tm_ast_fg)
        - vop * out["tov"]
        - vop * drb_pct * (out["fga"] - out["fgm"])
        - vop * K.FT_POSSESSION_COEF * (0.44 + (0.56 * drb_pct)) * (out["fta"] - out["ftm"])
        + vop * (1.0 - drb_pct) * out["drb"]
        + vop * drb_pct * out["orb"]
        + vop * out["stl"]
        + vop * drb_pct * out["blk"]
        - out["pf"] * ((lg_ft / lg_pf) - K.FT_POSSESSION_COEF * (lg_fta / lg_pf) * vop),
        mp,
    )
    out["uper"] = uper
    pace_adj = _safe_div(lg["pace"], out["tm_pace"], fill=1.0)
    aper = uper * pace_adj
    # League average aPER, minutes-weighted, is the divisor that sets 15.
    mask = np.isfinite(aper) & (mp.to_numpy() > 0)
    lg_aper = float(np.average(aper[mask], weights=mp.to_numpy()[mask])) if mask.any() else np.nan
    out["per"] = aper * (15.0 / lg_aper) if lg_aper and np.isfinite(lg_aper) else np.nan
    return out


# ---------------------------------------------------------------------------
# Individual offensive and defensive rating (Oliver, Basketball on Paper)
# ---------------------------------------------------------------------------

def add_individual_ratings(df: pd.DataFrame) -> pd.DataFrame:
    """Points produced per 100 individual possessions, and defensive rating.

    This is the most intricate calculation in the box-score family. It splits a
    player's scoring possessions into the part he created himself, the part he
    created for others, the free throw part and the offensive rebound part,
    then charges him for the possessions he ended without a score.
    """
    out = df.copy()
    mp = out["min"].astype(float)
    tm_mp5 = out["tm_min"].astype(float) / K.PLAYERS_ON_FLOOR
    minute_share = _safe_div(mp, tm_mp5, fill=0.0)

    fg, fga, fg3, ft, fta = out["fgm"], out["fga"], out["fg3m"], out["ftm"], out["fta"]
    ast, orb, tov, pts, pf = out["ast"], out["orb"], out["tov"], out["pts"], out["pf"]
    tm_fg, tm_fga, tm_fg3 = out["tm_fgm"], out["tm_fga"], out["tm_fg3m"]
    tm_ft, tm_fta, tm_ast = out["tm_ftm"], out["tm_fta"], out["tm_ast"]
    tm_pts, tm_orb, tm_tov = out["tm_pts"], out["tm_orb"], out["tm_tov"]
    tm_drb, tm_blk, tm_stl, tm_pf = out["tm_drb"], out["tm_blk"], out["tm_stl"], out["tm_pf"]

    # Share of a player's made baskets that were assisted, estimated from how
    # much of the team's assisting happened around him.
    other_ast = _safe_div(out["tm_ast"], out["tm_min"]) * mp * 5.0 - ast
    other_fg = _safe_div(out["tm_fgm"], out["tm_min"]) * mp * 5.0 - fg
    q_ast = (minute_share * (1.14 * _safe_div(tm_ast - ast, tm_fg))
             + _safe_div(other_ast, other_fg) * (1.0 - minute_share))
    q_ast = np.clip(np.nan_to_num(q_ast, nan=0.0), 0.0, 1.0)

    fg_part = fg * (1.0 - 0.5 * _safe_div(pts - ft, 2.0 * fga, fill=0.0) * q_ast)
    ast_part = 0.5 * _safe_div((tm_pts - tm_ft) - (pts - ft),
                               2.0 * (tm_fga - fga), fill=0.0) * ast
    ft_pct = _safe_div(ft, fta, fill=0.0)
    ft_part = np.where(fta > 0, (1.0 - (1.0 - ft_pct) ** 2) * 0.4 * fta, 0.0)

    tm_ft_pct = _safe_div(tm_ft, tm_fta, fill=0.0)
    tm_scoring_poss = tm_fg + (1.0 - (1.0 - tm_ft_pct) ** 2) * tm_fta * 0.4
    tm_orb_pct = _safe_div(tm_orb, tm_orb + out["opp_drb"], fill=0.0)
    tm_play_pct = _safe_div(tm_scoring_poss, tm_fga + tm_fta * 0.4 + tm_tov, fill=0.0)
    denom = ((1.0 - tm_orb_pct) * tm_play_pct + tm_orb_pct * (1.0 - tm_play_pct))
    tm_orb_weight = _safe_div((1.0 - tm_orb_pct) * tm_play_pct, denom, fill=0.0)

    orb_part = orb * tm_orb_weight * tm_play_pct
    shrink = 1.0 - _safe_div(tm_orb, tm_scoring_poss, fill=0.0) * tm_orb_weight * tm_play_pct
    sc_poss = (fg_part + ast_part + ft_part) * shrink + orb_part

    fgx_poss = (fga - fg) * (1.0 - 1.07 * tm_orb_pct)
    ftx_poss = np.where(fta > 0, ((1.0 - ft_pct) ** 2) * 0.4 * fta, 0.0)
    tot_poss = sc_poss + fgx_poss + ftx_poss + tov

    pprod_fg = 2.0 * (fg + 0.5 * fg3) * (1.0 - 0.5 * _safe_div(pts - ft, 2.0 * fga, fill=0.0) * q_ast)
    pprod_ast = (2.0 * _safe_div(tm_fg - fg + 0.5 * (tm_fg3 - fg3), tm_fg - fg, fill=0.0)
                 * 0.5 * _safe_div((tm_pts - tm_ft) - (pts - ft), 2.0 * (tm_fga - fga), fill=0.0)
                 * ast)
    pprod_orb = orb * tm_orb_weight * tm_play_pct * _safe_div(tm_pts, tm_scoring_poss, fill=0.0)
    pprod = (pprod_fg + pprod_ast + ft) * shrink + pprod_orb

    out["scoring_poss"] = sc_poss
    out["individual_poss"] = tot_poss
    out["points_produced"] = pprod
    out["off_rating"] = 100.0 * _safe_div(pprod, tot_poss)

    # --- defence ---
    opp_fg, opp_fga, opp_ft, opp_fta = out["opp_fgm"], out["opp_fga"], out["opp_ftm"], out["opp_fta"]
    opp_orb, opp_tov, opp_pts = out["opp_orb"], out["opp_tov"], out["opp_pts"]
    dor_pct = _safe_div(opp_orb, opp_orb + tm_drb, fill=0.0)
    dfg_pct = _safe_div(opp_fg, opp_fga, fill=0.0)
    fmwt = _safe_div(dfg_pct * (1.0 - dor_pct),
                     dfg_pct * (1.0 - dor_pct) + (1.0 - dfg_pct) * dor_pct, fill=0.0)

    stops1 = out["stl"] + out["blk"] * fmwt * (1.0 - 1.07 * dor_pct) + out["drb"] * (1.0 - fmwt)
    opp_ft_pct = _safe_div(opp_ft, opp_fta, fill=0.0)
    stops2 = (
        (_safe_div(opp_fga - opp_fg - tm_blk, out["tm_min"], fill=0.0) * fmwt
         * (1.0 - 1.07 * dor_pct)
         + _safe_div(opp_tov - tm_stl, out["tm_min"], fill=0.0)) * mp
        + _safe_div(pf, tm_pf, fill=0.0) * 0.4 * opp_fta * (1.0 - opp_ft_pct) ** 2
    )
    stops = stops1 + stops2
    # Stop% is expressed on a team-equivalent scale -- "if all five defenders
    # were this player, this is the share of possessions the team would stop"
    # -- so league average sits near .50, not near .10. That scaling is what
    # makes the defensive rating formula below land on the team's own rating
    # for an average defender.
    stop_pct = _safe_div(stops * out["tm_min"], out["tm_poss"] * mp)

    tm_drtg = 100.0 * _safe_div(opp_pts, out["opp_poss"])
    d_pts_per_scposs = _safe_div(
        opp_pts, opp_fg + (1.0 - (1.0 - opp_ft_pct) ** 2) * opp_fta * 0.4, fill=0.0
    )
    out["stop_pct"] = stop_pct
    out["def_rating"] = tm_drtg + 0.2 * (100.0 * d_pts_per_scposs * (1.0 - stop_pct) - tm_drtg)
    out["net_rating_individual"] = out["off_rating"] - out["def_rating"]
    return out


# ---------------------------------------------------------------------------
# Win Shares
# ---------------------------------------------------------------------------

def add_win_shares(df: pd.DataFrame, league: dict) -> pd.DataFrame:
    """Offensive, defensive and total win shares, plus WS per 48 minutes.

    The method charges each player against a replacement-quality baseline
    (0.92 of league points per possession on offence, 1.08 on defence) and
    divides the surplus by the points it takes to buy one win.
    """
    out = df.copy()
    if "points_produced" not in out.columns:
        out = add_individual_ratings(out)

    lg_pts_per_poss = league["pts_per_poss"]
    lg_pts_per_game = league["pts"] / league["games"] / 2.0

    marginal_offense = out["points_produced"] - 0.92 * lg_pts_per_poss * out["individual_poss"]
    pace_ratio = _safe_div(out["tm_pace"], league["pace"], fill=1.0)
    marginal_pts_per_win = 0.32 * lg_pts_per_game * pace_ratio

    out["ows"] = _safe_div(marginal_offense, marginal_pts_per_win)

    minute_share = _safe_div(out["min"], out["tm_min"], fill=0.0)
    marginal_defense = (minute_share * out["tm_poss"]
                        * (1.08 * lg_pts_per_poss - out["def_rating"] / 100.0))
    out["dws"] = _safe_div(marginal_defense, marginal_pts_per_win)
    out["ws"] = out["ows"] + out["dws"]
    out["ws_per_48"] = _safe_div(out["ws"] * K.MINUTES_PER_GAME, out["min"])
    return out


# ---------------------------------------------------------------------------
# Transparent box-score impact model
# ---------------------------------------------------------------------------

#: Default coefficients for `box_impact`, in points per 100 possessions per
#: unit of each per-100 input. They are a reasonable starting prior, not a
#: fitted result -- call `impact.fit_box_impact` to replace them with
#: coefficients fitted against RAPM (real data) or ground truth (synthetic).
DEFAULT_BOX_IMPACT_COEFS = {
    "intercept": -5.90,
    "pts_100": 0.118,
    "fga_100": -0.098,
    "fta_100": -0.038,
    "fg3m_100": 0.148,
    "ast_100": 0.182,
    "orb_100": 0.181,
    "drb_100": 0.089,
    "stl_100": 0.760,
    "blk_100": 0.345,
    "tov_100": -0.700,
    "pf_100": -0.108,
    "ts_pct": 8.60,
}

_IMPACT_COUNTS = ["pts", "fga", "fta", "fg3m", "ast", "orb", "drb", "stl", "blk", "tov", "pf"]


def impact_features(df: pd.DataFrame) -> pd.DataFrame:
    """Per-100-possession features used by the box impact model."""
    out = pd.DataFrame(index=df.index)
    poss = df["min"].astype(float) * _safe_div(
        df["tm_poss"] * K.PLAYERS_ON_FLOOR, df["tm_min"], fill=np.nan
    )
    out["_poss"] = poss
    for c in _IMPACT_COUNTS:
        out[f"{c}_100"] = 100.0 * _safe_div(df[c], poss)
    out["ts_pct"] = df["ts_pct"] if "ts_pct" in df.columns else _safe_div(
        df["pts"], 2.0 * (df["fga"] + K.FT_POSSESSION_COEF * df["fta"])
    )
    return out


def add_box_impact(df: pd.DataFrame, coefs: dict | None = None,
                   *, column: str = "box_impact") -> pd.DataFrame:
    """Apply the linear box-score impact model.

    Adds `box_impact` (points per 100 possessions vs a league-average player)
    and `box_impact_wins` (a VORP-style volume number: impact over a
    replacement level of -2.0, scaled by minutes played).
    """
    coefs = dict(DEFAULT_BOX_IMPACT_COEFS if coefs is None else coefs)
    out = df.copy()
    feats = impact_features(out)
    value = np.full(len(out), float(coefs.get("intercept", 0.0)))
    for name, beta in coefs.items():
        if name == "intercept":
            continue
        if name not in feats.columns:
            raise KeyError(f"box impact coefficient {name!r} has no matching feature")
        value = value + beta * np.nan_to_num(feats[name].to_numpy(), nan=0.0)
    out[column] = value

    replacement = -2.0
    minute_share = _safe_div(out["min"], out["tm_min"] / K.PLAYERS_ON_FLOOR, fill=0.0)
    team_games = out["tm_games"].replace(0, np.nan)
    out[f"{column}_vorp"] = (value - replacement) * minute_share * team_games / 82.0
    return out


# ---------------------------------------------------------------------------
# One-call convenience
# ---------------------------------------------------------------------------

def add_all(df: pd.DataFrame, league: dict,
            box_impact_coefs: dict | None = None) -> pd.DataFrame:
    """Add every box-score metric in this module, in dependency order."""
    out = add_shooting(df)
    out = add_rates(out)
    out = add_individual_ratings(out)
    out = add_per(out, league)
    out = add_win_shares(out, league)
    out = add_box_impact(out, box_impact_coefs)
    out["game_score_total"] = game_score(out)
    out["game_score_per_game"] = _safe_div(out["game_score_total"], out["games"])
    return out
