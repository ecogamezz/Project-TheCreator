#!/usr/bin/env python3
"""Project-TheCreator server: REST API over the vault + static web app.   python3 server.py [port]"""
import base64
import io
import json
import mimetypes
import os
import re
import sys
import traceback
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse

from creator.generators import GENERATORS, match_generator, process_queue, queue_request, run_generator, seed
from creator.prompt import interpret
from creator.publish import export_zip
from creator.store import PROJECTS, ROOT, Store

WEB = os.path.join(ROOT, "web")
store = Store()
if not store.q("SELECT 1 FROM projects LIMIT 1"):
    seed(store)

ROUTES = []


def route(method, pattern):
    def deco(fn):
        ROUTES.append((method, re.compile("^" + pattern + "$"), fn))
        return fn
    return deco


# ----------------------------------------------------------------------------- API

@route("GET", "/api/stats")
def api_stats(h, m, body):
    return store.stats()


@route("GET", "/api/projects")
def api_projects(h, m, body):
    return {"projects": store.list_projects(), "folders": store.folders()}


@route("GET", "/api/projects/([\\w-]+)")
def api_project(h, m, body):
    d = store.project_detail(m[1])
    if not d:
        raise KeyError(m[1])
    return d


@route("PATCH", "/api/projects/([\\w-]+)")
def api_update(h, m, body):
    return store.update_project(m[1], body)


@route("POST", "/api/projects/([\\w-]+)/open")
def api_open(h, m, body):
    store.mark_opened(m[1])
    return {"ok": True}


@route("POST", "/api/projects/([\\w-]+)/tags")
def api_tags(h, m, body):
    store.set_tags(m[1], body.get("tags", []))
    return store.project_summary(store.get_project(m[1]))


@route("POST", "/api/projects/([\\w-]+)/duplicate")
def api_dup(h, m, body):
    return store.duplicate(m[1])


@route("POST", "/api/projects/([\\w-]+)/snapshot")
def api_snapshot(h, m, body):
    return {"version": store.snapshot(m[1], body.get("note") or "Manual snapshot")}


@route("POST", "/api/projects/([\\w-]+)/regenerate")
def api_regen(h, m, body):
    p = store.get_project(m[1])
    gen = json.loads(p["spec_json"] or "{}").get("generator")
    if gen not in GENERATORS:
        raise ValueError("No built-in generator for this request yet - it waits in the inbox.")
    run_generator(store, p, gen)
    return store.project_summary(store.get_project(p["id"]))


@route("POST", "/api/projects/([\\w-]+)/rescan")
def api_rescan(h, m, body):
    return {"added": store.rescan(m[1])}


@route("DELETE", "/api/projects/([\\w-]+)")
def api_delete(h, m, body):
    if body.get("purge"):
        store.purge(m[1])
    else:
        store.trash(m[1])
    return {"ok": True}


@route("POST", "/api/projects/([\\w-]+)/restore")
def api_restore(h, m, body):
    store.restore(m[1])
    return {"ok": True}


@route("POST", "/api/projects/([\\w-]+)/preview")
def api_preview(h, m, body):
    for key, rel in (("thumbnail", "preview/thumbnail.png"), ("sprite", "preview/turntable_sprite.png")):
        if body.get(key):
            store.save_preview(m[1], rel, base64.b64decode(body[key].split(",", 1)[1]))
    return store.project_summary(store.get_project(m[1]))


@route("POST", "/api/projects/([\\w-]+)/assets")
def api_upload(h, m, body):
    p = store.get_project(m[1])
    name = os.path.basename(body["name"])
    kind = body.get("kind") or None
    sub = {"mesh": "meshes", "texture": "textures", "shader": "shaders", "font": "fonts", "animation": "animations"}.get(
        kind or store_kind(name), "uploads")
    rel = os.path.join(sub, name)
    full = os.path.join(store.project_dir(p["slug"]), rel)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "wb") as f:
        f.write(base64.b64decode(body["data"].split(",", 1)[-1]))
    store.add_asset(p["id"], store.project_dir(p["slug"]), rel, kind, "uploaded")
    if p["status"] == "queued":
        store.x("UPDATE projects SET status='in-progress' WHERE id=?", (p["id"],))
    return store.project_detail(p["id"])


def store_kind(name):
    from creator.store import KIND_BY_EXT
    return KIND_BY_EXT.get(os.path.splitext(name)[1].lower(), "data")


