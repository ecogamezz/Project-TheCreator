// Project-TheCreator · real-time stage. Renders every bundle straight from the vault files:
// OBJ meshes, PNG textures, the generated GLSL programs, scene graphs, particle systems and baked animations.
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { OBJLoader } from 'three/addons/loaders/OBJLoader.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';

const textCache = new Map();
const texCache = new Map();

export const fetchText = (url) => {
  if (!textCache.has(url)) textCache.set(url, fetch(url).then((r) => { if (!r.ok) throw new Error(url + ' ' + r.status); return r.text(); }));
  return textCache.get(url);
};
export const fetchJSON = async (url) => JSON.parse(await fetchText(url));

export function loadTex(url, { srgb = true, nearest = false, repeat = true } = {}) {
  const key = [url, srgb, nearest, repeat].join('|');
  if (!texCache.has(key)) {
    texCache.set(key, new Promise((res, rej) => new THREE.TextureLoader().load(url, (t) => {
      t.colorSpace = srgb ? THREE.SRGBColorSpace : THREE.NoColorSpace;
      if (repeat) t.wrapS = t.wrapT = THREE.RepeatWrapping;
      if (nearest) { t.magFilter = THREE.NearestFilter; t.minFilter = THREE.NearestFilter; t.generateMipmaps = false; }
      else t.anisotropy = 4;
      res(t);
    }, undefined, rej)));
  }
  return texCache.get(key);
}

const isColorMap = (name) => /albedo|uMap|map$/i.test(name) && !/normal|rough/i.test(name);

export function applyPatch(target, patch) {
  for (const [path, value] of Object.entries(patch || {})) {
    const keys = path.split('.');
    let o = target;
    for (const k of keys.slice(0, -1)) o = o[k] ??= {};
    o[keys.at(-1)] = structuredClone(value);
  }
  return target;
}

export function defaultVariants(project) {
  const pick = {};
  for (const v of project.variants || []) if (v.default && !(v.group in pick)) pick[v.group] = v.id;
  for (const v of project.variants || []) if (!(v.group in pick)) pick[v.group] = v.id;
  return pick;
}

function variantPatch(project, selection) {
  const p = {};
  for (const id of Object.values(selection || {})) Object.assign(p, (project.variants || []).find((v) => v.id === id)?.patch || {});
  return p;
}

const toUniform = (v) => (Array.isArray(v) ? (v.length === 3 ? new THREE.Vector3(...v) : new THREE.Vector4(...v)) : v);

// ----------------------------------------------------------------------------------------------- base stage
class Stage {
  constructor(canvas, project, opts = {}) {
    this.canvas = canvas;
    this.project = project;
    this.opts = opts;
    this.base = `/vault/projects/${project.slug}/`;
    this.selection = opts.variants || defaultVariants(project);
    this.mode = opts.mode || 'shader';
    this.clock = new THREE.Clock();
    this.time = 0;
    this.speed = 1;
    this.playing = true;
    this.listeners = {};
    this.renderer = new THREE.WebGLRenderer({ canvas, antialias: opts.antialias ?? true, alpha: true, preserveDrawingBuffer: !!opts.capture });
    this.renderer.setPixelRatio(opts.pixelRatio ?? Math.min(window.devicePixelRatio, 2));
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.debug.onShaderError = (gl, prog, vs, fs) => {
      const log = gl.getShaderInfoLog(fs) || gl.getShaderInfoLog(vs) || gl.getProgramInfoLog(prog);
      this.emit('error', 'Shader compile error: ' + log);
    };
    this.scene = new THREE.Scene();
    this.camera = new THREE.PerspectiveCamera(40, 1, 0.05, 2000);
    this.shared = {
      uTime: { value: 0 }, uExposure: { value: 1 },
      uLightDir: { value: new THREE.Vector3(0.55, 0.85, 0.4) }, uLightColor: { value: new THREE.Vector3(1.1, 1.05, 1) },
    };
    if (opts.interactive !== false) {
      this.controls = new OrbitControls(this.camera, canvas);
      this.controls.enableDamping = true;
      this.controls.autoRotateSpeed = 0.8;
    }
    this.ro = opts.interactive !== false ? new ResizeObserver(() => this.resize()) : null;
    this.ro?.observe(canvas.parentElement || canvas);
  }
  on(ev, fn) { (this.listeners[ev] ||= []).push(fn); return this; }
  emit(ev, ...a) { (this.listeners[ev] || []).forEach((f) => f(...a)); }
  url(rel) { return this.base + rel; }

