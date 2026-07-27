from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from fastapi import Request
from fastapi.templating import Jinja2Templates
from starlette.responses import Response

templates = Jinja2Templates(directory="app/templates")


def _template_context(request: Request) -> dict[str, str]:
    """Provide trusted, request-scoped presentation values to templates."""

    origin = str(request.app.state.settings.public_base_url).rstrip("/")
    path = "/" + request.url.path.lstrip("/")
    return {"canonical_url": f"{origin}{path}"}


templates.context_processors.append(_template_context)


def is_htmx(request: Request) -> bool:
    """Return true only for an explicit HTMX request header."""

    return request.headers.get("HX-Request", "").lower() == "true"


def render(
    request: Request,
    template: str,
    context: Mapping[str, Any] | None = None,
    status_code: int = 200,
) -> Response:
    """Render a server-side template with the current request available."""

    return templates.TemplateResponse(
        request=request,
        name=template,
        context=dict(context or {}),
        status_code=status_code,
    )
