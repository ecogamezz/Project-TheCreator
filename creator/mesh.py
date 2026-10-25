"""Mesh toolkit: parametric primitives, deformers, OBJ / MTL / glTF writers."""
import base64
import json
import math
import struct


# ----------------------------------------------------------------------------- vector math

def v_add(a, b): return (a[0] + b[0], a[1] + b[1], a[2] + b[2])
def v_sub(a, b): return (a[0] - b[0], a[1] - b[1], a[2] - b[2])
def v_mul(a, s): return (a[0] * s, a[1] * s, a[2] * s)
def v_dot(a, b): return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
def v_cross(a, b): return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])
def v_len(a): return math.sqrt(v_dot(a, a))


def v_norm(a):
    l = v_len(a)
    return (a[0] / l, a[1] / l, a[2] / l) if l > 1e-12 else (0.0, 1.0, 0.0)


def rot_x(p, a):
    c, s = math.cos(a), math.sin(a)
    return (p[0], p[1] * c - p[2] * s, p[1] * s + p[2] * c)


def rot_y(p, a):
    c, s = math.cos(a), math.sin(a)
    return (p[0] * c + p[2] * s, p[1], -p[0] * s + p[2] * c)


def rot_z(p, a):
    c, s = math.cos(a), math.sin(a)
    return (p[0] * c - p[1] * s, p[0] * s + p[1] * c, p[2])


# quaternions (x, y, z, w)
def q_axis(axis, ang):
    ax = v_norm(axis)
    s = math.sin(ang / 2)
    return (ax[0] * s, ax[1] * s, ax[2] * s, math.cos(ang / 2))


def q_mul(a, b):
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return (aw * bx + ax * bw + ay * bz - az * by,
            aw * by - ax * bz + ay * bw + az * bx,
            aw * bz + ax * by - ay * bx + az * bw,
            aw * bw - ax * bx - ay * by - az * bz)


def q_rotate(q, v):
    qv = (q[0], q[1], q[2])
    t = v_mul(v_cross(qv, v), 2)
    return v_add(v_add(v, v_mul(t, q[3])), v_cross(qv, t))


def q_norm(q):
    l = math.sqrt(sum(c * c for c in q))
    return tuple(c / l for c in q)


# ----------------------------------------------------------------------------- mesh parts

class Part:
    """One named, single-material chunk of geometry."""

    def __init__(self, name, material):
        self.name, self.material = name, material
        self.pos, self.uv, self.nrm, self.tris = [], [], [], []

    @property
    def tri_count(self):
        return len(self.tris)

    def transform(self, fn):
        self.pos = [fn(p) for p in self.pos]
        return self

    def translate(self, t):
        return self.transform(lambda p: v_add(p, t))

    def scale(self, s):
        s = s if isinstance(s, (tuple, list)) else (s, s, s)
        return self.transform(lambda p: (p[0] * s[0], p[1] * s[1], p[2] * s[2]))

    def rotate(self, rx=0.0, ry=0.0, rz=0.0):
        return self.transform(lambda p: rot_y(rot_x(rot_z(p, rz), rx), ry))

    def flip(self):
        self.tris = [(a, c, b) for a, b, c in self.tris]
        return self

    def append(self, other):
        off = len(self.pos)
        self.pos += other.pos
        self.uv += other.uv
        self.tris += [(a + off, b + off, c + off) for a, b, c in other.tris]
        return self

    def compute_normals(self, weld=True):
        acc = {}
        keys = [(round(p[0], 5), round(p[1], 5), round(p[2], 5)) if weld else i for i, p in enumerate(self.pos)]
        for a, b, c in self.tris:
            n = v_cross(v_sub(self.pos[b], self.pos[a]), v_sub(self.pos[c], self.pos[a]))
            for i in (a, b, c):
                k = keys[i]
                o = acc.get(k, (0.0, 0.0, 0.0))
                acc[k] = v_add(o, n)
        self.nrm = [v_norm(acc.get(k, (0, 1, 0))) for k in keys]
        return self

    def bounds(self):
        xs, ys, zs = zip(*self.pos)
        return (min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs))

    def centroid(self):
        lo, hi = self.bounds()
        return v_mul(v_add(lo, hi), 0.5)


