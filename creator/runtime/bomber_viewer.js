// Project-TheCreator plug-in viewer · heavy bomber in turbulence.
// Baked flight clips drive the airframe + control surfaces; props, contrails, streaks and the sky run live.
export default async function setup(ctx) {
  const { THREE, scene, camera, render: R, stage } = ctx;
  const S = R.shaders;
  const data = await ctx.fetchJSON(R.anim);
  const clips = Object.fromEntries(data.clips.map((c) => [c.name, c]));
  const v3 = (a) => new THREE.Vector3(...a);
  const SKY = {
    uSunDir: { value: v3(R.sky.sun) }, uZenith: { value: v3(R.sky.zenith) }, uHorizon: { value: v3(R.sky.horizon) },
    uSunColor: { value: v3(R.sky.sunColor) }, uFlash: { value: 0 },
  };
  const FX = { uGust: { value: 0 }, uBuffet: { value: 0 }, uSpeed: { value: data.airspeed_ms } };
  const metal = { value: R.metal };

  // ---------------- materials
  const texCache = {};
  const tex = async (p, srgb) => (texCache[p + srgb] ||= await ctx.loadTex(p, { srgb }));
  const paintSets = {};
  const paintMat = async (name, flex) => {
    const [alb, rough, nrm] = name === 'metal' ? [R.prop, R.prop, R.textures.paint[2]] : name === 'prop' ? [R.prop, R.textures.paint[1], R.textures.paint[2]] : R.textures[name];
    const set = { uAlbedo: { value: await tex(alb, true) }, uRough: { value: await tex(rough, false) }, uNormalMap: { value: await tex(nrm, false) } };
    (paintSets[name] ||= []).push(set);
    return ctx.shaderMaterial({ vert: S.bomber_vert, frag: S.bomber_paint_frag }, { ...SKY, ...FX, ...set, uMetal: name === 'metal' ? { value: 1 } : metal, uFlexMask: { value: flex ? 1 : 0 } });
  };
  const glassMat = await ctx.shaderMaterial({ vert: S.bomber_vert, frag: S.canopy_glass_frag }, { ...SKY, ...FX, uFrame: { value: v3([0.18, 0.19, 0.16]) }, uFlexMask: { value: 0 } });
  glassMat.transparent = true;

  // ---------------- rig from OBJ (bind pose) + bone pivots
  const bonesDef = data.bones;
  const buildRig = async (path) => {
    const bones = {};
    for (const b of bonesDef) bones[b.name] = new THREE.Group();
    for (const b of bonesDef) {
      const pp = b.parent ? bonesDef.find((x) => x.name === b.parent).pivot : [0, 0, 0];
      bones[b.name].position.set(b.pivot[0] - pp[0], b.pivot[1] - pp[1], b.pivot[2] - pp[2]);
      bones[b.name].userData.rest = bones[b.name].position.clone();
      if (b.parent) bones[b.parent].add(bones[b.name]);
    }
    const obj = ctx.parseOBJ(await ctx.fetchText(path));
    const meshes = [];
    obj.traverse((m) => m.isMesh && meshes.push(m));
    let tris = 0;
    const cache = {};
    for (const m of meshes) {
      const bone = m.name.split('__')[0];
      const piv = bonesDef.find((x) => x.name === bone).pivot;
      m.geometry.translate(-piv[0], -piv[1], -piv[2]);
      const mn = [].concat(m.material)[0].name;
      const key = mn + (bone === 'airframe');
      m.material = mn === 'glass' ? glassMat : (cache[key] ||= await paintMat(mn, bone === 'airframe' && mn === 'wing'));
      if (mn === 'glass') m.renderOrder = 3;
      tris += m.geometry.attributes.position.count / 3;
      bones[bone].add(m);
    }
    return { bones, root: bones.airframe, tris };
  };
  let rig = await buildRig(R.mesh);
  scene.add(rig.root);

  // ---------------- sky
  const sky = new THREE.Mesh(new THREE.SphereGeometry(5000, 48, 24), await ctx.shaderMaterial({ vert: S.flight_sky_vert, frag: S.flight_sky_frag }, {
    ...SKY, uSpeed: FX.uSpeed, uCover: { value: R.sky.cover }, uStorm: { value: R.sky.storm }, uCloudLit: { value: v3(R.sky.cloudLit) }, uCloudShade: { value: v3(R.sky.cloudShade) },
  }));
  sky.material.side = THREE.BackSide; sky.material.depthWrite = false; sky.frustumCulled = false; sky.renderOrder = -10;
  scene.add(sky);
  camera.far = 12000; camera.near = 0.2; camera.updateProjectionMatrix();

  // ---------------- prop discs, contrails, streaks
  const discMat = await ctx.shaderMaterial({ vert: S.bomber_vert, frag: S.prop_disc_frag }, { ...FX, uAngle: { value: 0 }, uBlur: { value: 1 }, uFlexMask: { value: 0 } });
  discMat.transparent = true; discMat.depthWrite = false; discMat.side = THREE.DoubleSide;
  const attachDiscs = () => {
    for (let k = 0; k < 4; k++) {
      const d = new THREE.Mesh(new THREE.PlaneGeometry(3.7, 3.7), discMat);
      d.position.z = 0.12; d.renderOrder = 4; d.name = 'disc';
      rig.bones['prop_' + k].add(d);
    }
  };
  attachDiscs();
  const trailMat = await ctx.shaderMaterial({ vert: S.contrail_vert, frag: S.contrail_frag }, { ...FX, uOpacity: { value: 0.35 } });
  trailMat.transparent = true; trailMat.depthWrite = false; trailMat.side = THREE.DoubleSide;
  const trails = new THREE.Group();
  const N = 64;
  for (const b of bonesDef.filter((x) => x.name.startsWith('prop_'))) {
    const pos = [], age = [], side = [], idx = [];
    for (let i = 0; i <= N; i++) {
      const a = i / N;
      for (const s of [-1, 1]) { pos.push(b.pivot[0], b.pivot[1], b.pivot[2] - 4.5 - a * 140); age.push(a); side.push(s); }
      if (i < N) idx.push(i * 2, i * 2 + 1, i * 2 + 2, i * 2 + 1, i * 2 + 3, i * 2 + 2);
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
    g.setAttribute('aAge', new THREE.Float32BufferAttribute(age, 1));
    g.setAttribute('aSide', new THREE.Float32BufferAttribute(side, 1));
    g.setIndex(idx);
    const m = new THREE.Mesh(g, trailMat); m.frustumCulled = false; m.renderOrder = 5;
    trails.add(m);
  }
  scene.add(trails);
  const streakGeo = new THREE.BufferGeometry();
  const SP = [], SS = [];
  for (let i = 0; i < 700; i++) { SP.push((Math.random() - 0.5) * 70, (Math.random() - 0.5) * 26, (Math.random() - 0.5) * 160); SS.push(Math.random(), Math.random(), Math.random(), Math.random()); }
  streakGeo.setAttribute('position', new THREE.Float32BufferAttribute(SP, 3));
  streakGeo.setAttribute('aSeed', new THREE.Float32BufferAttribute(SS, 4));
  const streakMat = await ctx.shaderMaterial({ vert: S.speed_streaks_vert, frag: S.speed_streaks_frag }, { ...FX });
  streakMat.transparent = true; streakMat.depthWrite = false; streakMat.blending = THREE.AdditiveBlending;
  const streaks = new THREE.Points(streakGeo, streakMat); streaks.frustumCulled = false;
  scene.add(streaks);

  // ---------------- state
  const st = { clip: 'turbulence', t: 0, lastT: 0, amp: 1, blur: true, trails: true, doors: 0, doorsTarget: 0, cam: 'chase', lod: 'lod0', propA: 0, fadeFrom: null, fade: 1, prevPos: new THREE.Vector3() };
  const qa = new THREE.Quaternion(), qb = new THREE.Quaternion(), qi = new THREE.Quaternion();
  const sample = (clip, t) => {
    const c = clips[clip], n = c.frames.length, x = ((t % c.duration) + c.duration) % c.duration * data.fps;
    const i0 = Math.min(Math.floor(x), n - 1), i1 = (i0 + 1) % n, a = x - i0, A = c.frames[i0], B = c.frames[i1];
    const L = (k) => A[k] + (B[k] - A[k]) * a;
    return { p: A.p.map((v, k) => v + (B.p[k] - v) * a), q: qa.fromArray(A.q).slerp(qb.fromArray(B.q), a).toArray(),
      ail: L('ail'), elev: L('elev'), rud: L('rud'), gust: L('gust'), buffet: L('buffet'), flash: L('flash') };
  };
  const setClip = (name) => {
    st.fadeFrom = sample(st.clip, st.t); st.fade = 0; st.clip = name; st.t = 0;
    api.duration = clips[name].duration; api.events = clips[name].events;
    ctx.emit('clip'); ctx.emit('controls');
  };
  const camLocal = { cockpit: [[-0.45, 1.55, 7.6], [-0.45, 1.3, 40]], wing: [[-14.5, 0.9, -1.5], [0, 0, 2]], tail: [[0, 1.4, -13.5], [0, 0.3, -60]] };
  const tmp = new THREE.Vector3(), tmp2 = new THREE.Vector3();

  const api = {
    fps: data.fps,
    duration: clips.turbulence.duration,
    events: clips.turbulence.events,
    clipName: () => clips[st.clip].label,
    clipTime: () => st.t % clips[st.clip].duration,
    controls: [
      { type: 'select', label: 'Flight clip', options: data.clips.map((c) => [c.name, c.label]), get: () => st.clip, set: (v) => setClip(v) },
      { type: 'range', label: 'Turbulence scale', min: 0, max: 2.5, step: 0.05, get: () => st.amp, set: (v) => (st.amp = v) },
      { type: 'select', label: 'Camera', options: [['chase', 'Chase'], ['cockpit', 'Cockpit'], ['wing', 'Wing cam'], ['tail', 'Tail gunner']], get: () => st.cam, set: (v) => { st.cam = v; if (v === 'chase') stage.resetView(); } },
      { type: 'toggle', label: 'Propeller blur discs', get: () => st.blur, set: (v) => (st.blur = v) },
      { type: 'toggle', label: 'Trails', get: () => st.trails, set: (v) => (st.trails = trails.visible = v) },
      { type: 'toggle', label: 'Bomb bay doors open', get: () => st.doorsTarget > 0.5, set: (v) => (st.doorsTarget = v ? 1 : 0) },
      { type: 'select', label: 'Detail', options: [['lod0', 'LOD0 · hero'], ['lod1', 'LOD1']], get: () => st.lod, set: async (v) => {
        st.lod = v; scene.remove(rig.root); rig = await buildRig(v === 'lod0' ? R.mesh : R.lod1); attachDiscs(); scene.add(rig.root);
      } },
    ],
    update(dt, t) {
      let d = t - st.lastT; st.lastT = t;
      if (d < 0 || d > 0.25) d = 0;
      st.t += d; st.fade = Math.min(1, st.fade + d / 0.8);
      const s = sample(st.clip, st.t);
      if (st.fadeFrom && st.fade < 1) {
        const f = st.fade;
        for (const k of ['ail', 'elev', 'rud', 'gust', 'buffet', 'flash']) s[k] = st.fadeFrom[k] + (s[k] - st.fadeFrom[k]) * f;
        s.p = s.p.map((v, k) => st.fadeFrom.p[k] + (v - st.fadeFrom.p[k]) * f);
        s.q = qa.fromArray(st.fadeFrom.q).slerp(qb.fromArray(s.q), f).toArray();
      }
      const k = st.amp;
      const B = rig.bones;
      B.airframe.position.set(s.p[0] * k, s.p[1] * k, s.p[2] * k);
      B.airframe.quaternion.copy(qi.identity().slerp(qa.fromArray(s.q), Math.min(k, 1)));
      if (k > 1) B.airframe.quaternion.multiply(qb.identity().slerp(qa.fromArray(s.q), k - 1));
      B.aileron_r.rotation.x = s.ail * k; B.aileron_l.rotation.x = -s.ail * k;
      B.elevator_r.rotation.x = B.elevator_l.rotation.x = s.elev * k; B.rudder.rotation.y = s.rud * k;
      FX.uGust.value = s.gust * Math.min(k, 1.5); FX.uBuffet.value = s.buffet * k; SKY.uFlash.value = s.flash;
      const rpm = clips[st.clip].rpm;
      st.propA += d * (rpm / 60) * Math.PI * 2 * (stage.playing ? 1 : 0);
      for (let i = 0; i < 4; i++) {
        const p = B['prop_' + i];
        p.children.forEach((c) => { if (c.name !== 'disc') { c.visible = !st.blur; } else c.visible = st.blur; });
        p.rotation.z = (i < 2 ? 1 : -1) * (st.blur ? st.propA * 0.02 : st.propA * 0.017);
      }
      discMat.uniforms.uAngle.value = st.propA * 0.013;
      st.doors += (st.doorsTarget - st.doors) * Math.min(1, d * 2.5);
      B.bay_r.rotation.z = -1.35 * st.doors; B.bay_l.rotation.z = 1.35 * st.doors;
      trails.position.copy(B.airframe.position);
      // cameras
      B.airframe.updateMatrixWorld(true);
      if (st.cam === 'chase') {
        tmp.copy(B.airframe.position).sub(st.prevPos);
        camera.position.add(tmp);
        stage.controls?.target.add(tmp);
      } else {
        const [eye, look] = camLocal[st.cam];
        camera.position.copy(tmp.set(...eye).applyMatrix4(B.airframe.matrixWorld));
        const shake = s.gust * 0.05 * k + s.buffet * 0.02;
        camera.position.add(tmp2.set(Math.random() - 0.5, Math.random() - 0.5, 0).multiplyScalar(shake));
        stage.controls?.target.copy(tmp2.set(...look).applyMatrix4(B.airframe.matrixWorld));
        camera.lookAt(stage.controls?.target || tmp2);
      }
      st.prevPos.copy(B.airframe.position);
    },
    seek(t) { st.t = Math.max(0, t); },
    async applyVariant(R2) {
      for (const name of ['paint', 'wing', 'fin']) {
        const [alb, rough] = R2.textures[name];
        for (const set of paintSets[name] || []) { set.uAlbedo.value = await tex(alb, true); set.uRough.value = await tex(rough, false); }
      }
      metal.value = R2.metal;
      for (const [k, u] of [['sun', 'uSunDir'], ['zenith', 'uZenith'], ['horizon', 'uHorizon'], ['sunColor', 'uSunColor']]) SKY[u].value.set(...R2.sky[k]);
      const su = sky.material.uniforms;
      su.uCover.value = R2.sky.cover; su.uStorm.value = R2.sky.storm; su.uCloudLit.value.set(...R2.sky.cloudLit); su.uCloudShade.value.set(...R2.sky.cloudShade);
    },
    pose(i, n, hero) {
      st.cam = 'chase'; st.amp = 1; st.fade = 1; st.fadeFrom = null; st.lastT = 0; st.prevPos.set(0, 0, 0);
      st.clip = hero ? 'evasive' : 'turbulence'; st.t = hero ? 2.4 : (i / n) * clips.turbulence.duration;
      const off = camera.position.clone().sub(stage.controls?.target || new THREE.Vector3());
      if (!hero) off.applyAxisAngle(new THREE.Vector3(0, 1, 0), (i / n) * Math.PI * 2);
      camera.position.copy(off);
      stage.controls?.target.set(0, 0, 0);
      camera.lookAt(0, 0, 0);
    },
    poseTime: () => 0,
    statsLine: () => `${clips[st.clip].label} · ${data.airspeed_ms} m/s · gust ${FX.uGust.value.toFixed(2)} · aileron ${(rig.bones.aileron_r.rotation.x * 57.3).toFixed(1)}° · ${Math.round(rig.tris).toLocaleString()} tris`,
  };
  return api;
}
