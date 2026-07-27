# Luit & Loom FastAPI Commerce Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a production-shaped FastAPI and PostgreSQL foundation with an artistic, accessible, read-only storefront for the 12-piece River, Reed & Gold sample catalogue.

**Architecture:** A modular FastAPI monolith renders Jinja pages and exposes narrowly scoped JSON endpoints. SQLAlchemy 2 and Alembic own PostgreSQL persistence; catalogue services return typed view data rather than leaking ORM objects into templates. HTMX progressively enhances filters and search while every browsing route remains functional without JavaScript.

**Tech Stack:** Python 3.12, FastAPI, Uvicorn, SQLAlchemy 2 async, psycopg 3, Alembic, PostgreSQL 16, Pydantic Settings, Jinja2, HTMX, vanilla JavaScript, modern CSS, pytest, pytest-asyncio, HTTPX, Ruff, mypy, and Docker Compose for local PostgreSQL.

## Global Constraints

- The brand name is **Luit & Loom** and the tagline is **Woven by Assam. Worn with meaning.**
- The visual position is premium contemporary: authentic Assamese heritage presented with modern refinement.
- The palette is Muga gold, warm ivory, deep lac red, betel-leaf green, and charcoal.
- Use restrained Assamese textile geometry; do not use generic gold gradients, crowded festival graphics, or ornamental excess.
- INR is the authoritative catalogue currency.
- Money is stored as integer minor units with an ISO 4217 currency code; floating point is forbidden for commerce amounts.
- PostgreSQL is the authoritative durable store; SQLite is not an application or integration-test substitute.
- Primary content is server rendered and all browsing routes work without JavaScript.
- Theme-controlled experiences target WCAG 2.2 AA with keyboard support, visible focus, reduced motion, and 44-by-44-pixel touch targets.
- Generated imagery and sample identities must remain visibly marked as samples and must never be published as actual sale inventory or documentary evidence.
- Sample records are visible only when `CATALOGUE_PREVIEW_ENABLED=true`; production defaults this setting to `false`.
- Phase 1 is read-only commerce: it does not add cart mutation, checkout, payments, customer data, staff authentication, or live publishing.

---

## File Map

- `pyproject.toml` — package metadata, dependency ranges, and quality-tool configuration.
- `.env.example` — non-secret configuration contract.
- `compose.yaml` — local PostgreSQL service and health check.
- `alembic.ini`, `migrations/env.py`, `migrations/versions/*` — schema migration history.
- `app/main.py` — application factory and router assembly.
- `app/config.py` — validated settings.
- `app/db.py` — SQLAlchemy base, engine, sessions, and request dependency.
- `app/health.py` — liveness and readiness routes.
- `app/catalog/models.py` — catalogue persistence models.
- `app/catalog/schemas.py` — immutable catalogue query and view types.
- `app/catalog/repository.py` — database query boundary.
- `app/catalog/service.py` — catalogue filtering, money display, and publication rules.
- `app/catalog/routes.py` — HTML and JSON catalogue endpoints.
- `app/storefront/routes.py` — homepage and supporting public pages.
- `app/templates/*` — Jinja layouts, components, and public pages.
- `app/static/css/site.css` — brand tokens, layout, responsive, and accessibility styles.
- `app/static/js/site.js` — minimal disclosure and progressive-enhancement behaviour.
- `app/seed.py` — idempotent sample-catalogue import.
- `data/river-reed-gold.json` — twelve sample products and sample public artisan profiles.
- `tests/unit/*` — pure service tests.
- `tests/integration/*` — real-PostgreSQL repository and HTTP tests.
- `tests/accessibility/*` — rendered-page semantic checks.
- `.github/workflows/quality.yml` — automated checks.

---

### Task 1: Application and PostgreSQL foundation

**Files:**
- Create: `pyproject.toml`
- Create: `.env.example`
- Create: `compose.yaml`
- Create: `app/__init__.py`
- Create: `app/main.py`
- Create: `app/config.py`
- Create: `app/db.py`
- Create: `app/health.py`
- Create: `alembic.ini`
- Create: `migrations/env.py`
- Create: `migrations/script.py.mako`
- Create: `tests/conftest.py`
- Create: `tests/integration/test_health.py`

**Interfaces:**
- Produces: `Settings`, `get_settings()`, `Base`, `get_session()`, `create_app(settings: Settings | None = None) -> FastAPI`, `GET /health/live`, and `GET /health/ready`.
- Consumes: `DATABASE_URL`, `SECRET_KEY`, `ENVIRONMENT`, `PUBLIC_BASE_URL`, and `CATALOGUE_PREVIEW_ENABLED`.

