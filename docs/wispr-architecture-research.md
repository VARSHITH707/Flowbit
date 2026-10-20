# How Wispr Flow works, and how to rebuild it locally

Research date: 2026-10-20. Sources are listed at the end. **V** = stated in Wispr's own docs/blog/case study, **3P** = third-party (reviews, competitors; may be biased), **REA** = from analysing the installed app on this PC (`docs/rea-findings.md`), **A** = my inference.

## 1. The pipeline (what happens when you dictate)

```
hotkey (native helper)            [REA/A]
  -> audio captured in the app (Web Audio worklet)            [REA]
  -> sent to Wispr's cloud: "Transcription always occurs on the cloud"   [V]
       1. ASR: speech -> raw words. Now "Canto", Wispr's own model.        [V]
          Gets terms from your personal dictionary at runtime.             [V]
       2. Cleanup LLM: fine-tuned Meta Llama, on Baseten/AWS, TensorRT-LLM  [V]
          Uses context: app name (always), text around the cursor,
          optionally text from the active window ("Context Awareness"),
          your dictionary, your style setting per app category.            [V]
  -> text pasted at the cursor; if formatting fails, the raw transcript is pasted   [V]
```
- Latency budget [V]: <200 ms ASR + <200 ms LLM + ≤200 ms network, aiming at ~700 ms after you stop speaking. LLM must produce 100+ tokens in <250 ms (p99). Third-party testers measure 0.4–2 s in practice [3P].
- Canto [V]: autoregressive speech model, pretrained on "millions of hours", then supervised fine-tuning, then reinforcement learning (GRPO) with a word-error-rate reward. Opted-in users' edits become training data. A model ten times larger is in training. No weights, no API, and no published latency.
- **Important finding in Wispr's own Canto write-up:** feeding dictionary terms to the speech model made it adopt *wrong but similar-sounding* terms up to ~5x more often, until they trained with distractors. We hit exactly this locally (Whisper added "And PySide6." when given a glossary), which is why VoiceType's glossary hinting is off by default.

## 2. Features to replicate (from Wispr's docs)

### Smart Formatting [V]
- Removes filler words; fixes grammar, punctuation and capitalization. **Does not fix misheard words.**
- Lists: saying "one… two…" or "first… second…" produces a numbered list.
- Spoken commands: "period/full stop", "comma", "question mark", "colon", "new line / next line / line break / skip a line", "new paragraph".
- Writing styles per app category (Personal, Work, Email, Other): Formal / Casual / Very casual / Excited. For example, casual style drops trailing periods in chat apps.

### Backtrack, the self-correction you asked about [V]
- Triggers: "actually", "scratch that", "never mind", **or simply restating what you meant**. It uses *the whole dictation as context* to decide what to change.
- Example: "Let's do coffee at 2 actually 3" → "Let's do coffee at 3."
- Guardrail: "I actually enjoyed the movie" is kept, because that "actually" is not a correction.
- Your example ("…point 6, point 7 is X, no no that's not the 7th point, point 7 is Y") is a restate-style backtrack: the cleanup LLM sees the whole utterance, drops the retracted point 7, and keeps the list numbered 1–7. This is an LLM rewrite step, not a rule.
- Undo: the original transcript is always kept, and "Undo AI edit" restores it.

### Dictionary and learning from your corrections [V]
- Manual entries plus "wrong → right" corrections. Matching is whole-word and case-insensitive, keeps your saved capitalization, and the longer phrase wins. Max 60 characters per entry.
- **Auto-learn (Windows/Mac):** "Flow monitors the text box where it pasted text and adds any word whose spelling you change." It skips file paths, URLs, code, numbers, dates, emoji, common words, famous names and everyday acronyms, and notifies you in batches. Deleted words are never re-learned.
- Wispr's blog describes the *planned* next level: capture edits on-device, decide if an edit should generalise, learn a per-user policy, and train the LLM to follow edits. They say "most personalization data must live on a user's device".
- Dictionary entries are **stored on Wispr's servers and synced, regardless of privacy settings** [3P, consistent with V sync docs].

### Context Awareness [V + 3P]
- Always used: the app name for formatting, plus textbox content for capitalization, punctuation and Command Mode [V].
- Optional: "relevant text from the active app window" [V]. Third-party reviews also report on-screen text and screenshots being sent [3P, disputed].

### What leaves your PC with Wispr today [V]
- Audio and transcripts for every dictation (cloud transcription, no offline mode).
- App name and text around the cursor; window text if Context Awareness is on.
- Dictionary (synced); usage statistics "regardless of data controls".
- Training use is a toggle ("Improve the model for everyone"). Storing history needs "Dictation Cloud Storage".

## 3. Patents and papers
- Wispr AI patents (inventors Kothari, Garg, Leonardo) cover **silent speech and EMG/gesture input** from the company's earlier wearable work. **No patent on Flow's dictation pipeline was found.**
- Useful public research for the cleanup step:
  - "Mind the Pause" (ACL 2026): tag disfluent tokens, then fine-tune an LLM to rewrite. It shows rewriting beats plain deletion for keeping grammar, and covers **Hindi, Bengali and Marathi**.
  - LLM disfluency detection/removal with prompting (STIL 2024).
  - US 11556722: transcript editing with disfluency correction metadata.
