<p align="center"><img src="docs/img/flowbit-logo.svg" alt="Flowbit" width="420"></p>

**Flowbit is free, private voice typing for Windows.** Click into any text box, hold a key (or click the little mascot), speak, and your words appear, neatly punctuated, with lists and numbers formatted.

Speech recognition and formatting run on your own PC. No account, no subscription, no weekly word limit, and your voice never leaves your computer.

<p align="center"><img src="docs/img/indicator.svg" alt="The Flowbit mascot: dim and still when not recording, bright orange with moving sound waves while recording" width="460"></p>

> Not affiliated with or endorsed by Wispr Flow. Flowbit is an independent open-source project that does the same job locally. A public search found a cancelled 2013 US "FLOWBIT" trademark and an unrelated "FlowBits" smart-home app. No conflict was found, but name availability is not guaranteed.

## What it does

| | |
|---|---|
| **Types anywhere** | Notepad, VS Code, browsers, chat apps: any text box. Your clipboard is put back afterwards. |
| **Readable text** | Punctuation, capitals and spacing. "First point … second point …" becomes a numbered list; "bullet point" makes bullets; "new paragraph" and "new line" work; "fifteen percent" becomes 15%. |
| **Two modes** | **Smart Formatting**, or **Exact Transcription** (your words exactly as recognised). |
| **A mascot that shows the truth** | It floats at the bottom of the screen. It's dim when idle, turns bright orange with sound waves that follow your real voice while recording, and shows a progress ring while working. If it isn't moving, it isn't recording. Click it to start or stop; drag it anywhere. |
| **Safe undo** | `Ctrl+Alt+Z` removes the last text Flowbit typed, but only when it can prove that's exactly its text. |
| **Learns from you** | Your own vocabulary, plus words it learns when you correct its typing. |
| **Private** | Everything runs on this PC. Tested: 0 network connections while dictating. |

## Quick start

You need Windows 11 (the only version tested), a microphone, and Python 3.11. An NVIDIA GPU makes it much faster but isn't required.

```powershell
git clone https://github.com/VARSHITH707/Unlimited-WisprFlow.git
cd Unlimited-WisprFlow
uv venv --python 3.11 .venv
uv pip install --python .venv\Scripts\python.exe -r requirements.txt
.\.venv\Scripts\python.exe -m voicetype
```

The first start downloads the speech model once (about 1.6 GB). After that, dictation works offline.

**Optional:** install [Ollama](https://ollama.com) and run `ollama pull qwen2.5:7b-instruct-q4_K_M` (4.7 GB, once). The local AI then adds punctuation to long run-on sentences (it may never change a word) and removes fillers and self-corrections ("2, actually 3" becomes "3"). Without it, everything else still works.

No `uv`? Use `py -3.11 -m venv .venv` and `.venv\Scripts\python -m pip install -r requirements.txt` instead.

## How to use it

1. Click in any text box.
2. **Hold `Ctrl+Alt+D`** and speak, then let go. Or press **`Ctrl+Alt+T`** (or click the mascot) to start, and again to stop.
3. The text appears where your cursor was.

| Action | Shortcut |
|---|---|
| Push to talk | hold `Ctrl+Alt+D` |
| Start / stop (toggle) | `Ctrl+Alt+T` or click the mascot |
| Cancel | `Esc` |
| Undo last insertion | `Ctrl+Alt+Z` |
| Settings | `Ctrl+Alt+Shift+V` |

You can change every shortcut in Settings. Flowbit refuses shortcuts that clash with editing keys such as `Ctrl+Z`, or that another program already uses.

| You say | Flowbit types |
|---|---|
| "first point improve the UI second point fix the microphone" | 1. Improve the UI.<br>2. Fix the microphone. |
| "bullet point improve the design bullet point fix recording errors" | - Improve the design.<br>- Fix recording errors. |
| "the price went up by fifteen percent to three point five million dollars" | The price went up by 15% to $3.5 million. |
| "let's do coffee at 2 actually 3" (with the local AI) | Let's do coffee at 3. |
| "dear team new paragraph the release is ready" | Dear team<br><br>The release is ready. |

Your history (time, text and your exact original words) is in the **History** tab. Export it to a text file there.

## How well it works

| | |
|---|---|
| Time from letting go to text | **0.5–1.6 s** |
| Recognition errors on test audio | **1.9%** of words |
| Formatting tests | **lists, bullets, numbers, commands, punctuation:** all pass |
| Network connections while dictating | **0** |
| Automated tests | **186 pass** |

See the [dashboard](docs/DASHBOARD.md) for charts and every version, and [feature status](docs/status.md) for what is verified and what isn't.

## Your data stays here

| Folder | Contents |
|---|---|
| `userdata\` | settings, history, learned words, and voice clips only if you record them for training |
| `models\` | speech models |

Both folders are excluded from git. Normal dictation never saves audio. Details: [privacy](docs/privacy.md).

## Documentation

- [Guide](docs/GUIDE.md): every setting, troubleshooting, building a `.exe`, training on your voice
- [Formatting](docs/formatting.md): how punctuation, lists and numbers work, and why punctuation was missing (measured)
- [Windows integration](docs/windows-integration.md): shortcuts, mascot, focus, insertion, undo and their limits
- [Feature status](docs/status.md), [testing](docs/testing.md), [architecture](docs/architecture.md)
- [Version history](VERSION_HISTORY.md), [project report](PROJECT_REPORT.md), [dashboard](docs/DASHBOARD.md)

## References

1. Radford, A. et al. (2022). *Robust Speech Recognition via Large-Scale Weak Supervision*. OpenAI. [arXiv:2212.04356](https://arxiv.org/abs/2212.04356). This is the Whisper model that turns speech into text.
2. Hu, E. J. et al. (2021). *LoRA: Low-Rank Adaptation of Large Language Models*. [arXiv:2106.09685](https://arxiv.org/abs/2106.09685). This is how Flowbit can be fine-tuned on your voice in 8 GB of GPU memory.
3. SYSTRAN. *faster-whisper*. [github.com/SYSTRAN/faster-whisper](https://github.com/SYSTRAN/faster-whisper). This is the engine Flowbit runs Whisper with.

Also built with [Ollama](https://ollama.com) and [Qwen2.5](https://github.com/QwenLM/Qwen2.5) (optional local AI), and [PySide6](https://doc.qt.io/qtforpython-6/).

## License

[MIT](LICENSE). Use it, change it, and share it. This repository accepts changes only from its owner and collaborators; to suggest something, [open an issue](https://github.com/VARSHITH707/Unlimited-WisprFlow/issues).
