# Feature status

Legend: **Tested** = implemented and verified by running it (automated test and/or real hardware). **Untested parts** are listed in the notes. See `docs/testing.md` for evidence.

| Feature | Status | Notes |
|---|---|---|
| Local transcription, GPU (default) | Tested | large-v3-turbo / medium / small benchmarked; TTS audio and one real mic clip |
| CPU fallback | Tested | forced CPU run correct (1.7 s for 7 s audio, small) |
| GPU out-of-memory recovery | Tested (simulated) | retry on CPU with a notice; a real 8 GB OOM was not forced |
| Never returns text on failure | Tested | empty, silent and no-speech audio raise errors |
| Offline after model download | Tested | zero network attempts with all sockets blocked; network not physically disconnected |
| Model download, progress, availability, delete, pinning | Tested | real download through the UI paths; pinned to benchmarked commits |
| Hold-to-talk, toggle, cancel, open-settings hotkeys | Tested with injected keys | **physical key presses by a person not yet tried**; elevated windows not reachable (Windows) |
| Chord key does not leak into the app | Tested | injected keys |
| Insert into focused app (paste, typing fallback) | Tested | real Notepad, real Edge textarea/input, owned Tk window; accents, emoji, CJK, multiline, 5400 chars |
| Clipboard restored | Tested | text; non-text clipboard is never touched |
| Focus-change safety (copy, never paste elsewhere) | Tested | policy is a setting |
| Cancel inserts nothing | Tested | during recording and during processing |
| Floating status pill | Tested | never takes focus; 5 states; reviewed in screenshots; multi-monitor/DPI untested |
| System tray | Partly tested | icon visible, menu present; menu clicks not exercised |
| Main window: Home, History, Models, Settings | Tested | automated UI tests + screenshots; file dialogs not clicked |
| First-run setup (mic test, model download, hotkeys) | Tested | |
| Settings persistence | Tested | corrupt/invalid values handled |
| History (search, copy, export, delete, clear, retention) | Tested | deleted text overwritten in the file; no raw audio stored |
| Custom vocabulary | Tested | replacement mode (default); recogniser hinting is opt-in because it altered output |
| Exact mode / Clean mode | Tested | clean removes um/uh only |
| Dark / light theme | Tested | live "system" theme switch untested |
| Silence auto-stop | Implemented, not fully tested | logic tested with synthetic audio only; off by default |
| Max recording duration | Tested | capped at exactly the limit |
| Logging without transcript text | Tested | all log calls reviewed |
| Keyboard accessibility | Partly tested | all controls focusable and labelled (automated); no screen-reader or manual Tab walk |
| Language: English | Tested | |
| Language: other languages, auto-detect on non-English, code-switching | Not verified | model supports ~100 languages; not evaluated here |
| Real human speech accuracy | Not verified | benchmarks use synthetic TTS voices |
| Mic unplugged mid-recording | Partial | clear error for a bad/unavailable device; mid-stream loss not specially handled |
| Chrome, Word, Discord, VS Code and other apps | Not verified | only Notepad, Edge, Tk |
| Standalone .exe (GPU build, PyInstaller one-folder, 2.3 GB) | Partly tested | launches, shows windows, exits cleanly, GPU transcription works inside it (--selftest); hotkey/insert flow, CPU-only build, second PC and code signing not tested |
| Smart cleanup with local AI (fillers, self-corrections/Backtrack, numbered lists, spoken punctuation) | Tested | qwen2.5 7B via Ollama on 127.0.0.1; 14/14 typed benchmark cases, 6/6 spoken clips through Whisper+AI, 8/8 in the real app; raw fallback on added/dropped words or no AI |
| Undo AI edit / Copy original | Tested | original kept in history; automated UI test + real app |
| Writing style per app (formal/casual, chat drops final period) | Tested (logic) | category detection and prompts unit-tested; how well the AI follows 'casual' was not measured |
| Memory: learn word fixes from your edits | Tested | real Notepad + Edge; names after 1 fix, other words after 2, Friday->Monday not learned; occasionally misses a fix (1 miss in ~8 runs) |
| Paste confirmation + 'no text box selected' guard | Tested | in apps that expose their text (Notepad, Edge) a paste that did not arrive is reported and left on the clipboard; if a button/menu has focus, the text is copied with a message instead of vanishing. In rapid automated tests Notepad missed about 1 paste in 15, each one detected |
| Clipboard restore incl. HTML, images, files | Tested | byte-for-byte on the real clipboard; >64 MB or metafiles -> typed instead, clipboard untouched |
| Rewrite modes (professional, concise) | Planned | Smart mode covers cleanup; rewriting tone/length is not implemented |
| Command mode, snippets | Planned | present in the reference product |
| Using surrounding text / screen context in the AI prompt | Not implemented | VoiceType only uses the app category, never window contents, in the prompt |
| Mobile / macOS | Out of scope | |
