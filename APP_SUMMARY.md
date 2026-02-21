# Pypad - Full App Summary

## 1) Product Summary
Pypad is a PySide6 desktop text editor with:
- Multi-tab editing (detachable + reorderable tabs)
- Markdown tooling and live preview
- Unified editor widget API with optional advanced backend support
- Workspace browsing/search/replace
- Version history, autosave, and crash recovery
- Note encryption (`.encnote`)
- AI generation/explanation/chat (Gemini-compatible SDKs)
- Update checking/downloading from XML feed
- Sidebar settings system with schema migration
- Shortcut mapper with presets/import/export
- Runtime UI translation with Google Translate + local translation cache

Entry points:
- `src/run.py` (splash, startup timing, boot)
- `src/notepadclone/app.py` (creates app window and global exception hook)
- `src/notepadclone/ui/main_window/window.py` (`Notepad` main window class)

## 2) UI Architecture
Main window class composition:
- `Notepad(UiSetupMixin, FileOpsMixin, EditOpsMixin, ViewOpsMixin, MiscMixin, QMainWindow)`

Main responsibilities by module:
- `src/notepadclone/ui/main_window/ui_setup.py`: actions, menus, toolbars, tab icon rendering, setup wiring
- `src/notepadclone/ui/main_window/file_ops.py`: file open/save/save-as/export/print
- `src/notepadclone/ui/main_window/edit_ops.py`: edit/find/replace flows
- `src/notepadclone/ui/main_window/view_ops.py`: zoom/fullscreen/wrap/focus/view toggles
- `src/notepadclone/ui/main_window/misc.py`: settings apply/load/save, autosave, recovery, session, tab context logic, summary, macros, bookmarks

Core tab model:
- `src/notepadclone/ui/editor_tab.py` contains per-tab state:
  - file path, zoom, language override, markdown mode
  - pinned/favorite/read-only/color/tags
  - encoding and EOL mode
  - bookmarks, split/clone state
  - column mode, multi-caret, folding flags
  - version history, autosave ids
  - encryption state/password (in-memory)

Editor abstraction:
- `src/notepadclone/ui/editor_widget.py`
  - Uses `PySide6.Qsci.QsciScintilla` when available
  - Falls back to `QTextEdit` if QScintilla is missing
  - Normalizes text, selection, cursor, editing APIs for both backends

## 3) Menus and Commands
Top menus:
- File
- Edit
- Search
- Format
- View
- Settings
- Tools
- Macros
- Markdown
- Plugins
- Help

File menu highlights:
- New/Open/Save/Save As/Save All
- Close Tab, Close All Tabs
- Close Multiple Documents:
  - Close All But Active
  - Close All But Pinned
  - Close All To The Left
  - Close All To The Right
  - Close All Unchanged
- Print + Print Preview
- Pin/Favorite/Tags
- Templates (new from template + insert template)
- Export (PDF/Markdown/HTML)
- Encoding (UTF-8/UTF-16/ANSI) + EOL (LF/CRLF)
- Workspace (set/open/search)
- Session (save/load session files)
- Security (enable/disable/change note encryption password)
- AI actions (Ask AI, Explain Selection)
- Recent Files + Favorite Files

Edit/Search/View/Markdown highlights:
- Dedicated Search menu:
  - Find/Find Next/Find Previous/Replace/Replace in Files
  - Find in Files, Select-and-Find next/previous, volatile find actions
  - Incremental search, Go To, Mark, change-history navigation
  - Token styling (style all/one, clear style, jump/copy styled text)
  - Bookmark line operations (cut/copy/replace/remove/invert bookmarked lines)
- Bookmark set/next/previous/clear
- Word wrap/font/format actions
- Zoom in/out/reset
- Document Summary dialog
- Full screen + Focus mode
- Always-on-top, Post-it mode, distraction-free mode
- View Current File in (Explorer/default viewer/CMD), text direction RTL/LTR
- Column mode + Multi-caret + Code folding
- QScintilla line hiding with restore:
  - Hide Lines
  - Show Hidden Lines
- Split/clone view actions
- View toggle for AI Chat Panel (left dock)
- Markdown formatting and preview actions

