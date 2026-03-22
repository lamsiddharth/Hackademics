"""
main.py
-------
FastAPI voice server. No auth for MVP.

WebSocket URL:
    ws://localhost:8001/interview?session_id=<uuid>&job_role=<role>&difficulty=<level>

Browser → Server text frames:
    "PING"           — keepalive
    "STOP_RECORDING" — user clicked stop, end this STT turn

Browser → Server binary frames:
    raw PCM-16 at 16000 Hz mono

Server → Browser text frames:
    "PONG"               — keepalive reply
    "TRANSCRIPT:<text>"  — live caption
    "END_OF_RESPONSE"    — interviewer done, mic can open
    "SESSION_END"        — interview complete

Server → Browser binary frames:
    raw PCM-16 audio at 24000 Hz (Kokoro output)
"""

import asyncio
import httpx
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query

from config import settings
from pipeline import run_pipeline


app = FastAPI(title="Hackedemics Voice Server")


async def _post_transcript_to_django(
    session_id: str,
    conversation: list[dict],
    prep_mode: str,
    profile: dict,
) -> None:
    payload = {
        "session_id": session_id,
        "conversation": conversation,
        "prep_mode": prep_mode,
        "profile": profile,
    }
    headers = {"X-Internal-Secret": settings.DJANGO_INTERNAL_SECRET}

    # Retry up to 3 times — Django callback is critical for saving the interview
    for attempt in range(1, 4):
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    settings.DJANGO_CALLBACK_URL,
                    json=payload,
                    headers=headers,
                    timeout=30.0,  # feedback generation can take time
                )
                if resp.status_code == 200:
                    print(f"[main] Django callback OK for session {session_id}")
                    return
                else:
                    print(f"[main] Django callback returned {resp.status_code} for {session_id}: {resp.text}")
        except Exception as e:
            print(f"[main] Django callback attempt {attempt}/3 failed for {session_id}: {e}")

        if attempt < 3:
            await asyncio.sleep(2 * attempt)  # backoff: 2s, 4s

    print(f"[main] Django callback FAILED after 3 attempts for session {session_id}")


@app.websocket("/interview")
async def interview_endpoint(
    websocket: WebSocket,
    session_id: str = Query(...),
    job_role:   str = Query(default="Software Engineer"),
    difficulty: str = Query(default="medium"),
    prep_mode:  str = Query(default="subjective"),
    target_role: str = Query(default=""),
    target_company: str = Query(default=""),
    tech_stack: str = Query(default=""),
    current_profile: str = Query(default=""),
):
    await websocket.accept()
    print(
        f"[main] {session_id} connected — {job_role} / {difficulty} / {prep_mode}"
    )

    audio_in_queue:  asyncio.Queue[bytes | None] = asyncio.Queue(maxsize=100)
    audio_out_queue: asyncio.Queue[bytes | None] = asyncio.Queue(maxsize=100)

    async def _receive_from_browser():
        try:
            while True:
                msg = await websocket.receive()

                if "bytes" in msg and msg["bytes"]:
                    # Raw PCM audio chunk — forward to STT
                    await audio_in_queue.put(msg["bytes"])

                elif "text" in msg:
                    text = msg["text"]
                    if text == "PING":
                        await websocket.send_text("PONG")
                    elif text == "STOP_RECORDING":
                        # User clicked stop — signal STT to close this turn
                        print("[main] STOP_RECORDING received")
                        await audio_in_queue.put(b"__STOP__")

        except WebSocketDisconnect:
            print(f"[main] {session_id} browser disconnected")
        except Exception as e:
            print(f"[main] receive error: {e}")
        finally:
            # Sentinel tells pipeline the session is truly over
            await audio_in_queue.put(None)

    async def _send_to_browser():
        while True:
            chunk = await audio_out_queue.get()

            if chunk is None:
                try:
                    await websocket.send_text("SESSION_END")
                    await websocket.close()
                except Exception:
                    pass
                return

            if chunk == b"__END_OF_RESPONSE__":
                try:
                    await websocket.send_text("END_OF_RESPONSE")
                except Exception:
                    return
            else:
                try:
                    await websocket.send_bytes(chunk)
                except Exception:
                    return

    async def _on_transcript(transcript: str):
        try:
            if transcript.startswith("__ASSISTANT__:"):
                # Show interviewer text in feed immediately
                await websocket.send_text(f"ASSISTANT:{transcript[14:]}")
            else:
                await websocket.send_text(f"TRANSCRIPT:{transcript}")
        except Exception:
            pass

    receive_task = asyncio.create_task(_receive_from_browser())
    send_task    = asyncio.create_task(_send_to_browser())

    profile = {
        "target_role": target_role,
        "target_company": target_company,
        "tech_stack": tech_stack,
        "current_profile": current_profile,
    }

    conversation = await run_pipeline(
        session_id=session_id,
        job_role=job_role,
        difficulty=difficulty,
        prep_mode=prep_mode,
        profile=profile,
        audio_queue=audio_in_queue,
        audio_out_queue=audio_out_queue,
        on_transcript=_on_transcript,
    )

    receive_task.cancel()
    send_task.cancel()
    await asyncio.gather(receive_task, send_task, return_exceptions=True)

    await _post_transcript_to_django(session_id, conversation, prep_mode, profile)
    print(f"[main] {session_id} ended — {len(conversation)} turns")


@app.get("/health")
async def health():
    return {"status": "ok"}