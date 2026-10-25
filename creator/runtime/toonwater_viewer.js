// Project-TheCreator plug-in viewer · toon water shader.
// Two passes: opaque scene -> render target (colour + depth), then scene + water reading that depth for thickness.
export default async function setup(ctx) {
  const { THREE, scene, renderer, camera, render: R } = ctx;
  const S = R.shaders;
  const foamTex = await ctx.loadTex(R.textures.foam, { srgb: false });
  const causticTex = await ctx.loadTex(R.textures.caustics, { srgb: false });
  const v3 = (a) => new THREE.Vector3(...a);
  const sun = { value: v3(R.light.sun) }, ambient = { value: v3(R.light.ambient) };
  const caustics = { value: R.water.caustics };

  const rt = new THREE.WebGLRenderTarget(16, 16, { depthBuffer: true });
  rt.depthTexture = new THREE.DepthTexture(16, 16);

  const water = {
    tDepth: { value: rt.depthTexture }, tScene: { value: rt.texture }, uFoamTex: { value: foamTex }, uCausticTex: { value: causticTex },
    uResolution: { value: new THREE.Vector2(16, 16) }, uNear: { value: camera.near }, uFar: { value: camera.far },
    uShallow: { value: v3(R.water.shallow) }, uDeep: { value: v3(R.water.deep) }, uFoamColor: { value: v3(R.water.foam) }, uSunDir: sun,
    uBands: { value: R.water.bands }, uDepthMax: { value: R.water.depthMax }, uFoamDist: { value: R.water.foamDist }, uCaustics: caustics,
    uRefract: { value: R.water.refract }, uWaveSpeed: { value: R.water.waveSpeed }, uWaveHeight: { value: R.water.waveHeight },
  };
  const waterMat = await ctx.shaderMaterial({ vert: S.toon_water_v, frag: S.toon_water_f }, water);
  const propMats = {};
  const prop = async (name, extra) => (propMats[name] ||= await ctx.shaderMaterial({ vert: S.toon_prop_v, frag: S.toon_prop_f }, {
    uBase: { value: v3(R.props[name] || [0.8, 0.8, 0.8]) }, uSunDir: sun, uAmbient: ambient, uIsGround: { value: name === 'ground' ? 1 : 0 },
    uIsOutline: { value: 0 }, uOutline: { value: 0 }, uInk: { value: v3([0.08, 0.1, 0.16]) }, uCausticTex: { value: causticTex }, uCaustics: caustics, ...extra,
  }));
  const outlineMat = await ctx.shaderMaterial({ vert: S.toon_prop_v, frag: S.toon_prop_f }, {
    uBase: { value: v3([0, 0, 0]) }, uSunDir: sun, uAmbient: ambient, uIsGround: { value: 0 }, uIsOutline: { value: 1 },
    uOutline: { value: 0.035 }, uInk: { value: v3([0.08, 0.1, 0.16]) }, uCausticTex: { value: causticTex }, uCaustics: caustics,
  });
  outlineMat.side = THREE.BackSide;

  const sky = new THREE.Mesh(new THREE.SphereGeometry(400, 32, 16), await ctx.shaderMaterial({ vert: S.toon_sky_v, frag: S.toon_sky_f }, {
    uTop: { value: v3(R.sky.top) }, uBottom: { value: v3(R.sky.bottom) }, uSunDir: sun,
  }));
  sky.material.side = THREE.BackSide; sky.material.depthWrite = false; sky.frustumCulled = false; sky.renderOrder = -1;
  scene.add(sky);

  let waterMesh = null, tris = 0;
  const outlines = [];
  for (const path of R.meshes) {
    const obj = ctx.parseOBJ(await ctx.fetchText(path));
    const meshes = [];
    obj.traverse((m) => m.isMesh && meshes.push(m));
    for (const m of meshes) {
      const name = [].concat(m.material)[0].name;
      tris += m.geometry.attributes.position.count / 3;
      if (name === 'water') { m.material = waterMat; waterMesh = m; continue; }
      m.material = await prop(name);
      if (name !== 'ground') {
        const o = new THREE.Mesh(m.geometry, outlineMat);
        o.position.copy(m.position);
        m.parent.add(o);
        outlines.push(o);
      }
    }
    scene.add(obj);
  }

  const st = { outlines: true };
  const hex = (v) => '#' + v.toArray().map((c) => Math.round(Math.min(1, c) * 255).toString(16).padStart(2, '0')).join('');
  const fromHex = (s, vec) => vec.set(parseInt(s.slice(1, 3), 16) / 255, parseInt(s.slice(3, 5), 16) / 255, parseInt(s.slice(5, 7), 16) / 255);
  const U = (k) => water[k];

  return {
    controls: [
      { type: 'color', label: 'Shallow colour', get: () => hex(U('uShallow').value), set: (v) => fromHex(v, U('uShallow').value) },
      { type: 'color', label: 'Deep colour', get: () => hex(U('uDeep').value), set: (v) => fromHex(v, U('uDeep').value) },
      { type: 'range', label: 'Colour bands', min: 2, max: 8, step: 1, get: () => U('uBands').value, set: (v) => (U('uBands').value = v) },
      { type: 'range', label: 'Depth range', min: 0.5, max: 5, step: 0.1, get: () => U('uDepthMax').value, set: (v) => (U('uDepthMax').value = v) },
      { type: 'range', label: 'Foam width', min: 0.1, max: 1.5, step: 0.05, get: () => U('uFoamDist').value, set: (v) => (U('uFoamDist').value = v) },
      { type: 'range', label: 'Caustics', min: 0, max: 2, step: 0.05, get: () => caustics.value, set: (v) => (caustics.value = v) },
      { type: 'range', label: 'Refraction', min: 0, max: 0.15, step: 0.005, get: () => U('uRefract').value, set: (v) => (U('uRefract').value = v) },
      { type: 'range', label: 'Wave speed', min: 0, max: 3, step: 0.05, get: () => U('uWaveSpeed').value, set: (v) => (U('uWaveSpeed').value = v) },
      { type: 'range', label: 'Wave height', min: 0, max: 0.25, step: 0.01, get: () => U('uWaveHeight').value, set: (v) => (U('uWaveHeight').value = v) },
      { type: 'toggle', label: 'Ink outlines', get: () => st.outlines, set: (v) => { st.outlines = v; outlines.forEach((o) => (o.visible = v)); } },
    ],
    onResize() {
      const size = renderer.getDrawingBufferSize(new THREE.Vector2());
      rt.setSize(size.x, size.y);
      water.uResolution.value.copy(size);
    },
    draw() {
      water.uNear.value = camera.near; water.uFar.value = camera.far;
      waterMesh.visible = false;
      outlines.forEach((o) => (o.userData.v = o.visible, o.visible = false));
      renderer.setRenderTarget(rt);
      renderer.render(scene, camera);
      renderer.setRenderTarget(null);
      waterMesh.visible = true;
      outlines.forEach((o) => (o.visible = o.userData.v));
      renderer.render(scene, camera);
    },
    applyVariant(R2) {
      U('uShallow').value.set(...R2.water.shallow); U('uDeep').value.set(...R2.water.deep); U('uFoamColor').value.set(...R2.water.foam);
      sky.material.uniforms.uTop.value.set(...R2.sky.top); sky.material.uniforms.uBottom.value.set(...R2.sky.bottom);
      ambient.value.set(...R2.light.ambient);
      ctx.emit('controls');
    },
    statsLine: () => `2 passes · depth pre-pass ${rt.width}×${rt.height}`,
    dispose() { rt.dispose(); },
  };
}