## 4) Toolbar Layout
Top rows are rebuilt dynamically to prevent empty/ghost rows:
- Main toolbar row (editing + file/view actions)
- Markdown toolbar row (toggleable, hidden by default)
- Find panel row (toggleable, hidden by default)

Toolbar behavior is driven by settings:
- `show_main_toolbar`
- `show_markdown_toolbar`
- `show_find_panel`
- `icon_size_px`
- `toolbar_label_mode`
- `ui_density`

## 5) Tab System
Tab capabilities:
- Closable tabs (with styled red close button)
- Draggable tab reorder
- Detach tab to new window (`DetachableTabBar`)
- Right-click tab context menu with file operations and metadata actions
- Pin/favorite/read-only markers overlaid on tab icon
- Extension-aware base tab icon selection
- Per-tab color customization
- Read-only support and file attribute integration

Tab icon logic:
- Base icon by file extension (`.py`, `.md`, `.json`, `.js`, `.ts`, `.html`, etc.)
- Overlay icons for pin, favorite, read-only states
- Both pin and favorite overlays can appear together

## 6) Editing and Text Features
General editing:
- Undo/redo/cut/copy/paste/delete/select all
- Time/date insert
- Find panel with highlight-all + match case
- Replace in current file and across workspace files

Advanced (QScintilla path):
- Column selection mode
- Multi-caret editing
- Code folding
- Bookmarks rendered as margin markers
- Symbol visibility toggles (space/tab, EOL, non-printing/control chars, indent guide, wrap symbol)
- Line hiding/showing support via Scintilla commands

Markdown features:
- Heading levels 1..6
- Bold/italic/underline/strikethrough
- Lists, tasks, blockquote, links, images, table, horizontal rule
- Inline code + fenced code block
- Live markdown preview pane toggle
- Markdown toolbar visibility toggle

Syntax highlighting:
- Language modes: Auto, Python, JavaScript, JSON, Markdown, Plain
- Per-tab language override via status bar combo

Document summary (View -> Document Summary):
- File path
- Created and modified timestamps (when file exists)
- Character count (excluding line endings)
- Word count
- Line count
- Selected character count
- Selected byte count (UTF-8)
- Selected range with line/column and index range

## 7) Workspace and File Operations
Workspace features:
- Choose workspace root folder
- List workspace files via dialog
- Search query across workspace files
- Replace in Files with:
  - plain text or regex
  - case sensitivity
  - skip modified open tabs option
  - reload unmodified open tabs after replacement

Media insertion:
- Inserts media paths
- In markdown mode, images are inserted as markdown image links

Drag and drop:
- Handles dropped files/media into editor

## 8) Version History, Autosave, Recovery, Session
Version history:
- Per-tab snapshot history with max entries/interval settings
- Diff preview dialog

Autosave:
- Periodic autosave to roaming app data directory
- Per-tab autosave ids and files

Crash recovery:
- Recovery dialog on startup when autosave entries exist
- Restore/discard selected entries
- Startup callback marks app as started and dismisses splash correctly during recovery

Session management:
- Save session JSON
- Save Session As / Load Session
- Restore last session at startup (if enabled)
- Tracks active file and workspace root

## 9) Security and Privacy
Note encryption:
- Optional per-note encryption toggle
- Uses `.encnote` payload format helpers in `src/notepadclone/ui/note_crypto.py`
- Password prompt on open/save for encrypted notes
- Password stored in memory per tab/session only

App privacy lock:
- Optional lock screen on app open
- Unlock via password or PIN

Credential persistence model:
- App settings in `settings.json`
- Password/PIN data in `password.bin` (separate file)
- Plaintext password/PIN are cleared from persisted settings payload

## 10) AI and Updates
AI:
- Ask AI opens/focuses a left dock chat panel with message bubbles
- Chat supports live generation streaming and cancel-in-flight
- Assistant bubbles include per-message Copy and Insert-to-tab actions
- Chat history persists in settings (`ai_chat_history`)
- Explain Selection prompt format: `Explain this text: {selection}`
- Async worker threads for standard dialog-based flows are still available
- Supports `google-genai` path with fallback to `google-generativeai`
- API key from settings or `GEMINI_API_KEY` env var
- Missing key message includes direct settings path and API key URL

