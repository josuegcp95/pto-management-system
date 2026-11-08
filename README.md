# PTO-Management-System

CMSC 495 Capstone: AI-Assisted PTO Management System

## Team

| Name | Role |
|---|---|
| Nicolas DiPaolo | Lead Architect |
| Evan Darby | Interface Designer |
| Josue Cruz | Integration Lead |

## Live Deployment

- **App:** https://pto-web.onrender.com
- **API:** https://pto-api-m5lw.onrender.com ([API docs](https://pto-api-m5lw.onrender.com/docs))

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React + TypeScript (Vite), Oxlint |
| Backend | Python 3.12 + FastAPI |
| Database | PostgreSQL (Render) |
| AI | OpenAI API (backend only) |
| CI/CD | GitHub Actions + Render auto-deploy |

## Repository Structure

```
pto-management-system/
├── backend/        FastAPI app, tests, scripts
├── frontend/       React + TypeScript app
├── .github/        CI workflow and PR template
└── .nvmrc          Node version (24 LTS)
```

## Prerequisites

- Git
- Python 3.12
- PostgreSQL 15+ (running locally)
- Node.js 24 LTS (via [nvm](https://github.com/nvm-sh/nvm); run `nvm use` in the repo root)
- VS Code (recommended)

## Local Setup

### 1. Clone

```bash
git clone https://github.com/josuegcp95/pto-management-system.git
cd pto-management-system
```

### 2. Local PostgreSQL Database

- Ensure PostgreSQL is running locally 
- Create the `pto_db` database with the following commands depending on your platform:

- Windows:
```bash
psql -U postgres -c "CREATE DATABASE pto_db;"
```

- MacOS:
```bash
brew install postgresql@18
brew services start postgresql@18
createdb pto_db
```

### 3. Backend

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env               # then fill in local values (see below), update DATABASE_URL
alembic upgrade head
uvicorn app.main:app --reload
```

- Health check: http://localhost:8000/health
- API docs: http://localhost:8000/docs
- Run tests: `pytest`
- Run migrations: `alembic upgrade head`
- Generate a new migration: `alembic revision --autogenerate -m "description"`

### 4. Frontend

In a second terminal:

```bash
cd frontend
nvm use
npm install
cp .env.example .env.local
npm run dev
```

Open http://localhost:5173. The page should show **✅ Connected** when the backend is running.

## Environment Variables

| Variable | File | Purpose | Local value |
|---|---|---|---|
| `DATABASE_URL` | `backend/.env` | PostgreSQL connection string | Windows: `postgresql+psycopg://postgres:postgres@localhost:5432/pto_db` MacOS: `postgresql+psycopg://YOUR_MAC_USERNAME@localhost:5432/pto_db` |
| `JWT_SECRET` | `backend/.env` | Signs login tokens | Any dev string, e.g. `dev-only-local-secret` |
| `OPENAI_API_KEY` | `backend/.env` | OpenAI access | Empty unless working on AI features |
| `FRONTEND_ORIGIN` | `backend/.env` | Allowed origin for CORS | `http://localhost:5173` |
| `VITE_API_URL` | `frontend/.env.local` | Backend URL | `http://localhost:8000` |

- **Never commit `.env` or `.env.local` files.** Both are gitignored. Production values live only in Render.
- **OpenAI keys:** you don't need one unless you're working on the AI feature. The rest of the app runs without it. If you do need one, ask the Integration Lead for your own dev key; keys are never shared between developers.

## Development Workflow

1. Branch from `main`: `feature/...`, `fix/...`, `chore/...`, or `docs/...`
2. Commit using the same prefixes, e.g. `feat: add PTO request form`
3. Open a pull request and fill in the template
4. CI runs backend tests and frontend lint/build automatically
5. Get **one teammate approval** and **all checks green** before merging
6. **Squash and merge.** Render deploys automatically after CI passes on `main`

> **Team policy:** never merge with failing checks. GitHub doesn't enforce this on private repos without GitHub Pro, so it's a team agreement.