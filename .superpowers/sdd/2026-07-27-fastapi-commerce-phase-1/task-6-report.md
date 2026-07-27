# Task 6 report — validated sample catalogue and quality automation

## RED evidence

Before `app/seed.py` and `data/river-reed-gold.json` existed, ran:

```powershell
$env:TEST_DATABASE_URL='postgresql+psycopg://postgres@127.0.0.1:55432/luit_loom_test'
.\.venv\Scripts\python.exe -m pytest tests/unit/test_seed.py tests/integration/test_seed.py -q
```

Result: collection failed as intended with `ModuleNotFoundError: No module named 'app.seed'` in both seed test modules.

## GREEN evidence

After implementing the validated loader and deterministic catalogue, the focused safety suite passed against real PostgreSQL:

```text
5 passed in 0.50s
```

Final Phase 1 verification against `postgresql+psycopg://postgres@127.0.0.1:55432/luit_loom_test`:

```text
66 passed in 4.73s
All checks passed!                     # Ruff
Success: no issues found in 16 source files  # mypy
0002_catalogue (head)                  # Alembic current
```

The migration upgrade/current check used the Windows selector event-loop policy before invoking Alembic because psycopg's async driver cannot use the Windows Proactor loop. The test fixture also creates a fresh PostgreSQL schema and upgrades it through `head` for the test suite.

## Self-review

- The JSON contains exactly the approved 12 names: four Muga, four Pat, two Eri, and two Silk blend records.
- Every source product, artisan, media item, and provenance statement is explicitly marked sample/placeholder; provenance is `unverified` and is not persisted or exposed as verified live inventory.
- Products and variants are preview-only; normal published reads return no seeded products.
- Validation completes before the loader opens its transaction. Stable product slugs and variant SKUs make the first run create 12 products and the second update 12 without duplicates.
- Prices are positive integer INR minor units; required commerce data, unique slugs/SKUs, sample artisans, and placeholder media are verified by tests.
- CI uses PostgreSQL 16 and runs migrations, the complete test suite, Ruff, and mypy without repository secrets.
- README explains the preview safety boundary and precise local commands. It explicitly defers application containerization to final production hardening.
- `git diff --check` reported no whitespace errors.

## Concerns

- Direct `alembic` CLI execution on this Windows environment needs a selector event-loop policy for psycopg async compatibility. This does not affect Linux CI; the clean PostgreSQL schema upgrade is exercised by tests and verified locally through the compatible wrapper.
- The current persistence model has no provenance table. Accordingly, source provenance remains explicitly labelled, unverified sample metadata and is deliberately not promoted into a verified public claim.

## Fix round 1/5 — seed evolution and validation hardening

### RED evidence

Focused seed tests initially produced six expected failures:

- duplicate media `display_order` and case-folded slug duplicates passed validation;
- a SKU change left 13 variants instead of 12;
- a renamed source artisan left the old sample profile behind;
- invalid duplicate media reached PostgreSQL and raised a unique-constraint error after writes began;
- case-only slug/SKU/artisan changes created a duplicate product.

### GREEN evidence

After the reconciliation and boundary-validation changes:

```text
11 passed in 1.08s  # focused seed unit + PostgreSQL integration tests
72 passed in 4.53s # complete Phase 1 suite
All checks passed! # Ruff
Success: no issues found in 16 source files # mypy
0002_catalogue (head) # Alembic current
```

### Self-review

- Slugs are trimmed/lower-cased and SKUs trimmed/upper-cased before validation; product titles are not transformed.
- Duplicate slugs, SKUs, artisan identities, featured ranks, and per-product media display orders are rejected before `session.begin`.
- Incoming SKU resolution occurs before stale **preview** variants are deleted. Published or otherwise non-preview variants are not removed.
- The loader captures artisan IDs previously associated with the incoming seeded slugs, reassigns the source products, then deletes only unreferenced sample artisan profiles. Profiles still referenced by unrelated products remain intact.
- Added front-loaded checks for negative inventory and exactly one primary placeholder-media record per product.

### Concerns

- SQLite-free PostgreSQL integration coverage exercises the revised behavior. As before, direct Alembic CLI execution on this Windows host requires a selector event loop for psycopg async compatibility; Linux CI is unaffected.

## Fix round 2/5 — explicit sample ownership and collision safety

### RED evidence

The new collision regression module initially failed collection because `SeedCollisionError` did not exist. The tests define the required behavior for non-sample product/variant collisions, preservation of an unrelated preview variant on a sample product, and case-insensitive legacy key collisions.

### GREEN evidence

```text
12 passed in 1.57s # focused PostgreSQL seed suite
77 passed in 5.63s # complete Phase 1 suite
All checks passed! # Ruff
Success: no issues found in 16 source files # mypy
0003_sample_catalogue_ownership (head) # Alembic upgrade/current
```

### Self-review

- Migration `0003_sample_catalogue_ownership` adds `products.is_sample` and `variants.is_sample`, both non-null and false by default. It intentionally does not infer ownership from preview state or artisan data.
- The validated loader sets both flags only for its created or already seed-owned rows.
- Before any mutation, canonical lower-case slug and upper-case SKU lookups reject all matching non-sample rows with clear `SeedCollisionError` messages. Product, media, artisan, publication state, price, and inventory stay untouched because the transaction has not mutated state.
- Stale-variant reconciliation now deletes only `Variant.is_sample=true` variants on `Product.is_sample=true` products. An unrelated preview variant survives a source SKU change.
- Sample ownership remains internal persistence data; current public sample labelling already derives safely from preview/artisan state and does not need a schema expansion.

### Concerns

- Existing historical rows that predate migration `0003` remain `is_sample=false` by design. The loader safely reports a collision rather than guessing ownership; operators should explicitly mark or replace legacy preview data before reseeding it.
