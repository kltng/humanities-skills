"""Shared helpers for the local-audio-transcription scripts. Standard library only.

A job is a folder:
    job.json        settings, the chunk list, runs, notes (see references/api_reference.md)
    chunks/         16 kHz mono WAV pieces of each recording (made by prepare.py)
    rows.jsonl      one line per chunk transcribed (written by the run_*.py scripts; resumable)
    speakers.jsonl  one line per recording with speaker turns (written by diarize.py)
    export/         files made by export.py
    report.md       made by report.py
"""
from __future__ import annotations

import argparse
import html
import json
import os
import platform
import re
import shutil
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable

SKILL_VERSION = "1.0.0"
HOME = Path(os.environ.get("LOCAL_ASR_HOME", Path.home() / ".cache" / "local-audio-transcription")).expanduser()
REGISTRY = HOME / "registry.json"
MODELS_DIR = HOME / "models"
MODELS = ("whisper", "qwen3-asr", "sensevoice", "parakeet")


# ---------- offline guard ----------

def offline_requested(data: dict[str, Any] | None = None) -> bool:
    return bool((data or {}).get("offline")) or os.environ.get("LOCAL_ASR_OFFLINE") == "1"


def network_guard() -> None:
    """Make every network connection fail loudly, except to this machine.

    Called before the model libraries are imported, so that nothing downloads or phones home.
    Also tells Hugging Face libraries to work from the cache only.
    """
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["HF_DATASETS_OFFLINE"] = "1"
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    os.environ["DO_NOT_TRACK"] = "1"
    os.environ["LOCAL_ASR_OFFLINE"] = "1"

    def blocked(addr: Any) -> bool:
        host = addr[0] if isinstance(addr, tuple) else str(addr)
        return host not in ("127.0.0.1", "::1", "localhost", "")

    real_connect = socket.socket.connect
    real_connect_ex = socket.socket.connect_ex

    def connect(self: socket.socket, addr: Any) -> None:
        if blocked(addr):
            raise OSError(f"network blocked by local-audio-transcription offline mode: tried to reach {addr}")
        return real_connect(self, addr)

    def connect_ex(self: socket.socket, addr: Any) -> int:
        if blocked(addr):
            raise OSError(f"network blocked by local-audio-transcription offline mode: tried to reach {addr}")
        return real_connect_ex(self, addr)

    socket.socket.connect = connect  # type: ignore[method-assign]
    socket.socket.connect_ex = connect_ex  # type: ignore[method-assign]
    socket.create_connection = _blocked_create_connection  # type: ignore[assignment]
    socket.getaddrinfo = _blocked_getaddrinfo  # type: ignore[assignment]


_real_getaddrinfo = socket.getaddrinfo


def _blocked_getaddrinfo(host: Any, *args: Any, **kw: Any) -> Any:
    if host not in (None, "", "localhost", "127.0.0.1", "::1"):
        raise OSError(f"network blocked by local-audio-transcription offline mode: tried to resolve {host}")
    return _real_getaddrinfo(host, *args, **kw)


def _blocked_create_connection(address: Any, *args: Any, **kw: Any) -> Any:
    raise OSError(f"network blocked by local-audio-transcription offline mode: tried to reach {address}")


# ---------- jobs ----------

def load_job(job: Path) -> dict[str, Any]:
    f = Path(job) / "job.json"
    if not f.exists():
        raise SystemExit(f"{job} is not a job folder (no job.json). Make one with prepare.py.")
    return json.loads(f.read_text(encoding="utf-8"))


def save_job(job: Path, data: dict[str, Any]) -> None:
    f = Path(job) / "job.json"
    tmp = f.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(f)


def read_jsonl(path: Path, key: str, repair: bool = False) -> dict[str, dict[str, Any]]:
    """Rows by key. The last row for a key wins. repair=True cuts a half-written last line."""
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8")
    if repair and text and not text.endswith("\n"):
        text = text[: text.rfind("\n") + 1]
        path.write_text(text, encoding="utf-8")
    rows: dict[str, dict[str, Any]] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue  # a half line from a killed run
        rows[row[key]] = row
    return rows


def read_rows(job: Path, repair: bool = False) -> dict[str, dict[str, Any]]:
    return read_jsonl(Path(job) / "rows.jsonl", "chunk", repair)


