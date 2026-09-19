/* hoopsim browser interface. No dependencies, no build step. */
'use strict';

const S = {
  state: null,
  playersById: new Map(),
  lineup: [],
  currentTeam: null,
  playerRows: [],
  rapmRows: null,
  sort: {},
};

/* ---------------------------------------------------------------- utils */

const $ = (sel) => document.querySelector(sel);
const el = (tag, cls, text) => {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text !== undefined && text !== null) n.textContent = text;
  return n;
};

function toast(message, ms = 2600) {
  const t = $('#toast');
  t.textContent = message;
  t.classList.remove('hidden');
  clearTimeout(toast._timer);
  toast._timer = setTimeout(() => t.classList.add('hidden'), ms);
}

async function api(path, options) {
  const res = await fetch(path, options);
  let payload;
  try { payload = await res.json(); } catch { payload = { error: 'bad response' }; }
  if (!res.ok || payload.error) throw new Error(payload.error || `HTTP ${res.status}`);
  return payload;
}

const post = (path, body) => api(path, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
});

const num = (v, digits = 1) =>
  (v === null || v === undefined || Number.isNaN(v)) ? '' : Number(v).toFixed(digits);
const signed = (v, digits = 1) =>
  (v === null || v === undefined || Number.isNaN(v)) ? '' : (v >= 0 ? '+' : '') + Number(v).toFixed(digits);
const cls = (v) => (v > 0 ? 'pos-val' : v < 0 ? 'neg-val' : '');

/* Columns that read better as a percentage-style 3-decimal value. */
const RATE_COLS = new Set(['ts_pct', 'efg_pct', 'fg_pct', 'fg3_pct', 'ft_pct',
  'usage_rate', 'ast_rate', 'trb_rate', 'orb_rate', 'drb_rate', 'stl_rate',
  'blk_rate', 'tov_rate', 'fg3a_rate', 'ft_rate', 'win_pct', 'ws_per_48',
  'pythag_win_pct', 'off_efg_pct', 'off_tov_rate', 'off_orb_rate', 'off_ft_rate',
  'def_efg_pct', 'def_tov_rate', 'def_drb_rate', 'def_ft_rate', 'playoff_prob',
  'title_prob', 'playin_prob', 'conf_finals_prob', 'finals_prob', 'stop_pct']);
const SIGNED_COLS = new Set(['box_impact', 'net_rating', 'adj_net_rating', 'srs',
  'sos', 'luck', 'rapm', 'rapm_off', 'rapm_def', 'margin', 'on_off_net',
  'net_change', 'usage_effect', 'fit_bonus', 'impact', 'home_margin_per_100']);

function formatCell(key, value) {
  if (value === null || value === undefined) return '';
  if (typeof value === 'boolean') return value ? 'yes' : 'no';
  if (typeof value !== 'number') return String(value);
  if (RATE_COLS.has(key)) return value.toFixed(3);
  if (SIGNED_COLS.has(key)) return signed(value, 2);
  if (Number.isInteger(value)) return String(value);
  return value.toFixed(Math.abs(value) < 10 ? 2 : 1);
}

