"""Example 1 - Sea turtle with a golden crown. <= 15,000 polygons, textured, custom shaders, LOD chain."""
import math
import os

from . import mesh as M
from . import procedural as P
from .glsl import shader

BUDGET = 15000


# ----------------------------------------------------------------------------- geometry

def build_turtle(q=1.0):
    """q scales tessellation (1.0 = hero LOD0). Returns list of Parts. Turtle faces +Z, Y up."""
    s = lambda n, lo=4: max(lo, int(round(n * q)))
    parts = []

    # Carapace: dome sculpted with vertebral ridge, rear taper, serrated marginal scutes.
    def carapace(p, u, v):
        x, y, z = p
        ridge = 0.07 * math.exp(-(x / 0.18) ** 2) * max(y, 0)
        y = y * 0.5 + ridge if y > 0 else y * 0.32
        z *= 1.32
        if z < 0:
            x *= 1 - 0.16 * (-z / 1.32) ** 2
        rim = P.smoothstep(0.75, 1.0, v)
        serr = 1 + rim * 0.035 * max(0.0, math.sin(u * math.pi * 2 * 26)) * P.smoothstep(0.1, -0.9, z / 1.32)
        return (x * serr, y - rim * 0.03, z * serr)

    shell = M.uv_sphere("carapace", "shell", s(84, 12), s(28, 6), carapace, th_max=math.pi * 0.62)
    shell.uv = [(p[0] / 2.2 + 0.5, p[2] / 2.8 + 0.5) for p in shell.pos]   # planar top-down: scutes live in this space
    parts.append(shell.translate((0, 0.12, 0)))

    plastron = M.uv_sphere("plastron", "plastron", s(40, 10), s(14, 5))
    plastron.scale((0.9, 0.13, 1.18)).translate((0, -0.02, 0))
    plastron.uv = [(p[0] / 1.9 + 0.5, p[2] / 2.4 + 0.5) for p in plastron.pos]
    parts.append(plastron)

    # Head: egg with hooked beak, slightly raised to look forward/up.
    def head_shape(p, u, v):
        x, y, z = p
        beak = P.smoothstep(0.2, 1.0, z)
        y = y * (1 - 0.25 * beak) - 0.08 * beak * beak
        x = x * (1 - 0.3 * beak)
        return (x * 0.27, y * 0.24, z * 0.38)

    head = M.uv_sphere("head", "skin", s(48, 10), s(24, 6), head_shape).rotate(rx=-0.12).translate((0, 0.12, 1.62))
    parts.append(head)

    neck = M.lathe("neck", "skin", [(0.3, 0), (0.29, 0.12), (0.25, 0.26), (0.22, 0.38), (0.2, 0.46)], s(24, 8))
    parts.append(neck.rotate(rx=math.pi / 2).rotate(rx=-0.1).translate((0, 0.07, 1.0)))

    for side in (1, -1):
        eye = M.uv_sphere("eye_" + ("r" if side > 0 else "l"), "eye", s(16, 6), s(8, 4)).scale(0.055)
        parts.append(eye.translate((side * 0.205, 0.2, 1.75)))

    # Flippers: span along +X from the root, swept back, tapered, wing-thin.
    def flipper(length, width, sweep, thick):
        def f(p, u, v):
            t = (p[0] + 1) / 2
            taper = 1 - 0.72 * t ** 1.3
            x = t * length
            z = p[2] * width * taper - sweep * t * t
            y = p[1] * thick * (1 - 0.6 * t) + 0.05 * math.sin(t * math.pi)
            return (x, y, z)
        return f

    for side in (1, -1):
        fr = M.uv_sphere("flipper_front_" + ("r" if side > 0 else "l"), "skin", s(32, 8), s(14, 5),
                         flipper(1.35, 0.27, 0.55, 0.06)).rotate(rz=-0.18).translate((0.78, -0.02, 0.72))
        rr = M.uv_sphere("flipper_rear_" + ("r" if side > 0 else "l"), "skin", s(24, 8), s(10, 4),
                         flipper(0.6, 0.22, 0.25, 0.05)).rotate(ry=-0.6, rz=-0.1).translate((0.55, -0.04, -0.98))
        if side < 0:
            for part in (fr, rr):
                part.scale((-1, 1, 1)).flip()
        parts += [fr, rr]

    tail = M.lathe("tail", "skin", [(0.11, 0), (0.08, 0.16), (0.0, 0.32)], s(16, 6))
    parts.append(tail.rotate(rx=-math.pi / 2 - 0.15).translate((0, 0.0, -1.18)))

    # Crown: tilted band + seven spikes topped with orbs + three front jewels.
    crown_parts, gems = [], []
    band = M.lathe("crown_band", "crown", [(0.155, 0), (0.175, 0.0), (0.185, 0.035), (0.178, 0.095),
                                           (0.163, 0.095), (0.155, 0.0)], s(48, 12))
    crown_parts.append(band)
    n_spikes = 7
    for k in range(n_spikes):
        a = k / n_spikes * 2 * math.pi
        spike = M.lathe("crown_spike_%d" % k, "crown", [(0.034, 0), (0.02, 0.07), (0.0, 0.13)], s(14, 5), cap_bottom=True)
        spike.rotate(rz=-0.18).rotate(ry=-a).translate((0.172 * math.cos(a), 0.09, 0.172 * math.sin(a)))
        crown_parts.append(spike)
        orb = M.uv_sphere("crown_orb_%d" % k, "gem", s(12, 6), s(6, 3)).scale(0.024)
        tip = M.rot_y(M.rot_z((0, 0.13, 0), -0.18), -a)
        gems.append(orb.translate((0.172 * math.cos(a) + tip[0], 0.09 + tip[1], 0.172 * math.sin(a) + tip[2])))
    for k, a in enumerate((math.pi / 2 - 0.5, math.pi / 2, math.pi / 2 + 0.5)):
        jewel = M.uv_sphere("crown_jewel_%d" % k, "gem", s(14, 6), s(8, 4)).scale((0.03, 0.03, 0.016))
        jewel.rotate(ry=math.pi / 2 - a)
        gems.append(jewel.translate((0.186 * math.cos(a), 0.05, 0.186 * math.sin(a))))
    for part in crown_parts + gems:
        part.rotate(rx=-0.22, rz=0.12).translate((0.0, 0.29, 1.56))
    parts += crown_parts + gems
    for part in parts:
        part.compute_normals()
    return parts


