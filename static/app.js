// ── State ─────────────────────────────────────────────────────────────────
let PROJECTS = [];
let DATA = { fb: null, goog: null };
let RANGE = { from: null, to: null };

// ── Formatting ────────────────────────────────────────────────────────────
const fmtEur = n => n >= 1000 ? (n / 1000).toFixed(1) + 'k €' : Math.round(n) + ' €';
const fmtN   = n => n >= 1000 ? (n / 1000).toFixed(1) + 'k'   : String(Math.round(n));
const fmtDate = d => d.toISOString().slice(0, 10);

function delta(curr, prev, higherIsBetter) {
  if (!prev || prev === 0) return { cls: 'neu', text: 'Keine Vorperiode' };
  const pct = Math.round(((curr - prev) / prev) * 100);
  const up = pct >= 0;
  const cls = (higherIsBetter ? up : !up) ? 'up' : 'down';
  return { cls, text: (up ? '▲' : '▼') + ' ' + Math.abs(pct) + '% ggü. Vorperiode' };
}

// ── DOM helpers ───────────────────────────────────────────────────────────
const set = (id, v) => { const e = document.getElementById(id); if (e) e.textContent = v; };
function setD(id, text, cls, isCh) {
  const e = document.getElementById(id);
  if (!e) return;
  e.textContent = text;
  e.className = (isCh ? 'ch-kpi-d' : 'kpi-d') + ' ' + cls;
}

// ── Date range helpers ────────────────────────────────────────────────────
function daysBetween(a, b) {
  return Math.round((b - a) / 86400000);
}

function getPresetRange(preset) {
  const today = new Date(); today.setHours(0, 0, 0, 0);
  const yd = new Date(today); yd.setDate(yd.getDate() - 1);

  switch (preset) {
    case '7d': {
      const f = new Date(yd); f.setDate(f.getDate() - 6);
      return { from: f, to: yd };
    }
    case '28d': {
      const f = new Date(yd); f.setDate(f.getDate() - 27);
      return { from: f, to: yd };
    }
    case 'this_month':
      return { from: new Date(today.getFullYear(), today.getMonth(), 1), to: yd };
    case 'last_month': {
      const t = new Date(today.getFullYear(), today.getMonth(), 0);
      return { from: new Date(t.getFullYear(), t.getMonth(), 1), to: t };
    }
    case 'last_quarter': {
      const q = Math.floor(today.getMonth() / 3);
      const pq = q === 0 ? 3 : q - 1;
      const yr = q === 0 ? today.getFullYear() - 1 : today.getFullYear();
      return {
        from: new Date(yr, pq * 3, 1),
        to:   new Date(yr, pq * 3 + 3, 0),
      };
    }
    case 'this_year':
      return { from: new Date(today.getFullYear(), 0, 1), to: yd };
    default:
      return null;
  }
}

function prevPeriod(from, to) {
  const days = daysBetween(from, to) + 1;
  const pTo = new Date(from); pTo.setDate(pTo.getDate() - 1);
  const pFrom = new Date(pTo); pFrom.setDate(pFrom.getDate() - (days - 1));
  return { from: pFrom, to: pTo };
}

// ── Aggregation ───────────────────────────────────────────────────────────
const KEYS = ['spend', 'donors', 'rec', 'einzel', 'imp', 'clicks', 'lpvisits'];

function aggregate(rows, from, to) {
  const sum = Object.fromEntries(KEYS.map(k => [k, 0]));
  rows.forEach(row => {
    const d = new Date(row.date);
    if (d >= from && d <= to) KEYS.forEach(k => { sum[k] += row[k] || 0; });
  });
  sum.spend = Math.round(sum.spend * 100) / 100;
  return sum;
}

// ── KPI fill ─────────────────────────────────────────────────────────────
function fill(cur, prev, pre, isCh) {
  const cpd    = cur.donors   ? Math.round(cur.spend / cur.donors) : 0;
  const pCpd   = prev?.donors ? Math.round(prev.spend / prev.donors) : 0;
  const lpcvr  = cur.lpvisits   ? cur.donors / cur.lpvisits * 100 : 0;
  const pLpcvr = prev?.lpvisits ? prev.donors / prev.lpvisits * 100 : 0;
  const ctr    = cur.imp   ? cur.clicks / cur.imp * 100 : 0;
  const pCtr   = prev?.imp ? prev.clicks / prev.imp * 100 : 0;
  const c2d    = cur.clicks   ? cur.donors / cur.clicks * 100 : 0;
  const pC2d   = prev?.clicks ? prev.donors / prev.clicks * 100 : 0;

  const d = (v, pv, hib) => delta(v, pv, hib);

  set(pre + 'spend', fmtEur(cur.spend));
  setD(pre + 'spend-d', d(cur.spend, prev?.spend, true).text, d(cur.spend, prev?.spend, true).cls, isCh);
  set(pre + 'cpd', cpd + ' €');
  setD(pre + 'cpd-d', d(cpd, pCpd, false).text, d(cpd, pCpd, false).cls, isCh);
  set(pre + 'donors', fmtN(cur.donors));
  setD(pre + 'donors-d', d(cur.donors, prev?.donors, true).text, d(cur.donors, prev?.donors, true).cls, isCh);
  set(pre + 'lpcvr', lpcvr.toFixed(1) + '%');
  setD(pre + 'lpcvr-d', d(lpcvr, pLpcvr, true).text, d(lpcvr, pLpcvr, true).cls, isCh);
  set(pre + 'imp', fmtN(cur.imp));
  setD(pre + 'imp-d', d(cur.imp, prev?.imp, true).text, d(cur.imp, prev?.imp, true).cls, isCh);
  set(pre + 'clicks', fmtN(cur.clicks));
  setD(pre + 'clicks-d', d(cur.clicks, prev?.clicks, true).text, d(cur.clicks, prev?.clicks, true).cls, isCh);
  set(pre + 'ctr', ctr.toFixed(2) + '%');
  setD(pre + 'ctr-d', d(ctr, pCtr, true).text, d(ctr, pCtr, true).cls, isCh);
  set(pre + 'c2d', c2d.toFixed(2) + '%');
  setD(pre + 'c2d-d', d(c2d, pC2d, true).text, d(c2d, pC2d, true).cls, isCh);
  if (!isCh) {
    set(pre + 'einzel', fmtN(cur.einzel));
    setD(pre + 'einzel-d', d(cur.einzel, prev?.einzel, true).text, d(cur.einzel, prev?.einzel, true).cls, false);
    set(pre + 'rec', fmtN(cur.rec));
    setD(pre + 'rec-d', d(cur.rec, prev?.rec, true).text, d(cur.rec, prev?.rec, true).cls, false);
    set(pre + 'donors', fmtN(cur.donors));
  }
}

