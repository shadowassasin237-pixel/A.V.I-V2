"""
A.V.I. Internet Tools
Live data the LLM can call as functions:
  - web_search
  - get_weather
  - read_webpage
  - get_news
  - get_current_time

Plus everything auto-discovered from the tools/registry (Round 1):
  - screenshots, mouse / keyboard, UI Automation, file ops,
    applications, system info, perception, etc.
"""

import re
import json
import urllib.parse
from datetime import datetime
from html import unescape

import requests
from ddgs import DDGS
from bs4 import BeautifulSoup


# ---------------------------------------------------------------
# Tool registry auto-discovery
# ---------------------------------------------------------------
# All @register'd tools (tools_*.py) become available to the LLM
# automatically.  The registry loads on first call to get_all_*
# so importing this module never crashes even if a single tool
# module has a missing dep.

_REGISTRY_LOADED = False


def _ensure_registry_loaded() -> None:
    global _REGISTRY_LOADED
    if _REGISTRY_LOADED:
        return
    try:
        from tools.registry import load_all
        load_all()
        _REGISTRY_LOADED = True
    except Exception as _exc:  # noqa: BLE001
        # Don't break the legacy tools if the registry fails
        import logging
        logging.getLogger("avi.core").warning(
            "Tool registry failed to load: %s", _exc
        )


def _build_registry_tool_dispatch():
    """Return a function that dispatches registered tools to their
    registered handlers, with permission checks and error mapping.
    """
    from tools.registry import dispatch
    def _runner(args: dict) -> str:
        # We need the tool name.  The LLM always calls tools with
        # the name as the first positional — here we don't have it
        # in args, so the LLM client should call dispatch directly.
        # This helper is for legacy single-name dispatch.
        name = args.get("__tool_name__") or args.get("name") or args.get("tool")
        if not name:
            return (
                "Tool dispatch error: no tool name supplied. "
                "Use the registry dispatcher directly."
            )
        result = dispatch(name, {k: v for k, v in args.items() if k != "__tool_name__"})
        ok = result.get("ok", False)
        if ok:
            return str(result.get("result", ""))
        return f"Tool {name} failed: {result.get('error', 'unknown error')}"
    return _runner


# Lightweight parameter-schema inference.  For tools that don't
# declare their own schema in META, we synthesise a permissive one
# so the LLM can still call them.

def _infer_schema_from_doc(doc: str) -> dict:
    """Heuristic schema generator: parses param names from the
    docstring's Args/Parameters block.
    """
    params = {"type": "object", "properties": {}}
    if not doc:
        return params
    lines = doc.splitlines()
    in_args = False
    for line in lines:
        stripped = line.strip()
        if not in_args:
            if re.match(r"^(Args|Arguments|Parameters)\s*:?\s*$", stripped):
                in_args = True
            continue
        if not stripped or re.match(r"^(Returns|Raises|Notes|Example)[:\s]",
                                    stripped):
            break
        m = re.match(r"^(\w+)\s*(\([^)]+\))?\s*:\s*(.*)$", stripped)
        if m:
            name = m.group(1)
            desc = m.group(3) or ""
            param_type = "string"
            low = desc.lower()
            if any(t in low for t in ("int", "integer", "count", "number", "seconds", "pixels")):
                param_type = "integer" if "int" in low or "count" in low or "pixels" in low or "seconds" in low else "number"
            elif any(t in low for t in ("bool", "true/false", "yes/no", "true or false")):
                param_type = "boolean"
            params["properties"][name] = {"type": param_type, "description": desc[:200]}
    return params


# ================================================================
# TIME
# ================================================================

def get_current_time(timezone_name: str = "local") -> str:
    """Return current time as a string. Always local for now."""
    now = datetime.now()
    return now.strftime("%A %d %B %Y, %I:%M:%S %p")


# ================================================================
# WEB SEARCH (DuckDuckGo)
# ================================================================