def read_speakers(job: Path) -> dict[str, dict[str, Any]]:
    return read_jsonl(Path(job) / "speakers.jsonl", "doc")


def append_row(job: Path, row: dict[str, Any], name: str = "rows.jsonl") -> None:
    with open(Path(job) / name, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def todo_chunks(job: Path, data: dict[str, Any], limit: int | None = None,
                redo: set[str] | None = None) -> list[dict[str, Any]]:
    """Chunks still to transcribe. Chunks with an error row are done again; redo forces chunks."""
    rows = read_rows(job, repair=True)
    redo = redo or set()
    out = []
    for c in data["chunks"]:
        r = rows.get(c["id"])
        if c["id"] in redo or r is None or r.get("status") == "error":
            out.append(c)
    return out[:limit] if limit is not None else out


def start_run(job: Path, model: str, backend: str, versions: dict[str, str]) -> int:
    data = load_job(job)
    data.setdefault("runs", []).append({
        "model": model, "backend": backend, "versions": versions, "machine": machine_summary(),
        "offline": offline_requested(data), "started": now(), "ended": None, "chunks_done": 0,
        "skill_version": SKILL_VERSION,
    })
    save_job(job, data)
    return len(data["runs"]) - 1


def end_run(job: Path, index: int, chunks_done: int, outcome: str) -> None:
    data = load_job(job)
    run = data["runs"][index]
    run.update(ended=now(), chunks_done=chunks_done, outcome=outcome)
    save_job(job, data)


def run_chunks(job: Path, model: str, backend: str, versions: dict[str, str], chunks: list[dict[str, Any]],
               transcribe: Callable[[Path, dict[str, Any]], dict[str, Any]]) -> None:
    """Transcribe each chunk with transcribe(wav_path, chunk) and append its row. Safe to stop at any time.

    transcribe() returns {"segments": [{"start", "end", "text", ...}], "language": ..., ...} with times
    relative to the chunk. They are shifted to the recording's own clock here.
    """
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(143))  # so the finally block and atexit hooks run
    index = start_run(job, model, backend, versions)
    done, outcome = 0, "stopped"
    try:
        for n, c in enumerate(chunks, 1):
            t = time.time()
            try:
                row = transcribe(Path(job) / c["file"], c)
            except (OSError, ValueError) as e:  # a bad file; model errors still stop the run
                row = {"status": "error", "segments": [], "error": f"{type(e).__name__}: {e}"}
            segs = []
            for s in row.get("segments") or []:
                s = dict(s)
                s["start"] = round(float(s.get("start") or 0) + c["start"], 2)
                s["end"] = round(float(s.get("end") or s["start"] - c["start"]) + c["start"], 2)
                s["text"] = (s.get("text") or "").strip()
                for w in s.get("words") or []:
                    w["start"] = round(float(w["start"]) + c["start"], 2)
                    w["end"] = round(float(w["end"]) + c["start"], 2)
                if s["text"]:
                    segs.append(s)
            row["segments"] = segs
            row = {"chunk": c["id"], "doc": c["doc"], "model": model, "backend": backend,
                   "seconds": round(time.time() - t, 1), **row}
            row.setdefault("status", "ok")
            row["text"] = join_text(segs)
            flag_row(row, c)
            append_row(job, row)
            done += 1
            chars = len(row["text"])
            speed = round(c["duration"] / row["seconds"], 1) if row["seconds"] else 0
            print(f"{n}/{len(chunks)} chunk {c['id']} ({c['doc']} {fmt_time(c['start'])}-{fmt_time(c['end'])}) "
                  f"{row['seconds']}s ({speed}x real time) {chars} chars {row['status']}"
                  + (f" [{row['flag']}]" if row.get("flag") else ""), flush=True)
        outcome = "finished"
    finally:
        end_run(job, index, done, outcome)
    print(f"DONE {done} chunks", flush=True)


def join_text(segments: list[dict[str, Any]]) -> str:
    """Segments joined into one text. CJK text is joined without spaces."""
    out = ""
    for s in segments:
        t = s["text"]
        if out and not (is_cjk(out[-1]) and is_cjk(t[:1])):
            out += " "
        out += t
    return out


