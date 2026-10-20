# Architecture

```
 hotkeys.py  (Win32 low-level keyboard hook, own thread)
     | start / stop / toggle / cancel / settings  (queued, handled off the hook thread)
     v
 dictation.py  controller: idle -> recording -> processing -> done | failed   (UI-agnostic, callbacks)
     |-- audio.py       Recorder: sounddevice InputStream, 16 kHz mono, max duration, optional silence auto-stop
     |-- transcriber.py lazy-loaded model, serialises runs, unloads when idle, applies vocabulary/cleanup
     |      |-- speech.py    Engine: faster-whisper (CTranslate2), GPU first, CPU fallback, never returns text on failure
     |      |-- models.py    pinned Hugging Face downloads, availability, delete
     |      |-- textproc.py  vocabulary replacement, filler removal ("clean" mode)
     |      |-- cleanup.py   Smart mode: local LLM via Ollama (127.0.0.1), safety check, raw fallback
     |      |-- memory.py    learned word fixes + edit examples (memory folder), app categories for style
     |-- insertion.py   paste (whole clipboard saved/restored) or paced typing into the window focused when recording started
     |-- learner.py     after pasting, watches the same text box (UI Automation) and learns your fixes
     v
 app.py  wires Qt UI <-> controller through a Bridge(QObject) of signals (worker/hook threads never touch widgets)
     |-- ui/pill.py          non-activating, click-through status pill (idle/listening/transcribing/done/failed)
     |-- ui/main_window.py   Home, History, Memory, Models, Settings pages; ui/setup_dialog.py first-run wizard
     |-- history.py          SQLite, secure_delete, export
     |-- config.py           JSON settings with per-value validation, atomic writes
```

## Key decisions (and why)
| Decision | Reason |
|---|---|
| faster-whisper, default `large-v3-turbo` | Measured: same speed as `small` on a 5.7 min clip, WER 1.9 %, 1.1 GB VRAM (docs/benchmark.md) |
| Paste by default, typing only as fallback | Real Win11 Notepad garbled flooded Unicode typing; paste is atomic and handles accents/emoji |
| Never paste into a different window | Focus is remembered at record start; if it changed, text goes to the clipboard and the user is told |
| Own low-level hook instead of the `keyboard` library | The library kept stuck modifier state after Windows-generated key events |
| Chord key swallowed while its modifiers are held | Otherwise the letter of `ctrl+alt+d` is typed into the app (AltGr behaviour in some apps) |
| Vocabulary = replacement, recogniser hinting opt-in | Feeding a glossary to Whisper made it add or drop words in real audio |
| Models pinned to commit SHAs | A change to a repository's `main` cannot swap the weights we load |
| Audio only in memory | Nothing about speech is ever written to disk |
| Transcription runs one at a time | A cancelled run may still be finishing when the next starts |
| Local LLM cleanup with a word-level safety check | Benchmark: qwen2.5 7B 14/14; smaller models obeyed injected instructions or answered questions. The check rejects any output with >2 words that were never said |
| Learn names after 1 fix, other words after 2 | A one-off grammar edit (send->sent) must not rewrite all future text; Friday->Monday style content changes are never learned |
| Save/restore every clipboard format | Browsers add HTML formats; text-only restore would have forced slow typing after every browser copy |

## Threads
UI thread (Qt) | hotkey hook thread (does almost nothing: updates key state, may swallow a key) | hotkey dispatcher thread (calls the controller) | audio callback thread (PortAudio) | transcription worker thread (one per dictation, serialised by a lock) | download/mic-test jobs (`ui/workers.py`).

## Known limits
- A normal-user app cannot type into windows running as administrator (Windows UIPI).
- Windows may drop a low-level hook if its thread stalls for ~300 ms; the hook does no heavy work, and transcription runs outside the Python GIL.
- Clipboard content that cannot be restored exactly (metafiles, owner-drawn formats, over 64 MB) is never overwritten; the text is typed instead.
- Learning from corrections only works in apps that expose their text through UI Automation (verified: Notepad, Edge).
- Smart mode needs Ollama and ~4.7 GB of GPU memory next to Whisper; without it, the plain transcript is used.
