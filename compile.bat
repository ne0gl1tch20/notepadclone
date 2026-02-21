@echo off
setlocal
cd /d "%~dp0"

echo [1/3] Checking optional QScintilla dependency...
python -c "import importlib.util as u,sys; sys.exit(0 if u.find_spec('PySide6.Qsci') else 2)"
if errorlevel 2 (
    echo [WARN] PySide6.Qsci not found. Build will still work, but advanced editor features will be disabled.
)

echo [2/3] Syncing version metadata...
python tools\gen_version_info.py
if errorlevel 1 (
    echo [ERROR] Version metadata sync failed.
    exit /b %errorlevel%
)

echo [3/3] Building with PyInstaller...
python -m PyInstaller --noconfirm --clean run.spec
if errorlevel 1 (
    echo [ERROR] Build failed.
    exit /b %errorlevel%
)

echo [4/4] Done. Output: dist\run.exe
