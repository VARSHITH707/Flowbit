# Windows integration: shortcuts, mascot, focus, insertion, undo

## Recording modes (exactly two)

| Mode | How it works | Default |
|---|---|---|
| Push to talk | Hold the shortcut, speak, let go. Key auto-repeat never starts a second session. | `Ctrl+Alt+D` |
| Toggle | Press once to start, again to stop. Clicking the mascot does the same. Optional auto-stop after a pause. | `Ctrl+Alt+T` |
| Cancel | Discards the recording, nothing is inserted | `Esc` |
| Undo last insertion | See below | `Ctrl+Alt+Z` |

How it works:
- **The hook.** Shortcuts come from Flowbit's own low-level keyboard hook (`voicetype/hotkeys.py`), which sees key-down *and* key-up, so push-to-talk is reliable. The keys of a matched chord are swallowed, so the letter doesn't also reach your app.
- **Modifier-only toggles** such as `Ctrl+Win` are supported. They fire when that exact chord is pressed and released with no other key in between, so `Ctrl+Win+D` and similar still work. This is covered by unit tests only. It wasn't pressed for real, because the installed Wispr Flow uses `Ctrl+Win` and reacts to injected Windows-key chords.

**Conflict checks**, run when you save settings and at startup:
- Editing shortcuts (`Ctrl+Z`, `Ctrl+C`, `Ctrl+V` …) are refused as recording keys.
- Push-to-talk and toggle can't overlap, where one chord is part of the other.
- `Ctrl+Win` is refused while Wispr Flow is running.
- Any chord another program has registered is refused. Windows answers "already registered" when Flowbit asks.

**Found on this PC:**
- `Ctrl+Alt+Space`, the old toggle default, and `Ctrl+Alt+M` are owned by another program.
- Settings that still use `Ctrl+Alt+Space` are moved to `Ctrl+Alt+T` automatically, with a message saying so.

**Limit:** keys typed into windows running as administrator are invisible to a normal program (Windows UIPI).

## State machine

`IDLE → RECORDING → PROCESSING → INSERTING → DONE → IDLE`, or `FAILED` from any active state.
- Cancel works from recording and processing.
- A start while active, a second stop, or a result that arrives after a cancel is ignored.
- Each session inserts at most once, enforced by a generation check under a lock.
- Recording and transcription run off the UI thread. Tested: the UI loop never stalls more than about 80 ms during a 5.7-minute transcription.

## Auto-stop after silence (toggle mode only)

- Never while you hold a key.
- A block of audio counts as speech when its loudness (RMS) is above the larger of your setting and 3× the quietest block heard so far. That makes it work with quiet microphones and in noisy rooms. Tested: fan-level noise that kept the old version recording forever.
- Flowbit says why it stopped: after a pause, no speech for 10 s, or the longest recording length.

## The mascot

- A frameless, always-on-top, translucent window drawn with vector shapes (`voicetype/ui/mascot.py`).
- It has the Windows styles `WS_EX_NOACTIVATE` and `WS_EX_TOOLWINDOW`, so clicking or dragging it never takes the keyboard focus from the app you're dictating into.
- It is *not* click-through: only its fully transparent pixels let clicks pass.
- Real-desktop test (`scripts/it_ui.py`, using real mouse input): a click emits start/stop and the target app keeps focus; a drag moves it and saves the position (with 125% display scaling); a drag isn't counted as a click.
- The position is saved and kept inside the screen it's on (any monitor), above the taskbar. Opacity (30–100%) and showing it when idle are configurable.
- "Reduced motion" removes the idle float and blink.
- It only redraws while something is happening: 15 frames a second idle (none with reduced motion), 30 while active.
- The privacy indicator is the bubble: "Listening 0:03 · on this PC", "Transcribing on this PC". Flowbit has no external service to indicate.

## Inserting the text

1. When recording starts, the foreground window is remembered as the target.
2. **Flowbit's own windows** (settings, history, mascot) are never a target. The text is copied instead, with an explanation.
3. **If a Flowbit window is in front when the text is ready** (for example the preview), the target is brought back to the front first. Windows allows this only because Flowbit owns the foreground at that moment.
4. **If any other window took focus**, nothing is pasted. The text goes to the clipboard and you're told. This is configurable.
5. **If the focused control is a button or menu**, nothing is pasted, and you're told.
6. **Pasting:**
   - The whole clipboard is saved first: text, HTML, images and copied files.
   - Flowbit pastes, then confirms the text appeared (in apps that expose it). It never retries, because a retry once caused a duplicate.
   - It then restores your clipboard, unless something newer was copied in the meantime (checked with `GetClipboardSequenceNumber`).
   - If the clipboard can't be saved, the text is typed instead.
7. Unicode, emoji and multi-line text are tested in Notepad, Edge and a Tk window.

**Optional preview:** before inserting, a dialog shows the text so you can check or edit it, then Insert, Copy only, or Cancel. Off by default.

## Undo Last Insertion

Windows has no universal undo for text typed into another app, and a blind `Ctrl+Z` could undo something else. So Flowbit only deletes when it can prove the text is exactly what it typed:
1. The same window and the same text box (UI Automation runtime id) have the focus.
2. The box's whole text is unchanged since the insertion.
3. The text occurs exactly once.
4. Flowbit selects exactly that range and reads the selection back.
5. The focus is checked once more right before Delete.
6. After Delete, the result is verified.

**Tested for real** (`scripts/it_undo.py`, 11 of 11):
- In Notepad and Edge, it removes exactly the inserted text.
- In both, it refuses after you've typed more, and when another window is in front.
- In an app that hides its text (Tk), it declines and suggests the app's own Undo.

A bug found by this test was fixed: a popup took focus between selecting and deleting, so the last-moment focus check was added.

**Limits:**
- Undo doesn't work in apps that don't expose their text to UI Automation.
- It doesn't work after you've edited the box.
- It doesn't work when the same text appears twice in the box.
