---
name: local-audio-transcription
description: >-
  Transcribe audio or video recordings (interviews, oral history, lectures, fieldwork, meetings) into
  text on the user's own computer with open speech models: Whisper large-v3-turbo (99 languages),
  Qwen3-ASR (Chinese dialects incl. Cantonese, 30 languages), SenseVoice (tiny, CPU, Chinese/Japanese/
  Korean/English) and Parakeet (fast, European languages), plus optional speaker labels. Asks one
  question first: must the recording and transcript stay completely offline? If yes, it installs and
  tests everything on a sample clip the user provides, proves the pipeline runs with the network blocked,
  and then hands the user a script to run after disconnecting. Checks the hardware, picks the model,
  resumable runs, exports txt, Markdown, SRT, VTT, JSON, CSV and TEI, and ends with a report. Use when the
  user wants to transcribe, caption or subtitle a recording locally, asks which speech model their machine
  can run, mentions Whisper, Qwen3-ASR, SenseVoice, Parakeet or diarization, or needs transcription of
  confidential interviews that must not leave the computer.
version: 1.1.0
license: MIT
author: Kwok-leong Tang
contributors:
  - Claude (Anthropic)
---

# Local Audio Transcription (Whisper, Qwen3-ASR, SenseVoice, Parakeet)

## Overview

This skill turns recordings into text on the user's own machine. Nothing is sent to a cloud service,
except that each model is downloaded once. It uses four open models:

| Model | Size | Runs on | Speed | Best for |
|---|---|---|---|---|
| **Whisper large-v3-turbo** (OpenAI) | 1.6 GB | Apple Silicon (MLX), NVIDIA GPU, or CPU (slow) | 10-25x real time on a Mac; 1-3x on CPU | 99 languages, one language per recording; good timestamps; subtitles |
| **Qwen3-ASR 1.7B** (Alibaba) | 2.5 GB (8-bit MLX) / 4.7 GB | Apple Silicon 16 GB+, NVIDIA 8 GB+, or CPU (slow) | 10-20x on a Mac | **Chinese and Cantonese** (writes real Cantonese), 22 Chinese dialects, 30 languages, mixed languages in one recording |
| **SenseVoice-Small** (Alibaba) | 0.25 GB | any computer, CPU | 40-80x | Chinese, Cantonese, Korean, English on a weak machine; fast draft. Weak on Japanese |
| **Parakeet TDT 0.6B v3** (NVIDIA) | 2.5 GB (MLX) / 0.65 GB (ONNX) | Apple Silicon, or CPU | 30-60x | English and 24 other European languages, very fast and exact. **Not** Chinese, Japanese, Korean |

"10x real time" means a 60-minute recording takes 6 minutes. Optional **speaker labels** (who spoke when)
come from `diarize.py`, which runs on CPU on any computer (about 2-4x real time). Details and the test
results are in `references/models.md`.

Every script is in `scripts/` and runs with `uv run`. The runners carry their own dependencies (PEP 723),
so `uv` installs them the first time. `ffmpeg` must be installed (`brew install ffmpeg`,
`sudo apt install ffmpeg`, `winget install ffmpeg`).

In the commands below, `SCRIPTS` stands for the full path of this skill's `scripts/` folder (for example
`~/.claude/skills/local-audio-transcription/scripts`). **Write the real path out in every command. Do not
put it in a shell variable** (`S=...; uv run SCRIPTS/doctor.py`): Claude Code cannot check a command that sets
a variable against the user's permission rules, so it is refused.

If `uv` prints a warning that a `.python-version` file does not match the script's Python, ignore it. `uv`
picks a fitting Python by itself. Tell the user it is not an error.

## When to Use

- "Transcribe this interview", "make subtitles for this lecture video", "turn these oral history
  recordings into text", "transcribe this folder of MP3s".
- "Which speech model can my laptop run?" (step 1 alone answers this).
- The recordings are confidential (human subjects, restricted archives, unpublished fieldwork) and must
  not leave the computer: the strict offline path (step 0, then 5B).
