"""
A.V.I. Brain
Conversation, smart memory, web search, and LLM (OpenRouter) with tool calling.

Resolution order:
  1. Built-in commands (shutdown, memory ops, name/game/color etc.)
  2. LLM (OpenRouter) with function-calling tools (web/weather/news/etc.)
  3. Rule-based fallback when LLM is not configured or errors out
"""

import random

from core.memory import AVIMemory
from core.language import (
    detect_language, system_prompt_for, LANG_ENGLISH
)
from core.llm import (
    OpenRouterClient, LLMError, LLMAuthError, LLMRateLimitError
)
from core.internet import TOOL_FUNCTIONS, TOOL_SCHEMAS
from tools.web import AVIWebSearch
from config import LLM_MODEL


class AVIBrain:

    def __init__(self, api_key: str = "", model: str = ""):
        self.name = "A.V.I."
        self.status = "online"

        self.memory = AVIMemory()
        self.web = AVIWebSearch()
        self.llm = OpenRouterClient(
            api_key=api_key,
            model=model or LLM_MODEL,
            system_prompt=system_prompt_for(LANG_ENGLISH)
        )

        # Load the auto-discovered tool registry (Round 1) so the
        # LLM can call any of the ~70 MYRAA-derived tools without
        # any code change here.
        try:
            from tools.registry import load_all, list_tools
            load_all()
            tools = list_tools()
            self.available_tools = [t["name"] for t in tools]
            print(f"A.V.I. brain: {len(tools)} tools available from registry.")
        except Exception as exc:
            self.available_tools = []
            print(f"A.V.I. brain: tool registry load failed: {exc}")

        # last known user language (defaults to English on first turn)
        self.current_language = LANG_ENGLISH

    # ============================================================
    # CONFIG
    # ============================================================

    def configure_llm(self, api_key: str, model: str = ""):
        self.llm.configure(api_key, model)

    @property
    def has_llm(self) -> bool:
        return self.llm.is_configured

    # ============================================================
    # SHUTDOWN / EXIT INTENT
    # ============================================================

    SHUTDOWN_PHRASES = {
        "exit", "quit", "bye", "goodbye", "close",
        "shut down", "shutdown", "power off", "turn off",
        "terminate", "stop", "good night", "goodnight",
        "see you", "see ya", "cya", "later",
        "alvida", "bid ", "alwida",     # Hindi
        "khuda hafiz", "alvida",         # Hindi/Urdu farewell
        "fir milenge", "milte hain",     # Hindi
        "lehi",                          # Punjabi casual
    }

    GOODBYE_RESPONSES = [
        "Shutting down. Goodbye.",
        "Powering off. See you soon.",
        "Systems standing down. Goodbye.",
        "Going offline. Talk to you later.",
    ]

    def is_shutdown_command(self, text: str) -> bool:
        if not text:
            return False
        cleaned = (
            text.lower()
            .strip()
            .replace(".", "")
            .replace("!", "")
            .replace("?", "")
        )
        if cleaned in self.SHUTDOWN_PHRASES:
            return True
        for phrase in self.SHUTDOWN_PHRASES:
            if phrase in cleaned:
                return True
        return False

    # ============================================================
    # MAIN ENTRY
    # ============================================================

    def respond(self, user_input: str) -> str:

        text = user_input.strip()
        if not text:
            return "I didn't hear anything."

        lower_text = text.lower()

        # ---------------------------------------------------------
        # 1. SHUTDOWN
        # ---------------------------------------------------------

        if self.is_shutdown_command(text):
            return random.choice(self.GOODBYE_RESPONSES)

        # ---------------------------------------------------------
        # 2. UPDATE LANGUAGE + SYSTEM PROMPT
        # ---------------------------------------------------------

        self.current_language = detect_language(text)
        self.llm.system_prompt = system_prompt_for(self.current_language)

        # ---------------------------------------------------------
        # 3. LLM PATH (primary when configured)
        # ---------------------------------------------------------

        if self.has_llm:
            try:
                return self._llm_respond(text)
            except LLMAuthError as e:
                return (
                    f"{e} Open settings (⚙) to add your OpenRouter API key. "
                    "I'll fall back to local rules for now."
                )
            except LLMRateLimitError as e:
                return f"{e} Falling back to local response."
            except LLMError as e:
                return f"LLM error: {e}. Falling back to local."

        # ---------------------------------------------------------
        # 4. RULE-BASED FALLBACK
        # ---------------------------------------------------------

        return self._rule_based_respond(text, lower_text)

    # ============================================================
    # LLM PATH
    # ============================================================

    def _llm_respond(self, text: str) -> str:
        # small history with memory recall context
        history = self._build_memory_context()
        return self.llm.generate(text, history=history)

    def _build_memory_context(self) -> list:
        """Feed the LLM a short memory dump so it knows user facts."""
        mem = self.memory.all_memory()
        if not mem:
            return []
        lines = ["Known facts about the user:"]
        for k, v in mem.items():
            lines.append(f"- {k}: {v}")
        return [{
            "role": "user",
            "text": "\n".join(lines)
        }]

    # ============================================================
    # RULE-BASED FALLBACK (works without any API key)
    # ============================================================

    def _rule_based_respond(self, text: str, lower_text: str) -> str:

        # ----- basic conversation -----
        if "hello" in lower_text or "hi " in lower_text or lower_text == "hi":
            return "Hello. A.V.I. is online and ready."

        if "your name" in lower_text:
            return "My name is A.V.I. — Artificial Voice Intelligence."

        creator_phrases = [
            "who made you", "who created you", "who is your creator",
            "who's your creator", "who built you", "who developed you",
            "who designed you", "who programmed you",
            "who created avi", "who made avi", "who built avi",
        ]
        if any(p in lower_text for p in creator_phrases):
            return "I was made by Arnav Kumar."

        if "how are you" in lower_text:
            return "All systems are operational."

        if "status" in lower_text:
            return "A.V.I. is online and ready."

        # ----- web search -----
        if (lower_text.startswith("search ")
                or lower_text.startswith("search the web for ")
                or lower_text.startswith("look up ")):
            if lower_text.startswith("search the web for "):
                query = text[len("search the web for "):].strip()
            elif lower_text.startswith("search "):
                query = text[len("search "):].strip()
            else:
                query = text[len("look up "):].strip()

            if not query:
                return "What would you like me to search for?"

            results = self.web.search(query, max_results=3)
            if not results:
                return "I couldn't find any search results."
            if "error" in results[0]:
                return "I couldn't complete the web search."

            r = results[0]
            title = r.get("title", "").strip()
            snippet = r.get("snippet", "").strip()
            if len(snippet) > 300:
                snippet = snippet[:300] + "..."
            if title and snippet:
                return f"I found a result about {title}. {snippet}"
            if title:
                return f"I found a result about {title}."
            return "I found a web result, but not enough information."

        # ----- memory write -----
        if lower_text.startswith("my name is "):
            value = text[len("my name is "):].strip()
            self.memory.remember("name", value)
            return f"I'll remember that your name is {value}."

        if lower_text.startswith("i live in "):
            value = text[len("i live in "):].strip()
            self.memory.remember("location", value)
            return f"I'll remember that you live in {value}."

        if lower_text.startswith("my favorite color is "):
            value = text[len("my favorite color is "):].strip()
            self.memory.remember("favorite_color", value)
            return f"I'll remember that your favorite color is {value}."

        if lower_text.startswith("my favourite color is "):
            value = text[len("my favourite colour is "):].strip()
            self.memory.remember("favorite_color", value)
            return f"I'll remember that your favorite color is {value}."

        if lower_text.startswith("my favorite game is "):
            value = text[len("my favorite game is "):].strip()
            self.memory.remember("favorite_game", value)
            return f"I'll remember that your favorite game is {value}."

        if lower_text.startswith("my favorite food is "):
            value = text[len("my favorite food is "):].strip()
            self.memory.remember("favorite_food", value)
            return f"I'll remember that your favorite food is {value}."

        # ----- memory recall -----
        if ("what is my name" in lower_text
                or "what's my name" in lower_text
                or "whats my name" in lower_text):
            value = self.memory.recall("name")
            return f"Your name is {value}." if value else \
                "You haven't told me your name yet."

        if "where do i live" in lower_text:
            value = self.memory.recall("location")
            return f"You live in {value}." if value else \
                "You haven't told me where you live yet."

        if "what is my favorite color" in lower_text or \
                "what's my favorite color" in lower_text:
            value = self.memory.recall("favorite_color")
            return f"Your favorite color is {value}." if value else \
                "You haven't told me your favorite color yet."

        if "what is my favorite game" in lower_text or \
                "what's my favorite game" in lower_text:
            value = self.memory.recall("favorite_game")
            return f"Your favorite game is {value}." if value else \
                "You haven't told me your favorite game yet."

        if "what is my favorite food" in lower_text:
            value = self.memory.recall("favorite_food")
            return f"Your favorite food is {value}." if value else \
                "You haven't told me your favorite food yet."

        # ----- show all memory -----
        if ("what do you remember" in lower_text
                or "show my memories" in lower_text
                or "show my memory" in lower_text):
            memories = self.memory.all_memory()
            if not memories:
                return "I don't have anything stored yet."
            bits = []
            if "name" in memories:
                bits.append(f"your name is {memories['name']}")
            if "location" in memories:
                bits.append(f"you live in {memories['location']}")
            if "favorite_color" in memories:
                bits.append(
                    f"your favorite color is {memories['favorite_color']}"
                )
            if "favorite_game" in memories:
                bits.append(
                    f"your favorite game is {memories['favorite_game']}"
                )
            if "favorite_food" in memories:
                bits.append(
                    f"your favorite food is {memories['favorite_food']}"
                )
            return "I remember that " + ", ".join(bits) + "."

        # ----- general memory -----
        if lower_text.startswith("remember "):
            memory_text = text[9:].strip()
            if not memory_text:
                return "What would you like me to remember?"
            key = f"memory_{len(self.memory.all_memory()) + 1}"
            self.memory.remember(key, memory_text)
            return f"I'll remember that: {memory_text}"

        # ----- fallback -----
        if self.current_language != LANG_ENGLISH:
            return (
                f"Got it: {text}. "
                "(Add an OpenRouter API key in settings for real AI replies.)"
            )
        return f"I received your request: {text}"


# ================================================================
# TEST
# ================================================================

if __name__ == "__main__":

    brain = AVIBrain()
    print("LLM configured:", brain.has_llm)
    print()
    samples = [
        "hello",
        "who made you",
        "search the web for India cricket",
        "my name is Arnav",
        "what is my name",
        "exit",
    ]
    for s in samples:
        print(f"You: {s}")
        print(f"A.V.I.: {brain.respond(s)}")
        print()
