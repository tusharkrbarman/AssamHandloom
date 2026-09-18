from os import environ
from pathlib import Path

import psycopg


MIGRATIONS = Path(__file__).resolve().parents[1] / "migrations"


def main() -> None:
    database_url = environ.get("DATABASE_URL")
    if not database_url:
        raise SystemExit("DATABASE_URL is required")

    with psycopg.connect(database_url) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
              version text PRIMARY KEY,
              applied_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        for path in sorted(MIGRATIONS.glob("*.sql")):
            version = path.name
            applied = connection.execute(
                "SELECT 1 FROM schema_migrations WHERE version = %s",
                (version,),
            ).fetchone()
            if applied:
                continue
            connection.execute(path.read_text(encoding="utf-8"))
            connection.execute(
                "INSERT INTO schema_migrations (version) VALUES (%s)",
                (version,),
            )
            print(f"applied {version}")


if __name__ == "__main__":
    main()
