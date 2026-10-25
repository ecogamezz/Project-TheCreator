"""Prompt interpreter: turns free text into a structured creation spec + pipeline plan.

Deterministic and explainable on purpose: every extracted field records the words that triggered it,
so the UI can highlight *why* the system decided something.
"""
import re

# Weighted evidence per kind: (pattern, weight). A word that names the *head* of the request
# (within the first few words) counts extra, so "a fox with a fur texture" stays an object.
KIND_EVIDENCE = {
    "animation": [(r"\banimat\w*", 3), (r"\bloop\w*", 1), (r"\bkeyframe\w*", 2), (r"\b(jumps?|spins?|rotates?|bounces?|walks?|flies)\b", 1)],
    "scene": [(r"\bscene\b", 3), (r"\b(environment|level|landscape|diorama|beach|alley|forest|city|island|room|interior)\b", 2)],
    "shader": [(r"\bshaders?\b", 2)],
    "font": [(r"\b(font|typeface|glyphs?)\b", 3)],
    "texture": [(r"\btextures?\b", 1), (r"\b(texture|material) (pack|set|sheet|atlas)\b", 3)],
    "object": [(r"\b(3d|obj|model|mesh|prop|character|creature|vehicle)\b", 2), (r"low[- ]?poly", 1),
               (r"\d[\d,.]*k?\s*(?:polygons|polys|poly|tris|triangles)", 2)],
}
HEAD_BONUS = {"shader": r"\bshader\b", "texture": r"\btexture\b", "font": r"\bfont\b", "scene": r"\bscene\b"}


def _classify(low):
    head = " ".join(low.split()[:6])
    scores, why = {}, {}
    for kind, rules in KIND_EVIDENCE.items():
        for pat, w in rules:
            m = re.search(pat, low)
            if m:
                scores[kind] = scores.get(kind, 0) + w
                why.setdefault(kind, m.group(0))
        if kind in HEAD_BONUS and re.search(HEAD_BONUS[kind], head):
            scores[kind] = scores.get(kind, 0) + 3
    if not scores:
        return "object", None, {}
    kind = max(scores, key=lambda k: (scores[k], k == "object"))
    return kind, why.get(kind), scores


STYLES = {
    "ps2": r"\bps2\b|playstation ?2", "ps1": r"\bps1\b|playstation ?1|\bpsx\b", "low-poly": r"low[- ]?poly",
    "realistic": r"realistic|photoreal", "stylized": r"styli[sz]ed|cartoon|toon", "pixel": r"\bpixel",
    "n64": r"\bn64\b", "noir": r"\bnoir\b", "cyberpunk": r"cyberpunk|neon",
}
MATERIALS = ["gold", "golden", "silver", "metal", "steel", "copper", "glass", "wood", "stone", "sand", "water",
             "crystal", "marble", "chrome", "obsidian", "jade", "ice", "lava"]
EFFECTS = {"particles": r"particle", "wind": r"\bwind", "clouds": r"cloud", "waves": r"\bwaves?\b",
           "flash": r"\bflash", "shards": r"shards?|debris|fragments?", "regeneration": r"regenerat|heal|reform",
           "fade": r"\bfad\w*", "glow": r"\bglow", "fog": r"\bfog\b|\bmist\b", "rain": r"\brain\b", "fire": r"\bfire\b|flame"}
MOTIONS = ["jumps", "jump", "rotates", "rotate", "spins", "lands", "falls", "flies", "swims", "walks", "bounces", "explodes"]
COLORS = ["red", "green", "blue", "white", "black", "yellow", "orange", "purple", "pink", "cyan", "magenta", "teal", "violet"]

