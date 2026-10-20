# VoiceType

Local, private voice typing for Windows 11. Hold a hotkey, speak, release: the text appears in the app you were typing in. Speech recognition runs **on your PC** (Whisper on your NVIDIA GPU, or the CPU), so there is **no account, no subscription, no word limit and no upload of your audio**.

This is an original application. It was designed after studying the public behaviour of commercial dictation tools (see `docs/rea-findings.md`); it contains none of their code or assets. It is **not affiliated with or endorsed by Wispr Flow**; the name is only used to describe what this project replaces.

License: [MIT](LICENSE). You are free to clone, use and modify your own copy. This repository itself only accepts changes from its owner and collaborators; to suggest something, open an issue.

> Status: working MVP, tested on one machine (Windows 11, RTX 4060 Laptop, Python 3.11). Read [What is and is not verified](#what-is-and-is-not-verified) before relying on it.

## Requirements
- Windows 11 x64, a microphone
- Python **3.11** (not 3.13). [uv](https://docs.astral.sh/uv/) is the easiest way to get it
- Optional: NVIDIA GPU + recent driver for fast transcription (about 1.1 GB VRAM with the default model). Without one the app uses the CPU automatically (slower)
- About 2 GB disk for the `large-v3-turbo` model (or 0.5 GB for `small`), downloaded once
- For **Smart mode** (AI cleanup, see below): [Ollama](https://ollama.com) installed, then `ollama pull qwen2.5:7b-instruct-q4_K_M` (4.7 GB, once). Whisper + this model use about 6.6 GB of an 8 GB GPU. Without Ollama, VoiceType still works and simply inserts the plain transcript

## Install
```powershell
git clone https://github.com/VARSHITH707/Unlimited-WisprFlow.git
cd Unlimited-WisprFlow
uv venv --python 3.11 .venv
uv pip install --python .venv\Scripts\python.exe -r requirements.txt
```
(Without uv: `py -3.11 -m venv .venv` then `.venv\Scripts\python -m pip install -r requirements.txt`.)
For a CPU-only install, delete the two `nvidia-...` lines from `requirements.txt` first.

## Run
```powershell
.\.venv\Scripts\python.exe -m voicetype
```
On first start a short wizard lets you pick and test a microphone and download a speech model. You can also download models later from the **Models** tab, or from a terminal:
```powershell
.\.venv\Scripts\python.exe -c "from voicetype import models; models.download('large-v3-turbo')"
```
After the download, dictation works fully offline. The app lives in the system tray; closing the window keeps it running so the hotkeys keep working. Quit from the tray menu.

## Use
| Action | Default hotkey |
|---|---|
| Dictate (push to talk) | **hold** `Ctrl+Alt+D`, speak, release |
| Dictate (toggle) | press `Ctrl+Alt+Space` to start, again to stop |
| Cancel (nothing is inserted) | `Esc` while recording or transcribing |
| Open settings | `Ctrl+Alt+Shift+V` |

1. Click into any text field (Notepad, browser, chat, editor).
2. Hold the hotkey and speak. A small pill at the bottom of the screen shows *Listening*, then *Transcribing*, then *Done*.
3. The text is pasted where your cursor was. Your clipboard is restored afterwards.

### Smart mode (default): cleanup like Wispr Flow, on your laptop
A local AI (qwen2.5 7B through Ollama on `127.0.0.1`) tidies what you said before it is pasted:
| You say | VoiceType types |
|---|---|
| "um so I think uh we should ship it on Friday" | So I think we should ship it on Friday. |
| "let's do coffee at 2 actually 3" | Let's do coffee at 3. |
| "schedule it for Monday no scratch that Tuesday" | Schedule it for Tuesday. |
| "one open the laptop two log in ... seven buy milk no no that is not the seventh point the seventh point is archive the old files" | a numbered list 1-7 ending with "Archive the old files" |
| "hello comma how are you question mark" | Hello, how are you? |
| "I actually enjoyed the movie" / "what is the capital of France" | kept as said (not "corrected", not answered) |

Safety: if the AI's version contains words you never said, or drops most of it, or the AI is not running, VoiceType pastes the plain transcript instead and tells you why. **Undo AI edit** (Home tab, and *Copy original* in History) gives you exactly what was recognised. Writing style can be set per kind of app (email, work chat, personal chat, code, other); casual style drops the final period in chat apps, as Wispr Flow does.

### Memory: it learns from your corrections
After pasting, VoiceType keeps an eye on that same text box. When you fix a word it typed (for example *cubernetes* to *Kubernetes*) and move on, it remembers the fix in `userdata\memory` (inside the VoiceType folder) and writes it your way next time. **Names** (you capitalised them) apply after one fix; **other words** only after you make the same fix twice, so a one-off edit never rewrites future text; content changes such as *Friday* to *Monday* are never learned. See and delete what it learned in the **Memory** tab. Works in apps that expose their text to Windows (verified: Notepad, Edge); elsewhere it quietly does nothing. Turn it off in Settings.

If you switch to another window while speaking, the text is **not** pasted anywhere: it is copied to the clipboard and you are told (you can change this in Settings). Hotkeys can be changed in **Settings**; if you also run another dictation tool, give the two apps different hotkeys.

### Fine-tune on your own voice (in progress)
Step 1 of 3 (record, then train, then evaluate). Record a dataset of your voice:
```powershell
.\.venv\Scripts\python.exe scripts\record_voice.py
```
1. Read the sentence shown, or say anything you normally dictate. Press **F5** to start and stop.
2. The current model's transcript appears. Correct it until it matches **exactly** what you said. If you read the sentence word for word, click *I read the sentence above exactly*.
3. Press **Save** (`Ctrl+S`).

The sentences mix everyday dictation with your own past dictations. Aim for 30–60 minutes in total; you can stop and continue any time. The window shows how often the current model gets your words wrong; that number is the baseline the fine-tuned model has to beat. Clips are saved in `userdata\voice\`, which stays on your PC and out of git.

## Settings and data
Everything VoiceType saves stays **inside its own folder**: settings, history, memory and the log in `userdata\`, speech models in `models\`. Both are excluded from git. (Settings has an *Open data folder* button). Audio is never saved. Details: [docs/privacy.md](docs/privacy.md).

| Setting | Notes |
|---|---|
| Model | `large-v3-turbo` (default, most accurate), `medium`, `small` (fastest/lightest) |
| Run on | Automatic (GPU if available), GPU, or CPU |
| Language | English by default; pick another or auto-detect (only English was tested) |
| Hotkeys / mode | hold, toggle, or both |
| Longest recording | default 5 minutes; optional stop after a pause in speech |
| Text mode | *Smart* (default, local AI cleanup), *Clean* (only drops um/uh), *Exact* (as recognised) |
| Local AI model | default `qwen2.5:7b-instruct-q4_K_M` (chosen by benchmark, see docs/cleanup-benchmark.md) |
| Writing style per app | formal or casual for email, work chat, personal chat, code, everything else |
| Learn from my corrections | on by default; reads the text box after pasting, on this PC only |
| Custom vocabulary | `Kubernetes` fixes spelling/case; `py side six=>PySide6` replaces what was heard |
| History | on/off, auto-delete after N days, search, copy, export, delete |

## Tests
```powershell
uv pip install --python .venv\Scripts\python.exe -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q tests          # 107 tests, ~4 s, opens no windows
```
Hardware-dependent integration scripts and their results are in [docs/testing.md](docs/testing.md).

## Troubleshooting
| Problem | What to do |
|---|---|
| "Model ... is not downloaded yet" | Models tab -> Download (needs internet once) |
| Nothing happens when I press the hotkey | Another app may use the same keys (change them in Settings). The hook cannot see keys typed into windows running **as administrator**: run VoiceType as admin or dictate into a normal window |
| Text goes to the clipboard instead of the window | Focus moved while you were speaking (by design), or the target is an elevated window |
| "AI cleanup skipped: ..." | The AI's version added or dropped words, so the plain transcript was used (by design). If it says the local AI is unavailable: start Ollama and run `ollama pull qwen2.5:7b-instruct-q4_K_M` |
| Smart mode is slow the first time | The AI loads when VoiceType starts (about 3-15 s in the background). After that, about 0.5-1.6 s per dictation |
| "No speech detected" / "No audio captured" | Mic is silent or muted: check Settings -> Microphone and Windows microphone privacy settings |
| GPU error / out of memory | Pick `small` or CPU in Settings. The app already retries on the CPU automatically and says so |
| Slow first dictation | The model loads on first use (about 3 s from cache). It is unloaded after 10 idle minutes (changeable) |
| Another dictation tool types extra text | Give the two apps different hotkeys |
| Windows says "symlinks not supported" during download | Harmless; set `HF_HUB_DISABLE_SYMLINKS_WARNING=1` to hide it |

## Project layout
`voicetype/` application code (see [docs/architecture.md](docs/architecture.md)) | `tests/` automated tests | `scripts/` integration, benchmark and measurement scripts | `docs/` research, requirements, benchmark, privacy, testing, status.

## Build a standalone executable
```powershell
uv pip install --python .venv\Scripts\python.exe -r requirements-dev.txt
powershell -ExecutionPolicy Bypass -File scripts\build_exe.ps1            # GPU build -> dist\VoiceType\VoiceType.exe
powershell -ExecutionPolicy Bypass -File scripts\build_exe.ps1 -CpuOnly   # CPU build (much smaller)
```
The result is a folder (`dist\VoiceType`), not a single file. Copy the whole folder. Speech models are **not** bundled: they download on first use, as in the development install.

What was verified for the GPU build (about 2.3 GB, of which ~2.0 GB is NVIDIA's cuBLAS/cuDNN): it launches and exits with code 0, shows its windows, and transcribes on the GPU from inside the `.exe` (`VoiceType.exe --selftest sample.wav --selftest-out result.json` writes a JSON report; the packaged app has no console). **Not verified:** the hotkey/insert flow and the first-run wizard inside the packaged build (they run the same code as the development install), the CPU-only build, installing on a second PC, and code signing (Windows SmartScreen will warn about an unsigned `.exe`).

Gotcha fixed in the build script: building from a shell whose PATH contains Git's `mingw64\bin` bundles the wrong OpenSSL and breaks `import ssl` ("DLL load failed while importing _ssl"). The script builds with a clean PATH.

## What is and is not verified
See the feature table in [docs/status.md](docs/status.md). In short: the core loop (hotkey -> record -> local transcription -> insert) is verified end to end on real hardware, including real Notepad and Edge. **Not yet verified:** pressing the hotkeys by hand, real human speech accuracy (benchmarks use synthetic voices), other languages, unplugging the mic mid-recording, apps other than Notepad/Edge. Please try those and report what breaks.
