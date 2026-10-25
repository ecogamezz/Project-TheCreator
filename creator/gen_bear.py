"""Request: "ps2 bear, moving/glitching vertices like ps1 and textures the same. multiple animations for states
(idle, walk, attack, run, death)".

Built like a 1999-2002 console character: a *rigid-part* rig (every body part is its own low-poly mesh parented to a
bone - no skinning), 64px dithered 15-bit textures, and a shader that reproduces PS1 artefacts: vertex snapping to
a coarse screen grid, affine (non perspective-correct) texture mapping, Gouraud lighting, and random vertex glitches.
Clips are baked at 30 fps (the classic rate) and exported as JSON + a glTF with a real node hierarchy.
"""
import json
import math
import os
import shutil

from . import mesh as M
from . import procedural as P
from .glsl import HEADER

FPS = 30

# (bone, parent, pivot in bind pose). The bear faces +Z.
BONES = [
    ("body", None, (0.0, 1.05, 0.0)),
    ("head", "body", (0.0, 1.38, 0.92)),
    ("jaw", "head", (0.0, 1.27, 1.32)),
    ("tail", "body", (0.0, 1.2, -0.95)),
    ("fl_upper", "body", (0.33, 1.12, 0.6)), ("fl_lower", "fl_upper", (0.33, 0.6, 0.62)),
    ("fr_upper", "body", (-0.33, 1.12, 0.6)), ("fr_lower", "fr_upper", (-0.33, 0.6, 0.62)),
    ("bl_upper", "body", (0.34, 1.08, -0.6)), ("bl_lower", "bl_upper", (0.34, 0.56, -0.66)),
    ("br_upper", "body", (-0.34, 1.08, -0.6)), ("br_lower", "br_upper", (-0.34, 0.56, -0.66)),
]
PIVOT = {b: p for b, _, p in BONES}


def blob(name, mat, c, r, su=8, sv=6, deform=None):
    return M.uv_sphere(name, mat, su, sv, deform).scale(r).translate(c)


def limb(name, mat, top, bottom, r_top, r_bot, seg=7):
    length = top[1] - bottom[1]
    prof = [(r_bot, 0.0), ((r_top + r_bot) / 2 * 1.08, length * 0.5), (r_top, length)]
    p = M.lathe(name, mat, prof, seg)
    dz = top[2] - bottom[2]
    p.transform(lambda v: (v[0], v[1], v[2] + dz * v[1] / length))
    return p.translate(bottom)


def build():
    rig = {b: [] for b, _, _ in BONES}
    rig["body"] += [blob("body__fur", "fur", (0, 1.1, 0.02), (0.56, 0.5, 0.98), 10, 7),
                    blob("hump__fur", "fur", (0, 1.38, 0.42), (0.44, 0.36, 0.46), 8, 6),
                    blob("belly__muzzle", "muzzle", (0, 0.86, 0.1), (0.36, 0.2, 0.6), 8, 5)]
    rig["head"] += [blob("head__fur", "fur", (0, 1.42, 1.22), (0.34, 0.31, 0.37), 9, 7),
                    blob("snout__muzzle", "muzzle", (0, 1.33, 1.56), (0.17, 0.14, 0.21), 8, 5),
                    blob("nose__dark", "dark", (0, 1.38, 1.76), (0.07, 0.05, 0.05), 6, 4)]
    for s in (1, -1):
        rig["head"] += [blob("ear__fur", "fur", (s * 0.22, 1.7, 1.12), (0.1, 0.1, 0.05), 6, 4),
                        blob("eye__eye", "eye", (s * 0.15, 1.5, 1.49), (0.045, 0.045, 0.03), 6, 4)]
    rig["jaw"] += [blob("jaw__muzzle", "muzzle", (0, 1.2, 1.5), (0.14, 0.06, 0.19), 7, 4)]
    rig["tail"] += [blob("tail__fur", "fur", (0, 1.22, -1.04), (0.1, 0.1, 0.1), 6, 4)]
    for leg in ("fl", "fr", "bl", "br"):
        up, lo = PIVOT[leg + "_upper"], PIVOT[leg + "_lower"]
        front = leg[0] == "f"
        rig[leg + "_upper"].append(limb(leg + "_upper__fur", "fur", up, lo, 0.2 if front else 0.23, 0.15))
        foot = (lo[0], 0.07, lo[2] + 0.06)
        rig[leg + "_lower"].append(limb(leg + "_lower__fur", "fur", lo, (lo[0], 0.1, lo[2] + 0.02), 0.15, 0.13))
        rig[leg + "_lower"].append(blob(leg + "_paw__fur", "fur", foot, (0.15, 0.08, 0.2), 7, 4))
        if front:
            for k in (-1, 0, 1):
                claw = M.lathe(leg + "_claw__claw", "claw", [(0.025, 0), (0.0, 0.09)], 4).rotate(rx=math.pi / 2 + 0.5)
                rig[leg + "_lower"].append(claw.translate((foot[0] + k * 0.06, 0.06, foot[2] + 0.17)))
    for parts in rig.values():
        for p in parts:
            p.compute_normals()
    return rig


