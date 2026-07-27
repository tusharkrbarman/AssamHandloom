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
