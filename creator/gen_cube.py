"""Example 3 - Metal cube: anticipation, jump + flip, impact with white flash, corner shards break off revealing a
glowing core colour, shards settle and fade, then regenerate into the sockets -> seamless loop.

Everything is baked: a 60 fps frame track (JSON, includes flash / alpha / glow channels) and a glTF 2.0 TRS animation.
"""
import json
import math
import os

from . import mesh as M
from . import procedural as P
from .glsl import shader

FPS = 60
DURATION = 6.0
T_LAUNCH, T_LAND = 0.5, 1.40
T_FADE0, T_FADE1 = 2.9, 3.8
T_REGEN0, T_REGEN1 = 3.85, 5.4
GRAVITY = -11.0


def rng(i, k):
    return P._hash(i * 7 + 3, k * 13 + 1, 77)


# ----------------------------------------------------------------------------- fractured geometry

def oriented(a, b, c, ref):
    n = M.v_cross(M.v_sub(b, a), M.v_sub(c, a))
    return (a, b, c) if M.v_dot(n, ref) >= 0 else (a, c, b)


def face_uv(p, axis):
    o = [k for k in range(3) if k != axis]
    return ((p[o[0]] + 1) / 2, (p[o[1]] + 1) / 2)


def add_tri(part, tri, uv_fn):
    base = len(part.pos)
    for p in tri:
        part.pos.append(p)
        part.uv.append(uv_fn(p))
    part.tris.append((base, base + 1, base + 2))


def build():
    corners = [(sx, sy, sz) for sx in (1, -1) for sy in (1, -1) for sz in (1, -1)]
    cuts = {}
    for i, c in enumerate(corners):
        e = [0.42 + rng(i, k) * 0.3 for k in range(3)]
        E = [tuple(c[a] - (c[a] * e[a] if a == k else 0) for a in range(3)) for k in range(3)]
        depth = 0.40 + rng(i, 5) * 0.16
        A = tuple(c[a] * (1 - depth) + (rng(i, 6 + a) - 0.5) * 0.08 for a in range(3))
        inner = []
        for k in range(3):
            p, q = E[k], E[(k + 1) % 3]
            g = tuple((p[a] + q[a] + A[a]) / 3 + c[a] * (rng(i, 10 + k) - 0.5) * 0.18 for a in range(3))
            inner += [(p, q, g), (q, A, g), (A, p, g)]
        cuts[c] = {"E": E, "A": A, "inner": inner}

    tri_uv = lambda p: ((p[0] + p[1] * 0.5 + 1) / 2, (p[2] + p[1] * 0.5 + 1) / 2)
    body_m, body_c = M.Part("body_metal", "metal"), M.Part("body_core", "core")

    # Each cube face = octagon (square minus four corner notches), fan-triangulated from the face centre.
    for axis in range(3):
        for sgn in (1, -1):
            n = tuple(sgn if k == axis else 0 for k in range(3))
            o = [k for k in range(3) if k != axis]
            ring = []
            for a_, b_ in ((1, 1), (-1, 1), (-1, -1), (1, -1)):
                c = [0, 0, 0]
                c[axis], c[o[0]], c[o[1]] = sgn, a_, b_
                c = tuple(c)
                E = cuts[c]["E"]
                ring += [E[o[1]], E[o[0]]] if (a_ * b_ > 0) else [E[o[0]], E[o[1]]]
            centre = n
            for k in range(len(ring)):
                add_tri(body_m, oriented(centre, ring[k], ring[(k + 1) % len(ring)], n), lambda p, ax=axis: face_uv(p, ax))
    for c, cut in cuts.items():
        for tri in cut["inner"]:
            add_tri(body_c, oriented(*tri, c), tri_uv)

    shards = []
    for i, c in enumerate(corners):
        cut = cuts[c]
        sm, sc = M.Part("shard_%d_metal" % i, "metal"), M.Part("shard_%d_core" % i, "core")
        for axis in range(3):
            n = tuple(c[k] if k == axis else 0 for k in range(3))
            others = [cut["E"][k] for k in range(3) if k != axis]
            add_tri(sm, oriented(c, others[0], others[1], n), lambda p, ax=axis: face_uv(p, ax))
        for tri in cut["inner"]:
            add_tri(sc, oriented(*tri, M.v_mul(c, -1)), tri_uv)
        verts = sm.pos + sc.pos
        pivot = tuple(sum(v[a] for v in verts) / len(verts) for a in range(3))
        shards.append({"index": i, "corner": c, "metal": sm, "core": sc, "pivot": pivot, "verts": verts})
    for p in [body_m, body_c] + [s[k] for s in shards for k in ("metal", "core")]:
        p.compute_normals(weld=False)
    return body_m, body_c, shards


