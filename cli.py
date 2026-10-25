#!/usr/bin/env python3
"""Project-TheCreator command line.

  python3 cli.py seed                 generate + register the three founding examples
  python3 cli.py list                 table of every project in the vault
  python3 cli.py info <slug>          files, dependencies, stats of one project
  python3 cli.py request "<prompt>"   queue a new prompt (creates project shell + inbox ticket)
  python3 cli.py inbox                show queued tickets waiting for a generator
  python3 cli.py process [slug]       run the queue: matching generator builds each request, ticket closed
  python3 cli.py rescan <slug>        register files that were dropped into a project folder
  python3 cli.py regen <slug>         re-run the built-in generator of a project
  python3 cli.py integrity            re-hash the vault and report modified / missing / orphan files
  python3 cli.py publish <slug>|--all upload bundle ZIPs to the GitHub Release "creations" (needs gh)
  python3 cli.py import <zip|url>     add a published bundle ZIP to this vault
"""
import json
import os
import sys

from creator.generators import GENERATORS, process_queue, queue_request, run_generator, seed
from creator.publish import import_zip, publish
from creator.store import INBOX, Store


def human(n):
    for u in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return "%.1f %s" % (n, u) if u != "B" else "%d B" % n
        n /= 1024
    return "%.1f TB" % n


def main(argv):
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(__doc__)
        return
    cmd, args = argv[0], argv[1:]
    store = Store()
    if cmd == "seed":
        seed(store)
    elif cmd == "list":
        for p in store.list_projects():
            flag = "★" if p["favorite"] else " "
            print("%s %-30s %-10s %-9s %4d files %10s  %s" % (flag, p["name"][:30], p["kind"], p["status"], p["file_count"], human(p["size"]), p["slug"]))
    elif cmd == "info":
        d = store.project_detail(args[0])
        print(json.dumps({k: d[k] for k in ("name", "slug", "kind", "status", "prompt", "stats", "tags")}, indent=2))
        for a in d["assets"]:
            print("  %-9s %-46s %10s  %s" % (a["kind"], a["path"], human(a["size"]), a["sha256"][:12]))
    elif cmd == "request":
        p = queue_request(store, " ".join(args))
        print("queued %s (%s) -> vault/inbox/%s.request.json" % (p["name"], p["kind"], p["slug"]))
    elif cmd == "inbox":
        for fn in sorted(os.listdir(INBOX)):
            t = json.load(open(os.path.join(INBOX, fn)))
            print("· %-32s %-9s %s" % (t["slug"], t["spec"]["kind"], t["prompt"][:70]))
    elif cmd == "process":
        done = process_queue(store, args[0] if args else None)
        print("processed %d request(s)" % len(done))
    elif cmd == "rescan":
        added = store.rescan(args[0])
        p = store.get_project(args[0])
        if added and p["status"] == "queued":
            store.x("UPDATE projects SET status='ready' WHERE id=?", (p["id"],))
            store.snapshot(p["id"], "Delivered %d files" % len(added))
        print("registered %d new files" % len(added), *added, sep="\n  ")
    elif cmd == "regen":
        p = store.get_project(args[0])
        gen = json.loads(p["spec_json"]).get("generator")
        if gen not in GENERATORS:
            sys.exit("no built-in generator for %s" % p["slug"])
        run_generator(store, p, gen)
        print("regenerated", p["name"])
    elif cmd == "publish":
        slugs = [p["slug"] for p in store.list_projects() if not p["deleted_at"] and p["status"] == "ready"] if "--all" in args else args
        publish(store, slugs)
        print("published %d bundle(s) to the 'creations' release" % len(slugs))
    elif cmd == "import":
        p = import_zip(store, args[0])
        print("imported %s (%d files) -> vault/projects/%s" % (p["name"], p["file_count"], p["slug"]))
    elif cmd == "integrity":
        r = store.integrity()
        print("ok: %d  modified: %d  missing: %d  orphans: %d" % (r["ok"], len(r["modified"]), len(r["missing"]), len(r["orphans"])))
        for k in ("modified", "missing", "orphans"):
            for f in r[k]:
                print("  %-8s %s" % (k, f))
    else:
        sys.exit("unknown command %r\n%s" % (cmd, __doc__))


if __name__ == "__main__":
    main(sys.argv[1:])
