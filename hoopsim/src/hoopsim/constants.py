"""League-level constants and tunable coefficients.

Everything here is a modelling assumption with a source or a rationale. They are
collected in one module so they can be audited, overridden per-league, or
re-fit from data rather than being scattered through the codebase as magic
numbers.
"""

from __future__ import annotations

# --------------------------------------------------------------------------
# Game structure
# --------------------------------------------------------------------------

MINUTES_PER_GAME = 48.0          # NBA regulation
MINUTES_PER_OT = 5.0
PLAYERS_ON_FLOOR = 5
TEAM_MINUTES_PER_GAME = MINUTES_PER_GAME * PLAYERS_ON_FLOOR   # 240

NCAA_MINUTES_PER_GAME = 40.0
FIBA_MINUTES_PER_GAME = 40.0

# --------------------------------------------------------------------------
# Possession estimation
# --------------------------------------------------------------------------

# Coefficient on FTA in the possession formula. It approximates the share of
# free throws that end a possession. 0.44 is the standard modern NBA value;
# it drifts with rule eras (and-1 frequency, away-from-play fouls), so it is
# exposed rather than hard-coded at the call site.
FT_POSSESSION_COEF = 0.44

# --------------------------------------------------------------------------
# Rate normalization bases
# --------------------------------------------------------------------------

# Minute-denominated bases: value = minutes in the basis.
PER_MINUTE_BASES = {
    "per_game": None,      # handled specially (divide by games)
    "per_24": 24.0,
    "per_36": 36.0,
    "per_40": 40.0,        # NCAA / FIBA regulation
    "per_48": 48.0,
}

# Possession-denominated bases: value = possessions in the basis.
PER_POSSESSION_BASES = {
    "per_75": 75.0,        # modern standard; approximates a heavy starter's load
    "per_100": 100.0,      # classic Oliver basis
}

DEFAULT_PER_MODE = "per_36"

# --------------------------------------------------------------------------
# Pythagorean expectation
# --------------------------------------------------------------------------

# Daryl Morey's fitted NBA exponent, for the fixed-exponent Pythagorean.
PYTHAGOREAN_EXPONENT = 13.91

# Pythagenpat derives a per-team exponent from the scoring environment instead
# of fixing one, which prices very high- and very low-scoring teams better.
#
# The familiar 0.287 is the *baseball* coefficient, where the exponent is
# ((RS + RA) / G) ** 0.287 and games score around nine runs. Applied to
# basketball's scale it returns an exponent near 4.8, which is nothing like
# the 13.91 the sport actually needs. So this is parameterised around the
# basketball exponent instead: at a league-average scoring environment the
# exponent equals PYTHAGOREAN_EXPONENT, and it flexes from there.
PYTHAGENPAT_REFERENCE_PPG = 230.0     # both teams combined, per game
PYTHAGENPAT_COEF = 0.287              # how hard the exponent responds to scoring

# --------------------------------------------------------------------------
# Home court advantage
# --------------------------------------------------------------------------

# Points of margin. League HCA has compressed substantially: ~3.5 in the 1990s,
# ~2.2-2.8 in recent seasons. Used as the default prior when a season's own
# HCA cannot be estimated from data.
DEFAULT_HOME_ADVANTAGE = 2.5

# Rest effects in points of margin, indexed by days of rest. Second night of a
# back-to-back (0 days rest) is the well-established penalty; beyond 3 days the
# effect is indistinguishable from zero and may reverse (rust).
REST_ADJUSTMENT = {
    0: -1.6,   # second night of a back-to-back
    1: -0.2,
    2: 0.0,
    3: 0.1,
}
REST_ADJUSTMENT_DEFAULT = 0.0

# --------------------------------------------------------------------------
# Margin -> win probability
# --------------------------------------------------------------------------

# Standard deviation of single-game point margin around its expectation. This
# is the scale parameter that turns a projected margin into a win probability,
# and it is the single most important number in the whole model.
#
# It has a hard floor. Margin variance is the sum of the two teams'
# *independent* score variance (shared factors like pace cancel in a
# difference), and per-possession scoring randomness alone puts each team's
# independent SD near 10 points over ~99 possessions. So margin SD cannot be
# much below 13 no matter how good the projection is. Values near 11 that
# circulate for "model residual SD" describe margin against a *closing spread*
# on a filtered slate, not raw margin. 13.0 is the defensible figure here.
GAME_MARGIN_SD = 13.0

