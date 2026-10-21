# Privacy: what Flowbit stores, where, and what leaves your PC

## Short version
Speech is turned into text **on this PC**. Flowbit has no account, no subscription, no word limit and no telemetry. The only network use is the one-time model download that **you** start.

## What happens to your voice
1. The microphone is read **only while recording** (hold-to-talk, toggle, or the Start button).
2. Audio is kept **in memory only**, handed to the local speech model, then discarded. It is **never written to disk** and never uploaded. (The one exception is the separate voice-training recorder, which you start yourself; see the `voice\` row below.)
3. The text is pasted into the window that was focused when you started recording (or copied to the clipboard; see below).

## What is stored on disk
All in `userdata\` inside the Flowbit folder (override with `VOICETYPE_HOME`). The folder is excluded from git, so it is never published. The Settings page has an *Open data folder* button.

| File | Contents | How to remove |
|---|---|---|
| `settings.json` | Your settings, hotkeys, custom vocabulary | Delete the file (defaults return) |
| `history.db` | Transcripts you dictated (time, cleaned text, the original recognised text for *Undo AI edit*, language, model). **Off with the "Save transcripts to history" switch.** Optional auto-delete after N days. | History tab: Delete / Clear all, or Settings: *Delete all history now*. Clear-all also compacts the file so deleted text is not left behind. |
| `voicetype.log` | Start/stop messages and errors. **Never contains transcript text** (every log call was reviewed). Rotates at ~500 KB. | Delete the file |
| `voicetype.lock` | Prevents two copies from running | Removed on exit |
| `memory\learned.json` | Word fixes learned from your corrections (*heard* -> *written as*, how often, when) | Memory tab: Forget selected / Forget everything, or delete the folder |
| `voice\clips\*.wav`, `voice\dataset.jsonl` | **Recordings of your voice**, saved on purpose to fine-tune the speech model, each with the text you confirmed. Only created by `scripts\record_voice.py`, only when you press Save; normal dictation never adds to it. Never uploaded | *Delete last saved clip* in the recorder, or delete the `voice` folder |
| `memory\examples.json` | Up to 20 recent edits you made to AI-cleaned text (the cleaned sentence and what you changed it to). A few are shown to the local AI as examples of your style | Memory tab: Forget everything, or delete the file |

Speech models live in `models\` inside the Flowbit folder (also excluded from git). Fine-tuning (`scripts\train_voice.py`) runs entirely on this PC's GPU; your clips and the trained `models\my-voice\` never leave it. The only network use is the one-time setup download (PyTorch, training libraries, base model) that you start. Delete them from the Models tab.

## The local AI (optional)
If Ollama is installed, the recognised text can be sent to **Ollama running on this PC** for two optional steps, each with its own switch in Settings → Formatting: the *punctuation pass* (adds punctuation to long run-on speech; its answer is rejected if any word changes) and, in Smart mode, *AI cleanup* (fillers, self-corrections). In both cases the text is sent to **Ollama running on this PC** (`http://127.0.0.1:11434`, never another address; the code refuses anything else). With it go your vocabulary/learned word spellings, the writing style for the app you are dictating into (only the category, such as "email", not the window title), and up to 3 of your recent edit examples. Ollama keeps the model in GPU memory for 30 minutes after the last use. Verified: with every non-local network connection blocked, Smart mode still works and makes **0** outside connections (`scripts/check_offline.py`). Downloading the AI model itself (`ollama pull`) is a one-time download you start.

## Undo Last Insertion
When you use Undo, Flowbit reads the text of the box it last typed into (UI Automation, the same as learning) to prove the text is unchanged before deleting exactly its own words. It reads nothing else and stores only what it inserted, in memory, until the next insertion.

## The mascot
The mascot's bubble is the privacy indicator: it says *Listening · on this PC* while the microphone is open and *Transcribing on this PC* while working. The microphone is only open while the mascot is orange. Flowbit has no external service, so there is nothing else to indicate.

## Learning from your corrections
When *Learn from my corrections* is on (default), after Flowbit pastes it reads **the same text box** through Windows UI Automation, once per second, until you leave that box or 90 seconds pass. It compares what it typed with what is there now and keeps only word-level spelling fixes (and, for AI-cleaned text, the edited sentence as a style example). It reads nothing else on screen, never reads boxes it did not just type into, never logs the text, and stores only `memory\learned.json` / `examples.json`. Apps that do not expose their text to Windows are simply not read. Turn it off in Settings.

## The clipboard
To insert text, Flowbit briefly puts your transcript on the clipboard and sends Ctrl+V, then **restores exactly what was there before**: text, browser HTML/rich text, images and copied files are saved and put back byte-for-byte (tested). If something cannot be restored (metafiles, owner-drawn formats, or more than 64 MB), it types the text instead and leaves your clipboard alone. If focus moved to another window while you were speaking, the text is **copied to the clipboard and not pasted anywhere**, and you are told. Clipboard-history tools (such as Windows' Win+V) may record the transcript while it is on the clipboard.

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
