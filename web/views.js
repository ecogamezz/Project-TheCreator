// Project studio, vault explorer, activity feed, file inspector.
import { $, $$, api, ago, bytes, byId, dateTime, debounce, esc, go, h, highlight, hooks, icon, KIND_COLOR, KIND_HEX, KIND_ICON, kindBadge,
  modal, num, patch, projectMenu, contextMenu, refresh, state, toast, editTags, moveTo, exportZip, duplicate, copy } from './core.js';
import { createStage, previewMesh, fetchText, fetchJSON, drawBitmapText, defaultVariants } from './engine.js';

let live = [];
export function disposeView() { live.forEach((d) => d?.dispose?.()); live = []; }
const fileUrl = (p, a) => `/vault/projects/${p.slug}/${a.path}`;
const extOf = (path) => path.split('.').pop().toLowerCase();

// =============================================================================================== PROJECT STUDIO
const MODES = [['shader', 'GLSL'], ['pbr', 'PBR'], ['clay', 'Clay'], ['wire', 'Wire'], ['normals', 'Normals'], ['uv', 'UV']];
const FIELD_COLORS = { kind: '#8b5cf6', poly_budget: '#f5b942', subject: '#22d3ee', styles: '#ff6bb5', materials: '#f5b942', effects: '#34d399', motions: '#fb923c', colors: '#f87171', deliverables: '#a78bfa' };

export async function renderProject(view, slug) {
  let p = await api('/projects/' + slug);
  api(`/projects/${p.id}/open`, { method: 'POST' });
  const ready = !!p.render?.type;
  const isScene = p.render?.type === 'scene', isModule = p.render?.type === 'module';
  const isAnim = p.render?.type === 'animation' || (isModule && !!p.render.timeline);
  const modes = isModule ? p.render.modes || [] : MODES;
  view.innerHTML = `
  <div class="project">
    <div class="viewport" id="vp">
      <canvas class="gl" tabindex="0"></canvas>${isScene ? '<canvas class="hud"></canvas>' : ''}
      ${ready ? `<div class="vp-loading"><div style="text-align:center"><div class="ring"></div>Assembling bundle…</div></div>` : queuedViewport(p)}
      ${ready ? `
      <div class="vp-top">
        ${isScene ? `<div class="glass seg"><button data-cin class="on">${icon('camera')}Cinematic</button><button data-orbit>${icon('orbit')}Free orbit</button></div>`
        : modes.length ? `<div class="glass seg" id="modes">${modes.map(([m, l], i) => `<button data-mode="${m}" class="${i === 0 ? 'on' : ''}">${l}</button>`).join('')}</div>` : ''}
        <div class="grow"></div>
        <div class="glass" style="display:flex;padding:2px">
          ${isModule ? `<button class="btn sm icon" data-rot title="Auto-rotate">${icon('orbit')}</button>` : isScene ? `<button class="btn sm on" data-hud title="HUD font overlay">${icon('font')}HUD</button>` : `<button class="btn sm icon" data-rot title="Auto-rotate">${icon('orbit')}</button><button class="btn sm icon" data-grid title="Grid">${icon('hash')}</button>`}
          <button class="btn sm icon" data-reset title="Reset view (R)">${icon('refresh')}</button>
          <button class="btn sm icon" data-shot title="Screenshot">${icon('camera')}</button>
          <button class="btn sm" data-thumb title="Use current view as the library preview">${icon('preview')}Set preview</button>
          <button class="btn sm icon" data-full title="Fullscreen (F)">${icon('maximize')}</button>
        </div>
      </div>
      <div class="glass variant-bar" id="vbar"></div>
      ${isAnim ? `<div class="glass timeline"><button class="btn icon sm" data-play>${icon('pause')}</button><div class="tl-clip mono"></div><div class="tl-track"><div class="tl-bar"></div><div class="tl-fill"></div><div class="tl-head"></div></div><div class="tl-time">0.00s · f0</div><div class="seg">${[0.25, 0.5, 1, 2].map((s) => `<button data-speed="${s}" class="${s === 1 ? 'on' : ''}">${s}×</button>`).join('')}</div></div>` : ''}
      <div class="glass vp-stats" id="vstats">…</div>` : ''}
    </div>
    <aside class="inspector" id="insp"></aside>
  </div>`;
  const insp = $('#insp', view);
  renderInspector(insp, p);
  if (!ready) return bindQueued(view, p);

  const vp = $('#vp', view);
  let stage;
  try {
    stage = await createStage($('canvas.gl', vp), p, {});
  } catch (e) {
    $('.vp-loading', vp).innerHTML = `<div style="color:#fca5a5">${esc(e.message)}</div>`;
    return;
  }
  live.push(stage);
  window.__stage = stage;   // handy for debugging from the console
  $('.vp-loading', vp)?.remove();
  stage.on('error', (msg) => { vp.append(h(`<div class="glass vp-error">${esc(msg).slice(0, 600)}</div>`)); });
  if (isScene) stage.attachHud($('canvas.hud', vp));

  // toolbar
  vp.addEventListener('click', async (e) => {
    const b = e.target.closest('button');
    if (!b) return;
    if (b.dataset.mode) { $$('[data-mode]', vp).forEach((x) => x.classList.toggle('on', x === b)); await stage.setMode(b.dataset.mode); }
    if ('rot' in b.dataset) { stage.controls.autoRotate = !stage.controls.autoRotate; b.classList.toggle('on', stage.controls.autoRotate); }
    if ('grid' in b.dataset) { b.classList.toggle('on'); stage.setGrid?.(b.classList.contains('on')); }
    if ('reset' in b.dataset) stage.resetView();
    if ('cin' in b.dataset) { stage.setCinematic(true); syncCin(true); }
    if ('orbit' in b.dataset) { stage.setCinematic(false); syncCin(false); }
    if ('hud' in b.dataset) { b.classList.toggle('on'); stage.setHud(b.classList.contains('on')); }
    if ('full' in b.dataset) vp.requestFullscreen?.();
    if ('shot' in b.dataset) { stage.tick(0); const a = document.createElement('a'); a.href = stage.composite(); a.download = p.slug + '-' + Date.now() + '.png'; a.click(); toast('Screenshot saved'); }
    if ('thumb' in b.dataset) {
      const t = toast('Rendering preview + 16-frame strip…', { progress: 0.2 });
      const cap = await stage.capture();
      const res = await api(`/projects/${p.id}/preview`, { method: 'POST', body: cap });
      Object.assign(byId(p.id) || {}, res);
      t.done('Library preview updated');
    }
    if ('play' in b.dataset) { stage.playing = !stage.playing; b.innerHTML = icon(stage.playing ? 'pause' : 'play'); }
    if (b.dataset.speed) { stage.speed = +b.dataset.speed; $$('[data-speed]', vp).forEach((x) => x.classList.toggle('on', x === b)); }
  });
  const syncCin = (on) => { $('[data-cin]', vp)?.classList.toggle('on', on); $('[data-orbit]', vp)?.classList.toggle('on', !on); };
  stage.on('cinematic', syncCin);

  // variants
  const vbar = $('#vbar', vp);
  const sel = defaultVariants(p);
  const groups = {};
  (p.variants || []).forEach((v) => (groups[v.group] ||= []).push(v));
  const drawVariants = () => {
    vbar.innerHTML = Object.entries(groups).map(([g, vs]) => `<div><div class="g">${esc(g)}</div><div class="opts">${vs.map((v) =>
      `<span class="vchip ${sel[g] === v.id ? 'on' : ''}" data-v="${v.id}" data-g="${esc(g)}">${v.swatch ? `<i style="background:${v.swatch}"></i>` : ''}${esc(v.name)}</span>`).join('')}</div></div>`).join('');
    if (!Object.keys(groups).length) vbar.remove();
  };
  drawVariants();
  vbar.addEventListener('click', async (e) => {
    const c = e.target.closest('[data-v]');
    if (!c) return;
    sel[c.dataset.g] = c.dataset.v;
    drawVariants();
    await stage.setVariants(sel);
    $('[data-mode].on', vp) && (await stage.setMode($('[data-mode].on', vp).dataset.mode));
  });
  hooks.applyVariant = async (g, id) => { sel[g] = id; drawVariants(); await stage.setVariants(sel); };

  // timeline
  if (isAnim) {
    const track = $('.tl-track', vp), fill = $('.tl-fill', vp), head = $('.tl-head', vp), tm = $('.tl-time', vp);
    const evColors = { impact: '#f87171', launch: '#4fb3ff', regen: '#34d399', restored: '#34d399', fade: '#fbbf24', anticipation: '#a78bfa', gust: '#fbbf24', hit: '#f87171', step: '#64748b', fall: '#f87171' };
    const drawEvents = () => {
      $$('.tl-ev', track).forEach((e) => e.remove());
      (stage.events || []).forEach((ev, i) => track.append(h(`<div class="tl-ev" title="${esc(ev.label)} @ ${ev.t}s" style="left:${(ev.t / stage.duration) * 100}%;--evc:${evColors[ev.type] || '#aab'};${i % 2 ? 'top:-12px' : ''}">${esc(ev.label.split(/[·+]/)[0].trim())}</div>`)));
      $('.tl-clip', vp).textContent = stage.api?.clipName?.() || '';
    };
    drawEvents();
    stage.on('clip', () => { stage.syncTimeline?.(); drawEvents(); });
    let drag = false;
    const seekTo = (e) => { const r = track.getBoundingClientRect(); stage.seek(Math.max(0, Math.min(1, (e.clientX - r.left) / r.width)) * stage.duration); };
    track.addEventListener('pointerdown', (e) => { drag = true; track.setPointerCapture(e.pointerId); seekTo(e); });
    track.addEventListener('pointermove', (e) => drag && seekTo(e));
    track.addEventListener('pointerup', () => (drag = false));
    stage.on('frame', (t) => {
      const d = stage.duration || 1;
      const tt = stage.api?.clipTime ? stage.api.clipTime() : ((t % d) + d) % d;
      const pct = Math.min(100, (tt / d) * 100);
      fill.style.width = pct + '%'; head.style.left = pct + '%';
      tm.textContent = tt.toFixed(2) + 's · f' + Math.floor(tt * (stage.api?.fps || stage.anim?.fps || 60));
    });
  }

  // plug-in controls (declared by the bundle's viewer module)
  if (isModule && stage.controlsSpec.length) {
    const panel = h(`<div class="glass ctl-panel"></div>`);
    const draw = () => {
      panel.innerHTML = stage.controlsSpec.map((c, i) => {
        const v = c.get();
        if (c.type === 'select') return `<div class="ctl"><div class="g">${esc(c.label)}</div><div class="opts">${c.options.map(([val, l]) => `<span class="vchip ${v === val ? 'on' : ''}" data-ci="${i}" data-val="${esc(val)}">${esc(l)}</span>`).join('')}</div></div>`;
        if (c.type === 'toggle') return `<div class="ctl"><label class="tgl"><input type="checkbox" data-ci="${i}" ${v ? 'checked' : ''}> ${esc(c.label)}</label></div>`;
        if (c.type === 'range') return `<div class="ctl"><div class="g">${esc(c.label)} <span class="mono" data-out="${i}">${(+v).toFixed(c.step < 1 ? 2 : 0)}</span></div><input type="range" class="range" style="width:100%" data-ci="${i}" min="${c.min}" max="${c.max}" step="${c.step || 0.01}" value="${v}"></div>`;
        if (c.type === 'color') return `<div class="ctl"><label class="tgl"><input type="color" data-ci="${i}" value="${v}"> ${esc(c.label)}</label></div>`;
        return '';
      }).join('');
    };
    draw();
    panel.addEventListener('click', (e) => { const o = e.target.closest('[data-val]'); if (o) { stage.controlsSpec[+o.dataset.ci].set(o.dataset.val); draw(); } });
    panel.addEventListener('input', (e) => {
      const el = e.target, c = stage.controlsSpec[+el.dataset.ci];
      if (!c) return;
      c.set(el.type === 'checkbox' ? el.checked : el.type === 'range' ? +el.value : el.value);
      const out = $(`[data-out="${el.dataset.ci}"]`, panel); if (out) out.textContent = (+el.value).toFixed(c.step < 1 ? 2 : 0);
    });
    stage.on('controls', draw);
    vp.append(panel);
  }

  // stats overlay
  let frames = 0, last = performance.now();
  stage.on('frame', () => frames++);
  const statsEl = $('#vstats', vp);
  const iv = setInterval(() => {
    if (!document.body.contains(statsEl)) return clearInterval(iv);
    const now = performance.now(), fps = Math.round((frames * 1000) / (now - last));
    frames = 0; last = now;
    const i = stage.info();
    statsEl.innerHTML = `<b>${fps}</b> fps · <b>${num(i.tris)}</b> tris<br>${i.meshes} meshes · ${i.calls} draw calls<br>${i.programs} GLSL programs · ${i.textures} textures${isScene ? `<br>internal <b>${stage.rt.width}×${stage.rt.height}</b>` : ''}${stage.api?.statsLine ? '<br>' + stage.api.statsLine() : ''}`;
  }, 500);
  live.push({ dispose: () => clearInterval(iv) });

  // keyboard
  const key = (e) => {
    if (e.target.closest('input, textarea, [contenteditable]')) return;
    if (e.key === ' ' && isAnim) { e.preventDefault(); $('[data-play]', vp).click(); }
    if (e.key === 'f') vp.requestFullscreen?.();
    if (e.key === 'r') stage.resetView();
    if (/^[1-6]$/.test(e.key) && modes.length && !isScene) $$('[data-mode]', vp)[+e.key - 1]?.click();
    if (isAnim && e.key === 'ArrowRight') stage.seek((stage.api?.clipTime?.() ?? stage.time) + 1 / 60);
    if (isAnim && e.key === 'ArrowLeft') stage.seek((stage.api?.clipTime?.() ?? stage.time) - 1 / 60);
  };
  document.addEventListener('keydown', key);
  live.push({ dispose: () => document.removeEventListener('keydown', key) });

  // first visit: generate the library preview from this live stage if none exists yet
  if (!p.thumbnail) setTimeout(async () => {
    if (stage.disposed) return;
    const cap = await stage.capture();
    await api(`/projects/${p.id}/preview`, { method: 'POST', body: cap });
  }, 1500);
}