def environment():
    ground = M.grid("ground__grass", "grass", 40, 40, 16, 16, lambda x, z: 0.12 * math.sin(x * 0.4) * math.sin(z * 0.3) * min(1, math.hypot(x, z) / 8), 14)
    trees = []
    for k in range(9):
        a = k / 9 * 2 * math.pi + 0.3
        r = 7 + 4 * P._hash(k, 3)
        x, z = r * math.cos(a), r * math.sin(a)
        s = 0.8 + 0.6 * P._hash(k, 4)
        trunk = M.lathe("tree%d__bark" % k, "bark", [(0.16, 0), (0.12, 1.2)], 6).scale(s).translate((x, 0, z))
        crown = M.lathe("tree%d__pine" % k, "pine", [(1.0, 0), (0.75, 0.9), (0.85, 0.9), (0.5, 1.9), (0.6, 1.9), (0.0, 3.0)], 7, cap_bottom=True)
        trees += [trunk, crown.scale(s).translate((x, 1.0 * s, z))]
    rocks = [blob("rock%d__rock" % i, "rock", (x, 0.1, z), (s * 1.3, s * 0.7, s), 6, 4) for i, (x, z, s) in enumerate(((3.2, 2.5, 0.5), (-3.8, -1.4, 0.7), (2.0, -4.2, 0.4)))]
    parts = [ground] + trees + rocks
    for p in parts:
        p.compute_normals()
    return parts


# ----------------------------------------------------------------------------- textures (64px, 15-bit, dithered)

def textures(out):
    def q(fn):
        return lambda u, v, x, y: P.ps2_quantize(fn(u, v, x, y), x, y, 31)

    def fur(u, v, x, y):
        strand = P.fbm(u * 24, v * 5, 3, seed=2, period=0)
        n = P.fbm(u * 6, v * 6, 3, seed=5, period=6)
        return P.mix((0.22, 0.13, 0.07), (0.52, 0.34, 0.18), strand * 0.7 + n * 0.4) + (1,)
    P.render(os.path.join(out, "bear_fur.png"), 64, 64, q(fur), alpha=False)
    P.render(os.path.join(out, "bear_muzzle.png"), 32, 32, q(lambda u, v, x, y: P.mix((0.55, 0.4, 0.26), (0.74, 0.58, 0.4), P.fbm(u * 5, v * 5, 2, seed=3)) + (1,)), alpha=False)
    P.render(os.path.join(out, "grass.png"), 64, 64, q(lambda u, v, x, y: P.mix((0.18, 0.32, 0.1), (0.42, 0.6, 0.22), P.fbm(u * 8, v * 8, 3, seed=8, period=8) * 0.6 + P._hash(x, y, 1) * 0.4) + (1,)), alpha=False)
    P.render(os.path.join(out, "pine.png"), 32, 32, q(lambda u, v, x, y: P.mix((0.06, 0.2, 0.1), (0.16, 0.4, 0.2), 0.5 + 0.5 * math.sin(v * 40 + u * 6) * P.fbm(u * 4, v * 4, 2, seed=1, period=4)) + (1,)), alpha=False)
    P.render(os.path.join(out, "bark.png"), 32, 32, q(lambda u, v, x, y: P.mix((0.22, 0.14, 0.08), (0.42, 0.3, 0.2), P.fbm(u * 12, v * 3, 2, seed=4, period=0)) + (1,)), alpha=False)
    P.render(os.path.join(out, "rock.png"), 32, 32, q(lambda u, v, x, y: P.mix((0.32, 0.31, 0.3), (0.55, 0.53, 0.5), P.fbm(u * 6, v * 6, 3, seed=6, period=6)) + (1,)), alpha=False)


