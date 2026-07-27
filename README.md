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

Continuous integration runs those same checks against PostgreSQL 16.

## Deploy the preview on Render

The included `render.yaml` creates a free Docker web service and a free
PostgreSQL database in Singapore:

1. Push this branch to GitHub.
2. In Render, choose **New > Blueprint** and connect this repository.
3. Select `render.yaml` and apply the Blueprint.
4. Wait for `/health/ready` to pass, then open the generated `onrender.com` URL.

The container applies database migrations and idempotently loads the clearly
labelled sample catalogue before starting the site. Render generates the
application secret and supplies the database and public URLs; no credentials
are committed.

Render's free web service sleeps after 15 minutes without traffic and can take
about a minute to wake. Its free PostgreSQL database expires 30 days after
creation, so this setup is for a temporary demo rather than a production store.

To check the image locally:

```powershell
docker build --tag luit-and-loom:render .
```
