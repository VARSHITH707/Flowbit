# VoiceType: Project Report

| | |
|---|---|
| Project | VoiceType, a private voice-typing app for Windows 11 (local replacement for Wispr Flow) |
| Location | Everything in `Z:\Wispr Flow`: code, `userdata\` (history, settings, memory, log), `models\` (speech models). Nothing on C: |
| Machine | Windows 11 laptop, RTX 4060 Laptop GPU (8 GB), Python 3.11 |
| Current version | **v2.1.0** (see [VERSION_HISTORY.md](VERSION_HISTORY.md)) |
| Repository | https://github.com/VARSHITH707/Unlimited-WisprFlow (public, MIT license) |
| Status | Working on this machine; first hands-on test passed. Next: improve and fine-tune the models |
| Last updated | 2026-10-21 |

## 1. Summary
Wispr Flow sends every recording to the cloud and limits free use to 2,000 words a week. I built VoiceType, which does the same job on the laptop itself. You hold a hotkey, speak, and release; the text appears wherever the cursor is, in any app. No account, no word limit, and no audio or text leaves the PC.

In two build rounds it went from nothing to:
- **v1.0:** local speech-to-text, global hotkeys, typing into any app, a desktop app with history and settings, and a standalone `.exe`.
- **v2.0:** a local AI that cleans up speech ("2, actually 3" becomes "3"), a memory that learns from my corrections, and a different writing style for each kind of app.

## 2. Work log
Add one row each time something is built or changed. Newest at the bottom.

| Date | Time | Where (folder / files) | What was done | Result |
|---|---|---|---|---|
| 2026-10-20 | morning | Claude Code config | Installed the REA reverse-engineering toolkit (MCP server + skill) | Connected and working |
| 2026-10-20 | morning | prompt only | Wrote the build plan and a looping checklist (`docs/CHECKLIST.md`) | Plan approved, build started |
| 2026-10-20 | 15:55–16:11 | `.venv`, `requirements.txt` | Phase 0: environment set up (Python 3.11, GPU check, mic check) | GPU and mics detected |
| 2026-10-20 | 16:11 | `docs/rea-findings.md`, `docs/requirements.md` | Phase 1: read-only analysis of my installed Wispr Flow (layout and behaviour only, no code copied) | Found it is cloud-only; requirements written |
| 2026-10-20 | 16:12–16:15 | `voicetype/speech.py`, `docs/benchmark.md` | Phase 2: local speech engine (Whisper), benchmarked 3 models | `large-v3-turbo` chosen: 1.9% error rate, 41× faster than real time |
| 2026-10-20 | 16:17–16:31 | `voicetype/insertion.py`, `hotkeys.py` | Phase 3: hotkeys and typing into other apps | Works in Notepad and Edge |
| 2026-10-20 | 16:35–17:02 | `voicetype/ui/` | Phase 4: desktop app (tray, status pill, settings, history, models, first-run wizard, dark/light) | All pages working |
| 2026-10-20 | 16:44–16:47 | `voicetype/textproc.py` | Phase 5: punctuation, filler removal, custom vocabulary | Tested |
| 2026-10-20 | 17:11–17:30 | `scripts/`, `tests/`, `docs/privacy.md` | Phases 6–7: privacy, security review, tests, performance | 54 tests pass; 0 network connections while dictating |
| 2026-10-20 | 17:38–17:46 | `scripts/build_exe.ps1`, `dist\VoiceType` | Phase 8: packaged `.exe`, README | `.exe` runs and transcribes on the GPU |
| 2026-10-20 | 19:17 | `scripts/try_language.py`, `docs/testing.md` | Tool for testing other languages by hand | Ready for manual testing |
| 2026-10-20 | 19:27 | `docs/wispr-architecture-research.md` | Online research on how Wispr Flow works (papers, blog posts, patents) | Design for the local version |
| 2026-10-20 | 19:40–21:51 | `scripts/bench_cleanup.py`, `docs/cleanup-benchmark.md` | Benchmarked 4 local AI models for cleaning up speech | `qwen2.5:7b` won, 14 of 14 cases |
| 2026-10-20 | 21:55–22:20 | `voicetype/cleanup.py`, `memory.py`, `learner.py`, `ui/memory_page.py` | Phase 9: Smart mode, Undo AI edit, memory folder, styles per app | Working on real speech clips |
| 2026-10-20 | 22:06–22:43 | `voicetype/insertion.py`, `scripts/it_clipboard.py` | Fixed clipboard handling and paste reliability (found during testing) | Clipboard restored exactly; failed pastes are now always reported |
| 2026-10-20 | 22:45–22:49 | `docs/` | Full retest and documentation update | 107 tests pass; all hardware suites pass |
| 2026-10-21 | — | `PROJECT_REPORT.md`, `VERSION_HISTORY.md`, `README.md` | Created this report and the version history; fixed two broken paths in the README | Done |
| 2026-10-21 | — | `docs/manual-test.md` | Hands-on test sheet (20 tests); first real run on my own voice | Working well enough for now; more tuning planned |
| 2026-10-21 | — | GitHub: [VARSHITH707/Unlimited-WisprFlow](https://github.com/VARSHITH707/Unlimited-WisprFlow), `LICENSE` | Published as a public repo under the MIT license. Only I and collaborators can change it; `main` is protected | Anyone can clone and use it |
| 2026-10-21 | — | `voicetype/__init__.py`, `config.py`, `models.py`, `pytest.ini`, `scripts/_projtmp.py`, `.gitignore` | Everything the project writes now stays in `Z:\Wispr Flow`: `userdata\` (history, settings, memory, log), `models\` (speech models), `.tmp\` (temporary files). All three are excluded from git. Shared programs (Python, Ollama) stay on C | 108 tests pass; offline check: 0 outside connections, models load from Z: |
| 2026-10-21 | — | `voicetype/history.py` | CSV export now includes the original wording; exported my history to `userdata\history.csv` | 13 dictations exported |
| 2026-10-21 | — | `voicetype/history.py` | Text export readable in Notepad (no Office on this PC): time to the second, plus the original wording | `userdata\history.txt`, 14 dictations |
| 2026-10-21 | — | decision | Compared faster-whisper and openai/whisper. **Decision: keep faster-whisper** (same accuracy, about 4× faster, 1.2 GB vs about 6 GB of GPU memory, so it fits next to the Smart-mode AI) | Next: fine-tune on my voice |
| 2026-10-21 | — | `scripts/record_voice.py`, `voicetype/voicedata.py`, `scripts/voice_prompts.txt` | Fine-tuning step 1: a recording window to build a dataset of my voice (90 sentences plus my own past dictations) | 111 tests pass; window tested with a real clip and the real mic |

## 3. What was delivered
| Deliverable | Where |
|---|---|
| Desktop app (source) | `voicetype/` |
| Standalone app (GPU build, 2.3 GB folder) | `dist\VoiceType\VoiceType.exe` |
| Automated tests (107) | `tests/` |
| Hardware test scripts (Notepad, Edge, hotkeys, clipboard, AI, learning) | `scripts/it_*.py` |
| User guide | `README.md` |
| Privacy statement | `docs/privacy.md` |
| What is and is not verified | `docs/status.md`, `docs/testing.md` |
| Design and research | `docs/architecture.md`, `docs/wispr-architecture-research.md`, `docs/rea-findings.md` |
| Benchmarks | `docs/benchmark.md` (speech), `docs/cleanup-benchmark.md` (AI cleanup) |
| Task checklist with evidence (71 done, 0 open) | `docs/CHECKLIST.md` |

## 4. Key numbers
| Measure | Result |
|---|---|
| Delay from releasing the key to seeing text | 0.5–1.6 s (first use after start: 2.6 s) |
| Speech recognition error rate (test audio) | 1.9% |
| AI cleanup accuracy (benchmark) | 14 / 14 |
| GPU memory (speech + AI together) | 6.6 of 8 GB |
| Network connections leaving the PC while dictating | 0 |
| Automated tests | 107 pass |
| Cost | No subscription; all models are free and run locally |

## 5. Problems found and fixed
- **Notepad garbled fast typing.** Switched to pasting, with slow typing as a fallback.
- **The hotkey library got stuck.** Replaced it with my own keyboard hook.
- **Clash with the real Wispr Flow, which reacted to my test keys.** Moved VoiceType's default hotkey and made the tests use keys Wispr ignores.
- **Vocabulary hints made Whisper invent a sentence.** That option is now off by default.
- **The `.exe` couldn't download models.** The build had picked up the wrong OpenSSL library; the build script now uses a clean PATH.
- **The AI was slow on the first dictation (15.6 s).** Fixed with a warm-up; it now takes 0.98 s.
- **The memory would have learned wrong rules** (Friday → Monday, send → sent). The learning rules are now stricter.
- **Text vanished when Notepad's focus was on a toolbar button.** VoiceType now detects this, copies the text, and tells the user.
- **After copying from a browser, VoiceType typed slowly.** It now saves and restores every clipboard format.
- **A paste retry caused duplicate text.** The retry was removed; a paste that can't be confirmed is reported instead.

## 6. Risks and open items
| Item | Status |
|---|---|
| Pressing the hotkeys by hand (tests used simulated keys) | Not yet tested by a person |
| Accuracy on my real voice and long dictations | Not yet tested (benchmarks used synthetic voices) |
| Languages other than English | Not tested; `scripts/try_language.py` is ready |
| Apps other than Notepad and Edge (Word, Slack, VS Code) | Not tested |
| Notepad misses about 1 paste in 15 under fast automated testing | Every miss is detected and the text is left on the clipboard |
| Running alongside Wispr Flow | The two apps need different hotkeys |
| `.exe` on another PC, and code signing | Not tested; Windows will warn because the `.exe` is unsigned |

## 7. Next steps
1. Hands-on test: dictate in Notepad, Word and a chat app, then correct a word and check the Memory tab.
2. Try a second language with `scripts/try_language.py`.
3. Decide whether to keep Wispr Flow installed; if so, set its hotkey to something other than `Ctrl+Alt+D`.

## How to keep this file updated
After every build or change:
1. Add a row to **section 2** with the date, time, files, what was done, and the result.
2. Update **sections 3–6** if deliverables, numbers or risks changed.
3. Change *Current version* and *Last updated* at the top.
4. Add the same change as a new version in [VERSION_HISTORY.md](VERSION_HISTORY.md).
