from contextlib import contextmanager

from app.catalogue import (
    CatalogueQuery,
    catalogue_query_from_params,
    get_collection,
    get_product,
    list_collections,
    list_products,
)


class FakeCursor:
    def __init__(
        self,
        fetchone_results: list[dict[str, object] | None] | None = None,
        fetchall_results: list[list[dict[str, object]]] | None = None,
    ) -> None:
        self.statements: list[tuple[str, list[object]]] = []
        self._fetchone_results = list(fetchone_results or [{"total": 1}])
        self._fetchall_results = list(
            fetchall_results
            or [
                [
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
            ]
        )

    def __enter__(self) -> "FakeCursor":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def execute(self, statement: str, params: list[object] | None = None) -> None:
        self.statements.append((statement, list(params or [])))

    def fetchone(self) -> dict[str, object] | None:
        return self._fetchone_results.pop(0) if self._fetchone_results else None

    def fetchall(self) -> list[dict[str, object]]:
        return self._fetchall_results.pop(0) if self._fetchall_results else []


class FakeConnection:
    def __init__(self, cursor_instance: FakeCursor | None = None) -> None:
        self.cursor_instance = cursor_instance or FakeCursor()

    def __enter__(self) -> "FakeConnection":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def cursor(self) -> FakeCursor:
        return self.cursor_instance


class FakePool:
    def __init__(self, cursor_instance: FakeCursor | None = None) -> None:
        self.connection_instance = FakeConnection(cursor_instance)

    @contextmanager
    def connection(self):
        yield self.connection_instance


def test_html_query_defaults_invalid_sort_and_caps_page_size() -> None:
    query = catalogue_query_from_params({"q": "  Muga  ", "sort": "nope", "page_size": "99"})

    assert query.search == "Muga"
    assert query.sort == "featured"
    assert query.page_size == 24


def test_html_query_uses_q_when_search_is_blank() -> None:
    query = catalogue_query_from_params({"search": "   ", "q": " Pat "})

    assert query.search == "Pat"


def test_html_query_parses_aliases_and_truthy_available_only() -> None:
    query = catalogue_query_from_params(
        {
            "search": "  Eri Silk  ",
            "silk_type": "  Eri  ",
            "colour": " Ivory ",
            "occasion": " Bridal ",
            "available_only": "yes",
            "page": "3",
        },
        collection_slug="  festive-edit  ",
    )

    assert query == CatalogueQuery(
        search="Eri Silk",
        silk_type="Eri",
        colour="Ivory",
        occasion="Bridal",
        available_only=True,
        sort="featured",
        page=3,
        page_size=12,
        collection_slug="festive-edit",
    )


def test_get_collection_maps_public_fields() -> None:
    pool = fake_pool()

    result = get_collection(pool, "river-edit")  # type: ignore[arg-type]

    assert result == {
        "id": "collection-river",
        "slug": "river-edit",
        "title": "River Edit",
        "description": "A material conversation.",
    }


def test_list_collections_filters_to_published_and_orders_results() -> None:
    pool = FakePool(
        FakeCursor(
            fetchall_results=[
                [
                    {
                        "id": "collection-river",
                        "slug": "river-edit",
                        "title": "River Edit",
                        "description": "A material conversation.",
                    },
                    {
                        "id": "collection-festive",
                        "slug": "festive-edit",
                        "title": "Festive Edit",
                        "description": "",
                    },
                ]
            ]
        )
    )

    result = list_collections(pool)  # type: ignore[arg-type]

    assert result == [
        {
            "id": "collection-river",
            "slug": "river-edit",
            "title": "River Edit",
            "description": "A material conversation.",
        },
        {
            "id": "collection-festive",
            "slug": "festive-edit",
            "title": "Festive Edit",
            "description": "",
        },
    ]
    sql, params = pool.connection_instance.cursor_instance.statements[0]
    assert "WHERE publication_state = 'published'" in sql
    assert "ORDER BY display_order ASC, id ASC" in sql
    assert params == []


def test_get_product_maps_public_detail_variants_and_media() -> None:
    pool = FakePool(
        FakeCursor(
            fetchone_results=[
                {
                    "id": "product-golden-muga",
                    "slug": "golden-muga",
                    "title": "Golden Muga",
                    "description": "Handwoven in Assam.",
                    "silk_type": "Muga",
                    "colour": "Gold",
                    "occasion": "Wedding",
                }
            ],
            fetchall_results=[
                [
                    {
                        "id": "variant-1",
                        "sku": "MUGA-001",
                        "title": "Classic Drape",
                        "price_minor": 250000,
                        "currency": "INR",
                        "publication_state": "published",
                        "quantity": 3,
                    },
                    {
                        "id": "variant-2",
                        "sku": "MUGA-002",
                        "title": "Lightweight Drape",
                        "price_minor": 260000,
                        "currency": "INR",
                        "publication_state": "published",
                        "quantity": 0,
                    },
                ],
                [
                    {
                        "id": "media-1",
                        "object_key": "products/golden-muga/1.jpg",
                        "alt_text": "Golden Muga saree",
                        "content_type": "image/jpeg",
                    },
                    {
                        "id": "media-2",
                        "object_key": "products/golden-muga/2.jpg",
                        "alt_text": "Border detail",
                        "content_type": "image/jpeg",
                    },
                ],
            ],
        )
    )

    result = get_product(pool, "golden-muga")  # type: ignore[arg-type]

    assert result == {
        "id": "product-golden-muga",
        "slug": "golden-muga",
        "title": "Golden Muga",
        "description": "Handwoven in Assam.",
        "silkType": "Muga",
        "colour": "Gold",
        "occasion": "Wedding",
        "available": True,
        "variants": [
            {
                "id": "variant-1",
                "sku": "MUGA-001",
                "title": "Classic Drape",
                "priceMinor": 250000,
                "currency": "INR",
                "available": True,
            },
            {
                "id": "variant-2",
                "sku": "MUGA-002",
                "title": "Lightweight Drape",
                "priceMinor": 260000,
                "currency": "INR",
                "available": False,
            },
        ],
        "media": [
            {
                "id": "media-1",
                "url": "",
                "altText": "Golden Muga saree",
                "contentType": "image/jpeg",
            },
            {
                "id": "media-2",
                "url": "",
                "altText": "Border detail",
                "contentType": "image/jpeg",
            },
        ],
    }


def test_get_product_returns_none_for_missing_or_draft_product() -> None:
    pool = FakePool(FakeCursor(fetchone_results=[None], fetchall_results=[]))

    assert get_product(pool, "missing-slug") is None  # type: ignore[arg-type]


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
    count_sql = pool.connection_instance.cursor_instance.statements[0][0]
    list_sql = pool.connection_instance.cursor_instance.statements[1][0]
    assert "p.publication_state = 'published'" in count_sql
    assert "p.archived_at IS NULL" in count_sql
    assert "p.publication_state = 'published'" in list_sql
    assert "p.archived_at IS NULL" in list_sql
    assert "ORDER BY chosen_variant.price_minor ASC" in list_sql


def fake_pool() -> FakePool:
    return FakePool(
        FakeCursor(
            fetchone_results=[
                {
                    "id": "collection-river",
                    "slug": "river-edit",
                    "title": "River Edit",
                    "description": "A material conversation.",
                }
            ],
            fetchall_results=[],
        )
    )
