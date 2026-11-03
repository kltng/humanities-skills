#!/usr/bin/env python3
"""Check this machine for local OCR: hardware, tools, models already downloaded, earlier jobs.

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
from _common import (HOME, MODELS_DIR, apple_silicon, job_progress, machine_summary, nvidia_gpus,  # noqa: E402
                     registry)

# Hugging Face repos each model downloads, the files that show the download finished, and size in GB.
MODEL_FILES = {
    "chandra": [
        {"repo": "jwindle47/chandra-ocr-2-8bit-mlx", "need": ".safetensors", "gb": 5.2, "backends": ["mlx"]},
        {"repo": "datalab-to/chandra-ocr-2", "need": ".safetensors", "gb": 10.6, "backends": ["hf"]},
    ],
    "surya": [
        {"repo": "datalab-to/surya-ocr-2.5-gguf", "need": ".gguf", "gb": 2.0, "backends": ["llamacpp"]},
        {"repo": "datalab-to/surya-ocr-2.5", "need": ".safetensors", "gb": 1.4, "backends": ["vllm", "mlx"]},
        {"local": "surya-2.5-mlx-q8", "need": ".safetensors", "gb": 0.8, "backends": ["mlx"]},
    ],
    "indra": [
        {"repo": "datalab-to/indra-ocr", "need": ".onnx", "gb": 0.1, "backends": ["cpu"]},
    ],
}


def hf_cache() -> Path:
    if os.environ.get("HF_HUB_CACHE"):
        return Path(os.environ["HF_HUB_CACHE"]).expanduser()
    if os.environ.get("HF_HOME"):
        return Path(os.environ["HF_HOME"]).expanduser() / "hub"
    return Path.home() / ".cache" / "huggingface" / "hub"


def present(entry: dict[str, Any]) -> bool:
    """True only when the weight files are really there (an interrupted download does not count)."""
    if "local" in entry:
        root = MODELS_DIR / entry["local"]
        return root.is_dir() and any(f.name.endswith(entry["need"]) for f in root.iterdir())
    snaps = hf_cache() / ("models--" + entry["repo"].replace("/", "--")) / "snapshots"
    if not snaps.is_dir():
        return False
    for snap in snaps.iterdir():
        for f in snap.rglob("*" + entry["need"]):
            try:
                if f.resolve().stat().st_size > 1_000_000 or entry["need"] == ".onnx":
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

    # Indra: tiny, CPU only. Fine everywhere, but not for vertical CJK.
    rec["indra"] = {"verdict": "good", "backend": "cpu",
                    "why": "1M-parameter model on CPU, about 0.1 s per page. Horizontal print only: "
                           "it fails on vertical (top-to-bottom) Chinese or Japanese."}

    # Surya 2.5
    if mac and tools["llama-server"]:
        rec["surya"] = {"verdict": "good", "backend": "llamacpp", "why": "Apple Silicon with llama.cpp (Metal)."}
    elif mac and ram >= 8:
        rec["surya"] = {"verdict": "good", "backend": "mlx",
                        "why": "Apple Silicon: uses an 8-bit MLX build made on first use. "
                               "Installing llama.cpp (brew install llama.cpp) is faster still."}
    elif vram >= 8 and tools["docker"]:
        rec["surya"] = {"verdict": "good", "backend": "vllm", "why": f"NVIDIA GPU with {vram} GB and Docker."}
    elif vram >= 6 and tools["llama-server"]:
        rec["surya"] = {"verdict": "good", "backend": "llamacpp",
                        "why": f"NVIDIA GPU with {vram} GB; needs a llama.cpp build with CUDA."}
    elif tools["llama-server"] and ram >= 8:
        rec["surya"] = {"verdict": "slow", "backend": "llamacpp",
                        "why": "No GPU: llama.cpp on CPU works but may take a minute or more per page."}
    elif ram >= 8:
        rec["surya"] = {"verdict": "slow", "backend": "llamacpp",
                        "why": "No GPU and no llama.cpp. Install llama.cpp (llama-server) first, "
                               "then expect a minute or more per page on CPU."}
    else:
        rec["surya"] = {"verdict": "no", "backend": None, "why": f"Only {ram} GB of memory; Surya wants 8 GB."}

    # Chandra OCR 2
    if mac and ram >= 16:
        rec["chandra"] = {"verdict": "good", "backend": "mlx",
                          "why": f"Apple Silicon with {ram} GB: the 8-bit MLX model (5.2 GB) fits. "
                                 "About 55 s per page on an M-series Mac."}
    elif mac:
        rec["chandra"] = {"verdict": "no", "backend": None,
                          "why": f"Apple Silicon with only {ram} GB; the 8-bit model needs 16 GB."}
    elif vram >= 24:
        rec["chandra"] = {"verdict": "good", "backend": "hf", "why": f"NVIDIA GPU with {vram} GB."}
    elif vram >= 16:
        rec["chandra"] = {"verdict": "slow", "backend": "hf",
                          "why": f"NVIDIA GPU with {vram} GB: the full model (10.6 GB) fits, but big pages "
                                 "may run out of memory."}
    else:
        rec["chandra"] = {"verdict": "no", "backend": None,
                          "why": "Needs Apple Silicon with 16 GB or an NVIDIA GPU with 16 GB+. On CPU a page "
                                 "takes far too long."}

    for name, r in rec.items():
        used = [(e, ok) for e, ok in zip(MODEL_FILES[name], cached[name]) if r["backend"] in e["backends"]]
        r["downloaded"] = bool(used) and all(ok for _, ok in used)
        r["download_gb"] = round(sum(e["gb"] for e, ok in used if not ok), 1)
        r["other_copies"] = [e.get("repo") or e.get("local") for e, ok in zip(MODEL_FILES[name], cached[name])
                             if ok and (e, ok) not in used]
    return rec


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    m = machine_summary()
    tools = {t: bool(shutil.which(t)) for t in ("uv", "llama-server", "docker", "nvidia-smi", "gh")}
    cached = {name: [present(e) for e in entries] for name, entries in MODEL_FILES.items()}
    rec = recommend(m, tools, cached)
    disk = {"hf_cache": str(hf_cache()), "hf_cache_free_gb": free_gb(hf_cache()),
            "local_ocr_home": str(HOME), "cwd_free_gb": free_gb(Path.cwd())}
    jobs = []
    for path in registry()["jobs"]:
        p = Path(path)
        if (p / "job.json").exists():
            prog = job_progress(p)
            jobs.append({"path": path, **{k: prog[k] for k in ("name", "model", "pages", "counts", "eta_hours")}})
        else:
            jobs.append({"path": path, "missing": True})
    report = {"machine": m, "tools": tools, "disk": disk, "recommendation": rec, "jobs": jobs}

    if a.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return

    gpu = ", ".join(f"{g['name']} {g['vram_gb']} GB" for g in m["gpus"]) or (
        "Apple Silicon (shares main memory)" if apple_silicon() else "none found")
    print(f"Machine: {m['chip']} | {m['cpu_cores']} cores | {m['ram_gb']} GB memory | GPU: {gpu}")
    print(f"System:  {m['os']} ({m['arch']}), Python {m['python']}")
    print("Tools:   " + ", ".join(f"{t} {'yes' if ok else 'no'}" for t, ok in tools.items()))
    print(f"Disk:    {disk['hf_cache_free_gb']} GB free where models go ({disk['hf_cache']})")
    print()
    print("Models:")
    for name in ("chandra", "surya", "indra"):
        r = rec[name]
        if r["verdict"] == "no":
            have = ""
        elif r["downloaded"]:
            have = "already downloaded"
        else:
            have = f"download about {r['download_gb']} GB"
        print(f"  {name:8} {r['verdict'].upper():5} backend={r['backend'] or '-':8} {have}")
        print(f"           {r['why']}")
        if not r["downloaded"] and r["verdict"] != "no" and r["download_gb"] + 3 > disk["hf_cache_free_gb"]:
            print("           WARNING: not enough free disk for this download.")
        if r["other_copies"]:
            print(f"           Also on disk (another backend): {', '.join(r['other_copies'])}")
    print()
    if jobs:
        print("Earlier jobs on this machine:")
        for j in jobs:
            if j.get("missing"):
                print(f"  (folder gone) {j['path']}")
                continue
            c = j["counts"]
            done = j["pages"] - c.get("todo", 0) - c.get("error", 0)
            eta = f", about {j['eta_hours']} h left" if j["eta_hours"] and done < j["pages"] else ""
            print(f"  {j['name']}: {j['model']}, {done}/{j['pages']} pages{eta}  {j['path']}")
    else:
        print("Earlier jobs on this machine: none")


if __name__ == "__main__":
    main()
