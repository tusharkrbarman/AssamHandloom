from json import JSONDecodeError, loads
from pathlib import Path
from urllib.parse import urlencode
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from pydantic import ValidationError
from fastapi.responses import Response
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from .catalogue import (
    CatalogueQuery,
    catalogue_query_from_params,
    format_money,
    get_collection,
    get_product,
    list_collections,
    list_products,
)
from .dependencies import request_pool
from .dependencies import require_same_origin
from .links import verify_order_link
from .orders import CheckoutRequest, create_order, get_order
from .payments import razorpay_config
from .settings import Settings


TEMPLATES = Jinja2Templates(
    directory=str(Path(__file__).resolve().parents[1] / "templates")
)
TEMPLATES.env.globals["format_money"] = format_money
router = APIRouter()

EDITORIAL_PAGES = {
    "/artisans": {
        "title": "Artisans",
        "body": "Verified maker profiles will be introduced only with consent and confirmed public details.",
    },
    "/our-story": {
        "title": "Our story",
        "body": "Luit & Loom presents Assamese handloom with care. Browse the catalogue, reserve weaves through checkout preview, and complete payment once online payments open.",
    },
    "/journal": {
        "title": "Journal",
        "body": "Understanding Assam silk, identifying authentic Muga, and caring for handwoven sarees are planned editorial notes.",
    },
    "/pages/silk-guide": {
        "title": "Silk guide",
        "body": "Muga, Pat, and Eri have distinct qualities. This introduction does not replace verified product facts.",
    },
    "/pages/care": {
        "title": "Care guide",
        "body": "Care instructions must be verified for each real textile before purchase.",
    },
    "/pages/shipping": {
        "title": "Shipping",
        "body": "We ship across India first. Exact rates and timelines are published with the payments release; placing a preview order reserves stock at no cost.",
    },
    "/pages/returns": {
        "title": "Returns",
        "body": "Returns terms are being finalised for the commerce launch and will be confirmed before any payment is taken.",
    },
    "/pages/contact": {
        "title": "Contact",
        "body": "Contact channels are announced with the live commerce release. Preview orders are held safely in the meantime.",
    },
    "/pages/faq": {
        "title": "Frequently asked questions",
        "body": "You can browse, bag, and place a reservation order today. Online payments activate with our next release; reserved weaves cost nothing until then.",
    },
}


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


def render_error(
    request: Request, status_code: int, message: str, request_id: str
) -> Response:
    response = render_page(
        request,
        "error.html",
        {"title": f"{status_code} · Luit & Loom", "status_code": status_code, "message": message, "request_id": request_id},
        status_code,
    )
    response.headers["cache-control"] = "no-store"
    response.headers["x-request-id"] = request_id
    return response


def page_href(request: Request, page: int) -> str:
    params = [
        (key, str(page) if key == "page" else value)
        for key, value in request.query_params.multi_items()
    ]
    if not any(key == "page" for key, _value in params):
        params.append(("page", str(page)))
    return f"{request.url.path}?{urlencode(params)}"


TEMPLATES.env.globals["page_href"] = page_href


def checkout_fields(form) -> dict[str, str]:
    return {
        field: value
        for field in ("email", "name", "phone", "address1", "address2", "city", "state", "postal_code", "country")
        if isinstance(value := form.get(field), str)
    }


def checkout_error_message(error: HTTPException) -> str:
    if isinstance(error.detail, dict) and isinstance(error.detail.get("message"), str):
        return error.detail["message"]
    return "Please check the checkout details and try again."


