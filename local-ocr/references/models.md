# The three models

All three are from Datalab (https://www.datalab.to). The code is open source. The weights use a modified
OpenRAIL-M licence: free for research, personal use and companies under US$20M in funding or revenue, and
not for use that competes with Datalab's API. When you share output, credit Datalab and link the licence.

## Hardware and downloads

| | Chandra OCR 2 | Surya OCR 2.5 | Indra OCR 1.1 |
|---|---|---|---|
| Parameters | about 5B (vision-language model) | small vision-language model | about 1M (7.3M with all helpers) |
| Download | 5.2 GB (`jwindle47/chandra-ocr-2-8bit-mlx`) or 10.6 GB (`datalab-to/chandra-ocr-2`) | 2.0 GB (`datalab-to/surya-ocr-2.5-gguf`) or 1.4 GB (`datalab-to/surya-ocr-2.5`) | 0.1 GB (`datalab-to/indra-ocr`) |
| Apple Silicon | 16 GB memory or more (MLX, 8-bit) | 8 GB or more (llama.cpp Metal, or MLX) | yes |
| NVIDIA | 16 GB GPU memory at least, 24 GB to be safe (PyTorch, bf16) | 8 GB or more (vLLM in Docker), or llama.cpp with CUDA | yes (CPU) |
| CPU only | no (far too slow) | llama.cpp, a minute or more per page | yes, the fastest |
| Python package | `chandra-ocr==0.2.0` (+ `mlx-vlm==0.7.11` on Mac) | `surya-ocr==0.23.0` (+ `mlx-vlm==0.7.10` on Mac) | `indra-ocr==1.1.2` |

Downloads go to the Hugging Face cache (`~/.cache/huggingface/hub`, or `$HF_HUB_CACHE`) and are reused.
The Surya MLX build is kept in `~/.cache/local-ocr/models/surya-2.5-mlx-q8` (or under `$LOCAL_OCR_HOME`).

## Test results (150 pages, 2026-10-30 to 2026-11-02)

The test used 150 pages from four Chinese books, each with a checked transcription:

- a Qing woodblock print, clean scan (40 pages)
- a 1585 Japanese-held print (30 pages)
- a late-Ming woodblock book in a faint reprint (40 pages)
- a 1991 modern horizontal print with notes (40 pages)

The pages were split into easy (100), hard (42) and blank (8). Error = character error rate (CER) after
folding variant forms; lower is better. Speed is per page.

| Model (how it ran) | Median page error | Easy pages | Hard pages | Modern horizontal book (median) | Vertical woodblock books | Loops | Invented chars on 8 blank pages | Speed |
|---|---|---|---|---|---|---|---|---|
| Chandra OCR 2, 8-bit MLX | **1.3%** | 1.5% | 17% (median 8%) | **0.6%** | 0.6–5% median | 3 of 150 | 4,194 | median 35 s, mean 55 s |
| Surya 2.5, llama.cpp (Metal) | 2.6% | 2.7% | 17% (median 9%) | 1.1% | 2.4–6% median | none reported | 70 | median 2.6 s, mean 2.8 s |
| Surya 2.5, 8-bit MLX | 2.7% | 2.8% | 18% (median 9%) | 1.1% | 2.7–6% median | none reported | 71 | median 5 s, mean 8 s |
| Indra 1.1.2, CPU | about 100% | 61% | 64% | 9% | about 100% (reads nothing) | 0 | 9 | about 0.1 s |

What this means in practice:

- **Chandra** is the most accurate. Chandra beat Surya on 98 of 140 pages with text. Its weak points are
  loops (about 2% of pages, up to 11 minutes each, no usable text) and blank pages, where it makes up
  text. The runner skips pages that look blank and marks loops.
- **Surya** comes close on clean print and is 7–20 times faster. It never lost a text page in the test.
  On the hardest book (the faint late-Ming reprint) the overall error was 17% for Surya and 15% for
  Chandra, so neither gives a usable final text there.
- **Indra** reads modern horizontal text (9% error on the 1991 book, about 0.1 s per page). It does not
  detect vertical columns on woodblock pages: it returned almost nothing, even when told the page was
  vertical. Use it only for horizontal text, or where speed matters more than accuracy.
- Hard pages stay hard for every model. Plan for a person, or a vision LLM, to check them.

Machines: the Chandra and Surya MLX numbers come from an M4 Mac mini (16 GB) and an M1 Max (64 GB). Surya
with llama.cpp and Indra ran on the M1 Max. The NVIDIA paths (`hf`, `vllm`) follow Datalab's own code but
were not part of this test. Field reports from NVIDIA machines are especially welcome.

## Known quirks

- Chandra writes layout as `<div data-bbox="x0 y0 x1 y1" data-label="...">` on a 0–1000 grid. The runner
  turns these into pixel boxes.
- Surya 2.5 gives pixel boxes and HTML per block. It does not report when it loops, so a page over 120 s is
  marked `slow`.
- With the Surya MLX backend, `mlx_vlm.server` serves the first model it finds in the Hugging Face cache.
  The runner points Surya at an empty cache folder so that only the Surya build is found (the same trick
  as in the tested setup).
- Indra drops page headers and footers from its Markdown by default. The runner keeps every block and
  line, and `export.py --drop-furniture` removes headers and footers in any format.
- Google-digitized scans carry a sideways watermark ("Generated at …", "Digitized by Google"). All models
  read it as a page header or footer. Use `--drop-furniture`, or remove it later.
