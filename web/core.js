// Shared state, API client, icons, formatting, overlays (modals, context menus, toasts) and project actions.

const P = {
  search: '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
  star: '<path d="M12 3l2.7 5.6 6.1.9-4.4 4.3 1 6.1L12 17l-5.4 2.9 1-6.1L3.2 9.5l6.1-.9z"/>',
  pin: '<path d="M12 17v5M9 3h6l-1 6 3 3v2H7v-2l3-3z"/>',
  trash: '<path d="M3 6h18M8 6V4h8v2M6 6l1 14h10l1-14M10 11v5M14 11v5"/>',
  folder: '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
  grid: '<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',
  list: '<path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/>',
  object: '<path d="M12 2l9 5v10l-9 5-9-5V7z"/><path d="M3 7l9 5 9-5M12 12v10"/>',
  scene: '<path d="M3 20l6-10 4 6 3-4 5 8z"/><circle cx="17" cy="6" r="2"/>',
  animation: '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M7 4v16M17 4v16M3 9h4M3 15h4M17 9h4M17 15h4"/>',
  sparkles: '<path d="M12 3l1.8 4.7 4.7 1.8-4.7 1.8L12 16l-1.8-4.7-4.7-1.8 4.7-1.8z"/><path d="M19 15l.8 2.2L22 18l-2.2.8L19 21l-.8-2.2L16 18l2.2-.8z"/>',
  shader: '<path d="M4 17c3-6 5-6 8 0s5 6 8 0"/><path d="M4 7c3 6 5 6 8 0s5-6 8 0"/>',
  texture: '<rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="9" cy="9" r="2"/><path d="m21 15-5-5L5 21"/>',
  font: '<path d="M4 7V4h16v3M9 20h6M12 4v16"/>',
  database: '<ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v14c0 1.7 3.6 3 8 3s8-1.3 8-3V5M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3"/>',
  activity: '<path d="M3 12h4l3 8 4-16 3 8h4"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  archive: '<rect x="3" y="4" width="18" height="4" rx="1"/><path d="M5 8v11h14V8M10 12h4"/>',
  inbox: '<path d="M22 12h-6l-2 3h-4l-2-3H2"/><path d="M5.5 5h13L22 12v6a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2v-6z"/>',
  more: '<circle cx="5" cy="12" r="1.2"/><circle cx="12" cy="12" r="1.2"/><circle cx="19" cy="12" r="1.2"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  check: '<path d="M5 12l5 5L20 7"/>',
  x: '<path d="M6 6l12 12M18 6 6 18"/>',
  copy: '<rect x="8" y="8" width="13" height="13" rx="2"/><path d="M16 8V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h3"/>',
  download: '<path d="M12 3v12M7 10l5 5 5-5M5 21h14"/>',
  upload: '<path d="M12 21V9M7 14l5-5 5 5M5 3h14"/>',
  edit: '<path d="M4 20h4L19 9l-4-4L4 16z"/>',
  tag: '<path d="M3 12V3h9l9 9-9 9z"/><circle cx="7.5" cy="7.5" r="1.5"/>',
  lock: '<rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/>',
  unlock: '<rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 7.5-2"/>',
  move: '<path d="M5 9l-3 3 3 3M9 5l3-3 3 3M15 19l-3 3-3-3M19 9l3 3-3 3M2 12h20M12 2v20"/>',
  eye: '<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
  refresh: '<path d="M21 12a9 9 0 1 1-3-6.7L21 8M21 3v5h-5"/>',
  layers: '<path d="M12 2l10 5-10 5L2 7z"/><path d="M2 17l10 5 10-5M2 12l10 5 10-5"/>',
  history: '<circle cx="6" cy="6" r="2"/><circle cx="6" cy="18" r="2"/><circle cx="18" cy="8" r="2"/><path d="M6 8v8M18 10c0 4-6 3-10 6"/>',
  link: '<path d="M10 14a5 5 0 0 0 7 0l3-3a5 5 0 0 0-7-7l-1 1M14 10a5 5 0 0 0-7 0l-3 3a5 5 0 0 0 7 7l1-1"/>',
  play: '<path d="M7 4v16l13-8z"/>',
  pause: '<path d="M7 4h3v16H7zM14 4h3v16h-3z"/>',
  camera: '<path d="M3 8a2 2 0 0 1 2-2h2l2-3h6l2 3h2a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><circle cx="12" cy="13" r="4"/>',
  maximize: '<path d="M8 3H3v5M16 3h5v5M8 21H3v-5M16 21h5v-5"/>',
  orbit: '<ellipse cx="12" cy="12" rx="10" ry="4"/><circle cx="12" cy="12" r="3"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
  moon: '<path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/>',
  command: '<path d="M9 6a3 3 0 1 0-3 3h12a3 3 0 1 0-3-3v12a3 3 0 1 0 3-3H6a3 3 0 1 0 3 3z"/>',
  sidebar: '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M9 4v16"/>',
  hash: '<path d="M4 9h16M4 15h16M10 3 8 21M16 3l-2 18"/>',
  compare: '<rect x="3" y="4" width="7" height="16" rx="1.5"/><rect x="14" y="4" width="7" height="16" rx="1.5"/>',
  shield: '<path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z"/><path d="M9 12l2 2 4-4"/>',
  file: '<path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/><path d="M14 3v6h6"/>',
  wand: '<path d="M15 4V2M15 10V8M11 6h2M17 6h2M3 21l12-12"/>',
  bolt: '<path d="M13 2 4 14h7l-1 8 9-12h-7z"/>',
  particles: '<circle cx="5" cy="6" r="1.5"/><circle cx="12" cy="4" r="1"/><circle cx="18" cy="8" r="1.5"/><circle cx="8" cy="13" r="1"/><circle cx="15" cy="15" r="2"/><circle cx="6" cy="19" r="1.2"/>',
  material: '<circle cx="12" cy="12" r="9"/><path d="M3.5 9.5c5 3 12 3 17 0"/>',
  manifest: '<path d="M8 3H6a2 2 0 0 0-2 2v4l-2 3 2 3v4a2 2 0 0 0 2 2h2M16 3h2a2 2 0 0 1 2 2v4l2 3-2 3v4a2 2 0 0 1-2 2h-2"/>',
  keyboard: '<rect x="2" y="6" width="20" height="12" rx="2"/><path d="M6 10h.01M10 10h.01M14 10h.01M18 10h.01M7 14h10"/>',
  palette: '<circle cx="12" cy="12" r="9"/><circle cx="8" cy="10" r="1.2"/><circle cx="12" cy="7.5" r="1.2"/><circle cx="16" cy="10" r="1.2"/><path d="M12 21a3 3 0 0 1 0-6h3"/>',
  external: '<path d="M14 3h7v7M21 3l-9 9M19 14v5a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2h5"/>',
  back: '<path d="M19 12H5M12 19l-7-7 7-7"/>',
  graph: '<circle cx="5" cy="12" r="2.5"/><circle cx="19" cy="5" r="2.5"/><circle cx="19" cy="19" r="2.5"/><path d="M7.3 11l9.4-5M7.3 13l9.4 5"/>',
  note: '<path d="M4 4h16v12l-4 4H4z"/><path d="M16 20v-4h4M8 9h8M8 13h5"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 16v-5M12 8h.01"/>',
  settings: '<circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M4.2 4.2l2.1 2.1M17.7 17.7l2.1 2.1M2 12h3M19 12h3M4.2 19.8l2.1-2.1M17.7 6.3l2.1-2.1"/>',
  preview: '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="M3 15l5-4 4 3 3-2 6 4"/>',
  turtle: '<path d="M4 14c0-4 3.6-7 8-7s8 3 8 7z"/><path d="M20 12h2M2 15l2-1M6 14l-1 3M18 14l1 3M9 7.5 12 14l3-6.5"/>',
  palm: '<path d="M12 22c0-6 1-10 0-14"/><path d="M12 8c-3-3-7-3-9-1 3 0 6 1 9 1zM12 8c3-3 7-3 9-1-3 0-6 1-9 1zM12 8c-1-3-4-5-7-5 2 1 4 3 7 5zM12 8c1-3 4-5 7-5-2 1-4 3-7 5z"/>',
  zap: '<path d="M13 2 4 14h7l-1 8 9-12h-7z"/>',
};
export const icon = (n, cls = 'i') => `<svg class="${cls}" viewBox="0 0 24 24">${P[n] || P.file}</svg>`;

