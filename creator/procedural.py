"""Procedural toolkit: PNG encoding, noise, colour math, image buffers.

Pure standard library so the whole pipeline runs anywhere Python 3.9+ runs.
"""
import math
import struct
import zlib


# ----------------------------------------------------------------------------- PNG

def write_png(path, width, height, pixels, channels=4):
    """pixels: flat bytearray, row-major, `channels` bytes per pixel (3=RGB, 4=RGBA)."""
    color_type = 6 if channels == 4 else 2
    stride = width * channels
    raw = bytearray()
    for y in range(height):
        raw.append(0)
        raw += pixels[y * stride:(y + 1) * stride]

    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, color_type, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(bytes(raw), 9))
    png += chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(png)


class Image:
    """Float RGBA image buffer with helpers. Values in 0..1."""

    def __init__(self, w, h, fill=(0, 0, 0, 1)):
        self.w, self.h = w, h
        self.data = [list(fill) for _ in range(w * h)]

    def set(self, x, y, c):
        self.data[y * self.w + x] = list(c) if len(c) == 4 else [c[0], c[1], c[2], 1.0]

    def get(self, x, y):
        return self.data[(y % self.h) * self.w + (x % self.w)]

    def save(self, path, alpha=True):
        ch = 4 if alpha else 3
        buf = bytearray(self.w * self.h * ch)
        i = 0
        for px in self.data:
            for k in range(ch):
                v = px[k]
                buf[i] = 0 if v <= 0 else 255 if v >= 1 else int(v * 255 + 0.5)
                i += 1
        write_png(path, self.w, self.h, buf, ch)


def render(path, w, h, fn, alpha=True):
    """Evaluate fn(u, v, x, y) -> (r,g,b[,a]) for every pixel and save as PNG."""
    img = Image(w, h)
    for y in range(h):
        v = (y + 0.5) / h
        for x in range(w):
            img.set(x, y, fn((x + 0.5) / w, v, x, y))
    img.save(path, alpha)
    return img


def height_to_normal(heights, w, h, strength=2.0):
    """heights: flat list w*h -> Image of tangent-space normal map (tileable)."""
    img = Image(w, h)
    for y in range(h):
        for x in range(w):
            l = heights[y * w + (x - 1) % w]
            r = heights[y * w + (x + 1) % w]
            d = heights[((y - 1) % h) * w + x]
            u = heights[((y + 1) % h) * w + x]
            nx, ny, nz = (l - r) * strength, (d - u) * strength, 1.0
            inv = 1.0 / math.sqrt(nx * nx + ny * ny + nz * nz)
            img.set(x, y, (nx * inv * 0.5 + 0.5, ny * inv * 0.5 + 0.5, nz * inv * 0.5 + 0.5, 1))
    return img


# ----------------------------------------------------------------------------- noise

def _hash(ix, iy, seed=0):
    n = (ix * 374761393 + iy * 668265263 + seed * 2147483647) & 0xFFFFFFFF
    n = ((n ^ (n >> 13)) * 1274126177) & 0xFFFFFFFF
    return ((n ^ (n >> 16)) & 0xFFFFFF) / 16777215.0


def _hash2(ix, iy, seed=0):
    return _hash(ix, iy, seed), _hash(ix + 1013, iy - 7919, seed + 17)


def _fade(t):
    return t * t * (3 - 2 * t)


def value_noise(x, y, seed=0, period=0):
    ix, iy = math.floor(x), math.floor(y)
    fx, fy = x - ix, y - iy
    if period:
        x0, y0, x1, y1 = ix % period, iy % period, (ix + 1) % period, (iy + 1) % period
    else:
        x0, y0, x1, y1 = ix, iy, ix + 1, iy + 1
    a, b = _hash(x0, y0, seed), _hash(x1, y0, seed)
    c, d = _hash(x0, y1, seed), _hash(x1, y1, seed)
    u, v = _fade(fx), _fade(fy)
    return a + (b - a) * u + (c - a) * v + (a - b - c + d) * u * v


