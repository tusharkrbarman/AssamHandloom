from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
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


@router.get("/{editorial_path:path}")
def editorial_page(editorial_path: str, request: Request) -> Response:
    page = EDITORIAL_PAGES.get("/" + editorial_path)
    if page is None:
        return render_error(request, 404, "The requested page was not found.", str(uuid4()))
    return render_page(
        request,
        "editorial.html",
        {"page": page, "title": f"{page['title']} · Luit & Loom"},
    )
