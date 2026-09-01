from dataclasses import dataclass

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
