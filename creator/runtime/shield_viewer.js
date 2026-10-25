// Project-TheCreator plug-in viewer · animated shield texture.
// Shows the flipbook (or its live GLSL twin) on a force-field sphere, a flat card over a checkerboard, or tiled 3x3.
export default async function setup(ctx) {
  const { THREE, scene, render: R } = ctx;
  const meta = await ctx.fetchJSON(R.meta);
  const sheet = await ctx.loadTex(R.sheet, { srgb: false, repeat: false });
  sheet.minFilter = THREE.LinearFilter; sheet.generateMipmaps = false;
  const st = { view: 'sphere', source: 'flipbook', fps: meta.fps, blend: true, fresnel: 0.8, additive: false };

  const tint = new THREE.Vector3(...R.tint);
  const common = { uTint: { value: tint }, uFresnel: { value: st.fresnel }, uTiling: { value: new THREE.Vector2(1, 1) } };
  const flip = await ctx.shaderMaterial({ vert: R.shaders.vert, frag: R.shaders.flipbook }, {
    ...common, uSheet: { value: sheet }, uGrid: { value: new THREE.Vector2(meta.sheet.columns, meta.sheet.rows) },
    uFrames: { value: meta.frames }, uFrame: { value: 0 }, uBlend: { value: 1 },
  });
  const live = await ctx.shaderMaterial({ vert: R.shaders.vert, frag: R.shaders.live }, { ...common, uLoop: { value: meta.frames / meta.fps } });
  for (const m of [flip, live]) { m.transparent = true; m.depthWrite = false; m.side = THREE.DoubleSide; }

  scene.add(new THREE.HemisphereLight(0xbfd6ff, 0x1a1420, 1.1));
  const key = new THREE.DirectionalLight(0xffffff, 2.2); key.position.set(2, 3, 2); scene.add(key);

  // force-field demo: a little drone core inside the bubble
  const core = new THREE.Group();
  const body = new THREE.Mesh(new THREE.IcosahedronGeometry(0.42, 1), new THREE.MeshStandardMaterial({ color: 0x3a3f52, metalness: 0.8, roughness: 0.3, flatShading: true }));
  const eye = new THREE.Mesh(new THREE.SphereGeometry(0.12, 16, 12), new THREE.MeshBasicMaterial({ color: 0x9fe8ff }));
  eye.position.set(0, 0.05, 0.38);
  const ring = new THREE.Mesh(new THREE.TorusGeometry(0.62, 0.035, 8, 48), new THREE.MeshStandardMaterial({ color: 0x8a90a8, metalness: 0.9, roughness: 0.25 }));
  ring.rotation.x = Math.PI / 2.3;
  core.add(body, eye, ring);
  const bubble = new THREE.Mesh(new THREE.SphereGeometry(1.15, 64, 40), flip);
  bubble.renderOrder = 2;
  const card = new THREE.Mesh(new THREE.PlaneGeometry(2.2, 2.2), flip);
  card.position.z = 0.02; card.renderOrder = 2;

  const checkerTex = (() => {
    const c = document.createElement('canvas'); c.width = c.height = 64;
    const g = c.getContext('2d');
    for (let y = 0; y < 8; y++) for (let x = 0; x < 8; x++) { g.fillStyle = (x + y) % 2 ? '#2b2f3d' : '#3b4052'; g.fillRect(x * 8, y * 8, 8, 8); }
    const t = new THREE.CanvasTexture(c); t.magFilter = THREE.NearestFilter; t.wrapS = t.wrapT = THREE.RepeatWrapping; t.repeat.set(6, 6);
    return t;
  })();
  const checker = new THREE.Mesh(new THREE.PlaneGeometry(4.4, 4.4), new THREE.MeshBasicMaterial({ map: checkerTex }));
  checker.position.z = -0.4;
  scene.add(core, bubble, card, checker);

  const applyView = () => {
    const sphere = st.view === 'sphere';
    core.visible = bubble.visible = sphere;
    card.visible = checker.visible = !sphere;
    common.uTiling.value.set(st.view === 'tile' ? 3 : 1, st.view === 'tile' ? 3 : 1);
    card.scale.setScalar(st.view === 'tile' ? 1.6 : 1);
    if (sphere) { ctx.camera.position.set(0, 0.6, 4.9); } else { ctx.camera.position.set(0, 0, 4.4); }
    ctx.stage.controls?.target.set(0, 0, 0);
  };
  const applySource = () => {
    const m = st.source === 'live' ? live : flip;
    bubble.material = card.material = m;
    m.blending = st.additive ? THREE.AdditiveBlending : THREE.NormalBlending;
  };
  applyView(); applySource();

  const api = {
    fps: st.fps,
    duration: meta.frames / st.fps,
    events: [{ t: 0, type: 'step', label: 'Loop seam' }, { t: meta.frames / st.fps / 2, type: 'step', label: 'Half' }],
    clipName: () => (st.source === 'live' ? 'live glsl' : 'flipbook'),
    controls: [
      { type: 'select', label: 'Preview on', options: [['sphere', 'Force field'], ['plane', 'Card + alpha'], ['tile', 'Tiling 3×3']], get: () => st.view, set: (v) => { st.view = v; applyView(); } },
      { type: 'select', label: 'Source', options: [['flipbook', 'Baked sheet'], ['live', 'Live GLSL']], get: () => st.source, set: (v) => { st.source = v; applySource(); ctx.emit('clip'); } },
      { type: 'range', label: 'Playback fps', min: 6, max: 60, step: 1, get: () => st.fps, set: (v) => { st.fps = v; api.fps = v; api.duration = meta.frames / v; api.events[1].t = api.duration / 2; live.uniforms.uLoop.value = api.duration; ctx.emit('clip'); } },
      { type: 'toggle', label: 'Blend between frames', get: () => st.blend, set: (v) => { st.blend = v; flip.uniforms.uBlend.value = v ? 1 : 0; } },
      { type: 'range', label: 'Fresnel rim', min: 0, max: 2, step: 0.05, get: () => st.fresnel, set: (v) => { st.fresnel = v; common.uFresnel.value = v; } },
      { type: 'toggle', label: 'Additive glow', get: () => st.additive, set: (v) => { st.additive = v; applySource(); } },
    ],
    update(dt, t) {
      flip.uniforms.uFrame.value = (t * st.fps) % meta.frames;
      core.rotation.y = t * 0.6;
      core.position.y = Math.sin(t * 1.3) * 0.05;
      ring.rotation.z = t * 1.4;
    },
    applyVariant(R2) { tint.set(...R2.tint); },
    pose(i, n, hero) { st.view = 'sphere'; applyView(); },
    poseTime: (i, n, hero) => (hero ? 8 / st.fps : (i / n) * (meta.frames / st.fps)),
    statsLine: () => `${meta.frames} frames · ${meta.frame_size.join('×')} · loop ${(meta.frames / st.fps).toFixed(2)}s`,
  };
  return api;
}