def is_cjk(ch: str) -> bool:
    if not ch:
        return False
    o = ord(ch)
    return (0x3000 <= o <= 0x30FF or 0x3400 <= o <= 0x4DBF or 0x4E00 <= o <= 0x9FFF or 0xF900 <= o <= 0xFAFF
            or 0xFF00 <= o <= 0xFFEF or 0xAC00 <= o <= 0xD7AF or 0x20000 <= o <= 0x2FFFF)


def flag_row(row: dict[str, Any], chunk: dict[str, Any]) -> None:
    """Mark chunks a person should look at. One flag per chunk, the most serious first."""
    if row.get("status") == "error":
        return
    speech = chunk.get("speech_share")
    text = row.get("text", "")
    rep = repeated_segments(row.get("segments", []))
    if rep:
        row["flag"] = "repeat"
        row["warning"] = f"the same text repeats {rep} times in a row; the model may have looped"
    elif text and speech is not None and speech < 0.05 and len(text) > 20:
        row["flag"] = "no_speech"
        row["warning"] = "text on a chunk that sounds silent; probably invented by the model"
    elif not text and (speech is None or speech > 0.3):
        row["flag"] = "empty"
        row["warning"] = "no text, although the chunk has sound"
    elif row.get("seconds") and chunk.get("duration") and row["seconds"] > 3 * chunk["duration"]:
        row["flag"] = "slow"
        row["warning"] = "took more than three times the length of the audio"
    else:
        low = [s for s in row.get("segments", []) if s.get("logprob") is not None and s["logprob"] < -1.5]
        if low:
            row["flag"] = "uncertain"
            row["warning"] = (f"{len(low)} segment(s) with very low confidence (Whisper logprob under -1.5): "
                              "often invented text on music, noise or a language the model did not expect")
    exp = chunk.get("language")
    got = row.get("language")
    if exp and got and norm_lang(exp) != norm_lang(got) and not row.get("flag"):
        row["flag"] = "language"
        row["warning"] = f"detected language {got}, expected {exp}"


def repeated_segments(segments: list[dict[str, Any]], at_least: int = 4) -> int:
    best = run = 1
    prev = None
    for s in segments:
        t = re.sub(r"\W+", "", s.get("text", "")).lower()
        if t and t == prev:
            run += 1
            best = max(best, run)
        else:
            run = 1
        prev = t
    return best if best >= at_least else 0


LANG_ALIASES = {
    "zh": "zh", "chinese": "zh", "mandarin": "zh", "zh-cn": "zh", "zh-tw": "zh", "zh-hans": "zh", "zh-hant": "zh",
    "yue": "yue", "cantonese": "yue", "zh-hk": "yue", "zh-yue": "yue",
    "en": "en", "english": "en", "ja": "ja", "japanese": "ja", "ko": "ko", "korean": "ko",
    "de": "de", "german": "de", "fr": "fr", "french": "fr", "es": "es", "spanish": "es", "it": "it", "italian": "it",
    "pt": "pt", "portuguese": "pt", "ru": "ru", "russian": "ru", "vi": "vi", "vietnamese": "vi", "th": "th", "thai": "th",
    "ar": "ar", "arabic": "ar", "nl": "nl", "dutch": "nl", "id": "id", "indonesian": "id", "ms": "ms", "malay": "ms",
    "hi": "hi", "hindi": "hi", "tr": "tr", "turkish": "tr", "pl": "pl", "polish": "pl",
}


def norm_lang(lang: str | None) -> str | None:
    """A short code for a language name or code (zh, yue, en, ja ...). Unknown names pass through."""
    if not lang:
        return None
    key = lang.strip().lower()
    return LANG_ALIASES.get(key, LANG_ALIASES.get(key.split("-")[0], key))


def runner_args(description: str, backends: list[str]) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=description, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("job", type=Path)
    ap.add_argument("--backend", choices=["auto", *backends], default="auto")
    ap.add_argument("--limit", type=int, help="transcribe at most N chunks (smoke test)")
    ap.add_argument("--chunks", help="chunk ids to do again, e.g. 00012,00040")
    ap.add_argument("--setup", action="store_true", help="install, download and load the model, then stop")
    ap.add_argument("--language", help="force the language (code or name); default: from the job, else detect")
    return ap.parse_args()