- An earlier job stopped and should go on ("continue the transcription", "how far did it get?").

Not for: a recording that already has a good transcript or caption file; translation (the models
transcribe in the spoken language); music or lyrics. Classical Chinese read aloud, heavy dialects and poor
recordings will need a person to correct every line. Treat every result as a first draft.

## Workflow

Follow the steps in order. Use plain words with the user and explain any technical term once.

### 0. The first question: completely offline, or not?

Before anything else (before the doctor, before any download), ask with `AskUserQuestion`, as one
question on its own. If that tool is not there (for example in a headless run), write the question as
plain text, stop, and wait for the answer. Do not guess it.

> Do the recordings or their transcripts have to stay completely offline? Choose **Yes** if the material
> is confidential (interviews with living people, restricted archives, anything you are not allowed to
> send over the internet), or if you simply want that guarantee. Choose **No** if the material is not
> sensitive. In both cases the transcription runs on this computer, and nothing is uploaded; the
> difference is how carefully we prove it.

Explain the two paths in a sentence each:

- **No (normal):** download the model, test it on a sample clip, then transcribe the real files here
  while the computer stays online.
- **Yes (strict offline):** everything is installed and proven first on a short sample clip that the
  user provides and that is **not** from the sensitive material. The proof runs with every network
  connection blocked. Only then does the user disconnect the computer and run a ready-made script on the
  real recordings. This assistant needs the internet to work, so it cannot be present during the offline
  run; and it must **never read the real transcripts** (that would send them to the AI provider).

Store the answer: `offline: true/false`. It changes steps 4 and 5.

### 1. Check the machine and what is already there

```bash
uv run SCRIPTS/doctor.py
```

This prints the machine (chip, memory, GPU, free disk), the tools found (`uv`, `ffmpeg`, `ffprobe`,
`nvidia-smi`, `gh`), a verdict for each model (GOOD / SLOW / NO, the backend, the download size or
"already downloaded"), whether the speaker-label helper models are there, and **earlier jobs** with their
progress.

- If an earlier job is unfinished and matches what the user wants, offer to continue it (step 5).
- If `ffmpeg` is missing, say how to install it before going on.
- If the disk warning shows, say how much space is needed.

### 2. Interview, and ask for the sample clip

Ask with `AskUserQuestion` (up to 4 questions per call), or in plain text if that tool is not there.
Skip what the request already answered. Ask:

1. **The recordings.** Path to the files or folder. Roughly how many hours? Audio or video?
2. **The speech.** Language(s): Mandarin, Cantonese, another Chinese dialect, Japanese, Korean, English,
   another European language, mixed? Is it an interview (two voices), a lecture (one voice), a meeting
   (many)? Recording quality (studio, phone, old tape, noisy room)?
3. **Wanted.** Speaker labels (who said what)? Timestamps? The goal: a working transcript to search and
   quote, or subtitles?
4. **Output formats** (multiSelect): plain text with times (`txt`), Markdown (`md`), subtitles (`srt`,
   `vtt`), data (`json`, `jsonl`, `csv`), TEI for a digital edition (`tei`).

Then **ask for the sample clip** (always, both paths). Say:

> Please give me a short clip, 30 seconds to 3 minutes, in the same language and recorded in the same
> way as your material. It is used to install and test the model before the real run.
> It must be something you are allowed to put through a test: for a confidential project, record one
> yourself or use a public talk, **not** a piece of the confidential recordings.

Do not pick a clip from the user's files yourself. Wait for the path. Save the answers to a small JSON
file, for example `brief.json`, with the keys `material`, `languages`, `speakers`, `recording`, `quality`,
`goal`, `formats`, `offline`. `prepare.py --brief` stores it in the job, and the field report uses the
non-private keys.

### 3. Choose the model

Combine the languages with the doctor's verdicts:

