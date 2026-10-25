"""The Vault: SQLite catalogue + content-addressed project folders on disk.

Layout
    vault/
      projects/<slug>/            one bundle per request (manifest.json + typed subfolders)
      inbox/<slug>.request.json   queued prompts waiting for a generator
    thecreator.db                 catalogue (projects, assets, dependencies, tags, folders, history)
"""
import hashlib
import json
import mimetypes
import os
import re
import shutil
import sqlite3
import threading
import time
import uuid

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VAULT = os.path.join(ROOT, "vault")
PROJECTS = os.path.join(VAULT, "projects")
INBOX = os.path.join(VAULT, "inbox")
DB_PATH = os.path.join(ROOT, "thecreator.db")

mimetypes.add_type("text/plain", ".obj")
mimetypes.add_type("text/plain", ".mtl")
mimetypes.add_type("text/x-glsl", ".glsl")
mimetypes.add_type("text/x-glsl", ".vert")
mimetypes.add_type("text/x-glsl", ".frag")
mimetypes.add_type("model/gltf+json", ".gltf")
mimetypes.add_type("application/x-font-bdf", ".bdf")

SCHEMA = """
CREATE TABLE IF NOT EXISTS folders (
  id TEXT PRIMARY KEY, name TEXT NOT NULL, color TEXT DEFAULT '#8b5cf6', icon TEXT DEFAULT 'folder',
  parent_id TEXT, position INTEGER DEFAULT 0, created_at REAL
);
CREATE TABLE IF NOT EXISTS projects (
  id TEXT PRIMARY KEY, slug TEXT UNIQUE, name TEXT, prompt TEXT, kind TEXT, status TEXT,
  folder_id TEXT, favorite INTEGER DEFAULT 0, pinned INTEGER DEFAULT 0, archived INTEGER DEFAULT 0,
  locked INTEGER DEFAULT 0, rating INTEGER DEFAULT 0, color_label TEXT, notes TEXT DEFAULT '',
  spec_json TEXT, stats_json TEXT, pipeline_json TEXT, render_json TEXT, variants_json TEXT,
  thumbnail TEXT, sprite TEXT, version INTEGER DEFAULT 1, views INTEGER DEFAULT 0,
  created_at REAL, updated_at REAL, opened_at REAL, deleted_at REAL
);
CREATE TABLE IF NOT EXISTS assets (
  id TEXT PRIMARY KEY, project_id TEXT, kind TEXT, role TEXT, name TEXT, path TEXT,
  mime TEXT, size INTEGER, sha256 TEXT, meta_json TEXT, variant TEXT, created_at REAL
);
CREATE TABLE IF NOT EXISTS dependencies (
  project_id TEXT, from_asset TEXT, to_asset TEXT, relation TEXT
);
CREATE TABLE IF NOT EXISTS tags (project_id TEXT, tag TEXT, PRIMARY KEY (project_id, tag));
CREATE TABLE IF NOT EXISTS activity (
  id INTEGER PRIMARY KEY AUTOINCREMENT, project_id TEXT, action TEXT, detail TEXT, at REAL
);
CREATE TABLE IF NOT EXISTS versions (
  id INTEGER PRIMARY KEY AUTOINCREMENT, project_id TEXT, version INTEGER, note TEXT,
  snapshot_json TEXT, at REAL
);
CREATE INDEX IF NOT EXISTS idx_assets_project ON assets(project_id);
CREATE INDEX IF NOT EXISTS idx_deps_project ON dependencies(project_id);
CREATE INDEX IF NOT EXISTS idx_activity_project ON activity(project_id);
"""

KIND_BY_EXT = {
    ".obj": "mesh", ".gltf": "mesh", ".glb": "mesh", ".fbx": "mesh", ".mtl": "material",
    ".png": "texture", ".jpg": "texture", ".jpeg": "texture", ".webp": "texture",
    ".glsl": "shader", ".vert": "shader", ".frag": "shader", ".wgsl": "shader",
    ".ttf": "font", ".otf": "font", ".woff2": "font", ".bdf": "font",
}

_lock = threading.RLock()


def now():
    return time.time()


def slugify(text):
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:48] or "project"


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 16), b""):
            h.update(block)
    return h.hexdigest()


