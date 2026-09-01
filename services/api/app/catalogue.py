from dataclasses import dataclass
from typing import Mapping

from fastapi import HTTPException
from psycopg_pool import ConnectionPool


SORT_SQL = {
    "featured": "p.featured_rank ASC, p.created_at DESC, p.id ASC",
    "newest": "p.created_at DESC, p.id ASC",
    "price_asc": "chosen_variant.price_minor ASC, p.id ASC",
    "price_desc": "chosen_variant.price_minor DESC, p.id ASC",
}


def format_money(price_minor: int, currency: str) -> str:
    if price_minor < 0:
        raise ValueError("price cannot be negative")
    major, minor = divmod(price_minor, 100)
    amount = f"{major:,}" + (f".{minor:02d}" if minor else "")
    symbol = {"INR": "₹", "USD": "$", "GBP": "£", "EUR": "€"}.get(currency)
    return f"{symbol}{amount}" if symbol else f"{currency} {amount}"


@dataclass(frozen=True, slots=True)
class CatalogueQuery:
    search: str | None = None
    silk_type: str | None = None
    colour: str | None = None
    occasion: str | None = None
    available_only: bool = False
    sort: str = "featured"
    page: int = 1
    page_size: int = 12
    collection_slug: str | None = None


def _normalise(value: str | None) -> str | None:
    clean = " ".join((value or "").split())
    if not clean:
        return None
    if len(clean) > 160:
        raise HTTPException(status_code=422, detail="Query value is too long.")
    return clean


def _like(value: str) -> str:
    return "%" + value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


def _normalise_optional(value: str | None, *, limit: int | None = None) -> str | None:
    clean = _normalise(value)
    if clean is None or limit is None:
        return clean
    return clean[:limit]


def _int_param(value: str | None, *, default: int, minimum: int = 1, maximum: int | None = None) -> int:
    try:
        parsed = int((value or "").strip() or default)
    except ValueError:
        return default
    if parsed < minimum:
        return default
    if maximum is not None and parsed > maximum:
        return maximum
    return parsed


def catalogue_query_from_params(
    params: Mapping[str, str], collection_slug: str | None = None
) -> CatalogueQuery:
    sort = _normalise(params.get("sort")) or "featured"
    if sort not in SORT_SQL:
        sort = "featured"
    return CatalogueQuery(
        search=_normalise(params.get("search") or params.get("q")),
        silk_type=_normalise_optional(params.get("silk_type"), limit=80),
        colour=_normalise_optional(params.get("colour"), limit=80),
        occasion=_normalise_optional(params.get("occasion"), limit=80),
        available_only=(params.get("available_only") or "").strip().lower() in {"1", "true", "yes", "on"},
        sort=sort,
        page=_int_param(params.get("page"), default=1),
        page_size=_int_param(params.get("page_size"), default=12, maximum=24),
        collection_slug=_normalise_optional(collection_slug or params.get("collection_slug"), limit=80),
    )


def _filters(query: CatalogueQuery) -> tuple[str, list[object]]:
    clauses = ["p.publication_state = 'published'", "p.archived_at IS NULL"]
    params: list[object] = []

    search = _normalise(query.search)
    if search:
        value = _like(search)
        clauses.append(
            "(p.title LIKE %s ESCAPE '\\' OR p.description LIKE %s ESCAPE '\\' "
            "OR p.silk_type LIKE %s ESCAPE '\\')"
        )
        params.extend([value, value, value])
    for column, value in (
        ("p.silk_type", query.silk_type),
        ("p.colour", query.colour),
        ("p.occasion", query.occasion),
    ):
        clean = _normalise(value)
        if clean:
            clauses.append(f"{column} = %s")
            params.append(clean)
    if query.available_only:
        clauses.append(
            "EXISTS ("
            "SELECT 1 FROM variants available_variant "
            "JOIN inventory_items available_stock "
            "ON available_stock.variant_id = available_variant.id "
            "WHERE available_variant.product_id = p.id "
            "AND available_variant.publication_state = 'published' "
            "AND available_stock.quantity > 0"
            ")"
        )
    collection_slug = _normalise(query.collection_slug)
    if collection_slug:
        clauses.append(
            "EXISTS ("
            "SELECT 1 FROM collection_products membership "
            "JOIN collections collection ON collection.id = membership.collection_id "
            "WHERE membership.product_id = p.id "
            "AND collection.slug = %s "
            "AND collection.publication_state = 'published'"
            ")"
        )
        params.append(collection_slug)
    return " AND ".join(clauses), params


def _row_to_product(row: dict[str, object]) -> dict[str, object]:
    return {
        "id": row["id"],
        "slug": row["slug"],
        "title": row["title"],
        "silkType": row["silk_type"],
        "colour": row["colour"],
        "priceMinor": row["price_minor"],
        "currency": row["currency"],
        "available": bool(row["available"]),
        "mediaId": row["media_id"],
        "altText": row["alt_text"],
    }


