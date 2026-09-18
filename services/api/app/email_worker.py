from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from .email import process_outbox
from .settings import Settings


def main() -> None:
    settings = Settings.from_env()
    if not settings.database_url:
        raise SystemExit("DATABASE_URL is required")
    pool = ConnectionPool(
        conninfo=settings.database_url,
        min_size=1,
        max_size=1,
        timeout=5,
        kwargs={"row_factory": dict_row},
        open=False,
    )
    pool.open(wait=True)
    try:
        print(process_outbox(pool, settings))
    finally:
        pool.close()


if __name__ == "__main__":
    main()