export const KIND_ICON = { object: 'object', scene: 'scene', animation: 'animation', shader: 'shader', texture: 'texture', font: 'font',
  mesh: 'object', material: 'material', particles: 'particles', manifest: 'manifest', preview: 'preview', data: 'file' };
export const KIND_COLOR = { object: 'var(--k-object)', scene: 'var(--k-scene)', animation: 'var(--k-animation)', shader: 'var(--k-shader)',
  texture: 'var(--k-texture)', font: 'var(--k-font)', mesh: '#f5b942', material: '#a78bfa', particles: '#67e8f9', manifest: '#94a3b8', preview: '#64748b', data: '#64748b' };
export const KIND_HEX = { mesh: '#f5b942', texture: '#34d399', shader: '#ff6bb5', material: '#a78bfa', scene: '#4fb3ff', animation: '#c06bff',
  particles: '#67e8f9', font: '#fb923c', manifest: '#94a3b8', preview: '#64748b', data: '#64748b' };
export const LABELS = ['#f87171', '#fb923c', '#f5b942', '#34d399', '#22d3ee', '#4fb3ff', '#8b5cf6', '#ff6bb5', '#94a3b8'];

export const $ = (s, el = document) => el.querySelector(s);
export const $$ = (s, el = document) => [...el.querySelectorAll(s)];
export const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
export const h = (html) => { const t = document.createElement('template'); t.innerHTML = html.trim(); return t.content.firstElementChild; };
export function bytes(n) { if (n < 1024) return n + ' B'; const u = ['KB', 'MB', 'GB']; let i = -1; do { n /= 1024; i++; } while (n >= 1024 && i < 2); return n.toFixed(n < 10 ? 1 : 0) + ' ' + u[i]; }
export const num = (n) => (n >= 1e6 ? (n / 1e6).toFixed(1) + 'M' : n >= 1e3 ? (n / 1e3).toFixed(n >= 1e4 ? 0 : 1) + 'k' : String(n ?? 0));
export function ago(t) {
  const s = Date.now() / 1000 - t;
  if (s < 60) return 'just now'; if (s < 3600) return Math.floor(s / 60) + 'm ago'; if (s < 86400) return Math.floor(s / 3600) + 'h ago';
  if (s < 86400 * 7) return Math.floor(s / 86400) + 'd ago'; return new Date(t * 1000).toLocaleDateString();
}
export const dateTime = (t) => new Date(t * 1000).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' });
export const kindBadge = (k) => `<span class="kind" style="--kc:${KIND_COLOR[k] || 'var(--muted)'}">${icon(KIND_ICON[k] || 'file')}${esc(k)}</span>`;
export const debounce = (fn, ms) => { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; };