function queuedViewport(p) {
  const steps = p.pipeline || [];
  const done = steps.filter((s) => s.state === 'done').length;
  return `<div class="vp-loading" style="background:none"><div style="text-align:center;max-width:460px;text-transform:none;letter-spacing:0">
    <div class="thumb" style="width:300px;margin:0 auto 22px;border-radius:18px;--cl:${p.color_label || 'var(--accent)'}"><div class="placeholder"><div class="orb"></div></div><div class="shimmer"></div></div>
    <div style="font:700 20px var(--display);color:#fff">Queued for creation</div>
    <p style="color:#9aa0b8;font:13px/1.6 var(--font)">Interpreted as a <b style="color:#fff">${esc(p.kind)}</b> request with ${steps.length} pipeline stages (${done} done).<br>
    A generator delivers files into <code class="mono">vault/projects/${esc(p.slug)}/</code> — or drop files here to attach them by hand.</p>
    <button class="btn primary" data-upload>${icon('upload')}Attach files…</button>
    <input type="file" multiple hidden data-file>
  </div></div>`;
}
function bindQueued(view, p) {
  const inp = $('[data-file]', view);
  $('[data-upload]', view).onclick = () => inp.click();
  inp.onchange = () => hooks.uploadFiles?.(p, inp.files).then(() => renderProject(view, p.slug));
  const vp = $('#vp', view);
  vp.addEventListener('dragover', (e) => e.preventDefault());
  vp.addEventListener('drop', (e) => { e.preventDefault(); hooks.uploadFiles?.(p, e.dataTransfer.files).then(() => renderProject(view, p.slug)); });
}

