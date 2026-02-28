# Pypad

Pypad is a PySide6 desktop text editor focused on fast note-taking and power-user workflows.

Creator's Thoughts
- You might wonder why my naming is like the other repos, i think i named it on my own since its a great way despite all the mess...

Highlights:
- Soft modern rounded UI overhaul with token-based theming
- Multi-tab editor with detachable tabs, pin/favorite states, and rich tab actions
- Quick Open / Go to Anything (`Ctrl+Alt+P`) with file, line, symbol, workspace-symbol, and command modes
- AI chat dock with one-click apply actions (Insert/Replace/Append/New Tab/Replace File/Diff)
- Markdown tools + live preview, syntax modes, workspace search, autosave/recovery, version history
- Preferences with unified PyPad + Notepad++ compatibility pages
- Visual UI regression tooling (screenshot smoke tests + baseline compare CI)

## Install / Run

- Development: run `src/run.py`
- Build: `compile.bat`
- Version file: `assets/version.txt`
- Installer artifacts (when built): `dist/installer/`

## Key Paths

- Main window: `src/pypad/ui/main_window/window.py`
- Theme tokens / chrome QSS: `src/pypad/ui/theme_tokens.py`
- Dialog theming helpers: `src/pypad/ui/dialog_theme.py`
- AI chat dock: `src/pypad/ui/ai_chat_dock.py`
- Quick Open dialog: `src/pypad/ui/quick_open_dialog.py`
- Settings dialog: `src/pypad/ui/main_window/settings_dialog.py`
- Update feed metadata: `update.xml`

## UI Test / Visual Regression Commands

- Fast UI checks:
  - `powershell -File scripts/run_ui_checks.ps1 -Fast`
- Runtime smoke:
  - `powershell -File scripts/run_ui_checks.ps1 -Runtime`
- Visual smoke baseline compare:
  - `powershell -File scripts/run_ui_checks.ps1 -Visual`
- Update visual baseline (intentional refresh):
  - `powershell -File scripts/run_ui_checks.ps1 -Visual -UpdateVisualBaseline`

## Notes

- `tests/visual_smoke_phase2_baseline.json` is the committed visual baseline used by CI.
- `tests_tmp/visual_smoke_phase2/index.html` is generated during visual smoke runs for quick review.

## Credits
I use codex to turbo boost the codebase, however, i still use my coding skills for that.