// ------------------------------------------------------------------------------------------- persisted prefs
const PREF_KEY = 'thecreator.prefs';
let saved = {};
try { saved = JSON.parse(localStorage.getItem(PREF_KEY) || '{}'); } catch {}
export const prefs = Object.assign({ theme: 'dark', accent: 'violet', view: 'grid', cardSize: 290, sort: 'pinned', collapsed: false, autoPreviews: true }, saved);
export function savePrefs() { try { localStorage.setItem(PREF_KEY, JSON.stringify(prefs)); } catch {} }
export const ACCENTS = { violet: ['#8b5cf6', '#22d3ee'], sunset: ['#f97316', '#ec4899'], emerald: ['#10b981', '#a3e635'], ocean: ['#3b82f6', '#06b6d4'], rose: ['#f43f5e', '#a855f7'] };
export function applyTheme() {
  document.documentElement.dataset.theme = prefs.theme;
  const [a, b] = ACCENTS[prefs.accent] || ACCENTS.violet;
  document.documentElement.style.setProperty('--accent', a);
  document.documentElement.style.setProperty('--accent2', b);
  document.documentElement.style.setProperty('--card-min', prefs.cardSize + 'px');
  document.getElementById('app')?.classList.toggle('collapsed', !!prefs.collapsed);
}