def web_search(query: str, max_results: int = 5) -> str:
    """Run a DuckDuckGo text search and return formatted results."""
    try:
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                results.append({
                    "title": r.get("title", ""),
                    "link": r.get("href", ""),
                    "snippet": r.get("body", "")
                })
        if not results:
            return "No results found."
        lines = []
        for i, r in enumerate(results, 1):
            lines.append(
                f"[{i}] {r['title']}\n"
                f"    {r['link']}\n"
                f"    {r['snippet']}"
            )
        return "\n\n".join(lines)
    except Exception as error:
        return f"Web search error: {error}"


# ================================================================
# WEATHER (wttr.in — no API key)
# ================================================================

def get_weather(city: str = "") -> str:
    """Get current weather for a city using wttr.in. No key needed."""
    try:
        location = city.strip() or "auto"
        url = f"https://wttr.in/{urllib.parse.quote(location)}?format=j1"
        resp = requests.get(url, timeout=10, headers={"User-Agent": "A.V.I."})
        if resp.status_code != 200:
            return f"Weather service error: HTTP {resp.status_code}"

        data = resp.json()
        current = data.get("current_condition", [{}])[0]
        area = data.get("nearest_area", [{}])[0]

        area_name = (
            area.get("areaName", [{}])[0].get("value", city or "Unknown")
        )
        region = (
            area.get("region", [{}])[0].get("value", "")
        )
        country = (
            area.get("country", [{}])[0].get("value", "")
        )

        desc = current.get("weatherDesc", [{}])[0].get("value", "Unknown")
        temp_c = current.get("temp_C", "?")
        temp_f = current.get("temp_F", "?")
        feels_c = current.get("FeelsLikeC", "?")
        humidity = current.get("humidity", "?")
        wind = current.get("windspeedKmph", "?")
        obs_time = current.get("observation_time", "")

        location_str = area_name
        if region and region != area_name:
            location_str += f", {region}"
        if country:
            location_str += f", {country}"

        return (
            f"Weather for {location_str}:\n"
            f"- Conditions: {desc}\n"
            f"- Temperature: {temp_c}°C ({temp_f}°F)\n"
            f"- Feels like: {feels_c}°C\n"
            f"- Humidity: {humidity}%\n"
            f"- Wind: {wind} km/h\n"
            f"- Observed: {obs_time} UTC"
        )
    except Exception as error:
        return f"Weather lookup error: {error}"


# ================================================================
# PAGE READER
# ================================================================

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


def read_webpage(url: str, max_chars: int = 6000) -> str:
    """Fetch a URL and return its main text content (truncated)."""
    try:
        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        resp = requests.get(
            url,
            timeout=12,
            headers={"User-Agent": _USER_AGENT}
        )
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")

        # remove script/style/nav/footer
        for tag in soup(["script", "style", "nav", "footer", "noscript",
                         "header", "aside"]):
            tag.decompose()

        # title
        title = soup.title.string.strip() if soup.title and soup.title.string else ""

        # gather paragraph text
        paragraphs = []
        for p in soup.find_all(["p", "h1", "h2", "h3", "li"]):
            text = p.get_text(separator=" ", strip=True)
            if text and len(text) > 25:
                paragraphs.append(text)

        body = "\n\n".join(paragraphs)
        body = re.sub(r"\s+", " ", body)

        if title:
            output = f"Title: {title}\n\n{body}"
        else:
            output = body

        if len(output) > max_chars:
            output = output[:max_chars] + "..."

        return output or "Page loaded but no readable text was found."
    except Exception as error:
        return f"Page read error: {error}"


# ================================================================
# NEWS (Google News RSS, no key)
# ================================================================

def get_news(topic: str = "", max_items: int = 5) -> str:
    """Fetch top news headlines from Google News RSS. No API key needed."""
    try:
        if topic:
            url = (
                "https://news.google.com/rss/search?q="
                + urllib.parse.quote(topic)
                + "&hl=en-IN&gl=IN&ceid=IN:en"
            )
        else:
            url = "https://news.google.com/rss?hl=en-IN&gl=IN&ceid=IN:en"

        resp = requests.get(
            url,
            timeout=12,
            headers={"User-Agent": _USER_AGENT}
        )
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "xml")
        items = soup.find_all("item")[:max_items]

        if not items:
            return "No news found."

        lines = []
        for i, item in enumerate(items, 1):
            title = item.title.string if item.title else "Untitled"
            title = unescape(title)
            pub = item.pubDate.string if item.pubDate else ""
            # Google News titles often end with " - Source Name"
            lines.append(f"[{i}] {title}\n    Published: {pub}")

        header = f"Top news" + (f" on '{topic}'" if topic else "") + ":"
        return header + "\n\n" + "\n\n".join(lines)
    except Exception as error:
        return f"News fetch error: {error}"


