"""
agent.py
--------
LangGraph ReAct agent backed by Groq llama-3.3-70b-versatile.

Key design decisions:
- One shared InMemorySaver checkpointer for all sessions.
  Thread isolation is via thread_id = session_id from Django.
- Agents are compiled once per session and cached in _session_agents.
  This avoids re-compiling the LangGraph graph on every turn.
- On session end, call evict_session() to free memory.
"""

from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import InMemorySaver
from typing import AsyncIterator

from config import settings


# ---------------------------------------------------------------------------
# Shared in-process checkpointer
# Swap for SqliteSaver / PostgresSaver if you need persistence across restarts
# ---------------------------------------------------------------------------
_memory = InMemorySaver()

_llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    api_key=settings.GROQ_API_KEY,
    temperature=0.7,
    stop_sequences=["User:", "Candidate:", "Human:"],
)

_SUBJECTIVE_SYSTEM_PROMPT = """\
You are a professional technical interviewer conducting a mock interview.

Job Role: {job_role}
Difficulty: {difficulty}

Rules — follow them strictly:
1. Ask ONE question per turn. Never bundle multiple questions.
2. After each candidate answer, briefly acknowledge what they said (show you were listening), \
give a short constructive observation, then transition to the next question.
3. Vary question types across the interview:
    - Technical concepts and problem solving
    - Behavioral questions (ask them to use the STAR format)
    - Situational and system design scenarios
4. If the candidate gives a vague or incomplete answer, ask a focused follow-up \
to help them go deeper before moving on.
5. Keep each response under 4 sentences. You are speaking aloud:
    - No markdown, no bullet points, no asterisks, no emojis.
    - Use natural spoken language only.
6. After exactly 5 questions (and any follow-ups), tell the candidate the interview is complete, \
then give a 3-sentence overall performance summary.
7. If the candidate goes off-topic, gently redirect them back.

Begin by greeting the candidate warmly and asking your first question immediately.\
"""

_INTERACTIVE_SYSTEM_PROMPT = """\
You are a professional technical interviewer running a live, voice-based interview.

Job Role: {job_role}
Difficulty: {difficulty}
Candidate Profile:
{profile_summary}

Rules — follow them strictly:
1. Ask ONE question per turn. Never bundle multiple questions.
2. Tailor every question to the candidate's specific profile, target role, and tech stack.
3. After each candidate answer, briefly acknowledge their response (reference something specific they said), \
give a short constructive observation, then transition to the next question.
4. If the candidate gives a vague or incomplete answer, ask a targeted follow-up \
to help them demonstrate deeper knowledge before moving on.
5. Mix question types across the interview:
    - Technical depth on their stated tech stack
    - Problem solving and system design relevant to the target company
    - Behavioral questions using STAR format
    - Culture fit for the target company
6. Keep each response under 4 sentences. You are speaking aloud:
    - No markdown, no bullet points, no asterisks, no emojis.
    - Use natural spoken language only.
7. After exactly 6 questions (and any follow-ups), tell the candidate the interview is complete, \
then give a 3-sentence overall performance summary.
8. If the candidate goes off-topic, gently redirect them back.

Begin by greeting the candidate warmly, briefly mentioning their target role, and asking your first question immediately.\
"""

# session_id -> compiled agent graph
_session_agents: dict = {}


def _format_profile_summary(profile: dict) -> str:
    lines = []
    target_role = profile.get("target_role") or ""
    target_company = profile.get("target_company") or ""
    tech_stack = profile.get("tech_stack") or ""
    current_profile = profile.get("current_profile") or ""

    if target_role:
        lines.append(f"Target role: {target_role}")
    if target_company:
        lines.append(f"Target company: {target_company}")
    if tech_stack:
        lines.append(f"Tech stack: {tech_stack}")
    if current_profile:
        lines.append(f"Current profile: {current_profile}")

    if not lines:
        return "Not provided."

    return "\n".join(lines)


def _build_system_prompt(
    job_role: str,
    difficulty: str,
    prep_mode: str,
    profile: dict,
) -> str:
    if prep_mode == "interactive":
        profile_summary = _format_profile_summary(profile)
        return _INTERACTIVE_SYSTEM_PROMPT.format(
            job_role=job_role,
            difficulty=difficulty,
            profile_summary=profile_summary,
        )

    return _SUBJECTIVE_SYSTEM_PROMPT.format(
        job_role=job_role,
        difficulty=difficulty,
    )


def get_agent_for_session(
    session_id: str,
    job_role: str,
    difficulty: str,
    prep_mode: str,
    profile: dict,
):
    """
    Returns cached compiled agent for this session.
    Creates it on first call.
    """
    if session_id not in _session_agents:
        prompt = _build_system_prompt(job_role, difficulty, prep_mode, profile)
        agent = create_react_agent(
            model=_llm,
            tools=[],           # pure conversation, no tools needed
            checkpointer=_memory,
            prompt=prompt,
        )
        _session_agents[session_id] = agent

    return _session_agents[session_id]


def evict_session(session_id: str):
    """Free memory when an interview session ends."""
    _session_agents.pop(session_id, None)


async def stream_agent_response(
    transcript: str,
    session_id: str,
    job_role: str,
    difficulty: str,
    prep_mode: str,
    profile: dict,
) -> AsyncIterator[str]:
    """
    Feed one user turn into the agent, yield text tokens as they stream.
    pipeline.py collects these and forwards them to Kokoro TTS.
    """
    agent = get_agent_for_session(
        session_id,
        job_role,
        difficulty,
        prep_mode,
        profile,
    )
    config = {"configurable": {"thread_id": session_id}}

    stream = agent.astream(
        {"messages": [HumanMessage(content=transcript)]},
        config,
        stream_mode="messages",
    )

    async for message, _metadata in stream:
        if not hasattr(message, "content") or not message.content:
            continue

        if isinstance(message.content, str):
            yield message.content
        elif isinstance(message.content, list):
            for block in message.content:
                if isinstance(block, dict) and block.get("type") == "text":
                    if block["text"]:
                        yield block["text"]