function renderInspector(insp, p) {
  const folder = state.folders.find((f) => f.id === p.folder_id);
  const tabs = [['overview', 'Overview'], ['files', 'Files', p.assets.length], ['graph', 'Graph', p.dependencies.length], ['variants', 'Variants', (p.variants || []).length], ['history', 'History', p.versions.length], ['notes', 'Notes']];
  insp.innerHTML = `
    <div class="insp-head">
      <div style="display:flex;align-items:center;gap:8px">${kindBadge(p.kind)}<span class="status ${p.status}">${p.status}</span><span class="grow" style="flex:1"></span>
        <span class="muted" style="font-size:12px">${icon('folder')} ${esc(folder?.name || 'Library')}</span></div>
      <h1>${p.color_label ? `<span style="width:12px;height:12px;border-radius:4px;background:${p.color_label};flex:none"></span>` : ''}<span contenteditable spellcheck="false" data-name>${esc(p.name)}</span>${p.locked ? `<span class="lock-badge" title="Locked">${icon('lock')}</span>` : ''}</h1>
      <div class="stars" data-rate>${[1, 2, 3, 4, 5].map((r) => `<svg class="i ${r <= p.rating ? 'on' : ''}" data-r="${r}" viewBox="0 0 24 24"><path d="M12 3l2.7 5.6 6.1.9-4.4 4.3 1 6.1L12 17l-5.4 2.9 1-6.1L3.2 9.5l6.1-.9z"/></svg>`).join('')}</div>
      <div class="insp-actions">
        <button class="btn sm ${p.favorite ? 'on' : ''}" data-a="fav">${icon('star')}${p.favorite ? 'Favourite' : 'Favourite'}</button>
        <button class="btn sm ${p.pinned ? 'on' : ''}" data-a="pin">${icon('pin')}Pin</button>
        <button class="btn sm" data-a="tags">${icon('tag')}Tags</button>
        <button class="btn sm" data-a="move">${icon('move')}Move</button>
        <button class="btn sm" data-a="zip">${icon('download')}Export</button>
        <button class="btn sm icon" data-a="more">${icon('more')}</button>
      </div>
    </div>
    <div class="tabs">${tabs.map(([k, l, n], i) => `<button data-tab="${k}" class="${i ? '' : 'on'}">${l}${n != null ? `<span class="n">${n}</span>` : ''}</button>`).join('')}</div>
    <div class="insp-body" id="ibody"></div>`;
  const body = $('#ibody', insp);
  const show = (tab) => { $$('[data-tab]', insp).forEach((b) => b.classList.toggle('on', b.dataset.tab === tab)); TABS[tab](body, p); body.scrollTop = 0; };
  insp.addEventListener('click', async (e) => {
    const t = e.target.closest('[data-tab]');
    if (t) return show(t.dataset.tab);
    const r = e.target.closest('[data-r]');
    if (r) { await patch(p, { rating: +r.dataset.r === p.rating ? 0 : +r.dataset.r }, 'Rated ' + r.dataset.r + '/5'); return reloadInspector(insp, p.slug); }
    const a = e.target.closest('[data-a]')?.dataset.a;
    if (!a) return;
    const sp = byId(p.id) || p;
    if (a === 'fav') { await patch(sp, { favorite: p.favorite ? 0 : 1 }, p.favorite ? 'Removed from favourites' : 'Added to favourites'); reloadInspector(insp, p.slug); }
    if (a === 'pin') { await patch(sp, { pinned: p.pinned ? 0 : 1 }, p.pinned ? 'Unpinned' : 'Pinned'); reloadInspector(insp, p.slug); }
    if (a === 'tags') { await editTags(sp); }
    if (a === 'zip') exportZip(p);
    if (a === 'move') {
      const rect = e.target.closest('button').getBoundingClientRect();
      contextMenu(rect.left, rect.bottom + 6, [{ label: 'Library root', icon: 'layers', run: () => moveTo(sp, null).then(() => reloadInspector(insp, p.slug)) },
        ...state.folders.map((f) => ({ label: f.name, icon: 'folder', run: () => moveTo(sp, f.id).then(() => reloadInspector(insp, p.slug)) }))]);
    }
    if (a === 'more') { const rect = e.target.closest('button').getBoundingClientRect(); contextMenu(rect.right - 240, rect.bottom + 6, projectMenu(sp)); }
  });
  const nm = $('[data-name]', insp);
  nm.addEventListener('keydown', (e) => { if (e.key === 'Enter') { e.preventDefault(); nm.blur(); } });
  nm.addEventListener('blur', async () => { const v = nm.textContent.trim(); if (v && v !== p.name) { await patch(byId(p.id) || p, { name: v }, 'Renamed'); p.name = v; $('#crumb-name') && ($('#crumb-name').textContent = v); } });
  show('overview');
}
async function reloadInspector(insp, slug) { const p = await api('/projects/' + slug); renderInspector(insp, p); }

function highlightPrompt(p) {
  let html = esc(p.prompt || '');
  const hits = (p.spec?.explain || []).filter((x) => x.because && x.because !== 'default');
  for (const hit of hits) {
    for (const word of String(hit.because).split(', ')) {
      if (word.length < 2) continue;
      const rx = new RegExp('(' + word.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + ')', 'i');
      html = html.replace(rx, `<mark style="--mc:${FIELD_COLORS[hit.field] || '#8b5cf6'}" title="${hit.field}">$1</mark>`);
    }
  }
  return html;
}

const STAT_LABELS = { triangles: 'Triangles', vertices: 'Vertices', budget: 'Poly budget', budget_used: 'Budget used %', parts: 'Mesh parts', materials: 'Materials',
  textures: 'Textures', shaders: 'Shader stages', lods: 'LOD levels', unique_meshes: 'Unique meshes', instances: 'Instances', clouds: 'Cloud cards',
  particles: 'Particles', internal_resolution: 'Internal res', max_texture: 'Max texture', pieces: 'Pieces', shards_broken: 'Shards broken', fps: 'FPS',
  duration: 'Duration (s)', frames: 'Baked frames', events: 'Events', loop: 'Loop', generated_in_s: 'Generated in (s)' };

