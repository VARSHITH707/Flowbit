# VoiceType

**Free, private voice typing for Windows.** Hold a key, speak, let go, and your words are typed wherever your cursor is: email, chat, browser, code editor, anywhere.

Everything runs on your own PC. No account, no subscription, no word limit, and your voice never leaves your computer.

<p align="center"><img src="docs/img/indicator.svg" alt="The VoiceType logo at the bottom of the screen: still when not recording, moving while recording" width="420"></p>

> Not affiliated with or endorsed by Wispr Flow. This is an independent, open-source project that does the same job locally.

## What it does

| | |
|---|---|
| **Types anywhere** | Works in any app with a text box. Your clipboard is put back afterwards. |
| **Cleans up your speech** | Removes "um" and "uh", fixes self-corrections ("at 2, actually 3" becomes "at 3"), builds numbered lists, and turns "comma" and "question mark" into punctuation. A local AI does this. |
| **Learns from you** | When you correct a name or word it got wrong, it remembers it for next time. |
| **Shows when it's listening** | A small logo at the bottom of the screen moves with your voice while recording. If it isn't moving, it isn't recording. |
| **Stays private** | Speech recognition and the AI both run on your PC. Tested: 0 network connections while dictating. |
| **Can learn your voice** | Optional: record yourself and fine-tune the speech model on your own voice. |

## Quick start

You need Windows 11 (the only version tested), a microphone, and Python 3.11. An NVIDIA GPU makes it much faster but isn't required.

```powershell
git clone https://github.com/VARSHITH707/Unlimited-WisprFlow.git
cd Unlimited-WisprFlow
uv venv --python 3.11 .venv
uv pip install --python .venv\Scripts\python.exe -r requirements.txt
.\.venv\Scripts\python.exe -m voicetype
```

A short setup wizard opens on first start: pick your microphone and download the speech model (about 1.6 GB, once).

For the speech cleanup, install [Ollama](https://ollama.com) and run `ollama pull qwen2.5:7b-instruct-q4_K_M` (4.7 GB, once). Without it, VoiceType still types exactly what you said.

No `uv`? Use `py -3.11 -m venv .venv` and `.venv\Scripts\python -m pip install -r requirements.txt` instead.

## How to use it

1. Click in any text box.
2. **Hold `Ctrl+Alt+D`** and speak. The logo at the bottom turns red and moves.
3. **Let go.** Your text appears in a second or two.

| Do this | Press |
|---|---|
| Dictate while holding the key | hold `Ctrl+Alt+D` |
| Start and stop hands-free | `Ctrl+Alt+Space` |
| Cancel | `Esc` |
| Open settings | `Ctrl+Alt+Shift+V` |

| You say | It types |
|---|---|
| "um so I think uh we should ship it on Friday" | So I think we should ship it on Friday. |
| "let's do coffee at 2 actually 3" | Let's do coffee at 3. |
| "hello comma how are you question mark" | Hello, how are you? |

Everything you dictate is listed in the **History** tab, with the time. Export it to a text file from there.

## How well it works

See the **[dashboard](docs/DASHBOARD.md)** for charts of speed, accuracy and every version.

| | |
|---|---|
| Time from letting go to seeing text | **0.5–1.6 s** |
| Speech recognition errors on test audio | **1.9%** of words |
| Speech cleanup test cases passed | **14 of 14** |
| Network connections while dictating | **0** |
| Automated tests | **117 pass** |

All numbers were measured on one laptop (RTX 4060, 8 GB). Accuracy on your own voice and accent will differ, which is what the voice fine-tuning is for.

## Where your data goes

Everything stays inside the VoiceType folder, and none of it is ever uploaded:

| Folder | What's in it |
|---|---|
| `userdata\` | your history, settings, learned words, and (only if you record them) voice clips for training |
| `models\` | the speech models |

Both folders are excluded from git. Normal dictation never saves audio. Details: [docs/privacy.md](docs/privacy.md).

## Train it on your voice (optional)

> New: recording is tested. The training and checking steps are still being verified end to end. Results will appear on the [dashboard](docs/DASHBOARD.md).

1. **Record:** `.\.venv\Scripts\python.exe scripts\record_voice.py`. Read the sentences shown and correct any mistakes. 30–60 minutes is a good amount.
2. **Train:** `.\.venv-train\Scripts\python.exe scripts\train_voice.py` (one-time setup in the [guide](docs/GUIDE.md#fine-tune-on-your-own-voice-in-progress)).
3. **Check:** `.\.venv\Scripts\python.exe scripts\eval_voice.py`. It tells you whether your trained model is better. If it is, pick **my-voice** in Settings.

## More

- [Full guide](docs/GUIDE.md): every setting, troubleshooting, and building a `.exe`
- [Dashboard](docs/DASHBOARD.md): measured results and versions
- [Version history](VERSION_HISTORY.md) and [project report](PROJECT_REPORT.md)
- [How it's built](docs/architecture.md) and [what's tested](docs/testing.md)

## References

1. Radford, A. et al. (2022). *Robust Speech Recognition via Large-Scale Weak Supervision*. OpenAI. [arXiv:2212.04356](https://arxiv.org/abs/2212.04356). This is the Whisper model that turns speech into text.
2. Hu, E. J. et al. (2021). *LoRA: Low-Rank Adaptation of Large Language Models*. [arXiv:2106.09685](https://arxiv.org/abs/2106.09685). This is the method used to fine-tune Whisper on your voice in 8 GB of GPU memory.
3. SYSTRAN. *faster-whisper: Faster Whisper transcription with CTranslate2*. [github.com/SYSTRAN/faster-whisper](https://github.com/SYSTRAN/faster-whisper). This is the engine VoiceType runs Whisper with: about 4× faster and much lighter than the original.

Also built with [Ollama](https://ollama.com) and [Qwen2.5](https://github.com/QwenLM/Qwen2.5) for the cleanup, and [PySide6](https://doc.qt.io/qtforpython-6/) for the app window.

## License

[MIT](LICENSE). Use it, change it, and share it. This repository accepts changes only from its owner and collaborators; to suggest something, [open an issue](https://github.com/VARSHITH707/Unlimited-WisprFlow/issues).