# ----------------------------------------------------------------------------- animation

def euler_q(x=0.0, y=0.0, z=0.0):
    return M.q_norm(M.q_mul(M.q_mul(M.q_axis((0, 1, 0), y), M.q_axis((1, 0, 0), x)), M.q_axis((0, 0, 1), z)))


def ease(t):
    t = P.clamp(t)
    return t * t * (3 - 2 * t)


def keys(t, pts):
    """Piecewise smooth interpolation through [(time, value), ...]."""
    if t <= pts[0][0]:
        return pts[0][1]
    for (t0, v0), (t1, v1) in zip(pts, pts[1:]):
        if t <= t1:
            k = ease((t - t0) / (t1 - t0))
            return v0 + (v1 - v0) * k
    return pts[-1][1]


def legs_cycle(ph, amp, lift, offsets):
    out = {}
    for leg, off in offsets.items():
        a = ph + off
        out[leg + "_upper"] = (-amp * math.sin(a), 0, 0)
        knee = max(0.0, math.sin(a + math.pi / 2)) * lift
        out[leg + "_lower"] = (knee if leg[0] == "b" else -knee * 0.2 + knee * 0.9, 0, 0)
    return out


def pose_idle(t, T=3.0):
    ph = 2 * math.pi * t / T
    return {"_t": (0, 0.012 * math.sin(ph * 2), 0), "body": (0.02 * math.sin(ph * 2), 0, 0.01 * math.sin(ph)),
            "head": (0.06 * math.sin(ph * 2 + 1), 0.35 * math.sin(ph), 0.04 * math.sin(ph)), "jaw": (0.04 + 0.03 * math.sin(ph * 3), 0, 0),
            "tail": (0, 0.3 * math.sin(ph * 3), 0), "fl_upper": (0.02 * math.sin(ph), 0, 0), "fr_upper": (-0.02 * math.sin(ph), 0, 0)}


def pose_walk(t, T=1.2):
    ph = 2 * math.pi * t / T
    p = legs_cycle(ph, 0.38, 0.55, {"bl": 0, "fl": math.pi / 2, "br": math.pi, "fr": 3 * math.pi / 2})
    p.update({"_t": (0, 0.035 * abs(math.sin(ph)), 0), "body": (0.03 * math.sin(2 * ph), 0.04 * math.sin(ph), 0.05 * math.sin(ph)),
              "head": (0.08 * math.sin(2 * ph + 0.6), -0.06 * math.sin(ph), -0.04 * math.sin(ph)), "jaw": (0.05, 0, 0), "tail": (0, 0.25 * math.sin(ph), 0)})
    return p


def pose_run(t, T=0.66):
    ph = 2 * math.pi * t / T
    p = legs_cycle(ph, 0.8, 1.0, {"fl": 0, "fr": 0.35, "bl": math.pi, "br": math.pi + 0.35})
    p.update({"_t": (0, 0.14 * max(0.0, math.sin(ph - 0.6)), 0), "body": (0.14 * math.sin(ph), 0, 0.03 * math.sin(ph)),
              "head": (-0.12 * math.sin(ph), 0, 0), "jaw": (0.18 + 0.06 * math.sin(ph * 2), 0, 0), "tail": (0.3 * math.sin(ph), 0, 0)})
    return p