- Open-source local clones to learn from: OpenWispr (Whisper + any GGUF LLM), OpenWhispr, Handy, whispr-bro. None verified here.

## 4. What can be replicated on this laptop (and what cannot)

| Wispr part | Local replacement | Feasible? |
|---|---|---|
| Canto (cloud ASR) | faster-whisper large-v3-turbo on the RTX 4060 (built, benchmarked) | Yes, not identical |
| Fine-tuned Llama cleanup | Local instruct LLM via **Ollama (already installed: mistral, phi3, qwen3-coder)** or llama.cpp, with a strict cleanup/backtrack prompt | Yes; quality and latency must be measured |
| Smart formatting, lists, spoken punctuation | LLM + deterministic rules for spoken commands | Yes |
| Backtrack ("no no, the 7th point is…") | LLM with the whole utterance, plus a guardrail that rejects output adding words you never said (fall back to raw) | Yes, with measured accuracy |
| Styles per app | App name of the focused window (local) → style setting | Yes |
| Context: text around the cursor | Windows UI Automation on the focused control (local only) | Partly; works in many apps, not all |
| Auto-learn from your edits ("memory") | After pasting, re-read the same text box via UI Automation, diff against what was pasted, store word corrections | Partly; apps that expose their text via UI Automation |
| Memory folder | `%APPDATA%\VoiceType\memory\` (dictionary, corrections, styles, raw + cleaned history), all local | Yes |
| Undo AI edit | Keep raw + cleaned for every dictation | Yes |
| Their trained models, data, RL | Not available | **No.** An exact replica is impossible; the behaviour can be approximated |

### Hardware budget (8 GB VRAM)
Whisper turbo ≈ 1.2 GB + a 3–4 B LLM at 4-bit ≈ 2.5–3.5 GB → fits. A 7 B model (mistral) ≈ 4.5–5 GB → fits but slower. Expect roughly 0.5 s for speech plus 0.5–1.5 s for cleanup locally. That's slower than Wispr's 700 ms target, but nothing leaves the laptop and there's no limit. **This must be measured before choosing a model.**

### Risks
- A cleanup LLM can **add, drop or rephrase** content. That is fatal for "never fabricate". Mitigation: a strict prompt, a word-level diff guardrail, raw fallback, and an "Undo AI edit" button.
- Backtrack is judgment-based. Wispr itself only removes *clear* corrections. Expect occasional misses.
- Reading other apps' text boxes (UI Automation) is sensitive. Keep it local, opt-in, and never log it.
- Non-English cleanup quality with small local LLMs is unknown (to be tested with your voice).

## 5. Proposed next build (for approval; not started)
1. Benchmark local cleanup LLMs (the installed ones, plus one small 3–4 B instruct model) on a fixed test set: fillers, spoken punctuation, lists, backtrack cases (including your "7th point" example), "I actually enjoyed…" guardrail, and no-added-words. Measure latency and VRAM next to Whisper.
2. Add the cleanup stage: Exact (as now) / Smart (LLM), raw fallback, guardrail, Undo AI edit.
3. Memory folder + auto-learn from edits (UI Automation diff), styles per app, context from the text around the cursor. All local and opt-in.
4. Test everything with your real voice (English first, then your other languages).

## Sources
- Wispr, "Technical challenges and breakthroughs behind Flow": https://wisprflow.ai/post/technical-challenges
- Baseten customer story, Wispr Flow: https://www.baseten.co/resources/customers/wispr-flow/
- Wispr, "Canto: a speech model built for the real world": https://wisprflow.ai/canto
- Wispr docs, Smart Formatting & Backtrack: https://docs.wisprflow.ai/articles/5373093536-how-do-i-use-smart-formatting-and-backtrack
- Wispr docs, dictionary: https://docs.wisprflow.ai/articles/4052411709-teach-flow-your-words-with-the-dictionary
- Wispr data controls: https://wisprflow.ai/data-controls
- Patents assigned to Wispr AI: https://patents.justia.com/assignee/wispr-ai-inc
- Fortune on the $2B round: https://fortune.com/2026/08/17/wispr-2-billion-valuation-dictations-only-the-beginning/
- "Mind the Pause" (ACL 2026): https://arxiv.org/pdf/2605.12242
- Disfluency detection with LLMs (STIL 2024): https://aclanthology.org/2024.stil-1.16
- US 11556722: https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/11556722
- Context-awareness reports (third-party): https://getspeakup.app/blog/wispr-flow-screenshots-privacy/ , https://www.getvoibe.com/resources/is-wispr-flow-safe/
- Open-source local clones: https://github.com/RohitAg13/openWispr , https://openwhispr.com/compare/wisprflow , https://github.com/Micaxes/whispr-bro/issues/1