/* Renders a sortable table into `mount`. */
function renderTable(mount, rows, columns, opts = {}) {
  mount.innerHTML = '';
  if (!rows || !rows.length) {
    mount.appendChild(el('p', 'hint', 'No rows.'));
    return;
  }
  const key = opts.sortKey || mount.id;
  const sort = S.sort[key] || { col: opts.defaultSort || columns[0].k, dir: -1 };
  S.sort[key] = sort;

  const sorted = [...rows].sort((a, b) => {
    const x = a[sort.col], y = b[sort.col];
    if (x === y) return 0;
    if (x === null || x === undefined) return 1;
    if (y === null || y === undefined) return -1;
    return (x > y ? 1 : -1) * sort.dir;
  });

  const wrap = el('div', 'scroll');
  const table = el('table');
  const thead = el('thead');
  const hr = el('tr');
  columns.forEach((c) => {
    const th = el('th', c.k === sort.col ? 'sorted' : '', c.label);
    th.title = c.title || c.label;
    th.addEventListener('click', () => {
      if (sort.col === c.k) sort.dir *= -1; else { sort.col = c.k; sort.dir = -1; }
      renderTable(mount, rows, columns, opts);
    });
    hr.appendChild(th);
  });
  thead.appendChild(hr);
  table.appendChild(thead);

  const tbody = el('tbody');
  sorted.slice(0, opts.limit || 400).forEach((r) => {
    const tr = el('tr');
    columns.forEach((c) => {
      const td = el('td', typeof r[c.k] === 'number' ? 'num' : '');
      td.textContent = formatCell(c.k, r[c.k]);
      if (SIGNED_COLS.has(c.k) && typeof r[c.k] === 'number') td.classList.add(cls(r[c.k]));
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  });
  table.appendChild(tbody);
  wrap.appendChild(table);
  mount.appendChild(wrap);
}

/* Auto-derives columns from the first row when we do not have a hand list. */
function autoColumns(rows, drop = []) {
  const skip = new Set(['team_id', 'player_id', 'lineup', 'players', ...drop]);
  return Object.keys(rows[0])
    .filter((k) => !skip.has(k))
    .map((k) => ({ k, label: k.replace(/_/g, ' ') }));
}

/* ------------------------------------------------------------ bootstrap */

async function boot() {
  try {
    S.state = await api('/api/state');
  } catch (e) {
    $('#league-meta').textContent = 'failed to load: ' + e.message;
    return;
  }
  const st = S.state;
  st.players.forEach((p) => S.playersById.set(p.player_id, p));
  $('#league-meta').textContent =
    `${st.season} · ${st.source} · ${st.teams.length} teams · ${st.players.length} players` +
    (st.has_pbp ? ' · play-by-play' : ' · box score only');

  fillTeamSelects(st.teams);
  fillSelect($('#per-mode'), st.per_modes.map((m) => ({ value: m, label: m })), 'per_36');
  fillSelect($('#split-dimension'),
    st.verticals.map((v) => ({ value: v.key, label: `${v.label} (${v.level})` })), 'rest');

  wireTabs();
  wireLineups();
  wirePlayers();
  wireSplits();
  wireSimulate();

  S.currentTeam = st.teams[0].team_id;
  $('#lineup-team').value = S.currentTeam;
  renderRoster();
  loadPlayers();
  loadTeams();
  loadSplits();
}

function fillSelect(select, items, selected) {
  select.innerHTML = '';
  items.forEach((it) => {
    const o = el('option', null, it.label);
    o.value = it.value;
    select.appendChild(o);
  });
  if (selected !== undefined) select.value = selected;
}

function fillTeamSelects(teams) {
  const items = teams.map((t) => ({ value: t.team_id, label: `${t.team_abbrev} — ${t.team_name}` }));
  fillSelect($('#lineup-team'), items);
  fillSelect($('#sim-home'), items);
  fillSelect($('#sim-away'), items, teams[1] ? teams[1].team_id : teams[0].team_id);
  [['#player-team', 'all'], ['#split-team', 'league wide']].forEach(([sel, label]) => {
    fillSelect($(sel), [{ value: '', label }, ...items], '');
  });
}

function wireTabs() {
  document.querySelectorAll('.tab').forEach((btn) => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.tab').forEach((b) => b.classList.remove('active'));
      document.querySelectorAll('.panel').forEach((p) => p.classList.remove('active'));
      btn.classList.add('active');
      $('#tab-' + btn.dataset.tab).classList.add('active');
    });
  });
}

/* -------------------------------------------------------------- lineups */

function teamPlayers(teamId) {
  return S.state.players
    .filter((p) => p.team_id === teamId)
    .sort((a, b) => b.minutes - a.minutes);
}

