# Architecture (Flowbit)

The Python package is still called `voicetype` (renaming it would break installs and data paths); everything the user sees is Flowbit.

```
 hotkeys.py  (Win32 low-level keyboard hook, own thread) + conflict checks (RegisterHotKey probe, editing keys, overlaps)
     | start / stop / toggle / cancel / undo / settings  (queued, handled off the hook thread)
     v
 dictation.py  controller: idle -> recording -> processing -> inserting -> done | failed   (UI-agnostic, callbacks)
     |-- audio.py       Recorder: 16 kHz mono, max duration, live level, adaptive silence auto-stop (toggle mode), stop reason
     |-- transcriber.py lazy-loaded model, serialises runs, unloads when idle, applies vocabulary/cleanup
     |      |-- speech.py    Engine: faster-whisper (CTranslate2), GPU first, CPU fallback, never returns text on failure
     |      |-- formatting.py rules: segment join, spacing, capitals, sentence ends, lists, bullets, commands, numbers
     |      |-- models.py    pinned Hugging Face downloads, availability, delete
     |      |-- textproc.py  vocabulary replacement, filler removal
     |      |-- cleanup.py   local LLM via Ollama (127.0.0.1): cleanup (word safety check) and punctuation-only pass (words must match)
     |      |-- memory.py    learned word fixes + edit examples (memory folder), app categories for style
     |-- insertion.py   paste (whole clipboard saved/restored) or paced typing into the window focused when recording started
     |-- learner.py     after pasting, watches the same text box (UI Automation) and learns your fixes
     |-- undo.py        Undo Last Insertion: verifies window, box, unchanged text, exact selection, then deletes
     v
 app.py  wires Qt UI <-> controller through a Bridge(QObject) of signals (worker/hook threads never touch widgets)
     |-- ui/mascot.py        Flowbit mascot: non-activating, clickable, draggable; vector drawing driven by real state + mic level
     |-- ui/preview.py       optional check-before-insert dialog
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
| Rule-based formatting first, AI optional | Basic formatting must work without an LLM; explicit list/command cues are applied before the AI so it cannot lose them (it did) |
| AI punctuation pass accepted only with identical words | Whisper leaves run-on speech unpunctuated on every model size (measured); the guard makes the AI unable to change what was said |
| Mascot not click-through, but WS_EX_NOACTIVATE | It must receive clicks and drags without ever taking the cursor from the target app (verified with real mouse input) |
| Undo only with proof, never Ctrl+Z | Ctrl+Z goes to whatever is focused and undoes unknown things; deleting a verified selection is the only safe option |
| Toggle default Ctrl+Alt+T | Ctrl+Alt+Space turned out to be registered by another program on this PC (RegisterHotKey probe) |

## Threads
UI thread (Qt) | hotkey hook thread (does almost nothing: updates key state, may swallow a key) | hotkey dispatcher thread (calls the controller) | audio callback thread (PortAudio) | transcription worker thread (one per dictation, serialised by a lock) | download/mic-test jobs (`ui/workers.py`).

## Known limits
- A normal-user app cannot type into windows running as administrator (Windows UIPI).
- Windows may drop a low-level hook if its thread stalls for ~300 ms; the hook does no heavy work, and transcription runs outside the Python GIL.
- Clipboard content that cannot be restored exactly (metafiles, owner-drawn formats, over 64 MB) is never overwritten; the text is typed instead.
- Learning from corrections only works in apps that expose their text through UI Automation (verified: Notepad, Edge).
- The AI steps need Ollama and ~4.7 GB of GPU memory next to Whisper; without them the rule-based formatting still runs.
- Undo works only in apps that expose their text (verified: Notepad, Edge).
