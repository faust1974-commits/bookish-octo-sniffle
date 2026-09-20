# hoopsim

A basketball analytics engine: advanced metrics on any rate basis, lineup
evaluation with honest usage redistribution, impact ratings from play-by-play,
player projection, and game and season simulation.

Built for two jobs: **team and roster decisions** (who should be on the floor
together, who should play how many minutes, who is actually good) and **game
and season forecasting** (win probabilities, projected scores, win totals,
playoff and title odds).

Built on **real NBA data**: the complete 2025-26 regular season &mdash; 1,230
games, 500 players, 30 teams, from play-by-play.

## Three ways to run it, easiest first

**1. Double-click a file.** `dist/hoopsim.html` is the whole thing in one
file &mdash; real players, real teams, styles, calculations. Put it on your
desktop and open it. No install, no terminal, no internet connection.

**2. Double-click the launcher** (Mac). `Open hoopsim.command` sets itself up
the first time, then starts the full Python version and opens your browser.
It keeps everything it installs in a private folder beside the script.

**3. The command line**, if you want the whole engine.

```bash
pip install -e .
hoopsim demo          # a full tour on generated data, no network needed
hoopsim serve         # the browser interface
```

### How the single file stays honest

The browser cannot run Python, so `web/engine.js` re-implements the lineup
model in JavaScript. That is a real hazard: a silent divergence would make the
file confidently wrong.

Two things prevent it. Every tunable number is exported from `constants.py`
into the file rather than retyped in JavaScript, so there is one source of
truth &mdash; and a test asserts that no tunable is hardcoded on the JavaScript
side. Then `tests/test_standalone.py` runs the JavaScript under node and
compares it against the Python engine lineup by lineup: ratings to 1e-4, usage
redistribution to 1e-6. If the two ever drift, the test fails.

Rebuild it against any data with:

```bash
python build_standalone.py                     # real NBA, current season
python build_standalone.py --season 2024-25    # any published season
python build_standalone.py --source synthetic  # generated data
```

---

## What it actually does

### Advanced metrics, on any denominator

Every metric in the standard toolkit, computed from first principles with the
team-context terms the formulas actually require:

| Family | What's in it |
|---|---|
| Shooting | TS%, eFG%, FG%, 2P%, 3P%, FT%, 3PAr, FTr, points per shot |
| Involvement | USG%, AST%, TOV%, AST/TO, ORB%, DRB%, TRB%, STL%, BLK%, PF rate |
| Composite | PER (pace- and league-normalised to 15), Game Score, Win Shares (OWS/DWS/WS/48) |
| Individual ratings | Oliver's offensive rating, points produced, individual possessions, Stop%, defensive rating |
| Impact | On/off, five-man unit ratings with standard errors, RAPM (offence and defence split), a re-fittable box-score impact model |
| Team | Pace, ORtg/DRtg/NetRtg, four factors on both ends, SRS, SOS, schedule-adjusted ratings, Pythagorean and Pythagenpat, luck |

Eight rate bases: `totals`, `per_game`, `per_24`, `per_36`, `per_40`, `per_48`,
`per_75`, `per_100` — plus pace adjustment, opponent adjustment, era z-scores
and percentile ranks as separate, composable operations.

```bash
hoopsim players --per per_100 --min-minutes 500 --sort box_impact
hoopsim players --per per_75            # pace-independent, per-game scale
```

### Lineup swapping that accounts for usage

This is the part most tools get wrong. When you take a player off the floor,
the other four do **not** keep their per-36 rates. The possessions he was
ending have to go somewhere, and whoever absorbs them shoots worse on the
marginal possession than on their existing ones.

Remove a 32%-usage scorer and the model reports what actually happens:

```
usage ABSORBED by each remaining player:
   A      0.220 -> 0.273  (+0.053)   TS -0.0353
   B      0.180 -> 0.220  (+0.040)   TS -0.0258
   C      0.160 -> 0.194  (+0.034)   TS -0.0216
   D      0.120 -> 0.143  (+0.023)   TS -0.0141

efficiency cost to the remaining four: -4.31 points per 100 possessions
```

A naive per-36 extrapolation reports zero. That error is why this module
exists.

A lineup's rating is built, and reported, in parts:

```
  Projected net rating         +15.61 per 100
  additive offence              +7.15     each player's own value
  additive defence              +5.59
  usage redistribution          +1.87     cost or gain of fitting five usages into one possession
  fit bonus                     +1.00     spacing, rim pressure, playmaking, rebounding, rim protection
  coverage penalty              -0.00     charged when nobody on the floor provides a needed skill
```

Five identical players grade about **11 points per 100 below** five
complementary ones with identical individual impact. Position viability is
solved as a bipartite matching, not by counting nominal positions, so genuinely
versatile lineups are judged correctly.

```bash
hoopsim lineup P0001 P0002 P0003 P0004 P0005
hoopsim swap P0001 P0002 P0003 P0004 P0005 --out P0001 --in P0009
hoopsim best-lineups --team BOS        # searches every legal five
hoopsim rotation --team BOS            # optimises minutes under constraints
```

### Impact from play-by-play

