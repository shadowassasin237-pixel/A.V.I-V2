from __future__ import annotations
"""
Search commands: open a search results page for a query on a given engine.

These launch in the user's actual Windows default browser. In-page
interaction uses the native screen, mouse, and keyboard tools.
"""

from typing import Any, Dict, Optional, Tuple, List, Union, Iterable, Callable, Set, Iterator

from tools.registry import ToolError, register
from tools.tools_websites import _build_search_url, open_url


@register("searchWeb", risk="R1", description="Search a query on a search engine.")
def search_web(args: Dict[str, Any]) -> Dict[str, Any]:
    query = args.get("query") or args.get("q")
    engine = (args.get("engine") or "google").strip().lower()
    if not query:
        raise ToolError("Parameter 'query' is required.")
    url = _build_search_url(engine, str(query))
    resolved = open_url(url)
    return {"result": f"Searching {engine} for '{query}': opened {resolved}."}


@register("searchYouTube", risk="R1", description="Search a query on YouTube.")
def search_youtube(args: Dict[str, Any]) -> Dict[str, Any]:
    query = args.get("query") or args.get("q")
    if not query:
        raise ToolError("Parameter 'query' is required.")
    url = _build_search_url("youtube", str(query))
    resolved = open_url(url)
    return {"result": f"YouTube search for '{query}' opened at {resolved}."}


@register("searchGoogle", risk="R1", description="Search a query on Google.")
def search_google(args: Dict[str, Any]) -> Dict[str, Any]:
    query = args.get("query") or args.get("q")
    if not query:
        raise ToolError("Parameter 'query' is required.")
    url = _build_search_url("google", str(query))
    resolved = open_url(url)
    return {"result": f"Google search for '{query}' opened at {resolved}."}


@register("searchGitHub", risk="R1", description="Search a query on GitHub.")
def search_github(args: Dict[str, Any]) -> Dict[str, Any]:
    query = args.get("query") or args.get("q")
    if not query:
        raise ToolError("Parameter 'query' is required.")
    url = _build_search_url("github", str(query))
    resolved = open_url(url)
    return {"result": f"GitHub search for '{query}' opened at {resolved}."}


__all__ = ["search_web", "search_youtube", "search_google", "search_github"]