@route("GET", "/api/projects/([\\w-]+)/export.zip")
def api_export(h, m, body):
    p, data = export_zip(store, m[1])
    store.log(p["id"], "exported", "ZIP bundle (%d KB)" % (len(data) // 1024))
    return ("application/zip", data, p["slug"] + ".zip")


@route("GET", "/api/queue")
def api_queue(h, m, body):
    out = []
    for p in store.q("SELECT * FROM projects WHERE status IN ('queued', 'in-progress') AND deleted_at IS NULL ORDER BY created_at"):
        spec = json.loads(p["spec_json"] or "{}")
        out.append({"id": p["id"], "slug": p["slug"], "name": p["name"], "prompt": p["prompt"], "kind": p["kind"],
                    "generator": spec.get("generator") or match_generator(p["prompt"] or "")})
    return out


@route("POST", "/api/process")
def api_process(h, m, body):
    log = []
    done = process_queue(store, body.get("slug"), log=log.append)
    return {"done": done, "log": log}


@route("POST", "/api/parse")
def api_parse(h, m, body):
    return interpret(body.get("prompt", ""))


@route("POST", "/api/requests")
def api_request(h, m, body):
    return queue_request(store, body["prompt"], body.get("folder_id"))


@route("GET", "/api/folders")
def api_folders(h, m, body):
    return store.folders()


@route("POST", "/api/folders")
def api_folder_new(h, m, body):
    return {"id": store.create_folder(body["name"], body.get("color", "#8b5cf6"), body.get("icon", "folder"))}


@route("PATCH", "/api/folders/([\\w-]+)")
def api_folder_upd(h, m, body):
    store.update_folder(m[1], body)
    return {"ok": True}


@route("DELETE", "/api/folders/([\\w-]+)")
def api_folder_del(h, m, body):
    store.delete_folder(m[1])
    return {"ok": True}


@route("GET", "/api/assets")
def api_assets(h, m, body):
    return store.all_assets()


@route("GET", "/api/activity")
def api_activity(h, m, body):
    return store.activity()


@route("GET", "/api/integrity")
def api_integrity(h, m, body):
    return store.integrity()


@route("GET", "/api/db/(\\w+)")
def api_table(h, m, body):
    return store.table(m[1])


@route("GET", "/api/tree")
def api_tree(h, m, body):
    def walk(path):
        out = []
        for name in sorted(os.listdir(path)):
            full = os.path.join(path, name)
            if os.path.isdir(full):
                out.append({"name": name, "dir": True, "children": walk(full)})
            else:
                out.append({"name": name, "size": os.path.getsize(full)})
        return out
    return walk(os.path.dirname(PROJECTS))


# ----------------------------------------------------------------------------- HTTP plumbing

class Handler(BaseHTTPRequestHandler):
    server_version = "TheCreator/1.0"

    def log_message(self, fmt, *args):
        if "/api/" in str(args[0] if args else "") or "code %d" in fmt:
            sys.stderr.write("%s\n" % (fmt % args))

    def send(self, code, ctype, data, filename=None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store" if "json" in ctype else "no-cache")
        if filename:
            self.send_header("Content-Disposition", 'attachment; filename="%s"' % filename)
        self.end_headers()
        self.wfile.write(data)

    def handle_any(self, method):
        url = urlparse(self.path)
        path = unquote(url.path)
        if path.startswith("/api/"):
            body = {}
            n = int(self.headers.get("Content-Length") or 0)
            if n:
                body = json.loads(self.rfile.read(n) or b"{}")
            body.update({k: v[0] for k, v in parse_qs(url.query).items()})
            for meth, rx, fn in ROUTES:
                mt = rx.match(path)
                if meth == method and mt:
                    try:
                        res = fn(self, mt, body)
                        if isinstance(res, tuple):
                            return self.send(200, res[0], res[1], res[2])
                        return self.send(200, "application/json", json.dumps(res, default=str).encode())
                    except KeyError as e:
                        return self.send(404, "application/json", json.dumps({"error": "not found: %s" % e}).encode())
                    except PermissionError as e:
                        return self.send(423, "application/json", json.dumps({"error": str(e)}).encode())
                    except Exception as e:
                        traceback.print_exc()
                        return self.send(400, "application/json", json.dumps({"error": str(e)}).encode())
            return self.send(404, "application/json", b'{"error":"no route"}')
        if method != "GET":
            return self.send(405, "text/plain", b"method not allowed")
        if path.startswith("/vault/"):
            full = os.path.normpath(os.path.join(ROOT, path.lstrip("/")))
            root = os.path.join(ROOT, "vault")
        else:
            full = os.path.normpath(os.path.join(WEB, (path.lstrip("/") or "index.html")))
            root = WEB
            if not os.path.splitext(full)[1]:
                full = os.path.join(WEB, "index.html")
        if not full.startswith(root) or not os.path.isfile(full):
            return self.send(404, "text/plain", b"not found")
        ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
        if full.endswith((".vert", ".frag", ".glsl", ".obj", ".mtl", ".bdf")):
            ctype = "text/plain; charset=utf-8"
        with open(full, "rb") as f:
            self.send(200, ctype, f.read())

    def do_GET(self):
        self.handle_any("GET")

    def do_POST(self):
        self.handle_any("POST")

    def do_PATCH(self):
        self.handle_any("PATCH")

    def do_DELETE(self):
        self.handle_any("DELETE")


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 4747
    print("Project-TheCreator running on http://localhost:%d" % port)
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
