---
name: historical-timeline
description: Generate interactive historical timelines as standalone HTML files using TimelineJS3. Supports BCE/CE dates, eras, media, groups, and rich text. Use when the user asks to create, build, or visualize a timeline of historical events, periods, dynasties, or biographical milestones.
version: 1.0.0
license: MIT
author: Kwok-leong Tang
contributors:
  - name: Claude
    type: AI Assistant
---

# Historical Timeline Skill

Generate interactive historical timelines as self-contained HTML files powered by TimelineJS3.

## Critical: Things Claude Won't Know Without This Skill

### BCE dates use negative year numbers

```json
{"year": -551, "month": 9, "day": 28}
```

This renders as "551 BCE". No special syntax — just negative integers.

### The `scale` property matters for ancient dates

For timelines spanning thousands of years or BCE dates, set `"scale": "human"` (the default). Use `"scale": "cosmological"` only for astronomical/geological timescales.

### The output is a single standalone HTML file

The Python script generates a complete HTML file that loads TimelineJS3 from CDN. No server, no build step — just open in a browser. The JSON data is embedded inline.

### Title slide has no `start_date`

The `title` object is a special slide that appears first. It does **not** use `start_date`. Only `events` entries require dates.

### `display_date` overrides rendered dates

If the default date rendering is wrong (e.g., you want "Spring 221 BCE" instead of "221 BCE"), set `display_date` on the date object or the slide:

```json
{
  "start_date": {"year": -221},
  "display_date": "Spring 221 BCE",
  "text": {"headline": "Qin Unification"}
}
```

### Groups create labeled rows

Events with the same `group` string are clustered in adjacent rows on the timeline nav, making it easy to show parallel threads (e.g., "Politics", "Culture", "Military").

### Eras label background spans

Eras are colored bands behind the timeline that label periods (e.g., "Han Dynasty", "Tang Dynasty"). They require both `start_date` and `end_date`.

## Workflow

### 1. Generate timeline JSON

Build a TimelineJS3 JSON object with events. The Python script provides a builder API:

```python
from scripts.timeline_builder import TimelineBuilder

tl = TimelineBuilder(title="The Tang Dynasty", subtitle="618–907 CE")

# Add eras (colored background spans)
tl.add_era(-221, 220, "Imperial China Begins", end_month=12)
tl.add_era(618, 907, "Tang Dynasty", color="#2a9d8f")

# Add events
tl.add_event(
    start_year=618, start_month=6, start_day=18,
    headline="Li Yuan founds Tang",
    body="<p>After the collapse of the Sui dynasty...</p>",
    group="Politics",
)
tl.add_event(
    start_year=701, end_year=762,
    headline="Li Bai (李白)",
    body="<p>One of the greatest Chinese poets.</p>",
    group="Culture",
    media_url="https://upload.wikimedia.org/wikipedia/commons/4/4e/Li_Bai.jpg",
    media_caption="Li Bai, the Immortal Poet",
)
tl.add_event(
    start_year=-551, start_month=9, start_day=28,
    end_year=-479,
    headline="Confucius (孔子)",
    body="<p>Philosopher whose teachings shaped Chinese civilization.</p>",
    display_date="551–479 BCE",
)

# Save as standalone HTML
tl.save_html("tang_dynasty.html")

# Or get raw JSON for custom use
import json
print(json.dumps(tl.to_dict(), indent=2, ensure_ascii=False))
```

### 2. Open the HTML file

```bash
open tang_dynasty.html        # macOS
xdg-open tang_dynasty.html    # Linux
start tang_dynasty.html       # Windows
```

The timeline is fully interactive: click events, scroll through time, zoom in/out.

### 3. Customize appearance

Pass options to `save_html()`:

```python
tl.save_html(
    "timeline.html",
    font="Georgia-Helvetica",          # Built-in font pair
    initial_zoom=2,                     # Starting zoom level
    timenav_position="bottom",          # Nav bar position
    hash_bookmark=True,                 # URL updates with slide
    start_at_end=True,                  # Start at last event
    default_bg_color="#1a1a2e",         # Dark background
    language="zh-cn",                   # Chinese interface
)
```

## JSON Format Quick Reference

```json
{
  "title": {
    "text": {"headline": "Timeline Title", "text": "<p>Subtitle or description</p>"},
    "media": {"url": "https://example.com/image.jpg", "caption": "Credit"}
  },
  "events": [
    {
      "start_date": {"year": 618, "month": 6, "day": 18},
      "end_date": {"year": 907},
      "text": {"headline": "Event Title", "text": "<p>Details in HTML</p>"},
      "media": {"url": "...", "caption": "...", "credit": "..."},
      "group": "Category",
      "display_date": "Custom date text",
      "background": {"color": "#2a9d8f"},
      "unique_id": "event-001"
    }
  ],
  "eras": [
    {
      "start_date": {"year": 618},
      "end_date": {"year": 907},
      "text": {"headline": "Tang Dynasty"}
    }
  ],
  "scale": "human"
}
```

### Date object fields

| Field | Required | Type | Notes |
|-------|----------|------|-------|
| `year` | Yes | int | Negative for BCE (e.g., `-551`) |
| `month` | No | int | 1–12 |
| `day` | No | int | 1–31 |
| `hour` | No | int | 0–23 |
| `minute` | No | int | 0–59 |
| `second` | No | int | 0–59 |
| `display_date` | No | string | Overrides default rendering |

### Media types supported

TimelineJS3 auto-detects media type from URL:

- Images (jpg, png, gif, webp)
- YouTube, Vimeo, Dailymotion
- Wikipedia articles
- Google Maps
- Twitter/X posts
- Flickr, Instagram
- Spotify, SoundCloud
- PDF documents
- Any URL (renders as iframe)

## Built-in Font Pairs

`default`, `Bitter-Raleway`, `Dancing-Ledger`, `Georgia-Helvetica`, `Lustria-Lato`, `Medula-Lato`, `Old-Standard`, `Playfair-Faunaone`, `PT`, `Roboto-Megrim`, `Ubuntu`, `UnicaOne-Vollkorn`

## API Etiquette

- TimelineJS3 loads from `cdn.knightlab.com` — no rate limiting for the CDN itself
- If embedding media from external sources (Wikipedia, Wikimedia Commons), follow their usage policies
- Generated HTML files are fully offline-capable after first load (browser caches CDN assets)

## Related Skills

- **cbdb-api** / **cbdb-local**: Retrieve biographical data for Chinese historical figures to populate timeline events
- **chgis-tgaz**: Look up historical place names and coordinates for timeline event context
- **cjk-calendar**: Convert lunisolar dates to Gregorian for accurate timeline placement
- **arxiv-search**: Find scholarly articles about historical periods for timeline research

## Resources

- `references/timelinejs_reference.md` — Complete TimelineJS3 JSON format, options, and media type documentation
- `scripts/timeline_builder.py` — Python builder for generating timeline JSON and standalone HTML files
