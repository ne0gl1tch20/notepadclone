# Context Summary

## Docs Updated
- Last docs sync: 2026-02-27
- Synced files:
  - `CONTEXT_SUMMARY.md`
  - `APP_SUMMARY.md`
  - `README.md`
  - `CHANGELOG.md`
  - `update.xml`
  - `assets/version.txt`
  - `assets/version_info.txt`

## Current Release Metadata
- Version: `1.7.5-prerelease`
- Update feed entry: `update.xml` (2026-02-27)
- Changelog entry added: `1.7.5-prerelease`

## Current Focus (Completed)
- LSP definition client hardening (timeouts/retries/logging + server preference settings)
- Factory reset workflow added in Settings (confirmation + close-on-reset)
- Release metadata/docs updated for `1.7.5-prerelease`
- PySide6 Scintilla-compat engine expanded to cover advanced editing/view behaviors without PyQt/Qsci dependency

## What Was Completed (Phases 1-4)

### Theme Architecture
- Added `UIThemeTokens` and token builders in `src/pypad/ui/theme_tokens.py`
- Main window chrome QSS now generated from tokens
- Dialog theme system in `src/pypad/ui/dialog_theme.py` now token-driven
- Shared wrappers for themed `QMessageBox` and `QProgressDialog`

### UI Overhaul Coverage
- Core chrome: tabs, toolbars, menus, docks, status bar, scrollbars
- High-traffic dialogs/panels:
  - Settings
  - Tutorial
  - Autosave recovery
  - Quick Open / Go to Anything
  - AI Chat dock
  - AI Edit Preview / AI Rewrite dialogs
  - Workspace dialogs
  - Debug Logs dialog
  - updater dialogs
- Additional custom dialogs in `main_window/misc.py` now use shared dialog theming (windows manager, macro run dialog, licenses, jump history, search results window, user guide, document summary, and more)

### Scintilla Compatibility Expansion (Post-Release Ongoing in Unreleased)
- Added `src/pypad/ui/editor/scintilla_compat.py` and routed fallback editor path through Scintilla-like backend.
- Margin system improvements:
  - fold/marker/line-number painting
  - per-margin type/width/mask/sensitivity controls
  - margin index click signal routing
- Marker symbol families implemented (circle/arrow/plus/minus/rect/empty).
- Folding now supports indentation + bracket-guided regions with fold-all/line/level operations.
- Column mode and multi-caret upgrades:
  - persistent rectangular selections after edits
  - synchronized typing/delete/navigation
  - row-aware multi-paste support
- Indicator/hotspot features:
  - styled indicator ranges with active hover state
  - hotspot and indicator hover/click payload signals
- Added lightweight calltip/annotation methods, brace-match highlighting, symbol overlays, and lexer-style token ranges.

### Quick Open / Productivity Features
- file/line/symbol/workspace-symbol/command modes
- grouped results
- `Tab` / `Shift+Tab` mode cycling
- background indexing + persistent file/symbol caches
- incremental auto-refresh during indexing
- same-count refresh detection via content signatures

### AI Chat UX + Apply Flow
- one-click assistant actions: Insert / Replace / Append / New Tab / Replace File / Diff
- hidden command parsing compatibility (`OFF_INSERT` alias support)
- improved apply and diff-preview workflows

### Visual Regression Tooling
- `tests/test_ui_visual_smoke_screenshots.py`
- Screenshots generated into `tests_tmp/visual_smoke_phase2/`
- HTML manifest: `tests_tmp/visual_smoke_phase2/index.html`
- Baseline file: `tests/visual_smoke_phase2_baseline.json`
- Compare/update modes via env vars:
  - `PYPAD_VISUAL_BASELINE_MODE`
  - `PYPAD_VISUAL_AHASH_THRESHOLD`

### CI / Local Dev Workflow
- CI workflows:
  - `.github/workflows/ui-fast-and-runtime.yml`
  - `.github/workflows/ui-visual-smoke.yml`
- Local runner:
  - `scripts/run_ui_checks.ps1` (`-Fast`, `-Runtime`, `-Visual`, `-All`, `-UpdateVisualBaseline`)

## Key Files (Most Relevant Now)
- `src/pypad/ui/theme_tokens.py`
- `src/pypad/ui/dialog_theme.py`
- `src/pypad/ui/main_window/misc.py`
- `src/pypad/ui/main_window/view_ops.py`
- `src/pypad/ui/main_window/settings_dialog.py`
- `src/pypad/ui/quick_open_dialog.py`
- `src/pypad/ui/ai_chat_dock.py`
- `tests/test_ui_visual_smoke_screenshots.py`
- `tests/visual_smoke_phase2_baseline.json`
- `scripts/run_ui_checks.ps1`

## Validation Snapshot (Recent)
- Visual baseline compare test passes
- Targeted UI/theme/runtime/visual suites pass (including long visual/runtime runs)
- `.pytest_cache` warnings may appear due local filesystem permissions; non-blocking
- Preferences Appearance race instrumentation retained:
  - `SettingsThemeProbe` logs from `pypad.ui.main_window.settings_dialog` at `open`, `first_paint`, `post_150ms`, `post_600ms`
  - Logs include computed theme tokens (`dark_mode`, `text`, `surface_bg`, `input_bg`) and effective palettes for host/scroll/viewport/body
  - Keep enabled for future regressions where settings content contrast/background appears inconsistent at dialog startup

## Next Easy Resume Points
1. Build/release packaging validation for `1.7.5-prerelease` (installer output + update feed URL verification).
2. Optional visual baseline refresh after intentional UI/editor rendering changes using `scripts/run_ui_checks.ps1 -Visual -UpdateVisualBaseline`.
3. If targeting deeper Scintilla parity, prioritize:
   - advanced lexer stateful styling/perf
   - fuller indicator metadata/query APIs
   - annotation/calltip theming and interaction polish


PyPad UI defaults:

- Style: soft rounded modern
- Layout: Notepad++ style menus + dock panels
- Minimap: right dock, toggle in View
- Panels: QDockWidget-based
- Icons: monochrome SVG themed (if dark mode, white icons, if light mode, black in icons)
- Density: medium compact
- Platform feel: Windows-first but cross-platform safe

If ambiguous, choose the simplest consistent option.
Ask at most one clarification question.
