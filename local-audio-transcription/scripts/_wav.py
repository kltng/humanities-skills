"""Read pieces of a 16 kHz mono WAV as float32 numpy arrays (for runners that take arrays)."""
from __future__ import annotations

import wave
from pathlib import Path

import numpy as np


def read_piece(path: Path, start: float | None = None, end: float | None = None) -> np.ndarray:
    with wave.open(str(path)) as w:
        rate = w.getframerate()
        if w.getsampwidth() != 2 or w.getnchannels() != 1:
            raise ValueError(f"{path} is not 16-bit mono (run prepare.py)")
        a = int((start or 0) * rate)
        b = w.getnframes() if end is None else min(w.getnframes(), int(end * rate))
        w.setpos(a)
        raw = w.readframes(max(0, b - a))
    return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