# How strongly a game self-corrects: the fraction of the current margin, in
# points per 100 possessions, that is given back over the rest of the game as
# the leading team slows down and the benches empty. Calibrated so that
# possession-level simulation reproduces GAME_MARGIN_SD above, which independent
# possessions cannot -- see sim.game for the derivation.
GAME_MEAN_REVERSION = 1.25

# Standard deviation of a single team's score around its expectation, used by
# the analytic score model. Team scores are positively correlated within a game
# (shared pace), which the possession-level simulator handles explicitly.
TEAM_SCORE_SD = 10.5

# --------------------------------------------------------------------------
# Aging
# --------------------------------------------------------------------------

# Peak age by skill family. Athletic/finishing skills peak earlier and decay
# faster; shooting and passing hold much longer. These drive projection.aging.
AGING_PEAKS = {
    "scoring_volume": 27.0,
    "scoring_efficiency": 27.5,
    "three_point": 29.0,
    "free_throw": 29.0,
    "playmaking": 28.0,
    "rebounding": 26.5,
    "steals": 25.0,
    "blocks": 25.5,
    "turnovers": 28.0,
    "minutes": 27.0,
    "defense": 27.0,
}

# Curvature of the aging curve, per year-squared away from peak, expressed in
# fraction-of-peak units, with a separate value on each side of the peak.
#
# The growth side is the steeper one, which surprises people. A 22-year-old is
# a long way from what he will become; a 32-year-old is still close to what he
# was. The sharp fall comes later, and is handled by the cliff term below
# rather than by bending the whole curve.
AGING_GROWTH_CURVATURE = 0.0060
AGING_DECLINE_CURVATURE = 0.0032

# Aging bends volume far more than it bends efficiency. A 21-year-old shoots
# roughly as well from three as he ever will; what he lacks is the role. So
# each skill scales the curvature above, and rate statistics get a small
# fraction of the curve that counting statistics get. Without this, applying a
# volume-shaped curve to a percentage produces absurd projections.
AGING_CURVATURE_SCALE = {
    # Tuned so that at age 36 a player retains roughly: 95% of peak three
    # point accuracy, 93% of peak scoring efficiency, 88% of playmaking,
    # 85% of rebounding, 70% of steals and blocks, and 72% of scoring volume.
    "three_point": 0.32,
    "free_throw": 0.28,
    "scoring_efficiency": 0.30,
    "turnovers": 0.40,
    "playmaking": 0.60,
    "rebounding": 0.55,
    "blocks": 0.80,
    "steals": 0.80,
    "defense": 0.75,
    "scoring_volume": 1.00,
    "minutes": 1.00,
}
AGING_CURVATURE_SCALE_DEFAULT = 0.70

# Age past which decline accelerates further (cliff).
AGING_CLIFF_AGE = 33.0
AGING_CLIFF_EXTRA = 0.0020

# --------------------------------------------------------------------------
# Regression to the mean (empirical Bayes)
# --------------------------------------------------------------------------

# Stabilization points: the number of attempts/opportunities at which the
# observed rate deserves 50% weight against the prior. Derived from the
# split-half reliability literature; these are the widely cited NBA values.
# Read as: "3P% needs ~750 attempts before you trust it as much as the prior."
STABILIZATION_POINTS = {
    "fg3_pct": 750.0,      # 3-point percentage
    "ft_pct": 250.0,       # free throw percentage
    "fg2_pct": 400.0,      # 2-point percentage
    "ts_pct": 500.0,       # true shooting
    "efg_pct": 450.0,
    "usage_rate": 250.0,   # in minutes
    "ast_rate": 300.0,
    "tov_rate": 300.0,
    "orb_rate": 500.0,
    "drb_rate": 400.0,
    "stl_rate": 600.0,
    "blk_rate": 550.0,
}
STABILIZATION_DEFAULT = 500.0