| Speech | First choice | Fallback |
|---|---|---|
| Cantonese, or any Chinese dialect, or Mandarin mixed with another language | Qwen3-ASR | SenseVoice (fast draft; no punctuation) |
| Mandarin only | Qwen3-ASR or Whisper. **If unsure, run both on the sample and compare** (make a second sample job). On a literary reading Qwen3-ASR made fewer errors (5.9% of characters wrong, Whisper 8.7%) | SenseVoice on a weak machine |
| Japanese, Korean | Whisper | Qwen3-ASR. **Not SenseVoice for Japanese** |
| English, or one European language | Parakeet (fastest, word times) | Whisper (when accents, names or noise are hard) |
| Mixed languages in one recording | Qwen3-ASR | Whisper with `--language` set to the main one |
| Anything else (Thai, Vietnamese, Arabic, Hindi …) | Whisper | Qwen3-ASR if the language is in its list |
| Weak machine, no GPU, 8 GB | SenseVoice (CJK, English) or Parakeet ONNX (European) | Whisper on CPU, slow |

Qwen3-ASR and SenseVoice write **simplified characters** even for Cantonese and Taiwan Mandarin; say so
if the user needs traditional characters (OpenCC converts them afterwards). Whisper often writes
simplified characters too, also with `--language zh`. To steer it, give `run_whisper.py` a short sentence
in the style wanted: `--prompt "以下是普通話的句子，使用繁體字。"`. It usually follows, but not always.

Set expectations on punctuation: the models put in commas and full stops, but **not** quotation marks or
book-title marks (「」, 《》). SenseVoice gives no punctuation at all.

Tell the user the plan in one short paragraph: the model, why, the download size, the time (hours of
audio ÷ the speed), speaker labels or not, and the output formats. Wait for their OK before a download
over 1 GB or a run over an hour.

### 4. Sample job: install, download, test

```bash
uv run SCRIPTS/prepare.py SAMPLE.m4a --job ~/transcription-jobs/NAME-sample --model qwen3-asr --language yue \
    --formats txt,srt --sample --brief brief.json [--offline] [--diarize]
uv run SCRIPTS/run_qwen3asr.py ~/transcription-jobs/NAME-sample --setup   # installs, downloads, loads, then stops
uv run SCRIPTS/diarize.py ~/transcription-jobs/NAME-sample --setup         # only with --diarize (50 MB)
uv run SCRIPTS/run_qwen3asr.py ~/transcription-jobs/NAME-sample            # the sample itself
uv run SCRIPTS/diarize.py ~/transcription-jobs/NAME-sample --speakers 2    # only with --diarize
uv run SCRIPTS/export.py ~/transcription-jobs/NAME-sample
```

- Runner per model: `run_whisper.py`, `run_qwen3asr.py`, `run_sensevoice.py`, `run_parakeet.py`. The
  backend is picked automatically (`--backend` overrides): MLX on Apple Silicon; faster-whisper
  (CTranslate2), PyTorch or ONNX elsewhere.
- `--offline` on `prepare.py` marks the job strict: from then on every run except `--setup` blocks all
  network connections (a `socket` guard inside the process, plus the Hugging Face offline switches). In an
  offline job, `--setup` is the only step that may use the network.
- `--setup` is safe to run again. If the model is already there, it only loads it.
- Put jobs where the user wants them, outside iCloud/Dropbox/OneDrive folders. `~/transcription-jobs/<name>`
  is a good default. Every job is recorded in `~/.cache/local-audio-transcription/registry.json`.

Then check the result together. Show the user the sample's text file next to what was said and ask
them to judge it (you cannot listen). Tell them what to listen for: most errors are **words that sound
the same**, above all names and rare or literary words (博徒 heard as 博图, 滿臉濺朱 as 满脸见猪). These
read as fluent text, so they are only found by ear. Reading the sample transcript is fine: the user said the clip may
be tested. Note the real speed from the runner's output ("12.6x real time") and give the new time
estimate. If the quality is poor, change the model now (`prepare.py ... --model whisper` switches the
job), not after ten hours of audio.

### 5A. Normal path: the real recordings

