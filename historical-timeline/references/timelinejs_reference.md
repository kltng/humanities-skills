# TimelineJS3 Reference

Complete reference for the TimelineJS3 JSON format, configuration options, and HTML embedding.

## JSON Format

### Top-Level Object

```json
{
  "title": { ... },
  "events": [ ... ],
  "eras": [ ... ],
  "scale": "human"
}
```

| Property | Required | Type | Description |
|----------|----------|------|-------------|
| `events` | Yes | Array of Slide Objects | Timeline events |
| `title` | No | Slide Object | Introductory slide (no `start_date` needed) |
| `eras` | No | Array of Era Objects | Labeled time spans shown as background bands |
| `scale` | No | String | `"human"` (default) or `"cosmological"` |

### Slide Object (events and title)

| Property | Required | Type | Description |
|----------|----------|------|-------------|
| `start_date` | Yes* | Date Object | Event start (*not required for title slide) |
| `end_date` | No | Date Object | Event end (creates a range) |
| `text` | No | Text Object | Headline and body content |
| `media` | No | Media Object | Image, video, or other media |
| `group` | No | String | Groups events with same value into labeled rows |
| `display_date` | No | String | Overrides the rendered date text |
| `background` | No | Object | `{"url": "...", "color": "#hex"}` |
| `autolink` | No | Boolean | Auto-detect links/emails (default: true) |
| `unique_id` | No | String | ID for hash bookmark linking |

### Date Object

| Property | Required | Type | Description |
|----------|----------|------|-------------|
| `year` | Yes | Number | Negative for BCE (e.g., `-551` → "551 BCE") |
| `month` | No | Number | 1–12 |
| `day` | No | Number | 1–31 |
| `hour` | No | Number | 0–23 |
| `minute` | No | Number | 0–59 |
| `second` | No | Number | 0–59 |
| `millisecond` | No | Number | 0–999 |
| `display_date` | No | String | Custom display text for this date |
| `format` | No | String | Formatting string override |

**BCE Examples:**

```json
{"year": -551}                           → "551 BCE"
{"year": -221, "display_date": "秦始皇統一"}  → "秦始皇統一"
{"year": -206, "month": 2}              → "Feb 206 BCE"
```

### Text Object

| Property | Required | Type | Description |
|----------|----------|------|-------------|
| `headline` | No | String | Title text (HTML supported) |
| `text` | No | String | Body content (HTML supported, not used for eras) |

### Media Object

| Property | Required | Type | Description |
|----------|----------|------|-------------|
| `url` | Yes | String | Media URL (auto-detected type) |
| `caption` | No | String | Description (HTML supported) |
| `credit` | No | String | Attribution (HTML supported) |
| `thumbnail` | No | String | Custom marker icon URL |
| `alt` | No | String | Image alt text (defaults to caption) |
| `title` | No | String | Image title attribute |
| `link` | No | String | Wraps media in anchor tag |
| `link_target` | No | String | Anchor target (e.g., `"_blank"`) |

### Era Object

| Property | Required | Type | Description |
|----------|----------|------|-------------|
| `start_date` | Yes | Date Object | Era start |
| `end_date` | Yes | Date Object | Era end |
| `text` | No | Text Object | Label (only `headline` is displayed) |

## Configuration Options

Pass as the third argument to `TL.Timeline()` or as options to `save_html()`.

### Display

| Option | Default | Type | Description |
|--------|---------|------|-------------|
| `font` | `"default"` | String | Font pair name or CSS URL |
| `height` | container | Number | Height in pixels |
| `width` | container | Number | Width in pixels |
| `theme` | `""` | String | `"contrast"` for high contrast |
| `default_bg_color` | `"white"` | String | Hex code or CSS color name |
| `language` | `"en"` | String | Language code (e.g., `"zh-cn"`, `"ja"`, `"ko"`) |

### Navigation

