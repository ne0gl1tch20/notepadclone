# Pypad 📝

A desktop notes editor built with `PySide6` featuring markdown, reminders, autosave recovery, workspace search, per-note encryption, and AI helpers 🤖.

## Run

```bash
cd notepadclone/src
python run.py
```

Expected layout in development:

- `src/run.py`
- `assets/icons/*.svg`

## Features

- Multi-tab editor with detachable tabs 🗂️
- Middle-click tab close
- Markdown formatting and live preview ✨
- Syntax highlighting with per-tab language picker
- QScintilla power editing: column mode, multi-caret, code folding, bookmarks
- Search panel with highlight-all
- Version history with diff preview ♻️
- Autosave and crash recovery
- Reminders, recurrence, and snooze ⏰
- Templates (meeting, daily log, checklist)
- Export to PDF, Markdown, HTML
- Favorites, pinned tabs, tags 📌♥
- Workspace folder browser and search across files
- Drag-drop media insertion for markdown/text notes
- Per-note encryption (`.encnote`) 🔐
- AI actions:
  - Ask AI
  - Explain selected text
  - Generate text to current tab
  - Async generation + result panel (copy/insert/replace)
- Update checker with changelog + download/install support from update XML feed
- Interactive first-run tutorial with fade animation ✨
- Sidebar-based Settings with search/filter and profile import/export ⚙️

## AI Setup (Gemini)

Install optional dependency:

```bash
pip install google-genai
```

Install QScintilla dependency for advanced editor features:

```bash
pip install PySide6-QScintilla
```

Set your API key (either in app settings or env var):

```bash
# Windows PowerShell
$env:GEMINI_API_KEY="your_api_key_here"

# Linux/macOS
export GEMINI_API_KEY="your_api_key_here"
```

AI settings:

- `Settings -> AI & Updates -> Gemini API key`
- `Settings -> AI & Updates -> Model` (default `gemini-3-flash-preview`)
- Result panel actions: `Copy`, `Insert`, `Replace Selection`

Update settings:

- `Settings -> AI & Updates -> Update feed URL`
- `Settings -> AI & Updates -> Check for updates on startup`
- Manual check: `Help -> Check for Updates...`

## Encryption Notes

- Enable from `File -> Security -> Enable Note Encryption...`
- Save encrypted notes as `.encnote`
- Opening encrypted notes prompts for password
- Password is kept in-memory per open tab/session and is not written to settings

## Workspace Notes

- Set workspace via `File -> Workspace -> Open Workspace Folder...`
- Browse workspace files from `Workspace Files...`
- Search text across workspace from `Search Workspace...`

## Plugins

Pypad includes a local plugin system with permission-based capabilities.

- Open manager: `Settings -> Plugin Manager...`
- Plugin docs: `docs/plugins.md`
- Plugin folder layout:
  - `plugins/<plugin_folder>/plugin.json`
  - `plugins/<plugin_folder>/plugin.py`

Supported permissions:

- `file`: allows file/text write operations through plugin API
- `network`: allows network-capability checks through plugin API
- `ai`: allows plugin-triggered AI requests through plugin API

Included examples:

- `plugins/example_word_tools` (`file`, `ai`)
- `plugins/example_hello_network` (`network`)

## Project Structure

- `src/notepadclone/ui/main_window/window.py`: main UI shell and integration points
- `src/notepadclone/ui/asset_paths.py`: dev/PyInstaller asset path resolver (`_MEIPASS` aware)
- `src/notepadclone/ui/workspace_controller.py`: workspace/media logic
- `src/notepadclone/ui/security_controller.py`: per-note encryption flow
- `src/notepadclone/ui/ai_controller.py`: Gemini AI actions
- `src/notepadclone/ui/updater_controller.py`: update feed check/download/install flow
- `src/notepadclone/ui/updater_helpers.py`: unit-testable update XML/version helpers
- `src/notepadclone/ui/note_crypto.py`: encrypted payload format and crypto helpers
- `src/notepadclone/ui/crypto_helpers.py`: pure crypto primitives
- `src/notepadclone/ui/workspace_search_helpers.py`: pure workspace scan/search helpers
- `src/notepadclone/ui/tutorial_dialog.py`: first-run interactive tutorial dialog
- `src/notepadclone/ui/main_window/settings_dialog.py`: sidebar settings UI

Made with OpenAI ChatGPT Codex Agent. Ideas & Concepts by me. Inspired by one simple notepad app.

