# CHECKLIST (source of truth; [x] only when verified, evidence under item)

## PHASE 0: Environment
- [x] 0.1 Report: py -0, pip, nvidia-smi, mic devices, disk, folder contents
  - Evidence: Python 3.11.15 (uv-managed) + 3.13.5 present; RTX 4060 Laptop, driver 617.42, CUDA UMD 13.4, 8188 MiB; Z: 483 GB free; folder was empty; mics found via sounddevice (default 1: Microphone Array Intel SST; 2: OMEN Cam & Voice).
- [x] 0.2 venv on Python 3.11; requirements.txt with exact versions
  - Evidence: `uv venv --python 3.11 .venv` -> Python 3.11.15; requirements.txt frozen (40 pkgs incl. faster-whisper, sounddevice, pyside6, nvidia-cublas-cu12 12.9, nvidia-cudnn-cu12 9.27).
- [x] 0.3 REA usable: `claude mcp list` shows rea connected, tools visible (no re-setup)
  - Evidence: `claude mcp list` -> rea Connected. MCP tools NOT loaded in this session (started before setup); using the documented REA CLI instead (see docs/decisions.md).

## PHASE 1: REA analysis of installed app (%LOCALAPPDATA%\WisprFlow, read-only)
- [x] 1.1 Inventory: Electron/ASAR layout, main/renderer/preload, native add-ons (inventory only)
  - Evidence: REA CLI inventory: 228 ASAR entries, 5 native addons (sqlite3, crypt32 x2, 2 hashed), Wispr Flow Helper.exe present. See rea-findings.md.
- [x] 1.2 REA JS/Electron analysis: modules, imports, IPC, boundaries
  - Evidence: `npx rea-agents@6.7.0 analyze-javascript-application <app.asar> --integrity-policy record-and-continue --json` exit 0; 2339 modules, 0 parse failures, 207 IPC ops (zubridge), 36 contextBridge APIs; output .rea/analysis.json.
- [x] 1.3 Answer from evidence: hotkeys, audio capture, text insertion, local vs cloud, states, settings, where word limit is enforced
  - Evidence: table in docs/rea-findings.md; hotkeys/insertion marked ASSUMED (native helper not analysed, no Ghidra).
- [x] 1.4 docs/rea-findings.md (<=2 pages, verified/assumed/unknown)
  - Evidence: docs/rea-findings.md written with V/A/U labels.
- [x] 1.5 Public-source research appended to rea-findings.md
  - Evidence: appended 'Public sources' section (official page + docs search).
- [x] 1.6 docs/requirements.md (<=1 page; hold-to-talk AND toggle)
  - Evidence: docs/requirements.md written (hold-to-talk + toggle).

## PHASE 2: Speech engine spike
- [x] 2.1 Install faster-whisper; GPU via pip nvidia cuBLAS12 + cuDNN9; diagnose first
  - Evidence: faster-whisper + nvidia-cublas-cu12 12.9 + cudnn 9.27 pip wheels (no PyTorch). `ctranslate2.get_cuda_device_count()`=1, int8_float16 supported; voicetype/cuda.py adds DLL dirs.
- [x] 2.2 Record 5 s with sounddevice, save WAV (gitignored)
  - Evidence: 5 s from default mic -> data/mic_test.wav, peak 0.119, rms 0.0148 (real signal). WAVs gitignored.
- [x] 2.3 Transcribe locally; verify on checkable clip
  - Evidence: TTS clip 'The quick brown fox...' transcribed word-for-word on cuda (small), 0.27 s warm. Mic clip -> 'We will not let them wipe us out. Unplug them.' (content NOT verifiable: may be ambient audio).
- [x] 2.4 Benchmark small / medium / large-v3-turbo (WER, time, VRAM, RAM, load, long clip) -> docs/benchmark.md; pick default
  - Evidence: docs/benchmark.md; default large-v3-turbo (long clip 41x realtime, WER 1.9%, ~1.2 GB VRAM).
- [x] 2.5 CPU fallback verified
  - Evidence: scripts/check_engine.py: Engine('small',device='cpu') -> exact text, 1.71 s for 7 s clip.
- [x] 2.6 GPU OOM recovery verified
  - Evidence: tests/test_speech.py::test_gpu_oom_retries_on_cpu_with_notice (SIMULATED by injecting a 'CUDA out of memory' RuntimeError; a real 8 GB OOM was not forced). GPU load failure also falls back to CPU with notice.