function renderRoster() {
  const mount = $('#roster');
  mount.innerHTML = '';
  const roster = teamPlayers(S.currentTeam);
  if (!roster.length) {
    mount.appendChild(el('p', 'hint', 'No players with enough minutes on this team.'));
    return;
  }
  roster.forEach((p) => {
    const row = el('div', 'player-row' + (S.lineup.includes(p.player_id) ? ' selected' : ''));
    row.appendChild(el('span', 'nm', p.name));
    row.appendChild(el('span', 'pos', p.position));
    const imp = el('span', 'num ' + cls(p.impact), signed(p.impact, 1));
    imp.title = 'impact, points per 100 possessions vs an average player';
    row.appendChild(imp);
    const usg = el('span', 'num', (p.usage * 100).toFixed(1) + '%');
    usg.title = 'usage rate';
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
  renderRoster();
  evaluateLineup();
}

function renderSlots() {
  const mount = $('#lineup-slots');
  mount.innerHTML = '';
  for (let i = 0; i < 5; i++) {
    const pid = S.lineup[i];
    const slot = el('div', 'slot' + (pid ? ' filled' : ''));
    slot.appendChild(el('span', 'pos', pid ? S.playersById.get(pid).position : '·'));
    slot.appendChild(el('span', null, pid ? S.playersById.get(pid).name : 'empty'));
    if (pid) {
      const x = el('button', 'remove', '✕');
      x.addEventListener('click', (e) => { e.stopPropagation(); toggle(pid); });
      slot.appendChild(x);
    } else {
      slot.appendChild(el('span'));
    }
    mount.appendChild(slot);
  }
  $('#lineup-count').textContent = `${S.lineup.length} of 5`;
  const opts = S.lineup.map((p) => ({ value: p, label: S.playersById.get(p).name }));
  fillSelect($('#swap-out'), opts.length ? opts : [{ value: '', label: '—' }]);
  const bench = teamPlayers(S.currentTeam).filter((p) => !S.lineup.includes(p.player_id));
  fillSelect($('#swap-in'), bench.length
    ? bench.map((p) => ({ value: p.player_id, label: p.name }))
    : [{ value: '', label: '—' }]);
}

async function evaluateLineup() {
  const result = $('#lineup-result');
  const warn = $('#lineup-warning');
  if (S.lineup.length !== 5) {
    result.innerHTML = '';
    $('#breakdown').innerHTML = '';
    $('#usage-table').innerHTML = '';
    warn.classList.add('hidden');
    return;
  }
  result.innerHTML = '<div class="spinner">evaluating…</div>';
  let ev;
  try {
    ev = await post('/api/lineup/evaluate', { players: S.lineup });
  } catch (e) { result.innerHTML = ''; toast(e.message); return; }

  result.innerHTML = '';
  const head = el('div');
  const big = el('div', 'bignum ' + cls(ev.net_rating), signed(ev.net_rating, 2));
  head.appendChild(big);
  head.appendChild(el('div', 'hint', 'projected net rating, points per 100 possessions'));
  result.appendChild(head);

  const kv = el('div', 'kv');
  [['offensive rating', num(ev.off_rating, 1)],
   ['defensive rating', num(ev.def_rating, 1)]].forEach(([k, v]) => {
    kv.appendChild(el('div', 'k', k));
    kv.appendChild(el('div', 'v', v));
  });
  result.appendChild(kv);

  const positionsOk = ev.coverage_penalty < 4;
  warn.classList.toggle('hidden', positionsOk);
  if (!positionsOk) {
    warn.textContent = 'This five has a coverage gap — it is missing a skill nobody on the floor provides.';
  }

  renderBreakdown(ev);
  renderUsage(ev.usage_table);
}

function renderBreakdown(ev) {
  const mount = $('#breakdown');
  mount.innerHTML = '';
  const kv = el('div', 'kv');
  const add = (k, v, signedValue = true) => {
    kv.appendChild(el('div', 'k', k));
    const d = el('div', 'v ' + (signedValue ? cls(v) : ''), signedValue ? signed(v, 2) : num(v, 2));
    kv.appendChild(d);
  };
  add('additive offence', ev.additive_off);
  add('additive defence', ev.additive_def);
  add('usage redistribution', ev.usage_effect);
  add('fit bonus', ev.fit_bonus);
  add('coverage penalty', -ev.coverage_penalty);
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
    const zero = el('div', 'bar-zero');
    zero.style.left = '50%';
    track.appendChild(zero);
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
  const mount = $('#usage-table');
  if (!rows || !rows.length) { mount.innerHTML = ''; return; }
  const named = rows.map((r) => ({
    player: S.playersById.get(r.player_id) ? S.playersById.get(r.player_id).name : r.player_id,
    base_usage: r.base_usage,
    adjusted_usage: r.adjusted_usage,
    usage_change: r.usage_change,
    base_ts_pct: r.base_ts_pct,
    adjusted_ts_pct: r.adjusted_ts_pct,
    pts_per_100_effect: r.pts_per_100_effect,
  }));
  renderTable(mount, named, [
    { k: 'player', label: 'player' },
    { k: 'base_usage', label: 'usage', title: 'established usage rate' },
    { k: 'adjusted_usage', label: 'in this five' },
    { k: 'usage_change', label: 'change' },
    { k: 'base_ts_pct', label: 'TS%' },
    { k: 'adjusted_ts_pct', label: 'adj TS%' },
    { k: 'pts_per_100_effect', label: 'pts/100' },
  ], { sortKey: 'usage', defaultSort: 'adjusted_usage' });
}

function wireLineups() {
  $('#lineup-team').addEventListener('change', (e) => {
    S.currentTeam = e.target.value;
    S.lineup = [];
    $('#best-card').classList.add('hidden');
    renderRoster();
    evaluateLineup();
  });
  $('#load-starters').addEventListener('click', () => {
    S.lineup = teamPlayers(S.currentTeam).slice(0, 5).map((p) => p.player_id);
    renderRoster();
    evaluateLineup();
  });
  $('#clear-lineup').addEventListener('click', () => {
    S.lineup = [];
    renderRoster();
    evaluateLineup();
  });
  $('#do-swap').addEventListener('click', doSwap);
  $('#rank-replacements').addEventListener('click', rankReplacements);
  $('#find-best').addEventListener('click', findBest);
  $('#optimise-rotation').addEventListener('click', optimiseRotation);
}

async function doSwap() {
  if (S.lineup.length !== 5) { toast('Put five players on the floor first.'); return; }
  const out = $('#swap-out').value, inp = $('#swap-in').value;
  if (!out || !inp) { toast('Pick a player to come off and one to come on.'); return; }
  const mount = $('#swap-result');
  mount.innerHTML = '<div class="spinner">simulating the change…</div>';
  let res;
  try { res = await post('/api/lineup/swap', { players: S.lineup, out, in: inp }); }
  catch (e) { mount.innerHTML = ''; toast(e.message); return; }

  mount.innerHTML = '';
  const head = el('div');
  head.appendChild(el('div', 'bignum ' + cls(res.net_change), signed(res.net_change, 2)));
  head.appendChild(el('div', 'hint',
    `net rating change — out ${res.out_name}, in ${res.in_name} ` +
    `(${signed(res.before.net_rating, 2)} → ${signed(res.after.net_rating, 2)})`));
  mount.appendChild(head);

  const shifts = res.usage_shifts
    .filter((r) => r.player_id !== res.out_player && r.player_id !== res.in_player)
    .map((r) => ({
      player: S.playersById.get(r.player_id) ? S.playersById.get(r.player_id).name : r.player_id,
      usage_shift: r.usage_shift,
      ts_shift: r.ts_shift,
      pts_per_100_shift: r.pts_per_100_shift,
    }));
  if (shifts.length) {
    mount.appendChild(el('h2', null, 'Who absorbs the possessions'));
    mount.appendChild(el('p', 'hint',
      'A naive per-36 extrapolation says these four are unchanged. They are not: ' +
      'the departing player’s shots have to go somewhere, and they come at a cost.'));
    const t = el('div');
    mount.appendChild(t);
    renderTable(t, shifts, [
      { k: 'player', label: 'player' },
      { k: 'usage_shift', label: 'usage change' },
      { k: 'ts_shift', label: 'TS% change' },
      { k: 'pts_per_100_shift', label: 'pts/100' },
    ], { sortKey: 'shifts', defaultSort: 'usage_shift' });
  }
  const apply = el('button', 'ghost', 'Apply this change to the lineup');
  apply.addEventListener('click', () => {
    S.lineup = S.lineup.map((p) => (p === res.out_player ? res.in_player : p));
    renderRoster();
    evaluateLineup();
    mount.innerHTML = '';
  });
  mount.appendChild(el('div', null, ' '));
  mount.appendChild(apply);
}

async function rankReplacements() {
  if (S.lineup.length !== 5) { toast('Put five players on the floor first.'); return; }
  const out = $('#swap-out').value;
  const mount = $('#swap-result');
  mount.innerHTML = '<div class="spinner">ranking candidates…</div>';
  const candidates = teamPlayers(S.currentTeam).map((p) => p.player_id);
  let res;
  try {
    res = await post('/api/lineup/best-replacement',
      { players: S.lineup, out, candidates, top: 15 });
  } catch (e) { mount.innerHTML = ''; toast(e.message); return; }
  mount.innerHTML = '';
  mount.appendChild(el('h2', null,
    `Every replacement for ${S.playersById.get(out).name}, ranked`));
  const t = el('div');
  mount.appendChild(t);
  renderTable(t, res.rows, [
    { k: 'in_name', label: 'player' },
    { k: 'position', label: 'pos' },
    { k: 'net_change', label: 'net change' },
    { k: 'net_rating', label: 'net rating' },
    { k: 'off_rating', label: 'offence' },
    { k: 'def_rating', label: 'defence' },
    { k: 'usage_effect', label: 'usage effect' },
  ], { sortKey: 'replacements', defaultSort: 'net_change' });
}

async function findBest() {
  const card = $('#best-card'), mount = $('#best-result');
  card.classList.remove('hidden');
  $('#best-title').textContent = 'Best five-man units';
  mount.innerHTML = '<div class="spinner">searching every combination…</div>';
  let res;
  try { res = await api(`/api/best-lineups?team=${encodeURIComponent(S.currentTeam)}&pool=10&top=12`); }
  catch (e) { mount.innerHTML = ''; toast(e.message); return; }
  mount.innerHTML = '';
  res.rows.forEach((r) => {
    const row = el('div', 'player-row');
    row.appendChild(el('span', 'nm', r.names.join(', ')));
    row.appendChild(el('span', 'pos', ''));
    row.appendChild(el('span', 'num ' + cls(r.net_rating), signed(r.net_rating, 2)));
    row.appendChild(el('span', 'num', num(r.off_rating, 1) + ' / ' + num(r.def_rating, 1)));
    row.title = 'click to load this five';
    row.addEventListener('click', () => {
      S.lineup = [...r.players];
      renderRoster();
      evaluateLineup();
      window.scrollTo({ top: 0, behavior: 'smooth' });
    });
    mount.appendChild(row);
  });
}

async function optimiseRotation() {
  const card = $('#best-card'), mount = $('#best-result');
  card.classList.remove('hidden');
  $('#best-title').textContent = 'Optimised rotation';
  mount.innerHTML = '<div class="spinner">optimising minutes…</div>';
  let res;
  try { res = await api(`/api/rotation?team=${encodeURIComponent(S.currentTeam)}&pool=10`); }
  catch (e) { mount.innerHTML = ''; toast(e.message); return; }
  mount.innerHTML = '';
  mount.appendChild(el('p', 'hint',
    `projected net rating ${signed(res.net_rating, 2)} — offence ${num(res.off_rating, 1)}, ` +
    `defence ${num(res.def_rating, 1)}. Minutes must total 240.`));
  const t = el('div');
  mount.appendChild(t);
  renderTable(t, res.minutes, [
    { k: 'name', label: 'player' },
    { k: 'minutes', label: 'minutes' },
    { k: 'impact', label: 'impact' },
  ], { sortKey: 'rotation', defaultSort: 'minutes' });

  mount.appendChild(el('h2', null, 'Unit plan'));
  const segs = res.segments.map((s) => ({
    start: s.start_minute, lineup: s.names.join(', '),
    net_rating: s.net_rating, usage_effect: s.usage_effect,
  }));
  const t2 = el('div');
  mount.appendChild(t2);
  renderTable(t2, segs, [
    { k: 'start', label: 'from' },
    { k: 'lineup', label: 'on the floor' },
    { k: 'net_rating', label: 'net' },
  ], { sortKey: 'segments', defaultSort: 'start', limit: 20 });
  S.sort.segments = { col: 'start', dir: 1 };
}

/* -------------------------------------------------------------- players */

const PLAYER_COLUMNS = [
  { k: 'player_name', label: 'player' },
  { k: 'position', label: 'pos' },
  { k: 'games', label: 'G' },
  { k: 'min', label: 'MIN' },
  { k: 'pts', label: 'PTS' },
  { k: 'trb', label: 'REB' },
  { k: 'ast', label: 'AST' },
  { k: 'ts_pct', label: 'TS%', title: 'true shooting' },
  { k: 'usage_rate', label: 'USG%' },
  { k: 'per', label: 'PER' },
  { k: 'ws', label: 'WS' },
  { k: 'ws_per_48', label: 'WS/48' },
  { k: 'box_impact', label: 'impact', title: 'points per 100 vs average, from the box score' },
];

async function loadPlayers() {
  const mount = $('#players-table');
  mount.innerHTML = '<div class="spinner">loading…</div>';
  const per = $('#per-mode').value;
  const min = $('#min-minutes').value || 0;
  const team = $('#player-team').value;
  const help = { totals: 'Season totals.', per_game: 'Divided by games played.',
    per_24: 'Per 24 minutes — half a game.', per_36: 'Per 36 minutes — a starter’s workload.',
    per_40: 'Per 40 minutes — NCAA and FIBA regulation.', per_48: 'Per 48 minutes — a full game.',
    per_75: 'Per 75 possessions — pace-independent, close to per-game scale.',
    per_100: 'Per 100 possessions — pace-independent, the Oliver standard.' };
  $('#per-mode-help').textContent = help[per] || '';
  try {
    const res = await api(`/api/players?per=${per}&min_minutes=${min}&team=${encodeURIComponent(team)}`);
    S.playerRows = res.rows;
    S.rapmRows = null;
    filterPlayers();
  } catch (e) { mount.innerHTML = ''; toast(e.message); }
}

function filterPlayers() {
  const q = ($('#player-search').value || '').toLowerCase();
  const source = S.rapmRows || S.playerRows;
  const rows = q ? source.filter((r) => String(r.player_name || '').toLowerCase().includes(q)) : source;
  const columns = S.rapmRows
    ? [{ k: 'player_name', label: 'player' }, { k: 'position', label: 'pos' },
       { k: 'possessions', label: 'poss' }, { k: 'rapm_off', label: 'O-RAPM' },
       { k: 'rapm_def', label: 'D-RAPM' }, { k: 'rapm', label: 'RAPM' }]
    : PLAYER_COLUMNS;
  renderTable($('#players-table'), rows, columns,
    { sortKey: 'players', defaultSort: S.rapmRows ? 'rapm' : 'box_impact', limit: 400 });
}

function wirePlayers() {
  ['#per-mode', '#min-minutes', '#player-team'].forEach((sel) =>
    $(sel).addEventListener('change', loadPlayers));
  $('#player-search').addEventListener('input', filterPlayers);
  $('#show-rapm').addEventListener('click', async () => {
    if (S.rapmRows) { S.rapmRows = null; $('#show-rapm').textContent = 'Show RAPM'; filterPlayers(); return; }
    try {
      const res = await api('/api/rapm?min_possessions=300');
      S.rapmRows = res.rows;
      $('#show-rapm').textContent = 'Show box metrics';
      toast(`home court advantage recovered from the data: ${signed(res.home_advantage, 2)} per 100`);
      filterPlayers();
    } catch (e) { toast(e.message); }
  });
}

/* ---------------------------------------------------------------- teams */

async function loadTeams() {
  try {
    const res = await api('/api/teams');
    renderTable($('#teams-table'), res.rows, [
      { k: 'team_abbrev', label: 'team' },
      { k: 'conference', label: 'conf' },
      { k: 'w', label: 'W' }, { k: 'l', label: 'L' },
      { k: 'pace', label: 'pace' },
      { k: 'off_rating', label: 'ORtg' },
      { k: 'def_rating', label: 'DRtg' },
      { k: 'adj_off_rating', label: 'adj ORtg', title: 'adjusted for opponents faced' },
      { k: 'adj_def_rating', label: 'adj DRtg' },
      { k: 'adj_net_rating', label: 'adj net' },
      { k: 'srs', label: 'SRS' }, { k: 'sos', label: 'SOS' },
      { k: 'pythag_win_pct', label: 'pythag' },
      { k: 'luck', label: 'luck', title: 'wins above what the scoring says' },
    ], { sortKey: 'teams', defaultSort: 'adj_net_rating' });
    renderTable($('#factors-table'), res.rows, [
      { k: 'team_abbrev', label: 'team' },
      { k: 'off_efg_pct', label: 'eFG%' },
      { k: 'off_tov_rate', label: 'TOV%' },
      { k: 'off_orb_rate', label: 'ORB%' },
      { k: 'off_ft_rate', label: 'FTr' },
      { k: 'def_efg_pct', label: 'opp eFG%' },
      { k: 'def_tov_rate', label: 'opp TOV%' },
      { k: 'def_drb_rate', label: 'DRB%' },
      { k: 'def_ft_rate', label: 'opp FTr' },
    ], { sortKey: 'factors', defaultSort: 'off_efg_pct' });
  } catch (e) { toast(e.message); }
}

/* --------------------------------------------------------------- splits */

async function loadSplits() {
  const mount = $('#splits-table');
  mount.innerHTML = '<div class="spinner">loading…</div>';
  const dim = $('#split-dimension').value;
  const team = $('#split-team').value;
  const meta = S.state.verticals.find((v) => v.key === dim);
  $('#split-help').textContent = meta ? meta.description : '';
  $('#split-team').disabled = meta && meta.level === 'possession';
  try {
    const res = await api(`/api/splits?dimension=${dim}&team=${encodeURIComponent(team)}`);
    if (!res.rows.length) { mount.innerHTML = '<p class="hint">No rows.</p>'; return; }
    renderTable(mount, res.rows, autoColumns(res.rows),
      { sortKey: 'splits', defaultSort: 'bucket' });
    S.sort.splits = { col: 'bucket', dir: 1 };
  } catch (e) { mount.innerHTML = `<p class="hint">${e.message}</p>`; }
}

function wireSplits() {
  $('#split-dimension').addEventListener('change', loadSplits);
  $('#split-team').addEventListener('change', loadSplits);
}

/* ------------------------------------------------------------- simulate */

function wireSimulate() {
  $('#run-game').addEventListener('click', runGame);
  $('#run-season').addEventListener('click', runSeason);
}

async function runGame() {
  const mount = $('#game-result');
  const home = $('#sim-home').value, away = $('#sim-away').value;
  if (home === away) { toast('Pick two different teams.'); return; }
  mount.innerHTML = '<div class="spinner">simulating…</div>';
  let res;
  try { res = await post('/api/game', { home, away, sims: 20000 }); }
  catch (e) { mount.innerHTML = ''; toast(e.message); return; }

  const name = (id) => {
    const t = S.state.teams.find((x) => x.team_id === id);
    return t ? t.team_name : id;
  };
  const s = res.summary;
  mount.innerHTML = '';
  mount.appendChild(el('div', 'bignum', (s.home_win_prob * 100).toFixed(1) + '%'));
  mount.appendChild(el('div', 'hint', `${name(home)} win probability (closed-form model: ` +
    `${(res.closed_form_win_prob * 100).toFixed(1)}%)`));
  const kv = el('div', 'kv');
  [['projected score', `${num(s.mean_home_score, 1)} — ${num(s.mean_away_score, 1)}`],
   ['margin', `${signed(s.mean_margin, 2)} (sd ${num(s.margin_sd, 2)})`],
   ['implied spread', signed(s.spread, 1)],
   ['projected total', num(s.median_total, 1)]].forEach(([k, v]) => {
    kv.appendChild(el('div', 'k', k));
    kv.appendChild(el('div', 'v', v));
  });
  mount.appendChild(kv);
  drawHistogram(res.margin_histogram, name(home));
}

function drawHistogram(hist, homeName) {
  const mount = $('#margin-chart');
  mount.innerHTML = '';
  if (!hist) return;
  const w = mount.clientWidth || 700, h = 150, pad = 22;
  const max = Math.max(...hist.counts) || 1;
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('class', 'chart');
  svg.setAttribute('viewBox', `0 0 ${w} ${h}`);
  svg.setAttribute('role', 'img');
  svg.setAttribute('aria-label', `Distribution of simulated margins for ${homeName}`);
  const bw = (w - pad * 2) / hist.counts.length;
  hist.counts.forEach((c, i) => {
    const bh = (c / max) * (h - pad * 2);
    const r = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
    r.setAttribute('x', pad + i * bw);
    r.setAttribute('y', h - pad - bh);
    r.setAttribute('width', Math.max(1, bw - 1));
    r.setAttribute('height', bh);
    const mid = (hist.edges[i] + hist.edges[i + 1]) / 2;
    r.setAttribute('fill', mid >= 0 ? 'var(--good)' : 'var(--bad)');
    r.setAttribute('opacity', '0.85');
    const title = document.createElementNS('http://www.w3.org/2000/svg', 'title');
    title.textContent = `margin ${mid.toFixed(0)}: ${c} of 20,000`;
    r.appendChild(title);
    svg.appendChild(r);
  });
  const zeroX = pad + ((0 - hist.edges[0]) / (hist.edges[hist.edges.length - 1] - hist.edges[0])) * (w - pad * 2);
  const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
  line.setAttribute('x1', zeroX); line.setAttribute('x2', zeroX);
  line.setAttribute('y1', pad / 2); line.setAttribute('y2', h - pad);
  line.setAttribute('stroke', 'var(--muted)');
  line.setAttribute('stroke-dasharray', '3 3');
  svg.appendChild(line);
  [[pad, hist.edges[0]], [w - pad, hist.edges[hist.edges.length - 1]]].forEach(([x, v]) => {
    const t = document.createElementNS('http://www.w3.org/2000/svg', 'text');
    t.setAttribute('x', x); t.setAttribute('y', h - 6);
    t.setAttribute('fill', 'var(--muted)'); t.setAttribute('font-size', '11');
    t.setAttribute('text-anchor', x === pad ? 'start' : 'end');
    t.textContent = (v > 0 ? '+' : '') + v.toFixed(0);
    svg.appendChild(t);
  });
  mount.appendChild(svg);
  mount.appendChild(el('p', 'hint', `Distribution of simulated margins for ${homeName}. ` +
    'The dashed line is a tie.'));
}

async function runSeason() {
  const mount = $('#season-result');
  mount.innerHTML = '<div class="spinner">simulating seasons… this takes a few seconds</div>';
  let res;
  try { res = await post('/api/season', { sims: 1500 }); }
  catch (e) { mount.innerHTML = ''; toast(e.message); return; }
  mount.innerHTML = '';
  const rows = (res.playoffs || []).map((p) => {
    const w = res.wins.find((x) => x.team_id === p.team_id) || {};
    return {
      team: p.team_abbrev, conference: p.conference,
      net_rating: w.net_rating, mean_wins: w.mean_wins,
      p05_wins: w.p05_wins, p95_wins: w.p95_wins,
      playoff_prob: p.playoff_prob, conf_finals_prob: p.conf_finals_prob,
      title_prob: p.title_prob,
    };
  });
  renderTable(mount, rows, [
    { k: 'team', label: 'team' }, { k: 'conference', label: 'conf' },
    { k: 'net_rating', label: 'net' },
    { k: 'mean_wins', label: 'wins' },
    { k: 'p05_wins', label: '5th pct' }, { k: 'p95_wins', label: '95th pct' },
    { k: 'playoff_prob', label: 'playoffs' },
    { k: 'conf_finals_prob', label: 'conf finals' },
    { k: 'title_prob', label: 'title' },
  ], { sortKey: 'season', defaultSort: 'title_prob', limit: 40 });
}

boot();
