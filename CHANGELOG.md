# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog, and this project uses Semantic Versioning.

## [Unreleased]

## [1.6.11-prerelease] - 2026-02-19

### Changes
- No API key message navigation 

## [1.6.10-prerelease] - 2026-02-19

### Added
- Startup arguments now support opening folders as workspace roots (shows Workspace Files).

### Changed
- Startup file opening now keeps the first file active instead of switching to the last.

### Fixed
- Fixed workspace dialog acceptance check to use `QDialog.Accepted`, preventing a crash.

### Added
- New top-level `Search` menu with Notepad++-style actions and submenus:
  - Find in Files, Select-and-Find next/previous, Volatile find next/previous
  - Incremental Search, Go To, Mark, Change History, style/copy-styled workflows
  - Extended bookmark operations (cut/copy/replace/remove/invert bookmarked lines)
- Expanded `View` menu with richer Notepad++-style structure:
  - Always on Top, Post-it mode, Distraction Free mode
  - View Current File in (Explorer/default viewer/CMD)
  - Show Symbol submenu (space/tab, EOL, non-printing/control chars, indent guides, wrap symbol)
  - Fold/Unfold actions (all/current/level-based), text direction RTL/LTR, project panel shortcuts
- True QScintilla line-hiding support:
  - `Hide Lines` now uses Scintilla line hiding for selected/current lines
  - Added `Show Hidden Lines` (`Alt+Shift+H`) to restore hidden lines
- Command palette with fuzzy action search (`Ctrl+Shift+P`).
- AI rewrite quick actions for selected text:
  - shorten
  - formal
  - fix grammar
  - summarize
- AI rewrite diff preview dialog with selectable hunks before applying edits.
- AI prompt template workflow:
  - run saved/default templates
  - save custom templates
- Context-aware AI action: "Ask About This File...".
- AI usage meter in the status bar and session usage summary dialog.
- AI action history log (timestamp, action, model, prompt/response sizes).
- AI private mode toggle that blocks outgoing AI requests for sensitive work.
- Simple mode toggle and one-click UI presets:
  - Reading
  - Coding
  - Focus
- Experimental advanced feature pack:
  - Plugin system with permission model (`file`, `network`, `ai`) and Plugin Manager UI
  - Minimap dock + symbol outline dock + breadcrumbs
  - Basic go-to-definition and diff/merge helpers
  - Snippet engine + shared template packs
  - TODO/FIXME task workflow with due-date reminder sync
  - AI extras: file citations, commit/changelog drafting, batch refactor preview
  - Backup scheduler + diagnostics bundle export
  - Keyboard-only mode + accessibility presets
  - LAN collaboration baseline + annotation layer
- Plugin documentation:
  - `docs/plugins.md`
- Example plugin:
  - `plugins/example_word_tools`
- Windows shell integration commands in `run.py`:
  - `--register-shell-menu`
  - `--unregister-shell-menu`
  - Registers/removes `Open with Notepad Clone` for File Explorer context menu (current user).
- Inno Setup packaging support:
  - `installer/NotepadClone.iss`
  - `build_installer.bat`
  - Optional installer tasks for `.txt` association and context menu entry.
- Configurable backup output directory:
  - new setting key `backup_output_dir`
  - picker in Preferences `Backup & Restore`
  - used by Backup Scheduler and Run Backup Now.

### Changed
- Reassigned Pin Tab shortcut from `Ctrl+Shift+P` to `Ctrl+Alt+P` to avoid conflict with Command Palette.
- Toolbar overflow (`>>`) behavior reworked:
  - converted to right-edge overlay button instead of regular toolbar action
  - dynamic hidden-tools menu now uses proxy actions for reliable text entries.

### Fixed
- Prevented startup/runtime crashes from stale/deleted Qt action wrappers (`QWidgetAction` / `QAction`) by adding defensive `RuntimeError` guards in shortcut and tooltip/action wiring paths.
- Fixed overflow menu flicker while resizing/opening menus by avoiding layout-request-triggered rapid rebuilds.
- Fixed off-screen placement of overlay `>>` button by anchoring to toolbar `contentsRect()`.
- Fixed mojibake/garbled labels in Preferences navigation and buttons (emoji/category text).
- Fixed `build_installer.bat` parse error (`was was unexpected at this time`) caused by unescaped parentheses in a block `echo`.

## [1.6.9-prerelease] - 2026-02-18

### Changed
- Updated `notepad.xml` release feed metadata for `1.6.9-prerelease`.
- Refined updater UI flow with non-blocking update-available dialog behavior.
- Expanded updater debug logs with worker/thread lifecycle and feed parsing details.

