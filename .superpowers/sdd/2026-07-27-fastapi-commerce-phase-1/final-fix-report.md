# Final hardening report

## Scope completed

- Public reads now exclude every `Product.is_sample` and `Variant.is_sample` record when preview is disabled, even when manually marked published. Preview reads retain them and apply the sample label whenever the visible product, variant, or artisan is sample-owned.
- Product-card and detail pricing share an integer-only formatter. Detail templates consume `ProductVariant.display_price`, retaining paise without division or float conversion.
- The validated seed source now uses the exact twelve specified titles and slugs, and reconciles the preview-only **River, Reed & Gold** collection with twelve ordered memberships.
- Collection sample ownership and case-insensitive slug safety are persisted in migration `0005_sample_collection_ownership`; preflight refuses legacy case-only collection conflicts before creating the index.
- Header, mobile navigation, homepage, and footer now lead to honest editorial and guidance destinations. These render through one reusable storefront page template.
- The app factory has a deterministic lifespan that disposes its engine, and readiness has regression coverage for a database failure response.

## Verification evidence

```text
90 passed in 6.59s  # initial focused hardening tests
19 passed in 2.71s  # seed collection boundary tests
105 passed in 7.53s # complete PostgreSQL test suite
All checks passed!  # Ruff app/tests/migrations
Success: no issues found in 16 source files  # mypy app
0005_sample_collection_ownership (head) # Alembic chain
```

## Environment note

The elevated Windows test process cannot access the default pytest temporary directory. Full and focused verification therefore use the workspace-safe `--basetemp C:\tmp\assam-handloom-*` setting; this does not affect application behavior or CI.
