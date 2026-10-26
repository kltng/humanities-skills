---
name: historical-map
description: Generate interactive historical maps as standalone HTML files using Leaflet.js. Supports markers with popups, GeoJSON boundary overlays, historical tile layers (Academia Sinica, MapWarper), image overlays, WMS layers, and layer controls. Use when the user asks to create, build, or visualize a map of historical places, routes, boundaries, or events.
version: 1.0.2
license: MIT
author: Kwok-leong Tang
contributors:
  - name: Claude
    type: AI Assistant
---

# Historical Map Skill

Generate interactive historical maps as self-contained HTML files powered by Leaflet.js.

## Critical: Things Claude Won't Know Without This Skill

### The output is a standalone HTML file

The Python script generates a complete HTML file that loads Leaflet.js from CDN. No server, no build step, no pip install — just open in a browser. Zero external Python dependencies.

### Pre-configured basemaps are available

```python
from scripts.map_builder import BASEMAPS
# Keys: "osm", "watercolor", "toner_lite", "carto_light", "carto_dark"
```

`osm` (OpenStreetMap) is the default. It is the only one that works without an account.

The other four need a key (tested 2026-10-26):

- `carto_light`, `carto_dark`: every tile shows "API KEY REQUIRED" (see carto.com/basemaps/apikey).
- `watercolor`, `toner_lite` (Stadia): tiles return HTTP 401 when the HTML file is opened from disk. Stadia needs an account and a registered domain or API key.

The builder prints a warning if you pick one of these. Use them only if you have a key; add it to the tile URL yourself with `add_tile_layer(..., overlay=False)`.

### Historical world boundaries are one method call away

36 pre-configured GeoJSON boundary files (2000 BCE – 1994 CE) from `aourednik/historical-basemaps` (keys in `HISTORICAL_BOUNDARIES`):

```python
m.add_historical_boundaries("200_bce")   # World c. 200 BCE
m.add_historical_boundaries("100_ce")    # World c. 100 CE
m.add_historical_boundaries("1400_ce")   # World c. 1400 CE
```

These are fetched at runtime from GitHub by the browser. Each polygon has a `NAME` property for popups/tooltips.

### Available boundary periods

BCE: `2000_bce`, `1000_bce`, `500_bce`, `323_bce`, `200_bce`, `100_bce`, `1_bce`

CE: `100_ce` through `1994_ce` in ~100-year increments, plus special years: `1279_ce`, `1492_ce`, `1783_ce`, `1815_ce`, `1880_ce`, `1920_ce`, `1938_ce`, `1945_ce`, `1960_ce`

### What is HTML and what is plain text

`popup` and `attribution` strings are inserted as **HTML** (so `<b>`, `<br>`, links work). Only pass trusted HTML there; escape any text that comes from outside data. Everything else is treated as plain text and escaped for you: `label`, `tooltip`, layer and group names, and GeoJSON property values shown by `popup_property` / `tooltip_property`.

### Colored marker icons are loaded from GitHub

Marker colors: `blue`, `gold`, `red`, `green`, `orange`, `yellow`, `violet`, `grey`, `black`. These use the `pointhi/leaflet-color-markers` CDN icons.

### Academia Sinica provides Chinese historical map tiles

WMTS tiles based on Tan Qixiang's Historical Atlas of China (谭其骧《中国历史地图集》), covering 222 BCE – 1911 CE.
The server is WMTS only (it does not answer WMS `GetMap`), so do **not** use `add_wms_layer`.
Use `add_sinica_layer` with a layer ID:

```python
m.add_sinica_layer("ad1582")                 # Ming atlas
m.add_sinica_layer("ad0741", opacity=0.5)    # Tang atlas
```

One layer per dynasty volume (keys in `SINICA_LAYERS`, from the capabilities file, checked 2026-10-26):

| ID | Atlas map | ID | Atlas map |
|----|-----------|----|-----------|
| `bc0210` | Qin 秦 | `ad0612` | Sui 隋 |
| `bc0007` | Western Han 西漢 | `ad0741` | Tang 唐 |
| `ad0140` | Eastern Han 東漢 | `ad1111` | Northern Song 北宋 |
| `ad0262` | Three Kingdoms 三國 | `ad1208` | Southern Song 南宋 |
| `ad0281` | Western Jin 西晉 | `ad1330` | Yuan 元 |
| `ad0382` | Eastern Jin 東晉 | `ad1582` | Ming 明 |
| `ad0497` | Southern and Northern Dynasties 南北朝 | `ad1820` | Qing 清 |

