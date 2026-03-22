"""
stt.py
------
Per-turn STT using Groq Whisper API with parallel chunked transcription.

While the user is recording, audio is accumulated in ~3-second chunks.
Each chunk is sent to Groq Whisper in parallel as soon as it fills up.
When the user clicks stop, the final partial chunk is sent too.
All transcription futures are awaited, results joined in order,
and the full transcript is put into transcript_queue.

This means by the time the user clicks stop, most audio is already
transcribed — only the last chunk needs to finish.
"""

import asyncio
import io
import wave

from groq import Groq
from config import settings

# ~3 seconds of 16kHz 16-bit mono PCM = 96000 bytes
CHUNK_DURATION_SEC = 3
CHUNK_SIZE_BYTES = 16000 * 2 * CHUNK_DURATION_SEC  # 96KB per chunk


def _transcribe_audio(audio_buffer: bytes) -> str:
    """
    Send raw PCM-16 audio to Groq Whisper and return the transcript.
    Wraps the raw PCM bytes in a WAV container so the API can parse it.
    """
    wav_io = io.BytesIO()
    with wave.open(wav_io, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)        # 16-bit = 2 bytes
        wf.setframerate(16000)
        wf.writeframes(audio_buffer)
    wav_io.seek(0)

    client = Groq(api_key=settings.GROQ_API_KEY.get_secret_value())

    transcription = client.audio.transcriptions.create(
        file=("recording.wav", wav_io),
        model="whisper-large-v3",
        language="en",
        response_format="text",
    )

    return transcription.strip() if isinstance(transcription, str) else str(transcription).strip()


async def _transcribe_async(audio_buffer: bytes, loop: asyncio.AbstractEventLoop) -> str:
    """Run the blocking Groq API call in a thread pool."""
    return await loop.run_in_executor(
        None,
        lambda: _transcribe_audio(audio_buffer),
    )


async def run_stt(
    audio_queue: "asyncio.Queue[bytes | None]",
    transcript_queue: "asyncio.Queue[str | None]",
) -> None:
    """
    Long-running STT manager — one per interview session.
    Chunks audio during recording and transcribes in parallel via Groq Whisper.
    """
    print("[stt] STT manager started, waiting for audio turns...")

    loop = asyncio.get_event_loop()

    while True:
        # Block until the first audio chunk of a new turn arrives
        first_chunk = await audio_queue.get()

        # None = session ended by browser disconnect
        if first_chunk is None:
            print("[stt] session end signal received")
            await transcript_queue.put(None)
            return

        # __STOP__ with no prior audio = user clicked stop immediately
        if first_chunk == b"__STOP__":
            print("[stt] empty turn (stop with no audio)")
            continue

        # ---- Accumulate audio in chunks, fire off parallel transcriptions ----
        pending_tasks: list[asyncio.Task] = []  # ordered transcription futures
        current_chunk = bytearray()

        if len(first_chunk) > 0:
            current_chunk.extend(first_chunk)

        session_ending = False

        while True:
            # If current chunk is big enough, send it for transcription
            if len(current_chunk) >= CHUNK_SIZE_BYTES:
                chunk_bytes = bytes(current_chunk)
                current_chunk = bytearray()
                task = asyncio.create_task(_transcribe_async(chunk_bytes, loop))
                pending_tasks.append(task)
                chunk_num = len(pending_tasks)
                duration = len(chunk_bytes) / (16000 * 2)
                print(f"[stt] chunk {chunk_num} sent to Groq ({duration:.1f}s audio)")

            chunk = await audio_queue.get()

            if chunk is None:
                session_ending = True
                await audio_queue.put(None)
                break

            if chunk == b"__STOP__":
                break

            if len(chunk) > 0:
                current_chunk.extend(chunk)

        # ---- Send the final partial chunk (if any) ----
        if len(current_chunk) > 0:
            final_bytes = bytes(current_chunk)
            duration = len(final_bytes) / (16000 * 2)
            if duration >= 0.3:  # skip tiny fragments
                task = asyncio.create_task(_transcribe_async(final_bytes, loop))
                pending_tasks.append(task)
                print(f"[stt] final chunk {len(pending_tasks)} sent to Groq ({duration:.1f}s audio)")
            else:
                print(f"[stt] skipping tiny final chunk ({duration:.1f}s)")

        if not pending_tasks:
            print("[stt] no audio captured this turn")
            await transcript_queue.put("__NO_TRANSCRIPT__")
            continue

        # ---- Await all parallel transcriptions and join in order ----
        print(f"[stt] waiting for {len(pending_tasks)} chunk transcription(s)...")
        results = await asyncio.gather(*pending_tasks, return_exceptions=True)

        transcript_parts = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                print(f"[stt] chunk {i+1} error: {result}")
            elif result:
                transcript_parts.append(result)

        transcript = " ".join(transcript_parts).strip()

        if transcript:
            print(f"[stt] turn transcript: {transcript!r}")
            await transcript_queue.put(transcript)
        else:
            print("[stt] no transcript for this turn — notifying pipeline")
            await transcript_queue.put("__NO_TRANSCRIPT__")

        # Loop back to wait for the next turn