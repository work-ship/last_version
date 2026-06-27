from __future__ import annotations

import json
import shutil
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass
class AppSettings:
    host: str = "127.0.0.1"
    port: int = 8000
    auto_open_browser: bool = True
    auto_restart_services: bool = True
    enable_logs: bool = True
    app_root: str = ""
    python_executable: str = ""
    node_executable: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _find_project_root(start: Path | None = None) -> Path:
    """Find the Django project root by searching for manage.py upward from multiple locations."""
    candidates: list[Path] = []
    if start is not None:
        try:
            candidates.append(start.resolve())
        except Exception:
            pass

    try:
        current_dir = Path.cwd().resolve()
        candidates.append(current_dir)
    except Exception:
        pass

    # When running as bundled .exe, search from executable location
    if getattr(sys, "frozen", False):
        try:
            exe_path = Path(sys.executable).resolve()
            exe_parent = exe_path.parent
            candidates.extend([
                exe_parent,
                exe_parent.parent,
                exe_parent.parent.parent,
                exe_parent.parent.parent.parent,
            ])
        except Exception:
            pass

    # Source/development mode locations
    try:
        launcher_dir = Path(__file__).resolve().parent
        candidates.extend([
            launcher_dir.parent,
            launcher_dir.parent.parent,
        ])
    except Exception:
        pass

    seen: set[Path] = set()
    for candidate in candidates:
        try:
            candidate = candidate.resolve()
        except Exception:
            continue
        for path in [candidate, *candidate.parents]:
            if path in seen:
                continue
            seen.add(path)
            try:
                manage_py = path / "manage.py"
                whatsapp_js = path / "whatsapp_service" / "server.js"
                if manage_py.exists() and whatsapp_js.exists():
                    return path
            except Exception:
                continue

    # Return current directory as fallback, but ensure it's valid
    try:
        return Path.cwd().resolve()
    except Exception:
        # If even that fails, return Path("/")
        return Path("/")


def _default_app_root() -> Path:
    return _find_project_root()


def _default_python_executable(app_root: Path) -> str:
    candidate = app_root / "Python" / "python.exe"
    if candidate.exists():
        return str(candidate)
    return sys.executable


def _default_node_executable() -> str:
    for name in ("node.exe", "node"):
        found = shutil.which(name)
        if found:
            return found
    return "node"


def load_settings(config_path: Path | None = None, app_root: Path | None = None) -> AppSettings:
    """Load settings from config file or return sensible defaults if all else fails."""
    
    # Determine app root
    app_root_resolved: Path | None = None
    if app_root:
        try:
            app_root_resolved = app_root.resolve()
        except Exception:
            pass
    
    if not app_root_resolved:
        try:
            app_root_resolved = _find_project_root().resolve()
        except Exception:
            pass
    
    if not app_root_resolved:
        try:
            app_root_resolved = Path.cwd().resolve()
        except Exception:
            app_root_resolved = Path("C:\\")

    # Build config candidates
    config_candidates: list[Path] = []
    
    if config_path:
        try:
            config_candidates.append(config_path.resolve())
        except Exception:
            pass
    
    # Try Launcher/config.json
    if app_root_resolved:
        try:
            launcher_config = app_root_resolved / "Launcher" / "config.json"
            config_candidates.append(launcher_config)
        except Exception:
            pass
    
    # Try root config.json
    if app_root_resolved:
        try:
            root_config = app_root_resolved / "config.json"
            config_candidates.append(root_config)
        except Exception:
            pass

    # Try to load from existing config files
    for config_file in config_candidates:
        try:
            if config_file and config_file.exists():
                with config_file.open("r", encoding="utf-8") as handle:
                    raw_data = json.load(handle)
                settings = AppSettings(**raw_data)
                if not settings.app_root:
                    settings.app_root = str(app_root_resolved)
                if not settings.python_executable:
                    settings.python_executable = _default_python_executable(app_root_resolved)
                if not settings.node_executable:
                    settings.node_executable = _default_node_executable()
                return settings
        except Exception:
            continue

    # Create defaults
    defaults = AppSettings(
        app_root=str(app_root_resolved),
        python_executable=_default_python_executable(app_root_resolved),
        node_executable=_default_node_executable(),
    )

    # Try to write defaults to first valid config file location
    for config_file in config_candidates:
        try:
            if not config_file:
                continue
            parent_dir = config_file.parent
            parent_dir.mkdir(parents=True, exist_ok=True)
            with config_file.open("w", encoding="utf-8") as handle:
                json.dump(defaults.to_dict(), handle, indent=2)
            return defaults
        except (OSError, IOError, PermissionError, TypeError):
            continue
        except Exception:
            continue

    return defaults