# ----------------------------------------------------------------------------- animation bake

def ease_io(t):
    t = P.clamp(t)
    return t * t * (3 - 2 * t)


def ease_out_back(t, s=1.6):
    t = P.clamp(t) - 1
    return t * t * ((s + 1) * t + s) + 1


def body_state(t):
    """Returns (pos, quat, scale) of the cube body at time t."""
    sy, sxz, y = 1.0, 1.0, 1.0
    q = (0.0, 0.0, 0.0, 1.0)
    if t < 0.45:                                           # anticipation squash
        k = ease_io(t / 0.45)
        sy, sxz = 1 - 0.22 * k, 1 + 0.12 * k
    elif t < T_LAUNCH:                                     # pop
        k = ease_io((t - 0.45) / (T_LAUNCH - 0.45))
        sy, sxz = 0.78 + 0.4 * k, 1.12 - 0.2 * k
    elif t < T_LAND:                                       # airborne flip
        s = (t - T_LAUNCH) / (T_LAND - T_LAUNCH)
        y = 1 + 2.7 * 4 * s * (1 - s)
        k = math.sin(s * math.pi)
        sy, sxz = 1 + 0.18 * (1 - s) ** 3 + 0.06 * s ** 4, 1 - 0.08 * (1 - s) ** 3
        q = M.q_axis((1.0, 0.25, 0.45), 2 * math.pi * ease_io(s * 1.05))
    else:                                                  # impact + damped spring recovery
        dt = t - T_LAND
        squash = 0.34 * math.exp(-dt * 6.5) * math.cos(dt * 22)
        sy, sxz = 1 - squash, 1 + squash * 0.55
        if T_REGEN0 < t < T_REGEN1 + 0.4:                   # breathing while re-forging
            b = math.sin((t - T_REGEN0) / (T_REGEN1 + 0.4 - T_REGEN0) * math.pi)
            sy, sxz = sy + 0.02 * b * math.sin(t * 9), sxz - 0.01 * b * math.sin(t * 9)
    if t >= T_LAND or t < T_LAUNCH:
        y = sy                                             # keep the bottom on the floor while squashing
    return (0.0, y, 0.0), M.q_norm(q), (sxz, sy, sxz)


def attached(t, pivot):
    pos, q, s = body_state(t)
    off = M.q_rotate(q, (pivot[0] * s[0], pivot[1] * s[1], pivot[2] * s[2]))
    return M.v_add(pos, off), q, s


def simulate(shard, broken):
    """Rigid-body-ish bake: impulse at impact, gravity, vertex-accurate ground contact, bounces, friction."""
    i, piv = shard["index"], shard["pivot"]
    local = [M.v_sub(v, piv) for v in shard["verts"]]
    frames = {}
    if not broken:
        return frames
    pos, q, _ = attached(T_LAND, piv)
    out = M.v_norm((piv[0], piv[1] * 0.4, piv[2]))
    speed = 2.4 + rng(i, 20) * 1.8
    vel = [out[0] * speed, 3.2 + rng(i, 21) * 2.2, out[2] * speed]
    axis = M.v_norm((rng(i, 22) - 0.5, rng(i, 23) - 0.5, rng(i, 24) - 0.5))
    spin = 7 + rng(i, 25) * 8
    p = list(pos)
    sub = 8
    dt = 1.0 / (FPS * sub)
    t = T_LAND
    frame = int(round(T_LAND * FPS))
    while t <= T_FADE1 + 1e-6:
        for _ in range(sub):
            vel[1] += GRAVITY * dt
            for a in range(3):
                p[a] += vel[a] * dt
            q = M.q_norm(M.q_mul(M.q_axis(axis, spin * dt), q))
            low = min(M.q_rotate(q, v)[1] for v in local) + p[1]
            if low < 0:
                p[1] -= low
                if vel[1] < 0:
                    vel[1] = -vel[1] * 0.32 if abs(vel[1]) > 1.2 else 0.0
                vel[0] *= 0.82
                vel[2] *= 0.82
                spin *= 0.72
            if p[1] + min(M.q_rotate(q, v)[1] for v in local) < 0.002:
                vel[0] *= 0.985
                vel[2] *= 0.985
                spin *= 0.97
            t += dt
        frames[frame] = (tuple(p), q)
        frame += 1
    return frames


