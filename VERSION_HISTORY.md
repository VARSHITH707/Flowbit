# VoiceType: Version History

Each version records what was built, what changed since the previous version, the files involved, how it was tested, and what was still open at that point. Newest version first. Never edit or delete an old entry; add a new version on top instead.

| Version | Date | Theme |
|---|---|---|
| [v2.0.3](#v203--2026-10-21) | 2026-10-21 | CSV export includes the original wording |
| [v2.0.2](#v202--2026-10-21) | 2026-10-21 | Everything stays in the project folder (nothing on C) |
| [v2.0.1](#v201--2026-10-21) | 2026-10-21 | Published on GitHub (MIT), hands-on test sheet |
| [v2.0](#v20--2026-10-20-evening) | 2026-10-20, evening | Smart mode, memory that learns, styles per app |
| [v1.1](#v11--2026-10-20-early-evening) | 2026-10-20, early evening | Language test tool and Wispr Flow research (no app changes) |
| [v1.0](#v10--2026-10-20-afternoon) | 2026-10-20, afternoon | First working app: local dictation into any window |
| [v0](#v0--2026-10-20-morning) | 2026-10-20, morning | Tooling and plan, before any code |

---

## v2.0.3 · 2026-10-21
**Why:** I opened `history.db` in Notepad and saw unreadable text. It's a database, so a readable file was needed.
### Changed
- The History → Export → CSV file now has an "original (before AI cleanup)" column next to the final text and timestamp.
### Tested
- 108 tests pass (the export test now checks the original wording). Exported my 13 dictations to `userdata\history.csv`.

---

## v2.0.2 · 2026-10-21
**Theme:** Keep everything that belongs to this project inside its own folder.
**Why:** All of my AI projects live on Z:. VoiceType was saving history in `C:\Users\...\AppData\Roaming\VoiceType`, models in the shared Hugging Face cache on C, and test files in the C temp folder.

### Changed
| What | Before (on C) | Now |
|---|---|---|
| History, settings, memory, log | `%APPDATA%\VoiceType` | `userdata\` |
| Speech models | `%USERPROFILE%\.cache\huggingface` | `models\` |
| Temporary files (app, tests, scripts) | `%TEMP%` | `.tmp\` |

- All three folders are excluded from git, so personal data and models are never published.
- For the packaged `.exe`, the same folders are created next to `VoiceType.exe`.
- `VOICETYPE_HOME` still overrides the data folder.
- Updated the README, privacy doc and `.env.example`.
- The 3 speech models VoiceType had downloaded were copied to `models\`. Other projects' models on C were left alone.
- Stays on C on purpose: shared programs used by other projects too (Python 3.11 that `.venv` runs on, Ollama and its server). The local AI model was already on `I:\ollama\models`.

### Tested
- 108 automated tests pass (new: data and models resolve inside the app folder).
- `check_offline.py` passes, with models loading from `Z:\Wispr Flow\models` and temp files landing in `.tmp\`.

---

## v2.0.1 · 2026-10-21
**Theme:** Publish the project. No changes to how the app works.
**Why:** The first hands-on test was good enough. Share it publicly while the models are improved.

### Added
- `LICENSE` (MIT).
- `docs/manual-test.md`: 20 hands-on tests with expected results.
- `PROJECT_REPORT.md` and this file.
- Public GitHub repo: https://github.com/VARSHITH707/Unlimited-WisprFlow
  - Anyone can clone it.
  - Only the owner and collaborators can push.
  - `main` is protected: no force-push, no deletion, and changes go through a reviewed pull request.

### Changed
- README: `git clone` install steps, license, and a "not affiliated with Wispr Flow" note.
- README: fixed two broken paths and the test count (107).
- Removed the Windows username from a path in `docs/CHECKLIST.md`.

### Not published (stays on this PC only)
- `.venv/`, `dist/` (the 2.3 GB `.exe`), `data/` (test recordings and screenshots), `.rea/` (raw analysis of the installed Wispr Flow), `.env`.

### Still open at v2.0.1
- Better accuracy through model tuning and fine-tuning (planned next).
- The items listed under v2.0.

---

## v2.0 · 2026-10-20 (evening)
**Theme:** Behave like Wispr Flow (clean up speech, learn from corrections) while keeping everything on the laptop.
**Why:** Wispr Flow does its cleanup in the cloud. The goal was the same features with nothing leaving the PC.
**Built:** 19:40–22:49 · **Checklist:** phase 9 (items 9.1–9.10)

### Added
- **Smart mode** (`voicetype/cleanup.py`). A local AI (qwen2.5 7B via Ollama on `127.0.0.1`) removes fillers, handles self-corrections ("2, actually 3" becomes "3"; "Monday, scratch that, Tuesday" becomes "Tuesday"), builds numbered lists, and turns spoken punctuation into symbols. It is the new default mode.
- **Safety check.** If the AI adds words that were never said, drops most of the text, or isn't running, the plain transcript is used and the user is told why.
- **Undo AI edit** (Home tab) and **Copy original** (History). The original transcript is stored next to the cleaned one.
- **Memory** (`voicetype/memory.py`, `learner.py`, `ui/memory_page.py`, folder `%APPDATA%\VoiceType\memory`).
  - After pasting, VoiceType watches that text box and learns word fixes.
  - Names are learned after one fix; other words after two identical fixes.
  - The new Memory tab shows what was learned and can forget it.
- **Writing style per app.** Formal or casual for email, work chat, personal chat, code and everything else. Casual chat drops the final period.
- **Warm-up at start**, so the first dictation is fast.
- New tests: `tests/test_smart.py`, `tests/test_paste_confirm.py`.
- New hardware scripts: `it_smart.py`, `it_e2e_smart.py`, `it_learn.py`, `it_clipboard.py`, and the AI benchmark `bench_cleanup.py`.

### Changed
- `insertion.py` now saves and restores **every** clipboard format (browser HTML, RTF, images, copied files), not only text.
- Every paste is now confirmed by reading the text box. A paste that can't be confirmed is reported, never retried.
- History stores the original transcript (`raw` column, migrated automatically).
- `transcriber.py` and `dictation.py` pass the app category through, so the style can follow the app.
- Settings has new controls: text mode (Smart / Clean / Exact), AI model, style per app, and "Learn from my corrections".
- `check_offline.py` allows connections to the local AI on `127.0.0.1` only.
- Hardware tests use Shift+F9/F10/F11 so the real Wispr Flow doesn't react.

### Fixed
- The first AI call took 15.6 s because warm-up and real calls used different settings. Now 0.98 s.
- The first dictation after start took 5.1 s. Now 2.6 s, because Whisper also warms up.
- The learning rules would have learned content changes (Friday → Monday) and one-off edits (send → sent). The rules are now stricter.
- After any browser copy, VoiceType fell back to slow typing. Fixed by restoring the full clipboard.
- Text was lost when Notepad's focus was on a toolbar button. VoiceType now copies the text and tells the user.
- A paste retry produced duplicate text. The retry was removed.
- A test created the real `%APPDATA%\VoiceType\memory` folder. Tests are now isolated in a temp folder.

### Tested
- 107 automated tests pass.
- Hardware suites: smart 6/6, smart end to end 8/8, auto-learn 9/9, clipboard 9/9, insertion 10/10, hotkeys 8/8, Edge 7/7, recorder 8/8, UI 5/5, end to end 13/13.
- 0 network connections leave the PC; bandit and pip-audit are clean.
- Notepad 6/8: one paste miss, detected and reported as designed.

### Still open at v2.0
- Not yet tested on a real voice or long dictations.
- How well the "casual" style is followed hasn't been measured.
- Learning hasn't been tested in Word, Slack or VS Code.
- Notepad misses about 1 paste in 15 under fast automation.

---

## v1.1 · 2026-10-20 (early evening)
**Theme:** Prepare for testing, and research how Wispr Flow works. No changes to the app.
**Built:** 19:17–19:27

### Added
- `scripts/try_language.py`, to test any language by hand.
- Manual testing guide in `docs/testing.md`.
- `docs/wispr-architecture-research.md`: how Wispr Flow works, from public sources.
  - Its speech recognition and its text-cleanup AI both run in the cloud.
  - It has "Backtrack" (self-correction) and auto-learn from edits.
  - Its patents cover only silent speech.
  - This research became the plan for v2.0.

---

## v1.0 · 2026-10-20 (afternoon)
**Theme:** First working version. Local, private dictation into any app.
**Built:** 15:55–17:46 · **Checklist:** phases 0–8

### Added
- **Speech engine** (`voicetype/speech.py`, `cuda.py`, `models.py`).
  - faster-whisper on the GPU, with automatic CPU fallback.
  - Default model `large-v3-turbo`, chosen by benchmark (`docs/benchmark.md`).
  - Model downloads are pinned to exact versions.
- **Global hotkeys** (`hotkeys.py`). Hold `Ctrl+Alt+D` to talk, `Ctrl+Alt+Space` to toggle, Esc to cancel. Uses its own low-level keyboard hook.
- **Typing into any app** (`insertion.py`).
  - Pastes by default, with slow typing as a fallback.
  - Restores the clipboard afterwards.
  - Never pastes into a different window if focus moved.
- **Recording** (`audio.py`). Kept in memory only and never saved. Has a maximum length and an optional stop after a pause.
- **Desktop app** (`voicetype/ui/`).
  - Tray icon and a floating status pill that never steals focus.
  - Home, History, Models and Settings pages; first-run wizard; dark and light themes.
- **Text processing** (`textproc.py`). Exact and Clean modes (Clean removes um/uh), plus custom vocabulary.
- **History** (`history.py`). Search, copy, export, and deletion that really erases the data.
- **Packaging.** `scripts/build_exe.ps1` builds `dist\VoiceType\VoiceType.exe`; `--selftest` mode.
- **Docs:** README, privacy, architecture, status, testing, decisions, REA findings, requirements.

### Fixed during the build
- Notepad garbled fast typing, so pasting became the default.
- The `keyboard` library left modifier keys stuck, so it was replaced with an own hook.
- The hold hotkey clashed with the real Wispr Flow. It moved from `Ctrl+Win` to `Ctrl+Alt+D`, and the letter no longer leaks into the app.
- Vocabulary hints made Whisper invent text, so that option is now opt-in.
- Two transcriptions could run on one model at once after a cancel. They now run one at a time.
- The `.exe` bundled the wrong OpenSSL, so the build now uses a clean PATH.

### Tested
- 54 automated tests pass.
- Real Notepad 7/7, Edge 7/7, hotkeys 7/7, recorder 8/8 (no leaks over 20 cycles), UI 5/5, end to end 13/13.
- 0 network connections while dictating; pip-audit clean.
- Delay: 0.5–0.6 s warm; 5.7 minutes of audio transcribed in about 8–10 s.

### Still open at v1.0
- Physical key presses, real voice accuracy, other languages, unplugging the mic mid-recording.
- Chrome and other apps.
- The `.exe` on another PC.

---

## v0 · 2026-10-20 (morning)
**Theme:** Tooling and planning. No app code yet.
- Set up REA (reverse-engineering toolkit) for Claude Code: MCP server and skill registered.
- Wrote the master build prompt and the looping checklist (`docs/CHECKLIST.md`). The rules include: read-only analysis of the installed Wispr Flow, no copying of its code, nothing destructive, and no admin rights.

---

## Template for the next version
```
## vX.Y · YYYY-MM-DD (time of day)
**Theme:** one line
**Why:** what prompted it
**Built:** HH:MM–HH:MM · **Checklist:** items

### Added
### Changed
### Fixed
### Tested
### Still open at vX.Y
```
Use a minor number (v2.1) for fixes and small additions, and a major number (v3.0) for a new feature area. Also add a row to the work log in [PROJECT_REPORT.md](PROJECT_REPORT.md).