Play-by-play is parsed into lineups and stints by walking the event log and
tracking substitutions, with possessions counted exactly rather than estimated.
From there:

- **RAPM** — ridge-regularised adjusted plus-minus, offence and defence
  estimated separately, with optional informative priors (feed it box-score
  impact and you get the shape used by the well-known proprietary metrics).
  The ridge penalty is chosen by cross-validation, not assumed.
- **On/off and five-man unit ratings**, each reported alongside its own
  standard error, because a unit with 40 possessions carries an error bar of
  roughly 18 points per 100 and almost every extreme lineup rating in a season
  is noise.
- **A re-fittable box-score impact model.** The built-in coefficients are a
  prior; `Analysis.refit_box_impact()` fits them against RAPM for the league
  you actually loaded. On test data that lifts correlation with true impact
  from 0.35 to 0.60.

### Projection

Three steps, and skipping any of them is where naive systems go wrong:

1. **Blend history**, weighting recent seasons more.
2. **Regress toward a prior** using each rate's own stabilization point —
   free throws settle after ~250 attempts, three-pointers need ~750, which is
   more than most players take in a season. A 42% three-point season on 120
   attempts projects to .373, not .420.
3. **Age it forward, per skill.** Shooting and athleticism decline on
   completely different schedules. At 36 a player retains ~94% of peak
   three-point accuracy but only ~68% of his steal rate.

Every projection carries an uncertainty estimate. Availability is projected
too, from age and history, against the schedule length inferred from the data.

### Simulation

Two models that agree with each other:

- **Closed-form.** Projected margin plus a standard deviation is a complete
  probabilistic forecast. Fast enough for a whole season of what-ifs.
- **Possession-level Monte Carlo.** Full outcome distributions — scores,
  margins, totals — for anything that depends on a tail or a threshold.

They agree to within **0.009 in probability and 0.24 points of margin** across
the full range of matchups. That took work, and the reason is instructive:
points per possession has a standard deviation near 1.2, so 99 independent
possessions per side implies a margin SD around 18. Real NBA margins vary by
about 13.5. The difference is that basketball games are **self-correcting** —
leading teams slow down, trailing teams push, benches empty once a game is
decided. Modelling that feedback both reconciles the two models and
independently reproduces the ~0.4 correlation between the two teams' scores
that real data shows.

Season simulation gives win totals with intervals, seeding, play-in, playoff
and title odds. Calibration tooling (Brier, log loss, skill score, reliability
curves, walk-forward backtesting) is included, because a model nobody checked
is a model nobody should use.

```bash
hoopsim game --home BOS --away LAL --sims 20000
hoopsim season --sims 5000
```

### Splits — every vertical

Any metric, cut by any dimension, without new code per cut:

*Game level* — home/away, days of rest, back-to-backs, month, opponent quality
quartile, win/loss, game margin bucket.
*Possession level* — quarter, half, garbage time, clutch (last five minutes,
score within five).

Plus with/without for any player, pair on/off for any two, and cross-splits
(rest × home/away as a grid). Adding a vertical is one registration call.

```bash
hoopsim splits list
hoopsim splits rest --team BOS
hoopsim splits clutch
```

---

## Data

The adapter interface means the models never know where numbers came from.

**`SyntheticSource`** generates a complete, self-consistent league —
play-by-play first, box scores derived from it — with known ground truth.
That is what makes the impact models testable: you can check whether RAPM
recovers the impact that actually generated the games. It does, at r ≈ 0.60,
and it independently recovers the home-court advantage it was never told.

