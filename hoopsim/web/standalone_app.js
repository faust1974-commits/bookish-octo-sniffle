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

  const S = { lineup: [], team: null, sort: {}, rapmMode: false,
              moves: {}, undo: [], rosterA: null, rosterB: null };

  /* ------------------------------------------------- roster overrides */

  /* A roster feed is never quite right: trades land, signings lag, and some
   * entries are simply wrong. So the feed is a starting point, not the
   * truth, and anything the person changes here wins over it.
   *
   * Overrides live in this browser only. They survive closing the file and
   * never leave the machine. Storage can be unavailable (private windows,
   * blocked site data), so every read and write is guarded and the page
   * works fine without it -- it just forgets between sessions. */
  const MOVES_KEY = 'hoopsim.rosters.v1';

  function loadMoves() {
    try {
      const raw = localStorage.getItem(MOVES_KEY);
      const parsed = raw ? JSON.parse(raw) : null;
      if (!parsed || typeof parsed !== 'object') return {};
      // Drop ids that are not in this build, so an older saved set cannot
      // resurrect players the data no longer has.
      const clean = {};
      for (const [pid, team] of Object.entries(parsed)) {
        if (D.playersById[pid] && (team === '' || teamsById[team])) clean[pid] = team;
      }
      return clean;
    } catch (e) { return {}; }
  }

  function saveMoves() {
    try { localStorage.setItem(MOVES_KEY, JSON.stringify(S.moves)); } catch (e) { /* fine */ }
  }

  /** The team a player is on right now, override included. '' means no team. */
  function effTeam(p) {
    return Object.prototype.hasOwnProperty.call(S.moves, p.player_id)
      ? S.moves[p.player_id] : (p.team_id || '');
  }

  function movePlayer(pid, teamId) {
    const p = D.playersById[pid];
    if (!p || effTeam(p) === teamId) return false;
    S.undo.push({ pid: pid, prev: effTeam(p) });
    // Back to where the feed had him is not an override, it is a deletion --
    // otherwise "reset" and "moved back by hand" would look different.
    if ((p.team_id || '') === teamId) delete S.moves[pid];
    else S.moves[pid] = teamId;
    saveMoves();
    afterRosterChange();
    return true;
  }

  /** Anyone no longer on the selected team cannot stay on its floor. */
  function afterRosterChange() {
    const before = S.lineup.length;
    S.lineup = S.lineup.filter(pid => effTeam(D.playersById[pid]) === S.team);
    renderRosterEditor();
    renderRoster();
    evaluate();
    loadPlayers();
    loadTeams();          // team projections are built from the rosters
    loadSeason();         // and so are the standings
    loadTeam();
    loadRankings();
    loadCompare();
    loadUpcoming();
    updateEditFlag();
  }

  function editCount() { return Object.keys(S.moves).length; }

  function updateEditFlag() {
    const n = editCount();
    const label = n ? `${n} roster change${n === 1 ? '' : 's'} of your own` : '';
    $('#edit-count').textContent = label;
    const flag = $('#roster-edited');
    if (flag) {
      flag.textContent = n ? `· ${n} edited` : '';
    }
    $('#undo-move').disabled = !S.undo.length;
    $('#reset-rosters').disabled = !n;
  }

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

  /* Odds read as odds, not as decimals nobody converts in their head. */
  const PCT_COLS = new Set(['playoff_odds', 'play_in_odds', 'top_seed_odds', 'confidence',
    'title_odds', 'pbp_share']);
  const ONE_DP = new Set(['wins', 'losses', 'avg_seed', 'sos']);

  function fmt(key, v) {
    if (v === null || v === undefined) return '';
    if (typeof v === 'boolean') return v ? 'yes' : 'no';
    if (typeof v !== 'number') return String(v);
    if (PCT_COLS.has(key)) return (v * 100).toFixed(0) + '%';
    if (ONE_DP.has(key)) return v.toFixed(1);
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
    const sort = S.sort[key] || {
      col: opts.defaultSort || columns[0].k,
      dir: opts.defaultDir === undefined ? -1 : opts.defaultDir,
    };
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

    S.moves = loadMoves();
    setupRosterEditor();

    S.team = D.teams[0].team_id;
    $('#lineup-team').value = S.team;
    renderRoster();
    fillSelect($('#team-pick'), D.teams.map(t => ({
      value: t.team_id, label: `${t.team_abbrev} — ${t.team_name}`,
    })), D.teams[0].team_id);
    $('#team-pick').addEventListener('change', (e) => {
      S.teamPage = e.target.value; loadTeam();
    });

    loadPlayers();
    loadTeams();
    loadSeason();
    loadTeam();
    loadRankings();
    fillCompareOptions();
    loadCompare();
    fillSelect($('#sched-team'), [{ value: '', label: 'every team' }].concat(
      D.teams.map(t => ({ value: t.team_abbrev, label: t.team_name }))), '');
    if (D.schedule && D.schedule.length && D.schedule[0].length > 2) {
      $('#sched-from').value = D.schedule[0][2];
    }
    ['#sched-team', '#sched-from'].forEach(s =>
      $(s).addEventListener('change', loadUpcoming));
    loadUpcoming();
    loadSplits();

    $('#cmp-mode').addEventListener('change', () => {
      fillCompareOptions(); loadCompare();
    });
    ['#cmp-a', '#cmp-b'].forEach(s =>
      $(s).addEventListener('change', loadCompare));
  }

  /* --------------------------------------------------- roster editor */

  /** Team options for the per-row "move to" menu, free agency included. */
  function moveOptions() {
    return [{ value: '', label: '—' }].concat(
      D.teams.map(t => ({ value: t.team_id, label: t.team_abbrev })));
  }

  function dragRow(p) {
    const moved = Object.prototype.hasOwnProperty.call(S.moves, p.player_id);
    const row = el('div', 'drag-row' + (moved ? ' moved' : ''));
    row.draggable = true;
    row.dataset.pid = p.player_id;
    row.title = moved ? 'You moved this player. Undo or reset puts him back.' : '';

    row.appendChild(el('span', 'handle', '⠿'));

    const nm = el('span', 'nm', p.name);
    if (p.unrated) nm.appendChild(el('span', 'vintage unrated', 'no record'));
    else if (p.data_season && p.data_season !== D.meta.season) {
      nm.appendChild(el('span', 'vintage', p.data_season));
    }
    row.appendChild(nm);

    const per = el('span', 'num', p.per === null || p.per === undefined
      ? '—' : p.per.toFixed(1));
    per.title = 'PER: player efficiency rating. League average is 15.';
    row.appendChild(per);

    // Dragging is nice; a menu is what works on a phone, with one hand, or
    // when the target team is not one of the two on screen.
    const sel = document.createElement('select');
    fillSelect(sel, moveOptions(), effTeam(p));
    sel.title = 'move to another team';
    sel.addEventListener('change', (e) => {
      if (!movePlayer(p.player_id, e.target.value)) return;
      const to = e.target.value ? teamsById[e.target.value].team_abbrev : 'free agents';
      toast(`${p.name} → ${to}`);
    });
    sel.addEventListener('click', (e) => e.stopPropagation());
    row.appendChild(sel);

    row.addEventListener('dragstart', (e) => {
      e.dataTransfer.setData('text/plain', p.player_id);
      e.dataTransfer.effectAllowed = 'move';
      row.classList.add('dragging');
    });
    row.addEventListener('dragend', () => row.classList.remove('dragging'));
    return row;
  }

  function fillList(mount, players, emptyText) {
    mount.innerHTML = '';
    if (!players.length) {
      mount.appendChild(el('p', 'empty', emptyText));
      return;
    }
    players.forEach(p => mount.appendChild(dragRow(p)));
  }

  function makeDropTarget(mount, teamIdFn) {
    mount.addEventListener('dragover', (e) => {
      e.preventDefault();
      e.dataTransfer.dropEffect = 'move';
      mount.classList.add('over');
    });
    mount.addEventListener('dragleave', () => mount.classList.remove('over'));
    mount.addEventListener('drop', (e) => {
      e.preventDefault();
      mount.classList.remove('over');
      const pid = e.dataTransfer.getData('text/plain');
      const target = teamIdFn();
      const p = D.playersById[pid];
      if (!p) return;
      if (!movePlayer(pid, target)) {
        toast(`${p.name} is already there.`);
        return;
      }
      toast(`${p.name} → ${target ? teamsById[target].team_abbrev : 'free agents'}`);
    });
  }

  function renderRosterEditor() {
    $('#roster-a-title').textContent = S.rosterA
      ? teamsById[S.rosterA].team_name : '—';
    $('#roster-b-title').textContent = S.rosterB
      ? teamsById[S.rosterB].team_name : '—';
    fillList($('#roster-a-list'), teamPlayers(S.rosterA), 'Nobody here. Drag someone in.');
    fillList($('#roster-b-list'), teamPlayers(S.rosterB), 'Nobody here. Drag someone in.');

    const q = ($('#fa-search').value || '').trim().toLowerCase();
    let pool = D.players.filter(p => effTeam(p) === '');
    // The search box looks across the whole league, so you can pull a player
    // over without first knowing which team the feed thinks he is on.
    if (q) {
      pool = D.players.filter(p => p.name.toLowerCase().includes(q)
        && effTeam(p) !== S.rosterA && effTeam(p) !== S.rosterB);
    }
    pool.sort((a, b) => (b.min || 0) - (a.min || 0));
    fillList($('#fa-list'), pool.slice(0, 120),
      q ? 'No player by that name.' : 'Everyone with a record is on a roster.');
    updateEditFlag();
  }

  function setupRosterEditor() {
    const teamItems = D.teams.map(t => ({
      value: t.team_id, label: `${t.team_abbrev} — ${t.team_name}`,
    }));
    S.rosterA = D.teams[0].team_id;
    S.rosterB = (D.teams[1] || D.teams[0]).team_id;
    fillSelect($('#roster-a'), teamItems, S.rosterA);
    fillSelect($('#roster-b'), teamItems, S.rosterB);

    $('#roster-a').addEventListener('change', (e) => {
      S.rosterA = e.target.value; renderRosterEditor();
    });
    $('#roster-b').addEventListener('change', (e) => {
      S.rosterB = e.target.value; renderRosterEditor();
    });
    $('#fa-search').addEventListener('input', renderRosterEditor);

    makeDropTarget($('#roster-a-list'), () => S.rosterA);
    makeDropTarget($('#roster-b-list'), () => S.rosterB);
    makeDropTarget($('#fa-list'), () => '');

    $('#undo-move').addEventListener('click', () => {
      const last = S.undo.pop();
      if (!last) return;
      const p = D.playersById[last.pid];
      if ((p.team_id || '') === last.prev) delete S.moves[last.pid];
      else S.moves[last.pid] = last.prev;
      saveMoves();
      afterRosterChange();
      toast(`${p.name} back to ${last.prev ? teamsById[last.prev].team_abbrev : 'free agents'}`);
    });

    $('#reset-rosters').addEventListener('click', () => {
      if (!editCount()) return;
      const n = editCount();
      S.moves = {}; S.undo = [];
      saveMoves();
      afterRosterChange();
      toast(`${n} change${n === 1 ? '' : 's'} undone. Back to the official rosters.`);
    });

    renderRosterEditor();
  }

  /* --------------------------------------------------------- lineups */

  function teamPlayers(teamId) {
    return D.players.filter(p => effTeam(p) === teamId)
      .sort((a, b) => (a.unrated ? 1 : 0) - (b.unrated ? 1 : 0)
        || (b.min || 0) - (a.min || 0));
  }

  /* A rating is a weighted average of what the possessions say and what the
   * box score says. Which one is doing the work matters more than the number
   * itself, so say it plainly wherever the number appears. */
  function impactTitle(p) {
    if (p.unrated) {
      return 'He has never played an NBA possession. Shown at replacement ' +
        'level because that is the least-wrong placeholder, not a projection.';
    }
    const share = Math.round((p.pbp_share || 0) * 100);
    const se = (p.impact_se === null || p.impact_se === undefined)
      ? '' : ` Give or take ${p.impact_se.toFixed(1)}.`;
    let basis;
    if (share >= 45) {
      basis = `Mostly measured: ${share}% of this comes from what actually ` +
        'happened on the floor with him out there.';
    } else if (share >= 25) {
      basis = `Half and half: ${share}% from possessions played, the rest ` +
        'from his box score.';
    } else {
      basis = `Thin evidence: only ${share}% of this is measured impact. ` +
        'The rest is his box score, and box scores flatter efficient big men.';
    }
    return `Impact: points per 100 possessions versus an average player.${se} ` +
      basis;
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
      const per = el('span', 'num', p.per === null || p.per === undefined
        ? '—' : p.per.toFixed(1));
      per.title = 'PER: player efficiency rating. League average is 15.';
      row.appendChild(per);
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

  /* Everyone on this team with enough of a record to rate. */
  function rosterOf(teamId) {
    return D.players.filter(p => effTeam(p) === teamId && p.min && p.games);
  }

  /* What this team projects to, from the players on it today -- as opposed
   * to what last season's team did. After a trade those are different
   * questions, and showing only the second one is how a roster with Giannis
   * on it can read as a mediocre defence. */
  function projectedTeams() {
    return D.teams.map((t) => {
      const s = E.teamStrength(D, rosterOf(t.team_id));
      const lg = D.meta.league_off_rating;
      return Object.assign({}, t, {
        // Put both halves on the familiar scale: points scored and points
        // allowed per 100, so they sit beside last season's columns without
        // the reader having to flip a sign in their head.
        proj_off: lg + s.off,
        proj_def: lg - s.def,
        proj_net: s.net,
      });
    });
  }

  /* ------------------------------------------------- upcoming games */

  /** Predicted result for one scheduled game. */
  function predictGame(homeId, awayId, strengths) {
    const h = strengths[homeId] || 0, a = strengths[awayId] || 0;
    const p = E.winProbability(K, h, a);
    const margin = E.projectedMargin(K, h, a);
    // Split the projected margin around the league's own scoring level, so
    // the two numbers add up to a believable final score rather than just a
    // difference.
    const total = 2 * K.pace * (D.meta.league_off_rating / 100);
    return {
      home_win_prob: p,
      margin: margin,
      home_score: total / 2 + margin / 2,
      away_score: total / 2 - margin / 2,
    };
  }

  function loadUpcoming() {
    const mount = $('#upcoming');
    mount.innerHTML = '';
    if (!D.schedule || !D.schedule.length || D.schedule[0].length < 3) {
      mount.appendChild(el('p', 'empty', 'No dated schedule in this build.'));
      return;
    }
    const strengths = strengthMap();
    const idByAbbrev = {};
    for (const t of D.teams) idByAbbrev[t.team_abbrev] = t.team_id;

    const from = $('#sched-from').value || D.schedule[0][2];
    const only = $('#sched-team').value;
    const rows = [];
    for (const g of D.schedule) {
      if (g[2] < from) continue;
      if (only && g[0] !== only && g[1] !== only) continue;
      const h = idByAbbrev[g[0]], a = idByAbbrev[g[1]];
      if (!h || !a) continue;
      const pr = predictGame(h, a, strengths);
      const homeFav = pr.home_win_prob >= 0.5;
      rows.push({
        date: g[2],
        game: `${g[1]} at ${g[0]}`,
        pick: homeFav ? g[0] : g[1],
        confidence: homeFav ? pr.home_win_prob : 1 - pr.home_win_prob,
        // Written in the same order as the fixture, so "LAL at LAC 113–112"
        // reads left to right without anyone having to work out which
        // number belongs to which side.
        score: `${g[1]} ${Math.round(pr.away_score)} – ` +
               `${Math.round(pr.home_score)} ${g[0]}`,
      });
      if (rows.length >= 60) break;
    }
    if (!rows.length) {
      mount.appendChild(el('p', 'empty', 'No games from that date on.'));
      return;
    }
    table(mount, rows, [
      { k: 'date', label: 'date' },
      { k: 'game', label: 'game' },
      { k: 'pick', label: 'pick' },
      { k: 'confidence', label: 'confidence',
        title: 'how often this side wins, simulating the matchup' },
      { k: 'score', label: 'projected score' },
    ], { sortKey: 'upcoming', defaultSort: 'date', defaultDir: 1 });
  }

  /* --------------------------------------------------------- compare */

  /** One comparison row: label, both values, and which side is better. */
  function cmpRow(label, a, b, opts) {
    const o = opts || {};
    const fmtv = o.fmt || ((v) => (v === null || v === undefined) ? '—'
      : (o.signed ? signed(v, o.dp === undefined ? 1 : o.dp)
                  : Number(v).toFixed(o.dp === undefined ? 1 : o.dp)));
    let winner = 0;
    if (typeof a === 'number' && typeof b === 'number' && a !== b) {
      const aBetter = o.lowerIsBetter ? a < b : a > b;
      winner = aBetter ? -1 : 1;
    }
    return { label: label, a: a, b: b, fa: fmtv(a), fb: fmtv(b),
             winner: winner, title: o.title };
  }

  function renderCmp(mount, nameA, nameB, rows) {
    mount.innerHTML = '';
    const grid = el('div', 'cmp');
    const ha = el('div', 'head'); ha.textContent = nameA;
    ha.style.textAlign = 'right';
    grid.appendChild(ha);
    grid.appendChild(el('div', 'head', ''));
    grid.appendChild(el('div', 'head', nameB));
    for (const r of rows) {
      const a = el('div', 'side a' + (r.winner === -1 ? ' win' : ''), r.fa);
      const lbl = el('div', 'lbl', r.label);
      const b = el('div', 'side b' + (r.winner === 1 ? ' win' : ''), r.fb);
      if (r.title) { lbl.title = r.title; }
      grid.appendChild(a); grid.appendChild(lbl); grid.appendChild(b);
    }
    mount.appendChild(grid);
  }

  function compareTeams(idA, idB) {
    const strengths = strengthMap();
    const season = (D.schedule && D.schedule.length)
      ? E.projectSeason(D, strengths, 800, 31) : null;
    const proj = projectedTeams();
    const pa = proj.find(t => t.team_id === idA), pb = proj.find(t => t.team_id === idB);
    const sa = season && season.find(r => r.team_id === idA);
    const sb = season && season.find(r => r.team_id === idB);
    const rows = [];
    if (sa && sb) {
      rows.push(cmpRow('projected wins', sa.wins, sb.wins, { dp: 0 }));
      rows.push(cmpRow('playoff odds', sa.playoff_odds, sb.playoff_odds,
        { fmt: v => (v * 100).toFixed(0) + '%' }));
      rows.push(cmpRow('top seed odds', sa.top_seed_odds, sb.top_seed_odds,
        { fmt: v => (v * 100).toFixed(0) + '%' }));
    }
    rows.push(cmpRow('net rating', pa.proj_net, pb.proj_net, { signed: true }));
    rows.push(cmpRow('offence', pa.proj_off, pb.proj_off,
      { title: 'projected points scored per 100' }));
    rows.push(cmpRow('defence', pa.proj_def, pb.proj_def,
      { lowerIsBetter: true, title: 'projected points allowed per 100 — lower is better' }));

    const profA = teamProfile(idA), profB = teamProfile(idB);
    if (profA && profB) {
      for (const k of Object.keys(SKILL_LABELS)) {
        rows.push(cmpRow(SKILL_LABELS[k], profA[k], profB[k], { signed: true, dp: 2 }));
      }
    }

    // The verdict, in words.
    const A = teamsById[idA], B = teamsById[idB];
    const gap = pa.proj_net - pb.proj_net;
    const better = gap >= 0 ? A : B, worse = gap >= 0 ? B : A;
    const bits = [];
    if (Math.abs(gap) < 1) {
      bits.push(`${A.team_name} and ${B.team_name} project as essentially the same team — ` +
        `${Math.abs(gap).toFixed(1)} points per 100 apart, which is inside the noise.`);
    } else {
      bits.push(`${better.team_name} projects ${Math.abs(gap).toFixed(1)} points per 100 ` +
        `better than ${worse.team_name}.`);
    }
    if (sa && sb) {
      bits.push(`That is about ${Math.abs(sa.wins - sb.wins).toFixed(0)} wins across a season.`);
    }
    if (profA && profB) {
      let biggest = null, mag = 0;
      for (const k of Object.keys(SKILL_LABELS)) {
        const d = profA[k] - profB[k];
        if (Math.abs(d) > mag) { mag = Math.abs(d); biggest = { k: k, d: d }; }
      }
      if (biggest && mag > 0.2) {
        const side = biggest.d > 0 ? A : B;
        bits.push(`The clearest difference between them is ${SKILL_LABELS[biggest.k]}, ` +
          `where ${side.team_abbrev} is well ahead.`);
      }
    }
    // Head to head, if they play.
    const hp = E.winProbability(K, strengths[idA] || 0, strengths[idB] || 0);
    bits.push(`On a neutral floor ${A.team_abbrev} would beat ${B.team_abbrev} about ` +
      `${(E.winProbability(K, strengths[idA] || 0, strengths[idB] || 0, { neutral: true }) * 100).toFixed(0)}` +
      `% of the time; at home, ${(hp * 100).toFixed(0)}%.`);

    return { nameA: A.team_name, nameB: B.team_name, rows: rows, verdict: bits.join(' ') };
  }

  function comparePlayers(idA, idB) {
    const a = D.playersById[idA], b = D.playersById[idB];
    const per36 = (p, k) => (p.min > 0 ? (p[k] || 0) * 36 / p.min : 0);
    const rows = [
      cmpRow('win shares', a.ws, b.ws),
      cmpRow('PER', a.per, b.per, { title: 'league average is 15' }),
      cmpRow('win shares per 48', a.ws_per_48, b.ws_per_48, { dp: 3 }),
      cmpRow('minutes', a.min, b.min, { dp: 0 }),
      cmpRow('points per 36', per36(a, 'pts'), per36(b, 'pts')),
      cmpRow('rebounds per 36', per36(a, 'trb'), per36(b, 'trb')),
      cmpRow('assists per 36', per36(a, 'ast'), per36(b, 'ast')),
      cmpRow('steals per 36', per36(a, 'stl'), per36(b, 'stl')),
      cmpRow('blocks per 36', per36(a, 'blk'), per36(b, 'blk')),
      cmpRow('true shooting', a.ts_pct, b.ts_pct,
        { fmt: v => (v * 100).toFixed(1) + '%' }),
      cmpRow('usage', a.usage_rate, b.usage_rate,
        { fmt: v => (v * 100).toFixed(1) + '%' }),
      cmpRow('turnover rate', a.tov_rate, b.tov_rate,
        { lowerIsBetter: true, fmt: v => (v * 100).toFixed(1) + '%' }),
    ];

    const bits = [];
    const gap = (a.ws || 0) - (b.ws || 0);
    const better = gap >= 0 ? a : b, worse = gap >= 0 ? b : a;
    if (Math.abs(gap) < 1.0) {
      bits.push(`${a.name} and ${b.name} were worth about the same last season — ` +
        `${(a.ws || 0).toFixed(1)} win shares against ${(b.ws || 0).toFixed(1)}.`);
    } else {
      bits.push(`${better.name} was worth ${Math.abs(gap).toFixed(1)} more wins than ` +
        `${worse.name} last season — ${(better.ws || 0).toFixed(1)} win shares ` +
        `against ${(worse.ws || 0).toFixed(1)}.`);
    }
    const dper = (a.per || 0) - (b.per || 0);
    if (Math.abs(dper) > 2) {
      const eff = dper > 0 ? a : b;
      bits.push(`${eff.name} was also the more efficient of the two, ` +
        `${Math.max(a.per || 0, b.per || 0).toFixed(1)} PER against ` +
        `${Math.min(a.per || 0, b.per || 0).toFixed(1)}.`);
    }
    const am = a.min || 0, bm = b.min || 0;
    if (am > 0 && bm > 0 && Math.abs(am - bm) / Math.max(am, bm) > 0.3) {
      const more = am > bm ? a : b;
      bits.push(`${more.name} played far more — ${Math.max(am, bm).toFixed(0)} minutes ` +
        `against ${Math.min(am, bm).toFixed(0)} — so his rating rests on more evidence ` +
        `and he contributed more in total.`);
    }
    return { nameA: a.name, nameB: b.name, rows: rows, verdict: bits.join(' ') };
  }

  function loadCompare() {
    const mode = $('#cmp-mode').value;
    const a = $('#cmp-a').value, b = $('#cmp-b').value;
    if (!a || !b) return;
    const out = mode === 'teams' ? compareTeams(a, b) : comparePlayers(a, b);
    const v = $('#cmp-verdict');
    v.innerHTML = '';
    const box = el('div', 'intro');
    box.appendChild(el('p', null, out.verdict));
    v.appendChild(box);
    renderCmp($('#cmp-table'), out.nameA, out.nameB, out.rows);
  }

  function fillCompareOptions() {
    const mode = $('#cmp-mode').value;
    let items;
    if (mode === 'teams') {
      items = D.teams.map(t => ({ value: t.team_id, label: t.team_name }));
    } else {
      items = D.players.filter(p => p.min && !p.unrated)
        .sort((x, y) => (y.min || 0) - (x.min || 0))
        .slice(0, 300)
        .map(p => ({ value: p.player_id, label: p.name }))
        .sort((x, y) => x.label.localeCompare(y.label));
    }
    fillSelect($('#cmp-a'), items, items[0] && items[0].value);
    fillSelect($('#cmp-b'), items, items[1] ? items[1].value : items[0].value);
  }

  /* -------------------------------------------------------- rankings */

  function rankList(mount, rows, valueFn, noteFn) {
    mount.innerHTML = '';
    rows.forEach((r, i) => {
      const row = el('div', 'player-row');
      row.appendChild(el('span', 'pos', String(i + 1)));
      row.appendChild(el('span', 'nm', r.label));
      const v = el('span', 'num ' + (r.signed ? cls(r.value) : ''), valueFn(r));
      if (r.thin) v.classList.add('thin');
      if (noteFn) v.title = noteFn(r);
      row.appendChild(v);
      mount.appendChild(row);
    });
  }

  function loadRankings() {
    const strengths = strengthMap();
    const projected = projectedTeams();
    const hasSchedule = D.schedule && D.schedule.length;
    const season = hasSchedule ? E.projectSeason(D, strengths, 1200, 17) : null;

    // The lede: the two or three things someone actually wants told to them.
    const lede = $('#rank-lede');
    lede.innerHTML = '';
    const box = el('div', 'intro');
    const byNet = projected.slice().sort((a, b) => b.proj_net - a.proj_net);
    // Ranked on win shares: points produced and points prevented, converted
    // into wins, from what a player actually did on the floor. It is a
    // forty-year-old public method with a known formula, not a regression
    // that assigns credit among five men who are always out there together.
    const bestPlayers = D.players
      .filter(p => !p.unrated && p.min && p.ws !== null && p.ws !== undefined)
      .sort((a, b) => b.ws - a.ws);
    if (season) {
      const fav = season.slice().sort((a, b) => b.top_seed_odds - a.top_seed_odds)[0];
      const east = season.filter(r => r.conference === 'East')
        .sort((a, b) => b.wins - a.wins)[0];
      const west = season.filter(r => r.conference === 'West')
        .sort((a, b) => b.wins - a.wins)[0];
      box.appendChild(el('p', null,
        `${west.team_name} project to lead the West at ` +
        `${west.wins.toFixed(0)}-${west.losses.toFixed(0)}, and ` +
        `${east.team_name} the East at ${east.wins.toFixed(0)}-${east.losses.toFixed(0)}. ` +
        `${fav.team_abbrev} is the likeliest number one seed overall.`));
    }
    if (bestPlayers.length) {
      const b = bestPlayers[0];
      box.appendChild(el('p', null,
        `${b.name} leads the league at ${b.ws.toFixed(1)} win shares — the wins ` +
        `his scoring, rebounding and defence were worth across ` +
        `${b.min.toFixed(0)} minutes. A ${b.per.toFixed(1)} player efficiency ` +
        `rating against a league average of 15.`));
    }
    lede.appendChild(box);

    if (season) {
      rankList($('#rank-title'), season.slice()
        .sort((a, b) => b.top_seed_odds - a.top_seed_odds).slice(0, 8)
        .map(r => ({ label: `${r.team_name}`, value: r.top_seed_odds, row: r })),
        r => (r.value * 100).toFixed(0) + '%',
        r => `Projected ${r.row.wins.toFixed(0)}-${r.row.losses.toFixed(0)}, ` +
             `${(r.row.playoff_odds * 100).toFixed(0)}% to make the top six.`);
    } else {
      rankList($('#rank-title'), byNet.slice(0, 8)
        .map(r => ({ label: r.team_name, value: r.proj_net, signed: true })),
        r => signed(r.value, 1));
    }

    rankList($('#rank-players'), bestPlayers.slice(0, 12).map(p => ({
      label: p.name, value: p.ws, p: p,
    })), r => r.value.toFixed(1) + ' WS',
       r => `${r.p.per.toFixed(1)} PER, ${(r.p.ts_pct * 100).toFixed(1)}% true ` +
            `shooting, ${r.p.min.toFixed(0)} minutes. Win shares: the wins his ` +
            `production was worth.`);

    rankList($('#rank-off'), projected.slice()
      .sort((a, b) => b.proj_off - a.proj_off).slice(0, 8)
      .map(t => ({ label: t.team_name, value: t.proj_off })),
      r => r.value.toFixed(1),
      () => 'projected points scored per 100 possessions');

    rankList($('#rank-def'), projected.slice()
      .sort((a, b) => a.proj_def - b.proj_def).slice(0, 8)
      .map(t => ({ label: t.team_name, value: t.proj_def })),
      r => r.value.toFixed(1),
      () => 'projected points allowed per 100 possessions — lower is better');
  }

  /* ------------------------------------------------------ one team */

  const SKILL_LABELS = {
    spacing: 'shooting and spacing',
    rim_pressure: 'getting to the rim',
    playmaking: 'playmaking',
    rebounding: 'rebounding',
    rim_protection: 'rim protection',
  };

  /** Minutes-weighted skill profile for a roster, versus a league average. */
  function teamProfile(teamId) {
    const roster = rosterOf(teamId);
    if (!roster.length) return null;
    const mpg = roster.map(p => (p.games > 0 ? p.min / p.games : 0));
    const mins = E.projectMinutes(K, mpg);
    const total = mins.reduce((a, b) => a + b, 0) || 1;
    const out = {};
    for (const k of Object.keys(SKILL_LABELS)) {
      let v = 0;
      for (let i = 0; i < roster.length; i++) v += mins[i] * (roster[i][k] || 0);
      out[k] = v / total;
    }
    return out;
  }

  /** Roster sorted by projected minutes, with those minutes attached. */
  function rotation(teamId) {
    const roster = rosterOf(teamId);
    const mpg = roster.map(p => (p.games > 0 ? p.min / p.games : 0));
    const mins = E.projectMinutes(K, mpg);
    return roster.map((p, i) => Object.assign({}, p, { proj_min: mins[i] }))
      .filter(p => p.proj_min > 0.5)
      .sort((a, b) => b.proj_min - a.proj_min);
  }

  /* Say it in words. A table of decimals is not an answer to "are they any
   * good"; this turns the same numbers into the sentence a person would. */
  function describeTeam(row, profile) {
    const bits = [];
    const w = row.wins.toFixed(0);
    let tier;
    if (row.wins >= 58) tier = 'a genuine contender';
    else if (row.wins >= 50) tier = 'a solid playoff team';
    else if (row.wins >= 43) tier = 'in the play-in mix';
    else if (row.wins >= 33) tier = 'a fringe team';
    else tier = 'a rebuilding team';
    bits.push(`Projected ${w}-${row.losses.toFixed(0)} — ${tier}, with a ` +
      `${(row.playoff_odds * 100).toFixed(0)}% chance of finishing top six.`);

    if (profile) {
      const ranked = Object.keys(SKILL_LABELS)
        .map(k => ({ k: k, v: profile[k] }))
        .sort((a, b) => b.v - a.v);
      const best = ranked[0], worst = ranked[ranked.length - 1];
      if (best.v > 0.15) {
        bits.push(`Their strength is ${SKILL_LABELS[best.k]}.`);
      }
      if (worst.v < -0.15) {
        bits.push(`The clear weakness is ${SKILL_LABELS[worst.k]}` +
          (worst.v < -0.6 ? ', badly.' : '.'));
      }
    }

    const sos = row.sos || 0;
    if (Math.abs(sos) > 0.4) {
      bits.push(sos > 0
        ? 'They also draw one of the harder schedules in the league.'
        : 'They get an easier road than most.');
    }
    return bits.join(' ');
  }

  function loadTeam() {
    const teamId = S.teamPage || D.teams[0].team_id;
    S.teamPage = teamId;
    const t = teamsById[teamId];
    const strengths = strengthMap();
    const rows = E.projectSeason(D, strengths, 800, 99);
    const sos = E.scheduleStrength(D, strengths);
    const row = rows.find(r => r.team_id === teamId);
    if (row) row.sos = sos[teamId] || 0;
    const profile = teamProfile(teamId);

    const head = $('#team-headline');
    head.innerHTML = '';
    const card = el('div', 'card');
    card.appendChild(el('div', 'bignum',
      row ? `${row.wins.toFixed(0)}-${row.losses.toFixed(0)}` : '—'));
    card.appendChild(el('p', 'hint', row ? describeTeam(row, profile)
      : 'No schedule, so no projected record.'));
    if (row) {
      const kv = el('div', 'kv');
      const add = (k, v) => {
        kv.appendChild(el('span', 'k', k));
        kv.appendChild(el('span', 'v', v));
      };
      add('net rating', signed(row.net, 1));
      add('playoff odds', (row.playoff_odds * 100).toFixed(0) + '%');
      add('play-in odds', (row.play_in_odds * 100).toFixed(0) + '%');
      add('top seed odds', (row.top_seed_odds * 100).toFixed(0) + '%');
      add('likely range', `${row.wins_low.toFixed(0)}–${row.wins_high.toFixed(0)} wins`);
      card.appendChild(kv);
    }
    head.appendChild(card);

    // Depth chart, grouped the way a coach would read it.
    const depth = $('#team-depth');
    depth.innerHTML = '';
    const rot = rotation(teamId);
    if (!rot.length) {
      depth.appendChild(el('p', 'empty', 'Nobody on this roster has a record to project from.'));
    } else {
      for (const pos of K.positions) {
        const group = rot.filter(p => p.position === pos);
        if (!group.length) continue;
        const h = el('div', 'bar-row');
        h.appendChild(el('span', 'k', pos));
        const list = el('div');
        for (const p of group) {
          const line = el('div', 'player-row');
          line.appendChild(el('span', 'nm', p.name));
          line.appendChild(el('span', 'num', p.proj_min.toFixed(1) + ' min'));
          const per = el('span', 'num', p.per === null || p.per === undefined
            ? '—' : p.per.toFixed(1) + ' PER');
          per.title = 'Player efficiency rating. League average is 15.';
          line.appendChild(per);
          list.appendChild(line);
        }
        h.appendChild(list);
        h.appendChild(el('span'));
        depth.appendChild(h);
      }
    }

    // Skill profile as bars, so the shape is visible at a glance.
    const prof = $('#team-profile');
    prof.innerHTML = '';
    if (profile) {
      const bars = el('div', 'bars');
      for (const k of Object.keys(SKILL_LABELS)) {
        const v = profile[k];
        const r = el('div', 'bar-row');
        r.appendChild(el('span', null, SKILL_LABELS[k]));
        const track = el('div', 'bar-track');
        const fill = el('div', 'bar-fill');
        const mag = Math.min(1, Math.abs(v) / 1.2);
        fill.style.background = v >= 0 ? 'var(--good)' : 'var(--bad)';
        fill.style.width = (mag * 50) + '%';
        fill.style.left = v >= 0 ? '50%' : (50 - mag * 50) + '%';
        track.appendChild(fill);
        const zero = el('div', 'bar-zero'); zero.style.left = '50%';
        track.appendChild(zero);
        r.appendChild(track);
        r.appendChild(el('span', 'num', signed(v, 2)));
        bars.appendChild(r);
      }
      prof.appendChild(bars);
      prof.appendChild(el('p', 'hint',
        'Each bar is how this rotation compares with an average one, ' +
        'weighted by the minutes each player is projected to play.'));
    }

    // Best legal five from the top of the rotation.
    const bestMount = $('#team-best');
    bestMount.innerHTML = '';
    const pool = rot.filter(p => !p.unrated).slice(0, 9).map(p => p.player_id);
    if (pool.length < 5) {
      bestMount.appendChild(el('p', 'empty', 'Not enough rated players to search.'));
    } else {
      let best;
      try { best = E.bestLineups(D, pool, 5, true); } catch (e) { best = []; }
      if (!best.length) { try { best = E.bestLineups(D, pool, 5, false); } catch (e) {} }
      table(bestMount, best.map(b => ({
        lineup: b.names.join(', '),
        net_rating: b.net_rating,
        off_rating: b.off_rating,
        def_rating: b.def_rating,
      })), [
        { k: 'lineup', label: 'five on the floor' },
        { k: 'net_rating', label: 'net' },
        { k: 'off_rating', label: 'offence' },
        { k: 'def_rating', label: 'defence' },
      ], { sortKey: 'best', defaultSort: 'net_rating' });
    }
  }

  /* ---------------------------------------------------------- season */

  /** Net rating per team, from whoever is on the roster right now. */
  function strengthMap() {
    const out = {};
    for (const t of D.teams) out[t.team_id] = E.teamStrength(D, rosterOf(t.team_id)).net;
    return out;
  }

  function seasonColumns() {
    return [
      { k: 'team_abbrev', label: 'team' },
      { k: 'wins', label: 'W' },
      { k: 'losses', label: 'L' },
      { k: 'range', label: 'range', title: 'where the season plausibly lands, 8 times out of 10' },
      { k: 'net', label: 'net', title: 'points per 100 better than the opponent' },
      { k: 'sos', label: 'schedule', title: 'average opponent net rating — positive means a harder road' },
      { k: 'playoff_odds', label: 'playoff %', title: 'finishes top six' },
      { k: 'play_in_odds', label: 'play-in %', title: 'finishes seventh through tenth' },
      { k: 'top_seed_odds', label: 'no.1 seed %' },
    ];
  }

  function loadSeason() {
    const mount = $('#season-summary');
    if (!D.schedule || !D.schedule.length) {
      mount.innerHTML = '';
      mount.appendChild(el('p', 'empty',
        'No schedule published for this season yet, so records cannot be projected.'));
      return;
    }
    const strengths = strengthMap();
    const rows = E.projectSeason(D, strengths, 2000, 4242);
    const sos = E.scheduleStrength(D, strengths);
    rows.forEach(r => {
      r.sos = sos[r.team_id] || 0;
      r.range = `${r.wins_low.toFixed(0)}–${r.wins_high.toFixed(0)}`;
    });

    const byWins = rows.slice().sort((a, b) => b.wins - a.wins);
    const best = byWins[0];
    const favourite = rows.slice().sort((a, b) => b.top_seed_odds - a.top_seed_odds)[0];
    mount.innerHTML = '';
    const note = el('div', 'intro');
    note.appendChild(el('p', null,
      `${best.team_name} project best at ${best.wins.toFixed(0)}-${best.losses.toFixed(0)}. ` +
      `${favourite.team_abbrev} is likeliest to take a one seed, at ` +
      `${(favourite.top_seed_odds * 100).toFixed(0)}%. ` +
      `The range column is where a season plausibly lands 8 times out of 10 — ` +
      `projections a year out are wrong by about ` +
      `${(D.constants.team_strength_sd || 0).toFixed(1)} points per 100 on average, ` +
      `and that is built in rather than hidden.`));
    mount.appendChild(note);

    for (const [conf, sel] of [['East', '#east-table'], ['West', '#west-table']]) {
      const side = rows.filter(r => r.conference === conf)
        .sort((a, b) => b.wins - a.wins);
      table($(sel), side, seasonColumns(),
        { sortKey: 'season' + conf, defaultSort: 'wins' });
    }
  }

  function loadTeams() {
    table($('#teams-table'), projectedTeams(), [
      { k: 'team_abbrev', label: 'team' },
      { k: 'conference', label: 'conf' },
      { k: 'proj_off', label: 'proj offence',
        title: 'projected points scored per 100, from the players on this roster now' },
      { k: 'proj_def', label: 'proj defence',
        title: 'projected points allowed per 100 — lower is better' },
      { k: 'proj_net', label: 'proj net',
        title: 'projected points per 100 better than the opponent' },
    ], { sortKey: 'proj', defaultSort: 'proj_net' });

    table($('#last-season-table'), D.teams, [
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
      const hr = E.teamStrength(D, rosterOf(home)).net;
      const ar = E.teamStrength(D, rosterOf(away)).net;
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
