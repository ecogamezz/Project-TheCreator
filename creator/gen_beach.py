"""Example 2 - Sandy beach, clean waves, PlayStation 2 look: 128px dithered textures, Gouraud vertex lighting,
distance fog, 640x448 internal resolution, simple billboard clouds, three wind-driven particle systems."""
import json
import math
import os

from . import bitfont
from . import mesh as M
from . import procedural as P
from .glsl import HEADER


def shore_z(x):
    return -4.0 + 3.0 * math.sin(x * 0.05) + 1.2 * math.sin(x * 0.13 + 1.0)


def sand_height(x, z):
    d = z - shore_z(x)
    h = d * 0.065
    if d > 0:
        h += 0.06 * math.sin(x * 1.3 + z * 0.4) * P.smoothstep(2, 6, d)
    dune = P.smoothstep(10, 30, d)
    h += dune * (0.4 + 2.2 * P.fbm(x * 0.045 + 3, z * 0.05, 3, seed=2))
    return h


# ----------------------------------------------------------------------------- PS2 textures (128px, 5-bit dithered)

def ps2(fn, levels=28):
    return lambda u, v, x, y: P.ps2_quantize(fn(u, v, x, y), x, y, levels)


def textures(out):
    def sand(u, v, x, y):
        n = P.fbm(u * 8, v * 8, 4, seed=1, period=8)
        grain = P._hash(x, y, 3)
        ripple = 0.5 + 0.5 * math.sin((v + P.fbm(u * 4, v * 4, 2, seed=9, period=4) * 0.15) * math.pi * 2 * 9)
        c = P.mix((0.82, 0.68, 0.46), (0.97, 0.88, 0.66), n * 0.7 + ripple * 0.18 + grain * 0.12)
        if grain > 0.985:
            c = (1.0, 0.98, 0.9)
        return c + (1,)
    P.render(os.path.join(out, "sand.png"), 128, 128, ps2(sand), alpha=False)

    def water(u, v, x, y):
        f1, f2, _, _ = P.voronoi(u * 5, v * 5, seed=4, period=5)
        caustic = P.smoothstep(0.0, 0.18, f2 - f1)
        n = P.fbm(u * 6, v * 6, 3, seed=6, period=6)
        c = P.mix((0.55, 0.88, 0.95), (0.20, 0.55, 0.78), caustic * 0.75 + n * 0.25)
        return c + (1,)
    P.render(os.path.join(out, "water.png"), 128, 128, ps2(water), alpha=False)

    def cloud(u, v, x, y):
        d = 0.0
        for cx, cy, r in ((0.3, 0.55, 0.22), (0.5, 0.45, 0.28), (0.7, 0.55, 0.2), (0.42, 0.62, 0.18), (0.6, 0.62, 0.17)):
            d = max(d, 1 - math.hypot((u - cx) / r, (v - cy) / (r * 1.25)))
        d *= P.smoothstep(0.98, 0.7, v) * P.smoothstep(0.1, 0.32, v)
        n = P.fbm(u * 7, v * 5, 3, seed=8)
        a = P.smoothstep(0.0, 0.25, d + (n - 0.5) * 0.25)
        shade = P.mix((0.72, 0.78, 0.9), (1, 1, 1), P.smoothstep(0.35, 0.75, 1 - v + n * 0.2))
        a = round(a * 4) / 4                                            # stepped alpha = PS2 cloud card vibe
        return shade + (a,)
    P.render(os.path.join(out, "cloud.png"), 128, 64, ps2(cloud, 20))

    def leaf(u, v, x, y):
        w = 0.5 * (1 - v) ** 0.6 + 0.03
        du = abs(u - 0.5)
        tooth = 0.5 + 0.5 * math.sin(v * 70)
        inside = du < w * (0.75 + 0.25 * tooth)
        rib = du < 0.02
        g = P.fbm(u * 6, v * 12, 2, seed=5)
        c = P.mix((0.12, 0.42, 0.12), (0.42, 0.72, 0.22), g * 0.8 + (1 - du / max(w, 0.01)) * 0.3)
        if rib:
            c = (0.62, 0.66, 0.30)
        return c + ((1.0 if inside else 0.0),)
    P.render(os.path.join(out, "palm_leaf.png"), 64, 128, ps2(leaf, 20))

    def bark(u, v, x, y):
        ring = 0.5 + 0.5 * math.sin(v * math.pi * 2 * 14 + P.fbm(u * 4, v * 4, 2, seed=3, period=4) * 2)
        n = P.fbm(u * 6, v * 12, 3, seed=7, period=6)
        c = P.mix((0.30, 0.20, 0.12), (0.62, 0.48, 0.32), ring * 0.55 + n * 0.45)
        return c + (1,)
    P.render(os.path.join(out, "palm_bark.png"), 64, 128, ps2(bark), alpha=False)

    def rock(u, v, x, y):
        n = P.fbm(u * 6, v * 6, 4, seed=12, period=6)
        f1, f2, cid, _ = P.voronoi(u * 4, v * 4, seed=3, period=4)
        c = P.mix((0.36, 0.33, 0.30), (0.66, 0.62, 0.56), n * 0.7 + cid * 0.3)
        c = P.mix(c, (0.2, 0.18, 0.17), 1 - P.smoothstep(0.0, 0.08, f2 - f1))
        return c + (1,)
    P.render(os.path.join(out, "rock.png"), 64, 64, ps2(rock), alpha=False)

    def stripes(colors):
        def fn(u, v, x, y):
            c = colors[int(u * 8) % 2]
            n = P.fbm(u * 8, v * 8, 2, seed=2)
            return P.mix(c, (1, 1, 1), n * 0.12) + (1,)
        return fn
    P.render(os.path.join(out, "umbrella.png"), 64, 64, ps2(stripes([(0.92, 0.22, 0.22), (0.98, 0.95, 0.88)])), alpha=False)
    P.render(os.path.join(out, "towel.png"), 64, 64,
             ps2(lambda u, v, x, y: stripes([(0.15, 0.4, 0.85), (0.98, 0.84, 0.25)])(v, u, y, x)), alpha=False)