```bash
uv run SCRIPTS/prepare.py REC1.mp3 FOLDER/ --job ~/transcription-jobs/NAME --model qwen3-asr --language yue \
    --formats txt,srt,json --brief brief.json [--diarize]
uv run SCRIPTS/run_qwen3asr.py ~/transcription-jobs/NAME --limit 3            # smoke test: the first chunks
uv run SCRIPTS/run_qwen3asr.py ~/transcription-jobs/NAME > ~/transcription-jobs/NAME/run.log 2>&1   # run_in_background
uv run SCRIPTS/jobs.py status ~/transcription-jobs/NAME                        # chunks done, speed, time left, flags
uv run SCRIPTS/diarize.py ~/transcription-jobs/NAME --speakers 2               # optional; slow on long recordings
uv run SCRIPTS/export.py ~/transcription-jobs/NAME
```

- `prepare.py` takes audio and video files and folders. Each file is one recording; ffmpeg converts it to
  16 kHz mono and cuts it into chunks of about 10 minutes **at a silence**, so no word is cut. Running it
  again on the same job adds only new files.
- The runner is resumable: stopping is safe, and the same command goes on from the next chunk. Chunks
  with an error are tried again. `--chunks 00012,00040` redoes chunks.
- Exports: txt and md start a new paragraph, with its time mark, at a speaker change, a pause, or after
  60 seconds (`--max-paragraph-seconds`), so a place in the recording is easy to find. srt and vtt cut
  long segments into cues of about 8 seconds (`--max-cue-seconds`). Qwen3-ASR and SenseVoice give one
  time per piece between silences (up to 30 s), so the times of cues inside such a piece are
  **estimates**, shared out by the number of characters. For subtitles that must be exact, use Whisper
  with `--words` or Parakeet; `--piece-seconds 15` on the Qwen3-ASR runner also gives shorter pieces.
- While it runs, log anything unusual with `uv run SCRIPTS/jobs.py note JOB "..."`: a crash, a very slow chunk,
  a language the model got wrong, memory trouble. The notes go into the report.
- Reading a transcript into this chat sends it to the AI provider. In a normal job, read only what the
  user agrees to, and never more than needed to judge quality.

What the runners flag (one flag per chunk; the report and `export.py` list them):

- **repeat**: the same text many times in a row; the model looped. No usable text there.
- **no_speech**: text on a chunk that sounds silent; Whisper invents captions on silence and music.
- **uncertain**: Whisper segments with very low confidence; often invented text, or the wrong language.
- **empty**: no text although the chunk has sound.
- **language**: the detected language differs from the one given.
- **slow**: more than three times the length of the audio.

### 5B. Strict offline path: prove it, then hand over

Do this only after the sample ran well in step 4 with `--offline`.

1. **Prove the pipeline needs no network.** This runs every step on the sample clip in fresh processes
   with the network guard on and `uv run --offline`, and first checks that the guard itself blocks a
   connection:

   ```bash
   uv run SCRIPTS/offline.py check ~/transcription-jobs/NAME-sample
   ```

   Every line must say PASS. If one fails, fix it with the network on (usually the model's `--setup`
   again, or `diarize.py --setup`) and run the check again. Do not go on until it passes.

2. **Write the hand-over script** for the real job:

   ```bash
   uv run SCRIPTS/offline.py script ~/transcription-jobs/NAME-sample --job ~/transcription-jobs/NAME --speakers 2
   ```

   This writes `~/transcription-jobs/NAME/transcribe-offline.sh` (macOS, Linux) and `transcribe-offline.ps1`
   (Windows). The script refuses to start while the network is still reachable, then converts the
   recordings, transcribes, labels speakers (if planned), exports and writes the report, with the same
   settings as the sample. Show the user the exact command, with their recording paths filled in.

