#!/usr/bin/env python3
"""Check this machine for local transcription: hardware, tools, models already downloaded, earlier jobs.

    uv run doctor.py            # plain report with a recommendation per model
    uv run doctor.py --json     # the same as JSON

Standard library only, so it works before any model is installed.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (HOME, MODELS_DIR, apple_silicon, fmt_time, job_progress, machine_summary,  # noqa: E402
                     nvidia_gpus, registry)

# Where each model's files come from, what shows the download finished, and the size in GB.
# "repo" = a Hugging Face repo (kept in the HF cache); "local" = a folder under MODELS_DIR (sherpa-onnx).
MODEL_FILES: dict[str, list[dict[str, Any]]] = {
    "whisper": [
        {"repo": "mlx-community/whisper-large-v3-turbo", "need": ".safetensors", "gb": 1.6, "backends": ["mlx"]},
        {"repo": "mobiuslabsgmbh/faster-whisper-large-v3-turbo", "need": "model.bin", "gb": 1.6, "backends": ["ct2"]},
    ],
    "qwen3-asr": [
        {"repo": "mlx-community/Qwen3-ASR-1.7B-8bit", "need": ".safetensors", "gb": 2.1, "backends": ["mlx"]},
        {"repo": "Qwen/Qwen3-ASR-1.7B", "need": ".safetensors", "gb": 4.0, "backends": ["hf"]},
    ],
    "sensevoice": [
        {"local": "sherpa-onnx-sense-voice-zh-en-ja-ko-yue-int8-2025-09-09", "need": "model.int8.onnx", "gb": 0.25,
         "backends": ["onnx"]},
    ],
    "parakeet": [
        {"repo": "mlx-community/parakeet-tdt-0.6b-v3", "need": ".safetensors", "gb": 2.4, "backends": ["mlx"]},
        {"local": "sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8", "need": "encoder.int8.onnx", "gb": 0.65,
         "backends": ["onnx"]},
    ],
}
# Small helper models that sensevoice, parakeet-onnx and diarize.py need (sherpa-onnx, CPU).
HELPER_FILES = [
    {"local": "silero_vad.onnx", "need": "", "gb": 0.001, "for": "sensevoice, parakeet (onnx)"},
    {"local": "sherpa-onnx-pyannote-segmentation-3-0", "need": "model.onnx", "gb": 0.01, "for": "diarize.py"},
    {"local": "3dspeaker_speech_eres2net_base_sv_zh-cn_3dspeaker_16k.onnx", "need": "", "gb": 0.04, "for": "diarize.py"},
]


def hf_cache() -> Path:
    if os.environ.get("HF_HUB_CACHE"):
        return Path(os.environ["HF_HUB_CACHE"]).expanduser()
    if os.environ.get("HF_HOME"):
        return Path(os.environ["HF_HOME"]).expanduser() / "hub"
    return Path.home() / ".cache" / "huggingface" / "hub"


def present(entry: dict[str, Any]) -> bool:
    """True only when the model files are really there (an interrupted download does not count)."""
    if "local" in entry:
        p = MODELS_DIR / entry["local"]
        if not entry["need"]:
            return p.is_file() and p.stat().st_size > 100_000
        return p.is_dir() and any(f.name.endswith(entry["need"]) and f.stat().st_size > 100_000 for f in p.iterdir())
    snaps = hf_cache() / ("models--" + entry["repo"].replace("/", "--")) / "snapshots"
    if not snaps.is_dir():
        return False
    for snap in snaps.iterdir():
        for f in snap.rglob("*" + entry["need"]):
            try:
                if f.resolve().stat().st_size > 1_000_000:
                    return True
            except OSError:
                continue
    return False


def free_gb(path: Path) -> float:
    p = path
    while not p.exists():
        p = p.parent
    return round(shutil.disk_usage(p).free / 1024**3, 1)


def recommend(m: dict[str, Any], tools: dict[str, bool], cached: dict[str, list[bool]]) -> dict[str, Any]:
    ram = m["ram_gb"] or 0
    gpus = nvidia_gpus()
    vram = max((g["vram_gb"] for g in gpus), default=0)
    mac = apple_silicon()
    rec: dict[str, Any] = {}

    # SenseVoice: small, CPU, zh/yue/ja/ko/en. Fine everywhere.
    rec["sensevoice"] = {"verdict": "good", "backend": "onnx",
                         "why": "230 MB model on CPU, about 20-40x real time. Chinese, Cantonese, Japanese, "
                                "Korean, English only; sentence timestamps from the silence detector."}

    # Parakeet: fast, 25 European languages.
    if mac:
        rec["parakeet"] = {"verdict": "good", "backend": "mlx", "why": "Apple Silicon with MLX, about 50-100x real time."}
    else:
        rec["parakeet"] = {"verdict": "good", "backend": "onnx",
                           "why": "8-bit ONNX model on CPU, about 10-30x real time. European languages only."}

    # Whisper large-v3-turbo
    if mac and ram >= 8:
        rec["whisper"] = {"verdict": "good", "backend": "mlx",
                          "why": f"Apple Silicon with {ram} GB: MLX, about 20-30x real time."}
    elif vram >= 4:
        rec["whisper"] = {"verdict": "good", "backend": "ct2",
                          "why": f"NVIDIA GPU with {vram} GB: faster-whisper (CTranslate2, float16). "
                                 "Needs CUDA 12 and cuDNN 9 libraries."}
    elif ram >= 8:
        rec["whisper"] = {"verdict": "slow", "backend": "ct2",
                          "why": f"No GPU: faster-whisper on CPU (int8). Expect about 1-3x real time with "
                                 f"{m['cpu_cores']} cores."}
    else:
        rec["whisper"] = {"verdict": "no", "backend": None, "why": f"Only {ram} GB of memory; use sensevoice."}

    # Qwen3-ASR 1.7B
    if mac and ram >= 16:
        rec["qwen3-asr"] = {"verdict": "good", "backend": "mlx",
                            "why": f"Apple Silicon with {ram} GB: the 8-bit MLX model (2.1 GB), about 10-20x real time."}
    elif mac and ram >= 8:
        rec["qwen3-asr"] = {"verdict": "slow", "backend": "mlx",
                            "why": f"Apple Silicon with {ram} GB: the 8-bit model fits but leaves little room. "
                                   "Close other apps, or use --model-repo mlx-community/Qwen3-ASR-0.6B-8bit."}
    elif vram >= 8:
        rec["qwen3-asr"] = {"verdict": "good", "backend": "hf", "why": f"NVIDIA GPU with {vram} GB: PyTorch, bf16."}
    elif ram >= 16:
        rec["qwen3-asr"] = {"verdict": "slow", "backend": "hf",
                            "why": "No GPU: PyTorch on CPU works but may be slower than real time."}
    else:
        rec["qwen3-asr"] = {"verdict": "no", "backend": None,
                            "why": "Needs Apple Silicon with 8 GB, an NVIDIA GPU with 8 GB, or 16 GB of memory on CPU."}

    for name, r in rec.items():
        used = [(e, ok) for e, ok in zip(MODEL_FILES[name], cached[name]) if r["backend"] in e["backends"]]
        r["downloaded"] = bool(used) and all(ok for _, ok in used)
        r["download_gb"] = round(sum(e["gb"] for e, ok in used if not ok), 2)
        r["other_copies"] = [e.get("repo") or e.get("local") for e, ok in zip(MODEL_FILES[name], cached[name])
                             if ok and (e, ok) not in used]
    return rec


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    m = machine_summary()
    tools = {t: bool(shutil.which(t)) for t in ("uv", "ffmpeg", "ffprobe", "nvidia-smi", "gh")}
    cached = {name: [present(e) for e in entries] for name, entries in MODEL_FILES.items()}
    helpers = {e["local"]: present(e) for e in HELPER_FILES}
    rec = recommend(m, tools, cached)
    disk = {"hf_cache": str(hf_cache()), "hf_cache_free_gb": free_gb(hf_cache()),
            "local_asr_home": str(HOME), "cwd_free_gb": free_gb(Path.cwd())}
    jobs = []
    for path in registry()["jobs"]:
        p = Path(path)
        if (p / "job.json").exists():
            prog = job_progress(p)
            jobs.append({"path": path, **{k: prog[k] for k in ("name", "model", "chunks", "counts", "eta_minutes",
                                                              "audio_seconds")}})
        else:
            jobs.append({"path": path, "missing": True})
    report = {"machine": m, "tools": tools, "disk": disk, "recommendation": rec, "helpers": helpers, "jobs": jobs}

    if a.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return

    gpu = ", ".join(f"{g['name']} {g['vram_gb']} GB" for g in m["gpus"]) or (
        "Apple Silicon (shares main memory)" if apple_silicon() else "none found")
    print(f"Machine: {m['chip']} | {m['cpu_cores']} cores | {m['ram_gb']} GB memory | GPU: {gpu}")
    print(f"System:  {m['os']} ({m['arch']}), Python {m['python']}")
    print("Tools:   " + ", ".join(f"{t} {'yes' if ok else 'NO'}" for t, ok in tools.items()))
    if not tools["ffmpeg"]:
        print("         ffmpeg is required (macOS: brew install ffmpeg; Debian/Ubuntu: sudo apt install ffmpeg; "
              "Windows: winget install ffmpeg).")
    print(f"Disk:    {disk['hf_cache_free_gb']} GB free where models go ({disk['hf_cache']})")
    print()
    print("Models:")
    for name in ("whisper", "qwen3-asr", "sensevoice", "parakeet"):
        r = rec[name]
        if r["verdict"] == "no":
            have = ""
        elif r["downloaded"]:
            have = "already downloaded"
        else:
            have = f"download about {r['download_gb']} GB"
        print(f"  {name:10} {r['verdict'].upper():5} backend={r['backend'] or '-':5} {have}")
        print(f"             {r['why']}")
        if not r["downloaded"] and r["verdict"] != "no" and r["download_gb"] + 2 > disk["hf_cache_free_gb"]:
            print("             WARNING: not enough free disk for this download.")
        if r["other_copies"]:
            print(f"             Also on disk (another backend): {', '.join(r['other_copies'])}")
    print("  helpers    " + ", ".join(f"{e['local'].split('.')[0][:28]} {'yes' if helpers[e['local']] else 'no'}"
                                      for e in HELPER_FILES))
    print()
    if jobs:
        print("Earlier jobs on this machine:")
        for j in jobs:
            if j.get("missing"):
                print(f"  (folder gone) {j['path']}")
                continue
            c = j["counts"]
            done = j["chunks"] - c.get("todo", 0) - c.get("error", 0)
            eta = f", about {j['eta_minutes']} min left" if j["eta_minutes"] and done < j["chunks"] else ""
            print(f"  {j['name']}: {j['model']}, {done}/{j['chunks']} chunks, {fmt_time(j['audio_seconds'])} "
                  f"of audio{eta}  {j['path']}")
    else:
        print("Earlier jobs on this machine: none")


if __name__ == "__main__":
    main()