def fbm(x, y, octaves=4, seed=0, period=0, lacunarity=2.0, gain=0.5):
    amp, freq, total, norm = 1.0, 1.0, 0.0, 0.0
    for o in range(octaves):
        p = int(period * freq) if period else 0
        total += amp * value_noise(x * freq, y * freq, seed + o * 31, p)
        norm += amp
        amp *= gain
        freq *= lacunarity
    return total / norm


def voronoi(x, y, seed=0, period=0, jitter=1.0):
    """Returns (f1, f2, cell_id_float, cell_center) of a Worley cell field."""
    ix, iy = math.floor(x), math.floor(y)
    f1 = f2 = 9.0
    cid = 0.0
    center = (0, 0)
    for oy in (-1, 0, 1):
        for ox in (-1, 0, 1):
            cx, cy = ix + ox, iy + oy
            hx, hy = (cx % period, cy % period) if period else (cx, cy)
            jx, jy = _hash2(hx, hy, seed)
            px, py = cx + 0.5 + (jx - 0.5) * jitter, cy + 0.5 + (jy - 0.5) * jitter
            d = math.hypot(px - x, py - y)
            if d < f1:
                f2, f1 = f1, d
                cid = _hash(hx, hy, seed + 99)
                center = (px, py)
            elif d < f2:
                f2 = d
    return f1, f2, cid, center


# ----------------------------------------------------------------------------- colour

def lerp(a, b, t):
    return a + (b - a) * t


def mix(c1, c2, t):
    return tuple(lerp(a, b, t) for a, b in zip(c1, c2))


def clamp(v, lo=0.0, hi=1.0):
    return lo if v < lo else hi if v > hi else v


def smoothstep(e0, e1, x):
    t = clamp((x - e0) / (e1 - e0))
    return t * t * (3 - 2 * t)


def hexc(h, a=1.0):
    h = h.lstrip("#")
    return (int(h[0:2], 16) / 255, int(h[2:4], 16) / 255, int(h[4:6], 16) / 255, a)


def ramp(stops, t):
    """stops: list of (pos, colour)."""
    t = clamp(t)
    for i in range(len(stops) - 1):
        p0, c0 = stops[i]
        p1, c1 = stops[i + 1]
        if t <= p1:
            return mix(c0, c1, (t - p0) / max(p1 - p0, 1e-6))
    return stops[-1][1]


BAYER4 = [[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]


def ps2_quantize(c, x, y, levels=24):
    """Ordered-dither + channel quantisation for that 2000s console texture look."""
    d = (BAYER4[y & 3][x & 3] / 16.0 - 0.5) / levels
    return tuple(round(clamp(ch + d) * levels) / levels for ch in c[:3]) + (c[3] if len(c) > 3 else 1.0,)


def write_apng(path, width, height, frames, fps=24, channels=4):
    """Animated PNG (plays natively in browsers, keeps alpha). frames: list of flat bytearrays."""
    color_type = 6 if channels == 4 else 2
    stride = width * channels

    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    def packed(px):
        raw = bytearray()
        for y in range(height):
            raw.append(0)
            raw += px[y * stride:(y + 1) * stride]
        return zlib.compress(bytes(raw), 9)

    out = b"\x89PNG\r\n\x1a\n"
    out += chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, color_type, 0, 0, 0))
    out += chunk(b"acTL", struct.pack(">II", len(frames), 0))
    seq = 0
    for i, px in enumerate(frames):
        out += chunk(b"fcTL", struct.pack(">IIIIIHHBB", seq, width, height, 0, 0, 1, fps, 0, 0))
        seq += 1
        data = packed(px)
        if i == 0:
            out += chunk(b"IDAT", data)
        else:
            out += chunk(b"fdAT", struct.pack(">I", seq) + data)
            seq += 1
    out += chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(out)