# ----------------------------------------------------------------------------- textures

def shell_textures(out, res=512):
    seeds = []
    for z in (1.0, 0.52, 0.05, -0.42, -0.88):
        seeds.append((0.0, z, 0))
    for z in (0.78, 0.3, -0.18, -0.64):
        seeds += [(0.56, z, 1), (-0.56, z, 1)]
    for k in range(26):
        a = k / 26 * 2 * math.pi
        seeds.append((1.0 * math.cos(a) * 0.98, 1.3 * math.sin(a) * 0.97, 2))
    heights = [0.0] * (res * res)
    img = P.Image(res, res)
    dark, amber, honey = (0.16, 0.11, 0.05), (0.47, 0.30, 0.12), (0.78, 0.58, 0.26)
    for y in range(res):
        sz = ((y + 0.5) / res - 0.5) * 2.8
        for x in range(res):
            sx = ((x + 0.5) / res - 0.5) * 2.2
            best = second = 9.0
            bs = None
            for s_ in seeds:
                d = (s_[0] - sx) ** 2 + (s_[1] - sz) ** 2
                if d < best:
                    second, best, bs = best, d, s_
                elif d < second:
                    second = d
            f1, f2 = math.sqrt(best), math.sqrt(second)
            edge = f2 - f1
            cid = P._hash(int(bs[0] * 100), int(bs[1] * 100), 7)
            ang = math.atan2(sz - bs[1], sx - bs[0])
            streak = P.fbm(ang * 2.2 + cid * 10, f1 * 4, 3, seed=3)
            rings = 0.5 + 0.5 * math.sin(f1 * 62 + P.fbm(sx * 6, sz * 6, 2, seed=5) * 6)
            grime = P.fbm(sx * 5, sz * 5, 4, seed=11)
            t = P.clamp(0.25 + cid * 0.35 + (streak - 0.5) * 1.1 + (rings - 0.5) * 0.12)
            col = P.ramp([(0.0, dark), (0.45, amber), (1.0, honey)], t)
            if bs[2] == 2:
                col = P.mix(col, dark, 0.35)
            groove = 1 - P.smoothstep(0.0, 0.045, edge)
            col = P.mix(col, (0.05, 0.035, 0.02), groove * 0.85)
            col = P.mix(col, (0.10, 0.12, 0.06), (grime - 0.4) * 0.5 if grime > 0.4 else 0)
            img.set(x, y, col + (1,))
            heights[y * res + x] = -groove * 0.9 + rings * 0.06 + P.clamp(1 - f1 * 1.6) * 0.5 + streak * 0.1
    img.save(os.path.join(out, "shell_albedo.png"), alpha=False)
    P.height_to_normal(heights, res, res, 3.0).save(os.path.join(out, "shell_normal.png"), alpha=False)


