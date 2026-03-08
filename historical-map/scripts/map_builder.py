"""
Historical map builder — zero external dependencies.

Generates standalone HTML files with interactive Leaflet.js maps.
Supports markers, GeoJSON overlays, historical tile layers, image
overlays, and layer controls. All loaded from CDN — no server needed.
"""

import json
from typing import Any, Optional


# CDN URLs
_LEAFLET_CSS = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
_LEAFLET_JS = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"

# Pre-configured basemap tile URLs
BASEMAPS = {
    "osm": {
        "name": "OpenStreetMap",
        "url": "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
        "attribution": '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
        "max_zoom": 19,
    },
    "watercolor": {
        "name": "Stamen Watercolor",
        "url": "https://tiles.stadiamaps.com/tiles/stamen_watercolor/{z}/{x}/{y}.jpg",
        "attribution": '&copy; <a href="https://stadiamaps.com/">Stadia</a> &copy; <a href="https://stamen.com/">Stamen</a>',
        "max_zoom": 16,
    },
    "toner_lite": {
        "name": "Stamen Toner Lite",
        "url": "https://tiles.stadiamaps.com/tiles/stamen_toner_lite/{z}/{x}/{y}.png",
        "attribution": '&copy; <a href="https://stadiamaps.com/">Stadia</a> &copy; <a href="https://stamen.com/">Stamen</a>',
        "max_zoom": 20,
    },
    "carto_light": {
        "name": "CartoDB Positron",
        "url": "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
        "attribution": '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> &copy; <a href="https://carto.com/">CARTO</a>',
        "max_zoom": 20,
    },
    "carto_dark": {
        "name": "CartoDB Dark Matter",
        "url": "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
        "attribution": '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> &copy; <a href="https://carto.com/">CARTO</a>',
        "max_zoom": 20,
    },
}

# Historical boundary GeoJSON URLs (aourednik/historical-basemaps)
HISTORICAL_BOUNDARIES = {
    "2000_bce": "https://raw.githubusercontent.com/aourednik/historical-basemaps/master/geojson/world_bc2000.geojson",
    "1000_bce": "https://raw.githubusercontent.com/aourednik/historical-basemaps/master/geojson/world_bc1000.geojson",
    "500_bce": "https://raw.githubusercontent.com/aourednik/historical-basemaps/master/geojson/world_bc500.geojson",
    "323_bce": "https://raw.githubusercontent.com/aourednik/historical-basemaps/master/geojson/world_bc323.geojson",
    "200_bce": "https://raw.githubusercontent.com/aourednik/historical-basemaps/master/geojson/world_bc200.geojson",
    "100_bce": "https://raw.githubusercontent.com/aourednik/historical-basemaps/master/geojson/world_bc100.geojson",
    "1_bce": "https://raw.githubusercontent.com/aourednik/historical-basemaps/master/geojson/world_bc1.geojson",
    "100_ce": "https://raw.githubusercontent.com/aourednik/historical-basemaps/master/geojson/world_100.geojson",
    "200_ce": "https://raw.githubusercontent.com/aourednik/historical-basemaps/master/geojson/world_200.geojson",
    "300_ce": "https://raw.githubusercontent.com/aourednik/historical-basemaps/master/geojson/world_300.geojson",
    "400_ce": "https://raw.githubusercontent.com/aourednik/historical-basemaps/master/geojson/world_400.geojson",
    "500_ce": "https://raw.githubusercontent.com/aourednik/historical-basemaps/master/geojson/world_500.geojson",
    "600_ce": "https://raw.githubusercontent.com/aourednik/historical-basemaps/master/geojson/world_600.geojson",
    "700_ce": "https://raw.githubusercontent.com/aourednik/historical-basemaps/master/geojson/world_700.geojson",
    "800_ce": "https://raw.githubusercontent.com/aourednik/historical-basemaps/master/geojson/world_800.geojson",
    "900_ce": "https://raw.githubusercontent.com/aourednik/historical-basemaps/master/geojson/world_900.geojson",
    "1000_ce": "https://raw.githubusercontent.com/aourednik/historical-basemaps/master/geojson/world_1000.geojson",
    "1100_ce": "https://raw.githubusercontent.com/aourednik/historical-basemaps/master/geojson/world_1100.geojson",
    "1200_ce": "https://raw.githubusercontent.com/aourednik/historical-basemaps/master/geojson/world_1200.geojson",
    "1279_ce": "https://raw.githubusercontent.com/aourednik/historical-basemaps/master/geojson/world_1279.geojson",
    "1300_ce": "https://raw.githubusercontent.com/aourednik/historical-basemaps/master/geojson/world_1300.geojson",
    "1400_ce": "https://raw.githubusercontent.com/aourednik/historical-basemaps/master/geojson/world_1400.geojson",
    "1492_ce": "https://raw.githubusercontent.com/aourednik/historical-basemaps/master/geojson/world_1492.geojson",
    "1500_ce": "https://raw.githubusercontent.com/aourednik/historical-basemaps/master/geojson/world_1500.geojson",
    "1600_ce": "https://raw.githubusercontent.com/aourednik/historical-basemaps/master/geojson/world_1600.geojson",
    "1700_ce": "https://raw.githubusercontent.com/aourednik/historical-basemaps/master/geojson/world_1700.geojson",
    "1783_ce": "https://raw.githubusercontent.com/aourednik/historical-basemaps/master/geojson/world_1783.geojson",
    "1800_ce": "https://raw.githubusercontent.com/aourednik/historical-basemaps/master/geojson/world_1800.geojson",
    "1815_ce": "https://raw.githubusercontent.com/aourednik/historical-basemaps/master/geojson/world_1815.geojson",
    "1880_ce": "https://raw.githubusercontent.com/aourednik/historical-basemaps/master/geojson/world_1880.geojson",
    "1900_ce": "https://raw.githubusercontent.com/aourednik/historical-basemaps/master/geojson/world_1900.geojson",
    "1920_ce": "https://raw.githubusercontent.com/aourednik/historical-basemaps/master/geojson/world_1920.geojson",
    "1938_ce": "https://raw.githubusercontent.com/aourednik/historical-basemaps/master/geojson/world_1938.geojson",
    "1945_ce": "https://raw.githubusercontent.com/aourednik/historical-basemaps/master/geojson/world_1945.geojson",
    "1960_ce": "https://raw.githubusercontent.com/aourednik/historical-basemaps/master/geojson/world_1960.geojson",
    "1994_ce": "https://raw.githubusercontent.com/aourednik/historical-basemaps/master/geojson/world_1994.geojson",
}