const TABS = {
  overview(body, p) {
    const s = p.stats || {};
    const kv = Object.entries(s).filter(([k, v]) => STAT_LABELS[k] && typeof v !== 'object');
    const bars = s.per_part || s.per_mesh;
    const maxBar = bars ? Math.max(...Object.values(bars)) : 1;
    const spec = p.spec || {};
    const chips = [['kind', spec.kind], ['subject', spec.subject], ['budget', spec.poly_budget && num(spec.poly_budget) + ' polys'], ...(spec.styles || []).map((x) => ['style', x]),
      ...(spec.materials || []).map((x) => ['material', x]), ...(spec.effects || []).map((x) => ['effect', x]), ...(spec.motions || []).map((x) => ['motion', x])].filter((c) => c[1]);
    body.innerHTML = `
      <div class="section"><h4>${icon('sparkles')}Original prompt<span class="grow"></span><button class="btn ghost sm" data-copy>${icon('copy')}</button><button class="btn ghost sm" data-remix>${icon('wand')}Remix</button></h4>
        <div class="prompt-box">${highlightPrompt(p)}</div>
        <div class="forge-chips">${chips.map(([k, v]) => `<span class="parse-chip"><b>${k}</b>${esc(v)}</span>`).join('')}</div></div>
      ${s.budget ? `<div class="section"><h4>${icon('object')}Polygon budget</h4><div class="box"><div style="display:flex;justify-content:space-between"><b style="font:700 20px var(--display)">${num(s.triangles)} <span class="muted" style="font-size:13px">/ ${num(s.budget)}</span></b><span class="mono muted">${s.budget_used}%</span></div><div class="budget" style="height:8px"><i style="width:${s.budget_used}%"></i></div></div></div>` : ''}
      <div class="section"><h4>${icon('info')}Stats</h4><div class="kv">${kv.map(([k, v]) => `<div><div class="k">${STAT_LABELS[k]}</div><div class="v">${typeof v === 'number' ? num(v) : esc(v)}</div></div>`).join('')}
        <div><div class="k">Files</div><div class="v">${p.file_count}</div></div><div><div class="k">Bundle size</div><div class="v">${bytes(p.size)}</div></div></div></div>
      ${bars ? `<div class="section"><h4>${icon('layers')}Triangles per ${s.per_part ? 'part' : 'mesh'}</h4><div class="bars">${Object.entries(bars).sort((a, b) => b[1] - a[1]).map(([k, v]) => `<div class="row"><span>${esc(k.replace(/_/g, ' '))}</span><div class="track"><i style="width:${(v / maxBar) * 100}%"></i></div><span class="num">${num(v)}</span></div>`).join('')}</div></div>` : ''}
      <div class="section"><h4>${icon('activity')}Creation pipeline</h4><div class="pipeline">${(p.pipeline || []).map((st) => `<div class="pipe-step ${st.state}"><div class="dot">${st.state === 'done' ? icon('check') : ''}</div><div><div class="t">${esc(st.stage)}</div>${st.note ? `<div class="n">${esc(st.note)}</div>` : ''}</div></div>`).join('')}</div></div>
      <div class="section"><h4>${icon('database')}Record</h4><div class="kv">
        <div><div class="k">Project ID</div><div class="v mono" style="font-size:12px">${p.id}</div></div><div><div class="k">Vault path</div><div class="v mono" style="font-size:12px">projects/${esc(p.slug)}</div></div>
        <div><div class="k">Created</div><div class="v" style="font-size:13px">${dateTime(p.created_at)}</div></div><div><div class="k">Updated</div><div class="v" style="font-size:13px">${ago(p.updated_at)}</div></div>
        <div><div class="k">Version</div><div class="v">v${p.version}</div></div><div><div class="k">Opened</div><div class="v">${p.views}×</div></div></div></div>`;
    $('[data-copy]', body).onclick = () => copy(p.prompt, 'Prompt copied');
    $('[data-remix]', body).onclick = () => hooks.openForge?.(p.prompt);
  },
  files(body, p) {
    const groups = {};
    p.assets.forEach((a) => (groups[a.kind] ||= []).push(a));
    const order = ['manifest', 'scene', 'animation', 'mesh', 'material', 'shader', 'texture', 'particles', 'font', 'preview', 'data'];
    body.innerHTML = `<div style="display:flex;gap:8px;margin-bottom:14px"><button class="btn sm" data-up>${icon('upload')}Add files</button><button class="btn sm" data-rescan>${icon('refresh')}Rescan folder</button><button class="btn sm" data-vault>${icon('database')}Open in vault</button><input type="file" multiple hidden></div>` +
      Object.keys(groups).sort((a, b) => order.indexOf(a) - order.indexOf(b)).map((k) => `<div class="file-group"><h5>${icon(KIND_ICON[k] || 'file')}${k}<span class="dim mono" style="font-size:11px">${groups[k].length} · ${bytes(groups[k].reduce((s, a) => s + a.size, 0))}</span></h5>
      ${groups[k].map((a) => `<div class="file-row" data-id="${a.id}"><div class="fi" style="--kc:${KIND_HEX[a.kind] || '#888'};${extOf(a.path) === 'png' ? `background-image:url('${fileUrl(p, a)}')` : ''}">${extOf(a.path) === 'png' ? '' : icon(KIND_ICON[a.kind] || 'file')}</div>
        <div style="min-width:0"><div class="nm">${esc(a.path)}</div><div class="rl">${esc(a.role || a.mime)}${a.variant ? ` · <span class="tag">${esc(a.variant)}</span>` : ''}</div></div><div class="sz">${bytes(a.size)}</div></div>`).join('')}</div>`).join('');
    body.onclick = async (e) => {
      const row = e.target.closest('[data-id]');
      if (row) return openFile(p, p.assets.find((a) => a.id === row.dataset.id));
      if (e.target.closest('[data-up]')) $('input[type=file]', body).click();
      if (e.target.closest('[data-vault]')) go('#/vault/' + p.slug);
      if (e.target.closest('[data-rescan]')) { const r = await api(`/projects/${p.id}/rescan`, { method: 'POST' }); toast(r.added.length ? `Registered ${r.added.length} new files` : 'Catalogue already matches the folder'); }
    };
    $('input[type=file]', body).onchange = (e) => hooks.uploadFiles?.(p, e.target.files);
  },
  graph(body, p) {
    body.innerHTML = `<div class="section"><h4>${icon('graph')}Dependency graph<span class="grow"></span><button class="btn sm" data-big>${icon('maximize')}Expand</button></h4>
      <p class="muted" style="font-size:12.5px;margin:0 0 10px">Every edge is a row in the <code class="mono">dependencies</code> table: what each file needs to render. Hover to trace, click to inspect.</p>
      <div class="graph-wrap"></div></div>`;
    drawGraph($('.graph-wrap', body), p, true);
    $('[data-big]', body).onclick = () => { const m = modal({ title: 'Dependency graph · ' + esc(p.name), body: '<div class="graph-wrap" style="max-height:72vh"></div>', cls: 'wide' }); drawGraph($('.graph-wrap', m.el), p, false); };
  },
  variants(body, p) {
    const groups = {};
    (p.variants || []).forEach((v) => (groups[v.group] ||= []).push(v));
    body.innerHTML = Object.keys(groups).length ? Object.entries(groups).map(([g, vs]) => `<div class="section"><h4>${icon('layers')}${esc(g)}</h4>${vs.map((v) => `
      <div class="box" style="margin-bottom:8px;cursor:pointer" data-g="${esc(g)}" data-v="${v.id}"><div style="display:flex;align-items:center;gap:10px">${v.swatch ? `<span style="width:22px;height:22px;border-radius:7px;background:${v.swatch}"></span>` : icon('layers')}<b>${esc(v.name)}</b>${v.default ? '<span class="tag">default</span>' : ''}<span class="grow" style="flex:1"></span><span class="btn sm">Apply</span></div>
      ${Object.keys(v.patch).length ? `<div class="mono muted" style="font-size:11px;margin-top:8px">${Object.entries(v.patch).map(([k, val]) => `${esc(k)} → ${esc(JSON.stringify(val))}`).join('<br>')}</div>` : '<div class="muted" style="font-size:12px;margin-top:6px">Base configuration</div>'}</div>`).join('')}</div>`).join('')
      : '<div class="empty">No variants yet.</div>';
    body.onclick = (e) => { const c = e.target.closest('[data-v]'); if (c) { hooks.applyVariant?.(c.dataset.g, c.dataset.v); toast('Applied variant'); } };
  },
  history(body, p) {
    const icons = { created: 'plus', generated: 'sparkles', generating: 'zap', updated: 'edit', tagged: 'tag', trashed: 'trash', restored: 'refresh', duplicated: 'copy', exported: 'download', 'asset added': 'upload' };
    body.innerHTML = `<div class="section"><h4>${icon('history')}Versions<span class="grow"></span><button class="btn sm" data-snap>${icon('plus')}Snapshot</button></h4>${p.versions.map((v) => `<div class="history-item"><div class="ic">v${v.version}</div><div><div class="t">${esc(v.note)}</div><div class="when">${dateTime(v.at)}</div></div></div>`).join('')}</div>
      <div class="section"><h4>${icon('activity')}Activity</h4>${p.activity.map((a) => `<div class="history-item"><div class="ic">${icon(icons[a.action] || 'activity')}</div><div><div class="t">${esc(a.detail || a.action)}</div><div class="when">${a.action} · ${ago(a.at)}</div></div></div>`).join('')}</div>`;
    $('[data-snap]', body).onclick = async () => { const { snapshot } = await import('./core.js'); await snapshot(byId(p.id) || p); };
  },
  notes(body, p) {
    body.innerHTML = `<div class="section"><h4>${icon('note')}Notes<span class="grow"></span><span class="dim mono" data-st style="font-size:11px">autosaves</span></h4><textarea class="notes" placeholder="Art direction, TODOs, feedback, links…">${esc(p.notes || '')}</textarea></div>`;
    const ta = $('textarea', body), st = $('[data-st]', body);
    ta.oninput = debounce(async () => { st.textContent = 'saving…'; await api('/projects/' + p.id, { method: 'PATCH', body: { notes: ta.value } }); p.notes = ta.value; st.textContent = 'saved ' + new Date().toLocaleTimeString(); }, 600);
  },
};

