"""Configurable image-generation bridge.

The desktop app does not pretend that an OpenRouter key is automatically an
image-generation key. Set AVI_IMAGE_API_URL and AVI_IMAGE_MODEL when using a
compatible OpenAI-style image endpoint. OPENAI_API_KEY can also be used with
the official OpenAI Images API when installed.
"""
from __future__ import annotations

import base64
import os
from pathlib import Path
from datetime import datetime
import requests


def generate_image(prompt: str, filename: str = "") -> str:
    prompt = (prompt or "").strip()
    if not prompt:
        return "Tell me what image you want me to generate."

    out = Path(filename).expanduser().resolve() if filename else Path(__file__).resolve().parent.parent / "generated" / f"avi_image_{datetime.now():%Y%m%d_%H%M%S}.png"
    out.parent.mkdir(parents=True, exist_ok=True)

    api_url = os.getenv("AVI_IMAGE_API_URL", "").strip()
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    model = os.getenv("AVI_IMAGE_MODEL", "gpt-image-1").strip()

    if api_url and api_key:
        try:
            response = requests.post(
                api_url,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={"model": model, "prompt": prompt, "size": "1024x1024", "n": 1},
                timeout=120,
            )
            response.raise_for_status()
            data = response.json()
            item = (data.get("data") or [{}])[0]
            if item.get("b64_json"):
                out.write_bytes(base64.b64decode(item["b64_json"]))
            elif item.get("url"):
                img = requests.get(item["url"], timeout=120)
                img.raise_for_status()
                out.write_bytes(img.content)
            else:
                return "The image service returned no image data."
            return f"Image generated and saved to {out}."
        except Exception as exc:
            return f"Image generation failed: {exc}"

    if api_key:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=api_key)
            result = client.images.generate(model=model, prompt=prompt, size="1024x1024")
            item = result.data[0]
            if getattr(item, "b64_json", None):
                out.write_bytes(base64.b64decode(item.b64_json))
            elif getattr(item, "url", None):
                img = requests.get(item.url, timeout=120)
                img.raise_for_status()
                out.write_bytes(img.content)
            else:
                return "The image service returned no image data."
            return f"Image generated and saved to {out}."
        except ImportError:
            return "Image generation needs the openai package: pip install openai"
        except Exception as exc:
            return f"Image generation failed: {exc}"

    return "Image generation is ready, but no image provider is configured. Set OPENAI_API_KEY or AVI_IMAGE_API_URL/AVI_IMAGE_MODEL in .env."