// ------------------------------------------------------------------------------------------- state + api
export const state = { projects: [], folders: [], stats: null, filter: { scope: 'all', folder: null, tag: null, kind: null, status: null, q: '' }, selected: new Set(), render: () => {} };

export async function api(path, opts = {}) {
  const r = await fetch('/api' + path, { method: opts.method || 'GET', headers: { 'Content-Type': 'application/json' }, body: opts.body ? JSON.stringify(opts.body) : undefined });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.error || r.statusText);
  return data;
}
export async function refresh() {
  const [{ projects, folders }, stats] = await Promise.all([api('/projects'), api('/stats')]);
  state.projects = projects; state.folders = folders; state.stats = stats;
  state.render();
}
export const byId = (id) => state.projects.find((p) => p.id === id || p.slug === id);

// ------------------------------------------------------------------------------------------- toasts
export function toast(msg, { undo, err, ms = 3600, progress } = {}) {
  const t = h(`<div class="toast ${err ? 'err' : ''}"><span class="ic">${icon(err ? 'x' : 'check')}</span><div style="flex:1"><div class="msg">${msg}</div>${progress != null ? '<div class="progress"><i></i></div>' : ''}</div>${undo ? '<button class="btn sm">Undo</button>' : ''}</div>`);
  document.getElementById('toasts').append(t);
  const close = () => { t.style.transition = 'opacity .25s, transform .25s'; t.style.opacity = 0; t.style.transform = 'translateX(30px)'; setTimeout(() => t.remove(), 260); };
  if (undo) t.querySelector('button').onclick = () => { undo(); close(); };
  let timer = progress == null ? setTimeout(close, ms) : null;
  return {
    set(m, p) { t.querySelector('.msg').innerHTML = m; if (p != null) t.querySelector('.progress i').style.width = p * 100 + '%'; },
    done(m) { if (m) t.querySelector('.msg').innerHTML = m; clearTimeout(timer); timer = setTimeout(close, 2200); },
  };
}

// ------------------------------------------------------------------------------------------- modal
export function modal({ title, body, foot, cls = '', onClose, raw = false }) {
  const root = document.getElementById('overlay-root');
  const back = h(`<div class="modal-back"><div class="modal ${cls}">${raw ? '' : `<div class="modal-head"><h3>${title}</h3><button class="btn icon sm ghost" data-x>${icon('x')}</button></div><div class="modal-body"></div>${foot ? '<div class="modal-foot"></div>' : ''}`}</div></div>`);
  const m = back.firstElementChild;
  if (raw) m.append(typeof body === 'string' ? h(body) : body);
  else {
    const b = m.querySelector('.modal-body');
    typeof body === 'string' ? (b.innerHTML = body) : b.append(body);
    if (foot) { const f = m.querySelector('.modal-foot'); typeof foot === 'string' ? (f.innerHTML = foot) : f.append(foot); }
  }
  const close = () => { back.remove(); document.removeEventListener('keydown', key, true); onClose?.(); };
  const key = (e) => { if (e.key === 'Escape') { e.stopPropagation(); close(); } };
  document.addEventListener('keydown', key, true);
  back.addEventListener('mousedown', (e) => { if (e.target === back) close(); });
  m.querySelector('[data-x]')?.addEventListener('click', close);
  root.append(back);
  return { el: m, close };
}

