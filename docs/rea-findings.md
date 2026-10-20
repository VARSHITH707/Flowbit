# REA findings: installed Wispr Flow 1.6.1174 (read-only)

Tool: `rea-agents@6.7.0 analyze-javascript-application ... --integrity-policy record-and-continue` on `resources/app.asar` (135 MB).
Raw output: `.rea/analysis.json` (208 MB, local only, gitignored). Labels: **V** verified by REA output, **A** assumed, **U** unknown.

## Inventory (V)
- Electron app, Squirrel-installed. 228 ASAR entries, 211 JS files parsed, 2339 modules, 0 parse failures, 29 source maps.
- Webpack bundles: `.webpack/main` and `.webpack/renderer`.
- Native add-ons (5, inventory only, not decompiled): `node_sqlite3.node`, `crypt32-x64.node` / `crypt32-ia32.node` (Windows cert store), and two hashed `.node` files in `app.asar.unpacked` (purpose **U**).
- Side-car binary `resources/Release/Wispr Flow Helper.exe` and `ax-inspect*.mjs` scripts (present on disk **V**; behaviour **U**, not analysed).
- REA integrity check flagged 3 unpacked native files whose hashes differ from the ASAR header. Normal after code signing; analysed with `record-and-continue`.

## Questions from the checklist
| Question | Finding | Label |
|---|---|---|
| Audio capture | Renderer contains `recorderWorklet.js` (a Web Audio AudioWorklet), so audio is captured in the Chromium renderer, not a native module. | V (file) / A (that it feeds dictation) |
| Hotkeys | No hotkey library found by module name. Likely done by `Wispr Flow Helper.exe` (low-level keyboard hook). | A |
| Text insertion | No clipboard/robot module by name. Likely the helper (paste / simulated keys). | A |
| Context awareness | `accessibility_drop/index.js` + `preload.js` and `ax-inspect*.mjs`: reads the focused app/field via the accessibility API to adapt formatting. | V (files) / A (use) |
| State/UI | `zubridge:*` IPC (Zustand state bridged between main and renderer windows). 10 literal channels, 90 dynamic. 36 `contextBridge` APIs. | V |
| Local storage | `node_sqlite3` so history/dictionary is a local SQLite DB. | V (module) / A (content) |
| Local vs cloud | Bundled HTTP client endpoints are mostly OpenAI-SDK paths (`/audio/transcriptions`, `/chat/completions`, `/realtime/...`) plus a Braintrust-style client. These are bundled SDK code, so they show *capability*, not which calls are made. No local speech model files found in the install. | A: transcription is cloud-side. U: exact provider. |
| Word limit enforcement | Not visible client-side in module names. A weekly quota tied to an account is almost certainly enforced by their server. | A |
| Recording states | Not extracted. Public UI shows idle / listening / processing. | U (see public section) |

## Implication for our build
There is no client-side quota to "remove": the cloud service is the limit. A local Whisper engine avoids it entirely and needs nothing from this app. We copy no code, assets, or endpoints; only the high-level design (renderer audio capture, native helper for hotkeys/insertion, accessibility context).

## Limits of this analysis
Native helper and `.node` files not decompiled (no Ghidra/IDA installed). Dynamic IPC channels (90) unresolved. Findings about hotkeys and insertion are inferences, to be confirmed by our own testing, not by deeper analysis of their binary.

## Public sources (wisprflow.ai home page; docs.wisprflow.ai hotkey article; web search)
- V (official page): dictates into any app ("types wherever your cursor is"); removes fillers, adds punctuation, applies mid-sentence corrections, formats lists/paragraphs. 100+ languages with auto-detect. Auto/manual personal dictionary. Per-app tone (formal / casual / very casual). Snippets (spoken shortcut inserts saved text). Mac, Windows, iOS, Android.
- V (official page): Free plan = 2,000 words/week; Pro = unlimited. Third-party pages disagree on details, so treat only the official figure as reliable.
- V (official docs, via search): push-to-talk = hold a key/mouse button; hands-free = double-tap to start/stop. Command Mode needs a paid plan. Default hands-free hotkey on Windows reported as Ctrl+Win+Space (older page, A).
- A: processing is cloud-based with an account (consistent with REA findings above).
- U: exact UI states/animations, onboarding steps, error messages.
