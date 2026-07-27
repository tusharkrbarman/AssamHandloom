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

## Fix round 1/5

### Findings addressed

- `list_collections()` now filters collection membership through the same product-and-visible-variant
  publication predicate as product queries. A published collection therefore cannot return draft
  members, and preview members appear only when preview is enabled.
- Preview products now explicitly set the public sample marker even when no artisan is assigned or
  the associated artisan is not itself a sample record. Artisan sample status continues to mark
  published sample products.
- `Variant.currency` now validates against the embedded ISO 4217 code registry at the SQLAlchemy
  write boundary. The PostgreSQL migration adds a `^[A-Z]{3}$` check constraint as a defence in
  depth safeguard for writes that bypass the model.

### Regression evidence

#### RED

Before the fix, ran:

```text
TEST_DATABASE_URL=postgresql+psycopg://postgres@127.0.0.1:55432/luit_loom_test
.venv\\Scripts\\python.exe -m pytest tests/unit/catalog/test_service.py tests/integration/catalog/test_repository.py -q
```

Result: 4 failed, 15 passed. The failures demonstrated the missing preview sample label, absent
ISO write-boundary validation, visible preview/draft collection members, and absent PostgreSQL
lowercase-currency protection.

#### GREEN

Focused regressions after the implementation:

```text
19 passed in 0.69s
```

Final verification:

```text
ruff check app/catalog migrations/versions/0002_catalogue.py tests/unit/catalog tests/integration/catalog
All checks passed!

mypy app
Success: no issues found in 10 source files

pytest tests/unit/catalog tests/integration/catalog -q
19 passed in 0.80s
```

### Files changed

- `app/catalog/models.py`
- `app/catalog/repository.py`
- `app/catalog/service.py`
- `migrations/versions/0002_catalogue.py`
- `tests/unit/catalog/test_service.py`
- `tests/integration/catalog/test_repository.py`

### Self-review

- The collection association query filters at the association level, so hidden products are not
  returned as collection members rather than merely being represented as unloaded relations.
- The preview label is derived from product publication state, independent of artisan identity.
- The model accepts only uppercase codes in the supplied ISO 4217 registry; PostgreSQL protects
  the three-character uppercase format if a write bypasses SQLAlchemy.
- The revised `0002_catalogue` migration remains consistent with the ORM because Task 2 is
  unreleased, and each PostgreSQL integration run applies it to a fresh isolated schema.

## Fix round 2/5

### Finding addressed

The PostgreSQL constraint previously required only an uppercase three-character currency value, so
a direct or bulk SQL write could store an unknown value such as `ZZZ`. The shared
`app.catalog.currencies` registry now produces a PostgreSQL `IN (...)` membership constraint. Both
the ORM model metadata and the unreleased `0002_catalogue` migration use that same source, while
the existing format constraint remains as a clear companion invariant.

### RED

Before adding the database membership constraint, ran:

```text
TEST_DATABASE_URL=postgresql+psycopg://postgres@127.0.0.1:55432/luit_loom_test
.venv\\Scripts\\python.exe -m pytest tests/integration/catalog/test_repository.py -k unknown_uppercase_currency -q

1 failed, 10 deselected in 0.47s
```

The direct SQL update to `ZZZ` did not raise `IntegrityError`.

### GREEN

After adding the shared membership predicate to the ORM and migration:

```text
1 passed, 10 deselected in 0.28s
```

The integration suite also explicitly persists `INR` and reads it back from PostgreSQL.

Final verification:

```text
pytest tests/unit/catalog tests/integration/catalog -q
21 passed in 0.81s

ruff check app/catalog migrations/versions/0002_catalogue.py tests/unit/catalog tests/integration/catalog
All checks passed!

mypy app
Success: no issues found in 11 source files
```

### Files changed

- `app/catalog/currencies.py`
- `app/catalog/models.py`
- `migrations/versions/0002_catalogue.py`
- `tests/integration/catalog/test_repository.py`

### Self-review

- Normal ORM writes remain protected by the same ISO registry as before, and direct/bulk SQL
  writes are now rejected unless their value is an ISO 4217 member.
- `INR` persistence is covered explicitly in PostgreSQL integration testing.
- The generated SQL membership list is deterministic because the shared registry is sorted.
- Reusing application data from the migration is acceptable here because revision `0002` is
  explicitly unreleased; once released, registry changes should use a new migration rather than
  mutate historical DDL behaviour.