export function prompt(title, value = '', { placeholder = '', ok = 'Save', multiline = false } = {}) {
  return new Promise((res) => {
    const input = multiline ? `<textarea class="field" rows="5" placeholder="${esc(placeholder)}">${esc(value)}</textarea>` : `<input class="field" value="${esc(value)}" placeholder="${esc(placeholder)}">`;
    const m = modal({ title, body: input, foot: `<button class="btn ghost" data-c>Cancel</button><button class="btn primary" data-ok>${ok}</button>`, onClose: () => res(null) });
    const f = m.el.querySelector('.field');
    f.focus(); f.select?.();
    const done = () => { const v = f.value; m.close(); res(v); };
    m.el.querySelector('[data-ok]').onclick = done;
    m.el.querySelector('[data-c]').onclick = () => m.close();
    f.addEventListener('keydown', (e) => { if (e.key === 'Enter' && (!multiline || e.metaKey)) done(); });
  });
}

export function confirmBox(title, text, { ok = 'Confirm', danger = false } = {}) {
  return new Promise((res) => {
    let answered = false;
    const m = modal({ title, body: `<p class="muted" style="margin:0">${text}</p>`, foot: `<button class="btn ghost" data-c>Cancel</button><button class="btn ${danger ? 'danger' : 'primary'}" data-ok>${ok}</button>`, onClose: () => !answered && res(false) });
    m.el.querySelector('[data-ok]').onclick = () => { answered = true; m.close(); res(true); };
    m.el.querySelector('[data-c]').onclick = () => m.close();
  });
}

// ------------------------------------------------------------------------------------------- context menu
let ctxEl = null;
export function closeCtx() { ctxEl?.remove(); ctxEl = null; }
document.addEventListener('mousedown', (e) => { if (ctxEl && !ctxEl.contains(e.target)) closeCtx(); });
document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeCtx(); });
window.addEventListener('blur', closeCtx);

function menuHtml(items) {
  return items.map((it, i) => {
    if (it === '-') return '<div class="sep"></div>';
    if (it.swatches) return `<div class="swatches">${it.swatches.map((c) => `<i data-sw="${c}" style="background:${c}"></i>`).join('')}<i data-sw="" style="background:transparent;border:1px dashed var(--dim)"></i></div>`;
    return `<div class="it ${it.danger ? 'danger' : ''}" data-i="${i}">${icon(it.icon || 'file')}<span>${esc(it.label)}</span>${it.kb ? `<span class="kb">${it.kb}</span>` : ''}${it.sub ? `<span class="kb">›</span><div class="ctx sub-menu">${menuHtml(it.sub)}</div>` : ''}</div>`;
  }).join('');
}
export function contextMenu(x, y, items) {
  closeCtx();
  ctxEl = h(`<div class="ctx">${menuHtml(items)}</div>`);
  document.body.append(ctxEl);
  const r = ctxEl.getBoundingClientRect();
  ctxEl.style.left = Math.min(x, innerWidth - r.width - 230 > 0 ? x : innerWidth - r.width - 8) + 'px';
  ctxEl.style.top = Math.min(y, innerHeight - r.height - 8) + 'px';
  const resolve = (el) => {
    const path = [];
    let n = el;
    while (n && n !== ctxEl) { if (n.dataset?.i != null) path.unshift(+n.dataset.i); n = n.parentElement; }
    let list = items, it;
    for (const i of path) { it = list[i]; list = it.sub || []; }
    return it;
  };
  ctxEl.addEventListener('click', (e) => {
    const sw = e.target.closest('[data-sw]');
    if (sw) { const owner = items.find((i) => i.swatches); owner.pick(sw.dataset.sw); closeCtx(); return; }
    const el = e.target.closest('.it');
    if (!el) return;
    const it = resolve(el);
    if (it?.sub) return;
    closeCtx();
    it?.run?.();
  });
}