# ----------------------------------------------------------------------------- geometry

def palm():
    trunk = M.lathe("trunk", "bark", [(0.3 - 0.13 * t / 8, 7.0 * t / 8) for t in range(9)], 8)
    trunk.transform(lambda p: (p[0] + 0.045 * p[1] ** 2, p[1], p[2]))
    top = (0.045 * 49, 7.0, 0.0)
    fronds = M.Part("fronds", "leaf")
    for k in range(9):
        a = k / 9 * 2 * math.pi + (0.3 if k % 2 else 0)
        L, W = 3.4 + 0.4 * math.sin(k * 2.1), 0.95
        strip = M.Part("f", "leaf")
        segs = 6
        for i in range(segs + 1):
            t = i / segs
            x = t * L
            y = 0.5 * t - 1.6 * t * t
            for side in (-1, 1):
                strip.pos.append((x, y - 0.12 * abs(side) * t, side * W * 0.5 * (1 - t * 0.6)))
                strip.uv.append((0.5 + side * 0.5, 1 - t))
        for i in range(segs):
            a0 = i * 2
            strip.tris += [(a0, a0 + 1, a0 + 2), (a0 + 1, a0 + 3, a0 + 2)]
        strip.rotate(ry=a).translate(top)
        fronds.append(strip)
    nuts = M.Part("coconuts", "bark")
    for k in range(3):
        a = k / 3 * 2 * math.pi
        nut = M.uv_sphere("n", "bark", 8, 5).scale(0.2).translate((top[0] + 0.28 * math.cos(a), top[1] - 0.25, 0.28 * math.sin(a)))
        nuts.append(nut)
    return [trunk, fronds, nuts]


def rock(seed):
    def f(p, u, v):
        n = P.fbm(p[0] * 1.3 + seed, p[2] * 1.3 + p[1], 3, seed=seed)
        r = 0.75 + n * 0.55
        return (p[0] * r * 1.3, max(p[1] * r * 0.8, -0.2), p[2] * r)
    r = M.uv_sphere("rock", "rock", 10, 6, f)
    r.uv = [(u * 2, v) for u, v in r.uv]
    return [r]


def umbrella():
    pole = M.lathe("pole", "umbrella", [(0.05, 0), (0.05, 2.6)], 6)
    canopy = M.lathe("canopy", "umbrella", [(1.6, 2.15), (1.3, 2.35), (0.8, 2.55), (0.0, 2.75)], 16)
    under = M.lathe("canopy_under", "umbrella", [(1.6, 2.15), (0.0, 2.65)], 16).flip()
    return [pole, canopy, under]


# ----------------------------------------------------------------------------- shaders

def glsl(name, desc, body):
    return HEADER.format(name=name, desc=desc) + body

WORLD_VERT = glsl("ps2_world.vert", "Gouraud (per-vertex) lighting like the Emotion Engine VU1 path, fog depth, optional vertex jitter + palm sway.", """
uniform vec3  uSunDir;
uniform vec3  uSunColor;
uniform vec3  uAmbient;
uniform float uTime;
uniform float uSway;
uniform float uSnap;
uniform vec2  uResolution;
varying vec2  vUv;
varying vec3  vLight;
varying vec3  vWorld;
varying float vFogDepth;

void main() {
  vec3 p = position;
  float h = max(p.y, 0.0);
  float phase = modelMatrix[3][0] * 0.37 + modelMatrix[3][2] * 0.21;
  p.x += sin(uTime * 1.25 + phase) * 0.011 * h * h * uSway;
  p.z += cos(uTime * 0.95 + phase) * 0.008 * h * h * uSway;
  vec4 wp = modelMatrix * vec4(p, 1.0);
  vWorld = wp.xyz;
  vec3 n = normalize(mat3(modelMatrix) * normal);
  float ndl = max(dot(n, normalize(uSunDir)), 0.0);
  vLight = uAmbient + uSunColor * ndl;
  vec4 mv = viewMatrix * wp;
  vFogDepth = -mv.z;
  vec4 cp = projectionMatrix * mv;
  if (uSnap > 0.0) {                                        // integer-ish screen snapping (toggle)
    vec2 grid = uResolution * 0.5 / uSnap;
    cp.xy = floor(cp.xy / cp.w * grid + 0.5) / grid * cp.w;
  }
  vUv = uv;
  gl_Position = cp;
}
""")

