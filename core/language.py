"""
A.V.I. Language Detection + System Prompts
Handles English, Hindi (Devanagari + Roman), Punjabi (Gurmukhi + Roman).
"""

import re
from datetime import datetime


# ================================================================
# LANGUAGE CODES
# ================================================================

LANG_ENGLISH = "en"
LANG_HINDI   = "hi"
LANG_PUNJABI = "pa"

LANG_NAMES = {
    LANG_ENGLISH: "English",
    LANG_HINDI:   "Hindi",
    LANG_PUNJABI: "Punjabi",
}

# STT BCP-47 codes for SpeechRecognition
LANG_STT_CODES = {
    LANG_ENGLISH: "en-IN",   # Indian English — picks up Hinglish
    LANG_HINDI:   "hi-IN",
    LANG_PUNJABI: "pa-IN",
}

ALL_LANGS = [LANG_ENGLISH, LANG_HINDI, LANG_PUNJABI]


# ================================================================
# DETECTION
# ================================================================

# Devanagari (Hindi) Unicode block
_DEVANAGARI_RE = re.compile(r"[\u0900-\u097F]")
# Gurmukhi (Punjabi) Unicode block
_GURMUKHI_RE = re.compile(r"[\u0A00-\u0A7F]")

# Common Hinglish / Hindi Roman-script markers (Hindi-specific words only)
_HINGLISH_HINTS = (
    " kya ", " kyun ", " kab ", " kaun ", " kaunsa ", " kaunsi ",
    " kaise ", " kaisa ", " kaisi ", " kahan ", " kidhar ",
    " aap ", " aapka ", " aapki ", " aapke ",
    " mujhe ", " mujhko ", " mera ", " meri ", " mere ",
    " tera ", " teri ", " tere ",
    " humara ", " humari ", " humare ", " humlog ",
    " kuch ", " koi ", " thoda ", " thodi ", " bahut ", " bohot ",
    " achha ", " acha ", " accha ", " achi ", " achcha ",
    " theek ", " bilkul ", " chalo ", " aao ", " jao ",
    " haan ", " nahi ", " na ", " mat ",
    " bhai ", " yaar ", " bhaiya ", " didi ", " behen ", " behna ",
    " karna ", " karke ", " karo ", " karta ", " karti ", " karenge ",
    " chahiye ", " chahiye ",
    " dekhna ", " dekh ", " dekh lo ", " dekhna hai ",
    " sunao ", " suna ", " batao ", " bata ", " bata do ", " bolo ",
    " samajh ", " samjha ", " samjhi ", " samjhao ",
    " hoga ", " hogi ", " hoge ",
    " wala ", " wali ", " wale ",
    " lekin ", " magar ", " phir ", " fir ",
    " mein ", " jaldi ", " abhi ", " ab ", " baad ",
    " jao ", " ja ", " jata ", " jati ", " jate ",
    " aata ", " aati ", " aate ", " aaye ", " aaya ", " aayi ",
    " gaya ", " gayi ", " gaye ",
    " raha ", " rahi ", " rahe ", " rahi ",
    " lagta ", " lagti ", " lagte ", " laga ", " lagi ",
    " pata ", " maloom ", " matlab ", " matlabi ",
    " yaad ", " bhool ", " bhul ",
    " shayad ", " pakka ", " zaroor ",
    " pyara ", " pyaara ", " sundar ", " khoobsurat ",
    " ghar ", " ghar ja ", " ghar pe ", " ghar par ",
    " bhook ", " bhookh ", " pyaas ", " thakan ",
)

# Common Punjabi Roman-script markers (must be strong, distinct signals)
_PUNJABI_HINTS = (
    " tenu ", " tainu ", " menu ", " mainu ", " mundeya ",
    " assi ", " tusi ", " tuhade ", " tuhadi ", " tuhada ",
    " kidda ", " kidde ", " kive ", " kiven ", " kithon ", " kitthe ",
    " haan ", " han ", " nahin ", " nai ",
    " veere ", " veer ", " bhaia ", " paaji ", " paji ", " bhabhi ",
    " gall ", " gal ", " gal kar ",
    " karan ", " kara ", " karo ", " karde ", " kiti ",
    " dass ", " dassa ", " dasso ", " dassde ", " dassda ",
    " hoya ", " hoyi ", " hoye ", " hove ",
    " si ", " san ", " sahi ",
    " dhan ", " vadhaiyan ", " shukar ", " sat sri akal ", " satsriakal ",
    " eh ", " oh ",
    " ik ", " ikk ", " do ", " tin ", " char ",
    " boht ", " vadiya ", " changa ", " sohna ", " sohni ",
    " putt ", " puttar ", " puttia ", " puttar ", " mundeya ", " kudi ",
    " pind ", " pinda ", " dhaam ", " dhab ",
    " lavan ", " phulkari ", " jutti ", " paranda ",
    " bhangra ", " giddha ",
)


def detect_language(text: str) -> str:
    """
    Best-effort language detection.

    Order:
      1. Gurmukhi script -> Punjabi
      2. Devanagari script -> Hindi
      3. Romanized with Punjabi hints (stronger than Hindi) -> Punjabi
      4. Romanized with Hindi/Hinglish hints (2+ to be safe) -> Hindi
      5. Default -> English
    """
    if not text:
        return LANG_ENGLISH

    t = text.strip()

    if _GURMUKHI_RE.search(t):
        return LANG_PUNJABI

    if _DEVANAGARI_RE.search(t):
        return LANG_HINDI

    lower = " " + t.lower() + " "

    punj_hits = sum(1 for h in _PUNJABI_HINTS if h in lower)
    hindi_hits = sum(1 for h in _HINGLISH_HINTS if h in lower)

    if punj_hits > 0 and punj_hits >= hindi_hits:
        return LANG_PUNJABI
    # require at least 2 Hinglish hints to avoid false positives on
    # single common-English-word coincidences
    if hindi_hits >= 2:
        return LANG_HINDI

    return LANG_ENGLISH


