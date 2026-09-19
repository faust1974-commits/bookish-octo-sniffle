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