  async shaderMaterial(def, extraUniforms = {}) {
    const [vs, fs] = await Promise.all([fetchText(this.url(def.vert)), fetchText(this.url(def.frag))]);
    const uniforms = { ...this.shared };
    for (const [k, path] of Object.entries(def.maps || {})) uniforms[k] = { value: await loadTex(this.url(path), { srgb: isColorMap(k) }) };
    for (const [k, v] of Object.entries(def.uniforms || {})) uniforms[k] = { value: toUniform(v) };
    Object.assign(uniforms, extraUniforms);
    return new THREE.ShaderMaterial({ vertexShader: vs, fragmentShader: fs, uniforms, side: def.doubleSided ? THREE.DoubleSide : THREE.FrontSide, transparent: !!def.transparent });
  }

  async pbrMaterial(def) {
    const p = def.pbr || {};
    const m = new THREE.MeshStandardMaterial({ roughness: p.roughness ?? 0.5, metalness: p.metalness ?? 0 });
    if (p.color) m.color.setRGB(...p.color);
    if (p.emissive) m.emissive.setRGB(...p.emissive);
    for (const slot of ['map', 'normalMap', 'roughnessMap']) if (p[slot]) m[slot] = await loadTex(this.url(p[slot]), { srgb: slot === 'map' });
    return m;
  }

  async utilityMaterial(mode) {
    if (mode === 'wire') return new THREE.MeshBasicMaterial({ color: 0x8b9cff, wireframe: true, transparent: true, opacity: 0.85 });
    if (mode === 'normals') return new THREE.MeshNormalMaterial();
    if (mode === 'clay') return new THREE.MeshStandardMaterial({ color: 0xbfb8ae, roughness: 0.85 });
    if (mode === 'uv') return new THREE.ShaderMaterial({
      vertexShader: 'varying vec2 vUv; void main(){ vUv=uv; gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0);}',
      fragmentShader: 'varying vec2 vUv; void main(){ vec2 c=floor(fract(vUv)*16.0); float k=mod(c.x+c.y,2.0); vec3 col=mix(vec3(fract(vUv),0.6),vec3(0.12),k*0.6); gl_FragColor=vec4(col,1.0);}',
    });
  }

  resize() {
    const el = this.canvas.parentElement || this.canvas;
    const w = this.opts.width || el.clientWidth || 480, h = this.opts.height || el.clientHeight || 320;
    this.renderer.setSize(w, h, false);
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
    this.onResize?.(w, h);
  }

  frameCamera(cam) {
    this.camera.fov = cam.fov || 40;
    this.camera.position.set(...cam.position);
    this.target = new THREE.Vector3(...(cam.target || [0, 0, 0]));
    this.camera.lookAt(this.target);
    if (this.controls) { this.controls.target.copy(this.target); this.controls.update(); }
    this.home = { position: this.camera.position.clone(), target: this.target.clone() };
  }
  resetView() {
    if (!this.home) return;
    this.camera.position.copy(this.home.position);
    this.controls?.target.copy(this.home.target);
    this.controls?.update();
  }

  start() {
    this.resize();
    const loop = () => {
      if (this.disposed) return;
      this.raf = requestAnimationFrame(loop);
      this.tick();
    };
    loop();
  }
  tick(dtOverride) {
    const dt = dtOverride ?? Math.min(this.clock.getDelta(), 0.1);
    if (this.playing) this.time += dt * this.speed;
    this.shared.uTime.value = this.time;
    this.update?.(dt);
    this.controls?.update();
    this.renderer.info.autoReset = false;
    this.renderer.info.reset();
    this.draw();
    this.emit('frame', this.time);
  }
  draw() { this.renderer.render(this.scene, this.camera); }

  async setMode(mode) { this.mode = mode; await this.applyMaterials?.(); }
  async setVariants(sel) { this.selection = { ...this.selection, ...sel }; await this.rebuild(); }

  info() {
    let tris = 0, meshes = 0;
    this.scene.traverse((o) => { if (o.isMesh && o.visible) { meshes++; const g = o.geometry; tris += (g.index ? g.index.count : g.attributes.position.count) / 3; } });
    const i = this.renderer.info;
    return { tris: Math.round(tris), meshes, calls: i.render.calls, programs: i.programs?.length || 0, textures: i.memory.textures, geometries: i.memory.geometries };
  }

