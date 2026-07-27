# Render Container Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the existing FastAPI/PostgreSQL catalogue preview deployable to Render from one Docker image and one Blueprint.

**Architecture:** Render builds the repository Dockerfile, provisions PostgreSQL, and supplies service configuration through environment variables. The container migrates and idempotently seeds the demo database before starting Uvicorn; the existing readiness endpoint gates deployment health.

**Tech Stack:** Python 3.12, FastAPI, Pydantic Settings, SQLAlchemy/Psycopg, Alembic, Docker, Render Blueprints

## Global Constraints

- Keep the application a read-only twelve-product sample catalogue.
- Use Render free plans for both the web service and PostgreSQL.
- Deploy both resources in the Singapore region.
- Do not commit secrets or database credentials.
- Do not add dependencies.
- Do not add checkout, payments, accounts, inventory management, or order management.
- The user explicitly waived a test-driven implementation sequence; verification follows implementation.

---

### Task 1: Accept Render Runtime Configuration

**Files:**
- Modify: `app/config.py`
- Modify: `tests/integration/test_health.py`

**Interfaces:**
- Consumes: Render `DATABASE_URL=postgresql://...` and `RENDER_EXTERNAL_URL=https://...`
- Produces: `Settings.database_url` using `postgresql+psycopg://...` and a validated `Settings.public_base_url`

- [ ] **Step 1: Normalize Render's database URL and accept its external URL**

Update `app/config.py` to import `AliasChoices` and `field_validator`, enable
field-name population, and define:

```python
public_base_url: AnyHttpUrl = Field(
    validation_alias=AliasChoices(
        "public_base_url",
        "PUBLIC_BASE_URL",
        "RENDER_EXTERNAL_URL",
    )
)

@field_validator("database_url")
@classmethod
def normalize_database_url(cls, value: str) -> str:
    if value.startswith("postgresql://"):
        return value.replace("postgresql://", "postgresql+psycopg://", 1)
    return value
```

Keep the existing PostgreSQL-only production validator unchanged after this
normalization.

- [ ] **Step 2: Add compatibility checks**

Add tests that call `Settings.model_validate` with Render-style uppercase
values and assert:

```python
assert settings.database_url == "postgresql+psycopg://luit:secret@db:5432/luit_loom"
assert str(settings.public_base_url) == "https://luit-and-loom.onrender.com/"
```

Keep the existing tests that reject an empty secret and non-PostgreSQL
production database.

- [ ] **Step 3: Run focused verification**

Run:

```powershell
python -m pytest tests/integration/test_health.py -q
python -m ruff check app/config.py tests/integration/test_health.py
python -m mypy app/config.py
```

Expected: all commands exit successfully.

### Task 2: Add the Container and Render Blueprint

**Files:**
- Create: `Dockerfile`
- Create: `.dockerignore`
- Create: `render.yaml`
- Modify: `.github/workflows/quality.yml`
- Modify: `README.md`

**Interfaces:**
- Consumes: installed `alembic`, `luit-loom-seed`, `uvicorn`, Render `PORT`, and Blueprint-provided environment variables
- Produces: an HTTP service on `0.0.0.0:${PORT}` with readiness at `/health/ready`

- [ ] **Step 1: Create the production image**

Create a Python 3.12 slim image that:

```dockerfile
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=10000

WORKDIR /app

COPY pyproject.toml ./
COPY app ./app
RUN pip install --no-cache-dir .

COPY alembic.ini ./
COPY migrations ./migrations

RUN addgroup --system app && \
    adduser --system --ingroup app app && \
    chown -R app:app /app

USER app
EXPOSE 10000

CMD ["sh", "-c", "alembic upgrade head && luit-loom-seed && exec uvicorn app.main:create_app --factory --host 0.0.0.0 --port ${PORT:-10000}"]
```

- [ ] **Step 2: Keep the build context small**

Create `.dockerignore` excluding Git state, worktrees, virtual environments,
environment files, caches, tests, documentation, Node artifacts, and local
test reports.

- [ ] **Step 3: Create the free Render Blueprint**

Create `render.yaml` with:

```yaml
services:
  - type: web
    name: luit-and-loom
    runtime: docker
    plan: free
    region: singapore
    healthCheckPath: /health/ready
    autoDeployTrigger: checksPass
    envVars:
      - key: ENVIRONMENT
        value: production
      - key: CATALOGUE_PREVIEW_ENABLED
        value: "true"
      - key: DATABASE_URL
        fromDatabase:
          name: luit-and-loom-db
          property: connectionString
      - key: PUBLIC_BASE_URL
        fromService:
          type: web
          name: luit-and-loom
          envVarKey: RENDER_EXTERNAL_URL
      - key: SECRET_KEY
        generateValue: true

databases:
  - name: luit-and-loom-db
    plan: free
    region: singapore
    postgresMajorVersion: "16"
    databaseName: luit_loom
    user: luit_loom
    ipAllowList: []
```

- [ ] **Step 4: Document deployment**

Replace the README statement that containerization is deferred. Add:

```text
1. Push the branch to GitHub.
2. In Render, choose New > Blueprint and connect this repository.
3. Select render.yaml and apply the Blueprint.
4. Wait for /health/ready to pass, then open the generated onrender.com URL.
```

State clearly that startup migrates and loads sample preview records, and that
the free service can cold-start after inactivity.

- [ ] **Step 5: Build the image**

Add the image build to the existing quality workflow:

```yaml
- name: Build deployment image
  run: docker build --tag luit-and-loom:ci .
```

Run locally when a Docker engine is available:

```powershell
docker build --tag luit-and-loom:render .
```

Expected: image build exits successfully.

### Task 3: Verify and Publish

**Files:**
- Verify all changed files
- Commit all implementation changes

**Interfaces:**
- Consumes: local PostgreSQL test database and Docker
- Produces: pushed GitHub branch ready for Render Blueprint deployment

- [ ] **Step 1: Run complete verification**

Run the repository's existing PostgreSQL-backed test suite, Ruff, mypy, and
Alembic current check:

```powershell
python -m pytest -q
python -m ruff check app tests migrations
python -m mypy app
alembic current
```

Expected: 105 existing tests plus the new configuration checks pass, Ruff and
mypy report no issues, and Alembic reports
`0005_sample_collection_ownership (head)`.

- [ ] **Step 2: Smoke-test the container**

Start the built image with a PostgreSQL URL reachable from the container and
production environment values. Confirm:

```text
GET /health/ready -> 200
GET / -> 200
```

Stop and remove only the temporary smoke-test container after the check.

- [ ] **Step 3: Review and commit**

Run `git diff --check`, inspect the final diff, and commit:

```text
feat: deploy catalogue preview on Render
```

- [ ] **Step 4: Push**

Push `feature/fastapi-commerce-phase-1` to `origin`, then provide the user the
Render Blueprint creation URL and the exact remaining dashboard action.
