@echo off
setlocal enabledelayedexpansion
REM ============================================
REM Shared Python interpreter detection routine
REM Used by: run.bat, build_universal.bat
REM
REM Each caller must set LOG_PREFIX before calling.
REM   run.bat:           set "LOG_PREFIX=echo [Python]"
REM   build_universal.bat: set "LOG_PREFIX=call :log_echo [Python]"
REM
REM Sets: PYTHON_EXE, PIP_EXE
REM ============================================

set "PYTHON_EXE="
set "PIP_EXE="

REM --- 1. Project virtualenv (must be runnable - base interpreter not removed) ---
if exist "%VENV_DIR%\Scripts\python.exe" (
    "%VENV_DIR%\Scripts\python.exe" --version >nul 2>&1
    if !errorlevel! equ 0 (
        set "PYTHON_EXE=%VENV_DIR%\Scripts\python.exe"
        if exist "%VENV_DIR%\Scripts\pip.exe" (
            set "PIP_EXE=%VENV_DIR%\Scripts\pip.exe"
        ) else (
            set "PIP_EXE=%VENV_DIR%\Scripts\python.exe -m pip"
        )
        %LOG_PREFIX% Project virtualenv detected: %VENV_DIR%
        goto :exit_detect
    ) else (
        %LOG_PREFIX% .venv exists but interpreter is broken ^(base Python missing^), skipping
    )
)

REM --- 2. PYTHON_HOME ---
if defined PYTHON_HOME (
    if exist "!PYTHON_HOME!\python.exe" (
        set "PYTHON_EXE=!PYTHON_HOME!\python.exe"
        if exist "!PYTHON_HOME!\Scripts\pip.exe" (
            set "PIP_EXE=!PYTHON_HOME!\Scripts\pip.exe"
        ) else (
            set "PIP_EXE=!PYTHON_HOME!\python.exe -m pip"
        )
        %LOG_PREFIX% PYTHON_HOME detected: !PYTHON_HOME!
        goto :exit_detect
    )
)

REM --- 3. pyenv-win ---
set "PYENV_ROOT=%USERPROFILE%\.pyenv\pyenv-win"

REM 3a. Try pyenv-win shims first (routes to active version)
if exist "!PYENV_ROOT!\shims\python.bat" (
    for /f "usebackq tokens=1 delims= " %%s in ("!PYENV_ROOT!\shims\python.bat") do (
        set "SHIM_LINE=%%s"
        if not "!SHIM_LINE!"=="@echo" (
            set "SHIM_LINE=!SHIM_LINE:"=!"
            if /i "!SHIM_LINE:~-10!"=="python.exe" (
                if exist "!SHIM_LINE!" (
                    set "PYTHON_EXE=!SHIM_LINE!"
                    for %%p in ("!SHIM_LINE!") do set "PIP_EXE=%%~dppScripts\pip.exe"
                    if not exist "!PIP_EXE!" set "PIP_EXE=!SHIM_LINE! -m pip"
                    %LOG_PREFIX% pyenv-win shims detected: !PYTHON_EXE!
                    goto :exit_detect
                )
            )
        )
    )
)

REM 3b. Try the version file (records active pyenv-win version)
if exist "!PYENV_ROOT!\versions" (
    set "PYENV_ACTIVE="
    if exist "!PYENV_ROOT!\version" (
        set /p PYENV_ACTIVE=<"!PYENV_ROOT!\version"
    )
    if not "!PYENV_ACTIVE!"=="" (
        if exist "!PYENV_ROOT!\versions\!PYENV_ACTIVE!\python.exe" (
            set "PYTHON_EXE=!PYENV_ROOT!\versions\!PYENV_ACTIVE!\python.exe"
            set "PIP_EXE=!PYENV_ROOT!\versions\!PYENV_ACTIVE!\Scripts\pip.exe"
            %LOG_PREFIX% pyenv-win active version: !PYENV_ACTIVE!
            %LOG_PREFIX% Path: !PYTHON_EXE!
            goto :exit_detect
        )
    )
    REM Fallback: pick the last version directory listed (alphabetical order)
    set "PYENV_PICK="
    for /f "delims=" %%d in ('dir /b /ad /on "!PYENV_ROOT!\versions" 2^>nul') do (
        if exist "!PYENV_ROOT!\versions\%%d\python.exe" set "PYENV_PICK=%%d"
    )
    if not "!PYENV_PICK!"=="" (
        set "PYTHON_EXE=!PYENV_ROOT!\versions\!PYENV_PICK!\python.exe"
        set "PIP_EXE=!PYENV_ROOT!\versions\!PYENV_PICK!\Scripts\pip.exe"
        %LOG_PREFIX% pyenv-win version detected: !PYENV_PICK!
        %LOG_PREFIX% Path: !PYTHON_EXE!
        goto :exit_detect
    )
)