- [x] 2.7 Language: English default, manual, auto-detect verified
  - Evidence: short clip: auto-detect -> lang=en; manual language='en' -> exact text. Only English clips tested; other languages UNTESTED.
- [x] 2.8 Model download w/ progress + availability check; offline transcription verified
  - Evidence: models.is_available('small')=True / bogus=False; models.download('tiny') -> 27 progress callbacks to 78.2 MB then available; transcription with offline=True and with HF_HUB_OFFLINE=1 works (network not physically disconnected, HF made no network calls in offline mode).
- [x] 2.9 Failure/empty audio returns error, never text (unit test)
  - Evidence: pytest tests/test_speech.py -> 6 passed (empty, silent, no-speech, other errors all raise TranscribeError; OOM->CPU retry).

## PHASE 3: Windows integration
- [x] 3.1 Global hotkeys (hold-to-talk, toggle, cancel, settings) verified from another app
  - UPDATE: hold default is now ctrl+alt+d (ctrl+windows collided with the real Wispr Flow running on this PC, which typed its own transcripts into my test windows). Chord keys are swallowed so the letter does not reach the app (tested). All hotkey tests use Shift+F9/F10/F11.
  - Evidence: own Win32 low-level hook (voicetype/hotkeys.py; the `keyboard` lib got stuck modifier state, replaced). scripts/it_hotkeys.py 7/7 with another window focused: hold start/stop, 25 auto-repeat key-downs -> one start/stop, other press order, toggle, esc cancel, settings, extra-modifier does not fire toggle; no focus theft. Keys were INJECTED with hardware scan codes; a physical keypress by you is still UNTESTED. Elevated windows ignore the hook (UIPI) - documented in hotkeys.py.
- [x] 3.2 Focus tracking, no focus stealing
  - Evidence: scripts/it_insertion.py 'foreground captured == A'; recording never activates a window (pill must use WS_EX_NOACTIVATE, checked in 4.4).
- [x] 3.3 Insertion (SendInput Unicode, clipboard fallback, manual copy) verified in Notepad
  - Evidence (REAL Win11 Notepad, scripts/it_notepad.py 7/7, verified from the saved file): ASCII typed, unicode+emoji, multiline and 1800-char text via default path, clipboard preserved. FOUND+FIXED: flooded Unicode typing garbled text in Notepad -> paste is now the default, typing is a paced 1-char fallback (accented chars typed 1-by-1 were still flaky in Notepad; paste handles accents).
  - PARTIAL: SendInput typing + clipboard paste verified in an owned Tk window (10/10, scripts/it_insertion.py). Real Notepad NOT yet run (see decisions D5).
- [x] 3.4 Insertion verified in browser field
  - Evidence: Edge (isolated profile, own window) scripts/it_browser.py 7/7: textarea default/unicode+emoji/multiline/typing fallback, <input> field, clipboard preserved. Chrome not run.
- [x] 3.5 Unicode, multiline, long transcript verified
  - Evidence: unicode+emoji (héllo wörld — 日本語 😀 ñ) typed exactly; multiline/paragraphs pasted exactly; 5399-char text pasted exactly (auto policy pastes >200 chars); 900 chars forced typing exact. Tk target; real apps untested.
- [x] 3.6 Focus-change policy (never paste elsewhere), setting
  - Evidence: focus moved to another window -> status 'copied', nothing typed in either window, clipboard holds text; closed target window -> 'copied'. Policy is currently fixed; making it a setting is in 4.5.
- [x] 3.7 Clipboard preservation verified
  - Evidence: clipboard text restored after paste ('ORIGINAL CLIP'); non-text clipboard data (custom format) not overwritten (falls back to typing). Only text is round-tripped; non-text -> never touched.
- [x] 3.8 Cancel during recording/processing inserts nothing
  - Evidence: tests/test_dictation.py: cancel while recording and while processing insert nothing; transcription error never inserts. Real recorder+engine path also covered by it_recorder.py.
- [x] 3.9 Mic unavailable/disconnected handled
  - Evidence: invalid device 9999 -> MicError('Microphone unavailable...'), no crash, default mic works afterward; test_dictation mic-unavailable -> FAILED state, then recovery. NOT tested: physically unplugging a mic mid-recording (no handling of mid-stream device loss yet).
