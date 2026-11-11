"""Shared helpers for the local-ocr scripts. Standard library only.

A job is a folder:
    job.json      settings, the page list, runs, notes (see references/api_reference.md)
    pages/        one image per page (made by prepare.py)
    rows.jsonl    one line per page read (written by the run_*.py scripts; resumable)
    export/       files made by export.py
    report.md     made by report.py
"""
from __future__ import annotations

import argparse
import html
import json
import os
import platform
import re
import shutil
import signal
import subprocess
import sys
import time
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable

SKILL_VERSION = "1.1.0"
HOME = Path(os.environ.get("LOCAL_OCR_HOME", Path.home() / ".cache" / "local-ocr")).expanduser()
REGISTRY = HOME / "registry.json"
MODELS_DIR = HOME / "models"


# ---------- jobs ----------

def load_job(job: Path) -> dict[str, Any]:
    f = Path(job) / "job.json"
    if not f.exists():
        raise SystemExit(f"{job} is not a job folder (no job.json). Make one with prepare.py.")
    return json.loads(f.read_text(encoding="utf-8"))


def save_job(job: Path, data: dict[str, Any]) -> None:
    f = Path(job) / "job.json"
    tmp = f.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(f)


def read_rows(job: Path, repair: bool = False) -> dict[str, dict[str, Any]]:
    """Rows by page id. The last row for a page wins. repair=True cuts a half-written last line."""
    f = Path(job) / "rows.jsonl"
    if not f.exists():
        return {}
    text = f.read_text(encoding="utf-8")
    if repair and text and not text.endswith("\n"):
        text = text[: text.rfind("\n") + 1]
        f.write_text(text, encoding="utf-8")
    rows: dict[str, dict[str, Any]] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue  # a half line from a killed run
        rows[row["page"]] = row
    return rows


def append_row(job: Path, row: dict[str, Any]) -> None:
    with open(Path(job) / "rows.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def todo_pages(job: Path, data: dict[str, Any], limit: int | None = None, redo: set[str] | None = None,
               skip_blank: bool = False) -> list[dict[str, Any]]:
    """Pages still to read. Pages with an error row are read again.

    redo (--pages): read only these pages, also when they were read before.
    """
    rows = read_rows(job, repair=True)
    only = redo is not None
    redo = redo or set()
    out = []
    for p in data["pages"]:
        r = rows.get(p["id"])
        if not p.get("file"):  # prepare.py could not render this page
            if r is None:
                append_row(job, {"page": p["id"], "status": "error", "blocks": [], "seconds": 0,
                                 "model": data.get("model"), "error": p.get("error", "no page image")})
            continue
        if only and p["id"] not in redo:
            continue
        if p["id"] in redo or r is None or r.get("status") == "error":
            if skip_blank and p.get("blank") and p["id"] not in redo:
                if r is None:
                    append_row(job, {"page": p["id"], "status": "skipped_blank", "blocks": [], "seconds": 0,
                                     "model": data.get("model"), "note": "page looks blank; not sent to the model"})
                continue
            out.append(p)
    return out[:limit] if limit is not None else out


def start_run(job: Path, model: str, backend: str, versions: dict[str, str]) -> int:
    data = load_job(job)
    data.setdefault("runs", []).append({
        "model": model, "backend": backend, "versions": versions, "machine": machine_summary(),
        "started": now(), "ended": None, "pages_read": 0, "skill_version": SKILL_VERSION,
    })
    save_job(job, data)
    return len(data["runs"]) - 1


def end_run(job: Path, index: int, pages_read: int, outcome: str) -> None:
    data = load_job(job)
    run = data["runs"][index]
    run.update(ended=now(), pages_read=pages_read, outcome=outcome)
    save_job(job, data)


def run_pages(job: Path, model: str, backend: str, versions: dict[str, str], pages: list[dict[str, Any]],
              read: Callable[[Path, dict[str, Any]], dict[str, Any]]) -> None:
    """Read each page with read(image_path, page) and append its row. Safe to stop at any time."""
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(143))  # so the finally block and atexit hooks run
    index = start_run(job, model, backend, versions)
    done, outcome = 0, "stopped"
    try:
        for n, p in enumerate(pages, 1):
            t = time.time()
            try:
                row = read(Path(job) / p["file"], p)
            except (OSError, ValueError) as e:  # a bad image; model errors still stop the run
                row = {"status": "error", "blocks": [], "error": f"{type(e).__name__}: {e}"}
            row = {"page": p["id"], "model": model, "backend": backend,
                   "seconds": round(time.time() - t, 1), **row}
            row.setdefault("status", "ok")
            append_row(job, row)
            done += 1
            chars = sum(len(b.get("text") or "") for b in row.get("blocks", []))
            print(f"{n}/{len(pages)} page {p['id']} ({p['doc']} p.{p['doc_page']}) "
                  f"{row['seconds']}s {chars} chars {row['status']}", flush=True)
        outcome = "finished"
    finally:
        end_run(job, index, done, outcome)
    print(f"DONE {done} pages", flush=True)


