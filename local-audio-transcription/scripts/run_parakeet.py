# /// script
# requires-python = ">=3.10,<3.14"
# dependencies = [
#   "parakeet-mlx==0.7.0; sys_platform == 'darwin' and platform_machine == 'arm64'",
#   "sherpa-onnx==2.0.1",
#   "numpy",
# ]
# ///
"""Transcribe a job's chunks with NVIDIA Parakeet TDT 0.6B v3 (25 European languages, very fast).

    uv run run_parakeet.py JOB [--backend mlx|onnx] [--limit N] [--chunks 00012,00040] [--setup]
                           [--piece-seconds 30] [--threads N]

Backends: mlx = parakeet-mlx on Apple Silicon (mlx-community/parakeet-tdt-0.6b-v3, 2.5 GB, sentence
timestamps); onnx = sherpa-onnx int8 model on the CPU of any computer (0.65 GB; chunks are cut at
silences into pieces, each piece one timed segment). The model detects the language itself; it does not
read Chinese, Japanese or Korean. Resumable.
"""
from __future__ import annotations

import argparse
import os
import platform
import sys
from importlib.metadata import version
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import MODELS_DIR, SHERPA, download, pieces, run_chunks, runner_args, runner_start  # noqa: E402

MLX_REPO = "mlx-community/parakeet-tdt-0.6b-v3"
ONNX_MODEL = "sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8"
ONNX_URL = f"{SHERPA}/asr-models/{ONNX_MODEL}.tar.bz2"


def pick_backend(choice: str) -> str:
    if choice != "auto":
        return choice
    if platform.system() == "Darwin" and platform.machine() == "arm64":
        return "mlx"
    return "onnx"


def main() -> None:
    sys.argv, extra = _split_extra(sys.argv)
    a = runner_args(__doc__, ["mlx", "onnx"])
    backend = pick_backend(a.backend)
    data, todo, language = runner_start(a)
    if not todo and not a.setup:
        print("Nothing to do: every chunk has a row. Use --chunks to do chunks again.")
        return

    if backend == "mlx":
        from parakeet_mlx import from_pretrained
        print(f"Loading {MLX_REPO} (downloads about 2.5 GB if it is not on this machine yet) …", flush=True)
        model = from_pretrained(MLX_REPO)
        versions = {"parakeet-mlx": version("parakeet-mlx"), "weights": MLX_REPO}

        def transcribe(path: Path, chunk: dict) -> dict:
            r = model.transcribe(str(path), chunk_duration=120.0, overlap_duration=15.0)
            segs = [{"start": round(s.start, 2), "end": round(s.end, 2), "text": s.text,
                     "words": [{"start": round(t.start, 2), "end": round(t.end, 2), "text": t.text.strip()}
                               for t in s.tokens]} for s in r.sentences]
            return {"language": None, "segments": segs}
    else:
        import numpy as np
        import sherpa_onnx
        from _wav import read_piece
        folder = download(ONNX_URL, MODELS_DIR)
        threads = extra.threads or max(1, min(8, (os.cpu_count() or 2) - 1))
        rec = sherpa_onnx.OfflineRecognizer.from_transducer(
            encoder=str(folder / "encoder.int8.onnx"), decoder=str(folder / "decoder.int8.onnx"),
            joiner=str(folder / "joiner.int8.onnx"), tokens=str(folder / "tokens.txt"),
            model_type="nemo_transducer", num_threads=threads)
        versions = {"sherpa-onnx": version("sherpa-onnx"), "weights": ONNX_MODEL, "threads": str(threads)}

        def transcribe(path: Path, chunk: dict) -> dict:
            segs = []
            for start, end in pieces(chunk, extra.piece_seconds):
                samples = read_piece(path, start, end)
                if not np.any(samples):
                    continue
                st = rec.create_stream()
                st.accept_waveform(16000, samples)
                rec.decode_stream(st)
                text = (st.result.text or "").strip()
                if text:
                    segs.append({"start": start, "end": end, "text": text})
            return {"language": None, "segments": segs}

    if a.setup:
        print(f"Parakeet is ready (backend {backend}).")
        return
    run_chunks(a.job, "parakeet", backend, versions, todo, transcribe)


def _split_extra(argv: list[str]) -> tuple[list[str], argparse.Namespace]:
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("--piece-seconds", type=float, default=30.0)
    ap.add_argument("--threads", type=int)
    extra, rest = ap.parse_known_args(argv[1:])
    return [argv[0], *rest], extra


if __name__ == "__main__":
    main()
