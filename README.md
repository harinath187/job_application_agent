# Job Application Agent

## Project Overview
Job Application Agent is an AI-powered job application automation system that helps job seekers streamline the application process. The system accepts a resume and job preferences, searches for relevant jobs, tailors the resume for each job description, generates personalized cover letters, and prepares application-ready documents.

## Key objectives
- Automate repetitive application tasks: tailoring resumes and generating targeted cover letters.
- Provide an easy upload + monitor UI with a stable API.
- Keep the system usable without LLM keys by providing safe fallbacks.

## Benefits to job seekers
- Saves time by creating tailored resumes and cover letters at scale.
- Improves ATS compatibility by mirroring job description keywords.
- Tracks generated artifacts per upload session for easy download.

## Features
- Resume upload and parsing (PDF)
- Job scraping and filtering (optional SerpApi)
- Resume tailoring per job (PDF output)
- Cover letter generation (DOCX output)
- Session and job tracking (SQLite)
- LLM-powered flows with safe fallbacks when keys are not configured

## Architecture
```mermaid
flowchart LR
  U[Frontend Upload] -->|POST /api/upload| API[FastAPI Backend]
  API --> Orch[Orchestrator (LangGraph)]
  Orch --> PDF[PDF Parser Agent]
  Orch --> Scrape[Job Scraper Agent]
  Orch --> Tailor[Resume Tailor Agent]
  Orch --> CL[Cover Letter Agent]
  Tailor --> Outputs[(outputs/resumes)]
  CL --> OutputsCL[(outputs/cover_letters)]
  API --> DB[SQLite DB (data/jobs.db)]
  API --> Downloads[/api/download]
```

## Component descriptions
- `backend/api/main.py` — FastAPI app entrypoint, CORS, lifespan lifecycle.
- `backend/api/routes/upload.py` — Upload endpoint; starts background pipeline and inserts session record.
- `backend/api/routes/jobs.py` — Retrieve jobs for a session and job detail endpoint.
- `backend/api/routes/download.py` — Serves generated files with path-safety checks.
- `backend/orchestrator/graph.py` — Builds the LangGraph pipeline coordinating agents.
- `backend/agents/pdf_parser.py` — Extracts text and structured resume data (Groq optional, heuristic fallback).
- `backend/agents/scraper_agent.py` — Fetches and normalizes job listings using SerpApi (optional).
- `backend/agents/tailor_agent.py` — Tailors resume content and writes tailored PDFs (ReportLab).
- `backend/agents/cover_letter_agent.py` — Generates cover letters (.docx) with advanced prompt or fallback template.
- `backend/utils/db.py` — SQLite helpers and schema initialization (`backend/data/jobs.db`).
- `backend/utils/file_helpers.py` — Output directory initialization, filename sanitization, safe path helpers.

## Agent workflow
1. User uploads a PDF resume via the frontend or `POST /api/upload`.
2. Backend saves the file and creates a `session_id`.
3. Orchestrator pipeline runs (PDF parse → job scrape → resume tailoring → cover letter generation).
4. Tailored resumes and cover letters are written to `backend/outputs/resumes/` and `backend/outputs/cover_letters/`.
5. Jobs and file paths are inserted into the SQLite DB and become accessible via `GET /api/jobs`.

## Technology Stack
- Frontend: React 18, Vite, Axios, Tailwind CSS
- Backend: Python, FastAPI, Uvicorn
- Agents: Groq (optional LLM client), pypdf, reportlab, python-docx, requests
- Database: SQLite (local)

## Project Structure (important files/folders)
- `backend/` — backend application and agents
  - `api/` — FastAPI app and routes
  - `agents/` — `pdf_parser.py`, `scraper_agent.py`, `tailor_agent.py`, `cover_letter_agent.py`
  - `orchestrator/` — graph and state
  - `utils/` — `db.py`, `file_helpers.py`
  - `outputs/` — runtime-generated `resumes/` and `cover_letters/`
  - `data/` — runtime SQLite DB file `jobs.db`
  - `run.py` — helper script to start the server
  - `requirements.txt` — Python dependencies
- `frontend/` — React + Vite application
  - `src/api/agentApi.js` — client wrapper for backend endpoints
  - `src/components/` — UI components
  - `src/pages/` — app pages (Home, Dashboard, JobDetail)
  - `package.json` — JS dependencies and scripts

## Installation Guide
### Prerequisites
- Python 3.10+ (backend)
- Node.js 18+ (frontend)
- pip, npm/yarn
- (Optional) `GROQ_API_KEY` for LLM features
- (Optional) `SERPAPI_KEY` for job scraping

### Clone repository
```bash
git clone <repo-url>
cd job_application_agent
```

### Backend setup
```bash
cd backend
python -m venv .venv
# Windows PowerShell
.venv\Scripts\activate
pip install -r requirements.txt
```

### Frontend setup
```bash
cd frontend
npm install
# or
# yarn
```

## Environment Variables (backend `.env` example)
```
PORT=8000
GROQ_API_KEY=your_groq_api_key_here
SERPAPI_KEY=your_serpapi_key_here
```

### Description of variables
- `PORT`: Backend port (default 8000)
- `GROQ_API_KEY`: Groq LLM API key; optional. Agents fall back to heuristics/templates when absent.
- `SERPAPI_KEY`: SerpApi key for job scraping; optional. When absent, scraper returns an empty job list.

## Running
### Run backend
```bash
cd backend
python run.py
# or
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

### Run frontend (dev)
```bash
cd frontend
npm run dev
```

## Usage Guide
1. Open the frontend in the browser (Vite dev URL).
2. Upload your resume (PDF), enter `role` and `location` and submit.
3. The frontend receives a `session_id` and polls `GET /api/jobs?session_id=<id>`.
4. When complete, download tailored resume PDFs and cover letters via the dashboard or `GET /api/download?file=<filename>`.

## API Endpoints
- `POST /api/upload` — Upload PDF resume and start processing.
- `GET /api/jobs?session_id=<id>` — Get list of jobs for a session.
- `GET /api/jobs/{job_id}` — Get job details.
- `GET /api/download?file=<filename>` — Download generated file.

### Example upload (curl)
```bash
curl -F "file=@./my_resume.pdf" -F "role=Software Engineer" -F "location=United States" http://localhost:8000/api/upload
```

## Error handling and resilience
- Agents validate LLM outputs and fall back to heuristics or templates when JSON parsing fails or LLM keys are missing.
- Background pipeline errors are logged and sessions are marked `failed` in the DB.
- Orchestrator includes simple `time.sleep` delays to reduce API pressure; add rate-limiters for production.

## Logging
- Uses Python `logging` across backend modules. FastAPI logs application lifecycle events.

## Challenges and Solutions
- Resume parsing: provides Groq-based extraction with a robust heuristic fallback.
- LLM hallucinations: responses are validated and rejected if malformed; fallback templates are used.
- Rate limiting: simple delays in orchestrator; more robust backoff strategies recommended for production.

## Future Enhancements
- ATS scoring and optimization
- Interview preparation agent
- Auto-application submission integrations
- Analytics dashboard and job recommendation engine

## Security Considerations
- Protect resume privacy: current storage is local under `backend/outputs/` — consider retention policies or encryption before production.
- Store API keys in environment variables; never commit secrets.
- Migrate from SQLite to a managed DB for production deployments.

## Contributing
- Fork, create feature branches, open pull requests. Keep PRs focused and include tests for significant logic.

## License
- Add your preferred open-source license here.

## Acknowledgements
- Built with FastAPI, LangGraph orchestration, and example LLM prompts and fallbacks.