// ------------------------------------------------------------------------------------------- project actions
export const go = (hash) => { location.hash = hash; };

export async function patch(p, fields, msg, undoFields) {
  const before = {};
  for (const k of Object.keys(fields)) before[k] = p[k];
  await api('/projects/' + p.id, { method: 'PATCH', body: fields });
  await refresh();
  if (msg) toast(msg, undoFields !== false ? { undo: async () => { await api('/projects/' + p.id, { method: 'PATCH', body: before }); await refresh(); } } : {});
}

export async function trash(p) {
  if (p.locked) return toast('“' + esc(p.name) + '” is locked — unlock it first', { err: true });
  await api('/projects/' + p.id, { method: 'DELETE' });
  await refresh();
  toast(`Moved <b>${esc(p.name)}</b> to trash`, { undo: async () => { await api(`/projects/${p.id}/restore`, { method: 'POST' }); await refresh(); } });
}

export async function purge(p) {
  if (!(await confirmBox('Delete forever?', `“${esc(p.name)}” and its ${p.file_count} files will be removed from the vault. This cannot be undone.`, { ok: 'Delete forever', danger: true }))) return;
  await api('/projects/' + p.id + '?purge=1', { method: 'DELETE' });
  await refresh();
  toast('Deleted permanently');
}

export async function rename(p) {
  const v = await prompt('Rename project', p.name);
  if (v && v.trim() && v !== p.name) await patch(p, { name: v.trim() }, 'Renamed');
}

export async function editTags(p) {
  const all = [...new Set(state.projects.flatMap((x) => x.tags))].sort();
  const cur = new Set(p.tags);
  const body = h(`<div><input class="field" placeholder="Add a tag and press Enter"><div class="tag-cloud" style="padding:12px 0 0;gap:6px"></div></div>`);
  const draw = () => {
    const cloud = body.querySelector('.tag-cloud');
    const tags = [...new Set([...all, ...cur])].sort();
    cloud.innerHTML = tags.map((t) => `<span class="chip ${cur.has(t) ? 'on' : ''}" data-t="${esc(t)}">${cur.has(t) ? icon('check') : icon('tag')}${esc(t)}</span>`).join('');
  };
  draw();
  body.addEventListener('click', (e) => { const c = e.target.closest('[data-t]'); if (!c) return; const t = c.dataset.t; cur.has(t) ? cur.delete(t) : cur.add(t); draw(); });
  const inp = body.querySelector('input');
  inp.addEventListener('keydown', (e) => { if (e.key === 'Enter' && inp.value.trim()) { cur.add(inp.value.trim().toLowerCase()); inp.value = ''; draw(); } });
  const m = modal({ title: 'Tags · ' + esc(p.name), body, foot: '<button class="btn primary" data-ok>Save tags</button>' });
  setTimeout(() => inp.focus(), 30);
  m.el.querySelector('[data-ok]').onclick = async () => { await api(`/projects/${p.id}/tags`, { method: 'POST', body: { tags: [...cur] } }); m.close(); await refresh(); toast('Tags updated'); };
}

export async function moveTo(p, folderId) {
  const name = folderId ? state.folders.find((f) => f.id === folderId)?.name : 'Library root';
  await patch(p, { folder_id: folderId }, `Moved to <b>${esc(name)}</b>`);
}

export async function newFolder() {
  const name = await prompt('New folder', '', { placeholder: 'e.g. Boss characters', ok: 'Create' });
  if (!name) return null;
  const color = LABELS[state.folders.length % LABELS.length];
  const { id } = await api('/folders', { method: 'POST', body: { name, color } });
  await refresh();
  toast('Folder created');
  return id;
}

export async function duplicate(p) {
  const t = toast('Duplicating ' + esc(p.name) + '…', { progress: 0 });
  const c = await api(`/projects/${p.id}/duplicate`, { method: 'POST' });
  await refresh();
  t.done(`Duplicated as <b>${esc(c.name)}</b>`);
}

