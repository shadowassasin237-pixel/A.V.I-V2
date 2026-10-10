"""A.V.I. safe desktop-control tools.

These tools deliberately avoid arbitrary shell execution. Computer control is
opt-in through AVI_ALLOW_COMPUTER_CONTROL=1.
"""
from __future__ import annotations

import os
import subprocess
import time
import webbrowser
from pathlib import Path

ENABLED = os.getenv("AVI_ALLOW_COMPUTER_CONTROL", "0").strip().lower() in {"1", "true", "yes", "on"}

COMMON_APPS = {
    "notepad": ["notepad.exe"],
    "calculator": ["calc.exe"],
    "paint": ["mspaint.exe"],
    "file explorer": ["explorer.exe"],
    "explorer": ["explorer.exe"],
    "chrome": ["cmd.exe", "/c", "start", "", "chrome"],
    "google chrome": ["cmd.exe", "/c", "start", "", "chrome"],
    "edge": ["cmd.exe", "/c", "start", "", "msedge"],
    "microsoft edge": ["cmd.exe", "/c", "start", "", "msedge"],
    "vscode": ["code.exe"],
    "visual studio code": ["code.exe"],
}


def _guard():
    if not ENABLED:
        return "Computer control is disabled. Set AVI_ALLOW_COMPUTER_CONTROL=1 in .env and restart A.V.I."
    return ""


def open_application(name: str) -> str:
    """Open a known Windows application or a common executable name."""
    err = _guard()
    if err:
        return err
    name = (name or "").strip().lower()
    if not name:
        return "Tell me which application to open."
    command = COMMON_APPS.get(name)
    if command is None:
        # Allow a simple executable name only; never accept shell syntax.
        if any(x in name for x in ["&", "|", ";", ">", "<", "`", "\n"]):
            return "I won't execute shell syntax through the computer tool."
        exe = name if name.endswith(".exe") else name + ".exe"
        command = [exe]
    try:
        subprocess.Popen(command, shell=False)
        return f"Opened {name}."
    except FileNotFoundError:
        return f"I couldn't find the application {name}."
    except Exception as exc:
        return f"I couldn't open {name}: {exc}"


def open_path(path: str) -> str:
    """Open a local file/folder with the Windows default application."""
    err = _guard()
    if err:
        return err
    raw = os.path.expandvars(os.path.expanduser((path or "").strip().strip('"')))
    if not raw:
        return "Tell me which file or folder to open."
    p = Path(raw).resolve()
    try:
        if not p.exists():
            return f"I couldn't find {p}."
        os.startfile(str(p))  # type: ignore[attr-defined]
        return f"Opened {p}."
    except Exception as exc:
        return f"I couldn't open {p}: {exc}"


def open_website(url: str) -> str:
    """Open a URL in the default browser."""
    err = _guard()
    if err:
        return err
    url = (url or "").strip()
    if not url:
        return "Tell me which website to open."
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    try:
        webbrowser.open(url, new=2)
        return f"Opened {url}."
    except Exception as exc:
        return f"I couldn't open the website: {exc}"


def create_folder(path: str) -> str:
    """Create a folder, including parents."""
    err = _guard()
    if err:
        return err
    raw = os.path.expandvars(os.path.expanduser((path or "").strip().strip('"')))
    if not raw:
        return "Tell me where to create the folder."
    p = Path(raw).resolve()
    try:
        p.mkdir(parents=True, exist_ok=True)
        return f"Folder ready: {p}."
    except Exception as exc:
        return f"I couldn't create the folder: {exc}"


def wait_seconds(seconds: float = 1.0) -> str:
    """Pause briefly for a desktop sequence. Maximum 10 seconds."""
    err = _guard()
    if err:
        return err
    seconds = max(0.0, min(float(seconds), 10.0))
    time.sleep(seconds)
    return f"Waited {seconds:g} seconds."
