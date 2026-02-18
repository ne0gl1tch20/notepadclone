# Context Summary

## Docs Updated
- Last docs sync: 2026-02-17
- Synced files: `CHANGELOG.md`, `APP_SUMMARY.md`, `CONTEXT_SUMMARY.md`

## Current Focus
- You are building a Notepad++-style editor clone in PySide6.
- Recent work has focused on AI UX, localization, tab lifecycle UX, icon theming consistency, and regression tests.

## Latest Completed Changes
- Added AI chat dock panel on the left:
  - Ask AI opens/focuses panel.
  - Message bubbles with live generation streaming.
  - Cancel/Stop in-flight generation.
  - Per-message Copy + Insert-to-tab actions.
  - Chat history persistence in settings (`ai_chat_history`).
- Added explicit missing API key guidance message with settings path and API key URL.
- AI explain-selection prompt now uses:
  - `Explain this text: {selection}`
- Added runtime translation infrastructure:
  - Google Translate-backed translation helper.
  - On-disk translation cache + clear-cache action.
  - Broader menu/action/widget/status translation coverage.
- Moved app preference commands to a top-level `Settings` menu:
  - `Preferences...` (renamed from Settings)
  - `Shortcut Mapper...`
- Removed `Generate Text to Tab` from AI actions/menu.
- Added AI and updater unit tests.
- Updated app/context summary docs.
- Updated tab-close UX:
  - Tabs remain draggable/detachable.
  - Closing the last tab now shows an empty-state prompt instead of auto-creating a new tab:
    - `You don't have any tabs ;( Just click File > New!`
- Enforced semantic SVG icon coloring by theme:
  - Light mode: black icons (`#000000`)
  - Dark mode: white icons (`#ffffff`)
  - Applied to both main-window SVG icons and AI panel SVG icons.
- Fixed theme consistency regressions:
  - Search toolbar controls now follow active theme colors.
  - Status-bar language combo now follows active theme colors.
  - AI chat dock now uses effective dark/light detection to avoid mixed-mode rendering.
- Updated Preferences dialog theming for consistent dark/light appearance across panels, inputs, lists, and buttons.
- Accent color preview now applies dialog theme updates live immediately when accent is picked or cleared.
- Fixed icon-loading and rendering regressions:
  - Corrected dev asset-root resolution to load from `assets/`.
  - Added missing SVG toolbar icons to remove placeholder/paper icons.
  - Fixed tab close icon color in light mode via explicit light/dark icon assets.
  - Fixed SVG monochrome recolor pipeline so icons no longer render blank.
- Updated version/changelog:
  - `assets/version.txt` now `1.6.5-prerelease`
  - `CHANGELOG.md` includes `1.6.5-prerelease` entry.
- Added dedicated top-level `Search` menu and moved/expanded search workflows:
  - Notepad++-style find variants, Go To, Mark, Change History, style/copy-styled actions
  - Extended bookmark line operations in Search -> Bookmark
- Expanded `View` menu substantially with Notepad++-style entries:
  - Always on Top, Post-it, Distraction Free
  - View Current File in, Show Symbol submenu, Fold/Unfold level controls
  - Project panel shortcuts and text direction RTL/LTR
- Implemented true Scintilla line hiding:
  - `Hide Lines` now hides selected/current lines via Scintilla
  - `Show Hidden Lines` restores hidden lines

## Key Architecture (Current)
- Main window class:
  - `src/notepadclone/ui/main_window/window.py` (`Notepad`)
- Mixins:
  - `ui_setup.py`, `file_ops.py`, `edit_ops.py`, `view_ops.py`, `misc.py`
- Settings system:
  - `src/notepadclone/ui/main_window/settings_dialog.py`
  - `src/notepadclone/app_settings/defaults.py`
  - `src/notepadclone/app_settings/coercion.py` (schema migration/coercion)
- AI system:
  - `src/notepadclone/ui/ai_controller.py`
  - `src/notepadclone/ui/ai_chat_dock.py`
- Localization:
  - `src/notepadclone/i18n/translator.py`
- Entry points:
  - `src/run.py` (splash/startup logs/timing)
  - `src/notepadclone/app.py` (app bootstrap + global exception hook)

## Packaging and Build
- Build script: `compile.bat`
- PyInstaller spec: `run.spec`
- Dist output expected in `dist/`

## Tests Present
- `tests/test_settings_migration.py`
- `tests/test_settings_dialog_mapping.py`
- `tests/test_settings_apply_runtime.py`
- `tests/test_shortcut_mapper.py`
- `tests/test_ai_controller.py`
- `tests/test_updater_controller.py`

## Open Tabs / Working Files (from latest context)
- `src/run.py`
- `CHANGELOG.md`
- `src/notepadclone/ui/ai_controller.py`
- `assets/version.txt`

## Next Easy Resume Point
1. Launch app and verify AI chat panel UX end-to-end:
   - Ask AI opens panel.
   - Streaming tokens render as Markdown.
   - Stop/Cancel works.
   - Copy/Insert bubble actions work.
2. Verify tab lifecycle UX:
   - Last tab closed -> empty-state screen appears.
   - File > New returns from empty state to normal tab view.
3. Verify icon theming:
   - Light mode SVG icons render black.
   - Dark mode SVG icons render white.
4. Verify toolbar/menu icon coverage:
   - No placeholder/paper icons remain.
   - No blank SVG icons under either theme.
5. Verify Preferences accent color behavior:
   - Picking/clearing Accent color updates the dialog theme immediately without reopening.
6. Run full test suite and add any missing UI tests for chat panel and empty-state behavior.

If QScintilla is unavailable, the editor falls back to `QTextEdit`; advanced Scintilla-only features are gated accordingly and we use methods for a sinctilla look.

Every time you add a new svg, make any script support it for both dark and light mode.