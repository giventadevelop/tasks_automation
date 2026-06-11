# YouTube_Transcribe

Download a YouTube video's audio and produce a text transcript (and English
translation if the audio isn't English) using local Whisper. No API keys, no
cloud, no captions required — works on videos with subtitles disabled.

## Layout

| File                       | What it does                                          |
|----------------------------|-------------------------------------------------------|
| `transcribe_youtube.py`    | The actual script. Run directly or via the .bat.      |
| `run_transcribe.bat`       | Double-click on Windows. Prompts for URL + model.     |
| `setup.bat`                | One-time installer for the WSL whisper venv.          |
| `transcripts/`             | Output directory (auto-created, gitignored).          |

## First run (one-time setup)

Double-click `setup.bat`. It will:
- Create `~/venvs/whisper` in WSL and install `faster-whisper` into it
- Verify `ffmpeg` and `yt-dlp` are available

If ffmpeg or yt-dlp are missing, the script tells you the exact command to fix it:
```bash
sudo apt install -y ffmpeg          # WSL
pipx install yt-dlp                 # WSL
```

## Normal use

Double-click `run_transcribe.bat`, paste a YouTube URL, press Enter.

Output files (in `transcripts/<videoId>_<slug>.*`):
- `*.transcript.txt`    — plain text in the source language
- `*.transcript.srt`    — timestamped subtitle file
- `*.translation.txt`   — English translation (only when source ≠ English)
- `*.summary7.txt`      — 7-sentence TL;DR (extractive summary of the English text)
- `*.summary.md`        — combined markdown with metadata + TL;DR + transcript + translation

The TL;DR is also printed to the console at the end of every run, so you can see the gist without opening any file.

The downloaded mp3 is deleted after transcription by default; pass
`--keep-audio` (or set `KEEP_AUDIO=1`) to retain it.

## Auto-cleanup of old outputs

Every run prunes files in `transcripts/` older than **20 days** by default.
This keeps the folder from growing indefinitely. Override with:

```bash
~/venvs/whisper/bin/python transcribe_youtube.py URL --prune-days 60   # keep 60 days
~/venvs/whisper/bin/python transcribe_youtube.py URL --prune-days 0    # disable pruning
```

Or run a **cleanup-only pass** with no URL — useful as a cron job:

```bash
~/venvs/whisper/bin/python transcribe_youtube.py --prune-days 20
```

Env-var equivalent: `PRUNE_DAYS=30`.

## CLI use (from WSL, no .bat)

```bash
cd /mnt/c/E_Drive/project_workspace/tasks_automation/YouTube_Transcribe
~/venvs/whisper/bin/python transcribe_youtube.py "https://youtube.com/watch?v=XXXXX"

# Bigger model (slower but more accurate)
~/venvs/whisper/bin/python transcribe_youtube.py URL --model medium

# Skip translation
~/venvs/whisper/bin/python transcribe_youtube.py URL --no-translate

# Keep the mp3
~/venvs/whisper/bin/python transcribe_youtube.py URL --keep-audio
```

## Model picker

| Model      | RAM    | Speed (2-min clip, CPU) | Quality        |
|------------|--------|--------------------------|----------------|
| `tiny`     | ~1 GB  | ~5 s                     | Rough          |
| `base`     | ~1 GB  | ~10 s                     | Decent         |
| `small`    | ~2 GB  | ~25 s (default)          | Good           |
| `medium`   | ~5 GB  | ~90 s                     | Very good      |
| `large-v3` | ~10 GB | ~3 min                    | Best (slow)    |

`small` is the sweet spot for news/podcasts. Use `medium`+ only for noisy or
heavily accented audio.

## Env-var overrides

| Var             | Purpose                                              |
|-----------------|------------------------------------------------------|
| `WHISPER_MODEL`     | model name (default `small`)                          |
| `SUMMARY_SENTENCES` | TL;DR length (default 7; `0` disables)                 |
| `PRUNE_DAYS`        | auto-delete files in out-dir older than N days (default 20; `0` disables) |
| `TRANSLATE`         | `1` → force-emit English translation                  |
| `KEEP_AUDIO`    | `1` → don't delete the mp3                            |
| `OUTPUT_DIR`    | override output directory                              |
| `YTDLP`         | yt-dlp binary path                                     |
| `WHISPER_PY`    | python interpreter that has `faster_whisper` installed |

## Pattern notes

Follows the same conventions as `WhatsApp_Web_Poll`:
- Minimal deps: stdlib + faster-whisper (one library), plus yt-dlp/ffmpeg from
  pipx/apt — no Selenium/Playwright/browser-use.
- `setup.bat` / `run_*.bat` double-click launchers for Windows users.
- Python script is the source of truth; the .bat is just a friendly wrapper.

## Known limits

- Whisper hallucinates a bit on long silences. The script enables
  `vad_filter=True` to suppress most of this.
- Music-heavy videos (no speech) produce nonsense. Whisper is a speech model.
- yt-dlp may fail on age-restricted or members-only videos. Sign-in cookie
  support is not built in (yet).
