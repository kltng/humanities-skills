# The four models

All four are open models that run on the user's own computer. Nothing is sent anywhere. Each is
downloaded once; after that the scripts work without the internet.

## Hardware and downloads

| | Whisper large-v3-turbo | Qwen3-ASR 1.7B | SenseVoice-Small | Parakeet TDT 0.6B v3 |
|---|---|---|---|---|
| Maker, licence | OpenAI, MIT | Alibaba Qwen, Apache 2.0 | Alibaba FunAudioLLM, model licence (research and commercial use allowed, see the repo) | NVIDIA, CC-BY-4.0 |
| Languages | 99 (one language per recording) | 30 languages + 22 Chinese dialects: Mandarin, Cantonese, Wu, Minnan, Sichuan … Mixed languages in one recording are fine | Chinese, Cantonese, Japanese, Korean, English | 25 European languages (English, German, French, Spanish, Italian, Portuguese, Dutch, Polish, Russian, Ukrainian …). Not Chinese, Japanese or Korean |
| Timestamps | per segment; `--words` per word | none from the model; the runner cuts each chunk at its silences into pieces of ≤30 s, one segment each | same as Qwen3-ASR | per sentence and per word (MLX); per piece (ONNX) |
| Apple Silicon | `mlx` (mlx-whisper), 1.6 GB, 8 GB memory | `mlx` (mlx-audio), 8-bit, 2.5 GB, 16 GB memory (8 GB with `--model-repo mlx-community/Qwen3-ASR-0.6B-8bit`, 1 GB) | `onnx` (sherpa-onnx, CPU), 0.25 GB | `mlx` (parakeet-mlx), 2.5 GB |
| NVIDIA GPU | `ct2` (faster-whisper, float16), 1.6 GB, 4 GB GPU memory; needs CUDA 12 + cuDNN 9 libraries | `hf` (qwen-asr, PyTorch bf16), 4.7 GB, 8 GB GPU memory | `onnx` (CPU) | `onnx` (sherpa-onnx int8, CPU), 0.65 GB |
| CPU only | `ct2` int8, about 1-3x real time | `hf` on CPU, slower than real time | `onnx`, 20-50x real time | `onnx`, 10-30x real time |
| Python packages | `mlx-whisper==0.4.3` / `faster-whisper==1.2.1` + `av<16` | `mlx-audio[stt]==0.6.5` / `qwen-asr==0.0.6` | `sherpa-onnx==2.0.1` | `parakeet-mlx==0.7.0` / `sherpa-onnx==2.0.1` |

Hugging Face downloads go to `~/.cache/huggingface/hub` (or `$HF_HUB_CACHE`). The sherpa-onnx models
(SenseVoice, Parakeet ONNX, the two speaker-diarization models) go to `~/.cache/local-audio-transcription/models`
(or `$LOCAL_ASR_HOME/models`); they come from the sherpa-onnx GitHub releases, no account needed.

## Test results (2026-11-09, Apple M1 Max, 64 GB)

The test clips were made with the macOS speech synthesizer from an original interview-style text
(about 40 s each): English (Daniel), Mandarin (Tingting), Cantonese (Sinji), Japanese (Kyoko), plus a
8.5-minute file alternating the English and Mandarin voices with 4-second pauses. Synthetic voices are
cleaner than real recordings, so take the quality notes as a best case. Speed is "x real time"
(10x = a 10-minute recording takes 1 minute), measured by the runners on 2-3 minute chunks.

| Model (backend) | English | Mandarin | Cantonese | Japanese | Speed | Notes |
|---|---|---|---|---|---|---|
| Whisper turbo (mlx) | exact | exact, with punctuation | written as standard Chinese, 3-4 errors; not Cantonese wording | good (1 wrong character) | 12-25x; 6x on the mixed-language file | On the mixed English/Mandarin file it treated whole stretches as the wrong language and **invented text** (flagged `uncertain`). One language per recording. Known to invent captions on silence or music. |
| Whisper turbo (ct2, CPU int8) | exact, word times | exact | - | - | 1.7x | Same model on CPU. On an NVIDIA GPU expect 10-30x (not tested here). |
| Qwen3-ASR 1.7B (mlx, 8-bit) | exact | exact, with punctuation | **exact, in Cantonese wording** (我哋, 嘅, 咗) but simplified characters | good | 10-20x | The best choice for Chinese and Cantonese. No native timestamps: segments are the silence-cut pieces. Handled the mixed-language file correctly. |
| Qwen3-ASR 0.6B (hf, CPU, PyTorch) | - | - | exact, in Cantonese wording | - | 2.1x on 10 CPU cores | The same code path as the NVIDIA backend (`qwen-asr` package), run on CPU to test it; not run on a GPU here. The 1.7B model on CPU will be slower than real time. |
| SenseVoice-Small (onnx, CPU) | all upper case, no punctuation, a few misspellings | exact, no punctuation | Cantonese wording, simplified characters, 1 error | **poor** (dropped the kana, Chinese characters only), even with `--language ja` | 40-80x | Tiny and fast. Best for Mandarin and Cantonese on a weak machine. Use `--language` always; auto-detection leans to Chinese. |
| Parakeet 0.6B v3 (mlx) | exact, with sentence and word times | garbage (romanized sounds) | garbage | garbage | 30-60x | European languages only. Very fast and accurate for English. |
| Parakeet 0.6B v3 (onnx, CPU) | exact | - | - | - | 25-35x | Same model, any computer. |

Speaker diarization (`diarize.py`, sherpa-onnx with pyannote segmentation 3.0 + 3D-Speaker embeddings,
CPU): on the 8.5-minute two-voice file it found exactly 2 speakers and 12 turns at the right times.
Speed: 4x real time with `--speakers 2` and 8 threads; 2x real time when it has to find the number of
speakers itself.

## Known quirks

- **Whisper and mixed languages.** Whisper decides the language once per 30-second window from the
  chunk's start. When a recording switches language, whole stretches can come out translated, garbled or
  invented. Use Qwen3-ASR for mixed-language recordings, or set `--language`.
- **Whisper on silence and music** invents captions ("Thanks for watching", "字幕志愿者" and the like).
  The runner flags chunks with very low confidence (`uncertain`), chunks that sound silent but got text
  (`no_speech`), and repeated text (`repeat`). Always listen to flagged chunks.
- **Qwen3-ASR and SenseVoice write simplified characters**, also for Cantonese and Taiwan Mandarin. Convert
  with OpenCC afterwards if traditional characters are wanted. Whisper follows the characters it detects
  (it wrote traditional characters for the Hong Kong voice).
- **Qwen3-ASR timestamps.** Each silence-cut piece is one segment (`--piece-seconds 30`). For word-level
  times, Qwen's forced aligner (Qwen3-ForcedAligner-0.6B) exists but is not wired in here.
- **SenseVoice** gives no punctuation in this build and adds emotion and event tags (laughter, applause,
  music) to each segment (`emotion`, `event` in the rows).
- **Parakeet** reads only European languages. Anything else comes out as romanized nonsense without
  warning, so never use it for Chinese, Japanese or Korean.
- **faster-whisper and PyAV.** faster-whisper 1.2.1 breaks with PyAV 16+ (`metadata_errors` error). The
  runner pins `av<16` and feeds samples directly, so decoding does not go through PyAV.
- **Diarization is CPU-bound and slow** on long recordings (a 2-hour interview takes 30-60 minutes).
  Give `--speakers N` when the number is known.
