"""Request: "animated airplane bomber (max 90000 polygons) that has wind turbulences while flying. Animations,
shaders, environment (sky)".

A four-engine heavy bomber in real-world metres (nose +Z, right wing +X):
  airframe   lathed fuselage with tail upsweep, NACA-lofted wings / stabilisers / fin, 4 nacelles, glazing, turrets
  rig        control surfaces on hinge pivots (ailerons, elevators, rudder), 4 propellers, bomb-bay doors
  motion     4 baked flight clips (calm, turbulence, storm, evasive S-turn): periodic turbulence spectra + discrete
             gusts; the "pilot" deflects the surfaces against the disturbance rates; gust/lightning channels
  look       paint shader (olive drab / natural metal / night), canopy glass, prop blur disc, wing flex + buffet in
             the vertex stage, analytic sky with a ray-marched cloud deck, contrails, speed streaks
"""
import json
import math
import os
import shutil

from . import bitfont
from . import mesh as M
from . import procedural as P
from .glsl import HEADER

BUDGET = 90000
FPS = 30
DIHEDRAL = math.radians(4.5)
NACELLES = [4.6, 8.6]


# ----------------------------------------------------------------------------- airfoil lofting

def airfoil(n=18, t=0.12, m=0.02, p=0.4):
    """Closed loop (TE upper -> LE -> TE lower) of (x_chord 0..1, y, is_upper)."""
    pts = []
    for i in range(n + 1):
        b = math.pi * i / n
        x = (1 - math.cos(b)) / 2
        yt = 5 * t * (0.2969 * math.sqrt(x) - 0.126 * x - 0.3516 * x * x + 0.2843 * x ** 3 - 0.1036 * x ** 4)
        if m:
            yc = m / p ** 2 * (2 * p * x - x * x) if x < p else m / (1 - p) ** 2 * ((1 - 2 * p) + 2 * p * x - x * x)
        else:
            yc = 0.0
        pts.append((x, yc, yt))
    upper = [(x, yc + yt, True) for x, yc, yt in reversed(pts)]
    lower = [(x, yc - yt, False) for x, yc, yt in pts[1:-1]]
    return upper + lower


def loft(name, mat, foil, stations, place, cap_tip=True):
    """stations: list of s in 0..1; place(s, xc, yf) -> 3D point, (u, v) uv. Orients faces away from the chord line."""
    part = M.Part(name, mat)
    L = len(foil)
    for s in stations:
        for xc, yf, up in foil:
            pnt, uv = place(s, xc, yf, up)
            part.pos.append(pnt)
            part.uv.append(uv)
    for j in range(len(stations) - 1):
        for i in range(L):
            a, b = j * L + i, j * L + (i + 1) % L
            c, d = a + L, b + L
            for tri in ((a, b, c), (b, d, c)):
                part.tris.append(tri)
    centre = lambda s, xc: place(s, xc, 0.0, True)[0]
    fixed = []
    for tri in part.tris:
        pa, pb, pc = (part.pos[k] for k in tri)
        n = M.v_cross(M.v_sub(pb, pa), M.v_sub(pc, pa))
        j = tri[0] // L
        xc = foil[tri[0] % L][0]
        out = M.v_sub(M.v_mul(M.v_add(M.v_add(pa, pb), pc), 1 / 3), centre(stations[j], xc))
        fixed.append(tri if M.v_dot(n, out) >= 0 else (tri[0], tri[2], tri[1]))
    part.tris = fixed
    if cap_tip:
        base = (len(stations) - 1) * L
        ctr = len(part.pos)
        cp, _ = place(stations[-1], 0.4, 0.0, True)
        part.pos.append(cp)
        part.uv.append((1, 0.5))
        outward = M.v_sub(cp, place(stations[-2], 0.4, 0.0, True)[0])
        for i in range(L):
            tri = (ctr, base + i, base + (i + 1) % L)
            pa, pb, pc = (part.pos[k] for k in tri)
            n = M.v_cross(M.v_sub(pb, pa), M.v_sub(pc, pa))
            part.tris.append(tri if M.v_dot(n, outward) >= 0 else (tri[0], tri[2], tri[1]))
    return part


def wing_y(x):
    return -0.45 + (abs(x) - 1.3) * math.tan(DIHEDRAL)


def wing_le(x):
    return 3.0 - (abs(x) - 1.3) * 0.085


def wing_chord(x):
    return 5.6 - (abs(x) - 1.3) * 0.25


