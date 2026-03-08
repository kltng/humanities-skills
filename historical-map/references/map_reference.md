# Historical Map Reference

Complete reference for basemaps, tile servers, historical boundary datasets, and Leaflet.js configuration.

## Basemaps

Pre-configured in `BASEMAPS` dict:

| Key | Name | Style | Max Zoom |
|-----|------|-------|----------|
| `osm` | OpenStreetMap | Standard street map | 19 |
| `watercolor` | Stamen Watercolor | Artistic, painterly (good for historical feel) | 16 |
| `toner_lite` | Stamen Toner Lite | Minimal black/white | 20 |
| `carto_light` | CartoDB Positron | Clean, muted (default — ideal for data overlays) | 20 |
| `carto_dark` | CartoDB Dark Matter | Dark theme | 20 |

### Using a custom basemap

```python
m.add_tile_layer(
    "https://tiles.example.com/{z}/{x}/{y}.png",
    name="Custom Basemap",
    overlay=False,   # False = appears in basemap selector, not overlays
)
```

## Historical Map Tile Servers

### Academia Sinica CCTS (Chinese Historical Maps)

Based on Tan Qixiang's Historical Atlas of China (谭其骧《中国历史地图集》). Coverage: 222 BCE – 1911 CE.

**WMTS endpoint:**
```
https://gis.sinica.edu.tw/ccts/wmts
```

**Usage with builder:**
```python
m.add_wms_layer(
    "https://gis.sinica.edu.tw/ccts/wmts",
    layers="LAYER_ID",
    name="Historical China",
    attribution='<a href="https://gis.sinica.edu.tw/">Academia Sinica</a>',
)
```

**Explorer:** https://gis.sinica.edu.tw/worldmap/

### MapWarper (Crowdsourced Georeferenced Maps)

**Tile URL pattern:**
```
https://mapwarper.net/maps/tile/{map_id}/{z}/{x}/{y}.png
```

**Usage with builder:**
```python
m.add_mapwarper_layer(14781, name="Historical Map Name")
```

**Browse maps:** https://mapwarper.net/

### NYPL Map Warper

**Tile URL pattern:**
```
https://maps.nypl.org/warper/maps/tile/{map_id}/{z}/{x}/{y}.png
```

### David Rumsey Map Collection

**Explorer:** https://www.davidrumsey.com/
**GeoGarage:** https://rumsey.geogarage.com/

150,000+ historical maps, many georeferenced.

### NLS (National Library of Scotland) Historic Maps

**API docs:** https://maps.nls.uk/projects/api/
**Free tier:** 100,000 tile requests/month (non-commercial)

### OpenHistoricalMap

**Vector tiles:** https://vtiles.openhistoricalmap.org/
**Best with MapLibre GL JS** (not Leaflet raster tiles)

## Historical Boundary Datasets

### aourednik/historical-basemaps (Built-in)

Pre-configured in `HISTORICAL_BOUNDARIES` dict. 54 GeoJSON files from 123,000 BCE to 2010 CE.

**Source:** https://github.com/aourednik/historical-basemaps
**Format:** GeoJSON (WGS 84 / EPSG:4326)
**License:** Open (work in progress)

**Feature properties:**
| Property | Description |
|----------|-------------|
| `NAME` | Country/polity name |
| `SUBJECTO` | Colonial/imperial power (if applicable) |
| `PARTOF` | Parent entity |
| `BORDERPRECISION` | 1 = precise, 2 = approximate, 3 = very approximate |

**Available periods:**

BCE:
```
2000_bce  1000_bce  500_bce  323_bce  200_bce  100_bce  1_bce
```

CE:
```
100_ce   200_ce   300_ce   400_ce   500_ce   600_ce   700_ce
800_ce   900_ce   1000_ce  1100_ce  1200_ce  1279_ce  1300_ce
1400_ce  1492_ce  1500_ce  1600_ce  1700_ce  1783_ce  1800_ce
1815_ce  1880_ce  1900_ce  1920_ce  1938_ce  1945_ce  1960_ce
1994_ce
```

### CHGIS (China Historical GIS)

**Source:** https://chgis.fas.harvard.edu/
**Download:** https://dataverse.harvard.edu/dataverse/chgis_v6
**Format:** Shapefiles (convertible to GeoJSON)
**Coverage:** 222 BCE – 1911 CE, Chinese administrative boundaries
**License:** Free for academic use, registration required

### Ancient World Mapping Center (AWMC)

**Source:** https://github.com/AWMC/geodata
**Format:** GeoJSON and Shapefiles
**Coverage:** Ancient Mediterranean / Classical world
**License:** ODC Open Database License