def skin_textures(out, res=512):
    heights = [0.0] * (res * res)
    img = P.Image(res, res)
    for y in range(res):
        v = (y + 0.5) / res
        for x in range(res):
            u = (x + 0.5) / res
            f1, f2, cid, _ = P.voronoi(u * 18, v * 18, seed=21, period=18, jitter=0.85)
            edge = f2 - f1
            mott = P.fbm(u * 6, v * 6, 4, seed=4, period=6)
            spot = P.smoothstep(0.62, 0.7, P.fbm(u * 10, v * 10, 3, seed=9, period=10))
            base = P.mix((0.20, 0.25, 0.19), (0.42, 0.45, 0.32), P.clamp(cid * 0.6 + mott * 0.5))
            base = P.mix(base, (0.70, 0.64, 0.42), spot * 0.55)
            base = P.mix(base, (0.07, 0.08, 0.06), 1 - P.smoothstep(0.0, 0.12, edge))
            img.set(x, y, base + (1,))
            heights[y * res + x] = P.smoothstep(0.0, 0.25, edge) * 0.8 + mott * 0.2
    img.save(os.path.join(out, "skin_albedo.png"), alpha=False)
    P.height_to_normal(heights, res, res, 2.2).save(os.path.join(out, "skin_normal.png"), alpha=False)


def plastron_texture(out, res=256):
    seams_v = (0.2, 0.37, 0.55, 0.72, 0.86)

    def fn(u, v, x, y):
        n = P.fbm(u * 8, v * 8, 4, seed=13)
        c = P.mix((0.74, 0.64, 0.42), (0.90, 0.82, 0.60), n)
        d = min([abs(v - s) for s in seams_v] + [abs(u - 0.5) * 1.4])
        c = P.mix(c, (0.35, 0.27, 0.15), 1 - P.smoothstep(0.0, 0.012, d))
        return c + (1,)
    P.render(os.path.join(out, "plastron_albedo.png"), res, res, fn, alpha=False)


def metal_crown_textures(out, res=256):
    tints = {"gold": ((1.0, 0.74, 0.30), (0.78, 0.50, 0.16)),
             "silver": ((0.93, 0.94, 0.97), (0.62, 0.64, 0.70)),
             "jade": ((0.45, 0.85, 0.62), (0.12, 0.42, 0.30))}
    scratches = []
    for k in range(70):
        a = P._hash(k, 1) * math.pi
        scratches.append((P._hash(k, 2), P._hash(k, 3), math.cos(a), math.sin(a), 0.05 + P._hash(k, 4) * 0.2))

    def scratch(u, v):
        s = 0.0
        for cx, cy, dx, dy, ln in scratches:
            px, py = u - cx, v - cy
            along = px * dx + py * dy
            if abs(along) < ln:
                perp = abs(-px * dy + py * dx)
                if perp < 0.0025:
                    s = max(s, 1 - perp / 0.0025)
        return s

    rough_h = []
    for name, (hi, lo) in tints.items():
        def fn(u, v, x, y, hi=hi, lo=lo):
            n = P.fbm(u * 10, v * 10, 4, seed=31, period=10)
            c = P.mix(lo, hi, 0.55 + n * 0.45)
            return P.mix(c, P.mix(c, (1, 1, 1), 0.3), scratch(u, v) * 0.6) + (1,)
        P.render(os.path.join(out, "crown_%s_albedo.png" % name), res, res, fn, alpha=False)

    def rough(u, v, x, y):
        r = 0.18 + P.fbm(u * 14, v * 14, 3, seed=8, period=14) * 0.22 + scratch(u, v) * 0.45
        return (r, r, r, 1)
    P.render(os.path.join(out, "crown_roughness.png"), res, res, rough, alpha=False)


