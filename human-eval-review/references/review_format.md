# Human-Eval Review — Data Format Reference

A review file is rendered from a single structure:

```json
{
  "config": { ... },
  "items":  [ { ... }, ... ]
}
```

`config` becomes the page's `CONFIG`; `items` becomes `DATA`. The Python builder
(`ReviewBuilder`) produces exactly this via `to_dict()` / `to_json()`, and the CLI consumes it.

---

## `config`

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `title` | string | `"Review"` | Shown in the header and as the document title. |
| `subtitle` | string | – | Small line under the title. Omit to hide. |
| `lang` | string | `"en"` | `<html lang>`. Use `"zh-Hant"`, `"ja"`, etc. for CJK. |
| `cjk` | bool | `false` | Enables `word-break: break-all` for long unbroken CJK strings. |
| `theme` | object | – | CSS variable overrides, e.g. `{"--accent": "#3b82f6"}`. See **Theming**. |
| `result_filename` | string | `"review_results.json"` | Filename used by **Download Results**. |
| `storage_key` | string | falls back to `title` | Key for browser autosave. Set explicitly to keep autosave stable when the title changes between runs. |

---

## `items[]`

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `id` | string | index | Stable id; appears in results as `item_id`. Builder auto-assigns `"1"`, `"2"`… |
| `heading` | string | `"Item N"` | Card header label (e.g. `"Entry 7"`). |
| `source` | string | – | The text under review, shown prominently. |
| `source_html` | bool | `false` | If true, `source` is rendered as HTML (otherwise plain text). |
| `context` | array | – | Metadata rows: `[{"label": "Land name", "value": "佳洋"}]`. Rendered as a muted strip. |
| `questions` | array | **required** | One or more questions (below). |

An item with several questions renders them stacked inside one card. The card shows the green
**Reviewed** badge only when *all* its questions are reviewed.

---

## `questions[]`

Common fields (all types):

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `id` | string | `q1`, `q2`… | Unique within the item; appears in results as `question_id`. |
| `type` | string | `"match"` | One of `match`, `single`, `rating`, `boolean`, `text`. |
| `prompt` | string | – | Question label shown above the controls. |
| `notes` | bool | `false` | Adds an optional notes textarea (any type). |

### `type: "match"` and `type: "single"`

Both render a list of candidates. `match` = checkboxes (multi-select); `single` = radios
(one). Extra fields:

| Field | Type | Notes |
|-------|------|-------|
| `candidates` | array | Visible candidate rows (below). |
| `excluded` | array | Same shape; rendered in a collapsed "Show N excluded candidates" `<details>`, still selectable. |
| `allow_none` | bool | Adds "None of the above", mutually exclusive with candidates. |

**Reviewed** when ≥1 candidate is selected, or *None* is checked.

#### candidate object

| Field | Type | Notes |
|-------|------|-------|
| `id` | string | **required.** Stable id; this is what's returned in `selected`. |
| `label` | string | Short id/code shown in monospace at the left (e.g. `"7-2-15-2"`). |
| `title` | string | One-line description (plain text). |
| `excerpt` | string | Longer snippet. **Rendered as HTML** — wrap matches in `<mark>…</mark>`. Keep it trusted/builder-generated. |
| `score` | number | 0–100. Color-coded: ≥80 green, ≥50 amber, else brown. Shown as `(88)`. |
| `reason` | string | Italic rationale line under the candidate (plain text). |
| `preselected` | bool | Start checked. Use for high-confidence proposals so review is confirm-by-exception. |

### `type: "rating"`

| Field | Type | Notes |
|-------|------|-------|
| `scale` | object | `{"min": 1, "max": 5, "labels": {"1": "Poor", "5": "Great"}, "caption": "…"}`. `labels` and `caption` optional. |
| `default` | number | Optional starting value. |

Renders one button per value `min…max`. **Reviewed** when a value is chosen. Result: `rating`.

### `type: "boolean"`