PIPELINES = {
    "object": ["Interpret prompt", "Blockout primitives", "Sculpt & deform", "Polygon budget pass", "UV layout",
               "Texture synthesis", "Normal & roughness bake", "Shader authoring", "Material binding", "LOD chain",
               "Variants", "Preview render", "Package bundle"],
    "scene": ["Interpret prompt", "Layout & terrain", "Hero props", "Water / sky systems", "Texture synthesis",
              "Shader authoring", "Particle systems", "Lighting & fog", "Time-of-day variants", "Post FX", "Preview render",
              "Package bundle"],
    "animation": ["Interpret prompt", "Rig-free model", "Fracture pre-pass", "Key poses", "Physics bake", "Event track",
                  "Texture synthesis", "Shader authoring", "Loop seam check", "glTF export", "Preview render", "Package bundle"],
    "shader": ["Interpret prompt", "Uniform design", "Vertex stage", "Fragment stage", "Preview render", "Package bundle"],
    "texture": ["Interpret prompt", "Pattern synthesis", "Map derivation", "Tiling check", "Preview render", "Package bundle"],
    "font": ["Interpret prompt", "Glyph design", "Metrics & kerning", "Atlas bake", "Specimen", "Package bundle"],
}


def _num(s):
    s = s.lower().replace(",", "").replace(".", "")
    return int(float(s[:-1]) * 1000) if s.endswith("k") else int(s)


def interpret(prompt):
    text = prompt.strip()
    low = text.lower()
    hits = []

    kind, kind_word, scores = _classify(low)
    hits.append({"field": "kind", "value": kind, "because": kind_word or "default"})

    budget = None
    m = re.search(r"(\d[\d,.]*k?)\s*(?:polygons|polys|poly|tris|triangles|faces)", low)
    if m:
        budget = _num(m.group(1))
        hits.append({"field": "poly_budget", "value": budget, "because": m.group(0)})

    subject = None
    m = re.search(r"\b(?:of|with)\s+(?:a|an|the)\s+([a-z0-9 \-]+?)(?:[.,]| with| but| that| and| for| at|$)", low)
    if not m:
        m = re.search(r"\b(?:a|an)\s+(?:3d\s+)?([a-z0-9 \-]+?)(?:[.,]| with| but| that| and| for| at|$)", low)
    if m:
        subject = re.sub(r"^(3d (obj|model|object) )", "", m.group(1)).strip()
        hits.append({"field": "subject", "value": subject, "because": m.group(0).strip()})

    styles = [s for s, pat in STYLES.items() if re.search(pat, low)]
    mats = sorted({w for w in MATERIALS if re.search(r"\b%s\b" % w, low)})
    effects = [e for e, pat in EFFECTS.items() if re.search(pat, low)]
    motions = [w for w in MOTIONS if re.search(r"\b%s\b" % w, low)]
    colors = [c for c in COLORS if re.search(r"\b%s\b" % c, low)]
    wants = [w for w, pat in (("textures", r"textur"), ("shaders", r"shader"), ("loop", r"\bloop"),
                              ("mesh", r"\bmesh|\bobj\b|polygon"), ("animation", r"animat")) if re.search(pat, low)]
    for f, vals in (("styles", styles), ("materials", mats), ("effects", effects), ("motions", motions),
                    ("colors", colors), ("deliverables", wants)):
        if vals:
            hits.append({"field": f, "value": vals, "because": ", ".join(vals)})

    name = (subject or kind).strip()
    name = " ".join(w.capitalize() for w in name.split()[:5])
    if styles and styles[0].replace("-", " ") not in name.lower().replace("-", " "):
        name += " · " + styles[0].upper()
    complexity = min(100, 18 + len(text) // 6 + 9 * (len(effects) + len(motions)) + 6 * len(mats))

    return {
        "kind": kind, "subject": subject, "name": name, "poly_budget": budget, "styles": styles,
        "materials": mats, "effects": effects, "motions": motions, "colors": colors, "deliverables": wants,
        "complexity": complexity, "explain": hits, "kind_scores": scores,
        "pipeline": [{"stage": s, "state": "pending"} for s in PIPELINES[kind]],
    }