  // Capture a still + a 16-frame strip (turntable for objects, timeline for animations, flyover for scenes).
  async capture({ w = 480, h = 320, frames = 16 } = {}) {
    const prev = { w: this.opts.width, h: this.opts.height, playing: this.playing, time: this.time };
    this.opts.width = w; this.opts.height = h;
    this.renderer.setPixelRatio(1);
    this.resize();
    this.playing = false;
    const still = await this.captureFrame(0, frames, true);
    const sprite = document.createElement('canvas');
    const fw = 240, fh = 160;
    sprite.width = fw * frames; sprite.height = fh;
    const ctx = sprite.getContext('2d');
    for (let i = 0; i < frames; i++) {
      const url = await this.captureFrame(i, frames, false);
      const img = await new Promise((r) => { const im = new Image(); im.onload = () => r(im); im.src = url; });
      ctx.drawImage(img, i * fw, 0, fw, fh);
    }
    Object.assign(this.opts, { width: prev.w, height: prev.h });
    this.playing = prev.playing; this.time = prev.time;
    this.renderer.setPixelRatio(this.opts.pixelRatio ?? Math.min(window.devicePixelRatio, 2));
    this.resize();
    return { thumbnail: still, sprite: sprite.toDataURL('image/webp', 0.86) };
  }
  async captureFrame(i, n, hero) {
    this.poseForCapture(i, n, hero);
    this.tick(0);
    return this.composite();
  }
  composite() { return this.renderer.domElement.toDataURL('image/png'); }
  poseForCapture(i, n, hero) {
    const target = this.home.target;
    const off = this.home.position.clone().sub(target);
    const ang = hero ? 0 : (i / n) * Math.PI * 2;
    off.applyAxisAngle(new THREE.Vector3(0, 1, 0), ang);
    this.camera.position.copy(target).add(off);
    this.camera.lookAt(target);
    this.controls?.target.copy(target);
    this.time = hero ? 1.2 : 1.2 + i * 0.12;
  }

  dispose() {
    this.disposed = true;
    cancelAnimationFrame(this.raf);
    this.ro?.disconnect();
    this.controls?.dispose();
    this.scene.traverse((o) => { o.geometry?.dispose(); [].concat(o.material || []).forEach((m) => m.dispose()); });
    this.renderer.dispose();
    this.renderer.forceContextLoss?.();
  }
}

// ----------------------------------------------------------------------------------------------- object stage
class ObjectStage extends Stage {
  async load() {
    this.scene.environment = new THREE.PMREMGenerator(this.renderer).fromScene(new RoomEnvironment(), 0.04).texture;
    this.fill = new THREE.HemisphereLight(0xdde6ff, 0x302820, 0.6);
    this.key = new THREE.DirectionalLight(0xffffff, 1.6);
    this.key.position.set(3, 5, 2);
    this.scene.add(this.fill, this.key);
    this.shadow = new THREE.Mesh(new THREE.CircleGeometry(2.4, 48), new THREE.ShaderMaterial({
      transparent: true, depthWrite: false,
      vertexShader: 'varying vec2 vUv; void main(){vUv=uv; gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0);}',
      fragmentShader: 'varying vec2 vUv; void main(){ float d=length(vUv-0.5)*2.0; gl_FragColor=vec4(0.0,0.0,0.0,(1.0-smoothstep(0.0,1.0,d))*0.45);}',
    }));
    this.shadow.rotation.x = -Math.PI / 2;
    this.grid = new THREE.GridHelper(12, 24, 0x6670a0, 0x2a2f45);
    this.grid.material.transparent = true; this.grid.material.opacity = 0.35;
    this.grid.visible = false;
    this.scene.add(this.shadow, this.grid);
    await this.rebuild();
    // Fit: keep the authored viewing direction, derive distance from the bounding sphere.
    const sphere = new THREE.Box3().setFromObject(this.root).getBoundingSphere(new THREE.Sphere());
    const cam = this.R.camera, fov = cam.fov || 40;
    const dir = new THREE.Vector3(...cam.position).sub(new THREE.Vector3(...cam.target)).normalize();
    const dist = (sphere.radius / Math.sin(THREE.MathUtils.degToRad(fov / 2))) * 0.78;
    this.frameCamera({ fov, target: sphere.center.toArray(), position: sphere.center.clone().addScaledVector(dir, dist).toArray() });
    if (this.controls) this.controls.autoRotate = this.opts.autoRotate ?? false;
  }
  async rebuild() {
    this.R = applyPatch(structuredClone(this.project.render), variantPatch(this.project, this.selection));
    const R = this.R;
    if (R.light) { this.shared.uLightDir.value.set(...R.light.dir); this.shared.uLightColor.value.set(...R.light.color); }
    for (const [k, v] of Object.entries(R.uniforms || {})) (this.shared[k] ||= { value: 0 }).value = toUniform(v);
    if (this.meshUrl !== R.mesh) {
      if (this.root) this.scene.remove(this.root);
      this.root = new OBJLoader().parse(await fetchText(this.url(R.mesh)));
      this.root.traverse((o) => { if (o.isMesh) o.userData.matNames = [].concat(o.material).map((m) => m.name); });
      this.scene.add(this.root);
      this.meshUrl = R.mesh;
      const box = new THREE.Box3().setFromObject(this.root);
      this.shadow.position.y = box.min.y - 0.01;
      this.grid.position.y = box.min.y - 0.012;
      this.shadow.scale.setScalar(Math.max(box.max.x - box.min.x, box.max.z - box.min.z) / 3.6);
    }
    await this.applyMaterials();
  }
  async applyMaterials() {
    const cache = {};
    const get = async (name) => {
      if (cache[name]) return cache[name];
      const def = this.R.materials[name];
      if (this.mode === 'shader' && def) return (cache[name] = await this.shaderMaterial(def));
      if (this.mode === 'pbr' && def) return (cache[name] = await this.pbrMaterial(def));
      return (cache[name] = await this.utilityMaterial(this.mode === 'shader' || this.mode === 'pbr' ? 'clay' : this.mode));
    };
    const meshes = [];
    this.root.traverse((o) => o.isMesh && meshes.push(o));
    for (const m of meshes) {
      const mats = await Promise.all(m.userData.matNames.map(get));
      m.material = mats.length === 1 ? mats[0] : mats;
    }
    this.renderer.toneMapping = this.mode === 'shader' ? THREE.NoToneMapping : THREE.ACESFilmicToneMapping;
  }
  setGrid(on) { this.grid.visible = on; }
}

