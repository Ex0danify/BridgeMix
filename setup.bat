@echo off
setlocal EnableDelayedExpansion
title BridgeMix

rem ============================================================================
rem  BridgeMix launcher / installer for Windows — friendly, no docs required.
rem
rem  Just run it (double-click, or `setup.bat` in a terminal). You get a menu:
rem    * Install ^& Launch — set things up, add a Start Menu shortcut, start it
rem    * Launch           — start it without adding a shortcut
rem    * Uninstall        — remove the Start Menu shortcut
rem
rem  Backend is automatic: a conda env if you have conda, otherwise a normal
rem  Python venv (.venv). Force one with BRIDGEMIX_BACKEND=conda^|venv.
rem  Non-interactive (e.g. launched from the shortcut) it installs ^& launches
rem  without prompting.
rem  Flags: --install ^| --launch ^| --uninstall ^| --help
rem ============================================================================

set "APP_NAME=BridgeMix"
set "ENV_NAME=bridgemix"
set "PY_MIN_MINOR=11"
set "SCRIPT_DIR=%~dp0"
if "%SCRIPT_DIR:~-1%"=="\" set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"
set "VENV_DIR=%SCRIPT_DIR%\.venv"
set "SHORTCUT=%APPDATA%\Microsoft\Windows\Start Menu\Programs\%APP_NAME%.lnk"

rem PY / PIP get filled in by the backend setup; BACKEND names which one we used.
set "PY="
set "PIP="
set "BACKEND="

rem -- Action resolution: flags -> non-interactive default -> menu --------------
set "ACTION="
for %%A in (%*) do (
    if /I "%%~A"=="--install"   set "ACTION=install"
    if /I "%%~A"=="--auto"      set "ACTION=install"
    if /I "%%~A"=="-y"          set "ACTION=install"
    if /I "%%~A"=="--launch"    set "ACTION=launch"
    if /I "%%~A"=="--play"      set "ACTION=launch"
    if /I "%%~A"=="--no-shortcut" set "ACTION=launch"
    if /I "%%~A"=="--uninstall" set "ACTION=uninstall"
    if /I "%%~A"=="--remove"    set "ACTION=uninstall"
    if /I "%%~A"=="--help"      goto :show_help
    if /I "%%~A"=="-h"          goto :show_help
    if /I "%%~A"=="/?"          goto :show_help
)

if not defined ACTION call :choose_action

if /I "%ACTION%"=="quit"      goto :bye
if /I "%ACTION%"=="uninstall" goto :do_uninstall
if /I "%ACTION%"=="install"   goto :do_install
if /I "%ACTION%"=="launch"    goto :do_launch
goto :bye

rem ============================================================================

:do_install
    call :setup_backend || goto :fail
    call :install_shortcut
    echo   Ready - starting %APP_NAME%... (%BACKEND%^)
    goto :run

:do_launch
    call :setup_backend || goto :fail
    echo   Ready - starting %APP_NAME%... (%BACKEND%^)
    goto :run

:do_uninstall
    call :remove_shortcut
    goto :eof_exit

:run
    rem Hand control to the app. %PY% is either a venv python.exe or `conda run`.
    %PY% -m bridgemix
    exit /b %ERRORLEVEL%

rem ============================================================================
rem  Interactive menu (numbered — robust across Windows terminals)
rem ============================================================================

:choose_action
    echo.
    echo   BridgeMix   - Roland Bridge Cast controller
    echo   ----------------------------------------
    echo.
    echo     [1] Install ^& Launch  -  add a Start Menu shortcut, then start
    echo     [2] Launch            -  start (no shortcut^)
    echo     [3] Uninstall         -  remove the Start Menu shortcut
    echo     [Q] Quit
    echo.
    choice /C 123Q /N /M "  Choose: "
    set "_c=%ERRORLEVEL%"
    if "%_c%"=="1" set "ACTION=install"   & goto :eof
    if "%_c%"=="2" set "ACTION=launch"    & goto :eof
    if "%_c%"=="3" set "ACTION=uninstall" & goto :eof
    set "ACTION=quit"
    goto :eof

rem ============================================================================
rem  Backend discovery
rem ============================================================================

:setup_backend
    set "_want=%BRIDGEMIX_BACKEND%"
    if /I "%_want%"=="conda" (
        call :find_conda || ( echo   BRIDGEMIX_BACKEND=conda but conda not found. & exit /b 1 )
        call :setup_conda || exit /b 1
        goto :relink_check
    )
    if /I "%_want%"=="venv" (
        call :setup_venv || exit /b 1
        goto :relink_check
    )
    rem Auto: prefer conda when present, else venv.
    call :find_conda && ( call :setup_conda || exit /b 1 ) || ( call :setup_venv || exit /b 1 )

:relink_check
    rem Keep the env pointed at THIS folder (handles a moved/renamed/cloned copy).
    rem Compare entirely inside Python with os.path.normcase so both paths are
    rem normalized the same way (case, slashes, 8.3 names) — otherwise a raw
    rem batch string vs. a realpath() result almost never match and we'd relink
    rem on every launch.
    set "_need="
    for /f "delims=" %%R in ('%PY% -c "import os,importlib.util as u;s=u.find_spec('bridgemix');cur=os.path.dirname(os.path.dirname(os.path.realpath(s.origin))) if s and s.origin else '';exp=os.path.realpath(r'%SCRIPT_DIR%\src');print('ok' if os.path.normcase(cur)==os.path.normcase(exp) else 'relink')" 2^>nul') do set "_need=%%R"
    if /I "%_need%"=="ok" exit /b 0
    echo   Linking this copy...
    %PIP% install -e "%SCRIPT_DIR%" >nul 2>&1
    exit /b 0