def _row_to_collection(row: Mapping[str, object]) -> dict[str, object]:
    return {
        "id": row["id"],
        "slug": row["slug"],
        "title": row["title"],
        "description": row["description"],
    }


def _row_to_variant(row: Mapping[str, object]) -> dict[str, object]:
    return {
        "id": row["id"],
        "sku": row["sku"],
        "title": row["title"],
        "priceMinor": row["price_minor"],
        "currency": row["currency"],
        "available": int(row["quantity"]) > 0,
    }


def _row_to_media(row: Mapping[str, object]) -> dict[str, object]:
    return {
        "id": row["id"],
        "url": "",
        "altText": row["alt_text"],
        "contentType": row["content_type"],
    }


def list_collections(pool: ConnectionPool) -> list[dict[str, object]]:
    sql = """
        SELECT id, slug, title, description
        FROM collections
        WHERE publication_state = 'published'
        ORDER BY display_order ASC, id ASC
    """
    with pool.connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql, [])
            return [_row_to_collection(row) for row in cursor.fetchall()]


def get_collection(pool: ConnectionPool, slug: str) -> dict[str, object] | None:
    sql = """
        SELECT id, slug, title, description
        FROM collections
        WHERE publication_state = 'published' AND slug = %s
        ORDER BY display_order ASC, id ASC
        LIMIT 1
    """
    with pool.connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql, [_normalise(slug)])
            row = cursor.fetchone()
    return _row_to_collection(row) if row else None


def get_product(pool: ConnectionPool, slug: str) -> dict[str, object] | None:
    product_sql = """
        SELECT id, slug, title, description, silk_type, colour, occasion
        FROM products
        WHERE publication_state = 'published' AND archived_at IS NULL AND slug = %s
        LIMIT 1
    """
    variants_sql = """
        SELECT v.id, v.sku, v.title, v.price_minor, v.currency,
               v.publication_state, stock.quantity
        FROM variants v
        JOIN inventory_items stock ON stock.variant_id = v.id
        WHERE v.product_id = %s AND v.publication_state = 'published'
        ORDER BY v.price_minor ASC, v.id ASC
    """
    media_sql = """
        SELECT id, object_key, alt_text, content_type
        FROM product_media
        WHERE product_id = %s
        ORDER BY display_order ASC, id ASC
    """
    with pool.connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(product_sql, [_normalise(slug)])
            row = cursor.fetchone()
            if not row:
                return None
            cursor.execute(variants_sql, [row["id"]])
            variant_rows = cursor.fetchall()
            cursor.execute(media_sql, [row["id"]])
            media_rows = cursor.fetchall()
    variants = [_row_to_variant(variant_row) for variant_row in variant_rows]
    return {
        "id": row["id"],
        "slug": row["slug"],
        "title": row["title"],
        "description": row["description"],
        "silkType": row["silk_type"],
        "colour": row["colour"],
        "occasion": row["occasion"],
        "available": any(bool(variant["available"]) for variant in variants),
        "variants": variants,
        "media": [_row_to_media(media_row) for media_row in media_rows],
    }


def list_products(pool: ConnectionPool, query: CatalogueQuery) -> dict[str, object]:
    if query.sort not in SORT_SQL:
        raise HTTPException(status_code=422, detail="The requested sort value is not supported.")
    where, params = _filters(query)
    chosen_variant_join = """
        JOIN variants chosen_variant ON chosen_variant.id = (
            SELECT candidate.id
            FROM variants candidate
            WHERE candidate.product_id = p.id
              AND candidate.publication_state = 'published'
            ORDER BY candidate.price_minor ASC, candidate.id ASC
            LIMIT 1
        )
    """
    count_sql = f"SELECT COUNT(*) AS total FROM products p {chosen_variant_join} WHERE {where}"
    list_sql = f"""
        SELECT p.id, p.slug, p.title, p.silk_type, p.colour,
          chosen_variant.price_minor, chosen_variant.currency,
          EXISTS (
            SELECT 1
            FROM variants available_variant
            JOIN inventory_items available_stock
              ON available_stock.variant_id = available_variant.id
            WHERE available_variant.product_id = p.id
              AND available_variant.publication_state = 'published'
              AND available_stock.quantity > 0
          ) AS available,
          primary_media.id AS media_id, primary_media.alt_text
        FROM products p
        {chosen_variant_join}
        LEFT JOIN product_media primary_media ON primary_media.id = (
          SELECT media.id
          FROM product_media media
          WHERE media.product_id = p.id
          ORDER BY media.display_order ASC, media.id ASC
          LIMIT 1
        )
        WHERE {where}
        ORDER BY {SORT_SQL[query.sort]}
        LIMIT %s OFFSET %s
    """
    offset = (query.page - 1) * query.page_size
    with pool.connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(count_sql, params)
            total_row = cursor.fetchone()
            cursor.execute(list_sql, [*params, query.page_size, offset])
            rows = cursor.fetchall()
    return {
        "items": [_row_to_product(row) for row in rows],
        "page": query.page,
        "pageSize": query.page_size,
        "total": int(total_row["total"] if total_row else 0),
    }