3. **Tell the user how to disconnect and run it.** Say, in plain words:

   - Close this assistant's work for now: it cannot run while the computer is offline, and it must not
     see the transcripts.
   - Keep the job folder and the recordings on the computer's own disk, not in a synced folder (iCloud
     Drive, Dropbox, OneDrive, Google Drive). Pause those apps.
   - Turn the network off. **macOS:** click Wi-Fi in the menu bar and switch it off; unplug the Ethernet
     cable or adapter; turn Bluetooth off if a phone could share its connection. **Windows:** Settings >
     Network & internet > Airplane mode on; unplug Ethernet. **Linux:** the network menu, or
     `nmcli networking off`; unplug Ethernet.
   - Open a terminal and run (the script checks it is offline before it starts):

     ```bash
     bash ~/transcription-jobs/NAME/transcribe-offline.sh /path/to/interview1.m4a /path/to/folder
     ```

     On Windows: `powershell -ExecutionPolicy Bypass -File ...\transcribe-offline.ps1 C:\path\interview1.m4a`.
   - If it stops (closed laptop, power), run the same command again: it continues.
   - When it prints DONE, the transcripts are in `~/transcription-jobs/NAME/export/` and a report without
     any transcript text is `report.md`. Reconnect, and come back if help with the report is wanted.

4. **After the run**, read only `report.md` and `field-report.md` (they contain counts, speeds and
   flags, never text). Never open `rows.jsonl`, `speakers.jsonl` or anything under `export/`, and do not
   run `cat`, `head`, `grep` or `Read` on them. If the user wants help with a passage, they decide what to
   paste.

### 6. Report, and the field report for GitHub

```bash
uv run SCRIPTS/report.py ~/transcription-jobs/NAME --describe "oral history, Cantonese, two speakers, phone recording"
```

This writes two files:

- `JOB/report.md` is for the user: hours transcribed, speed, languages found, speakers, the chunks to
  listen to (with the time in the recording), the files, notes, licences. Give the main points in plain
  words. Always say: **machine transcription, not proofread; listen before quoting.**
- `JOB/field-report.md` is for a GitHub issue: machine, model, backend, versions, speed, flags, notes.
  No transcript text, no file paths, no recording names (unless `--share-titles`). Read it, ask the user
  for their judgement of the quality, fill in the last three lines, and remove anything private.

Then offer to post the field report. It helps tune the advice on speed, memory and model choice for other
machines and languages. Issues are public, so ask first and show the text:

```bash
gh issue create --repo kltng/humanities-skills \
  --title "[local-audio-transcription] field report: <model> on <chip>, <language>, <hours> h" \
  --body-file ~/transcription-jobs/NAME/field-report.md
```

Without `gh`, give the user the link https://github.com/kltng/humanities-skills/issues/new and the file to paste.

## Best Practices

- Ask the offline question first, alone, every time. It decides the whole shape of the work.
- The user provides the sample clip. Never take a piece of the real recordings for the test.
- Always run the doctor first, then a sample, then a smoke test (`--limit 3`) before a long run.
- One language per recording for Whisper; set `--language` whenever it is known. Qwen3-ASR for mixed
  languages and for anything Cantonese.
- Listen to every flagged chunk before trusting it. Whisper's invented captions look fluent.
- Speaker labels are approximate: speakers who sound alike get merged, and labels can swap after a long
  pause. Give `--speakers N` when the number is known.
- Keep jobs out of synced folders. Chunks are large and change often.
- Do not run two model jobs at once on one machine; they share the memory.
- Licences: Whisper is MIT; Qwen3-ASR is Apache 2.0; Parakeet is CC-BY-4.0; SenseVoice has its own model
  licence. When the transcript is published, say which model made the first draft.

## Example Code

A set of Cantonese oral-history interviews (12 hours, confidential) on a 16 GB MacBook, speaker labels,
text and SRT wanted:

