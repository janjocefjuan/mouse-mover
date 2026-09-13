@echo off
title Marksman - First Time Setup
setlocal

set "HERE=%~dp0"
set "PY="

if exist "%HERE%..\..\python\python.exe" set "PY=%HERE%..\..\python\python.exe"
if not defined PY if exist "%HERE%..\python\python.exe" set "PY=%HERE%..\python\python.exe"
if not defined PY if exist "%HERE%..\..\..\python\python.exe" set "PY=%HERE%..\..\..\python\python.exe"

echo.
echo   ============================================
echo     Marksman - First Time Setup
echo   ============================================
echo.

if not defined PY (
    echo   [X] Could not find the portable Python.
    echo.
    echo   Make sure this Marksman folder is placed INSIDE your
    echo   WinPython folder - the one that contains a folder
    echo   named "python".
    echo.
    pause
    exit /b 1
)

echo   Installing the components Marksman needs...
echo   This takes a minute. Please wait.
echo.

"%PY%" -m pip install -r "%HERE%requirements.txt"

if errorlevel 1 (
    echo.
    echo   [X] Something went wrong during setup.
    echo   Check that you are connected to the internet and try again.
    echo.
    pause
    exit /b 1
)

echo.
echo   ============================================
echo     Setup complete!
echo.
echo     Next: double-click "Install Marksman Shortcut"
echo     to put Marksman on your Desktop.
echo   ============================================
echo.
pause
