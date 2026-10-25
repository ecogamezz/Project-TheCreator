"""Tiny 5x7 bitmap typeface ("TC-HUD") exported as BDF (a real X11 font format), a PNG atlas and JSON metrics."""
import os

from .procedural import write_png

GLYPHS = {
    "A": [14, 17, 17, 31, 17, 17, 17], "B": [30, 17, 17, 30, 17, 17, 30], "C": [14, 17, 16, 16, 16, 17, 14],
    "D": [30, 17, 17, 17, 17, 17, 30], "E": [31, 16, 16, 30, 16, 16, 31], "F": [31, 16, 16, 30, 16, 16, 16],
    "G": [14, 17, 16, 23, 17, 17, 15], "H": [17, 17, 17, 31, 17, 17, 17], "I": [14, 4, 4, 4, 4, 4, 14],
    "J": [7, 2, 2, 2, 2, 18, 12], "K": [17, 18, 20, 24, 20, 18, 17], "L": [16, 16, 16, 16, 16, 16, 31],
    "M": [17, 27, 21, 21, 17, 17, 17], "N": [17, 17, 25, 21, 19, 17, 17], "O": [14, 17, 17, 17, 17, 17, 14],
    "P": [30, 17, 17, 30, 16, 16, 16], "Q": [14, 17, 17, 17, 21, 18, 13], "R": [30, 17, 17, 30, 20, 18, 17],
    "S": [15, 16, 16, 14, 1, 1, 30], "T": [31, 4, 4, 4, 4, 4, 4], "U": [17, 17, 17, 17, 17, 17, 14],
    "V": [17, 17, 17, 17, 17, 10, 4], "W": [17, 17, 17, 21, 21, 21, 10], "X": [17, 17, 10, 4, 10, 17, 17],
    "Y": [17, 17, 17, 10, 4, 4, 4], "Z": [31, 1, 2, 4, 8, 16, 31],
    "0": [14, 17, 19, 21, 25, 17, 14], "1": [4, 12, 4, 4, 4, 4, 14], "2": [14, 17, 1, 2, 4, 8, 31],
    "3": [31, 2, 4, 2, 1, 17, 14], "4": [2, 6, 10, 18, 31, 2, 2], "5": [31, 16, 30, 1, 1, 17, 14],
    "6": [6, 8, 16, 30, 17, 17, 14], "7": [31, 1, 2, 4, 8, 8, 8], "8": [14, 17, 17, 14, 17, 17, 14],
    "9": [14, 17, 17, 15, 1, 2, 12], ":": [0, 12, 12, 0, 12, 12, 0], ".": [0, 0, 0, 0, 0, 12, 12],
    "!": [4, 4, 4, 4, 4, 0, 4], "-": [0, 0, 0, 31, 0, 0, 0], "/": [1, 1, 2, 4, 8, 16, 16],
    "'": [4, 4, 8, 0, 0, 0, 0], "*": [0, 4, 21, 14, 21, 4, 0], "+": [0, 4, 4, 31, 4, 4, 0],
    "%": [24, 25, 2, 4, 8, 19, 3], "?": [14, 17, 1, 2, 4, 0, 4], " ": [0] * 7,
}
CHARS = "".join(sorted(GLYPHS, key=lambda c: (c != " ", not c.isalpha(), c)))


def export(out_dir, name="tc_hud"):
    os.makedirs(out_dir, exist_ok=True)
    # BDF
    lines = ["STARTFONT 2.1", "FONT -thecreator-%s-medium-r-normal--7-70-75-75-c-60-iso10646-1" % name,
             "SIZE 7 75 75", "FONTBOUNDINGBOX 6 7 0 0", "STARTPROPERTIES 3", 'FAMILY_NAME "TC HUD"',
             "FONT_ASCENT 7", "FONT_DESCENT 0", "ENDPROPERTIES", "CHARS %d" % len(CHARS)]
    for ch in CHARS:
        lines += ["STARTCHAR U+%04X" % ord(ch), "ENCODING %d" % ord(ch), "SWIDTH 857 0", "DWIDTH 6 0", "BBX 6 7 0 0", "BITMAP"]
        lines += ["%02X" % (row << 3) for row in GLYPHS[ch]]
        lines.append("ENDCHAR")
    lines.append("ENDFONT")
    with open(os.path.join(out_dir, name + ".bdf"), "w") as f:
        f.write("\n".join(lines) + "\n")

    # Atlas: 16 columns, 8x10 cells at 2x scale with a 1px drop-shadow + outline (classic console HUD look).
    scale, cw, ch_ = 2, 8, 10
    cols = 16
    rows = (len(CHARS) + cols - 1) // cols
    W, H = cols * cw * scale, rows * ch_ * scale
    buf = bytearray(W * H * 4)

    def plot(x, y, rgba):
        if 0 <= x < W and 0 <= y < H:
            i = (y * W + x) * 4
            if buf[i + 3] <= rgba[3]:
                buf[i:i + 4] = bytes(rgba)

    for idx, c in enumerate(CHARS):
        ox, oy = (idx % cols) * cw * scale, (idx // cols) * ch_ * scale
        for pass_ in ("shadow", "outline", "fill"):
            for gy, row in enumerate(GLYPHS[c]):
                for gx in range(5):
                    if not row & (16 >> gx):
                        continue
                    for sy in range(scale):
                        for sx in range(scale):
                            px, py = ox + (gx + 1) * scale + sx, oy + (gy + 1) * scale + sy
                            if pass_ == "shadow":
                                plot(px + 2, py + 2, (10, 14, 40, 200))
                            elif pass_ == "outline":
                                for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                                    plot(px + dx, py + dy, (20, 30, 90, 255))
                            else:
                                g = 255 - int(gy / 6 * 70)   # top-to-bottom gradient like old menu fonts
                                plot(px, py, (255, g, int(g * 0.55), 255))
    write_png(os.path.join(out_dir, name + "_atlas.png"), W, H, buf, 4)

    import json
    meta = {"family": "TC HUD", "format": "bitmap 5x7", "chars": CHARS, "columns": cols, "cell": [cw * scale, ch_ * scale],
            "advance": 6 * scale, "lineHeight": ch_ * scale, "atlas": name + "_atlas.png", "bdf": name + ".bdf",
            "glyphs": {c: GLYPHS[c] for c in CHARS}}
    with open(os.path.join(out_dir, name + ".font.json"), "w") as f:
        json.dump(meta, f, indent=1)
    return [name + ".bdf", name + "_atlas.png", name + ".font.json"], (W, H)
