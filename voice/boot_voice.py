"""
A.V.I. Boot Voice
-----------------

Uses the SAME AVISpeaker instance as the main application.

Natural Inworld Priya voice (Indian English).
"""

from voice.speaker import AVISpeaker


def play_boot_voice(speaker=None):

    own_speaker = False

    # If no speaker was supplied, create one temporarily.
    if speaker is None:
        speaker = AVISpeaker()
        own_speaker = True

    boot_lines = [
        "A.V.I. online. All systems operational.",
        "I was created by Arnav Kumar.",
        "Awaiting your command.",
    ]
    for line in boot_lines:

        speaker.speak(line)

    # Only shut it down if we created it here.
    if own_speaker:

        speaker.close()