# Manual test sheet (hands-on, real voice)

Fill in **Result** as you go: `pass`, `fail`, or what happened. Send it back and it goes into PROJECT_REPORT.md and VERSION_HISTORY.md.

**Before you start**
- Quit Wispr Flow from its tray icon (right-click it, then Quit). If it stays running, its hotkey may record you and send the audio to its cloud.
- Start VoiceType: `.\.venv\Scripts\python.exe -m voicetype`
- First run shows a short setup wizard: pick your mic, click **Test**, keep the model `large-v3-turbo` (already downloaded), then finish.

| # | Test | How | Expected | Result |
|---|---|---|---|---|
| 1 | Basic dictation | Open Notepad, click in it, **hold** `Ctrl+Alt+D`, say "This is my first test", release | The pill shows Listening, then Transcribing; text appears in about 1–3 s | |
| 2 | Toggle mode | Press `Ctrl+Alt+Space`, speak 2 sentences, press it again | Both sentences appear | |
| 3 | Cancel | Hold `Ctrl+Alt+D`, speak, press `Esc` before releasing | Nothing is typed | |
| 4 | Fillers | Say "um so I think uh we should ship it on Friday" | "So I think we should ship it on Friday." | |
| 5 | Self-correction | Say "let's meet at 2 actually 3" | "Let's meet at 3." | |
| 6 | Scratch that | Say "schedule it for Monday no scratch that Tuesday" | Only Tuesday remains | |
| 7 | The 7-points example | Say points one to six, then a wrong seventh point, then "no no that is not the seventh point, the seventh point is ..." | A clean list 1–7 with the correct seventh point | |
| 8 | Spoken punctuation | Say "hello comma how are you question mark" | "Hello, how are you?" | |
| 9 | Not answered | Say "what is the capital of France" | The question is typed, not answered | |
| 10 | Undo AI edit | After test 5, open VoiceType → Home → **Undo AI edit**, then `Ctrl+V` in Notepad | The original wording ("...2 actually 3") is pasted | |
| 11 | Learning a name | Dictate a sentence with an unusual name; fix its spelling in Notepad; click elsewhere | A tray message says it learned it; it appears in the **Memory** tab | |
| 12 | Learned name is used | Dictate the same name again | It is spelled your way | |
| 13 | Browser | Repeat test 1 in a Chrome or Edge text box (Gmail, ChatGPT, any form) | Text appears | |
| 14 | Chat style | Dictate into WhatsApp/Discord/Slack (if you use one) | Casual style: no final period | |
| 15 | Other apps | Try Word, VS Code, or any app you use daily | Text appears (or a message says it was copied) | |
| 16 | Long dictation | Speak continuously for 1–2 minutes | Full text, sensible punctuation, no missing parts | |
| 17 | Clipboard kept | Copy something, dictate, then press `Ctrl+V` | Your copied item is pasted, not the dictation | |
| 18 | Focus change | Start dictating, click a different window before releasing | Not typed anywhere; a message says it's on the clipboard | |
| 19 | Other language (optional) | Settings → Language → your language; dictate | Correct text in that language | |
| 20 | History | Open the **History** tab | Every dictation is listed; search and Copy original work | |

**If something fails:** note the test number and what you saw. The log is in `%APPDATA%\VoiceType` (Settings → *Open data folder*). It never contains your words.
