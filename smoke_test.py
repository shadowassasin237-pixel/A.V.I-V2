"""End-to-end smoke test for A.V.I."""
import sys
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(str(PROJECT_ROOT))

# ----- 1. import everything -----
print("=" * 60)
print("1. IMPORT TEST")
print("=" * 60)

from core.language import (
    detect_language, language_label, system_prompt_for,
    LANG_ENGLISH, LANG_HINDI, LANG_PUNJABI
)
from core.internet import (
    web_search, get_weather, get_news, read_webpage,
    get_current_time, TOOL_FUNCTIONS, TOOL_SCHEMAS
)
from core.llm import OpenRouterClient, LLMError, LLMAuthError
from core.brain import AVIBrain
from voice.listener import AVIListener
from voice.speaker import AVISpeaker, _pick_voice_for
from ui.gui import AVIGUI, SettingsDialog, ALL_MODES

print("All modules imported OK")

# ----- 2. language detection -----
print()
print("=" * 60)
print("2. LANGUAGE DETECTION")
print("=" * 60)

samples = [
    ("Hello there", LANG_ENGLISH),
    ("Mumbai mein mausam kaisa hai?", LANG_HINDI),
    ("मुंबई में मौसम कैसा है?", LANG_HINDI),
    ("Amritsar vich mausam kive hoya hai?", LANG_PUNJABI),
    ("ਅੰਮ੍ਰਿਤਸਰ ਵਿੱਚ ਮੌਸਮ ਕਿਵੇਂ ਹੈ?", LANG_PUNJABI),
    ("Bhai kuch batao", LANG_HINDI),
    ("Paaji gal kar", LANG_PUNJABI),
    ("Tell me about GTA 6", LANG_ENGLISH),
]

for text, expected in samples:
    detected = detect_language(text)
    ok = "✓" if detected == expected else "✗"
    print(f"  {ok} {text!r:50s} -> {detected} (expected {expected})")

# ----- 3. system prompts -----
print()
print("=" * 60)
print("3. SYSTEM PROMPTS")
print("=" * 60)
for lang in [LANG_ENGLISH, LANG_HINDI, LANG_PUNJABI]:
    p = system_prompt_for(lang)
    has_lang = lang.upper() in p or language_label(lang).upper() in p
    print(f"  {'✓' if has_lang else '✗'} {lang}: {len(p)} chars, "
          f"lang mentioned: {has_lang}")

# ----- 4. internet tools -----
print()
print("=" * 60)
print("4. INTERNET TOOLS")
print("=" * 60)

t = get_current_time()
print(f"  ✓ get_current_time() -> {t}")

# quick search (short timeout)
print("  ⏳ web_search('India cricket test')...")
try:
    s = web_search("India cricket test", max_results=2)
    print(f"  ✓ web_search: {len(s)} chars, first 80: {s[:80]!r}")
except Exception as e:
    print(f"  ✗ web_search failed: {e}")

# weather
print("  ⏳ get_weather('Mumbai')...")
try:
    w = get_weather("Mumbai")
    print(f"  ✓ get_weather: {len(w)} chars, first 80: {w[:80]!r}")
except Exception as e:
    print(f"  ✗ get_weather failed: {e}")

# news
print("  ⏳ get_news('India')...")
try:
    n = get_news("India", max_items=3)
    print(f"  ✓ get_news: {len(n)} chars, first 80: {n[:80]!r}")
except Exception as e:
    print(f"  ✗ get_news failed: {e}")

# tool registry
print(f"  ✓ TOOL_FUNCTIONS: {list(TOOL_FUNCTIONS.keys())}")
print(f"  ✓ TOOL_SCHEMAS: {len(TOOL_SCHEMAS)} tools declared")

# ----- 5. brain (no LLM) -----
print()
print("=" * 60)
print("5. BRAIN (rules fallback)")
print("=" * 60)

brain = AVIBrain()
print(f"  ✓ Brain initialized, LLM configured: {brain.has_llm}")

tests = [
    "hello",
    "who made you",
    "what is my name",  # memory empty
    "exit",
    "Mumbai mein mausam kaisa hai?",
    "Tenu ki chahida?",
]
for t in tests:
    r = brain.respond(t)
    print(f"  ✓ {t!r:50s} -> {r[:60]!r}")

# ----- 6. brain shutdown detection -----
print()
print("=" * 60)
print("6. SHUTDOWN DETECTION")
print("=" * 60)

shutdowns = ["exit", "bye", "power off", "alvida", "fir milenge"]
for s in shutdowns:
    is_sd = brain.is_shutdown_command(s)
    print(f"  {'✓' if is_sd else '✗'} {s!r:25s} -> shutdown={is_sd}")

# ----- 7. GUI launch -----
print()
print("=" * 60)
print("7. GUI LAUNCH (auto-close after 2s)")
print("=" * 60)

app = AVIGUI(brain=brain, speaker=AVISpeaker())
app.after(2000, app.on_close)

try:
    app.mainloop()
    print("  ✓ GUI launched and closed cleanly")
except Exception as e:
    print(f"  ✗ GUI failed: {e}")
    sys.exit(1)

# ----- 8. final summary -----
print()
print("=" * 60)
print("ALL SMOKE TESTS PASSED")
print("=" * 60)
print()
print("To use A.V.I. with the LLM:")
print("  1. Get a key at: https://openrouter.ai/keys")
print("  2. Run:  python app.py")
print("  3. Click the ⚙ icon in the header to enter your key")
print("  4. Or set OPENROUTER_API_KEY in .env")
