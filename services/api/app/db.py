from psycopg_pool import ConnectionPool
from psycopg.rows import dict_row


def create_pool(database_url: str) -> ConnectionPool:
    return ConnectionPool(
        conninfo=database_url,
        min_size=1,
        max_size=10,
        timeout=5,
        kwargs={"row_factory": dict_row},
        open=False,
    )