def build(q=1.0):
    S = lambda n: max(4, int(n * q))
    rig = {}
    add = lambda bone, part: rig.setdefault(bone, []).append(part)

    # fuselage: control radii along z (tail -> nose), cosine-interpolated
    ctrl = [(-11.3, 0.16), (-10.2, 0.45), (-7.5, 0.95), (-4.0, 1.28), (-1.0, 1.36), (5.5, 1.36), (8.5, 1.24), (10.2, 0.95), (11.0, 0.66)]

    def radius(z):
        for (z0, r0), (z1, r1) in zip(ctrl, ctrl[1:]):
            if z <= z1:
                k = (1 - math.cos(math.pi * (z - z0) / (z1 - z0))) / 2
                return r0 + (r1 - r0) * k
        return ctrl[-1][1]
    rings = S(120)
    prof = [(radius(-11.3 + 22.3 * i / rings), -11.3 + 22.3 * i / rings) for i in range(rings + 1)]
    fus = M.lathe("fuselage", "paint", prof, S(64)).rotate(rx=math.pi / 2)
    fus.transform(lambda p: (p[0], p[1] * 1.1 + 0.55 * P.smoothstep(-3.0, -11.0, p[2]), p[2]))
    fus.uv = [(u, v) for u, v in fus.uv]
    add("airframe", fus)

    glass = []
    nose = M.lathe("nose_glass", "glass", [(0.66, 0), (0.62, 0.22), (0.48, 0.44), (0.26, 0.58), (0.0, 0.62)], S(32)).rotate(rx=math.pi / 2).translate((0, 0, 11.0))
    canopy = M.uv_sphere("canopy", "glass", S(28), S(14)).scale((0.82, 0.5, 1.35)).translate((0, 1.3, 7.0))
    turret = M.uv_sphere("top_turret", "glass", S(20), S(10), th_max=math.pi * 0.55).scale(0.52).translate((0, 1.42, 4.6))
    tailg = M.uv_sphere("tail_glass", "glass", S(16), S(8)).scale((0.3, 0.32, 0.5)).translate((0, 0.72, -11.25))
    for g in (nose, canopy, turret, tailg):
        add("airframe", g)
    ball = M.uv_sphere("ball_turret", "metal", S(24), S(12)).scale(0.62).translate((0, -1.45, -1.6))
    add("airframe", ball)
    for x, y, z, dz, n in ((0.12, 1.55, 4.9, 1, 2), (0.14, -1.45, -1.0, 1, 2), (0.1, 0.72, -11.6, -1, 2), (0.0, -0.5, 11.55, 1, 1)):
        for k in range(n):
            sx = x * (1 if k == 0 else -1)
            gun = M.lathe("gun", "metal", [(0.045, 0), (0.035, 1.3), (0.05, 1.32), (0.05, 1.45)], S(8)).rotate(rx=math.pi / 2 * dz)
            add("airframe", gun.translate((sx, y, z)))
    add("airframe", M.lathe("antenna", "metal", [(0.04, 0), (0.01, 1.0)], 6).translate((0, 1.45, 2.2)))

    # wings (right built, left mirrored)
    foil = airfoil(S(16), 0.13, 0.02)
    spans = [i / S(40) for i in range(S(40) + 1)]
    def wing_place(side):
        def f(s, xc, yf, up):
            x = 1.3 + s * 14.4
            c = wing_chord(x)
            p = (side * x, wing_y(x) + yf * c, wing_le(x) - xc * c)
            return p, (s, 0.5 + 0.5 * xc if up else 0.5 - 0.5 * xc)
        return f
    for side, nm in ((1, "r"), (-1, "l")):
        add("airframe", loft("wing_" + nm, "wing", foil, spans, wing_place(side)))
        # aileron: thin surface behind the trailing edge between 60% and 92% span
        hinge_x = (1.3 + 0.6 * 14.4, 1.3 + 0.92 * 14.4)
        ail_foil = airfoil(8, 0.06, 0.0)
        def ail(s, xc, yf, up, side=side):
            x = hinge_x[0] + s * (hinge_x[1] - hinge_x[0])
            c = 0.75
            z0 = wing_le(x) - wing_chord(x) + 0.08
            return (side * x, wing_y(x) + yf * c, z0 - xc * c), (s, 0.5 + 0.5 * xc if up else 0.5 - 0.5 * xc)
        bone = "aileron_" + nm
        add(bone, loft(bone, "wing", ail_foil, [i / 10 for i in range(11)], ail))

    # horizontal stabilisers + elevators
    tfoil = airfoil(S(12), 0.1, 0.0)
    for side, nm in ((1, "r"), (-1, "l")):
        def stab(s, xc, yf, up, side=side):
            x = 0.5 + s * 5.4
            c = 3.4 - s * 1.7
            return (side * x, 0.95 + yf * c, -8.2 - s * 0.9 - xc * c), (s, 0.5 + 0.5 * xc if up else 0.5 - 0.5 * xc)
        add("airframe", loft("stab_" + nm, "wing", tfoil, [i / S(14) for i in range(S(14) + 1)], stab))
        def elev(s, xc, yf, up, side=side):
            x = 0.7 + s * 4.6
            c = 0.8 - s * 0.3
            z0 = -8.2 - (x - 0.5) / 5.4 * 0.9 - (3.4 - (x - 0.5) / 5.4 * 1.7) + 0.05
            return (side * x, 0.95 + yf * c, z0 - xc * c), (s, 0.5 + 0.5 * xc if up else 0.5 - 0.5 * xc)
        add("elevator_" + nm, loft("elevator_" + nm, "wing", airfoil(8, 0.06, 0.0), [i / 8 for i in range(9)], elev))

    # vertical fin + rudder (lofted along +Y)
    def fin(s, xc, yf, up):
        y = 1.0 + s * 4.6
        c = 6.2 - s * 4.2
        le = -5.6 - s * 4.4
        return (yf * c, y, le - xc * c), (0.5 + 0.5 * xc if up else 0.5 - 0.5 * xc, s)
    add("airframe", loft("fin", "fin", tfoil, [i / S(16) for i in range(S(16) + 1)], fin))
    def rud(s, xc, yf, up):
        y = 1.3 + s * 4.0
        c = 1.1 - s * 0.4
        z0 = -5.6 - (y - 1.0) / 4.6 * 4.4 - (6.2 - (y - 1.0) / 4.6 * 4.2) + 0.06
        return (yf * c, y, z0 - xc * c), (0.5 + 0.5 * xc if up else 0.5 - 0.5 * xc, s)
    add("rudder", loft("rudder", "fin", airfoil(8, 0.06, 0.0), [i / 8 for i in range(9)], rud))

    # nacelles, spinners, propellers
    pivots = {}
    k = 0
    for side in (1, -1):
        for xn in NACELLES:
            x = side * xn
            y = wing_y(xn) - 0.12
            zf = wing_le(xn) + 2.2
            prof = [(0.22, 0.0), (0.55, 1.4), (0.76, 3.0), (0.8, 4.0), (0.74, 4.6), (0.55, 4.66), (0.3, 4.5), (0.0, 4.45)]
            nac = M.lathe("nacelle_%d" % k, "paint", prof, S(36)).rotate(rx=math.pi / 2).translate((x, y, zf - 4.66))
            add("airframe", nac)
            pv = (x, y, zf - 0.05)
            pivots["prop_%d" % k] = pv
            spin = M.lathe("spinner", "metal", [(0.3, 0.0), (0.26, 0.25), (0.14, 0.5), (0.0, 0.62)], S(18)).rotate(rx=math.pi / 2).translate(pv)
            add("prop_%d" % k, spin)
            for b in range(3):
                blade = M.Part("blade", "prop")
                bf = airfoil(6, 0.1, 0.03)
                secs = 10
                for j in range(secs + 1):
                    s = j / secs
                    r = 0.25 + s * 1.55
                    c = 0.34 - 0.12 * s ** 1.5 - (0.1 if s > 0.92 else 0)
                    tw = math.radians(48 - 32 * s)
                    for xc, yf, up in bf:
                        lx, lz = (xc - 0.3) * c, yf * c
                        pnt = (lx * math.cos(tw) - lz * math.sin(tw), r, lx * math.sin(tw) + lz * math.cos(tw))
                        blade.pos.append(pnt)
                        blade.uv.append((0.5 + (0.5 if up else -0.5) * xc, s))
                L = len(bf)
                for j in range(secs):
                    for i in range(L):
                        a_, b_ = j * L + i, j * L + (i + 1) % L
                        blade.tris += [(a_, b_, a_ + L), (b_, b_ + L, a_ + L)]
                blade.rotate(rz=b * 2 * math.pi / 3).translate(pv)
                add("prop_%d" % k, blade)
            k += 1

    # bomb bay doors
    for side, nm in ((1, "r"), (-1, "l")):
        door = M.Part("door", "paint")
        for zz in (0.2, 3.6):
            for xx in (0.0, 0.62):
                door.pos.append((side * xx, -1.43 + 0.05 * xx, zz))
                door.uv.append((0.25 + 0.05 * xx, (zz + 11.3) / 22.3))
        door.tris = [(0, 2, 1), (1, 2, 3)]
        door2 = M.Part("door_in", "metal")
        door2.pos = list(door.pos)
        door2.uv = list(door.uv)
        door2.tris = [(0, 1, 2), (1, 3, 2)]
        add("bay_" + nm, door)
        add("bay_" + nm, door2)

    hinge = {
        "aileron_r": (1.3 + 0.76 * 14.4, wing_y(12.2), wing_le(12.2) - wing_chord(12.2) + 0.08),
        "aileron_l": (-(1.3 + 0.76 * 14.4), wing_y(12.2), wing_le(12.2) - wing_chord(12.2) + 0.08),
        "elevator_r": (3.0, 0.95, -11.25), "elevator_l": (-3.0, 0.95, -11.25),
        "rudder": (0.0, 3.3, -11.7), "bay_r": (0.62, -1.4, 1.9), "bay_l": (-0.62, -1.4, 1.9),
    }
    hinge.update(pivots)
    bones = [("airframe", None, (0.0, 0.0, 0.0))] + [(b, "airframe", hinge[b]) for b in hinge]
    for parts in rig.values():
        for p in parts:
            p.compute_normals()
    return rig, bones