// ----------------------------------------------------------------------------------------------- animation stage
class AnimationStage extends Stage {
  async load() {
    this.anim = await fetchJSON(this.url(this.project.render.animation));
    this.duration = this.anim.duration;
    this.events = this.anim.events;
    this.world = new THREE.Group();
    this.scene.add(this.world);
    this.scene.environment = new THREE.PMREMGenerator(this.renderer).fromScene(new RoomEnvironment(), 0.04).texture;
    this.scene.add(new THREE.HemisphereLight(0xdde6ff, 0x302820, 0.7));
    const key = new THREE.DirectionalLight(0xffffff, 1.6); key.position.set(3, 6, 2); this.scene.add(key);
    const root = new OBJLoader().parse(await fetchText(this.url(this.project.render.mesh)));
    this.pieces = {};
    const meshes = [];
    root.traverse((o) => o.isMesh && meshes.push(o));
    for (const m of meshes) {
      const [obj] = Object.entries(this.anim.objects).find(([, names]) => names.includes(m.name)) || [m.name];
      const piv = this.anim.pivots[obj];
      if (piv) m.geometry.translate(-piv[0], -piv[1], -piv[2]);
      m.userData.material = m.material.name;
      m.userData.obj = obj;
      m.userData.alpha = { value: 1 };
      (this.pieces[obj] ||= []).push(m);
      this.world.add(m);
    }
    this.casters = Array.from({ length: 9 }, () => new THREE.Vector4(0, -10, 0, 0.01));
    this.fx = { uFlash: { value: 0 }, uGlow: { value: 0 } };
    await this.rebuild();
    this.frameCamera(this.project.render.camera);
  }
  async rebuild() {
    this.R = applyPatch(structuredClone(this.project.render), variantPatch(this.project, this.selection));
    if (this.R.light) { this.shared.uLightDir.value.set(...this.R.light.dir); this.shared.uLightColor.value.set(...this.R.light.color); }
    const F = this.R.floor;
    if (!this.floor) {
      this.floor = new THREE.Mesh(new THREE.PlaneGeometry(80, 80), null);
      this.floor.rotation.x = -Math.PI / 2;
      this.world.add(this.floor);
    }
    this.floor.material = await this.shaderMaterial({ vert: F.vert, frag: F.frag }, {
      uCasters: { value: this.casters }, uFloorColor: { value: new THREE.Vector3(...F.color) },
      uGridColor: { value: new THREE.Vector3(...F.grid) }, uRingColor: { value: new THREE.Vector3(...F.ring) },
      uImpact: (this.impactU ||= { value: 0 }),
    });
    await this.applyMaterials();
  }
  async applyMaterials() {
    for (const list of Object.values(this.pieces)) {
      for (const m of list) {
        const def = this.R.materials[m.userData.material];
        if (this.mode === 'shader') m.material = await this.shaderMaterial(def, { ...this.fx, uAlpha: m.userData.alpha });
        else if (this.mode === 'pbr') { m.material = await this.pbrMaterial(def); m.material.transparent = true; m.userData.pbr = true; }
        else m.material = await this.utilityMaterial(this.mode);
        m.material.transparent = true;
      }
    }
    this.floor.visible = true;
    this.renderer.toneMapping = this.mode === 'shader' ? THREE.NoToneMapping : THREE.ACESFilmicToneMapping;
  }
  sample(t) {
    const fr = this.anim.frames, n = fr.length;
    const x = ((t % this.duration) + this.duration) % this.duration * this.anim.fps;
    const i0 = Math.min(Math.floor(x), n - 1), i1 = Math.min(i0 + 1, n - 1), a = x - i0;
    return [fr[i0], fr[i1], a];
  }
  update() {
    const [A, B, a] = this.sample(this.time);
    const lerp3 = (p, q) => [p[0] + (q[0] - p[0]) * a, p[1] + (q[1] - p[1]) * a, p[2] + (q[2] - p[2]) * a];
    const qa = new THREE.Quaternion(), qb = new THREE.Quaternion();
    const set = (obj, sa, sb, alpha) => {
      qa.fromArray(sa.q); qb.fromArray(sb.q); qa.slerp(qb, a);
      for (const m of this.pieces[obj] || []) {
        m.position.fromArray(lerp3(sa.p, sb.p));
        m.quaternion.copy(qa);
        m.scale.fromArray(lerp3(sa.s, sb.s));
        m.userData.alpha.value = alpha;
        if (m.userData.pbr || this.mode !== 'shader') { m.material.opacity = alpha; }
        m.visible = alpha > 0.003 && m.scale.x > 0.001;
      }
    };
    set('body', A.body, B.body, 1);
    A.shards.forEach((s, i) => set('shard_' + i, s, B.shards[i], s.a + (B.shards[i].a - s.a) * a));
    const fx = (k) => A.fx[k] + (B.fx[k] - A.fx[k]) * a;
    this.fx.uFlash.value = fx('flash');
    this.fx.uGlow.value = fx('glow');
    const shake = fx('shake');
    this.world.position.set((Math.random() - 0.5) * shake, (Math.random() - 0.5) * shake * 0.5, (Math.random() - 0.5) * shake);
    const land = this.events.find((e) => e.type === 'impact').t;
    const tt = ((this.time % this.duration) + this.duration) % this.duration;
    this.impactU.value = tt >= land && tt < land + 0.7 ? (tt - land) / 0.7 : 0;
    const b = this.pieces.body[0];
    this.casters[0].set(b.position.x, b.position.y - b.scale.y, b.position.z, 1.25 * b.scale.x);
    A.shards.forEach((s, i) => {
      const m = this.pieces['shard_' + i][0];
      const on = m.visible && s.m === 1;
      this.casters[i + 1].set(m.position.x, m.position.y - 0.25, m.position.z, on ? 0.42 * m.scale.x * m.userData.alpha.value : 0.0001);
    });
  }
  get frame() { return Math.floor((((this.time % this.duration) + this.duration) % this.duration) * this.anim.fps); }
  seek(t) { this.time = t; }
  poseForCapture(i, n, hero) {
    super.poseForCapture(0, n, true);
    this.time = hero ? 2.05 : (i / n) * this.duration;
  }
}