# ----------------------------------------------------------------------------- shaders

VERT = shader("turtle.vert", "Shared vertex stage: world-space varyings + procedural flipper stroke (uSwim).", """
uniform float uTime;
uniform float uSwim;
varying vec3 vWorldPos;
varying vec3 vNormal;
varying vec2 vUv;

void main() {
  vUv = uv;
  vec3 p = position;
  vec3 n = normal;
  // Flippers are the only geometry far from the body axis -> stroke them with a phase lag along the span.
  float span = smoothstep(0.62, 2.1, abs(p.x));
  float front = smoothstep(-0.2, 0.3, p.z);
  float phase = uTime * 1.7 - span * 1.2 + (front > 0.5 ? 0.0 : 2.4);
  float lift = sin(phase) * span * (0.55 * front + 0.22) * uSwim;
  p.y += lift * abs(p.x) * 0.5;
  p.z += cos(phase) * span * 0.12 * uSwim * front;
  // Gentle bob for the whole body.
  p.y += sin(uTime * 0.85) * 0.03 * uSwim;
  vec4 wp = modelMatrix * vec4(p, 1.0);
  vWorldPos = wp.xyz;
  vNormal = normalize(mat3(modelMatrix) * n);
  gl_Position = projectionMatrix * viewMatrix * wp;
}
""", frag=False)

SHELL = shader("shell.frag", "Carapace: wet clear-coat over keratin scutes, wrapped diffuse, thin-edge translucency.", """
uniform sampler2D uAlbedo;
uniform sampler2D uNormalMap;
uniform float uWetness;
varying vec3 vWorldPos;
varying vec3 vNormal;
varying vec2 vUv;

void main() {
  vec3 N = normalize(vNormal);
  if (!gl_FrontFacing) N = -N;
  vec3 mapN = texture2D(uNormalMap, vUv).xyz * 2.0 - 1.0;
  vec3 Nb = perturbNormal(N, vWorldPos, vUv, mapN, 1.0);
  vec3 V = normalize(cameraPosition - vWorldPos);
  vec3 L = normalize(uLightDir);
  vec3 alb = texture2D(uAlbedo, vUv).rgb;

  float wrap = max((dot(Nb, L) + 0.35) / 1.35, 0.0);
  vec3 diffuse = alb * (uLightColor * wrap + envColor(Nb) * 0.32);
  // Translucent keratin: light leaking through thin bright scute areas.
  float lum = dot(alb, vec3(0.333));
  diffuse += alb * vec3(1.0, 0.55, 0.2) * pow(max(dot(-V, L), 0.0), 3.0) * lum * 0.8;

  // Clear-coat uses the *geometric* normal: water film smooths out the grooves.
  vec3 H = normalize(L + V);
  float ndv = max(dot(N, V), 0.0);
  float fres = 0.04 + 0.96 * pow(1.0 - ndv, 5.0);
  float coat = pow(max(dot(N, H), 0.0), 260.0) * 1.4 * uWetness;
  vec3 refl = envColor(reflect(-V, N)) * fres * uWetness;
  float base = pow(max(dot(Nb, H), 0.0), 14.0) * 0.06;
  vec3 col = diffuse + uLightColor * (coat + base) * max(dot(N, L), 0.0) + refl * 0.7;
  gl_FragColor = vec4(tonemap(col), 1.0);
}
""")

