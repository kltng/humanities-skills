# local-audio-transcription: scripts, files and formats

Run every script with `uv run`. `doctor.py`, `prepare.py`, `jobs.py`, `export.py`, `report.py` and
`offline.py` use only the standard library (`prepare.py` needs the `ffmpeg` program). Each `run_*.py`
and `diarize.py` declares its packages inline (PEP 723), so `uv` installs them on first use.

Environment variables:

| Variable | Meaning | Default |
|---|---|---|
| `LOCAL_ASR_HOME` | where the job list and the sherpa-onnx models are kept | `~/.cache/local-audio-transcription` |
| `HF_HUB_CACHE` / `HF_HOME` | the Hugging Face model cache (Whisper, Qwen3-ASR, Parakeet MLX) | `~/.cache/huggingface/hub` |
| `LOCAL_ASR_OFFLINE=1` | turn on the network guard in any script (set by offline jobs themselves) | off |

## Scripts

### doctor.py

`uv run doctor.py [--json]`

Reports the machine, tools (`uv`, `ffmpeg`, `ffprobe`, `nvidia-smi`, `gh`), free disk, a verdict per model
(`good`, `slow` or `no`) with its backend, whether the model files are already downloaded (and the download
size if not), whether the helper models for diarization are there, and the jobs on this machine with their
progress. `--json` gives `{machine, tools, disk, recommendation, helpers, jobs}`.

### prepare.py

`uv run prepare.py SOURCE... --job JOB --model whisper|qwen3-asr|sensevoice|parakeet [options]`

| Option | Meaning |
|---|---|
| `--name` | job name (default: the folder name) |
| `--language zh` | the language spoken (code or name: zh, yue, en, ja, ko, de …); leave out to detect |
| `--formats txt,srt,json` | export formats stored in the job (txt, md, srt, vtt, json, jsonl, tei, csv) |
| `--chunk-minutes 10` | target chunk length; the cut is at the longest silence between 60% and 100% of it |
| `--offline` | strict offline job: every run blocks all network connections |
| `--diarize` | plan speaker labels (the offline script then runs `diarize.py`) |
| `--sample` | this job holds the user's sample clip (a test job) |
| `--brief brief.json` | interview answers, stored in `job.json` |
| `--noise-db -35`, `--min-silence 0.5` | what counts as silence for ffmpeg's `silencedetect` |

Sources: audio (wav, mp3, m4a, aac, flac, ogg, opus, wma, aiff, amr …) or video (mp4, mov, mkv, webm, avi …)
files, or folders of them (searched recursively). Each file is one recording. ffmpeg converts it to
16 kHz mono 16-bit WAV, the silences are found, and the WAV is cut into `JOB/chunks/NNNNN.wav`.

### run_whisper.py / run_qwen3asr.py / run_sensevoice.py / run_parakeet.py

`uv run run_<model>.py JOB [--backend B] [--limit N] [--chunks ID,ID] [--setup] [--language L]`

| Option | Meaning |
|---|---|
| `--backend` | whisper: `mlx`, `ct2`; qwen3-asr: `mlx`, `hf`; sensevoice: `onnx`; parakeet: `mlx`, `onnx`. Default `auto` (MLX on Apple Silicon, else the other). |
| `--limit N` | transcribe at most N chunks not done yet (smoke test) |
| `--chunks` | do these chunk ids again, even if done |
| `--setup` | install, download and load the model, then stop (network allowed, also in offline jobs) |
| `--language` | force the language; default: the job's language, else detect |
| `--words` | (whisper) word timestamps |
| `--model-repo` | (whisper, qwen3-asr) another Hugging Face repo, e.g. `mlx-community/Qwen3-ASR-0.6B-8bit` |
| `--piece-seconds 30` | (qwen3-asr, sensevoice, parakeet-onnx) longest piece between silences = one segment |
| `--threads N` | (sensevoice, parakeet-onnx) CPU threads (default: cores − 1, at most 8) |

The runners are resumable. A row is written after each chunk; a half-written last line is cut on the next
start; chunks with an error row are done again. Each run is logged in `job.json` → `runs` (model, backend,
package versions, machine, offline flag, start, end, outcome). In an offline job (or with
`LOCAL_ASR_OFFLINE=1`) the runner installs the network guard before importing the model library: every
`socket.connect` to a non-local address raises `OSError`, and the Hugging Face offline variables are set.

To use the `ct2` backend on a Mac (not the default): `uv run --with "faster-whisper==1.2.1" --with "av<16" --with numpy python run_whisper.py JOB --backend ct2`.

### diarize.py

`uv run diarize.py JOB [--speakers N] [--threshold 0.5] [--docs rec1,rec2] [--threads N] [--redo] [--setup]`

