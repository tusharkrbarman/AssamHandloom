
# FastAPI Storefront Cutover Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** Serve the existing public Quiet Commerce storefront from FastAPI while preserving its URLs, markup, CSS, browser behavior, guest checkout, signed order links, and Razorpay payment flow.

**Architecture:** FastAPI becomes the single web origin for public HTML, the existing CSS/JavaScript assets, and the existing JSON APIs. Jinja2 templates reproduce the current Worker page structure; a thin web module calls the existing PostgreSQL catalogue, order, link, and payment services without duplicating business rules. The legacy Worker remains available as rollback until the AWS storefront passes smoke checks.

**Tech Stack:** Python 3.12, FastAPI, Jinja2, Starlette StaticFiles, python-multipart, psycopg connection pool, PostgreSQL, existing app/static/css/site.css, app/static/js/bag.js, and app/static/js/pay.js.

**Spec:** docs/superpowers/specs/2026-09-01-fastapi-storefront-cutover-design.md

## Global Constraints

- Preserve the current Quiet Commerce visual layout, copy, class names, accessible labels, and public URL paths.
- Keep the existing CSS, bag.js, and pay.js; do not add a SPA framework or a second frontend build.
- Keep the browser, pages, assets, and JSON APIs on one origin; do not add CORS.
- Reuse the existing Python catalogue, order, signed-link, and payment services; HTML routes must not execute SQL or recalculate prices.
- Public routes include catalogue, editorial, bag, checkout, and order pages only. Admin, customer accounts, media upload/S3, email, refunds, shipping, tax, and infrastructure are out of scope.
- Render a textile placeholder when no known local media URL is available; defer public S3 media to its own task.
- Keep JSON API paths and response shapes unchanged.
- Add compact tests with each implementation task and run the full suite after the changes; do not use a test-first workflow.
- Keep the legacy Worker code and Wrangler toolchain untouched during this cutover for rollback.

---

### Task 1: Add rendering dependencies and shared request/static wiring

**Files:**
- Modify: services/api/pyproject.toml
- Create: services/api/app/dependencies.py
- Modify: services/api/app/main.py lines 1-66
- Test: services/api/tests/test_health.py