SKIN = shader("skin.frag", "Scaled reptile skin: wrap lighting, scale sheen, warm subsurface rim.", """
uniform sampler2D uAlbedo;
uniform sampler2D uNormalMap;
uniform float uTiling;
uniform vec3  uTint;
varying vec3 vWorldPos;
varying vec3 vNormal;
varying vec2 vUv;

void main() {
  vec2 uv = vUv * uTiling;
  vec3 N = normalize(vNormal);
  if (!gl_FrontFacing) N = -N;
  vec3 Nb = perturbNormal(N, vWorldPos, uv, texture2D(uNormalMap, uv).xyz * 2.0 - 1.0, 1.2);
  vec3 V = normalize(cameraPosition - vWorldPos);
  vec3 L = normalize(uLightDir);
  vec3 alb = texture2D(uAlbedo, uv).rgb * uTint;
  float ndv = max(dot(N, V), 0.0);

  float wrap = max((dot(Nb, L) + 0.5) / 1.5, 0.0);
  vec3 col = alb * (uLightColor * wrap * 0.95 + envColor(Nb) * 0.38);
  col += alb * vec3(0.9, 0.42, 0.25) * pow(1.0 - ndv, 2.5) * 0.45;              // subsurface rim
  vec3 H = normalize(L + V);
  col += uLightColor * pow(max(dot(Nb, H), 0.0), 36.0) * 0.18;                    // scale sheen
  col += envColor(reflect(-V, Nb)) * pow(1.0 - ndv, 5.0) * 0.25;
  gl_FragColor = vec4(tonemap(col), 1.0);
}
""")

CROWN = shader("crown_metal.frag", "Polished metal crown: roughness-blended environment reflections + animated glints.", """
uniform sampler2D uAlbedo;
uniform sampler2D uRoughness;
varying vec3 vWorldPos;
varying vec3 vNormal;
varying vec2 vUv;

void main() {
  vec3 N = normalize(vNormal);
  if (!gl_FrontFacing) N = -N;
  vec3 V = normalize(cameraPosition - vWorldPos);
  vec3 L = normalize(uLightDir);
  vec3 F0 = texture2D(uAlbedo, vUv).rgb;
  float r = texture2D(uRoughness, vUv).r;
  float ndv = max(dot(N, V), 0.0);
  vec3 F = F0 + (1.0 - F0) * pow(1.0 - ndv, 5.0);

  vec3 R = reflect(-V, N);
  vec3 sharp = envColor(R);
  vec3 blurry = (envColor(normalize(R + N * 0.6)) + envColor(N)) * 0.5;
  vec3 env = mix(sharp, blurry, smoothstep(0.1, 0.7, r));
  vec3 H = normalize(L + V);
  float gloss = mix(400.0, 20.0, r);
  float spec = pow(max(dot(N, H), 0.0), gloss) * (gloss + 8.0) / 25.0;
  vec3 col = F * env + F * uLightColor * spec * max(dot(N, L), 0.0);

  // Glints: sparse cells that twinkle when they face the light.
  float g = hash13(floor(vWorldPos * 260.0) + floor(uTime * 3.0));
  col += vec3(1.0, 0.92, 0.7) * step(0.985, g) * pow(max(dot(N, H), 0.0), 8.0) * 4.0;
  gl_FragColor = vec4(tonemap(col), 1.0);
}
""")

GEM = shader("gem.frag", "Cut gemstone: faceted derivative normals, fake refraction, pulsing inner fire.", """
uniform vec3  uGemColor;
uniform float uGlow;
varying vec3 vWorldPos;
varying vec3 vNormal;
varying vec2 vUv;

void main() {
  vec3 N = normalize(cross(dFdx(vWorldPos), dFdy(vWorldPos)));               // faceted look
  vec3 V = normalize(cameraPosition - vWorldPos);
  if (dot(N, V) < 0.0) N = -N;
  float ndv = max(dot(N, V), 0.0);
  float fres = 0.06 + 0.94 * pow(1.0 - ndv, 4.0);
  vec3 refr = envColor(refract(-V, N, 0.58)) * uGemColor * 1.3;
  vec3 refl = envColor(reflect(-V, N));
  float fire = 0.6 + 0.4 * sin(uTime * 2.3 + dot(vWorldPos, vec3(31.0, 17.0, 23.0)));
  vec3 col = mix(refr, refl, fres) + uGemColor * uGlow * fire;
  gl_FragColor = vec4(tonemap(col), 1.0);
}
""")