- [ ] **Step 1: Write failing health and configuration tests**

Create an HTTP test that starts the app with explicit test settings:

```python
async def test_liveness_does_not_require_database(app_client):
    response = await app_client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "live"}


async def test_readiness_checks_postgresql(app_client):
    response = await app_client.get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready", "database": "up"}
```

Add a settings test asserting an empty `SECRET_KEY` fails validation and a non-PostgreSQL `DATABASE_URL` is rejected outside the `test` environment.

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/integration/test_health.py -q`

Expected: collection fails because `app.main` and the fixtures do not exist.

- [ ] **Step 3: Implement the application factory and database boundary**

Use:

```python
def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings or get_settings()
    app = FastAPI(title="Luit & Loom", version="0.1.0")
    app.state.settings = resolved
    app.state.engine = create_async_engine(resolved.database_url)
    app.include_router(health_router)
    return app
```

`GET /health/live` returns without touching dependencies. `GET /health/ready` executes `SELECT 1` through the application engine and returns HTTP 503 with `{"status": "not_ready", "database": "down"}` on database failure.

Configure `tests/conftest.py` to require `TEST_DATABASE_URL` pointing to PostgreSQL, create an isolated database schema per test session, apply Alembic migrations, and override the application session dependency. Do not silently fall back to SQLite.

- [ ] **Step 4: Add the initial empty migration and local database**

`compose.yaml` defines PostgreSQL 16 with a named volume, health check, non-production credentials, and port `5432`. `.env.example` uses:

```dotenv
ENVIRONMENT=development
DATABASE_URL=postgresql+psycopg://luit:luit@localhost:5432/luit_loom
SECRET_KEY=replace-with-at-least-32-random-bytes
PUBLIC_BASE_URL=http://localhost:8000
CATALOGUE_PREVIEW_ENABLED=true
```

The initial migration creates no domain tables but proves Alembic can upgrade from an empty database.

- [ ] **Step 5: Verify GREEN and quality**

Run:

```bash
python -m pytest tests/integration/test_health.py -q
python -m ruff check app tests
python -m mypy app
```

Expected: health tests pass, Ruff reports no violations, and mypy reports success.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml .env.example compose.yaml app alembic.ini migrations tests
git commit -m "feat: establish FastAPI and PostgreSQL foundation"
```

---

### Task 2: Catalogue persistence and publication rules

**Files:**
- Create: `app/catalog/__init__.py`
- Create: `app/catalog/models.py`
- Create: `app/catalog/schemas.py`
- Create: `app/catalog/repository.py`
- Create: `app/catalog/service.py`
- Create: `migrations/versions/0002_catalogue.py`
- Create: `tests/unit/catalog/test_service.py`
- Create: `tests/integration/catalog/test_repository.py`

**Interfaces:**
- Consumes: `Base`, `AsyncSession`.
- Produces: `Product`, `Variant`, `Collection`, `CollectionProduct`, `ProductMedia`, `ArtisanProfile`, `ProductListQuery`, `ProductCard`, `ProductDetail`, `Page[T]`, `CatalogRepository`, and `CatalogService`.

- [ ] **Step 1: Write failing publication and money tests**

Use literal expected values:

```python
def test_product_card_formats_integer_minor_units():
    card = ProductCard(
        slug="luit-dawn",
        title="Luit Dawn",
        silk_type="Muga",
        artisan_name="Sample artisan",
        price_minor=1890000,
        currency="INR",
        available=True,
        primary_image=None,
    )
    assert card.display_price == "₹18,900"


def test_draft_product_is_never_returned(catalog_service, draft_product):
    result = catalog_service.visible_product(draft_product, preview_enabled=True)
    assert result is None
```

Add tests for compare-at price validation, unique slug/SKU, non-negative price, product-without-visible-variant exclusion, sample status propagation, preview records hidden when preview is disabled, and preview records visible with an explicit sample label when preview is enabled.

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/unit/catalog/test_service.py -q`

Expected: import fails because catalogue types do not exist.

- [ ] **Step 3: Implement catalogue models and types**

Use UUID primary keys, timezone-aware timestamps, integer money columns, explicit check constraints, and stable slugs. `Product` owns catalogue content and a publication state of `draft`, `preview`, or `published`. `Variant` owns SKU, price, weight, and read-only phase-one inventory quantity. `ArtisanProfile` contains only approved public display fields plus `is_sample`.

Define:

```python
@dataclass(frozen=True)
class ProductListQuery:
    search: str | None = None
    silk_types: tuple[str, ...] = ()
    colours: tuple[str, ...] = ()
    occasions: tuple[str, ...] = ()
    available_only: bool = False
    sort: Literal["featured", "newest", "price_asc", "price_desc"] = "featured"
    page: int = 1
    page_size: int = 12