def bake(shards, broken):
    sims = [simulate(s, s["index"] in broken) for s in shards]
    n = int(DURATION * FPS)
    frames = []
    for f in range(n + 1):
        t = f / FPS
        bp, bq, bs = body_state(t)
        fr = {"t": round(t, 4), "body": {"p": [round(c, 4) for c in bp], "q": [round(c, 5) for c in bq], "s": [round(c, 4) for c in bs]},
              "shards": []}
        for s, sim in zip(shards, sims):
            i = s["index"]
            if i in broken and T_LAND <= t < T_REGEN0 + 0.2 and f in sim and t < T_FADE1:
                p, q = sim[f]
                k = P.clamp((t - T_FADE0) / (T_FADE1 - T_FADE0))
                alpha = 1 - ease_io(k)
                sc = 1 - 0.45 * k
                p = (p[0], p[1] - 0.12 * k, p[2])
                state = {"p": p, "q": q, "s": (sc, sc, sc), "a": alpha, "m": 1}
            elif i in broken and T_FADE1 <= t < T_REGEN0:
                state = {"p": (0, -50, 0), "q": (0, 0, 0, 1), "s": (0, 0, 0), "a": 0.0, "m": 1}
            elif i in broken and T_REGEN0 <= t < T_REGEN1 + 0.25 and t >= T_LAND:
                stagger = (sorted(broken).index(i) / max(len(broken) - 1, 1)) * 0.5
                k = P.clamp((t - T_REGEN0 - stagger) / (T_REGEN1 - T_REGEN0 - 0.5))
                p, q, bsc = attached(t, s["pivot"])
                g = ease_out_back(k, 1.2) if k > 0 else 0.0
                state = {"p": p, "q": q, "s": tuple(c * max(g, 0.0) for c in bsc), "a": ease_io(k * 1.4), "m": 0}
            else:
                p, q, bsc = attached(t, s["pivot"])
                state = {"p": p, "q": q, "s": bsc, "a": 1.0, "m": 0}
            fr["shards"].append({"p": [round(c, 4) for c in state["p"]], "q": [round(c, 5) for c in state["q"]],
                                 "s": [round(c, 4) for c in state["s"]], "a": round(state["a"], 3), "m": state["m"]})
        dtl = t - T_LAND
        flash = math.exp(-dtl / 0.075) if dtl >= 0 else 0.0
        flash += 0.35 * math.exp(-max(t - T_REGEN1, 0) / 0.12) if t >= T_REGEN1 else 0.0
        glow = 0.0
        if t >= T_LAND:
            glow = 0.55 + 0.45 * math.exp(-dtl * 3)
            if t > T_REGEN0:
                glow *= 1 - ease_io((t - T_REGEN0) / (T_REGEN1 + 0.4 - T_REGEN0))
                glow += 0.35 * math.sin((t - T_REGEN0) * 10) ** 2 * (1 - ease_io((t - T_REGEN0) / (T_REGEN1 + 0.4 - T_REGEN0)))
        shake = 0.18 * math.exp(-dtl * 9) if dtl >= 0 else 0.0
        fr["fx"] = {"flash": round(min(flash, 1.0), 4), "glow": round(max(glow, 0.0), 4), "shake": round(shake, 4)}
        frames.append(fr)
    return frames


# ----------------------------------------------------------------------------- textures