export function exportZip(p) {
  const a = document.createElement('a');
  a.href = `/api/projects/${p.id}/export.zip`;
  a.download = p.slug + '.zip';
  a.click();
  toast('Exporting bundle ' + esc(p.slug) + '.zip');
}

export async function copy(text, what = 'Copied') {
  try { await navigator.clipboard.writeText(text); toast(what); } catch { toast('Clipboard unavailable', { err: true }); }
}

export async function snapshot(p) {
  const note = await prompt('Save version snapshot', '', { placeholder: 'What changed? (optional)', ok: 'Snapshot' });
  if (note === null) return;
  const r = await api(`/projects/${p.id}/snapshot`, { method: 'POST', body: { note } });
  await refresh();
  toast('Saved as version v' + r.version);
}

export async function regenerate(p) {
  const t = toast('Re-running generator for ' + esc(p.name) + '…', { progress: 0.3 });
  try {
    await api(`/projects/${p.id}/regenerate`, { method: 'POST' });
    await refresh();
    hooks.invalidatePreview?.(p.id);
    t.done('Regenerated — new version saved');
  } catch (e) { t.done(); toast(esc(e.message), { err: true }); }
}

export const hooks = {};   // filled by app.js: openForge, quickLook, compare, invalidatePreview, rerenderPreview

export function projectMenu(p) {
  const folderItems = [{ label: 'Library root', icon: 'layers', run: () => moveTo(p, null) }, ...state.folders.map((f) => ({ label: f.name, icon: 'folder', run: () => moveTo(p, f.id) })), '-', { label: 'New folder…', icon: 'plus', run: async () => { const id = await newFolder(); if (id) moveTo(p, id); } }];
  if (p.deleted_at) {
    return [
      { label: 'Restore', icon: 'refresh', run: async () => { await api(`/projects/${p.id}/restore`, { method: 'POST' }); await refresh(); toast('Restored ' + esc(p.name)); } },
      '-', { label: 'Delete forever', icon: 'trash', danger: true, run: () => purge(p) },
    ];
  }
  return [
    { label: 'Open', icon: 'external', kb: '↵', run: () => go('#/p/' + p.slug) },
    { label: 'Quick look', icon: 'eye', kb: 'Space', run: () => hooks.quickLook?.(p) },
    { label: 'Show files in vault', icon: 'database', run: () => go('#/vault/' + p.slug) },
    '-',
    { label: p.favorite ? 'Remove favourite' : 'Add to favourites', icon: 'star', kb: 'F', run: () => patch(p, { favorite: p.favorite ? 0 : 1 }, p.favorite ? 'Removed from favourites' : 'Added to favourites') },
    { label: p.pinned ? 'Unpin' : 'Pin to top', icon: 'pin', kb: 'P', run: () => patch(p, { pinned: p.pinned ? 0 : 1 }, p.pinned ? 'Unpinned' : 'Pinned to top') },
    { label: 'Rename…', icon: 'edit', kb: 'R', run: () => rename(p) },
    { label: 'Move to', icon: 'move', sub: folderItems },
    { label: 'Tags…', icon: 'tag', kb: 'T', run: () => editTags(p) },
    { label: 'Rating', icon: 'star', sub: [0, 1, 2, 3, 4, 5].map((r) => ({ label: r ? '★'.repeat(r) + '☆'.repeat(5 - r) : 'No rating', icon: r ? 'star' : 'x', run: () => patch(p, { rating: r }, r ? `Rated ${r}/5` : 'Rating cleared') })) },
    { swatches: LABELS, pick: (c) => patch(p, { color_label: c || null }, 'Label updated') },
    '-',
    { label: 'Duplicate', icon: 'copy', kb: 'D', run: () => duplicate(p) },
    { label: 'Remix prompt…', icon: 'wand', run: () => hooks.openForge?.(p.prompt) },
    { label: 'Compare with…', icon: 'compare', run: () => hooks.compare?.(p) },
    { label: 'Versions & pipeline', icon: 'history', sub: [
      { label: 'Save version snapshot…', icon: 'history', run: () => snapshot(p) },
      { label: 'Regenerate bundle', icon: 'refresh', run: () => regenerate(p) },
      { label: 'Re-render preview', icon: 'camera', run: () => hooks.rerenderPreview?.(p) }] },
    '-',
    { label: 'Export bundle (.zip)', icon: 'download', kb: 'E', run: () => exportZip(p) },
    { label: 'Copy', icon: 'copy', sub: [
      { label: 'Prompt', icon: 'sparkles', run: () => copy(p.prompt, 'Prompt copied') },
      { label: 'Link', icon: 'link', run: () => copy(location.origin + '/#/p/' + p.slug, 'Link copied') },
      { label: 'Vault path', icon: 'folder', run: () => copy('vault/projects/' + p.slug + '/', 'Path copied') }] },
    '-',
    { label: p.locked ? 'Unlock' : 'Lock (protect from delete)', icon: p.locked ? 'unlock' : 'lock', kb: 'L', run: () => patch(p, { locked: p.locked ? 0 : 1 }, p.locked ? 'Unlocked' : 'Locked — delete is disabled') },
    { label: p.archived ? 'Unarchive' : 'Archive', icon: 'archive', kb: 'A', run: () => patch(p, { archived: p.archived ? 0 : 1 }, p.archived ? 'Unarchived' : 'Archived') },
    { label: 'Move to trash', icon: 'trash', kb: '⌫', danger: true, run: () => trash(p) },
  ];
}