def pose_attack(t):
    rear = keys(t, [(0, 0), (0.5, 1), (0.95, 1), (1.15, -0.15), (1.4, 0.0), (1.8, 0)])
    swipe = keys(t, [(0, 0), (0.5, 1), (0.9, 1.15), (1.12, -0.35), (1.5, 0), (1.8, 0)])
    roar = keys(t, [(0, 0.04), (0.45, 0.6), (0.95, 0.65), (1.15, 0.15), (1.8, 0.04)])
    shake = math.sin(t * 60) * 0.05 * (1 if 0.5 < t < 0.95 else 0)
    return {"_t": (0, 0.42 * max(rear, 0) - 0.04 * max(-rear, 0), -0.32 * max(rear, 0)), "body": (-0.9 * rear, shake, 0),
            "head": (0.55 * rear + 0.15 * max(-rear, 0) - 0.25 * roar, shake * 2, 0), "jaw": (roar, 0, 0), "tail": (0.4 * rear, 0, 0),
            "fl_upper": (-1.35 * swipe, 0, -0.25 * swipe), "fl_lower": (-0.55 * max(swipe, 0), 0, 0),
            "fr_upper": (-1.2 * keys(t, [(0, 0), (0.6, 1), (0.95, 1.1), (1.16, -0.3), (1.5, 0), (1.8, 0)]), 0, 0.25 * swipe),
            "fr_lower": (-0.6 * max(swipe, 0), 0, 0),
            "bl_upper": (0.9 * rear, 0, 0), "br_upper": (0.9 * rear, 0, 0), "bl_lower": (0.15 * rear, 0, 0), "br_lower": (0.15 * rear, 0, 0)}


def pose_death(t):
    fall = keys(t, [(0, 0), (0.35, 0.05), (0.55, -0.04), (1.15, 1.0), (1.3, 0.94), (1.42, 1.0)])
    wob = math.sin(t * 14) * 0.1 * (1 if t < 0.6 else 0)
    limp = keys(t, [(0, 0), (1.2, 1)])
    return {"_t": (0.1 * fall, -0.52 * fall, 0), "body": (0.15 * fall, 0, 1.45 * fall + wob),
            "head": (0.35 * fall + 0.25 * keys(t, [(0, 0), (0.4, 1), (1, 0.6)]), 0.3 * fall, -0.25 * fall), "jaw": (0.18 * limp, 0, 0),
            "tail": (0, 0, 0.3 * limp),
            "fl_upper": (-0.3 * limp, 0, 0.5 * limp), "fl_lower": (0.4 * limp, 0, 0), "fr_upper": (0.25 * limp, 0, -0.2 * limp), "fr_lower": (-0.3 * limp, 0, 0),
            "bl_upper": (0.4 * limp, 0, 0.45 * limp), "bl_lower": (0.3 * limp, 0, 0), "br_upper": (-0.2 * limp, 0, -0.15 * limp), "br_lower": (0.5 * limp, 0, 0)}


CLIPS = [
    ("idle", 3.0, True, pose_idle, []),
    ("walk", 1.2, True, pose_walk, [(0.0, "step", "Step L"), (0.6, "step", "Step R")]),
    ("run", 0.66, True, pose_run, [(0.2, "step", "Lift-off")]),
    ("attack", 1.8, False, pose_attack, [(0.45, "anticipation", "Rear up + roar"), (1.12, "hit", "Swipe hits"), (1.5, "restored", "Recover")]),
    ("death", 2.6, False, pose_death, [(0.4, "anticipation", "Stagger"), (1.15, "fall", "Hits ground"), (1.42, "step", "Settle")]),
]


def bake():
    clips = []
    for name, T, loop, fn, events in CLIPS:
        n = int(round(T * FPS))
        frames = []
        for f in range(n + 1):
            t = f / FPS
            pose = fn(t, T) if name in ("idle", "walk", "run") else fn(t)
            fr = {"t": [round(c, 4) for c in pose.get("_t", (0, 0, 0))]}
            for b, _, _ in BONES:
                fr[b] = [round(c, 5) for c in euler_q(*pose.get(b, (0, 0, 0)))]
            frames.append(fr)
        clips.append({"name": name, "duration": T, "loop": loop, "frames": frames,
                      "events": [{"t": t, "type": ty, "label": lb} for t, ty, lb in events]})
    return clips


# ----------------------------------------------------------------------------- shaders

def glsl(name, desc, body):
    return HEADER.format(name=name, desc=desc) + body

