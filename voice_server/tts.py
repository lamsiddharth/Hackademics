"""
tts.py
------
Kokoro TTS WebSocket adapter (neosun100/kokoro-tts Docker image).

Kokoro's WS protocol:
  Send:    { "text": "...", "voice": "af_heart" }
  Receive: { "status": "chunk",    "audio": "<base64-encoded PCM bytes>" }
           { "status": "complete"                                         }
           { "status": "error",    "message": "..."                       }

We keep a single persistent WS connection per interview session.
For each LLM response, we:
  1. Send the full text as one JSON message.
  2. Receive audio chunks until we get {"status": "complete"}.
  3. Decode each base64 chunk and yield raw bytes back to pipeline.py,
     which forwards them to the browser over the main WebSocket.

Why not stream text tokens into Kokoro word-by-word?
  Kokoro doesn't support partial-text streaming in the Docker image —
  it expects complete sentences for natural prosody. Sending tokens
  individually produces robotic, choppy audio. We collect the full LLM
  response first, then send it to Kokoro in one shot.
  (This adds ~300-500ms extra latency vs streaming TTS, acceptable for
  interview pacing where the user expects a full question before replying.)
"""

import asyncio
import base64
import json
import websockets
from typing import AsyncIterator

from config import settings


class KokoroTTS:
    """
    Persistent Kokoro WS connection for one interview session.
    Call connect() before use, close() when session ends.
    """

    def __init__(self):
        self._ws = None

    async def connect(self) -> None:
        self._ws = await websockets.connect(
            settings.KOKORO_WS_URL,
            ping_interval=20,
            ping_timeout=30,
            max_size=10 * 1024 * 1024,  # 10 MB — Kokoro can send large audio frames
        )

    async def close(self) -> None:
        if self._ws:
            try:
                await self._ws.close()
            except Exception:
                pass
            self._ws = None

    async def synthesize(self, text: str) -> AsyncIterator[bytes]:
        """
        Send text to Kokoro, yield raw PCM audio bytes as chunks arrive.

        The browser expects raw PCM-16 at 24000 Hz (Kokoro's output rate).
        You'll need to handle playback format on the frontend accordingly.
        """
        if not self._ws:
            raise RuntimeError("KokoroTTS.connect() must be called first")

        # Send synthesis request
        await self._ws.send(json.dumps({
            "text": text,
            "voice": settings.KOKORO_VOICE,
        }))

        # Stream back audio chunks until complete
        async for raw in self._ws:
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue

            status = data.get("status")

            if status == "chunk":
                audio_b64 = data.get("audio", "")
                if audio_b64:
                    yield base64.b64decode(audio_b64)

            elif status == "complete":
                # This sentence is done — caller can request the next one
                return

            elif status == "error":
                print(f"[tts] Kokoro error: {data.get('message')}")
                return