WORLD_FRAG = glsl("ps2_world.frag", "Texture x vertex light, alpha test, wet-sand band, linear distance fog.", """
uniform sampler2D uMap;
uniform vec3  uTint;
uniform vec3  uFogColor;
uniform float uFogNear;
uniform float uFogFar;
uniform float uAlphaTest;
uniform float uWetLine;
uniform float uUvScale;
varying vec2  vUv;
varying vec3  vLight;
varying vec3  vWorld;
varying float vFogDepth;

void main() {
  vec4 t = texture2D(uMap, vUv * uUvScale);
  if (t.a < uAlphaTest) discard;
  vec3 c = t.rgb * uTint * vLight;
  if (uWetLine > 0.0) {
    float wet = 1.0 - smoothstep(0.02, uWetLine, vWorld.y);
    c *= mix(1.0, 0.64, wet);
    c = mix(c, c * vec3(0.9, 0.95, 1.05), wet);
  }
  c = mix(c, uFogColor, smoothstep(uFogNear, uFogFar, vFogDepth));
  gl_FragColor = vec4(c, 1.0);
}
""")

WATER_VERT = glsl("water.vert", "Three summed Gerstner waves rolling toward the shore, attenuated in the shallows.", """
uniform float uTime;
uniform vec4  uWaveA;   // dir.xy, steepness, wavelength
uniform vec4  uWaveB;
uniform vec4  uWaveC;
varying vec2  vUv;
varying vec3  vWorld;
varying vec3  vNormal;
varying float vCrest;
varying float vFogDepth;

float shoreZ(float x) { return -4.0 + 3.0 * sin(x * 0.05) + 1.2 * sin(x * 0.13 + 1.0); }

vec3 gerstner(vec4 w, vec3 p, float amp, inout vec3 T, inout vec3 B) {
  float k = 6.28318 / w.w;
  float c = sqrt(9.8 / k);
  vec2 d = normalize(w.xy);
  float f = k * (dot(d, p.xz) - c * uTime * 0.55);
  float s = w.z * amp;
  float a = s / k;
  T += vec3(-d.x * d.x * s * sin(f), d.x * s * cos(f), -d.x * d.y * s * sin(f));
  B += vec3(-d.x * d.y * s * sin(f), d.y * s * cos(f), -d.y * d.y * s * sin(f));
  return vec3(d.x * a * cos(f), a * sin(f), d.y * a * cos(f));
}

void main() {
  vec3 p = (modelMatrix * vec4(position, 1.0)).xyz;
  float depth = shoreZ(p.x) - p.z;                         // metres out to sea
  float amp = smoothstep(-1.0, 14.0, depth) * 0.85 + 0.15;
  vec3 T = vec3(1.0, 0.0, 0.0), B = vec3(0.0, 0.0, 1.0);
  vec3 g = p;
  g += gerstner(uWaveA, p, amp, T, B);
  g += gerstner(uWaveB, p, amp, T, B);
  g += gerstner(uWaveC, p, amp, T, B);
  vCrest = g.y;
  vNormal = normalize(cross(B, T));
  vWorld = g;
  vUv = p.xz * 0.08;
  vec4 mv = viewMatrix * vec4(g, 1.0);
  vFogDepth = -mv.z;
  gl_Position = projectionMatrix * mv;
}
""")

