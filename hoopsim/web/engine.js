/* hoopsim calculation engine, in the browser.
 *
 * This is a faithful port of the Python lineup model so the standalone file
 * gives the same answers as `hoopsim` on the command line. Two rules keep it
 * honest:
 *
 *   1. Every tunable number is read from the exported payload's `constants`
 *      block, never retyped here. Python remains the single source of truth.
 *   2. tests/test_standalone.py runs this file under node and compares its
 *      output to the Python engine's, lineup by lineup. A drift fails the build.
 *
 * No DOM access in this file -- it is pure arithmetic, so it can be tested
 * headlessly.
 */
'use strict';

(function (root) {

  /* --------------------------------------------------------- statistics */

  function mean(xs) {
    if (!xs.length) return 0;
    let s = 0;
    for (const x of xs) s += x;
    return s / xs.length;
  }

  /** Population standard deviation, matching numpy's default (ddof=0). */
  function stdev(xs) {
    if (!xs.length) return 0;
    const m = mean(xs);
    let s = 0;
    for (const x of xs) s += (x - m) * (x - m);
    return Math.sqrt(s / xs.length);
  }

  function clamp(x, lo, hi) { return Math.min(hi, Math.max(lo, x)); }

  /** Standard normal CDF. Abramowitz & Stegun 7.1.26, accurate to ~1.5e-7. */
  function normalCdf(z) {
    const sign = z < 0 ? -1 : 1;
    const x = Math.abs(z) / Math.SQRT2;
    const t = 1 / (1 + 0.3275911 * x);
    const y = 1 - (((((1.061405429 * t - 1.453152027) * t) + 1.421413741) * t
      - 0.284496736) * t + 0.254829592) * t * Math.exp(-x * x);
    return 0.5 * (1 + sign * y);
  }

  /* ------------------------------------------------------ usage tradeoff */

  /**
   * Change in true shooting percentage from moving off established usage.
   * Positive when usage falls. Asymmetric: absorbing costs more than
   * shedding gains.
   */
  function tsDelta(K, baseUsage, newUsage) {
    const dp = (newUsage - baseUsage) * 100.0;
    if (dp >= 0) {
      return -(K.usage_efficiency_slope * dp + K.usage_curve_convexity * dp * dp);
    }
    return -K.usage_efficiency_slope_down * dp;
  }

  /**
   * Rebalance five players' usage so it totals one possession.
   * Mirrors impact.usage.redistribute_usage, iteration for iteration.
   */
  function redistributeUsage(K, profiles, targetTotal) {
    const target = targetTotal === undefined ? 1.0 : targetTotal;
    const floor = K.usage_floor, ceiling = K.usage_ceiling;
    const exponent = K.usage_absorption_exponent;

    const base = profiles.map(p => p.usage);
    const total = base.reduce((a, b) => a + b, 0);
    const gap = target - total;

    const weights = base.map(u => Math.pow(Math.max(u, 1e-6), exponent));
    const wsum = weights.reduce((a, b) => a + b, 0);
    let adjusted = base.map((u, i) => u + gap * (weights[i] / wsum));

    for (let iter = 0; iter < 8; iter++) {
      const clipped = adjusted.map(u => clamp(u, floor, ceiling));
      const residual = target - clipped.reduce((a, b) => a + b, 0);
      if (Math.abs(residual) < 1e-9) { adjusted = clipped; break; }
      const free = clipped.map(u => u > floor + 1e-12 && u < ceiling - 1e-12);
      if (!free.some(Boolean)) { adjusted = clipped; break; }
      const w = weights.map((x, i) => (free[i] ? x : 0));
      const sum = w.reduce((a, b) => a + b, 0);
      adjusted = clipped.map((u, i) => u + residual * (w[i] / sum));
    }
    adjusted = adjusted.map(u => clamp(u, floor, ceiling));

    return profiles.map((p, i) => {
      const delta = tsDelta(K, p.usage, adjusted[i]);
      return {
        player_id: p.player_id,
        name: p.name,
        base_usage: p.usage,
        adjusted_usage: adjusted[i],
        usage_change: adjusted[i] - p.usage,
        base_ts_pct: p.ts_pct,
        adjusted_ts_pct: p.ts_pct + delta,
        ts_change: delta,
        pts_per_100_effect: adjusted[i] * delta * 2.0 * 100.0,
      };
    });
  }

  /* ---------------------------------------------------------- lineups */

  const SKILLS = ['spacing', 'rim_pressure', 'playmaking', 'rebounding', 'rim_protection'];

  function coveragePenalty(K, squad) {
    let penalty = 0.0;
    for (const [skill, threshold] of Object.entries(K.coverage_thresholds)) {
      let best = -Infinity;
      for (const p of squad) best = Math.max(best, p[skill]);
      if (best < threshold) {
        const weight = K.fit_weights[skill] === undefined ? 1.0 : K.fit_weights[skill];
        penalty += weight * (threshold - best) * 1.5;
      }
    }
    return penalty;
  }

  /** Project a five-man unit. Mirrors impact.lineup.LineupModel.evaluate. */
  function evaluateLineup(payload, playerIds, opponentIds) {
    const K = payload.constants;
    const squad = playerIds.map(id => payload.playersById[id]);
    if (squad.some(p => !p)) throw new Error('unknown player in lineup');
    if (new Set(playerIds).size !== playerIds.length) {
      throw new Error('a lineup cannot contain the same player twice');
    }
    if (playerIds.length !== K.players_on_floor) {
      throw new Error('a lineup is ' + K.players_on_floor + ' players, got ' + playerIds.length);
    }

    const additiveOff = squad.reduce((a, p) => a + p.off_impact, 0);
    const additiveDef = squad.reduce((a, p) => a + p.def_impact, 0);

    const usageTable = redistributeUsage(K, squad);
    const usageEffect = usageTable.reduce((a, r) => a + r.pts_per_100_effect, 0);

    const fitDetail = {};
    let fitBonus = 0.0;
    for (const skill of SKILLS) {
      const weight = K.fit_weights[skill] === undefined ? 0.0 : K.fit_weights[skill];
      const contribution = weight * mean(squad.map(p => p[skill]));
      fitDetail[skill] = contribution;
      fitBonus += contribution;
    }

    let penalty = coveragePenalty(K, squad);
    const creationSpread = stdev(squad.map(p => p.playmaking));
    let redundancy = 0.0;
    if (creationSpread < K.redundancy_threshold) {
      redundancy = K.redundancy_penalty * (K.redundancy_threshold - creationSpread);
    }
    penalty += redundancy;
    fitDetail.redundancy = -redundancy;

    let offRating = payload.meta.league_off_rating + additiveOff + usageEffect
      + fitBonus - penalty;
    let defRating = payload.meta.league_off_rating - additiveDef;

    if (opponentIds && opponentIds.length === K.players_on_floor) {
      const opp = opponentIds.map(id => payload.playersById[id]);
      offRating -= opp.reduce((a, p) => a + p.def_impact, 0);
      defRating += opp.reduce((a, p) => a + p.off_impact, 0);
    }

    return {
      players: playerIds.slice(),
      names: squad.map(p => p.name),
      off_rating: offRating,
      def_rating: defRating,
      net_rating: offRating - defRating,
      additive_off: additiveOff,
      additive_def: additiveDef,
      usage_effect: usageEffect,
      fit_bonus: fitBonus,
      coverage_penalty: penalty,
      fit_detail: fitDetail,
      usage_table: usageTable,
    };
  }

  /** Before/after for one substitution, with who absorbs the possessions. */
  function swapPlayer(payload, playerIds, outId, inId) {
    if (!playerIds.includes(outId)) throw new Error('that player is not in this lineup');
    if (playerIds.includes(inId)) throw new Error('that player is already in this lineup');
    const afterIds = playerIds.map(p => (p === outId ? inId : p));
    const before = evaluateLineup(payload, playerIds);
    const after = evaluateLineup(payload, afterIds);

    const byId = {};
    for (const r of before.usage_table) byId[r.player_id] = { before: r, after: null };
    for (const r of after.usage_table) {
      if (!byId[r.player_id]) byId[r.player_id] = { before: null, after: null };
      byId[r.player_id].after = r;
    }
    const shifts = Object.entries(byId).map(([pid, pair]) => ({
      player_id: pid,
      name: payload.playersById[pid] ? payload.playersById[pid].name : pid,
      usage_shift: (pair.after ? pair.after.adjusted_usage : 0)
        - (pair.before ? pair.before.adjusted_usage : 0),
      ts_shift: (pair.after && pair.before)
        ? pair.after.adjusted_ts_pct - pair.before.adjusted_ts_pct : null,
      pts_per_100_shift: (pair.after ? pair.after.pts_per_100_effect : 0)
        - (pair.before ? pair.before.pts_per_100_effect : 0),
    }));

    return {
      out_player: outId, in_player: inId,
      out_name: payload.playersById[outId].name,
      in_name: payload.playersById[inId].name,
      net_change: after.net_rating - before.net_rating,
      before: before, after: after, usage_shifts: shifts,
    };
  }

  /**
   * Can these five cover the five positions? Solved as a bipartite matching,
   * not by counting nominal positions, so versatile lineups pass.
   */
  function positionsViable(payload, playerIds) {
    const K = payload.constants;
    const slots = K.positions;
    const covers = playerIds.map(id => {
      const pos = payload.playersById[id].position;
      return new Set(K.position_coverage[pos] || [pos]);
    });
    const assigned = {};

    function tryAssign(i, seen) {
      for (let s = 0; s < slots.length; s++) {
        if (covers[i].has(slots[s]) && !seen.has(s)) {
          seen.add(s);
          if (assigned[s] === undefined || tryAssign(assigned[s], seen)) {
            assigned[s] = i;
            return true;
          }
        }
      }
      return false;
    }
    for (let i = 0; i < playerIds.length; i++) {
      if (!tryAssign(i, new Set())) return false;
    }
    return true;
  }

  /** Rank every candidate who could take one player's place. */
  function bestReplacement(payload, playerIds, outId, candidateIds, top) {
    const base = evaluateLineup(payload, playerIds);
    const pool = [...new Set(candidateIds)].filter(c => !playerIds.includes(c));
    const rows = [];
    for (const cand of pool) {
      if (!payload.playersById[cand]) continue;
      const after = playerIds.map(p => (p === outId ? cand : p));
      let ev;
      try { ev = evaluateLineup(payload, after); } catch (e) { continue; }
      rows.push({
        in_player: cand,
        name: payload.playersById[cand].name,
        position: payload.playersById[cand].position,
        net_rating: ev.net_rating,
        net_change: ev.net_rating - base.net_rating,
        off_rating: ev.off_rating,
        def_rating: ev.def_rating,
        usage_effect: ev.usage_effect,
      });
    }
    rows.sort((a, b) => b.net_change - a.net_change);
    return rows.slice(0, top || 12);
  }

  /** Search a candidate pool for the best legal five-man units. */
  function bestLineups(payload, candidateIds, top, requirePositions) {
    const pool = [...new Set(candidateIds)].filter(c => payload.playersById[c]);
    const n = pool.length;
    const K = payload.constants;
    if (n < K.players_on_floor) throw new Error('need at least five candidates');
    const rows = [];
    const idx = [0, 1, 2, 3, 4];
    while (true) {
      const combo = idx.map(i => pool[i]);
      if (!requirePositions || positionsViable(payload, combo)) {
        const ev = evaluateLineup(payload, combo);
        rows.push({
          players: combo, names: ev.names,
          net_rating: ev.net_rating, off_rating: ev.off_rating,
          def_rating: ev.def_rating, usage_effect: ev.usage_effect,
          fit_bonus: ev.fit_bonus, coverage_penalty: ev.coverage_penalty,
        });
      }
      // Next combination in lexicographic order.
      let i = 4;
      while (i >= 0 && idx[i] === i + n - 5) i--;
      if (i < 0) break;
      idx[i]++;
      for (let j = i + 1; j < 5; j++) idx[j] = idx[j - 1] + 1;
    }
    rows.sort((a, b) => b.net_rating - a.net_rating);
    return rows.slice(0, top || 10);
  }

  /* --------------------------------------------------- roster strength */

  /**
   * Split a team's 240 minutes across a roster, in proportion to last
   * season's per-game minutes. Mirrors impact.roster_strength.project_minutes.
   */
  function projectMinutes(K, minutesPerGame) {
    const cap = K.max_minutes_per_game;
    const total = K.team_minutes;
    const mpg = minutesPerGame.map(m => (Number.isFinite(m) && m > 0 ? m : 0));
    const sum = mpg.reduce((a, b) => a + b, 0);
    if (sum <= 0) return mpg.map(() => 0);

    let out = mpg.map(m => m * (total / sum));
    // A short roster cannot cover the game under the cap; there the cap is
    // arithmetically impossible, so it is dropped rather than fielding four
    // and a half men.
    if (out.filter(m => m > 0).length * cap < total) return out;

    for (let iter = 0; iter < 12; iter++) {
      const over = out.map(m => m > cap);
      if (!over.some(Boolean)) break;
      let spare = 0;
      for (let i = 0; i < out.length; i++) {
        if (over[i]) { spare += out[i] - cap; out[i] = cap; }
      }
      const room = out.map((m, i) => !over[i] && m > 0);
      const roomSum = out.reduce((a, m, i) => a + (room[i] ? m : 0), 0);
      if (roomSum <= 0) break;
      for (let i = 0; i < out.length; i++) {
        if (room[i]) out[i] += spare * (out[i] / roomSum);
      }
    }
    return out;
  }

  /** Uncalibrated offence and defence for a roster, in points per 100. */
  function rawStrength(K, roster) {
    if (!roster.length) return { off: 0, def: 0 };
    const mpg = roster.map(p => (p.games > 0 ? p.min / p.games : 0));
    const allocated = projectMinutes(K, mpg);
    if (allocated.reduce((a, b) => a + b, 0) <= 0) return { off: 0, def: 0 };
    let off = 0, def = 0;
    for (let i = 0; i < roster.length; i++) {
      const share = allocated[i] / K.team_minutes * K.players_on_floor;
      off += share * (roster[i].off_impact || 0);
      def += share * (roster[i].def_impact || 0);
    }
    return { off: off, def: def };
  }

  /**
   * Calibrated strength for a roster. The calibration is fitted against the
   * league's own net ratings, so the slope applies to both halves and the
   * intercept -- a whole-team offset -- is split between them.
   */
  function teamStrength(payload, roster) {
    const K = payload.constants;
    const cal = K.roster_strength;
    const raw = rawStrength(K, roster);
    const half = cal.intercept / 2;
    return {
      off: cal.slope * raw.off + half,
      def: cal.slope * raw.def + half,
      net: cal.slope * (raw.off + raw.def) + cal.intercept,
      raw_off: raw.off,
      raw_def: raw.def,
    };
  }

  /* ------------------------------------------------------ the season */

  /**
   * Play the schedule out. Returns per-team expected wins, playoff odds and
   * seed distribution.
   *
   * Expected wins is the sum of per-game win probabilities -- exact, no
   * simulation needed. Everything else (seeds, playoff odds) depends on how
   * teams finish relative to each other, which is not a sum, so those come
   * from simulating the actual schedule many times.
   *
   * `strengths` maps team_id to a net rating; passing it in rather than
   * recomputing means an edited roster flows straight through.
   */
  function projectSeason(payload, strengths, sims, seed) {
    const K = payload.constants;
    const teams = payload.teams;
    const idByAbbrev = {};
    for (const t of teams) idByAbbrev[t.team_abbrev] = t.team_id;

    const games = [];
    for (const g of (payload.schedule || [])) {
      const h = idByAbbrev[g[0]], a = idByAbbrev[g[1]];
      if (h && a) games.push([h, a]);
    }

    const ids = teams.map(t => t.team_id);
    const idx = {};
    ids.forEach((id, i) => { idx[id] = i; });
    const conf = teams.map(t => t.conference);

    // Per-game home win probability, fixed across simulations.
    const p = new Float64Array(games.length);
    for (let g = 0; g < games.length; g++) {
      const h = strengths[games[g][0]] || 0, a = strengths[games[g][1]] || 0;
      p[g] = winProbability(K, h, a);
    }

    const expected = new Float64Array(ids.length);
    const played = new Float64Array(ids.length);
    for (let g = 0; g < games.length; g++) {
      const hi = idx[games[g][0]], ai = idx[games[g][1]];
      expected[hi] += p[g];
      expected[ai] += 1 - p[g];
      played[hi] += 1; played[ai] += 1;
    }

    const nSims = sims || 2000;
    const rng = makeRng(seed === undefined ? 4242 : seed);
    const playoff = new Float64Array(ids.length);
    const playIn = new Float64Array(ids.length);
    const topSeed = new Float64Array(ids.length);
    const seedSum = new Float64Array(ids.length);
    const wins = new Float64Array(ids.length);
    const winSum = new Float64Array(ids.length);
    const winsBySim = [];
    for (let i = 0; i < ids.length; i++) winsBySim.push(new Float64Array(nSims));

    // A projection is not a fact. Each simulated season draws every team's
    // true strength from around its projection, by as much as projections
    // are actually wrong a year out. Without this the model reports 70-win
    // seasons and near-certain seeds, which the evidence does not support.
    const sd = K.team_strength_sd || 0;
    const shock = new Float64Array(ids.length);
    const gp = new Float64Array(games.length);

    for (let s = 0; s < nSims; s++) {
      wins.fill(0);
      if (sd > 0) {
        for (let i = 0; i < ids.length; i++) shock[i] = gauss(rng) * sd;
        for (let g = 0; g < games.length; g++) {
          const hi = idx[games[g][0]], ai = idx[games[g][1]];
          gp[g] = winProbability(K,
            (strengths[games[g][0]] || 0) + shock[hi],
            (strengths[games[g][1]] || 0) + shock[ai]);
        }
      } else {
        for (let g = 0; g < games.length; g++) gp[g] = p[g];
      }
      for (let g = 0; g < games.length; g++) {
        const hi = idx[games[g][0]], ai = idx[games[g][1]];
        if (rng() < gp[g]) wins[hi] += 1; else wins[ai] += 1;
      }
      for (let i = 0; i < ids.length; i++) {
        winSum[i] += wins[i];
        winsBySim[i][s] = wins[i];
      }
      for (const c of ['East', 'West']) {
        const order = [];
        for (let i = 0; i < ids.length; i++) if (conf[i] === c) order.push(i);
        // Ties are broken by a coin flip rather than by index, so no team
        // gets a seed for being early in the alphabet.
        order.sort((x, y) => (wins[y] - wins[x]) || (rng() - 0.5));
        for (let r = 0; r < order.length; r++) {
          const i = order[r];
          seedSum[i] += r + 1;
          if (r < 6) playoff[i] += 1;
          else if (r < 10) playIn[i] += 1;
          if (r === 0) topSeed[i] += 1;
        }
      }
    }

    // The published schedule holds back two games a team pending cup
    // results, so scale the season out to its real length rather than
    // reporting an 80-game record as if it were the whole year.
    const full = K.games_per_season || 82;
    const pct = (arr, q) => {
      const sorted = Array.from(arr).sort((a, b) => a - b);
      return sorted[Math.min(sorted.length - 1, Math.floor(q * sorted.length))];
    };
    return teams.map((t, i) => {
      const scale = played[i] > 0 ? full / played[i] : 1;
      const mean = (sd > 0 ? winSum[i] / nSims : expected[i]) * scale;
      return {
        team_id: t.team_id,
        team_abbrev: t.team_abbrev,
        team_name: t.team_name,
        conference: t.conference,
        net: strengths[t.team_id] || 0,
        wins: mean,
        losses: full - mean,
        // The range a season this uncertain can plausibly land in.
        wins_low: pct(winsBySim[i], 0.10) * scale,
        wins_high: pct(winsBySim[i], 0.90) * scale,
        scheduled: played[i],
        playoff_odds: playoff[i] / nSims,
        play_in_odds: playIn[i] / nSims,
        top_seed_odds: topSeed[i] / nSims,
        avg_seed: seedSum[i] / nSims,
      };
    });
  }

  /** Strength of schedule: the average opponent a team actually faces. */
  function scheduleStrength(payload, strengths) {
    const idByAbbrev = {};
    for (const t of payload.teams) idByAbbrev[t.team_abbrev] = t.team_id;
    const sum = {}, n = {};
    for (const g of (payload.schedule || [])) {
      const h = idByAbbrev[g[0]], a = idByAbbrev[g[1]];
      if (!h || !a) continue;
      sum[h] = (sum[h] || 0) + (strengths[a] || 0); n[h] = (n[h] || 0) + 1;
      sum[a] = (sum[a] || 0) + (strengths[h] || 0); n[a] = (n[a] || 0) + 1;
    }
    const out = {};
    for (const id of Object.keys(n)) out[id] = sum[id] / n[id];
    return out;
  }

  /* ------------------------------------------------------- rate bases */

  /** Put a player's counting stats on a rate basis. Mirrors metrics.normalize. */
  function normalize(payload, player, mode) {
    const K = payload.constants;
    const counts = payload.count_columns;
    const out = {};
    let denom, basis;
    if (mode === 'totals') { denom = 1; basis = 1; }
    else if (mode === 'per_game') { denom = player.games; basis = 1; }
    else if (K.per_minute_bases[mode] !== undefined) {
      denom = player.min; basis = K.per_minute_bases[mode];
    } else if (K.per_possession_bases[mode] !== undefined) {
      denom = player.poss; basis = K.per_possession_bases[mode];
    } else {
      throw new Error('unknown rate basis ' + mode);
    }
    for (const c of counts) {
      out[c] = denom > 0 ? (player[c] * basis) / denom : null;
    }
    return out;
  }

  /* ------------------------------------------------------- simulation */

  function restAdjustment(K, days) {
    const table = K.rest_adjustment;
    const key = String(days);
    return table[key] === undefined ? K.rest_adjustment_default : table[key];
  }

  function projectedMargin(K, homeRating, awayRating, opts) {
    const o = opts || {};
    let margin = homeRating - awayRating;
    if (!o.neutral) margin += K.home_advantage;
    if (o.homeRest !== undefined) margin += restAdjustment(K, o.homeRest);
    if (o.awayRest !== undefined) margin -= restAdjustment(K, o.awayRest);
    return margin;
  }

  function winProbability(K, homeRating, awayRating, opts) {
    return normalCdf(projectedMargin(K, homeRating, awayRating, opts) / K.game_margin_sd);
  }

  /**
   * Possession-level Monte Carlo, including the self-correction that keeps
   * the margin distribution realistic. Mirrors sim.game.simulate_game.
   */
  function simulateGame(payload, homeRating, awayRating, nSims, seed) {
    const K = payload.constants;
    const rng = makeRng(seed === undefined ? 12345 : seed);
    const outcomes = K.possession_outcomes;
    const baseProbs = K.possession_base_probs;
    const baseScoreProb = 1 - baseProbs[0];
    let baseMean = 0;
    for (let i = 0; i < outcomes.length; i++) baseMean += outcomes[i] * baseProbs[i];
    const conditionalMean = baseMean / baseScoreProb;

    function cdfFor(targetPpp) {
      const needed = clamp(targetPpp / conditionalMean, 0.05, 0.95);
      const probs = baseProbs.slice();
      let tail = 0;
      for (let i = 1; i < probs.length; i++) {
        probs[i] = probs[i] * (needed / baseScoreProb);
        tail += probs[i];
      }
      probs[0] = 1 - tail;
      const cdf = [];
      let acc = 0;
      for (const p of probs) { acc += p; cdf.push(acc); }
      return cdf;
    }

    const league = payload.meta.league_off_rating;
    const homeOff = league + homeRating / 2, homeDef = league - homeRating / 2;
    const awayOff = league + awayRating / 2, awayDef = league - awayRating / 2;
    let homePpp = (homeOff + awayDef - league) / 100 + K.home_advantage / 2 / 100;
    let awayPpp = (awayOff + homeDef - league) / 100 - K.home_advantage / 2 / 100;

    const homeScores = new Float64Array(nSims);
    const awayScores = new Float64Array(nSims);
    const chunks = 8;

    for (let s = 0; s < nSims; s++) {
      const poss = Math.max(60, Math.round(K.pace + gauss(rng) * K.pace_sd));
      const homeShock = gauss(rng) * K.efficiency_shock_sd / 100;
      const awayShock = gauss(rng) * K.efficiency_shock_sd / 100;
      let h = 0, a = 0, played = 0;
      for (let c = 0; c < chunks; c++) {
        const start = Math.floor(poss * (c / chunks));
        const end = Math.floor(poss * ((c + 1) / chunks));
        const len = end - start;
        if (len <= 0) continue;
        const expected = (homePpp - awayPpp) * played;
        const deviation = (h - a) - expected;
        const remaining = 1 - c / chunks;
        const adjust = K.mean_reversion * deviation / 100 * remaining;
        const hc = cdfFor(clamp(homePpp + homeShock - adjust, 0.55, 1.75));
        const ac = cdfFor(clamp(awayPpp + awayShock + adjust, 0.55, 1.75));
        for (let p = 0; p < len; p++) {
          h += outcomes[pick(hc, rng())];
          a += outcomes[pick(ac, rng())];
        }
        played += len;
      }
      homeScores[s] = h;
      awayScores[s] = a;
    }

    const margins = new Float64Array(nSims);
    let wins = 0, ties = 0;
    for (let i = 0; i < nSims; i++) {
      margins[i] = homeScores[i] - awayScores[i];
      if (margins[i] > 0) wins++; else if (margins[i] === 0) ties++;
    }
    return {
      home_scores: homeScores, away_scores: awayScores, margins: margins,
      home_win_prob: (wins + 0.5 * ties) / nSims,
      mean_home: meanOf(homeScores), mean_away: meanOf(awayScores),
      mean_margin: meanOf(margins), margin_sd: sdOf(margins),
      n_sims: nSims,
    };
  }

  function pick(cdf, u) {
    for (let i = 0; i < cdf.length; i++) if (u < cdf[i]) return i;
    return cdf.length - 1;
  }
  function meanOf(arr) { let s = 0; for (const x of arr) s += x; return s / arr.length; }
  function sdOf(arr) {
    const m = meanOf(arr);
    let s = 0;
    for (const x of arr) s += (x - m) * (x - m);
    return Math.sqrt(s / arr.length);
  }

  /** mulberry32: small, fast, seedable. Reproducible runs matter here. */
  function makeRng(seed) {
    let a = seed >>> 0;
    return function () {
      a |= 0; a = (a + 0x6D2B79F5) | 0;
      let t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  /** Box-Muller, one draw at a time. */
  function gauss(rng) {
    let u = 0, v = 0;
    while (u === 0) u = rng();
    while (v === 0) v = rng();
    return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
  }

  /* -------------------------------------------------------------- api */

  const api = {
    mean, stdev, clamp, normalCdf,
    tsDelta, redistributeUsage,
    projectMinutes, rawStrength, teamStrength,
    projectSeason, scheduleStrength,
    evaluateLineup, swapPlayer, positionsViable, bestReplacement, bestLineups,
    normalize, projectedMargin, winProbability, simulateGame, makeRng,
    SKILLS,
  };

  // A global is the only export, because a global is how the browser actually
  // loads this file: a plain <script> tag in the standalone page. A CommonJS
  // branch here would be dead code -- the repository's package.json declares
  // "type": "module", so node treats this file as ESM and `module` is
  // undefined. Tests load it the same way the browser does.
  root.HoopsimEngine = api;

})(typeof globalThis !== 'undefined' ? globalThis : this);
