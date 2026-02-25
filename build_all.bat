@echo off
setlocal
cd /d "%~dp0"

echo [1/2] Building app with PyInstaller...
call "%~dp0compile.bat"
if errorlevel 1 (
    echo [ERROR] PyInstaller build step failed.
    exit /b %errorlevel%
)

echo [2/2] Building installer with Inno Setup...
call "%~dp0build_installer.bat"
if errorlevel 1 (
    echo [ERROR] Inno Setup installer build step failed.
    exit /b %errorlevel%
)

echo [DONE] Full build completed (PyInstaller + Inno Setup).
echo [INFO] EXE: dist\run.exe
echo [INFO] Installer: dist\installer\
exit /b 0
