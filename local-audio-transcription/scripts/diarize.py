# /// script
# requires-python = ">=3.10,<3.14"
# dependencies = ["sherpa-onnx==2.0.1", "numpy"]
# ///
"""Find who speaks when (speaker diarization) for each recording of a job. CPU, any computer.

    uv run diarize.py JOB [--speakers N] [--threshold 0.5] [--docs rec1,rec2] [--threads N] [--setup]

Uses sherpa-onnx with the pyannote segmentation 3.0 model and a 3D-Speaker embedding model (about
50 MB together, downloaded once from the sherpa-onnx GitHub releases; no account or token needed).
Writes JOB/speakers.jsonl, one line per recording: {"doc", "turns": [{"start", "end", "speaker"}]}.
export.py then labels every segment with its speaker. Slow: about 1-2x real time on a laptop CPU.
--speakers N helps a lot when the number of speakers is known (an interview: 2).
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from importlib.metadata import version
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (MODELS_DIR, SHERPA, append_row, download, fmt_time, load_job, network_guard,  # noqa: E402
                     offline_requested, read_speakers)
from _wav import read_piece  # noqa: E402

SEG_URL = f"{SHERPA}/speaker-segmentation-models/sherpa-onnx-pyannote-segmentation-3-0.tar.bz2"
EMB_URL = f"{SHERPA}/speaker-recongition-models/3dspeaker_speech_eres2net_base_sv_zh-cn_3dspeaker_16k.onnx"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("job", type=Path)
    ap.add_argument("--speakers", type=int, default=-1, help="number of speakers if known (default: find out)")
    ap.add_argument("--threshold", type=float, default=0.5, help="clustering threshold when the number is unknown; "
                    "smaller = more speakers")
    ap.add_argument("--docs", help="only these recordings (comma list); default: all not yet done")
    ap.add_argument("--threads", type=int)
    ap.add_argument("--redo", action="store_true", help="do recordings again even if speakers.jsonl has them")
    ap.add_argument("--setup", action="store_true", help="download the models, then stop")
    a = ap.parse_args()

    data = load_job(a.job)
    if offline_requested(data) and not a.setup:
        network_guard()
        print("offline mode: every network connection is blocked for this run", flush=True)
    seg_dir = download(SEG_URL, MODELS_DIR)
    emb = download(EMB_URL, MODELS_DIR)
    if a.setup:
        print("Speaker diarization models are ready.")
        return

    import sherpa_onnx
    threads = a.threads or max(1, min(8, (os.cpu_count() or 2) - 1))
    cfg = sherpa_onnx.OfflineSpeakerDiarizationConfig(
        segmentation=sherpa_onnx.OfflineSpeakerSegmentationModelConfig(
            pyannote=sherpa_onnx.OfflineSpeakerSegmentationPyannoteModelConfig(model=str(seg_dir / "model.onnx")),
            num_threads=threads),
        embedding=sherpa_onnx.SpeakerEmbeddingExtractorConfig(model=str(emb), num_threads=threads),
        clustering=sherpa_onnx.FastClusteringConfig(num_clusters=a.speakers, threshold=a.threshold),
        min_duration_on=0.3, min_duration_off=0.5)
    sd = sherpa_onnx.OfflineSpeakerDiarization(cfg)

    done = read_speakers(a.job)
    want = set(a.docs.split(",")) if a.docs else None
    for src in data["sources"]:
        doc = src["doc"]
        if (want and doc not in want) or (doc in done and not a.redo and not want):
            continue
        chunks = [c for c in data["chunks"] if c["doc"] == doc]
        if not chunks:
            continue
        t = time.time()
        audio = np.concatenate([read_piece(a.job / c["file"]) for c in chunks])
        offset = chunks[0]["start"]
        res = sd.process(audio).sort_by_start_time()
        turns = [{"start": round(r.start + offset, 2), "end": round(r.end + offset, 2), "speaker": int(r.speaker)}
                 for r in res]
        n = len({tr["speaker"] for tr in turns})
        row = {"doc": doc, "turns": turns, "speakers": n, "seconds": round(time.time() - t, 1),
               "settings": {"num_speakers": a.speakers, "threshold": a.threshold},
               "versions": {"sherpa-onnx": version("sherpa-onnx")}}
        append_row(a.job, row, "speakers.jsonl")
        print(f"{doc}: {n} speaker(s), {len(turns)} turns, {fmt_time(src.get('duration', 0))} of audio in "
              f"{row['seconds']} s", flush=True)
    print("DONE. Run export.py again to put the speaker labels into the files.")


if __name__ == "__main__":
    main()
