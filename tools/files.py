"""A.V.I. filesystem tools."""
from __future__ import annotations

import os
from pathlib import Path

ROOTS = [Path.home() / "Desktop", Path.home() / "Documents", Path.home() / "Downloads"]


def _safe_path(path: str) -> Path:
    raw = os.path.expandvars(os.path.expanduser((path or "").strip().strip('"')))
    return Path(raw).resolve()


def find_files(query: str, location: str = "") -> str:
    """Search common user folders for filenames containing query."""
    query = (query or "").strip().lower()
    if not query:
        return "Tell me what file to find."
    roots = [_safe_path(location)] if location else ROOTS
    hits = []
    for root in roots:
        if not root.exists():
            continue
        try:
            for p in root.rglob("*"):
                if len(hits) >= 30:
                    break
                if p.is_file() and query in p.name.lower():
                    hits.append(str(p))
        except (PermissionError, OSError):
            continue
    if not hits:
        return f"I couldn't find a file matching '{query}'."
    return "Matching files:\n" + "\n".join(f"- {p}" for p in hits)


def list_folder(path: str = "") -> str:
    """List a folder without executing anything."""
    p = _safe_path(path or str(Path.home() / "Desktop"))
    if not p.exists() or not p.is_dir():
        return f"Folder not found: {p}"
    try:
        items = sorted(p.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))[:80]
        if not items:
            return f"{p} is empty."
        return "\n".join(("[DIR] " if x.is_dir() else "[FILE] ") + x.name for x in items)
    except Exception as exc:
        return f"I couldn't list {p}: {exc}"


def create_text_file(path: str, content: str = "") -> str:
    """Create or overwrite a text file. Intended for user-requested generated notes/code."""
    p = _safe_path(path)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content or "", encoding="utf-8")
        return f"Created {p}."
    except Exception as exc:
        return f"I couldn't create {p}: {exc}"