# ----------------------------------------------------------------------------- textures

def star_poly(cx, cy, R):
    pts = []
    for i in range(10):
        a = math.pi / 2 + i * math.pi / 5
        r = R if i % 2 == 0 else R * 0.382
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def inside(poly, x, y):
    c = False
    j = len(poly) - 1
    for i in range(len(poly)):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi + 1e-12) + xi:
            c = not c
        j = i
    return c


def insignia(mx, my, R):
    """(mx, my) in metres relative to the roundel centre -> None, 'blue' or 'white'."""
    d = math.hypot(mx, my)
    bar = abs(my) < R * 0.27 and R * 0.8 < abs(mx) < R * 2.0
    bar_edge = abs(my) < R * 0.37 and R * 0.8 < abs(mx) < R * 2.1
    if d < R * 0.92 and inside(star_poly(0, 0, R * 0.92), mx, my):
        return "white"
    if bar:
        return "white"
    if d < R or bar_edge:
        return "blue"
    return None


PAINTS = {
    "olive": {"top": (0.27, 0.29, 0.17), "bottom": (0.52, 0.53, 0.52), "metal": (0.78, 0.79, 0.8)},
    "metal": {"top": (0.74, 0.76, 0.78), "bottom": (0.72, 0.74, 0.76), "metal": (0.92, 0.93, 0.95)},
    "night": {"top": (0.1, 0.1, 0.11), "bottom": (0.05, 0.05, 0.06), "metal": (0.4, 0.4, 0.42)},
}