Writes `JOB/speakers.jsonl`: one line per recording, `{doc, speakers, turns: [{start, end, speaker}], seconds}`.
Speakers are numbered from 0 per recording; exports show them as "Speaker 1", "Speaker 2" …

### export.py

`uv run export.py JOB [--formats txt,srt] [--no-timestamps] [--max-gap 1.0]`

### jobs.py

`uv run jobs.py list | status JOB | note JOB "text" | forget JOB`

### report.py

`uv run report.py JOB [--describe "..."] [--share-titles]` writes `JOB/report.md` and `JOB/field-report.md`.
Neither contains transcript text.

### offline.py

`uv run offline.py check SAMPLE_JOB` runs, in `SAMPLE_JOB/offline-check/`, with `LOCAL_ASR_OFFLINE=1` and
`uv run --offline`: the guard self-test (a connection through it must fail), ffmpeg, prepare, the model,
diarization if planned, export, report. Prints PASS/FAIL per step; exit code 1 if any failed.

`uv run offline.py script SAMPLE_JOB --job REAL_JOB [--speakers N]` writes `REAL_JOB/transcribe-offline.sh`
(bash) and `REAL_JOB/transcribe-offline.ps1` (PowerShell). Both take the recordings (files or folders) as
arguments, refuse to start while `https://huggingface.co` is reachable (skip with
`LOCAL_ASR_SKIP_NETCHECK=1`), then run prepare, the model, diarization, export and report with the same
settings as the sample job. Running the script again continues a stopped job.

## The job folder

```
JOB/
  job.json              settings, brief, sources, chunks, runs, notes
  chunks/00001.wav      16 kHz mono pieces of the recordings (numbered across all recordings)
  rows.jsonl            one line per chunk transcribed; the last line for a chunk wins
  speakers.jsonl        one line per recording with speaker turns (diarize.py)
  run.log               the runner's output, if you redirect it there
  export/<format>/      exports
  report.md, field-report.md
  transcribe-offline.sh, transcribe-offline.ps1   (offline jobs)
  offline-check/        (sample jobs) the job made by offline.py check
```

`job.json` → `chunks[]`: `{id, doc, index, file, start, end, duration, speech_share, silences, language}`.
`start`/`end` are seconds in the recording; `silences` are `[start, end]` pairs relative to the chunk;
`speech_share` is the part of the chunk that is not silence (0-1).

`rows.jsonl`, one line per chunk:

```json
{"chunk": "00012", "doc": "interview1", "model": "whisper", "backend": "mlx", "seconds": 25.9,
 "status": "ok", "language": "zh", "text": "今天下午…",
 "segments": [{"start": 126.38, "end": 138.76, "text": "今天下午，…", "logprob": -0.07, "no_speech": 0.0,
               "compression": 1.04, "words": [{"start": 126.4, "end": 126.7, "text": "今天"}]}],
 "flag": "uncertain", "warning": "1 segment(s) with very low confidence …"}
```

- `status`: `ok` or `error` (`error` carries the message; the chunk is done again on the next run).
- `flag` (one per chunk, the most serious): `repeat`, `no_speech`, `empty`, `slow`, `uncertain`, `language`.
- Segment times are seconds in the recording (chunk offset already added). `logprob`, `no_speech`,
  `compression` are Whisper only; `language`, `emotion`, `event` are Qwen3-ASR/SenseVoice; `words` with
  `--words` (Whisper) or always (Parakeet MLX).

## Export formats

| Format | Files | Notes |
|---|---|---|
| `txt` | `export/txt/<rec>.txt` | paragraphs (new one at a speaker change, a pause over `--max-gap`, or 1,200 chars); `[m:ss]` at the start of each, `Speaker N:` when known |
| `md` | `export/md/<rec>.md` | the same with a heading and bold times/speakers |
| `srt` | `export/srt/<rec>.srt` | one cue per segment; long segments with word times are split at about 6 s / 70 chars; `Speaker N:` prefix |
| `vtt` | `export/vtt/<rec>.vtt` | WebVTT with `<v Speaker N>` voice tags |
| `json` | `export/json/<rec>.json` | `{recording, source, duration, job, model, language, speakers, flags, segments[]}` |
| `jsonl` | `export/jsonl/<job>.jsonl` | one line per segment: `{recording, start, end, text, speaker?, …}` |
| `csv` | `export/csv/<job>.csv` | `recording, start, end, speaker, language, text` |
| `tei` | `export/tei/<rec>.xml` | TEI P5 transcribed speech: `<recordingStmt>`, `<particDesc>` with one `<person>` per speaker, a `<timeline>`, and one `<u who start end>` per paragraph |

Chunks with status `error` or not done yet are left out and listed when `export.py` finishes.