class HistoricalMapBuilder:
    """Builder for interactive Leaflet.js historical maps.

    Parameters
    ----------
    title : str
        Map title (shown in browser tab and optional header).
    center : tuple[float, float]
        Initial map center as ``(latitude, longitude)``.
    zoom : int
        Initial zoom level (0–18).
    basemap : str
        Key from ``BASEMAPS`` dict or ``"none"`` for no basemap.
    """

    def __init__(
        self,
        title: str = "Historical Map",
        center: tuple[float, float] = (35.0, 105.0),
        zoom: int = 5,
        basemap: str = "carto_light",
    ) -> None:
        self.title = title
        self.center = center
        self.zoom = zoom
        self.basemap = basemap

        self._markers: list[dict[str, Any]] = []
        self._geojson_layers: list[dict[str, Any]] = []
        self._geojson_url_layers: list[dict[str, Any]] = []
        self._tile_layers: list[dict[str, Any]] = []
        self._image_overlays: list[dict[str, Any]] = []
        self._wms_layers: list[dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Markers
    # ------------------------------------------------------------------

    def add_marker(
        self,
        lat: float,
        lng: float,
        label: str,
        *,
        popup: Optional[str] = None,
        tooltip: Optional[str] = None,
        color: str = "blue",
        group: Optional[str] = None,
    ) -> "HistoricalMapBuilder":
        """Add a marker with optional popup and tooltip.

        Parameters
        ----------
        lat, lng : float
            Marker coordinates.
        label : str
            Internal label (used as default tooltip if tooltip not set).
        popup : str, optional
            HTML content shown on click.
        tooltip : str, optional
            Text shown on hover.
        color : str
            Marker color. One of: blue, gold, red, green, orange, yellow,
            violet, grey, black.
        group : str, optional
            Layer group name (for layer control toggle).
        """
        self._markers.append({
            "lat": lat,
            "lng": lng,
            "label": label,
            "popup": popup or f"<b>{label}</b>",
            "tooltip": tooltip or label,
            "color": color,
            "group": group,
        })
        return self

    # ------------------------------------------------------------------
    # GeoJSON layers
    # ------------------------------------------------------------------

    def add_geojson(
        self,
        geojson: dict[str, Any],
        name: str = "GeoJSON",
        *,
        style: Optional[dict[str, Any]] = None,
        popup_property: Optional[str] = None,
        tooltip_property: Optional[str] = None,
    ) -> "HistoricalMapBuilder":
        """Add inline GeoJSON data as a map layer.

        Parameters
        ----------
        geojson : dict
            A GeoJSON FeatureCollection or Feature.
        name : str
            Layer name (shown in layer control).
        style : dict, optional
            Leaflet path style: ``{"color": "#e63946", "weight": 2,
            "fillOpacity": 0.3}``.
        popup_property : str, optional
            Feature property key to show in popup on click.
        tooltip_property : str, optional
            Feature property key to show on hover.
        """
        self._geojson_layers.append({
            "data": geojson,
            "name": name,
            "style": style or {"color": "#e63946", "weight": 2, "fillOpacity": 0.2},
            "popup_property": popup_property,
            "tooltip_property": tooltip_property,
        })
        return self

    def add_geojson_url(
        self,
        url: str,
        name: str = "GeoJSON",
        *,
        style: Optional[dict[str, Any]] = None,
        popup_property: Optional[str] = None,
        tooltip_property: Optional[str] = None,
    ) -> "HistoricalMapBuilder":
        """Add a GeoJSON layer loaded from a URL at runtime.

        Parameters
        ----------
        url : str
            URL to a GeoJSON file (fetched by the browser).
        name : str
            Layer name (shown in layer control).
        style : dict, optional
            Leaflet path style.
        popup_property : str, optional
            Feature property key to show in popup on click.
        tooltip_property : str, optional
            Feature property key to show on hover.
        """
        self._geojson_url_layers.append({
            "url": url,
            "name": name,
            "style": style or {"color": "#457b9d", "weight": 2, "fillOpacity": 0.2},
            "popup_property": popup_property,
            "tooltip_property": tooltip_property,
        })
        return self

    def add_historical_boundaries(
        self,
        period: str,
        *,
        name: Optional[str] = None,
        style: Optional[dict[str, Any]] = None,
    ) -> "HistoricalMapBuilder":
        """Add world historical boundaries from aourednik/historical-basemaps.

        Parameters
        ----------
        period : str
            Key from ``HISTORICAL_BOUNDARIES``, e.g. ``"200_bce"``,
            ``"618_ce"``, ``"1400_ce"``.
        name : str, optional
            Layer name (defaults to formatted period).
        style : dict, optional
            Leaflet path style.
        """
        url = HISTORICAL_BOUNDARIES.get(period)
        if url is None:
            available = ", ".join(sorted(HISTORICAL_BOUNDARIES.keys()))
            raise ValueError(
                f"Unknown period {period!r}. Available: {available}"
            )
        display_name = name or f"World {period.replace('_', ' ').upper()}"
        self.add_geojson_url(
            url,
            name=display_name,
            style=style or {"color": "#6c5b7b", "weight": 1.5, "fillOpacity": 0.15},
            popup_property="NAME",
            tooltip_property="NAME",
        )
        return self

    # ------------------------------------------------------------------
    # Tile layers
    # ------------------------------------------------------------------

    def add_tile_layer(
        self,
        url: str,
        name: str,
        *,
        attribution: str = "",
        max_zoom: int = 18,
        opacity: float = 0.7,
        overlay: bool = True,
    ) -> "HistoricalMapBuilder":
        """Add a custom XYZ tile layer.

        Parameters
        ----------
        url : str
            Tile URL template with ``{z}``, ``{x}``, ``{y}`` placeholders.
        name : str
            Layer name (shown in layer control).
        opacity : float
            Initial layer opacity (0–1).
        overlay : bool
            If True, shown in overlay section of layer control.
            If False, shown as alternative basemap.
        """
        self._tile_layers.append({
            "url": url,
            "name": name,
            "attribution": attribution,
            "max_zoom": max_zoom,
            "opacity": opacity,
            "overlay": overlay,
        })
        return self

    def add_mapwarper_layer(
        self,
        map_id: int,
        name: str = "MapWarper",
        *,
        opacity: float = 0.7,
    ) -> "HistoricalMapBuilder":
        """Add a georeferenced historical map from MapWarper.

        Parameters
        ----------
        map_id : int
            MapWarper map ID (visible in the MapWarper URL).
        name : str
            Layer name.
        opacity : float
            Layer opacity (0–1).
        """
        url = f"https://mapwarper.net/maps/tile/{map_id}/{{z}}/{{x}}/{{y}}.png"
        self.add_tile_layer(
            url, name,
            attribution='<a href="https://mapwarper.net/">MapWarper</a>',
            opacity=opacity,
        )
        return self

    # ------------------------------------------------------------------
    # WMS layers
    # ------------------------------------------------------------------

    def add_wms_layer(
        self,
        url: str,
        layers: str,
        name: str,
        *,
        fmt: str = "image/png",
        transparent: bool = True,
        opacity: float = 0.7,
        attribution: str = "",
    ) -> "HistoricalMapBuilder":
        """Add a WMS tile layer.

        Parameters
        ----------
        url : str
            WMS base URL.
        layers : str
            WMS layer name(s).
        name : str
            Display name in layer control.
        """
        self._wms_layers.append({
            "url": url,
            "layers": layers,
            "name": name,
            "format": fmt,
            "transparent": transparent,
            "opacity": opacity,
            "attribution": attribution,
        })
        return self

    # ------------------------------------------------------------------
    # Image overlays
    # ------------------------------------------------------------------

    def add_image_overlay(
        self,
        url: str,
        bounds: tuple[tuple[float, float], tuple[float, float]],
        name: str = "Image Overlay",
        *,
        opacity: float = 0.7,
    ) -> "HistoricalMapBuilder":
        """Overlay a georeferenced image (e.g., scanned historical map).

        Parameters
        ----------
        url : str
            Image URL.
        bounds : tuple
            ``((south_lat, west_lng), (north_lat, east_lng))``.
        name : str
            Layer name in layer control.
        opacity : float
            Image opacity (0–1).
        """
        self._image_overlays.append({
            "url": url,
            "bounds": [list(bounds[0]), list(bounds[1])],
            "name": name,
            "opacity": opacity,
        })
        return self

    # ------------------------------------------------------------------
    # HTML generation
    # ------------------------------------------------------------------

    def _build_js(self) -> str:
        """Generate the JavaScript for the map."""
        lines: list[str] = []

        # Basemap
        if self.basemap != "none" and self.basemap in BASEMAPS:
            bm = BASEMAPS[self.basemap]
            lines.append(f"""
    var basemap = L.tileLayer({json.dumps(bm['url'])}, {{
        attribution: {json.dumps(bm['attribution'])},
        maxZoom: {bm['max_zoom']}
    }});
    var baseMaps = {{{json.dumps(bm['name'])}: basemap}};
""")
        else:
            lines.append("    var baseMaps = {};\n")

        # Additional basemaps from tile layers with overlay=false
        for i, tl in enumerate(self._tile_layers):
            if not tl["overlay"]:
                lines.append(f"""
    var tileBase_{i} = L.tileLayer({json.dumps(tl['url'])}, {{
        attribution: {json.dumps(tl['attribution'])},
        maxZoom: {tl['max_zoom']},
        opacity: {tl['opacity']}
    }});
    baseMaps[{json.dumps(tl['name'])}] = tileBase_{i};
""")

        # Map init
        center_js = json.dumps(list(self.center))
        default_layers = "basemap" if (self.basemap != "none" and self.basemap in BASEMAPS) else ""
        lines.append(f"""
    var map = L.map('map', {{
        center: {center_js},
        zoom: {self.zoom},
        layers: [{default_layers}]
    }});
    var overlayMaps = {{}};
""")

        # Overlay tile layers
        for i, tl in enumerate(self._tile_layers):
            if tl["overlay"]:
                lines.append(f"""
    var tileOverlay_{i} = L.tileLayer({json.dumps(tl['url'])}, {{
        attribution: {json.dumps(tl['attribution'])},
        maxZoom: {tl['max_zoom']},
        opacity: {tl['opacity']}
    }}).addTo(map);
    overlayMaps[{json.dumps(tl['name'])}] = tileOverlay_{i};
""")

        # WMS layers
        for i, wms in enumerate(self._wms_layers):
            lines.append(f"""
    var wms_{i} = L.tileLayer.wms({json.dumps(wms['url'])}, {{
        layers: {json.dumps(wms['layers'])},
        format: {json.dumps(wms['format'])},
        transparent: {json.dumps(wms['transparent'])},
        opacity: {wms['opacity']},
        attribution: {json.dumps(wms['attribution'])}
    }}).addTo(map);
    overlayMaps[{json.dumps(wms['name'])}] = wms_{i};
""")

        # Image overlays
        for i, img in enumerate(self._image_overlays):
            bounds_js = json.dumps(img["bounds"])
            lines.append(f"""
    var imgOverlay_{i} = L.imageOverlay({json.dumps(img['url'])}, {bounds_js}, {{
        opacity: {img['opacity']}
    }}).addTo(map);
    overlayMaps[{json.dumps(img['name'])}] = imgOverlay_{i};
""")

        # Inline GeoJSON layers
        for i, gj in enumerate(self._geojson_layers):
            data_js = json.dumps(gj["data"], ensure_ascii=False)
            style_js = json.dumps(gj["style"])
            lines.append(f"""
    var geojsonData_{i} = {data_js};
    var geojson_{i} = L.geoJSON(geojsonData_{i}, {{
        style: function() {{ return {style_js}; }},
""")
            if gj["popup_property"]:
                lines.append(f"""        onEachFeature: function(feature, layer) {{
            if (feature.properties) {{
                var pp = feature.properties[{json.dumps(gj['popup_property'])}];
                var tp = feature.properties[{json.dumps(gj.get('tooltip_property') or gj['popup_property'])}];
                if (pp) layer.bindPopup('<b>' + pp + '</b>');
                if (tp) layer.bindTooltip(tp);
            }}
        }}
""")
            lines.append(f"""    }}).addTo(map);
    overlayMaps[{json.dumps(gj['name'])}] = geojson_{i};
""")

        # Remote GeoJSON layers (fetched at runtime)
        for i, gj in enumerate(self._geojson_url_layers):
            style_js = json.dumps(gj["style"])
            lines.append(f"""
    (function() {{
        var idx = {i};
        fetch({json.dumps(gj['url'])})
            .then(function(r) {{ return r.json(); }})
            .then(function(data) {{
                var layer = L.geoJSON(data, {{
                    style: function() {{ return {style_js}; }},
""")
            if gj["popup_property"]:
                pp = json.dumps(gj["popup_property"])
                tp = json.dumps(gj.get("tooltip_property") or gj["popup_property"])
                lines.append(f"""                    onEachFeature: function(feature, layer) {{
                        if (feature.properties) {{
                            var pp = feature.properties[{pp}];
                            var tp = feature.properties[{tp}];
                            if (pp) layer.bindPopup('<b>' + pp + '</b>');
                            if (tp) layer.bindTooltip(tp);
                        }}
                    }}
""")
            lines.append(f"""                }}).addTo(map);
                overlayMaps[{json.dumps(gj['name'])}] = layer;
                controlLayer.addOverlay(layer, {json.dumps(gj['name'])});
            }});
    }})();
""")

        # Markers (grouped)
        groups: dict[str, list[int]] = {}
        for i, m in enumerate(self._markers):
            g = m.get("group") or "__default__"
            groups.setdefault(g, []).append(i)

        # Colored marker icon helper
        if self._markers:
            lines.append("""
    function colorIcon(color) {
        return L.icon({
            iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-' + color + '.png',
            shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
            iconSize: [25, 41], iconAnchor: [12, 41],
            popupAnchor: [1, -34], shadowSize: [41, 41]
        });
    }
""")

        for group_name, indices in groups.items():
            var_name = f"markerGroup_{id(group_name)}"
            lines.append(f"    var {var_name} = L.layerGroup().addTo(map);")
            for i in indices:
                m = self._markers[i]
                lines.append(f"""
    L.marker([{m['lat']}, {m['lng']}], {{icon: colorIcon({json.dumps(m['color'])})}})
        .bindPopup({json.dumps(m['popup'])})
        .bindTooltip({json.dumps(m['tooltip'])})
        .addTo({var_name});""")
            if group_name != "__default__":
                lines.append(
                    f"    overlayMaps[{json.dumps(group_name)}] = {var_name};"
                )

        # Layer control
        lines.append("""
    var controlLayer = L.control.layers(baseMaps, overlayMaps, {collapsed: false}).addTo(map);
""")

        # Scale bar
        lines.append("    L.control.scale().addTo(map);")

        return "\n".join(lines)

    def save_html(self, path: str) -> str:
        """Write a standalone HTML file with the embedded map.

        Parameters
        ----------
        path : str
            Output file path.

        Returns
        -------
        str
            The path written.
        """
        js_code = self._build_js()

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{_escape_html(self.title)}</title>
  <link rel="stylesheet" href="{_LEAFLET_CSS}">
  <script src="{_LEAFLET_JS}"></script>
  <style>
    html, body {{ height: 100%; margin: 0; padding: 0; }}
    #map {{ width: 100%; height: 100%; }}
    .map-title {{
      position: absolute; top: 10px; left: 50%;
      transform: translateX(-50%); z-index: 1000;
      background: rgba(255,255,255,0.9); padding: 8px 20px;
      border-radius: 4px; font-family: Georgia, serif;
      font-size: 18px; font-weight: bold;
      box-shadow: 0 2px 6px rgba(0,0,0,0.2);
      pointer-events: none;
    }}
  </style>
</head>
<body>
  <div id="map"></div>
  <div class="map-title">{_escape_html(self.title)}</div>
  <script>
{js_code}
  </script>
</body>
</html>
"""
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
        return path


def _escape_html(text: str) -> str:
    """Minimal HTML escaping for title text."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


# ------------------------------------------------------------------
# Demo
# ------------------------------------------------------------------

def main() -> None:
    m = HistoricalMapBuilder(
        title="Silk Road: Key Cities & Han Dynasty Boundaries",
        center=(35.0, 80.0),
        zoom=4,
        basemap="carto_light",
    )

    # Historical boundaries — Han dynasty era (100 CE)
    m.add_historical_boundaries(
        "100_ce",
        name="World Boundaries c. 100 CE",
        style={"color": "#6c5b7b", "weight": 1.5, "fillOpacity": 0.15},
    )

    # Silk Road cities
    cities = [
        (34.26, 108.94, "Chang'an (長安)", "Capital of the Han Dynasty. Starting point of the Silk Road.", "red"),
        (36.06, 103.83, "Lanzhou (蘭州)", "Key crossing point on the Yellow River.", "blue"),
        (40.14, 94.66, "Dunhuang (敦煌)", "Gateway to the western regions. Famous for the Mogao Caves.", "gold"),
        (39.47, 75.99, "Kashgar (喀什)", "Major oasis city at the junction of northern and southern Silk Road routes.", "gold"),
        (41.30, 69.28, "Tashkent", "Important stop on the northern Silk Road route.", "blue"),
        (39.65, 66.96, "Samarkand", "Sogdian trading hub and cultural center.", "orange"),
        (37.94, 58.39, "Merv", "One of the largest cities in the ancient world.", "orange"),
        (32.65, 51.68, "Isfahan", "Persian trading city on the western Silk Road.", "green"),
        (33.51, 36.29, "Damascus", "Ancient city connecting the Silk Road to the Mediterranean.", "green"),
        (36.20, 36.16, "Antioch", "Major Roman city and Silk Road terminus.", "violet"),
        (41.01, 28.98, "Constantinople", "Eastern Roman capital. Ultimate western terminus.", "red"),
    ]
    for lat, lng, name, desc, color in cities:
        m.add_marker(
            lat, lng, name,
            popup=f"<b>{name}</b><br>{desc}",
            color=color,
            group="Silk Road Cities",
        )

    # Add a GeoJSON route (simplified Silk Road path)
    silk_road_route = {
        "type": "Feature",
        "properties": {"name": "Silk Road (main route)"},
        "geometry": {
            "type": "LineString",
            "coordinates": [
                [108.94, 34.26], [103.83, 36.06], [94.66, 40.14],
                [75.99, 39.47], [69.28, 41.30], [66.96, 39.65],
                [58.39, 37.94], [51.68, 32.65], [36.29, 33.51],
                [36.16, 36.20], [28.98, 41.01],
            ],
        },
    }
    m.add_geojson(
        {"type": "FeatureCollection", "features": [silk_road_route]},
        name="Silk Road Route",
        style={"color": "#c44536", "weight": 3, "dashArray": "8 4", "fillOpacity": 0},
    )

    output = m.save_html("silk_road_demo.html")
    print(f"Map saved to: {output}")
    print("Open in a browser to see the interactive map.")


if __name__ == "__main__":
    main()