| Field | Type | Notes |
|-------|------|-------|
| `labels` | object | `{"yes": "Correct", "no": "Incorrect"}` (defaults Yes/No). |
| `default` | bool | Optional starting value. |

Two buttons; clicking the active one again clears it. **Reviewed** when either is chosen.
Result: `value` (`true`/`false`).

### `type: "text"`

| Field | Type | Notes |
|-------|------|-------|
| `placeholder` | string | Textarea placeholder. |
| `rows` | number | Initial height (default 2). |
| `default` | string | Optional pre-filled text. |

**Reviewed** when the box is non-empty. Result: `text`.

---

## Results JSON (Download / Load)

```json
{
  "title": "…",
  "subtitle": "… or null",
  "exported_at": "ISO-8601 timestamp",
  "reviewed_count": 18,
  "total": 20,
  "results": [ { per-question result }, … ]
}
```

Per-question result fields:

| Field | Always | Notes |
|-------|--------|-------|
| `item_id`, `question_id` | yes | Join keys back to the input. |
| `type` | yes | The question type. |
| `reviewed` | yes | Whether this question meets its "reviewed" condition. |
| `item_heading`, `source`, `prompt` | when present | Echoed for readability. |
| `selected` | match/single | Array of selected candidate `id`s. |
| `none` | match/single | `true` if "None of the above" chosen. |
| `rating` | rating | Chosen value (or `null`). |
| `value` | boolean | `true` / `false` (or `null`). |
| `text` | text | The entered string. |
| `notes` | when `notes: true` | The notes string. |

**Load** re-imports this file: it matches each result by `item_id` + `question_id` and restores
the selection. Items/questions not present are left untouched, so a partial file resumes fine.

---

## Theming

The page is styled entirely with CSS custom properties. Override any of them through
`config.theme`. Defaults (the serif "manuscript" look):

| Variable | Default | Role |
|----------|---------|------|
| `--bg` | `#f5f3ee` | Page background |
| `--ink` / `--ink-soft` | `#2c2416` / `#1a1208` | Text |
| `--muted` / `--muted2` | `#7a6a50` / `#9a8870` | Secondary text |
| `--card` | `#ffffff` | Card background |
| `--line` / `--line-soft` / `--panel` | `#d9d2c5` / `#ede8df` / `#ede8df` | Borders & header strips |
| `--header-bg` / `--header-ink` | `#2c2416` / `#f5f3ee` | Top bar |
| `--accent` / `--accent-hi` / `--accent-lo` / `--accent-ink` | `#c8a060` / `#dfc08a` / `#b8945a` / `#2c2416` | Buttons, progress, active rating |
| `--reviewed` | `#8aad6e` | Reviewed badge / state |
| `--mark` | `#fff0a0` | `<mark>` highlight |
| `--hover` | `#faf8f4` | Row hover |
| `--score-high` / `--score-med` / `--score-low` | `#5a8a30` / `#c88020` / `#a06030` | Score colors |
| `--serif` / `--mono` | Georgia stack / Courier stack | Fonts |

Example — a cooler, modern palette:

```json
"theme": {
  "--bg": "#f8fafc", "--ink": "#0f172a", "--card": "#ffffff",
  "--header-bg": "#1e293b", "--accent": "#3b82f6", "--accent-ink": "#ffffff",
  "--reviewed": "#22c55e", "--serif": "system-ui, sans-serif"
}
```

---

## Keyboard shortcuts (built into the page)

| Key | Action |
|-----|--------|
| `j` / `↓` | Focus next question (scrolls into view) |
| `k` / `↑` | Focus previous question |
| `1`–`9` | Select / toggle the Nth option (match/single), or set the Nth rating, or Yes/No |
| `n` | Toggle "None of the above" on the focused question |
| `?` | Toggle the help overlay |
| `Esc` | Close help / blur the current field |

Shortcuts are ignored while typing in a textarea or input, so notes and corrections type normally.