# ================================================================
# DESKTOP / VISION TOOL IMPORTS
# ================================================================

from tools.computer import open_application, open_path, open_website, create_folder, wait_seconds
from tools.files import find_files, list_folder, create_text_file
from tools.screenshot import capture_screenshot
from vision.camera import camera_status, capture_camera_frame
from tools.image_generator import generate_image


# ================================================================
# TOOL REGISTRY (used by LLM function-calling)
# ================================================================

# Built-in / legacy tools.  These stay as direct lambdas so they
# always work, even if the tool-registry import fails.
TOOL_FUNCTIONS = {
    "web_search": lambda args: web_search(args.get("query", ""), int(args.get("max_results", 5))),
    "get_weather": lambda args: get_weather(args.get("city", "")),
    "read_webpage": lambda args: read_webpage(args.get("url", ""), int(args.get("max_chars", 6000))),
    "get_news": lambda args: get_news(args.get("topic", ""), int(args.get("max_items", 5))),
    "get_current_time": lambda args: get_current_time(args.get("timezone", "local")),
    "open_application": lambda args: open_application(args.get("name", "")),
    "open_path": lambda args: open_path(args.get("path", "")),
    "open_website": lambda args: open_website(args.get("url", "")),
    "create_folder": lambda args: create_folder(args.get("path", "")),
    "find_files": lambda args: find_files(args.get("query", ""), args.get("location", "")),
    "list_folder": lambda args: list_folder(args.get("path", "")),
    "create_text_file": lambda args: create_text_file(args.get("path", ""), args.get("content", "")),
    "capture_screenshot": lambda args: capture_screenshot(args.get("path", "")),
    "camera_status": lambda args: camera_status(),
    "capture_camera_frame": lambda args: capture_camera_frame(args.get("path", "")),
    "generate_image": lambda args: generate_image(args.get("prompt", ""), args.get("filename", "")),
    "wait_seconds": lambda args: wait_seconds(float(args.get("seconds", 1))),
}


def _merge_registry_into_tool_functions() -> None:
    """After the registry has loaded, register every tool as a
    function the LLM can call directly.  The function calls
    ``registry.dispatch()`` so that permission checks and error
    mapping are applied consistently.
    """
    try:
        _ensure_registry_loaded()
        from tools.registry import TOOLS, dispatch as _dispatch
        for name in TOOLS:
            if name in TOOL_FUNCTIONS:
                continue  # built-in already present
            def _make(n: str):
                def _call(args: dict) -> str:
                    r = _dispatch(n, args)
                    if r.get("ok"):
                        return str(r.get("result", ""))
                    return f"Tool {n} failed: {r.get('error', 'unknown error')}"
                _call.__name__ = f"tool_{n}"
                return _call
            TOOL_FUNCTIONS[name] = _make(name)
    except Exception:
        pass


# Merge on import so the LLM client sees every tool immediately.
_merge_registry_into_tool_functions()


# ================================================================
# TOOL SCHEMAS
# ================================================================