def uv_sphere(name, material, seg_u=32, seg_v=16, deform=None, th_max=math.pi):
    """Unit sphere (or dome when th_max < pi); deform(p, u, v) -> p sculpts it."""
    part = Part(name, material)
    for j in range(seg_v + 1):
        v = j / seg_v
        th = v * th_max
        for i in range(seg_u + 1):
            u = i / seg_u
            ph = u * 2 * math.pi
            p = (math.sin(th) * math.cos(ph), math.cos(th), math.sin(th) * math.sin(ph))
            part.pos.append(deform(p, u, v) if deform else p)
            part.uv.append((u, 1 - v))
    row = seg_u + 1
    for j in range(seg_v):
        for i in range(seg_u):
            a, b = j * row + i, j * row + i + 1
            c, d = a + row, b + row
            if j != 0:
                part.tris.append((a, b, c))
            if j != seg_v - 1 or th_max < math.pi - 1e-6:
                part.tris.append((b, d, c))
    return part


def lathe(name, material, profile, seg=24, cap_top=False, cap_bottom=False):
    """profile: [(radius, y), ...] bottom->top, revolved around +Y."""
    part = Part(name, material)
    n = len(profile)
    for j, (r, y) in enumerate(profile):
        for i in range(seg + 1):
            a = i / seg * 2 * math.pi
            part.pos.append((r * math.cos(a), y, r * math.sin(a)))
            part.uv.append((i / seg, j / (n - 1)))
    row = seg + 1
    for j in range(n - 1):
        for i in range(seg):
            a, b = j * row + i, j * row + i + 1
            c, d = a + row, b + row
            part.tris += [(a, c, b), (b, c, d)]
    for cap, (r, y), flip in ((cap_bottom, profile[0], True), (cap_top, profile[-1], False)):
        if not cap:
            continue
        ci = len(part.pos)
        part.pos.append((0, y, 0))
        part.uv.append((0.5, 0.5))
        base = len(part.pos)
        for i in range(seg):
            a = i / seg * 2 * math.pi
            part.pos.append((r * math.cos(a), y, r * math.sin(a)))
            part.uv.append((0.5 + 0.5 * math.cos(a), 0.5 + 0.5 * math.sin(a)))
        for i in range(seg):
            t = (ci, base + (i + 1) % seg, base + i)
            part.tris.append((t[0], t[2], t[1]) if flip else t)
    return part


def grid(name, material, size_x, size_z, nx, nz, height=None, uv_repeat=1.0):
    """Flat XZ grid centred at origin; height(x, z) -> y."""
    part = Part(name, material)
    for j in range(nz + 1):
        for i in range(nx + 1):
            x = (i / nx - 0.5) * size_x
            z = (j / nz - 0.5) * size_z
            part.pos.append((x, height(x, z) if height else 0.0, z))
            part.uv.append((i / nx * uv_repeat, j / nz * uv_repeat))
    row = nx + 1
    for j in range(nz):
        for i in range(nx):
            a, b = j * row + i, j * row + i + 1
            c, d = a + row, b + row
            part.tris += [(a, c, b), (b, c, d)]
    return part


def quad(name, material, w, h):
    part = Part(name, material)
    part.pos = [(-w / 2, 0, 0), (w / 2, 0, 0), (w / 2, h, 0), (-w / 2, h, 0)]
    part.uv = [(0, 0), (1, 0), (1, 1), (0, 1)]
    part.tris = [(0, 1, 2), (0, 2, 3)]
    return part


# ----------------------------------------------------------------------------- writers

def write_obj(path, parts, mtl_name=None, header=""):
    lines = ["# " + l for l in header.strip().splitlines()] if header else []
    lines.append("# Generated by Project-TheCreator")
    if mtl_name:
        lines.append("mtllib " + mtl_name)
    off = 1
    for p in parts:
        if not p.nrm:
            p.compute_normals()
        lines.append("o " + p.name)
        lines += ["v %.5f %.5f %.5f" % v for v in p.pos]
        lines += ["vt %.5f %.5f" % t for t in p.uv]
        lines += ["vn %.4f %.4f %.4f" % n for n in p.nrm]
        lines.append("usemtl " + p.material)
        lines.append("s 1")
        for a, b, c in p.tris:
            a, b, c = a + off, b + off, c + off
            lines.append("f %d/%d/%d %d/%d/%d %d/%d/%d" % (a, a, a, b, b, b, c, c, c))
        off += len(p.pos)
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")