Tiles of `ad0741`, `ad1111`, `ad1582`, `ad1820`, `bc0007` and `bc0210` were fetched and worked. The number in the ID is the atlas year (`ad1582` = 1582 CE).

Other layers (city maps, 1:50,000 sheets) are in the capabilities file:
`https://gis.sinica.edu.tw/ccts/wmts?SERVICE=WMTS&REQUEST=GetCapabilities`
Each layer's `ResourceURL template` gives its ID and image format, e.g. `Beijing_50K_1928b-png-...`.
For a PNG layer, `add_sinica_layer("Beijing_50K_1928b", name="Beijing 1928")` works. For a JPG layer, use
`add_tile_layer` with the template URL.

### MapWarper provides crowdsourced georeferenced historical maps

```python
m.add_mapwarper_layer(MAP_ID, name="Map title")
```

Find a map ID by browsing https://mapwarper.net/ in a browser, and open the map there first to check that it is rectified (warped). Unrectified maps have no tiles (the server returns HTTP 500). The site blocks automated access, so do not script lookups of its pages.

### TGAZ coordinates: watch for longitude 0

Coordinates from chgis-tgaz or tgaz-sqlite include thousands of duplicate POLYGON records whose longitude is 0 (a few have 1-5). Plotted, they land near Africa. Drop them before mapping: `api.search(..., drop_bad_coords=True)` in chgis-tgaz, or `--good-coords` in tgaz-sqlite. `add_marker` warns when latitude or longitude is exactly 0.

## Workflow

### 1. Build a map with the Python builder

```python
from scripts.map_builder import HistoricalMapBuilder

m = HistoricalMapBuilder(
    title="Tang Dynasty China",
    center=(35.0, 108.0),
    zoom=5,
    basemap="osm",   # the default; the others need an API key
)

# Add historical boundaries
m.add_historical_boundaries("700_ce", name="World c. 700 CE")

# Add markers
m.add_marker(34.26, 108.94, "Chang'an (長安)",
    popup="<b>Chang'an</b><br>Capital of the Tang Dynasty",
    color="red", group="Capitals")

m.add_marker(34.75, 113.65, "Luoyang (洛陽)",
    popup="<b>Luoyang</b><br>Eastern capital",
    color="red", group="Capitals")

m.add_marker(31.23, 121.47, "Huating (華亭)",
    popup="<b>Huating</b><br>Modern-day Shanghai area",
    color="blue", group="Cities")

# Add GeoJSON data (inline)
m.add_geojson(
    geojson_data,              # Any GeoJSON dict
    name="Grand Canal",
    style={"color": "#0077b6", "weight": 3},
    popup_property="name",     # Show feature.properties.name on click
    tooltip_property="name",   # Show on hover
)

# Add GeoJSON from URL (fetched by browser at runtime)
m.add_geojson_url(
    "https://example.com/data.geojson",
    name="Trade Routes",
    style={"color": "#e63946", "weight": 2, "dashArray": "5 3"},
)

# Add a scanned historical map as image overlay
m.add_image_overlay(
    "https://example.com/old_map.jpg",
    bounds=((30.0, 100.0), (42.0, 120.0)),  # (SW corner, NE corner)
    name="Historical Map",
    opacity=0.6,
)

# Add custom tile layer
m.add_tile_layer(
    "https://tiles.example.com/{z}/{x}/{y}.png",
    name="Custom Tiles",
    opacity=0.7,
)

# Save
m.save_html("tang_dynasty.html")
```

### 2. Open the HTML file

```bash
open tang_dynasty.html
```

Interactive features: pan, zoom, click markers for popups, hover for tooltips, toggle layers on/off via the layer control panel.

### 3. Combine with other skills

```python
# Use CBDB data to place historical figures on the map
# Use CHGIS/TGAZ data for accurate historical coordinates
# Use CJK Calendar to annotate dates
```

