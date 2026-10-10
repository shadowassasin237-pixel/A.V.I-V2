"""
A.V.I. - Artificial Voice Intelligence
Main Application Entry Point
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.resolve()

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config import (
    OPENROUTER_API_KEY,
    LLM_MODEL,
    LIVEKIT_URL,
    LIVEKIT_API_KEY,
    LIVEKIT_API_SECRET,
    AVI_VOICE,
)
from core.brain import AVIBrain
from voice.agent_launcher import AVIAgentLauncher
from voice.boot_voice import play_boot_voice
from voice.speaker import AVISpeaker
from ui.gui import AVIGUI, load_saved_config


def main():
    # Pull the most recent settings saved via the GUI dialog
    load_saved_config()

    # Re-import so any updates loaded above are visible
    from config import (
        OPENROUTER_API_KEY as _OR_KEY,
        LLM_MODEL as _OR_MODEL,
        LIVEKIT_URL as _LK_URL,
        LIVEKIT_API_KEY as _LK_KEY,
        LIVEKIT_API_SECRET as _LK_SECRET,
        AVI_VOICE as _AVI_VOICE,
    )

    print("=" * 60)
    print("A.V.I. - Artificial Voice Intelligence")
    print("=" * 60)
    print(f"  Project root : {PROJECT_ROOT}")
    print("  LLM provider : OpenRouter")
    print(f"  LLM model    : {_OR_MODEL or '(not set)'}")
    print(
        "  LLM key      : "
        f"{'(set)' if _OR_KEY else '(not set)'}"
    )
    print()
    print("  Voice provider : Inworld via LiveKit")
    print(f"  TTS voice      : {_AVI_VOICE}")
    print("  TTS model      : inworld/inworld-tts-2")
    print(
        "  LiveKit config : "
        + ("(set)" if all((_LK_URL, _LK_KEY, _LK_SECRET)) else "(INCOMPLETE)")
    )
    print()

    if not all((_LK_URL, _LK_KEY, _LK_SECRET)):
        print("A.V.I. ERROR: TTS cannot start because LiveKit credentials are missing.")
        print("Set LIVEKIT_URL, LIVEKIT_API_KEY and LIVEKIT_API_SECRET in .env,")
        print("or open the GUI settings (⚙) to enter them there.")
        print("The application will continue, but voice output will remain disabled.")
        print()

    brain = AVIBrain(
        api_key=_OR_KEY,
        model=_OR_MODEL,
    )

    # Start the LiveKit worker before the desktop room/client.
    # Make sure AVI_VOICE is in the environment so the agent process
    # boots with the voice the user picked in the GUI settings.
    import os
    os.environ.setdefault("AVI_VOICE", _AVI_VOICE or "Arjun")
    os.environ.setdefault("AVI_LLM_MODEL", _OR_MODEL or "")

    agent_launcher = AVIAgentLauncher()
    if not agent_launcher.start():
        print("A.V.I. WARNING: LiveKit agent did not start cleanly. Voice may be unavailable.")

    speaker = AVISpeaker(voice=_AVI_VOICE)

    try:
        # Wait for the real voice agent before any boot speech.
        # This avoids the startup race that previously dropped the intro.
        if speaker.wait_until_ready(timeout=45):
            play_boot_voice(speaker)
        else:
            print("A.V.I. WARNING: Voice agent was not ready in time; continuing without boot audio.")

        print()
        print("Starting graphical interface...")
        print()

        app = AVIGUI(
            brain=brain,
            speaker=speaker,
            agent_launcher=agent_launcher,
        )

        app.mainloop()

    except KeyboardInterrupt:
        print()
        print("A.V.I.: Shutdown requested.")

    finally:
        try:
            speaker.close()
        except Exception:
            pass

        agent_launcher.stop()


if __name__ == "__main__":
    main()
