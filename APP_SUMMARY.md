# Pypad - App Summary

Last updated: 2026-02-26
Release target: `1.7.4-prerelease`

## Product Snapshot

Pypad is a PySide6 desktop editor that combines note-taking, coding/markdown workflows, workspace tools, and AI-assisted editing. The app now ships with a token-based modern rounded UI theme system applied across the main chrome and most dialogs/panels.

## Major Capabilities

- Multi-tab editing with detachable tabs, pin/favorite/read-only states, tags, and per-tab metadata
- Markdown formatting tools and live preview
- Workspace files/search dialogs and search result navigation
- Autosave, crash recovery, and version history with diff preview
- Per-note encryption (`.encnote`) and app privacy lock options
- AI chat dock, AI inline edits, workspace citation workflows, and diff/apply previews
- Update checking/downloading from XML feed (`update.xml`)
- Unified Preferences (PyPad + Notepad++ compatibility pages)

## UI Overhaul Status (Completed Through Phase 4 Sweep)

Implemented:
- Shared `UIThemeTokens` in `src/pypad/ui/theme_tokens.py`
- Token-driven main window chrome QSS (tabs/toolbars/menus/docks/status/scrollbars)
- Token-driven dialog theme system in `src/pypad/ui/dialog_theme.py`
- Token-aligned high-traffic dialogs and panels:
  - Settings, Tutorial, Autosave, Workspace dialogs
  - Quick Open / Go to Anything
  - AI Chat dock and AI edit preview dialogs
  - Debug Logs and updater dialogs
- Additional completion sweep on niche/custom dialogs in `main_window/misc.py`
- Visual regression tooling + CI baseline gate

Remaining style islands are limited to small functional inline styles (for example transient highlights, color preview swatches, or compact layout micro-adjustments).

## Key Architecture

Main window class:
- `src/pypad/ui/main_window/window.py` (`Notepad`)

Mixins:
- `src/pypad/ui/main_window/ui_setup.py`
- `src/pypad/ui/main_window/file_ops.py`
- `src/pypad/ui/main_window/edit_ops.py`
- `src/pypad/ui/main_window/view_ops.py`
- `src/pypad/ui/main_window/misc.py`

Core UI modules:
- `src/pypad/ui/theme_tokens.py`
- `src/pypad/ui/dialog_theme.py`
- `src/pypad/ui/quick_open_dialog.py`
- `src/pypad/ui/ai_chat_dock.py`
- `src/pypad/ui/ai_edit_preview_dialog.py`

Settings system:
- `src/pypad/ui/main_window/settings_dialog.py`
- `src/pypad/ui/main_window/settings_notepadpp_pages.py`
- `src/pypad/app_settings/defaults.py`
- `src/pypad/app_settings/coercion.py`

## QA / Regression Tooling

Fast UI checks:
- `tests/test_ui_theme_tokens.py`
- `tests/test_dialog_theme.py`
- `tests/test_main_theme_qss_builder.py`

Runtime smoke:
- `tests/test_settings_apply_runtime.py`

Visual smoke + baseline compare:
- `tests/test_ui_visual_smoke_screenshots.py`
- Baseline: `tests/visual_smoke_phase2_baseline.json`
- CI workflow: `.github/workflows/ui-visual-smoke.yml`

Local wrapper:
- `scripts/run_ui_checks.ps1`

## Release Metadata Files

- App version: `assets/version.txt`
- Windows version info: `assets/version_info.txt`
- Update feed: `update.xml`
- Human changelog: `CHANGELOG.md`
