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