function drawGraph(wrap, p, compact) {
  const order = ['manifest', 'scene', 'animation', 'mesh', 'material', 'particles', 'shader', 'texture', 'font', 'preview', 'data'];
  const cols = {};
  p.assets.forEach((a) => (cols[a.kind] ||= []).push(a));
  const kinds = Object.keys(cols).sort((a, b) => order.indexOf(a) - order.indexOf(b));
  const W = 176, H = 24, GX = 70, GY = 8, pad = 16;
  const pos = {};
  kinds.forEach((k, ci) => cols[k].forEach((a, ri) => (pos[a.id] = { x: pad + ci * (W + GX), y: pad + 22 + ri * (H + GY), a })));
  const width = pad * 2 + kinds.length * (W + GX) - GX, height = pad * 2 + 22 + Math.max(...kinds.map((k) => cols[k].length)) * (H + GY);
  const edges = p.dependencies.filter((d) => pos[d.from_asset] && pos[d.to_asset] && d.relation !== 'contains');
  const svg = `<svg viewBox="0 0 ${width} ${height}" width="${compact ? '100%' : width}" ${compact ? '' : `height="${height}"`}>
    ${kinds.map((k, ci) => `<text x="${pad + ci * (W + GX)}" y="${pad + 8}" style="font-weight:600;fill:${KIND_HEX[k]};text-transform:uppercase;letter-spacing:.1em">${k}</text>`).join('')}
    ${edges.map((d, i) => { const a = pos[d.from_asset], b = pos[d.to_asset]; const fwd = a.x < b.x; const x1 = fwd ? a.x + W : a.x, x2 = fwd ? b.x : b.x + W, y1 = a.y + H / 2, y2 = b.y + H / 2, mx = (x1 + x2) / 2;
      return `<path class="edge" data-f="${d.from_asset}" data-t="${d.to_asset}" d="M${x1},${y1} C${mx},${y1} ${mx},${y2} ${x2},${y2}"/>`; }).join('')}
    ${Object.entries(pos).map(([id, { x, y, a }]) => `<g class="node" data-id="${id}" transform="translate(${x},${y})"><rect width="${W}" height="${H}" rx="6"/><rect width="4" height="${H}" rx="2" style="fill:${KIND_HEX[a.kind]};stroke:none"/><text x="12" y="16">${esc(a.path.split('/').pop().slice(0, 26))}</text></g>`).join('')}
  </svg>`;
  wrap.innerHTML = svg;
  wrap.addEventListener('mouseover', (e) => {
    const n = e.target.closest('.node');
    $$('.hl', wrap).forEach((x) => x.classList.remove('hl'));
    if (!n) return;
    const id = n.dataset.id;
    n.classList.add('hl');
    $$('path.edge', wrap).forEach((pth) => { if (pth.dataset.f === id || pth.dataset.t === id) { pth.classList.add('hl'); $(`.node[data-id="${pth.dataset.f === id ? pth.dataset.t : pth.dataset.f}"]`, wrap)?.classList.add('hl'); } });
  });
  wrap.addEventListener('click', (e) => { const n = e.target.closest('.node'); if (n) openFile(p, p.assets.find((a) => a.id === n.dataset.id)); });
}

// =============================================================================================== FILE INSPECTOR
export function openFile(p, a) {
  const m = modal({ title: `${icon(KIND_ICON[a.kind] || 'file')} ${esc(a.path)}`, body: '<div data-prev></div>', cls: 'wide', onClose: () => disp.forEach((d) => d.dispose()) });
  const disp = [];
  renderFilePreview($('[data-prev]', m.el), p, a, disp, false);
}

