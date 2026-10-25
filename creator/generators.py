"""Generator registry + the three founding requests."""
import json
import os
import time

import importlib
import re

from .prompt import interpret
from .store import INBOX, Store

# generator id -> module (imported lazily so one broken generator never blocks the others)
GENERATORS = {"sea-turtle": "gen_turtle", "ps2-beach": "gen_beach", "metal-cube": "gen_cube",
              "shield-texture": "gen_shield", "toon-water": "gen_toonwater", "ps2-bear": "gen_bear", "bomber": "gen_bomber"}

# Which generator picks up a queued prompt. First match wins; unmatched requests stay in the inbox.
MATCHERS = [
    (r"\bbear\b", "ps2-bear"),
    (r"bomber|airplane|aircraft|\bplane\b", "bomber"),
    (r"shield.*textur|textur.*shield|force ?field", "shield-texture"),
    (r"toon.*water|water.*shader", "toon-water"),
    (r"sea turtle", "sea-turtle"),
    (r"\bbeach\b", "ps2-beach"),
    (r"metal cube", "metal-cube"),
]

# Nicer names/tags for requests whose interpreted name is weak.
META = {
    "ps2-bear": ("Grizzly · PS2/PS1 Bear", ["character", "retro", "ps1", "animation-set"]),
    "bomber": ("Heavy Bomber · Turbulence Flight", ["vehicle", "aircraft", "90k-budget", "sky"]),
    "shield-texture": ("Hex Energy Shield · Loop", ["vfx", "loop", "alpha", "flipbook"]),
    "toon-water": ("Toon Water Shader", ["shader", "stylized", "water", "foam"]),
}


def generator_module(name):
    return importlib.import_module("creator." + GENERATORS[name])


def match_generator(prompt):
    low = prompt.lower()
    for rx, gen in MATCHERS:
        if re.search(rx, low):
            return gen
    return None

EXAMPLES = [
    {"generator": "sea-turtle", "name": "Crowned Sea Turtle", "folder": "Creatures", "tags": ["creature", "hero-asset", "gold", "15k-budget"],
     "color": "#f5b942", "prompt": "Create a 3d obj with textures and shaders of a sea turtle. Use 15000 polygons max for the mesh. golden crown on its head."},
    {"generator": "ps2-beach", "name": "Sunny Shores · PS2 Beach", "folder": "Environments", "tags": ["environment", "retro", "ps2", "particles"],
     "color": "#4fb3ff", "prompt": "Create a scene of a sandy beach with clean waves but playstation2 style. simple ps2 clouds and some wind particle effects"},
    {"generator": "metal-cube", "name": "Shatter Cube Loop", "folder": "Motion Lab", "tags": ["animation", "loop", "vfx", "metal"],
     "color": "#b03bff", "prompt": "Make a animation of a 3d metal cube that jumps, rotates and when it lands again some shards of it fall of like it took damage. "
                                   "Then after a bit they slowly and fadingly regenerate so the animation would loop. The texture of the cube is your choice "
                                   "but when it takes damage and shards fall of add a quick white flash to its texture and the fallen shards should have some "
                                   "special color on the inside of the fallen off parts."},
]

FOLDERS = [("Creatures", "#f5b942", "turtle"), ("Environments", "#4fb3ff", "palm"), ("Motion Lab", "#b03bff", "bolt"), ("Inbox", "#64748b", "inbox")]


def run_generator(store, project, generator):
    t0 = time.time()
    store.log(project["id"], "generating", "Generator '%s' started" % generator)
    base = store.project_dir(project["slug"])
    bundle = generator_module(generator).generate(base, json.loads(project["spec_json"] or "{}"))
    if os.path.exists(os.path.join(base, "request.brief.json")):
        bundle["files"].append({"path": "request.brief.json", "kind": "manifest", "role": "original request + interpreted spec"})
    bundle["generator"] = generator
    bundle["generated_in_s"] = round(time.time() - t0, 2)
    bundle["stats"]["generated_in_s"] = bundle["generated_in_s"]
    store.ingest_bundle(project["id"], bundle)
    return bundle


