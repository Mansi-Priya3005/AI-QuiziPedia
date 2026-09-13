# AI QuiziPedia 🧠📚

An AI-powered full-stack educational web application that transforms Wikipedia articles into interactive quizzes for smarter learning. Built with FastAPI, React, PostgreSQL, and Google Gemini.

## 🚀 Features

### 🤖 AI-Powered Quiz Generation
- **Instant Quiz Creation**: Convert any Wikipedia article into an interactive quiz in seconds
- **PDF/Text Upload**: Generate a quiz from your own PDF or .txt document instead of a Wikipedia URL (up to 10 MB; scanned/image-only PDFs aren't supported yet, since that needs OCR)
- **Structured, schema-validated output**: Gemini's structured output mode enforces the quiz JSON shape directly, rather than hoping the model formats free text correctly
- **Smart Content Analysis**: Extracts key sections, entities, and related topics from the article
- **AI-Based Explanations**: Each answer includes an explanation to improve understanding

### 🎯 Interactive Quiz Experience
- **Timed Quiz Sessions**: Track how quickly you answer questions
- **Multiple Attempts**: Retry quizzes and improve your score
- **Instant Feedback**: Correct answers and explanations shown immediately after submission
- **Question Navigation**: Smooth, user-friendly progress tracking

### 📊 Performance Insights
- **Attempt History**: Paginated list of past quizzes and scores
- **Accuracy Tracking**: See how you're performing over time
- **Detailed Review Mode**: Compare your answers against correct ones

### 🎨 Modern User Interface
- **Responsive Design**: Works on desktop and mobile
- **Smooth Animations**: Framer Motion throughout
- **Clean Dashboard**: Minimal, modern interface

---

## 🛠️ Tech Stack

### Backend
- **FastAPI** — async Python web framework
- **PostgreSQL** + **SQLAlchemy** — relational storage and ORM
- **Alembic** — versioned, reversible schema migrations
- **Google Gemini** (`google-genai`) — quiz generation with structured JSON output
- **httpx** — async HTTP client for scraping (doesn't block the event loop)
- **BeautifulSoup4** — Wikipedia HTML parsing
- **Pydantic** — request/response validation
- **slowapi** — rate limiting on the AI-backed endpoint
- **tenacity** — retry with backoff on transient AI/network failures

### Frontend
- **React 19** + **Vite**
- **Tailwind CSS**
- **Framer Motion**
- **Lucide React**

### Testing & CI
- **pytest** + **pytest-asyncio** — backend test suite, run against a real Postgres instance
- **ESLint** (flat config, `eslint-plugin-react`) — frontend linting
- **GitHub Actions** — backend tests + frontend lint/build on every push and PR

### Deployment
- **Docker** / **docker-compose** — one-command local environment (Postgres + backend + frontend)
- **Render** — backend + managed Postgres (see `render.yaml`)
- Any static host (Vercel, Netlify, etc.) — frontend

---

## 🚀 Quick Start (Docker — recommended)

### Prerequisites
- Docker and Docker Compose
- A [Google Gemini API key](https://aistudio.google.com/app/apikey)

### Run it

```bash
git clone https://github.com/Mansi-Priya3005/AI-QuiziPedia.git
cd AI-QuiziPedia

export GEMINI_API_KEY=your-gemini-api-key-here
docker compose up --build
```

This starts three containers: Postgres, the FastAPI backend (migrations run automatically on boot), and the frontend served by nginx.

- Frontend: http://localhost:5173
- Backend API: http://localhost:8000
- API docs: http://localhost:8000/docs

---

## 🛠️ Manual Setup (without Docker)

### Prerequisites
- Python 3.11+
- Node.js 20+
- A running PostgreSQL instance
- A Google Gemini API key

### 1. Clone the repository

```bash
git clone https://github.com/Mansi-Priya3005/AI-QuiziPedia.git
cd AI-QuiziPedia
```

### 2. Backend setup

```bash
cd backend
python3 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env
# then edit .env and fill in DATABASE_URL and GEMINI_API_KEY

alembic upgrade head       # apply database migrations
uvicorn main:app --reload  # starts on http://localhost:8000
```

### 3. Frontend setup

In a second terminal:

```bash
cd frontend
npm install

cp .env.example .env   # defaults to http://localhost:8000, adjust if needed

npm run dev             # starts on http://localhost:5173
```

### 4. Run the backend tests

```bash
cd backend
# requires a Postgres database reachable at DATABASE_URL (a separate
# test DB is recommended — tests truncate tables between runs)
pytest tests/ -v --cov=. --cov-report=term-missing
```

---

## 🗄️ Database Migrations

Schema changes are managed with Alembic — **not** by an app-level `create_all()` on startup. To make a schema change:

```bash
cd backend
# 1. edit the SQLAlchemy models in database.py
# 2. generate a migration:
alembic revision --autogenerate -m "describe your change"
# 3. review the generated file in alembic/versions/, then apply it:
alembic upgrade head
```

Migrations are reversible (`alembic downgrade -1`) and run automatically on container start via `docker-entrypoint.sh`.

---

## 📁 Project Structure

```
AI-QuiziPedia/
├── backend/
│   ├── main.py                 # FastAPI routes
│   ├── config.py                # environment-driven settings
│   ├── database.py              # SQLAlchemy models
│   ├── schemas.py               # API request/response validation
│   ├── models.py                # Gemini structured-output schema
│   ├── llm_quiz_generator.py    # Gemini integration, retries, error handling
│   ├── scraper.py               # async Wikipedia scraping
│   ├── alembic/                 # database migrations
│   ├── tests/                   # pytest suite
│   ├── Dockerfile
│   └── docker-entrypoint.sh
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── tabs/
│   │   └── services/api.js
│   └── Dockerfile
├── docker-compose.yml
├── render.yaml
└── .github/workflows/ci.yml
```

---

## 🔐 Environment Variables

See `backend/.env.example` and `frontend/.env.example` for the full list. Key ones:

| Variable | Where | Description |
|---|---|---|
| `DATABASE_URL` | backend | PostgreSQL connection string |
| `GEMINI_API_KEY` | backend | Google Gemini API key |
| `JWT_SECRET_KEY` | backend | Random secret used to sign auth tokens (generate with `python3 -c "import secrets; print(secrets.token_hex(32))"`) |
| `CORS_ALLOWED_ORIGINS` | backend | Comma-separated allowed frontend origins |
| `VITE_API_BASE` | frontend | Backend URL (baked in at build time) |

---

## ⚠️ Known Limitations

Documented honestly rather than glossed over:

- **No password reset / email verification** — signup and login work, but there's no "forgot password" flow or email confirmation yet.
- **No caching layer** — every unique URL triggers a fresh Gemini call; no Redis/CDN caching of responses yet.
- **Synchronous-in-process generation** — quiz generation happens inline within the HTTP request rather than via a background job queue, so a slow Gemini response holds a request open for its full duration.

These are natural next steps; see open issues / roadmap for details.