:find_conda
    where conda >nul 2>&1 && ( set "CONDA_EXE=conda" & exit /b 0 )
    for %%C in (
        "%USERPROFILE%\miniconda3\Scripts\conda.exe"
        "%USERPROFILE%\anaconda3\Scripts\conda.exe"
        "%ProgramData%\miniconda3\Scripts\conda.exe"
        "%ProgramData%\anaconda3\Scripts\conda.exe"
    ) do if exist %%C ( set "CONDA_EXE=%%~C" & exit /b 0 )
    exit /b 1

:setup_conda
    set "BACKEND=conda"
    "%CONDA_EXE%" env list 2>nul | findstr /R /C:"^%ENV_NAME% " >nul
    if errorlevel 1 (
        echo   First-time setup ^(this can take a minute^)
        echo   Creating environment...
        "%CONDA_EXE%" create -n "%ENV_NAME%" "python=3.%PY_MIN_MINOR%" -y >nul 2>&1 || ( echo   Could not create the conda environment. & exit /b 1 )
        echo   Installing %APP_NAME%...
        "%CONDA_EXE%" run -n "%ENV_NAME%" pip install -e "%SCRIPT_DIR%" || ( echo   Install failed. & exit /b 1 )
    )
    set "PY="%CONDA_EXE%" run -n %ENV_NAME% python"
    set "PIP="%CONDA_EXE%" run -n %ENV_NAME% pip"
    exit /b 0

:setup_venv
    set "BACKEND=venv"
    if not exist "%VENV_DIR%\Scripts\python.exe" (
        call :find_python || (
            echo   Python 3.%PY_MIN_MINOR%+ not found and no conda.
            echo   Install Python 3 from python.org ^(check "Add to PATH"^), then try again.
            exit /b 1
        )
        echo   First-time setup ^(this can take a minute^)
        %FOUND_PY% -m venv "%VENV_DIR%" || ( echo   Could not create the Python environment. & exit /b 1 )
        "%VENV_DIR%\Scripts\python.exe" -m pip install --upgrade pip >nul 2>&1
        echo   Installing %APP_NAME%...
        "%VENV_DIR%\Scripts\pip.exe" install -e "%SCRIPT_DIR%" || ( echo   Install failed. & exit /b 1 )
    )
    set "PY="%VENV_DIR%\Scripts\python.exe""
    set "PIP="%VENV_DIR%\Scripts\pip.exe""
    exit /b 0

rem First Python that actually runs and is >= 3.%PY_MIN_MINOR%. Prefer versions
rem with full prebuilt-wheel coverage (3.11/3.12) over 3.13+ where python-rtmidi
rem may have no wheel yet. Uses the `py` launcher when available, else `python`.
:find_python
    set "FOUND_PY="
    where py >nul 2>&1 && (
        for %%V in (3.11 3.12 3.13) do (
            if not defined FOUND_PY (
                py -%%V -c "import sys" >nul 2>&1 && set "FOUND_PY=py -%%V"
            )
        )
        if not defined FOUND_PY (
            py -3 -c "import sys;exit(0 if sys.version_info[:2]>=(3,%PY_MIN_MINOR%) else 1)" >nul 2>&1 && set "FOUND_PY=py -3"
        )
    )
    if not defined FOUND_PY (
        python -c "import sys;exit(0 if sys.version_info[:2]>=(3,%PY_MIN_MINOR%) else 1)" >nul 2>&1 && set "FOUND_PY=python"
    )
    if defined FOUND_PY exit /b 0
    exit /b 1

rem ============================================================================
rem  Start Menu shortcut integration
rem ============================================================================

:install_shortcut
    rem The shortcut launches directly (--launch): skips the menu, just sets up
    rem the env and starts. Still routed through setup.bat so it self-heals
    rem if the folder moves.
    set "_icon="
    if exist "%SCRIPT_DIR%\assets\icon.ico" set "_icon=%SCRIPT_DIR%\assets\icon.ico"
    powershell -NoProfile -ExecutionPolicy Bypass -Command ^
        "$s=(New-Object -ComObject WScript.Shell).CreateShortcut('%SHORTCUT%');" ^
        "$s.TargetPath='%SCRIPT_DIR%\setup.bat';" ^
        "$s.Arguments='--launch';" ^
        "$s.WorkingDirectory='%SCRIPT_DIR%';" ^
        "if('%_icon%' -ne ''){$s.IconLocation='%_icon%,0'};" ^
        "$s.Description='Roland Bridge Cast controller';" ^
        "$s.Save()" >nul 2>&1
    if exist "%SHORTCUT%" (
        echo   Added %APP_NAME% to your Start Menu
    ) else (
        echo   Could not create the Start Menu shortcut ^(continuing anyway^).
    )
    exit /b 0

:remove_shortcut
    if exist "%SHORTCUT%" (
        del /f /q "%SHORTCUT%" >nul 2>&1
        echo   Removed %APP_NAME% from your Start Menu
        echo   ^(the environment in .venv / conda is left untouched^)
    ) else (
        echo   %APP_NAME% wasn't in your Start Menu - nothing to remove.
    )
    exit /b 0

rem ============================================================================

:show_help
    echo usage: setup.bat [--install ^| --launch ^| --uninstall]
    echo   no args (in a terminal): shows the menu
    goto :eof_exit

:fail
    echo.
    echo   Something went wrong. See the messages above.
    if /I not "%ACTION%"=="" pause
    exit /b 1

:bye
    echo   Bye!
    goto :eof_exit

:eof_exit
    exit /b 0
