"""
A.V.I. Listener
Converts microphone speech into text with auto language detection
(English, Hindi, Punjabi).
"""

import speech_recognition as sr

from core.language import (
    detect_language, stt_code_for, LANG_ENGLISH, language_label
)


class AVIListener:

    def __init__(self, default_language: str = LANG_ENGLISH, should_ignore=None):
        self.recognizer = sr.Recognizer()
        
        # Raised energy & pause thresholds to prevent speaker bleed
        self.recognizer.energy_threshold = 400
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.pause_threshold = 1.0
        self.recognizer.non_speaking_duration = 0.6
        
        self.default_language = default_language
        self.should_ignore = should_ignore
        # ordered list of BCP-47 codes to try for auto-detection
        self.language_attempts = ["en-IN", "hi-IN", "pa-IN"]

    def listen(self, language: str = None, auto_detect: bool = True):
        """
        Listen on the microphone and return (text, detected_language).
        Returns ("", language) on failure.
        """
        if self.should_ignore and self.should_ignore():
            return "", language or self.default_language

        with sr.Microphone() as source:

            self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
            print("🎤 Listening...")

            try:
                audio = self.recognizer.listen(
                    source,
                    timeout=None,
                    phrase_time_limit=8
                )
            except Exception as e:
                print(f"Listening error: {e}")
                return "", language or self.default_language

        # Double check ignore state after recording completes
        if self.should_ignore and self.should_ignore():
            return "", language or self.default_language

        # 1. If user pinned a language, use it directly
        if language and not auto_detect:
            text = self._recognize(audio, stt_code_for(language))
            return text, language

        # 2. Auto-detect: try in order
        first_text = ""
        first_lang = LANG_ENGLISH
        for code in self.language_attempts:
            text = self._recognize(audio, code)
            if text:
                lang = detect_language(text)
                if not first_text:
                    first_text = text
                    first_lang = lang
                if lang != LANG_ENGLISH:
                    return text, lang
        return first_text, first_lang

    def _recognize(self, audio, language_code: str) -> str:
        try:
            return self.recognizer.recognize_google(
                audio, language=language_code
            )
        except sr.UnknownValueError:
            return ""
        except sr.RequestError as error:
            print(f"A.V.I.: Speech service error: {error}")
            return ""