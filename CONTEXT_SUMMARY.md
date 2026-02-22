# Context Summary

## Docs Updated
- Last docs sync: 2026-02-22
- Synced file: `CONTEXT_SUMMARY.md`

## Current Focus
- PyPad (`src/pypad`) desktop editor UX and AI workflow integration.
- Recent work focused on Settings/Preferences unification (PyPad + N++ compatibility), runtime settings hooks, logging/diagnostics, and AI chat instrumentation/UI polish.

## Latest Completed Changes
- Logging and diagnostics overhaul:
  - centralized logging configuration with user-selectable global logging level in Preferences
  - process-wide console capture added to Debug Logs dialog (root logger + stdout/stderr)
  - verbose DEBUG instrumentation added across AI controller/chat, updater, autosave, and file operations
  - AI chat response correlation IDs (`cid`) thread stream -> parse -> hidden command apply confirmation logs

- AI Chat panel UX and tracing improvements:
  - OpenAI-style attachment chips above prompt input (icon + file name + remove button)
  - attachment chips wrap onto multiple lines in narrow dock widths
  - hidden command extraction / apply-preview / deep-link handling have detailed DEBUG traces
  - `ai_verbose_logging` user-facing messages include `cid` when available

- Editor right-click context menu upgrade:
  - rich Notepad++-inspired menu with AI and PyPad submenus
  - quick AI row (`Explain`, `Rewrite`, `Attach`, `More AI...`)
  - SVG icons, style submenu with swatches, native edit action ordering, dynamic submenu hiding

- Preferences / settings overhaul (PyPad + N++ compatibility):
  - large set of Notepad++-style compatibility pages added and persisted
  - settings nav redesigned with mixed PyPad/N++ grouping, scope filters, page header card, search/tooltips
  - N++ dark mode page merged into PyPad `Appearance` as embedded compatibility section
  - content layout refined (non-stretch controls, fixed max width, left-aligned content, wider nav, forced nav scrollbar)
  - additional Notepad++-vibe pass: tighter nav rows, subtle `PyPad Core` / `N++ Compatibility` separators, fixed-width form labels

- N++ compatibility runtime hooks added:
  - new-document encoding/EOL defaults applied on tab creation
  - indentation defaults + per-language overrides applied at runtime (new tabs and settings apply)
  - print margins and header/footer template settings applied during print/preview
  - AI chat external clickable links filtered by allowed URI schemes from settings

- Per-language indentation override table improvements:
  - editable language dropdown (pre-populated + custom text allowed)
  - inline validation coloring/tooltips (empty/duplicate language rows)
  - save/apply blocked on invalid rows, with dialog and auto-focus on first invalid row

- Dialog theming consistency:
  - `Recover Unsaved Notes` dialog synced to app dark/light + accent theme
  - startup recovery dialog now appears in taskbar correctly (top-level when main window hidden)
  - reusable global dialog theme filter added for utility dialogs and quick prompts

- AI file actions now route through AI Chat panel and hidden commands (instead of direct modal-only flows in several paths):
  - hidden full-file apply command support added (`PYPAD_CMD_SET_FILE_*`)
  - local yes/no confirm flow applies full file replacement in the current tab
  - file-oriented AI actions use chat prompts that request hidden apply commands
- AI built-in knowledge updated to document hidden commands:
  - insert offer (`PYPAD_CMD_OFFER_INSERT_*`)
  - full file replace (`PYPAD_CMD_SET_FILE_*`)
  - chat title set (`PYPAD_CMD_SET_CHAT_TITLE_*`)
- AI menu labels/tooltips updated to reflect "AI Chat Apply" behavior.

- AI Chat panel upgraded substantially:
  - separate saved chat sessions (`ai_chat_sessions`, `ai_chat_active_session_id`)
  - `Start` menu with:
    - New chat
    - Rename / Pin / Archive / Delete
    - Add current chat to project
    - saved/archived chat switching
  - embedded live filter inside `Start` menu (`Filter chats...`)
  - dialog search (`Search Chats...`) still present
  - chat transcript export to workspace (`.pypad_ai_chats/*.md`)
  - per-panel model button (`Model: ...`) to change `ai_model`

- Chat title behavior changed:
  - no longer set from first user prompt
  - no visible-response parsing heuristics for title
  - title is set by separate hidden title command only (`PYPAD_CMD_SET_CHAT_TITLE_*`)
  - local silent fallback added:
    - if first assistant response lacks title command, app makes a silent follow-up AI call asking only for a hidden title command
  - defensive base64 decoding added in title apply path to avoid raw base64 appearing as title