**`NBAGithubSource`** is the default and the source of `dist/hoopsim.html`.
It reads complete season dumps published at
[shufinskiy/nba_data](https://github.com/shufinskiy/nba_data) — one compressed
file per season instead of 1,230 rate-limited requests. A season loads in about
a minute and is then cached forever, because a finished season never changes.

Four quirks of that play-by-play format are handled explicitly. Each is silent
when missed, and each produced confidently wrong numbers before it was found:

* Team-level events (team rebounds, team turnovers, timeouts) put the **team id
  in the player column**. Left alone, thirty team entities enter the player
  table with 22,000 rebounds between them, and every per-game aggregate grows a
  third "team" — which dragged apparent scoring from 115.6 points per team down
  to 109.9.
* Teams change personnel at **quarter breaks with no substitution events**. The
  on-floor five has to be re-derived for each period; without that, one quarter
  break poisons the rest of the game and only 67% of stints hold five players.
* The clock **occasionally runs backwards**, making stint durations nonsense.
  It is held at its high-water mark within each game.
* A substitute who **records no statistic** never appears with an id anywhere in
  that game, so the incoming player cannot be resolved from in-game names alone
  and falls back to the season roster.

`tests/test_nba_real.py` pins all four.

Measured against the real league: 99.3 possessions per team per game (NBA ~99),
115.6 points (~115), .546 eFG (.542), .260 offensive rebound rate (.265), 55.4%
home wins (~55%), and box scores matching the final score in 98.8% of
team-games.

**`NBAStatsSource`** pulls live from `stats.nba.com` for anyone who wants the
official endpoint. It is written and documented but **could not be exercised
here** — this environment's network policy blocks that host.

**`rosters.py`** answers a different question from all of these, and keeping
the two apart is the point. A season dump says what a player did and who he
did it for; it cannot say he was traded in July. Build a lineup tool from the
dump alone and it shows last season's teams — Giannis in Milwaukee, Herro in
Miami — months after both moved, which is exactly the bug this module exists
to fix.

So roster membership comes from its own feed on its own clock: ESPN's daily
team-roster scrape, mirrored per season by
[hoopR-nba-data](https://github.com/sportsdataverse/hoopR-nba-data). It is one
small file, refreshed daily, and it also supplies the age and listed position
the play-by-play dumps leave blank.

The two feeds share no player id, so they join on a normalised name — accents,
punctuation, generational suffixes and hyphens stripped. That is the weak link
and it is handled explicitly: a key matching two players is refused rather than
guessed, and every unmatched player is counted rather than dropped in silence.

Three outcomes, all labelled in the interface:

* **Played last season** — his own numbers, his current team.
* **Missed last season entirely** — an achilles or an ACL costs a full year,
  and Haliburton, Lillard and VanVleet are all on rosters with no 2025-26 row
  at all. They fall back to the prior season, tagged with the year it came from
  rather than passed off as current.
* **No NBA record yet** — the 74 rookies. They are shown at replacement level,
  badged "no NBA record", because a placeholder you can see is better than a
  number that looks like a projection.

```python
from hoopsim.data import rosters

rosters.current_season()          # '2026-27' from 1 July onward
frame = rosters.fetch()           # today's rosters, cached six hours
```

**`CSVSource`** reads a directory of canonical CSVs — the escape hatch for
Kaggle dumps, paid-feed exports or your own scrapes.

```python
from hoopsim.context import Analysis

a = Analysis.from_nba_github("2025-26")   # real NBA, the default
a = Analysis.from_csv("./data", "2025-26")
a = Analysis.synthetic(n_teams=30, games_per_team=82)
```

---

## Honest limitations

- **Ratings are last season's; rosters are today's.** There is no way around
  this in September: the 2026-27 season opens on 20 October 2026 and nobody has
  played a possession yet. A player traded in July carries his old team's
  numbers to his new team, which is the right call for a veteran and a poor one
  for a rookie or a player whose role is about to change completely. Once games
  are played the same feed carries them, and a rebuild picks them up.

- **The synthetic league is not real basketball.** Its four factors, pace,
  offensive rating and home-court advantage all match NBA values closely, but
  team strength spread runs wide (5.9 vs ~4.5) and the margin distribution has
  fatter tails than reality. Anything depending on the *shape* of the scoring
  environment is faithful; anything depending on the *tails* will read
  pessimistic. Calibrate on real data.
- **`box_impact` is not Basketball-Reference's BPM**, and is not called BPM.
  It is a transparent linear model with exposed, re-fittable coefficients.
  Reproducing a published metric's coefficients from memory and labelling it
  with that metric's name would imply a match it does not have.
- **Seeding tiebreakers are simplified.** The NBA's real procedure starts with
  head-to-head, then division and conference records. This uses projected
  strength and then a deterministic constant. It matters only for teams on a
  tiebreak bubble, and the place to fix it is marked.
- **No tracking data.** Gravity, contest rates, defensive matchup assignments
  and shot quality relative to defender distance all need tracking feeds that
  are not public. The skill scores here are box-score shadows of those things.
- **Injury modelling is deliberately simple** — age and availability history
  only. Real injury modelling needs injury type and severity, which no public
  box-score feed carries.
- **Rest effects are priors, not fitted.** The generator does not model rest,
  so the values in `constants.REST_ADJUSTMENT` come from the literature and
  should be re-fit on real data.

Everything tunable lives in `constants.py`, in one auditable place, with the
reasoning written next to each number.

---

## Layout

```
src/hoopsim/
  constants.py     every modelling assumption, documented and in one place
  context.py       Analysis: ties the layers together, caches the expensive ones
  data/            schema, source adapters, play-by-play parsing, stints
  metrics/         box metrics, team efficiency, rate normalization, registry
  impact/          on/off, RAPM, usage curves, lineup model and swap engine
  projection/      aging, regression to the mean, player projection, rotations
  sim/             win probability, game and season Monte Carlo, calibration
  splits/          the verticals engine
  cli.py  api.py   command line and HTTP server (standard library only)
build_standalone.py  packs everything into one double-clickable HTML file
web/               browser interface and the JavaScript engine, no build step
dist/hoopsim.html  the double-clickable build, real NBA data
tests/             220 tests
```

## Development

```bash
pip install -e . && pip install pytest
pytest -q
```

The tests check identities rather than snapshots: PER averages exactly 15,
defensive ratings average to the league offensive rating, usage shares sum to
one possession per team, per-36 is exactly 1.5× per-24, minutes total 240,
title probabilities sum to 1, the Monte Carlo agrees with the closed form, and
RAPM recovers known ground truth, and the JavaScript engine agrees with
the Python one. If a formula is wrong, those fail.
