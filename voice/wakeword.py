"""
A.V.I. Wake Word
Detects common spoken variations of A.V.I.
"""


class AVIWakeWord:

    def __init__(self):
        self.wake_words = {
            "avi",
            "a v i",
            "a.v.i",
            "hey avi",
            "hey a v i",
            "hey a.v.i",
        }

    def is_wake_word(self, text: str) -> bool:
        if not text:
            return False

        cleaned = text.lower().strip()

        # Exact matches
        if cleaned in self.wake_words:
            return True

        # Remove punctuation
        normalized = (
            cleaned
            .replace(".", "")
            .replace(",", "")
            .replace("!", "")
            .replace("?", "")
        )

        if normalized in {
            "avi",
            "a v i",
            "hey avi",
            "hey a v i",
        }:
            return True

        return False


if __name__ == "__main__":

    wake_word = AVIWakeWord()

    print("A.V.I. Wake Word Test")
    print("-" * 30)

    while True:

        text = input("You: ")

        if text.lower() in {"exit", "quit"}:
            break

        if wake_word.is_wake_word(text):
            print("A.V.I.: Wake word detected!")
        else:
            print("A.V.I.: Waiting...")