// ----------------------------------------------------------------------------------------------- scene stage (PS2 beach)
function mulberry(seed) {
  return () => { seed |= 0; seed = (seed + 0x6d2b79f5) | 0; let t = Math.imul(seed ^ (seed >>> 15), 1 | seed); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
}

class SceneStage extends Stage {
  constructor(canvas, project, opts) {
    super(canvas, project, { ...opts, antialias: false });
    this.renderer.setPixelRatio(1);
    this.opts.pixelRatio = 1;
    this.cinematic = opts.cinematic ?? true;
    this.hudOn = opts.hud ?? true;
  }
  async load() {
    this.S0 = await fetchJSON(this.url(this.project.render.scene));
    this.particlesDef = await fetchJSON(this.url(this.S0.particles));
    this.fontDef = await fetchJSON(this.url(this.S0.hud.font));
    this.fontImg = await new Promise((r) => { const im = new Image(); im.onload = () => r(im); im.src = this.url(this.S0.hud.atlas); });
    this.rt = new THREE.WebGLRenderTarget(640, 448, { minFilter: THREE.NearestFilter, magFilter: THREE.NearestFilter });
    this.postScene = new THREE.Scene();
    this.postCam = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);
    await this.rebuild();
    this.frameCamera(this.S.camera);
    this.camera.far = 1200;
    this.curve = new THREE.CatmullRomCurve3(this.S.camera.path.map((p) => new THREE.Vector3(...p)), true);
    this.controls?.addEventListener('start', () => { this.cinematic = false; this.emit('cinematic', false); });
  }
  async rebuild() {
    this.S = applyPatch(structuredClone(this.S0), variantPatch(this.project, this.selection));
    const S = this.S, E = S.environment, RS = S.renderSettings;
    this.renderer.toneMapping = THREE.NoToneMapping;
    this.renderer.outputColorSpace = THREE.LinearSRGBColorSpace;        // display-referred pipeline, like the hardware
    for (const c of [...this.scene.children]) this.scene.remove(c);
    const env = {
      uSunDir: { value: new THREE.Vector3(...E.sunDir) }, uSunColor: { value: new THREE.Vector3(...E.sunColor) },
      uAmbient: { value: new THREE.Vector3(...E.ambient) }, uFogColor: { value: new THREE.Vector3(...E.fog.color) },
      uFogNear: { value: E.fog.near }, uFogFar: { value: E.fog.far }, uSnap: { value: RS.vertexSnap },
      uResolution: { value: new THREE.Vector2(...RS.internalResolution) },
    };
    this.env = env;
    const nearest = RS.textureFilter === 'nearest';
    const tex = (p) => loadTex(this.url(p), { srgb: false, nearest });
    const mat = async (name) => {
      const d = S.materials[name];
      if (name === 'water') {
        return this.shaderMaterial({ ...d, maps: {} }, {
          ...env, uMap: { value: await tex(d.maps.uMap) }, uDeep: { value: new THREE.Vector3(...E.water.deep) }, uShallow: { value: new THREE.Vector3(...E.water.shallow) },
          uWaveA: { value: new THREE.Vector4(...S.waves.A) }, uWaveB: { value: new THREE.Vector4(...S.waves.B) }, uWaveC: { value: new THREE.Vector4(...S.waves.C) },
        });
      }
      const u = { ...env, uMap: { value: await tex(d.maps.uMap) } };
      if (name === 'bark' || name === 'leaf') u.uSway = { value: S.palmSway };
      const m = await this.shaderMaterial({ ...d, maps: {} }, u);
      return m;
    };
    const mats = {};
    for (const n of Object.keys(S.materials)) mats[n] = await mat(n);
    mats.water.depthWrite = false;
    const sky = new THREE.Mesh(new THREE.SphereGeometry(500, 32, 16), await this.shaderMaterial(S.sky, {
      uZenith: { value: new THREE.Vector3(...E.zenith) }, uHorizon: { value: new THREE.Vector3(...E.horizon) },
      uSunDir: env.uSunDir, uSunColor: env.uSunColor, uBands: { value: E.skyBands },
    }));
    sky.material.side = THREE.BackSide; sky.material.depthWrite = false; sky.frustumCulled = false; sky.renderOrder = -10;
    this.scene.add(sky);

    const objCache = {};
    this.tris = 0;
    for (const inst of S.objects) {
      objCache[inst.mesh] ||= new OBJLoader().parse(await fetchText(this.url(inst.mesh)));
      const o = objCache[inst.mesh].clone(true);
      o.traverse((m) => {
        if (!m.isMesh) return;
        const names = [].concat(m.material).map((x) => x.name);
        const ms = names.map((n) => mats[n] || mats.rock);
        m.material = ms.length === 1 ? ms[0] : ms;
        if (names.includes('water')) m.renderOrder = 2;
        if (names.includes('water')) m.frustumCulled = false;
      });
      if (inst.position) o.position.set(...inst.position);
      if (inst.rotation) o.rotation.set(...inst.rotation);
      if (inst.scale) o.scale.setScalar(inst.scale);
      o.name = inst.name;
      this.scene.add(o);
    }
    const ctex = await tex(S.clouds.texture);
    const cmat = await this.shaderMaterial({ vert: S.clouds.vert, frag: S.clouds.frag }, {
      uMap: { value: ctex }, uTint: { value: new THREE.Vector3(...E.cloudTint) }, uOpacity: { value: 0.95 }, uDrift: { value: S.clouds.drift },
    });
    cmat.transparent = true; cmat.depthWrite = false;
    const cgeo = new THREE.PlaneGeometry(1, 1);
    for (const c of S.clouds.cards) {
      const m = new THREE.Mesh(cgeo, cmat);
      m.position.set(...c.position); m.scale.set(c.scale[0], c.scale[1], 1);
      m.frustumCulled = false; m.renderOrder = -5;
      this.scene.add(m);
    }
    const pd = this.particlesDef;
    for (const sys of pd.systems) {
      const rnd = mulberry(sys.seed);
      const pos = new Float32Array(sys.count * 3), seed = new Float32Array(sys.count * 4);
      for (let i = 0; i < sys.count; i++) {
        for (let k = 0; k < 3; k++) pos[i * 3 + k] = sys.box.min[k] + rnd() * (sys.box.max[k] - sys.box.min[k]);
        for (let k = 0; k < 4; k++) seed[i * 4 + k] = rnd();
      }
      const g = new THREE.BufferGeometry();
      g.setAttribute('position', new THREE.BufferAttribute(pos, 3));
      g.setAttribute('aSeed', new THREE.BufferAttribute(seed, 4));
      const m = await this.shaderMaterial(pd.shader, {
        uWind: { value: new THREE.Vector3(...sys.wind) }, uBoxMin: { value: new THREE.Vector3(...sys.box.min) }, uBoxMax: { value: new THREE.Vector3(...sys.box.max) },
        uGustFreq: { value: sys.gustFrequency }, uGustStrength: { value: sys.gustStrength }, uSize: { value: sys.size }, uWobble: { value: sys.wobble },
        uColor: { value: new THREE.Vector3(...sys.color) }, uOpacity: { value: sys.opacity }, uStreak: { value: sys.streak },
      });
      m.transparent = true; m.depthWrite = false;
      if (sys.blending === 'additive') m.blending = THREE.AdditiveBlending;
      const pts = new THREE.Points(g, m);
      pts.frustumCulled = false; pts.renderOrder = 5; pts.name = sys.name;
      this.scene.add(pts);
    }
    if (!this.post) {
      this.post = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), await this.shaderMaterial(S.post, {
        tScene: { value: this.rt.texture }, uRes: { value: new THREE.Vector2(640, 448) },
        uDither: { value: 1 }, uScanlines: { value: 0.6 }, uBloom: { value: 0.9 }, uLevels: { value: 31 },
      }));
      this.postScene.add(this.post);
    }
    const pu = this.post.material.uniforms;
    pu.uDither.value = RS.dither; pu.uScanlines.value = RS.scanlines; pu.uBloom.value = RS.bloom; pu.uLevels.value = RS.colorLevels;
    this.resize();
  }
  onResize(w, h) {
    if (!this.rt || !this.S) return;
    const ih = this.S.renderSettings.internalResolution[1];
    const iw = Math.round(ih * (w / h));
    this.rt.setSize(iw, ih);
    this.post.material.uniforms.uRes.value.set(iw, ih);
    this.env.uResolution.value.set(iw, ih);
    this.drawHud();
  }
  update() {
    if (this.hud && (this._hudT = (this._hudT || 0) + 1) % 18 === 0) this.drawHud();
    if (this.cinematic) {
      const t = (this.time * 0.012) % 1;
      this.camera.position.copy(this.curve.getPointAt(t));
      const look = this.target.clone().add(new THREE.Vector3(Math.sin(this.time * 0.1) * 3, 0, 0));
      this.camera.lookAt(look);
      this.controls?.target.copy(look);
    }
  }
  tick(dt) {
    if (this.cinematic && this.controls) { this.controls.enabled = false; super.tick(dt); this.controls.enabled = true; return; }
    super.tick(dt);
  }
  draw() {
    this.renderer.setRenderTarget(this.rt);
    this.renderer.render(this.scene, this.camera);
    this.renderer.setRenderTarget(null);
    this.renderer.render(this.postScene, this.postCam);
  }
  attachHud(canvas) { this.hud = canvas; this.drawHud(); }
  setHud(on) { this.hudOn = on; this.drawHud(); }
  drawHud() {
    const c = this.hud;
    if (!c || !this.fontDef) return;
    const el = c.parentElement;
    c.width = el.clientWidth; c.height = el.clientHeight;
    const ctx = c.getContext('2d');
    ctx.clearRect(0, 0, c.width, c.height);
    if (!this.hudOn) return;
    ctx.imageSmoothingEnabled = false;
    // Integer pixel scales only, anchored bottom-right like a console title card.
    const s = Math.max(1, Math.floor(c.height / 420)), sub = Math.max(1, Math.floor(s / 2));
    const w = (t, k) => t.length * this.fontDef.advance * k;
    const lh = this.fontDef.lineHeight;
    const blink = Math.floor(performance.now() / 600) % 2;
    drawBitmapText(ctx, this.fontDef, this.fontImg, this.S.hud.title, c.width - w(this.S.hud.title, s) - 28, c.height - lh * (s + sub) - 40, s);
    if (blink || !this.playing) drawBitmapText(ctx, this.fontDef, this.fontImg, this.S.hud.subtitle, c.width - w(this.S.hud.subtitle, sub) - 28, c.height - lh * sub - 30, sub);
  }
  composite() {
    const c = document.createElement('canvas');
    c.width = this.canvas.width; c.height = this.canvas.height;
    const ctx = c.getContext('2d');
    ctx.drawImage(this.canvas, 0, 0);
    return c.toDataURL('image/png');
  }
  poseForCapture(i, n, hero) {
    this.cinematic = false;
    this.controls?.target.copy(this.home.target);
    if (hero) { this.camera.position.copy(this.home.position); this.camera.lookAt(this.home.target); this.time = 4; return; }
    this.camera.position.copy(this.curve.getPointAt(i / n));
    this.camera.lookAt(this.home.target);
    this.time = 4 + i * 0.4;
  }
  setCinematic(on) { this.cinematic = on; if (!on) this.resetView(); }
}

