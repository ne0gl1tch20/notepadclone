@echo off
setlocal
cd /d "%~dp0"

if not exist "dist\run.exe" (
    echo [ERROR] dist\run.exe was not found.
    echo Build the app first, for example by running compile.bat.
    exit /b 1
)

set "ISCC_EXE="
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC_EXE=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not defined ISCC_EXE if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC_EXE=%ProgramFiles%\Inno Setup 6\ISCC.exe"

if not defined ISCC_EXE (
    echo [ERROR] Inno Setup 6 ISCC.exe was not found.
    echo Install Inno Setup 6 and re-run this script.
    exit /b 1
)

set "APP_VERSION=0.0.0"
if exist "assets\version.txt" (
    for /f "usebackq delims=" %%V in ("assets\version.txt") do (
        set "APP_VERSION=%%V"
        goto :version_read_done
    )
)
:version_read_done

echo [1/1] Building installer with Inno Setup...
"%ISCC_EXE%" "/DMyAppVersion=%APP_VERSION%" "installer\NotepadClone.iss"
if errorlevel 1 (
    echo [ERROR] Installer build failed.
    exit /b %errorlevel%
)

echo [DONE] Installer output is in dist\installer