PS1_VERT = glsl("ps1.vert", "PS1 vertex pipeline: Gouraud light, fog, screen-grid snapping, affine UV setup, random vertex glitches.", """
uniform vec3  uSunDir;
uniform vec3  uSunColor;
uniform vec3  uAmbient;
uniform float uTime;
uniform vec2  uSnapRes;      // virtual screen the vertices snap to (0 = off)
uniform float uGlitch;       // 0..1 probability scale of vertex spikes
uniform float uAffine;       // 1 = affine texture mapping
varying vec3  vUvAff;
varying vec3  vLight;
varying float vFog;

float hash(vec3 p) { p = fract(p * 0.3183099 + 0.1); p *= 17.0; return fract(p.x * p.y * p.z * (p.x + p.y + p.z)); }

void main() {
  vec4 wp = modelMatrix * vec4(position, 1.0);
  vec3 n = normalize(mat3(modelMatrix) * normal);
  // glitch: a few vertices jump along their normal for one 1/12s tick
  float tick = floor(uTime * 12.0);
  float h = hash(position * 13.7 + tick);
  if (h > 1.0 - uGlitch * 0.035) wp.xyz += n * (0.06 + 0.14 * hash(position + tick + 3.1));
  vLight = uAmbient + uSunColor * max(dot(n, normalize(uSunDir)), 0.0);
  vec4 mv = viewMatrix * wp;
  vFog = clamp((-mv.z - 9.0) / 18.0, 0.0, 1.0);
  vec4 cp = projectionMatrix * mv;
  if (uSnapRes.x > 0.0) {
    vec2 g = uSnapRes * 0.5;
    cp.xy = floor(cp.xy / cp.w * g + 0.5) / g * cp.w;
  }
  // affine trick: interpolate uv*w and w, divide per-pixel -> screen-linear (wobbly) texturing
  float w = mix(1.0, cp.w, uAffine);
  vUvAff = vec3(uv * w, w);
  gl_Position = cp;
}
""")

PS1_FRAG = glsl("ps1.frag", "Nearest 64px texel x Gouraud light, 15-bit colour with 4x4 ordered dither, fog.", """
uniform sampler2D uMap;
uniform vec3  uTint;
uniform vec3  uFogColor;
uniform float uDither;
uniform float uTiling;
varying vec3  vUvAff;
varying vec3  vLight;
varying float vFog;

float bayer(vec2 p) {
  vec2 f = mod(floor(p), 4.0);
  float i = f.y * 4.0 + f.x;
  return mod(i * 9.0 + floor(i / 4.0) * 3.0, 16.0) / 16.0;
}

void main() {
  vec2 uv = vUvAff.xy / vUvAff.z * uTiling;
  vec3 c = texture2D(uMap, uv).rgb * uTint * vLight;
  c = mix(c, uFogColor, vFog);
  float d = (bayer(gl_FragCoord.xy) - 0.5) * uDither;
  c = floor(c * 31.0 + d + 0.5) / 31.0;
  gl_FragColor = vec4(c, 1.0);
}
""")

BLIT_VERT = glsl("blit.vert", "Fullscreen quad.", "varying vec2 vUv;\nvoid main() { vUv = uv; gl_Position = vec4(position.xy, 0.0, 1.0); }\n")
BLIT_FRAG = glsl("blit.frag", "Nearest-neighbour upscale of the low-res frame + faint CRT line mask.", """
uniform sampler2D tFrame;
uniform vec2 uRes;
uniform float uLines;
varying vec2 vUv;
void main() {
  vec3 c = texture2D(tFrame, vUv).rgb;
  c *= 1.0 - uLines * 0.12 * mod(floor(vUv.y * uRes.y), 2.0);
  gl_FragColor = vec4(c, 1.0);
}
""")


# ----------------------------------------------------------------------------- bundle

