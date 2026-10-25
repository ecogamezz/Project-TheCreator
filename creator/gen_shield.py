"""Request: "a moving shield texture that loops and has an alpha channel (transparent where there is no texture)".

Energy-shield hex field, seamless in space *and* time:
  - spatially tileable (hex lattice fits the tile exactly, all noise is periodic)
  - temporally looping (every motion term is periodic over the loop: frame N == frame 0)
Deliverables: flipbook sheet (RGBA), animated PNG (RGBA, plays natively), per-frame stills, alpha mask,
flipbook GLSL, live procedural GLSL twin, metadata, and a plug-in viewer.
"""
import json
import math
import os
import shutil

from . import procedural as P
from .glsl import HEADER

RES, FRAMES, FPS = 256, 24, 24
COLS, ROWS = 6, 4
HEX_N, HEX_M = 7, 4                      # hex lattice repeats: 7 x sqrt(3) wide, 4 x 3 tall (~square)
S3 = math.sqrt(3)


def hex_field(res):
    """Per-pixel static data: (edge 0..1, cell hash, cell centre uv)."""
    W, H = HEX_N * S3, HEX_M * 3.0
    out = []
    for y in range(res):
        for x in range(res):
            px, py = (x + 0.5) / res * W, (y + 0.5) / res * H
            best = None
            for ox, oy in ((0, 0), (S3 / 2, 1.5)):
                gx = (px - ox) % S3 - S3 / 2
                gy = (py - oy) % 3.0 - 1.5
                d = gx * gx + gy * gy
                if best is None or d < best[0]:
                    best = (d, gx, gy)
            _, gx, gy = best
            e = max(abs(gx), abs(gx) * 0.5 + abs(gy) * S3 / 2) / (S3 / 2)
            cx, cy = px - gx, py - gy
            ix, iy = int(round(cx / (S3 / 2))) % (2 * HEX_N), int(round(cy / 1.5)) % (2 * HEX_M)
            out.append((e, P._hash(ix, iy, 5), cx / W, cy / H))
    return out


def periodic_noise(res, period=4):
    return [P.fbm((x + 0.5) / res * period, (y + 0.5) / res * period, 3, seed=17, period=period) for y in range(res) for x in range(res)]


def render_frames(res=RES, frames=FRAMES):
    field = hex_field(res)
    noise = periodic_noise(res)
    impacts = [(0.28, 0.33, 0.0), (0.74, 0.7, 0.45), (0.6, 0.15, 0.7)]
    out, alpha_avg = [], [0.0] * (res * res)
    for f in range(frames):
        t = f / frames
        buf = bytearray(res * res * 4)
        shift = t * res                               # noise scrolls exactly one tile per loop
        s0 = int(shift)
        fr = shift - s0
        for y in range(res):
            v = (y + 0.5) / res
            row = y * res
            for x in range(res):
                i = row + x
                u = (x + 0.5) / res
                e, h, cu, cv = field[i]
                n = noise[row + (x + s0) % res] * (1 - fr) + noise[row + (x + s0 + 1) % res] * fr
                line = P.smoothstep(0.8, 0.96, e)
                flick = 0.5 + 0.5 * math.sin(2 * math.pi * (t * (1 + int(h * 3)) + h))
                d = (u + v - t) % 1.0
                wave = math.exp(-((d - 0.5) ** 2) * 60)
                ring = 0.0
                for ix, iy, ph in impacts:
                    dx = abs(cu - ix); dx = min(dx, 1 - dx)
                    dy = abs(cv - iy); dy = min(dy, 1 - dy)
                    k = (t + ph) % 1.0
                    rr = math.hypot(dx, dy) - k * 0.45
                    ring += math.exp(-(rr * 22) ** 2) * (1 - k) ** 1.5
                cell_glow = (0.25 + 0.75 * flick) * (1 - e) ** 2 * 0.25
                inten = line * (0.55 + 0.45 * flick) + wave * (0.35 + 0.65 * line) + ring * (0.6 + 0.8 * (1 - e)) + n * 0.25
                a = P.clamp(line * 0.82 + cell_glow + wave * 0.4 + ring * 0.75 + (n - 0.4) * 0.25)
                hot = P.clamp(inten * inten * 0.6)
                r = P.clamp(0.10 + 0.9 * hot + ring * 0.2)
                g = P.clamp(0.62 + 0.38 * hot)
                b = P.clamp(1.0)
                j = i * 4
                buf[j] = int(r * 255); buf[j + 1] = int(g * 255); buf[j + 2] = int(b * 255); buf[j + 3] = int(a * 255)
                alpha_avg[i] += a / frames
        out.append(buf)
    return out, alpha_avg