```

`ProductCard.display_price` formats INR without floating point. Other currencies use their ISO code until a later localization phase.

- [ ] **Step 4: Implement repository queries**

`CatalogRepository.list_products(query, preview_enabled)` returns published products with at least one published variant. When preview is explicitly enabled, it also returns preview products and variants; it never returns drafts. Apply filters with SQLAlchemy expressions, use explicit ordering plus product ID for stable pagination, eager-load only data required by cards, and return total count with page results.

`CatalogRepository.get_product_by_slug(slug, preview_enabled)` follows the same publication rule and returns one product detail or `None`. `CatalogRepository.list_collections(preview_enabled)` follows the same rule and returns collections with their display ordering.

- [ ] **Step 5: Apply migration and verify PostgreSQL behaviour**

Run:

```bash
alembic upgrade head
python -m pytest tests/unit/catalog tests/integration/catalog -q
```

Expected: all catalogue tests pass against PostgreSQL, including unique constraints and stable pagination.

- [ ] **Step 6: Commit**

```bash
git add app/catalog migrations/versions/0002_catalogue.py tests/unit/catalog tests/integration/catalog
git commit -m "feat: add catalogue domain and PostgreSQL persistence"
```

---

### Task 3: Public catalogue and search routes

**Files:**
- Create: `app/catalog/routes.py`
- Create: `app/storefront/__init__.py`
- Create: `app/storefront/routes.py`
- Create: `app/web.py`
- Modify: `app/main.py`
- Create: `tests/integration/storefront/test_catalog_routes.py`

**Interfaces:**
- Consumes: `CatalogService`, `ProductListQuery`, Jinja environment.
- Produces: `GET /`, `GET /shop`, `GET /collections/{slug}`, `GET /products/{slug}`, `GET /search`, and `GET /api/v1/catalog/products`.

- [ ] **Step 1: Write failing route-behaviour tests**

Create data through factories, then assert observable responses:

```python
async def test_shop_filters_to_published_muga_products(client, seeded_catalog):
    response = await client.get("/shop?silk_type=Muga")
    assert response.status_code == 200
    assert "Luit Dawn" in response.text
    assert "Kopou Ivory" not in response.text


async def test_unknown_product_returns_branded_404(client):
    response = await client.get("/products/not-a-saree")
    assert response.status_code == 404
    assert "We couldn’t find that weave" in response.text
```

Add tests for URL-stable sorting, page bounds, query normalization, unpublished exclusion, HTML/JSON parity, and HTMX partial responses preserving the same query semantics.

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/integration/storefront/test_catalog_routes.py -q`

Expected: routes return 404 because they are not registered.

- [ ] **Step 3: Implement query parsing and route boundaries**

`app/web.py` provides `templates`, `render(request, template, context, status_code=200)`, and a safe `is_htmx(request)` helper. Parse repeated filters with `request.query_params.getlist`, clamp page size to 24, reject invalid sort values with HTTP 422 JSON for API requests, and fall back to featured sorting for HTML.

The JSON endpoint returns:

```json
{
  "items": [],
  "page": 1,
  "page_size": 12,
  "total": 0,
  "pages": 0
}
```

HTML routes render full templates normally and product-grid partials for HTMX requests.

- [ ] **Step 4: Implement 404 and error rendering**

Register application handlers for 404 and safe 500 responses. Production responses never include stack traces. The 404 page includes search and collection recovery links.

- [ ] **Step 5: Verify GREEN**

Run:

```bash
python -m pytest tests/integration/storefront/test_catalog_routes.py -q
python -m ruff check app tests
python -m mypy app
```

Expected: route tests and quality checks pass.

- [ ] **Step 6: Commit**

```bash
git add app tests/integration/storefront
git commit -m "feat: expose public catalogue and search routes"
```

---

### Task 4: Brand system and accessible application shell

**Files:**
- Create: `app/templates/base.html`
- Create: `app/templates/components/header.html`
- Create: `app/templates/components/footer.html`
- Create: `app/templates/components/icons.html`
- Create: `app/templates/errors/404.html`
- Create: `app/templates/errors/500.html`
- Create: `app/static/css/site.css`
- Create: `app/static/js/site.js`
- Create: `tests/accessibility/test_shell.py`
- Modify: `app/main.py`

**Interfaces:**
- Consumes: request, navigation data, search URL, current cart count fixed at zero for Phase 1.
- Produces: semantic page shell, skip link, responsive navigation, search disclosure, focus management, and brand CSS tokens.