def runner_start(a: argparse.Namespace) -> tuple[dict[str, Any], list[dict[str, Any]], str | None]:
    """Load the job, turn on the offline guard when the job wants it, and list the chunks to do."""
    data = load_job(a.job)
    if offline_requested(data) and not a.setup:
        network_guard()
        print("offline mode: every network connection is blocked for this run", flush=True)
    redo = set(a.chunks.split(",")) if a.chunks else None
    todo = todo_chunks(a.job, data, a.limit, redo)
    language = a.language or data.get("language")
    return data, todo, language


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def fmt_time(seconds: float) -> str:
    seconds = max(0.0, float(seconds))
    h, rem = divmod(int(seconds), 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def srt_time(seconds: float, sep: str = ",") -> str:
    seconds = max(0.0, float(seconds))
    ms = int(round((seconds - int(seconds)) * 1000))
    h, rem = divmod(int(seconds), 3600)
    m, s = divmod(rem, 60)
    if ms == 1000:
        ms = 0
        s += 1
    return f"{h:02d}:{m:02d}:{s:02d}{sep}{ms:03d}"


# ---------- registry of jobs on this machine ----------

def registry() -> dict[str, Any]:
    if REGISTRY.exists():
        try:
            return json.loads(REGISTRY.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {"jobs": {}}


def register_job(job: Path, data: dict[str, Any]) -> None:
    HOME.mkdir(parents=True, exist_ok=True)
    reg = registry()
    reg["jobs"][str(Path(job).resolve())] = {"name": data["name"], "model": data.get("model"),
                                             "created": data.get("created"), "chunks": len(data["chunks"]),
                                             "offline": bool(data.get("offline"))}
    REGISTRY.write_text(json.dumps(reg, ensure_ascii=False, indent=2), encoding="utf-8")


def job_progress(job: Path) -> dict[str, Any]:
    data = load_job(job)
    rows = read_rows(job)
    counts: dict[str, int] = {}
    done_audio = todo_audio = 0.0
    for c in data["chunks"]:
        r = rows.get(c["id"])
        s = r.get("status", "ok") if r else "todo"
        counts[s] = counts.get(s, 0) + 1
        if r and s != "error":
            done_audio += c["duration"]
        else:
            todo_audio += c["duration"]
    secs = sum(r["seconds"] for r in rows.values() if r.get("status") == "ok" and r.get("seconds"))
    speed = round(done_audio / secs, 1) if secs else None  # x real time
    flags: dict[str, int] = {}
    for r in rows.values():
        if r.get("flag"):
            flags[r["flag"]] = flags.get(r["flag"], 0) + 1
    return {"name": data["name"], "model": data.get("model"), "chunks": len(data["chunks"]), "counts": counts,
            "docs": len(data.get("sources", [])), "audio_seconds": done_audio + todo_audio,
            "done_seconds": done_audio, "speed": speed, "flags": flags,
            "eta_minutes": round(todo_audio / speed / 60, 1) if speed else None,
            "last_run": (data.get("runs") or [{}])[-1]}


# ---------- the machine ----------

def run_cmd(cmd: list[str], timeout: int = 10) -> str:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def nvidia_gpus() -> list[dict[str, Any]]:
    if not shutil.which("nvidia-smi"):
        return []
    out = run_cmd(["nvidia-smi", "--query-gpu=name,memory.total,memory.free", "--format=csv,noheader,nounits"])
    gpus = []
    for line in out.splitlines():
        parts = [x.strip() for x in line.split(",")]
        if len(parts) == 3:
            try:
                gpus.append({"name": parts[0], "vram_gb": round(int(parts[1]) / 1024, 1),
                             "free_gb": round(int(parts[2]) / 1024, 1)})
            except ValueError:
                pass
    return gpus


def ram_gb() -> float | None:
    system = platform.system()
    if system == "Darwin":
        v = run_cmd(["sysctl", "-n", "hw.memsize"])
        return round(int(v) / 1024**3, 1) if v.isdigit() else None
    if system == "Linux":
        try:
            for line in open("/proc/meminfo"):
                if line.startswith("MemTotal:"):
                    return round(int(line.split()[1]) / 1024**2, 1)
        except OSError:
            return None
    if system == "Windows":
        v = run_cmd(["powershell", "-NoProfile", "-Command",
                     "(Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory"])
        return round(int(v) / 1024**3, 1) if v.isdigit() else None
    return None


def chip_name() -> str:
    system = platform.system()
    if system == "Darwin":
        return run_cmd(["sysctl", "-n", "machdep.cpu.brand_string"]) or platform.processor()
    if system == "Linux":
        try:
            for line in open("/proc/cpuinfo"):
                if line.lower().startswith("model name"):
                    return line.split(":", 1)[1].strip()
        except OSError:
            pass
    return platform.processor() or platform.machine()


def apple_silicon() -> bool:
    return platform.system() == "Darwin" and platform.machine() == "arm64"


def machine_summary() -> dict[str, Any]:
    """What a field report may say about the machine. No user names, no paths."""
    return {"os": f"{platform.system()} {platform.release()}", "arch": platform.machine(), "chip": chip_name(),
            "cpu_cores": os.cpu_count(), "ram_gb": ram_gb(),
            "gpus": [{"name": g["name"], "vram_gb": g["vram_gb"]} for g in nvidia_gpus()],
            "python": platform.python_version()}


def ffmpeg() -> str:
    for name in ("ffmpeg", "ffmpeg.exe"):
        p = shutil.which(name)
        if p:
            return p
    raise SystemExit("ffmpeg was not found. Install it first: macOS `brew install ffmpeg`, "
                     "Debian/Ubuntu `sudo apt install ffmpeg`, Windows `winget install ffmpeg`.")


def wav_samples(path: Path) -> tuple[list[float], int]:
    """A 16 kHz mono 16-bit WAV as floats in -1..1 (no numpy needed)."""
    import array
    import wave
    with wave.open(str(path)) as w:
        if w.getsampwidth() != 2 or w.getnchannels() != 1:
            raise ValueError(f"{path} is not 16-bit mono (run prepare.py)")
        rate = w.getframerate()
        raw = array.array("h")
        raw.frombytes(w.readframes(w.getnframes()))
        if sys.byteorder != "little":
            raw.byteswap()
    return [x / 32768.0 for x in raw], rate


def pieces(chunk: dict[str, Any], max_len: float = 30.0, min_silence: float = 0.0) -> list[tuple[float, float]]:
    """Cut a chunk into pieces of at most max_len seconds at the middle of its silences.

    For models that give no timestamps (Qwen3-ASR, SenseVoice): each piece becomes one timed segment.
    Times are relative to the chunk. No audio is dropped.
    """
    dur = float(chunk["duration"])
    mids = sorted((s + e) / 2 for s, e in chunk.get("silences") or [] if e - s >= min_silence and 0 < (s + e) / 2 < dur)
    bounds = [0.0, *mids, dur]
    regions = [(bounds[i], bounds[i + 1]) for i in range(len(bounds) - 1) if bounds[i + 1] - bounds[i] > 0.05]
    out: list[tuple[float, float]] = []
    for s, e in regions:
        if out and e - out[-1][0] <= max_len:
            out[-1] = (out[-1][0], e)  # merge with the piece before
        else:
            while e - s > max_len:  # no silence for a long time: cut at a fixed length
                out.append((s, s + max_len))
                s += max_len
            out.append((s, e))
    return [(round(s, 2), round(e, 2)) for s, e in out]


def download(url: str, dest: Path) -> Path:
    """Download a file or a .tar.bz2 archive into dest (a folder). Returns the file or extracted folder."""
    import tarfile
    import urllib.request
    dest.mkdir(parents=True, exist_ok=True)
    name = url.rsplit("/", 1)[-1]
    target = dest / name
    if name.endswith(".tar.bz2"):
        folder = dest / name[: -len(".tar.bz2")]
        if folder.is_dir():
            return folder
    elif target.exists():
        return target
    if os.environ.get("LOCAL_ASR_OFFLINE") == "1":
        raise SystemExit(f"offline mode: {name} is missing and cannot be downloaded. Run --setup with the network on.")
    print(f"Downloading {name} …", flush=True)
    tmp = target.with_suffix(target.suffix + ".part")
    with urllib.request.urlopen(url, timeout=60) as r, open(tmp, "wb") as fh:
        shutil.copyfileobj(r, fh)
    if name.endswith(".tar.bz2"):
        with tarfile.open(tmp, "r:bz2") as tar:
            tar.extractall(dest, filter="data")
        tmp.unlink()
        return dest / name[: -len(".tar.bz2")]
    tmp.replace(target)
    return target


SHERPA = "https://github.com/k2-fsa/sherpa-onnx/releases/download"


def esc(s: str) -> str:
    return html.escape(s or "", quote=True)
