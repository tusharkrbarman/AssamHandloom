# Quiet Commerce Fidelity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Render home page faithfully match the already-approved Quiet Commerce draft.

**Architecture:** Keep the FastAPI/Jinja rendering path and existing design tokens. Correct the demo media at the seed boundary, then port the approved composition into the existing templates and CSS without adding runtime dependencies or commerce behavior.

**Tech Stack:** FastAPI, Jinja2, plain CSS, PostgreSQL seed catalogue.

## Global Constraints

- This remains a read-only demo.
- No TDD workflow is required; run focused render checks after implementation.
- Use only the existing Luit & Loom palette and type stacks.
- Preserve accessibility, truthful sample disclosures, and reduced-motion behavior.

---

### Task 1: Restore approved demo imagery

**Files:**
- Modify: `app/data/river-reed-gold.json`
- Verify: `tests/unit/test_seed.py`

**Interfaces:**
- Consumes: the existing idempotent sample-catalogue reconciliation.
- Produces: four photographic sample media records used by the home hero and featured grid.

- [ ] Replace the media URLs for featured ranks 12 through 9 with the four approved photographic references.
- [ ] Keep `is_placeholder: true` and keep alt text beginning with “Sample placeholder”.
- [ ] Run the seed validation unit checks.

### Task 2: Match shell and home-page structure

**Files:**
- Modify: `app/templates/base.html`
- Modify: `app/templates/components/header.html`
- Modify: `app/templates/storefront/home.html`
- Modify: `app/templates/components/footer.html`
- Test: `tests/accessibility/test_shell.py`

**Interfaces:**
- Consumes: the current Jinja context (`page`, `home`, product-card fields).
- Produces: the approved header, hero, trust, material, artisan, newsletter, and footer anatomy.

- [ ] Load Inter in the base document.
- [ ] Replace text-only header utilities and trust items with accessible inline SVG icons.
- [ ] Center the newsletter content and preserve disabled preview controls.
- [ ] Adjust the artisan study and footer columns to the approved structure.
- [ ] Update shell assertions only where the approved structure intentionally changes.

### Task 3: Port the approved visual measurements

**Files:**
- Modify: `app/static/css/site.css`

**Interfaces:**
- Consumes: the structural class names from Task 2.
- Produces: the approved desktop and mobile spacing, sizing, grid, and interaction states.

- [ ] Match header spacing, nav/search breakpoints, hero actions, and image hover.
- [ ] Match trust-strip rhythm and featured-card metadata layout.
- [ ] Match material, artisan, newsletter, and footer proportions.
- [ ] Preserve square corners, focus visibility, and reduced motion.

### Task 4: Verify and publish

**Files:**
- No production files created.

**Interfaces:**
- Consumes: the final rendered storefront.
- Produces: a focused pull request with passing checks.

- [ ] Run `git diff --check`.
- [ ] Run `uv run ruff check app tests`.
- [ ] Run `uv run mypy app`.
- [ ] Run database-free unit checks and a local rendered DOM check.
- [ ] Commit, push, open a pull request, and wait for CI.

