# Privacy: what VoiceType stores, where, and what leaves your PC

## Short version
Speech is turned into text **on this PC**. VoiceType has no account, no subscription, no word limit and no telemetry. The only network use is the one-time model download that **you** start.

## What happens to your voice
1. The microphone is read **only while recording** (hold-to-talk, toggle, or the Start button).
2. Audio is kept **in memory only**, handed to the local speech model, then discarded. It is **never written to disk** and never uploaded.
3. The text is pasted into the window that was focused when you started recording (or copied to the clipboard; see below).

## What is stored on disk
All in `userdata\` inside the VoiceType folder (override with `VOICETYPE_HOME`). The folder is excluded from git, so it is never published. The Settings page has an *Open data folder* button.

| File | Contents | How to remove |
|---|---|---|
| `settings.json` | Your settings, hotkeys, custom vocabulary | Delete the file (defaults return) |
| `history.db` | Transcripts you dictated (time, cleaned text, the original recognised text for *Undo AI edit*, language, model). **Off with the "Save transcripts to history" switch.** Optional auto-delete after N days. | History tab: Delete / Clear all, or Settings: *Delete all history now*. Clear-all also compacts the file so deleted text is not left behind. |
| `voicetype.log` | Start/stop messages and errors. **Never contains transcript text** (every log call was reviewed). Rotates at ~500 KB. | Delete the file |
| `voicetype.lock` | Prevents two copies from running | Removed on exit |
| `memory\learned.json` | Word fixes learned from your corrections (*heard* -> *written as*, how often, when) | Memory tab: Forget selected / Forget everything, or delete the folder |
| `memory\examples.json` | Up to 20 recent edits you made to AI-cleaned text (the cleaned sentence and what you changed it to). A few are shown to the local AI as examples of your style | Memory tab: Forget everything, or delete the file |

Speech models live in `models\` inside the VoiceType folder (also excluded from git). Delete them from the Models tab.

## Smart mode: the local AI
In Smart mode the recognised text is sent to **Ollama running on this PC** (`http://127.0.0.1:11434`, never another address; the code refuses anything else). With it go your vocabulary/learned word spellings, the writing style for the app you are dictating into (only the category, such as "email", not the window title), and up to 3 of your recent edit examples. Ollama keeps the model in GPU memory for 30 minutes after the last use. Verified: with every non-local network connection blocked, Smart mode still works and makes **0** outside connections (`scripts/check_offline.py`). Downloading the AI model itself (`ollama pull`) is a one-time download you start.

## Learning from your corrections
When *Learn from my corrections* is on (default), after VoiceType pastes it reads **the same text box** through Windows UI Automation, once per second, until you leave that box or 90 seconds pass. It compares what it typed with what is there now and keeps only word-level spelling fixes (and, for AI-cleaned text, the edited sentence as a style example). It reads nothing else on screen, never reads boxes it did not just type into, never logs the text, and stores only `memory\learned.json` / `examples.json`. Apps that do not expose their text to Windows are simply not read. Turn it off in Settings.

## The clipboard
To insert text, VoiceType briefly puts your transcript on the clipboard and sends Ctrl+V, then **restores exactly what was there before**: text, browser HTML/rich text, images and copied files are saved and put back byte-for-byte (tested). If something cannot be restored (metafiles, owner-drawn formats, or more than 64 MB), it types the text instead and leaves your clipboard alone. If focus moved to another window while you were speaking, the text is **copied to the clipboard and not pasted anywhere**, and you are told. Clipboard-history tools (such as Windows' Win+V) may record the transcript while it is on the clipboard.

## What leaves your PC
- **Model download** (you click Download): contacts Hugging Face to fetch the model files. Nothing about you or your audio is sent.
- **Nothing else.** Verified: with every network connection blocked in-process, model loading and transcription still work and zero connection attempts are made (`scripts/check_offline.py`).
- There is no analytics, crash reporting or update check.

## Optional features that could change this
Smart mode uses a **local** model only. There is no option to send text to an online AI; if one is ever added it will be off by default and clearly labelled.

## System access
- Runs as a normal user; needs no administrator rights, installs no service, no startup entry and changes no Windows security setting.
- Installs a global keyboard hook **only to detect your configured hotkeys**. It does not record or store other keystrokes. Source: `voicetype/hotkeys.py`.
- Reads which window is focused (and which program it belongs to, to pick the writing style) so it can insert text there.
- With learning on, reads the text box it just typed into (see above).
- Windows does not let a normal-user app type into windows running as administrator; dictation into those windows is not possible.
