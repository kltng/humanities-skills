---
name: local-ocr
description: >-
  OCR PDFs, page images, or a whole corpus on the user's own computer with Datalab's open models:
  Chandra OCR 2 (most accurate), Surya OCR 2.5 (fast, good on clean print) and Indra OCR (tiny, CPU only).
  Starts with a short interview (what the documents are, script and writing direction, quality goal,
  output formats), checks the hardware (Apple Silicon, NVIDIA GPU, memory, disk) and what is already
  downloaded or half done, picks the model the machine can run, downloads it once, runs a smoke test,
  then the full job (resumable), and exports JSON, plain text, Markdown, HTML, ALTO XML, PAGE XML, TEI or
  hOCR. Ends with a run report and a field report that can be posted as a GitHub issue. Use when the user
  wants to OCR, transcribe or "make searchable" a PDF, scans or a book locally, asks which OCR model their
  machine can handle, mentions Chandra, Surya, Indra or Datalab, or wants ALTO/PAGE XML from scans.
version: 1.0.0
license: MIT
author: Kwok-leong Tang
contributors:
  - Claude (Anthropic)
---

# Local OCR (Chandra, Surya, Indra)

## Overview

This skill runs OCR on the user's own machine. Nothing is sent to a cloud service, except that each
model is downloaded once from Hugging Face. It uses three open models from Datalab (https://www.datalab.to):

| Model | Size | Runs on | Speed (one page) | Best for |
|---|---|---|---|---|
| **Chandra OCR 2** | 5.2 GB (8-bit MLX) / 10.6 GB (full) | Apple Silicon with 16 GB+, or NVIDIA GPU with 16 GB+ | about 35–55 s | the best text: old prints, vertical CJK, mixed layouts, tables |
| **Surya OCR 2.5** | 1.4–2 GB | Apple Silicon, NVIDIA, or CPU (slow) | about 3–8 s | big, clean printed books; a fast searchable draft |
| **Indra OCR** | 0.1 GB | any computer, CPU only | about 0.1–0.5 s | modern horizontal print, quick text, weak machines |

All three give layout blocks (heading, text, footnote, page header, picture, table …) with boxes, so
the XML formats keep the page layout. The numbers come from a 150-page test on Chinese books
(`references/models.md`). Short version: Chandra is the most accurate, Surya is close on clean print, and
**Indra cannot read vertical (top-to-bottom) Chinese or Japanese**.

Every script is in `scripts/` and runs with `uv run`. The runners carry their own dependencies (PEP 723),
so `uv` installs them the first time. Define this in each Bash call:

```bash
S=~/.claude/skills/local-ocr/scripts      # or wherever this skill is installed
```

## When to Use

- "OCR this PDF", "make these scans searchable", "transcribe this book", "OCR this folder of PDFs".
- "Which OCR model can my laptop run?" (step 1 alone answers this).
- The user wants ALTO, PAGE XML, TEI or hOCR from scans (for Transkribus, eScriptorium, a digital library).
- An earlier OCR job stopped and should go on ("continue the OCR", "how far did it get?").

Not for: a PDF that already has a good text layer (extract that text instead; ask first), or pages that
need a scholar's reading of every hard character. For those, a vision LLM reading or a person is better.
Use local OCR as the first pass.

## Workflow

Follow the steps in order. Use plain words with the user and explain any technical term once.

### 1. Check the machine and what is already there

```bash
uv run $S/doctor.py
```

This prints the machine (chip, memory, GPU, free disk), the tools found (`llama-server`, `docker`,
`nvidia-smi`, `gh`), a verdict for each model (GOOD / SLOW / NO, the backend, and the download size, or
"already downloaded"), and **earlier jobs on this machine** with their progress.

- If an earlier job is unfinished and matches what the user wants, offer to continue it (step 6). Its
  pages and finished readings are kept, so nothing is downloaded or read twice.
- Models already downloaded are reused. Hugging Face keeps them in its cache (`~/.cache/huggingface/hub`).
- If the disk warning shows, tell the user how much space is needed before going on.

### 2. Interview

Ask with `AskUserQuestion` (up to 4 questions in one call). Skip any question the request has already
answered. Ask:

1. **The documents.** Path to the PDF, images or folder. Roughly how many pages?
2. **The material.** Script and language (Chinese, Japanese, Korean, English, mixed …). Writing direction
   (horizontal or vertical columns). Kind (modern print, old woodblock or movable type, typescript,
   handwriting, newspapers, tables). Scan quality.
3. **The goal.** "Best text I can get" or "a quick searchable draft". Is there a deadline? (A 500-page book
   takes about 8 hours with Chandra and about 1 hour with Surya.)
4. **Output formats** (multiSelect). Plain text (`txt`), Markdown (`md`), JSON (`json`, one file per
   document with blocks and boxes), JSON Lines (`jsonl`, one line per page), reading page (`html`), ALTO XML
   (`alto`), PAGE XML (`pagexml`), TEI (`tei`), hOCR (`hocr`). Say what each is for in a few words: ALTO and
   PAGE are what library systems, Transkribus and eScriptorium import; TEI is for text editions.

Then look at 2–3 pages yourself (render a page or open an image and Read it). Check the writing direction
and the layout. Users are sometimes wrong about these.

Save the answers to a small JSON file, for example `brief.json`, with the keys `material`, `script`,
`direction`, `languages`, `condition`, `goal`, `formats`. `prepare.py --brief` stores it in the job, and the
field report uses the non-private keys.

### 3. Choose the model

Combine the material with the doctor's verdicts:

| Material | First choice | Fallback |
|---|---|---|
| Vertical CJK (classical prints, manuscripts) | Chandra | Surya (draft only). **Never Indra.** |
| Hard pages: worn, faint, tables, mixed scripts, notes between lines | Chandra | Surya, then check the flagged pages |
| Clean modern print, many pages | Surya | Chandra if the time is there; Indra if the machine is weak |
| Modern horizontal print on a weak machine, or a quick look | Indra | Surya on CPU (slow) |
| Handwriting | Chandra | none of these is good; say so |

Tell the user the plan in one short paragraph: the model, why, the download size, the time (pages × the
speed in the table above, or the smoke-test speed), and the output formats. Wait for their OK before a
download over 1 GB or a run over an hour.

### 4. Make the job, then download the model

```bash
uv run $S/prepare.py BOOK.pdf --job ~/ocr-jobs/NAME --model chandra --formats json,txt,alto --brief brief.json
uv run $S/run_chandra.py ~/ocr-jobs/NAME --setup     # installs, downloads and loads the model, then stops
```

- `prepare.py` takes PDFs, images and folders, as many as you like. Each file becomes one document, and a
  folder of images is one document. Pages are saved as PNG in `JOB/pages/`. Useful options:
  `--pages 1-20,35`, `--dpi 300` for small print, `--long-side 3000` for very dense pages.
- Running `prepare.py` again on the same job adds only new files, so a corpus can grow.
- It flags pages that look blank. Chandra invents text on blank pages, so its runner skips them
  (`--read-blank` reads them anyway).
- Put jobs where the user wants them. `~/ocr-jobs/<name>` is a good default. Every job is recorded in
  `~/.cache/local-ocr/registry.json`, so the doctor finds it later.
- `--setup` is safe to run again. If the model is already there, it only loads it.

Backends are picked automatically (`--backend` overrides):

| Runner | Apple Silicon | NVIDIA GPU | CPU only |
|---|---|---|---|
| `run_chandra.py` | `mlx` (8-bit) | `hf` (PyTorch, full model) | not supported |
| `run_surya.py` | `llamacpp` if `llama-server` is installed (fastest), else `mlx` (builds an 8-bit copy once) | `vllm` with Docker, else `llamacpp` | `llamacpp` (slow) |
| `run_indra.py` | `cpu` | `cpu` | `cpu` |

### 5. Smoke test

```bash
uv run $S/run_chandra.py ~/ocr-jobs/NAME --limit 5
uv run $S/export.py ~/ocr-jobs/NAME --formats txt
```

Pick pages from different parts of the document if you can. Read 2–3 page images next to their text and
count clear errors. Show the user one page of output. Tell them the real speed and the new time estimate.
If the quality is poor, change the model now (`prepare.py ... --model surya` switches the job), not after
500 pages.

### 6. Full run

Run it in the background, because it can take hours. The runner is resumable: stopping is safe, and
running the same command again goes on from the next unread page. Pages with an error are tried again.

```bash
uv run $S/run_chandra.py ~/ocr-jobs/NAME > ~/ocr-jobs/NAME/run.log 2>&1     # with run_in_background
uv run $S/jobs.py status ~/ocr-jobs/NAME                                     # pages done, speed, time left
uv run $S/run_chandra.py ~/ocr-jobs/NAME --pages 00012,00040                 # read some pages again
```

While it runs, log anything unusual with `uv run $S/jobs.py note JOB "..."`: a crash, a page that stalled,
a layout the model gets wrong, a surprise in speed or memory. These notes go into the report.

What the runners flag:
- **loop** (Chandra): the model repeated itself up to the token limit. There is no usable text. About 2% of
  pages do this, and each one costs up to ~11 minutes.
- **slow** (Surya): a page over 120 s. Surya does not report loops, so check these pages.
- **skipped_blank**: the page looked blank and was not sent to the model.
- **error**: the image could not be opened or read.

### 7. Export

```bash
uv run $S/export.py ~/ocr-jobs/NAME                        # the formats chosen in the interview
uv run $S/export.py ~/ocr-jobs/NAME --formats tei,pagexml  # any others
```

Files go to `JOB/export/<format>/`. Options: `--drop-furniture` leaves out running heads and page
numbers; `--no-page-marks` writes txt/md without `[[page N]]` marks. Loop, error and skipped pages are
exported as empty pages and listed. Pages not read yet are left out. Format details are in
`references/api_reference.md`.

### 8. Report, and the field report for GitHub

```bash
uv run $S/report.py ~/ocr-jobs/NAME --describe "Qing woodblock print, vertical, good scan"
```

This writes two files:

- `JOB/report.md` is for the user: pages read, speed, the pages to look at (loops, slow pages, no text,
  little text for the amount of ink, text on pages that look blank), the files, notes, and the licence.
  Give the user the main points in plain words. Always say: **machine transcription, not proofread**.
- `JOB/field-report.md` is for a GitHub issue: machine, model, backend, versions, speed, flags, notes. It
  has **no page text, no file paths and no document names** (unless `--share-titles`). Read it, fill in
  "What the skill says / lacks" and "Proposed change", and remove anything private.

Then offer to post the field report. It helps tune the advice on speed, memory and model choice for other
machines. Issues are public, so ask first and show the text:

```bash
gh issue create --repo kltng/humanities-skills \
  --title "[local-ocr] field report: <model> on <chip>, <material>, <pages> pages" \
  --body-file ~/ocr-jobs/NAME/field-report.md
```

Without `gh`, give the user the link https://github.com/kltng/humanities-skills/issues/new and the file to paste.

## Best Practices

- Always run the doctor first. It is fast, it finds earlier jobs, and it stops you from starting a
  10 GB download on a full disk.
- Smoke test before every long run. Most bad results show up in the first 5 pages.
- Never call a loop, slow or "little text" page read until someone has looked at it.
- One model per job. To compare models, make a second job from the same files.
- Keep jobs out of cloud-synced folders (Dropbox, iCloud). The page images are large and change often.
- Chandra and Surya each need most of the machine's memory. Do not run two jobs at once on one machine.
- Licence: the model weights use Datalab's modified OpenRAIL-M licence (free for research, personal use,
  and small companies). When you share output, credit Datalab. The 8-bit MLX Chandra is a community
  conversion (`jwindle47/chandra-ocr-2-8bit-mlx`). In our test it read as well as the full model.

