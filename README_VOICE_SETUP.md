# A.V.I. — Natural Ashley TTS setup

This build uses **Inworld TTS 2 — Ashley** through **LiveKit Inference**.

There is deliberately **no pyttsx3 / Windows SAPI voice** in the normal
A.V.I. speech path.

## One-time setup

1. Open `.env`.
2. Set your OpenRouter key:
   `OPENROUTER_API_KEY=...`
3. Set the LiveKit values:
   `LIVEKIT_URL=wss://...`
   `LIVEKIT_API_KEY=...`
   `LIVEKIT_API_SECRET=...`
4. Keep:
   `LIVEKIT_ROOM=avi-room`
   `LIVEKIT_AGENT_NAME=avi`

The `.env.example` file is a clean template.

## Start A.V.I.

From the project root:

```powershell
python app.py
```

`app.py` automatically starts the LiveKit agent and the desktop LiveKit
audio client.

## Test Ashley without opening the GUI

```powershell
python voice/test_ashley.py
```

The test waits for the agent to announce:

`Ashley TTS is READY`

and then sends a sentence through the exact same speech path used by the GUI.

## Voice architecture

GUI reply
-> `AVISpeaker`
-> LiveKit data packet (`avi.speak`)
-> LiveKit AgentSession
-> `inworld/inworld-tts-2`
-> `Ashley`
-> LiveKit audio track
-> desktop `sounddevice` playback

The desktop process never instantiates the Inworld plugin itself. This is
intentional: the TTS plugin must run inside the LiveKit agent job context.

## If A.V.I. says it has no TTS

Look at the console. This build reports the actual failure, such as:

- missing `LIVEKIT_URL`
- missing `LIVEKIT_API_KEY`
- missing `LIVEKIT_API_SECRET`
- LiveKit connection failure
- LiveKit agent failure
- speaker/audio-device failure

Do not add pyttsx3 to fix this. The intended voice is Ashley.

## Security

Never commit `.env` or publish your API keys. If a key has ever been exposed,
rotate it before using it again.
