"""Request: "A toon water shader with foam and caustics".

The shader is the product; a little pond diorama exists to show it off. Technique:
  pass 1  opaque scene -> render target (colour + depth texture)
  pass 2  opaque scene -> screen, then the water plane reads pass-1 depth to get water *thickness* per pixel:
          banded shallow->deep colour, intersection foam (noise-cut, animated), refraction of pass-1 colour,
          toon caustics, stepped sun glint, gentle vertex waves with crest foam.
Props use a 3-band cel shader + inverted-hull outlines; the lake bed receives animated caustics below the waterline.
"""
import math
import os
import shutil

from . import mesh as M
from . import procedural as P
from .glsl import HEADER


def ground_height(x, z):
    r = math.hypot(x, z * 1.15)
    bowl = -1.9 * (1 - P.smoothstep(4.0, 10.5, r)) + 0.55 * P.smoothstep(9.5, 12.0, r)
    island = 3.1 * math.exp(-(((x - 2.6) / 2.1) ** 2 + ((z + 1.0) / 1.7) ** 2))
    bumps = (P.fbm(x * 0.25 + 3, z * 0.25, 3, seed=4) - 0.5) * 0.5
    return bowl + island + bumps


def box(name, mat, sx, sy, sz):
    p = M.Part(name, mat)
    faces = [((1, 0, 0), (0, 1, 0), (0, 0, 1)), ((-1, 0, 0), (0, 1, 0), (0, 0, -1)), ((0, 1, 0), (0, 0, 1), (1, 0, 0)),
             ((0, -1, 0), (0, 0, -1), (1, 0, 0)), ((0, 0, 1), (1, 0, 0), (0, 1, 0)), ((0, 0, -1), (-1, 0, 0), (0, 1, 0))]
    for n, a, b in faces:
        base = len(p.pos)
        for su, sv in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            v = tuple((n[k] + a[k] * su + b[k] * sv) * (sx, sy, sz)[k] * 0.5 for k in range(3))
            p.pos.append(v)
            p.uv.append(((su + 1) / 2, (sv + 1) / 2))
        tri = [(base, base + 1, base + 2), (base, base + 2, base + 3)]
        for t in tri:
            nn = M.v_cross(M.v_sub(p.pos[t[1]], p.pos[t[0]]), M.v_sub(p.pos[t[2]], p.pos[t[0]]))
            p.tris.append(t if M.v_dot(nn, n) > 0 else (t[0], t[2], t[1]))
    return p


def build():
    meshes = {}
    floor = M.grid("lakebed", "ground", 26, 26, 72, 72, ground_height, 6)
    meshes["lakebed"] = [floor]
    meshes["water_plane"] = [M.grid("water", "water", 24, 24, 96, 96, None, 1)]
    rocks = []
    for i, (x, z, s) in enumerate(((-3.2, 2.4, 0.9), (-4.4, 1.2, 0.55), (5.6, 3.6, 0.75), (0.4, -5.8, 0.65))):
        def f(p, u, v, sd=i):
            n = P.fbm(p[0] * 1.4 + sd * 3, p[2] * 1.4 + p[1], 3, seed=sd + 2)
            r = 0.8 + n * 0.5
            return (p[0] * r * 1.2, p[1] * r * 0.85, p[2] * r)
        r = M.uv_sphere("rock_%d" % i, "rock", 9, 6, f).scale(s).translate((x, ground_height(x, z) * 0.6 - 0.1, z))
        rocks.append(r)
    meshes["rocks"] = rocks
    dock = []
    for i, (x, z) in enumerate(((-6.4, -3.0), (-6.4, -1.2), (-4.4, -3.0), (-4.4, -1.2), (-2.4, -3.0), (-2.4, -1.2))):
        post = M.lathe("post_%d" % i, "wood", [(0.13, -2.4), (0.13, 0.55), (0.1, 0.62)], 10, cap_top=True)
        dock.append(post.translate((x, 0, z)))
    for k in range(9):
        plank = box("plank_%d" % k, "wood", 0.42, 0.08, 2.3).translate((-6.6 + k * 0.5, 0.6, -2.1))
        dock.append(plank)
    meshes["dock"] = dock
    pads = []
    for i, (x, z) in enumerate(((0.8, 4.2), (1.6, 4.9), (-0.6, 5.1), (5.4, -2.6))):
        pad = M.lathe("lily_%d" % i, "lily", [(0.42, 0.0), (0.42, 0.03)], 14, cap_top=True).translate((x, 0.01, z))
        pads.append(pad)
    flower = M.uv_sphere("lily_flower", "flower", 8, 5).scale((0.13, 0.09, 0.13)).translate((1.6, 0.1, 4.9))
    meshes["lilies"] = pads + [flower]
    return meshes