class Store:
    def __init__(self, db_path=DB_PATH):
        os.makedirs(PROJECTS, exist_ok=True)
        os.makedirs(INBOX, exist_ok=True)
        self.db = sqlite3.connect(db_path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)
        self.db.commit()

    # ------------------------------------------------------------------ helpers
    def q(self, sql, args=()):
        with _lock:
            return [dict(r) for r in self.db.execute(sql, args).fetchall()]

    def x(self, sql, args=()):
        with _lock:
            cur = self.db.execute(sql, args)
            self.db.commit()
            return cur

    def log(self, project_id, action, detail=""):
        self.x("INSERT INTO activity(project_id, action, detail, at) VALUES (?,?,?,?)", (project_id, action, detail, now()))

    def project_dir(self, slug):
        return os.path.join(PROJECTS, slug)

    def unique_slug(self, base):
        slug, n = slugify(base), 2
        while self.q("SELECT 1 FROM projects WHERE slug=?", (slug,)) or os.path.exists(self.project_dir(slug)):
            slug = "%s-%d" % (slugify(base), n)
            n += 1
        return slug

    # ------------------------------------------------------------------ projects
    def create_project(self, name, prompt, kind, spec, status="queued", slug=None, folder_id=None):
        pid = uuid.uuid4().hex[:12]
        slug = slug or self.unique_slug(name)
        os.makedirs(self.project_dir(slug), exist_ok=True)
        t = now()
        self.x("""INSERT INTO projects(id, slug, name, prompt, kind, status, folder_id, spec_json,
                  stats_json, pipeline_json, render_json, variants_json, created_at, updated_at)
                  VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
               (pid, slug, name, prompt, kind, status, folder_id, json.dumps(spec), "{}",
                json.dumps(spec.get("pipeline", [])), "{}", "[]", t, t))
        self.log(pid, "created", "Request registered: " + (prompt[:120] if prompt else name))
        return self.get_project(pid)

    def ingest_bundle(self, pid, bundle):
        """Register everything a generator produced: files, dependency edges, render recipe, stats."""
        p = self.get_project(pid)
        base = self.project_dir(p["slug"])
        self.x("DELETE FROM assets WHERE project_id=? AND kind != 'preview'", (pid,))   # previews survive a regen
        self.x("DELETE FROM dependencies WHERE project_id=?", (pid,))
        by_path = {}
        for f in bundle["files"]:
            aid = self.add_asset(pid, base, f["path"], f.get("kind"), f.get("role", ""), f.get("meta", {}),
                                 f.get("variant"), log=False)
            by_path[f["path"]] = aid
        for f in bundle["files"]:
            for dep in f.get("depends", []):
                if dep in by_path:
                    rel = "uses"
                    self.x("INSERT INTO dependencies VALUES (?,?,?,?)", (pid, by_path[f["path"]], by_path[dep], rel))
        manifest_path = os.path.join(base, "manifest.json")
        manifest = {k: v for k, v in bundle.items() if k != "files"}
        manifest["files"] = [{k: v for k, v in f.items()} for f in bundle["files"]]
        manifest["project"] = {"id": pid, "slug": p["slug"], "name": p["name"], "prompt": p["prompt"]}
        with open(manifest_path, "w") as fh:
            json.dump(manifest, fh, indent=2)
        mid = self.add_asset(pid, base, "manifest.json", "manifest", "bundle manifest", {}, None, log=False)
        for aid in by_path.values():
            self.x("INSERT INTO dependencies VALUES (?,?,?,?)", (pid, mid, aid, "contains"))
        spec = json.loads(p["spec_json"] or "{}")
        pipeline = bundle.get("pipeline") or spec.get("pipeline", [])
        self.x("""UPDATE projects SET status=?, stats_json=?, pipeline_json=?, render_json=?, variants_json=?,
                  updated_at=? WHERE id=?""",
               ("ready", json.dumps(bundle.get("stats", {})), json.dumps(pipeline), json.dumps(bundle.get("render", {})),
                json.dumps(bundle.get("variants", [])), now(), pid))
        self.snapshot(pid, "Generated bundle (%d files)" % len(bundle["files"]))
        self.log(pid, "generated", "%d files ingested into the vault" % (len(bundle["files"]) + 1))

    def add_asset(self, pid, base, rel, kind=None, role="", meta=None, variant=None, log=True):
        full = os.path.join(base, rel)
        ext = os.path.splitext(rel)[1].lower()
        kind = kind or KIND_BY_EXT.get(ext, "data")
        aid = uuid.uuid4().hex[:12]
        self.x("DELETE FROM assets WHERE project_id=? AND path=?", (pid, rel))
        self.x("""INSERT INTO assets(id, project_id, kind, role, name, path, mime, size, sha256, meta_json, variant, created_at)
                  VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
               (aid, pid, kind, role, os.path.basename(rel), rel, mimetypes.guess_type(rel)[0] or "application/octet-stream",
                os.path.getsize(full), sha256_file(full), json.dumps(meta or {}), variant, now()))
        if log:
            self.log(pid, "asset added", rel)
            self.touch(pid)
        return aid

    def touch(self, pid):
        self.x("UPDATE projects SET updated_at=? WHERE id=?", (now(), pid))

    def snapshot(self, pid, note):
        p = self.get_project(pid)
        assets = self.q("SELECT path, sha256, size FROM assets WHERE project_id=?", (pid,))
        ver = (self.q("SELECT MAX(version) v FROM versions WHERE project_id=?", (pid,))[0]["v"] or 0) + 1
        snap = {"name": p["name"], "status": p["status"], "assets": assets}
        self.x("INSERT INTO versions(project_id, version, note, snapshot_json, at) VALUES (?,?,?,?,?)",
               (pid, ver, note, json.dumps(snap), now()))
        self.x("UPDATE projects SET version=? WHERE id=?", (ver, pid))
        return ver

    def get_project(self, pid):
        rows = self.q("SELECT * FROM projects WHERE id=? OR slug=?", (pid, pid))
        return rows[0] if rows else None

    def project_summary(self, p):
        a = self.q("SELECT COUNT(*) n, COALESCE(SUM(size),0) s FROM assets WHERE project_id=?", (p["id"],))[0]
        kinds = self.q("SELECT kind, COUNT(*) n FROM assets WHERE project_id=? GROUP BY kind", (p["id"],))
        tags = [r["tag"] for r in self.q("SELECT tag FROM tags WHERE project_id=? ORDER BY tag", (p["id"],))]
        out = dict(p)
        for k in ("spec_json", "stats_json", "pipeline_json", "render_json", "variants_json"):
            out[k[:-5]] = json.loads(out.pop(k) or "null")
        out.update(file_count=a["n"], size=a["s"], tags=tags, kinds={r["kind"]: r["n"] for r in kinds})
        return out

    def list_projects(self):
        return [self.project_summary(p) for p in self.q("SELECT * FROM projects ORDER BY pinned DESC, created_at DESC")]

    def project_detail(self, pid):
        p = self.get_project(pid)
        if not p:
            return None
        out = self.project_summary(p)
        out["assets"] = [dict(a, meta=json.loads(a.pop("meta_json") or "{}")) for a in
                         self.q("SELECT * FROM assets WHERE project_id=? ORDER BY kind, path", (p["id"],))]
        out["dependencies"] = self.q("SELECT from_asset, to_asset, relation FROM dependencies WHERE project_id=?", (p["id"],))
        out["versions"] = self.q("SELECT version, note, at FROM versions WHERE project_id=? ORDER BY version DESC", (p["id"],))
        out["activity"] = self.q("SELECT action, detail, at FROM activity WHERE project_id=? ORDER BY at DESC LIMIT 60", (p["id"],))
        return out

    UPDATABLE = {"name", "favorite", "pinned", "archived", "locked", "rating", "color_label", "notes", "folder_id"}

    def update_project(self, pid, fields):
        p = self.get_project(pid)
        fields = {k: v for k, v in fields.items() if k in self.UPDATABLE}
        if not fields:
            return self.project_summary(p)
        sets = ", ".join("%s=?" % k for k in fields)
        self.x("UPDATE projects SET %s, updated_at=? WHERE id=?" % sets, (*fields.values(), now(), p["id"]))
        for k, v in fields.items():
            label = {"favorite": "favourite " + ("on" if v else "off"), "pinned": "pin " + ("on" if v else "off"),
                     "archived": "archived" if v else "unarchived", "locked": "locked" if v else "unlocked",
                     "rating": "rated %s/5" % v, "folder_id": "moved to " + self.folder_name(v),
                     "name": "renamed to " + str(v), "notes": "notes edited", "color_label": "label " + str(v)}[k]
            self.log(p["id"], "updated", label)
        return self.project_summary(self.get_project(p["id"]))

    def folder_name(self, fid):
        r = self.q("SELECT name FROM folders WHERE id=?", (fid,))
        return r[0]["name"] if r else "Library root"

    def set_tags(self, pid, tags):
        p = self.get_project(pid)
        self.x("DELETE FROM tags WHERE project_id=?", (p["id"],))
        for t in sorted({t.strip().lower() for t in tags if t.strip()}):
            self.x("INSERT INTO tags VALUES (?,?)", (p["id"], t))
        self.log(p["id"], "tagged", ", ".join(tags))

    def trash(self, pid):
        p = self.get_project(pid)
        if p["locked"]:
            raise PermissionError("Project is locked")
        self.x("UPDATE projects SET deleted_at=? WHERE id=?", (now(), p["id"]))
        self.log(p["id"], "trashed", "Moved to trash")

    def restore(self, pid):
        self.x("UPDATE projects SET deleted_at=NULL WHERE id=?", (pid,))
        self.log(pid, "restored", "Restored from trash")

    def purge(self, pid):
        p = self.get_project(pid)
        if p["locked"]:
            raise PermissionError("Project is locked")
        shutil.rmtree(self.project_dir(p["slug"]), ignore_errors=True)
        for t in ("assets", "dependencies", "tags", "versions"):
            self.x("DELETE FROM %s WHERE project_id=?" % t, (p["id"],))
        self.x("DELETE FROM projects WHERE id=?", (p["id"],))
        self.log(p["id"], "purged", p["name"])

    def duplicate(self, pid):
        p = self.get_project(pid)
        slug = self.unique_slug(p["slug"] + "-copy")
        shutil.copytree(self.project_dir(p["slug"]), self.project_dir(slug))
        nid = uuid.uuid4().hex[:12]
        t = now()
        cols = [c for c in p.keys() if c not in ("id", "slug", "name", "created_at", "updated_at", "views", "opened_at")]
        self.x("INSERT INTO projects(id, slug, name, created_at, updated_at, %s) VALUES (?,?,?,?,?,%s)"
               % (", ".join(cols), ", ".join("?" * len(cols))),
               (nid, slug, p["name"] + " (copy)", t, t, *[p[c] for c in cols]))
        idmap = {}
        for a in self.q("SELECT * FROM assets WHERE project_id=?", (p["id"],)):
            idmap[a["id"]] = uuid.uuid4().hex[:12]
            a.update(id=idmap[a["id"]], project_id=nid)
            self.x("INSERT INTO assets(%s) VALUES (%s)" % (", ".join(a), ", ".join("?" * len(a))), tuple(a.values()))
        for d in self.q("SELECT * FROM dependencies WHERE project_id=?", (p["id"],)):
            self.x("INSERT INTO dependencies VALUES (?,?,?,?)", (nid, idmap.get(d["from_asset"]), idmap.get(d["to_asset"]), d["relation"]))
        for t_ in self.q("SELECT tag FROM tags WHERE project_id=?", (p["id"],)):
            self.x("INSERT INTO tags VALUES (?,?)", (nid, t_["tag"]))
        self.x("UPDATE projects SET favorite=0, pinned=0, locked=0 WHERE id=?", (nid,))
        self.snapshot(nid, "Duplicated from " + p["name"])
        self.log(nid, "duplicated", "Forked from " + p["name"])
        return self.project_summary(self.get_project(nid))

    def mark_opened(self, pid):
        self.x("UPDATE projects SET views=views+1, opened_at=? WHERE id=?", (now(), pid))

    def save_preview(self, pid, rel, data):
        p = self.get_project(pid)
        base = self.project_dir(p["slug"])
        os.makedirs(os.path.join(base, "preview"), exist_ok=True)
        with open(os.path.join(base, rel), "wb") as f:
            f.write(data)
        self.add_asset(p["id"], base, rel, "preview", "turntable sprite" if "sprite" in rel else "thumbnail", {}, log=False)
        col = "sprite" if "sprite" in rel else "thumbnail"
        self.x("UPDATE projects SET %s=? WHERE id=?" % col, ("/vault/projects/%s/%s?v=%d" % (p["slug"], rel, int(now())), p["id"]))

    # ------------------------------------------------------------------ folders
    def folders(self):
        rows = self.q("SELECT * FROM folders ORDER BY position, name")
        counts = {r["folder_id"]: r["n"] for r in self.q(
            "SELECT folder_id, COUNT(*) n FROM projects WHERE deleted_at IS NULL GROUP BY folder_id")}
        for r in rows:
            r["count"] = counts.get(r["id"], 0)
        return rows

    def create_folder(self, name, color="#8b5cf6", icon="folder"):
        fid = uuid.uuid4().hex[:10]
        n = len(self.q("SELECT id FROM folders"))
        self.x("INSERT INTO folders VALUES (?,?,?,?,?,?,?)", (fid, name, color, icon, None, n, now()))
        return fid

    def update_folder(self, fid, fields):
        for k in ("name", "color", "icon"):
            if k in fields:
                self.x("UPDATE folders SET %s=? WHERE id=?" % k, (fields[k], fid))

    def delete_folder(self, fid):
        self.x("UPDATE projects SET folder_id=NULL WHERE folder_id=?", (fid,))
        self.x("DELETE FROM folders WHERE id=?", (fid,))

    # ------------------------------------------------------------------ insight
    def all_assets(self):
        return self.q("""SELECT a.*, p.name project_name, p.slug FROM assets a JOIN projects p ON p.id=a.project_id
                         WHERE p.deleted_at IS NULL ORDER BY p.created_at, a.kind, a.path""")

    def stats(self):
        live = "FROM projects WHERE deleted_at IS NULL"
        s = {
            "projects": self.q("SELECT COUNT(*) n " + live)[0]["n"],
            "trash": self.q("SELECT COUNT(*) n FROM projects WHERE deleted_at IS NOT NULL")[0]["n"],
            "queued": self.q("SELECT COUNT(*) n " + live + " AND status='queued'")[0]["n"],
            "assets": self.q("SELECT COUNT(*) n FROM assets")[0]["n"],
            "bytes": self.q("SELECT COALESCE(SUM(size),0) s FROM assets")[0]["s"],
            "by_kind": self.q("SELECT kind, COUNT(*) n, SUM(size) bytes FROM assets GROUP BY kind ORDER BY bytes DESC"),
            "duplicates": self.q("""SELECT sha256, COUNT(*) n, MAX(size) size, GROUP_CONCAT(path, ' | ') paths FROM assets
                                    GROUP BY sha256 HAVING n > 1 ORDER BY size DESC LIMIT 20"""),
            "triangles": 0,
        }
        for p in self.q("SELECT stats_json " + live):
            s["triangles"] += (json.loads(p["stats_json"] or "{}") or {}).get("triangles", 0)
        return s

    def activity(self, limit=80):
        return self.q("""SELECT a.*, p.name project_name FROM activity a LEFT JOIN projects p ON p.id=a.project_id
                         ORDER BY a.at DESC LIMIT ?""", (limit,))

    def integrity(self):
        """Re-hash every file on disk and compare with the catalogue; also find orphans."""
        report = {"ok": 0, "modified": [], "missing": [], "orphans": [], "checked_at": now()}
        known = set()
        for a in self.all_assets():
            full = os.path.join(self.project_dir(a["slug"]), a["path"])
            known.add(os.path.normpath(full))
            if not os.path.exists(full):
                report["missing"].append(a["slug"] + "/" + a["path"])
            elif sha256_file(full) != a["sha256"]:
                report["modified"].append(a["slug"] + "/" + a["path"])
            else:
                report["ok"] += 1
        live = {p["slug"] for p in self.q("SELECT slug FROM projects WHERE deleted_at IS NULL")}
        for slug in os.listdir(PROJECTS):
            if slug not in live:
                continue
            for dp, _, files in os.walk(self.project_dir(slug)):
                for fn in files:
                    full = os.path.normpath(os.path.join(dp, fn))
                    if full not in known:
                        report["orphans"].append(os.path.relpath(full, PROJECTS))
        return report

    def rescan(self, pid):
        """Register orphan files dropped into a project folder by hand (or by an external tool)."""
        p = self.get_project(pid)
        base = self.project_dir(p["slug"])
        known = {a["path"] for a in self.q("SELECT path FROM assets WHERE project_id=?", (p["id"],))}
        added = []
        for dp, _, files in os.walk(base):
            for fn in files:
                rel = os.path.relpath(os.path.join(dp, fn), base)
                if rel not in known and not fn.startswith("."):
                    self.add_asset(p["id"], base, rel)
                    added.append(rel)
        return added

    def table(self, name, limit=500):
        if name not in ("projects", "assets", "dependencies", "tags", "folders", "activity", "versions"):
            raise KeyError(name)
        cols = [r["name"] for r in self.q("PRAGMA table_info(%s)" % name)]
        rows = self.q("SELECT * FROM %s ORDER BY rowid DESC LIMIT ?" % name, (limit,))
        return {"columns": cols, "rows": rows, "total": self.q("SELECT COUNT(*) n FROM %s" % name)[0]["n"]}
