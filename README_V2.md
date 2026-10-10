# A.V.I. v2 — Desktop Intelligence Upgrade

A.V.I. now has a modular tool layer for Windows desktop actions, files,
screenshots, local camera checks/capture, and configurable image generation.

## Voice / echo fix

- No `pyttsx3` or Windows SAPI.
- Ashley is generated only inside the LiveKit agent.
- Desktop microphone is never published to LiveKit.
- While Ashley speaks, local microphone capture is paused.
- The agent publishes `avi.speech_start` / `avi.speech_end` so the desktop
  knows exactly when to pause/resume voice input.

## Computer control

Computer tools are opt-in. `.env` contains:

```env
AVI_ALLOW_COMPUTER_CONTROL=1
```

The tool layer intentionally does **not** execute arbitrary shell commands.
It supports controlled actions such as opening known applications, opening
paths/URLs, creating folders, finding files, listing folders, and screenshots.

## Camera

Camera support is local and currently provides availability checking and a
single-frame capture. Person identity recognition is intentionally not enabled
by default; the next vision phase can add explicit local enrollment.

## Image generation

Configure either an OpenAI-compatible image endpoint:

```env
AVI_IMAGE_API_URL=https://...
AVI_IMAGE_MODEL=gpt-image-1
OPENAI_API_KEY=...
```

or set `OPENAI_API_KEY` and install the `openai` package. The generated image
is saved under `generated/`.

## Start

```powershell
python app.py
```

The application starts its LiveKit worker automatically.
