// Project-TheCreator · app shell: routing, sidebar, library, prompt forge, command palette, quick look, previews.
import { $, $$, ACCENTS, ago, api, applyTheme, byId, bytes, contextMenu, debounce, esc, go, h, hooks, icon, KIND_COLOR, KIND_HEX, KIND_ICON, kindBadge,
  LABELS, modal, moveTo, newFolder, num, patch, prefs, projectMenu, refresh, savePrefs, state, toast, trash, rename, editTags, duplicate, exportZip } from './core.js';
import { disposeView, renderActivity, renderProject, renderVault } from './views.js';
import { createStage } from './engine.js';

const KINDS = ['object', 'scene', 'animation', 'shader', 'texture', 'font'];
const SCOPES = [['all', 'All creations', 'layers'], ['favorites', 'Favourites', 'star'], ['pinned', 'Pinned', 'pin'], ['recent', 'Recently opened', 'clock'],
  ['queued', 'Queued requests', 'inbox'], ['archived', 'Archived', 'archive'], ['trash', 'Trash', 'trash']];
const EXAMPLES = [
  'A low poly fox with 3000 polygons max, orange fur texture and a red scarf',
  'Create a scene of a neon cyberpunk alley at night with rain particles and fog',
  'Make an animation of a crystal that spins, cracks and reforms in a loop',
  'A hand-painted lava texture pack with glow',
  'A pixel font for a retro racing game HUD',
  'A toon water shader with foam and caustics',
];
let route = { name: 'library' };