- [ ] **Step 1: Write failing rendered-behaviour tests**

Parse the actual homepage response and assert:

```python
def test_shell_has_one_main_landmark_and_skip_target(rendered_home):
    document = rendered_home
    assert len(document.cssselect("main#main-content")) == 1
    skip = document.cssselect('a[href="#main-content"]')
    assert len(skip) == 1


def test_icon_buttons_have_accessible_names(rendered_home):
    for button in rendered_home.cssselect("button"):
        assert button.text_content().strip() or button.get("aria-label")
```

Add checks for one H1, labelled navigation, labelled search, form labels, image alternatives, no positive tabindex, and logical header/main/footer order.

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/accessibility/test_shell.py -q`

Expected: the homepage cannot render because the base template and static files do not exist.

- [ ] **Step 3: Implement the semantic shell**

`base.html` includes canonical metadata blocks, skip link, header, exactly one main landmark, footer, `site.css`, deferred `site.js`, and HTMX with a pinned local static asset rather than an unpinned CDN URL.

Header includes text-logo fallback “Luit & Loom”, the approved navigation, search, wishlist placeholder, cart placeholder, and mobile disclosure. Phase 1 wishlist and cart links are visibly labelled “Coming in checkout phase” and do not imitate working actions.

- [ ] **Step 4: Implement the visual system**

Define:

```css
:root {
  --color-muga: #bd8b2f;
  --color-ivory: #f7f1e6;
  --color-lac: #7e1f2b;
  --color-betel: #244d3b;
  --color-charcoal: #252320;
  --color-paper: #fffdf8;
  --color-border: #d8ccba;
  --font-display: "Iowan Old Style", "Baskerville", "Times New Roman", serif;
  --font-body: Inter, "Avenir Next", Avenir, "Segoe UI", sans-serif;
  --content-width: 90rem;
  --reading-width: 44rem;
}
```

Add a reset, fluid type scale, containers, editorial grids, buttons, forms, cards, drawers, visually-hidden utility, focus-visible states, 44-pixel controls, and a complete reduced-motion override. Use CSS borders and gradients for restrained woven rules; do not author decorative SVG illustrations.

- [ ] **Step 5: Implement disclosure behaviour**

`site.js` uses delegated events for `[data-disclosure-button]`, synchronizes `aria-expanded` and `hidden`, closes on Escape and backdrop interaction, and returns focus to the trigger. The navigation remains usable as normal links if JavaScript is disabled.

- [ ] **Step 6: Verify and commit**

Run:

```bash
python -m pytest tests/accessibility/test_shell.py -q
python -m pytest tests/integration/storefront -q
```

Expected: all rendered semantic and route tests pass.

```bash
git add app/templates app/static app/main.py tests/accessibility
git commit -m "feat: add Luit and Loom brand shell"
```

---

### Task 5: Homepage, collection, product, and editorial views

**Files:**
- Create: `app/templates/home.html`
- Create: `app/templates/shop.html`
- Create: `app/templates/collection.html`
- Create: `app/templates/product.html`
- Create: `app/templates/search.html`
- Create: `app/templates/partials/product_grid.html`
- Create: `app/templates/components/product_card.html`
- Create: `app/templates/components/pagination.html`
- Create: `app/templates/components/provenance.html`
- Create: `app/templates/page.html`
- Modify: `app/static/css/site.css`
- Create: `tests/integration/storefront/test_pages.py`
- Create: `tests/accessibility/test_pages.py`

**Interfaces:**
- Consumes: `ProductCard`, `ProductDetail`, `Page[T]`, collection summaries, sample-state flags.
- Produces: the approved homepage sequence, filterable shop and collection pages, provenance-rich product page, search states, and reusable product-card/pagination components.

- [ ] **Step 1: Write failing page-flow tests**

Assert real rendered outcomes:

```python
async def test_homepage_leads_to_collection_and_artisan_story(client, seeded_catalog):
    response = await client.get("/")
    assert response.status_code == 200
    assert "Woven by Assam. Worn with meaning." in response.text
    assert 'href="/shop"' in response.text
    assert "Meet the artisans" in response.text


async def test_product_page_exposes_commerce_and_provenance_facts(client, seeded_catalog):
    response = await client.get("/products/luit-dawn")
    assert response.status_code == 200
    for text in ("Muga", "Dimensions", "Care", "Motif", "Sample catalogue"):
        assert text in response.text
```

Add tests for no-results recovery, unavailable product state, absent optional image, pagination links preserving filters, image width/height, lazy loading below the hero, and sample labels.

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/integration/storefront/test_pages.py -q`

Expected: templates are missing or lack required content.