export async function renderFilePreview(el, p, a, disp, compact) {
  const url = fileUrl(p, a), ext = extOf(a.path);
  const deps = (p.dependencies || []);
  const name = (id) => p.assets?.find((x) => x.id === id)?.path;
  const uses = deps.filter((d) => d.from_asset === a.id).map((d) => name(d.to_asset)).filter(Boolean);
  const usedBy = deps.filter((d) => d.to_asset === a.id).map((d) => name(d.from_asset)).filter(Boolean);
  const meta = `<div class="kv" style="margin-top:14px;grid-template-columns:repeat(${compact ? 2 : 4},1fr)">
      <div><div class="k">Kind</div><div class="v" style="font-size:13px">${esc(a.kind)}</div></div><div><div class="k">Size</div><div class="v" style="font-size:13px">${bytes(a.size)}</div></div>
      <div><div class="k">MIME</div><div class="v mono" style="font-size:11px">${esc(a.mime)}</div></div><div><div class="k">Role</div><div class="v" style="font-size:13px">${esc(a.role || '—')}</div></div>
      <div style="grid-column:span ${compact ? 2 : 4}"><div class="k">SHA-256</div><div class="v mono" style="font-size:11px">${a.sha256}</div></div></div>
    ${uses.length || usedBy.length ? `<div class="kv" style="margin-top:8px;grid-template-columns:1fr 1fr"><div><div class="k">Depends on</div><div class="mono" style="font-size:11px;margin-top:4px">${uses.map(esc).join('<br>') || '—'}</div></div><div><div class="k">Used by</div><div class="mono" style="font-size:11px;margin-top:4px">${usedBy.map(esc).join('<br>') || '—'}</div></div></div>` : ''}
    <div style="display:flex;gap:8px;margin-top:14px"><a class="btn sm" href="${url}" download>${icon('download')}Download</a><a class="btn sm" href="${url}" target="_blank">${icon('external')}Raw</a><button class="btn sm" data-cp>${icon('copy')}Copy path</button></div>`;
  let main = '';
  if (ext === 'png' || ext === 'jpg' || ext === 'webp') {
    main = `<div class="preview-box"><div class="preview-img" data-img><img src="${url}" crossorigin="anonymous"></div>
      <div style="display:flex;gap:8px;padding:10px;align-items:center;flex-wrap:wrap"><div class="seg" data-ch>${['RGB', 'R', 'G', 'B', 'A'].map((c, i) => `<button class="${i ? '' : 'on'}" data-c="${c}">${c}</button>`).join('')}</div>
      <div class="seg" data-z>${[1, 2, 4].map((z) => `<button data-zz="${z}" class="${z === 1 ? 'on' : ''}">${z}×</button>`).join('')}</div><button class="btn sm" data-tile>${icon('grid')}Tile 3×3</button><span class="grow" style="flex:1"></span><span class="mono muted" data-dim></span></div></div>`;
  } else if (['obj', 'gltf'].includes(ext)) {
    main = `<div class="preview-box"><div class="preview-3d"><canvas></canvas></div></div>${ext === 'obj' ? '<pre class="code preview-box" style="margin-top:10px;max-height:220px" data-code></pre>' : ''}`;
  } else if (ext === 'bdf' || a.path.endsWith('.font.json') || (a.kind === 'font' && ext === 'png')) {
    main = `<div class="preview-box" style="padding:16px"><canvas data-spec style="width:100%;image-rendering:pixelated;background:#0b0d16;border-radius:10px"></canvas><input class="field" style="margin-top:10px" data-sample value="THE QUICK BROWN TURTLE JUMPS 0123456789!"></div>${ext === 'bdf' ? '<pre class="code preview-box" style="margin-top:10px;max-height:260px" data-code></pre>' : ''}`;
  } else {
    main = `<pre class="code preview-box" data-code></pre><div data-extra></div>`;
  }
  el.innerHTML = main + meta;
  $('[data-cp]', el).onclick = () => copy(`vault/projects/${p.slug}/${a.path}`, 'Path copied');

  if ($('[data-img]', el)) {
    const img = $('img', el);
    img.onload = () => { $('[data-dim]', el).textContent = `${img.naturalWidth}×${img.naturalHeight}px`; };
    let zoom = 1, tile = false, channel = 'RGB';
    const box = $('[data-img]', el);
    const apply = async () => {
      let src = url;
      if (channel !== 'RGB') {
        await img.decode().catch(() => {});
        const c = document.createElement('canvas'); c.width = img.naturalWidth; c.height = img.naturalHeight;
        const x = c.getContext('2d'); x.drawImage(img, 0, 0);
        const d = x.getImageData(0, 0, c.width, c.height), k = { R: 0, G: 1, B: 2, A: 3 }[channel];
        for (let i = 0; i < d.data.length; i += 4) { const v = d.data[i + k]; d.data[i] = d.data[i + 1] = d.data[i + 2] = v; d.data[i + 3] = 255; }
        x.putImageData(d, 0, 0); src = c.toDataURL();
      }
      if (tile) { box.innerHTML = ''; box.style.background = `url(${src}) 0 0/${(img.naturalWidth * zoom) / (window.devicePixelRatio || 1)}px repeat`; box.style.minHeight = '420px'; box.style.imageRendering = 'pixelated'; }
      else { box.style.background = ''; box.innerHTML = `<img src="${src}" style="transform:scale(${zoom})">`; }
    };
    $('[data-ch]', el).onclick = (e) => { const b = e.target.closest('[data-c]'); if (!b) return; channel = b.dataset.c; $$('[data-c]', el).forEach((x) => x.classList.toggle('on', x === b)); apply(); };
    $('[data-z]', el).onclick = (e) => { const b = e.target.closest('[data-zz]'); if (!b) return; zoom = +b.dataset.zz; $$('[data-zz]', el).forEach((x) => x.classList.toggle('on', x === b)); apply(); };
    $('[data-tile]', el).onclick = (e) => { tile = !tile; e.target.closest('button').classList.toggle('on', tile); apply(); };
  }
  if ($('.preview-3d', el)) disp.push(await previewMesh($('.preview-3d canvas', el), url));
  if ($('[data-spec]', el)) {
    const dir = a.path.split('/').slice(0, -1).join('/');
    const jsonA = p.assets.find((x) => x.path.endsWith('.font.json') && x.path.startsWith(dir));
    if (jsonA) {
      const def = await fetchJSON(fileUrl(p, jsonA));
      const img = await new Promise((r) => { const im = new Image(); im.onload = () => r(im); im.src = `/vault/projects/${p.slug}/${dir}/${def.atlas}`; });
      const cv = $('[data-spec]', el);
      const draw = () => {
        cv.width = 900; cv.height = 300;
        const ctx = cv.getContext('2d'); ctx.imageSmoothingEnabled = false;
        ctx.fillStyle = '#0b0d16'; ctx.fillRect(0, 0, 900, 300);
        drawBitmapText(ctx, def, img, def.family + ' · ' + def.format, 20, 16, 1.5);
        const s = $('[data-sample]', el).value;
        drawBitmapText(ctx, def, img, s.slice(0, 36), 20, 70, 2);
        drawBitmapText(ctx, def, img, s.slice(36, 72), 20, 120, 2);
        drawBitmapText(ctx, def, img, def.chars.slice(1, 37), 20, 200, 1);
        drawBitmapText(ctx, def, img, def.chars.slice(37), 20, 236, 1);
      };
      draw();
      $('[data-sample]', el).oninput = draw;
    }
  }
  const code = $('[data-code]', el);
  if (code) {
    let src = await fetchText(url);
    let lang = ['vert', 'frag', 'glsl'].includes(ext) ? 'glsl' : ext === 'json' ? 'json' : ext === 'obj' ? 'obj' : 'text';
    if (ext === 'json') {
      try {
        const j = JSON.parse(src);
        if (j.frames) { const n = j.frames.length; j.frames = `[… ${n} baked frames · first: ${JSON.stringify(j.frames[0]).slice(0, 160)}…]`; }
        if (j.buffers) j.buffers = j.buffers.map((b) => ({ ...b, uri: b.uri.slice(0, 60) + '…' }));
        src = JSON.stringify(j, null, 2);
      } catch {}
    }
    if (ext === 'obj') {
      const lines = src.split('\n');
      const c = (t) => lines.filter((l) => l.startsWith(t + ' ')).length;
      $('.preview-box', el)?.insertAdjacentHTML('afterend', `<div class="kv" style="margin-top:10px;grid-template-columns:repeat(4,1fr)"><div><div class="k">Vertices</div><div class="v">${num(c('v'))}</div></div><div><div class="k">Faces</div><div class="v">${num(c('f'))}</div></div><div><div class="k">Objects</div><div class="v">${c('o')}</div></div><div><div class="k">Materials</div><div class="v">${new Set(lines.filter((l) => l.startsWith('usemtl')).map((l) => l.slice(7))).size}</div></div></div>`);
      src = lines.slice(0, 80).join('\n') + `\n# … ${lines.length - 80} more lines`;
    }
    code.innerHTML = highlight(src, lang);
    if (lang === 'glsl') {
      const uniforms = [...src.matchAll(/uniform\s+(\w+)\s+(\w+)(\[\d+\])?;/g)];
      $('[data-extra]', el).innerHTML = uniforms.length ? `<div class="section" style="margin-top:14px"><h4>${icon('settings')}Uniform interface (${uniforms.length})</h4><div style="display:flex;flex-wrap:wrap;gap:6px">${uniforms.map((u) => `<span class="parse-chip"><b>${u[1]}</b>${u[2]}${u[3] || ''}</span>`).join('')}</div></div>` : '';
    }
  }
}

