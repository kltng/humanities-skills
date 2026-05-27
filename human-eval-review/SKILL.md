---
name: human-eval-review
description: Generate a single self-contained HTML file for human-in-the-loop evaluation of model output. The reviewer opens it in a browser, makes per-item judgments (pick the matching candidate(s), choose one, rate on a scale, yes/no, or free-text correction), and exports their decisions as JSON. Use when you have analysis output — candidate matches, rankings, classifications, translations, extractions — that a human needs to review, confirm, score, or correct.
version: 1.0.0
license: MIT
author: Kwok-leong Tang
contributors:
  - name: Claude
    type: AI Assistant
---

# Human-Eval Review Skill

Turn analysis output into a **single self-contained HTML review file**. A human opens it
in any browser (no server, no build step, no internet), works through the items, and clicks
**Download Results** to export their judgments as JSON. Progress is autosaved in the browser,
and a previous results file can be re-loaded to resume.

This generalizes a family of "did the model get it right?" review tasks into one builder.

## When to Use

- You ran a matching / retrieval / classification / extraction / translation step and a human
  needs to confirm, correct, score, or rank the output before it's trusted.
- You want a clean review UI you can hand to a collaborator who has only a browser.
- You're building a labeled gold set from model proposals.

## Critical: Things Claude Won't Know Without This Skill

### The output is ONE file, rendered from embedded data

`scripts/review_builder.py` substitutes your data into `scripts/template.html` and writes a
complete HTML file with the CSS, the renderer JS, and the data all inline. There is no CDN and
no dependency. The reviewer can be fully offline.

### You shape the data; the page renders it

The renderer is data-driven. You produce a `{"config": {...}, "items": [...]}` structure
(directly, or via the `ReviewBuilder` API), and the page builds itself. To support a new
review task you change the **data**, never the template.

### `excerpt` is the only field rendered as HTML — use `<mark>` for highlights

In a candidate, `excerpt` is injected as HTML so you can wrap matched spans in `<mark>…</mark>`
(rendered as a yellow highlight, exactly like the examples). All other fields (`title`,
`reason`, `source`, notes) are inserted as plain text and are safe. Only put trusted,
builder-generated HTML in `excerpt`.

### Five question types cover most eval shapes

| `type` | Reviewer does | "Reviewed" when |
|--------|---------------|-----------------|
| `match` | checks **any** matching candidates (multi-select) | ≥1 candidate or *None* checked |
| `single` | picks **one** candidate (radio) | one candidate or *None* chosen |
| `rating` | clicks a value on a scale (e.g. 1–5) | a value is chosen |
| `boolean` | clicks Yes / No | either chosen |
| `text` | types a correction | the box is non-empty |

`allow_none: true` adds a "None of the above" option (mutually exclusive with candidates).
`notes: true` adds an optional free-text notes box to any question. An item can hold **several
questions** (e.g. one per sub-entry) — progress counts questions, not items.

### Excluded candidates stay selectable

Candidates you put in `excluded` render inside a collapsed "Show N excluded candidates"
`<details>` block. They're still selectable, so a reviewer can rescue one the system wrongly
dropped — useful for catching false negatives.

### CJK text needs `cjk: true`

Set `cjk: true` (and an appropriate `lang`, e.g. `zh-Hant`) to enable `word-break: break-all`
so long unbroken Chinese strings wrap. The default theme is a serif "manuscript" look; override
any CSS variable via `theme` (see `references/review_format.md`).

## Workflow

### 1. Point at the analysis output and shape it

Read whatever the upstream step produced (CSV, JSON, JSONL, markdown table) and map it onto
items + questions. The fluent builder is usually the most direct:

```python
from scripts.review_builder import ReviewBuilder

rb = ReviewBuilder(
    title="Deed Matching Review",
    subtitle="Fufang Will vs. Jitou Collection",
    lang="zh-Hant", cjk=True,
    result_filename="deed_review_results.json",
)

for row in analysis_rows:                       # however your data is shaped
    item = rb.add_item(source=row["deed_text"], heading=f"Entry {row['n']}")
    q = item.add_question(type="match", allow_none=True, notes=True)
    for cand in row["candidates"][:5]:          # e.g. top-5
        q.add_candidate(
            id=cand["doc_id"], label=cand["doc_id"], title=cand["title"],
            excerpt=cand.get("excerpt"),        # may contain <mark>…</mark>
            score=cand.get("score"), reason=cand.get("reason"),
            preselected=cand.get("score", 0) >= 90,   # optional: pre-check strong hits
        )
    for cand in row["candidates"][5:]:          # the rest, collapsed
        q.add_excluded(id=cand["doc_id"], label=cand["doc_id"], title=cand["title"],
                       score=cand.get("score"))

rb.save_html("deed_review.html")
```