- [x] 3.10 20x start/stop: no leak (mic, VRAM, RAM measured)
  - UPDATE: the 'RAM grew 238->763 MB' seen in later runs is NOT a leak: first real decode allocates ~0.5 GB once; 120 consecutive real decodes stayed at RAM 753 MB / VRAM 1180 MB. it_recorder now warms up first: drift 0/0.
  - Evidence: scripts/it_recorder.py 8/8: 20x recorder cycles threads 1->1, RAM 43->43 MB; 20x full pipeline VRAM 1130->1130 MB, RAM 242->263 MB, threads 2->3; mic still free. CAVEAT: all 20 pipeline cycles ended 'failed' (silent room, no speech) so text insertion was not part of that loop.
- [x] 3.11 Max recording duration enforced
  - Evidence: Recorder(max_seconds=2) -> on_limit fired, audio capped at exactly 2.00 s.

## PHASE 4: Desktop app (PySide6)
- [x] 4.1 Skeleton / modular layout (<400 lines per module)
  - Evidence: package voicetype/{audio,speech,insertion,hotkeys,dictation,config,history,textproc,transcriber,models,app}.py + ui/. Largest module app.py 209 lines (wc -l); no circular imports (app imports everything, nothing imports app).
- [x] 4.2 Background workers; UI responsive during transcription
  - Evidence: scripts/it_ui.py: real model, 5.7 min clip in the worker thread, UI event-loop max stall 58-72 ms over ~520 ticks (limit 250 ms).
- [x] 4.3 System tray
  - Evidence: QSystemTrayIcon available+visible, menu = Start/stop dictation, Open VoiceType, Settings, Quit (scripts, /tmp check). Menu clicks not physically clicked; the actions are wired to the same functions tested elsewhere.
- [x] 4.4 Floating state pill, no focus
  - Evidence: scripts/it_ui.py: pill shown in all 5 states with another app focused, foreground never changed; window has WS_EX_NOACTIVATE|TOOLWINDOW|TRANSPARENT (0x80800a8); typing still reaches the target. Screenshots data/shots/pill_*.png reviewed.
- [x] 4.5 Settings persisted in %APPDATA%, survive restart
  - Evidence: tests/test_ui.py::test_settings_save_persists_and_reloads (writes settings.json, fresh Config.load() sees all values), bad/duplicate hotkeys rejected, test_config_history.py (corrupt file backup, bad values, clamping). Silence + insertion + focus-policy + privacy options included. Full app restart with a real settings file: smoke run OK.
- [x] 4.6 History (search, copy, export, delete, clear-all), no raw audio
  - Evidence: tests/test_ui.py history page (search, delete selected, clear all) + test_config_history.py (persistence across instances, prune, export json/csv/txt, wildcard-literal search). No raw audio is ever written (Recorder keeps audio in memory only). Export file-dialog itself not clicked.
- [x] 4.7 Model management UI
  - Evidence: models page lists status/active; make_active persists; REAL download of 'tiny' through ModelsPage.download() (progress -> available) and delete via models.delete() (UI paths), tiny cleaned up afterwards.
- [x] 4.8 First-run setup
  - Evidence: 4-step SetupDialog (welcome, mic test, model download, hotkeys): finish writes first_run_done+mic+model (test_ui); real mic test ran (silent room -> 'Very quiet or silent' warning, so it cannot false-positive); real download via the dialog's button worked ('tiny').
