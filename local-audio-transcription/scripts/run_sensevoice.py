# /// script
# requires-python = ">=3.10,<3.14"
# dependencies = ["sherpa-onnx==2.0.1", "numpy"]
# ///
"""Transcribe a job's chunks with SenseVoice-Small (Chinese, Cantonese, Japanese, Korean, English; tiny, CPU).

    uv run run_sensevoice.py JOB [--limit N] [--chunks 00012,00040] [--setup] [--language zh]
                             [--piece-seconds 30] [--threads N]

Runs with sherpa-onnx on the CPU of any computer (230 MB model, int8). The model gives no timestamps,
so each chunk is cut at its silences into pieces of at most --piece-seconds, and each piece becomes
one timed segment. Set --language ja for Japanese; auto-detection leans to Chinese. Resumable.
"""
from __future__ import annotations

import argparse
import os
import sys
from importlib.metadata import version
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import MODELS_DIR, SHERPA, download, norm_lang, pieces, run_chunks, runner_args, runner_start  # noqa: E402

MODEL = "sherpa-onnx-sense-voice-zh-en-ja-ko-yue-int8-2025-09-09"
URL = f"{SHERPA}/asr-models/{MODEL}.tar.bz2"
LANGS = {"zh": "zh", "yue": "yue", "en": "en", "ja": "ja", "ko": "ko"}


def main() -> None:
    sys.argv, extra = _split_extra(sys.argv)
    a = runner_args(__doc__, ["onnx"])
    data, todo, language = runner_start(a)
    code = norm_lang(language)
    lang = LANGS.get(code or "", "auto")
    if code and lang == "auto":
        print(f"note: SenseVoice does not know '{language}'; it reads Chinese, Cantonese, Japanese, Korean and "
              "English. Using auto-detection.", file=sys.stderr)
    if not todo and not a.setup:
        print("Nothing to do: every chunk has a row. Use --chunks to do chunks again.")
        return

    import numpy as np
    import sherpa_onnx
    from _wav import read_piece

    folder = download(URL, MODELS_DIR)
    threads = extra.threads or max(1, min(8, (os.cpu_count() or 2) - 1))
    rec = sherpa_onnx.OfflineRecognizer.from_sense_voice(model=str(folder / "model.int8.onnx"),
                                                         tokens=str(folder / "tokens.txt"), num_threads=threads,
                                                         use_itn=True, language=lang)
    versions = {"sherpa-onnx": version("sherpa-onnx"), "weights": MODEL, "threads": str(threads)}
    if a.setup:
        print("SenseVoice is ready (backend onnx).")
        return

    def transcribe(path: Path, chunk: dict) -> dict:
        segs, langs = [], {}
        for start, end in pieces(chunk, extra.piece_seconds):
            samples = read_piece(path, start, end)
            if not np.any(samples):
                continue
            st = rec.create_stream()
            st.accept_waveform(16000, samples)
            rec.decode_stream(st)
            r = st.result
            text = (r.text or "").strip()
            if text:
                seg = {"start": start, "end": end, "text": text, "language": r.lang or None}
                if getattr(r, "emotion", None):
                    seg["emotion"] = r.emotion
                if getattr(r, "event", None):
                    seg["event"] = r.event
                segs.append(seg)
                langs[r.lang] = langs.get(r.lang, 0) + 1
        top = max(langs, key=langs.get) if langs else None
        return {"language": code if lang != "auto" else top, "segments": segs}

    run_chunks(a.job, "sensevoice", "onnx", versions, todo, transcribe)


def _split_extra(argv: list[str]) -> tuple[list[str], argparse.Namespace]:
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("--piece-seconds", type=float, default=30.0)
    ap.add_argument("--threads", type=int)
    extra, rest = ap.parse_known_args(argv[1:])
    return [argv[0], *rest], extra


if __name__ == "__main__":
    main()