### Fixed
- Fixed updater cross-thread UI interactions that could cause unresponsive behavior.
- Fixed overlapping/manual-vs-auto update check handling during startup checks.
- Fixed update check timeout behavior with watchdog cancellation for stalled network calls.

## [1.6.8-prerelease] - 2026-02-18

### Changed
- Updated release feed payload in `notepad.xml` for `1.6.8-prerelease` and new installer URL.
- Update checker now supports plain-text feed payloads as fallback when XML is malformed/non-XML.
- Update check timeout behavior tightened and watchdog timeout handling added.
- Updater debug logging expanded with detailed step-by-step traces.

### Fixed
- Fixed updater action signal wiring so manual update checks always run as manual checks.
- Fixed missing `QTimer` import in updater progress flow.
- Fixed updater cross-thread UI access that caused Qt parent/thread warnings and freeze-like behavior.
- Switched `Update Available` popup to non-blocking dialog flow to avoid nested event-loop lockups.

## [1.6.5-prerelease] - 2026-02-17

### Fixed
- Corrected asset path resolution in development mode so icons are loaded from `assets/` reliably.
- Replaced missing-toolbar placeholder/paper icons by adding SVG assets for:
  - `edit-cut`, `edit-copy`, `edit-paste`
  - `edit-undo`, `edit-redo`
  - `document-print`, `zoom-in`, `zoom-out`
  - `document-new`, `document-open`, `document-save`, `document-save-all`
- Fixed light-mode tab close icon color:
  - added explicit `tab-close-light.svg` / `tab-close-dark.svg` and theme-aware selection in QSS.
- Fixed SVG recolor pipeline regression that could make icons render blank:
  - monochrome recoloring now safely rewrites only valid `stroke`/`fill` attributes.

### Changed
- Main toolbar icon mapping now prefers project SVG icon assets consistently for clearer cross-platform appearance.

## [1.6.4-prerelease] - 2026-02-17

### Changed
- Fixed additional light/dark theming inconsistencies across main window UI:
  - Search toolbar labels, checkboxes, input, and action buttons now follow active theme colors.
  - Status bar language combo and dropdown list now follow active theme colors.
- Fixed AI panel theme mode detection to use effective icon/text brightness, preventing mixed light/dark panel states.
- Updated main-window SVG tinting to use effective icon color (`_icon_color`) first, then dark-mode fallback.
- Added dedicated Preferences dialog styling for dark/light mode so its panels, lists, inputs, and buttons are consistently themed.
- Accent color preview in Preferences now updates dialog theme immediately when picking or clearing accent color.

## [1.6.3-prerelease] - 2026-02-17

### Changed
- Enforced strict SVG icon coloring by theme:
  - Light mode: all rendered SVG icons use black (`#000000`).
  - Dark mode: all rendered SVG icons use white (`#ffffff`).
- Updated main window SVG icon renderer to use black/white semantic icon colors.
- Updated AI panel SVG icon renderer to use black/white semantic icon colors.

## [1.6.2-prerelease] - 2026-02-17

### Changed
- AI panel now enforces SVG icon usage with in-memory tinted icon rendering.
- Light mode AI icons are recolored to dark/black tones in memory.
- Dark mode AI icons are recolored to light tones in memory.
- AI panel icon cache now refreshes correctly when theme changes.
- AI panel message action icons are refreshed after theme changes.

## [1.6.1-prerelease] - 2026-02-17

### Added
- Left-dock AI Chat Panel with:
  - message bubbles
  - live streaming generation
  - cancel/stop in-flight generation
  - per-message copy and insert-to-tab actions
- AI chat history persistence in settings (`ai_chat_history`).
- Runtime translation support using Google Translate with on-disk translation cache.
- Translation cache clear action in preferences.
- New AI/chat icon assets:
  - `assets/icons/ai-send.svg`
  - `assets/icons/ai-stop.svg`
  - `assets/icons/ai-copy.svg`
  - `assets/icons/ai-insert.svg`
- New tests:
  - `tests/test_ai_controller.py`
  - `tests/test_updater_controller.py`

### Changed
- Top-level `Settings` menu introduced; moved:
  - `Preferences...` (renamed from `Settings...`)
  - `Shortcut Mapper...`
- `Ask AI...` now opens/focuses the AI Chat Panel.
- Explain-selection AI prompt now uses:
  - `Explain this text: {selection}`
- Missing API key error now provides direct setup instructions and API key URL.
- AI chat bubbles now render Markdown content, including streamed responses.
- Dark mode bubble styling updated to gray-black backgrounds with white text.

### Removed
- `Generate Text to Tab` action from AI menu/workflow.
