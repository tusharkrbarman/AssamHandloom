# Task 2 report: catalogue persistence and publication rules

## Implementation

- Added the catalogue ORM domain: products, variants, collections and their membership,
  product media, and approved public artisan profiles.
- Added immutable query and public response schemas, including integer-minor-unit price display.
- Added repository queries that exclude drafts, gate previews on the explicit flag, require a
  visible variant, apply filters, and use product IDs as pagination tie-breakers.
- Added a service projection layer that keeps publication checks at the public boundary and
  propagates artisan sample status as the explicit `Sample` label.
- Added the `0002_catalogue` PostgreSQL migration with UUID keys, timezone-aware timestamps,
  unique product slugs/SKUs, and money/inventory check constraints.

## Files

- `app/catalog/__init__.py`
- `app/catalog/models.py`
- `app/catalog/schemas.py`
- `app/catalog/repository.py`
- `app/catalog/service.py`
- `migrations/versions/0002_catalogue.py`
- `tests/unit/catalog/test_service.py`
- `tests/integration/catalog/test_repository.py`
- `.gitignore` (excludes generated Python and test caches)

## Test evidence

### RED

Before catalogue implementation, ran:

```text
TEST_DATABASE_URL=postgresql+psycopg://postgres@127.0.0.1:55432/luit_loom_test
.venv\\Scripts\\python.exe -m pytest tests/unit/catalog/test_service.py -q
```

Result: collection failed with `ModuleNotFoundError: No module named 'app.catalog'`, the expected
missing-catalogue-types failure.

### GREEN

After the minimal domain and service implementation, the focused unit suite passed:

```text
7 passed in 0.07s
```

The complete catalogue suite was then run against the real PostgreSQL 16.14 test database. The
test fixture creates an isolated schema and applies Alembic through `upgrade(..., "head")`, which
exercises the new migration before every session-scoped integration run:

```text
15 passed in 0.74s
```

Final static verification:

```text
ruff check app/catalog migrations/versions/0002_catalogue.py tests/unit/catalog tests/integration/catalog
All checks passed!

mypy app
Success: no issues found in 10 source files
```

## Self-review

- Draft products and variants cannot appear through either repository or service projection.
- Preview products and variants appear only when `preview_enabled` is true.
- PostgreSQL enforces slug/SKU uniqueness, non-negative prices/inventory, and compare-at prices
  that are not lower than the sale price.
- Price sort and featured/newest sort add `Product.id` as an explicit stable pagination tie-breaker.
- Generated caches are ignored and will not be included in the task commit.

## Concerns

No known functional concerns. Price formatting currently treats stored currency values as two-decimal
minor units; an ISO-currency exponent registry remains intentionally deferred with localization.
