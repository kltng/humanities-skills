# /// script
# requires-python = ">=3.10,<3.14"
# dependencies = [
#   "mlx-audio[stt]==0.6.5; sys_platform == 'darwin' and platform_machine == 'arm64'",
#   "qwen-asr==0.0.6; sys_platform != 'darwin' or platform_machine != 'arm64'",
#   "numpy",
# ]
# ///
"""Transcribe a job's chunks with Qwen3-ASR 1.7B (30 languages and 22 Chinese dialects, incl. Cantonese).

    uv run run_qwen3asr.py JOB [--backend mlx|hf] [--limit N] [--chunks 00012,00040] [--setup]
                           [--language yue] [--model-repo REPO] [--piece-seconds 30]

Backends: mlx = mlx-audio on Apple Silicon (mlx-community/Qwen3-ASR-1.7B-8bit, 2.5 GB);
hf = the qwen-asr package with PyTorch on an NVIDIA GPU (Qwen/Qwen3-ASR-1.7B, 4.7 GB) or on CPU (slow).
The model gives no timestamps, so each chunk is cut at its silences into pieces of at most
--piece-seconds, and each piece becomes one timed segment. Resumable.
"""
from __future__ import annotations

import argparse
import platform
import shutil
import sys
from importlib.metadata import version
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import norm_lang, pieces, run_chunks, runner_args, runner_start  # noqa: E402

MLX_REPO = "mlx-community/Qwen3-ASR-1.7B-8bit"
HF_REPO = "Qwen/Qwen3-ASR-1.7B"
# Qwen3-ASR wants language names.
NAMES = {"zh": "Chinese", "yue": "Cantonese", "en": "English", "ja": "Japanese", "ko": "Korean", "de": "German",
         "fr": "French", "es": "Spanish", "pt": "Portuguese", "it": "Italian", "ru": "Russian", "ar": "Arabic",
         "vi": "Vietnamese", "th": "Thai", "id": "Indonesian", "ms": "Malay", "nl": "Dutch", "hi": "Hindi",
         "tr": "Turkish", "pl": "Polish", "sv": "Swedish", "da": "Danish", "fi": "Finnish", "cs": "Czech",
         "fil": "Filipino", "fa": "Persian", "el": "Greek", "hu": "Hungarian", "mk": "Macedonian", "ro": "Romanian"}
CODES = {v.lower(): k for k, v in NAMES.items()}


def pick_backend(choice: str) -> str:
    if choice != "auto":
        return choice
    if platform.system() == "Darwin" and platform.machine() == "arm64":
        return "mlx"
    return "hf"


def main() -> None:
    sys.argv, extra = _split_extra(sys.argv)
    a = runner_args(__doc__, ["mlx", "hf"])
    backend = pick_backend(a.backend)
    data, todo, language = runner_start(a)
    code = norm_lang(language)
    name = NAMES.get(code, language.title() if language else None) if code else None
    if not todo and not a.setup:
        print("Nothing to do: every chunk has a row. Use --chunks to do chunks again.")
        return

    import numpy as np
    from _wav import read_piece

    if backend == "mlx":
        from mlx_audio.stt.utils import load_model
        repo = extra.model_repo or MLX_REPO
        versions = {"mlx-audio": version("mlx-audio"), "weights": repo}
        print(f"Loading {repo} (downloads about 2.5 GB if it is not on this machine yet) …", flush=True)
        model = load_model(repo)

        def run_piece(samples: np.ndarray) -> tuple[str, str | None]:
            r = model.generate(samples, language=name)
            lang = r.language[0] if isinstance(r.language, list) and r.language else r.language
            return r.text, lang
    else:
        import torch
        from qwen_asr import Qwen3ASRModel
        repo = extra.model_repo or HF_REPO
        if shutil.which("nvidia-smi") and torch.cuda.is_available():
            device, dtype = "cuda:0", torch.bfloat16
        else:
            device, dtype = "cpu", torch.float32
        versions = {"qwen-asr": version("qwen-asr"), "torch": version("torch"), "weights": repo, "device": device}
        print(f"Loading {repo} on {device} (downloads about 4.7 GB if it is not on this machine yet) …", flush=True)
        model = Qwen3ASRModel.from_pretrained(repo, dtype=dtype, device_map=device, max_inference_batch_size=4,
                                              max_new_tokens=1024)

        def run_piece(samples: np.ndarray) -> tuple[str, str | None]:
            r = model.transcribe(audio=[(samples, 16000)], language=name)[0]
            return r.text, r.language

    if a.setup:
        print(f"Qwen3-ASR is ready (backend {backend}).")
        return

    def transcribe(path: Path, chunk: dict) -> dict:
        segs, langs = [], {}
        for start, end in pieces(chunk, extra.piece_seconds):
            samples = read_piece(path, start, end)
            if not np.any(samples):
                continue
            text, lang = run_piece(samples)
            text = (text or "").strip()
            if text:
                segs.append({"start": start, "end": end, "text": text, "language": lang})
                langs[lang] = langs.get(lang, 0) + 1
        top = max(langs, key=langs.get) if langs else None
        return {"language": CODES.get((top or "").lower(), top), "segments": segs}

    run_chunks(a.job, "qwen3-asr", backend, versions, todo, transcribe)


def _split_extra(argv: list[str]) -> tuple[list[str], argparse.Namespace]:
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("--model-repo")
    ap.add_argument("--piece-seconds", type=float, default=30.0)
    extra, rest = ap.parse_known_args(argv[1:])
    return [argv[0], *rest], extra


if __name__ == "__main__":
    main()
