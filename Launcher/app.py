from __future__ import annotations

import argparse
import os
import sys
import threading
import webbrowser
from pathlib import Path
from tkinter import Tk, ttk, messagebox

from .config import AppSettings, load_settings
from .logger_utils import LoggerManager
from .service_manager import ServiceManager


class SingleInstanceGuard:
    def __init__(self, app_name: str) -> None:
        self.app_name = app_name
        self._mutex = None

    def acquire(self) -> bool:
        if os.name != "nt":
            return True
        import ctypes

        self._mutex = ctypes.windll.kernel32.CreateMutexW(None, False, self.app_name)
        last_error = ctypes.windll.kernel32.GetLastError()
        return last_error != 183

    def release(self) -> None:
        if self._mutex is not None and os.name == "nt":
            import ctypes

            ctypes.windll.kernel32.ReleaseMutex(self._mutex)


class SplashWindow(Tk):
    def __init__(self, title: str = "SchoolERP Launcher") -> None:
        super().__init__()
        self.title(title)
        self.overrideredirect(True)
        self.configure(bg="#0f172a")
        self.geometry("520x260")
        self.resizable(False, False)
        self._center_window()

        self.label = ttk.Label(
            self,
            text="Starting SchoolERP...",
            foreground="#f8fafc",
            background="#0f172a",
            font=("Segoe UI", 16, "bold"),
        )
        self.label.pack(pady=(40, 10))

        self.progress = ttk.Progressbar(self, mode="indeterminate", length=360)
        self.progress.pack(pady=10)
        self.progress.start(12)

        self.status = ttk.Label(
            self,
            text="Preparing services",
            foreground="#cbd5e1",
            background="#0f172a",
            font=("Segoe UI", 10),
        )
        self.status.pack(pady=10)

    def _center_window(self) -> None:
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        if width == 1 and height == 1:
            width = 520
            height = 260
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = (screen_width // 2) - (width // 2)
        y = (screen_height // 2) - (height // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")

    def set_status(self, message: str) -> None:
        self.status.configure(text=message)
        self.update_idletasks()


class LauncherWindow(Tk):
    def __init__(self, controller: "SchoolERPLauncher") -> None:
        super().__init__()
        self.controller = controller
        self.title("SchoolERP Launcher")
        self.geometry("560x220")
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self.controller.shutdown)
        self.configure(bg="#f8fafc")
        self._build_ui()

    def _build_ui(self) -> None:
        ttk.Label(self, text="SchoolERP is running", font=("Segoe UI", 16, "bold")).pack(pady=(24, 6))
        ttk.Label(
            self,
            text="The web app and WhatsApp service are being monitored in the background.",
            wraplength=500,
            justify="center",
        ).pack(pady=(0, 16))
        ttk.Button(self, text="Stop Services", command=self.controller.shutdown).pack()


class SchoolERPLauncher:
    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings
        self.app_root = Path(settings.app_root).resolve()
        self.log_dir = self.app_root / "logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.logger_manager = LoggerManager(self.log_dir, enabled=settings.enable_logs)
        self.launcher_logger = self.logger_manager.get_logger("launcher", "launcher.log")
        self.service_manager = ServiceManager(settings, self.logger_manager)
        self.guard = SingleInstanceGuard("SchoolERP-LAUNCHER")
        self.splash: SplashWindow | None = None
        self.window: LauncherWindow | None = None
        self._shutdown_requested = False
        self._monitor_thread: threading.Thread | None = None

    def run(self, validate_only: bool = False) -> None:
        if not self.guard.acquire():
            raise RuntimeError("Another instance of SchoolERP Launcher is already running.")

        try:
            self._show_splash("Preparing SchoolERP")
            self.launcher_logger.info("Launcher started")
            self._validate_environment()
            self._show_splash("Starting services")
            self.service_manager.start_services()
            if not self.service_manager.wait_for_django():
                if self.service_manager.django_process is not None:
                    raise RuntimeError("Django did not start successfully.")
                self.launcher_logger.info("Django is already available; continuing without restart.")
            self._show_splash("Opening browser")
            if self.settings.auto_open_browser and not validate_only:
                self._open_browser()
            if validate_only:
                self.launcher_logger.info("Validation complete; exiting without keeping the launcher open.")
                return
            self.service_manager.start_monitor()
            self.window = LauncherWindow(self)
            self.window.mainloop()
        except Exception as exc:
            self.launcher_logger.exception("Launcher failed: %s", exc)
            messagebox.showerror("SchoolERP Launcher", str(exc))
        finally:
            self.shutdown()
            self.guard.release()

    def _validate_environment(self) -> None:
        self._require_file(self.app_root / "manage.py", "manage.py")
        self._require_file(self.app_root / "whatsapp_service" / "server.js", "whatsapp_service/server.js")
        self._require_file(Path(self.settings.python_executable), "Python interpreter")
        if not self.settings.node_executable:
            raise RuntimeError("Node.js was not found. Install Node.js and retry.")

    def _require_file(self, path: Path | str, label: str) -> None:
        target = Path(path)
        if not target.exists():
            raise FileNotFoundError(f"Missing {label}: {target}")

    def _show_splash(self, message: str) -> None:
        if self.splash is None:
            self.splash = SplashWindow()
            self.splash.update_idletasks()
        self.splash.set_status(message)
        self.splash.update_idletasks()

    def _open_browser(self) -> None:
        url = f"http://{self.settings.host}:{self.settings.port}"
        try:
            webbrowser.open(url, new=0)
            self.launcher_logger.info("Opened browser at %s", url)
        except Exception as exc:
            self.launcher_logger.warning("Browser launch failed: %s", exc)

    def shutdown(self) -> None:
        if self._shutdown_requested:
            return
        self._shutdown_requested = True
        self.launcher_logger.info("Shutting down launcher and services")
        self.service_manager.stop_services()
        if self.window is not None:
            self.window.destroy()
        if self.splash is not None:
            self.splash.destroy()
        self.launcher_logger.info("Launcher shut down")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="SchoolERP Windows launcher")
    parser.add_argument("--validate-only", action="store_true", help="Check configuration and exit")
    parser.add_argument("--config", type=str, default=None, help="Path to config.json")
    return parser.parse_args()


def main() -> None:
    try:
        args = parse_args()
        config_path = None
        if args.config:
            try:
                config_path = Path(args.config).resolve()
            except Exception:
                pass
        
        settings = load_settings(config_path=config_path)
        app = SchoolERPLauncher(settings)
        app.run(validate_only=args.validate_only)
    except Exception as e:
        import traceback
        from tkinter import Tk, messagebox
        
        root = Tk()
        root.withdraw()
        error_msg = f"Launcher Error:\n{type(e).__name__}: {str(e)}\n\nCheck logs for details."
        messagebox.showerror("SchoolERP Launcher Error", error_msg)
        root.destroy()
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    sys.exit(main())
