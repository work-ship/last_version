# SchoolERP Launcher

This launcher starts the Django app and the WhatsApp service on Windows and keeps them running in the background.

## What it does
- Shows a splash screen while services start.
- Checks for a running duplicate instance.
- Validates that required files exist.
- Starts Django with `manage.py runserver`.
- Starts WhatsApp with `server.js`.
- Waits for Django to respond before opening the browser.
- Monitors both services and restarts them if configured.
- Stops both processes cleanly when the launcher closes.

## Build SchoolERP.exe

**From the project root directory**, run:

```powershell
.venv\Scripts\python.exe -m PyInstaller `
  --noconsole `
  --windowed `
  --name SchoolERP `
  --distpath dist `
  launcher.py
```

The executable will be created at `dist/SchoolERP/SchoolERP.exe`.

## Deployment

The .exe must be run from the project directory (or with the project as the current working directory) so it can find `manage.py` and the `whatsapp_service` folder.

For best results, place the .exe in the project root and create a Windows shortcut that:
1. Sets the working directory to the project root
2. Points to `dist/SchoolERP/SchoolERP.exe`