// ------------------------------------------------------------------------------------------- tiny GLSL / JSON highlighter
const GLSL_K = /\b(uniform|varying|attribute|void|return|if|else|for|in|out|inout|const|discard|precision|highp|mediump|lowp|break|continue)\b/g;
const GLSL_T = /\b(float|int|bool|vec[234]|mat[234]|sampler2D|ivec[234])\b/g;
const GLSL_F = /\b(texture2D|normalize|dot|cross|mix|smoothstep|clamp|pow|max|min|sin|cos|fract|floor|mod|length|reflect|refract|step|abs|exp|sqrt|inversesqrt|dFdx|dFdy)\b/g;
export function highlight(src, lang) {
  const lines = src.replace(/\t/g, '  ').split('\n').slice(0, 1500);
  return lines.map((line) => {
    let s = esc(line);
    if (lang === 'glsl') {
      const ci = s.indexOf('//');
      let code = ci >= 0 ? s.slice(0, ci) : s, comment = ci >= 0 ? s.slice(ci) : '';
      code = code.replace(GLSL_K, '<span class="tok-k">$1</span>').replace(GLSL_T, '<span class="tok-t">$1</span>')
        .replace(GLSL_F, '<span class="tok-f">$1</span>').replace(/\b(u[A-Z]\w*)\b/g, '<span class="tok-u">$1</span>')
        .replace(/(?<![\w#])(\d+\.?\d*)(?![\w])/g, '<span class="tok-n">$1</span>');
      s = code + (comment ? `<span class="tok-c">${comment}</span>` : '');
    } else if (lang === 'json') {
      s = s.replace(/(&quot;[^&]*?&quot;)(\s*:)/g, '<span class="tok-u">$1</span>$2').replace(/:\s*(&quot;.*?&quot;)/g, ': <span class="tok-s">$1</span>')
        .replace(/(?<![\w#])(-?\d+\.?\d*)(?![\w])/g, '<span class="tok-n">$1</span>');
    } else if (lang === 'obj') {
      s = s.startsWith('#') ? `<span class="tok-c">${s}</span>` : s.replace(/^(\w+)/, '<span class="tok-k">$1</span>');
    }
    return `<span class="ln">${s || ' '}</span>`;
  }).join('');
}
