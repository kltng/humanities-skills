# /// script
# requires-python = ">=3.10,<3.14"
# dependencies = ["indra-ocr==1.1.2"]
# ///
"""Read a job's pages with Indra OCR (Datalab; 1M parameters, CPU, ONNX Runtime).

    uv run run_indra.py JOB [--limit N] [--pages 00012,00040] [--setup]

Fast (about 0.1 s per page) and small (76 MB). Horizontal text only: on vertical Chinese or
Japanese it finds almost nothing. Resumable: pages already in JOB/rows.jsonl are skipped.
"""
from __future__ import annotations

import os
import sys
from importlib.metadata import version
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import load_job, norm_label, run_pages, runner_args, page_ids, todo_pages  # noqa: E402


def inside(line_box: list[float], block_box: list[float]) -> bool:
    cx, cy = (line_box[0] + line_box[2]) / 2, (line_box[1] + line_box[3]) / 2
    return block_box[0] <= cx <= block_box[2] and block_box[1] <= cy <= block_box[3]


def main() -> None:
    a = runner_args(__doc__, ["cpu"])
    data = load_job(a.job)
    redo = page_ids(a.pages, data)
    todo = todo_pages(a.job, data, a.limit, redo)
    if not todo and not a.setup:
        print("Nothing to read: every page has a row. Use --pages to read pages again.")
        return

    import indra_ocr

    print("Loading Indra OCR (downloads about 76 MB if it is not on this machine yet) …", flush=True)
    conv = indra_ocr.load(threads=min(8, os.cpu_count() or 4), mode="ocr")
    if a.setup:
        print("Indra OCR is ready.")
        return

    def read(path: Path, page: dict) -> dict:
        pages = [p for _, p in conv.convert(str(path))]
        lines = [{"bbox": [round(v, 1) for v in ln.box], "text": ln.text, "conf": round(float(ln.conf), 3)}
                 for p in pages for ln in p.lines]
        blocks = []
        for p in pages:
            for b in p.blocks:
                bb = [round(float(v), 1) for v in b["bbox"]]
                blocks.append({"label": norm_label(b.get("label")), "bbox": bb, "text": b.get("text") or "",
                               "lines": [ln for ln in lines if inside(ln["bbox"], bb)]})
        if not blocks:  # no layout model output: one block per line
            blocks = [{"label": "Text", "bbox": ln["bbox"], "text": ln["text"], "lines": [ln]} for ln in lines]
        row = {"blocks": blocks, "finish_reason": "stop",
               "vertical": any(p.vertical for p in pages)}
        if row["vertical"]:
            row["warning"] = "Indra saw vertical text; its reading of vertical CJK is poor."
        return row

    run_pages(a.job, "indra", "cpu", {"indra-ocr": version("indra-ocr")}, todo, read)


if __name__ == "__main__":
    main()