def seed(store=None, verbose=True):
    store = store or Store()
    folder_ids = {f["name"]: f["id"] for f in store.folders()}
    for name, color, icon in FOLDERS:
        if name not in folder_ids:
            folder_ids[name] = store.create_folder(name, color, icon)
    for ex in EXAMPLES:
        if store.q("SELECT 1 FROM projects WHERE name=?", (ex["name"],)):
            continue
        spec = interpret(ex["prompt"])
        spec["generator"] = ex["generator"]
        p = store.create_project(ex["name"], ex["prompt"], spec["kind"], spec, status="generating", folder_id=folder_ids[ex["folder"]])
        store.x("UPDATE projects SET color_label=? WHERE id=?", (ex["color"], p["id"]))
        if verbose:
            print("· generating %-28s" % ex["name"], end="", flush=True)
        b = run_generator(store, p, ex["generator"])
        store.set_tags(p["id"], ex["tags"])
        if verbose:
            print(" %3d files  %6.1fs  %s tris" % (len(b["files"]), b["generated_in_s"], format(b["stats"].get("triangles", 0), ",")))
    return store


def queue_request(store, prompt, folder_id=None):
    """A brand-new prompt: interpret it, create the project shell + a ticket in vault/inbox for a generator to pick up."""
    spec = interpret(prompt)
    p = store.create_project(spec["name"], prompt, spec["kind"], spec, status="queued", folder_id=folder_id)
    if spec["pipeline"]:
        spec["pipeline"][0]["state"] = "done"
        store.x("UPDATE projects SET pipeline_json=? WHERE id=?", (json.dumps(spec["pipeline"]), p["id"]))
    ticket = {"project_id": p["id"], "slug": p["slug"], "prompt": prompt, "spec": spec, "queued_at": time.time(),
              "deliver_to": "vault/projects/%s/" % p["slug"],
              "how_to_complete": "Write files into deliver_to, then run: python3 cli.py rescan %s" % p["slug"]}
    with open(os.path.join(INBOX, p["slug"] + ".request.json"), "w") as f:
        json.dump(ticket, f, indent=2)
    store.add_asset(p["id"], store.project_dir(p["slug"]), _write_brief(store, p, spec), "manifest", "request brief", log=False)
    return store.project_summary(store.get_project(p["id"]))


def _write_brief(store, p, spec):
    rel = "request.brief.json"
    with open(os.path.join(store.project_dir(p["slug"]), rel), "w") as f:
        json.dump({"prompt": p["prompt"], "spec": spec}, f, indent=2)
    return rel


def process_queue(store, only=None, log=print):
    """Worker: hand every queued request to the generator that matches it, ingest, close the ticket."""
    done = []
    for p in store.q("SELECT * FROM projects WHERE status IN ('queued', 'in-progress') AND deleted_at IS NULL ORDER BY created_at"):
        if only and only not in (p["slug"], p["id"]):
            continue
        spec = json.loads(p["spec_json"] or "{}")
        gen = spec.get("generator") or match_generator(p["prompt"] or "")
        if gen not in GENERATORS:
            log("· skip %-28s no generator yet -> stays in inbox" % p["slug"])
            continue
        spec["generator"] = gen
        store.x("UPDATE projects SET spec_json=?, status='generating' WHERE id=?", (json.dumps(spec), p["id"]))
        log("· %-28s -> %s" % (p["slug"], gen), end="", flush=True) if log is print else log(p["slug"] + " -> " + gen)
        try:
            b = run_generator(store, store.get_project(p["id"]), gen)
        except Exception as e:
            store.x("UPDATE projects SET status='queued' WHERE id=?", (p["id"],))
            store.log(p["id"], "failed", "%s: %s" % (gen, e))
            raise
        if gen in META:
            name, tags = META[gen]
            store.x("UPDATE projects SET name=? WHERE id=?", (name, p["id"]))
            store.set_tags(p["id"], tags)
        ticket = os.path.join(INBOX, p["slug"] + ".request.json")
        if os.path.exists(ticket):
            os.remove(ticket)
        if log is print:
            print("  %3d files  %6.1fs" % (len(b["files"]), b["generated_in_s"]))
        done.append(p["slug"])
    return done
