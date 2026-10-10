"""
A.V.I. Gemini Live Voice
Real-time, bidirectional microphone + native Gemini audio.

Input: 16 kHz, mono, signed 16-bit PCM.
Output: 24 kHz, mono, signed 16-bit PCM.

The Live API handles VAD, natural interruption, multilingual speech,
audio-to-audio responses, transcription, Google Search grounding, and
A.V.I. function calling.
"""

import asyncio
import json
import threading
import time

try:
    import pyaudio
except ImportError:
    pyaudio = None

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None

from core.internet import (
    web_search, get_weather, read_webpage, get_news, get_current_time
)


class GeminiLiveVoice:
    def __init__(
        self,
        api_key: str,
        model: str = "gemini-3.8-live",
        voice: str = "Kore",
        system_instruction: str = "",
        memory=None,
        on_input_text=None,
        on_output_text=None,
        on_state=None,
        on_error=None,
    ):
        self.api_key = (api_key or "").strip()
        self.model = model
        self.voice = voice
        self.system_instruction = system_instruction
        self.memory = memory

        self.on_input_text = on_input_text
        self.on_output_text = on_output_text
        self.on_state = on_state
        self.on_error = on_error

        self.running = False
        self.stop_event = threading.Event()
        self.thread = None

        self._client = None
        self._session = None

    @property
    def available(self):
        return bool(self.api_key and genai is not None and pyaudio is not None)

    def start(self):
        if self.running:
            return
        if not self.available:
            self._error(
                "Gemini Live needs a Gemini API key, google-genai, and PyAudio."
            )
            return

        self.stop_event.clear()
        self.running = True
        self.thread = threading.Thread(
            target=self._thread_main,
            daemon=True,
            name="AVI-Gemini-Live"
        )
        self.thread.start()
        self._state("listening")

    def stop(self):
        self.stop_event.set()
        self.running = False
        self._state("idle")

    def _thread_main(self):
        try:
            asyncio.run(self._run())
        except Exception as error:
            self.running = False
            self._error(str(error))
            self._state("idle")

    async def _run(self):
        self._client = genai.Client(api_key=self.api_key)

        # Live API supports Google Search and client-side function calling.
        tools = [
            {"google_search": {}},
            {
                "function_declarations": [
                    {
                        "name": "web_search",
                        "description": "Search the web for current information.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "query": {"type": "string"},
                                "max_results": {"type": "integer"},
                            },
                            "required": ["query"],
                        },
                    },
                    {
                        "name": "get_weather",
                        "description": "Get current weather for a city.",
                        "parameters": {
                            "type": "object",
                            "properties": {"city": {"type": "string"}},
                            "required": [],
                        },
                    },
                    {
                        "name": "read_webpage",
                        "description": "Read useful text from a URL.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "url": {"type": "string"},
                                "max_chars": {"type": "integer"},
                            },
                            "required": ["url"],
                        },
                    },
                    {
                        "name": "get_news",
                        "description": "Get current news headlines.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "topic": {"type": "string"},
                                "max_items": {"type": "integer"},
                            },
                            "required": [],
                        },
                    },
                    {
                        "name": "get_current_time",
                        "description": "Get the current local date and time.",
                        "parameters": {
                            "type": "object",
                            "properties": {"timezone": {"type": "string"}},
                            "required": [],
                        },
                    },
                    {
                        "name": "remember",
                        "description": "Save a fact to A.V.I.'s persistent local memory.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "key": {"type": "string"},
                                "value": {"type": "string"},
                            },
                            "required": ["key", "value"],
                        },
                    },
                    {
                        "name": "recall",
                        "description": "Recall a fact from A.V.I.'s persistent local memory.",
                        "parameters": {
                            "type": "object",
                            "properties": {"key": {"type": "string"}},
                            "required": ["key"],
                        },
                    },
                    {
                        "name": "all_memory",
                        "description": "Read all A.V.I. persistent memory.",
                        "parameters": {
                            "type": "object",
                            "properties": {},
                        },
                    },
                ]
            },
        ]

        config = {
            "response_modalities": ["AUDIO"],
            "input_audio_transcription": {},
            "output_audio_transcription": {},
            "tools": tools,
            "speech_config": {
                "voice_config": {
                    "prebuilt_voice_config": {
                        "voice_name": self.voice
                    }
                }
            },
        }

        if self.system_instruction:
            config["system_instruction"] = self.system_instruction

        audio = pyaudio.PyAudio()
        input_stream = None
        output_stream = None

        try:
            input_stream = audio.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=16000,
                input=True,
                frames_per_buffer=1024,
            )
            output_stream = audio.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=24000,
                output=True,
                frames_per_buffer=1024,
            )

            async with self._client.aio.live.connect(
                model=self.model,
                config=config
            ) as session:
                self._session = session
                self._state("listening")

                sender = asyncio.create_task(
                    self._send_microphone(session, input_stream)
                )
                receiver = asyncio.create_task(
                    self._receive(session, output_stream)
                )

                done, pending = await asyncio.wait(
                    [sender, receiver],
                    return_when=asyncio.FIRST_COMPLETED,
                )

                # If the user clicked STOP, the sender has ended after
                # audio_stream_end. Keep receiving briefly so Gemini can
                # finish its final spoken response.
                if sender in done and receiver in pending:
                    try:
                        await asyncio.wait_for(receiver, timeout=3.0)
                    except (asyncio.TimeoutError, asyncio.CancelledError):
                        receiver.cancel()
                else:
                    for task in pending:
                        task.cancel()

                for task in done:
                    try:
                        task.result()
                    except asyncio.CancelledError:
                        pass

        finally:
            self._session = None
            try:
                if input_stream:
                    input_stream.stop_stream()
                    input_stream.close()
            except Exception:
                pass
            try:
                if output_stream:
                    output_stream.stop_stream()
                    output_stream.close()
            except Exception:
                pass
            audio.terminate()
            self.running = False
            self._state("idle")

    async def _send_microphone(self, session, stream):
        while not self.stop_event.is_set():
            try:
                chunk = await asyncio.to_thread(
                    stream.read,
                    1024,
                    exception_on_overflow=False,
                )
                if not chunk:
                    continue
                await session.send_realtime_input(
                    audio=types.Blob(
                        data=chunk,
                        mime_type="audio/pcm;rate=16000",
                    )
                )
            except asyncio.CancelledError:
                return
            except Exception as error:
                self._error(f"Microphone error: {error}")
                return

        try:
            await session.send_realtime_input(audio_stream_end=True)
        except Exception:
            pass

    async def _receive(self, session, output_stream):
        input_buffer = []
        output_buffer = []

        try:
            async for response in session.receive():
                # Fatal API/session errors can arrive as a response object.
                # Report them once and stop the session instead of producing
                # the same 1007/1011 message over and over.
                response_error = getattr(response, "error", None)
                if response_error:
                    self._error(str(response_error))
                    self.stop_event.set()
                    break

                server = getattr(response, "server_content", None)
                if server:
                    input_tx = getattr(server, "input_transcription", None)
                    if input_tx and getattr(input_tx, "text", None):
                        input_buffer.append(input_tx.text)

                    output_tx = getattr(server, "output_transcription", None)
                    if output_tx and getattr(output_tx, "text", None):
                        output_buffer.append(output_tx.text)

                    model_turn = getattr(server, "model_turn", None)
                    if model_turn:
                        for part in getattr(model_turn, "parts", []) or []:
                            inline = getattr(part, "inline_data", None)
                            if inline and getattr(inline, "data", None):
                                try:
                                    output_stream.write(inline.data)
                                    self._state("speaking")
                                except Exception as error:
                                    self._error(f"Audio playback error: {error}")

                    if getattr(server, "turn_complete", False):
                        if input_buffer:
                            self._input_text("".join(input_buffer).strip())
                            input_buffer.clear()
                        if output_buffer:
                            self._output_text("".join(output_buffer).strip())
                            output_buffer.clear()
                        self._state("listening")

                tool_call = getattr(response, "tool_call", None)
                if tool_call:
                    await self._handle_tool_call(session, tool_call)

        except asyncio.CancelledError:
            return
        except Exception as error:
            self.stop_event.set()
            self._error(str(error))

    async def _handle_tool_call(self, session, tool_call):
        responses = []

        for call in getattr(tool_call, "function_calls", []) or []:
            name = getattr(call, "name", "")
            args = getattr(call, "args", {}) or {}
            result = self._run_local_function(name, args)

            responses.append(
                types.FunctionResponse(
                    id=getattr(call, "id", None),
                    name=name,
                    response={"result": result},
                )
            )

        if responses:
            await session.send_tool_response(function_responses=responses)

    def _run_local_function(self, name, args):
        args = args or {}

        if name == "web_search":
            return web_search(
                str(args.get("query", "")),
                int(args.get("max_results", 5)),
            )

        if name == "get_weather":
            return get_weather(str(args.get("city", "")))

        if name == "read_webpage":
            return read_webpage(
                str(args.get("url", "")),
                int(args.get("max_chars", 6000)),
            )

        if name == "get_news":
            return get_news(
                str(args.get("topic", "")),
                int(args.get("max_items", 5)),
            )

        if name == "get_current_time":
            return get_current_time(str(args.get("timezone", "local")))

        if name == "remember":
            if not self.memory:
                return "Memory is unavailable."
            key = str(args.get("key", "")).strip()
            value = str(args.get("value", "")).strip()
            if not key:
                return "Memory key is empty."
            self.memory.remember(key, value)
            return {"saved": True, "key": key, "value": value}

        if name == "recall":
            if not self.memory:
                return "Memory is unavailable."
            key = str(args.get("key", "")).strip()
            return {"key": key, "value": self.memory.recall(key)}

        if name == "all_memory":
            if not self.memory:
                return "Memory is unavailable."
            return self.memory.all_memory()

        return {"error": f"Unknown function: {name}"}

    def _input_text(self, text):
        if callable(self.on_input_text):
            self.on_input_text(text)

    def _output_text(self, text):
        if callable(self.on_output_text):
            self.on_output_text(text)

    def _state(self, state):
        if callable(self.on_state):
            self.on_state(state)

    def _error(self, error):
        if callable(self.on_error):
            self.on_error(error)