_BUILTIN_TOOL_SCHEMAS = [
    {
        "name": "web_search",
        "description": "Search the web using DuckDuckGo for current information.",
        "parameters": {"type":"object","properties":{"query":{"type":"string"},"max_results":{"type":"integer","default":5}},"required":["query"]}
    },
    {
        "name": "get_weather",
        "description": "Get current weather for a city.",
        "parameters": {"type":"object","properties":{"city":{"type":"string"}},"required":[]}
    },
    {
        "name": "read_webpage",
        "description": "Read the text of a specific webpage.",
        "parameters": {"type":"object","properties":{"url":{"type":"string"},"max_chars":{"type":"integer","default":6000}},"required":["url"]}
    },
    {
        "name": "get_news",
        "description": "Fetch current news headlines, optionally filtered by topic.",
        "parameters": {"type":"object","properties":{"topic":{"type":"string"},"max_items":{"type":"integer","default":5}},"required":[]}
    },
    {
        "name": "get_current_time",
        "description": "Get the current local date and time.",
        "parameters": {"type":"object","properties":{"timezone":{"type":"string","default":"local"}},"required":[]}
    },
    {
        "name": "open_application",
        "description": "Open a desktop application such as Chrome, Notepad, Calculator, Paint, or File Explorer.",
        "parameters": {"type":"object","properties":{"name":{"type":"string"}},"required":["name"]}
    },
    {
        "name": "open_path",
        "description": "Open a local file or folder with its default Windows application.",
        "parameters": {"type":"object","properties":{"path":{"type":"string"}},"required":["path"]}
    },
    {
        "name": "open_website",
        "description": "Open a website in the default browser.",
        "parameters": {"type":"object","properties":{"url":{"type":"string"}},"required":["url"]}
    },
    {
        "name": "create_folder",
        "description": "Create a local folder.",
        "parameters": {"type":"object","properties":{"path":{"type":"string"}},"required":["path"]}
    },
    {
        "name": "find_files",
        "description": "Search Desktop, Documents, and Downloads for a filename.",
        "parameters": {"type":"object","properties":{"query":{"type":"string"},"location":{"type":"string"}},"required":["query"]}
    },
    {
        "name": "list_folder",
        "description": "List the contents of a local folder.",
        "parameters": {"type":"object","properties":{"path":{"type":"string"}},"required":[]}
    },
    {
        "name": "create_text_file",
        "description": "Create a text file with requested content.",
        "parameters": {"type":"object","properties":{"path":{"type":"string"},"content":{"type":"string"}},"required":["path","content"]}
    },
    {
        "name": "capture_screenshot",
        "description": "Capture the desktop and save a screenshot locally.",
        "parameters": {"type":"object","properties":{"path":{"type":"string"}},"required":[]}
    },
    {
        "name": "camera_status",
        "description": "Check whether the default webcam is available.",
        "parameters": {"type":"object","properties":{},"required":[]}
    },
    {
        "name": "capture_camera_frame",
        "description": "Capture one local webcam frame and save it.",
        "parameters": {"type":"object","properties":{"path":{"type":"string"}},"required":[]}
    },
    {
        "name": "generate_image",
        "description": "Generate an image from a prompt using the configured image provider and save it locally.",
        "parameters": {"type":"object","properties":{"prompt":{"type":"string"},"filename":{"type":"string"}},"required":["prompt"]}
    },
    {
        "name": "wait_seconds",
        "description": "Pause briefly during a desktop sequence; maximum 10 seconds.",
        "parameters": {"type":"object","properties":{"seconds":{"type":"number"}},"required":["seconds"]}
    },
]


# Plain list, populated with built-ins + registered tools at import
# time.  The LLM client treats it as a regular list.
TOOL_SCHEMAS: list = []


def _merge_registry_into_tool_schemas() -> None:
    """Add a schema for every registered tool so the LLM can call it."""
    # 1. Built-ins first
    TOOL_SCHEMAS.extend(_BUILTIN_TOOL_SCHEMAS)
    # 2. Then everything from the registry
    try:
        _ensure_registry_loaded()
        from tools.registry import META, has_permission
        existing = {s.get("name") for s in TOOL_SCHEMAS}
        for name, meta in META.items():
            if name in existing:
                continue
            doc = meta.get("doc", "")
            desc = meta.get("description", "")
            if not desc and doc:
                first = doc.strip().splitlines()
                desc = first[0] if first else name
            params = _infer_schema_from_doc(doc)
            if not params.get("properties") and not params.get("required"):
                params = {"type": "object", "properties": {}}
            risk = meta.get("risk", "R1")
            granted = has_permission(name)
            perm_note = (
                f" [risk {risk}, "
                f"{'granted' if granted else 'DENIED - ask user to enable'}]"
            )
            TOOL_SCHEMAS.append({
                "name": name,
                "description": (desc or name) + perm_note,
                "parameters": params,
            })
    except Exception:
        pass


_merge_registry_into_tool_schemas()


if __name__ == "__main__":
    print("Current time:", get_current_time())