WATER_FRAG = glsl("water.frag", "Two scrolling 128px layers, crest + shoreline foam bands, stepped sun glint, shallow transparency.", """
uniform sampler2D uMap;
uniform float uTime;
uniform vec3  uSunDir;
uniform vec3  uSunColor;
uniform vec3  uAmbient;
uniform vec3  uDeep;
uniform vec3  uShallow;
uniform vec3  uFogColor;
uniform float uFogNear;
uniform float uFogFar;
varying vec2  vUv;
varying vec3  vWorld;
varying vec3  vNormal;
varying float vCrest;
varying float vFogDepth;

float shoreZ(float x) { return -4.0 + 3.0 * sin(x * 0.05) + 1.2 * sin(x * 0.13 + 1.0); }

void main() {
  vec3 N = normalize(vNormal);
  vec3 V = normalize(cameraPosition - vWorld);
  float depth = shoreZ(vWorld.x) - vWorld.z;
  vec3 t1 = texture2D(uMap, vUv + vec2(uTime * 0.012, uTime * 0.02)).rgb;
  vec3 t2 = texture2D(uMap, vUv * 1.7 - vec2(uTime * 0.017, -uTime * 0.009)).rgb;
  vec3 base = mix(uShallow, uDeep, smoothstep(0.0, 22.0, depth));
  vec3 c = base * (t1 * 0.6 + t2 * 0.5) * 1.15;
  c *= uAmbient + uSunColor * max(dot(N, normalize(uSunDir)), 0.0) * 0.8;

  // "Clean waves": crisp foam lines marching toward the beach + wash at the shoreline.
  float band = fract(depth * 0.12 + uTime * 0.11);
  float lines = smoothstep(0.90, 0.96, band) * smoothstep(1.0, 0.97, band) * smoothstep(26.0, 3.0, depth);
  float wash = smoothstep(1.6, 0.2, depth + sin(uTime * 0.9 + vWorld.x * 0.2) * 0.6);
  float crest = smoothstep(0.32, 0.5, vCrest) * smoothstep(-2.0, 8.0, depth);
  float foam = clamp(lines + wash + crest, 0.0, 1.0);
  foam = floor(foam * 3.0 + 0.5) / 3.0;                     // posterised foam
  c = mix(c, vec3(0.97, 0.99, 1.0), foam * 0.9);

  vec3 H = normalize(normalize(uSunDir) + V);
  float glint = pow(max(dot(N, H), 0.0), 220.0);
  c += uSunColor * step(0.4, glint) * 0.9;

  float alpha = mix(0.55, 0.96, smoothstep(0.0, 6.0, depth));
  alpha = max(alpha, foam);
  c = mix(c, uFogColor, smoothstep(uFogNear, uFogFar, vFogDepth));
  gl_FragColor = vec4(c, alpha);
}
""")

SKY_VERT = glsl("sky.vert", "Infinite sky dome: follows the camera, writes at far depth.", """
varying vec3 vDir;
void main() {
  vDir = normalize(position);
  vec4 mv = viewMatrix * vec4(position + cameraPosition, 1.0);
  gl_Position = (projectionMatrix * mv).xyww;
}
""")

SKY_FRAG = glsl("sky.frag", "Banded gradient sky + sun disc with halo. Posterised like a 2001 skybox.", """
uniform vec3  uZenith;
uniform vec3  uHorizon;
uniform vec3  uSunDir;
uniform vec3  uSunColor;
uniform float uBands;
varying vec3  vDir;

void main() {
  vec3 d = normalize(vDir);
  float h = clamp(d.y, 0.0, 1.0);
  float t = pow(h, 0.45);
  t = floor(t * uBands) / uBands;
  vec3 c = mix(uHorizon, uZenith, t);
  float s = max(dot(d, normalize(uSunDir)), 0.0);
  c += uSunColor * (step(0.9993, s) * 1.6 + pow(s, 64.0) * 0.45 + pow(s, 6.0) * 0.12);
  if (d.y < 0.0) c = uHorizon * 0.9;
  gl_FragColor = vec4(c, 1.0);
}
""")

CLOUD_VERT = glsl("cloud.vert", "Camera-facing cloud card (billboard) with slow drift.", """
uniform float uTime;
uniform float uDrift;
varying vec2  vUv;
varying float vFogDepth;
void main() {
  vec3 center = modelMatrix[3].xyz;
  center.x = mod(center.x + uTime * uDrift + 160.0, 320.0) - 160.0;
  vec2 size = vec2(length(modelMatrix[0].xyz), length(modelMatrix[1].xyz));
  vec4 mv = viewMatrix * vec4(center, 1.0);
  mv.xy += position.xy * size;
  vUv = uv;
  vFogDepth = -mv.z;
  gl_Position = projectionMatrix * mv;
}
""")

CLOUD_FRAG = glsl("cloud.frag", "Stepped-alpha cloud card tinted by the time-of-day sky.", """
uniform sampler2D uMap;
uniform vec3 uTint;
uniform float uOpacity;
varying vec2 vUv;
void main() {
  vec4 t = texture2D(uMap, vUv);
  if (t.a < 0.05) discard;
  gl_FragColor = vec4(t.rgb * uTint, t.a * uOpacity);
}
""")

