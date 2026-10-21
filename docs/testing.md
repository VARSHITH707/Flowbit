# Testing

Everything below was actually run on this machine (Windows 11, RTX 4060 Laptop 8 GB, Python 3.11.15). Counts are from the final runs.

## Flowbit v3.0.0 results (2026-10-21)

Every script was run one at a time on an idle machine. Running them next to a PyInstaller build, or straight after another script's windows, made Windows refuse to focus the test window, and every later check in that script then failed. Those runs were repeated, and the table shows the clean runs.

| What | Result |
|---|---|
| Automated tests (`pytest -q tests`) | **186 pass** (formatting 51, undo 6, mascot 8, hotkeys, state machine, silence, config migration ...) |
| `it_ui.py`: mascot with **real mouse input** | **11/11**: never takes focus in 6 states; real click starts/stops; real drag moves it (125% scaling); a drag is not a click; UI max stall 80 ms during 5.7 min of audio |
| `it_undo.py`: Undo in real Notepad and Edge | **11/11**: removes exactly its text; refuses after an edit, in another window, and in an app that hides its text (Tk) |
| `it_e2e.py`: the full app (hold, toggle, cancel, focus change, history, log) | **13/13** |
| `it_e2e_smart.py`: Smart mode in the full app (7-point list, Undo AI edit, history) | **8/8** |
| `it_hotkeys.py` | **8/8** |
| `it_insertion.py` | **10/10** |
| `it_clipboard.py` | **9/9** |
| `it_browser.py`: Edge textarea and input | **7/7** (now InPrivate, so the new-profile sync page doesn't steal focus) |
| `it_recorder.py` | **8/8** |
| `it_smart.py`: spoken clips through Whisper and the AI | **6/6** |
| `it_learn.py` | **Edge 3/3**. The Notepad part was skipped because the user had Notepad open (tests never touch it) |
| `check_offline.py` | **0** outside connections |
| `bench_cleanup.py` (qwen2.5 7B, after the prompt change) | **14/14** |
| Formatting pipeline on spoken clips (`make_format_clips.ps1`) | list, bullets, numbers, commands and run-on speech all correct (see formatting.md) |
| Packaged `dist\Flowbit\Flowbit.exe --selftest` | exit 0, GPU, correct transcript |
| bandit (medium and high), pip-audit | no findings, no known vulnerabilities |

**Bugs found by this round and fixed:**
- `cancel` hotkey crash (a state name left over from the refactor).
- The AI rewrote "First point …" so lists were lost. Explicit cues are now applied before the AI.
- The AI invented a numbered list from ordinary speech. The prompt and examples were changed, and the benchmark re-run.
- The AI turned "new line" into a paragraph break. Line breaks are now restored exactly.
- Undo race: a popup could take focus between selecting and deleting. Added a last-moment focus check.
- Ollama started with a visible console window (a misplaced comment).
- The build script's icon path was broken by escape characters.
- Notepad tests closed the whole Notepad window, which Windows 11 fills with the user's restored tabs. They now close only their own tab.

## Run it
```powershell
.\.venv\Scripts\python.exe -m pytest -q tests          # 186 unit/UI tests, ~15 s, no desktop windows (offscreen Qt)
# Integration scripts: real desktop, real model, real windows. Close other dictation tools first (see "Interference").
.\.venv\Scripts\python.exe scripts\it_insertion.py     # insertion into an owned Tk window
.\.venv\Scripts\python.exe scripts\it_hotkeys.py       # global hotkeys with another app focused
.\.venv\Scripts\python.exe scripts\it_notepad.py       # real Win11 Notepad (temp file, only its own window)
.\.venv\Scripts\python.exe scripts\it_browser.py       # real Edge, isolated profile, own window
.\.venv\Scripts\python.exe scripts\it_recorder.py      # real microphone: bad device, max duration, 20x start/stop, leaks
.\.venv\Scripts\python.exe scripts\it_ui.py            # pill never takes focus; UI stays responsive while transcribing
.\.venv\Scripts\python.exe scripts\it_e2e.py           # hotkey -> transcription -> insertion -> history, cancel, focus change
.\.venv\Scripts\python.exe scripts\check_offline.py    # model load + transcribe with every network call blocked
.\.venv\Scripts\python.exe scripts\measure_perf.py     # startup, idle cost, VRAM, latency
```
Test audio: Windows text-to-speech clips with known reference text (`scripts/make_clips.ps1` -> `data/tts_*.wav`). The e2e/perf scripts replace **only the microphone** with that clip; everything else is the real app.

## Automated tests (v2 numbers; now 186, see above)
| Area | Tests cover |
|---|---|
| Speech engine | empty / silent / no-speech audio raises an error, never text; GPU out-of-memory falls back to CPU (simulated failure); other errors not swallowed |
| Dictation controller | happy path inserts into the original target; cancel while recording and while processing inserts nothing; errors are reported not inserted; mic unavailable then recovery; too-short tap ignored; result carries language and duration; two transcriptions never overlap on the model |
| Silence auto-stop | stops after speech then a pause, speech resets the timer, gives up after 10 s of no speech, off means never (synthetic audio) |
| Hotkeys | parsing, hold start/stop, auto-repeat ignored, exact-modifier matching, no stuck state, chord keys swallowed only inside the chord, bare Esc and modifiers never swallowed |
| Config | defaults, round trip, corrupt file backed up, bad values ignored one by one, clamping |
| History | add/search (wildcards literal)/delete/clear, persistence, prune, export json/csv/txt, deleted text really removed from the file |
| Text | vocabulary replacement (whole word, case, multi-word, regex characters literal, unrelated text untouched), clean mode only removes fillers, recogniser hinting off by default |
| UI | settings save/reload and validation, history page, models page, first-run dialog, error classification, keyboard reachability and labels, vocabulary import limits |

## Integration results (real hardware)
| Script | Result | Notes |
|---|---|---|
| `it_insertion.py` | 10/10 | type, unicode+emoji, multiline, 5399 chars, clipboard restored, non-text clipboard untouched, focus moved -> copy only, target closed |
| `it_hotkeys.py` | 8/8 | hold, 25 auto-repeat key-downs, toggle, cancel, settings, plain keys pass through, chord keys do not leak, no focus theft. **Keys were injected with hardware scan codes, not typed by a person** |
| `it_notepad.py` | 7/7 | verified from the saved file; typing fallback (ASCII), accents/emoji/CJK, multiline, 1800 chars, clipboard preserved |
| `it_browser.py` | 7/7 | Edge `<textarea>` and `<input>`; Chrome not run |
| `it_recorder.py` | 8/8 | invalid device -> clear error and recovery; max duration capped at exactly 2.00 s; 20 cycles: no thread/RAM growth; 20 full pipeline cycles: RAM and VRAM drift 0 after warm-up |
| `it_ui.py` | 5/5 | pill shown in all 5 states without changing the foreground window (styles `NOACTIVATE|TOOLWINDOW|TRANSPARENT`); UI event loop worst stall 58-72 ms while a 5.7 min clip transcribed |
| `it_e2e.py` | 13/13 | hold, toggle, Esc cancel mid-processing inserts nothing, focus change -> clipboard only, history row, clipboard restored. 6/6 clean in repeated isolated runs |
| `check_offline.py` | 0 network attempts | small and large-v3-turbo load and transcribe correctly with every socket call raising |
| `it_smart.py` | 6/6 | spoken clips -> Whisper -> local AI: Backtrack ('2 actually 3', 'scratch that'), your 7-point list, spoken punctuation, question not answered, plain sentence unchanged; 0.5-1.6 s warm, first call ~1 s after warm-up |
| `it_e2e_smart.py` | 8/8 | real app + hotkey: 7-item list pasted, 'buy milk' removed, clipboard restored, history keeps the original, Undo AI edit restores it |
| `it_learn.py` | 9/9 (one 8/9 run in ~8) | real Notepad + Edge: name fix learned and active, ordinary fix needs 2, Friday->Monday ignored, unsupported app ignored |
| `it_notepad.py` (reworked) | 8/8 in 6 of 8 runs | text read back via UI Automation (no extra keystrokes); new check: a focused button gets 'copied + message'. Misses (~1 paste in 15, rapid automated input) were all reported as 'paste could not be confirmed', text left on the clipboard |
| `it_clipboard.py` | 9/9 | browser HTML+RTF, image DIB+PNG, Explorer file list restored byte-for-byte; >64 MB left untouched |
| Model memory | flat | 120 consecutive real decodes: RAM 753 -> 753 MB, VRAM 1180 -> 1180 MB (first decode allocates ~0.5 GB once) |

## Performance (large-v3-turbo, int8_float16, RTX 4060 Laptop; `data/perf.json`)
| Measure | Value |
|---|---|
| App idle | 0.0 % CPU, ~191 MB RAM, 42 threads, 0 MB VRAM (model loads on first use) |
| Model load from disk cache | 2.9 s; 1.1 GB VRAM while loaded; 83 MB left after unload (CUDA context) |
| Key release -> text in the window | first use 3.5 s (includes model load), then 0.5-0.6 s for a 7 s utterance |
| Long audio | 5.7 min clip transcribed in ~8-10 s (41x real time, small and turbo) |
| Shutdown | exit code 0, no leftover processes, lock released, VRAM back to baseline (759 MB desktop baseline, delta 0) |
| Accuracy (TTS reference, `docs/benchmark.md`) | WER 1.9 % (turbo, medium), 5.8 % (small) on the 5.7 min clip |

## Smart mode benchmark
See `docs/cleanup-benchmark.md`: qwen2.5:7b-instruct 14/14, phi3 11/14, llama3.2:3b 10/14, qwen3:4b (thinking-only build) 0/14.

## NOT tested, so do not assume it works
- **Smart mode on your real speech and on long dictations**, and how well 'casual' style is followed.
- **Learning in apps other than Notepad and Edge** (Word, Slack, Discord, VS Code may or may not expose their text).
- **A person pressing the hotkeys on a physical keyboard.** All hotkey tests inject scan codes. Please try it yourself.
- **Real human speech accuracy.** Accuracy numbers come from synthetic TTS voices. One real microphone clip was transcribed but its content could not be verified. Accents, noise, fast speech, other languages: untested (auto-detect and manual language were only exercised on English).
- **Microphone unplugged mid-recording.** Only an invalid device index was tested; losing the device while recording is not handled specially.
- **Silence auto-stop with a real voice and room noise** (logic tested with synthetic audio; threshold may need tuning per microphone).
- Chrome, Word, Discord, VS Code, other apps; typing into **elevated (administrator) windows** (Windows blocks it for a normal-user app by design); multi-monitor / high-DPI layout of the pill; the "system" theme following a live OS change.
- Windows Start menu behaviour when releasing a hold chord that includes the Windows key (not reproduced with injected keys).
- Physically disconnecting the network (blocked in-process instead, to avoid changing system settings).
- Rewrite modes (professional, concise, casual, technical): not implemented.

## Interference found while testing (important)
This PC also runs a real **Wispr Flow** whose hold-to-talk chord overlaps Ctrl/Alt/Win. During testing, injected chords made Wispr Flow record the microphone and type its own cloud transcript into my test windows (stray sentences such as "Opa." and room speech appeared in the results). The test scripts now use `Shift+F9/F10/F11`, which never include Ctrl, Alt or Win. Back-to-back runs of the whole suite were still occasionally flaky (Notepad paste, one e2e run) on this shared, in-use machine; each passes on its own repeatedly. If you run the suite, close other dictation tools and do not use the keyboard or mouse meanwhile.
**If you use both apps, give them different hotkeys** (Settings tab). Flowbit's default hold chord is `ctrl+alt+d`, toggle `ctrl+alt+space`.

## Bugs found by this testing and fixed
- Win11 Notepad sometimes opens with keyboard focus on a toolbar **button**; Ctrl+V there silently did nothing. Now detected: text copied with a message. (Earlier 'flaky Notepad paste' failures were mostly this.)
- A paste retry produced a duplicate (once garbled): retries removed; unconfirmed pastes are reported instead.
- Any browser copy (HTML on the clipboard) forced slow typing: the whole clipboard is now saved and restored.
- Smart mode's first dictation took 15.6 s (model reloaded because warm-up used another context size): 0.98 s.
- Learning rules would have learned Friday->Monday and turned every 'send' into 'sent': stricter similarity, names vs other words.
- Unicode typed in a flood garbled text in real Notepad (Tk test windows hid it): paste is now the default, typing is a paced one-character fallback.
- The `keyboard` library got stuck modifier state: replaced with an own low-level hook.
- Feeding the vocabulary glossary to Whisper made it add or drop words: now opt-in, off by default.
- The hold chord's letter leaked into the focused app: chord keys are now swallowed.
- Model downloads followed the repository's moving `main` branch: pinned to the benchmarked commits.
- Two transcriptions could run on the model at once after a cancel: now serialised.
- History always stored duration 0 and the configured (not detected) language: fixed.
- Single history entry deletion left the text in the database file: `secure_delete` on.
