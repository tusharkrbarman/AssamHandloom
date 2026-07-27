# Render Seed Package Hotfix Design

## Problem

The Render container exits after migrations because `luit-loom-seed` cannot
find `river-reed-gold.json`. The console script imports `app.seed` from the
installed wheel, where `Path(__file__).parents[1] / "data"` resolves to
`site-packages/data`. The catalogue currently lives at repository-level
`data/`, outside the `app` package, so it is absent from that location.

## Fix

Move the catalogue to `app/data/river-reed-gold.json` and resolve it with
`Path(__file__).parent / "data" / "river-reed-gold.json"`. Hatchling already
packages files below `app`, so the source checkout and installed wheel use the
same package-relative path without container-specific configuration.

Update test fixtures that read the catalogue from the source tree. Extend the
existing GitHub Docker check to execute a small assertion inside the built
image, importing `app.seed` and confirming the package-relative catalogue file
exists. This specifically covers the installed-wheel layout that the previous
image-build-only check missed.

## Scope

No catalogue content, seed behavior, database schema, storefront behavior, or
Render configuration changes. The hotfix only corrects resource packaging and
adds the container-runtime regression check.

## Verification

- Complete PostgreSQL-backed test suite.
- Ruff and mypy.
- Alembic remains at the current head.
- Docker image builds.
- A command executed inside the image confirms the installed catalogue path
  exists.
- Render redeploy completes migration, seed, startup, and readiness checks.