export function drawBitmapText(ctx, def, img, text, x, y, scale = 1) {
  const [cw, ch] = def.cell;
  let cx = x;
  for (const chr of text.toUpperCase()) {
    const idx = def.chars.indexOf(chr);
    if (idx >= 0) {
      const sx = (idx % def.columns) * cw, sy = Math.floor(idx / def.columns) * ch;
      ctx.drawImage(img, sx, sy, cw, ch, Math.round(cx), Math.round(y), cw * scale, ch * scale);
    }
    cx += def.advance * scale;
  }
}

// ----------------------------------------------------------------------------------------------- plug-in stage
// A bundle can ship its own real-time viewer (render.type = "module", render.module = "runtime/viewer.js").
// The module's default export receives a context and returns hooks; the studio wires up timeline,
// clip switching, controls and variants from what it returns. New request types need no engine changes.
class ModuleStage extends Stage {
  async load() {
    this.R = applyPatch(structuredClone(this.project.render), variantPatch(this.project, this.selection));
    const mod = await import(this.url(this.project.render.module) + '?v=' + this.project.version + '.' + (this.project.updated_at | 0));
    this.api = (await mod.default({
      THREE, stage: this, scene: this.scene, camera: this.camera, renderer: this.renderer, shared: this.shared, render: this.R,
      url: (p) => this.url(p), fetchText: (p) => fetchText(this.url(p)), fetchJSON: (p) => fetchJSON(this.url(p)),
      loadTex: (p, o) => loadTex(this.url(p), o), parseOBJ: (txt) => new OBJLoader().parse(txt),
      shaderMaterial: (def, extra) => this.shaderMaterial(def, extra), emit: (ev, ...a) => this.emit(ev, ...a),
    })) || {};
    this.renderer.toneMapping = THREE.NoToneMapping;
    this.syncTimeline();
    this.frameCamera(this.R.camera || { position: [3, 2, 4], target: [0, 0.5, 0] });
  }
  syncTimeline() { this.duration = this.api.duration; this.events = this.api.events || []; }
  get controlsSpec() { return this.api.controls || []; }
  update(dt) { this.api.update?.(dt, this.time); }
  draw() { this.api.draw ? this.api.draw() : super.draw(); }
  onResize(w, h) { this.api?.onResize?.(w, h); }
  async rebuild() { this.R = applyPatch(structuredClone(this.project.render), variantPatch(this.project, this.selection)); await this.api.applyVariant?.(this.R); }
  async setMode(mode) { this.mode = mode; await this.api.setMode?.(mode); }
  seek(t) { if (this.api.seek) this.api.seek(t); else this.time = t; }
  get frame() { const d = this.duration || 1; return Math.floor((((this.time % d) + d) % d) * (this.api.fps || 30)); }
  poseForCapture(i, n, hero) {
    if (this.api.pose) { this.controls?.target.copy(this.home.target); this.camera.position.copy(this.home.position); this.camera.lookAt(this.home.target); this.api.pose(i, n, hero); this.time = this.api.poseTime?.(i, n, hero) ?? this.time; }
    else super.poseForCapture(i, n, hero);
  }
  composite() { return this.api.composite ? this.api.composite() : super.composite(); }
  dispose() { this.api?.dispose?.(); super.dispose(); }
}

