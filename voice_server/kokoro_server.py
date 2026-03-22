"""
kokoro_server.py
----------------
Standalone Kokoro TTS WebSocket server.
Exposes the same WS interface that tts.py expects.

Run:
    uvicorn kokoro_server:app --port 8300

Protocol:
  SEND:    {"text": "...", "voice": "af_heart"}
  RECEIVE: {"status": "chunk",    "audio": "<base64 PCM-16 bytes>"}
           {"status": "complete"}
           {"status": "error",    "message": "..."}

Audio output: raw PCM-16, 24000 Hz, mono — matches what tts.py decodes.
"""

import asyncio
import base64
import io
import json

import numpy as np
import soundfile as sf
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from kokoro import KPipeline


app = FastAPI(title="Kokoro TTS Server")

# Load model once at startup — stays in VRAM for the entire session
# lang_code="a" = American English
# Change to "b" for British English, "j" for Japanese, etc.
print("[kokoro] Loading Kokoro pipeline...")
_pipeline = KPipeline(lang_code="a")
print("[kokoro] Model ready.")


def _synthesize(text: str, voice: str) -> bytes:
    """
    Blocking synthesis — runs in a thread executor so it doesn't
    block the asyncio event loop.

    Returns raw PCM-16 bytes at 24000 Hz mono.
    """
    chunks = []
    for _, _, audio in _pipeline(text, voice=voice):
        chunks.append(audio)

    if not chunks:
        return b""

    audio_np = np.concatenate(chunks)

    buf = io.BytesIO()
    sf.write(buf, audio_np, 24000, format="RAW", subtype="PCM_16")
    return buf.getvalue()


@app.websocket("/ws/tts")
async def tts_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("[kokoro] client connected")

    loop = asyncio.get_event_loop()

    try:
        async for raw in websocket.iter_text():
            try:
                data  = json.loads(raw)
                text  = data.get("text", "").strip()
                voice = data.get("voice", "af_heart")
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({
                    "status": "error",
                    "message": "invalid JSON"
                }))
                continue

            if not text:
                await websocket.send_text(json.dumps({"status": "complete"}))
                continue

            try:
                # Run blocking synthesis off the event loop thread
                audio_bytes = await loop.run_in_executor(
                    None, _synthesize, text, voice
                )

                if audio_bytes:
                    b64 = base64.b64encode(audio_bytes).decode()
                    await websocket.send_text(json.dumps({
                        "status": "chunk",
                        "audio":  b64,
                    }))

                await websocket.send_text(json.dumps({"status": "complete"}))

            except Exception as e:
                print(f"[kokoro] synthesis error: {e}")
                await websocket.send_text(json.dumps({
                    "status":  "error",
                    "message": str(e),
                }))

    except WebSocketDisconnect:
        print("[kokoro] client disconnected")
    except Exception as e:
        print(f"[kokoro] unexpected error: {e}")


@app.get("/health")
async def health():
    return {"status": "ok"}
