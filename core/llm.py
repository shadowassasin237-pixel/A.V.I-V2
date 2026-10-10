"""
A.V.I. LLM Client — OpenRouter (OpenAI-compatible REST API)

Direct HTTP calls to OpenRouter. No SDK required.
One key gives access to hundreds of models (GPT, Claude, Llama, Qwen,
DeepSeek, Mistral, plus several free ones).

Endpoint:
  POST https://openrouter.ai/api/v1/chat/completions
  Authorization: Bearer sk-or-v1-...

Handles function calling (tool use) in a multi-turn loop, exactly like the
old Gemini client did. TOOL_SCHEMAS from core/internet.py are converted to
OpenAI tool format automatically, so that file needs no changes.
"""

import os
import time
import json
import requests

from core.internet import TOOL_FUNCTIONS, TOOL_SCHEMAS


# ================================================================
# CONFIG
# ================================================================

DEFAULT_MODEL = os.getenv("AVI_LLM_MODEL", "openai/gpt-4o-mini")

API_BASE = os.getenv(
    "AVI_LLM_BASE_URL", "https://openrouter.ai/api/v1"
).rstrip("/")

# Optional attribution headers (shown on openrouter.ai rankings)
APP_NAME = os.getenv("AVI_APP_NAME", "A.V.I.")
SITE_URL = os.getenv("AVI_SITE_URL", "")

MAX_TOOL_TURNS = 12       # allow long agentic chains (was 6, too low for
                           # multi-step desktop tasks)
REQUEST_TIMEOUT = 90       # seconds — give the model room for bigger
                           # tool chains


# ================================================================
# EXCEPTIONS
# ================================================================

class LLMError(Exception):
    pass


class LLMAuthError(LLMError):
    pass


class LLMRateLimitError(LLMError):
    pass


# ================================================================
# TOOL SCHEMA CONVERSION
# ================================================================
# core/internet.py declares tools in Gemini's flat format:
#     {"name": ..., "description": ..., "parameters": {...}}
# OpenRouter wants OpenAI's nested format:
#     {"type": "function", "function": {"name": ..., "parameters": {...}}}

def _lower_types(node):
    """Recursively lowercase JSON-schema type values (OBJECT -> object)."""
    if isinstance(node, dict):
        out = {}
        for key, value in node.items():
            if key == "type" and isinstance(value, str):
                out[key] = value.lower()
            else:
                out[key] = _lower_types(value)
        return out
    if isinstance(node, list):
        return [_lower_types(item) for item in node]
    return node


def _to_openai_tool(tool):
    """Convert one tool declaration. Accepts either format."""
    if not isinstance(tool, dict):
        return None

    if tool.get("type") == "function" and isinstance(tool.get("function"), dict):
        fn = dict(tool["function"])
    elif "name" in tool:
        fn = {
            "name": tool["name"],
            "description": tool.get("description", ""),
            "parameters": tool.get("parameters")
                          or {"type": "object", "properties": {}},
        }
    else:
        return None

    fn["parameters"] = _lower_types(
        fn.get("parameters") or {"type": "object", "properties": {}}
    )
    fn.setdefault("description", "")
    return {"type": "function", "function": fn}


def build_openai_tools(schemas=None):
    """Flatten and convert TOOL_SCHEMAS into OpenAI tool format."""
    schemas = TOOL_SCHEMAS if schemas is None else schemas
    if not schemas:
        return []

    flat = []
    for tool in schemas:
        if isinstance(tool, dict) and "function_declarations" in tool:
            flat.extend(tool["function_declarations"])
        elif isinstance(tool, dict) and "functionDeclarations" in tool:
            flat.extend(tool["functionDeclarations"])
        else:
            flat.append(tool)

    out = []
    for tool in flat:
        converted = _to_openai_tool(tool)
        if converted:
            out.append(converted)
    return out


# ================================================================
# CLIENT
# ================================================================

