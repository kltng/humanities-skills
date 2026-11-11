# /// script
# requires-python = ">=3.10"
# dependencies = ["pypdfium2>=4.30", "pillow>=10.2"]
# ///
"""Make an OCR job folder from PDFs, images, or folders of either (a whole corpus is fine).

    uv run prepare.py SOURCE [SOURCE ...] --job JOB --model chandra|surya|indra
                      [--name NAME] [--pages 1-20,35] [--dpi 200] [--long-side 2000]
                      [--formats json,txt] [--brief brief.json]

Each source becomes one "document" (exports keep documents apart). Every page is saved as
JOB/pages/NNNNN.png. Running it again with the same JOB adds only new sources. Pages that look
blank are flagged, because Chandra invents text on blank pages.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image, ImageOps

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import SKILL_VERSION, load_job, register_job, save_job  # noqa: E402

IMAGES = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".webp", ".bmp", ".jp2"}
FORMATS = {"json", "jsonl", "txt", "md", "html", "alto", "pagexml", "tei", "hocr"}


def parse_pages(spec: str | None, n: int) -> list[int]:
    if not spec:
        return list(range(1, n + 1))
    out: list[int] = []
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-", 1)
            out += range(int(a), min(int(b), n) + 1)
        elif part:
            out.append(int(part))
    return [p for p in out if 1 <= p <= n]


def doc_name(path: Path, taken: set[str]) -> str:
    base = re.sub(r"[^\w\-.]+", "_", path.stem, flags=re.UNICODE).strip("_") or "doc"
    name, i = base, 2
    while name in taken:
        name, i = f"{base}-{i}", i + 1
    return name


def ink_ratio(im: Image.Image) -> float:
    """Share of dark pixels, on a small grey copy with the outer 5% cut off (scanner edges, shadows)."""
    g = ImageOps.grayscale(im)
    g.thumbnail((400, 400))
    w, h = g.size
    g = g.crop((int(w * 0.05), int(h * 0.05), int(w * 0.95), int(h * 0.95)))
    hist = g.histogram()
    total = sum(hist) or 1
    mean = sum(i * c for i, c in enumerate(hist)) / total
    cut = max(60, mean - 70)  # "dark" relative to the paper, so yellowed paper is not ink
    return sum(hist[: int(cut)]) / total


def fit(im: Image.Image, long_side: int | None) -> Image.Image:
    if long_side and max(im.size) > long_side:
        s = long_side / max(im.size)
        im = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
    return im


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("sources", nargs="+", type=Path)
    ap.add_argument("--job", type=Path, required=True)
    ap.add_argument("--model", choices=["chandra", "surya", "indra"], required=True)
    ap.add_argument("--name")
    ap.add_argument("--pages", help="pages of each PDF to take, e.g. 1-20,35 (default all)")
    ap.add_argument("--dpi", type=int, default=200, help="PDF render resolution (default 200)")
    ap.add_argument("--long-side", type=int, default=2400, help="shrink pages whose long side is bigger (default 2400)")
    ap.add_argument("--formats", default="json,txt", help=f"export formats, from: {','.join(sorted(FORMATS))}")
    ap.add_argument("--brief", type=Path, help="JSON file with the interview answers, stored in job.json")
    ap.add_argument("--blank-below", type=float, default=0.0015, help="ink ratio under which a page counts as blank")
    a = ap.parse_args()

    formats = [f.strip() for f in a.formats.split(",") if f.strip()]
    bad = [f for f in formats if f not in FORMATS]
    if bad:
        raise SystemExit(f"unknown format(s): {', '.join(bad)}")

    job = a.job
    (job / "pages").mkdir(parents=True, exist_ok=True)
    if (job / "job.json").exists():
        data = load_job(job)
        if data["model"] != a.model:
            print(f"note: job was made for {data['model']}; switching to {a.model}. "
                  "Pages already read keep their old rows.", file=sys.stderr)
            data["model"] = a.model
    else:
        data = {"name": a.name or job.resolve().name, "created": time.strftime("%Y-%m-%d"),
                "skill_version": SKILL_VERSION, "model": a.model, "formats": formats,
                "brief": {}, "sources": [], "pages": [], "runs": [], "notes": []}
    data["formats"] = formats
    if a.brief:
        data["brief"] = json.loads(a.brief.read_text(encoding="utf-8"))

    files: list[Path] = []
    for s in a.sources:
        if s.is_dir():
            inner = sorted(p for p in s.rglob("*") if p.suffix.lower() in IMAGES | {".pdf"})
            pdfs = [p for p in inner if p.suffix.lower() == ".pdf"]
            imgs = [p for p in inner if p.suffix.lower() != ".pdf"]
            files += pdfs
            if imgs:
                files.append(s)  # a folder of images is one document
        elif s.exists():
            files.append(s)
        else:
            raise SystemExit(f"not found: {s}")

    known = {src["path"] for src in data["sources"]}
    taken = {src["doc"] for src in data["sources"]}
    n = len(data["pages"])
    added = 0
    for f in files:
        key = str(f.resolve())
        if key in known:
            continue
        doc = doc_name(f, taken)
        taken.add(doc)
        if f.is_dir():
            images = sorted(p for p in f.iterdir() if p.suffix.lower() in IMAGES)
            items = [(i, lambda p=p: Image.open(p)) for i, p in enumerate(images, 1)]
        elif f.suffix.lower() == ".pdf":
            pdf = pdfium.PdfDocument(str(f))
            items = [(i, lambda i=i: pdf[i - 1].render(scale=a.dpi / 72).to_pil())
                     for i in parse_pages(a.pages, len(pdf))]
        elif f.suffix.lower() in IMAGES:
            items = [(1, lambda f=f: Image.open(f))]
        else:
            print(f"skip (not a PDF or image): {f}", file=sys.stderr)
            continue
        count = 0
        for doc_page, opener in items:
            n += 1
            pid = f"{n:05d}"
            try:
                with opener() as im:
                    im = ImageOps.exif_transpose(im).convert("RGB")
                    orig_w, orig_h = im.size  # before shrinking: export.py --coords original needs it
                    im = fit(im, a.long_side)
                    im.save(job / "pages" / f"{pid}.png")
                    ink = ink_ratio(im)
                    data["pages"].append({"id": pid, "doc": doc, "doc_page": doc_page, "file": f"pages/{pid}.png",
                                          "width": im.width, "height": im.height,
                                          "orig_width": orig_w, "orig_height": orig_h, "ink": round(ink, 5),
                                          "blank": ink < a.blank_below})
            except Exception as e:  # one bad page should not stop a corpus
                data["pages"].append({"id": pid, "doc": doc, "doc_page": doc_page, "file": None,
                                      "error": f"{type(e).__name__}: {e}"})
            count += 1
            if count % 50 == 0:
                print(f"  {doc}: {count} pages", flush=True)
        data["sources"].append({"path": key, "doc": doc, "pages": count})
        added += count
        print(f"{doc}: {count} pages", flush=True)

    save_job(job, data)
    register_job(job, data)
    blank = [p["id"] for p in data["pages"] if p.get("blank")]
    broken = [p["id"] for p in data["pages"] if p.get("error")]
    print(f"\nJob {data['name']}: {len(data['pages'])} pages ({added} new) in {len(data['sources'])} document(s)")
    if blank:
        print(f"Look blank ({len(blank)}): {', '.join(blank[:20])}{' …' if len(blank) > 20 else ''}")
    if broken:
        print(f"Could not open ({len(broken)}): {', '.join(broken[:20])}")


if __name__ == "__main__":
    main()