// ----------------------------------------------------------------------------------------------- public API
export async function createStage(canvas, project, opts = {}) {
  const Cls = { object: ObjectStage, animation: AnimationStage, scene: SceneStage, module: ModuleStage }[project.render?.type];
  if (!Cls) throw new Error('No renderer for ' + project.kind);
  const stage = new Cls(canvas, project, opts);
  await stage.load();
  stage.resize();
  if (opts.interactive !== false) stage.start();
  return stage;
}

// Generic preview of any single mesh file (OBJ or glTF) for the vault explorer.
export async function previewMesh(canvas, url) {
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  const scene = new THREE.Scene();
  scene.environment = new THREE.PMREMGenerator(renderer).fromScene(new RoomEnvironment(), 0.04).texture;
  const cam = new THREE.PerspectiveCamera(40, 1, 0.01, 500);
  const controls = new OrbitControls(cam, canvas);
  controls.enableDamping = true; controls.autoRotate = true;
  let obj, mixer;
  if (url.endsWith('.gltf')) {
    const g = await new GLTFLoader().loadAsync(url);
    obj = g.scene;
    if (g.animations.length) { mixer = new THREE.AnimationMixer(obj); mixer.clipAction(g.animations[0]).play(); }
  } else {
    obj = new OBJLoader().parse(await fetchText(url));
    obj.traverse((m) => { if (m.isMesh) m.material = new THREE.MeshStandardMaterial({ color: 0xc9c3ff, roughness: 0.45, metalness: 0.1, flatShading: false }); });
    const wire = obj.clone();
    wire.traverse((m) => { if (m.isMesh) m.material = new THREE.MeshBasicMaterial({ color: 0x000000, wireframe: true, transparent: true, opacity: 0.12 }); });
    obj.add(wire);
  }
  scene.add(obj);
  const box = new THREE.Box3().setFromObject(obj);
  const size = box.getSize(new THREE.Vector3()).length() || 2;
  const c = box.getCenter(new THREE.Vector3());
  cam.position.copy(c).add(new THREE.Vector3(size * 0.8, size * 0.5, size * 0.9));
  controls.target.copy(c);
  const clock = new THREE.Clock();
  let raf, dead = false;
  const loop = () => {
    if (dead) return;
    raf = requestAnimationFrame(loop);
    const w = canvas.clientWidth, h = canvas.clientHeight;
    if (canvas.width !== w * renderer.getPixelRatio()) { renderer.setSize(w, h, false); cam.aspect = w / h; cam.updateProjectionMatrix(); }
    mixer?.update(clock.getDelta());
    controls.update();
    renderer.render(scene, cam);
  };
  loop();
  return { dispose() { dead = true; cancelAnimationFrame(raf); controls.dispose(); renderer.dispose(); renderer.forceContextLoss?.(); } };
}