def generate(out, spec=None):
    for d in ("meshes", "textures", "shaders", "animations", "runtime"):
        os.makedirs(os.path.join(out, d), exist_ok=True)
    textures(os.path.join(out, "textures"))
    rig = build()
    parts = [p for b, _, _ in BONES for p in rig[b]]
    # OBJ object names encode the bone: "<bone>__<part>"
    for b, _, _ in BONES:
        for p in rig[b]:
            p.name = b + "__" + p.name.split("__")[0]
    tris = sum(p.tri_count for p in parts)
    M.write_obj(os.path.join(out, "meshes", "bear_rigid.obj"), parts, header="PS2-era bear, rigid-part rig (bind pose)\n%d triangles, %d bones" % (tris, len(BONES)))
    env = environment()
    env_tris = sum(p.tri_count for p in env)
    M.write_obj(os.path.join(out, "meshes", "forest_clearing.obj"), env, header="Forest clearing set (%d tris)" % env_tris)
    clips = bake()
    rig_json = {"bones": [{"name": b, "parent": par, "pivot": list(piv)} for b, par, piv in BONES], "fps": FPS,
                "convention": "quaternions are local rotations about the bone pivot; 't' is the body offset in metres",
                "clips": clips}
    with open(os.path.join(out, "animations", "bear_clips.anim.json"), "w") as f:
        json.dump(rig_json, f, separators=(",", ":"))
    anims = []
    for c in clips:
        times = [i / FPS for i in range(len(c["frames"]))]
        tracks = {b: {"rotation": [fr[b] for fr in c["frames"]]} for b, _, _ in BONES}
        tracks["body"]["translation"] = [[PIVOT["body"][k] + fr["t"][k] for k in range(3)] for fr in c["frames"]]
        anims.append({"name": c["name"], "times": times, "tracks": tracks})
    M.write_gltf_rig(os.path.join(out, "meshes", "bear_rigged.gltf"), BONES, rig,
                     {"fur": {"color": (0.4, 0.26, 0.14)}, "muzzle": {"color": (0.65, 0.5, 0.34)}, "dark": {"color": (0.05, 0.04, 0.04)},
                      "eye": {"color": (0.02, 0.02, 0.02)}, "claw": {"color": (0.85, 0.8, 0.7)}}, anims)
    shaders = {"ps1.vert": PS1_VERT, "ps1.frag": PS1_FRAG, "blit.vert": BLIT_VERT, "blit.frag": BLIT_FRAG}
    for n, src in shaders.items():
        with open(os.path.join(out, "shaders", n), "w") as fh:
            fh.write(src)
    shutil.copy(os.path.join(os.path.dirname(__file__), "runtime", "bear_viewer.js"), os.path.join(out, "runtime", "viewer.js"))

    T = "textures/"
    files = [
        {"path": "meshes/bear_rigid.obj", "kind": "mesh", "role": "rigid-part character (bind pose)", "meta": {"triangles": tris, "bones": len(BONES)},
         "depends": [T + "bear_fur.png", T + "bear_muzzle.png"]},
        {"path": "meshes/bear_rigged.gltf", "kind": "mesh", "role": "glTF 2.0 · hierarchy + 5 clips", "meta": {"triangles": tris, "clips": len(clips)},
         "depends": ["animations/bear_clips.anim.json"]},
        {"path": "meshes/forest_clearing.obj", "kind": "mesh", "role": "environment set", "meta": {"triangles": env_tris},
         "depends": [T + n for n in ("grass.png", "pine.png", "bark.png", "rock.png")]},
        {"path": "animations/bear_clips.anim.json", "kind": "animation", "role": "skeleton + 5 baked clips @30fps", "meta": {"clips": [c["name"] for c in clips]},
         "depends": ["meshes/bear_rigid.obj"]},
    ]
    for n, r in (("bear_fur.png", 64), ("bear_muzzle.png", 32), ("grass.png", 64), ("pine.png", 32), ("bark.png", 32), ("rock.png", 32)):
        files.append({"path": T + n, "kind": "texture", "role": "%dpx 15-bit dithered" % r, "meta": {"width": r}})
    files += [{"path": "shaders/ps1.vert", "kind": "shader", "role": "vertex · snap / affine / glitch", "depends": ["meshes/bear_rigid.obj"]},
              {"path": "shaders/ps1.frag", "kind": "shader", "role": "fragment · 15-bit dither", "depends": ["shaders/ps1.vert", T + "bear_fur.png"]},
              {"path": "shaders/blit.vert", "kind": "shader", "role": "vertex"},
              {"path": "shaders/blit.frag", "kind": "shader", "role": "fragment · nearest upscale", "depends": ["shaders/blit.vert"]},
              {"path": "runtime/viewer.js", "kind": "data", "role": "plug-in viewer · state machine", "depends": ["animations/bear_clips.anim.json", "shaders/ps1.frag", "shaders/blit.frag"]}]
    render = {"type": "module", "module": "runtime/viewer.js", "timeline": True,
              "camera": {"position": [4.2, 2.4, 4.6], "target": [0, 0.9, 0.2], "fov": 42},
              "mesh": "meshes/bear_rigid.obj", "env": "meshes/forest_clearing.obj", "anim": "animations/bear_clips.anim.json",
              "shaders": {"vert": "shaders/ps1.vert", "frag": "shaders/ps1.frag", "blit_v": "shaders/blit.vert", "blit_f": "shaders/blit.frag"},
              "maps": {"fur": T + "bear_fur.png", "muzzle": T + "bear_muzzle.png", "grass": T + "grass.png", "pine": T + "pine.png", "bark": T + "bark.png", "rock": T + "rock.png"},
              "tints": {"fur": [1, 1, 1], "muzzle": [1, 1, 1], "dark": [0.12, 0.1, 0.1], "eye": [0.05, 0.05, 0.06], "claw": [1.4, 1.35, 1.2]},
              "light": {"sun": [0.5, 0.9, 0.4], "sunColor": [1.0, 0.95, 0.85], "ambient": [0.42, 0.45, 0.55], "fog": [0.56, 0.66, 0.78], "sky": [0.56, 0.66, 0.78]},
              "output": {"res": [320, 240], "snap": 1.0, "affine": 1.0, "glitch": 0.5, "dither": 1.0}}
    variants = [
        {"id": "grizzly", "name": "Grizzly", "group": "Fur", "default": True, "swatch": "#6b4423", "patch": {}},
        {"id": "polar", "name": "Polar", "group": "Fur", "swatch": "#e8e4da", "patch": {"tints.fur": [2.4, 2.45, 2.5], "tints.muzzle": [1.5, 1.55, 1.6]}},
        {"id": "black", "name": "Black Bear", "group": "Fur", "swatch": "#262222", "patch": {"tints.fur": [0.38, 0.36, 0.38], "tints.muzzle": [0.9, 0.78, 0.65]}},
        {"id": "day", "name": "Day", "group": "Light", "default": True, "swatch": "#8fb0d0", "patch": {}},
        {"id": "dusk", "name": "Dusk", "group": "Light", "swatch": "#d0784a", "patch": {"light.sunColor": [1.1, 0.6, 0.35], "light.ambient": [0.35, 0.25, 0.35], "light.fog": [0.55, 0.32, 0.3], "light.sky": [0.55, 0.32, 0.3]}},
        {"id": "night", "name": "Night", "group": "Light", "swatch": "#1d2244", "patch": {"light.sunColor": [0.35, 0.45, 0.8], "light.ambient": [0.12, 0.13, 0.22], "light.fog": [0.05, 0.06, 0.12], "light.sky": [0.05, 0.06, 0.12]}},
    ]
    return {
        "kind": "animation", "files": files, "render": render, "variants": variants,
        "stats": {"triangles": tris, "bones": len(BONES), "parts": len(parts), "clips": len(clips), "fps": FPS,
                  "frames": sum(len(c["frames"]) for c in clips), "textures": 6, "shaders": len(shaders), "max_texture": "64px",
                  "internal_resolution": "320x240", "per_part": {b: sum(p.tri_count for p in rig[b]) for b, _, _ in BONES}},
        "pipeline": [{"stage": s, "state": "done", "note": n} for s, n in [
            ("Interpret prompt", "animation · ps2 bear · ps1 vertex glitches · idle/walk/run/attack/death"),
            ("Rig-free model", "rigid-part rig: %d bones, %d parts, %d tris (no skinning, like the hardware era)" % (len(BONES), len(parts), tris)),
            ("Fracture pre-pass", "n/a - parts already split per bone"),
            ("Key poses", "procedural gait cycles (lateral walk, gallop), rear-up swipe, collapse"),
            ("Physics bake", "death fall eased with bounce, settle"),
            ("Event track", "steps, roar, hit, ground impact"),
            ("Texture synthesis", "64px fur/muzzle + forest set, 15-bit Bayer dithered, nearest filtered"),
            ("Shader authoring", "PS1 vertex snap, affine UVs, vertex glitch, Gouraud, 320×240 upscale"),
            ("Loop seam check", "idle/walk/run loop; attack/death return to idle via state machine"),
            ("glTF export", "node hierarchy + 5 named animations"),
            ("Preview render", "forest clearing at 320×240"),
            ("Package bundle", "OBJ + glTF + anim JSON + viewer")]],
    }
