"""
A.V.I. Tool Registry
--------------------

The @register decorator pattern adapted from MYRAA.  Each tool module
registers handlers into a flat ``TOOLS`` dict mapping
``tool_name -> callable(args: dict) -> dict``.

Handlers return a plain dict, typically ``{"result": "<status>"}``.
Errors should raise ``ToolError(message)`` so the brain can map them to
a user-friendly ``{"ok": False, "error": message}`` response.

Permissions
-----------
Each tool declares a risk level and required permission via the
``@register`` decorator.  A.V.I.'s brain consults the ``PERMISSIONS`` dict
before dispatching.  Users can grant/revoke individual permissions in
the GUI settings (Round 2).

Safety levels
-------------
* ``R0_READ``  - safe read-only inspection (active window, file stat, …)
* ``R1_REVERSIBLE`` - reversible user-visible action (open app, type, click)
* ``R2_MODERATE``  - moderate side-effects (create file, install)
* ``R3_DANGEROUS`` - requires GUI confirmation (delete, kill, move outside safe roots)
* ``R4_POWER``     - two-step token confirmation (shutdown, restart, sleep, lock)

A user with the corresponding permission can call R-level tools.
Anything at R3+ that lacks permission returns a graceful "permission
denied" message instead of an exception so the LLM can recover.
"""
from __future__ import annotations

import importlib
import logging
import os
import threading
from typing import Any, Callable, Dict, List, Optional, Tuple

log = logging.getLogger("avi.tools")


# ---------------------------------------------------------------
# Risk-level constants (must be defined early — used by _SHORT_RISK)
# ---------------------------------------------------------------

R0 = "R0_READ"
R1 = "R1_REVERSIBLE"
R2 = "R2_MODERATE"
R3 = "R3_DANGEROUS"
R4 = "R4_POWER"
RISK_LEVELS = (R0, R1, R2, R3, R4)

# ---------------------------------------------------------------
# Error type — raised by handlers, caught by the dispatcher
# ---------------------------------------------------------------


class ToolError(Exception):
    """Raised by a tool handler to signal a clean, user-facing failure."""

    def __init__(self, message: str, *, fatal: bool = False):
        super().__init__(message)
        self.message = message
        self.fatal = fatal


# ---------------------------------------------------------------
# Process-wide shared state (confirmation tokens, etc.)
# ---------------------------------------------------------------


class _State:
    """Process-wide shared state for tool handlers.

    Confirmation tokens for dangerous (power) actions:
    token -> {"action": <tool_name>, "expires": <epoch>}
    """

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.confirmations: Dict[str, Dict[str, Any]] = {}


STATE = _State()


# ---------------------------------------------------------------
# Risk-level normalisation
# ---------------------------------------------------------------

# Short aliases that the migrated MYRAA tools use, expanded to the
# canonical full names the rest of A.V.I. uses.
_SHORT_RISK = {
    "R0": R0,
    "R1": R1,
    "R2": R2,
    "R3": R3,
    "R4": R4,
    "READ": R0,
    "REVERSIBLE": R1,
    "MODERATE": R2,
    "DANGEROUS": R3,
    "POWER": R4,
}


def _normalise_risk(risk: str) -> str:
    risk = str(risk).upper().strip()
    return _SHORT_RISK.get(risk, risk)


# ---------------------------------------------------------------
# Registration
# ---------------------------------------------------------------

# tool_name -> handler(args: dict) -> dict
TOOLS: Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]] = {}

# tool_name -> (risk_level, description, required_permission)
META: Dict[str, Dict[str, Any]] = {}