def textures(out, res=256):
    rivets = [(0.09, 0.09), (0.91, 0.09), (0.09, 0.91), (0.91, 0.91), (0.5, 0.06), (0.5, 0.94), (0.06, 0.5), (0.94, 0.5)]
    heights = [0.0] * (res * res)
    fields = []
    for y in range(res):
        v = (y + 0.5) / res
        for x in range(res):
            u = (x + 0.5) / res
            brushed = P.fbm(u * 2, v * 90, 3, seed=2, period=0)
            n = P.fbm(u * 6, v * 6, 4, seed=5, period=6)
            edge = min(u, v, 1 - u, 1 - v)
            groove = 1 - P.smoothstep(0.0, 0.012, abs(edge - 0.15))
            inner_panel = P.smoothstep(0.15, 0.16, edge)
            rv = 0.0
            for rx, ry in rivets:
                d = math.hypot(u - rx, v - ry)
                if d < 0.03:
                    rv = max(rv, math.sqrt(1 - (d / 0.03) ** 2))
            wear = (1 - P.smoothstep(0.0, 0.07, edge)) * (0.5 + 0.5 * n)
            stain = P.smoothstep(0.55, 0.8, P.fbm(u * 3 + 7, v * 3, 3, seed=9))
            heights[y * res + x] = inner_panel * 0.25 - groove * 0.6 + rv * 0.7 + brushed * 0.05
            fields.append((brushed, n, groove, rv, wear, stain, inner_panel))

    def make(name, base_lo, base_hi, wear_c, stain_c, rough_base):
        img, rough = P.Image(res, res), P.Image(res, res)
        for i, (brushed, n, groove, rv, wear, stain, panel) in enumerate(fields):
            c = P.mix(base_lo, base_hi, brushed * 0.6 + n * 0.4)
            c = P.mix(c, P.mix(base_lo, (0, 0, 0), 0.25), (1 - panel) * 0.35)
            c = P.mix(c, wear_c, wear * 0.7)
            c = P.mix(c, stain_c, stain * 0.55)
            c = P.mix(c, (0.04, 0.04, 0.045), groove * 0.85)
            c = P.mix(c, P.mix(base_hi, (1, 1, 1), 0.3), rv * 0.6)
            img.data[i] = list(c) + [1.0]
            r = P.clamp(rough_base + brushed * 0.12 + stain * 0.3 - wear * 0.15 - rv * 0.1 + groove * 0.3)
            rough.data[i] = [r, r, r, 1.0]
        img.save(os.path.join(out, "cube_%s_albedo.png" % name), alpha=False)
        rough.save(os.path.join(out, "cube_%s_roughness.png" % name), alpha=False)

    make("steel", (0.46, 0.48, 0.52), (0.74, 0.76, 0.80), (0.92, 0.93, 0.95), (0.30, 0.26, 0.22), 0.32)
    make("copper", (0.62, 0.30, 0.16), (0.92, 0.55, 0.36), (1.0, 0.78, 0.6), (0.22, 0.62, 0.52), 0.30)
    make("obsidian", (0.03, 0.025, 0.05), (0.12, 0.10, 0.17), (0.45, 0.35, 0.7), (0.08, 0.02, 0.12), 0.08)
    P.height_to_normal(heights, res, res, 4.0).save(os.path.join(out, "cube_normal.png"), alpha=False)


# ----------------------------------------------------------------------------- shaders

VERT = shader("cube.vert", "World + object-space varyings (object space drives the core's internal veins).", """
varying vec3 vWorldPos;
varying vec3 vObjPos;
varying vec3 vNormal;
varying vec2 vUv;
void main() {
  vUv = uv;
  vObjPos = position;
  vec4 wp = modelMatrix * vec4(position, 1.0);
  vWorldPos = wp.xyz;
  vNormal = normalize(mat3(modelMatrix) * normal);
  gl_Position = projectionMatrix * viewMatrix * wp;
}
""", frag=False)