# ----------------------------------------------------------------------------- bundle

def generate(out, spec=None):
    for d in ("meshes", "materials", "textures", "shaders"):
        os.makedirs(os.path.join(out, d), exist_ok=True)
    tex = os.path.join(out, "textures")
    shell_textures(tex)
    skin_textures(tex)
    plastron_texture(tex)
    metal_crown_textures(tex)

    shaders = {"turtle.vert": VERT, "shell.frag": SHELL, "skin.frag": SKIN, "crown_metal.frag": CROWN, "gem.frag": GEM}
    for n, src in shaders.items():
        with open(os.path.join(out, "shaders", n), "w") as f:
            f.write(src)

    mtl = {
        "shell": {"Kd": (0.5, 0.33, 0.14), "Ks": (0.3, 0.3, 0.3), "Ns": 80, "map_Kd": "../textures/shell_albedo.png",
                  "map_Bump": "../textures/shell_normal.png"},
        "plastron": {"Kd": (0.82, 0.74, 0.52), "Ks": (0.1, 0.1, 0.1), "Ns": 20, "map_Kd": "../textures/plastron_albedo.png"},
        "skin": {"Kd": (0.35, 0.38, 0.28), "Ks": (0.15, 0.15, 0.15), "Ns": 30, "map_Kd": "../textures/skin_albedo.png",
                 "map_Bump": "../textures/skin_normal.png"},
        "crown": {"Kd": (1.0, 0.76, 0.33), "Ks": (1, 0.9, 0.6), "Ns": 300, "map_Kd": "../textures/crown_gold_albedo.png"},
        "gem": {"Kd": (0.8, 0.05, 0.12), "Ks": (1, 1, 1), "Ns": 500},
        "eye": {"Kd": (0.02, 0.02, 0.02), "Ks": (1, 1, 1), "Ns": 400},
    }
    M.write_mtl(os.path.join(out, "materials", "sea_turtle.mtl"), mtl)

    lods = []
    for i, q in enumerate((1.0, 0.5, 0.25)):
        parts = build_turtle(q)
        tris = sum(p.tri_count for p in parts)
        verts = sum(len(p.pos) for p in parts)
        if i == 0:
            assert tris <= BUDGET, "LOD0 over budget: %d" % tris
            hero = parts
        name = "meshes/sea_turtle_lod%d.obj" % i
        M.write_obj(os.path.join(out, name), parts, "../materials/sea_turtle.mtl",
                    "Sea turtle with golden crown - LOD%d\n%d triangles / %d vertices (budget %d)" % (i, tris, verts, BUDGET))
        lods.append({"path": name, "triangles": tris, "vertices": verts})

    per_part = {}
    for p in hero:
        key = p.name.rstrip("0123456789_lr").rstrip("_") or p.name
        per_part[key] = per_part.get(key, 0) + p.tri_count
    lo, hi = zip(*(p.bounds() for p in hero))
    bmin = [min(b[k] for b in lo) for k in range(3)]
    bmax = [max(b[k] for b in hi) for k in range(3)]

    gltf_mats = {"shell": {"color": (0.5, 0.33, 0.14), "roughness": 0.35}, "plastron": {"color": (0.82, 0.74, 0.52)},
                 "skin": {"color": (0.35, 0.38, 0.28), "roughness": 0.7},
                 "crown": {"color": (1.0, 0.76, 0.33), "metallic": 1.0, "roughness": 0.25},
                 "gem": {"color": (0.8, 0.05, 0.12), "roughness": 0.05, "emissive": (0.4, 0.0, 0.05)},
                 "eye": {"color": (0.02, 0.02, 0.02), "roughness": 0.05}}
    M.write_gltf(os.path.join(out, "meshes", "sea_turtle_lod0.gltf"), hero, gltf_mats)

    T = "textures/"
    sh = lambda frag, maps, uniforms, pbr: {"vert": "shaders/turtle.vert", "frag": "shaders/" + frag,
                                            "maps": maps, "uniforms": uniforms, "pbr": pbr}
    render = {
        "type": "object",
        "mesh": lods[0]["path"],
        "camera": {"position": [3.4, 2.1, 3.9], "target": [0, 0.15, 0.25], "fov": 35},
        "light": {"dir": [0.55, 0.85, 0.4], "color": [1.15, 1.08, 1.0]},
        "uniforms": {"uSwim": 1.0, "uExposure": 1.0},
        "materials": {
            "shell": sh("shell.frag", {"uAlbedo": T + "shell_albedo.png", "uNormalMap": T + "shell_normal.png"},
                        {"uWetness": 0.85}, {"map": T + "shell_albedo.png", "normalMap": T + "shell_normal.png", "roughness": 0.35}),
            "plastron": sh("skin.frag", {"uAlbedo": T + "plastron_albedo.png", "uNormalMap": T + "skin_normal.png"},
                           {"uTiling": 1.0, "uTint": [1, 1, 1]}, {"map": T + "plastron_albedo.png", "roughness": 0.6}),
            "skin": sh("skin.frag", {"uAlbedo": T + "skin_albedo.png", "uNormalMap": T + "skin_normal.png"},
                       {"uTiling": 2.0, "uTint": [1, 1, 1]}, {"map": T + "skin_albedo.png", "normalMap": T + "skin_normal.png", "roughness": 0.7}),
            "crown": sh("crown_metal.frag", {"uAlbedo": T + "crown_gold_albedo.png", "uRoughness": T + "crown_roughness.png"},
                        {}, {"map": T + "crown_gold_albedo.png", "roughnessMap": T + "crown_roughness.png", "metalness": 1.0, "roughness": 1.0}),
            "gem": sh("gem.frag", {}, {"uGemColor": [0.95, 0.06, 0.18], "uGlow": 0.35}, {"color": [0.9, 0.05, 0.15], "roughness": 0.05, "emissive": [0.3, 0, 0.05]}),
            "eye": sh("gem.frag", {}, {"uGemColor": [0.03, 0.03, 0.04], "uGlow": 0.0}, {"color": [0.02, 0.02, 0.02], "roughness": 0.05}),
        },
    }
    variants = [
        {"id": "royal-gold", "name": "Royal Gold", "group": "Crown", "default": True, "swatch": "#f5b942", "patch": {}},
        {"id": "moon-silver", "name": "Moon Silver", "group": "Crown", "swatch": "#d9dde6",
         "patch": {"materials.crown.maps.uAlbedo": T + "crown_silver_albedo.png", "materials.crown.pbr.map": T + "crown_silver_albedo.png",
                   "materials.gem.uniforms.uGemColor": [0.15, 0.45, 1.0]}},
        {"id": "jade-empress", "name": "Jade Empress", "group": "Crown", "swatch": "#4fd18b",
         "patch": {"materials.crown.maps.uAlbedo": T + "crown_jade_albedo.png", "materials.crown.pbr.map": T + "crown_jade_albedo.png",
                   "materials.gem.uniforms.uGemColor": [1.0, 0.75, 0.1]}},
        {"id": "lod0", "name": "LOD0 · %s tris" % format(lods[0]["triangles"], ","), "group": "Detail", "default": True, "patch": {}},
        {"id": "lod1", "name": "LOD1 · %s tris" % format(lods[1]["triangles"], ","), "group": "Detail", "patch": {"mesh": lods[1]["path"]}},
        {"id": "lod2", "name": "LOD2 · %s tris" % format(lods[2]["triangles"], ","), "group": "Detail", "patch": {"mesh": lods[2]["path"]}},
    ]

    files = [{"path": l["path"], "kind": "mesh", "role": "LOD%d mesh" % i, "meta": {"triangles": l["triangles"], "vertices": l["vertices"]},
              "depends": ["materials/sea_turtle.mtl"], "variant": None if i == 0 else "lod%d" % i} for i, l in enumerate(lods)]
    files.append({"path": "meshes/sea_turtle_lod0.gltf", "kind": "mesh", "role": "glTF 2.0 export", "meta": {"triangles": lods[0]["triangles"]}})
    files.append({"path": "materials/sea_turtle.mtl", "kind": "material", "role": "Wavefront material library",
                  "depends": [T + "shell_albedo.png", T + "shell_normal.png", T + "skin_albedo.png", T + "skin_normal.png",
                              T + "plastron_albedo.png", T + "crown_gold_albedo.png"]})
    tex_roles = {"shell_albedo.png": ("albedo", 512), "shell_normal.png": ("normal", 512), "skin_albedo.png": ("albedo", 512),
                 "skin_normal.png": ("normal", 512), "plastron_albedo.png": ("albedo", 256), "crown_gold_albedo.png": ("albedo", 256),
                 "crown_silver_albedo.png": ("albedo variant", 256), "crown_jade_albedo.png": ("albedo variant", 256),
                 "crown_roughness.png": ("roughness", 256)}
    for n, (role, r) in tex_roles.items():
        files.append({"path": T + n, "kind": "texture", "role": role, "meta": {"width": r, "height": r},
                      "variant": "moon-silver" if "silver" in n else "jade-empress" if "jade" in n else None})
    users = {"shell.frag": ["shell_albedo.png", "shell_normal.png"], "skin.frag": ["skin_albedo.png", "skin_normal.png", "plastron_albedo.png"],
             "crown_metal.frag": ["crown_gold_albedo.png", "crown_roughness.png", "crown_silver_albedo.png", "crown_jade_albedo.png"], "gem.frag": []}
    files.append({"path": "shaders/turtle.vert", "kind": "shader", "role": "vertex · swim stroke", "meta": {"stage": "vertex"},
                  "depends": [l["path"] for l in lods]})
    for n, deps in users.items():
        files.append({"path": "shaders/" + n, "kind": "shader", "role": "fragment", "meta": {"stage": "fragment"},
                      "depends": ["shaders/turtle.vert"] + [T + d for d in deps]})

    return {
        "kind": "object",
        "files": files,
        "render": render,
        "variants": variants,
        "stats": {"triangles": lods[0]["triangles"], "vertices": lods[0]["vertices"], "budget": BUDGET,
                  "budget_used": round(lods[0]["triangles"] / BUDGET * 100, 1), "parts": len(hero), "materials": len(mtl),
                  "textures": len(tex_roles), "shaders": len(shaders), "lods": len(lods), "per_part": per_part,
                  "bounds": {"min": [round(c, 3) for c in bmin], "max": [round(c, 3) for c in bmax]}},
        "pipeline": [{"stage": s, "state": "done", "note": n} for s, n in [
            ("Interpret prompt", "object · sea turtle · ≤15k polys · golden crown"),
            ("Blockout primitives", "carapace dome, plastron, head, neck, 4 flippers, tail"),
            ("Sculpt & deform", "vertebral ridge, serrated marginals, hooked beak, swept flippers"),
            ("Polygon budget pass", "%d / %d triangles" % (lods[0]["triangles"], BUDGET)),
            ("UV layout", "planar shell projection, spherical skin"),
            ("Texture synthesis", "scute voronoi, scale voronoi, plastron seams, brushed gold"),
            ("Normal & roughness bake", "height → tangent normals; scratch roughness"),
            ("Shader authoring", "5 GLSL programs incl. swim vertex stroke"),
            ("Material binding", "6 materials, MTL + manifest"),
            ("LOD chain", " → ".join(format(l["triangles"], ",") for l in lods)),
            ("Variants", "gold / silver / jade crowns"),
            ("Preview render", "rendered in-browser on first view"),
            ("Package bundle", "manifest.json + glTF export")]],
    }
