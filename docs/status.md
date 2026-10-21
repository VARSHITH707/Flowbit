# Flowbit feature status (v3.0.0, 2026-10-21)

Measured on one PC: Windows 11, RTX 4060 Laptop (8 GB). Evidence is in [testing.md](testing.md) and the scripts it names. A feature counts as verified only when it was run and checked, not because the code exists.

## Implemented and verified

| Feature | Evidence |
|---|---|
| Local transcription on GPU, CPU fallback, offline after download | benchmark; `check_offline.py`: 0 outside connections, only 127.0.0.1 for the local AI |
| Push to talk (hold) and toggle, auto-repeat ignored, cancel | `it_hotkeys.py` 8/8 and `it_e2e.py` 13/13 (keys injected as hardware scan codes) |
| State machine: idle, recording, processing, inserting, done; failed from any state; no duplicate session or insert | unit tests; `it_e2e.py` shows `recording → processing → inserting → done` |
| Formatting pipeline: segment join, spacing, capitals, sentence ends, questions | `test_formatting.py` (51 cases) and spoken clips |
| Numbered lists (`first point`, `point one`, `number one`, `firstly`, `numbered list`, `end list`), bullets, `new line`, `new paragraph` | unit tests, including cases that must *not* become lists; spoken clips through real Whisper |
| Context-aware numbers (25, 3.5, 15%, $20, $3.5 million, October 21, 21st, 250,000, 2026, 3:30 PM) | unit tests; Whisper's own digits untouched |
| Exact Transcription vs Smart Formatting | unit tests; spoken clips in both modes |
| AI punctuation for run-on speech, rejected if any word changes | run-on clips, punctuated in 0.5–1.3 s; prompt injection left as text |
| AI cleanup (fillers, self-corrections, the 7-point list) | benchmark 14/14 after the prompt change; `it_e2e_smart.py` 8/8 |
| Custom vocabulary (add, edit, delete, import, export, spoken=>written) | unit tests (whole words, case, multi-word, limits) |
| Learning from corrections | `it_learn.py` Edge 3/3 this round; Notepad part verified in v2.0 (skipped now because a Notepad window was open) |
| Floating mascot: always on top, translucent, never takes focus, clickable, draggable, position saved and kept on screen, opacity, reduced motion, states follow real state and mic level | `test_indicator.py`; `it_ui.py` 11/11 with **real mouse input** (click, drag, 125% scaling) |
| Insertion: never into Flowbit's own windows, focus restore from Flowbit windows, focus-change policy, button-focused guard | unit tests; `it_e2e.py` (focus moved: copied, not typed) |
| Clipboard fully restored (text, HTML, images, files), newer clipboard data kept | `it_clipboard.py` 9/9 |
| Insertion into Notepad, Edge textarea and input, Tk; Unicode, emoji, multi-line | `it_insertion.py` 10/10, `it_browser.py` 7/7, `it_undo.py` (Notepad) |
| Safe Undo Last Insertion | `it_undo.py` 11/11 in real Notepad and Edge: removes exactly its text, refuses after edits, in another window, and in apps it can't read |
| Shortcut conflict checks (editing keys, overlaps, registered by other programs, Wispr Flow running) | unit tests; found `Ctrl+Alt+Space` and `Ctrl+Alt+M` taken on this PC; old default migrated automatically |
| Settings persistence and migration from VoiceType settings | unit tests; the real `settings.json` migrated on first launch |
| History (search, copy, export with time and original wording, delete, clear, retention) | unit tests |
| UI stays responsive during long transcription | `it_ui.py`: max stall 80 ms during 5.7 minutes of audio |
| Branding: Flowbit name, black and orange theme, vector mascot and icon, logo | screenshots reviewed (`data/shots`, `docs/img`) |
| Windows package (PyInstaller, 2.35 GB GPU build) | `dist\Flowbit\Flowbit.exe --selftest`: GPU transcription correct |

## Implemented, not fully tested

| Feature | What is missing |
|---|---|
| Modifier-only toggle such as `Ctrl+Win` | Unit-tested only. It wasn't pressed for real, because the installed Wispr Flow reacts to injected Windows-key chords |
| Physical key presses by a person | All hotkey tests inject keys. Not yet confirmed by hand on this version |
| Adaptive silence auto-stop (toggle mode) | Unit-tested with synthetic audio, including fan-level noise; not with a real voice in a noisy room |
| Preview before insertion | Code path and dialog built; not exercised in an automated end-to-end run |
| Mascot on multiple monitors | Clamping uses the screen under the mascot; only one monitor was available |
| Packaged `.exe`: hotkeys, insertion, mascot | Only `--selftest` (transcription) was run inside the exe |
| Real human speech accuracy | Benchmarks use synthetic voices. My 25 real dictations show the punctuation problem the AI pass now fixes, but there's no accuracy number for my voice yet |
| Insertion in VS Code, Chrome, Word, Slack and other apps | Only Notepad, Edge and Tk were tested |
| `it_notepad.py` this round | Not run: a Notepad window with the user's own tabs was open, and the tests never touch it. Notepad insertion and undo were verified inside `it_undo.py` |

## Partially implemented

| Feature | State |
|---|---|
| Punctuation without the local AI | Rules add sentence ends and capitals. Commas inside long run-on speech need the AI pass (or a dedicated punctuation model, not installed) |
| Times and dates | Only "<hour> [minutes] am/pm" and "<Month> <number>" are converted |
| Undo | Only in apps that expose their text to UI Automation, and only while the text is unchanged |
| Fine-tuning on your voice | Pipeline verified end to end on synthetic clips. Waiting for your recordings |

## Planned
- A dedicated local punctuation model, so the rule-only mode also gets commas (a separate download, about 100–500 MB).
- Command mode and snippets, as in the reference product.

## Blocked
- **Dictating into windows running as administrator.** Windows (UIPI) hides their keys from a normal program, and Flowbit doesn't ask for admin rights by design.
- **Code signing.** It needs a paid certificate, so Windows SmartScreen warns about the unsigned `.exe`.
