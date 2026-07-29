@echo off
setlocal enabledelayedexpansion
rem hwp_palette branch launcher (ASCII + CRLF, encoding-safe -- same rule as run.bat)
rem
rem Picks a branch and runs it. The branch you are NOT currently on is opened in
rem its own worktree under .worktrees\, so you can run two of them side by side
rem without switching (no stash dance, no half-finished edits in the way).
rem
rem Why the data copy: paths.py puts user data in <project root>\data\ , and that
rem folder is gitignored -- a fresh worktree would start with an EMPTY palette.
rem We copy it once so the branch opens with your real paints. It is a COPY, not
rem a link: two running copies must not fight over one config.json.
cd /d "%~dp0"

git rev-parse --git-dir >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Not a git repository.
    pause
    exit /b 1
)

for /f "tokens=*" %%b in ('git rev-parse --abbrev-ref HEAD') do set "CURRENT=%%b"

echo.
echo   hwp_palette -- pick a branch
echo   ----------------------------------------
set /a N=0
for /f "tokens=*" %%b in ('git for-each-ref --format^="%%(refname:short)" refs/heads') do (
    set /a N+=1
    set "B!N!=%%b"
    if "%%b"=="!CURRENT!" (
        echo     !N!^) %%b   [current]
    ) else (
        echo     !N!^) %%b
    )
)
echo     0^) quit
echo.

set "PICK="
set /p "PICK=number: "
if "%PICK%"=="0" exit /b 0
if "%PICK%"=="" exit /b 0
set "BRANCH=!B%PICK%!"
if "%BRANCH%"=="" (
    echo [ERROR] No such number: %PICK%
    pause
    exit /b 1
)

rem -- already checked out here? then just run here.
if "%BRANCH%"=="%CURRENT%" (
    set "TARGET=%CD%"
    goto :run
)

rem -- otherwise use a worktree. Branch names have slashes; folders cannot.
set "SAFE=%BRANCH:/=-%"
set "TARGET=%CD%\.worktrees\%SAFE%"

if not exist "%TARGET%\main.py" (
    echo   preparing worktree for %BRANCH% ...
    git worktree prune
    git worktree add "%TARGET%" "%BRANCH%"
    if errorlevel 1 (
        echo.
        echo [ERROR] Could not create the worktree.
        echo         The branch may already be open in another folder.
        echo         Check with: git worktree list
        pause
        exit /b 1
    )
)

if not exist "%TARGET%\data" (
    if exist "%CD%\data" (
        echo   copying your data ^(palette, library, fragments^) ...
        xcopy "%CD%\data" "%TARGET%\data" /E /I /Q /Y >nul
    )
)

:run
echo.
echo   running %BRANCH%
echo   %TARGET%
echo.
cd /d "%TARGET%"
python -c "import pyhwpx" 2>nul || pip install pyhwpx
python -c "import openpyxl" 2>nul || pip install openpyxl
python main.py
if errorlevel 1 (
    echo.
    echo [ERROR] Failed to launch. Check: Python installed, Hangul^(HWP^) available.
    pause
)