// ── Render ────────────────────────────────────────────────────────────────
function render() {
  const { fb, goog } = DATA;
  if (!fb || !goog || !RANGE.from) return;

  const { from, to } = RANGE;
  const { from: pf, to: pt } = prevPeriod(from, to);

  const fbCur  = aggregate(fb.rows,   from, to);
  const fbPrev = aggregate(fb.rows,   pf,   pt);
  const ggCur  = aggregate(goog.rows, from, to);
  const ggPrev = aggregate(goog.rows, pf,   pt);

  const totCur  = Object.fromEntries(KEYS.map(k => [k, fbCur[k]  + ggCur[k]]));
  const totPrev = Object.fromEntries(KEYS.map(k => [k, fbPrev[k] + ggPrev[k]]));
  totCur.spend  = Math.round(totCur.spend  * 100) / 100;
  totPrev.spend = Math.round(totPrev.spend * 100) / 100;

  fill(totCur, totPrev, 'g-',    false);
  fill(fbCur,  fbPrev,  'm-',    false);
  fill(ggCur,  ggPrev,  'gg-',   false);
  fill(fbCur,  fbPrev,  'cv-m-', true);
  fill(ggCur,  ggPrev,  'cv-g-', true);

  const project = PROJECTS.find(p => p.id === new URLSearchParams(location.search).get('project'));
  const dateStr = fmtDate(from) + ' – ' + fmtDate(to);
  set('d-foot-note', (project?.name || '') + ' · ' + dateStr);
}

// ── Date preset UI ────────────────────────────────────────────────────────
function setPreset(preset, btn) {
  document.querySelectorAll('.preset-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');

  const customEl = document.getElementById('custom-range');
  if (preset === 'custom') {
    customEl.style.display = 'flex';
    return;
  }
  customEl.style.display = 'none';

  const range = getPresetRange(preset);
  if (range) { RANGE = range; render(); }
}

function applyCustom() {
  const from = new Date(document.getElementById('d-from').value);
  const to   = new Date(document.getElementById('d-to').value);
  if (!isNaN(from) && !isNaN(to) && from <= to) { RANGE = { from, to }; render(); }
}

// ── Project switching ─────────────────────────────────────────────────────
async function loadProject(projectId) {
  history.pushState({}, '', '?project=' + projectId);
  set('d-foot-note', 'Lädt Daten...');
  try {
    const [fb, goog] = await Promise.all([
      fetch('data/' + projectId + '/facebook.json').then(r => { if (!r.ok) throw Error(r.status); return r.json(); }),
      fetch('data/' + projectId + '/google.json').then(r => { if (!r.ok) throw Error(r.status); return r.json(); }),
    ]);
    DATA = { fb, goog };
    render();
  } catch (e) {
    set('d-foot-note', 'Fehler: ' + e.message);
  }
}

function onProjectChange(id) { loadProject(id); }

// ── Tab / diag toggles ────────────────────────────────────────────────────
function switchTab(tab, btn) {
  ['gesamt', 'meta', 'google', 'vergleich'].forEach(t => {
    document.getElementById('view-' + t).style.display = t === tab ? 'block' : 'none';
  });
  document.querySelectorAll('.d-tab').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
}

function toggleDiag(id, el) {
  const sec = document.getElementById(id);
  const open = sec.style.display === 'block';
  sec.style.display = open ? 'none' : 'block';
  el.innerHTML = '<i class="ti ti-chevron-' + (open ? 'down' : 'up') + '" style="font-size:13px"></i> Diagnose-Metriken ' + (open ? 'einblenden' : 'ausblenden');
}

// ── Boot ──────────────────────────────────────────────────────────────────
async function init() {
  RANGE = getPresetRange('28d');

  const projects = await fetch('data/projects.json').then(r => r.json());
  PROJECTS = projects;

  const sel = document.getElementById('project-select');
  sel.innerHTML = '';
  projects.forEach(p => {
    const opt = document.createElement('option');
    opt.value = p.id; opt.textContent = p.name;
    sel.appendChild(opt);
  });

  const params = new URLSearchParams(location.search);
  const projectId = params.get('project') || projects[0].id;
  sel.value = projectId;

  await loadProject(projectId);
}

init();