- [ ] **Step 3: Implement homepage and reusable product cards**

Homepage order:

1. Hero with approved tagline and Shop/Artisans actions
2. Featured products
3. Why Assam silk
4. Muga/Pat/Eri collection cards
5. Featured sample artisan disclosure
6. Craft assurances
7. Occasion edit
8. Shipping/returns/care assurances
9. Newsletter invitation labelled `Email sign-up opens in a later phase`

Product cards show primary image or designed textile-colour placeholder, silk type, artisan, title, price, availability, and sample label. Hover images appear only when a second image exists and hover is supported.

- [ ] **Step 4: Implement shop, collection, search, and product pages**

Filters use GET forms so URLs remain shareable. HTMX replaces only the product-grid region and updates browser history. The non-JavaScript form submission renders the same results.

Product pages show gallery, price, availability, specifications, artisan, region, motif, production details, care, authenticity explanation, shipping summary, and related items. Phase 1 purchase controls are disabled with the honest message `Checkout opens in the next build phase`.

- [ ] **Step 5: Verify accessibility and behaviour**

Run:

```bash
python -m pytest tests/integration/storefront/test_pages.py tests/accessibility/test_pages.py -q
python -m ruff check app tests
python -m mypy app
```

Expected: page-flow, semantic, and quality checks pass.

- [ ] **Step 6: Commit**

```bash
git add app/templates app/static/css/site.css tests/integration/storefront tests/accessibility
git commit -m "feat: build artistic public catalogue pages"
```

---

### Task 6: Validated sample catalogue and quality automation

**Files:**
- Create: `data/river-reed-gold.json`
- Create: `app/seed.py`
- Create: `tests/unit/test_seed.py`
- Create: `tests/integration/test_seed.py`
- Create: `.github/workflows/quality.yml`
- Create: `README.md`
- Modify: `pyproject.toml`

**Interfaces:**
- Consumes: catalogue models and services.
- Produces: `load_sample_catalogue(session, path) -> SeedResult`, deterministic 12-product sample data, and CI checks.

- [ ] **Step 1: Write failing seed safety tests**

Tests assert:

```python
async def test_seed_is_idempotent(db_session, catalogue_path):
    first = await load_sample_catalogue(db_session, catalogue_path)
    second = await load_sample_catalogue(db_session, catalogue_path)
    assert first.products_created == 12
    assert second.products_created == 0
    assert second.products_updated == 12


async def test_sample_records_cannot_be_published(db_session, catalogue_path):
    await load_sample_catalogue(db_session, catalogue_path)
    products = await published_products(db_session)
    assert products == []
```

Also verify exactly four Muga, four Pat, two Eri, and two silk-blend records; unique handles/SKUs; sample artisans; placeholder-media flags; integer INR prices; required commerce facts; and no fictional provenance exposed as verified.

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/unit/test_seed.py tests/integration/test_seed.py -q`

Expected: import fails because seed loader and data do not exist.

- [ ] **Step 3: Create the deterministic sample catalogue**

Use the twelve approved names and mark every product, artisan, media record, and provenance statement as sample. Products remain visible in `preview` mode but not `published` mode. The seed loader validates the entire input before opening a transaction and updates by stable slug/SKU without duplicating records.

- [ ] **Step 4: Add continuous integration verification**

CI starts PostgreSQL 16, installs the project, and runs:

```bash
alembic upgrade head
python -m pytest -q
python -m ruff check app tests
python -m mypy app
```

No secrets appear in workflow files. Application containerization is intentionally deferred to the final production-hardening phase.

- [ ] **Step 5: Run the complete Phase 1 verification**

Run:

```bash
alembic upgrade head
python -m pytest -q
python -m ruff check app tests
python -m mypy app
```

Expected: all tests pass with pristine output, static checks succeed, and the migration is current.

- [ ] **Step 6: Commit**

```bash
git add data app/seed.py tests .github README.md pyproject.toml
git commit -m "feat: add safe sample catalogue and quality automation"
```

---

## Phase 1 Exit Criteria

- A clean PostgreSQL database upgrades through all Alembic migrations.
- The seed command creates exactly 12 unpublished sample products and is idempotent.
- Homepage, shop, collection, search, product, and error pages render from PostgreSQL.
- All filters and pagination work with and without JavaScript.
- The Luit & Loom brand system is responsive, keyboard accessible, and reduced-motion aware.
- Sample and placeholder content cannot be mistaken for verified live inventory.
- Unit, PostgreSQL integration, rendered accessibility, Ruff, and mypy checks pass.
- No cart mutation, payment, customer, or staff feature is falsely presented as complete.