# --------------------------------------------------------------------------
# Usage / efficiency tradeoff
# --------------------------------------------------------------------------

# Points of TS% lost per 1 percentage point of usage added, when a player is
# forced above their established usage. The literature puts the marginal cost
# somewhere in the 0.4-0.8 TS% points per usage point range; it is not linear
# and not symmetric (players gain less from shedding usage than they lose from
# absorbing it).
USAGE_EFFICIENCY_SLOPE = 0.0055        # TS% lost per usage point added
USAGE_EFFICIENCY_SLOPE_DOWN = 0.0030   # TS% gained per usage point shed
USAGE_CURVE_CONVEXITY = 0.00022        # extra quadratic penalty far from base

# Usage that must be absorbed by the remaining four players when one leaves.
# Empirically the redistribution is not uniform: higher-usage players absorb
# disproportionately more. This exponent shapes that.
USAGE_ABSORPTION_EXPONENT = 1.35

# --------------------------------------------------------------------------
# RAPM
# --------------------------------------------------------------------------

# Ridge penalty for RAPM. Chosen by cross-validation in practice; this is a
# sane default for a single season of NBA possessions.
RAPM_DEFAULT_ALPHA = 2000.0

# Minimum possessions before a player gets an unregularized-ish estimate.
RAPM_MIN_POSSESSIONS = 100

# --------------------------------------------------------------------------
# Lineup fit
# --------------------------------------------------------------------------

# Weights on the five fit dimensions in the lineup model, in points per 100
# possessions per unit of the (standardized) fit score. These are structural
# assumptions, deliberately modest relative to the additive player term.
LINEUP_FIT_WEIGHTS = {
    "spacing": 1.35,        # floor spacing from shooting threat
    "rim_pressure": 0.85,   # rim attacks that bend the defense
    "playmaking": 0.95,     # shot creation for others
    "rebounding": 0.70,
    "rim_protection": 1.05,
}

# Diminishing returns: a lineup of five identical high-usage creators is worth
# less than the sum of its parts. Penalty scales with the concentration of
# usage and of playmaking.
LINEUP_REDUNDANCY_PENALTY = 2.2

# --------------------------------------------------------------------------
# Scoring environment defaults (used to seed synthetic data and as fallbacks)
# --------------------------------------------------------------------------

LEAGUE_DEFAULTS = {
    "pace": 99.0,                # possessions per 48
    "off_rating": 114.5,         # points per 100 possessions
    "efg_pct": 0.542,
    "tov_rate": 0.128,
    "orb_rate": 0.265,
    "ft_rate": 0.238,            # FTA / FGA
    "fg3a_rate": 0.395,          # 3PA / FGA
    "fg3_pct": 0.365,
    "fg2_pct": 0.545,
    "ft_pct": 0.785,
    "ast_rate": 0.610,           # share of made FG that are assisted
}

# --------------------------------------------------------------------------
# Rosters and positions
# --------------------------------------------------------------------------

POSITIONS = ["PG", "SG", "SF", "PF", "C"]

# Which positions a player at a given nominal position can credibly cover.
POSITION_COVERAGE = {
    "PG": ["PG", "SG"],
    "SG": ["PG", "SG", "SF"],
    "SF": ["SG", "SF", "PF"],
    "PF": ["SF", "PF", "C"],
    "C": ["PF", "C"],
}

# --------------------------------------------------------------------------
# Garbage time
# --------------------------------------------------------------------------

# A possession is garbage time when the absolute margin exceeds
# GARBAGE_TIME_MARGIN + GARBAGE_TIME_SLOPE * seconds_remaining_in_game.
GARBAGE_TIME_MARGIN = 20.0
GARBAGE_TIME_SLOPE = 0.025
GARBAGE_TIME_MAX_SECONDS = 360.0   # only applies inside the last 6 minutes

# --------------------------------------------------------------------------
# Clutch definition (league standard)
# --------------------------------------------------------------------------

CLUTCH_SECONDS_REMAINING = 300.0   # last 5 minutes
CLUTCH_MARGIN = 5.0                # score within 5 points