**Interfaces:**
- request_pool(request: Request) -> ConnectionPool
- require_same_origin(request: Request) -> None
- Static files available at /css/* and /js/*

- [ ] **Step 1: Add the required dependencies**

Add these entries to the existing project dependencies:

~~~toml
"jinja2>=3.1,<4.0",
"python-multipart>=0.0.9,<1.0",
~~~

Do not add a frontend framework, API client, ORM, or template helper package.

- [ ] **Step 2: Create shared request guards**

Create services/api/app/dependencies.py:

~~~python
from fastapi import HTTPException, Request
from psycopg_pool import ConnectionPool


def request_pool(request: Request) -> ConnectionPool:
    pool = getattr(request.app.state, "db_pool", None)
    if pool is None:
        raise HTTPException(
            status_code=503,
            detail={"status": "unavailable", "database": "not_configured"},
        )
    return pool


def require_same_origin(request: Request) -> None:
    origin = request.headers.get("origin")
    if not origin or origin != str(request.base_url).rstrip("/"):
        raise HTTPException(
            status_code=403,
            detail={"code": "invalid_origin", "message": "The request origin is not allowed."},
        )
~~~

Update main.py to import these functions, replace each existing pool helper call with request_pool, replace each same-origin helper call with require_same_origin, and remove the local helper definitions.

- [ ] **Step 3: Mount the existing assets without changing their URLs**

After creating the FastAPI app, add:

~~~python
from pathlib import Path
from fastapi.staticfiles import StaticFiles

STATIC_DIR = Path(__file__).resolve().parents[3] / "app" / "static"
app.mount("/css", StaticFiles(directory=STATIC_DIR / "css"), name="css")
app.mount("/js", StaticFiles(directory=STATIC_DIR / "js"), name="js")
~~~

The repository-root app/static directory remains the only asset source.

- [ ] **Step 4: Run the service checks**

~~~powershell
services/api/.venv/Scripts/python.exe -m pytest services/api/tests -q
~~~

Expected: all existing tests pass, including the existing 503 health/readiness behavior.

- [ ] **Step 5: Commit**

~~~powershell
git add services/api/pyproject.toml services/api/app/dependencies.py services/api/app/main.py
git commit -m "feat: prepare FastAPI for storefront rendering"
~~~

---

### Task 2: Add PostgreSQL catalogue reads for HTML pages

**Files:**
- Modify: services/api/app/catalogue.py
- Test: services/api/tests/test_catalogue.py

**Interfaces:**
- get_product(pool: ConnectionPool, slug: str) -> dict[str, object] | None
- list_collections(pool: ConnectionPool) -> list[dict[str, object]]
- get_collection(pool: ConnectionPool, slug: str) -> dict[str, object] | None
- catalogue_query_from_params(params: Mapping[str, str], collection_slug: str | None = None) -> CatalogueQuery

- [ ] **Step 1: Add the HTML query parser**

Implement catalogue_query_from_params in catalogue.py. Reuse the existing normalisation and sort constants. HTML requests default unknown sorting to featured; the JSON endpoint remains strict and returns 422. Cap page_size at 24, default it to 12, default page to 1, accept search or q, and treat 1, true, yes, and on as true for available_only.

- [ ] **Step 2: Add published collection queries**

Use this prepared statement for list_collections:

~~~sql
SELECT id, slug, title, description
FROM collections
WHERE publication_state = 'published'
ORDER BY display_order ASC, id ASC
~~~

For get_collection, add AND slug = %s LIMIT 1. Return None for a missing or draft collection.

- [ ] **Step 3: Add the product-detail query**

Load a product only when it is published and not archived. Then load its published variants with stock:

~~~sql
SELECT v.id, v.sku, v.title, v.price_minor, v.currency,
       v.publication_state, stock.quantity
FROM variants v
JOIN inventory_items stock ON stock.variant_id = v.id
WHERE v.product_id = %s AND v.publication_state = 'published'
ORDER BY v.price_minor ASC, v.id ASC
~~~

Return dictionaries with id, slug, title, description, silkType, colour, occasion, available, variants, and media. A variant contains id, sku, title, priceMinor, currency, and available. Load media metadata in display order, but leave the media URL empty so the web layer renders the placeholder.

- [ ] **Step 4: Extend catalogue tests**

Add fake-cursor coverage for query defaults and collection mapping:

~~~python
def test_html_query_defaults_invalid_sort_and_caps_page_size():
    query = catalogue_query_from_params(
        {"q": "  Muga  ", "sort": "nope", "page_size": "99"}
    )
    assert query.search == "Muga"
    assert query.sort == "featured"
    assert query.page_size == 24


def test_get_collection_maps_public_fields(fake_pool):
    result = get_collection(fake_pool, "river-edit")
    assert result == {
        "id": "collection-river",
        "slug": "river-edit",
        "title": "River Edit",
        "description": "A material conversation.",
    }
~~~

Keep the existing list-products assertions unchanged.

- [ ] **Step 5: Run catalogue tests and commit**

~~~powershell
services/api/.venv/Scripts/python.exe -m pytest services/api/tests/test_catalogue.py -q
git add services/api/app/catalogue.py services/api/tests/test_catalogue.py
git commit -m "feat: add FastAPI catalogue page queries"
~~~

---

### Task 3: Port the Quiet Commerce shell and catalogue pages

**Files:**
- Create: services/api/app/web.py
- Create: services/api/templates/base.html
- Create: services/api/templates/home.html
- Create: services/api/templates/catalogue.html
- Create: services/api/templates/product.html
- Create: services/api/templates/editorial.html
- Create: services/api/templates/error.html
- Create: services/api/templates/partials/header.html
- Create: services/api/templates/partials/footer.html
- Create: services/api/templates/partials/product-card.html
- Create: services/api/templates/partials/product-grid.html
- Modify: services/api/app/main.py
- Test: services/api/tests/test_web.py

**Interfaces:**
- router: APIRouter exported by web.py
- render_page(request, template, context, status_code=200) -> Response
- render_error(request, status_code, message, request_id) -> Response
- GET routes for home, catalogue, collection, product, and editorial pages

- [ ] **Step 1: Create the Jinja renderer and router**

Start web.py with:

~~~python
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import Response
from fastapi.templating import Jinja2Templates

from .catalogue import (
    catalogue_query_from_params,
    get_collection,
    get_product,
    list_collections,
    list_products,
)
from .dependencies import request_pool

TEMPLATES = Jinja2Templates(
    directory=str(Path(__file__).resolve().parents[1] / "templates")
)
router = APIRouter()


def render_page(
    request: Request,
    template: str,
    context: dict[str, object],
    status_code: int = 200,
) -> Response:
    return TEMPLATES.TemplateResponse(
        request=request,
        name=template,
        context=context,
        status_code=status_code,
    )
~~~

- [ ] **Step 2: Port the shared shell**

Move the current header, footer, skip link, canonical URL, safe title, and /js/bag.js tag from src/storefront.ts into the base template and partials. Preserve:

~~~html
<a class="skip-link" href="#main-content">Skip to main content</a>
<main id="main-content" tabindex="-1">{% block content %}{% endblock %}</main>
<script src="/js/bag.js" defer></script>
~~~

Use Jinja autoescaping for catalogue values. Render the textile placeholder when the product has no usable media URL.

- [ ] **Step 3: Port the catalogue markup**

Reproduce the current hero, trust strip, product card, filters, pagination, material, artisan, specifications, provenance, and related-product markup from src/storefront.ts. Use this context:

~~~python
{
    "page": page,
    "query": query,
    "url": str(request.url),
    "collection": collection,
    "product": product,
    "related": related,
    "title": page_title,
}
~~~

Keep links on /products/{slug}, /shop?sort=newest, /collections/{slug}, /css/site.css, and /js/bag.js.

- [ ] **Step 4: Add catalogue and editorial routes**

Implement these concrete route bodies in web.py:

~~~python
@router.get("/")
def home(request: Request) -> Response:
    page = list_products(request_pool(request), CatalogueQuery(page_size=4))
    return render_page(request, "home.html", {"page": page, "title": "Luit & Loom"})


@router.get("/shop")
def shop(request: Request) -> Response:
    query = catalogue_query_from_params(request.query_params)
    page = list_products(request_pool(request), query)
    return render_page(request, "catalogue.html", {"page": page, "query": query, "title": "Shop · Luit & Loom"})


@router.get("/search")
def search(request: Request) -> Response:
    query = catalogue_query_from_params(request.query_params)
    page = list_products(request_pool(request), query)
    return render_page(request, "catalogue.html", {"page": page, "query": query, "title": "Search · Luit & Loom"})


@router.get("/collections")
def collections(request: Request) -> Response:
    return render_page(request, "editorial.html", {"collections": list_collections(request_pool(request)), "title": "Collections · Luit & Loom"})


@router.get("/collections/{slug}")
def collection_page(slug: str, request: Request) -> Response:
    collection = get_collection(request_pool(request), slug)
    if collection is None:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "The requested collection was not found."})
    query = catalogue_query_from_params(request.query_params, slug)
    page = list_products(request_pool(request), query)
    return render_page(request, "catalogue.html", {"page": page, "query": query, "collection": collection, "title": f"{collection['title']} · Luit & Loom"})


@router.get("/products/{slug}")
def product_page(slug: str, request: Request) -> Response:
    product = get_product(request_pool(request), slug)
    if product is None:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "The requested product was not found."})
    query = CatalogueQuery(search=None, silk_type=str(product["silkType"]), page_size=4)
    related = [item for item in list_products(request_pool(request), query)["items"] if item["id"] != product["id"]][:3]
    return render_page(request, "product.html", {"product": product, "related": related, "title": f"{product['title']} · Luit & Loom"})
~~~

Add the existing editorial title/body map for /artisans, /our-story, /journal, /pages/silk-guide, /pages/care, /pages/shipping, /pages/returns, /pages/contact, and /pages/faq. Unknown editorial paths return the branded 404 response. Preserve the existing page copy from src/storefront.ts.

- [ ] **Step 5: Add branded browser error handling**

Create error.html with the current branded not-found and generic-failure copy. Export render_error from web.py. Register HTTPException and generic Exception handlers in main.py: return the existing JSON error shape for paths beginning with /api/, and render error.html for browser paths. Add an x-request-id response header for generic failures without logging request bodies or secrets.

- [ ] **Step 6: Register the router and add smoke tests**

Add from web import router as web_router and app.include_router(web_router) to main.py. Add test_web.py coverage for home hero copy, listing, draft exclusion, product 404, one editorial page, and /css/site.css and /js/bag.js. Use a fake pool or monkeypatched catalogue functions; no live PostgreSQL is required.

- [ ] **Step 7: Run web tests and commit**

~~~powershell
services/api/.venv/Scripts/python.exe -m pytest services/api/tests/test_web.py -q
git add services/api/app/web.py services/api/templates services/api/app/main.py services/api/tests/test_web.py
git commit -m "feat: serve Quiet Commerce catalogue from FastAPI"
~~~

---

### Task 4: Port bag, checkout, order, and payment HTML flows

**Files:**
- Modify: services/api/app/web.py
- Create: services/api/templates/commerce.html
- Modify: services/api/app/main.py
- Test: services/api/tests/test_web.py

**Interfaces:**
- GET /cart, GET /checkout, POST /checkout, and GET /orders/{order_id}
- The form adapter creates CheckoutRequest from the current hidden items JSON and field names.
- Existing JSON routes remain unchanged.

- [ ] **Step 1: Port the commerce markup**

Move the current cart, checkout, and order-confirmation markup from src/orders.ts into commerce.html. Preserve these hooks:

~~~html
<div id="cart-root"></div>
<input type="hidden" name="items" id="checkout-items" value="">
<div id="checkout-summary"></div>
<button class="button" type="button" id="pay-now" data-order-id="{{ order.id }}">Pay now</button>
<p class="form-alert" id="pay-error" role="alert" hidden></p>
~~~

Include Razorpay checkout.js and /js/pay.js only when payments are enabled and the order is pending.

- [ ] **Step 2: Parse the existing checkout form**

Implement checkout_payload(request: Request) -> CheckoutRequest in web.py. Read await request.form(), parse the hidden items value with json.loads, map postal_code to the Pydantic postalCode alias, and call CheckoutRequest.model_validate(body). Convert malformed JSON and validation errors into the existing checkout alert with status 422. Never accept prices or stock from the form.

- [ ] **Step 3: Add the HTML commerce routes**

Implement:

~~~python
@router.get("/cart")
def cart_page(request: Request) -> Response:
    return render_page(request, "commerce.html", {"kind": "cart", "title": "Your bag · Luit & Loom"})


@router.get("/checkout")
def checkout_page(request: Request) -> Response:
    payments_enabled = razorpay_config(Settings.from_env()) is not None
    return render_page(request, "commerce.html", {"kind": "checkout", "payments_enabled": payments_enabled, "title": "Checkout · Luit & Loom"})


@router.post("/checkout")
async def checkout_submit(request: Request) -> Response:
    require_same_origin(request)
    payload = await checkout_payload(request)
    result = create_order(request_pool(request), payload, Settings.from_env().cookie_signing_key)
    return RedirectResponse(f"/orders/{result['orderId']}?token={result['token']}", status_code=303)


@router.get("/orders/{order_id}")
def order_page(order_id: str, request: Request) -> Response:
    settings = Settings.from_env()
    query = request.query_params
    order = get_order(
        request_pool(request),
        order_id,
        query.get("token"),
        int(query["exp"]) if query.get("exp", "").isdigit() else None,
        query.get("sig"),
        settings.cookie_signing_key,
    )
    return render_page(
        request,
        "commerce.html",
        {
            "kind": "order",
            "order": order["order"],
            "payments_enabled": razorpay_config(settings) is not None,
            "title": f"Order {order_id[:8].upper()} · Luit & Loom",
        },
    )
~~~

Handle checkout HTTPExceptions by re-rendering commerce.html with the submitted safe fields and the error message. The order route passes token, exp, and sig to the existing get_order function and returns the branded 404 for invalid access.

- [ ] **Step 4: Add commerce and payment tests**

Extend test_web.py with:

~~~python
def test_cart_page_keeps_bag_script(client):
    response = client.get("/cart")
    assert response.status_code == 200
    assert 'id="cart-root"' in response.text
    assert 'src="/js/bag.js"' in response.text


def test_checkout_rejects_cross_origin(client):
    response = client.post("/checkout", data={"items": "[]"})
    assert response.status_code == 403


def test_invalid_order_link_is_not_found(client):
    response = client.get(
        "/orders/00000000-0000-0000-0000-000000000000?exp=1&sig=bad"
    )
    assert response.status_code == 404
~~~

Add one happy-path checkout test with a fake create_order return value and assert the 303 location contains the order ID and token. Add one pending-order test that confirms the Razorpay button appears only when all Razorpay settings are present.

- [ ] **Step 5: Run the full service suite and commit**

~~~powershell
services/api/.venv/Scripts/python.exe -m pytest services/api/tests -q
git add services/api/app/web.py services/api/templates/commerce.html services/api/tests/test_web.py
git commit -m "feat: preserve FastAPI checkout and order pages"
~~~

---

### Task 5: Update AWS documentation and finish verification

**Files:**
- Modify: README.md lines 15-16 and 63-80
- Modify: services/api/README.md
- Modify: services/api/tests/test_web.py

**Interfaces:**
- Documentation states that FastAPI serves the public storefront and the Worker is rollback-only.
- The existing AWS-only CI workflow continues to install and test the Python service.

- [ ] **Step 1: Mark the storefront cutover complete**

Update the root README so the browser storefront is no longer listed as pending. Keep Docker/ECS, AWS resources, S3 media, admin, email, refunds, shipping, and tax rules pending.

- [ ] **Step 2: Document the browser smoke check**

Add the FastAPI command and route checklist to services/api/README.md:

~~~powershell
services/api/.venv/Scripts/uvicorn app.main:app --app-dir services/api --reload
~~~

Check /, /shop, /products/{slug}, /cart, /checkout, and a signed /orders/{id} URL. Do not document Wrangler as part of the AWS request path.

- [ ] **Step 3: Add final markup assertions**

Assert that the home page contains one main element, the skip link, primary navigation, /css/site.css, and only the expected /js/bag.js script. Assert that product, cart, checkout, and order pages keep their current CSS hooks.

- [ ] **Step 4: Run CI-equivalent checks**

From services/api:

~~~powershell
.venv/Scripts/python.exe -m pytest tests -q
~~~

From the repository root also run:

~~~powershell
git diff --check
git status --short --branch
~~~

Confirm .github/workflows/quality.yml contains only Python setup, editable API installation, and the FastAPI test command.

- [ ] **Step 5: Commit documentation**

~~~powershell
git add README.md services/api/README.md services/api/tests/test_web.py
git commit -m "docs: mark FastAPI storefront cutover complete"
~~~

## Final Verification

Run:

~~~powershell
services/api/.venv/Scripts/python.exe -m pytest services/api/tests -q
git diff --check
git status --short --branch
~~~

Expected: all FastAPI tests pass, the final commit leaves a clean working tree, and the legacy Worker remains available only as rollback code.
