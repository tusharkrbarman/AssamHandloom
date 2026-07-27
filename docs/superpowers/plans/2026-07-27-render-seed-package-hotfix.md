# Render Seed Package Hotfix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the installed Render container find and load the bundled sample catalogue.

**Architecture:** Keep the catalogue inside the `app` Python package and resolve it relative to `app.seed`. Verify the installed layout by running an assertion inside the built Docker image.

**Tech Stack:** Python 3.12, Hatchling, Docker, GitHub Actions

## Global Constraints

- Do not change catalogue content or seed behavior.
- Do not change database migrations or Render resources.
- Do not add dependencies.
- Follow the user's existing preference for implementation followed by verification rather than TDD.

---

### Task 1: Package the Catalogue with the Seed Command

**Files:**
- Move: `data/river-reed-gold.json` to `app/data/river-reed-gold.json`
- Modify: `app/seed.py`
- Modify: `tests/unit/test_seed.py`
- Modify: `tests/integration/test_seed.py`

**Interfaces:**
- Consumes: installed `app.seed.__file__`
- Produces: package-relative `app/data/river-reed-gold.json`

- [ ] Move the unchanged JSON file below `app/data`.
- [ ] Change the runtime path to:

```python
Path(__file__).parent / "data" / "river-reed-gold.json"
```

- [ ] Update source-tree test paths to `app/data/river-reed-gold.json`.
- [ ] Run seed unit and integration tests.

### Task 2: Verify the Installed Container Layout

**Files:**
- Modify: `.github/workflows/quality.yml`

**Interfaces:**
- Consumes: `luit-and-loom:ci` image built by the preceding workflow step
- Produces: a failing CI job whenever the catalogue is absent from the installed package

- [ ] Add this step after the Docker build:

```yaml
- name: Verify packaged catalogue
  run: >-
    docker run --rm --entrypoint python luit-and-loom:ci -c
    "from pathlib import Path; import app.seed;
    assert (Path(app.seed.__file__).parent / 'data' / 'river-reed-gold.json').is_file()"
```

- [ ] Run the complete PostgreSQL test suite, Ruff, mypy, Alembic current, and
  `git diff --check`.
- [ ] Commit and push `codex/fix-render-seed-package`.
- [ ] Create a ready pull request against `master`.
- [ ] Wait for GitHub tests and both Docker steps to pass.