def runner_args(description: str, backends: list[str]) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=description, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("job", type=Path)
    ap.add_argument("--backend", choices=["auto", *backends], default="auto")
    ap.add_argument("--limit", type=int, help="read at most N of the unread pages, then stop (smoke test)")
    ap.add_argument("--pages", help="read ONLY these page ids, also if they were read before, e.g. 12,40 or "
                                    "00012,00040 or 12-15")
    ap.add_argument("--setup", action="store_true", help="install, download and load the model, then stop")
    return ap.parse_args()


def page_ids(spec: str | None, data: dict[str, Any] | None = None) -> set[str] | None:
    """--pages value to a set of page ids: '12,40', '00012', '12-15'. None when not given."""
    if not spec:
        return None
    out: set[str] = set()
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        lo, _, hi = part.partition("-")
        if hi and lo.isdigit() and hi.isdigit():
            out.update(f"{n:05d}" for n in range(int(lo), int(hi) + 1))
        else:
            out.add(part.zfill(5) if part.isdigit() else part)
    if data is not None:
        known = {p["id"] for p in data["pages"]}
        unknown = sorted(out - known)
        if unknown:
            print(f"--pages: not in this job: {', '.join(unknown[:10])}. Page ids are the 5-digit numbers in "
                  "pages/ and in the report.", file=sys.stderr)
    return out


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


# ---------- registry of jobs on this machine ----------