- AI chat rendering/parsing fixes:
  - safer `pypad://` link rendering via placeholder replacement after markdown->HTML conversion
  - normalized `pypad://` URLs to strip trailing markdown punctuation/emphasis (e.g. `**`)
  - hidden command parsing extended and hardened

- AI chat UI polish:
  - dedicated `ai-clear.svg` added and wired to Clear button
  - assistant bubbles use UI sans-serif font (less editor-like)
  - tighter list/paragraph spacing in assistant messages
  - session title label restyled to not look like an input field
  - clear/send/stop button icon setup unified

- Preferences / settings:
  - modern `Settings > Preferences > Layout` now exposes:
    - `Enable autosave (draft recovery)`
    - `Autosave interval (sec)`
  - existing `autosave_enabled` / `autosave_interval_sec` settings keys used

- Editor state sync:
  - active tab modified flag now syncs with on-disk file content:
    - file text matches buffer => marked saved
    - differs => marked unsaved
  - skipped for encrypted notes and partial large-file previews

## Key Architecture (Current)
- Main window class:
  - `src/pypad/ui/main_window/window.py` (`Notepad`)
- Mixins:
  - `src/pypad/ui/main_window/ui_setup.py`
  - `src/pypad/ui/main_window/file_ops.py`
  - `src/pypad/ui/main_window/edit_ops.py`
  - `src/pypad/ui/main_window/view_ops.py`
  - `src/pypad/ui/main_window/misc.py`
- Settings system:
  - `src/pypad/ui/main_window/settings_dialog.py`
  - `src/pypad/app_settings/defaults.py`
  - `src/pypad/app_settings/coercion.py`
- AI system:
  - `src/pypad/ui/ai_controller.py`
  - `src/pypad/ui/ai_chat_dock.py`
  - `src/pypad/ai_app_knowledge.py`
- Entry points:
  - `src/run.py`
  - `src/pypad/app.py`

## Packaging and Build
- Build script: `compile.bat`
- PyInstaller spec: `run.spec`
- Dist output: `dist/` (expected)

## Tests Present (selected)
- `tests/test_settings_migration.py`
- `tests/test_settings_dialog_mapping.py`
- `tests/test_settings_apply_runtime.py`
- `tests/test_shortcut_mapper.py`
- `tests/test_ai_controller.py`
- `tests/test_updater_controller.py`

## Current Working Context
- Active file lately: `src/run.py`
- Most recent implementation work concentrated in:
  - `src/pypad/ui/ai_chat_dock.py`
  - `src/pypad/ui/ai_controller.py`
  - `src/pypad/logging_utils.py`
  - `src/pypad/ui/autosave.py`
  - `src/pypad/ui/dialog_theme.py`
  - `src/pypad/ui/main_window/misc.py`
  - `src/pypad/ui/main_window/ui_setup.py`
  - `src/pypad/ui/main_window/settings_dialog.py`
  - `src/pypad/ui/main_window/settings_notepadpp_pages.py`
  - `src/pypad/ui/main_window/notepadpp_pref_runtime.py`
  - `src/pypad/app_settings/notepadpp_prefs.py`
  - `src/pypad/ai_app_knowledge.py`
  - `src/pypad/ui/icons/ai-clear.svg`

## Next Easy Resume Point
1. Visual QA `Settings > Preferences` on dark and light themes:
   - nav separators (`PyPad Core`, `N++ Compatibility`) render cleanly
   - tighter nav rows do not clip emoji labels
   - fixed-width form labels align rows across major pages
2. Verify N++ compatibility runtime hooks:
   - new tab uses configured encoding/EOL defaults
   - indentation overrides apply per language on new/open tabs
   - print preview reflects header/footer template and margins
3. Verify AI chat external link filtering:
   - allowed schemes open
   - blocked schemes are prevented with message
4. Verify recovery and utility dialogs:
   - startup recovery dialog appears in taskbar
   - dark/light theming applies consistently to common prompts/dialogs
5. Verify DEBUG logs workflow:
   - set logging level to `DEBUG`
   - confirm process-wide console capture appears in Debug Logs dialog

Notes:
- If QScintilla is unavailable, editor falls back to `QTextEdit`; Scintilla-only features remain gated.
- When adding new SVG icons, ensure they work with the AI/main-window monochrome recolor pipeline in both light and dark themes.
