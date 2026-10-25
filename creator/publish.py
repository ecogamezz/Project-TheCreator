"""Portable bundles: export a creation (files + its catalogue record) as a ZIP, publish ZIPs to a GitHub Release,
and import them back into any vault.

The ZIP layout is  <slug>/...files...  plus  <slug>/project.json  (name, prompt, spec, tags, render, variants, ...).
"""
import io
import json
import os
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.request
import uuid
import zipfile

from .store import PROJECTS, now

RECORD_FIELDS = ("name", "prompt", "kind", "status", "rating", "color_label", "notes", "spec_json", "stats_json",
                 "pipeline_json", "render_json", "variants_json", "version", "created_at")
RELEASE_TAG = "creations"


def export_zip(store, pid):
    p = store.get_project(pid)
    base = store.project_dir(p["slug"])
    record = {k: p[k] for k in RECORD_FIELDS}
    record["slug"] = p["slug"]
    record["tags"] = [t["tag"] for t in store.q("SELECT tag FROM tags WHERE project_id=?", (p["id"],))]
    record["format"] = "thecreator-bundle/1"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for dp, _, files in os.walk(base):
            for fn in sorted(files):
                full = os.path.join(dp, fn)
                z.write(full, os.path.join(p["slug"], os.path.relpath(full, base)))
        z.writestr(os.path.join(p["slug"], "project.json"), json.dumps(record, indent=2))
    return p, buf.getvalue()


def import_zip(store, source, folder_id=None):
    """source: path or http(s) URL of a bundle ZIP. Returns the new project summary."""
    if source.startswith(("http://", "https://")):
        try:
            with urllib.request.urlopen(source) as r:
                data = r.read()
        except urllib.error.URLError:
            # python.org builds on macOS ship without root certificates; curl uses the system store
            data = subprocess.run(["curl", "-fsSL", source], capture_output=True, check=True).stdout
    else:
        with open(source, "rb") as f:
            data = f.read()
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        names = z.namelist()
        root = names[0].split("/")[0]
        rec = json.loads(z.read(root + "/project.json"))
        slug = store.unique_slug(rec.get("slug") or root)
        dest = store.project_dir(slug)
        with tempfile.TemporaryDirectory() as tmp:
            for n in names:
                if n.endswith("/") or ".." in n.split("/") or n.startswith("/"):
                    continue
                z.extract(n, tmp)
            shutil.move(os.path.join(tmp, root), dest)
    os.remove(os.path.join(dest, "project.json"))
    pid = uuid.uuid4().hex[:12]
    t = now()
    store.x("""INSERT INTO projects(id, slug, name, prompt, kind, status, folder_id, rating, color_label, notes, spec_json,
               stats_json, pipeline_json, render_json, variants_json, version, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (pid, slug, rec["name"], rec["prompt"], rec["kind"], rec.get("status", "ready"), folder_id, rec.get("rating", 0),
             rec.get("color_label"), rec.get("notes", ""), rec["spec_json"], rec["stats_json"], rec["pipeline_json"],
             rec["render_json"], rec["variants_json"], rec.get("version", 1), rec.get("created_at", t), t))
    store.rescan(pid)
    for rel in ("preview/thumbnail.png", "preview/turntable_sprite.png"):
        if os.path.exists(os.path.join(dest, rel)):
            col = "sprite" if "sprite" in rel else "thumbnail"
            store.x("UPDATE assets SET kind='preview' WHERE project_id=? AND path=?", (pid, rel))
            store.x("UPDATE projects SET %s=? WHERE id=?" % col, ("/vault/projects/%s/%s" % (slug, rel), pid))
    store.set_tags(pid, rec.get("tags", []))
    store.snapshot(pid, "Imported from bundle")
    store.log(pid, "imported", source if len(source) < 200 else "bundle")
    return store.project_summary(store.get_project(pid))


def _gh(*args, check=True):
    return subprocess.run(["gh", *args], capture_output=True, text=True, check=check)


def publish(store, slugs, repo=None, log=print):
    """Upload bundle ZIPs as assets of the 'creations' GitHub Release (created on first use)."""
    repo_args = ["--repo", repo] if repo else []
    if _gh("release", "view", RELEASE_TAG, *repo_args, check=False).returncode != 0:
        _gh("release", "create", RELEASE_TAG, *repo_args, "--title", "Creations",
            "--notes", "Bundles exported from the Project-TheCreator vault. Import one with:\n\n"
                       "    python3 cli.py import <asset URL or .zip>\n")
    urls = []
    with tempfile.TemporaryDirectory() as tmp:
        for slug in slugs:
            p, data = export_zip(store, slug)
            path = os.path.join(tmp, p["slug"] + ".zip")
            with open(path, "wb") as f:
                f.write(data)
            _gh("release", "upload", RELEASE_TAG, path, "--clobber", *repo_args)
            store.log(p["id"], "published", "GitHub release asset %s.zip (%d KB)" % (p["slug"], len(data) // 1024))
            log("· %-30s %8d KB" % (p["slug"], len(data) // 1024))
            urls.append(p["slug"] + ".zip")
    return urls
