# /// script
# requires-python = ">=3.12,<3.13"
# dependencies = [
#   "surya-ocr==0.23.0",
#   "mlx-vlm==0.7.10; sys_platform == 'darwin' and platform_machine == 'arm64'",
# ]
# ///
"""Read a job's pages with Surya OCR 2.5 (Datalab): fast, good on clean print, with layout.

    uv run run_surya.py JOB [--backend llamacpp|mlx|vllm] [--limit N] [--pages 00012,00040] [--setup]

Backends (auto picks in this order):
  llamacpp  Apple Silicon (Metal), NVIDIA (CUDA build) or CPU. Needs the llama-server program
            (macOS: brew install llama.cpp). Downloads the GGUF model, about 2 GB.
  mlx       Apple Silicon without llama.cpp. Builds an 8-bit MLX copy on first use (downloads 1.4 GB).
  vllm      NVIDIA GPU with Docker: runs the vllm/vllm-openai image.
Surya does not report loops, so a page slower than 120 s is marked "slow" for checking. Resumable.
"""
from __future__ import annotations

import importlib.util
import os
import platform
import shutil
import subprocess
import sys
from importlib.metadata import version
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import MODELS_DIR, load_job, norm_label, html_to_text, run_pages, runner_args, page_ids, todo_pages  # noqa: E402

SOURCE = "datalab-to/surya-ocr-2.5"
MLX_BUILD = MODELS_DIR / "surya-2.5-mlx-q8"
SLOW = 120


def pick_backend(choice: str) -> str:
    if choice != "auto":
        return choice
    mac = platform.system() == "Darwin" and platform.machine() == "arm64"
    if shutil.which("llama-server") and (mac or not shutil.which("nvidia-smi") or not shutil.which("docker")):
        return "llamacpp"
    if mac:
        return "mlx"
    if shutil.which("nvidia-smi") and shutil.which("docker"):
        return "vllm"
    raise SystemExit("Surya needs llama.cpp here. Install it so that `llama-server` is on the PATH "
                     "(https://github.com/ggml-org/llama.cpp), then run again.")


def setup_mlx() -> None:
    """Build our 8-bit MLX copy once, then point Surya at it (same steps as the tested run)."""
    if not any(MLX_BUILD.glob("*.safetensors")):
        print(f"Building the 8-bit MLX model in {MLX_BUILD} (downloads {SOURCE}, about 1.4 GB) …", flush=True)
        build = Path(importlib.util.find_spec("surya").origin).parent / "scripts" / "build_mlx.py"
        MODELS_DIR.mkdir(parents=True, exist_ok=True)
        subprocess.check_call([sys.executable, str(build), "--checkpoint", SOURCE, "--out-dir", str(MODELS_DIR),
                               "--name", MLX_BUILD.name, "--q-bits", "8", "--overwrite"])
    # mlx_vlm.server lists every model in the HF cache, and Surya sends requests to the first one.
    # An empty cache folder leaves only our model.
    empty = MODELS_DIR / "empty-hf-cache"
    empty.mkdir(parents=True, exist_ok=True)
    os.environ.update(SURYA_MLX_MODEL=str(MLX_BUILD), SURYA_INFERENCE_PARALLEL="1",
                      SURYA_MODEL_CHECKPOINT=SOURCE, HF_HUB_CACHE=str(empty))


def main() -> None:
    a = runner_args(__doc__, ["llamacpp", "mlx", "vllm"])
    backend = pick_backend(a.backend)
    data = load_job(a.job)
    redo = page_ids(a.pages, data)
    todo = todo_pages(a.job, data, a.limit, redo)
    if not todo and not a.setup:
        print("Nothing to read: every page has a row. Use --pages to read pages again.")
        return

    os.environ["SURYA_INFERENCE_BACKEND"] = backend
    if backend == "mlx":
        setup_mlx()

    from PIL import Image
    from surya.inference import SuryaInferenceManager
    from surya.recognition import RecognitionPredictor

    print(f"Starting Surya 2.5 with {backend} (downloads the model if it is not on this machine yet) …", flush=True)
    rec = RecognitionPredictor(SuryaInferenceManager())
    versions = {"surya-ocr": version("surya-ocr")}
    if backend == "mlx":
        versions["mlx-vlm"] = version("mlx-vlm")
    if a.setup:
        with Image.new("RGB", (800, 200), "white") as im:  # one tiny page makes it download and start
            rec([im])
        print(f"Surya 2.5 is ready (backend {backend}).")
        return

    def read(path: Path, page: dict) -> dict:
        with Image.open(path) as im:
            image = im.convert("RGB")
        import time
        t = time.time()
        pred = rec([image])[0]
        blocks = [{"label": norm_label(b.label), "bbox": [round(float(v), 1) for v in b.bbox],
                   "html": b.html or "", "text": html_to_text(b.html or "")} for b in pred.blocks]
        row = {"blocks": blocks, "finish_reason": "unknown"}
        if time.time() - t > SLOW:
            row["status"] = "slow"
            row["warning"] = f"took over {SLOW} s; Surya may have repeated itself. Check this page."
        return row

    run_pages(a.job, "surya", backend, versions, todo, read)


if __name__ == "__main__":
    main()
