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

## Alpha Features

- **Login with roles:** email/password login with JWT tokens. Employees and managers see different dashboards.
- **Employee dashboard:** view your PTO balance (available, used, pending) and submit requests with an optional reason. Each request shows its dates, hours, status, policy notices, and the manager's comment.
- **Rule engine:** invalid requests are rejected (past start date, end before start, no workdays, overlapping requests). Policy concerns are flagged for the manager: short notice (under 7 days), long requests (more than 10 workdays), and requests that exceed the available balance. Weekends and company holidays are not counted.
- **Manager review:** managers see pending requests from their own team and approve or deny them with an optional comment. Approval is blocked if it would exceed the employee's balance.
- **AI policy chatbot:** any logged-in user can ask questions about the PTO policy. Answers come only from `backend/app/policy/pto_policy.md`. Answers that need a human are marked for confirmation with a manager or HR.

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
python -m scripts.seed             # load demo accounts (see "Demo Accounts" below)
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

Open http://localhost:5173 and log in with one of the [demo accounts](#demo-accounts).

To work on the frontend without the backend, set `VITE_USE_MOCK_API=true` in `frontend/.env.local`. Mock mode uses built-in sample data: any email and password logs in, and emails starting with `manager@` log in as a manager.

### Backend Dependencies

`backend/requirements.in` lists the direct dependencies. `backend/requirements.txt` is the lockfile generated from it, with every package pinned, so local machines, CI, and Render install the same versions.

To add or upgrade a dependency, edit `requirements.in` (never `requirements.txt` directly), then from `backend/` with the venv active:

```bash
pip-compile requirements.in -o requirements.txt
pip install -r requirements-dev.txt
```

Commit both files.

## Environment Variables

| Variable | File | Purpose | Local value |
|---|---|---|---|
| `DATABASE_URL` | `backend/.env` | PostgreSQL connection string | Windows: `postgresql+psycopg://postgres:postgres@localhost:5432/pto_db` MacOS: `postgresql+psycopg://YOUR_MAC_USERNAME@localhost:5432/pto_db` |
| `JWT_SECRET` | `backend/.env` | Signs login tokens | Any dev string, e.g. `dev-only-local-secret` |
| `OPENAI_API_KEY` | `backend/.env` | OpenAI access | Empty unless working on AI features |
| `OPENAI_MODEL` | `backend/.env` | OpenAI model for the chatbot | `gpt-5.4-mini` (default) |
| `AI_PROVIDER` | `backend/.env` | `openai` or `mock` (fixed demo reply, no API calls) | `mock` if you don't have an OpenAI key |
| `FRONTEND_ORIGIN` | `backend/.env` | Allowed origin for CORS | `http://localhost:5173` |
| `VITE_API_URL` | `frontend/.env.local` | Backend URL | `http://localhost:8000` |
| `VITE_USE_MOCK_API` | `frontend/.env.local` | `true` uses built-in mock data instead of the backend | `false` |

- **Never commit `.env` or `.env.local` files.** Both are gitignored. Production values live only in Render.
- **OpenAI keys:** you don't need one unless you're working on the AI feature. The rest of the app runs without it. If you do need one, ask the Integration Lead for your own dev key; keys are never shared between developers.

## Demo Accounts

Load or reset the demo accounts with the seed script. It is safe to run more than once: demo users and their requests are updated in place, and balances are recalculated.

- **Locally:** from `backend/` with the venv active, after `alembic upgrade head`, run `python -m scripts.seed`.
- **On Render:** open the `pto-api` service in the Render dashboard, go to the **Shell** tab, and run `python -m scripts.seed`.

| Name | Email | Password | Role | Balance (Total / Used / Pending / Avail) |
|---|---|---|---|---|
| Alice Manager | `manager@example.com` | `manager-pass-123` | `manager` | 120h / 0h / 0h / 120h |
| Bob Employee | `bob@example.com` | `bob-pass-123` | `employee` | 120h / 40h / 24h / 56h |
| Carol Employee | `carol@example.com` | `carol-pass-123` | `employee` | 120h / 16h / 16h / 88h |
| David Employee | `david@example.com` | `david-pass-123` | `employee` | 120h / 0h / 96h / 24h |

- **Alice Manager** supervises Bob, Carol, and David.
- **Bob Employee** has 1 approved request (40h) and 1 pending request over Thanksgiving week (24h).
- **Carol Employee** has 1 approved request (16h), 1 pending request with a `SHORT_NOTICE` flag (16h), and 1 denied request (24h).
- **David Employee** has 1 pending request with a `LONG_REQUEST` flag (96h).

## Development Workflow

1. Branch from `main`: `feature/...`, `fix/...`, `chore/...`, or `docs/...`
2. Commit using the same prefixes, e.g. `feat: add PTO request form`
3. Open a pull request and fill in the template
4. CI runs backend tests and frontend lint/build automatically
5. Get **one teammate approval**, **all checks green**, and **all review comments resolved** before merging
6. **Squash and merge.** Render deploys automatically after CI passes on `main`

> **Branch protection:** `main` requires a pull request, one approval, passing CI checks, and resolved conversations before merging. Only squash merging is allowed.