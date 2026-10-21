# Flowbit (formerly VoiceType): Version History

Each version records what was built, what changed since the previous version, the files involved, how it was tested, and what was still open at that point. Newest version first. Never edit or delete an old entry; add a new version on top instead.

| Version | Date | Theme |
|---|---|---|
| [v3.0.0](#v300--2026-10-21) | 2026-10-21 | **Flowbit**: formatting pipeline, mascot, safe undo, shortcut checks |
| [v2.2.1](#v221--2026-10-21) | 2026-10-21 | Fine-tuning pipeline verified end to end; data moved off C |
| [v2.2.0](#v220--2026-10-21) | 2026-10-21 | Moving logo while recording, dashboard, new README, fine-tuning scripts |
| [v2.1.0](#v210--2026-10-21) | 2026-10-21 | Fine-tuning step 1: record a dataset of my voice |
| [v2.0.4](#v204--2026-10-21) | 2026-10-21 | Text export readable in Notepad, with original wording |
| [v2.0.3](#v203--2026-10-21) | 2026-10-21 | CSV export includes the original wording |
| [v2.0.2](#v202--2026-10-21) | 2026-10-21 | Everything stays in the project folder (nothing on C) |
| [v2.0.1](#v201--2026-10-21) | 2026-10-21 | Published on GitHub (MIT), hands-on test sheet |
| [v2.0](#v20--2026-10-20-evening) | 2026-10-20, evening | Smart mode, memory that learns, styles per app |
| [v1.1](#v11--2026-10-20-early-evening) | 2026-10-20, early evening | Language test tool and Wispr Flow research (no app changes) |
| [v1.0](#v10--2026-10-20-afternoon) | 2026-10-20, afternoon | First working app: local dictation into any window |
| [v0](#v0--2026-10-20-morning) | 2026-10-20, morning | Tooling and plan, before any code |

---

## v3.0.0 · 2026-10-21: Flowbit
**Theme:** The master upgrade prompt. Rename to Flowbit, fix the transcription quality problems, and add a floating mascot, safe undo and reliable shortcuts.
**Why:** Punctuation, lists and numbers were wrong. I couldn't see when it was recording. There was no undo. Shortcuts could clash with other apps.

### Found by measuring (before changing anything)
- **Missing punctuation is a recogniser problem.** In my real history, Whisper returned long dictations with **0 punctuation marks** (129 words in one case). Test speech reproduced it on every model size. A style prompt didn't help.
- **`Ctrl+Alt+Space` (the old toggle) is registered by another program on this PC**, and so is `Ctrl+Alt+M`.
- **A comment had swallowed the "hidden window" flag**, so Ollama started with a visible console.

### Added
- **Formatting pipeline** (`voicetype/formatting.py`). Segment joining at real pauses, spacing, capitals, sentence ends, careful questions, numbered lists from explicit cues, bullets, "new line" and "new paragraph", and context-aware numbers and times. It's rule-based, tested on 51 cases, and works without any AI.
- **Exact Transcription / Smart Formatting** modes, with switches for numbers, spoken commands, AI punctuation and AI cleanup.
- **AI punctuation pass** (`cleanup.punctuate`). Only punctuation and capitals may change; it's rejected if any word differs.
- **Flowbit mascot** (`voicetype/ui/mascot.py`):
  - Vector art in black and orange.
  - Click to start or stop, drag to move, right-click for a menu.
  - Never takes focus.
  - The sound waves follow the real microphone.
  - States: idle, recording, transcribing, inserting, done, error.
  - Opacity, show-when-idle and reduced-motion settings; the position is remembered.
- **Undo Last Insertion** (`voicetype/undo.py`, `Ctrl+Alt+Z`). It deletes only after proving the window, the text box, the unchanged text and the exact selection.
- **Shortcut conflict checks** and a **modifier-only toggle** (for example `Ctrl+Win`).
- **INSERTING state**, and an **adaptive silence auto-stop** (toggle mode only) that says why it stopped.
- **Insertion guards:** never into Flowbit's own windows; focus restored from Flowbit windows; newer clipboard data kept.
- **Optional preview** before inserting.
- **Branding:** the Flowbit name, a `#0B0B0B` / `#FF7900` / `#F5F5F5` theme, the logo, and the mascot icon in the tray, window and `.exe`.
- **Docs:** `docs/formatting.md`, `docs/windows-integration.md`, a new `docs/status.md` (verified / incomplete / partial / planned / blocked), and the README rewritten for Flowbit.

### Changed
- Toggle default `Ctrl+Alt+Space` → `Ctrl+Alt+T` (migrated automatically). New Undo shortcut `Ctrl+Alt+Z`.
- Settings `cleanup_mode` / `show_idle_pill` migrated to `format_mode` / `ai_cleanup` / `mascot_visible`. The theme default is now dark.
- The local-AI prompt no longer invents lists, and it keeps line breaks. The benchmark still passes 14 of 14.
- Notepad tests close only their own tab (Windows 11 Notepad restores your tabs into every window). `np_helper.py`, which could kill Notepad, was deleted.

### Tested
- 186 automated tests pass.
- Real hardware: mascot 11/11 (real mouse), undo 11/11 (Notepad and Edge), full app 13/13, Smart in the full app 8/8, hotkeys 8/8, insertion 10/10, clipboard 9/9, Edge 7/7, recorder 8/8, spoken Smart clips 6/6, learning in Edge 3/3.
- 0 outside connections; bandit and pip-audit clean; the packaged `.exe` transcribes on the GPU.

### Still open at v3.0.0
- Physical key presses by a person on this version.
- `Ctrl+Win` pressed for real.
- Multiple monitors.
- The preview, and the hotkeys inside the `.exe`, run end to end.
- Accuracy on my real voice.
- Apps beyond Notepad and Edge.
- Without the AI, run-on speech still lacks commas.

---

## v2.2.1 · 2026-10-21
**Theme:** Prove the fine-tuning pipeline works, and compare the new model with the old one.

### Fixed (found by running it)
- transformers 5 renamed the `torch_dtype` option.
- transformers 5 no longer writes `preprocessor_config.json`, which the faster-whisper converter needs. It is now copied from the base model.
- The converter empties its output folder, which deleted the saved LoRA adapter. The adapter is now saved aside and moved in afterwards.
- The comparison timed the GPU's one-time warm-up as if it were model speed (14.7 s vs 0.28 s). It now warms up first (0.27 s vs 0.28 s).
- The first PyTorch download timed out (uv's 30-second default), so the timeout was raised.

### Tested: before vs after, on synthetic test clips
| | Base `large-v3-turbo` | Trained `my-voice` |
|---|---|---|
| Errors, held-out clip | 0.0% | 0.0% |
| Errors, reference English | 0.0% | 0.0% |
| Speed per clip | 0.27 s | 0.28 s |

- Training took 8 steps in 1.0 min, used 2.1 GB of GPU memory at peak, and trained 13.1 M parameters (1.6% of the model).
- The verdict was **NOT BETTER**, which is correct: the clips were synthetic and labelled by the base model itself, so there was nothing to learn. The test proves the pipeline works and that the tuned model doesn't get worse. A real gain needs my own recordings.
- The test model was deleted afterwards, so Settings never offers a "my-voice" model that wasn't trained on my voice.

### Changed
- My real data moved off C: 25 dictations, settings and learned words (verified), and the old C copies were deleted.
- The README and dashboard show the pipeline result.

---

## v2.2.0 · 2026-10-21
**Theme:** Make it obvious when it's recording, show how well it works, and make the GitHub page easy to understand.
**Why:** I couldn't tell when VoiceType was listening. I wanted a dashboard of the results, and a README anyone can follow.

### Added
- **Moving logo** (`voicetype/ui/pill.py`).
  - The small bar at the bottom of the screen is now a logo of 5 sound bars.
  - Idle: grey, small and still.
  - Recording: red, and the bars bounce with the live microphone level (`Recorder.level`, `Dictation.level()`), plus a gentle wave so it moves even during pauses.
  - Transcribing: amber wave. Done: green.
  - It only animates while active (30 frames a second), so it costs nothing when idle.
- **Dashboard** (`docs/DASHBOARD.md`).
  - Charts (SVG, light and dark) of the speed fixes, the speech and cleanup model choices, and tests per version.
  - Built from `docs/metrics.json` by `scripts/make_dashboard.py`.
  - Every bar has its value and a tooltip, and every chart has a data table.
- **New README**: short and plain, with an animated picture of the logo, a dashboard link and 3 references (Whisper, LoRA, faster-whisper). The old detailed README is now `docs/GUIDE.md`.
- **Fine-tuning steps 2 and 3** (`scripts/train_voice.py`, `scripts/eval_voice.py`).
  - LoRA training of whisper-large-v3-turbo, converted for faster-whisper into `models\my-voice`.
  - A before/after comparison on held-out clips and reference clips.
  - VoiceType lists `my-voice` once it exists.
  - **Not yet verified end to end** (the training packages were still downloading).
- Base model `openai/whisper-large-v3-turbo` (pinned version `41f01f3`) downloaded to `models\`. A separate `.venv-train\` is excluded from git.

### Tested
- 117 automated tests pass. New tests cover: the logo stays still when idle and moves while recording, louder means taller bars, the animation runs only while active, the live mic level, and the trained-model handling.
- Real-desktop UI check 5/5: the logo shows in all states, never takes focus, and typing still reaches the app underneath.
- The charts were rendered and checked with real fonts.

### Still open at v2.2.0
- Run the training pipeline end to end, then train on real recordings of my voice.

---

## v2.1.0 · 2026-10-21
**Theme:** Fine-tune speech recognition on my own voice. This is step 1 of 3: record, then train, then evaluate.
**Why:** I compared faster-whisper with openai/whisper and decided to keep faster-whisper. It uses about 1.2 GB of GPU memory against about 6 GB, which leaves room for the Smart-mode AI on an 8 GB GPU. The accuracy is the same, because both run the same models. The next improvement is a model fine-tuned on my voice.

### Added
- `scripts/record_voice.py`, a recording window.
  - It shows a sentence to read, records (F5), and shows what the current model heard.
  - I correct the text to exactly what I said, then save.
  - It also shows how often the current model gets my words wrong. That is the baseline to beat.
- `scripts/voice_prompts.txt`: 90 sentences. They are mixed with my own past dictations, so the dataset uses my real words.
- `voicetype/voicedata.py`: saves each clip (16 kHz WAV plus the confirmed text in `dataset.jsonl`), deletes the last clip, and computes the word error rate.
- Saved in `userdata\voice\`: on my PC only, excluded from git.

### Changed
- `docs/privacy.md` and the README explain that these training clips are saved on purpose. Normal dictation still never saves audio.

### Tested
- 111 tests pass (3 new: save and load, bad input rejected, word error rate).
- Window smoke test, run hidden with a temporary folder:
  - The model loads on the GPU.
  - A test clip is transcribed exactly, saved, and counted.
  - Pressing Save twice doesn't save twice, and undo deletes the clip.
  - A 2-second recording from the real microphone is captured, and nothing is saved until Save is pressed.

### Still open at v2.1.0
- Step 2 (training) and step 3 (evaluation) are not built yet.
- Training needs PyTorch, transformers and peft, plus the trainable version of `whisper-large-v3-turbo`: about 5 GB of downloads.

---

## v2.0.4 · 2026-10-21
**Why:** No Microsoft Office on this PC, so a CSV in Excel is no use. History has to be readable in Notepad.
### Changed
- History → Export → `.txt` now shows the time to the second, and adds "(you said: ...)" under any entry the AI cleaned up.
### Tested
- 108 tests pass. Exported 14 dictations to `userdata\history.txt`.

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
