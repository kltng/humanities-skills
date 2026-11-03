# local-ocr: scripts, files and formats

Run every script with `uv run`. `doctor.py`, `jobs.py`, `export.py` and `report.py` use only the standard
library. `prepare.py` needs `pypdfium2` and `pillow`. Each `run_*.py` needs its model package. All of these
are declared inline (PEP 723), so `uv` installs them.

Environment variables:

| Variable | Meaning | Default |
|---|---|---|
| `LOCAL_OCR_HOME` | where the job list and the Surya MLX build are kept | `~/.cache/local-ocr` |
| `HF_HUB_CACHE` / `HF_HOME` | the Hugging Face model cache | `~/.cache/huggingface/hub` |

## Scripts

### doctor.py

`uv run doctor.py [--json]`

This reports the machine, tools, free disk, a verdict per model (`good`, `slow` or `no`) with its backend,
whether the model files are already downloaded (and the download size if not), and the jobs from the job
list with their progress. With `--json` it gives the same data as `{machine, tools, disk, recommendation,
jobs}`.

### prepare.py

`uv run prepare.py SOURCE... --job JOB --model chandra|surya|indra [options]`

| Option | Meaning |
|---|---|
| `--name` | job name (default: the folder name) |
| `--pages 1-20,35` | pages to take from each PDF |
| `--dpi 200` | PDF render resolution |
| `--long-side 2400` | shrink images whose long side is bigger |
| `--formats json,txt` | export formats stored in the job |
| `--brief brief.json` | interview answers, stored in `job.json` |
| `--blank-below 0.0015` | ink share under which a page counts as blank |

Sources can be PDFs, images (png, jpg, tif, webp, bmp, jp2) or folders. A folder's PDFs become one
document each. Its images, taken together, are one document.

### run_chandra.py / run_surya.py / run_indra.py

`uv run run_<model>.py JOB [--backend B] [--limit N] [--pages ID,ID] [--setup]`

| Option | Meaning |
|---|---|
| `--backend` | chandra: `mlx`, `hf`; surya: `llamacpp`, `mlx`, `vllm`; indra: `cpu`. Default `auto`. |
| `--limit N` | read at most N unread pages (smoke test) |
| `--pages` | read these page ids again, even if done |
| `--setup` | install, download and load the model, then stop |
| `--read-blank` | (chandra) also read pages that look blank |
| `--max-tokens` | (chandra) token limit per page (default 12,384) |

The runners are resumable. A row is written after each page, and a half-written last line is cut on the
next start. Each run is logged in `job.json` → `runs` (model, backend, package versions, machine, start,
end, outcome).

### export.py

`uv run export.py JOB [--formats ...] [--drop-furniture] [--no-page-marks]`

### jobs.py

`uv run jobs.py list | status JOB | note JOB "text" | forget JOB`

### report.py

`uv run report.py JOB [--describe "..."] [--share-titles]` writes `JOB/report.md` and `JOB/field-report.md`.

## The job folder

```
JOB/
  job.json         settings, brief, sources, pages, runs, notes
  pages/00001.png  page images (numbered across all documents)
  rows.jsonl       one line per page read; the last line for a page wins
  run.log          the runner's output, if you redirect it there
  export/<format>/ exports
  report.md, field-report.md
```

`job.json` → `pages[]`: `{id, doc, doc_page, file, width, height, ink, blank}` (`error` if the page could
not be rendered).

`rows.jsonl`, one line per page:

```json
{"page": "00012", "model": "chandra", "backend": "mlx", "seconds": 41.3, "status": "ok",
 "finish_reason": "stop", "tokens": 1840, "raw": "<div data-bbox=...>...</div>",
 "blocks": [{"label": "SectionHeader", "bbox": [120.0, 88.5, 980.2, 160.0],
             "html": "<p>卷一</p>", "text": "卷一",
             "lines": [{"bbox": [...], "text": "...", "conf": 0.98}]}],
 "warning": null}
```

- `status`: `ok`, `loop` (Chandra hit the token limit), `slow` (Surya over 120 s), `skipped_blank`, `error`.
- `bbox`: `[x0, y0, x1, y1]` in pixels of `pages/<id>.png`.
- `lines`: only Indra gives line boxes. For the other models, exports use the block box for each line.
- `raw`: Chandra's full output. `tokens` and `finish_reason` are Chandra only. Indra adds `vertical`.
- Labels are made the same across models: `Title`, `SectionHeader`, `Text`, `ListItem`, `Footnote`,
  `Caption`, `Table`, `Picture`, `Equation`, `PageHeader`, `PageFooter`, `Form`, `Code`, `Handwriting`,
  `TableOfContents`. Unknown labels pass through as the model wrote them.

## Export formats

| Format | Files | Notes |
|---|---|---|
| `json` | `export/json/<doc>.json` | `{document, job, model, pages: [{id, doc_page, file, width, height, status, warning, blocks}]}` |
| `jsonl` | `export/jsonl/<job>.jsonl` | one line per page: `{document, page, id, status, text, blocks}` |
| `txt` | `export/txt/<doc>.txt` | blocks separated by a blank line; `[[page N]]` before each page (`(loop)` etc. when the page has no text) |
| `md` | `export/md/<doc>.md` | `Title` → `#`, `SectionHeader` → `##`, list items, small notes in `<small>`; `<!-- page N -->` marks |
| `html` | `export/html/<doc>.html` | a simple reading page; text is escaped, so model HTML (tables, links) is not kept |
| `alto` | `export/alto/<doc>/<page>.xml` | ALTO 4: `TextBlock` per block (`TAGREFS` = label), `TextLine` + `String` per line, `Illustration` for pictures |
| `pagexml` | `export/pagexml/<doc>/<page>.xml` | PAGE 2019: `TextRegion` (type from label, `custom="label:..."`), `TextLine`, `ImageRegion`, `TableRegion`, reading order |
| `tei` | `export/tei/<doc>.xml` | TEI P5: `<pb n facs>`, `<head>`, `<p>`, `<fw>` for page headers and footers, `<note>`, `<figure>`, `<lb/>` |
| `hocr` | `export/hocr/<doc>.hocr.html` | `ocr_page`, `ocr_carea`, `ocr_par`, `ocr_line` with `bbox` |

Pages with status `loop`, `error` or `skipped_blank` are exported with no text. Pages not read yet are
left out. Both are listed when `export.py` finishes.