# Permission flags (read from env on startup, also writable from the
# settings dialog at runtime).
DEFAULT_PERMISSIONS: Dict[str, bool] = {
    # Reads
    "systemInfo": True,
    "gpuInfo": True,
    "temperatureInfo": True,
    "screenFingerprint": True,
    "captureForVision": True,
    "getMonitors": True,
    "inputState": True,
    "activeWindow": True,
    "listVisibleWindows": True,
    "getActiveWindow": True,
    "recentFiles": True,
    "knownFolder": True,
    "statPath": True,
    "readFile": True,
    "listFiles": True,
    "searchFiles": True,
    "getClipboard": True,
    "takeScreenshot": True,
    "saveScreenshot": True,
    "analyzeScreenshot": True,
    "readScreen": True,
    "viewScreen": True,
    "observeDesktopState": True,
    "browserState": True,
    "systemInfo": True,
    "screenFingerprint": True,
    "captureForVision": True,
    # R1 reversible
    "openApplication": True,
    "openPath": True,
    "openWebsite": True,
    "searchWeb": True,
    "searchYouTube": True,
    "searchGoogle": True,
    "searchGitHub": True,
    "createFile": True,
    "createPythonFile": True,
    "writeCodeFile": True,
    "createProjectFolder": True,
    "createFolder": True,
    "openFolder": True,
    "renameFile": True,
    "moveFile": True,
    "copyFile": True,
    "typeText": True,
    "pressKey": True,
    "hotkey": True,
    "typeUnicode": True,
    "click": True,
    "doubleClick": True,
    "rightClick": True,
    "drag": True,
    "scroll": True,
    "moveMouse": True,
    "getCursorPosition": True,
    "locateText": True,
    "clickText": True,
    "setClipboardText": True,
    "copyFilesToClipboard": True,
    "copySelected": True,
    "pasteClipboard": True,
    "clearClipboard": True,
    "runPythonScript": True,
    "volumeUp": True,
    "volumeDown": True,
    "setVolume": True,
    "muteToggle": True,
    "brightnessUp": True,
    "brightnessDown": True,
    "setBrightness": True,
    "minimizeWindow": True,
    "maximizeWindow": True,
    "switchApplication": True,
    "waitForUi": True,
    "findUi": True,
    "inspectUi": True,
    "uiAction": True,
    "selectFiles": True,
    # R2 moderate
    "desktopIcons": True,
    "moveDesktopIcon": True,
    "setBrightness": True,
    "openWebsite": True,
    "minimizeWindow": True,
    "maximizeWindow": True,
    "minimizeWindow": True,
    "maximizeWindow": True,
    "deleteFile": True,   # goes to recycle bin
    "closeWindow": True,
    "closeApplication": True,
    # R3 dangerous
    "shutdown_pc": False,
    "restart_pc": False,
    "sleep_pc": False,
    "lock_pc": False,
    "requestPowerAction": False,
    "executePowerAction": False,
    "enableAutoStart": False,
    "disableAutoStart": False,
    "getAutoStartStatus": True,
    "deleteFilePermanent": False,
    "openPathExecutable": False,
}


# Tool name -> permission flag name (defaults to the tool name itself)
PERMISSION_NAME: Dict[str, str] = {}


def permission_for(tool_name: str) -> str:
    """The env var / config key that gates this tool."""
    return PERMISSION_NAME.get(tool_name, tool_name)


def has_permission(tool_name: str) -> bool:
    """Check whether the current user has permission to call this tool."""
    key = permission_for(tool_name)
    env_key = f"AVI_PERM_{key}"
    if env_key in os.environ:
        return os.environ[env_key].strip().lower() in ("1", "true", "yes", "on")
    return DEFAULT_PERMISSIONS.get(key, True)


def set_permission(tool_name: str, granted: bool) -> None:
    """Update the in-memory + env permission for a tool."""
    DEFAULT_PERMISSIONS[permission_for(tool_name)] = bool(granted)
    os.environ[f"AVI_PERM_{permission_for(tool_name)}"] = "1" if granted else "0"


# ---------------------------------------------------------------
# Decorator
# ---------------------------------------------------------------


def register(
    name: str,
    *,
    risk: str = R1,
    description: str = "",
    permission: Optional[str] = None,
):
    """Decorator to register a handler under a tool name.

    Parameters
    ----------
    name : str
        Tool name as it will appear in TOOLS and the LLM's tool list.
    risk : str
        One of R0..R4.  Defaults to R1 (reversible user-visible).
    description : str
        One-line human description; used for the GUI's permission
        manager.  The handler's own docstring is used for the LLM.
    permission : str, optional
        If multiple tools should share a single permission toggle,
        set this to a common key.  Defaults to the tool's own name.
    """
    risk = _normalise_risk(risk)
    if risk not in RISK_LEVELS:
        raise ValueError(f"risk must be one of {RISK_LEVELS}, got {risk!r}")

    def deco(fn: Callable[[Dict[str, Any]], Dict[str, Any]]):
        if name in TOOLS:
            raise RuntimeError(f"Tool {name!r} is already registered.")
        TOOLS[name] = fn
        META[name] = {
            "risk": risk,
            "description": description or (fn.__doc__ or "").strip().splitlines()[0] if fn.__doc__ else "",
            "doc": (fn.__doc__ or "").strip(),
            "function": fn,
        }
        if permission is not None:
            PERMISSION_NAME[name] = permission
        # Default permission for new tools: True unless R3/R4
        DEFAULT_PERMISSIONS.setdefault(
            permission or name, risk not in (R3, R4)
        )
        return fn

    return deco


# ---------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------


class PermissionDenied(Exception):
    """Raised when the user hasn't granted permission to a tool."""

    def __init__(self, tool_name: str, risk: str):
        super().__init__(f"Permission denied for {tool_name} ({risk})")
        self.tool_name = tool_name
        self.risk = risk


