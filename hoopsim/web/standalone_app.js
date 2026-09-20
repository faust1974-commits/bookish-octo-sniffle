/* UI for the standalone file. All data is already in the page, so nothing here
 * talks to a network -- every number is computed locally by HoopsimEngine. */
'use strict';

(function () {
  const E = window.HoopsimEngine;
  const D = window.__HOOPSIM__;
  const K = D.constants;

  D.playersById = {};
  for (const p of D.players) D.playersById[p.player_id] = p;
  const teamsById = {};
  for (const t of D.teams) teamsById[t.team_id] = t;

  const S = { lineup: [], team: null, sort: {}, rapmMode: false };

  /* ---------------------------------------------------------- helpers */

  const $ = (s) => document.querySelector(s);
  const el = (tag, cls, text) => {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text !== undefined && text !== null) n.textContent = text;
    return n;
  };
  const num = (v, d = 1) => (v === null || v === undefined || Number.isNaN(v))
    ? '' : Number(v).toFixed(d);
  const signed = (v, d = 1) => (v === null || v === undefined || Number.isNaN(v))
    ? '' : (v >= 0 ? '+' : '') + Number(v).toFixed(d);
  const cls = (v) => (v > 0 ? 'pos-val' : v < 0 ? 'neg-val' : '');

  function toast(msg, ms = 2600) {
    const t = $('#toast');
    t.textContent = msg;
    t.classList.remove('hidden');
    clearTimeout(toast._t);
    toast._t = setTimeout(() => t.classList.add('hidden'), ms);
  }

  const RATE_COLS = new Set(['ts_pct', 'efg_pct', 'fg_pct', 'fg3_pct', 'ft_pct',
    'usage_rate', 'ast_rate', 'trb_rate', 'orb_rate', 'drb_rate', 'stl_rate',
    'blk_rate', 'tov_rate', 'fg3a_rate', 'ft_rate', 'win_pct', 'ws_per_48',
    'pythag_win_pct', 'off_efg_pct', 'off_tov_rate', 'off_orb_rate',
    'off_ft_rate', 'def_efg_pct', 'def_tov_rate', 'def_drb_rate', 'def_ft_rate',
    'usage', 'base_usage', 'adjusted_usage']);
  const SIGNED_COLS = new Set(['box_impact', 'net_rating', 'adj_net_rating',
    'srs', 'sos', 'luck', 'rapm', 'rapm_off', 'rapm_def', 'margin', 'impact',
    'net_change', 'usage_effect', 'fit_bonus', 'usage_change', 'ts_change',
    'usage_shift', 'ts_shift', 'pts_per_100_shift', 'pts_per_100_effect',
    'home_margin_per_100', 'off_impact', 'def_impact']);

  function fmt(key, v) {
    if (v === null || v === undefined) return '';
    if (typeof v === 'boolean') return v ? 'yes' : 'no';
    if (typeof v !== 'number') return String(v);
    if (RATE_COLS.has(key)) return v.toFixed(3);
    if (SIGNED_COLS.has(key)) return signed(v, 2);
    if (Number.isInteger(v)) return String(v);
    return v.toFixed(Math.abs(v) < 10 ? 2 : 1);
  }

  function table(mount, rows, columns, opts = {}) {
    mount.innerHTML = '';
    if (!rows || !rows.length) {
      mount.appendChild(el('p', 'empty', 'Nothing to show here.'));
      return;
    }
    const key = opts.sortKey || mount.id;
    const sort = S.sort[key] || { col: opts.defaultSort || columns[0].k, dir: -1 };
    S.sort[key] = sort;

    const sorted = rows.slice().sort((a, b) => {
      const x = a[sort.col], y = b[sort.col];
      if (x === y) return 0;
      if (x === null || x === undefined) return 1;
      if (y === null || y === undefined) return -1;
      return (x > y ? 1 : -1) * sort.dir;
    });

    const wrap = el('div', 'scroll');
    const t = el('table');
    const head = el('tr');
    columns.forEach((c) => {
      const th = el('th', c.k === sort.col ? 'sorted' : '', c.label);
      if (c.title) th.title = c.title;
      th.addEventListener('click', () => {
        if (sort.col === c.k) sort.dir *= -1;
        else { sort.col = c.k; sort.dir = -1; }
        table(mount, rows, columns, opts);
      });
      head.appendChild(th);
    });
    const thead = el('thead'); thead.appendChild(head); t.appendChild(thead);

    const body = el('tbody');
    sorted.slice(0, opts.limit || 500).forEach((r) => {
      const tr = el('tr');
      columns.forEach((c) => {
        const td = el('td', typeof r[c.k] === 'number' ? 'num' : '');
        td.textContent = fmt(c.k, r[c.k]);
        if (SIGNED_COLS.has(c.k) && typeof r[c.k] === 'number') td.classList.add(cls(r[c.k]));
        tr.appendChild(td);
      });
      body.appendChild(tr);
    });
    t.appendChild(body); wrap.appendChild(t); mount.appendChild(wrap);
  }

  function fillSelect(sel, items, selected) {
    sel.innerHTML = '';
    items.forEach((it) => {
      const o = el('option', null, it.label);
      o.value = it.value;
      sel.appendChild(o);
    });
    if (selected !== undefined) sel.value = selected;
  }

  /* ------------------------------------------------------------ boot */

  function boot() {
    const rs = D.meta.roster_season;
    $('#league-meta').textContent = rs
      ? `${rs} rosters · ${D.meta.season} numbers · ${D.teams.length} teams · ` +
        `${D.players.length} players`
      : `${D.meta.season} · ${D.meta.source} · ${D.teams.length} teams · ` +
        `${D.players.length} players · ${D.meta.n_games} games`;

    const c = D.meta.roster_counts;
    const counts = c
      ? ` Of ${c.players} players under contract, ${c.current} have ` +
        `${D.meta.season} numbers, ${c.prior} last played in ` +
        `${D.meta.fallback_season}, and ${c.unrated} have no NBA record yet.`
      : '';
    $('#provenance').textContent = (rs
      ? `Rosters are ${rs}, as of ${D.meta.generated}. The ratings come from ` +
        `games actually played in ${D.meta.season} — a trade moves a player, ` +
        `not his production.${counts} `
      : `Generated ${D.meta.generated} by hoopsim ${D.meta.version} from ` +
        `${D.meta.source} data. `) +
      `Everything in this file is computed locally — it works with no ` +
      `internet connection and sends nothing anywhere.`;

    const teamItems = D.teams.map(t => ({
      value: t.team_id, label: `${t.team_abbrev} — ${t.team_name}`,
    }));
    fillSelect($('#lineup-team'), teamItems);
    fillSelect($('#sim-home'), teamItems);
    fillSelect($('#sim-away'), teamItems, D.teams[1] ? D.teams[1].team_id : D.teams[0].team_id);
    fillSelect($('#player-team'), [{ value: '', label: 'all teams' }, ...teamItems], '');

    const modes = ['totals', 'per_game', 'per_24', 'per_36', 'per_40', 'per_48',
      'per_75', 'per_100'];
    fillSelect($('#per-mode'), modes.map(m => ({ value: m, label: m.replace('_', ' ') })), 'per_36');

    const dims = Object.entries(D.splits).map(([k, v]) => ({
      value: k, label: `${v.label} (${v.level})`,
    }));
    if (dims.length) fillSelect($('#split-dimension'), dims, dims[0].value);

    document.querySelectorAll('.tab').forEach((btn) => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.tab').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
        btn.classList.add('active');
        $('#tab-' + btn.dataset.tab).classList.add('active');
      });
    });

    $('#lineup-team').addEventListener('change', (e) => {
      S.team = e.target.value; S.lineup = [];
      $('#best-card').classList.add('hidden');
      renderRoster(); evaluate();
    });
    $('#load-starters').addEventListener('click', () => {
      S.lineup = teamPlayers(S.team).slice(0, 5).map(p => p.player_id);
      renderRoster(); evaluate();
    });
    $('#clear-lineup').addEventListener('click', () => {
      S.lineup = []; renderRoster(); evaluate();
    });
    $('#do-swap').addEventListener('click', doSwap);
    $('#rank-replacements').addEventListener('click', rankReplacements);
    $('#find-best').addEventListener('click', findBest);

    ['#per-mode', '#min-minutes', '#player-team'].forEach(s =>
      $(s).addEventListener('change', loadPlayers));
    $('#player-search').addEventListener('input', loadPlayers);
    $('#show-rapm').addEventListener('click', () => {
      S.rapmMode = !S.rapmMode;
      $('#show-rapm').textContent = S.rapmMode ? 'Show box metrics' : 'Show impact ratings';
      loadPlayers();
    });
    $('#split-dimension').addEventListener('change', loadSplits);
    $('#run-game').addEventListener('click', runGame);

    S.team = D.teams[0].team_id;
    $('#lineup-team').value = S.team;
    renderRoster();
    loadPlayers();
    loadTeams();
    loadSplits();
  }

  /* --------------------------------------------------------- lineups */

  function teamPlayers(teamId) {
    return D.players.filter(p => p.team_id === teamId)
      .sort((a, b) => (a.unrated ? 1 : 0) - (b.unrated ? 1 : 0)
        || (b.min || 0) - (a.min || 0));
  }

  function renderRoster() {
    const mount = $('#roster');
    mount.innerHTML = '';
    const roster = teamPlayers(S.team);
    if (!roster.length) {
      mount.appendChild(el('p', 'empty', 'No players with enough minutes on this team.'));
      return;
    }
    roster.forEach((p) => {
      const row = el('div', 'player-row' + (S.lineup.includes(p.player_id) ? ' selected' : ''));
      const nm = el('span', 'nm', p.name);
      if (p.unrated) {
        nm.appendChild(el('span', 'vintage unrated', 'no NBA record'));
      } else if (p.data_season && p.data_season !== D.meta.season) {
        const tag = el('span', 'vintage', p.data_season);
        tag.title = `Did not play in ${D.meta.season}; these are his ` +
          `${p.data_season} numbers.`;
        nm.appendChild(tag);
      }
      row.appendChild(nm);
      row.appendChild(el('span', 'pos', p.position));
      const imp = el('span', 'num ' + cls(p.impact), signed(p.impact, 1));
      imp.title = p.unrated
        ? 'He has never played an NBA possession. Shown at replacement level ' +
          'because that is the least-wrong placeholder, not a projection.'
        : 'impact: points per 100 possessions versus an average player';
      row.appendChild(imp);
      const usg = el('span', 'num', (p.usage * 100).toFixed(1) + '%');
      usg.title = 'usage: share of the team’s possessions he ends';
      row.appendChild(usg);
      row.addEventListener('click', () => toggle(p.player_id));
      mount.appendChild(row);
    });
    renderSlots();
  }

  function toggle(pid) {
    const i = S.lineup.indexOf(pid);
    if (i >= 0) S.lineup.splice(i, 1);
    else if (S.lineup.length >= 5) { toast('Five on the floor. Remove someone first.'); return; }
    else S.lineup.push(pid);
    renderRoster(); evaluate();
  }

  function renderSlots() {
    const mount = $('#lineup-slots');
    mount.innerHTML = '';
    for (let i = 0; i < 5; i++) {
      const pid = S.lineup[i];
      const slot = el('div', 'slot' + (pid ? ' filled' : ''));
      slot.appendChild(el('span', 'pos', pid ? D.playersById[pid].position : '·'));
      slot.appendChild(el('span', null, pid ? D.playersById[pid].name : 'empty'));
      if (pid) {
        const x = el('button', 'remove', '✕');
        x.addEventListener('click', (e) => { e.stopPropagation(); toggle(pid); });
        slot.appendChild(x);
      } else slot.appendChild(el('span'));
      mount.appendChild(slot);
    }
    $('#lineup-count').textContent = `${S.lineup.length} of 5`;

    const onFloor = S.lineup.map(p => ({ value: p, label: D.playersById[p].name }));
    fillSelect($('#swap-out'), onFloor.length ? onFloor : [{ value: '', label: '—' }]);
    const bench = teamPlayers(S.team).filter(p => !S.lineup.includes(p.player_id));
    fillSelect($('#swap-in'), bench.length
      ? bench.map(p => ({ value: p.player_id, label: p.name }))
      : [{ value: '', label: '—' }]);
  }

  function evaluate() {
    const result = $('#lineup-result'), warn = $('#lineup-warning');
    if (S.lineup.length !== 5) {
      result.innerHTML = ''; $('#breakdown').innerHTML = ''; $('#usage-table').innerHTML = '';
      warn.classList.add('hidden');
      return;
    }
    let ev;
    try { ev = E.evaluateLineup(D, S.lineup); }
    catch (err) { toast(err.message); return; }

    result.innerHTML = '';
    result.appendChild(el('div', 'bignum ' + cls(ev.net_rating), signed(ev.net_rating, 2)));
    result.appendChild(el('div', 'hint',
      'projected net rating — points per 100 possessions better than the opponent'));
    const kv = el('div', 'kv');
    [['offensive rating', num(ev.off_rating, 1)],
     ['defensive rating', num(ev.def_rating, 1)]].forEach(([k, v]) => {
      kv.appendChild(el('div', 'k', k));
      kv.appendChild(el('div', 'v', v));
    });
    result.appendChild(kv);

    const viable = E.positionsViable(D, S.lineup);
    const gap = ev.coverage_penalty >= 4;
    warn.classList.toggle('hidden', viable && !gap);
    if (!viable) {
      warn.textContent = 'These five cannot cover the five positions between them.';
    } else if (gap) {
      warn.textContent = 'This five has a coverage gap — a skill nobody on the floor provides.';
    }

    renderBreakdown(ev);
    renderUsage(ev.usage_table);
  }

  function renderBreakdown(ev) {
    const mount = $('#breakdown');
    mount.innerHTML = '';
    const kv = el('div', 'kv');
    const add = (label, v, note) => {
      const k = el('div', 'k', label);
      if (note) k.title = note;
      kv.appendChild(k);
      kv.appendChild(el('div', 'v ' + cls(v), signed(v, 2)));
    };
    add('each player’s own offence', ev.additive_off,
      'the sum of what these five are worth on offence');
    add('each player’s own defence', ev.additive_def);
    add('usage redistribution', ev.usage_effect,
      'the cost or gain of fitting five usage rates into one possession');
    add('fit', ev.fit_bonus, 'spacing, rim pressure, playmaking, rebounding, rim protection');
    add('coverage penalty', -ev.coverage_penalty,
      'charged when nobody on the floor provides a needed skill');
    kv.appendChild(el('div', 'rule'));
    add('net rating', ev.net_rating);
    mount.appendChild(kv);

    const detail = Object.entries(ev.fit_detail || {});
    if (!detail.length) return;
    mount.appendChild(el('h2', null, 'Fit, by dimension'));
    const bars = el('div', 'bars');
    const max = Math.max(0.5, ...detail.map(([, v]) => Math.abs(v)));
    detail.forEach(([k, v]) => {
      const row = el('div', 'bar-row');
      row.appendChild(el('span', null, k.replace(/_/g, ' ')));
      const track = el('div', 'bar-track');
      const zero = el('div', 'bar-zero'); zero.style.left = '50%'; track.appendChild(zero);
      const fill = el('div', 'bar-fill');
      const half = Math.abs(v) / max * 50;
      fill.style.width = half + '%';
      fill.style.left = v >= 0 ? '50%' : (50 - half) + '%';
      fill.style.background = v >= 0 ? 'var(--good)' : 'var(--bad)';
      track.appendChild(fill);
      row.appendChild(track);
      row.appendChild(el('span', 'num ' + cls(v), signed(v, 2)));
      bars.appendChild(row);
    });
    mount.appendChild(bars);
  }

  function renderUsage(rows) {
    table($('#usage-table'), rows, [
      { k: 'name', label: 'player' },
      { k: 'base_usage', label: 'usual usage', title: 'his established share of possessions' },
      { k: 'adjusted_usage', label: 'in this five' },
      { k: 'usage_change', label: 'change' },
      { k: 'base_ts_pct', label: 'usual TS%' },
      { k: 'adjusted_ts_pct', label: 'adjusted TS%' },
      { k: 'pts_per_100_effect', label: 'pts/100' },
    ], { sortKey: 'usage', defaultSort: 'adjusted_usage' });
  }

  function doSwap() {
    if (S.lineup.length !== 5) { toast('Put five players on the floor first.'); return; }
    const out = $('#swap-out').value, inp = $('#swap-in').value;
    if (!out || !inp) { toast('Pick a player to take off and one to bring on.'); return; }
    let res;
    try { res = E.swapPlayer(D, S.lineup, out, inp); }
    catch (err) { toast(err.message); return; }

    const mount = $('#swap-result');
    mount.innerHTML = '';
    mount.appendChild(el('div', 'bignum ' + cls(res.net_change), signed(res.net_change, 2)));
    mount.appendChild(el('div', 'hint',
      `change in net rating — off ${res.out_name}, on ${res.in_name} ` +
      `(${signed(res.before.net_rating, 2)} → ${signed(res.after.net_rating, 2)})`));

    const shifts = res.usage_shifts.filter(r =>
      r.player_id !== res.out_player && r.player_id !== res.in_player
      && Math.abs(r.usage_shift) > 1e-9);
    if (shifts.length) {
      mount.appendChild(el('h2', null, 'Who absorbs the possessions'));
      mount.appendChild(el('p', 'hint',
        'A simple per-36 projection says these four are unchanged. They are not — ' +
        'the departing player’s shots go to them, and cost them efficiency.'));
      const t = el('div'); mount.appendChild(t);
      table(t, shifts, [
        { k: 'name', label: 'player' },
        { k: 'usage_shift', label: 'usage change' },
        { k: 'ts_shift', label: 'TS% change' },
        { k: 'pts_per_100_shift', label: 'pts/100' },
      ], { sortKey: 'shifts', defaultSort: 'usage_shift' });
    }
    const apply = el('button', 'ghost', 'Make this change');
    apply.addEventListener('click', () => {
      S.lineup = S.lineup.map(p => (p === res.out_player ? res.in_player : p));
      renderRoster(); evaluate(); mount.innerHTML = '';
    });
    mount.appendChild(el('div', null, ' '));
    mount.appendChild(apply);
  }

  function rankReplacements() {
    if (S.lineup.length !== 5) { toast('Put five players on the floor first.'); return; }
    const out = $('#swap-out').value;
    const candidates = teamPlayers(S.team).map(p => p.player_id);
    const rows = E.bestReplacement(D, S.lineup, out, candidates, 15);
    const mount = $('#swap-result');
    mount.innerHTML = '';
    mount.appendChild(el('h2', null, `Every replacement for ${D.playersById[out].name}`));
    const t = el('div'); mount.appendChild(t);
    table(t, rows, [
      { k: 'name', label: 'player' },
      { k: 'position', label: 'pos' },
      { k: 'net_change', label: 'net change' },
      { k: 'net_rating', label: 'net rating' },
      { k: 'off_rating', label: 'offence' },
      { k: 'def_rating', label: 'defence' },
    ], { sortKey: 'replacements', defaultSort: 'net_change' });
  }

  function findBest() {
    const card = $('#best-card'), mount = $('#best-result');
    card.classList.remove('hidden');
    mount.innerHTML = '<div class="spinner">searching every combination…</div>';
    setTimeout(() => {
      const pool = teamPlayers(S.team).slice(0, 10).map(p => p.player_id);
      let rows;
      try { rows = E.bestLineups(D, pool, 12, true); }
      catch (err) { mount.innerHTML = ''; toast(err.message); return; }
      mount.innerHTML = '';
      rows.forEach((r) => {
        const row = el('div', 'player-row');
        row.appendChild(el('span', 'nm', r.names.join(', ')));
        row.appendChild(el('span', 'pos', ''));
        row.appendChild(el('span', 'num ' + cls(r.net_rating), signed(r.net_rating, 2)));
        row.appendChild(el('span', 'num', num(r.off_rating, 1) + ' / ' + num(r.def_rating, 1)));
        row.title = 'click to put this five on the floor';
        row.addEventListener('click', () => {
          S.lineup = r.players.slice();
          renderRoster(); evaluate();
          window.scrollTo({ top: 0, behavior: 'smooth' });
        });
        mount.appendChild(row);
      });
    }, 10);
  }

  /* --------------------------------------------------------- players */

  const HELP = {
    totals: 'Season totals, no denominator.',
    per_game: 'Divided by games played. Mixes production with playing time.',
    per_24: 'Per 24 minutes — half a game. Useful for bench roles.',
    per_36: 'Per 36 minutes — a starter’s workload. The usual default.',
    per_40: 'Per 40 minutes — college and international regulation.',
    per_48: 'Per 48 minutes — a whole game; inflates everything.',
    per_75: 'Per 75 possessions — pace-independent, close to per-game scale.',
    per_100: 'Per 100 possessions — pace-independent, the classic standard.',
  };

  function loadPlayers() {
    const per = $('#per-mode').value;
    const minMinutes = Number($('#min-minutes').value || 0);
    const team = $('#player-team').value;
    const q = ($('#player-search').value || '').toLowerCase();
    $('#per-mode-help').textContent = HELP[per] || '';

    let pool = D.players.filter(p => (p.min || 0) >= minMinutes);
    if (team) pool = pool.filter(p => p.team_id === team);
    if (q) pool = pool.filter(p => (p.name || '').toLowerCase().includes(q));

    if (S.rapmMode) {
      const rows = pool.filter(p => p.rapm !== undefined && p.rapm !== null);
      table($('#players-table'), rows, [
        { k: 'name', label: 'player' },
        { k: 'position', label: 'pos' },
        { k: 'rapm_poss', label: 'possessions' },
        { k: 'rapm_off', label: 'offence' },
        { k: 'rapm_def', label: 'defence' },
        { k: 'rapm', label: 'impact', title: 'points per 100 possessions vs an average player' },
      ], { sortKey: 'players-rapm', defaultSort: 'rapm' });
      return;
    }

    const rows = pool.map((p) => {
      const rated = E.normalize(D, p, per);
      return Object.assign({}, p, rated);
    });
    table($('#players-table'), rows, [
      { k: 'name', label: 'player' },
      { k: 'position', label: 'pos' },
      { k: 'games', label: 'G' },
      { k: 'min', label: 'MIN' },
      { k: 'pts', label: 'PTS' },
      { k: 'trb', label: 'REB' },
      { k: 'ast', label: 'AST' },
      { k: 'ts_pct', label: 'TS%', title: 'true shooting percentage' },
      { k: 'usage_rate', label: 'USG%' },
      { k: 'per', label: 'PER' },
      { k: 'ws', label: 'WS', title: 'win shares' },
      { k: 'box_impact', label: 'impact' },
    ], { sortKey: 'players', defaultSort: 'box_impact' });
  }

  /* ----------------------------------------------------------- teams */

  function loadTeams() {
    table($('#teams-table'), D.teams, [
      { k: 'team_abbrev', label: 'team' },
      { k: 'conference', label: 'conf' },
      { k: 'w', label: 'W' }, { k: 'l', label: 'L' },
      { k: 'pace', label: 'pace' },
      { k: 'off_rating', label: 'offence' },
      { k: 'def_rating', label: 'defence' },
      { k: 'adj_net_rating', label: 'adjusted net', title: 'adjusted for who they played' },
      { k: 'srs', label: 'SRS' },
      { k: 'pythag_win_pct', label: 'expected win%' },
      { k: 'luck', label: 'luck', title: 'wins above what the scoring says they deserved' },
    ], { sortKey: 'teams', defaultSort: 'adj_net_rating' });

    table($('#factors-table'), D.teams, [
      { k: 'team_abbrev', label: 'team' },
      { k: 'off_efg_pct', label: 'eFG%' },
      { k: 'off_tov_rate', label: 'TOV%' },
      { k: 'off_orb_rate', label: 'ORB%' },
      { k: 'off_ft_rate', label: 'FT rate' },
      { k: 'def_efg_pct', label: 'opp eFG%' },
      { k: 'def_tov_rate', label: 'opp TOV%' },
      { k: 'def_drb_rate', label: 'DRB%' },
      { k: 'def_ft_rate', label: 'opp FT rate' },
    ], { sortKey: 'factors', defaultSort: 'off_efg_pct' });
  }

  /* ---------------------------------------------------------- splits */

  function loadSplits() {
    const key = $('#split-dimension').value;
    const split = D.splits[key];
    const mount = $('#splits-table');
    if (!split) { mount.innerHTML = '<p class="empty">Nothing to show here.</p>'; return; }
    $('#split-help').textContent = split.description;
    const skip = new Set(['team_id']);
    const columns = Object.keys(split.rows[0])
      .filter(k => !skip.has(k))
      .map(k => ({ k, label: k.replace(/_/g, ' ') }));
    // Buckets read best in their natural order, so seed the sort ascending.
    S.sort.splits = { col: 'bucket', dir: 1 };
    table(mount, split.rows, columns, { sortKey: 'splits' });
  }

  /* -------------------------------------------------------- simulate */

  function runGame() {
    const home = $('#sim-home').value, away = $('#sim-away').value;
    if (home === away) { toast('Pick two different teams.'); return; }
    const mount = $('#game-result');
    mount.innerHTML = '<div class="spinner">simulating…</div>';
    setTimeout(() => {
      const hr = D.ratings[home] || 0, ar = D.ratings[away] || 0;
      const res = E.simulateGame(D, hr, ar, 10000, 7);
      const analytic = E.winProbability(K, hr, ar);
      mount.innerHTML = '';
      mount.appendChild(el('div', 'bignum', (res.home_win_prob * 100).toFixed(1) + '%'));
      mount.appendChild(el('div', 'hint',
        `${teamsById[home].team_name} win probability ` +
        `(quick model: ${(analytic * 100).toFixed(1)}%)`));
      const kv = el('div', 'kv');
      [['projected score', `${num(res.mean_home, 1)} — ${num(res.mean_away, 1)}`],
       ['margin', `${signed(res.mean_margin, 2)} (spread ${num(res.margin_sd, 1)})`],
       ['simulations run', res.n_sims.toLocaleString()]].forEach(([k, v]) => {
        kv.appendChild(el('div', 'k', k));
        kv.appendChild(el('div', 'v', v));
      });
      mount.appendChild(kv);
      drawHistogram(res.margins, teamsById[home].team_name);
    }, 10);
  }

  function drawHistogram(margins, homeName) {
    const mount = $('#margin-chart');
    mount.innerHTML = '';
    const bins = 41, lo = -50, hi = 50;
    const counts = new Array(bins).fill(0);
    for (const m of margins) {
      const i = Math.floor((m - lo) / (hi - lo) * bins);
      if (i >= 0 && i < bins) counts[i]++;
    }
    const w = mount.clientWidth || 700, h = 150, pad = 22;
    const max = Math.max(...counts) || 1;
    const NS = 'http://www.w3.org/2000/svg';
    const svg = document.createElementNS(NS, 'svg');
    svg.setAttribute('class', 'chart');
    svg.setAttribute('viewBox', `0 0 ${w} ${h}`);
    svg.setAttribute('role', 'img');
    svg.setAttribute('aria-label', `Distribution of simulated margins for ${homeName}`);
    const bw = (w - pad * 2) / bins;
    counts.forEach((c, i) => {
      const bh = (c / max) * (h - pad * 2);
      const r = document.createElementNS(NS, 'rect');
      r.setAttribute('x', pad + i * bw);
      r.setAttribute('y', h - pad - bh);
      r.setAttribute('width', Math.max(1, bw - 1));
      r.setAttribute('height', bh);
      const mid = lo + (i + 0.5) * (hi - lo) / bins;
      r.setAttribute('fill', mid >= 0 ? 'var(--good)' : 'var(--bad)');
      r.setAttribute('opacity', '0.85');
      const title = document.createElementNS(NS, 'title');
      title.textContent = `margin ${mid.toFixed(0)}: ${c} of ${margins.length}`;
      r.appendChild(title);
      svg.appendChild(r);
    });
    const zeroX = pad + ((0 - lo) / (hi - lo)) * (w - pad * 2);
    const line = document.createElementNS(NS, 'line');
    line.setAttribute('x1', zeroX); line.setAttribute('x2', zeroX);
    line.setAttribute('y1', pad / 2); line.setAttribute('y2', h - pad);
    line.setAttribute('stroke', 'var(--muted)');
    line.setAttribute('stroke-dasharray', '3 3');
    svg.appendChild(line);
    [[pad, lo], [w - pad, hi]].forEach(([x, v]) => {
      const t = document.createElementNS(NS, 'text');
      t.setAttribute('x', x); t.setAttribute('y', h - 6);
      t.setAttribute('fill', 'var(--muted)'); t.setAttribute('font-size', '11');
      t.setAttribute('text-anchor', x === pad ? 'start' : 'end');
      t.textContent = (v > 0 ? '+' : '') + v;
      svg.appendChild(t);
    });
    mount.appendChild(svg);
    mount.appendChild(el('p', 'hint',
      `How ${homeName}’s margin came out across every simulation. ` +
      'The dashed line is a tie — bars to the right are wins.'));
  }

  boot();
})();
