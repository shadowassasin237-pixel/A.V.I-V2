"""
A.V.I. LiveKit Voice Agent (Dedicated TTS Engine)
-------------------------------------------------
This worker runs strictly as a dedicated Inworld TTS renderer.
It waits for the desktop GUI to send text on topic `avi.speak`,
and speaks that exact text via Inworld TTS.

It does NOT run local STT or LLM to prevent double-replies.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os

from dotenv import load_dotenv
from livekit import rtc
from livekit.agents import Agent, AgentServer, AgentSession, JobContext, cli, inference

load_dotenv()

LIVEKIT_AGENT_NAME = os.getenv("LIVEKIT_AGENT_NAME", "avi")
AVI_VOICE = os.getenv("AVI_VOICE", "Arjun").strip() or "Arjun"
AVI_TTS_LANGUAGE = os.getenv("AVI_LANGUAGE", "en-IN").strip() or "en-IN"

logger = logging.getLogger("avi-livekit")
logger.setLevel(logging.INFO)

server = AgentServer()


@server.rtc_session(agent_name=LIVEKIT_AGENT_NAME)
async def avi_voice_session(ctx: JobContext):
    logger.info("A.V.I. TTS voice worker started for room %s", ctx.room.name)

    # Lock to queue speech requests linearly
    speech_lock = asyncio.Lock()

    # Dedicated TTS-only session (STT and LLM omitted so the agent doesn't talk on its own)
    session = AgentSession(
        tts=inference.TTS(
            model="inworld/inworld-tts-2",
            voice=AVI_VOICE,
            language=AVI_TTS_LANGUAGE,
        )
    )

    await session.start(room=ctx.room)
    await ctx.connect()

    async def publish_ready():
        payload = json.dumps({
            "status": "ready",
            "voice": AVI_VOICE,
            "tts": "inworld/inworld-tts-2",
        }).encode("utf-8")
        try:
            await ctx.room.local_participant.publish_data(
                payload,
                reliable=True,
                topic="avi.ready",
            )
            logger.info("A.V.I. Priya TTS is READY.")
        except Exception:
            logger.exception("Could not publish avi.ready.")

    @ctx.room.on("data_received")
    def on_data_received(packet: rtc.DataPacket):
        if packet.topic == "avi.hello":
            asyncio.create_task(publish_ready())
            return

        if packet.topic != "avi.speak":
            return

        try:
            payload = json.loads(packet.data.decode("utf-8"))
            text = str(payload.get("text", "")).strip()
        except (UnicodeDecodeError, json.JSONDecodeError, AttributeError):
            logger.warning("Invalid avi.speak packet received.")
            return

        if not text:
            return

        logger.info("Speech request from desktop GUI: %s", text)

        async def speak_and_signal():
            async with speech_lock:
                try:
                    await ctx.room.local_participant.publish_data(
                        b"{}", reliable=True, topic="avi.speech_start"
                    )
                    handle = session.say(
                        text,
                        allow_interruptions=True,
                        add_to_chat_ctx=False,
                    )
                    await handle.wait_for_playout()
                except asyncio.CancelledError:
                    raise
                except Exception:
                    logger.exception("TTS failed for speech request.")
                finally:
                    try:
                        await ctx.room.local_participant.publish_data(
                            b"{}", reliable=True, topic="avi.speech_end"
                        )
                    except Exception:
                        logger.exception("Could not publish avi.speech_end.")

        asyncio.create_task(speak_and_signal())

    await publish_ready()
    logger.info("A.V.I. voice system online. Dedicated TTS ready.")
    await asyncio.Event().wait()


if __name__ == "__main__":
    cli.run_app(server)