## Example Code

A 300-page Qing woodblock print on a 32 GB MacBook, ALTO and text wanted:

```bash
S=~/.claude/skills/local-ocr/scripts
uv run $S/doctor.py                                   # chandra GOOD mlx, download about 5.2 GB
uv run $S/prepare.py ~/Downloads/wenmiao.pdf --job ~/ocr-jobs/wenmiao --model chandra \
    --formats alto,txt --brief /tmp/brief.json
uv run $S/run_chandra.py ~/ocr-jobs/wenmiao --setup   # one-time download
uv run $S/run_chandra.py ~/ocr-jobs/wenmiao --limit 5 # smoke test, then look at the pages
uv run $S/run_chandra.py ~/ocr-jobs/wenmiao > ~/ocr-jobs/wenmiao/run.log 2>&1   # background, ~4–5 h
uv run $S/jobs.py status ~/ocr-jobs/wenmiao
uv run $S/export.py ~/ocr-jobs/wenmiao
uv run $S/report.py ~/ocr-jobs/wenmiao --describe "Qing woodblock print, vertical"
```

A folder of 2,000 modern English typescript scans on an older Windows laptop:

```bash
uv run $S/doctor.py                                   # chandra NO, surya SLOW, indra GOOD
uv run $S/prepare.py D:/scans --job D:/ocr-jobs/letters --model indra --formats txt,pagexml
uv run $S/run_indra.py D:/ocr-jobs/letters --limit 10
uv run $S/run_indra.py D:/ocr-jobs/letters            # about 0.5 s per page
```