class OpenRouterClient:
    """Thin OpenRouter client with tool-calling support."""

    def __init__(
        self,
        api_key: str = "",
        model: str = DEFAULT_MODEL,
        system_prompt: str = "",
    ):
        self.api_key = api_key.strip() if api_key else ""
        self.model = (model or "").strip() or DEFAULT_MODEL
        self.system_prompt = system_prompt
        self.last_error = ""
        self._last_call_at = 0.0
        self._session = requests.Session()

    # --------------------------------------------------------
    # availability
    # --------------------------------------------------------

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    def configure(self, api_key: str, model: str = None):
        self.api_key = (api_key or "").strip()
        if model:
            self.model = model.strip()

    # --------------------------------------------------------
    # core
    # --------------------------------------------------------

    def generate(
        self,
        user_message: str,
        history: list = None,
        use_tools: bool = True,
    ) -> str:
        """
        Send a message and return the final text reply.
        Performs an internal tool-calling loop (up to MAX_TOOL_TURNS).
        """
        if not self.is_configured:
            raise LLMAuthError("OpenRouter API key not set.")

        messages = self._build_messages(history or [], user_message)
        tools = build_openai_tools() if use_tools else []

        for turn in range(MAX_TOOL_TURNS):
            payload = {
                "model": self.model,
                "messages": messages,
                "temperature": 0.7,
                "top_p": 0.9,
                "max_tokens": 1024,
            }
            if tools:
                payload["tools"] = tools
                payload["tool_choice"] = "auto"

            data = self._post(payload)

            choices = data.get("choices", [])
            if not choices:
                return "I'm not able to respond to that right now."

            message = choices[0].get("message") or {}
            tool_calls = message.get("tool_calls") or []

            if not tool_calls:
                text = (message.get("content") or "").strip()
                return text or "(empty response)"

            # the model wants to use tools — record its turn, then answer it
            messages.append({
                "role": "assistant",
                "content": message.get("content") or "",
                "tool_calls": tool_calls,
            })

            for call in tool_calls:
                messages.append(self._run_tool(call))

        # ran out of turns
        return (
            "I went too deep looking for an answer. "
            "Could you rephrase the question?"
        )

    # --------------------------------------------------------
    # internals
    # --------------------------------------------------------

    def _build_messages(self, history, user_message):
        """
        Build the OpenAI message list.

        Accepts the old Gemini-style history used by core/brain.py
        ({"role": "user"|"model", "text": ...}) as well as plain
        OpenAI-style entries ({"role": ..., "content": ...}).
        """
        messages = []

        if self.system_prompt:
            messages.append({
                "role": "system",
                "content": self.system_prompt,
            })

        # truncate history to last 10 to keep the prompt small
        for h in history[-10:]:
            if not isinstance(h, dict):
                continue

            role = h.get("role")
            content = h.get("content")
            if content is None:
                content = h.get("text", "")

            if role == "model":
                role = "assistant"
            if role not in ("user", "assistant", "system") or not content:
                continue

            messages.append({"role": role, "content": content})

        messages.append({"role": "user", "content": user_message})
        return messages

    def _headers(self):
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        if SITE_URL:
            headers["HTTP-Referer"] = SITE_URL
        if APP_NAME:
            headers["X-Title"] = APP_NAME
        return headers

    def _post(self, payload: dict) -> dict:
        # small rate-limit guard
        wait = 0.4 - (time.time() - self._last_call_at)
        if wait > 0:
            time.sleep(wait)
        self._last_call_at = time.time()

        url = f"{API_BASE}/chat/completions"
        try:
            resp = self._session.post(
                url,
                json=payload,
                timeout=REQUEST_TIMEOUT,
                headers=self._headers(),
            )
        except requests.RequestException as e:
            raise LLMError(f"Network error: {e}")

        if resp.status_code in (401, 403):
            raise LLMAuthError(
                "OpenRouter rejected the API key. "
                "Check it at openrouter.ai/keys."
            )
        if resp.status_code == 402:
            raise LLMError(
                "Out of OpenRouter credits for this model. "
                "Switch to a ':free' model or top up your account."
            )
        if resp.status_code == 429:
            raise LLMRateLimitError("Rate limit hit. Try again in a moment.")
        if resp.status_code == 404:
            raise LLMError(
                f"Model '{self.model}' not found on OpenRouter. "
                "Check the id at openrouter.ai/models."
            )

        try:
            data = resp.json()
        except ValueError as e:
            raise LLMError(f"Invalid JSON from OpenRouter: {e}")

        if not resp.ok or "error" in data:
            err = data.get("error")
            message = err.get("message") if isinstance(err, dict) else str(err)
            raise LLMError(
                message or f"OpenRouter HTTP {resp.status_code}: "
                           f"{resp.text[:300]}"
            )

        return data

    def _run_tool(self, call: dict) -> dict:
        """Execute one tool call and return the tool message for the model."""
        fn_block = call.get("function") or {}
        name = fn_block.get("name", "")
        raw_args = fn_block.get("arguments") or "{}"

        try:
            args = json.loads(raw_args) if isinstance(raw_args, str) \
                else dict(raw_args)
        except (ValueError, TypeError):
            args = {}

        handler = TOOL_FUNCTIONS.get(name)
        if not handler:
            result = f"Unknown tool '{name}'"
        else:
            try:
                # TOOL_FUNCTIONS handlers take a single args dict
                result = handler(args)
            except Exception as e:
                result = f"Tool error: {e}"

        return {
            "role": "tool",
            "tool_call_id": call.get("id", name),
            "name": name,
            "content": str(result)[:8000],
        }

    # --------------------------------------------------------
    # helpers for the settings dialog
    # --------------------------------------------------------

    def test_key(self) -> bool:
        """Cheap round-trip to check the key works."""
        try:
            self._post({
                "model": self.model,
                "messages": [{"role": "user", "content": "ping"}],
                "max_tokens": 5,
                "temperature": 0,
            })
            self.last_error = ""
            return True
        except LLMError as e:
            self.last_error = str(e)
            return False

    def list_models(self) -> list:
        """Return available model ids from OpenRouter (no key required)."""
        try:
            resp = self._session.get(
                f"{API_BASE}/models", timeout=REQUEST_TIMEOUT
            )
            resp.raise_for_status()
            return sorted(
                m.get("id", "") for m in resp.json().get("data", [])
            )
        except Exception as e:
            raise LLMError(f"Could not list models: {e}")


# ================================================================
# BACKWARDS COMPATIBILITY
# ================================================================
# Old code did `from core.llm import GeminiClient`. Keep that working.
GeminiClient = OpenRouterClient
LLMClient = OpenRouterClient


# ================================================================
# TEST
# ================================================================

if __name__ == "__main__":

    key = os.getenv("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", "")

    if not key:
        print("Set OPENROUTER_API_KEY env var to test live.")
    else:
        c = OpenRouterClient(
            api_key=key,
            system_prompt=(
                "You are A.V.I. Reply in the user's language. "
                "Be brief."
            )
        )
        print(c.generate("Hello! What can you do?"))