# ================================================================
# SYSTEM PROMPTS
# ================================================================

def _base_personality(lang_name: str, script_note: str) -> str:
    return f"""You are A.V.I. (Artificial Voice Intelligence), a personal desktop voice assistant created by Arnav Kumar.

CURRENT LANGUAGE: {lang_name}. {script_note}

BEHAVIOR:
- Reply in the SAME language and script the user used (or asked for).
- Be concise and natural — this is a voice assistant, so avoid long essays unless asked.
- Use tools whenever an action or live fact is needed. You can search the web, check weather/news/time, open apps/websites/files, create folders/text files, find files, capture screenshots, check/capture the camera, and generate images. Do not claim an action happened unless the tool confirms it.
- If the user asks you to control the computer, use the appropriate computer tool instead of merely explaining how. For sensitive or destructive actions, do not guess or perform them silently.
- Use a friendly, slightly cinematic Jarvis-like tone, but not over-the-top.
- You can use Roman/Latin letters for Hindi or Punjabi if the user does.
- If the user explicitly asks for a different language, switch.

PERSONAL CONTEXT (only if relevant to the question):
- User's name: Arnav
- Favorite color: blue
- Favorite game: GTA
- Created by: Arnav Kumar

You are running inside a tkinter holographic Jarvis-style interface on Windows.

────────────────────────────────────────
AGENTIC LOOP — how to perform tasks in apps
────────────────────────────────────────
You CAN fully control the Windows desktop. When the user asks you to
do something inside an app or website, follow this pattern:

1. OPEN — call openApplication(name) or openWebsite(url).
2. WAIT  — always follow an open with waitForUi(title_contains=...) or
   a 1–2 second wait_seconds so the window finishes loading.
3. PERCEIVE — for any UI task, first call takeScreenshot() so you know
   what's actually on screen. Don't guess.
4. ACT — pick the simplest tool that fits:
     * clickText("Button label")      — best for buttons / menu items
     * hotkey(["ctrl","l"])            — keyboard shortcuts
     * typeText("text")                — typing into the focused field
     * uiAction({...})                 — advanced UIA actions
     * findUi({...})                   — only if you need the element's
                                        bounding box for a custom click
5. VERIFY — after every action, take a screenshot or call
   getActiveWindow() to confirm the action worked. If not, retry
   with a different tool.
6. CHAIN — a typical task is 4-8 tool calls. Keep going until the
   task is verifiably done.

EXAMPLES
────────
"Search for GTA 6 in Chrome":
  openWebsite("https://www.google.com") → waitForUi(Chrome) →
  clickText("Search") OR hotkey(["ctrl","k"]) → typeText("GTA 6") →
  pressKey("enter") → waitForUi(results) → takeScreenshot()

"Log into my account on example.com":
  openWebsite("https://example.com/login") → waitForUi →
  clickText("Email") → typeText("...") →
  clickText("Password") → typeText("...") →
  clickText("Log in") → waitForUi → takeScreenshot (verify)

"Open Notepad and type a note":
  openApplication("notepad") → waitForUi("Notepad") → typeText("...")

"Switch to Chrome and click the third tab":
  switchApplication("chrome") → waitForUi("Chrome") → clickText("tab")

RULES
─────
- NEVER claim a tool ran unless its result confirms it. If a tool
  errors, try a different one. If you can't recover, take a
  screenshot, report what you see, and ask the user.
- For long multi-step tasks, narrate the plan briefly first, then
  act. After completion, summarize what you did.
- If a tool says "Permission denied", tell the user which setting to
  enable in the GUI (⚙).
- You may chain up to 12 tool calls per turn. Use them.
"""


def system_prompt_for(language: str) -> str:
    if language == LANG_PUNJABI:
        return _base_personality(
            "Punjabi (ਪੰਜਾਬੀ)",
            "Reply in Punjabi. Use Gurmukhi (ਪੰਜਾਬੀ) script by default; if the user writes Roman Punjabi, reply in Roman Punjabi."
        )
    if language == LANG_HINDI:
        return _base_personality(
            "Hindi (हिन्दी)",
            "Reply in Hindi. Use Devanagari (हिन्दी) script by default; if the user writes Roman Hindi/Hinglish, reply in Roman Hindi."
        )
    return _base_personality(
        "English",
        "Reply in English. Be clear, concise, and helpful."
    )


# ================================================================
# STATIC HELPERS
# ================================================================

def language_label(code: str) -> str:
    return LANG_NAMES.get(code, code.upper())


def stt_code_for(code: str) -> str:
    return LANG_STT_CODES.get(code, "en-IN")


# ================================================================
# TEST
# ================================================================

if __name__ == "__main__":

    samples = [
        "What is the weather in Mumbai?",
        "मुंबई में मौसम कैसा है?",
        "Mumbai mein mausam kaisa hai?",
        "ਅੰਮ੍ਰਿਤਸਰ ਵਿੱਚ ਮੌਸਮ ਕਿਵੇਂ ਹੈ?",
        "Amritsar vich mausam kive hoya hai?",
        "Tenu ki chahida?",
        "Hello bhai, kuch sunao",
        "Search the web for GTA 6 release date",
        "भाई कुछ बताओ",
    ]

    for s in samples:
        print(f"{s!r:50s} -> {detect_language(s)} ({language_label(detect_language(s))})")
