import sys
import tempfile
import unittest
import warnings
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import map_builder
from scripts.map_builder import BASEMAPS, SINICA_LAYERS, HistoricalMapBuilder


def build_html(m):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "map.html"
        m.save_html(str(path))
        return path.read_text(encoding="utf-8")


class BasemapTest(unittest.TestCase):
    def test_default_is_osm_without_subdomains(self):
        m = HistoricalMapBuilder()
        self.assertEqual(m.basemap, "osm")
        html = build_html(m)
        self.assertIn("https://tile.openstreetmap.org/{z}/{x}/{y}.png", html)
        self.assertNotIn("cartocdn", html)

    def test_osm_needs_no_key(self):
        self.assertFalse(BASEMAPS["osm"].get("needs_key"))
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            HistoricalMapBuilder(basemap="osm")

    def test_keyed_basemaps_warn(self):
        for key in ("carto_light", "carto_dark", "watercolor", "toner_lite"):
            with self.assertWarns(UserWarning, msg=key):
                HistoricalMapBuilder(basemap=key)


class SinicaTest(unittest.TestCase):
    def test_sinica_layer_url_and_name(self):
        m = HistoricalMapBuilder()
        m.add_sinica_layer("ad1582")
        layer = m._tile_layers[0]
        self.assertEqual(
            layer["url"],
            "https://gis.sinica.edu.tw/ccts/file-exists.php?img=ad1582-png-{z}-{x}-{y}",
        )
        self.assertEqual(layer["name"], SINICA_LAYERS["ad1582"])
        self.assertIn("ad1582-png-{z}-{x}-{y}", build_html(m))

    def test_unknown_layer_id_passes_through(self):
        m = HistoricalMapBuilder()
        m.add_sinica_layer("Beijing_50K_1928b", name="Beijing 1928")
        self.assertIn("img=Beijing_50K_1928b-png-", m._tile_layers[0]["url"])
        self.assertEqual(m._tile_layers[0]["name"], "Beijing 1928")

    def test_known_layers_include_tan_qixiang_dynasties(self):
        for key in ("ad0741", "ad1582", "ad1820"):
            self.assertIn(key, SINICA_LAYERS)


class ZeroCoordinateTest(unittest.TestCase):
    def test_zero_longitude_warns(self):
        m = HistoricalMapBuilder()
        with self.assertWarns(UserWarning):
            m.add_marker(31.27687, 0.0, "苏州 (POLYGON row)")
        # The marker is still added; the warning only flags it.
        self.assertEqual(len(m._markers), 1)

    def test_normal_marker_does_not_warn(self):
        m = HistoricalMapBuilder()
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            m.add_marker(31.31271, 120.61862, "苏州")


class DemoTest(unittest.TestCase):
    def test_demo_uses_osm(self):
        with tempfile.TemporaryDirectory() as tmp:
            cwd = Path.cwd()
            try:
                import os
                os.chdir(tmp)
                with warnings.catch_warnings():
                    warnings.simplefilter("error")
                    map_builder.main()
            finally:
                os.chdir(cwd)


if __name__ == "__main__":
    unittest.main()
