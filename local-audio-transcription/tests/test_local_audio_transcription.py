"""Offline tests for the standard-library parts of local-audio-transcription (no models, no network, no ffmpeg).

    cd local-audio-transcription && python3 -m unittest discover -s tests
"""
import json
import os
import socket
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))
os.environ["LOCAL_ASR_HOME"] = tempfile.mkdtemp()

import _common  # noqa: E402
import doctor  # noqa: E402
import export  # noqa: E402
import offline  # noqa: E402
import prepare  # noqa: E402
import report  # noqa: E402


def make_job(root: Path, rows: list, chunks: int = 3, speech: float = 0.9, **extra) -> Path:
    job = root / "job"
    (job / "chunks").mkdir(parents=True)
    data = {"name": "t", "created": "2026-11-09", "model": "whisper", "language": None, "formats": ["txt", "srt"],
            "offline": False, "diarize": False, "sample": False, "brief": {},
            "sources": [{"path": "/x/a.mp3", "doc": "a", "duration": 600.0 * chunks, "chunks": chunks}],
            "runs": [], "notes": [],
            "chunks": [{"id": f"{i:05d}", "doc": "a", "index": i, "file": f"chunks/{i:05d}.wav",
                        "start": 600.0 * (i - 1), "end": 600.0 * i, "duration": 600.0, "speech_share": speech,
                        "silences": [[100.0, 101.0], [250.0, 252.0]], "language": None}
                       for i in range(1, chunks + 1)], **extra}
    _common.save_job(job, data)
    with open(job / "rows.jsonl", "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    return job


class TestChunking(unittest.TestCase):
    def test_cut_at_longest_silence_in_window(self):
        silences = [(100, 101), (430, 434), (500, 501), (1150, 1153)]
        cuts = prepare.cut_points(1800, silences, target=600, min_chunk=60)
        # window 360-600: the 4 s silence at 430-434 beats the 1 s one; 792-1032 and 1392-1632 have none
        self.assertEqual(cuts, [432.0, 1032.0, 1632.0])

    def test_cut_without_silence_falls_back_to_target(self):
        self.assertEqual(prepare.cut_points(1300, [], 600, 60), [600, 1200])

    def test_short_file_is_one_chunk(self):
        self.assertEqual(prepare.cut_points(500, [(200, 201)], 600, 60), [])

    def test_speech_share(self):
        self.assertEqual(prepare.speech_share(0, 100, [(10, 20), (90, 110)]), 0.8)

    def test_pieces_merge_up_to_max(self):
        chunk = {"duration": 100.0, "silences": [[20, 22], [45, 46], [70, 71]]}
        self.assertEqual(_common.pieces(chunk, 30), [(0.0, 21.0), (21.0, 45.5), (45.5, 70.5), (70.5, 100.0)])

    def test_pieces_cut_long_silence_free_audio(self):
        self.assertEqual(_common.pieces({"duration": 65.0, "silences": []}, 30), [(0.0, 30.0), (30.0, 60.0), (60.0, 65.0)])


class TestFlags(unittest.TestCase):
    def test_repeat(self):
        segs = [{"text": "謝謝大家。"}] * 5 + [{"text": "再見"}]
        self.assertEqual(_common.repeated_segments(segs), 5)
        self.assertEqual(_common.repeated_segments(segs[:3]), 0)

    def test_flag_order(self):
        chunk = {"duration": 100.0, "speech_share": 0.02}
        row = {"status": "ok", "seconds": 5, "text": "字幕由志願者提供 謝謝觀看 謝謝觀看 請訂閱我們的頻道",
               "segments": [{"text": "x", "logprob": -3.0}]}
        _common.flag_row(row, chunk)
        self.assertEqual(row["flag"], "no_speech")
        row = {"status": "ok", "seconds": 5, "text": "", "segments": []}
        _common.flag_row(row, {"duration": 100.0, "speech_share": 0.9})
        self.assertEqual(row["flag"], "empty")
        row = {"status": "ok", "seconds": 5, "text": "ok", "segments": [{"text": "ok", "logprob": -2.0}]}
        _common.flag_row(row, {"duration": 100.0, "speech_share": 0.9})
        self.assertEqual(row["flag"], "uncertain")
        row = {"status": "ok", "seconds": 5, "text": "ok", "segments": [{"text": "ok"}], "language": "zh"}
        _common.flag_row(row, {"duration": 100.0, "speech_share": 0.9, "language": "yue"})
        self.assertEqual(row["flag"], "language")

    def test_norm_lang(self):
        for raw, want in [("Cantonese", "yue"), ("zh-HK", "yue"), ("Chinese", "zh"), ("EN", "en"), ("ja", "ja"), ("xx", "xx")]:
            self.assertEqual(_common.norm_lang(raw), want)

    def test_join_text_cjk_no_space(self):
        self.assertEqual(_common.join_text([{"text": "你好"}, {"text": "世界"}, {"text": "hello"}, {"text": "world"}]),
                         "你好世界 hello world")

    def test_times(self):
        self.assertEqual(_common.srt_time(3661.5), "01:01:01,500")
        self.assertEqual(_common.srt_time(0.9996, "."), "00:00:01.000")
        self.assertEqual(_common.fmt_time(3661), "1:01:01")


class TestResume(unittest.TestCase):
    def test_half_line_and_errors_are_done_again(self):
        with tempfile.TemporaryDirectory() as d:
            job = make_job(Path(d), [{"chunk": "00001", "status": "ok", "segments": []},
                                     {"chunk": "00002", "status": "error", "segments": []}])
            with open(job / "rows.jsonl", "a") as fh:
                fh.write('{"chunk": "00003", "sta')  # killed mid-write
            todo = _common.todo_chunks(job, _common.load_job(job))
            self.assertEqual([c["id"] for c in todo], ["00002", "00003"])
            self.assertTrue((job / "rows.jsonl").read_text().endswith("\n"))

    def test_run_chunks_shifts_times_and_flags(self):
        with tempfile.TemporaryDirectory() as d:
            job = make_job(Path(d), [])
            data = _common.load_job(job)
            calls = []

            def fake(path, chunk):
                calls.append(chunk["id"])
                return {"language": "zh", "segments": [{"start": 1.0, "end": 2.0, "text": " 你好 ",
                                                        "words": [{"start": 1.0, "end": 1.5, "text": "你好"}]}]}
            _common.run_chunks(job, "whisper", "mlx", {"x": "1"}, data["chunks"][1:2], fake)
            rows = _common.read_rows(job)
            self.assertEqual(calls, ["00002"])
            self.assertEqual(rows["00002"]["segments"][0]["start"], 601.0)
            self.assertEqual(rows["00002"]["segments"][0]["words"][0]["end"], 601.5)
            self.assertEqual(rows["00002"]["text"], "你好")
            self.assertEqual(_common.load_job(job)["runs"][0]["outcome"], "finished")
            prog = _common.job_progress(job)
            self.assertEqual(prog["counts"], {"ok": 1, "todo": 2})


class TestDoctor(unittest.TestCase):
    def rec(self, ram, mac, gpus=(), cores=8):
        tools = {"uv": True, "ffmpeg": True, "ffprobe": True, "nvidia-smi": bool(gpus), "gh": True}
        cached = {k: [False] * len(v) for k, v in doctor.MODEL_FILES.items()}
        with mock.patch.object(doctor, "apple_silicon", return_value=mac), \
                mock.patch.object(doctor, "nvidia_gpus", return_value=list(gpus)):
            return doctor.recommend({"ram_gb": ram, "cpu_cores": cores}, tools, cached)

    def test_mac_16gb(self):
        r = self.rec(16, True)
        self.assertEqual((r["whisper"]["verdict"], r["whisper"]["backend"]), ("good", "mlx"))
        self.assertEqual((r["qwen3-asr"]["verdict"], r["qwen3-asr"]["backend"]), ("good", "mlx"))
        self.assertEqual(r["parakeet"]["backend"], "mlx")
        self.assertEqual(r["whisper"]["download_gb"], 1.6)

    def test_nvidia(self):
        r = self.rec(32, False, gpus=[{"name": "RTX 4090", "vram_gb": 24.0, "free_gb": 23}])
        self.assertEqual((r["whisper"]["backend"], r["qwen3-asr"]["backend"], r["parakeet"]["backend"]), ("ct2", "hf", "onnx"))

    def test_cpu_only_laptop(self):
        r = self.rec(8, False)
        self.assertEqual(r["whisper"]["verdict"], "slow")
        self.assertEqual(r["qwen3-asr"]["verdict"], "no")
        self.assertEqual(r["sensevoice"]["verdict"], "good")
        self.assertEqual(r["parakeet"]["backend"], "onnx")


class TestOfflineGuard(unittest.TestCase):
    def test_guard_blocks_remote_allows_local(self):
        saved = (socket.socket.connect, socket.socket.connect_ex, socket.create_connection, socket.getaddrinfo)
        env = {k: os.environ.get(k) for k in ("HF_HUB_OFFLINE", "LOCAL_ASR_OFFLINE")}
        try:
            _common.network_guard()
            self.assertEqual(os.environ["HF_HUB_OFFLINE"], "1")
            with self.assertRaises(OSError):
                socket.create_connection(("huggingface.co", 443), timeout=1)
            with self.assertRaises(OSError):
                socket.getaddrinfo("huggingface.co", 443)
            s = socket.socket()
            with self.assertRaises(OSError):
                s.connect(("93.184.216.34", 80))
            s.close()
            srv = socket.socket(); srv.bind(("127.0.0.1", 0)); srv.listen(1)
            c = socket.socket(); c.connect(("127.0.0.1", srv.getsockname()[1])); c.close(); srv.close()
        finally:
            (socket.socket.connect, socket.socket.connect_ex, socket.create_connection, socket.getaddrinfo) = saved
            for k, v in env.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v


class TestExportAndReport(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        segs1 = [{"start": 0.0, "end": 4.0, "text": "學而時習之", "logprob": -0.1},
                 {"start": 4.5, "end": 9.0, "text": "不亦說乎 <x>", "logprob": -0.2},
                 {"start": 30.0, "end": 36.0, "text": "有朋自遠方來", "logprob": -0.1,
                  "words": [{"start": 30.0, "end": 33.0, "text": "有朋"}, {"start": 33.0, "end": 36.0, "text": "自遠方來"}]}]
        segs2 = [{"start": 600.0, "end": 605.0, "text": "謝謝觀看", "logprob": -3.0}]
        self.job = make_job(Path(self.tmp.name), [
            {"chunk": "00001", "status": "ok", "seconds": 20, "language": "zh", "segments": segs1, "text": "x"},
            {"chunk": "00002", "status": "ok", "seconds": 20, "language": "zh", "segments": segs2, "text": "謝謝觀看",
             "flag": "uncertain", "warning": "low"},
        ])
        with open(self.job / "speakers.jsonl", "w") as fh:
            fh.write(json.dumps({"doc": "a", "speakers": 2, "turns": [{"start": 0, "end": 10, "speaker": 0},
                                                                        {"start": 10, "end": 700, "speaker": 1}]}) + "\n")

    def tearDown(self):
        self.tmp.cleanup()

    def test_all_formats(self):
        data, docs, missing = export.collect(self.job)
        self.assertEqual(missing, ["00003"])
        self.assertEqual([s.get("speaker") for s in docs["a"]["segments"]], [0, 0, 1, 1])
        opt = mock.Mock(no_timestamps=False, max_gap=1.0, max_paragraph_seconds=60.0, max_cue_seconds=8.0)
        for name, writer in export.WRITERS.items():
            out = self.job / "export" / name
            out.mkdir(parents=True)
            writer(out, data, docs, opt)
        txt = (self.job / "export/txt/a.txt").read_text()
        self.assertIn("[0:00] Speaker 1: 學而時習之不亦說乎 <x>", txt)   # merged: CJK, gap 0.5 s, same speaker
        self.assertIn("[0:30] Speaker 2: 有朋自遠方來", txt)              # new paragraph: speaker change
        srt = (self.job / "export/srt/a.srt").read_text()
        self.assertIn("00:00:04,500 --> 00:00:09,000\nSpeaker 1: 不亦說乎 <x>", srt)
        vtt = (self.job / "export/vtt/a.vtt").read_text()
        self.assertTrue(vtt.startswith("WEBVTT"))
        self.assertIn("<v Speaker 2>有朋自遠方來", vtt)
        tei = ET.parse(self.job / "export/tei/a.xml").getroot()   # well-formed
        ns = {"t": "http://www.tei-c.org/ns/1.0"}
        us = tei.findall(".//t:u", ns)
        self.assertEqual([u.get("who") for u in us], ["#spk1", "#spk2", "#spk2"])
        self.assertEqual(us[0].text, "學而時習之不亦說乎 <x>")
        j = json.loads((self.job / "export/json/a.json").read_text())
        self.assertEqual(j["flags"], {"uncertain": ["00002"]})
        csv_text = (self.job / "export/csv/t.csv").read_text()
        self.assertIn("a,600.0,605.0,Speaker 2,zh,謝謝觀看", csv_text)
        self.assertEqual(len((self.job / "export/jsonl/t.jsonl").read_text().splitlines()), 4)

    def test_report_has_no_transcript_text(self):
        with mock.patch.object(sys, "argv", ["report.py", str(self.job), "--describe", "test"]):
            report.main()
        field = (self.job / "field-report.md").read_text()
        user = (self.job / "report.md").read_text()
        for text in (field, user):
            self.assertNotIn("學而", text)
            self.assertNotIn("謝謝", text)
        self.assertNotIn(str(self.job), field)
        self.assertIn("uncertain 1", field)
        self.assertIn("**uncertain** (1)", user)
        self.assertIn("Speakers: a: 2 speaker(s)", user)


class TestOfflineScript(unittest.TestCase):
    def test_script_carries_settings(self):
        with tempfile.TemporaryDirectory() as d:
            job = make_job(Path(d), [], offline=True, sample=True, diarize=True, language="yue")
            data = _common.load_job(job)
            data.update(model="qwen3-asr", language="yue")
            _common.save_job(job, data)
            real = Path(d) / "real"
            with mock.patch.object(sys, "argv", ["offline.py", "script", str(job), "--job", str(real), "--speakers", "2"]):
                offline.main()
            sh = (real / "transcribe-offline.sh").read_text()
            ps = (real / "transcribe-offline.ps1").read_text()
            for text in (sh, ps):
                self.assertIn("run_qwen3asr.py", text)
                self.assertIn("--language yue", text)
                self.assertIn("diarize.py", text)
                self.assertIn("--speakers 2", text)
                self.assertIn("--offline", text)
                self.assertIn("LOCAL_ASR_OFFLINE", text)
            self.assertIn("uv run --offline", sh)
            self.assertTrue(os.access(real / "transcribe-offline.sh", os.X_OK))


class TestIssue31(unittest.TestCase):
    def test_long_segment_without_word_times_becomes_short_cues(self):
        text = "第一章序。我要給阿Q做正傳，已經不止一兩年了。但一面要做，一面又往回想，這足見我不是一個立言的人。因為從來不朽之筆，須傳不朽之人。"
        cues = export._cues({"segments": [{"start": 10.0, "end": 38.0, "text": text}]}, 8.0)
        self.assertGreaterEqual(len(cues), 4)
        self.assertEqual(cues[0]["start"], 10.0)
        self.assertEqual(cues[-1]["end"], 38.0)
        self.assertEqual("".join(c["text"] for c in cues), text)
        for a, b in zip(cues, cues[1:]):
            self.assertEqual(a["end"], b["start"])
        self.assertTrue(all(c["end"] - c["start"] <= 12 for c in cues))
        self.assertTrue(all(c["text"][-1] in "。，" for c in cues))      # cut at punctuation

    def test_short_segment_and_word_times_are_kept(self):
        d = {"segments": [{"start": 0.0, "end": 3.0, "text": "Hello there."},
                          {"start": 3.0, "end": 15.0, "text": "one two three four",
                           "words": [{"start": 3.0, "end": 5.0, "text": "one"}, {"start": 5.0, "end": 9.5, "text": "two"},
                                     {"start": 9.5, "end": 12.0, "text": "three"}, {"start": 12.0, "end": 15.0, "text": "four"}]}]}
        cues = export._cues(d, 8.0)
        self.assertEqual(cues[0], {"start": 0.0, "end": 3.0, "text": "Hello there.", "speaker": None})
        self.assertEqual([c["text"] for c in cues[1:]], ["one two", "three four"])
        self.assertNotIn("estimated", cues[1])

    def test_split_text(self):
        self.assertEqual(export.split_text("short", 1), ["short"])
        parts = export.split_text("The price was 3.5 dollars. It rose again, and nobody knew why. Then it fell.", 3)
        self.assertEqual(len(parts), 3)
        self.assertTrue(parts[0].endswith("dollars."))
        self.assertEqual(len(export.split_text("天" * 90, 3)), 3)            # no punctuation at all

    def test_paragraphs_get_a_time_mark_at_least_every_minute(self):
        segs = [{"start": i * 10.0, "end": i * 10.0 + 9.8, "text": f"句子{i}。"} for i in range(18)]   # 3 minutes, no pauses
        self.assertEqual(len(export.paragraphs(segs, 1.0, 0)), 1)
        paras = export.paragraphs(segs, 1.0, 60.0)
        self.assertEqual([p["start"] for p in paras], [0.0, 60.0, 120.0])

    def test_doctor_sizes_match_the_documentation(self):
        sizes = {e.get("repo"): e["gb"] for entries in doctor.MODEL_FILES.values() for e in entries}
        self.assertEqual(sizes["mlx-community/Qwen3-ASR-1.7B-8bit"], 2.5)
        skill = (HERE.parent / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("2.5 GB (8-bit MLX)", skill)
        self.assertFalse("$S/" in skill, "SKILL.md must not use a shell variable for the scripts path")


if __name__ == "__main__":
    unittest.main()
