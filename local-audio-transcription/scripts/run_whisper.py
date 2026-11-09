# /// script
# requires-python = ">=3.10,<3.14"
# dependencies = [
#   "mlx-whisper==0.4.3; sys_platform == 'darwin' and platform_machine == 'arm64'",
#   "faster-whisper==1.2.1; sys_platform != 'darwin' or platform_machine != 'arm64'",
#   "av>=11,<16; sys_platform != 'darwin' or platform_machine != 'arm64'",
#   "numpy",
# ]
# ///
"""Transcribe a job's chunks with OpenAI Whisper large-v3-turbo (99 languages, timestamps).

    uv run run_whisper.py JOB [--backend mlx|ct2] [--limit N] [--chunks 00012,00040] [--setup]
                          [--language zh] [--words] [--model-repo REPO]

Backends: mlx = mlx-whisper on Apple Silicon (mlx-community/whisper-large-v3-turbo, 1.6 GB);
ct2 = faster-whisper (CTranslate2) on an NVIDIA GPU (float16) or on CPU (int8, slow).
Segments come with start/end times; --words adds word times. Resumable.
"""
from __future__ import annotations

import argparse
import platform
import shutil
import sys
from importlib.metadata import version
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import norm_lang, run_chunks, runner_args, runner_start  # noqa: E402

MLX_REPO = "mlx-community/whisper-large-v3-turbo"
CT2_REPO = "large-v3-turbo"  # alias for mobiuslabsgmbh/faster-whisper-large-v3-turbo

WHISPER_LANG = {"yue": "yue", "zh": "zh"}  # Whisper has its own code for Cantonese


def pick_backend(choice: str) -> str:
    if choice != "auto":
        return choice
    if platform.system() == "Darwin" and platform.machine() == "arm64":
        return "mlx"
    return "ct2"


def main() -> None:
    sys.argv, extra = _split_extra(sys.argv)
    a = runner_args(__doc__, ["mlx", "ct2"])
    backend = pick_backend(a.backend)
    data, todo, language = runner_start(a)
    lang = norm_lang(language)
    if not todo and not a.setup:
        print("Nothing to do: every chunk has a row. Use --chunks to do chunks again.")
        return

    if backend == "mlx":
        import mlx_whisper
        repo = extra.model_repo or MLX_REPO
        versions = {"mlx-whisper": version("mlx-whisper"), "weights": repo}
        print(f"Loading {repo} (first use downloads about 1.6 GB) …", flush=True)
        mlx_whisper.transcribe(_silence_path(), path_or_hf_repo=repo, verbose=None)  # loads (and downloads) the model

        def transcribe(path: Path, chunk: dict) -> dict:
            r = mlx_whisper.transcribe(str(path), path_or_hf_repo=repo, language=lang, word_timestamps=extra.words,
                                       verbose=None)
            return {"language": r.get("language"), "segments": [_seg(s, extra.words) for s in r["segments"]]}
    else:
        from faster_whisper import WhisperModel
        repo = extra.model_repo or CT2_REPO
        if shutil.which("nvidia-smi"):
            device, compute = "cuda", "float16"
        else:
            device, compute = "cpu", "int8"
        versions = {"faster-whisper": version("faster-whisper"), "weights": repo, "device": device, "compute": compute}
        print(f"Loading {repo} on {device} ({compute}; first use downloads about 1.6 GB) …", flush=True)
        model = WhisperModel(repo, device=device, compute_type=compute)

        from _wav import read_piece

        def transcribe(path: Path, chunk: dict) -> dict:
            segments, info = model.transcribe(read_piece(path), language=lang, vad_filter=True,
                                              word_timestamps=extra.words)
            segs = [_seg({"start": s.start, "end": s.end, "text": s.text, "avg_logprob": s.avg_logprob,
                          "no_speech_prob": s.no_speech_prob, "compression_ratio": s.compression_ratio,
                          "words": [{"start": w.start, "end": w.end, "text": w.word} for w in (s.words or [])]},
                         extra.words) for s in segments]
            return {"language": info.language, "language_prob": round(info.language_probability, 3), "segments": segs}

    if a.setup:
        print(f"Whisper is ready (backend {backend}).")
        return
    run_chunks(a.job, "whisper", backend, versions, todo, transcribe)


def _seg(s: dict, words: bool) -> dict:
    out = {"start": s["start"], "end": s["end"], "text": s["text"],
           "logprob": round(s.get("avg_logprob", 0) or 0, 3), "no_speech": round(s.get("no_speech_prob", 0) or 0, 3),
           "compression": round(s.get("compression_ratio", 0) or 0, 2)}
    if words and s.get("words"):
        out["words"] = [{"start": w["start"], "end": w["end"], "text": (w.get("text") or w.get("word") or "").strip()}
                        for w in s["words"]]
    return out


def _silence_path() -> str:
    """A one-second silent WAV, to make the model load before the first real chunk."""
    import tempfile
    import wave
    p = Path(tempfile.gettempdir()) / "local-asr-silence.wav"
    if not p.exists():
        with wave.open(str(p), "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000); w.writeframes(b"\0" * 32000)
    return str(p)


def _split_extra(argv: list[str]) -> tuple[list[str], argparse.Namespace]:
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("--words", action="store_true")
    ap.add_argument("--model-repo")
    extra, rest = ap.parse_known_args(argv[1:])
    return [argv[0], *rest], extra


if __name__ == "__main__":
    main()
