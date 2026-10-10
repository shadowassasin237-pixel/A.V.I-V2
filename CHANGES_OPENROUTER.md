# A.V.I. — Gemini removed, OpenRouter in

## What changed

| File | Change |
|---|---|
| `core/llm.py` | Rewritten. `OpenRouterClient` replaces `GeminiClient` (kept as an alias). Same public interface: `is_configured`, `configure()`, `system_prompt`, `generate(msg, history, use_tools)`. |
| `config.py` | `GEMINI_API_KEY` / `GEMINI_MODEL` → `OPENROUTER_API_KEY`, `LLM_MODEL`, `OPENROUTER_BASE_URL`, `OPENROUTER_APP_NAME`, `OPENROUTER_SITE_URL`. |
| `core/brain.py` | Imports `OpenRouterClient`, defaults to `LLM_MODEL` from config, error text points at OpenRouter. |
| `ui/gui.py` | Settings dialog relabelled; model dropdown now holds OpenRouter ids. |
| `app.py`, `smoke_test.py`, `.env`, `requirements.txt` | Updated names, links and comments. |

`core/internet.py`, `core/language.py`, `core/memory.py`, `tools/web.py` and
everything under `voice/` are untouched.

## Tool calling still works

`TOOL_SCHEMAS` stays in its existing flat format. `core/llm.py` converts it to
OpenAI's `{"type": "function", "function": {...}}` shape at call time and
lowercases any uppercase JSON-schema types. `TOOL_FUNCTIONS` handlers are still
called with a single args dict, exactly as before.

Verified end to end against a mocked API: all five tools are advertised, a
`get_current_time` call round-trips through the tool loop, and the model's
final text comes back.

## Model choice matters

Search, weather, news and page reading all depend on tool calling, and plenty
of OpenRouter models — free ones especially — don't support it. Default is
`openai/gpt-4o-mini`. Free model ids rotate with little notice, so check
<https://openrouter.ai/models> before pinning one.

## Voice

OpenRouter is text-only. `voice/speaker.py` (pyttsx3) is unchanged and still
works as the local fallback. For real-time speech, LiveKit sits *outside* this
code: its agent handles STT and TTS, and calls `AVIBrain.respond(text) -> str`
as the thinking step. Nothing in the brain or LLM client needs to change for
that — `respond()` is already a plain text-in/text-out function.

## Run

```
pip install -r requirements.txt
# paste your key into OPENROUTER_API_KEY in .env
python app.py
```
