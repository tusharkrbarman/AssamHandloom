from contextlib import contextmanager

from app.catalogue import CatalogueQuery, list_products


class FakeCursor:
    def __init__(self) -> None:
        self.statements: list[tuple[str, list[object]]] = []

    def __enter__(self) -> "FakeCursor":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def execute(self, statement: str, params: list[object]) -> None:
        self.statements.append((statement, params))

    def fetchone(self) -> dict[str, int]:
        return {"total": 1}

    def fetchall(self) -> list[dict[str, object]]:
        return [
            {
                "id": "variant-product",
                "slug": "golden-muga",
                "title": "Golden Muga",
                "silk_type": "Muga",
                "colour": "Gold",
                "price_minor": 250000,
                "currency": "INR",
                "available": True,
                "media_id": "media-1",
                "alt_text": "Golden Muga saree",
            }
        ]


class FakeConnection:
    def __init__(self) -> None:
        self.cursor_instance = FakeCursor()

    def __enter__(self) -> "FakeConnection":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def cursor(self) -> FakeCursor:
        return self.cursor_instance


class FakePool:
    def __init__(self) -> None:
        self.connection_instance = FakeConnection()

    @contextmanager
    def connection(self):
        yield self.connection_instance


def test_list_products_maps_postgres_rows_to_public_api_shape() -> None:
    pool = FakePool()

    result = list_products(
        pool,  # type: ignore[arg-type]
        CatalogueQuery(search="Muga", sort="price_asc", page=2, page_size=6),
    )

    assert result == {
        "items": [
            {
                "id": "variant-product",
                "slug": "golden-muga",
                "title": "Golden Muga",
                "silkType": "Muga",
                "colour": "Gold",
                "priceMinor": 250000,
                "currency": "INR",
                "available": True,
                "mediaId": "media-1",
                "altText": "Golden Muga saree",
            }
        ],
        "page": 2,
        "pageSize": 6,
        "total": 1,
    }
    list_sql = pool.connection_instance.cursor_instance.statements[1][0]
    assert "ORDER BY chosen_variant.price_minor ASC" in list_sql