def registry() -> dict[str, Any]:
    if REGISTRY.exists():
        try:
            return json.loads(REGISTRY.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {"jobs": {}}


def register_job(job: Path, data: dict[str, Any]) -> None:
    HOME.mkdir(parents=True, exist_ok=True)
    reg = registry()
    reg["jobs"][str(Path(job).resolve())] = {"name": data["name"], "model": data.get("model"),
                                             "created": data.get("created"), "pages": len(data["pages"])}
    REGISTRY.write_text(json.dumps(reg, ensure_ascii=False, indent=2), encoding="utf-8")


def job_progress(job: Path) -> dict[str, Any]:
    data = load_job(job)
    rows = read_rows(job)
    counts: dict[str, int] = {}
    for p in data["pages"]:
        r = rows.get(p["id"])
        s = r.get("status", "ok") if r else "todo"
        counts[s] = counts.get(s, 0) + 1
    secs = sorted(r["seconds"] for r in rows.values() if r.get("status") in ("ok", "loop", "slow") and r.get("seconds"))
    median = secs[len(secs) // 2] if secs else None
    todo = counts.get("todo", 0) + counts.get("error", 0)
    return {"name": data["name"], "model": data.get("model"), "pages": len(data["pages"]), "counts": counts,
            "median_seconds": median, "eta_hours": round(todo * median / 3600, 1) if median else None,
            "last_run": (data.get("runs") or [{}])[-1]}


# ---------- the machine ----------

def run_cmd(cmd: list[str], timeout: int = 10) -> str:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def nvidia_gpus() -> list[dict[str, Any]]:
    if not shutil.which("nvidia-smi"):
        return []
    out = run_cmd(["nvidia-smi", "--query-gpu=name,memory.total,memory.free", "--format=csv,noheader,nounits"])
    gpus = []
    for line in out.splitlines():
        parts = [x.strip() for x in line.split(",")]
        if len(parts) == 3:
            try:
                gpus.append({"name": parts[0], "vram_gb": round(int(parts[1]) / 1024, 1),
                             "free_gb": round(int(parts[2]) / 1024, 1)})
            except ValueError:
                pass
    return gpus


def ram_gb() -> float | None:
    system = platform.system()
    if system == "Darwin":
        v = run_cmd(["sysctl", "-n", "hw.memsize"])
        return round(int(v) / 1024**3, 1) if v.isdigit() else None
    if system == "Linux":
        try:
            for line in open("/proc/meminfo"):
                if line.startswith("MemTotal:"):
                    return round(int(line.split()[1]) / 1024**2, 1)
        except OSError:
            return None
    if system == "Windows":
        v = run_cmd(["powershell", "-NoProfile", "-Command",
                     "(Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory"])
        return round(int(v) / 1024**3, 1) if v.isdigit() else None
    return None


def chip_name() -> str:
    system = platform.system()
    if system == "Darwin":
        return run_cmd(["sysctl", "-n", "machdep.cpu.brand_string"]) or platform.processor()
    if system == "Linux":
        try:
            for line in open("/proc/cpuinfo"):
                if line.lower().startswith("model name"):
                    return line.split(":", 1)[1].strip()
        except OSError:
            pass
    return platform.processor() or platform.machine()


def apple_silicon() -> bool:
    return platform.system() == "Darwin" and platform.machine() == "arm64"


def machine_summary() -> dict[str, Any]:
    """What a field report may say about the machine. No user names, no paths."""
    return {"os": f"{platform.system()} {platform.release()}", "arch": platform.machine(), "chip": chip_name(),
            "cpu_cores": os.cpu_count(), "ram_gb": ram_gb(),
            "gpus": [{"name": g["name"], "vram_gb": g["vram_gb"]} for g in nvidia_gpus()],
            "python": platform.python_version()}


# ---------- model output -> blocks ----------

class _TextParser(HTMLParser):
    BREAK_AFTER = {"p", "div", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "table", "blockquote", "caption"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []

    def handle_starttag(self, tag: str, attrs: Any) -> None:
        if tag == "br":
            self.out.append("\n")
        elif tag in ("td", "th") and self.out and not self.out[-1].endswith("\n"):
            self.out.append("\t")
        elif tag == "img":
            alt = dict(attrs).get("alt")
            if alt:
                self.out.append(alt)

    def handle_endtag(self, tag: str) -> None:
        if tag in self.BREAK_AFTER:
            self.out.append("\n")

    def handle_data(self, data: str) -> None:
        self.out.append(data)


def html_to_text(fragment: str) -> str:
    p = _TextParser()
    p.feed(fragment or "")
    p.close()
    text = "".join(p.out)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


_DIV = re.compile(r'<div\s+data-bbox="([^"]*)"\s+data-label="([^"]*)"\s*>', re.I)


def chandra_blocks(raw: str, width: int, height: int, scale: int = 1000) -> list[dict[str, Any]]:
    """Chandra writes <div data-bbox="x0 y0 x1 y1" data-label="Text">…</div> blocks, boxes on a 0–scale grid.

    Returns blocks with boxes in image pixels. Divs are found by their opening tag; a block ends where
    the next block starts, so nested divs inside a block do not break it.
    """
    starts = list(_DIV.finditer(raw or ""))
    blocks = []
    for i, m in enumerate(starts):
        end = starts[i + 1].start() if i + 1 < len(starts) else len(raw)
        inner = raw[m.end():end]
        inner = re.sub(r"</div>\s*$", "", inner.strip())
        try:
            x0, y0, x1, y1 = (float(v) for v in m.group(1).split())
            bbox = [round(x0 / scale * width, 1), round(y0 / scale * height, 1),
                    round(x1 / scale * width, 1), round(y1 / scale * height, 1)]
        except ValueError:
            bbox = [0, 0, width, height]
        blocks.append({"label": norm_label(m.group(2)), "bbox": bbox, "html": inner, "text": html_to_text(inner)})
    if not blocks and (raw or "").strip():  # no layout divs at all: keep the text as one block
        blocks.append({"label": "Text", "bbox": [0, 0, width, height], "html": raw, "text": html_to_text(raw)})
    return blocks


LABELS = {
    "sectionheader": "SectionHeader", "section-header": "SectionHeader", "title": "Title", "text": "Text",
    "pageheader": "PageHeader", "page-header": "PageHeader", "pagefooter": "PageFooter",
    "page-footer": "PageFooter", "footnote": "Footnote", "caption": "Caption", "table": "Table",
    "picture": "Picture", "image": "Picture", "figure": "Picture", "listitem": "ListItem",
    "list-group": "ListItem", "list": "ListItem", "equation": "Equation", "equation-block": "Equation",
    "form": "Form", "code": "Code", "code-block": "Code", "handwriting": "Handwriting",
    "tableofcontents": "TableOfContents", "complex-block": "Text", "chemical-block": "Equation",
    "diagram": "Picture", "bibliography": "Text", "blank-page": "Blank",
}


def norm_label(label: str) -> str:
    """One label set for all models (Chandra, Surya and Indra spell some labels differently)."""
    key = (label or "Text").strip().lower().replace("_", "-").replace(" ", "")
    return LABELS.get(key, LABELS.get(key.replace("-", ""), (label or "Text").strip() or "Text"))


def esc(s: str) -> str:
    return html.escape(s or "", quote=True)