def write_mtl(path, materials):
    """materials: {name: {Kd: (r,g,b), Ks, Ns, map_Kd, map_Bump, ...}}"""
    out = ["# Generated by Project-TheCreator"]
    for name, m in materials.items():
        out.append("newmtl " + name)
        for k, v in m.items():
            out.append("%s %s" % (k, " ".join("%.4f" % c for c in v) if isinstance(v, (tuple, list)) else v))
        out.append("")
    with open(path, "w") as f:
        f.write("\n".join(out))


def write_gltf(path, parts, materials, animation=None, node_pivots=None):
    """Minimal but valid glTF 2.0 with one node per part and optional TRS animation.

    animation: {"name": str, "times": [...], "tracks": {part_name: {"translation": [...], "rotation": [...], "scale": [...]}}}
    node_pivots: {part_name: (x,y,z)} -> geometry is recentred so nodes rotate about that pivot.
    """
    buf = bytearray()
    views, accessors, meshes, nodes = [], [], [], []
    mat_index = {name: i for i, name in enumerate(materials)}

    def add_view(data, target=None):
        while len(buf) % 4:
            buf.append(0)
        views.append({"buffer": 0, "byteOffset": len(buf), "byteLength": len(data), **({"target": target} if target else {})})
        buf.extend(data)
        return len(views) - 1

    def add_acc(values, comp, typ, count, minmax=False, target=None):
        flat = [c for v in values for c in (v if isinstance(v, (tuple, list)) else (v,))]
        fmt = "<%d%s" % (len(flat), "f" if comp == 5126 else "I")
        view = add_view(struct.pack(fmt, *flat), target)
        acc = {"bufferView": view, "componentType": comp, "count": count, "type": typ}
        if minmax:
            n = len(flat) // count
            acc["min"] = [min(flat[i::n]) for i in range(n)]
            acc["max"] = [max(flat[i::n]) for i in range(n)]
        accessors.append(acc)
        return len(accessors) - 1

    for p in parts:
        if not p.nrm:
            p.compute_normals()
        piv = (node_pivots or {}).get(p.name, (0.0, 0.0, 0.0))
        pos = [v_sub(v, piv) for v in p.pos]
        attrs = {
            "POSITION": add_acc(pos, 5126, "VEC3", len(pos), True, 34962),
            "NORMAL": add_acc(p.nrm, 5126, "VEC3", len(p.nrm), False, 34962),
            "TEXCOORD_0": add_acc([(u, 1 - v) for u, v in p.uv], 5126, "VEC2", len(p.uv), False, 34962),
        }
        idx = add_acc([i for t in p.tris for i in t], 5125, "SCALAR", len(p.tris) * 3, False, 34963)
        meshes.append({"name": p.name, "primitives": [{"attributes": attrs, "indices": idx, "material": mat_index[p.material]}]})
        nodes.append({"name": p.name, "mesh": len(meshes) - 1, "translation": list(piv)})

    gltf = {
        "asset": {"version": "2.0", "generator": "Project-TheCreator"},
        "scene": 0,
        "scenes": [{"nodes": list(range(len(nodes)))}],
        "nodes": nodes, "meshes": meshes,
        "materials": [{"name": n, "pbrMetallicRoughness": {
            "baseColorFactor": list(m.get("color", (0.8, 0.8, 0.8))) + [1.0],
            "metallicFactor": m.get("metallic", 0.0), "roughnessFactor": m.get("roughness", 0.6)},
            **({"emissiveFactor": list(m["emissive"])} if "emissive" in m else {})} for n, m in materials.items()],
    }
    if animation:
        t_acc = add_acc(animation["times"], 5126, "SCALAR", len(animation["times"]), True)
        samplers, channels = [], []
        names = [p.name for p in parts]
        for pname, tr in animation["tracks"].items():
            for path_, typ in (("translation", "VEC3"), ("rotation", "VEC4"), ("scale", "VEC3")):
                if path_ in tr:
                    out = add_acc(tr[path_], 5126, typ, len(tr[path_]))
                    samplers.append({"input": t_acc, "output": out, "interpolation": "LINEAR"})
                    channels.append({"sampler": len(samplers) - 1, "target": {"node": names.index(pname), "path": path_}})
        gltf["animations"] = [{"name": animation["name"], "samplers": samplers, "channels": channels}]
    gltf["accessors"] = accessors
    gltf["bufferViews"] = views
    gltf["buffers"] = [{"byteLength": len(buf), "uri": "data:application/octet-stream;base64," + base64.b64encode(bytes(buf)).decode()}]
    with open(path, "w") as f:
        json.dump(gltf, f, separators=(",", ":"))


