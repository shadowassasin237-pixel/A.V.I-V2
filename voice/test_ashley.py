"""
A.V.I. Ashley TTS test.

Run from the project root after filling .env:
    python voice/test_ashley.py

This starts the same LiveKit agent used by app.py, waits for the
Ashley/Inworld readiness handshake, and sends one test sentence.
"""
from __future__ import annotations

import time

from voice.agent_launcher import AVIAgentLauncher
from voice.speaker import AVISpeaker


def main():
    launcher = AVIAgentLauncher()
    speaker = AVISpeaker()

    try:
        if not launcher.start():
            raise SystemExit("LiveKit agent failed to start. Read the agent console.")

        print("Waiting for Ashley TTS...")
        if not speaker.wait_until_ready(timeout=60):
            status = speaker.get_status()
            raise SystemExit(
                "Ashley TTS did not become ready.\n"
                f"Status: {status}\n"
                "Check .env and the LiveKit agent console."
            )

        print("Ashley TTS is READY.")
        speaker.speak(
            "Hello Arnav. This is A.V.I. speaking with the Ashley voice. "
            "Your natural voice system is operational."
        )
        time.sleep(8)

    finally:
        speaker.close()
        launcher.stop()


if __name__ == "__main__":
    main()