def textures(out):
    res = 256

    def foam(u, v, x, y):
        a = P.fbm(u * 6, v * 6, 4, seed=3, period=6)
        b = P.fbm(u * 12 + 5, v * 12, 3, seed=9, period=12)
        return (a, b, 0.5, 1)
    P.render(os.path.join(out, "toon_foam_noise.png"), res, res, foam, alpha=False)

    def caustic(u, v, x, y):
        f1, f2, _, _ = P.voronoi(u * 6, v * 6, seed=11, period=6, jitter=0.9)
        e = 1 - P.smoothstep(0.0, 0.16, f2 - f1)
        g1, g2, _, _ = P.voronoi(u * 10 + 0.3, v * 10, seed=23, period=10, jitter=0.9)
        e2 = 1 - P.smoothstep(0.0, 0.14, g2 - g1)
        return (e, e2, 0, 1)
    P.render(os.path.join(out, "toon_caustics.png"), res, res, caustic, alpha=False)


def glsl(name, desc, body):
    return HEADER.format(name=name, desc=desc) + body

WATER_VERT = glsl("toon_water.vert", "Gentle summed sine waves; passes world position, wave height and clip position.", """
uniform float uTime;
uniform float uWaveSpeed;
uniform float uWaveHeight;
varying vec3  vWorld;
varying float vWave;
varying vec2  vUv;
void main() {
  vec4 wp = modelMatrix * vec4(position, 1.0);
  float t = uTime * uWaveSpeed;
  float w = sin(wp.x * 0.9 + t * 1.3) * 0.5 + sin(wp.z * 1.3 - t * 1.1) * 0.35 + sin((wp.x + wp.z) * 2.1 + t * 2.0) * 0.15;
  wp.y += w * uWaveHeight;
  vWave = w;
  vWorld = wp.xyz;
  vUv = uv;
  gl_Position = projectionMatrix * viewMatrix * wp;
}
""")

