"""Desktop screenshot tool."""
from __future__ import annotations

import os
from pathlib import Path
from datetime import datetime


def capture_screenshot(path: str = "") -> str:
    """Capture the primary desktop using Pillow if installed."""
    try:
        from PIL import ImageGrab
    except ImportError:
        return "Screenshot support needs Pillow. Install it with: pip install pillow"

    if path:
        target = Path(os.path.expandvars(os.path.expanduser(path))).resolve()
    else:
        target = Path(__file__).resolve().parent.parent / "generated" / f"screenshot_{datetime.now():%Y%m%d_%H%M%S}.png"
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        image = ImageGrab.grab(all_screens=True)
        image.save(target)
        return f"Screenshot saved to {target}."
    except Exception as exc:
        return f"I couldn't capture the screen: {exc}"