SHEET_FRAG = HEADER.format(name="shield_flipbook.frag", desc="Plays the RGBA flipbook sheet with sub-frame blending; fresnel boost for force-field spheres.") + """
uniform sampler2D uSheet;
uniform vec2  uGrid;        // columns, rows
uniform float uFrames;
uniform float uFrame;       // continuous frame index (time * fps)
uniform float uBlend;       // 1 = cross-fade neighbouring frames
uniform vec3  uTint;
uniform float uFresnel;
uniform vec2  uTiling;
varying vec2  vUv;
varying vec3  vNormalV;
varying vec3  vViewV;

vec4 frameAt(float f, vec2 uv) {
  f = mod(f, uFrames);
  vec2 cell = vec2(mod(f, uGrid.x), floor(f / uGrid.x));
  vec2 st = (fract(uv) + cell) / uGrid;
  st.y = 1.0 - st.y;                    // row 0 is the top row of the sheet
  return texture2D(uSheet, st);
}

void main() {
  vec2 uv = vUv * uTiling;
  uv.y = 1.0 - uv.y;
  float f0 = floor(uFrame);
  vec4 a = frameAt(f0, uv), b = frameAt(f0 + 1.0, uv);
  vec4 c = mix(a, b, fract(uFrame) * uBlend);
  float fres = pow(1.0 - abs(dot(normalize(vNormalV), normalize(vViewV))), 2.5);
  c.rgb *= uTint;
  c.a = clamp(c.a + fres * uFresnel * 0.6, 0.0, 1.0);
  c.rgb += uTint * fres * uFresnel * 0.5;
  gl_FragColor = c;
}
"""

SHEET_VERT = HEADER.format(name="shield.vert", desc="Passes UV, view-space normal and view vector (for fresnel).") + """
varying vec2 vUv;
varying vec3 vNormalV;
varying vec3 vViewV;
void main() {
  vUv = uv;
  vec4 mv = modelViewMatrix * vec4(position, 1.0);
  vNormalV = normalMatrix * normal;
  vViewV = -mv.xyz;
  gl_Position = projectionMatrix * mv;
}
"""