WATER_FRAG = glsl("toon_water.frag", "Depth-aware toon water: banded colour by thickness, noise-cut intersection foam, crest foam, refraction, toon caustics, stepped glint.", """
uniform sampler2D tDepth;
uniform sampler2D tScene;
uniform sampler2D uFoamTex;
uniform sampler2D uCausticTex;
uniform vec2  uResolution;
uniform float uNear;
uniform float uFar;
uniform float uTime;
uniform vec3  uShallow;
uniform vec3  uDeep;
uniform vec3  uFoamColor;
uniform vec3  uSunDir;
uniform float uBands;
uniform float uDepthMax;
uniform float uFoamDist;
uniform float uCaustics;
uniform float uRefract;
varying vec3  vWorld;
varying float vWave;
varying vec2  vUv;

float linearDepth(float d) {
  float z = d * 2.0 - 1.0;
  return 2.0 * uNear * uFar / (uFar + uNear - z * (uFar - uNear));
}

void main() {
  vec2 suv = gl_FragCoord.xy / uResolution;
  float thick = max(linearDepth(texture2D(tDepth, suv).r) - linearDepth(gl_FragCoord.z), 0.0);
  float t = clamp(thick / uDepthMax, 0.0, 1.0);
  float band = floor(t * uBands) / max(uBands - 1.0, 1.0);
  vec3 col = mix(uShallow, uDeep, clamp(band, 0.0, 1.0));

  // stylised refraction: see the bed through shallow water, wobbling with the foam noise
  vec2 n = (texture2D(uFoamTex, vWorld.xz * 0.12 + vec2(uTime * 0.02, uTime * 0.013)).rg - 0.5) * uRefract;
  vec3 under = texture2D(tScene, suv + n * (1.0 - t)).rgb;
  col = mix(under * mix(vec3(1.0), uShallow * 1.6, 0.55), col, 0.35 + 0.65 * smoothstep(0.0, 0.6, t));

  // toon caustics: two scrolling layers, min-combined, hard threshold
  vec2 cp = vWorld.xz * 0.22;
  float c = min(texture2D(uCausticTex, cp + vec2(uTime * 0.035, uTime * 0.01)).r, texture2D(uCausticTex, cp * 1.3 - vec2(uTime * 0.02, uTime * 0.03)).g);
  col += step(0.42, c) * uCaustics * (1.0 - t) * 0.55;

  // intersection foam: a band that breathes, cut by noise so it reads as hand-drawn
  float fn = texture2D(uFoamTex, vWorld.xz * 0.35 + vec2(uTime * 0.04, -uTime * 0.03)).r;
  float edge = 1.0 - clamp(thick / (uFoamDist * (0.85 + 0.15 * sin(uTime * 1.7 + vWorld.x))), 0.0, 1.0);
  float foam = step(1.0 - edge, fn * 0.6 + 0.18) * step(0.25, edge);
  float ring = step(0.9, fract(edge * 2.0 - uTime * 0.35)) * step(0.15, edge) * 0.8;
  float crest = step(0.78, vWave + fn * 0.35);
  foam = clamp(max(max(foam, ring), crest * 0.85), 0.0, 1.0);

  // stepped sun glint
  vec3 V = normalize(cameraPosition - vWorld);
  vec3 N = normalize(vec3(-cos(vWorld.x * 0.9 + uTime) * 0.12, 1.0, -cos(vWorld.z * 1.3 - uTime) * 0.12));
  float g = pow(max(dot(reflect(-normalize(uSunDir), N), V), 0.0), 60.0);
  col += step(0.5, g) * 0.6;
  col = mix(col, uFoamColor, foam);
  gl_FragColor = vec4(col, 1.0);
}
""")

PROP_VERT = glsl("toon_prop.vert", "Cel-shaded props; with uOutline > 0 the same program extrudes an inverted hull for ink lines.", """
uniform float uOutline;
varying vec3 vNormal;
varying vec3 vWorld;
varying vec2 vUv;
void main() {
  vec3 p = position + normal * uOutline;
  vec4 wp = modelMatrix * vec4(p, 1.0);
  vWorld = wp.xyz;
  vNormal = normalize(mat3(modelMatrix) * normal);
  vUv = uv;
  gl_Position = projectionMatrix * viewMatrix * wp;
}
""")

PROP_FRAG = glsl("toon_prop.frag", "3-band cel shading + rim; ground variant blends sand->grass by height and receives caustics under the waterline.", """
uniform vec3  uBase;
uniform vec3  uSunDir;
uniform vec3  uAmbient;
uniform float uIsGround;
uniform float uIsOutline;
uniform vec3  uInk;
uniform sampler2D uCausticTex;
uniform float uCaustics;
uniform float uTime;
varying vec3 vNormal;
varying vec3 vWorld;
varying vec2 vUv;

void main() {
  if (uIsOutline > 0.5) { gl_FragColor = vec4(uInk, 1.0); return; }
  vec3 base = uBase;
  if (uIsGround > 0.5) {
    vec3 sand = vec3(0.93, 0.82, 0.58), wet = vec3(0.62, 0.55, 0.40), grass = vec3(0.45, 0.78, 0.36);
    base = mix(wet, sand, step(-0.05, vWorld.y));
    base = mix(base, grass, step(0.55, vWorld.y + sin(vWorld.x * 3.0) * 0.06));
  }
  vec3 N = normalize(vNormal);
  float ndl = dot(N, normalize(uSunDir));
  float cel = ndl > 0.55 ? 1.0 : ndl > 0.1 ? 0.72 : 0.48;
  vec3 col = base * (uAmbient + cel * 0.75);
  vec3 V = normalize(cameraPosition - vWorld);
  col += step(0.62, 1.0 - max(dot(N, V), 0.0)) * 0.12;
  if (uIsGround > 0.5 && vWorld.y < 0.0) {
    vec2 cp = vWorld.xz * 0.22;
    float c = min(texture2D(uCausticTex, cp + vec2(uTime * 0.035, uTime * 0.01)).r, texture2D(uCausticTex, cp * 1.3 - vec2(uTime * 0.02, uTime * 0.03)).g);
    float depth = clamp(-vWorld.y / 2.0, 0.0, 1.0);
    col += step(0.42, c) * uCaustics * (1.0 - depth * 0.6) * 0.45;
  }
  gl_FragColor = vec4(col, 1.0);
}
""")

