# Live Interview Prep Integration Guide

## Overview
Live Interview Prep adds a new `prep_mode=interactive` that personalizes the interviewer prompt with candidate profile data and generates a structured final performance report. The voice pipeline remains unchanged (STT -> LLM -> TTS), but it now receives profile metadata and uses mode-specific prompts. Django endpoints pass through profile data and produce the final report.

## Features Implemented
- Interactive voice interview mode with profile-aware prompt injection.
- Mode-aware interviewer behavior (subjective vs interactive).
- Structured end-of-interview performance report with score.
- End-to-end metadata plumbing from session start to report generation.

## Integration Points

### 1) Start Interview (Frontend -> Django)
**Endpoint**
`POST /mock-interview/start/`

**Request body**
```json
{
  "prep_mode": "interactive",
  "job_role": "Software Engineer",
  "difficulty": "medium",
  "target_role": "Backend Engineer",
  "target_company": "Stripe",
  "tech_stack": "Python, FastAPI, Postgres",
  "current_profile": "2 years backend, fintech, REST APIs"
}
```

**Behavior**
- `prep_mode` defaults to `subjective` if omitted.
- `job_role` defaults to `target_role` if present, otherwise to "Software Engineer".
- Returns a WebSocket URL containing all parameters.

**Response**
```json
{
  "session_id": "<uuid>",
  "ws_url": "ws://localhost:8001/interview?session_id=...&job_role=...&difficulty=...&prep_mode=interactive&target_role=...&target_company=...&tech_stack=...&current_profile=..."
}
```

**Implementation**
- Start handler: `views.py::start_interview`

---

### 2) Live Interview (Frontend -> FastAPI WebSocket)
**WebSocket**
`ws://localhost:8001/interview?session_id=<uuid>&job_role=<role>&difficulty=<level>&prep_mode=<mode>&target_role=...&target_company=...&tech_stack=...&current_profile=...`

**Behavior**
- Params are parsed in FastAPI and passed into the pipeline.
- Subjective mode keeps the existing 5-question flow.
- Interactive mode uses profile-aware prompt injection.

**Implementation**
- WebSocket handling: `main.py::interview_endpoint`
- Pipeline: `pipeline.py::run_pipeline`
- Prompt selection: `agent.py::_build_system_prompt`

---

### 3) End Interview (FastAPI -> Django internal callback)
**Endpoint**
`POST /mock-interview/end/` (internal only)

**Payload**
```json
{
  "session_id": "<uuid>",
  "conversation": [
    {"role": "user", "content": "..."},
    {"role": "assistant", "content": "..."}
  ],
  "prep_mode": "interactive",
  "profile": {
    "target_role": "...",
    "target_company": "...",
    "tech_stack": "...",
    "current_profile": "..."
  }
}
```

**Behavior**
- Saves transcript and status.
- Generates structured performance report via LLM.

**Implementation**
- End handler: `views.py::end_interview`
- Feedback generator: `views.py::_generate_feedback`

---

## Final Performance Report Format
The report is a single text response with:
1. Summary
2. Strengths
3. Gaps and risks
4. STAR/structure usage
5. Next-step recommendations
6. A dedicated score line: `Score: X/10`

**Example (format only)**
```
Summary: ...
Strengths: ...
Gaps and risks: ...
STAR/structure usage: ...
Next-step recommendations: ...
Score: 7/10
```

---

## Prompt Behavior

### Subjective Mode
- Uses original 5-question cadence and generic role/difficulty.

### Interactive Mode
- Injects candidate profile into the interviewer prompt.
- Asks tailored questions based on profile and answers.
- Current cadence: 6 questions (configurable in `agent.py`).

---

## Data Flow Summary
1. Frontend sends `prep_mode` + profile to Django start endpoint.
2. Django returns a WebSocket URL with mode/profile query params.
3. FastAPI runs the voice pipeline and uses mode-aware prompts.
4. FastAPI posts transcript + metadata to Django end endpoint.
5. Django generates and stores the structured performance report.

---

## Frontend Requirements
- Add UI option for "Live Interview Prep".
- Collect and send `target_role`, `target_company`, `tech_stack`, `current_profile`.
- Pass `prep_mode=interactive` to `/mock-interview/start/`.

---

## Optional Enhancements
- Persist candidate profile fields on the Django InterviewSession model.
- Return profile data in results response.
- Make question count configurable per mode.