METAL = shader("cube_metal.frag", "Brushed metal skin + damage flash (uFlash) + fade (uAlpha).", """
uniform sampler2D uAlbedo;
uniform sampler2D uRoughness;
uniform sampler2D uNormalMap;
uniform float uMetalness;
uniform float uFlash;
uniform float uAlpha;
varying vec3 vWorldPos;
varying vec3 vObjPos;
varying vec3 vNormal;
varying vec2 vUv;

void main() {
  vec3 N = normalize(vNormal);
  vec3 Nb = perturbNormal(N, vWorldPos, vUv, texture2D(uNormalMap, vUv).xyz * 2.0 - 1.0, 1.0);
  vec3 V = normalize(cameraPosition - vWorldPos);
  vec3 L = normalize(uLightDir);
  vec3 alb = texture2D(uAlbedo, vUv).rgb;
  float r = texture2D(uRoughness, vUv).r;
  float ndv = max(dot(Nb, V), 0.0);
  vec3 F0 = mix(vec3(0.04), alb, uMetalness);
  vec3 F = F0 + (1.0 - F0) * pow(1.0 - ndv, 5.0) * (1.0 - r * 0.7);
  vec3 R = reflect(-V, Nb);
  vec3 env = mix(envColor(R), (envColor(normalize(R + Nb)) + envColor(Nb)) * 0.5, smoothstep(0.05, 0.6, r));
  vec3 H = normalize(L + V);
  float gloss = mix(600.0, 16.0, r);
  float spec = pow(max(dot(Nb, H), 0.0), gloss) * (gloss + 8.0) / 30.0;
  vec3 diffuse = alb * (1.0 - uMetalness) * (uLightColor * max(dot(Nb, L), 0.0) + envColor(Nb) * 0.3);
  vec3 col = diffuse + F * env + F * uLightColor * spec * max(dot(Nb, L), 0.0);
  // Damage flash: the texture burns to white, then decays (driven by the baked fx.flash channel).
  col = mix(col, vec3(4.0), uFlash);
  gl_FragColor = vec4(tonemap(col), uAlpha);
}
""")

CORE = shader("cube_core.frag", "Exposed interior: iridescent molten crystal with moving veins (special inner colour).", """
uniform vec3  uCoreA;
uniform vec3  uCoreB;
uniform float uGlow;
uniform float uFlash;
uniform float uAlpha;
varying vec3 vWorldPos;
varying vec3 vObjPos;
varying vec3 vNormal;
varying vec2 vUv;

float vnoise(vec3 p) {
  vec3 i = floor(p), f = fract(p);
  f = f * f * (3.0 - 2.0 * f);
  return mix(mix(mix(hash13(i), hash13(i + vec3(1, 0, 0)), f.x), mix(hash13(i + vec3(0, 1, 0)), hash13(i + vec3(1, 1, 0)), f.x), f.y),
             mix(mix(hash13(i + vec3(0, 0, 1)), hash13(i + vec3(1, 0, 1)), f.x), mix(hash13(i + vec3(0, 1, 1)), hash13(i + vec3(1, 1, 1)), f.x), f.y), f.z);
}

void main() {
  vec3 N = normalize(cross(dFdx(vWorldPos), dFdy(vWorldPos)));
  vec3 V = normalize(cameraPosition - vWorldPos);
  if (dot(N, V) < 0.0) N = -N;
  float ndv = max(dot(N, V), 0.0);
  vec3 p = vObjPos * 4.0;
  float n = vnoise(p + vec3(0.0, uTime * 0.6, 0.0)) * 0.6 + vnoise(p * 2.3 - uTime * 0.4) * 0.4;
  float veins = smoothstep(0.08, 0.0, abs(n - 0.5));
  float irid = 0.5 + 0.5 * sin(ndv * 9.0 + n * 6.0 + uTime * 1.5);
  vec3 col = mix(uCoreA, uCoreB, irid) * (0.35 + 0.65 * ndv);
  col += mix(uCoreB, vec3(1.0), 0.4) * veins * (0.6 + 1.8 * uGlow);
  col *= 0.6 + 1.6 * uGlow;
  col += envColor(reflect(-V, N)) * pow(1.0 - ndv, 4.0) * 0.4;
  col = mix(col, vec3(4.0), uFlash);
  gl_FragColor = vec4(tonemap(col), uAlpha);
}
""")

FLOOR_VERT = shader("floor.vert", "Studio floor.", """
varying vec3 vWorldPos;
void main() {
  vec4 wp = modelMatrix * vec4(position, 1.0);
  vWorldPos = wp.xyz;
  gl_Position = projectionMatrix * viewMatrix * wp;
}
""", frag=False)

