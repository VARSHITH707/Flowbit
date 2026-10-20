# Requirements (MVP)
Original local-first Windows voice typer. Python 3.11, faster-whisper, PySide6.

## Build
- Hold-to-talk AND toggle hotkeys (+ cancel, open settings), configurable.
- Local transcription (faster-whisper, GPU with CPU fallback), English default, manual language + auto-detect.
- Insert into the previously focused field (SendInput Unicode, clipboard fallback, manual copy). Never paste into a different window.
- Tray icon, small floating state pill, settings, history, model manager, first-run setup.
- Custom vocabulary (initial_prompt + whole-word replacement). Exact-transcription mode never rewrites.
- No quota, no account, no telemetry, no raw audio stored.

## Skip (why)
- Cloud processing, accounts, teams/sharing: against the local-first goal.
- Command Mode, per-app tone learning, snippets: need an LLM or accessibility context. Optional later.
- Mobile/macOS: out of scope.
- Matching their branding, assets, or any of their code or endpoints.

## Design choices from research
Audio in-process (they capture in the renderer; we use sounddevice). Native helper for hotkeys/insertion (we use Win32 via ctypes). Local SQLite or JSON for history.