// ============================================================================================== routing
function parseRoute() {
  const parts = location.hash.replace(/^#\/?/, '').split('/');
  if (parts[0] === 'p' && parts[1]) return { name: 'project', slug: parts[1] };
  if (parts[0] === 'vault') return { name: 'vault', slug: parts[1] };
  if (parts[0] === 'activity') return { name: 'activity' };
  return { name: 'library' };
}
async function onRoute() {
  disposeView();
  $('#app').classList.remove('drawer');
  route = parseRoute();
  renderSidebar();
  renderTopbar();
  const view = $('#view');
  view.scrollTop = 0;
  if (route.name === 'project') await renderProject(view, route.slug).catch((e) => { view.innerHTML = `<div class="empty"><div class="big">Project not found</div>${esc(e.message)}</div>`; });
  else if (route.name === 'vault') await renderVault(view, route.slug);
  else if (route.name === 'activity') await renderActivity(view);
  else renderLibrary();
}
state.render = () => {
  renderSidebar();
  if (route.name === 'library') renderLibrary(true);
};

// ============================================================================================== filtering
function visible() {
  const f = state.filter;
  let list = state.projects.filter((p) => {
    if (f.scope === 'trash') return !!p.deleted_at;
    if (p.deleted_at) return false;
    if (f.scope === 'archived') return !!p.archived;
    if (p.archived && f.scope !== 'all') return false;
    if (p.archived) return false;
    if (f.scope === 'favorites' && !p.favorite) return false;
    if (f.scope === 'pinned' && !p.pinned) return false;
    if (f.scope === 'recent' && !p.opened_at) return false;
    if (f.scope === 'queued' && !['queued', 'in-progress'].includes(p.status)) return false;
    return true;
  });
  if (f.folder) list = list.filter((p) => p.folder_id === f.folder);
  if (f.tag) list = list.filter((p) => p.tags.includes(f.tag));
  if (f.kind) list = list.filter((p) => p.kind === f.kind);
  if (f.q) {
    const terms = f.q.toLowerCase().split(/\s+/).filter(Boolean);
    list = list.filter((p) => { const hay = [p.name, p.prompt, p.kind, p.status, p.slug, ...p.tags, p.notes].join(' ').toLowerCase(); return terms.every((t) => hay.includes(t)); });
  }
  const s = prefs.sort;
  const tri = (p) => p.stats?.triangles || 0;
  const cmp = { pinned: (a, b) => b.pinned - a.pinned || b.created_at - a.created_at, newest: (a, b) => b.created_at - a.created_at, oldest: (a, b) => a.created_at - b.created_at,
    name: (a, b) => a.name.localeCompare(b.name), size: (a, b) => b.size - a.size, tris: (a, b) => tri(b) - tri(a), rating: (a, b) => b.rating - a.rating || b.favorite - a.favorite,
    updated: (a, b) => b.updated_at - a.updated_at, recent: (a, b) => (b.opened_at || 0) - (a.opened_at || 0) }[f.scope === 'recent' ? 'recent' : s];
  return list.sort(cmp);
}
const live = () => state.projects.filter((p) => !p.deleted_at);

// ============================================================================================== sidebar
function renderSidebar() {
  const sb = $('#sidebar');
  const L = live();
  const counts = { all: L.filter((p) => !p.archived).length, favorites: L.filter((p) => p.favorite).length, pinned: L.filter((p) => p.pinned).length,
    recent: L.filter((p) => p.opened_at).length, queued: L.filter((p) => ['queued', 'in-progress'].includes(p.status)).length,
    archived: L.filter((p) => p.archived).length, trash: state.projects.filter((p) => p.deleted_at).length };
  const tags = {};
  L.forEach((p) => p.tags.forEach((t) => (tags[t] = (tags[t] || 0) + 1)));
  const f = state.filter, lib = route.name === 'library';
  const st = state.stats;
  sb.innerHTML = `
    <div class="brand" data-home><div class="brand-mark">${icon('object')}</div><div class="brand-name">TheCreator<small>prompt → asset vault</small></div></div>
    <div class="side-scroll">
      <div class="nav-item ${lib ? 'active' : ''}" data-nav="#/">${icon('grid')}<span>Library</span><span class="count">${counts.all}</span></div>
      <div class="nav-item ${route.name === 'vault' ? 'active' : ''}" data-nav="#/vault">${icon('database')}<span>Vault explorer</span><span class="count">${st?.assets ?? ''}</span></div>
      <div class="nav-item ${route.name === 'activity' ? 'active' : ''}" data-nav="#/activity">${icon('activity')}<span>Activity</span></div>
      <div class="nav-item" data-forge>${icon('sparkles')}<span>New request</span><span class="count"><kbd>N</kbd></span></div>
      <div class="side-label">Collections</div>
      ${SCOPES.map(([k, l, i]) => `<div class="nav-item ${lib && f.scope === k && !f.folder && !f.kind && !f.tag ? 'active' : ''}" data-scope="${k}">${icon(i)}<span>${l}</span><span class="count">${counts[k] || ''}</span></div>`).join('')}
      <div class="side-label">Types</div>
      ${KINDS.map((k) => { const n = L.filter((p) => p.kind === k && !p.archived).length; return `<div class="nav-item ${lib && f.kind === k ? 'active' : ''}" data-kind="${k}" style="${n ? '' : 'opacity:.45'}"><span style="color:${KIND_COLOR[k]};display:grid">${icon(KIND_ICON[k])}</span><span style="text-transform:capitalize">${k}s</span><span class="count">${n || ''}</span></div>`; }).join('')}
      <div class="side-label">Folders<button data-newfolder title="New folder">${icon('plus')}</button></div>
      ${state.folders.map((fo) => `<div class="nav-item ${lib && f.folder === fo.id ? 'active' : ''}" data-folder="${fo.id}"><span class="dot" style="background:${fo.color}"></span><span>${esc(fo.name)}</span><span class="count">${fo.count || ''}</span></div>`).join('')}
      ${Object.keys(tags).length ? `<div class="side-label">Tags</div><div class="tag-cloud">${Object.entries(tags).sort((a, b) => b[1] - a[1]).map(([t, n]) => `<span class="tag" data-tag="${esc(t)}" style="${f.tag === t ? 'color:var(--text);border-color:var(--accent)' : ''}">#${esc(t)} ${n}</span>`).join('')}</div>` : ''}
    </div>
    ${st ? `<div class="storage"><div style="display:flex;justify-content:space-between;font-size:12.5px"><b>Vault storage</b><span class="mono muted">${bytes(st.bytes)}</span></div>
      <div class="bar">${st.by_kind.map((k) => `<span style="flex:${k.bytes};background:${KIND_HEX[k.kind]}" title="${k.kind}"></span>`).join('')}</div>
      <div class="storage-legend">${st.by_kind.slice(0, 6).map((k) => `<span><i style="background:${KIND_HEX[k.kind]}"></i>${k.kind}</span>`).join('')}</div></div>` : ''}`;
}
function bindSidebar() {
  const sb = $('#sidebar');
  const toLib = (fn) => { fn(); state.selected.clear(); if (route.name !== 'library') go('#/'); else { renderSidebar(); renderLibrary(); } };
  sb.addEventListener('click', async (e) => {
    const t = e.target.closest('[data-nav],[data-scope],[data-kind],[data-folder],[data-tag],[data-newfolder],[data-forge],[data-home]');
    if (!t) return;
    const f = state.filter;
    if (innerWidth <= 760) $('#app').classList.remove('drawer');
    if (t.dataset.nav) go(t.dataset.nav);
    else if ('home' in t.dataset) toLib(() => Object.assign(f, { scope: 'all', folder: null, kind: null, tag: null }));
    else if (t.dataset.scope) toLib(() => Object.assign(f, { scope: t.dataset.scope, folder: null, kind: null, tag: null }));
    else if (t.dataset.kind) toLib(() => Object.assign(f, { scope: 'all', kind: f.kind === t.dataset.kind ? null : t.dataset.kind, folder: null, tag: null }));
    else if (t.dataset.folder) toLib(() => Object.assign(f, { scope: 'all', folder: t.dataset.folder, kind: null, tag: null }));
    else if (t.dataset.tag) toLib(() => Object.assign(f, { tag: f.tag === t.dataset.tag ? null : t.dataset.tag }));
    else if ('newfolder' in t.dataset) newFolder();
    else if ('forge' in t.dataset) openForge();
  });
  sb.addEventListener('contextmenu', (e) => {
    const fo = e.target.closest('[data-folder]');
    if (!fo) return;
    e.preventDefault();
    const folder = state.folders.find((x) => x.id === fo.dataset.folder);
    contextMenu(e.clientX, e.clientY, [
      { label: 'Rename folder…', icon: 'edit', run: async () => { const { prompt } = await import('./core.js'); const v = await prompt('Rename folder', folder.name); if (v) { await api('/folders/' + folder.id, { method: 'PATCH', body: { name: v } }); refresh(); } } },
      { swatches: LABELS, pick: async (c) => { await api('/folders/' + folder.id, { method: 'PATCH', body: { color: c || '#64748b' } }); refresh(); } },
      '-', { label: 'Delete folder (keeps projects)', icon: 'trash', danger: true, run: async () => { await api('/folders/' + folder.id, { method: 'DELETE' }); if (state.filter.folder === folder.id) state.filter.folder = null; refresh(); toast('Folder removed — its projects moved to the library root'); } },
    ]);
  });
  // drag cards onto folders / trash
  sb.addEventListener('dragover', (e) => { const t = e.target.closest('[data-folder],[data-scope="trash"],[data-scope="favorites"],[data-scope="archived"]'); if (t && e.dataTransfer.types.includes('text/x-project')) { e.preventDefault(); $$('.drop-target', sb).forEach((x) => x !== t && x.classList.remove('drop-target')); t.classList.add('drop-target'); } });
  sb.addEventListener('dragleave', (e) => e.target.closest?.('.drop-target')?.classList.remove('drop-target'));
  sb.addEventListener('drop', async (e) => {
    const t = e.target.closest('[data-folder],[data-scope]');
    $$('.drop-target', sb).forEach((x) => x.classList.remove('drop-target'));
    const ids = e.dataTransfer.getData('text/x-project').split(',').filter(Boolean);
    if (!t || !ids.length) return;
    e.preventDefault();
    for (const id of ids) {
      const p = byId(id);
      if (t.dataset.folder) await api('/projects/' + p.id, { method: 'PATCH', body: { folder_id: t.dataset.folder } });
      else if (t.dataset.scope === 'trash') { if (!p.locked) await api('/projects/' + p.id, { method: 'DELETE' }); }
      else if (t.dataset.scope === 'favorites') await api('/projects/' + p.id, { method: 'PATCH', body: { favorite: 1 } });
      else if (t.dataset.scope === 'archived') await api('/projects/' + p.id, { method: 'PATCH', body: { archived: 1 } });
    }
    await refresh();
    toast(`${ids.length} project${ids.length > 1 ? 's' : ''} → ${esc(t.textContent.trim().replace(/\d+$/, ''))}`);
  });
}

// ============================================================================================== topbar
function renderTopbar() {
  const tb = $('#topbar');
  const p = route.slug && byId(route.slug);
  const f = state.filter;
  let crumbs = '';
  if (route.name === 'project') crumbs = `<a href="#/">Library</a><span class="sep">/</span><span id="crumb-name">${esc(p?.name || route.slug)}</span>`;
  else if (route.name === 'vault') crumbs = `<a href="#/">Library</a><span class="sep">/</span><span>Vault</span>${route.slug ? `<span class="sep">/</span><span class="mono">${esc(route.slug)}</span>` : ''}`;
  else if (route.name === 'activity') crumbs = `<a href="#/">Library</a><span class="sep">/</span><span>Activity</span>`;
  else crumbs = `<span>Library</span>${f.folder ? `<span class="sep">/</span><span>${esc(state.folders.find((x) => x.id === f.folder)?.name)}</span>` : ''}`;
  tb.innerHTML = `
    <button class="btn icon ghost" data-collapse title="Toggle sidebar">${icon('sidebar')}</button>
    ${route.name === 'project' ? `<button class="btn icon ghost" data-back title="Back">${icon('back')}</button>` : ''}
    <div class="crumbs">${crumbs}</div>
    <div class="search">${icon('search')}<input id="q" placeholder="Search creations, prompts, tags…" value="${esc(f.q)}"><kbd>/</kbd></div>
    <button class="btn ghost" data-palette title="Command palette">${icon('command')}<kbd>⌘K</kbd></button>
    <button class="btn icon ghost" data-theme title="Toggle theme">${icon(prefs.theme === 'dark' ? 'sun' : 'moon')}</button>
    <button class="btn icon ghost" data-settings title="Settings">${icon('settings')}</button>
    <button class="btn primary" data-forge>${icon('sparkles')}New request</button>`;
  const q = $('#q', tb);
  q.oninput = debounce(() => { state.filter.q = q.value; if (route.name !== 'library') go('#/'); else renderLibrary(); }, 140);
}
function bindTopbar() {
  $('#topbar').addEventListener('click', (e) => {
    const b = e.target.closest('button');
    if (!b) return;
    if ('collapse' in b.dataset) { if (innerWidth <= 760) return $('#app').classList.toggle('drawer'); prefs.collapsed = !prefs.collapsed; savePrefs(); applyTheme(); }
    if ('back' in b.dataset) history.length > 1 ? history.back() : go('#/');
    if ('palette' in b.dataset) openPalette();
    if ('theme' in b.dataset) { prefs.theme = prefs.theme === 'dark' ? 'light' : 'dark'; savePrefs(); applyTheme(); renderTopbar(); }
    if ('settings' in b.dataset) openSettings();
    if ('forge' in b.dataset) openForge();
  });
}

// ============================================================================================== library
function renderLibrary(keepScroll) {
  const view = $('#view');
  const scroll = view.scrollTop;
  const st = state.stats || {};
  const list = visible();
  const f = state.filter;
  const L = live();
  const title = f.tag ? '#' + f.tag : f.kind ? f.kind[0].toUpperCase() + f.kind.slice(1) + 's' : f.folder ? state.folders.find((x) => x.id === f.folder)?.name : SCOPES.find((s) => s[0] === f.scope)[1];
  const showHero = f.scope === 'all' && !f.folder && !f.kind && !f.tag && !f.q;
  const forgeDraft = $('#forge-text')?.value || '';
  view.innerHTML = `<div class="page">
    ${showHero ? `<div class="hero">
      <div class="forge"><h1>What should <em>TheCreator</em> make next?</h1><p>Describe an object, scene, animation, shader, texture or font. It's interpreted live, bundled, versioned and stored in the vault.</p>
        <div class="forge-input"><textarea id="forge-text" rows="1" placeholder="e.g. A low poly fox with 3000 polygons and a red scarf…">${esc(forgeDraft)}</textarea><button class="btn primary" id="forge-go">${icon('sparkles')}Queue</button></div>
        <div class="forge-chips" id="forge-chips"></div></div>
      <div class="stats-grid">
        ${statTile(st.projects ?? 0, 'Bundles', 'layers')}${statTile(st.assets ?? 0, 'Files in vault', 'file')}${statTile(bytes(st.bytes || 0), 'Storage', 'database')}
        ${statTile(num(st.triangles || 0), 'Triangles', 'object')}${statTile(L.filter((p) => p.favorite).length, 'Favourites', 'star')}${statTile(st.queued ?? 0, 'Queued', 'inbox')}
        <div class="stat wide"><div><div class="l" style="margin:0 0 8px">Asset mix</div><div class="meter" style="width:100%;min-width:200px">${(st.by_kind || []).map((k) => `<span style="flex:${k.n};background:${KIND_HEX[k.kind]}" title="${k.kind}: ${k.n}"></span>`).join('')}</div></div>
        <div style="display:flex;flex-wrap:wrap;gap:4px 10px;font-size:11px;color:var(--muted)">${(st.by_kind || []).map((k) => `<span><i style="display:inline-block;width:7px;height:7px;border-radius:2px;background:${KIND_HEX[k.kind]};margin-right:4px"></i>${k.n} ${k.kind}</span>`).join('')}</div></div>
      </div></div>` : ''}
    <div class="toolbar">
      <h2>${esc(title)}</h2><span class="muted mono" style="font-size:12px">${list.length} item${list.length === 1 ? '' : 's'}</span>
      ${f.q ? `<span class="chip on" data-clearq>${icon('search')}“${esc(f.q)}” ${icon('x')}</span>` : ''}
      <span class="grow"></span>
      ${KINDS.slice(0, 3).map((k) => `<span class="chip ${f.kind === k ? 'on' : ''}" data-fk="${k}"><span style="color:${KIND_COLOR[k]};display:grid">${icon(KIND_ICON[k])}</span>${k}</span>`).join('')}
      <select class="field" id="sort" style="width:auto;height:34px;padding:0 10px">${[['pinned', 'Pinned first'], ['newest', 'Newest'], ['oldest', 'Oldest'], ['updated', 'Last modified'], ['name', 'Name A–Z'], ['size', 'Largest'], ['tris', 'Most triangles'], ['rating', 'Top rated']].map(([v, l]) => `<option value="${v}" ${prefs.sort === v ? 'selected' : ''}>${l}</option>`).join('')}</select>
      <input type="range" class="range" min="220" max="440" value="${prefs.cardSize}" id="csize" title="Card size">
      <div class="seg"><button data-view="grid" class="${prefs.view === 'grid' ? 'on' : ''}" title="Grid">${icon('grid')}</button><button data-view="list" class="${prefs.view === 'list' ? 'on' : ''}" title="List">${icon('list')}</button></div>
      <button class="btn sm ${state.selectMode ? 'on' : ''}" data-select>${icon('check')}Select</button>
      ${f.scope === 'trash' && list.length ? `<button class="btn sm danger" data-empty-trash>${icon('trash')}Empty trash</button>` : ''}
    </div>
    ${list.length ? `<div class="grid ${prefs.view}" id="grid">${list.map(card).join('')}</div>` : emptyState()}
  </div>`;
  if (keepScroll) view.scrollTop = scroll;
  bindForgeInline();
  renderBulkbar();
}
const statTile = (v, l, i) => `<div class="stat">${icon(i, 'i bg')}<div class="v">${v}</div><div class="l">${l}</div></div>`;
function emptyState() {
  const f = state.filter;
  if (f.scope === 'trash') return `<div class="empty">${icon('trash')}<div class="big">Trash is empty</div>Deleted creations wait here until you restore or purge them.</div>`;
  if (f.q) return `<div class="empty">${icon('search')}<div class="big">Nothing matches “${esc(f.q)}”</div><button class="btn" data-clearq>Clear search</button></div>`;
  return `<div class="empty">${icon('sparkles')}<div class="big">Nothing here yet</div>Queue a request with <kbd>N</kbd> or drag projects into this folder.</div>`;
}

function card(p, i) {
  const s = p.stats || {};
  const ready = !!p.render?.type;
  const cl = p.color_label || KIND_HEX[p.kind === 'object' ? 'mesh' : p.kind] || 'var(--accent)';
  const folder = state.folders.find((x) => x.id === p.folder_id);
  return `<article class="card ${state.selected.has(p.id) ? 'selected' : ''} ${p.deleted_at ? 'trashed' : ''}" data-id="${p.id}" draggable="true" style="--cl:${cl};animation-delay:${Math.min(i, 12) * 35}ms">
    <div class="thumb">
      ${p.thumbnail ? `<div class="img" style="background-image:url('${p.thumbnail}')"></div>` : `<div class="placeholder"><div class="orb" style="--a:${(i * 67) % 360}deg"></div><div class="lbl">${ready ? icon('camera') + 'rendering preview' : icon('inbox') + 'awaiting generator'}</div></div><div class="shimmer"></div>`}
      ${p.sprite ? `<div class="sprite" data-sprite="${p.sprite}"></div><div class="scrub"><i></i></div>` : ''}
      <div class="thumb-top"><span class="check hover-only" data-act="select">${icon('check')}</span><span class="grow"></span>
        ${p.locked ? `<span class="ibtn lock-badge" title="Locked">${icon('lock')}</span>` : ''}
        <span class="ibtn pin ${p.pinned ? 'on' : 'hover-only'}" data-act="pin" title="Pin">${icon('pin')}</span>
        <span class="ibtn fav ${p.favorite ? 'on' : 'hover-only'}" data-act="fav" title="Favourite (F)">${icon('star')}</span>
        <span class="ibtn hover-only" data-act="ql" title="Quick look (Space)">${icon('eye')}</span>
        <span class="ibtn hover-only" data-act="menu" title="More">${icon('more')}</span></div>
      <div class="thumb-bottom">${kindBadge(p.kind)}</div>
    </div>
    <div class="card-body">
      <div><div class="card-title">${p.color_label ? '<span class="label"></span>' : ''}<h3 data-act="rename" title="Double-click to rename">${esc(p.name)}</h3><span class="status ${p.status}">${p.status}</span></div>
      <div class="card-prompt">${esc(p.prompt)}</div></div>
      <div class="card-meta"><span title="Files">${icon('file')}${p.file_count}</span><span title="Bundle size">${icon('database')}${bytes(p.size)}</span>${s.triangles ? `<span title="Triangles">${icon('object')}${num(s.triangles)}</span>` : ''}${s.duration ? `<span>${icon('clock')}${s.duration}s</span>` : ''}<span title="Version">v${p.version}</span>${folder ? `<span title="Folder"><i style="width:7px;height:7px;border-radius:2px;background:${folder.color}"></i>${esc(folder.name)}</span>` : ''}</div>
      <div class="card-foot"><div class="tags">${p.tags.slice(0, 3).map((t) => `<span class="tag">#${esc(t)}</span>`).join('')}</div>
        <div class="stars">${[1, 2, 3, 4, 5].map((r) => `<svg class="i ${r <= p.rating ? 'on' : ''}" data-rate="${r}" viewBox="0 0 24 24"><path d="M12 3l2.7 5.6 6.1.9-4.4 4.3 1 6.1L12 17l-5.4 2.9 1-6.1L3.2 9.5l6.1-.9z"/></svg>`).join('')}</div>
        <span class="dim mono" style="font-size:11px" title="${new Date(p.created_at * 1000).toLocaleString()}">${ago(p.created_at)}</span></div>
      ${s.budget ? `<div class="budget" title="Polygon budget ${s.budget_used}%"><i style="width:${s.budget_used}%"></i></div>` : ''}
    </div></article>`;
}

function bindLibrary() {
  const view = $('#view');
  view.addEventListener('click', async (e) => {
    if (route.name !== 'library') return;
    const tb = e.target.closest('[data-view],[data-select],[data-fk],[data-clearq],[data-empty-trash],.forge-chips [data-ex]');
    if (tb) {
      if (tb.dataset.view) { prefs.view = tb.dataset.view; savePrefs(); renderLibrary(true); }
      if ('select' in tb.dataset) { state.selectMode = !state.selectMode; if (!state.selectMode) state.selected.clear(); renderLibrary(true); }
      if (tb.dataset.fk) { state.filter.kind = state.filter.kind === tb.dataset.fk ? null : tb.dataset.fk; renderSidebar(); renderLibrary(); }
      if ('clearq' in tb.dataset) { state.filter.q = ''; $('#q').value = ''; renderLibrary(); }
      if ('emptyTrash' in tb.dataset) emptyTrash();
      if (tb.dataset.ex != null) { $('#forge-text').value = tb.dataset.ex; $('#forge-text').dispatchEvent(new Event('input')); }
      return;
    }
    const c = e.target.closest('.card');
    if (!c) return;
    const p = byId(c.dataset.id);
    const act = e.target.closest('[data-act]')?.dataset.act;
    const rate = e.target.closest('[data-rate]')?.dataset.rate;
    if (rate) return patch(p, { rating: +rate === p.rating ? 0 : +rate }, `Rated ${rate}/5`);
    if (act === 'fav') return patch(p, { favorite: p.favorite ? 0 : 1 }, p.favorite ? 'Removed from favourites' : `<b>${esc(p.name)}</b> added to favourites`);
    if (act === 'pin') return patch(p, { pinned: p.pinned ? 0 : 1 }, p.pinned ? 'Unpinned' : 'Pinned to top');
    if (act === 'ql') return quickLook(p);
    if (act === 'menu') { const r = e.target.closest('[data-act]').getBoundingClientRect(); return contextMenu(r.right - 240, r.bottom + 6, projectMenu(p)); }
    if (act === 'select' || state.selectMode || e.metaKey || e.shiftKey) { toggleSelect(p.id, c); return; }
    if (act === 'rename') return;
    if (p.deleted_at) return contextMenu(e.clientX, e.clientY, projectMenu(p));
    go('#/p/' + p.slug);
  });
  view.addEventListener('dblclick', (e) => { const t = e.target.closest('[data-act="rename"]'); if (t && route.name === 'library') { e.preventDefault(); rename(byId(t.closest('.card').dataset.id)); } });
  view.addEventListener('contextmenu', (e) => { const c = e.target.closest('.card'); if (!c || route.name !== 'library') return; e.preventDefault(); contextMenu(e.clientX, e.clientY, projectMenu(byId(c.dataset.id))); });
  view.addEventListener('change', (e) => {
    if (e.target.id === 'sort') { prefs.sort = e.target.value; savePrefs(); renderLibrary(true); }
  });
  view.addEventListener('input', (e) => { if (e.target.id === 'csize') { prefs.cardSize = +e.target.value; savePrefs(); applyTheme(); } });
  // hover: sprite scrub + keyboard target
  view.addEventListener('mousemove', (e) => {
    const c = e.target.closest('.card');
    state.hover = c?.dataset.id || null;
    const th = e.target.closest('.thumb');
    if (!th) return;
    const sp = $('.sprite', th);
    if (!sp) return;
    if (!sp.classList.contains('ready')) {
      if (!sp.dataset.loading) { sp.dataset.loading = 1; const im = new Image(); im.onload = () => { sp.style.backgroundImage = `url('${sp.dataset.sprite}')`; sp.classList.add('ready'); $('.scrub', th)?.classList.add('ready'); }; im.src = sp.dataset.sprite; }
      return;
    }
    const r = th.getBoundingClientRect();
    const fr = Math.max(0, Math.min(15, Math.floor(((e.clientX - r.left) / r.width) * 16)));
    sp.style.backgroundPosition = `${(fr / 15) * 100}% 0`;
    $('.scrub i', th).style.width = ((fr + 1) / 16) * 100 + '%';
  });
  view.addEventListener('mouseleave', () => (state.hover = null), true);
  // drag cards
  view.addEventListener('dragstart', (e) => {
    const c = e.target.closest?.('.card');
    if (!c) return;
    const ids = state.selected.has(c.dataset.id) ? [...state.selected] : [c.dataset.id];
    e.dataTransfer.setData('text/x-project', ids.join(','));
    e.dataTransfer.effectAllowed = 'move';
    c.classList.add('dragging');
  });
  view.addEventListener('dragend', (e) => e.target.closest?.('.card')?.classList.remove('dragging'));
  // drop OS files onto a card → upload into that bundle
  view.addEventListener('dragover', (e) => { const c = e.target.closest('.card'); if (c && e.dataTransfer.types.includes('Files')) { e.preventDefault(); $$('.drop-files').forEach((x) => x.classList.remove('drop-files')); c.classList.add('drop-files'); } });
  view.addEventListener('drop', async (e) => {
    $$('.drop-files').forEach((x) => x.classList.remove('drop-files'));
    $('#drop-overlay').classList.remove('show');
    const c = e.target.closest('.card');
    if (c && e.dataTransfer.files.length) { e.preventDefault(); await uploadFiles(byId(c.dataset.id), e.dataTransfer.files); }
  });
}
function toggleSelect(id, el) {
  state.selected.has(id) ? state.selected.delete(id) : state.selected.add(id);
  el?.classList.toggle('selected', state.selected.has(id));
  renderBulkbar();
}
function renderBulkbar() {
  const bar = $('#bulkbar');
  const n = state.selected.size;
  bar.classList.toggle('show', n > 0 && route.name === 'library');
  if (!n) return;
  bar.innerHTML = `<b>${n} selected</b>
    <button class="btn sm" data-b="fav">${icon('star')}Favourite</button><button class="btn sm" data-b="move">${icon('move')}Move</button>
    <button class="btn sm" data-b="tag">${icon('tag')}Tag</button><button class="btn sm" data-b="archive">${icon('archive')}Archive</button>
    <button class="btn sm" data-b="zip">${icon('download')}Export</button><button class="btn sm" data-b="compare" ${n === 2 ? '' : 'disabled style="opacity:.4"'}>${icon('compare')}Compare</button>
    <button class="btn sm danger" data-b="trash">${icon('trash')}Delete</button><button class="btn sm icon ghost" data-b="clear">${icon('x')}</button>`;
}
function bindBulkbar() {
  $('#bulkbar').addEventListener('click', async (e) => {
    const b = e.target.closest('[data-b]')?.dataset.b;
    if (!b) return;
    const ps = [...state.selected].map(byId).filter(Boolean);
    const each = async (fields) => { for (const p of ps) await api('/projects/' + p.id, { method: 'PATCH', body: fields }); await refresh(); };
    if (b === 'fav') { await each({ favorite: 1 }); toast(`${ps.length} added to favourites`); }
    if (b === 'archive') { await each({ archived: 1 }); toast(`${ps.length} archived`, { undo: () => { state.selected = new Set(ps.map((p) => p.id)); each({ archived: 0 }); } }); state.selected.clear(); }
    if (b === 'zip') ps.forEach((p, i) => setTimeout(() => exportZip(p), i * 400));
    if (b === 'compare' && ps.length === 2) compare(ps[0], ps[1]);
    if (b === 'clear') { state.selected.clear(); state.selectMode = false; renderLibrary(true); }
    if (b === 'trash') { for (const p of ps) if (!p.locked) await api('/projects/' + p.id, { method: 'DELETE' }); state.selected.clear(); await refresh(); toast(`${ps.length} moved to trash`, { undo: async () => { for (const p of ps) await api(`/projects/${p.id}/restore`, { method: 'POST' }); refresh(); } }); }
    if (b === 'move') { const r = e.target.closest('button').getBoundingClientRect(); contextMenu(r.left, r.top - 8 - 40 * (state.folders.length + 1), [{ label: 'Library root', icon: 'layers', run: () => each({ folder_id: null }) }, ...state.folders.map((f) => ({ label: f.name, icon: 'folder', run: () => each({ folder_id: f.id }).then(() => toast('Moved to ' + esc(f.name))) }))]); }
    if (b === 'tag') { const { prompt } = await import('./core.js'); const t = await prompt(`Add tag to ${ps.length} projects`, '', { placeholder: 'tag' }); if (t) { for (const p of ps) await api(`/projects/${p.id}/tags`, { method: 'POST', body: { tags: [...p.tags, t] } }); await refresh(); toast('Tagged #' + esc(t)); } }
  });
}
async function emptyTrash() {
  const { confirmBox } = await import('./core.js');
  const items = state.projects.filter((p) => p.deleted_at);
  if (!(await confirmBox('Empty trash?', `${items.length} bundles and all their files will be permanently removed from the vault.`, { ok: 'Empty trash', danger: true }))) return;
  for (const p of items) await api(`/projects/${p.id}?purge=1`, { method: 'DELETE' }).catch((e) => toast(esc(e.message), { err: true }));
  await refresh();
  toast('Trash emptied');
}

// ============================================================================================== prompt forge
const parseChips = (spec) => {
  const out = [['kind', spec.kind]];
  if (spec.subject) out.push(['subject', spec.subject]);
  if (spec.poly_budget) out.push(['budget', num(spec.poly_budget) + ' polys']);
  spec.styles.forEach((s) => out.push(['style', s]));
  spec.materials.forEach((s) => out.push(['material', s]));
  spec.effects.forEach((s) => out.push(['effect', s]));
  spec.motions.forEach((s) => out.push(['motion', s]));
  spec.colors.forEach((s) => out.push(['colour', s]));
  return out.map(([k, v]) => `<span class="parse-chip"><b>${k}</b>${esc(v)}</span>`).join('');
};
function bindForgeInline() {
  const ta = $('#forge-text');
  if (!ta) return;
  const chips = $('#forge-chips');
  const examples = () => `<span class="muted" style="font-size:12px;align-self:center;margin-right:4px">Try:</span>${EXAMPLES.slice(0, 4).map((x) => `<span class="chip" data-ex="${esc(x)}">${esc(x.length > 42 ? x.slice(0, 40) + '…' : x)}</span>`).join('')}`;
  const grow = () => { ta.style.height = 'auto'; ta.style.height = Math.min(ta.scrollHeight, 140) + 'px'; };
  const parse = debounce(async () => {
    if (!ta.value.trim()) return (chips.innerHTML = examples());
    const spec = await api('/parse', { method: 'POST', body: { prompt: ta.value } });
    chips.innerHTML = parseChips(spec) + `<span class="parse-chip"><b>stages</b>${spec.pipeline.length}</span><span class="parse-chip"><b>complexity</b>${spec.complexity}</span>`;
  }, 220);
  ta.addEventListener('input', () => { grow(); parse(); });
  ta.addEventListener('keydown', (e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); $('#forge-go').click(); } });
  $('#forge-go').onclick = () => { const text = ta.value; ta.value = ''; submitRequest(text, null).then((ok) => { const fresh = $('#forge-text'); if (!ok && fresh) { fresh.value = text; fresh.dispatchEvent(new Event('input')); } }); };
  grow();
  ta.value ? parse() : (chips.innerHTML = examples());
}
async function submitRequest(text, folderId) {
  if (!text.trim()) { toast('Describe what to create first', { err: true }); return false; }
  const p = await api('/requests', { method: 'POST', body: { prompt: text.trim(), folder_id: folderId } });
  await refresh();
  toast(`Queued <b>${esc(p.name)}</b> as ${p.kind} · ticket in vault/inbox`, { undo: async () => { await api(`/projects/${p.id}?purge=1`, { method: 'DELETE' }); refresh(); } });
  return true;
}
function openForge(initial = '') {
  const body = h(`<div>
    <textarea class="field" rows="4" id="fm-text" placeholder="Describe the creation…" style="font-size:15px;resize:vertical">${esc(initial)}</textarea>
    <div class="example-chips">${EXAMPLES.map((x) => `<span class="chip" data-ex="${esc(x)}">${esc(x.length > 46 ? x.slice(0, 44) + '…' : x)}</span>`).join('')}</div>
    <div id="fm-parse" style="margin-top:18px"></div>
    <div style="display:flex;gap:10px;align-items:center;margin-top:16px"><span class="muted" style="font-size:13px">File into</span><select class="field" id="fm-folder" style="width:auto">${['<option value="">Library root</option>', ...state.folders.map((f) => `<option value="${f.id}" ${f.name === 'Inbox' ? 'selected' : ''}>${esc(f.name)}</option>`)].join('')}</select></div>
  </div>`);
  const m = modal({ title: `${icon('sparkles')} New creation request`, body, cls: 'wide', foot: `<span class="muted" style="font-size:12px;margin-right:auto">The interpreter is deterministic — every decision is explained.</span><button class="btn ghost" data-c>Cancel</button><button class="btn primary" data-ok>${icon('sparkles')}Queue request <kbd style="background:transparent;color:#fff;border-color:rgba(255,255,255,.4)">⌘↵</kbd></button>` });
  const ta = $('#fm-text', body), out = $('#fm-parse', body);
  const parse = debounce(async () => {
    if (!ta.value.trim()) return (out.innerHTML = '');
    const s = await api('/parse', { method: 'POST', body: { prompt: ta.value } });
    out.innerHTML = `<div style="display:grid;grid-template-columns:1.2fr 1fr;gap:16px">
      <div><div class="section"><h4>${icon('wand')}Interpretation</h4><div class="kv">
        <div><div class="k">Proposed name</div><div class="v">${esc(s.name)}</div></div><div><div class="k">Type</div><div class="v">${kindBadge(s.kind)}</div></div>
        <div><div class="k">Polygon budget</div><div class="v">${s.poly_budget ? num(s.poly_budget) : '—'}</div></div><div><div class="k">Complexity</div><div class="v">${s.complexity}/100<div class="complexity" style="margin-top:6px"><i style="width:${s.complexity}%"></i></div></div></div></div></div>
        <div class="section"><h4>${icon('info')}Why</h4>${s.explain.map((x) => `<div class="legend-row" style="grid-template-columns:110px 1fr"><span class="mono muted" style="font-size:11px">${x.field}</span><span>${esc(Array.isArray(x.value) ? x.value.join(', ') : x.value)} <span class="dim" style="font-size:12px">← “${esc(x.because)}”</span></span></div>`).join('')}</div></div>
      <div class="section"><h4>${icon('activity')}Planned pipeline</h4><div class="pipeline">${s.pipeline.map((st, i) => `<div class="pipe-step ${i ? '' : 'done'}"><div class="dot">${i ? i + 1 : icon('check')}</div><div><div class="t">${esc(st.stage)}</div></div></div>`).join('')}</div></div></div>`;
  }, 200);
  ta.addEventListener('input', parse);
  body.addEventListener('click', (e) => { const c = e.target.closest('[data-ex]'); if (c) { ta.value = c.dataset.ex; parse(); } });
  const go_ = async () => { if (await submitRequest(ta.value, $('#fm-folder', body).value || null)) m.close(); };
  m.el.querySelector('[data-ok]').onclick = go_;
  m.el.querySelector('[data-c]').onclick = () => m.close();
  ta.addEventListener('keydown', (e) => { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) go_(); });
  setTimeout(() => ta.focus(), 40);
  if (initial) parse();
}

// ============================================================================================== command palette
function openPalette() {
  const actions = [
    ['New creation request', 'sparkles', () => openForge(), 'N'], ['Go to library', 'grid', () => go('#/')], ['Open vault explorer', 'database', () => go('#/vault')],
    ['Activity feed', 'activity', () => go('#/activity')], ['Show favourites', 'star', () => { state.filter.scope = 'favorites'; go('#/'); onRoute(); }],
    ['Show trash', 'trash', () => { state.filter.scope = 'trash'; go('#/'); onRoute(); }], ['Run integrity check', 'shield', () => go('#/vault')], ['Process request queue', 'zap', () => go('#/vault')],
    ['Toggle theme', 'sun', () => { prefs.theme = prefs.theme === 'dark' ? 'light' : 'dark'; savePrefs(); applyTheme(); renderTopbar(); }],
    ['New folder', 'folder', () => newFolder()], ['Re-render all previews', 'camera', () => ensurePreviews(true)], ['Keyboard shortcuts', 'keyboard', () => openShortcuts(), '?'], ['Settings', 'settings', () => openSettings()],
  ];
  const body = h(`<div><input placeholder="Search projects, files and actions…"><div class="res"></div></div>`);
  const m = modal({ body, raw: true, cls: 'palette' });
  const inp = $('input', body), res = $('.res', body);
  let items = [], idx = 0;
  const draw = () => {
    const q = inp.value.toLowerCase().trim();
    const score = (s) => { s = s.toLowerCase(); if (!q) return 1; if (s.includes(q)) return 2 + (s.startsWith(q) ? 1 : 0); let i = 0; for (const ch of s) if (ch === q[i]) i++; return i === q.length ? 1 : 0; };
    const ps = live().map((p) => ({ p, s: Math.max(score(p.name), score(p.prompt) * 0.8, score(p.tags.join(' '))) })).filter((x) => x.s).sort((a, b) => b.s - a.s).slice(0, 7);
    const as = actions.map((a) => ({ a, s: score(a[0]) })).filter((x) => x.s).slice(0, 8);
    const actionsFirst = q && as.some((x) => x.s >= 2);
    const pItems = ps.map(({ p }) => ({ run: () => go('#/p/' + p.slug), html: `<div class="th" style="background-image:url('${p.thumbnail || ''}')"></div><div><div>${esc(p.name)}</div><div class="dim" style="font-size:11.5px">${esc(p.prompt.slice(0, 70))}</div></div><span class="sub">${p.kind}</span>` }));
    const aItems = as.map(({ a }) => ({ run: a[2], html: `${icon(a[1])}<span>${a[0]}</span>${a[3] ? `<span class="sub"><kbd>${a[3]}</kbd></span>` : ''}` }));
    const groups = actionsFirst ? [['Actions', aItems], ['Creations', pItems]] : [['Creations', pItems], ['Actions', aItems]];
    items = groups.flatMap((g) => g[1]);
    idx = Math.min(idx, items.length - 1);
    let n = 0;
    res.innerHTML = groups.filter((g) => g[1].length).map(([label, list]) => `<div class="pal-group">${label}</div>` + list.map((it) => { const i = n++; return `<div class="pal-item ${i === idx ? 'on' : ''}" data-i="${i}">${it.html}</div>`; }).join('')).join('');
  };
  inp.oninput = () => { idx = 0; draw(); };
  inp.onkeydown = (e) => {
    if (e.key === 'ArrowDown') { idx = (idx + 1) % items.length; draw(); e.preventDefault(); }
    if (e.key === 'ArrowUp') { idx = (idx - 1 + items.length) % items.length; draw(); e.preventDefault(); }
    if (e.key === 'Enter' && items[idx]) { m.close(); items[idx].run(); }
  };
  res.onclick = (e) => { const it = e.target.closest('[data-i]'); if (it) { m.close(); items[+it.dataset.i].run(); } };
  draw();
  setTimeout(() => inp.focus(), 20);
}

// ============================================================================================== quick look, compare, settings, shortcuts
async function quickLook(p) {
  if (!p.render?.type) return toast('Nothing to preview yet — this request is still queued', { err: true });
  const body = h(`<div class="quicklook"><div class="viewport"><canvas class="gl"></canvas>${p.render.type === 'scene' ? '<canvas class="hud"></canvas>' : ''}<div class="vp-loading"><div><div class="ring"></div>Loading</div></div></div>
    <div class="ql-side"><div style="display:flex;gap:8px;align-items:center">${kindBadge(p.kind)}<span class="status ${p.status}">${p.status}</span><span style="flex:1"></span><button class="btn icon sm ghost" data-x>${icon('x')}</button></div>
    <h2 style="font:700 22px var(--display);margin:12px 0 6px;letter-spacing:-.02em">${esc(p.name)}</h2><p class="muted" style="font-size:13px">${esc(p.prompt)}</p>
    <div class="kv" style="margin:14px 0">${[['Files', p.file_count], ['Size', bytes(p.size)], ['Triangles', num(p.stats?.triangles || 0)], ['Version', 'v' + p.version]].map(([k, v]) => `<div><div class="k">${k}</div><div class="v">${v}</div></div>`).join('')}</div>
    <div style="display:flex;flex-wrap:wrap;gap:6px">${p.tags.map((t) => `<span class="tag">#${esc(t)}</span>`).join('')}</div>
    <div style="display:flex;gap:8px;margin-top:18px"><a class="btn primary" href="#/p/${p.slug}" data-open>${icon('external')}Open studio</a><button class="btn" data-zip>${icon('download')}Export</button></div>
    <p class="dim" style="font-size:12px;margin-top:18px"><kbd>Space</kbd> or <kbd>Esc</kbd> to close</p></div></div>`);
  let stage;
  const m = modal({ body, raw: true, cls: 'wide', onClose: () => stage?.dispose() });
  m.el.style.width = 'auto';
  $('[data-x]', body).onclick = () => m.close();
  $('[data-open]', body).onclick = () => m.close();
  $('[data-zip]', body).onclick = () => exportZip(p);
  const close = (e) => { if (e.key === ' ' && !e.target.closest('input,textarea')) { e.preventDefault(); m.close(); document.removeEventListener('keydown', close, true); } };
  setTimeout(() => document.addEventListener('keydown', close, true), 50);
  stage = await createStage($('canvas.gl', body), p, { autoRotate: true });
  if (stage.controls) stage.controls.autoRotate = p.render.type !== 'scene';
  if (p.render.type === 'scene') stage.attachHud($('canvas.hud', body));
  $('.vp-loading', body)?.remove();
}

function compare(a, b) {
  if (!b) {
    const others = live().filter((x) => x.id !== a.id);
    const m = modal({ title: 'Compare “' + esc(a.name) + '” with…', body: `<div>${others.map((o) => `<div class="pal-item" data-id="${o.id}"><div class="th" style="background-image:url('${o.thumbnail || ''}')"></div><div>${esc(o.name)}</div><span class="sub">${o.kind}</span></div>`).join('')}</div>` });
    m.el.onclick = (e) => { const it = e.target.closest('[data-id]'); if (it) { m.close(); compare(a, byId(it.dataset.id)); } };
    return;
  }
  const rows = [['Type', (p) => p.kind], ['Status', (p) => p.status], ['Files', (p) => p.file_count], ['Bundle size', (p) => bytes(p.size)], ['Triangles', (p) => num(p.stats?.triangles || 0)],
    ['Textures', (p) => p.stats?.textures ?? '—'], ['Shader stages', (p) => p.stats?.shaders ?? '—'], ['Variants', (p) => (p.variants || []).length], ['Version', (p) => 'v' + p.version],
    ['Rating', (p) => '★'.repeat(p.rating) || '—'], ['Generated in', (p) => (p.stats?.generated_in_s ? p.stats.generated_in_s + 's' : '—')], ['Created', (p) => ago(p.created_at)]];
  const col = (p) => `<div><div class="th" style="background-image:url('${p.thumbnail || ''}')"></div><h3 style="font:700 17px var(--display);margin:12px 0 4px">${esc(p.name)}</h3><p class="muted" style="font-size:12.5px;margin:0 0 6px">${esc(p.prompt)}</p>
    <table>${rows.map(([l, f]) => `<tr><td class="muted">${l}</td><td>${f(p)}</td></tr>`).join('')}</table><div style="margin-top:8px">${Object.entries(p.kinds).map(([k, n]) => `<span class="tag" style="margin:2px">${n} ${k}</span>`).join('')}</div></div>`;
  modal({ title: `${icon('compare')} Compare`, body: `<div class="compare">${col(a)}${col(b)}</div>`, cls: 'wide' });
}

function openSettings() {
  const body = h(`<div>
    <div class="section"><h4>Appearance</h4><div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap"><div class="seg"><button data-th="dark" class="${prefs.theme === 'dark' ? 'on' : ''}">${icon('moon')}Dark</button><button data-th="light" class="${prefs.theme === 'light' ? 'on' : ''}">${icon('sun')}Light</button></div>
      ${Object.entries(ACCENTS).map(([k, [a, b]]) => `<span data-ac="${k}" title="${k}" style="width:30px;height:30px;border-radius:10px;cursor:pointer;background:linear-gradient(135deg,${a},${b});outline:${prefs.accent === k ? '2px solid var(--text)' : 'none'};outline-offset:2px"></span>`).join('')}</div></div>
    <div class="section"><h4>Library</h4><label style="display:flex;gap:10px;align-items:center"><input type="checkbox" data-auto ${prefs.autoPreviews ? 'checked' : ''}> Render missing previews automatically (WebGL, in this browser)</label>
      <div style="display:flex;gap:8px;margin-top:12px"><button class="btn sm" data-rerender>${icon('camera')}Re-render all previews</button><button class="btn sm" data-keys>${icon('keyboard')}Shortcuts</button></div></div>
    <div class="section"><h4>About</h4><p class="muted" style="font-size:13px;margin:0">Project-TheCreator · SQLite catalogue <code class="mono">thecreator.db</code> + file vault <code class="mono">vault/projects/*</code>. Every file is SHA-256 addressed, versioned and dependency-linked. CLI: <code class="mono">python3 cli.py --help</code></p></div></div>`);
  const m = modal({ title: `${icon('settings')} Settings`, body });
  body.onclick = (e) => {
    const t = e.target.closest('[data-th],[data-ac],[data-rerender],[data-keys]');
    if (!t) return;
    if (t.dataset.th) prefs.theme = t.dataset.th;
    if (t.dataset.ac) prefs.accent = t.dataset.ac;
    if ('rerender' in t.dataset) { m.close(); ensurePreviews(true); }
    if ('keys' in t.dataset) { m.close(); openShortcuts(); }
    savePrefs(); applyTheme(); renderTopbar();
    if (t.dataset.th || t.dataset.ac) { m.close(); openSettings(); }
  };
  $('[data-auto]', body).onchange = (e) => { prefs.autoPreviews = e.target.checked; savePrefs(); };
}

function openShortcuts() {
  const rows = [['⌘K', 'Command palette'], ['/', 'Search'], ['N', 'New creation request'], ['?', 'This help'], ['Esc', 'Close / clear selection'],
    ['Space', 'Quick look hovered card'], ['↵', 'Open hovered card'], ['F', 'Favourite hovered card'], ['P', 'Pin'], ['R', 'Rename'], ['T', 'Tags'], ['D', 'Duplicate'], ['E', 'Export ZIP'], ['L', 'Lock'], ['A', 'Archive'], ['⌫', 'Move to trash'],
    ['1–6', 'Studio: render mode'], ['Space', 'Studio: play / pause animation'], ['← →', 'Studio: step one frame'], ['F', 'Studio: fullscreen'], ['R', 'Studio: reset camera']];
  modal({ title: `${icon('keyboard')} Keyboard shortcuts`, body: `<div style="columns:2;column-gap:30px">${rows.map(([k, l]) => `<div style="display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid var(--line);break-inside:avoid"><span>${l}</span><kbd>${k}</kbd></div>`).join('')}</div>`, cls: 'wide' });
}

// ============================================================================================== uploads + previews
async function uploadFiles(p, files) {
  const list = [...files];
  if (!list.length) return;
  const t = toast(`Uploading ${list.length} file(s) into ${esc(p.name)}…`, { progress: 0 });
  for (const [i, f] of list.entries()) {
    const data = await new Promise((r) => { const fr = new FileReader(); fr.onload = () => r(fr.result); fr.readAsDataURL(f); });
    await api(`/projects/${p.id}/assets`, { method: 'POST', body: { name: f.name, data } });
    t.set(`Uploaded ${i + 1}/${list.length}`, (i + 1) / list.length);
  }
  await refresh();
  t.done(`Added ${list.length} file(s) to <b>${esc(p.name)}</b> — catalogued & hashed`);
}

let previewBusy = false;
async function ensurePreviews(force = false) {
  if (previewBusy) return;
  const todo = live().filter((p) => p.render?.type && (force || !p.thumbnail));
  if (!todo.length) return;
  previewBusy = true;
  const t = toast(`Rendering ${todo.length} preview${todo.length > 1 ? 's' : ''} with WebGL…`, { progress: 0 });
  for (const [i, p] of todo.entries()) {
    try { await renderPreview(p); } catch (e) { console.error(e); toast('Preview failed for ' + esc(p.name) + ': ' + esc(e.message), { err: true }); }
    t.set(`Rendered ${i + 1}/${todo.length} · ${esc(p.name)}`, (i + 1) / todo.length);
    await refresh();
  }
  t.done(`Previews ready · hover a card to scrub its 16-frame strip`);
  previewBusy = false;
}
async function renderPreview(p) {
  const canvas = document.createElement('canvas');
  canvas.width = 480; canvas.height = 320;
  const stage = await createStage(canvas, p, { interactive: false, width: 480, height: 320, capture: true, pixelRatio: 1 });
  try {
    for (let i = 0; i < 4; i++) stage.tick(1 / 30);
    const cap = await stage.capture();
    await api(`/projects/${p.id}/preview`, { method: 'POST', body: cap });
  } finally { stage.dispose(); }
}
hooks.openForge = openForge;
hooks.quickLook = quickLook;
hooks.compare = (p) => compare(p);
hooks.uploadFiles = uploadFiles;
hooks.rerenderPreview = async (p) => { const t = toast('Rendering preview…', { progress: 0.4 }); await renderPreview(p); await refresh(); t.done('Preview updated'); };

// ============================================================================================== keyboard
function bindKeys() {
  document.addEventListener('keydown', (e) => {
    const typing = e.target.closest('input, textarea, select, [contenteditable]');
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); return openPalette(); }
    if (typing || document.querySelector('.modal-back')) return;
    if (e.key === '/') { e.preventDefault(); $('#q')?.focus(); return; }
    if (e.key === 'n' || e.key === 'N') { e.preventDefault(); return openForge(); }
    if (e.key === '?') return openShortcuts();
    if (e.key === 'Escape' && state.selected.size) { state.selected.clear(); state.selectMode = false; return renderLibrary(true); }
    if (route.name !== 'library' || !state.hover) return;
    const p = byId(state.hover);
    if (!p) return;
    const k = e.key.toLowerCase();
    const map = { f: () => patch(p, { favorite: p.favorite ? 0 : 1 }, p.favorite ? 'Removed from favourites' : 'Added to favourites'), p: () => patch(p, { pinned: p.pinned ? 0 : 1 }, p.pinned ? 'Unpinned' : 'Pinned'),
      r: () => rename(p), t: () => editTags(p), d: () => duplicate(p), e: () => exportZip(p), l: () => patch(p, { locked: p.locked ? 0 : 1 }, p.locked ? 'Unlocked' : 'Locked'),
      a: () => patch(p, { archived: p.archived ? 0 : 1 }, p.archived ? 'Unarchived' : 'Archived'), backspace: () => trash(p), delete: () => trash(p), ' ': () => quickLook(p), enter: () => go('#/p/' + p.slug) };
    if (map[k]) { e.preventDefault(); map[k](); }
  });
  let dragDepth = 0;
  window.addEventListener('dragenter', (e) => { if (e.dataTransfer.types.includes('Files') && route.name === 'library') { dragDepth++; $('#drop-overlay').classList.add('show'); } });
  window.addEventListener('dragleave', () => { if (--dragDepth <= 0) { dragDepth = 0; $('#drop-overlay').classList.remove('show'); } });
  window.addEventListener('drop', () => { dragDepth = 0; $('#drop-overlay').classList.remove('show'); });
  window.addEventListener('dragover', (e) => e.preventDefault());
}

// ============================================================================================== boot
(async function boot() {
  applyTheme();
  bindSidebar();
  bindTopbar();
  bindLibrary();
  bindBulkbar();
  bindKeys();
  await refresh();
  window.addEventListener('hashchange', onRoute);
  await onRoute();
  if (prefs.autoPreviews) setTimeout(() => ensurePreviews(), 600);
})();
