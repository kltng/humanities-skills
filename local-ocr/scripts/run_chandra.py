# /// script
# requires-python = ">=3.12,<3.13"
# dependencies = [
#   "chandra-ocr==0.2.0",
#   "mlx-vlm==0.7.11; sys_platform == 'darwin' and platform_machine == 'arm64'",
#   "chandra-ocr[hf]==0.2.0; sys_platform != 'darwin'",
# ]
# ///
"""Read a job's pages with Chandra OCR 2 (Datalab), the most accurate of the three models.

    uv run run_chandra.py JOB [--backend mlx|hf] [--limit N] [--pages 00012,00040] [--setup]
                          [--read-blank] [--max-tokens 12384]

Backends: mlx = 8-bit MLX build on Apple Silicon (5.2 GB, needs 16 GB memory);
hf = the full model with PyTorch on an NVIDIA GPU (10.6 GB, 16–24 GB of GPU memory).
Pages that look blank are skipped unless --read-blank, because Chandra invents text on them.
A page that hits the token limit is marked "loop": its text is not a reading. Resumable.
"""
from __future__ import annotations

import argparse
import platform
import shutil
import sys
from importlib.metadata import version
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import chandra_blocks, load_job, run_pages, runner_args, todo_pages  # noqa: E402

MLX_MODEL = "jwindle47/chandra-ocr-2-8bit-mlx"


def pick_backend(choice: str) -> str:
    if choice != "auto":
        return choice
    if platform.system() == "Darwin" and platform.machine() == "arm64":
        return "mlx"
    if shutil.which("nvidia-smi"):
        return "hf"
    raise SystemExit("Chandra needs Apple Silicon or an NVIDIA GPU. Use Surya or Indra on this machine, "
                     "or force --backend hf to try PyTorch on CPU (very slow).")


def main() -> None:
    sys.argv, extra = _split_extra(sys.argv)
    a = runner_args(__doc__, ["mlx", "hf"])
    backend = pick_backend(a.backend)
    data = load_job(a.job)
    redo = set(a.pages.split(",")) if a.pages else None
    todo = todo_pages(a.job, data, a.limit, redo, skip_blank=not extra.read_blank)
    if not todo and not a.setup:
        print("Nothing to read: every page has a row. Use --pages to read pages again.")
        return

    from chandra.model.util import scale_to_fit
    from chandra.prompts import PROMPT_MAPPING
    from chandra.settings import settings
    from PIL import Image

    max_tokens = extra.max_tokens or settings.MAX_OUTPUT_TOKENS
    versions = {"chandra-ocr": version("chandra-ocr")}

    if backend == "mlx":
        from mlx_vlm import generate, load
        from mlx_vlm.prompt_utils import apply_chat_template

        print(f"Loading {MLX_MODEL} (first use downloads about 5.2 GB) …", flush=True)
        model, processor = load(MLX_MODEL)
        prompt = apply_chat_template(processor, model.config, PROMPT_MAPPING["ocr_layout"], num_images=1)
        versions["mlx-vlm"] = version("mlx-vlm")
        versions["weights"] = MLX_MODEL

        def generate_raw(image):
            res = generate(model, processor, prompt, [scale_to_fit(image)], max_tokens=max_tokens,
                           temperature=0.0, eos_tokens=["<|im_end|>"], verbose=False)
            return res.text, res.generation_tokens
    else:
        from chandra.model import InferenceManager
        from chandra.model.schema import BatchInputItem

        print(f"Loading {settings.MODEL_CHECKPOINT} with PyTorch (first use downloads about 10.6 GB) …", flush=True)
        manager = InferenceManager(method="hf")
        versions["torch"] = version("torch")
        versions["weights"] = settings.MODEL_CHECKPOINT

        def generate_raw(image):
            out = manager.generate([BatchInputItem(image=image, prompt_type="ocr_layout")],
                                   max_output_tokens=max_tokens)[0]
            if out.error:
                raise RuntimeError("Chandra returned an error for this page")
            return out.raw, out.token_count

    if a.setup:
        print(f"Chandra OCR 2 is ready (backend {backend}).")
        return

    def read(path: Path, page: dict) -> dict:
        with Image.open(path) as im:
            image = im.convert("RGB")
        raw, tokens = generate_raw(image)
        looped = tokens >= max_tokens
        row = {"raw": raw, "tokens": tokens, "finish_reason": "length" if looped else "stop",
               "blocks": chandra_blocks(raw, image.width, image.height)}
        if looped:
            row["status"] = "loop"
            row["warning"] = "hit the token limit (the model repeated itself); do not treat this page as read"
        return row

    run_pages(a.job, "chandra", backend, versions, todo, read)


def _split_extra(argv: list[str]) -> tuple[list[str], argparse.Namespace]:
    """Options only this runner has; the rest go to the shared runner_args()."""
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("--read-blank", action="store_true")
    ap.add_argument("--max-tokens", type=int)
    extra, rest = ap.parse_known_args(argv[1:])
    return [argv[0], *rest], extra


if __name__ == "__main__":
    main()