Other question types:

```python
item.add_question(type="single", allow_none=True)        # pick exactly one
item.add_question(type="rating",
                  scale={"min": 1, "max": 5,
                         "labels": {"1": "1 Poor", "5": "5 Excellent"},
                         "caption": "Judge fidelity and fluency."})
item.add_question(type="boolean", labels={"yes": "Correct", "no": "Incorrect"})
item.add_question(type="text", placeholder="Enter the corrected transcription", rows=3)
```

### 2. Generate the file

`rb.save_html("review.html")` — or, if you assembled a data dict / JSON file instead:

```bash
python scripts/review_builder.py data.json -o review.html
```

where `data.json` is `{"config": {...}, "items": [...]}` (get this shape from `rb.to_dict()` /
`rb.to_json()`). Then open it:

```bash
open review.html        # macOS
xdg-open review.html    # Linux
```

### 3. Review, export, resume

- The reviewer works top to bottom; the header bar shows live progress and a green **Reviewed**
  badge appears on each completed card.
- **Keyboard:** `j`/`k` (or ↑/↓) move between questions, `1`–`9` select the Nth option / rating,
  `n` toggles *None*, `?` shows help.
- Work is **autosaved to the browser** continuously; reopening the same file restores it and
  shows a "Restored your in-progress review" banner (**Start over** clears it).
- **Download Results** writes the JSON. **Load** re-imports a downloaded results file to resume
  on another machine.

### 4. Read the results JSON back

```json
{
  "title": "Deed Matching Review",
  "exported_at": "2026-05-27T12:00:00.000Z",
  "reviewed_count": 18, "total": 20,
  "results": [
    {"item_id": "1", "question_id": "q1", "type": "match", "reviewed": true,
     "source": "毛陳氏賣契壹紙…", "selected": ["7-2-15-2"], "none": false, "notes": ""},
    {"item_id": "3", "question_id": "q1", "type": "single", "reviewed": true,
     "selected": [], "none": true},
    {"item_id": "5", "question_id": "q1", "type": "rating", "reviewed": true, "rating": 4},
    {"item_id": "6", "question_id": "q1", "type": "boolean", "reviewed": true, "value": false},
    {"item_id": "7", "question_id": "q1", "type": "text", "reviewed": true, "text": "…"}
  ]
}
```

Each result carries `item_id` + `question_id` (the join keys), `type`, `reviewed`, and the
type-specific answer. Use it to build gold labels, compute agreement, or feed the next step.

## Best Practices

- **Pre-select high-confidence proposals** (`preselected=True`) so the reviewer confirms by
  exception rather than selecting everything from scratch — but only when scores are reliable.
- **Show the model's reasoning.** Populate `reason` and `<mark>` the matched span in `excerpt`;
  it dramatically speeds up adjudication.
- **Keep the visible candidate list short** (top ~5) and push the long tail into `excluded`.
- **One question per decision.** For sub-entry tasks, add multiple questions to one item rather
  than cramming choices together — progress and results stay clean.
- **Set a stable `storage_key`** in config if the title changes between runs but you want the
  browser autosave to carry over (otherwise autosave keys off the title).

## Related Skills

- **cbdb-local / tgaz-sqlite / wikidata-search** — produce the candidate matches this skill
  reviews (entity linking, placename resolution).
- **sync-html** — push the generated review file to the central HTML vault so a collaborator
  can open it from the browser.

## Resources

- `scripts/review_builder.py` — zero-dependency Python builder + CLI.
- `scripts/template.html` — the HTML/CSS/JS template (edit only to change look or behavior for
  *all* reviews; per-task changes go in the data).
- `references/review_format.md` — complete data schema, every field, theming variables, and the
  results JSON spec.
