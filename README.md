# Hackademics

**Your AI Career Coach That Actually Understands You**

Hackademics is an AI-powered career intelligence platform that helps job seekers assess their skills, find matching jobs, build professional resumes, and create personalized learning roadmaps — all from a single unified interface powered by Google Gemini AI.

---

## Tech Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Backend | Django 5.2 (Python) | Web framework, ORM, authentication |
| AI Engine | Google Gemini API | Question generation, answer evaluation, skill extraction, resume enhancement, roadmap generation |
| Frontend | Tailwind CSS + HTML5 | Responsive dark-themed UI |
| Visualization | Chart.js | Interactive performance analytics |
| Job Data | Jooble + Remotive APIs | Real-time job listings |
| Document Export | python-docx | Professional resume DOCX generation |
| Database | SQLite | Lightweight data storage (MVP) |

---

## Features

### 1. AI Competency Assessment

Test your knowledge for any job role with AI-generated questions.

- Enter any job role (e.g., "Data Scientist", "Product Manager")
- AI generates **6 role-specific subjective questions** — 2 easy, 2 medium, 2 hard
- Write free-form answers evaluated by AI on a **0.0–1.0 scale**
- Instant scoring with per-question feedback
- No static question banks — fresh, relevant questions every time

**Key routes:** `/competency/generate/` → `/competency/test/<session>/question/<id>/` → `/competency/test/<session>/result/`

---

### 2. Interview Preparation

Practice interview questions across multiple categories with AI-powered feedback.

- Generate questions by category: **Behavioral, Technical, Situational, System Design**
- 5 questions generated per batch for a specific job role
- Practice mode: submit your answer and receive AI scoring + detailed feedback
- Compare your answer against AI-generated model answers
- Track scores and feedback history

**Key routes:** `/competency/interview-prep/` → `/competency/interview-prep/<id>/practice/`

---

### 3. AI Resume Builder

Transform your profile into a polished, professional resume.

- AI enhances raw profile data with **strong action verbs, metrics, and professional language**
- Choose from **3 templates**: Professional, Creative, or Minimalist
- **Download as DOCX** with custom formatting (section headings, bullet points, color-coded contact info)
- Manage multiple resume versions — view, edit, and delete
- Fallback plain-text generation if AI is unavailable

**Key routes:** `/resume/generate/` → `/resume/view-resume/` → `/resume/download/<id>/`

---

### 4. Smart Skill Extraction

Automatically map your skills from your entire professional profile.

- AI analyzes your education, experience, projects, and achievements
- Infers both **explicit and implicit skills** (not just what you list)
- Outputs a structured inventory: technical skills, soft skills, tools
- Extracted skills are stored and power downstream features (job matching, roadmaps, gap analysis)

**Key routes:** `/recommendations/extract-skills/`

---

### 5. Job Recommendations

Get real job listings matched to your actual skills.

- Skills refined into optimal search keywords by AI
- **Live job data** fetched from Jooble (keyword search) and Remotive (remote jobs)
- AI ranks each job and provides a **match explanation** (e.g., "Your Python backend experience aligns with 4 of 5 required competencies")
- **Bookmark jobs** for later — saved with duplicate prevention
- Remove saved jobs when no longer needed

**Key routes:** `/recommendations/job-recommendation/` · `/recommendations/match-live-jobs/` · `/recommendations/saved-jobs/`

---

### 6. Skill Gap Analysis

Understand exactly what's missing between your current skills and a target role.

- Enter a target role (e.g., "Senior Data Engineer")
- AI compares your current skills against role requirements
- Outputs: **current skills, missing skills, match percentage, actionable recommendations**

**Key routes:** `/recommendations/skill-gap/`

---

### 7. Adaptive Learning Roadmaps

Get a personalized 90-day plan to reach your target role.

- AI identifies specific skill gaps for your target job
- Generates a **week-by-week structured learning plan** with curated resources
- Includes links to documentation, courses, and tutorials
- **Interactive checklists** to track your progress step by step

**Key routes:** `/recommendations/roadmap/<job_title>/`

---

### 8. Performance Analytics

Track your growth over time with visual dashboards.

- **Line charts** showing correct answers vs total questions across tests
- Test history with dates, scores, and per-question breakdowns
- Score trends over time using Chart.js
- Filter performance by job role

**Key routes:** `/competency/test/historygraph/` · `/competency/test/history/`

---

### 9. User Dashboard

A central hub with real-time stats and quick actions.

- **Profile completeness** percentage with progress tracking
- Aggregated stats: total resumes, completed tests, average score, saved jobs, extracted skills
- **Quick action cards** for all major features (generate resume, take test, interview prep, roadmap, skill gap, job recommendations)
- **Recent activity feed** (last 5 actions)
- Activity log with full history (last 50 actions)

**Key routes:** `/dashboard/` · `/activity/`

---

## Project Structure

