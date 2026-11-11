#!/usr/bin/env python3
"""Write a job's readings in the formats the user asked for. Standard library only.

    uv run export.py JOB [--formats json,txt,alto] [--drop-furniture] [--no-page-marks]

Formats (default: the ones stored in job.json):
  json     one file per document: pages -> blocks (label, box in pixels, text, html, lines)
  jsonl    one line per page, all documents (for scripts and databases)
  txt      plain text per document, with [[page N]] marks
  md       Markdown per document (headings from layout labels)
  html     a reading page per document (text only; model HTML is not trusted)
  alto     ALTO 4 XML, one file per page (libraries, Transkribus, eScriptorium)
  pagexml  PAGE XML 2019, one file per page (Transkribus, eScriptorium, OCR-D)
  tei      TEI P5 per document, with <pb/> page breaks
  hocr     hOCR (HTML with boxes) per document
Output: JOB/export/<format>/...  Pages not read yet are left out and listed at the end.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import esc, load_job, read_rows  # noqa: E402

FURNITURE = {"PageHeader", "PageFooter"}
HEADINGS = {"Title": "#", "SectionHeader": "##"}
READ = {"ok", "slow"}  # statuses whose text is a reading


def collect(job: Path, drop_furniture: bool) -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]], list[str]]:
    data = load_job(job)
    rows = read_rows(job)
    docs: dict[str, list[dict[str, Any]]] = {}
    missing = []
    for p in data["pages"]:
        r = rows.get(p["id"])
        if r is None:
            missing.append(p["id"])
            continue
        blocks = r.get("blocks") or []
        if r.get("status") not in READ:
            blocks = []  # loops, errors and skipped pages carry no text
        if drop_furniture:
            blocks = [b for b in blocks if b.get("label") not in FURNITURE]
        docs.setdefault(p["doc"], []).append({**p, "status": r.get("status", "ok"), "model": r.get("model"),
                                              "warning": r.get("warning"), "blocks": blocks})
    return data, docs, missing


def to_original(docs: dict[str, list[dict[str, Any]]]) -> list[str]:
    """Scale every box from the working copy (pages/<id>.png) to the size of the original image.

    Returns the ids of pages whose original size is not known (jobs made before version 1.1.0).
    """
    unknown = []
    for pages in docs.values():
        for p in pages:
            ow, oh, w, h = p.get("orig_width"), p.get("orig_height"), p.get("width"), p.get("height")
            if not (ow and oh and w and h):
                unknown.append(p["id"])
                continue
            if (ow, oh) == (w, h):
                continue
            sx, sy = ow / w, oh / h

            def scale(bbox: list[float]) -> list[float]:
                return [round(bbox[0] * sx, 1), round(bbox[1] * sy, 1), round(bbox[2] * sx, 1), round(bbox[3] * sy, 1)]

            p["blocks"] = [{**b, "bbox": scale(b["bbox"]),
                            **({"lines": [{**ln, "bbox": scale(ln["bbox"])} for ln in b["lines"]]} if b.get("lines") else {})}
                           for b in p["blocks"]]
            p["width"], p["height"] = ow, oh
    return unknown


def coords_note(p: dict[str, Any]) -> str:
    """Say in the file which image the coordinates belong to."""
    ow, oh = p.get("orig_width"), p.get("orig_height")
    if p.get("coords") == "original":
        return (f"Coordinates are in pixels of the original image ({p.get('width')} x {p.get('height')}). For a PDF "
                "this is the page as rendered by prepare.py at its dpi setting.")
    note = f"Coordinates are in pixels of the working copy {p.get('file') or ''} ({p.get('width')} x {p.get('height')})"
    if ow and oh and (ow, oh) != (p.get("width"), p.get("height")):
        note += (f", which was shrunk from the original ({ow} x {oh}). Export again with the option "
                 "'coords original' for coordinates that fit the original image")
    return note + "."  # no double hyphen in these notes: they go into an XML comment


def page_text(page: dict[str, Any]) -> str:
    return "\n\n".join(b["text"] for b in page["blocks"] if b.get("text"))


def box(b: dict[str, Any]) -> tuple[int, int, int, int]:
    x0, y0, x1, y1 = (int(round(v)) for v in b["bbox"])
    return x0, y0, max(x1 - x0, 1), max(y1 - y0, 1)


def lines_of(b: dict[str, Any]) -> list[dict[str, Any]]:
    """Line boxes when the model gave them (Indra); otherwise each text line gets the block's box."""
    if b.get("lines"):
        return b["lines"]
    return [{"bbox": b["bbox"], "text": t} for t in (b.get("text") or "").split("\n") if t.strip()]


