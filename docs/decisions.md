# Decisions
- D1: Python 3.11 via uv (py launcher lacks 3.11). venv at .venv.
- D2: REA MCP tools not loaded in this session; use `npx rea-agents <cmd>` CLI (same workflows, per REA README). Read-only on the Wispr Flow install.
- D3: Default model large-v3-turbo (see benchmark.md); small as fast option. TTS clips used as the checkable reference.
- D4: On Windows without Developer Mode HF cache copies instead of symlinking (uses more disk, harmless); set HF_HUB_DISABLE_SYMLINKS_WARNING=1.
- D5: Automated insertion tests use an owned Tk window (reads back reliably). Win11 Notepad restores old tabs and a helper I wrote killed that process once (user's saved LICENSE tab; file on disk untouched), so no more process kills. Notepad/browser checks are run separately and carefully.
- D6: Insertion policy: type short single-line text (SendInput Unicode); paste (Ctrl+V with save/restore) for multi-line or >200 chars; if the clipboard holds non-text data, never overwrite it (type instead). Focus changed or insert failed -> copy to clipboard, never paste elsewhere.