```bash
# SCRIPTS = the full path of this skill's scripts/ folder, written out in every command
# step 0: offline = yes.  step 1:
uv run SCRIPTS/doctor.py                                           # qwen3-asr GOOD mlx, download about 2.5 GB
# step 2: the user gives ~/Desktop/test-clip.m4a (a clip they recorded themselves)
uv run SCRIPTS/prepare.py ~/Desktop/test-clip.m4a --job ~/transcription-jobs/oh-sample --model qwen3-asr \
    --language yue --formats txt,srt --sample --offline --diarize --brief /tmp/brief.json
uv run SCRIPTS/run_qwen3asr.py ~/transcription-jobs/oh-sample --setup
uv run SCRIPTS/diarize.py ~/transcription-jobs/oh-sample --setup
uv run SCRIPTS/run_qwen3asr.py ~/transcription-jobs/oh-sample          # network blocked from here on
uv run SCRIPTS/diarize.py ~/transcription-jobs/oh-sample --speakers 2
uv run SCRIPTS/export.py ~/transcription-jobs/oh-sample                # show the user the text, judge together
uv run SCRIPTS/offline.py check ~/transcription-jobs/oh-sample         # all PASS
uv run SCRIPTS/offline.py script ~/transcription-jobs/oh-sample --job ~/transcription-jobs/oh --speakers 2
# the user disconnects and runs:  bash ~/transcription-jobs/oh/transcribe-offline.sh ~/Interviews/
# later, online again: read only the report
cat ~/transcription-jobs/oh/report.md
```

A 90-minute English lecture video, not sensitive, subtitles wanted, on a Windows laptop without a GPU:

```bash
uv run SCRIPTS/doctor.py                                           # parakeet GOOD onnx, whisper SLOW ct2
uv run SCRIPTS/prepare.py lecture.mp4 --job D:/transcription-jobs/lecture --model parakeet --language en --formats srt,vtt,txt
uv run SCRIPTS/run_parakeet.py D:/transcription-jobs/lecture --limit 2
uv run SCRIPTS/run_parakeet.py D:/transcription-jobs/lecture          # about 25x real time on CPU
uv run SCRIPTS/export.py D:/transcription-jobs/lecture
uv run SCRIPTS/report.py D:/transcription-jobs/lecture --describe "English lecture video, one speaker"
```

## Resources

- `references/models.md`: the four models, the test results, hardware needs, licences, quirks.
- `references/api_reference.md`: every script and option, the job folder, the row format, the exports,
  and how the offline guard works.
- Whisper https://github.com/openai/whisper (MLX build: mlx-community); Qwen3-ASR
  https://github.com/QwenLM/Qwen3-ASR; SenseVoice https://github.com/FunAudioLLM/SenseVoice; Parakeet
  https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3; sherpa-onnx https://github.com/k2-fsa/sherpa-onnx
- Tests (offline, no models): `cd local-audio-transcription && python3 -m unittest discover -s tests`

## Feedback and Citation

**Report a problem.** This skill is part of the public repository [kltng/humanities-skills](https://github.com/kltng/humanities-skills). If it fails (a model or package changed, a script errors, or these instructions are wrong), report it as a GitHub issue:

1. Ask the user before filing. Issues are public.
2. Check for an existing report: `gh issue list --repo kltng/humanities-skills --state all --search "local-audio-transcription"`
3. File it: `gh issue create --repo kltng/humanities-skills --label bug --title "[local-audio-transcription] <short summary>" --body "<details>"`. Without `gh`, give the user this link: https://github.com/kltng/humanities-skills/issues/new?template=skill-problem.yml
4. Include the skill name and version, what you ran, the error text, what you expected, and the environment (OS, Python version). Leave out API keys, personal data, private file paths, transcript text, and unpublished research.

Field reports from finished jobs (step 6) are welcome too. Use the title `[local-audio-transcription] field report: ...`.

**Cite.** If this skill helped work that is published, please cite it, together with the model it used (OpenAI's Whisper, Alibaba's Qwen3-ASR or SenseVoice, NVIDIA's Parakeet):

> Tang, Kwok-leong. *humanities-skills: local-audio-transcription* (version <version at the top of this file>). GitHub, <year>. https://github.com/kltng/humanities-skills

When you help a user write up results that relied on this skill, remind them once about this citation.