async def checkout_payload(request: Request) -> CheckoutRequest:
    form = await request.form()
    try:
        items = loads(str(form.get("items", "")))
    except (JSONDecodeError, TypeError):
        raise HTTPException(
            status_code=422,
            detail={"code": "invalid_cart", "message": "The bag could not be read."},
        ) from None
    body = {**checkout_fields(form), "items": items}
    if "postal_code" in body:
        body["postalCode"] = body.pop("postal_code")
    try:
        return CheckoutRequest.model_validate(body)
    except ValidationError:
        raise HTTPException(
            status_code=422,
            detail={"code": "invalid_checkout_field", "message": "Please check the checkout details and try again."},
        ) from None


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
    return render_page(
        request,
        "editorial.html",
        {"collections": list_collections(request_pool(request)), "title": "Collections · Luit & Loom"},
    )


@router.get("/collections/{slug}")
def collection_page(slug: str, request: Request) -> Response:
    collection = get_collection(request_pool(request), slug)
    if collection is None:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "The requested collection was not found."})
    query = catalogue_query_from_params(request.query_params, slug)
    page = list_products(request_pool(request), query)
    return render_page(
        request,
        "catalogue.html",
        {"page": page, "query": query, "collection": collection, "title": f"{collection['title']} · Luit & Loom"},
    )


@router.get("/products/{slug}")
def product_page(slug: str, request: Request) -> Response:
    product = get_product(request_pool(request), slug)
    if product is None:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "The requested product was not found."})
    query = CatalogueQuery(search=None, silk_type=str(product["silkType"]), page_size=4)
    related = [item for item in list_products(request_pool(request), query)["items"] if item["id"] != product["id"]][:3]
    return render_page(
        request,
        "product.html",
        {"product": product, "related": related, "title": f"{product['title']} · Luit & Loom"},
    )


@router.get("/cart")
def cart_page(request: Request) -> Response:
    return render_page(request, "commerce.html", {"kind": "cart", "title": "Your bag · Luit & Loom"})


@router.get("/checkout")
def checkout_page(request: Request) -> Response:
    payments_enabled = razorpay_config(Settings.from_env()) is not None
    return render_page(
        request,
        "commerce.html",
        {"kind": "checkout", "payments_enabled": payments_enabled, "title": "Checkout · Luit & Loom"},
    )


@router.post("/checkout")
async def checkout_submit(request: Request) -> Response:
    require_same_origin(request)
    payments_enabled = razorpay_config(Settings.from_env()) is not None
    try:
        payload = await checkout_payload(request)
        result = create_order(request_pool(request), payload, Settings.from_env().cookie_signing_key)
    except HTTPException as error:
        return render_page(
            request,
            "commerce.html",
            {
                "kind": "checkout",
                "fields": checkout_fields(await request.form()),
                "message": checkout_error_message(error),
                "payments_enabled": payments_enabled,
                "title": "Checkout · Luit & Loom",
            },
            error.status_code,
        )
    return RedirectResponse(f"/orders/{result['orderId']}?token={result['token']}", status_code=303)


@router.get("/orders/{order_id}")
def order_page(order_id: str, request: Request) -> Response:
    settings = Settings.from_env()
    query = request.query_params
    if not query.get("token") and not (
        settings.cookie_signing_key
        and verify_order_link(
            order_id,
            int(query["exp"]) if query.get("exp", "").isdigit() else None,
            query.get("sig"),
            settings.cookie_signing_key,
        )
    ):
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "That order could not be found."})
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


@router.get("/artisans")
@router.get("/our-story")
@router.get("/journal")
def editorial_page(request: Request) -> Response:
    page = EDITORIAL_PAGES[request.url.path]
    return render_page(
        request,
        "editorial.html",
        {"page": page, "title": f"{page['title']} · Luit & Loom"},
    )


@router.get("/pages/{editorial_path}")
def editorial_detail(editorial_path: str, request: Request) -> Response:
    page = EDITORIAL_PAGES.get(f"/pages/{editorial_path}")
    if page is None:
        return render_error(request, 404, "The requested page was not found.", str(uuid4()))
    return render_page(
        request,
        "editorial.html",
        {"page": page, "title": f"{page['title']} · Luit & Loom"},
    )
