#!/usr/bin/env python3
"""Earlier and running OCR jobs on this machine. Standard library only.

    uv run jobs.py list                 # every job this machine knows, with progress
    uv run jobs.py status JOB           # pages by status, speed, time left, last run
    uv run jobs.py note JOB "text"      # log a problem or observation (goes into the report)
    uv run jobs.py forget JOB           # drop a job from the list (its folder is not touched)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import REGISTRY, job_progress, load_job, now, registry, save_job  # noqa: E402


def show(path: Path) -> None:
    p = job_progress(path)
    c = p["counts"]
    done = p["pages"] - c.get("todo", 0) - c.get("error", 0)
    print(f"{p['name']} ({p['model']}): {done}/{p['pages']} pages  {path}")
    print("  " + ", ".join(f"{k} {v}" for k, v in sorted(c.items())))
    if p["median_seconds"]:
        print(f"  median {p['median_seconds']} s per page" + (f", about {p['eta_hours']} h left" if p["eta_hours"] else ""))
    run = p["last_run"]
    if run:
        state = "running or killed" if not run.get("ended") else run.get("outcome", "")
        print(f"  last run: {run.get('model')}/{run.get('backend')} started {run.get('started')}, {state}, "
              f"{run.get('pages_read', 0)} pages")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    s = sub.add_parser("status"); s.add_argument("job", type=Path)
    n = sub.add_parser("note"); n.add_argument("job", type=Path); n.add_argument("text")
    f = sub.add_parser("forget"); f.add_argument("job", type=Path)
    a = ap.parse_args()

    if a.cmd == "list":
        jobs = registry()["jobs"]
        if not jobs:
            print("No jobs on this machine yet.")
        for path in jobs:
            if (Path(path) / "job.json").exists():
                show(Path(path))
            else:
                print(f"(folder gone) {path}")
    elif a.cmd == "status":
        show(a.job)
    elif a.cmd == "note":
        data = load_job(a.job)
        data.setdefault("notes", []).append({"time": now(), "text": a.text})
        save_job(a.job, data)
        print(f"noted ({len(data['notes'])} notes)")
    elif a.cmd == "forget":
        reg = registry()
        reg["jobs"].pop(str(a.job.resolve()), None)
        REGISTRY.write_text(json.dumps(reg, ensure_ascii=False, indent=2), encoding="utf-8")
        print("removed from the list; the folder is unchanged")


if __name__ == "__main__":
    main()