// =============================================================================================== VAULT EXPLORER
export async function renderVault(view, slug) {
  const [assets, tree, stats] = await Promise.all([api('/assets'), api('/tree'), api('/stats')]);
  const vs = { tab: 'files', q: '', kind: null, prefix: slug ? 'projects/' + slug + '/' : '', sort: ['project_name', 1], sel: null, table: 'projects' };
  view.innerHTML = `<div class="vault"><div class="tree" id="vtree"></div><div class="vault-main" id="vmain"></div><div class="vault-preview" id="vprev"></div></div>`;
  const disp = [];
  live.push({ dispose: () => disp.forEach((d) => d.dispose()) });

  const treeHtml = (nodes, path) => nodes.map((n) => {
    const p = path + n.name + (n.dir ? '/' : '');
    return n.dir ? `<div class="node ${vs.prefix === p ? 'sel' : ''}" data-dir="${esc(p)}">${icon('folder')}${esc(n.name)}<span class="sz">${countFiles(n)}</span></div><div class="kids" ${path.split('/').length > 3 && !vs.prefix.startsWith(p) ? 'hidden' : ''}>${treeHtml(n.children, p)}</div>`
      : `<div class="node" data-file="${esc(p)}">${icon(fileIcon(n.name))}${esc(n.name)}<span class="sz">${bytes(n.size)}</span></div>`;
  }).join('');
  const countFiles = (n) => (n.dir ? n.children.reduce((s, c) => s + countFiles(c), 0) : 1);
  const fileIcon = (n) => ({ png: 'texture', obj: 'object', gltf: 'object', mtl: 'material', vert: 'shader', frag: 'shader', json: 'manifest', bdf: 'font', webp: 'preview' }[extOf(n)] || 'file');
  const drawTree = () => { $('#vtree', view).innerHTML = `<div class="side-label" style="padding-top:4px">vault/</div><div class="node ${!vs.prefix ? 'sel' : ''}" data-dir="">${icon('database')}All files<span class="sz">${assets.length}</span></div>${treeHtml(tree, '')}`; };
  $('#vtree', view).onclick = (e) => {
    const d = e.target.closest('[data-dir]');
    if (d) { vs.prefix = d.dataset.dir; vs.tab = 'files'; const kids = d.nextElementSibling; if (kids?.classList.contains('kids')) kids.hidden = false; drawTree(); drawMain(); return; }
    const f = e.target.closest('[data-file]');
    if (f) { const a = assets.find((x) => 'projects/' + x.slug + '/' + x.path === f.dataset.file); if (a) select(a); else toast('Not catalogued (orphan) — run Rescan on its project', { err: true }); }
  };

  const select = async (a) => {
    vs.sel = a.id;
    $$('tr[data-id]', view).forEach((r) => r.classList.toggle('sel', r.dataset.id === a.id));
    const prev = $('#vprev', view);
    disp.forEach((d) => d.dispose()); disp.length = 0;
    const proj = await api('/projects/' + a.project_id);
    prev.innerHTML = `<div style="display:flex;align-items:center;gap:8px;margin-bottom:12px">${kindBadge(a.kind)}<b style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(a.name)}</b><button class="btn sm icon" data-open title="Open large">${icon('maximize')}</button></div>
      <div class="muted" style="font-size:12px;margin-bottom:12px">in <a href="#/p/${proj.slug}" style="color:var(--text)">${esc(proj.name)}</a></div><div data-pv></div>`;
    $('[data-open]', prev).onclick = () => openFile(proj, proj.assets.find((x) => x.id === a.id) || a);
    renderFilePreview($('[data-pv]', prev), proj, proj.assets.find((x) => x.id === a.id) || a, disp, true);
  };

  const drawMain = () => {
    const main = $('#vmain', view);
    const tabs = [['files', 'Files', 'file'], ['storage', 'Storage', 'database'], ['database', 'Database', 'layers'], ['integrity', 'Integrity', 'shield'], ['inbox', 'Inbox', 'inbox']];
    main.innerHTML = `<div style="display:flex;align-items:center;gap:12px;margin-bottom:16px;flex-wrap:wrap"><h2 style="font:700 22px var(--display);margin:0;letter-spacing:-.02em">Vault explorer</h2>
      <span class="muted mono" style="font-size:12px">${stats.assets} files · ${bytes(stats.bytes)} · ${stats.projects} bundles</span><span style="flex:1"></span>
      <div class="seg">${tabs.map(([k, l, i]) => `<button data-vt="${k}" class="${vs.tab === k ? 'on' : ''}">${icon(i)}${l}</button>`).join('')}</div></div><div id="vtab"></div>`;
    $$('[data-vt]', main).forEach((b) => (b.onclick = () => { vs.tab = b.dataset.vt; drawMain(); }));
    VT[vs.tab]($('#vtab', main));
  };

  const VT = {
    files(el) {
      const kinds = [...new Set(assets.map((a) => a.kind))];
      let rows = assets.filter((a) => ('projects/' + a.slug + '/' + a.path).startsWith(vs.prefix) && (!vs.kind || a.kind === vs.kind) &&
        (!vs.q || (a.path + a.project_name + a.role + a.sha256).toLowerCase().includes(vs.q.toLowerCase())));
      const [col, dir] = vs.sort;
      rows.sort((x, y) => (x[col] > y[col] ? dir : x[col] < y[col] ? -dir : 0));
      el.innerHTML = `<div style="display:flex;gap:8px;margin-bottom:12px;flex-wrap:wrap;align-items:center"><div class="search" style="margin:0;max-width:300px">${icon('search')}<input data-q placeholder="Filter path, role, hash…" value="${esc(vs.q)}" style="padding-right:12px"></div>
        <span class="chip ${!vs.kind ? 'on' : ''}" data-k="">All</span>${kinds.map((k) => `<span class="chip ${vs.kind === k ? 'on' : ''}" data-k="${k}" style="${vs.kind === k ? '' : ''}"><i style="width:8px;height:8px;border-radius:3px;background:${KIND_HEX[k]}"></i>${k}</span>`).join('')}
        ${vs.prefix ? `<span class="tag">${esc(vs.prefix)}</span>` : ''}<span class="muted mono" style="font-size:11px;margin-left:auto">${rows.length} rows · ${bytes(rows.reduce((s, a) => s + a.size, 0))}</span></div>
        <div style="overflow:auto;border-radius:12px;border:1px solid var(--line)"><table class="data"><thead><tr>${[['project_name', 'Project'], ['path', 'Path'], ['kind', 'Kind'], ['role', 'Role'], ['size', 'Size'], ['variant', 'Variant'], ['sha256', 'SHA-256']].map(([k, l]) => `<th data-s="${k}">${l}${vs.sort[0] === k ? (vs.sort[1] > 0 ? ' ↑' : ' ↓') : ''}</th>`).join('')}</tr></thead>
        <tbody>${rows.map((a) => `<tr data-id="${a.id}" class="${vs.sel === a.id ? 'sel' : ''}"><td>${esc(a.project_name)}</td><td class="mono">${esc(a.path)}</td><td><span style="color:${KIND_HEX[a.kind]}">●</span> ${a.kind}</td><td class="muted">${esc(a.role || '')}</td><td class="mono">${bytes(a.size)}</td><td>${a.variant ? `<span class="tag">${esc(a.variant)}</span>` : ''}</td><td class="mono dim">${a.sha256.slice(0, 12)}</td></tr>`).join('')}</tbody></table></div>`;
      const q = $('[data-q]', el);
      q.oninput = debounce(() => { vs.q = q.value; VT.files(el); $('[data-q]', el).focus(); const v = $('[data-q]', el); v.setSelectionRange(v.value.length, v.value.length); }, 200);
      el.onclick = (e) => {
        const k = e.target.closest('[data-k]'); if (k) { vs.kind = k.dataset.k || null; return VT.files(el); }
        const s = e.target.closest('[data-s]'); if (s) { vs.sort = [s.dataset.s, vs.sort[0] === s.dataset.s ? -vs.sort[1] : 1]; return VT.files(el); }
        const r = e.target.closest('tr[data-id]'); if (r) select(assets.find((a) => a.id === r.dataset.id));
      };
    },
    storage(el) {
      const tot = stats.bytes || 1;
      const byProj = {};
      assets.forEach((a) => { (byProj[a.project_name] ||= { s: 0, n: 0, kinds: {} }); byProj[a.project_name].s += a.size; byProj[a.project_name].n++; byProj[a.project_name].kinds[a.kind] = (byProj[a.project_name].kinds[a.kind] || 0) + a.size; });
      el.innerHTML = `<div class="box" style="margin-bottom:16px"><div style="display:flex;justify-content:space-between;margin-bottom:10px"><b>Storage by asset kind</b><span class="mono muted">${bytes(stats.bytes)}</span></div>
        <div class="meter">${stats.by_kind.map((k) => `<span title="${k.kind} ${bytes(k.bytes)}" style="flex:${k.bytes};background:${KIND_HEX[k.kind]}"></span>`).join('')}</div>
        <div style="margin-top:12px">${stats.by_kind.map((k) => `<div class="legend-row"><i style="background:${KIND_HEX[k.kind]}"></i><span>${k.kind}</span><span class="mono muted">${k.n} files</span><span class="mono">${bytes(k.bytes)} · ${((k.bytes / tot) * 100).toFixed(1)}%</span></div>`).join('')}</div></div>
        <div class="box" style="margin-bottom:16px"><b>Storage by bundle</b><div style="margin-top:12px">${Object.entries(byProj).sort((a, b) => b[1].s - a[1].s).map(([n, v]) => `<div style="margin-bottom:12px"><div style="display:flex;justify-content:space-between;font-size:13px;margin-bottom:6px"><span>${esc(n)}</span><span class="mono muted">${v.n} files · ${bytes(v.s)}</span></div><div class="meter" style="height:10px">${Object.entries(v.kinds).map(([k, s]) => `<span style="flex:${s};background:${KIND_HEX[k]}" title="${k}"></span>`).join('')}</div></div>`).join('')}</div></div>
        <div class="box"><b>Content-addressed duplicates</b><p class="muted" style="font-size:12.5px;margin:4px 0 10px">Files with identical SHA-256 across the vault — candidates for de-duplication.</p>${stats.duplicates.length ? stats.duplicates.map((d) => `<div class="legend-row" style="grid-template-columns:1fr auto"><span class="mono" style="font-size:11px;white-space:normal">${esc(d.paths)}</span><span class="mono">${d.n}× ${bytes(d.size)}</span></div>`).join('') : '<div class="muted">No duplicates — every file is unique.</div>'}</div>`;
    },
    async database(el) {
      const tables = ['projects', 'assets', 'dependencies', 'tags', 'folders', 'versions', 'activity'];
      el.innerHTML = `<div style="display:flex;gap:8px;align-items:center;margin-bottom:12px;flex-wrap:wrap"><div class="seg">${tables.map((t) => `<button data-t="${t}" class="${vs.table === t ? 'on' : ''}">${t}</button>`).join('')}</div><span class="muted mono" data-cnt style="font-size:11px;margin-left:auto"></span></div><div style="overflow:auto;border-radius:12px;border:1px solid var(--line);max-height:calc(100vh - 220px)" data-grid>Loading…</div>`;
      $$('[data-t]', el).forEach((b) => (b.onclick = () => { vs.table = b.dataset.t; VT.database(el); }));
      const t = await api('/db/' + vs.table);
      $('[data-cnt]', el).textContent = `thecreator.db · ${vs.table} · ${t.total} rows · ${t.columns.length} columns`;
      $('[data-grid]', el).innerHTML = `<table class="data"><thead><tr>${t.columns.map((c) => `<th>${c}</th>`).join('')}</tr></thead><tbody>${t.rows.map((r) => `<tr>${t.columns.map((c) => { let v = r[c]; if (v == null) return '<td class="dim">NULL</td>'; v = String(v); if (/_at$/.test(c) && +v > 1e9) v = dateTime(+v); return `<td class="${/json|sha|id/.test(c) ? 'mono' : ''}" title="${esc(v.slice(0, 400))}">${esc(v.slice(0, 80))}</td>`; }).join('')}</tr>`).join('')}</tbody></table>`;
    },
    integrity(el) {
      el.innerHTML = `<div class="box"><div style="display:flex;align-items:center;gap:12px"><div style="flex:1"><b>Vault integrity check</b><div class="muted" style="font-size:12.5px">Re-hashes every file on disk and compares it with the SHA-256 stored in the catalogue. Also finds orphans (files on disk the DB doesn't know).</div></div><button class="btn primary" data-run>${icon('shield')}Run check</button></div><div data-res style="margin-top:14px"></div></div>`;
      $('[data-run]', el).onclick = async () => {
        $('[data-res]', el).innerHTML = '<div class="muted">Hashing…</div>';
        const r = await api('/integrity');
        const bad = r.modified.length + r.missing.length;
        $('[data-res]', el).innerHTML = `<div class="integrity-badge ${bad ? 'bad' : 'ok'}">${icon(bad ? 'x' : 'shield')}${bad ? bad + ' problems found' : 'All ' + r.ok + ' files verified'}</div>
          ${['modified', 'missing', 'orphans'].map((k) => r[k].length ? `<div style="margin-top:12px"><b style="text-transform:capitalize">${k}</b> (${r[k].length})<div class="mono muted" style="font-size:11.5px;margin-top:4px">${r[k].map(esc).join('<br>')}</div></div>` : '').join('')}
          <div class="mono dim" style="font-size:11px;margin-top:10px">checked ${dateTime(r.checked_at)}</div>`;
      };
    },
    async inbox(el) {
      const queue = await api('/queue');
      el.innerHTML = queue.length ? `<div class="box" style="margin-bottom:14px;display:flex;gap:14px;align-items:center"><div style="flex:1"><b>${queue.length} request(s) waiting</b>
        <div class="muted" style="font-size:12.5px">Each has a ticket in <code class="mono">vault/inbox/</code>. <b>Process queue</b> hands every request that matches a generator to it; the rest wait until a generator exists for them (ask Claude to write one).</div></div>
        <button class="btn primary" data-proc ${queue.some((q) => q.generator) ? '' : 'disabled style="opacity:.5"'}>${icon('zap')}Process queue</button></div>
        <div class="cards-2">${queue.map((p) => `
        <div class="box"><div style="display:flex;gap:8px;align-items:center">${kindBadge(p.kind)}<span class="status queued">queued</span></div><div style="font:600 15px var(--display);margin:10px 0 4px">${esc(p.name)}</div><div class="muted" style="font-size:12.5px">${esc(p.prompt)}</div>
        <div class="mono" style="font-size:11px;margin:10px 0;color:${p.generator ? 'var(--good)' : 'var(--warn)'}">${p.generator ? '✓ generator: ' + esc(p.generator) : '… no generator yet'}</div>
        <div style="display:flex;gap:6px"><a class="btn sm" href="#/p/${p.slug}">${icon('external')}Open</a>${p.generator ? `<button class="btn sm" data-one="${p.slug}">${icon('zap')}Run</button>` : ''}<button class="btn sm" data-rs="${p.id}">${icon('refresh')}Rescan</button></div></div>`).join('')}</div>`
        : `<div class="empty">${icon('inbox')}<div class="big">Inbox zero</div>Every request has been created. Queue a new one with <kbd>N</kbd>.</div>`;
      el.onclick = async (e) => {
        const b = e.target.closest('[data-rs],[data-proc],[data-one]');
        if (!b) return;
        if (b.dataset.rs) { const r = await api(`/projects/${b.dataset.rs}/rescan`, { method: 'POST' }); return toast(`Registered ${r.added.length} files`); }
        const t = toast('Generating… this can take a minute', { progress: 0.3 });
        try {
          const r = await api('/process', { method: 'POST', body: b.dataset.one ? { slug: b.dataset.one } : {} });
          await refresh();
          t.done(`Created ${r.done.length} bundle(s)`);
          VT.inbox(el);
        } catch (err) { t.done(); toast(esc(err.message), { err: true }); }
      };
    },
  };
  drawTree();
  drawMain();
}

