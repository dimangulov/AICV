# Testing Patterns

**Analysis Date:** 2026-04-22

## Summary

**No automated tests exist in this repository.** The codebase is a live prototype / portfolio project that relies on manual verification plus a runtime dev console (`frontend/components/DevConsole.tsx`) for in-browser diagnostic logs and a backend `/health` endpoint for operational checks.

## Test Framework

**None configured.**

Exhaustive search results:
- No `jest.config.*`, `vitest.config.*`, `playwright.config.*`, `cypress.config.*`, `.mocharc.*` in `frontend/`
- No `pytest.ini`, `pyproject.toml` `[tool.pytest]` section, `conftest.py`, `tox.ini`, or `setup.cfg` in `backend/`
- No `tests/`, `test/`, `__tests__/`, `spec/`, or `e2e/` directories anywhere in the repo
- No `*.test.ts`, `*.test.tsx`, `*.spec.ts`, `*.spec.tsx`, `test_*.py`, or `*_test.py` files anywhere in the repo
- No `@testing-library/*`, `jest`, `vitest`, `playwright`, `cypress`, `pytest`, `unittest`, or `mock` packages listed in `frontend/package.json` devDependencies or `backend/requirements.txt`

## CI Integration

**No test step in CI.**

The only CI workflow is `.github/workflows/deploy-azure.yml` which runs on push to `main`:

- **Job `terraform-infra`** — `terraform init` / `validate` / `apply` in `infra/terraform/`
- **Job `build-backend`** — `docker build` + `docker push` to Azure Container Registry
- **Job `deploy-backend`** — `az containerapp update` to roll the new image
- **Job `deploy-frontend`** — Next.js static export deploy to Azure Static Web Apps

There is no test / lint / type-check job. `terraform validate` is the only validation gate.

The `frontend/package.json` `lint` script (`next lint`) exists but is **not invoked in CI**; it is only available locally.

## Runtime Verification (in lieu of tests)

### Backend `/health` endpoint
`backend/main.py` (`@app.get("/health")`) returns a `HealthResponse` with:
- `status`: `"healthy"` or `"degraded"`
- `ollama`: connection status or Azure OpenAI deployment name
- `qdrant`: mode (`in-memory` | `docker` | cloud URL)
- `rag_chain`: `"initialized"` or `"failed"`

### Backend `/ping` endpoint
Cold-start warmup probe at `GET /ping` — called by the frontend on page load (`ping()` in `frontend/lib/api.ts`).

### Frontend `DevConsole` component
`frontend/components/DevConsole.tsx` renders an in-page log panel fed by `onLog()` callbacks from `ChatInterface`, `VideoPlayer`, and `page.tsx`. Levels: `info`, `success`, `warning`, `error`. Pipeline step tags (0–4) mark progress through listen → RAG → inference → response.

### Local setup script
`setup-local.ps1` at repo root bootstraps a local dev environment (PowerShell) to enable manual smoke testing.

### Docker Compose
`docker-compose.yml` at repo root runs the stack locally for manual verification.

## How to Run "Tests"

No automated tests to run. Available verification commands:

**Frontend lint** (from `frontend/`):
```bash
pnpm lint        # or npm run lint — runs `next lint`
```

**Frontend type-check** (implicit during build, from `frontend/`):
```bash
pnpm build       # runs `next build` — fails on type errors (strict mode)
```

**Backend startup check** (from `backend/`, venv activated):
```bash
uvicorn main:app --reload
# then GET http://localhost:8000/health
# then GET http://localhost:8000/ping
```

**Infrastructure validation** (from `infra/terraform/`):
```bash
terraform validate
```

## Mocking

**No test mocking framework in use.**

Mock-like patterns do exist in production code for graceful degradation (not for testing):

- `backend/main.py` — `/session` endpoint returns a mock `{"session_id": "mock-session-id", "livekit_url": "", "livekit_client_token": "mock-token"}` when `LIVEAVATAR_API_KEY` is unset
- `frontend/components/VideoPlayer.tsx` — detects `session.session_id === "mock-session-id"` and falls back to a canvas placeholder stream (`startMockStream`)
- `backend/tts.py` — gTTS fallback when `AZURE_SPEECH_KEY` is unset (local dev without Azure credentials)
- `backend/rag.py` — in-memory Qdrant (`location=":memory:"`) when `QDRANT_MODE=memory`, allowing local runs without Docker / cloud

These fallbacks are runtime provider selections, not test doubles.

## Fixtures / Test Data

No fixtures directory. The RAG knowledge base source is `backend/bio.txt` (ingested at startup into Qdrant). `backend/damir_imangulov_cv.pdf` is a generated artefact (see `backend/generate_cv.py`).

## Coverage

**No coverage tooling configured.** No `coverage.py`, `pytest-cov`, `c8`, `nyc`, `istanbul`, or `vitest --coverage` setup anywhere in the repo.

## Test Types

| Type | Status |
|------|--------|
| Unit tests | Not present |
| Integration tests | Not present |
| Contract tests | Not present |
| E2E tests | Not present |
| Smoke tests | Not present (manual only via `/health` + `/ping` + DevConsole) |
| Load tests | Not present |
| Visual regression | Not present |

## Recommendations for Adding Tests

If introducing tests, the codebase shape suggests the following entry points:

**Backend (`backend/`):**
- Pin `pytest` and `pytest-asyncio` in `requirements.txt` (or migrate to `pyproject.toml`)
- Use FastAPI's `TestClient` / `httpx.AsyncClient` against the `app` in `backend/main.py`
- Unit-test pure functions first: `format_history()` in `backend/rag.py`, `UUID_RE` validation, Pydantic validators in `backend/models.py`
- Mock the LLM with a fake `RunnableSerializable` injected in place of `_rag_chain`
- Add a `tests/` directory as a sibling of the backend modules

**Frontend (`frontend/`):**
- Vitest (aligns with Next.js 16 / React 19) + `@testing-library/react` + `jsdom`
- Unit-test pure logic: `buildHistory()` in `ChatInterface.tsx`, SSE parser in `askQuestionStream()` (`frontend/lib/api.ts`), `trackEvent()` no-op guard (`frontend/lib/analytics.ts`)
- Component tests for `DevConsole` pagination and `ChatInterface` message flow
- Playwright or Cypress for E2E covering the chat → avatar speak → interrupt flow
- Co-locate tests as `Component.test.tsx` next to sources, or create `frontend/__tests__/`

**CI:**
- Add a `test` job to `.github/workflows/deploy-azure.yml` that runs before `build-backend` and `deploy-frontend`, gating deployment on test success

---

*Testing analysis: 2026-04-22*