### Natural Earth (Modern Reference)

**Source:** https://www.naturalearthdata.com/
**Format:** Shapefiles, GeoJSON conversions available
**Coverage:** Current-day boundaries only (useful as reference basemap)
**License:** Public domain

## Leaflet.js Reference

### Tile Layer

```javascript
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '© OpenStreetMap',
    maxZoom: 19,
    opacity: 0.7
}).addTo(map);
```

### WMS Layer

```javascript
L.tileLayer.wms('https://wms.example.com/service', {
    layers: 'layer_name',
    format: 'image/png',
    transparent: true,
    opacity: 0.7
}).addTo(map);
```

### Image Overlay

```javascript
L.imageOverlay('https://example.com/map.jpg', [
    [south_lat, west_lng],   // Southwest corner
    [north_lat, east_lng]    // Northeast corner
], {opacity: 0.7}).addTo(map);
```

### GeoJSON Layer

```javascript
L.geoJSON(geojsonData, {
    style: function(feature) {
        return {color: '#e63946', weight: 2, fillOpacity: 0.2};
    },
    onEachFeature: function(feature, layer) {
        if (feature.properties && feature.properties.name) {
            layer.bindPopup('<b>' + feature.properties.name + '</b>');
            layer.bindTooltip(feature.properties.name);
        }
    }
}).addTo(map);
```

### Marker with Colored Icon

```javascript
var icon = L.icon({
    iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-red.png',
    shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
    iconSize: [25, 41], iconAnchor: [12, 41],
    popupAnchor: [1, -34], shadowSize: [41, 41]
});
L.marker([lat, lng], {icon: icon})
    .bindPopup('<b>Place Name</b><br>Description')
    .bindTooltip('Place Name')
    .addTo(map);
```

Available colors: `blue`, `gold`, `red`, `green`, `orange`, `yellow`, `violet`, `grey`, `black`

### Layer Control

```javascript
var baseMaps = {"OpenStreetMap": osmLayer, "Watercolor": watercolorLayer};
var overlayMaps = {"Boundaries": boundaryLayer, "Cities": markerGroup};
L.control.layers(baseMaps, overlayMaps, {collapsed: false}).addTo(map);
```

### Style Options

| Property | Type | Description |
|----------|------|-------------|
| `color` | String | Stroke color (hex or CSS name) |
| `weight` | Number | Stroke width in pixels |
| `opacity` | Number | Stroke opacity (0–1) |
| `fillColor` | String | Fill color (defaults to `color`) |
| `fillOpacity` | Number | Fill opacity (0–1) |
| `dashArray` | String | Dash pattern (e.g., `"5 3"`, `"10 5 3 5"`) |
| `lineCap` | String | `"butt"`, `"round"`, `"square"` |
| `lineJoin` | String | `"miter"`, `"round"`, `"bevel"` |

## GeoJSON Format Quick Reference

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "properties": {
        "name": "Han Dynasty",
        "start_year": -206,
        "end_year": 220
      },
      "geometry": {
        "type": "Polygon",
        "coordinates": [[[lng, lat], [lng, lat], ...]]
      }
    },
    {
      "type": "Feature",
      "properties": {"name": "Silk Road"},
      "geometry": {
        "type": "LineString",
        "coordinates": [[lng, lat], [lng, lat], ...]
      }
    },
    {
      "type": "Feature",
      "properties": {"name": "Chang'an"},
      "geometry": {
        "type": "Point",
        "coordinates": [108.94, 34.26]
      }
    }
  ]
}
```

**Important:** GeoJSON uses `[longitude, latitude]` order (opposite of Leaflet's `[lat, lng]`).

## Common Coordinate References

| Place | Latitude | Longitude | Notes |
|-------|----------|-----------|-------|
| Chang'an (長安) | 34.26 | 108.94 | Tang capital (modern Xi'an) |
| Luoyang (洛陽) | 34.75 | 113.65 | Eastern capital |
| Beijing (北京) | 39.90 | 116.40 | Ming/Qing capital |
| Nanjing (南京) | 32.06 | 118.80 | Ming early capital |
| Hangzhou (杭州) | 30.25 | 120.17 | Song southern capital |
| Kaifeng (開封) | 34.80 | 114.35 | Song northern capital |
| Dunhuang (敦煌) | 40.14 | 94.66 | Silk Road gateway |
| Kashgar (喀什) | 39.47 | 75.99 | Western Silk Road |
| Guangzhou (廣州) | 23.13 | 113.26 | Maritime trade hub |
| Quanzhou (泉州) | 24.87 | 118.68 | Maritime Silk Road port |