def write_gltf_rig(path, bones, parts_by_bone, materials, animations):
    """glTF 2.0 with a real node hierarchy (one node per bone, one multi-primitive mesh per bone) and N clips.

    bones: [(name, parent_or_None, pivot_world)]  (geometry is stored relative to its bone pivot)
    animations: [{"name", "times", "tracks": {bone: {"rotation": [...], "translation": [...]}}}]  (local TRS)
    """
    buf = bytearray()
    views, accessors, meshes, nodes = [], [], [], []
    mat_index = {name: i for i, name in enumerate(materials)}

    def add(values, comp, typ, count, minmax=False, target=None):
        flat = [c for v in values for c in (v if isinstance(v, (tuple, list)) else (v,))]
        while len(buf) % 4:
            buf.append(0)
        data = struct.pack("<%d%s" % (len(flat), "f" if comp == 5126 else "I"), *flat)
        views.append({"buffer": 0, "byteOffset": len(buf), "byteLength": len(data), **({"target": target} if target else {})})
        buf.extend(data)
        acc = {"bufferView": len(views) - 1, "componentType": comp, "count": count, "type": typ}
        if minmax:
            n = len(flat) // count
            acc["min"] = [min(flat[i::n]) for i in range(n)]
            acc["max"] = [max(flat[i::n]) for i in range(n)]
        accessors.append(acc)
        return len(accessors) - 1

    index = {b[0]: i for i, b in enumerate(bones)}
    pivots = {b[0]: b[2] for b in bones}
    for name, parent, piv in bones:
        prims = []
        for p in parts_by_bone.get(name, []):
            if not p.nrm:
                p.compute_normals()
            pos = [v_sub(v, piv) for v in p.pos]
            attrs = {"POSITION": add(pos, 5126, "VEC3", len(pos), True, 34962), "NORMAL": add(p.nrm, 5126, "VEC3", len(p.nrm), False, 34962),
                     "TEXCOORD_0": add([(u, 1 - v) for u, v in p.uv], 5126, "VEC2", len(p.uv), False, 34962)}
            prims.append({"attributes": attrs, "indices": add([i for t in p.tris for i in t], 5125, "SCALAR", len(p.tris) * 3, False, 34963),
                          "material": mat_index[p.material]})
        node = {"name": name, "translation": list(v_sub(piv, pivots[parent]) if parent else piv)}
        if prims:
            meshes.append({"name": name, "primitives": prims})
            node["mesh"] = len(meshes) - 1
        kids = [index[b[0]] for b in bones if b[1] == name]
        if kids:
            node["children"] = kids
        nodes.append(node)
    anims = []
    for a in animations:
        t_acc = add(a["times"], 5126, "SCALAR", len(a["times"]), True)
        samplers, channels = [], []
        for bone, tr in a["tracks"].items():
            for path_, typ in (("translation", "VEC3"), ("rotation", "VEC4")):
                if path_ in tr:
                    samplers.append({"input": t_acc, "output": add(tr[path_], 5126, typ, len(tr[path_])), "interpolation": "LINEAR"})
                    channels.append({"sampler": len(samplers) - 1, "target": {"node": index[bone], "path": path_}})
        anims.append({"name": a["name"], "samplers": samplers, "channels": channels})
    gltf = {"asset": {"version": "2.0", "generator": "Project-TheCreator"}, "scene": 0,
            "scenes": [{"nodes": [index[b[0]] for b in bones if not b[1]]}], "nodes": nodes, "meshes": meshes,
            "materials": [{"name": n, "pbrMetallicRoughness": {"baseColorFactor": list(m.get("color", (0.8, 0.8, 0.8))) + [1.0],
                                                                "metallicFactor": 0.0, "roughnessFactor": 0.9}} for n, m in materials.items()],
            "animations": anims, "accessors": accessors, "bufferViews": views,
            "buffers": [{"byteLength": len(buf), "uri": "data:application/octet-stream;base64," + base64.b64encode(bytes(buf)).decode()}]}
    with open(path, "w") as f:
        json.dump(gltf, f, separators=(",", ":"))