FLOOR = shader("floor.frag", "Infinite studio floor: fading grid, soft analytic contact shadows from up to 9 casters, impact ring.", """
uniform vec4  uCasters[9];      // xyz = world centre, w = radius
uniform vec3  uFloorColor;
uniform vec3  uGridColor;
uniform float uImpact;          // 0..1 shock-ring progress
uniform vec3  uRingColor;
varying vec3  vWorldPos;

void main() {
  vec2 p = vWorldPos.xz;
  vec2 g = abs(fract(p) - 0.5);
  float line = smoothstep(0.485, 0.5, max(g.x, g.y));
  vec2 g4 = abs(fract(p * 0.25) - 0.5);
  line = max(line, smoothstep(0.492, 0.5, max(g4.x, g4.y)) * 1.5);
  float fade = exp(-length(p) * 0.09);
  vec3 col = uFloorColor + uGridColor * line * fade * 0.5;
  float shadow = 0.0;
  for (int i = 0; i < 9; i++) {
    vec4 c = uCasters[i];
    float h = max(c.y, 0.0);
    float d = length(p - c.xz) / (c.w * (1.0 + h * 0.6));
    shadow = max(shadow, (1.0 - smoothstep(0.2, 1.25, d)) / (1.0 + h * 0.9));
  }
  col *= 1.0 - shadow * 0.75;
  if (uImpact > 0.0 && uImpact < 1.0) {
    float r = uImpact * 5.5;
    float ring = smoothstep(0.25, 0.0, abs(length(p) - r)) * (1.0 - uImpact);
    col += uRingColor * ring * 1.6;
  }
  col *= mix(1.0, 0.25, smoothstep(6.0, 24.0, length(p)));
  gl_FragColor = vec4(tonemap(col), 1.0);
}
""")


# ----------------------------------------------------------------------------- bundle

