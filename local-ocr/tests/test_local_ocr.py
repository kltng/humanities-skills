"""Offline tests for the standard-library parts of local-ocr (no models, no network).

    cd local-ocr && python3 -m unittest discover -s tests
"""
import json
import os
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))
os.environ["LOCAL_OCR_HOME"] = tempfile.mkdtemp()

import _common  # noqa: E402
import doctor  # noqa: E402
import export  # noqa: E402
import report  # noqa: E402

# Real Chandra OCR 2 output (a HathiTrust page with only the Google footer).
CHANDRA_RAW = (
    '<div data-bbox="0 515 44 988" data-label="Page-Footer"><p>Generated at Harvard University through HathiTrust'
    ' on 2026-03-05 23:27 GMT<br/><a href="https://hdl.handle.net/2027/hvd.32044068331941">https://hdl.handle.net/'
    '2027/hvd.32044068331941</a> / Public Domain, Google-digitized</p></div><div data-bbox="148 969 348 1000" '
    'data-label="Page-Footer"><p>Digitized by Google</p></div><div data-bbox="654 972 841 1000" '
    'data-label="Page-Footer"><p>Original from<br/>HARVARD UNIVERSITY</p></div>'
)


def make_job(root: Path, rows: list, pages: int = 3, blank: tuple = ()) -> Path:
    job = root / "job"
    (job / "pages").mkdir(parents=True)
    data = {"name": "t", "created": "2026-11-02", "model": "chandra", "formats": ["json", "txt"], "brief": {},
            "sources": [{"path": "/x/a.pdf", "doc": "a", "pages": pages}], "runs": [], "notes": [],
            "pages": [{"id": f"{i:05d}", "doc": "a", "doc_page": i, "file": f"pages/{i:05d}.png", "width": 1000,
                       "height": 2000, "ink": 0.0 if i in blank else 0.05, "blank": i in blank}
                      for i in range(1, pages + 1)]}
    _common.save_job(job, data)
    with open(job / "rows.jsonl", "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    return job


class TestParsing(unittest.TestCase):
    def test_chandra_blocks_real_output(self):
        blocks = _common.chandra_blocks(CHANDRA_RAW, 1000, 2000)
        self.assertEqual(len(blocks), 3)
        self.assertEqual(blocks[0]["label"], "PageFooter")
        self.assertEqual(blocks[0]["bbox"], [0.0, 1030.0, 44.0, 1976.0])  # 0–1000 grid -> pixels
        self.assertEqual(blocks[2]["text"], "Original from\nHARVARD UNIVERSITY")

    def test_chandra_without_divs_keeps_text(self):
        blocks = _common.chandra_blocks("<p>只有文字</p>", 100, 100)
        self.assertEqual(blocks[0]["text"], "只有文字")

    def test_html_to_text_table_and_entities(self):
        t = _common.html_to_text("<table><tr><td>甲</td><td>乙 &amp; 丙</td></tr></table>")
        self.assertEqual(t, "甲\t乙 & 丙")

    def test_labels(self):
        for raw, want in [("Section-Header", "SectionHeader"), ("PageFooter", "PageFooter"),
                          ("Picture", "Picture"), ("Something-New", "Something-New")]:
            self.assertEqual(_common.norm_label(raw), want)


class TestResume(unittest.TestCase):
    def test_half_line_and_errors_are_read_again(self):
        with tempfile.TemporaryDirectory() as d:
            job = make_job(Path(d), [{"page": "00001", "status": "ok", "blocks": []},
                                     {"page": "00002", "status": "error", "blocks": []}])
            with open(job / "rows.jsonl", "a") as fh:
                fh.write('{"page": "00003", "sta')  # killed mid-write
            todo = _common.todo_pages(job, _common.load_job(job))
            self.assertEqual([p["id"] for p in todo], ["00002", "00003"])
            self.assertTrue((job / "rows.jsonl").read_text().endswith("\n"))

    def test_blank_pages_skipped_and_logged(self):
        with tempfile.TemporaryDirectory() as d:
            job = make_job(Path(d), [], blank=(2,))
            todo = _common.todo_pages(job, _common.load_job(job), skip_blank=True)
            self.assertEqual([p["id"] for p in todo], ["00001", "00003"])
            self.assertEqual(_common.read_rows(job)["00002"]["status"], "skipped_blank")


class TestDoctor(unittest.TestCase):
    def rec(self, ram, mac, gpus=(), tools=None):
        tools = {"uv": True, "llama-server": False, "docker": False, "nvidia-smi": bool(gpus), "gh": True,
                 **(tools or {})}
        cached = {k: [False] * len(v) for k, v in doctor.MODEL_FILES.items()}
        with mock.patch.object(doctor, "apple_silicon", return_value=mac), \
                mock.patch.object(doctor, "nvidia_gpus", return_value=list(gpus)):
            return doctor.recommend({"ram_gb": ram}, tools, cached)

    def test_mac_16gb(self):
        r = self.rec(16, True)
        self.assertEqual((r["chandra"]["verdict"], r["chandra"]["backend"]), ("good", "mlx"))
        self.assertEqual(r["surya"]["backend"], "mlx")
        self.assertEqual(r["chandra"]["download_gb"], 5.2)

    def test_mac_8gb_no_chandra(self):
        self.assertEqual(self.rec(8, True)["chandra"]["verdict"], "no")

    def test_mac_with_llamacpp_prefers_it_for_surya(self):
        self.assertEqual(self.rec(16, True, tools={"llama-server": True})["surya"]["backend"], "llamacpp")

    def test_nvidia_24gb(self):
        r = self.rec(32, False, gpus=[{"name": "RTX 4090", "vram_gb": 24.0, "free_gb": 23}], tools={"docker": True})
        self.assertEqual((r["chandra"]["verdict"], r["chandra"]["backend"]), ("good", "hf"))
        self.assertEqual(r["surya"]["backend"], "vllm")

    def test_cpu_only_laptop(self):
        r = self.rec(8, False)
        self.assertEqual(r["chandra"]["verdict"], "no")
        self.assertEqual(r["surya"]["verdict"], "slow")
        self.assertEqual(r["indra"]["verdict"], "good")


class TestExportAndReport(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        blocks = _common.chandra_blocks(
            '<div data-bbox="100 50 900 100" data-label="Section-Header"><p>卷一</p></div>'
            '<div data-bbox="100 120 900 900" data-label="Text"><p>學而時習之<br/>不亦說乎 &lt;x&gt;</p></div>'
            '<div data-bbox="100 920 900 990" data-label="Picture"></div>', 1000, 2000)
        self.job = make_job(Path(self.tmp.name), [
            {"page": "00001", "status": "ok", "seconds": 50, "blocks": blocks},
            {"page": "00002", "status": "loop", "seconds": 600, "blocks": blocks},
        ])

    def tearDown(self):
        self.tmp.cleanup()

    def test_all_formats(self):
        data, docs, missing = export.collect(self.job, drop_furniture=False)
        self.assertEqual(missing, ["00003"])
        self.assertEqual(docs["a"][1]["blocks"], [])  # a loop page carries no text
        for name, writer in export.WRITERS.items():
            out = self.job / "export" / name
            out.mkdir(parents=True)
            writer(out, data, docs)
        txt = (self.job / "export/txt/a.txt").read_text()
        self.assertIn("[[page 1]]\n卷一", txt)
        self.assertIn("[[page 2]] (loop)", txt)
        self.assertIn("## 卷一", (self.job / "export/md/a.md").read_text())
        for f in list((self.job / "export").rglob("*.xml")):
            ET.parse(f)  # well-formed
        alto = ET.parse(self.job / "export/alto/a/00001.xml").getroot()
        ns = {"a": "http://www.loc.gov/standards/alto/ns-v4#"}
        strings = [s.get("CONTENT") for s in alto.iterfind(".//a:String", ns)]
        self.assertEqual(strings, ["卷一", "學而時習之", "不亦說乎 <x>"])
        self.assertEqual(len(alto.findall(".//a:Illustration", ns)), 1)
        self.assertNotIn("<x>", (self.job / "export/html/a.html").read_text())  # escaped

    def test_report_has_no_page_text(self):
        with mock.patch.object(sys, "argv", ["report.py", str(self.job), "--describe", "test"]):
            report.main()
        field = (self.job / "field-report.md").read_text()
        self.assertNotIn("學而", field)
        self.assertNotIn(str(self.job), field)
        self.assertIn("loop 1", field)
        self.assertIn("loop", (self.job / "report.md").read_text())


if __name__ == "__main__":
    unittest.main()
