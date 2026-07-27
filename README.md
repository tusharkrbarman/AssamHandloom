# Luit & Loom — Phase 1 catalogue preview

This project is a read-only preview of the Luit & Loom catalogue. It is built around a PostgreSQL database and a FastAPI storefront so the visual experience can be reviewed before commerce is enabled.

The bundled twelve-product River, Reed & Gold catalogue is **sample content only**. Its people, pictures, prices, stock and provenance notes are placeholders, not verified live inventory. Records load only in preview mode, are not published, and no checkout or payment flow is available.

## Run locally

You need Python 3.12 and a local PostgreSQL 16 database. Copy `.env.example` to `.env`, choose a long local development `SECRET_KEY`, and set `DATABASE_URL` to your PostgreSQL database.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
alembic upgrade head
luit-loom-seed
uvicorn app.main:create_app --factory --reload
```

Open `http://localhost:8000`. Keep `CATALOGUE_PREVIEW_ENABLED=true` while reviewing the sample catalogue; turning it off hides every bundled record.

## Check the project

With PostgreSQL running, set `TEST_DATABASE_URL` to a disposable PostgreSQL database (for example `postgresql+psycopg://postgres@127.0.0.1:55432/luit_loom_test`) and run:

```powershell
alembic upgrade head
python -m pytest -q
python -m ruff check app tests
python -m mypy app
alembic current
```

Continuous integration runs those same checks against PostgreSQL 16. Application containerization is intentionally deferred to the final production-hardening phase; this Phase 1 preview does not add an application Dockerfile or Compose setup.