def dispatch(name: str, args: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Look up + permission-check + call a tool.

    Returns
    -------
    dict
        On success: ``{"ok": True, "result": <handler result>, "tool": name}``
        On failure: ``{"ok": False, "error": "<message>", "tool": name, "risk": "R?"}``
    """
    args = args or {}
    handler = TOOLS.get(name)
    if handler is None:
        return {"ok": False, "tool": name, "error": f"Unknown tool {name!r}."}

    meta = META.get(name, {})
    risk = meta.get("risk", R1)

    if not has_permission(name):
        return {
            "ok": False,
            "tool": name,
            "error": (
                f"Permission denied for {name} (risk {risk}). "
                f"Enable it in the A.V.I. settings (⚙) to allow this tool."
            ),
            "risk": risk,
        }

    try:
        result = handler(args) or {}
    except ToolError as exc:
        return {"ok": False, "tool": name, "error": exc.message, "risk": risk}
    except PermissionDenied as exc:
        return {"ok": False, "tool": name, "error": str(exc), "risk": risk}
    except Exception as exc:  # noqa: BLE001
        log.exception("Tool %s raised an unhandled exception", name)
        return {
            "ok": False,
            "tool": name,
            "error": f"Tool {name} failed: {exc}",
            "risk": risk,
        }

    if not isinstance(result, dict):
        result = {"result": str(result)}
    result.setdefault("tool", name)
    result["ok"] = True
    result["risk"] = risk
    return result


# ---------------------------------------------------------------
# Loader
# ---------------------------------------------------------------

# Modules to import so their @register decorators run.
# Each is imported defensively — a missing/broken module must not
# prevent the rest of the toolset from loading.
_MODULE_NAMES: List[str] = [
    "tools_files",         # replaces the old A.V.I. files.py
    "tools_input",
    "tools_screenshot",
    "tools_perception",
    "tools_pc",
    "tools_windows",
    "tools_clipboard",
    "tools_websites",
    "tools_coding",
    "tools_applications",
    "tools_targeting",
    "tools_uia",
    "tools_system",
    "tools_confirmation",
    "tools_search",
]


def load_all() -> None:
    """Import every tool module so its @register decorators fire.

    This is called once at brain startup.  Individual failures are
    logged and swallowed so a single broken module never bricks the
    whole agent.
    """
    for mod_name in _MODULE_NAMES:
        # Module names are stored bare ("tools_files") so the brain
        # can look up which package they came from.  When actually
        # importing, we prefix with the "tools" package.
        full = mod_name if "." in mod_name else f"tools.{mod_name}"
        try:
            importlib.import_module(full)
        except Exception as exc:  # noqa: BLE001
            log.warning("Tool module %s failed to import: %s", full, exc)


def list_tools() -> List[Dict[str, Any]]:
    """Return a list of all registered tools, sorted by name."""
    out: List[Dict[str, Any]] = []
    for name, meta in sorted(META.items()):
        out.append(
            {
                "name": name,
                "risk": meta.get("risk", R1),
                "description": meta.get("description", ""),
                "doc": meta.get("doc", ""),
                "granted": has_permission(name),
            }
        )
    return out


# ---------------------------------------------------------------
# Confirmation token helpers (for power actions)
# ---------------------------------------------------------------

import secrets
import time

TOKEN_TTL_SECONDS = 60.0
DANGEROUS_ACTIONS = {"shutdown", "restart", "sleep", "lock"}
ACTION_LABEL = {
    "shutdown": "shut down the computer",
    "restart": "restart the computer",
    "sleep": "put the computer to sleep",
    "lock": "lock the computer",
}


def _purge_expired_confirmations() -> None:
    now = time.time()
    expired = [t for t, v in STATE.confirmations.items() if v["expires"] < now]
    for t in expired:
        STATE.confirmations.pop(t, None)


def mint_confirmation_token(action: str) -> Tuple[str, float]:
    """Create a single-use, short-lived token for a dangerous action."""
    if action not in DANGEROUS_ACTIONS:
        raise ValueError(f"Unknown action {action!r}")
    with STATE.lock:
        _purge_expired_confirmations()
        token = secrets.token_urlsafe(6)
        STATE.confirmations[token] = {
            "action": action,
            "expires": time.time() + TOKEN_TTL_SECONDS,
        }
    return token, TOKEN_TTL_SECONDS


def consume_confirmation_token(action: str, token: Optional[str]) -> None:
    """Validate & consume a confirmation token.  Raises ToolError on failure."""
    with STATE.lock:
        _purge_expired_confirmations()
        if not token:
            raise ToolError(
                f"No confirmation token supplied for {ACTION_LABEL.get(action, action)}. "
                "Call requestPowerAction first and ask the user to confirm."
            )
        entry = STATE.confirmations.get(token)
        if entry is None:
            raise ToolError(
                f"Confirmation token is invalid or expired for "
                f"{ACTION_LABEL.get(action, action)}. Ask the user again."
            )
        if entry["action"] != action:
            raise ToolError(
                "Confirmation token does not match the requested action."
            )
        STATE.confirmations.pop(token, None)


__all__ = [
    "TOOLS",
    "META",
    "ToolError",
    "PermissionDenied",
    "STATE",
    "R0",
    "R1",
    "R2",
    "R3",
    "R4",
    "RISK_LEVELS",
    "register",
    "dispatch",
    "load_all",
    "list_tools",
    "has_permission",
    "set_permission",
    "permission_for",
    "DEFAULT_PERMISSIONS",
    "DANGEROUS_ACTIONS",
    "ACTION_LABEL",
    "mint_confirmation_token",
    "consume_confirmation_token",
    "TOKEN_TTL_SECONDS",
]
