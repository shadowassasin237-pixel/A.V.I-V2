"""
A.V.I. Speaker
--------------
Desktop bridge to the LiveKit/Inworld voice agent.

No Windows SAPI, pyttsx3, or local robotic TTS is used.

The active TTS voice id is stored in `self.voice`.  When the user picks
a new voice from the settings dialog, the GUI restarts the LiveKit
agent subprocess so the new voice id is picked up on the next speak.
"""

from __future__ import annotations

import os

from voice.livekit_client import AVILiveKitClient

# Pull the canonical default from config so all paths agree
try:
    from config import AVI_VOICE as _DEFAULT_VOICE
except Exception:
    _DEFAULT_VOICE = "Arjun"


class AVISpeaker:
    def __init__(
        self,
        rate: int = 175,
        volume: float = 1.0,
        language: str = "en",
        client: AVILiveKitClient | None = None,
        voice: str = "",
    ):
        self.rate = rate
        self.volume = volume
        self.language = language
        self.voice_provider = "Inworld via LiveKit"
        self.voice = (voice or _DEFAULT_VOICE or "Arjun").strip() or "Arjun"
        self.enabled = True
        self.client = client or AVILiveKitClient()
        self._started = False
        self._speaking = False

        print("A.V.I. Speaker: Inworld TTS bridge initialized.")
        print(f"A.V.I. Voice: {self.voice}")
        print("A.V.I. TTS: inworld/inworld-tts-2")

    def start(self):
        if not self._started:
            self.client.start()
            self._started = True

    @property
    def is_speaking(self) -> bool:
        return self._speaking or bool(getattr(self.client, "speaking", False))

    def set_language(self, language: str):
        if language:
            self.language = language

    def set_enabled(self, enabled: bool):
        self.enabled = bool(enabled)
        if not self.enabled:
            self.stop()

    def set_voice(self, voice: str):
        """Switch the active TTS voice id.

        The LiveKit agent reads ``AVI_VOICE`` from the environment when
        it boots, so callers must also restart the agent subprocess for
        the new voice to take effect.  The GUI settings dialog does that
        automatically when saving.
        """
        voice = (voice or "").strip()
        if not voice:
            return
        self.voice = voice
        # Push the new value into the environment so the next
        # ``AVIAgentLauncher.start()`` will see it.
        os.environ["AVI_VOICE"] = voice
        try:
            import config
            config.AVI_VOICE = voice
        except Exception:
            pass
        print(f"A.V.I. Voice switched to: {voice}")

    def wait_until_ready(self, timeout: float = 45.0) -> bool:
        self.start()
        return self.client.wait_until_ready(timeout=timeout)

    def speak(self, text: str, language: str | None = None):
        if not self.enabled:
            return False

        text = str(text or "").strip()
        if not text:
            return False

        if language:
            self.language = language

        print(f"A.V.I.: {text}")

        if not self.wait_until_ready():
            reason = getattr(self.client, "last_error", "")
            print(
                "A.V.I. Voice Error: TTS is not ready."
                + (f" {reason}" if reason else "")
            )
            return False

        self._speaking = True
        ok = bool(self.client.speak(text, wait_for_ready=False))
        if not ok:
            self._speaking = False
        return ok

    async def speak_async(self, text: str, language: str | None = None):
        return self.speak(text, language)

    def stop(self):
        try:
            self.client.stop()
        except Exception as exc:
            print(f"A.V.I. Voice stop error: {exc}")
        self._started = False
        self._speaking = False

    def close(self):
        self.stop()
        print("A.V.I. Speaker: Shutdown complete.")

    def get_status(self):
        return {
            "enabled": self.enabled,
            "language": self.language,
            "voice_provider": self.voice_provider,
            "voice": self.voice,
            "tts_model": "inworld/inworld-tts-2",
            "local_tts": False,
            "pyttsx3": False,
            "livekit_connected": bool(self.client.connected),
            "tts_ready": bool(self.client.ready),
            "last_error": getattr(self.client, "last_error", ""),
        }


if __name__ == "__main__":
    speaker = AVISpeaker()
    try:
        speaker.speak(
            "Hello Arnav. A.V.I. is online. "
            "Voice communication is operational."
        )
    finally:
        speaker.close()