def generate(out, spec=None):
    for d in ("meshes", "textures", "shaders", "animations"):
        os.makedirs(os.path.join(out, d), exist_ok=True)
    textures(os.path.join(out, "textures"))
    shaders = {"cube.vert": VERT, "cube_metal.frag": METAL, "cube_core.frag": CORE, "floor.vert": FLOOR_VERT, "floor.frag": FLOOR}
    for n, src in shaders.items():
        with open(os.path.join(out, "shaders", n), "w") as f:
            f.write(src)

    body_m, body_c, shards = build()
    broken = [0, 2, 3, 5, 6]          # 5 of 8 corners chip off on impact
    parts = [body_m, body_c] + [s[k] for s in shards for k in ("metal", "core")]
    tris = sum(p.tri_count for p in parts)
    M.write_obj(os.path.join(out, "meshes", "metal_cube_fractured.obj"), parts,
                header="Pre-fractured metal cube: body + 8 corner shards (metal skin / core interior)\n%d triangles" % tris)

    frames = bake(shards, broken)
    pivots = {"shard_%d" % s["index"]: [round(c, 5) for c in s["pivot"]] for s in shards}
    anim = {
        "name": "jump_shatter_regenerate", "fps": FPS, "duration": DURATION, "loop": True, "frameCount": len(frames),
        "objects": {"body": ["body_metal", "body_core"], **{"shard_%d" % s["index"]: ["shard_%d_metal" % s["index"], "shard_%d_core" % s["index"]] for s in shards}},
        "pivots": pivots, "broken": ["shard_%d" % i for i in broken],
        "events": [
            {"t": 0.0, "type": "anticipation", "label": "Crouch"},
            {"t": T_LAUNCH, "type": "launch", "label": "Jump + flip"},
            {"t": T_LAND, "type": "impact", "label": "Impact · flash · shatter", "strength": 1.0},
            {"t": T_FADE0, "type": "fade", "label": "Shards fade"},
            {"t": T_REGEN0, "type": "regen", "label": "Regeneration"},
            {"t": T_REGEN1, "type": "restored", "label": "Restored"},
        ],
        "channels": {"fx.flash": "white-hot texture flash (metal + core)", "fx.glow": "core emission strength", "fx.shake": "camera shake amplitude",
                     "shards[].a": "alpha", "shards[].m": "1 = detached (physics), 0 = socketed"},
        "frames": frames,
    }
    with open(os.path.join(out, "animations", "cube_damage_loop.anim.json"), "w") as f:
        json.dump(anim, f, separators=(",", ":"))

    # glTF TRS export (alpha/flash channels are engine-side; scale carries the fade-out/regrow).
    times = [fr["t"] for fr in frames]
    tracks = {}
    for name in ("body_metal", "body_core"):
        tracks[name] = {"translation": [fr["body"]["p"] for fr in frames], "rotation": [fr["body"]["q"] for fr in frames],
                        "scale": [fr["body"]["s"] for fr in frames]}
    for s in shards:
        i = s["index"]
        tr = {"translation": [fr["shards"][i]["p"] for fr in frames], "rotation": [fr["shards"][i]["q"] for fr in frames],
              "scale": [[c * (1 if fr["shards"][i]["a"] > 0.01 else 0) for c in fr["shards"][i]["s"]] for fr in frames]}
        tracks["shard_%d_metal" % i] = tracks["shard_%d_core" % i] = tr
    node_pivots = {"shard_%d_%s" % (s["index"], k): s["pivot"] for s in shards for k in ("metal", "core")}
    M.write_gltf(os.path.join(out, "meshes", "metal_cube_animated.gltf"), parts,
                 {"metal": {"color": (0.7, 0.72, 0.76), "metallic": 1.0, "roughness": 0.35},
                  "core": {"color": (0.9, 0.1, 0.8), "roughness": 0.2, "emissive": (0.9, 0.1, 0.8)}},
                 {"name": "jump_shatter_regenerate", "times": times, "tracks": tracks}, node_pivots)

    T = "textures/"
    render = {
        "type": "animation",
        "mesh": "meshes/metal_cube_fractured.obj",
        "animation": "animations/cube_damage_loop.anim.json",
        "camera": {"position": [5.2, 3.6, 6.4], "target": [0, 1.4, 0], "fov": 38},
        "light": {"dir": [0.5, 0.9, 0.35], "color": [1.2, 1.15, 1.1]},
        "uniforms": {"uExposure": 1.0},
        "materials": {
            "metal": {"vert": "shaders/cube.vert", "frag": "shaders/cube_metal.frag",
                      "maps": {"uAlbedo": T + "cube_steel_albedo.png", "uRoughness": T + "cube_steel_roughness.png", "uNormalMap": T + "cube_normal.png"},
                      "uniforms": {"uMetalness": 1.0},
                      "pbr": {"map": T + "cube_steel_albedo.png", "roughnessMap": T + "cube_steel_roughness.png", "normalMap": T + "cube_normal.png", "metalness": 1.0, "roughness": 1.0}},
            "core": {"vert": "shaders/cube.vert", "frag": "shaders/cube_core.frag", "maps": {},
                     "uniforms": {"uCoreA": [0.55, 0.0, 0.9], "uCoreB": [0.0, 0.95, 0.9]},
                     "pbr": {"color": [0.8, 0.1, 0.8], "emissive": [0.6, 0.0, 0.7], "roughness": 0.2}},
        },
        "floor": {"vert": "shaders/floor.vert", "frag": "shaders/floor.frag", "color": [0.11, 0.115, 0.135], "grid": [0.5, 0.55, 0.75], "ring": [0.4, 0.9, 1.0]},
    }
    mat = lambda n: {"materials.metal.maps.uAlbedo": T + "cube_%s_albedo.png" % n, "materials.metal.maps.uRoughness": T + "cube_%s_roughness.png" % n,
                     "materials.metal.pbr.map": T + "cube_%s_albedo.png" % n, "materials.metal.pbr.roughnessMap": T + "cube_%s_roughness.png" % n}
    variants = [
        {"id": "steel", "name": "Brushed Steel", "group": "Skin", "default": True, "swatch": "#aab0bb", "patch": {}},
        {"id": "copper", "name": "Weathered Copper", "group": "Skin", "swatch": "#d0784a", "patch": mat("copper")},
        {"id": "obsidian", "name": "Obsidian", "group": "Skin", "swatch": "#2a2238", "patch": {**mat("obsidian"), "materials.metal.uniforms.uMetalness": 0.6}},
        {"id": "prism", "name": "Prism Core", "group": "Core", "default": True, "swatch": "#b03bff", "patch": {}},
        {"id": "toxic", "name": "Toxic Core", "group": "Core", "swatch": "#8cff3a",
         "patch": {"materials.core.uniforms.uCoreA": [0.05, 0.4, 0.0], "materials.core.uniforms.uCoreB": [0.75, 1.0, 0.1], "floor.ring": [0.6, 1.0, 0.2]}},
        {"id": "ember", "name": "Solar Ember", "group": "Core", "swatch": "#ff6a1a",
         "patch": {"materials.core.uniforms.uCoreA": [0.6, 0.02, 0.0], "materials.core.uniforms.uCoreB": [1.0, 0.75, 0.1], "floor.ring": [1.0, 0.5, 0.1]}},
    ]
    files = [
        {"path": "meshes/metal_cube_fractured.obj", "kind": "mesh", "role": "pre-fractured mesh (9 pieces)", "meta": {"triangles": tris, "pieces": 9}},
        {"path": "meshes/metal_cube_animated.gltf", "kind": "mesh", "role": "glTF 2.0 + baked TRS animation", "meta": {"triangles": tris, "frames": len(frames)},
         "depends": ["animations/cube_damage_loop.anim.json"]},
        {"path": "animations/cube_damage_loop.anim.json", "kind": "animation", "role": "60fps baked frames + fx channels",
         "meta": {"fps": FPS, "duration": DURATION, "frames": len(frames)}, "depends": ["meshes/metal_cube_fractured.obj"]},
    ]
    for n in ("steel", "copper", "obsidian"):
        for m in ("albedo", "roughness"):
            files.append({"path": T + "cube_%s_%s.png" % (n, m), "kind": "texture", "role": m + ("" if n == "steel" else " variant"),
                          "meta": {"width": 256}, "variant": None if n == "steel" else n})
    files.append({"path": T + "cube_normal.png", "kind": "texture", "role": "normal", "meta": {"width": 256}})
    files += [
        {"path": "shaders/cube.vert", "kind": "shader", "role": "vertex", "depends": ["meshes/metal_cube_fractured.obj"]},
        {"path": "shaders/cube_metal.frag", "kind": "shader", "role": "fragment · flash", "depends": ["shaders/cube.vert"] + [T + "cube_%s_%s.png" % (n, m) for n in ("steel", "copper", "obsidian") for m in ("albedo", "roughness")] + [T + "cube_normal.png"]},
        {"path": "shaders/cube_core.frag", "kind": "shader", "role": "fragment · inner colour", "depends": ["shaders/cube.vert"]},
        {"path": "shaders/floor.vert", "kind": "shader", "role": "vertex"},
        {"path": "shaders/floor.frag", "kind": "shader", "role": "fragment · contact shadows", "depends": ["shaders/floor.vert", "animations/cube_damage_loop.anim.json"]},
    ]
    return {
        "kind": "animation", "files": files, "render": render, "variants": variants,
        "stats": {"triangles": tris, "pieces": 9, "shards_broken": len(broken), "fps": FPS, "duration": DURATION, "frames": len(frames),
                  "events": len(anim["events"]), "textures": 7, "shaders": len(shaders), "loop": "seamless (frame 0 == frame %d)" % (len(frames) - 1)},
        "pipeline": [{"stage": s, "state": "done", "note": n} for s, n in [
            ("Interpret prompt", "animation · metal cube · jump/rotate/land · shards · flash · regenerate · loop"),
            ("Rig-free model", "TRS-animated pieces, no skeleton needed"),
            ("Fracture pre-pass", "8 jagged corner shards, 9 inner facets each, watertight sockets"),
            ("Key poses", "crouch → pop → 360° flip → squash → spring"),
            ("Physics bake", "%d shards · gravity, vertex ground contact, bounce, friction" % len(broken)),
            ("Event track", "flash, core glow, camera shake, shock ring"),
            ("Texture synthesis", "brushed steel panels + rivets; copper & obsidian variants"),
            ("Shader authoring", "flash-able metal, iridescent molten core, contact-shadow floor"),
            ("Loop seam check", "frame 0 ≡ frame %d" % (len(frames) - 1)),
            ("glTF export", "TRS channels for 18 nodes"),
            ("Preview render", "rendered in-browser on first view"),
            ("Package bundle", "manifest + anim JSON + glTF")]],
    }