WIND_VERT = glsl("wind_particles.vert", "GPU-advected particles: wind + gusts + curl-ish wobble, wrapped in an emitter box.", """
attribute vec4 aSeed;
uniform float uTime;
uniform vec3  uWind;
uniform vec3  uBoxMin;
uniform vec3  uBoxMax;
uniform float uGustFreq;
uniform float uGustStrength;
uniform float uSize;
uniform float uWobble;
varying float vAlpha;
varying float vStretch;

void main() {
  float t = uTime + aSeed.w * 37.0;
  vec3 span = uBoxMax - uBoxMin;
  float gust = 1.0 + uGustStrength * sin(uTime * uGustFreq + position.x * 0.03 + aSeed.y * 2.0);
  vec3 p = position + uWind * t * (0.65 + aSeed.x * 0.7) * gust;
  p.y += sin(t * 2.1 + aSeed.y * 6.283) * uWobble;
  p.z += cos(t * 1.3 + aSeed.z * 6.283) * uWobble * 1.4;
  p = uBoxMin + mod(p - uBoxMin, span);
  vec3 rel = (p - uBoxMin) / span;
  vAlpha = smoothstep(0.0, 0.12, rel.x) * smoothstep(1.0, 0.88, rel.x) * smoothstep(0.0, 0.1, rel.z) * smoothstep(1.0, 0.9, rel.z);
  vAlpha *= 0.55 + 0.45 * sin(t * 3.0 + aSeed.x * 9.0);
  vStretch = gust;
  vec4 mv = viewMatrix * vec4(p, 1.0);
  gl_PointSize = uSize * (0.5 + aSeed.x) * 260.0 / max(-mv.z, 0.5);
  gl_Position = projectionMatrix * mv;
}
""")

WIND_FRAG = glsl("wind_particles.frag", "Soft horizontal streak sprite.", """
uniform vec3  uColor;
uniform float uOpacity;
uniform float uStreak;
varying float vAlpha;
varying float vStretch;
void main() {
  vec2 q = (gl_PointCoord - 0.5) * vec2(1.0, uStreak * vStretch);
  float d = length(q) * 2.0;
  float a = smoothstep(1.0, 0.2, d) * vAlpha * uOpacity;
  if (a < 0.02) discard;
  gl_FragColor = vec4(uColor, a);
}
""")

POST_FRAG = glsl("ps2_post.frag", "Final blit: nearest upscale of the 640x448 buffer, soft glow, 16-bit ordered dither, interlace lines, vignette.", """
uniform sampler2D tScene;
uniform vec2  uRes;
uniform float uDither;
uniform float uScanlines;
uniform float uBloom;
uniform float uLevels;
varying vec2  vUv;

float bayer4(vec2 p) {
  vec2 f = mod(floor(p), 4.0);
  float m[16];
  m[0]=0.0; m[1]=8.0; m[2]=2.0; m[3]=10.0; m[4]=12.0; m[5]=4.0; m[6]=14.0; m[7]=6.0;
  m[8]=3.0; m[9]=11.0; m[10]=1.0; m[11]=9.0; m[12]=15.0; m[13]=7.0; m[14]=13.0; m[15]=5.0;
  return m[int(f.y * 4.0 + f.x)] / 16.0;
}

void main() {
  vec2 px = 1.0 / uRes;
  vec3 c = texture2D(tScene, vUv).rgb;
  vec3 glow = vec3(0.0);
  for (int i = 0; i < 8; i++) {
    float a = float(i) * 0.785398;
    vec2 o = vec2(cos(a), sin(a)) * px * 3.0;
    glow += max(texture2D(tScene, vUv + o).rgb - 0.72, 0.0);
    glow += max(texture2D(tScene, vUv + o * 2.2).rgb - 0.72, 0.0) * 0.6;
  }
  c += glow * uBloom / 8.0;
  vec2 cell = floor(vUv * uRes);
  float d = (bayer4(cell) - 0.5) * uDither;
  c = floor(c * uLevels + d + 0.5) / uLevels;
  c *= 1.0 - uScanlines * mod(cell.y, 2.0) * 0.14;
  vec2 q = vUv - 0.5;
  c *= 1.0 - dot(q, q) * 0.55;
  gl_FragColor = vec4(c, 1.0);
}
""")

POST_VERT = glsl("ps2_post.vert", "Fullscreen triangle-pair for the post pass.", """
varying vec2 vUv;
void main() { vUv = uv; gl_Position = vec4(position.xy, 0.0, 1.0); }
""")


# ----------------------------------------------------------------------------- bundle