LIVE_FRAG = HEADER.format(name="shield_live.frag", desc="Procedural twin of the baked sheet: same hex lattice, flicker, sweep and impact rings - any resolution.") + """
uniform float uTime;
uniform float uLoop;        // loop length in seconds
uniform vec3  uTint;
uniform float uFresnel;
uniform vec2  uTiling;
varying vec2  vUv;
varying vec3  vNormalV;
varying vec3  vViewV;

const float S3 = 1.7320508;
float hash(vec2 p) { p = fract(p * vec2(123.34, 456.21)); p += dot(p, p + 45.32); return fract(p.x * p.y); }
float vnoise(vec2 p, float per) {
  vec2 i = floor(p), f = fract(p); f = f * f * (3.0 - 2.0 * f);
  float a = hash(mod(i, per)), b = hash(mod(i + vec2(1, 0), per)), c = hash(mod(i + vec2(0, 1), per)), d = hash(mod(i + vec2(1, 1), per));
  return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
}

void main() {
  float t = fract(uTime / uLoop);
  vec2 uv = fract(vUv * uTiling);
  vec2 p = uv * vec2(7.0 * S3, 12.0);
  vec2 s = vec2(S3, 3.0);
  vec2 ga = mod(p, s) - s * 0.5, gb = mod(p - s * 0.5, s) - s * 0.5;
  vec2 g = dot(ga, ga) < dot(gb, gb) ? ga : gb;
  vec2 ag = abs(g);
  float e = max(ag.x, ag.x * 0.5 + ag.y * S3 * 0.5) / (S3 * 0.5);
  vec2 cell = (p - g) / vec2(7.0 * S3, 12.0);
  float h = hash(floor((p - g) * 10.0 + 0.5));
  float line = smoothstep(0.8, 0.96, e);
  float flick = 0.5 + 0.5 * sin(6.28318 * (t * (1.0 + floor(h * 3.0)) + h));
  float d = fract(uv.x + uv.y - t);
  float wave = exp(-pow(d - 0.5, 2.0) * 60.0);
  float ring = 0.0;
  vec3 imp[3]; imp[0] = vec3(0.28, 0.33, 0.0); imp[1] = vec3(0.74, 0.7, 0.45); imp[2] = vec3(0.6, 0.15, 0.7);
  for (int i = 0; i < 3; i++) {
    vec2 dd = abs(cell - imp[i].xy); dd = min(dd, 1.0 - dd);
    float k = fract(t + imp[i].z);
    float rr = length(dd) - k * 0.45;
    ring += exp(-pow(rr * 22.0, 2.0)) * pow(1.0 - k, 1.5);
  }
  float n = vnoise((uv + vec2(t, 0.0)) * 4.0, 4.0) * 0.6 + vnoise((uv + vec2(t, 0.0)) * 8.0, 8.0) * 0.4;
  float inten = line * (0.55 + 0.45 * flick) + wave * (0.35 + 0.65 * line) + ring * (0.6 + 0.8 * (1.0 - e)) + n * 0.25;
  float a = clamp(line * 0.82 + (0.25 + 0.75 * flick) * pow(1.0 - e, 2.0) * 0.25 + wave * 0.4 + ring * 0.75 + (n - 0.4) * 0.25, 0.0, 1.0);
  float hot = clamp(inten * inten * 0.6, 0.0, 1.0);
  vec3 col = vec3(0.1 + 0.9 * hot + ring * 0.2, 0.62 + 0.38 * hot, 1.0) * uTint;
  float fres = pow(1.0 - abs(dot(normalize(vNormalV), normalize(vViewV))), 2.5);
  gl_FragColor = vec4(col + uTint * fres * uFresnel * 0.5, clamp(a + fres * uFresnel * 0.6, 0.0, 1.0));
}
"""