// =============================================================================================== ACTIVITY
export async function renderActivity(view) {
  const rows = await api('/activity');
  const icons = { created: 'plus', generated: 'sparkles', generating: 'zap', updated: 'edit', tagged: 'tag', trashed: 'trash', restored: 'refresh', duplicated: 'copy', exported: 'download', 'asset added': 'upload', purged: 'x' };
  let day = '';
  view.innerHTML = `<div class="page"><div class="toolbar"><h2>Activity</h2><span class="muted mono" style="font-size:12px">${rows.length} recent events across the vault</span></div><div class="timeline-feed">${rows.map((r) => {
    const d = new Date(r.at * 1000).toDateString();
    const head = d !== day ? `<div class="feed-day">${d === new Date().toDateString() ? 'Today' : d}</div>` : '';
    day = d;
    const p = byId(r.project_id);
    return head + `<a class="feed-item" ${p ? `href="#/p/${p.slug}"` : ''}><div class="ic">${icon(icons[r.action] || 'activity')}</div><div><div><b>${esc(r.project_name || 'Deleted project')}</b> <span class="muted">· ${esc(r.action)}</span></div><div class="muted" style="font-size:12.5px">${esc(r.detail)}</div></div><span class="mono dim" style="font-size:11px">${ago(r.at)}</span></a>`;
  }).join('')}</div></div>`;
}