```
Hackademics-1/
├── manage.py                     # Django management CLI
├── requirements.txt              # Python dependencies
├── .env                          # Environment variables (API keys, secrets)
├── db.sqlite3                    # SQLite database
│
├── config/                       # Django project configuration
│   ├── settings.py               # Settings (DB, auth, installed apps)
│   ├── urls.py                   # Root URL routing
│   ├── views.py                  # Custom 404/500 error handlers
│   ├── wsgi.py                   # WSGI entry point
│   └── asgi.py                   # ASGI entry point
│
├── users/                        # User management module
│   ├── models.py                 # User, UserProfile, ActivityLog
│   ├── views.py                  # Register, login, logout, dashboard, profile
│   ├── forms.py                  # Authentication & registration forms
│   └── urls.py                   # User routes
│
├── competency/                   # Competency assessment module
│   ├── models.py                 # CompetencyTest, Question, Session, Answer, InterviewQuestion
│   ├── views.py                  # Test generation, questions, results, interview prep
│   ├── utils.py                  # AI question generation & answer evaluation
│   ├── urls.py                   # Competency routes
│   └── templatetags/
│       └── math_filters.py       # Custom template filters
│
├── resume_builder/               # Resume generation module
│   ├── models.py                 # Resume model
│   ├── views.py                  # Generate, view, edit, delete, download
│   ├── utils.py                  # AI resume enhancement via Gemini
│   └── urls.py                   # Resume routes
│
├── recommendations/              # Job matching & learning paths module
│   ├── models.py                 # JobRecommendation, SavedJob, SkillGapAnalysis, Roadmap, LearningPath
│   ├── views.py                  # Job matching, skill extraction, roadmaps, saved jobs
│   ├── utils.py                  # AI job matching, skill extraction, roadmap generation
│   ├── ollama_utils.py           # Alternative local LLM utilities
│   └── urls.py                   # Recommendation routes
│
└── templates/                    # Django HTML templates
    ├── base.html                 # Master layout (nav, footer, Tailwind config)
    ├── users/                    # Landing, login, register, dashboard, profile
    ├── competency/               # Test generation, questions, results, analytics, interview prep
    ├── resume_templates/         # Resume templates (3 designs), edit, view
    ├── recommendations/          # Jobs, roadmap, skill gap, skill extraction, saved jobs
    └── errors/                   # 404 and 500 error pages
```

---

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                          BROWSER                             │
│              Tailwind CSS  ·  Chart.js  ·  HTML5             │
└─────────────────────────────┬────────────────────────────────┘
                              │
┌─────────────────────────────▼────────────────────────────────┐
│                      DJANGO BACKEND                          │
│                                                              │
│   ┌──────────┐  ┌────────────┐  ┌───────────┐  ┌─────────┐ │
│   │  Users   │  │ Competency │  │  Resume   │  │  Recom- │ │
│   │  Module  │  │   Module   │  │  Builder  │  │ endations│ │
│   └────┬─────┘  └─────┬──────┘  └─────┬─────┘  └────┬────┘ │
│        └───────────────┴───────────────┴─────────────┘      │
│                          │                                   │
│               ┌──────────▼──────────┐                        │
│               │   SQLite Database   │                        │
│               └─────────────────────┘                        │
└─────────────────────────────┬────────────────────────────────┘
                              │
┌─────────────────────────────▼────────────────────────────────┐
│                    EXTERNAL SERVICES                          │
│                                                              │
│   ┌───────────────┐  ┌────────────┐  ┌─────────────────┐    │
│   │ Google Gemini │  │ Jooble API │  │  Remotive API   │    │
│   │    (Gen AI)   │  │   (Jobs)   │  │  (Remote Jobs)  │    │
│   └───────────────┘  └────────────┘  └─────────────────┘    │
└──────────────────────────────────────────────────────────────┘
```

---

## Getting Started

### Prerequisites

- Python 3.10+
- pip

### Installation

1. **Clone the repository**

   ```bash
   git clone https://github.com/your-username/Hackademics-1.git
   cd Hackademics-1
   ```

2. **Create and activate a virtual environment**

   ```bash
   python -m venv venv
   source venv/bin/activate        # Linux/macOS
   venv\Scripts\activate           # Windows
   ```

3. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**

   Create a `.env` file in the project root:

   ```env
   SECRET_KEY=your-django-secret-key
   DEBUG=True
   ALLOWED_HOSTS=localhost,127.0.0.1

   GEMINI_API_KEY=your-google-gemini-api-key
   GEMINI_MODEL=gemini-2.5-flash

   JOOBLE_API_KEY=your-jooble-api-key
   ```

5. **Run database migrations**

   ```bash
   python manage.py migrate
   ```

6. **Create a superuser** (optional, for admin access)

   ```bash
   python manage.py createsuperuser
   ```

7. **Start the development server**

   ```bash
   python manage.py runserver
   ```

   Open [http://localhost:8000](http://localhost:8000) in your browser.

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `SECRET_KEY` | Yes | Django secret key for cryptographic signing |
| `DEBUG` | No | Enable debug mode (`True`/`False`, defaults to `False`) |
| `ALLOWED_HOSTS` | No | Comma-separated list of allowed hostnames |
| `GEMINI_API_KEY` | Yes | Google Gemini API key for all AI features |
| `GEMINI_MODEL` | No | Gemini model to use (defaults to `gemini-2.5-flash`) |
| `JOOBLE_API_KEY` | Yes | Jooble API key for job search integration |

---

## API Integrations

### Google Gemini AI
Powers all AI features — question generation, answer evaluation, skill extraction, resume enhancement, job matching explanations, and learning roadmap generation. Accessed via the `google-generativeai` Python SDK.

### Jooble API
Provides real-time job listings based on keyword search. Used in the job recommendations feature to fetch positions matching the user's extracted skills.

### Remotive API
Fetches remote job listings. Used alongside Jooble to provide remote-friendly job matches based on user skills.

---

## Future Roadmap

| Phase | Focus | Features |
|-------|-------|----------|
| Phase 1 | Current MVP | AI assessment, resume builder, job recommendations, learning roadmaps |
| Phase 2 | Enhanced Intelligence | Video interview analysis, company culture matching, salary insights |
| Phase 3 | Enterprise | Employer dashboard, bulk assessment, custom question banks, APIs |
| Phase 4 | Scale | Mobile apps, multi-language support, regional job boards, certifications |

---

## License

Hackademics &copy; 2026 — Built by Siddharth
