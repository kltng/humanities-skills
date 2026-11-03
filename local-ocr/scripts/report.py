#!/usr/bin/env python3
"""Write the run report for the user and a field report that is safe to post on GitHub.

    uv run report.py JOB [--describe "Ming woodblock print, vertical"] [--share-titles]

JOB/report.md        for the user: what was read, how fast, which pages need a look, where the files are.
JOB/field-report.md  for a GitHub issue: machine, model, speed, problems and notes.
                     No text from the pages, no file paths, no document names (unless --share-titles).
Standard library only.
"""
from __future__ import annotations

import argparse
import statistics
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import SKILL_VERSION, job_progress, load_job, read_rows  # noqa: E402

FLAGS = ("loop", "slow", "error", "skipped_blank")
WHY = {"loop": "the model repeated itself until the token limit; no usable text",
       "slow": "very slow page; the model may have repeated itself",
       "error": "could not be read",
       "skipped_blank": "looked blank, not sent to the model"}


def stats(data: dict[str, Any], rows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    pages = data["pages"]
    secs = [r["seconds"] for r in rows.values() if r.get("status") in ("ok", "slow", "loop") and r.get("seconds")]
    chars = {pid: sum(len(b.get("text") or "") for b in r.get("blocks", [])) for pid, r in rows.items()}
    empty = [p["id"] for p in pages if rows.get(p["id"], {}).get("status") == "ok" and chars.get(p["id"], 0) == 0]
    flagged = {s: [p["id"] for p in pages if rows.get(p["id"], {}).get("status") == s] for s in FLAGS}
    # text on pages that looked blank: models (Chandra above all) invent text there
    invented = [p["id"] for p in pages if p.get("blank") and chars.get(p["id"], 0) > 20
                and rows.get(p["id"], {}).get("status") == "ok"]
    # much ink but little text: the model missed the text (Indra on vertical CJK, faint scans, pictures)
    little = [p["id"] for p in pages if rows.get(p["id"], {}).get("status") == "ok"
              and p.get("ink", 0) >= 0.02 and 0 < chars.get(p["id"], 0) < 100]
    labels: dict[str, int] = {}
    for r in rows.values():
        for b in r.get("blocks", []):
            labels[b.get("label", "?")] = labels.get(b.get("label", "?"), 0) + 1
    warnings = [p["id"] for p in pages if rows.get(p["id"], {}).get("warning")]
    return {"pages": len(pages), "read": len(rows), "docs": len(data["sources"]),
            "median_s": round(statistics.median(secs), 1) if secs else None,
            "mean_s": round(statistics.mean(secs), 1) if secs else None,
            "time": duration(sum(secs)), "chars": sum(chars.values()),
            "empty": empty, "little": little, "flagged": flagged, "invented": invented, "labels": labels, "warnings": warnings}


def duration(seconds: float) -> str:
    if seconds < 90:
        return f"{round(seconds)} seconds"
    if seconds < 5400:
        return f"{round(seconds / 60)} minutes"
    return f"{round(seconds / 3600, 1)} hours"


def ids(xs: list[str], n: int = 25) -> str:
    return ", ".join(xs[:n]) + (f" … (+{len(xs) - n})" if len(xs) > n else "") if xs else "none"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("job", type=Path)
    ap.add_argument("--describe", help="a short, non-private description of the material for the field report")
    ap.add_argument("--share-titles", action="store_true", help="name the documents in the field report")
    a = ap.parse_args()

    data = load_job(a.job)
    rows = read_rows(a.job)
    s = stats(data, rows)
    prog = job_progress(a.job)
    runs = data.get("runs") or []
    last = runs[-1] if runs else {}
    m = last.get("machine", {})
    gpu = ", ".join(f"{g['name']} {g['vram_gb']} GB" for g in m.get("gpus", [])) or "none / Apple Silicon"
    brief = data.get("brief") or {}
    export = a.job / "export"
    exported = sorted(p.name for p in export.iterdir()) if export.exists() else []
    page_doc = {p["id"]: f"{p['doc']} p.{p['doc_page']}" for p in data["pages"]}

    # ---------- report.md (for the user) ----------
    u = [f"# OCR report: {data['name']}", "",
         f"Model **{data.get('model')}** ({last.get('backend', '?')}), skill local-ocr {SKILL_VERSION}. "
         "Machine transcription, not proofread: check against the page image before quoting.", "",
         "## What was read", "",
         f"- {s['read']} of {s['pages']} pages in {s['docs']} document(s); {s['chars']:,} characters.",
         f"- Speed: median {s['median_s']} s per page, {s['time']} of reading in {len(runs)} run(s)."]
    if prog["eta_hours"] and s["read"] < s["pages"]:
        u.append(f"- Not finished: about {prog['eta_hours']} hours left. Run the same command again to continue.")
    u += ["", "## Pages to look at", ""]
    for st in FLAGS:
        if s["flagged"][st]:
            u.append(f"- **{st}** ({len(s['flagged'][st])}): {WHY[st]}. "
                     + ids([f"{x} ({page_doc[x]})" for x in s["flagged"][st]], 15))
    if s["empty"]:
        u.append(f"- **no text found** ({len(s['empty'])}): {ids([f'{x} ({page_doc[x]})' for x in s['empty']], 15)}")
    if s["little"]:
        u.append(f"- **little text for the ink on the page** ({len(s['little'])}): the model may have missed the "
                 "text (wrong model for this layout, faint scan) or the page is a picture. "
                 + ids([f"{x} ({page_doc[x]})" for x in s["little"]], 15))
    if s["invented"]:
        u.append(f"- **text on a page that looks blank** ({len(s['invented'])}): probably invented by the model. "
                 + ids([f"{x} ({page_doc[x]})" for x in s["invented"]], 15))
    if u[-1] == "":
        u.append("- none flagged. Still read a few pages against the image.")
    u += ["", "## Files", "", f"- Job folder: `{a.job.resolve()}`",
          f"- Exports: {', '.join(f'`export/{x}/`' for x in exported) or 'none yet (run export.py)'}",
          "- Raw readings: `rows.jsonl` (one line per page)", ""]
    if data.get("notes"):
        u += ["## Notes", ""] + [f"- {n['text']}" for n in data["notes"]] + [""]
    u += ["## Licence", "",
          "Datalab's model weights (Chandra, Surya, Indra) use a modified OpenRAIL-M licence: free for research "
          "and personal use. When you share the output, credit Datalab (https://www.datalab.to).", ""]
    (a.job / "report.md").write_text("\n".join(u), encoding="utf-8")

    # ---------- field-report.md (for GitHub) ----------
    material = a.describe or ", ".join(f"{k}: {v}" for k, v in brief.items() if k in
                                       ("material", "script", "direction", "languages", "condition")) or "(not described)"
    if a.share_titles:
        material += f" | documents: {', '.join(src['doc'] for src in data['sources'])}"
    flagged_line = "; ".join(f"{st} {len(v)}" for st, v in s["flagged"].items() if v) or "none"
    f = [f"**Skill:** local-ocr {SKILL_VERSION} | **Date:** {data.get('created')} – {(last.get('ended') or '')[:10]}",
         f"**Machine:** {m.get('chip')} | {m.get('cpu_cores')} cores | {m.get('ram_gb')} GB | GPU: {gpu} | "
         f"{m.get('os')} {m.get('arch')}",
         f"**Model / backend:** {data.get('model')} / {last.get('backend')} | "
         + ", ".join(f"{k} {v}" for k, v in (last.get("versions") or {}).items()),
         f"**Material:** {material}",
         f"**Pages:** {s['read']}/{s['pages']} read in {s['docs']} document(s) | "
         f"median {s['median_s']} s/page, mean {s['mean_s']} s/page | {len(runs)} run(s)",
         f"**Flagged pages:** {flagged_line} | no text {len(s['empty'])} | little text for the ink {len(s['little'])} | text on blank-looking pages {len(s['invented'])}",
         f"**Layout labels seen:** {', '.join(f'{k} {v}' for k, v in sorted(s['labels'].items(), key=lambda x: -x[1]))}",
         f"**Formats exported:** {', '.join(exported) or 'none'}", "",
         "**What happened / problems:**"]
    f += [f"- {n['text']}" for n in data.get("notes", [])] or ["- (no notes logged)"]
    stopped = [r for r in runs if r.get("outcome") != "finished"]
    if stopped:
        f.append(f"- {len(stopped)} run(s) did not finish (stopped, killed or crashed).")
    f += ["", "**What the skill says / lacks:** <fill in>", "", "**Proposed change:** <fill in>"]
    (a.job / "field-report.md").write_text("\n".join(f) + "\n", encoding="utf-8")

    print(f"Wrote {a.job / 'report.md'}")
    print(f"Wrote {a.job / 'field-report.md'} (read it and fill in the last two lines before posting)")


if __name__ == "__main__":
    main()
