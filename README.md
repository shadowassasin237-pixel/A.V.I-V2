# A.V.I. — Artificial Voice Intelligence

A holographic desktop voice assistant built in Python with a **red Ultron-inspired command center GUI**, **Inworld TTS-2** voice (Indian English, voice: **Arjun**), **OpenRouter** LLM brain, and **LiveKit** real-time audio.

Built by **Arnav Kumar** as a school project.

---

## Features

- 🔴 **Red holographic GUI** — reactive central reactor, animated particles, energy arcs, scanlines, glitch FX, hexagonal grid
- 🗣️ **Natural Indian English voice** — Inworld TTS-2 via LiveKit (voice: Arjun)
- 🧠 **OpenRouter LLM brain** — any tool-calling model from openrouter.ai
- 👂 **Voice input** — SpeechRecognition with mic-pause-while-speaking
- 💬 **Chat panel** — real-time conversation log
- 🛠️ **Tool layer** — files, web search, screenshots, computer control (opt-in)
- 📷 **Local vision** — camera availability check + single-frame capture
- 🎨 **5 HUD modes** — reactor, clock, network, voice, mask

## Tech Stack

- **Python 3.13**
- **tkinter** (CustomTkinter-ready)
- **Inworld TTS-2** via **LiveKit** real-time audio
- **OpenRouter** for LLM (GPT-4o-mini default)
- **Deepgram Nova-3** for STT
- **Silero VAD** for voice activity detection

## Quick Start

```bash
# 1. Clone the repo
git clone https://github.com/<your-username>/A.V.I.git
cd A.V.I

# 2. Create a virtual environment
python -m venv venv

# 3. Activate the venv
#    Windows PowerShell:
.\venv\Scripts\Activate.ps1
#    Windows CMD:
venv\Scripts\activate.bat

# 4. Install dependencies
pip install -r requirements.txt

# 5. Configure your .env (copy .env.example)
copy .env.example .env
# Edit .env with your own OPENROUTER_API_KEY, LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET.

# 6. Launch
python app.py
```

Or just double-click `START_AVI.bat`.

> **Note:** `.env` is intentionally **not** committed to this repo. You need to
> supply your own OpenRouter + LiveKit credentials before the AI brain and voice
> will work. The repo ships with `.env.example` as a template.

## Project Structure

```
A.V.I/
├── app.py                  # Main entry point
├── config.py               # Centralized settings
├── core/                   # Brain, LLM, language, memory, internet
├── voice/                  # LiveKit client, speaker, listener, agent
├── ui/                     # Holographic GUI
├── tools/                  # Files, web, screenshot, computer, image gen
├── vision/                 # Local camera
├── data/                   # Memory persistence
├── logs/                   # Runtime logs
└── requirements.txt
```

## Environment Variables

See `.env.example` for the full list. Required:

- `OPENROUTER_API_KEY` — your OpenRouter key
- `LIVEKIT_URL` — your LiveKit server URL
- `LIVEKIT_API_KEY` / `LIVEKIT_API_SECRET` — LiveKit credentials

## License

Personal school project. © Arnav Kumar.