## Resources

- `references/models.md`: the three models, the test results, hardware needs, licences.
- `references/api_reference.md`: every script and option, the job folder, the row format, and the exports.
- Datalab: Chandra https://github.com/datalab-to/chandra, Surya https://github.com/datalab-to/surya,
  Indra https://github.com/datalab-to/indra; models at https://huggingface.co/datalab-to
- Tests (offline, no models): `cd local-ocr && python3 -m unittest discover -s tests`

## Feedback and Citation

**Report a problem.** This skill is part of the public repository [kltng/humanities-skills](https://github.com/kltng/humanities-skills). If it fails (a model or package changed, a script errors, or these instructions are wrong), report it as a GitHub issue:

1. Ask the user before filing. Issues are public.
2. Check for an existing report: `gh issue list --repo kltng/humanities-skills --state all --search "local-ocr"`
3. File it: `gh issue create --repo kltng/humanities-skills --label bug --title "[local-ocr] <short summary>" --body "<details>"`. Without `gh`, give the user this link: https://github.com/kltng/humanities-skills/issues/new?template=skill-problem.yml
4. Include the skill name and version, what you ran, the error text, what you expected, and the environment (OS, Python version). Leave out API keys, personal data, private file paths, and unpublished research.

Field reports from finished jobs (step 8) are welcome too. Use the title `[local-ocr] field report: ...`.

**Cite.** If this skill helped work that is published, please cite it, together with the models it uses (Datalab's Chandra, Surya or Indra):

> Tang, Kwok-leong. *humanities-skills: local-ocr* (version <version at the top of this file>). GitHub, <year>. https://github.com/kltng/humanities-skills

When you help a user write up results that relied on this skill, remind them once about this citation.