Updater:
- Reads local app version from `assets/version.txt`
- Checks XML update feed URL
- Compares semantic-ish version tuples
- Shows changelog/update prompt
- Downloads update asset to chosen location
- Can open installer path directly

## 11) Settings System
Settings dialog:
- Sidebar category layout (`src/notepadclone/ui/main_window/settings_dialog.py`)
- Search/filter that highlights matching controls
- Category count badges during search
- Apply / OK / Cancel / Restore Defaults
- Profile import/export
- Backup/restore actions
- "Edit with settings.json" action opens settings JSON inside the app

Category set:
- Appearance
- Editor
- Tabs
- Workspace
- Search
- Shortcuts
- AI & Updates
- Privacy & Security
- Backup & Restore
- Advanced

Schema/migration:
- Defaults: `src/notepadclone/app_settings/defaults.py`
- Migration/coercion: `src/notepadclone/app_settings/coercion.py`
- Current target schema version: `2`
- Normalizes enums, booleans, colors, and numeric ranges
- Preserves unknown keys where possible
- Includes language setting and translation cache clear action

Settings storage paths:
- `settings.json`
- `password.bin`
- `reminders.json`
- `autosave/`
- Path utilities in `src/notepadclone/app_settings/paths.py`

## 12) Shortcut Mapper
Module:
- `src/notepadclone/ui/shortcut_mapper.py`

Capabilities:
- Presets: `default`, `vscode`, `notepad++`, `sublime`
- Action table: action name + current shortcut + set/reset controls
- Key capture dialog for direct shortcut recording
- Conflict policy: `warn`, `block`, `allow`
- JSON import/export for maps/profiles
- Apply live to all QAction shortcuts
- Persist to settings immediately on apply

Access points:
- Settings menu action `Shortcut Mapper...`
- Shortcut section in Settings dialog

## 13) Recent UI/Theming Updates
- Added an always-available AI chat dock title bar and per-control theme refresh behavior.
- Standardized toolbar icon sourcing to app SVG assets for better cross-platform consistency.
- Added missing SVG toolbar icons (new/open/save/save-all, cut/copy/paste, undo/redo, print, zoom in/out).
- Fixed development asset-root resolution so icons consistently load from `assets/icons`.
- Added theme-aware tab close icons:
  - Light mode uses dark close glyph.
  - Dark mode uses light close glyph.
- Improved theme consistency for:
  - search toolbar controls
  - status bar language combo
  - preferences dialog controls and live accent preview updates
- Hardened SVG recoloring so icons no longer render blank when forcing monochrome black/white.

## 14) Startup, Splash, Logging
Startup sequence (`src/run.py`):
- Resolve assets for dev and PyInstaller contexts
- Load splash image + splash font
- Read and print version from `assets/version.txt`
- Show startup console logs:
  - version
  - waiting message
  - startup elapsed ms/sec
- Uses callback property `startup_ready_callback` so the app can mark startup complete from recovery flow too

Main app error handling:
- Global `sys.excepthook` is replaced to log errors into app debug log stream

## 15) Packaging and Build
PyInstaller:
- Spec file: `run.spec`
- Build script: `compile.bat`
- Includes `assets` bundle and optional QScintilla handling

Build flow in `compile.bat`:
- Check optional `PySide6.Qsci`
- Run `pyinstaller --clean --noconfirm run.spec`
- Output executable in `dist/`

## 16) Tests and Coverage Targets
Current tests include:
- `tests/test_settings_migration.py`
- `tests/test_settings_dialog_mapping.py`
- `tests/test_settings_apply_runtime.py`
- `tests/test_shortcut_mapper.py`
- `tests/test_ai_controller.py`
- `tests/test_updater_controller.py`

Covered areas:
- Settings migration and coercion
- Settings dialog mapping/apply/cancel/defaults behavior
- Runtime apply behavior for key UI toggles
- Shortcut mapper parsing/preset/import/export/conflict handling

## 17) Known Design Notes
- QScintilla is optional; advanced editor features degrade gracefully when unavailable.
- Some newly added settings keys are validated and persisted even where runtime hooks are still minimal.
- First-run tutorial is interactive (`InteractiveTutorialDialog`) and animated (fade transitions).

---

If you want, next step can be a generated "feature matrix by menu item -> method -> settings keys -> tests" table for faster debugging and maintenance.

