# ReMind

[![CI](https://github.com/Kanha-Gupta18/ReMind/actions/workflows/ci.yml/badge.svg)](https://github.com/Kanha-Gupta18/ReMind/actions/workflows/ci.yml)

ReMind is an evidence-grounded memory-support platform for people living with dementia, Alzheimer's disease, acquired brain injury, or other forms of memory impairment. It helps families preserve autobiographical context and present verified memories through a calm timeline and conversational interface.

> [!IMPORTANT]
> ReMind is an early-stage prototype. It is not a diagnostic product, a substitute for medical care, or ready for use with real patient data. Deletion propagation, production security, and clinical validation remain in progress.

## Product principles

- Dignity over everything.
- Evidence before narrative.
- Uncertainty must remain visible.
- Human review before patient delivery.
- No fabricated autobiographical memories.
- Consent, provenance, and important actions must be auditable.

The core invariant is that no patient-facing autobiographical claim should exist without traceable evidence and appropriate review.

## What exists today

The current prototype includes:

- Server-backed login sessions and revocable patient relationships for patients,
  family contributors/reviewers, caregivers, guardians, and clinicians.
- Source upload, metadata capture, checksums, local development storage, and simulated processing pipelines.
- Memory drafts, review states, revisions, evidence, confidence scoring, and sensitivity flags.
- Patient timeline views grouped chronologically, by decade, and by place.
- People, face-match review, and an evidence-bearing knowledge graph.
- Grounded conversation over approved memories with basic medical and sensitive-topic guardrails.
- Versioned consent policies enforced across patient-data routes, delegated
  guardian authority, third-party consent records, safety events, notifications,
  engagement summaries, and audit records.
- A role-aware React web application for the implemented workflows.

AI extraction is currently simulated. Real OCR, speech, vision, embedding, and model-provider integrations have not been connected.

## Technology

| Layer | Stack |
| --- | --- |
| Web | React 19, TypeScript, React Router, Vite |
| API | Python, FastAPI, Pydantic |
| Data | PostgreSQL, SQLAlchemy, Alembic |
| Auth | Server-backed JWT access/refresh sessions, refresh rotation, bcrypt |
| Tests | Pytest, FastAPI TestClient |

## Repository layout

```text
ReMind/
├── apps/web/                 React web application
├── services/api/            FastAPI service, models, migrations, and tests
├── docs/                    Product, architecture, and roadmap documentation
├── infra/                   Infrastructure work (planned)
├── packages/                Shared packages (planned)
├── workers/                 Background processing workers (planned)
└── tests/                   Cross-service tests (planned)
```

## Local development

### Requirements

- Node.js 22.12 or newer (CI uses Node.js 22)
- Python 3.11 or newer
- PostgreSQL 15 or newer

### 1. Configure PostgreSQL

Create development and test databases and a local role with access to them. The default examples expect:

```text
database: remind
test database: remind_test
user: remind
password: remind_dev
```

Use different credentials outside local development.

### 2. Start the API

From `services/api`:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
alembic upgrade head
python scripts/seed_user.py patient@example.com "Pat Patient" patient
python -m uvicorn app.main:app --reload
```

Review `.env` before starting the service. Never use the example JWT secret or database credentials in a deployed environment.

The API is served at `http://localhost:8000`; interactive API documentation is available at `http://localhost:8000/docs`.

### 3. Start the web app

From `apps/web`:

```powershell
npm ci
npm run dev
```

The web app is served at `http://localhost:3000` and expects the API at `http://localhost:8000`. Override it with `VITE_API_URL` when needed.

## Tests

Backend tests require a dedicated PostgreSQL database whose name ends in `_test`.
Override `TEST_DATABASE_URL` to select it. Each run creates a unique schema,
applies Alembic migrations, checks model/schema consistency, and removes only
that schema afterward. Uploaded test files always use a newly allocated temporary
directory, even when `STORAGE_DIR` is configured for the application.

```powershell
cd services/api
.\venv\Scripts\python.exe -m pytest
```

Frontend type-check and production build:

```powershell
cd apps/web
npm run build
```

The current backend suite covers authentication sessions, relationship and consent
enforcement, patient profiles and onboarding, source processing, memory review,
timeline delivery, graph operations, conversation safety, notifications, and
administration.

## Current limitations

Before controlled testing, the project still needs correct revision promotion,
deletion propagation, and authorized export. It also needs encrypted object
storage, background jobs, real multimodal processing, production identity controls
such as MFA, observability, and patient-grade accessibility.

See [Build plan](docs/BUILD_PLAN.md), [Build status](docs/BUILD_STATUS.md),
[Product](docs/PRODUCT.md), [Architecture](docs/ARCHITECTURE.md),
[Roadmap](docs/ROADMAP.md), and [Security](SECURITY.md) for more detail.

## Contributing

Read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a change. Safety-sensitive behavior should be introduced with tests that prove restricted, disputed, deleted, or unreviewed data cannot reach patient-facing surfaces.

## License

No open-source license has been selected yet. Until a license is added, all rights are reserved by the repository owner.

## Live Demo

Deployment in progress — link will be added on first Railway/Render deploy.
