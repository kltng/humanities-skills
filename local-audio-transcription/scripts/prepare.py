#!/usr/bin/env python3
"""Make a transcription job folder from audio or video files, or folders of them.

    uv run prepare.py SOURCE [SOURCE ...] --job JOB --model whisper|qwen3-asr|sensevoice|parakeet
                      [--language zh] [--formats txt,srt,json] [--chunk-minutes 10] [--offline]
                      [--diarize] [--sample] [--brief brief.json] [--name NAME]

Each file becomes one "recording" (exports keep recordings apart). ffmpeg converts it to 16 kHz mono
WAV and finds the silences; the recording is cut into chunks of about --chunk-minutes at the longest
silence near the cut, so no word is cut in half. Chunks go to JOB/chunks/NNNNN.wav. Running it again
with the same JOB adds only new files. Standard library only, but ffmpeg and ffprobe must be installed.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import time
import wave
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import MODELS, SKILL_VERSION, ffmpeg, fmt_time, load_job, norm_lang, register_job, save_job  # noqa: E402

AUDIO = {".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg", ".oga", ".opus", ".wma", ".aiff", ".aif", ".amr",
         ".wv", ".ape", ".caf", ".mp4", ".m4v", ".mov", ".mkv", ".webm", ".avi", ".mts", ".3gp", ".mpeg", ".mpg"}
FORMATS = {"txt", "md", "srt", "vtt", "json", "jsonl", "tei", "csv"}
RATE = 16000


def doc_name(path: Path, taken: set[str]) -> str:
    base = re.sub(r"[^\w\-.]+", "_", path.stem, flags=re.UNICODE).strip("_") or "rec"
    name, i = base, 2
    while name in taken:
        name, i = f"{base}-{i}", i + 1
    return name


def convert(src: Path, wav: Path, noise_db: int, min_silence: float) -> list[tuple[float, float]]:
    """ffmpeg: any audio/video -> 16 kHz mono 16-bit WAV, and the list of silences (start, end)."""
    cmd = [ffmpeg(), "-nostdin", "-hide_banner", "-loglevel", "info", "-y", "-i", str(src), "-vn", "-sn", "-dn",
           "-map", "0:a:0", "-ac", "1", "-ar", str(RATE), "-c:a", "pcm_s16le",
           "-af", f"silencedetect=noise={noise_db}dB:d={min_silence}", str(wav)]
    p = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
    if p.returncode != 0 or not wav.exists():
        tail = "\n".join(p.stderr.strip().splitlines()[-5:])
        raise RuntimeError(f"ffmpeg could not read {src.name}: {tail}")
    silences: list[tuple[float, float]] = []
    start = None
    for line in p.stderr.splitlines():
        m = re.search(r"silence_start:\s*(-?[\d.]+)", line)
        if m:
            start = max(0.0, float(m.group(1)))
        m = re.search(r"silence_end:\s*(-?[\d.]+)", line)
        if m and start is not None:
            silences.append((start, float(m.group(1))))
            start = None
    if start is not None:  # silence to the end of the file
        silences.append((start, wav_duration(wav)))
    return silences


def wav_duration(wav: Path) -> float:
    with wave.open(str(wav)) as w:
        return w.getnframes() / w.getframerate()


def cut_points(duration: float, silences: list[tuple[float, float]], target: float, min_chunk: float) -> list[float]:
    """Where to cut: the longest silence between 60% and 100% of the target length, else at the target."""
    cuts: list[float] = []
    cur = 0.0
    while duration - cur > target + min_chunk:
        lo, hi = cur + 0.6 * target, cur + target
        best = None
        for s, e in silences:
            mid = (s + e) / 2
            if lo <= mid <= hi and (best is None or e - s > best[1]):
                best = (mid, e - s)
        cut = best[0] if best else hi
        cuts.append(round(cut, 2))
        cur = cut
    return cuts


def speech_share(start: float, end: float, silences: list[tuple[float, float]]) -> float:
    length = end - start
    if length <= 0:
        return 0.0
    quiet = sum(max(0.0, min(e, end) - max(s, start)) for s, e in silences)
    return round(max(0.0, 1 - quiet / length), 3)


def write_chunk(src: wave.Wave_read, out: Path, start: float, end: float) -> None:
    rate = src.getframerate()
    src.setpos(int(start * rate))
    frames = src.readframes(int((end - start) * rate))
    with wave.open(str(out), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(frames)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("sources", nargs="+", type=Path)
    ap.add_argument("--job", type=Path, required=True)
    ap.add_argument("--model", choices=MODELS, required=True)
    ap.add_argument("--name")
    ap.add_argument("--language", help="the language spoken (zh, yue, en, ja, ...); leave out to detect")
    ap.add_argument("--formats", default="txt,srt,json", help=f"export formats, from: {','.join(sorted(FORMATS))}")
    ap.add_argument("--chunk-minutes", type=float, default=10, help="target chunk length (default 10)")
    ap.add_argument("--offline", action="store_true", help="strict offline job: runs block every network connection")
    ap.add_argument("--diarize", action="store_true", help="plan speaker labels (diarize.py) for this job")
    ap.add_argument("--sample", action="store_true", help="this job holds the user's sample clip (a test job)")
    ap.add_argument("--brief", type=Path, help="JSON file with the interview answers, stored in job.json")
    ap.add_argument("--noise-db", type=int, default=-35, help="silence threshold for ffmpeg silencedetect")
    ap.add_argument("--min-silence", type=float, default=0.5, help="seconds of quiet that count as a silence")
    a = ap.parse_args()

    formats = [f.strip() for f in a.formats.split(",") if f.strip()]
    bad = [f for f in formats if f not in FORMATS]
    if bad:
        raise SystemExit(f"unknown format(s): {', '.join(bad)}")
    ffmpeg()
    if not shutil.which("ffprobe"):
        print("note: ffprobe not found; durations are read from the converted WAV instead", file=sys.stderr)

    job = a.job
    (job / "chunks").mkdir(parents=True, exist_ok=True)
    if (job / "job.json").exists():
        data = load_job(job)
        if data["model"] != a.model:
            print(f"note: job was made for {data['model']}; switching to {a.model}. "
                  "Chunks already transcribed keep their old rows.", file=sys.stderr)
            data["model"] = a.model
    else:
        data = {"name": a.name or job.resolve().name, "created": time.strftime("%Y-%m-%d"),
                "skill_version": SKILL_VERSION, "model": a.model, "language": None, "formats": formats,
                "offline": False, "diarize": False, "sample": False, "brief": {},
                "sources": [], "chunks": [], "runs": [], "notes": []}
    data["formats"] = formats
    data["offline"] = data.get("offline") or a.offline
    data["diarize"] = data.get("diarize") or a.diarize
    data["sample"] = data.get("sample") or a.sample
    if a.language:
        data["language"] = norm_lang(a.language)
    if a.brief:
        data["brief"] = json.loads(a.brief.read_text(encoding="utf-8"))

    files: list[Path] = []
    for s in a.sources:
        if s.is_dir():
            files += sorted(p for p in s.rglob("*") if p.suffix.lower() in AUDIO and not p.name.startswith("."))
        elif s.exists():
            files.append(s)
        else:
            raise SystemExit(f"not found: {s}")

    known = {src["path"] for src in data["sources"]}
    taken = {src["doc"] for src in data["sources"]}
    n = len(data["chunks"])
    added = 0
    target = a.chunk_minutes * 60
    tmp = job / "chunks" / "_whole.wav"
    for f in files:
        key = str(f.resolve())
        if key in known:
            continue
        if f.suffix.lower() not in AUDIO:
            print(f"skip (not audio or video): {f}", file=sys.stderr)
            continue
        doc = doc_name(f, taken)
        try:
            silences = convert(f, tmp, a.noise_db, a.min_silence)
            duration = wav_duration(tmp)
        except (RuntimeError, OSError, wave.Error) as e:
            print(f"could not read {f}: {e}", file=sys.stderr)
            data["sources"].append({"path": key, "doc": doc, "duration": 0, "chunks": 0, "error": str(e)})
            taken.add(doc)
            continue
        taken.add(doc)
        cuts = cut_points(duration, silences, target, min(60.0, target / 4))
        bounds = [0.0, *cuts, round(duration, 2)]
        count = 0
        with wave.open(str(tmp)) as src:
            for i in range(len(bounds) - 1):
                start, end = bounds[i], bounds[i + 1]
                if end - start < 0.2:
                    continue
                n += 1
                cid = f"{n:05d}"
                write_chunk(src, job / "chunks" / f"{cid}.wav", start, end)
                inside = [[round(max(s0, start) - start, 2), round(min(e0, end) - start, 2)]
                          for s0, e0 in silences if e0 > start and s0 < end]
                data["chunks"].append({"id": cid, "doc": doc, "index": i + 1, "file": f"chunks/{cid}.wav",
                                       "start": start, "end": end, "duration": round(end - start, 2),
                                       "speech_share": speech_share(start, end, silences),
                                       "silences": inside, "language": data.get("language")})
                count += 1
        tmp.unlink(missing_ok=True)
        data["sources"].append({"path": key, "doc": doc, "duration": round(duration, 2), "chunks": count,
                                "silences": len(silences)})
        added += count
        print(f"{doc}: {fmt_time(duration)}, {count} chunk(s)", flush=True)

    save_job(job, data)
    register_job(job, data)
    total = sum(s.get("duration", 0) for s in data["sources"])
    quiet = [c["id"] for c in data["chunks"] if c["speech_share"] < 0.05]
    broken = [s["doc"] for s in data["sources"] if s.get("error")]
    print(f"\nJob {data['name']}: {len(data['sources'])} recording(s), {fmt_time(total)} of audio, "
          f"{len(data['chunks'])} chunks ({added} new); model {data['model']}, "
          f"language {data.get('language') or 'detect'}, offline {'yes' if data['offline'] else 'no'}")
    if quiet:
        print(f"Chunks that sound silent ({len(quiet)}): {', '.join(quiet[:20])}{' …' if len(quiet) > 20 else ''}")
    if broken:
        print(f"Could not read ({len(broken)}): {', '.join(broken[:20])}")


if __name__ == "__main__":
    main()