# ---------- writers ----------

def w_json(out: Path, data: dict, docs: dict) -> None:
    for doc, pages in docs.items():
        (out / f"{doc}.json").write_text(json.dumps(
            {"document": doc, "job": data["name"], "model": data.get("model"),
             "pages": [{k: p.get(k) for k in ("id", "doc_page", "file", "width", "height", "orig_width", "orig_height",
                                              "coords", "status", "warning", "blocks")}
                       for p in pages]}, ensure_ascii=False, indent=1), encoding="utf-8")


def w_jsonl(out: Path, data: dict, docs: dict) -> None:
    with open(out / f"{data['name']}.jsonl", "w", encoding="utf-8") as fh:
        for doc, pages in docs.items():
            for p in pages:
                fh.write(json.dumps({"document": doc, "page": p["doc_page"], "id": p["id"], "status": p["status"],
                                     "text": page_text(p), "blocks": p["blocks"]}, ensure_ascii=False) + "\n")


def w_txt(out: Path, data: dict, docs: dict, marks: bool = True) -> None:
    for doc, pages in docs.items():
        parts = []
        for p in pages:
            head = f"[[page {p['doc_page']}]]" + ("" if p["status"] in READ else f" ({p['status']})")
            parts.append((head + "\n" if marks else "") + page_text(p))
        (out / f"{doc}.txt").write_text("\n\n".join(parts).strip() + "\n", encoding="utf-8")


def w_md(out: Path, data: dict, docs: dict, marks: bool = True) -> None:
    for doc, pages in docs.items():
        parts = [f"# {doc}\n"]
        for p in pages:
            if marks:
                parts.append(f"<!-- page {p['doc_page']} {p['status']} -->")
            for b in p["blocks"]:
                t = (b.get("text") or "").strip()
                if not t:
                    continue
                if b["label"] in HEADINGS:
                    parts.append(f"{HEADINGS[b['label']]} {' '.join(t.split())}")
                elif b["label"] == "ListItem":
                    parts.append("- " + t.replace("\n", "\n  "))
                elif b["label"] in ("Footnote", "PageFooter", "PageHeader", "Caption"):
                    parts.append(f"<small>{t}</small>")
                else:
                    parts.append(t.replace("\n", "  \n"))
        (out / f"{doc}.md").write_text("\n\n".join(parts).strip() + "\n", encoding="utf-8")