REM --- 4. Per-user python.org install (LOCALAPPDATA) ---
set "PY_PICK_DIR="
for /f "delims=" %%d in ('dir /b /ad /on "%LOCALAPPDATA%\Programs\Python" 2^>nul') do (
    if exist "%LOCALAPPDATA%\Programs\Python\%%d\python.exe" set "PY_PICK_DIR=%LOCALAPPDATA%\Programs\Python\%%d"
)
if not "!PY_PICK_DIR!"=="" (
    set "PYTHON_EXE=!PY_PICK_DIR!\python.exe"
    set "PIP_EXE=!PY_PICK_DIR!\Scripts\pip.exe"
    %LOG_PREFIX% Per-user install detected: !PY_PICK_DIR!
    goto :exit_detect
)

REM --- 5a. System-wide python.org install (Program Files) ---
set "PY_PICK_DIR="
for /f "delims=" %%d in ('dir /b /ad /on "%ProgramFiles%\Python*" 2^>nul') do (
    if exist "%ProgramFiles%\%%d\python.exe" set "PY_PICK_DIR=%ProgramFiles%\%%d"
)
if not "!PY_PICK_DIR!"=="" (
    set "PYTHON_EXE=!PY_PICK_DIR!\python.exe"
    set "PIP_EXE=!PY_PICK_DIR!\Scripts\pip.exe"
    %LOG_PREFIX% System install detected: !PY_PICK_DIR!
    goto :exit_detect
)

REM --- 5b. System-wide python.org install (Program Files x86) ---
set "PY_PICK_DIR="
for /f "delims=" %%d in ('dir /b /ad /on "%ProgramFiles(x86)%\Python*" 2^>nul') do (
    if exist "%ProgramFiles(x86)%\%%d\python.exe" set "PY_PICK_DIR=%ProgramFiles(x86)%\%%d"
)
if not "!PY_PICK_DIR!"=="" (
    set "PYTHON_EXE=!PY_PICK_DIR!\python.exe"
    set "PIP_EXE=!PY_PICK_DIR!\Scripts\pip.exe"
    %LOG_PREFIX% System install (x86) detected: !PY_PICK_DIR!
    goto :exit_detect
)

REM --- 6. Legacy C:\Python* ---
set "PY_PICK_DIR="
for /f "delims=" %%d in ('dir /b /ad /on "C:\Python*" 2^>nul') do (
    if exist "C:\%%d\python.exe" set "PY_PICK_DIR=C:\%%d"
)
if not "!PY_PICK_DIR!"=="" (
    set "PYTHON_EXE=!PY_PICK_DIR!\python.exe"
    set "PIP_EXE=!PY_PICK_DIR!\Scripts\pip.exe"
    %LOG_PREFIX% Legacy install detected: !PY_PICK_DIR!
    goto :exit_detect
)

REM --- 7. System PATH ---
where python >nul 2>&1
if !errorlevel! equ 0 (
    for /f "delims=" %%p in ('where python 2^>nul') do (
        if not defined PYTHON_EXE set "PYTHON_EXE=%%p"
    )
    set "PIP_EXE=pip"
    %LOG_PREFIX% System PATH python detected: !PYTHON_EXE!
    goto :exit_detect
)

REM --- Fallback (no Python found) ---
%LOG_PREFIX% No Python interpreter located, falling back to "python" on PATH
set "PYTHON_EXE=python"
set "PIP_EXE=pip"

:exit_detect
REM 将变量提升到调用者作用域（endlocal 销毁本地变量前保存到外层）
endlocal & set "PYTHON_EXE=%PYTHON_EXE%" & set "PIP_EXE=%PIP_EXE%"
goto :eof