| Option | Default | Type | Description |
|--------|---------|------|-------------|
| `initial_zoom` | varies | Number | Starting zoom level index |
| `scale_factor` | `2` | Number | Screen widths for display |
| `zoom_sequence` | `[0.5,1,2,3,5,8,13,21,34,55,89]` | Array | Zoom multipliers |
| `timenav_position` | `"bottom"` | String | `"top"` or `"bottom"` |
| `timenav_height` | `150` | Number | Nav height in pixels |
| `timenav_height_percentage` | `25` | Number | Nav height as % of screen |
| `optimal_tick_width` | `100` | Number | Preferred axis tick spacing |

### Behavior

| Option | Default | Type | Description |
|--------|---------|------|-------------|
| `start_at_slide` | `0` | Number | Initial slide index |
| `start_at_end` | `false` | Boolean | Start at last event |
| `hash_bookmark` | `false` | Boolean | Update URL hash on navigation |
| `dragging` | `true` | Boolean | Enable drag panning |
| `duration` | `1000` | Number | Animation duration (ms) |
| `trackResize` | `true` | Boolean | Respond to window resize |
| `use_bc` | `false` | Boolean | Use "BC" suffix instead of "BCE" |

## Supported Languages

`en`, `zh-cn`, `zh-tw`, `ja`, `ko`, `ar`, `de`, `es`, `fr`, `he`, `hi`, `it`, `nl`, `pt`, `ru`, `tr`, `vi`, and many more.

## Media Types (auto-detected from URL)

| Type | URL Pattern |
|------|-------------|
| Image | `.jpg`, `.png`, `.gif`, `.webp`, `.svg` |
| YouTube | `youtube.com/watch?v=...`, `youtu.be/...` |
| Vimeo | `vimeo.com/...` |
| Wikipedia | `*.wikipedia.org/wiki/...` |
| Google Maps | `maps.google.com/...`, `goo.gl/maps/...` |
| Twitter/X | `twitter.com/.../status/...`, `x.com/.../status/...` |
| Flickr | `flickr.com/photos/...` |
| Spotify | `open.spotify.com/...` |
| SoundCloud | `soundcloud.com/...` |
| PDF | `.pdf` |
| iframe | Any other URL |

## HTML Embedding Template

Minimal standalone HTML:

```html
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Timeline</title>
  <link rel="stylesheet" href="https://cdn.knightlab.com/libs/timeline3/latest/css/timeline.css">
  <script src="https://cdn.knightlab.com/libs/timeline3/latest/js/timeline.js"></script>
  <style>
    html, body { height: 100%; margin: 0; padding: 0; }
    #timeline-embed { width: 100%; height: 100%; }
  </style>
</head>
<body>
  <div id="timeline-embed"></div>
  <script>
    var timelineData = { /* JSON here */ };
    var options = { /* options here */ };
    new TL.Timeline('timeline-embed', timelineData, options);
  </script>
</body>
</html>
```

## Complete Example: Chinese Dynasties

```json
{
  "title": {
    "text": {
      "headline": "Chinese Dynastic History",
      "text": "<p>Major dynasties from Qin to Qing</p>"
    }
  },
  "eras": [
    {
      "start_date": {"year": -221},
      "end_date": {"year": -206},
      "text": {"headline": "Qin"}
    },
    {
      "start_date": {"year": -206},
      "end_date": {"year": 220},
      "text": {"headline": "Han"}
    },
    {
      "start_date": {"year": 618},
      "end_date": {"year": 907},
      "text": {"headline": "Tang"}
    }
  ],
  "events": [
    {
      "start_date": {"year": -221},
      "text": {
        "headline": "Qin Unification",
        "text": "<p>Qin Shi Huang unifies China.</p>"
      },
      "group": "Politics"
    },
    {
      "start_date": {"year": -206},
      "end_date": {"year": -202},
      "text": {
        "headline": "Chu-Han Contention",
        "text": "<p>Civil war between Xiang Yu and Liu Bang.</p>"
      },
      "group": "Military"
    },
    {
      "start_date": {"year": 105},
      "text": {
        "headline": "Cai Lun improves papermaking",
        "text": "<p>A pivotal advancement in information technology.</p>"
      },
      "group": "Culture"
    }
  ],
  "scale": "human"
}
```
