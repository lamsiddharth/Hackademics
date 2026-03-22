"""
pipeline.py
-----------
Orchestrates the full voice pipeline for ONE interview session:

    Browser audio  →  STT (Groq Whisper)
                   →  LLM (Groq llama-3.3-70b via LangChain)
                   →  TTS (Kokoro)
                   →  Browser audio

Data flow via asyncio Queues (no shared mutable state):

    browser WS frames
         │
         ▼
    audio_queue          (bytes | None)
         │
      [stt.py]           accumulates PCM, sends to Groq Whisper
         │
         ▼
    transcript_queue     (str | None)
         │
      [agent.py]         streams tokens from Groq
         │
         ▼  (text collected fully before TTS call)
      [tts.py]           synthesizes via Kokoro WS
         │
         ▼
    audio_out_queue      (bytes | None)
         │
      [main.py]          sends bytes over browser WS

All four stages run concurrently as asyncio tasks.
"""

import asyncio
from typing import Callable, Awaitable

from stt import run_stt
from tts import KokoroTTS
from agent import stream_agent_response, evict_session


async def run_pipeline(
    session_id: str,
    job_role: str,
    difficulty: str,
    prep_mode: str,
    profile: dict,
    audio_queue: "asyncio.Queue[bytes | None]",
    audio_out_queue: "asyncio.Queue[bytes | None]",
    on_transcript: Callable[[str], Awaitable[None]] | None = None,
) -> list[dict]:
    """
    Main pipeline coroutine. Runs until the session ends (None sentinel
    in audio_queue) or an unrecoverable error occurs.

    Args:
        session_id:      Django session UUID — used as LangChain thread_id.
        job_role:        e.g. "Backend Engineer"
        difficulty:      "easy" | "medium" | "hard"
        audio_queue:     Input — raw PCM bytes from the browser.
        audio_out_queue: Output — raw PCM bytes to send to the browser.
        on_transcript:   Optional async callback called with each final
                         transcript (use to stream captions to frontend).

    Returns:
        List of {"role": "user"|"assistant", "content": str} dicts
        representing the full conversation — passed back to Django.
    """

    transcript_queue: asyncio.Queue[str | None] = asyncio.Queue()
    tts = KokoroTTS()
    conversation_history: list[dict] = []

    await tts.connect()

    await transcript_queue.put("Hello, I am ready for the interview.")
    # -----------------------------------------------------------------------
    # STT task: accumulates audio per turn, transcribes via Groq Whisper
    # -----------------------------------------------------------------------
    stt_task = asyncio.create_task(
        run_stt(audio_queue, transcript_queue)
    )

    # -----------------------------------------------------------------------
    # Pipeline task: consumes transcripts, runs LLM, runs TTS
    # -----------------------------------------------------------------------
    async def _llm_tts_loop():
        while True:
            transcript = await transcript_queue.get()

            # None = STT is done (session ended)
            if transcript is None:
                await audio_out_queue.put(None)
                return
            if not transcript.strip():
                continue

            # No transcript captured (too short audio, STT error, etc.)
            # — re-enable the mic without running LLM/TTS
            if transcript == "__NO_TRANSCRIPT__":
                print("[pipeline] empty turn — re-enabling mic")
                await audio_out_queue.put(b"__END_OF_RESPONSE__")
                continue

            # Skip empty transcripts
            if not transcript.strip():
                continue

            print(f"[pipeline] transcript: {transcript!r}")

            # Optional: stream caption to frontend
            if on_transcript:
                await on_transcript(transcript)

            # Save user turn
            conversation_history.append({"role": "user", "content": transcript})

            # --- LLM → TTS: stream sentence-by-sentence ---
            # Accumulate tokens into sentences. As soon as a sentence
            # boundary is detected, fire it off to Kokoro immediately
            # while the LLM keeps generating the next sentence.
            full_response = ""
            sentence_buf = ""
            sentence_enders = {'.', '!', '?'}

            async for token in stream_agent_response(
                transcript,
                session_id,
                job_role,
                difficulty,
                prep_mode,
                profile,
            ):
                full_response += token
                sentence_buf += token

                # Check if we have a complete sentence
                stripped = sentence_buf.strip()
                if stripped and stripped[-1] in sentence_enders and len(stripped) > 5:
                    # Send this sentence to TTS immediately
                    print(f"[pipeline] tts sentence: {stripped!r}")
                    async for audio_chunk in tts.synthesize(stripped):
                        await audio_out_queue.put(audio_chunk)
                    sentence_buf = ""

            # Flush any remaining text that didn't end with punctuation
            leftover = sentence_buf.strip()
            if leftover:
                print(f"[pipeline] tts leftover: {leftover!r}")
                async for audio_chunk in tts.synthesize(leftover):
                    await audio_out_queue.put(audio_chunk)

            print(f"[pipeline] llm response: {full_response!r}")

            if not full_response.strip():
                continue

            # Save assistant turn
            conversation_history.append({"role": "assistant", "content": full_response})

            if on_transcript:
                await on_transcript(f"__ASSISTANT__:{full_response}")

            # Signal frontend that this response is complete — re-enable mic
            await audio_out_queue.put(b"__END_OF_RESPONSE__")

    llm_tts_task = asyncio.create_task(_llm_tts_loop())

    # Wait for both tasks to complete
    await asyncio.gather(stt_task, llm_tts_task)
    await tts.close()
    evict_session(session_id)

    return conversation_history
