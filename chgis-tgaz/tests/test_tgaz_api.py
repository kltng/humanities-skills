import io
import json
import sys
import unittest
import urllib.request
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.tgaz_api import TGAZAPI


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def search_result(sys_id, xy, obj="POINT"):
    return {"sys_id": sys_id, "name": "苏州", "transcription": "Su Zhou",
            "object type": obj, "xy coordinates": xy}


SEARCH = {"placenames": [
    search_result("hvd_32071", "120.61862, 31.31271"),
    search_result("hvd_90239", "0.00000, 31.312710", "POLYGON"),
    search_result("hvd_2027", "0.00000, 0.00000"),
]}


def unit(child, name, begin, end):
    return {"child id": child, "name": name, "transcribed": name,
            "begin_year": str(begin), "end_year": str(end)}


# A province with two prefectures (one gone by 1850) and their counties.
RECORDS = {
    "hvd_P": {"historical_context": {"subordinate units": [
        unit("hvd_F1", "杭州府", 1645, 1911),
        unit("hvd_F2", "旧府", 1645, 1700),
        unit("hvd_F1", "杭州府", 1645, 1911),  # listed twice: keep once
    ]}},
    "hvd_F1": {"historical_context": {"subordinate units": [
        unit("hvd_C1", "钱塘县", 1645, 1911),
        unit("hvd_C2", "仁和县", 1645, 1911),
        unit("hvd_C3", "新县", 1900, 1911),
    ]}},
    "hvd_F2": {"historical_context": {"subordinate units": dict(unit("hvd_C9", "x", 1645, 1700))}},
}


class TGAZTest(unittest.TestCase):
    def setUp(self):
        self._urlopen = urllib.request.urlopen
        self.urls = []

        def fake(req, timeout=None):
            url = req.full_url
            self.urls.append(url)
            if "/placename/json/" in url:
                body = RECORDS[url.rsplit("/", 1)[1]]
            else:
                body = SEARCH
            return FakeResponse(json.dumps(body).encode())
        urllib.request.urlopen = fake
        self.api = TGAZAPI(min_request_interval=0)

    def tearDown(self):
        urllib.request.urlopen = self._urlopen

    def test_has_bad_coords(self):
        bad = TGAZAPI.has_bad_coords
        self.assertFalse(bad(search_result("a", "120.61862, 31.31271")))
        self.assertTrue(bad(search_result("a", "0.00000, 31.312710")))
        self.assertTrue(bad(search_result("a", "5.00000, 31.78")))
        self.assertTrue(bad(search_result("a", "120.6, 0.00000")))
        self.assertTrue(bad({"xy coordinates": ""}))
        self.assertFalse(bad({"spatial": {"longitude": "120.16862", "latitude": "30.29412"}}))
        self.assertTrue(bad({"spatial": {"longitude": "0.00000", "latitude": "30.29"}}))

    def test_search_keeps_all_rows_by_default(self):
        self.assertEqual(len(self.api.search("苏州")), 3)

    def test_search_can_drop_bad_coords(self):
        rows = self.api.search("苏州", drop_bad_coords=True)
        self.assertEqual([r["sys_id"] for r in rows], ["hvd_32071"])

    def test_search_sends_space_as_plus_and_chinese_as_utf8(self):
        self.api.search("su zhou", year=1100)
        self.assertIn("n=su+zhou", self.urls[-1])
        self.assertIn("yr=1100", self.urls[-1])

    def test_descendants_two_levels_filtered_by_year(self):
        units = self.api.get_descendants("hvd_P", year=1850)
        self.assertEqual([(u["child id"], u["level"]) for u in units],
                         [("hvd_F1", 1), ("hvd_C1", 2), ("hvd_C2", 2)])
        self.assertEqual(units[1]["parent id"], "hvd_F1")
        # One request for the province, one for the prefecture alive in 1850.
        self.assertEqual(len(self.urls), 2)

    def test_descendants_one_level(self):
        units = self.api.get_descendants("hvd_P", year=1850, levels=1)
        self.assertEqual([u["child id"] for u in units], ["hvd_F1"])

    def test_descendants_without_year(self):
        units = self.api.get_descendants("hvd_P")
        self.assertEqual({u["child id"] for u in units if u["level"] == 2},
                         {"hvd_C1", "hvd_C2", "hvd_C3", "hvd_C9"})


if __name__ == "__main__":
    unittest.main()