## Builder API Reference

### Constructor

```python
HistoricalMapBuilder(
    title="Map Title",
    center=(lat, lng),         # Default: (35.0, 105.0)
    zoom=5,                    # Default: 5, range 0-18
    basemap="osm",             # Key from BASEMAPS or "none"
)
```

### Methods

| Method | Description |
|--------|-------------|
| `add_marker(lat, lng, label, *, popup, tooltip, color, group)` | Colored marker with popup/tooltip |
| `add_geojson(data, name, *, style, popup_property, tooltip_property)` | Inline GeoJSON overlay |
| `add_geojson_url(url, name, *, style, popup_property, tooltip_property)` | Remote GeoJSON (fetched by browser) |
| `add_historical_boundaries(period, *, name, style)` | World boundaries from historical-basemaps |
| `add_tile_layer(url, name, *, attribution, max_zoom, opacity, overlay)` | XYZ tile layer |
| `add_sinica_layer(layer_id, name, *, opacity)` | Academia Sinica atlas layer (see `SINICA_LAYERS`) |
| `add_mapwarper_layer(map_id, name, *, opacity)` | MapWarper georeferenced map |
| `add_wms_layer(url, layers, name, *, fmt, transparent, opacity, attribution)` | WMS tile layer (real WMS servers only) |
| `add_image_overlay(url, bounds, name, *, opacity)` | Georeferenced image overlay |
| `save_html(path)` | Write standalone HTML file |

### Leaflet Style Options

```python
style = {
    "color": "#e63946",      # Stroke color (hex or CSS name)
    "weight": 2,             # Stroke width in pixels
    "opacity": 1,            # Stroke opacity (0-1)
    "fillColor": "#f1faee",  # Fill color (defaults to color)
    "fillOpacity": 0.2,      # Fill opacity (0-1)
    "dashArray": "5 3",      # Dash pattern
}
```

## API Etiquette

- **Historical boundaries**: Fetched from GitHub raw URLs — no rate limit, but cache results for repeated use
- **MapWarper**: Public tile service — use reasonably. Its robots.txt disallows automated access to map pages.
- **OpenStreetMap**: Follow the tile usage policy (https://operations.osmfoundation.org/policies/tiles/). Fine for viewing a map; do not bulk-download tiles.
- **Academia Sinica**: Public WMTS — use for academic purposes
- **Leaflet CDN**: No rate limits on `unpkg.com`

## Related Skills

- **cbdb-api** / **cbdb-local**: Retrieve biographical data with geographic coordinates to place historical figures on maps
- **chgis-tgaz** / **tgaz-sqlite**: Look up historical place names with coordinates for accurate marker placement
- **cjk-calendar**: Convert lunisolar dates for timeline annotations
- **historical-timeline**: Create a companion timeline visualization alongside the map
- **wikidata-search**: Retrieve coordinates and geographic identifiers for historical places

## Resources

- `references/map_reference.md` — Complete reference for basemaps, tile servers, boundary datasets, and Leaflet configuration
- `scripts/map_builder.py` — Python builder with zero dependencies for generating standalone HTML maps

## Feedback and Citation

**Report a problem.** This skill is part of the public repository [kltng/humanities-skills](https://github.com/kltng/humanities-skills). If it fails (an API changed, a script errors, or these instructions are wrong), report it as a GitHub issue:

1. Ask the user before filing. Issues are public.
2. Check for an existing report: `gh issue list --repo kltng/humanities-skills --state all --search "historical-map"`
3. File it: `gh issue create --repo kltng/humanities-skills --label bug --title "[historical-map] <short summary>" --body "<details>"`. Without `gh`, give the user this link: https://github.com/kltng/humanities-skills/issues/new?template=skill-problem.yml
4. Include the skill name and version, what you ran, the error text, what you expected, and the environment (OS, Python version). Leave out API keys, personal data, private file paths, and unpublished research.

**Cite.** If this skill helped work that is published, please cite it, together with the data source it uses:

> Tang, Kwok-leong. *humanities-skills: historical-map* (version <version at the top of this file>). GitHub, <year>. https://github.com/kltng/humanities-skills

When you help a user write up results that relied on this skill, remind them once about this citation.