def generate(out, spec=None):
    for d in ("meshes", "textures", "shaders", "scenes", "particles", "fonts"):
        os.makedirs(os.path.join(out, d), exist_ok=True)
    textures(os.path.join(out, "textures"))
    font_files, atlas_size = bitfont.export(os.path.join(out, "fonts"))

    shaders = {"ps2_world.vert": WORLD_VERT, "ps2_world.frag": WORLD_FRAG, "water.vert": WATER_VERT, "water.frag": WATER_FRAG,
               "sky.vert": SKY_VERT, "sky.frag": SKY_FRAG, "cloud.vert": CLOUD_VERT, "cloud.frag": CLOUD_FRAG,
               "wind_particles.vert": WIND_VERT, "wind_particles.frag": WIND_FRAG, "ps2_post.vert": POST_VERT, "ps2_post.frag": POST_FRAG}
    for n, src in shaders.items():
        with open(os.path.join(out, "shaders", n), "w") as f:
            f.write(src)

    meshes = {}
    terrain = M.grid("terrain", "sand", 110, 74, 56, 40, None, 22)
    terrain.translate((0, 0, 7))
    terrain.pos = [(x, sand_height(x, z), z) for x, _, z in terrain.pos]
    meshes["terrain"] = [terrain]
    meshes["water"] = [M.grid("water", "water", 220, 120, 88, 52).translate((0, 0, -52))]
    meshes["palm"] = palm()
    for i, sd in enumerate((3, 8, 14)):
        meshes["rock_" + "abc"[i]] = rock(sd)
    meshes["umbrella"] = umbrella()
    towel = M.grid("towel", "towel", 1.0, 1.9, 2, 2)
    meshes["towel"] = [towel]
    tri_total = 0
    mesh_meta = {}
    for name, parts in meshes.items():
        for p in parts:
            p.compute_normals()
        tris = sum(p.tri_count for p in parts)
        mesh_meta[name] = tris
        M.write_obj(os.path.join(out, "meshes", name + ".obj"), parts, header="PS2 beach - %s (%d tris)" % (name, tris))

    on_sand = lambda x, z, dy=0.0: [round(x, 3), round(sand_height(x, z) + dy, 3), round(z, 3)]
    instances = [
        {"name": "Terrain", "mesh": "meshes/terrain.obj", "materials": {"sand": "sand"}},
        {"name": "Ocean", "mesh": "meshes/water.obj", "materials": {"water": "water"}},
        {"name": "Palm A", "mesh": "meshes/palm.obj", "position": on_sand(-9, 9, -0.2), "rotation": [0, 0.4, 0], "scale": 1.0},
        {"name": "Palm B", "mesh": "meshes/palm.obj", "position": on_sand(-14.5, 13, -0.2), "rotation": [0, 2.6, 0], "scale": 1.18},
        {"name": "Palm C", "mesh": "meshes/palm.obj", "position": on_sand(17, 15, -0.2), "rotation": [0, 3.6, 0], "scale": 0.92},
        {"name": "Palm D", "mesh": "meshes/palm.obj", "position": on_sand(24, 21, -0.2), "rotation": [0, 1.1, 0], "scale": 1.1},
        {"name": "Rock 1", "mesh": "meshes/rock_a.obj", "position": on_sand(6, -2.5, -0.15), "rotation": [0, 0.3, 0], "scale": 1.4},
        {"name": "Rock 2", "mesh": "meshes/rock_b.obj", "position": on_sand(8.2, -1.2, -0.1), "rotation": [0, 1.7, 0], "scale": 0.8},
        {"name": "Rock 3", "mesh": "meshes/rock_c.obj", "position": on_sand(-20, -2, -0.2), "rotation": [0, 2.2, 0], "scale": 2.2},
        {"name": "Rock 4", "mesh": "meshes/rock_a.obj", "position": on_sand(-17.5, -0.4, -0.1), "rotation": [0, 4.0, 0], "scale": 1.0},
        {"name": "Rock 5", "mesh": "meshes/rock_b.obj", "position": on_sand(13, 6, -0.1), "rotation": [0, 0.9, 0], "scale": 0.6},
        {"name": "Umbrella", "mesh": "meshes/umbrella.obj", "position": on_sand(1.5, 5.5, -0.1), "rotation": [0.12, 0.4, -0.08], "scale": 1.0},
        {"name": "Towel", "mesh": "meshes/towel.obj", "position": on_sand(3.0, 6.2, 0.04), "rotation": [-0.06, 0.5, 0], "scale": 1.0},
    ]
    clouds = []
    for k in range(14):
        h = P._hash(k, 4)
        clouds.append({"position": [round(-150 + k * 23 + h * 10, 1), round(26 + P._hash(k, 5) * 18, 1), round(-120 - P._hash(k, 6) * 60, 1)],
                       "scale": [round(34 + h * 26, 1), round(15 + h * 10, 1)]})

    particles = {
        "systems": [
            {"name": "Wind streaks", "count": 420, "box": {"min": [-40, 0.6, -18], "max": [40, 7, 30]},
             "wind": [-7.5, 0.0, -1.5], "gustFrequency": 0.45, "gustStrength": 0.7, "wobble": 0.35,
             "size": 0.55, "streak": 5.0, "color": [1.0, 1.0, 1.0], "opacity": 0.42, "blending": "additive", "seed": 7},
            {"name": "Sand drift", "count": 900, "box": {"min": [-30, 0.05, -2], "max": [30, 0.9, 28]},
             "wind": [-5.0, 0.0, -0.8], "gustFrequency": 0.8, "gustStrength": 0.9, "wobble": 0.12,
             "size": 0.11, "streak": 2.0, "color": [0.98, 0.86, 0.62], "opacity": 0.85, "blending": "normal", "seed": 11},
            {"name": "Sea spray", "count": 260, "box": {"min": [-40, 0.1, -9], "max": [40, 1.6, -1]},
             "wind": [-3.0, 0.25, 0.6], "gustFrequency": 1.2, "gustStrength": 0.5, "wobble": 0.4,
             "size": 0.22, "streak": 1.0, "color": [0.92, 0.98, 1.0], "opacity": 0.5, "blending": "additive", "seed": 23},
        ],
        "shader": {"vert": "shaders/wind_particles.vert", "frag": "shaders/wind_particles.frag"},
    }
    with open(os.path.join(out, "particles", "wind.particles.json"), "w") as f:
        json.dump(particles, f, indent=2)

    W = "shaders/ps2_world.vert", "shaders/ps2_world.frag"
    world = lambda tex, **u: {"vert": W[0], "frag": W[1], "maps": {"uMap": "textures/" + tex},
                              "uniforms": {"uTint": [1, 1, 1], "uAlphaTest": 0.0, "uWetLine": 0.0, "uUvScale": 1.0, "uSway": 0.0, **u}}
    scene = {
        "name": "Sunny Shores",
        "renderSettings": {"internalResolution": [640, 448], "textureFilter": "bilinear", "colorLevels": 31, "dither": 1.0,
                           "scanlines": 0.6, "bloom": 0.9, "vertexSnap": 0.0, "colorPipeline": "display-referred (no linear workflow, like 2001)"},
        "environment": {"zenith": [0.18, 0.42, 0.85], "horizon": [0.72, 0.86, 0.98], "sunDir": [-0.35, 0.55, -0.75],
                        "sunColor": [1.0, 0.93, 0.78], "ambient": [0.52, 0.56, 0.66], "fog": {"color": [0.74, 0.86, 0.97], "near": 45, "far": 150},
                        "skyBands": 14, "cloudTint": [1, 1, 1], "water": {"deep": [0.07, 0.30, 0.55], "shallow": [0.30, 0.78, 0.82]}},
        "waves": {"A": [0.0, 1.0, 0.22, 16.0], "B": [0.25, 1.0, 0.16, 9.0], "C": [-0.3, 1.0, 0.1, 5.0]},
        "materials": {
            "sand": world("sand.png", uWetLine=0.55, uUvScale=1.0),
            "bark": world("palm_bark.png"),
            "leaf": dict(world("palm_leaf.png", uAlphaTest=0.5), doubleSided=True),
            "rock": world("rock.png"),
            "umbrella": dict(world("umbrella.png"), doubleSided=True),
            "towel": world("towel.png"),
            "water": {"vert": "shaders/water.vert", "frag": "shaders/water.frag", "maps": {"uMap": "textures/water.png"}, "transparent": True},
        },
        "palmSway": 1.0,
        "objects": instances,
        "clouds": {"texture": "textures/cloud.png", "vert": "shaders/cloud.vert", "frag": "shaders/cloud.frag", "drift": 1.2, "cards": clouds},
        "sky": {"vert": "shaders/sky.vert", "frag": "shaders/sky.frag"},
        "post": {"vert": "shaders/ps2_post.vert", "frag": "shaders/ps2_post.frag"},
        "particles": "particles/wind.particles.json",
        "camera": {"position": [-7.5, 3.4, 21], "target": [2.5, 1.2, -6], "fov": 52,
                   "path": [[-7.5, 3.4, 21], [6, 2.6, 16], [14, 4.5, 6], [4, 6.5, 24], [-7.5, 3.4, 21]]},
        "hud": {"font": "fonts/tc_hud.font.json", "atlas": "fonts/tc_hud_atlas.png", "title": "SUNNY SHORES", "subtitle": "STAGE 1-1  *  PRESS START"},
    }
    with open(os.path.join(out, "scenes", "beach.scene.json"), "w") as f:
        json.dump(scene, f, indent=2)

    variants = [
        {"id": "noon", "name": "High Noon", "group": "Time of day", "default": True, "swatch": "#5aa9ff", "patch": {}},
        {"id": "sunset", "name": "Golden Sunset", "group": "Time of day", "swatch": "#ff8a4c", "patch": {
            "environment.zenith": [0.25, 0.22, 0.52], "environment.horizon": [1.0, 0.58, 0.32], "environment.sunDir": [-0.2, 0.12, -0.95],
            "environment.sunColor": [1.0, 0.62, 0.32], "environment.ambient": [0.52, 0.38, 0.42], "environment.fog.color": [0.95, 0.6, 0.45],
            "environment.cloudTint": [1.0, 0.72, 0.6], "environment.water.deep": [0.18, 0.15, 0.35], "environment.water.shallow": [0.75, 0.45, 0.4]}},
        {"id": "night", "name": "Moonlit Night", "group": "Time of day", "swatch": "#2a2f6b", "patch": {
            "environment.zenith": [0.01, 0.02, 0.08], "environment.horizon": [0.08, 0.12, 0.28], "environment.sunDir": [0.3, 0.45, -0.8],
            "environment.sunColor": [0.55, 0.65, 0.95], "environment.ambient": [0.12, 0.15, 0.3], "environment.fog.color": [0.06, 0.09, 0.2],
            "environment.cloudTint": [0.3, 0.35, 0.55], "environment.water.deep": [0.02, 0.05, 0.14], "environment.water.shallow": [0.1, 0.25, 0.4]}},
        {"id": "ps2-faithful", "name": "Faithful 480i", "group": "Output", "default": True, "patch": {}},
        {"id": "ps1-wobble", "name": "PS1 Wobble", "group": "Output", "patch": {"renderSettings.internalResolution": [320, 224], "renderSettings.vertexSnap": 1.0, "renderSettings.colorLevels": 15}},
        {"id": "remaster", "name": "HD Remaster", "group": "Output", "patch": {"renderSettings.internalResolution": [1920, 1080], "renderSettings.scanlines": 0.0, "renderSettings.dither": 0.0, "renderSettings.colorLevels": 255}},
    ]

    tex_meta = {"sand.png": 128, "water.png": 128, "cloud.png": 128, "palm_leaf.png": 64, "palm_bark.png": 64, "rock.png": 64,
                "umbrella.png": 64, "towel.png": 64}
    files = []
    for n, tris in mesh_meta.items():
        tex_for = {"terrain": ["sand.png"], "water": ["water.png"], "palm": ["palm_bark.png", "palm_leaf.png"],
                   "umbrella": ["umbrella.png"], "towel": ["towel.png"]}.get(n, ["rock.png"])
        files.append({"path": "meshes/%s.obj" % n, "kind": "mesh", "role": "scene prop", "meta": {"triangles": tris},
                      "depends": ["textures/" + t for t in tex_for]})
    for n, r in tex_meta.items():
        files.append({"path": "textures/" + n, "kind": "texture", "role": "PS2 %dpx dithered" % r, "meta": {"width": r}})
    for n in shaders:
        deps = {"water.frag": ["textures/water.png"], "cloud.frag": ["textures/cloud.png"], "ps2_world.frag": ["textures/sand.png"]}.get(n, [])
        files.append({"path": "shaders/" + n, "kind": "shader", "role": "vertex" if n.endswith(".vert") else "fragment", "depends": deps})
    files.append({"path": "particles/wind.particles.json", "kind": "particles", "role": "3 emitter systems",
                  "depends": ["shaders/wind_particles.vert", "shaders/wind_particles.frag"]})
    for fn in font_files:
        files.append({"path": "fonts/" + fn, "kind": "font", "role": {"bdf": "BDF bitmap font", "png": "glyph atlas", "json": "metrics"}[fn.split(".")[-1]],
                      "meta": {"atlas": list(atlas_size)} if fn.endswith(".png") else {}})
    files.append({"path": "scenes/beach.scene.json", "kind": "scene", "role": "scene graph",
                  "depends": ["meshes/%s.obj" % n for n in mesh_meta] + ["shaders/" + n for n in shaders]
                  + ["particles/wind.particles.json", "fonts/tc_hud.font.json", "fonts/tc_hud_atlas.png", "textures/cloud.png"]})
    for n in mesh_meta:
        tri_total += mesh_meta[n] * sum(1 for i in instances if i["mesh"] == "meshes/%s.obj" % n)

    render = {"type": "scene", "scene": "scenes/beach.scene.json"}
    return {
        "kind": "scene", "files": files, "render": render, "variants": variants,
        "stats": {"triangles": tri_total, "unique_meshes": len(mesh_meta), "instances": len(instances), "clouds": len(clouds),
                  "particles": sum(s["count"] for s in particles["systems"]), "textures": len(tex_meta), "shaders": len(shaders),
                  "internal_resolution": "640x448", "max_texture": "128px", "per_mesh": mesh_meta},
        "pipeline": [{"stage": s, "state": "done", "note": n} for s, n in [
            ("Interpret prompt", "scene · sandy beach · PS2 style · clouds · wind particles"),
            ("Layout & terrain", "curved shoreline, slope + fbm dunes, 4,480 tri sand"),
            ("Hero props", "4 palms, 5 rocks, umbrella, towel (instanced)"),
            ("Water / sky systems", "3 Gerstner waves, foam bands, banded sky dome"),
            ("Texture synthesis", "8 textures ≤128px, Bayer dithered, 5-bit quantised"),
            ("Shader authoring", "12 GLSL stages incl. post"),
            ("Particle systems", "wind streaks · sand drift · sea spray"),
            ("Lighting & fog", "Gouraud vertex lighting, linear fog"),
            ("Time-of-day variants", "noon / sunset / night"),
            ("Post FX", "640x448 nearest upscale, glow, dither, interlace"),
            ("Preview render", "rendered in-browser on first view"),
            ("Package bundle", "scene graph + HUD bitmap font")]],
    }