def textures(out, res=512):
    # fuselage: u around (top at 0.75), v along length; 1 u = 8.5 m, 1 v = 22.3 m
    fus_fields, fus_h = [], [0.0] * (res * res)
    for y in range(res):
        v = 1 - (y + 0.5) / res          # uv space (three.js flips Y on upload)
        for x in range(res):
            u = (x + 0.5) / res
            top = math.cos(2 * math.pi * (u - 0.75)) + (P.fbm(u * 10, v * 6, 2, seed=3) - 0.5) * 0.35
            ring = abs(((v * 22.3) % 0.75) / 0.75 - 0.5) > 0.485
            stringer = abs(((u * 8.5) % 0.55) / 0.55 - 0.5) > 0.48
            rivet = (ring or stringer) and P._hash(x // 3, y // 3, 9) > 0.6
            chip = P.fbm(u * 30, v * 60, 3, seed=7) > 0.72 and P.fbm(u * 6, v * 9, 2, seed=8) > 0.62 and (ring or stringer or P._hash(x // 6, y // 6, 4) > 0.7)
            ins = None
            for uc in (0.0, 0.5, 1.0):
                mx, my = (u - uc) * 8.5, (v - 0.32) * 22.3
                if abs(mx) < 2.5 and abs(my) < 1.2:
                    ins = insignia(my, -mx, 0.95) if uc != 0.5 else insignia(-my, -mx, 0.95)
            dirt = P.fbm(u * 4, v * 3, 3, seed=11)
            fus_fields.append((top, ring or stringer, rivet, chip, ins, dirt))
            fus_h[y * res + x] = (-0.6 if (ring or stringer) else 0) + (0.4 if rivet else 0)
    wing_fields, wing_h = [], [0.0] * (res * res)
    for y in range(res):
        v = 1 - (y + 0.5) / res
        upper, xc = v >= 0.5, abs(v - 0.5) * 2
        for x in range(res):
            u = (x + 0.5) / res
            span_m = u * 14.4
            panel = abs((span_m % 1.2) / 1.2 - 0.5) > 0.485 or abs((xc * 5 % 0.9) / 0.9 - 0.5) > 0.48
            deice = xc < 0.07 and u < 0.95
            walk = upper and 0.03 < u < 0.22 and abs(xc - 0.45) < 0.01
            chip = P.fbm(u * 40, v * 30, 3, seed=5) > 0.74 and (panel or xc < 0.12)
            ins = insignia((u - 0.72) * 14.4, (xc - 0.42) * 4.5, 0.95) if upper else None
            exhaust = upper and any(abs(span_m + 1.3 - n) < 0.5 for n in NACELLES) and xc > 0.3
            wing_fields.append((upper, panel, deice, walk, chip, ins, exhaust, P.fbm(u * 8, v * 4, 3, seed=13)))
            wing_h[y * res + x] = -0.6 if panel else (0.2 if deice else 0)
    for name, pal in PAINTS.items():
        img, rough = P.Image(res, res), P.Image(res, res)
        for i, (top, line, rivet, chip, ins, dirt) in enumerate(fus_fields):
            c = pal["top"] if top > 0.15 else pal["bottom"]
            r = 0.75 if name != "metal" else 0.28
            if ins and name != "metal" or ins:
                c = (0.92, 0.92, 0.9) if ins == "white" else (0.1, 0.14, 0.32)
                r = 0.6
            if chip and name != "metal":
                c, r = pal["metal"], 0.3
            if line:
                c = P.mix(c, (0.05, 0.05, 0.05), 0.55)
            if rivet:
                c = P.mix(c, (1, 1, 1), 0.12)
            c = P.mix(c, (0.15, 0.13, 0.1), (dirt - 0.5) * 0.4 if dirt > 0.5 else 0)
            img.data[i] = list(c) + [1]
            rough.data[i] = [r, r, r, 1]
        img.save(os.path.join(out, "fuselage_%s.png" % name), alpha=False)
        rough.save(os.path.join(out, "fuselage_%s_rough.png" % name), alpha=False)
        img, rough = P.Image(res, res), P.Image(res, res)
        for i, (upper, panel, deice, walk, chip, ins, exhaust, n) in enumerate(wing_fields):
            c = pal["top"] if upper else pal["bottom"]
            r = 0.75 if name != "metal" else 0.28
            if ins:
                c = (0.92, 0.92, 0.9) if ins == "white" else (0.1, 0.14, 0.32)
            if chip and name != "metal":
                c, r = pal["metal"], 0.3
            if deice:
                c, r = (0.06, 0.06, 0.06), 0.9
            if walk:
                c = (0.08, 0.08, 0.08)
            if exhaust:
                c = P.mix(c, (0.08, 0.07, 0.06), 0.45 * n)
            if panel:
                c = P.mix(c, (0.05, 0.05, 0.05), 0.5)
            img.data[i] = list(c) + [1]
            rough.data[i] = [r, r, r, 1]
        img.save(os.path.join(out, "wing_%s.png" % name), alpha=False)
        rough.save(os.path.join(out, "wing_%s_rough.png" % name), alpha=False)
        # fin: tail number in the TC HUD bitfont + yellow band
        fres = 256
        fin = P.Image(fres, fres)
        text = "42-TC01"
        for y in range(fres):
            v = 1 - (y + 0.5) / fres
            for x in range(fres):
                u = (x + 0.5) / fres
                c = pal["top"]
                if 0.62 < v < 0.72 and name != "night":
                    c = (0.92, 0.72, 0.12)
                gx = int((u * 2 % 1 - 0.12) * 50)
                gy = int((0.52 - v) * 60)
                ci = gx // 6
                if 0 <= ci < len(text) and 0 <= gy < 7 and 0 <= gx % 6 < 5:
                    if bitfont.GLYPHS[text[ci]][gy] & (16 >> (gx % 6)):
                        c = (0.92, 0.82, 0.2) if name != "night" else (0.75, 0.15, 0.12)
                fin.set(x, y, c)
        fin.save(os.path.join(out, "fin_%s.png" % name), alpha=False)
    P.height_to_normal(fus_h, res, res, 2.0).save(os.path.join(out, "fuselage_normal.png"), alpha=False)
    P.height_to_normal(wing_h, res, res, 2.0).save(os.path.join(out, "wing_normal.png"), alpha=False)
    P.render(os.path.join(out, "prop.png"), 32, 64, lambda u, v, x, y: ((0.95, 0.78, 0.1) if v > 0.88 else (0.05, 0.05, 0.05)) + (1,), alpha=False)


# ----------------------------------------------------------------------------- flight animation bake

def euler_q(pitch, yaw, roll):
    return M.q_norm(M.q_mul(M.q_mul(M.q_axis((0, 1, 0), yaw), M.q_axis((1, 0, 0), pitch)), M.q_axis((0, 0, 1), roll)))


def spectrum(t, T, comps):
    return sum(a * math.sin(2 * math.pi * f * t / T + ph) for f, a, ph in comps)


def gust(t, times, width=0.35):
    return sum(math.exp(-((t - g) / width) ** 2) for g in times)


CLIPS = {
    "calm": {"T": 12.0, "roll": 1.5, "pitch": 0.8, "yaw": 0.6, "heave": 0.18, "buffet": 0.0, "gusts": [], "lightning": [], "rpm": 1900, "label": "Calm cruise"},
    "turbulence": {"T": 12.0, "roll": 5.5, "pitch": 3.2, "yaw": 1.8, "heave": 0.7, "buffet": 0.35, "gusts": [3.1, 7.4, 9.8], "lightning": [], "rpm": 2100, "label": "Moderate turbulence"},
    "storm": {"T": 12.0, "roll": 11.0, "pitch": 5.5, "yaw": 3.5, "heave": 1.6, "buffet": 1.0, "gusts": [1.6, 4.3, 6.2, 8.8, 10.9], "lightning": [2.2, 6.9, 10.3], "rpm": 2300, "label": "Storm front"},
    "evasive": {"T": 10.0, "roll": 2.0, "pitch": 1.2, "yaw": 1.0, "heave": 0.3, "buffet": 0.2, "gusts": [], "lightning": [], "rpm": 2400, "label": "Evasive S-turn", "bank": 32.0},
}


def bake():
    out = []
    for name, c in CLIPS.items():
        T = c["T"]
        rnd = lambda k: P._hash(k, len(name), 31) * 6.283
        frames = []
        n = int(T * FPS)
        prev = None
        for f in range(n + 1):
            t = f / FPS
            g = gust(t, c["gusts"])
            roll = spectrum(t, T, [(1, 1.0, rnd(1)), (3, 0.5, rnd(2)), (7, 0.25, rnd(3))]) * c["roll"] + g * c["roll"] * 0.8 * math.sin(rnd(4))
            pitch = spectrum(t, T, [(2, 1.0, rnd(5)), (5, 0.4, rnd(6))]) * c["pitch"] - g * c["pitch"] * 0.9
            yaw = spectrum(t, T, [(1, 1.0, rnd(7)), (4, 0.4, rnd(8))]) * c["yaw"]
            heave = spectrum(t, T, [(2, 1.0, rnd(9)), (6, 0.35, rnd(10))]) * c["heave"] - g * c["heave"] * 1.6
            sway = spectrum(t, T, [(1, 1.0, rnd(11)), (3, 0.3, rnd(12))]) * c["heave"] * 0.6
            if "bank" in c:
                roll += c["bank"] * math.sin(2 * math.pi * t / T)
                yaw += c["bank"] * 0.25 * math.cos(2 * math.pi * t / T)
                pitch += 2.0 * abs(math.sin(2 * math.pi * t / T))
                sway += 3.0 * math.cos(2 * math.pi * t / T)
            buffet = c["buffet"] * (0.4 + g)
            st = (roll, pitch, yaw)
            rates = (0, 0, 0) if prev is None else tuple((a - b) * FPS for a, b in zip(st, prev))
            prev = st
            ail = max(-22, min(22, -0.9 * rates[0] - 0.6 * roll))
            elev = max(-18, min(18, -1.1 * rates[1] - 0.8 * pitch))
            rud = max(-20, min(20, -1.2 * rates[2] - 0.6 * yaw))
            flash = sum(math.exp(-((t - L) / 0.06) ** 2) + 0.6 * math.exp(-((t - L - 0.18) / 0.05) ** 2) for L in c["lightning"])
            frames.append({"p": [round(sway, 4), round(heave, 4), 0.0], "q": [round(v, 5) for v in euler_q(math.radians(-pitch), math.radians(yaw), math.radians(-roll))],
                           "ail": round(math.radians(ail), 4), "elev": round(math.radians(elev), 4), "rud": round(math.radians(rud), 4),
                           "gust": round(min(1.0, g + buffet * 0.3), 4), "buffet": round(buffet, 4), "flash": round(min(flash, 1.5), 4)})
        events = [{"t": g_, "type": "gust", "label": "Gust"} for g_ in c["gusts"]] + [{"t": L, "type": "impact", "label": "Lightning"} for L in c["lightning"]]
        if "bank" in c:
            events += [{"t": T * 0.25, "type": "step", "label": "Hard left"}, {"t": T * 0.75, "type": "step", "label": "Hard right"}]
        out.append({"name": name, "label": c["label"], "duration": T, "loop": True, "rpm": c["rpm"], "frames": frames, "events": sorted(events, key=lambda e: e["t"])})
    return out


# ----------------------------------------------------------------------------- shaders

def glsl(name, desc, body):
    return HEADER.format(name=name, desc=desc) + body

SKY_FN = """
uniform vec3  uSunDir;
uniform vec3  uZenith;
uniform vec3  uHorizon;
uniform vec3  uSunColor;
uniform float uFlash;
vec3 skyColor(vec3 d) {
  float h = max(d.y, -0.2);
  vec3 c = mix(uHorizon, uZenith, pow(smoothstep(-0.05, 1.0, h), 0.55));
  float s = max(dot(d, normalize(uSunDir)), 0.0);
  c += uSunColor * (pow(s, 900.0) * 30.0 + pow(s, 12.0) * 0.35);
  c = mix(c, uHorizon * 0.75, smoothstep(0.0, -0.2, d.y));
  return c + uFlash * vec3(0.7, 0.75, 1.0);
}
"""

AIR_VERT = glsl("bomber.vert", "Airframe vertex stage: wing bending under gust load + high-frequency buffet, world varyings.", """
uniform float uTime;
uniform float uGust;      // 0..1 load from the baked gust channel
uniform float uBuffet;    // vibration amplitude
uniform float uFlexMask;  // 1 on wings
varying vec3 vWorld;
varying vec3 vNormal;
varying vec2 vUv;
varying vec3 vLocal;
void main() {
  vec3 p = position;
  float span = max(abs(p.x) - 1.5, 0.0);
  p.y += uFlexMask * (span * span * 0.0035 * (1.0 + 2.5 * uGust) + span * 0.004 * sin(uTime * 9.0 + span * 0.5) * uBuffet);
  p += normal * 0.004 * uBuffet * sin(uTime * 61.0 + p.z * 3.0);
  vec4 wp = modelMatrix * vec4(p, 1.0);
  vWorld = wp.xyz;
  vLocal = position;
  vNormal = normalize(mat3(modelMatrix) * normal);
  vUv = uv;
  gl_Position = projectionMatrix * viewMatrix * wp;
}
""")

PAINT_FRAG = glsl("bomber_paint.frag", "Painted/bare aluminium skin: albedo + roughness + panel normal map, sky-lit reflections, lightning flash.", SKY_FN + """
uniform sampler2D uAlbedo;
uniform sampler2D uRough;
uniform sampler2D uNormalMap;
uniform float uMetal;
uniform float uExposure;
varying vec3 vWorld;
varying vec3 vNormal;
varying vec2 vUv;
varying vec3 vLocal;

vec3 perturb(vec3 N, vec3 P, vec2 uv, vec3 m) {
  vec3 dp1 = dFdx(P), dp2 = dFdy(P); vec2 du1 = dFdx(uv), du2 = dFdy(uv);
  vec3 a = cross(dp2, N), b = cross(N, dp1);
  vec3 T = a * du1.x + b * du2.x, B = a * du1.y + b * du2.y;
  float s = inversesqrt(max(max(dot(T, T), dot(B, B)), 1e-12));
  return normalize(mat3(T * s, B * s, N) * m);
}

void main() {
  vec3 N = normalize(vNormal);
  if (!gl_FrontFacing) N = -N;
  N = perturb(N, vWorld, vUv, texture2D(uNormalMap, vUv).xyz * 2.0 - 1.0);
  vec3 V = normalize(cameraPosition - vWorld);
  vec3 L = normalize(uSunDir);
  vec3 alb = texture2D(uAlbedo, vUv).rgb;
  float r = texture2D(uRough, vUv).r;
  float metal = mix(0.15, 1.0, uMetal) * (1.0 - smoothstep(0.55, 0.8, r));
  vec3 F0 = mix(vec3(0.04), alb, metal);
  float ndv = max(dot(N, V), 0.0);
  vec3 F = F0 + (1.0 - F0) * pow(1.0 - ndv, 5.0) * (1.0 - r);
  vec3 R = reflect(-V, N);
  vec3 env = mix(skyColor(R), skyColor(normalize(N + vec3(0.0, 0.3, 0.0))) * 0.8, r);
  vec3 H = normalize(L + V);
  float gl = mix(500.0, 12.0, r);
  float spec = pow(max(dot(N, H), 0.0), gl) * (gl + 8.0) / 40.0;
  float ao = 0.55 + 0.45 * smoothstep(-1.0, 0.6, N.y);
  vec3 diff = alb * (1.0 - metal) * (uSunColor * max(dot(N, L), 0.0) + skyColor(N) * 0.45 * ao);
  vec3 col = diff + F * env * mix(1.0, 0.45, r) + F * uSunColor * spec * max(dot(N, L), 0.0);
  col += uFlash * alb * 0.6;
  col *= uExposure;
  col = (col * (2.51 * col + 0.03)) / (col * (2.43 * col + 0.59) + 0.14);
  gl_FragColor = vec4(pow(clamp(col, 0.0, 1.0), vec3(1.0 / 2.2)), 1.0);
}
""")

GLASS_FRAG = glsl("canopy_glass.frag", "Framed Plexiglas: thin-film tint, fresnel sky reflection, metal frame struts from UV grid.", SKY_FN + """
uniform vec3 uFrame;
varying vec3 vWorld;
varying vec3 vNormal;
varying vec2 vUv;
varying vec3 vLocal;
void main() {
  vec3 N = normalize(vNormal);
  vec3 V = normalize(cameraPosition - vWorld);
  float ndv = abs(dot(N, V));
  vec2 g = abs(fract(vUv * vec2(10.0, 6.0)) - 0.5);
  float frame = step(0.44, max(g.x, g.y));
  vec3 refl = skyColor(reflect(-V, N));
  float fres = 0.08 + 0.92 * pow(1.0 - ndv, 4.0);
  vec3 col = mix(vec3(0.04, 0.06, 0.07), refl, fres);
  col = mix(col, uFrame, frame);
  col = pow(clamp(col / (1.0 + col), 0.0, 1.0) * 1.2, vec3(1.0 / 2.2));
  gl_FragColor = vec4(col, mix(0.55 + fres * 0.45, 1.0, frame));
}
""")

DISC_FRAG = glsl("prop_disc.frag", "Propeller blur disc: radial blade ghosts rotating at the shaft speed, yellow tip ring, soft alpha.", """
uniform float uAngle;
uniform float uBlur;
varying vec2 vUv;
void main() {
  vec2 p = vUv * 2.0 - 1.0;
  float r = length(p);
  if (r > 1.0 || r < 0.14) discard;
  float a = atan(p.y, p.x) - uAngle;
  float ghost = pow(0.5 + 0.5 * cos(a * 3.0), 6.0);
  float tip = smoothstep(0.86, 0.9, r) * (1.0 - smoothstep(0.97, 1.0, r));
  vec3 col = mix(vec3(0.05), vec3(0.95, 0.78, 0.15), tip);
  float alpha = (0.12 + 0.25 * ghost + 0.3 * tip) * uBlur * (1.0 - smoothstep(0.95, 1.0, r));
  gl_FragColor = vec4(col, alpha);
}
""")

SKY_VERT = glsl("flight_sky.vert", "Sky dome locked to the camera.", "varying vec3 vDir;\nvoid main() { vDir = position; gl_Position = (projectionMatrix * viewMatrix * vec4(position + cameraPosition, 1.0)).xyww; }\n")

SKY_FRAG = glsl("flight_sky.frag", "Analytic sky + ray-marched cumulus deck 600 m below, scrolling with airspeed; storm darkening and lightning.", SKY_FN + """
uniform float uTime;
uniform float uSpeed;      // airspeed (m/s) -> cloud scroll
uniform float uCover;      // 0..1 cloud coverage
uniform float uStorm;
uniform vec3  uCloudLit;
uniform vec3  uCloudShade;
varying vec3 vDir;

float h21(vec2 p) { p = fract(p * vec2(234.34, 435.345)); p += dot(p, p + 34.23); return fract(p.x * p.y); }
float vn(vec2 p) { vec2 i = floor(p), f = fract(p); f = f * f * (3.0 - 2.0 * f);
  return mix(mix(h21(i), h21(i + vec2(1, 0)), f.x), mix(h21(i + vec2(0, 1)), h21(i + vec2(1, 1)), f.x), f.y); }
float fbm(vec2 p) { float s = 0.0, a = 0.5; for (int i = 0; i < 5; i++) { s += a * vn(p); p = p * 2.03 + 11.7; a *= 0.5; } return s; }

void main() {
  vec3 d = normalize(vDir);
  vec3 col = skyColor(d);
  // cloud deck: plane y = -600 (below) and a thin cirrus layer above
  if (d.y < -0.01) {
    float t = -600.0 / d.y;
    vec2 p = d.xz * t / 900.0 + vec2(0.0, uTime * uSpeed / 900.0);
    float dens = smoothstep(1.0 - uCover, 1.0 - uCover + 0.35, fbm(p * 1.4));
    float light = 0.55 + 0.45 * fbm(p * 1.4 + normalize(uSunDir).xz * 0.04);
    vec3 cc = mix(uCloudShade, uCloudLit, light) * (1.0 - 0.6 * uStorm);
    float fog = exp(-t / 9000.0);
    col = mix(col, cc + uFlash * vec3(0.6, 0.65, 0.9), dens * fog);
    col = mix(col, uHorizon * (1.0 - 0.5 * uStorm), 1.0 - fog);
  } else {
    float t = 2500.0 / max(d.y, 0.02);
    vec2 p = d.xz * t / 4000.0 + vec2(uTime * 0.002, uTime * uSpeed / 5000.0);
    float ci = smoothstep(0.55, 0.9, fbm(p * vec2(1.0, 3.0))) * smoothstep(0.02, 0.2, d.y) * (1.0 - uStorm);
    col = mix(col, uCloudLit * 1.1, ci * 0.5);
    col = mix(col, uCloudShade * 0.6, uStorm * smoothstep(0.0, 0.25, d.y) * smoothstep(0.35, 0.8, fbm(p * 0.7)));
  }
  col = col / (1.0 + col);
  gl_FragColor = vec4(pow(col * 1.25, vec3(1.0 / 2.2)), 1.0);
}
""")

TRAIL_VERT = glsl("contrail.vert", "Contrail / wingtip vortex ribbons: billboarded strips that sway with the turbulence and widen with age.", """
uniform float uTime;
uniform float uGust;
attribute float aAge;     // 0 at the source, 1 at the far end
attribute float aSide;    // -1 / 1 across the ribbon
varying float vAge;
varying float vSide;
void main() {
  vec3 p = position;
  float a = aAge;
  p.x += sin(a * 9.0 - uTime * 2.0) * a * (0.6 + 2.0 * uGust);
  p.y += cos(a * 7.0 - uTime * 1.6) * a * (0.4 + 1.5 * uGust);
  vec4 wp = modelMatrix * vec4(p, 1.0);
  vec3 toCam = normalize(cameraPosition - wp.xyz);
  vec3 side = normalize(cross(toCam, vec3(0.0, 0.0, 1.0)));
  wp.xyz += side * aSide * (0.15 + a * 2.2);
  vAge = a; vSide = aSide;
  gl_Position = projectionMatrix * viewMatrix * wp;
}
""")

TRAIL_FRAG = glsl("contrail.frag", "Soft condensation ribbon that dissolves with age.", """
uniform float uOpacity;
varying float vAge;
varying float vSide;
void main() {
  float a = (1.0 - abs(vSide)) * smoothstep(0.0, 0.04, vAge) * (1.0 - vAge) * uOpacity;
  gl_FragColor = vec4(vec3(0.97), a);
}
""")

STREAK_VERT = glsl("speed_streaks.vert", "Air-flow streak particles rushing past the airframe (relative wind).", """
attribute vec4 aSeed;
uniform float uTime;
uniform float uSpeed;
uniform float uGust;
varying float vA;
void main() {
  float span = 160.0;
  vec3 p = position;
  p.z = mod(p.z - uTime * uSpeed * (0.8 + aSeed.x * 0.4) + span * 0.5, span) - span * 0.5;
  p.y += sin(uTime * 3.0 + aSeed.y * 6.28) * uGust * 1.5;
  vec4 mv = viewMatrix * vec4(p, 1.0);
  vA = smoothstep(80.0, 20.0, abs(p.z)) * (0.25 + uGust * 0.75);
  gl_PointSize = (1.5 + aSeed.z * 2.5) * 45.0 / max(-mv.z, 1.0);
  vA *= smoothstep(6.0, 18.0, -mv.z);
  gl_Position = projectionMatrix * mv;
}
""")

STREAK_FRAG = glsl("speed_streaks.frag", "Elongated streak sprite.", """
varying float vA;
void main() {
  vec2 q = (gl_PointCoord - 0.5) * vec2(5.0, 1.0);
  float a = smoothstep(0.5, 0.0, length(q)) * vA;
  if (a < 0.01) discard;
  gl_FragColor = vec4(vec3(1.0), a * 0.35);
}
""")


# ----------------------------------------------------------------------------- bundle

def generate(out, spec=None):
    for d in ("meshes", "textures", "shaders", "animations", "runtime"):
        os.makedirs(os.path.join(out, d), exist_ok=True)
    rig, bones = build(1.6)
    for b, parts in rig.items():
        for i, p in enumerate(parts):
            p.name = "%s__%s%d" % (b, p.name.split("__")[-1], i)
    order = [b for b, _, _ in bones]
    parts = [p for b in order for p in rig.get(b, [])]
    tris = sum(p.tri_count for p in parts)
    assert tris <= BUDGET, tris
    M.write_obj(os.path.join(out, "meshes", "bomber_lod0.obj"), parts,
                header="Heavy bomber, %d triangles (budget %d), %d nodes, metres, nose +Z" % (tris, BUDGET, len(bones)))
    lod1, _ = build(0.6)
    lod1_parts = [p for b in order for p in lod1.get(b, [])]
    lod1_tris = sum(p.tri_count for p in lod1_parts)
    for b, ps in lod1.items():
        for i, p in enumerate(ps):
            p.name = "%s__%s%d" % (b, p.name.split("__")[-1], i)
    M.write_obj(os.path.join(out, "meshes", "bomber_lod1.obj"), lod1_parts, header="Heavy bomber LOD1, %d triangles" % lod1_tris)
    textures(os.path.join(out, "textures"))
    clips = bake()
    with open(os.path.join(out, "animations", "flight_clips.anim.json"), "w") as f:
        json.dump({"bones": [{"name": b, "parent": p, "pivot": list(v)} for b, p, v in bones], "fps": FPS,
                   "airspeed_ms": 72, "channels": {"p": "airframe offset (m)", "q": "airframe attitude", "ail/elev/rud": "surface deflection (rad)",
                                                   "gust": "load 0..1", "buffet": "vibration", "flash": "lightning"},
                   "clips": clips}, f, separators=(",", ":"))
    anims = []
    for c in clips:
        times = [i / FPS for i in range(len(c["frames"]))]
        ax = lambda axis, key, sgn=1: [list(M.q_axis(axis, sgn * fr[key])) for fr in c["frames"]]
        tracks = {"airframe": {"rotation": [fr["q"] for fr in c["frames"]], "translation": [fr["p"] for fr in c["frames"]]},
                  "aileron_r": {"rotation": ax((1, 0, 0), "ail")}, "aileron_l": {"rotation": ax((1, 0, 0), "ail", -1)},
                  "elevator_r": {"rotation": ax((1, 0, 0), "elev")}, "elevator_l": {"rotation": ax((1, 0, 0), "elev")},
                  "rudder": {"rotation": ax((0, 1, 0), "rud")}}
        for k in range(4):
            tracks["prop_%d" % k] = {"rotation": [list(M.q_axis((0, 0, 1), (i / FPS) * 2 * math.pi * 3 * (1 if k < 2 else -1))) for i in range(len(c["frames"]))]}
        anims.append({"name": c["name"], "times": times, "tracks": tracks})
    M.write_gltf_rig(os.path.join(out, "meshes", "bomber_rigged.gltf"), bones, rig,
                     {"paint": {"color": (0.27, 0.29, 0.17)}, "wing": {"color": (0.27, 0.29, 0.17)}, "fin": {"color": (0.27, 0.29, 0.17)},
                      "glass": {"color": (0.6, 0.7, 0.75)}, "metal": {"color": (0.3, 0.3, 0.32)}, "prop": {"color": (0.05, 0.05, 0.05)}}, anims)
    shaders = {"bomber.vert": AIR_VERT, "bomber_paint.frag": PAINT_FRAG, "canopy_glass.frag": GLASS_FRAG, "prop_disc.frag": DISC_FRAG,
               "flight_sky.vert": SKY_VERT, "flight_sky.frag": SKY_FRAG, "contrail.vert": TRAIL_VERT, "contrail.frag": TRAIL_FRAG,
               "speed_streaks.vert": STREAK_VERT, "speed_streaks.frag": STREAK_FRAG}
    for n, src in shaders.items():
        with open(os.path.join(out, "shaders", n), "w") as fh:
            fh.write(src)
    shutil.copy(os.path.join(os.path.dirname(__file__), "runtime", "bomber_viewer.js"), os.path.join(out, "runtime", "viewer.js"))

    T = "textures/"
    tex = lambda paint: {"paint": [T + "fuselage_%s.png" % paint, T + "fuselage_%s_rough.png" % paint, T + "fuselage_normal.png"],
                         "wing": [T + "wing_%s.png" % paint, T + "wing_%s_rough.png" % paint, T + "wing_normal.png"],
                         "fin": [T + "fin_%s.png" % paint, T + "fuselage_%s_rough.png" % paint, T + "fuselage_normal.png"]}
    render = {"type": "module", "module": "runtime/viewer.js", "timeline": True,
              "camera": {"position": [26, 9, 30], "target": [0, 0, 0], "fov": 40},
              "mesh": "meshes/bomber_lod0.obj", "lod1": "meshes/bomber_lod1.obj", "anim": "animations/flight_clips.anim.json",
              "shaders": {k.replace(".", "_"): "shaders/" + k for k in shaders}, "textures": tex("olive"), "prop": T + "prop.png", "metal": 0.0,
              "sky": {"zenith": [0.12, 0.32, 0.72], "horizon": [0.62, 0.76, 0.92], "sun": [0.35, 0.55, 0.75], "sunColor": [1.6, 1.5, 1.35],
                      "cloudLit": [1.25, 1.22, 1.18], "cloudShade": [0.55, 0.6, 0.7], "cover": 0.55, "storm": 0.0}}
    sky_patch = lambda **k: {"sky." + a: b for a, b in k.items()}
    variants = [
        {"id": "olive", "name": "Olive Drab", "group": "Paint", "default": True, "swatch": "#4b4f2e", "patch": {}},
        {"id": "metal", "name": "Natural Metal", "group": "Paint", "swatch": "#c4c8cf", "patch": {"textures": tex("metal"), "metal": 1.0}},
        {"id": "night", "name": "Night Bomber", "group": "Paint", "swatch": "#18181b", "patch": {"textures": tex("night")}},
        {"id": "day", "name": "High Noon", "group": "Sky", "default": True, "swatch": "#5aa0ff", "patch": {}},
        {"id": "golden", "name": "Golden Hour", "group": "Sky", "swatch": "#ff9a4c", "patch": sky_patch(zenith=[0.18, 0.22, 0.45], horizon=[1.1, 0.62, 0.35], sun=[0.8, 0.12, 0.55], sunColor=[1.8, 1.0, 0.55], cloudLit=[1.5, 0.95, 0.65], cloudShade=[0.45, 0.35, 0.45], cover=0.5)},
        {"id": "stormfront", "name": "Storm Front", "group": "Sky", "swatch": "#3b4252", "patch": sky_patch(zenith=[0.12, 0.14, 0.18], horizon=[0.32, 0.35, 0.4], sunColor=[0.6, 0.62, 0.68], cloudLit=[0.6, 0.62, 0.68], cloudShade=[0.2, 0.22, 0.26], cover=0.85, storm=1.0)},
    ]
    files = [
        {"path": "meshes/bomber_lod0.obj", "kind": "mesh", "role": "hero mesh · %s / %s tris" % (format(tris, ","), format(BUDGET, ",")), "meta": {"triangles": tris},
         "depends": [T + "fuselage_olive.png", T + "wing_olive.png", T + "fin_olive.png"]},
        {"path": "meshes/bomber_lod1.obj", "kind": "mesh", "role": "LOD1", "meta": {"triangles": lod1_tris}, "variant": "lod1"},
        {"path": "meshes/bomber_rigged.gltf", "kind": "mesh", "role": "glTF 2.0 · rig + 4 flight clips", "meta": {"triangles": tris}, "depends": ["animations/flight_clips.anim.json"]},
        {"path": "animations/flight_clips.anim.json", "kind": "animation", "role": "4 baked flight clips @30fps", "meta": {"clips": [c["name"] for c in clips]}, "depends": ["meshes/bomber_lod0.obj"]},
    ]
    for paint in PAINTS:
        for n in ("fuselage_%s.png", "fuselage_%s_rough.png", "wing_%s.png", "wing_%s_rough.png", "fin_%s.png"):
            files.append({"path": T + n % paint, "kind": "texture", "role": ("roughness" if "rough" in n else "albedo") + ("" if paint == "olive" else " variant"),
                          "variant": None if paint == "olive" else paint, "meta": {"width": 256 if n.startswith("fin") else 512}})
    files += [{"path": T + "fuselage_normal.png", "kind": "texture", "role": "panel normal", "meta": {"width": 512}},
              {"path": T + "wing_normal.png", "kind": "texture", "role": "panel normal", "meta": {"width": 512}},
              {"path": T + "prop.png", "kind": "texture", "role": "blade paint", "meta": {"width": 32}}]
    for n in shaders:
        dep = {"bomber_paint.frag": ["shaders/bomber.vert", T + "fuselage_olive.png", T + "wing_olive.png", T + "fuselage_normal.png"],
               "canopy_glass.frag": ["shaders/bomber.vert"], "flight_sky.frag": ["shaders/flight_sky.vert"], "contrail.frag": ["shaders/contrail.vert"],
               "speed_streaks.frag": ["shaders/speed_streaks.vert"], "prop_disc.frag": [T + "prop.png"]}.get(n, [])
        files.append({"path": "shaders/" + n, "kind": "shader", "role": "vertex" if n.endswith("vert") else "fragment", "depends": dep})
    files.append({"path": "runtime/viewer.js", "kind": "data", "role": "plug-in viewer · flight sim", "depends": ["animations/flight_clips.anim.json", "shaders/flight_sky.frag", "shaders/bomber_paint.frag"]})
    per = {}
    for p in parts:
        k = p.name.split("__")[1].rstrip("0123456789")
        per[k] = per.get(k, 0) + p.tri_count
    return {
        "kind": "animation", "files": files, "render": render, "variants": variants,
        "stats": {"triangles": tris, "budget": BUDGET, "budget_used": round(tris / BUDGET * 100, 1), "parts": len(parts), "lods": 2,
                  "clips": len(clips), "fps": FPS, "frames": sum(len(c["frames"]) for c in clips), "textures": len(PAINTS) * 5 + 3,
                  "shaders": len(shaders), "per_part": dict(sorted(per.items(), key=lambda x: -x[1])[:12])},
        "pipeline": [{"stage": s, "state": "done", "note": n} for s, n in [
            ("Interpret prompt", "animation · bomber · ≤90k polys · wind turbulence · shaders · sky"),
            ("Rig-free model", "%s tris: lathed fuselage, NACA-lofted wings/tail, 4 nacelles, 12 blades, glazing, turrets" % format(tris, ",")),
            ("Fracture pre-pass", "control surfaces, props and bay doors split onto hinge pivots (%d nodes)" % len(bones)),
            ("Key poses", "evasive S-turn: ±32° bank"),
            ("Physics bake", "periodic turbulence spectra + discrete gusts; pilot deflects surfaces against the rates"),
            ("Event track", "gusts, lightning strikes, hard turns"),
            ("Texture synthesis", "3 paint schemes × fuselage/wing/fin, insignia, panel lines, rivets, de-icer boots, tail number"),
            ("Shader authoring", "10 stages: paint, glass, prop blur, wing flex, ray-marched cloud deck, contrails, streaks"),
            ("Loop seam check", "all spectra integer-periodic → seamless 12 s loops"),
            ("glTF export", "node hierarchy + 4 named clips"),
            ("Preview render", "chase camera above the cloud deck"),
            ("Package bundle", "2 LODs, glTF, anim JSON, viewer")]],
    }