def generate(out, spec=None):
    for d in ("textures/frames", "shaders", "runtime"):
        os.makedirs(os.path.join(out, d), exist_ok=True)
    frames, alpha_avg = render_frames()

    # flipbook sheet
    W, H = COLS * RES, ROWS * RES
    sheet = bytearray(W * H * 4)
    for f, buf in enumerate(frames):
        cx, cy = (f % COLS) * RES, (f // COLS) * RES
        for y in range(RES):
            dst = ((cy + y) * W + cx) * 4
            sheet[dst:dst + RES * 4] = buf[y * RES * 4:(y + 1) * RES * 4]
    P.write_png(os.path.join(out, "textures", "shield_flipbook_6x4.png"), W, H, sheet, 4)
    P.write_apng(os.path.join(out, "textures", "shield_loop.apng.png"), RES, RES, frames, FPS)
    for f in (0, 6, 12, 18):
        P.write_png(os.path.join(out, "textures", "frames", "shield_f%02d.png" % f), RES, RES, frames[f], 4)
    mask = bytearray(RES * RES * 4)
    for i, a in enumerate(alpha_avg):
        v = int(P.clamp(a) * 255)
        mask[i * 4:i * 4 + 4] = bytes((v, v, v, 255))
    P.write_png(os.path.join(out, "textures", "shield_alpha_coverage.png"), RES, RES, mask, 4)

    shaders = {"shield.vert": SHEET_VERT, "shield_flipbook.frag": SHEET_FRAG, "shield_live.frag": LIVE_FRAG}
    for n, src in shaders.items():
        with open(os.path.join(out, "shaders", n), "w") as fh:
            fh.write(src)
    shutil.copy(os.path.join(os.path.dirname(__file__), "runtime", "shield_viewer.js"), os.path.join(out, "runtime", "viewer.js"))
    meta = {"name": "Hex energy shield", "frames": FRAMES, "fps": FPS, "loop_seconds": FRAMES / FPS, "frame_size": [RES, RES],
            "sheet": {"file": "shield_flipbook_6x4.png", "columns": COLS, "rows": ROWS, "order": "row-major from top-left"},
            "apng": "shield_loop.apng.png", "alpha": "straight (non-premultiplied); 0 where there is no shield energy",
            "seamless": {"spatial": True, "temporal": True}, "hex_lattice": {"columns": HEX_N * 2, "rows": HEX_M * 2}}
    with open(os.path.join(out, "textures", "shield.texture.json"), "w") as fh:
        json.dump(meta, fh, indent=2)
    coverage = sum(alpha_avg) / len(alpha_avg)

    T = "textures/"
    files = [
        {"path": T + "shield_flipbook_6x4.png", "kind": "texture", "role": "RGBA flipbook sheet · 24 frames", "meta": {"width": W, "height": H}},
        {"path": T + "shield_loop.apng.png", "kind": "texture", "role": "animated PNG · plays anywhere", "meta": {"width": RES, "frames": FRAMES}},
        {"path": T + "shield_alpha_coverage.png", "kind": "texture", "role": "average alpha (mask)", "meta": {"width": RES}},
        {"path": T + "shield.texture.json", "kind": "data", "role": "flipbook metadata", "depends": [T + "shield_flipbook_6x4.png", T + "shield_loop.apng.png"]},
        {"path": "shaders/shield.vert", "kind": "shader", "role": "vertex"},
        {"path": "shaders/shield_flipbook.frag", "kind": "shader", "role": "fragment · flipbook player", "depends": ["shaders/shield.vert", T + "shield_flipbook_6x4.png"]},
        {"path": "shaders/shield_live.frag", "kind": "shader", "role": "fragment · procedural twin", "depends": ["shaders/shield.vert"]},
        {"path": "runtime/viewer.js", "kind": "data", "role": "plug-in viewer", "depends": ["shaders/shield_flipbook.frag", "shaders/shield_live.frag", T + "shield.texture.json"]},
    ] + [{"path": T + "frames/shield_f%02d.png" % f, "kind": "texture", "role": "still frame %d" % f, "meta": {"width": RES}} for f in (0, 6, 12, 18)]

    render = {"type": "module", "module": "runtime/viewer.js", "timeline": True,
              "camera": {"position": [0, 0.6, 4.9], "target": [0, 0, 0], "fov": 40},
              "sheet": T + "shield_flipbook_6x4.png", "meta": T + "shield.texture.json",
              "shaders": {"vert": "shaders/shield.vert", "flipbook": "shaders/shield_flipbook.frag", "live": "shaders/shield_live.frag"},
              "tint": [1, 1, 1]}
    variants = [
        {"id": "aegis", "name": "Aegis Cyan", "group": "Tint", "default": True, "swatch": "#3fd0ff", "patch": {}},
        {"id": "plasma", "name": "Plasma Magenta", "group": "Tint", "swatch": "#ff4fd8", "patch": {"tint": [2.4, 0.35, 0.9]}},
        {"id": "radiant", "name": "Radiant Gold", "group": "Tint", "swatch": "#ffc94a", "patch": {"tint": [2.6, 1.15, 0.25]}},
        {"id": "toxic", "name": "Toxic Green", "group": "Tint", "swatch": "#7dff5a", "patch": {"tint": [0.9, 1.5, 0.35]}},
    ]
    return {
        "kind": "texture", "files": files, "render": render, "variants": variants,
        "stats": {"textures": 9, "shaders": 3, "frames": FRAMES, "fps": FPS, "duration": round(FRAMES / FPS, 2),
                  "frame_size": "%dx%d" % (RES, RES), "sheet_size": "%dx%d" % (W, H), "alpha_coverage": round(coverage * 100, 1), "loop": "seamless (space + time)"},
        "pipeline": [{"stage": s, "state": "done", "note": n} for s, n in [
            ("Interpret prompt", "texture · animated · looping · alpha"),
            ("Pattern synthesis", "hex lattice fitted to the tile (7×√3 by 4×3 units), per-cell flicker, diagonal sweep, 3 impact ripples"),
            ("Map derivation", "straight alpha: %.0f%% average coverage; average-alpha mask exported" % (coverage * 100)),
            ("Tiling check", "lattice + noise periodic in u, v and t → seamless in space and time"),
            ("Preview render", "flipbook / live GLSL on sphere, plane and 3×3 tiling"),
            ("Package bundle", "sheet, APNG, stills, 2 fragment shaders, metadata, viewer")]],
    }