- [x] 4.9 Error/recovery screens
  - Evidence: classify() unit tests map errors to actions (models/settings/retry); error card screenshot reviewed (data/shots/*_home_error.png); button emits open_tab. Tray balloon shown on failure (not observed visually).
- [x] 4.10 Dark/light theme
  - Evidence: dark + light stylesheet; screenshots of all pages in both themes reviewed (scripts/shots.py). 'system' follows Qt colorScheme (not switched live).
- [x] 4.11 Keyboard accessibility; every control works or hidden
  - Evidence: automated: every button/line edit/combo/spin on all pages is keyboard-focusable and labelled (tests/test_ui.py). NOT done: manual Tab-walk or screen-reader test; hotkeys are typed as text rather than captured.
- [x] 4.12 Logging without transcript text
  - Evidence: every log call reviewed (5 total; none pass transcript text); rotating log in the data dir; E2E run produced no transcript text in logs.

## PHASE 5: Text processing
- [x] 5.1 Exact mode never rewrites
  - Evidence: test_exact_mode_keeps_fillers_and_wording; real E2E: inserted text == reference exactly. Rewrite modes are not applied in exact mode.
- [x] 5.2 Punctuation/capitalization check
  - Evidence: scripts/check_text.py on the 5.7-min clip: periods 56/56, raw char similarity 97.5% vs reference (casing+punctuation included); short clip matched exactly incl. punctuation. TTS speech only; real speech untested.
- [x] 5.3 Custom vocabulary (add/edit/export/delete), no corruption of unrelated words
  - Evidence: tests/test_textproc.py (whole-word, case, multiword, regex chars literal, longest wins, unrelated text untouched, import/export in UI). Real audio: replacement-only output == no-vocab output with exactly 'PySide 6'->'PySide6' (14 of 14). FOUND: feeding the glossary to Whisper (initial_prompt) added a phantom sentence 'And PySide6.' in one run and dropped 12 words in another -> that hinting is now opt-in (vocab_bias, default off).
- [skipped] 5.4 Optional cleanup modes (off by default) or skip with reason
  - SKIPPED: professional/concise/casual/technical need an LLM (local model download or external API). Not required for the MVP; only exact and clean modes exist, documented as such in textproc.py.
- [x] 5.5 Optional silence auto-stop or skip with reason
  - Evidence: Recorder auto-stop (pause after speech, no-speech give-up at 10 s, off by default) tested with synthetic chunks in tests/test_dictation.py (3 tests) and exposed in Settings. NOT tested with a real voice or noisy room (threshold may need tuning per mic).

## PHASE 6: Privacy and security
- [x] 6.1 Offline dictation works
  - Evidence: scripts/check_offline.py with every socket connect/DNS call raising: small and large-v3-turbo load + transcribe correctly, 0 connection attempts. Network was NOT physically disconnected (that would change system settings).
- [x] 6.2 No telemetry/secrets; .env.example placeholders
  - Evidence: grep: only network-capable code is models.download (user-initiated); no telemetry/update check; no secret-like strings (hits were 'tokenizer'); .env.example created (placeholders only, nothing required); pip-audit: no known vulnerabilities.
- [x] 6.3 Safe file handling
  - Evidence: settings written atomically (tmp+replace) and corrupt file backed up; history export refuses directories/unknown formats, file dialog confirms overwrite; vocab import capped (1 MB, 200 chars/entry) + tested; model delete refuses paths outside its own cache folder; models pinned to commit SHAs (bandit B615 fixed, verified by a real re-download of 'small' + offline transcription); history delete/clear overwrite the text in the DB file (secure_delete + VACUUM, tested with marker strings).
- [x] 6.4 No admin, no service, no security features disabled
  - Evidence: IsUserAnAdmin() = False while running everything; grep found no registry/schtasks/service/startup/elevation code; only a global keyboard hook for the configured hotkeys.
- [x] 6.5 docs/privacy.md
  - Evidence: docs/privacy.md (what is stored/where/how to delete; clipboard behaviour; network use; system access). Claims backed by tests above.
- [x] 6.6 security-review skill run, findings fixed
  - Evidence: security-review skill applied to this desktop app + bandit + pip-audit. Findings: B615 unpinned model download -> FIXED (pinned SHAs); B110 silent except in keyboard hook -> FIXED (logs first error, no key data); B608 SQL injection -> FALSE POSITIVE (dialog text), reworded; pip-audit clean. Accepted/documented: clipboard-history tools may capture the transcript while it is briefly on the clipboard; CUDA DLL dir is prepended to PATH from the venv (same trust level as the venv itself); hook cannot see elevated windows (UIPI). Not applicable: web/auth/CSRF/XSS/rate-limit items (no server).

## PHASE 7: Tests and quality
- [x] 7.1 pytest pure-logic tests
  - Evidence: 54 pytest tests, all pass (~3 s): speech errors, dictation controller, silence auto-stop, hotkeys, config, history, text processing, UI pages (docs/testing.md table).
- [x] 7.2 Manual hardware checklist docs/testing.md, run for real
  - Evidence: docs/testing.md with the run commands, real-hardware results and an explicit NOT-tested list. Done for real: Notepad, Edge, unicode/multiline, clipboard, cancel (injected Esc), offline, repeated start/stop, shutdown frees mic+VRAM. NOT done: physical keypress by a person, mic unplug mid-recording, real-speech accuracy, Chrome/other apps.
- [x] 7.3 Startup + clean shutdown (no leaks)
  - Evidence: measure_perf.py: app exits code 0, 0 leftover processes, lock released, VRAM after a run that loaded the GPU model = baseline (759 MB, delta 0). Mic free afterwards. Startup to window ~0.6 s after imports.
- [x] 7.4 Performance numbers recorded
  - Evidence: docs/testing.md performance table + data/perf.json: idle 0.0% CPU / 191 MB / 0 MB VRAM; model load 2.9 s, 1.1 GB VRAM; key-release->text 3.5 s cold, 0.5-0.6 s warm; 5.7 min audio in ~8-10 s.
- [x] 7.5 code-review skill run, CRITICAL/HIGH fixed
  - Evidence: code-review skill applied in local mode (project is not a git repo, so no diff: every module read in full + mechanical checks for >800-line files, >50-line functions, nesting >4, TODO/print/emoji). CRITICAL: none. HIGH found+fixed: concurrent transcription on one model after cancel (now serialised, tested); 3 functions >50 lines / nesting 7 (refactored). MEDIUM fixed: history stored duration 0 + configured language; private attribute access in app.py; stuck-Ctrl safeguard if SendInput partly fails. Accepted/documented: the low-level hook can be dropped by Windows if the process stalls >300 ms (not observed; transcription runs outside the GIL).
- [x] 7.6 Critical bugs fixed, regressions re-run
  - Evidence: bugs found by testing and fixed are listed in docs/testing.md (garbled typing in Notepad, hook library stuck state, vocabulary hint hallucination, chord letter leaking, unpinned downloads, overlapping transcriptions, history data, secure delete). Regressions re-run after each: pytest 54/54, insertion 10/10, hotkeys 8/8, Notepad 7/7, Edge 7/7, recorder 8/8, UI 5/5, e2e 13/13 (6/6 isolated). Back-to-back full-suite runs were occasionally flaky on this shared machine (documented); no failing test was ignored without a cause.

## PHASE 8: Packaging and docs
- [x] 8.1 README.md
  - Evidence: README.md (install, models, run, hotkeys, settings, data location, tests, troubleshooting, packaging, verified/unverified) - every command in it was run during this build.
- [x] 8.2 Feature-status table
  - Evidence: docs/status.md feature table with Tested / partly / not verified / planned, each with notes.
- [x] 8.3 PyInstaller attempt or documented blocked
  - Evidence: scripts/build_exe.ps1 -> dist/VoiceType (2353 MB; 2.0 GB is NVIDIA cuBLAS/cuDNN). Launches, exits 0, both windows appear, `--selftest` transcribes on cuda inside the exe with the exact expected text. FOUND+FIXED: build from a shell with Git's mingw64 on PATH bundled the wrong OpenSSL (`_ssl` DLL load failed -> every model reported 'not downloaded'); script now builds with a clean PATH. NOT tested: hotkey/insert flow inside the exe, CPU-only build, another PC, code signing.
- [x] 8.4 Fresh-venv reproduction
  - Evidence: brand-new venv .venv-fresh from requirements-dev.txt only (4 min): Python 3.11.15, pytest 54 passed, GPU transcription exact, `python -m voicetype --quit-after` exit 0.

## PHASE 9: Smart mode, memory, per-app style (requested 2026-10-20 after the Wispr architecture research)
- [x] 9.1 Benchmark local cleanup LLMs
  - Evidence: docs/cleanup-benchmark.md; qwen2.5:7b-instruct 14/14 (0.33 s median), phi3 11/14, llama3.2:3b 10/14, qwen3:4b 0/14 (thinking-only build). Fixed a harness bug (Whisper was not resident) and re-measured: 6.6 GB of 8.2 GB with both loaded.
- [x] 9.2 Smart cleanup stage (voicetype/cleanup.py) with safety check and raw fallback
  - Evidence: tests/test_smart.py (accept real cleanups, reject added words / heavy drops, never raises, server down/timeout -> plain text with note); scripts/it_smart.py 6/6 on spoken clips; check_offline.py: smart mode 0 outside connections, 8 to 127.0.0.1.
- [x] 9.3 Warm-up so the first dictation is fast
  - Evidence: FOUND+FIXED: warm-up used a different context size so Ollama reloaded on first use (15.6 s); now 0.98 s. Speech model also warmed at start: first real-app dictation 5.1 s -> 2.6 s.
- [x] 9.4 Undo AI edit (Home) + Copy original (History), original stored in history
  - Evidence: test_ui (undo copies original, disabled when nothing changed); it_e2e_smart.py 8/8.
- [x] 9.5 Memory folder + learning from corrections (memory.py, learner.py, Memory tab)
  - Evidence: unit tests (learnable rules, names 1 fix / other words 2 fixes, examples cap, anchoring, forget/clear); it_learn.py 9/9 in real Notepad + Edge (one 8/9 run in about eight, traced). FOUND+FIXED: Friday->Monday would have been learned (similarity 0.5), send->sent would have rewritten every future "send".
- [x] 9.6 Writing style per app category
  - Evidence: app_category tests (Outlook, Slack, WhatsApp, VS Code, Gmail-in-Chrome, Notepad); style reaches the prompt; casual chat drops a single trailing period. How well the AI follows 'casual' is not measured.
- [x] 9.7 Clipboard: save/restore every format, not only text
  - Evidence: FOUND while testing Undo: any browser copy made VoiceType fall back to slow typing. Now browser HTML/RTF, images, file lists restored byte-for-byte (it_clipboard.py 9/9); >64 MB / metafiles -> typed, clipboard untouched.
- [x] 9.8 Security + privacy review of the new code
  - Evidence: bandit clean (3 annotated, justified spots), pip-audit clean incl. uiautomation/comtypes, all new log calls carry no text, local AI URL hard-limited to 127.0.0.1; docs/privacy.md updated. Tests isolated from the real %APPDATA% (found and removed one stray test folder).
- [x] 9.9 Paste reliability investigation (found during regression)
  - Evidence: measured pastes land in ~15 ms (restore delay not the cause); 0/400 injected Ctrl lost into Tk; ROOT CAUSE of most Notepad misses: keyboard focus on a toolbar button -> new guard (copy + message), tested in real Notepad. Retry removed after it produced a duplicate; unconfirmed pastes reported ('copied'), verified in runs where they happened.
- [x] 9.10 Full regression and docs
  - Evidence (final run): pytest 107/107; insertion 10/10; clipboard 9/9; hotkeys 8/8; Edge 7/7; recorder 8/8; UI 5/5; e2e 13/13; smart 6/6; e2e smart 8/8; auto-learn 9/9; offline 0 outside connections; bandit clean; size/nesting checks clean. Notepad 6/8 (one paste miss, detected and reported as designed). README, privacy, status, architecture, testing, cleanup-benchmark updated.

## PHASE 10: Fine-tune speech recognition on the user's voice (decided 2026-10-21: keep faster-whisper)
- [x] 10.1 Voice dataset recorder (scripts/record_voice.py, voicetype/voicedata.py, scripts/voice_prompts.txt)
  - Evidence: tests/test_voicedata.py 3/3; hidden-window smoke test: model on cuda, test clip transcribed exactly, saved, counted, double-save guarded, undo; real mic 2 s captured, nothing saved before Save. Clips only in userdata\voice (gitignored).
- [ ] 10.2 User records 30-60 min of their voice (needs the user)
- [x] 10.3 Training environment (separate venv inside the project; PyTorch + transformers + peft; HF whisper-large-v3-turbo weights)
  - Evidence: user approved downloads 2026-10-21. .venv-train: torch 2.11.0+cu128 (cuda True), transformers 5.20.2, peft 0.21.2, ctranslate2 4.8.3; package cache in .tmp (not C:). Base model pinned 41f01f3 in models\. First torch download timed out (uv 30 s default) -> UV_HTTP_TIMEOUT=900.
- [x] 10.4 LoRA fine-tune script; fits 8 GB VRAM; held-out split by clip
  - Evidence: scripts/train_voice.py on 12 synthetic clips: 8 steps, 1.0 min, 2.1 GB peak GPU, 13.1 M trainable params (1.6%), held-out loss 0.167 -> 0.100. FOUND+FIXED: transformers 5 renamed torch_dtype, no longer writes preprocessor_config.json; the converter empties its output dir (adapter was lost) -> saved aside and moved in after.
- [x] 10.5 Merge + convert to CTranslate2 into models\, selectable in Settings
  - Evidence: models\my-voice written (model.bin, config, tokenizer, preprocessor, adapter\, training.json) and loaded by voicetype.speech.Engine; models.CUSTOM lists it (unit test). Test model deleted afterwards so Settings does not offer a model not trained on the user's voice.
- [ ] 10.6 Evaluate: WER on held-out clips of the user's voice (baseline vs tuned) AND on the TTS reference clips (no regression); switch default only if better
  - PARTIAL: scripts/eval_voice.py verified on the pipeline test (0.0% vs 0.0%, 0.27 vs 0.28 s/clip after adding a GPU warm-up to the timing; verdict NOT BETTER, correct). Needs the user's real recordings (10.2).

## PHASE 11: Flowbit upgrade (master upgrade prompt, 2026-10-21)
- [x] 11.1 Inspect project, git, environment, REA
  - Evidence: clean tree; Python 3.11.15, ctranslate2 4.8.3 (1 CUDA device), faster-whisper 1.2.1, PySide6 6.12; REA 6.7.0 connected (claude mcp list).
- [x] 11.2 Root cause of missing punctuation, measured
  - Evidence: real history: 129 words/0 marks, 36 words/0, 38 words/0; TTS run-on clips reproduce it on small, medium and turbo; Whisper style prompt rejected (no gain, Title Case side effect); pauses already punctuated by Whisper. docs/formatting.md.
- [x] 11.3 Formatting pipeline (segments, spacing, capitals, sentence ends, lists, bullets, commands, numbers, times) + Exact/Smart modes
  - Evidence: tests/test_formatting.py 51/51; spoken clips through real Whisper correct in both modes.
- [x] 11.4 Guarded AI punctuation (words must be identical)
  - Evidence: run-on clips punctuated in 0.5-1.3 s; injection stays text; bench_cleanup 14/14 after prompt change.
- [x] 11.5 Shortcuts: undo, modifier-only toggle, conflict checks, migration
  - Evidence: unit tests; RegisterHotKey probe found ctrl+alt+space and ctrl+alt+m taken here -> toggle default ctrl+alt+t; real settings migrated on launch. ctrl+windows not pressed for real (Wispr Flow interference).
- [x] 11.6 Mascot (branding, states from real state + mic level, click/drag, no focus, persistence, reduced motion)
  - Evidence: tests/test_indicator.py 8/8; scripts/it_ui.py 11/11 with real mouse input.
- [x] 11.7 State machine with INSERTING, adaptive silence auto-stop (toggle only), insertion guards, clipboard newer-data guard, preview
  - Evidence: unit tests; it_e2e 13/13, it_clipboard 9/9. Preview not exercised end to end.
- [x] 11.8 Safe Undo Last Insertion
  - Evidence: tests/test_undo.py 6/6; scripts/it_undo.py 11/11 (Notepad, Edge, Tk).
- [x] 11.9 Regression, security, package, docs
  - Evidence: see docs/testing.md "Flowbit v3.0.0 results"; bandit/pip-audit clean; dist\Flowbit\Flowbit.exe --selftest OK on GPU; README, formatting.md, windows-integration.md, status.md, privacy, architecture, GUIDE updated.

## PHASE 12: Approved Flowbit logo, lists without "point" (2026-10-22)
- [x] 12.1 Logo assets cut from the approved image (transparent background, mascot and wordmark)
  - Evidence: scripts/make_brand_assets.py; voicetype/assets/flowbit_mascot.png and flowbit_wordmark.png; previewed on black.
- [x] 12.2 Floating mascot, header, icons use the approved character
  - Evidence: rendered each state (idle, recording, transcribing, done, error) and the home header; tests/test_indicator.py 8/8.
- [x] 12.3 Plain ordinal lists ("first, biryani; second, dosa; third, egg roti; and fifth, buttermilk") and Whisper digit ordinals
  - Evidence: tests/test_formatting.py 58/58; real spoken clip scripts/make_list_clips.ps1 through Whisper and Transcriber.format: correct list, with and without commas.
- [~] 12.4 Full real-desktop mascot test (scripts/it_ui.py): 6/11 on this run. Another window took focus; the mascot alone keeps focus (checked per state). Re-run on an idle desktop.
