@echo off
REM Create a Windows shortcut that launches SchoolERP.exe with the correct working directory
setlocal

if not exist "dist\SchoolERP\SchoolERP.exe" (
    echo SchoolERP.exe not found. Run build first: .venv\Scripts\python.exe -m PyInstaller --noconsole --windowed --name SchoolERP launcher.py
    exit /b 1
)

set SCRIPT_DIR=%~dp0
set EXE_PATH=%SCRIPT_DIR%dist\SchoolERP\SchoolERP.exe
set SHORTCUT_PATH=%SCRIPT_DIR%SchoolERP.lnk
set WORKING_DIR=%SCRIPT_DIR%

echo Creating shortcut: %SHORTCUT_PATH%

powershell -Command ^
    "$WshShell = New-Object -ComObject WScript.Shell; " ^
    "$Shortcut = $WshShell.CreateShortcut('%SHORTCUT_PATH%'); " ^
    "$Shortcut.TargetPath = '%EXE_PATH%'; " ^
    "$Shortcut.WorkingDirectory = '%WORKING_DIR%'; " ^
    "$Shortcut.WindowStyle = 1; " ^
    "$Shortcut.Description = 'SchoolERP Launcher'; " ^
    "$Shortcut.Save()"

if %errorlevel% equ 0 (
    echo Shortcut created successfully!
    echo Double-click SchoolERP.lnk to start the application.
) else (
    echo Failed to create shortcut.
    exit /b 1
)
