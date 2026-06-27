@echo off
setlocal
cd /d "%~dp0.."
"%~dp0..\.venv\Scripts\python.exe" -m PyInstaller --clean --console --name SchoolERP launcher.py
if errorlevel 1 (
    echo Build failed.
    exit /b 1
)
echo Build complete. Check dist\SchoolERP.exe
