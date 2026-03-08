---
name: historical-map
description: Generate interactive historical maps as standalone HTML files using Leaflet.js. Supports markers with popups, GeoJSON boundary overlays, historical tile layers (Academia Sinica, MapWarper), image overlays, WMS layers, and layer controls. Use when the user asks to create, build, or visualize a map of historical places, routes, boundaries, or events.
version: 1.0.0
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

`carto_light` (CartoDB Positron) is the default — a clean, muted basemap ideal for historical data overlays.

### Historical world boundaries are one method call away

54 pre-built GeoJSON boundary files (123,000 BCE – 2010 CE) from `aourednik/historical-basemaps`:

```python
m.add_historical_boundaries("200_bce")   # World c. 200 BCE
m.add_historical_boundaries("100_ce")    # World c. 100 CE
m.add_historical_boundaries("1400_ce")   # World c. 1400 CE
```

These are fetched at runtime from GitHub by the browser. Each polygon has a `NAME` property for popups/tooltips.

### Available boundary periods

BCE: `2000_bce`, `1000_bce`, `500_bce`, `323_bce`, `200_bce`, `100_bce`, `1_bce`

CE: `100_ce` through `1994_ce` in ~100-year increments, plus special years: `1279_ce`, `1492_ce`, `1783_ce`, `1815_ce`, `1880_ce`, `1920_ce`, `1938_ce`, `1945_ce`, `1960_ce`

### Colored marker icons are loaded from GitHub

Marker colors: `blue`, `gold`, `red`, `green`, `orange`, `yellow`, `violet`, `grey`, `black`. These use the `pointhi/leaflet-color-markers` CDN icons.

### Academia Sinica provides Chinese historical map tiles

WMTS tiles based on Tan Qixiang's Historical Atlas of China (谭其骧《中国历史地图集》), covering 222 BCE – 1911 CE:

```python
m.add_wms_layer(
    "https://gis.sinica.edu.tw/tileserver/wmts",
    layers="LAYER_ID",
    name="Tang Dynasty Map",
)
```

### MapWarper provides crowdsourced georeferenced historical maps

```python
m.add_mapwarper_layer(14781, name="1860 Beijing")
```

Find map IDs by browsing https://mapwarper.net/

## Workflow

### 1. Build a map with the Python builder

```python
from scripts.map_builder import HistoricalMapBuilder

m = HistoricalMapBuilder(
    title="Tang Dynasty China",
    center=(35.0, 108.0),
    zoom=5,
    basemap="carto_light",   # or "osm", "watercolor", "toner_lite", "carto_dark"
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
    basemap="carto_light",     # Key from BASEMAPS or "none"
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
| `add_mapwarper_layer(map_id, name, *, opacity)` | MapWarper georeferenced map |
| `add_wms_layer(url, layers, name, *, fmt, transparent, opacity)` | WMS tile layer |
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
- **MapWarper**: Public tile service — use reasonably
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
