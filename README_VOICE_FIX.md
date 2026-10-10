# A.V.I. corrected voice architecture

This version fixes the TTS problem caused by trying to run the LiveKit
Inworld TTS plugin directly from `python app.py`.

## Architecture

`python app.py` starts:

1. A.V.I. OpenRouter brain.
2. A LiveKit Agent worker as a child process.
3. A desktop LiveKit client.
4. GUI speech requests are sent over LiveKit data packets.
5. The LiveKit Agent receives the request and calls `AgentSession.say()`.
6. Inworld TTS 2 / Ashley runs inside the LiveKit Agent job.
7. Ashley audio is published back to the desktop and played through
   `sounddevice`.

Realtime microphone mode continues to use the same LiveKit Agent:
microphone -> STT -> OpenRouter -> Inworld Ashley.

## Required environment

Fill these in `.env`:

- `OPENROUTER_API_KEY`
- `LIVEKIT_URL`
- `LIVEKIT_API_KEY`
- `LIVEKIT_API_SECRET`

The Ashley voice uses LiveKit Inference, so an `INWORLD_API_KEY` is
not required for this path.

## Install

Inside the project virtual environment:

```powershell
pip install -r requirements.txt
```

## Run

```powershell
python app.py
```

You should see:

```text
A.V.I. Speaker: LiveKit voice bridge initialized.
A.V.I. Voice: Ashley
A.V.I. LiveKit voice agent started.
```

Then the boot lines are routed through the LiveKit agent and spoken by
Ashley.

## Important

Do not put `livekit.plugins.inworld.TTS(...)` in `voice/speaker.py`.
The Inworld TTS object belongs inside `voice/livekit_agent.py` so it is
created inside the LiveKit AgentSession/job context.

If credentials were ever exposed in a chat, ZIP, screenshot, or log,
rotate them before using the project again.
