// Project-TheCreator plug-in viewer · PS2/PS1 bear.
// Rigid-part rig driven by baked clips, a small state machine with cross-fades, and a low-res PS1 pipeline.
export default async function setup(ctx) {
  const { THREE, scene, renderer, camera, render: R } = ctx;
  const rig = await ctx.fetchJSON(R.anim);
  const clips = Object.fromEntries(rig.clips.map((c) => [c.name, c]));
  const v3 = (a) => new THREE.Vector3(...a);
  const U = {
    uSunDir: { value: v3(R.light.sun) }, uSunColor: { value: v3(R.light.sunColor) }, uAmbient: { value: v3(R.light.ambient) },
    uFogColor: { value: v3(R.light.fog) }, uSnapRes: { value: new THREE.Vector2(...R.output.res) }, uGlitch: { value: R.output.glitch },
    uAffine: { value: R.output.affine }, uDither: { value: R.output.dither },
  };
  const tints = {};
  const mats = {};
  const mat = async (name) => {
    if (mats[name]) return mats[name];
    const map = R.maps[name] || R.maps.muzzle;
    const tex = await ctx.loadTex(map, { srgb: false, nearest: true });
    tints[name] = { value: v3(R.tints[name] || [1, 1, 1]) };
    return (mats[name] = await ctx.shaderMaterial({ vert: R.shaders.vert, frag: R.shaders.frag }, { ...U, uMap: { value: tex }, uTint: tints[name], uTiling: { value: 1 } }));
  };

  // ---------------- rig: bone groups positioned at pivots, part meshes re-centred on their bone
  const bones = {};
  for (const b of rig.bones) { const g = new THREE.Group(); g.name = b.name; bones[b.name] = g; }
  for (const b of rig.bones) {
    const g = bones[b.name];
    const pp = b.parent ? rig.bones.find((x) => x.name === b.parent).pivot : [0, 0, 0];
    g.position.set(b.pivot[0] - pp[0], b.pivot[1] - pp[1], b.pivot[2] - pp[2]);
    g.userData.rest = g.position.clone();
    (b.parent ? bones[b.parent] : scene).add(g);
  }
  const bearObj = ctx.parseOBJ(await ctx.fetchText(R.mesh));
  const parts = [];
  bearObj.traverse((m) => m.isMesh && parts.push(m));
  let tris = 0;
  for (const m of parts) {
    const bone = m.name.split('__')[0];
    const piv = rig.bones.find((x) => x.name === bone).pivot;
    m.geometry.translate(-piv[0], -piv[1], -piv[2]);
    m.material = await mat([].concat(m.material)[0].name);
    tris += m.geometry.attributes.position.count / 3;
    bones[bone].add(m);
  }
  const root = bones.body;
  const mover = new THREE.Group();
  scene.add(mover);
  mover.add(root);

  const env = ctx.parseOBJ(await ctx.fetchText(R.env));
  const envMeshes = [];
  env.traverse((m) => m.isMesh && envMeshes.push(m));
  for (const m of envMeshes) m.material = await mat([].concat(m.material)[0].name);
  scene.add(env);
  scene.background = new THREE.Color(...R.light.sky);

  // ---------------- low-res frame + nearest blit
  const rt = new THREE.WebGLRenderTarget(320, 240, { minFilter: THREE.NearestFilter, magFilter: THREE.NearestFilter });
  const blitScene = new THREE.Scene(), blitCam = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);
  const blit = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), await ctx.shaderMaterial({ vert: R.shaders.blit_v, frag: R.shaders.blit_f },
    { tFrame: { value: rt.texture }, uRes: { value: new THREE.Vector2(320, 240) }, uLines: { value: 1 } }));
  blitScene.add(blit);
  const OUT = { ps1: { res: [320, 240], snap: true, affine: 1, dither: 1, lines: 1 }, ps2: { res: [640, 448], snap: false, affine: 0, dither: 0.7, lines: 0.6 }, hd: { res: [0, 0], snap: false, affine: 0, dither: 0, lines: 0 } };

  // ---------------- state machine
  const st = { clip: 'idle', t: 0, prev: null, fade: 1, demo: true, demoStep: 0, demoT: 0, stepped: false, roam: true, output: 'ps1', snap: true, lastT: 0, shake: 0, angle: 0, held: 0 };
  const DEMO = [['idle', 3], ['walk', 4.8], ['run', 3.3], ['attack', 1.8], ['idle', 1.5], ['walk', 2.4], ['death', 4.2]];
  const qa = new THREE.Quaternion(), qb = new THREE.Quaternion();

  const sample = (clip, t, out) => {
    const c = clips[clip], n = c.frames.length;
    const x = (c.loop ? ((t % c.duration) + c.duration) % c.duration : Math.min(t, c.duration)) * rig.fps;
    const i0 = Math.min(Math.floor(x), n - 1), i1 = st.stepped ? i0 : Math.min(i0 + 1, n - 1), a = x - i0;
    const A = c.frames[i0], B = c.frames[i1];
    for (const b of rig.bones) out[b.name] = qa.fromArray(A[b.name]).slerp(qb.fromArray(B[b.name]), a).toArray();
    out.t = A.t.map((v, k) => v + (B.t[k] - v) * a);
    return out;
  };
  const current = {};
  const apply = (pose) => {
    for (const b of rig.bones) bones[b.name].quaternion.fromArray(pose[b.name]);
    root.position.copy(root.userData.rest).add(new THREE.Vector3(...pose.t));
  };
  const play = (clip) => {
    if (clip === st.clip && clips[clip].loop) return;
    st.prev = JSON.parse(JSON.stringify(current));
    st.fade = 0; st.clip = clip; st.t = 0; st.held = 0;
    api.duration = clips[clip].duration; api.events = clips[clip].events;
    ctx.emit('clip'); ctx.emit('controls');
  };
  const applyOutput = () => {
    const o = OUT[st.output];
    U.uAffine.value = o.affine; U.uDither.value = o.dither; blit.material.uniforms.uLines.value = o.lines;
    st.snap = o.snap; api.onResize();
  };

  const api = {
    fps: rig.fps,
    duration: clips.idle.duration,
    events: clips.idle.events,
    clipName: () => st.clip,
    clipTime: () => Math.min(clips[st.clip].loop ? st.t % clips[st.clip].duration : st.t, clips[st.clip].duration),
    controls: [
      { type: 'select', label: 'State', options: rig.clips.map((c) => [c.name, c.name[0].toUpperCase() + c.name.slice(1)]), get: () => st.clip, set: (v) => { st.demo = false; play(v); } },
      { type: 'toggle', label: 'Demo: cycle all states', get: () => st.demo, set: (v) => { st.demo = v; st.demoStep = 0; st.demoT = 0; play(DEMO[0][0]); } },
      { type: 'toggle', label: 'Roam while walking/running', get: () => st.roam, set: (v) => (st.roam = v) },
      { type: 'select', label: 'Output', options: [['ps1', 'PS1 320×240'], ['ps2', 'PS2 640×448'], ['hd', 'Clean HD']], get: () => st.output, set: (v) => { st.output = v; applyOutput(); } },
      { type: 'range', label: 'Vertex glitch', min: 0, max: 3, step: 0.05, get: () => U.uGlitch.value, set: (v) => (U.uGlitch.value = v) },
      { type: 'toggle', label: 'Vertex snapping (wobble)', get: () => st.snap, set: (v) => { st.snap = v; api.onResize(); } },
      { type: 'toggle', label: 'Affine textures', get: () => U.uAffine.value > 0.5, set: (v) => (U.uAffine.value = v ? 1 : 0) },
      { type: 'toggle', label: 'Stepped 30 fps (no interpolation)', get: () => st.stepped, set: (v) => (st.stepped = v) },
    ],
    update(dt, t) {
      let d = t - st.lastT;
      st.lastT = t;
      if (d < 0 || d > 0.25) d = 0;
      st.t += d; st.fade = Math.min(1, st.fade + d / 0.25);
      const c = clips[st.clip];
      for (const ev of c.events) if (ev.type === 'hit' && st.t - d < ev.t && st.t >= ev.t) st.shake = 0.12;
      if (!c.loop && st.t >= c.duration) {
        st.held += d;
        if (st.clip === 'attack') play('idle');
        else if (st.clip === 'death' && st.held > 1.6 && st.demo) { mover.position.set(0, 0, 0); play('idle'); }
      }
      if (st.demo) {
        st.demoT += d;
        if (st.demoT > DEMO[st.demoStep][1]) { st.demoT = 0; st.demoStep = (st.demoStep + 1) % DEMO.length; play(DEMO[st.demoStep][0]); }
      }
      sample(st.clip, st.t, current);
      if (st.prev && st.fade < 1) {
        const blended = { t: current.t.map((v, k) => st.prev.t[k] + (v - st.prev.t[k]) * st.fade) };
        for (const b of rig.bones) blended[b.name] = qa.fromArray(st.prev[b.name]).slerp(qb.fromArray(current[b.name]), st.fade).toArray();
        apply(blended);
      } else apply(current);
      // roam in a circle while moving
      const speed = st.roam ? { walk: 0.9, run: 3.2 }[st.clip] || 0 : 0;
      if (speed) {
        st.angle += (d * speed) / 2.6;
        mover.position.set(Math.sin(st.angle) * 2.6, 0, Math.cos(st.angle) * 2.6 - 2.6);
        mover.rotation.y = st.angle + Math.PI / 2;
      }
      st.shake *= 0.86;
      scene.position.set((Math.random() - 0.5) * st.shake, (Math.random() - 0.5) * st.shake * 0.5, 0);
    },
    seek(t) { st.t = Math.max(0, t); st.fade = 1; },
    onResize() {
      const size = renderer.getDrawingBufferSize(new THREE.Vector2());
      const o = OUT[st.output];
      const h = o.res[1] || size.y, w = o.res[1] ? Math.round(h * (size.x / Math.max(size.y, 1))) : size.x;
      rt.setSize(w, h);
      blit.material.uniforms.uRes.value.set(w, h);
      U.uSnapRes.value.set(st.snap ? w : 0, st.snap ? h : 0);
    },
    draw() {
      renderer.setRenderTarget(rt);
      renderer.render(scene, camera);
      renderer.setRenderTarget(null);
      renderer.render(blitScene, blitCam);
    },
    applyVariant(R2) {
      for (const [k, v] of Object.entries(R2.tints)) tints[k]?.value.set(...v);
      U.uSunColor.value.set(...R2.light.sunColor); U.uAmbient.value.set(...R2.light.ambient); U.uFogColor.value.set(...R2.light.fog);
      scene.background.setRGB(...R2.light.sky);
    },
    pose(i, n, hero) {
      st.demo = false; st.roam = false; mover.position.set(0, 0, 0); mover.rotation.y = 0; st.prev = null; st.fade = 1;
      if (hero) { st.clip = 'attack'; st.t = 0.75; } else { st.clip = 'walk'; st.t = (i / n) * clips.walk.duration; }
      st.lastT = 0;
    },
    poseTime: () => 0,
    statsLine: () => `${rig.bones.length} bones · ${Math.round(tris)} tris · ${st.clip} ${st.t.toFixed(2)}s · ${rt.width}×${rt.height}`,
    dispose() { rt.dispose(); },
  };
  return api;
}
