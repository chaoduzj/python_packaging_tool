@echo off
setlocal enabledelayedexpansion
:: Fix PATH to ensure standard Windows commands work
set PATH=%SystemRoot%\system32;%SystemRoot%;%SystemRoot%\System32\Wbem;%PATH%

:: ============================================
:: Check admin privileges and auto-elevate
:: ============================================
>nul 2>&1 "%SYSTEMROOT%\system32\cacls.exe" "%SYSTEMROOT%\system32\config\system"

if '%errorlevel%' NEQ '0' (
    echo Requesting administrative privileges...
    :: Create temp VBS script for elevation
    echo Set UAC = CreateObject^("Shell.Application"^) > "%temp%\getadmin.vbs"
    echo UAC.ShellExecute "%~s0", "", "", "runas", 1 >> "%temp%\getadmin.vbs"

    :: Run VBS script
    "%temp%\getadmin.vbs"

    :: Exit current non-admin script
    exit /b
) else (
    :: Delete temp VBS file if exists
    if exist "%temp%\getadmin.vbs" ( del "%temp%\getadmin.vbs" )
)

:: ============================================
:: Change back to script directory after elevation
:: ============================================
cd /d "%~dp0"

:: Set title
title Python Packaging Tool

echo ==================================================
echo Environment Check
echo ==================================================

:: Detect Python interpreter (priority: .venv > PYTHON_HOME > pyenv-win > standard paths > PATH)
set "VENV_DIR=%~dp0.venv"
call :detect_python_interpreter
echo [Python] Selected interpreter: !PYTHON_EXE!

:: 1. Check Virtual Environment
if exist "!VENV_DIR!\Scripts\python.exe" (
    REM Validate the venv interpreter still works; broken venvs (base Python uninstalled) must be recreated
    "!VENV_DIR!\Scripts\python.exe" --version >nul 2>&1
    if !errorlevel! equ 0 (
        echo [INFO] Virtual environment detected: !VENV_DIR!
        goto :check_deps
    ) else (
        echo [WARNING] .venv exists but interpreter is broken ^(base Python missing^), recreating...
        rmdir /s /q "!VENV_DIR!" 2>nul
    )
)

echo [INFO] Virtual environment not found. Creating with: !PYTHON_EXE!
"!PYTHON_EXE!" -m venv ".venv"
if errorlevel 1 goto :error_venv

:: If we just created the venv, we force dependency installation
goto :install_deps

:check_deps
:: 2. Check Dependencies
if not exist "requirements.txt" goto :run_app

:: If marker file exists, assume dependencies are installed
if exist ".venv\installed.marker" goto :run_app

:install_deps
echo [INFO] Installing dependencies from requirements.txt...
".venv\Scripts\python.exe" -m pip install -r requirements.txt --no-input
if errorlevel 1 goto :error_install

:: Create a marker file to indicate success
echo installed > ".venv\installed.marker"
echo [INFO] Dependencies installed successfully.
goto :run_app

:run_app
echo.
echo ==================================================
echo Starting Application
echo ==================================================
echo.

if not exist "main.py" goto :error_main

:: Run the main application
".venv\Scripts\python.exe" main.py

:: Capture exit code
set EXIT_CODE=%errorlevel%

:: Exit immediately - console will close automatically
exit /b %EXIT_CODE%

:: ----------------------------------------------------
:: Error Handlers
:: ----------------------------------------------------

:error_venv
    echo.
echo [ERROR] Failed to create virtual environment with: !PYTHON_EXE!
echo Please ensure Python is installed. Checked paths:
echo   1. .venv\Scripts\python.exe
echo   2. %%PYTHON_HOME%%\python.exe
echo   3. pyenv-win versions
echo   4. %%LOCALAPPDATA%%\Programs\Python\Python*
echo   5. C:\Python*
echo   6. System PATH
    echo.
    pause
    exit /b 1

:error_install
echo.
echo [ERROR] Failed to install dependencies.
echo Please check your internet connection or requirements.txt.
    echo.
pause
exit /b 1

:error_main
    echo.
echo [ERROR] main.py not found in the current directory.
    echo.
    pause
exit /b 1

REM ============================================
REM Detect Python interpreter on Windows
REM Search order (first match wins):
REM   1. Project virtualenv      : %VENV_DIR%\Scripts\python.exe
REM   2. PYTHON_HOME env var     : %PYTHON_HOME%\python.exe
REM   3. pyenv-win               : %USERPROFILE%\.pyenv\pyenv-win\shims\python.bat
REM      (prefers shims first, then active version from pyenv-win\version, otherwise latest)
REM   4. Per-user python.org     : %LOCALAPPDATA%\Programs\Python\Python*\python.exe
REM   5. System-wide python.org  : %ProgramFiles%\Python*\python.exe / %ProgramFiles(x86)%\Python*\python.exe
REM   6. Legacy path             : C:\Python*\python.exe
REM   7. System PATH (where python)
REM Sets: PYTHON_EXE, PIP_EXE
REM ============================================
:detect_python_interpreter
set "LOG_PREFIX=echo [Python]"
call "%~dp0scripts\detect_python.cmd"
goto :eof