SKY_FRAG = glsl("toon_sky.frag", "Two-tone toon sky with a hard sun disc.", """
uniform vec3 uTop;
uniform vec3 uBottom;
uniform vec3 uSunDir;
varying vec3 vDir;
void main() {
  vec3 d = normalize(vDir);
  vec3 c = mix(uBottom, uTop, smoothstep(-0.05, 0.5, d.y));
  c = mix(c, vec3(1.0, 0.97, 0.85), step(0.9985, dot(d, normalize(uSunDir))));
  gl_FragColor = vec4(c, 1.0);
}
""")

SKY_VERT = glsl("toon_sky.vert", "Sky dome locked to the camera.", """
varying vec3 vDir;
void main() { vDir = position; gl_Position = (projectionMatrix * viewMatrix * vec4(position + cameraPosition, 1.0)).xyww; }
""")


def generate(out, spec=None):
    for d in ("meshes", "textures", "shaders", "runtime"):
        os.makedirs(os.path.join(out, d), exist_ok=True)
    textures(os.path.join(out, "textures"))
    shaders = {"toon_water.vert": WATER_VERT, "toon_water.frag": WATER_FRAG, "toon_prop.vert": PROP_VERT, "toon_prop.frag": PROP_FRAG,
               "toon_sky.vert": SKY_VERT, "toon_sky.frag": SKY_FRAG}
    for n, src in shaders.items():
        with open(os.path.join(out, "shaders", n), "w") as fh:
            fh.write(src)
    meshes = build()
    tris = {}
    for n, parts in meshes.items():
        for p in parts:
            p.compute_normals()
        tris[n] = sum(p.tri_count for p in parts)
        M.write_obj(os.path.join(out, "meshes", n + ".obj"), parts, header="Toon water demo - " + n)
    shutil.copy(os.path.join(os.path.dirname(__file__), "runtime", "toonwater_viewer.js"), os.path.join(out, "runtime", "viewer.js"))

    T = "textures/"
    files = [{"path": "meshes/%s.obj" % n, "kind": "mesh", "role": "demo diorama" if n != "water_plane" else "water surface", "meta": {"triangles": t}} for n, t in tris.items()]
    files += [
        {"path": T + "toon_foam_noise.png", "kind": "texture", "role": "foam / refraction noise (R,G)", "meta": {"width": 256}},
        {"path": T + "toon_caustics.png", "kind": "texture", "role": "caustic cells (2 scales in R,G)", "meta": {"width": 256}},
        {"path": "shaders/toon_water.vert", "kind": "shader", "role": "vertex · waves", "depends": ["meshes/water_plane.obj"]},
        {"path": "shaders/toon_water.frag", "kind": "shader", "role": "fragment · THE toon water", "depends": ["shaders/toon_water.vert", T + "toon_foam_noise.png", T + "toon_caustics.png"]},
        {"path": "shaders/toon_prop.vert", "kind": "shader", "role": "vertex · cel + outline hull"},
        {"path": "shaders/toon_prop.frag", "kind": "shader", "role": "fragment · cel + bed caustics", "depends": ["shaders/toon_prop.vert", T + "toon_caustics.png"]},
        {"path": "shaders/toon_sky.vert", "kind": "shader", "role": "vertex"},
        {"path": "shaders/toon_sky.frag", "kind": "shader", "role": "fragment", "depends": ["shaders/toon_sky.vert"]},
        {"path": "runtime/viewer.js", "kind": "data", "role": "plug-in viewer (depth pre-pass)", "depends": ["shaders/toon_water.frag", "shaders/toon_prop.frag", "shaders/toon_sky.frag"] + ["meshes/%s.obj" % n for n in tris]},
    ]
    look = lambda sh, dp, fo, top, bot, amb: {"water.shallow": sh, "water.deep": dp, "water.foam": fo, "sky.top": top, "sky.bottom": bot, "light.ambient": amb}
    render = {"type": "module", "module": "runtime/viewer.js",
              "camera": {"position": [9.5, 6.5, 11.5], "target": [0, -0.2, 0], "fov": 40},
              "meshes": ["meshes/%s.obj" % n for n in tris], "textures": {"foam": T + "toon_foam_noise.png", "caustics": T + "toon_caustics.png"},
              "shaders": {k.split(".")[0] + ("_v" if k.endswith("vert") else "_f"): "shaders/" + k for k in shaders},
              "water": {"shallow": [0.36, 0.93, 0.86], "deep": [0.06, 0.38, 0.62], "foam": [1, 1, 1], "bands": 4, "depthMax": 2.2, "foamDist": 0.4,
                        "caustics": 0.9, "refract": 0.05, "waveSpeed": 1.0, "waveHeight": 0.06},
              "sky": {"top": [0.36, 0.66, 0.98], "bottom": [0.82, 0.93, 1.0]}, "light": {"sun": [0.5, 0.8, 0.35], "ambient": [0.45, 0.47, 0.55]},
              "props": {"rock": [0.62, 0.6, 0.66], "wood": [0.62, 0.42, 0.26], "lily": [0.36, 0.72, 0.3], "flower": [1.0, 0.62, 0.82]}}
    variants = [
        {"id": "lagoon", "name": "Tropical Lagoon", "group": "Look", "default": True, "swatch": "#4fe3d0", "patch": {}},
        {"id": "arctic", "name": "Arctic", "group": "Look", "swatch": "#9fd2ff", "patch": look([0.72, 0.9, 1.0], [0.12, 0.3, 0.55], [1, 1, 1], [0.55, 0.72, 0.92], [0.92, 0.96, 1.0], [0.55, 0.6, 0.7])},
        {"id": "swamp", "name": "Swamp", "group": "Look", "swatch": "#7c9a3c", "patch": look([0.55, 0.66, 0.3], [0.14, 0.24, 0.12], [0.86, 0.9, 0.7], [0.55, 0.62, 0.5], [0.82, 0.84, 0.7], [0.4, 0.42, 0.36])},
        {"id": "dusk", "name": "Candy Dusk", "group": "Look", "swatch": "#ff8fb8", "patch": look([1.0, 0.62, 0.72], [0.33, 0.2, 0.55], [1.0, 0.94, 0.86], [0.38, 0.28, 0.62], [1.0, 0.7, 0.62], [0.55, 0.42, 0.55])},
    ]
    return {
        "kind": "shader", "files": files, "render": render, "variants": variants,
        "stats": {"shaders": len(shaders), "textures": 2, "triangles": sum(tris.values()), "per_mesh": tris, "passes": 2, "uniforms_tweakable": 9},
        "pipeline": [{"stage": s, "state": "done", "note": n} for s, n in [
            ("Interpret prompt", "shader · toon water · foam · caustics"),
            ("Uniform design", "9 artist controls: colours, bands, foam width, caustics, refraction, waves"),
            ("Vertex stage", "3 summed sines → height + crest mask"),
            ("Fragment stage", "depth pre-pass thickness → bands, noise-cut foam, rings, toon caustics, glint"),
            ("Preview render", "pond diorama: cel props + ink outlines + caustic lake bed"),
            ("Package bundle", "6 GLSL stages, 2 noise textures, 5 demo meshes, viewer")]],
    }