def w_html(out: Path, data: dict, docs: dict) -> None:
    for doc, pages in docs.items():
        body = []
        for p in pages:
            body.append(f'<section id="p{p["doc_page"]}"><h2>Page {p["doc_page"]}'
                        + ("" if p["status"] in READ else f' <span class="st">{esc(p["status"])}</span>') + "</h2>")
            for b in p["blocks"]:
                if b.get("text"):
                    tag = "h3" if b["label"] in HEADINGS else "p"
                    body.append(f'<{tag} class="{esc(b["label"])}">{esc(b["text"]).replace(chr(10), "<br>")}</{tag}>')
            body.append("</section>")
        (out / f"{doc}.html").write_text(f"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(doc)}</title>
<style>body{{max-width:46em;margin:2em auto;padding:0 1em;font:17px/1.7 serif}}h2{{font:600 13px sans-serif;
color:#777;border-top:1px solid #ddd;padding-top:1em}}.st{{color:#b00}}.PageHeader,.PageFooter,.Footnote,.Caption
{{font-size:.85em;color:#555}}</style></head><body><h1>{esc(doc)}</h1>
<p><small>Machine OCR ({esc(data.get('model') or '')}), not proofread.</small></p>
{chr(10).join(body)}</body></html>""", encoding="utf-8")


def w_alto(out: Path, data: dict, docs: dict) -> None:
    for doc, pages in docs.items():
        (out / doc).mkdir(exist_ok=True)
        for p in pages:
            blocks = []
            for i, b in enumerate(p["blocks"], 1):
                x, y, w, h = box(b)
                lines = []
                for j, ln in enumerate(lines_of(b), 1):
                    lx, ly, lw, lh = box(ln)
                    lines.append(f'<TextLine ID="b{i}_l{j}" HPOS="{lx}" VPOS="{ly}" WIDTH="{lw}" HEIGHT="{lh}">'
                                 f'<String CONTENT="{esc(ln["text"])}" HPOS="{lx}" VPOS="{ly}" WIDTH="{lw}" HEIGHT="{lh}"/>'
                                 "</TextLine>")
                tag = "Illustration" if b["label"] == "Picture" else "TextBlock"
                inner = "" if tag == "Illustration" else "".join(lines)
                blocks.append(f'<{tag} ID="b{i}" TAGREFS="{esc(b["label"])}" HPOS="{x}" VPOS="{y}" WIDTH="{w}" '
                              f'HEIGHT="{h}">{inner}</{tag}>')
            labels = sorted({b["label"] for b in p["blocks"]})
            tags = "".join(f'<OtherTag ID="{esc(lab)}" LABEL="{esc(lab)}" TYPE="block"/>' for lab in labels)
            xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<alto xmlns="http://www.loc.gov/standards/alto/ns-v4#" xmlns:xlink="http://www.w3.org/1999/xlink" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.loc.gov/standards/alto/ns-v4# http://www.loc.gov/standards/alto/v4/alto-4-4.xsd">
<!-- {esc(coords_note(p))} -->
<Description><MeasurementUnit>pixel</MeasurementUnit><sourceImageInformation><fileName>{esc(p['file'] or '')}</fileName></sourceImageInformation>
<OCRProcessing ID="ocr"><ocrProcessingStep><processingSoftware><softwareName>{esc(p.get('model') or '')} via local-ocr</softwareName></processingSoftware></ocrProcessingStep></OCRProcessing></Description>
<Tags>{tags}</Tags>
<Layout><Page ID="p{p['doc_page']}" PHYSICAL_IMG_NR="{p['doc_page']}" WIDTH="{p.get('width') or 0}" HEIGHT="{p.get('height') or 0}">
<PrintSpace HPOS="0" VPOS="0" WIDTH="{p.get('width') or 0}" HEIGHT="{p.get('height') or 0}">{''.join(blocks)}</PrintSpace></Page></Layout>
</alto>
"""
            (out / doc / f"{p['doc_page']:05d}.xml").write_text(xml, encoding="utf-8")


PAGE_TYPES = {"Title": "heading", "SectionHeader": "heading", "PageHeader": "header", "PageFooter": "footer",
              "Footnote": "footnote", "Caption": "caption", "ListItem": "list-label", "Text": "paragraph"}


def pts(b: dict[str, Any]) -> str:
    x0, y0, x1, y1 = (int(round(v)) for v in b["bbox"])
    return f"{x0},{y0} {x1},{y0} {x1},{y1} {x0},{y1}"


def w_pagexml(out: Path, data: dict, docs: dict) -> None:
    for doc, pages in docs.items():
        (out / doc).mkdir(exist_ok=True)
        for p in pages:
            regions = []
            for i, b in enumerate(p["blocks"], 1):
                if b["label"] == "Picture":
                    regions.append(f'<ImageRegion id="r{i}"><Coords points="{pts(b)}"/></ImageRegion>')
                    continue
                if b["label"] == "Table":
                    regions.append(f'<TableRegion id="r{i}"><Coords points="{pts(b)}"/></TableRegion>')
                    continue
                lines = "".join(f'<TextLine id="r{i}l{j}"><Coords points="{pts(ln)}"/><TextEquiv><Unicode>'
                                f'{esc(ln["text"])}</Unicode></TextEquiv></TextLine>'
                                for j, ln in enumerate(lines_of(b), 1))
                kind = PAGE_TYPES.get(b["label"], "other")
                regions.append(f'<TextRegion id="r{i}" type="{kind}" custom="label:{esc(b["label"])};">'
                               f'<Coords points="{pts(b)}"/>{lines}<TextEquiv><Unicode>{esc(b.get("text") or "")}'
                               "</Unicode></TextEquiv></TextRegion>")
            order = "".join(f'<RegionRefIndexed index="{i - 1}" regionRef="r{i}"/>' for i in range(1, len(p["blocks"]) + 1))
            ro = f'<ReadingOrder><OrderedGroup id="ro">{order}</OrderedGroup></ReadingOrder>' if order else ""
            xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<PcGts xmlns="http://schema.primaresearch.org/PAGE/gts/pagecontent/2019-07-15">
<Metadata><Creator>{esc(p.get('model') or '')} via local-ocr</Creator><Created>{esc(data.get('created') or '')}T00:00:00</Created><LastChange>{esc(data.get('created') or '')}T00:00:00</LastChange><Comments>{esc(coords_note(p))}</Comments></Metadata>
<Page imageFilename="{esc(p['file'] or '')}" imageWidth="{p.get('width') or 0}" imageHeight="{p.get('height') or 0}">{ro}{''.join(regions)}</Page>
</PcGts>
"""
            (out / doc / f"{p['doc_page']:05d}.xml").write_text(xml, encoding="utf-8")


TEI_TAGS = {"Title": "head", "SectionHeader": "head", "PageHeader": "fw", "PageFooter": "fw", "Footnote": "note",
            "Caption": "figDesc", "ListItem": "item"}


def w_tei(out: Path, data: dict, docs: dict) -> None:
    for doc, pages in docs.items():
        body = []
        for p in pages:
            body.append(f'<pb n="{p["doc_page"]}" facs="{esc(p["file"] or "")}"/>')
            for b in p["blocks"]:
                t = esc(b.get("text") or "").replace("\n", "<lb/>")
                if b["label"] == "Picture":
                    body.append("<figure/>")
                elif not t:
                    continue
                elif b["label"] in ("PageHeader", "PageFooter"):
                    body.append(f'<fw type="{"header" if b["label"] == "PageHeader" else "footer"}">{t}</fw>')
                elif b["label"] == "Caption":
                    body.append(f"<figure><figDesc>{t}</figDesc></figure>")
                elif b["label"] == "ListItem":
                    body.append(f"<list><item>{t}</item></list>")
                elif b["label"] in TEI_TAGS:
                    body.append(f"<{TEI_TAGS[b['label']]}>{t}</{TEI_TAGS[b['label']]}>")
                else:
                    body.append(f"<p>{t}</p>")
        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<TEI xmlns="http://www.tei-c.org/ns/1.0">
<teiHeader><fileDesc><titleStmt><title>{esc(doc)}</title></titleStmt>
<publicationStmt><p>Machine OCR, not proofread. Made with {esc(data.get('model') or '')} via local-ocr.</p></publicationStmt>
<sourceDesc><p>{esc(doc)}</p></sourceDesc></fileDesc></teiHeader>
<text><body><div>
{chr(10).join(body)}
</div></body></text>
</TEI>
"""
        (out / f"{doc}.xml").write_text(xml, encoding="utf-8")


def w_hocr(out: Path, data: dict, docs: dict) -> None:
    for doc, pages in docs.items():
        body = []
        for p in pages:
            body.append(f'<div class="ocr_page" id="page_{p["doc_page"]}" title="image {esc(p["file"] or "")}; '
                        f'bbox 0 0 {p.get("width") or 0} {p.get("height") or 0}">')
            for i, b in enumerate(p["blocks"], 1):
                x0, y0, x1, y1 = (int(round(v)) for v in b["bbox"])
                lines = "".join(
                    '<span class="ocr_line" title="bbox {} {} {} {}">{}</span>'.format(
                        *(int(round(v)) for v in ln["bbox"]), esc(ln["text"])) for ln in lines_of(b))
                body.append(f'<div class="ocr_carea" id="b{p["doc_page"]}_{i}" title="bbox {x0} {y0} {x1} {y1}">'
                            f'<p class="ocr_par" lang="">{lines}</p></div>')
            body.append("</div>")
        (out / f"{doc}.hocr.html").write_text(f"""<!doctype html><html><head><meta charset="utf-8"><title>{esc(doc)}</title>
<meta name="ocr-system" content="{esc(data.get('model') or '')} via local-ocr"><meta name="ocr-capabilities" content="ocr_page ocr_carea ocr_par ocr_line"></head>
<body>{''.join(body)}</body></html>""", encoding="utf-8")


WRITERS = {"json": w_json, "jsonl": w_jsonl, "txt": w_txt, "md": w_md, "html": w_html, "alto": w_alto,
           "pagexml": w_pagexml, "tei": w_tei, "hocr": w_hocr}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("job", type=Path)
    ap.add_argument("--formats", help="comma list; default: job.json formats")
    ap.add_argument("--drop-furniture", action="store_true", help="leave out running heads and page numbers")
    ap.add_argument("--no-page-marks", action="store_true", help="txt/md without page marks")
    ap.add_argument("--coords", choices=["working", "original"], default="working",
                    help="boxes in pixels of the working copies in pages/ (default), or scaled to the original images")
    a = ap.parse_args()

    data, docs, missing = collect(a.job, a.drop_furniture)
    for pages in docs.values():
        for p in pages:
            p["coords"] = "working"
    if a.coords == "original":
        unknown = to_original(docs)
        for pages in docs.values():
            for p in pages:
                if p["id"] not in unknown:
                    p["coords"] = "original"
        if unknown:
            print(f"--coords original: the original size of {len(unknown)} page(s) is not recorded (job made by an "
                  "older version). Their boxes stay in working-copy pixels. Run prepare.py again in a new job to fix this.")
    formats = [f.strip() for f in (a.formats or ",".join(data.get("formats") or ["json", "txt"])).split(",") if f.strip()]
    for f in formats:
        if f not in WRITERS:
            raise SystemExit(f"unknown format: {f} (choose from {', '.join(WRITERS)})")
        out = a.job / "export" / f
        out.mkdir(parents=True, exist_ok=True)
        if f in ("txt", "md"):
            WRITERS[f](out, data, docs, marks=not a.no_page_marks)
        else:
            WRITERS[f](out, data, docs)
        print(f"{f}: {out}")
    not_text = [p["id"] for pages in docs.values() for p in pages if p["status"] not in READ]
    print(f"{sum(len(v) for v in docs.values())} pages exported in {len(docs)} document(s).")
    if not_text:
        print(f"{len(not_text)} pages carry no text (loop, error, or skipped blank): {', '.join(not_text[:15])}"
              + (" …" if len(not_text) > 15 else ""))
    if missing:
        print(f"{len(missing)} pages not read yet, left out: {', '.join(missing[:15])}" + (" …" if len(missing) > 15 else ""))


if __name__ == "__main__":
    main()
