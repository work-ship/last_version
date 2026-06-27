from __future__ import annotations

import os
import subprocess
import threading
import time
from pathlib import Path
from typing import Optional

import psutil
import requests

from .config import AppSettings
from .logger_utils import LoggerManager


class ServiceManager:
    def __init__(self, settings: AppSettings, logger_manager: LoggerManager) -> None:
        self.settings = settings
        self.logger_manager = logger_manager
        self.app_root = Path(settings.app_root).resolve()
        self.django_logger = logger_manager.get_logger("django", "django.log")
        self.whatsapp_logger = logger_manager.get_logger("whatsapp", "whatsapp.log")
        self.launcher_logger = logger_manager.get_logger("launcher", "launcher.log")
        self.django_process: Optional[subprocess.Popen[bytes]] = None
        self.whatsapp_process: Optional[subprocess.Popen[bytes]] = None
        self.monitor_thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()
        self._lock = threading.Lock()

    def start_services(self) -> None:
        self._check_required_files()
        self._ensure_django_running()
        self._ensure_whatsapp_running()

    def _check_required_files(self) -> None:
        required = [
            self.app_root / "manage.py",
            self.app_root / "whatsapp_service" / "server.js",
        ]
        missing = [path for path in required if not path.exists()]
        if missing:
            raise FileNotFoundError("Missing required files: " + ", ".join(str(path) for path in missing))

    def _check_port_availability(self) -> None:
        port = self.settings.port
        for conn in psutil.net_connections(kind="inet"):
            if conn.status == "LISTEN" and conn.laddr.port == port:
                raise RuntimeError(f"Port {port} is already in use by another service.")

    def _ensure_django_running(self) -> None:
        url = f"http://{self.settings.host}:{self.settings.port}"
        try:
            response = requests.get(url, timeout=1.5)
            if response.ok:
                self.launcher_logger.info("Django is already responding at %s", url)
                self.django_process = None
                return
        except requests.RequestException:
            pass

        self._check_port_availability()
        self._start_django()

    def _ensure_whatsapp_running(self) -> None:
        if self._is_process_running("whatsapp") or self._is_process_running("server.js"):
            self.whatsapp_logger.info("WhatsApp service is already running.")
            self.whatsapp_process = None
            return
        self._start_whatsapp()

    def _is_process_running(self, token: str) -> bool:
        try:
            try:
                iterator = psutil.process_iter(["pid", "name", "cmdline"], ignore_errors=True)
            except TypeError:
                iterator = psutil.process_iter(["pid", "name", "cmdline"])
            for proc in iterator:
                try:
                    cmdline = " ".join(proc.info.get("cmdline") or [])
                except Exception:
                    # Some psutil versions may not populate .info or cmdline; skip safely
                    continue
                if token.lower() in cmdline.lower():
                    return True
        except Exception:
            return False
        return False

    def _start_django(self) -> None:
        python_executable = Path(self.settings.python_executable)
        if not python_executable.exists():
            raise FileNotFoundError(f"Python executable not found: {python_executable}")

        command = [str(python_executable), "manage.py", "runserver", f"{self.settings.host}:{self.settings.port}"]
        self.django_logger.info("Starting Django with command: %s", " ".join(command))
        self.django_process = self._spawn_process(
            command=command,
            cwd=self.app_root,
            log_path=self.app_root / "logs" / "django.log",
            logger=self.django_logger,
            name="Django",
        )

    def _start_whatsapp(self) -> None:
        node_executable = self.settings.node_executable or "node"
        command = [str(node_executable), str(self.app_root / "whatsapp_service" / "server.js")]
        self.whatsapp_logger.info("Starting WhatsApp service with command: %s", " ".join(command))
        self.whatsapp_process = self._spawn_process(
            command=command,
            cwd=self.app_root / "whatsapp_service",
            log_path=self.app_root / "logs" / "whatsapp.log",
            logger=self.whatsapp_logger,
            name="WhatsApp",
        )

    def _spawn_process(self, *, command: list[str], cwd: Path, log_path: Path, logger, name: str) -> subprocess.Popen[bytes]:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_handle = log_path.open("a", encoding="utf-8")
        creationflags = 0
        if os.name == "nt":
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        process = subprocess.Popen(
            command,
            cwd=str(cwd),
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            creationflags=creationflags,
            text=False,
        )
        logger.info("Started %s process with pid %s", name, process.pid)
        return process

    def wait_for_django(self, timeout_seconds: int = 60) -> bool:
        url = f"http://{self.settings.host}:{self.settings.port}"
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            if self.stop_event.is_set():
                return False
            try:
                response = requests.get(url, timeout=1.5)
                if response.ok:
                    self.launcher_logger.info("Django is responding at %s", url)
                    return True
            except requests.RequestException:
                pass
            time.sleep(1)
        self.launcher_logger.error("Django did not become ready within %s seconds", timeout_seconds)
        return False

    def start_monitor(self) -> None:
        self.stop_event.clear()
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()

    def _monitor_loop(self) -> None:
        while not self.stop_event.is_set():
            self._check_process("django", self.django_process, self.settings.auto_restart_services)
            self._check_process("whatsapp", self.whatsapp_process, self.settings.auto_restart_services)
            time.sleep(5)

    def _check_process(self, name: str, process: Optional[subprocess.Popen[bytes]], should_restart: bool) -> None:
        if process is None:
            return
        return_code = process.poll()
        if return_code is None:
            return
        self.launcher_logger.warning("%s process exited unexpectedly with code %s", name, return_code)
        if should_restart:
            if name == "django":
                self._start_django()
            else:
                self._start_whatsapp()

    def stop_services(self) -> None:
        self.stop_event.set()
        for process, name in ((self.django_process, "django"), (self.whatsapp_process, "whatsapp")):
            if process is None:
                continue
            try:
                if process.poll() is None:
                    process.terminate()
                    process.wait(timeout=10)
            except Exception:
                try:
                    process.kill()
                except Exception:
                    pass
            self.launcher_logger.info("Stopped %s process", name)
