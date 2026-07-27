from __future__ import annotations

from dataclasses import dataclass
from math import ceil
from typing import Literal


@dataclass(frozen=True)
class ProductListQuery:
    """Supported public catalogue filters and stable pagination settings."""

    search: str | None = None
    collection_slug: str | None = None
    silk_types: tuple[str, ...] = ()
    colours: tuple[str, ...] = ()
    occasions: tuple[str, ...] = ()
    available_only: bool = False
    sort: Literal["featured", "newest", "price_asc", "price_desc"] = "featured"
    page: int = 1
    page_size: int = 12

    def __post_init__(self) -> None:
        if self.page < 1:
            raise ValueError("page must be at least 1")
        if not 1 <= self.page_size <= 100:
            raise ValueError("page_size must be between 1 and 100")


@dataclass(frozen=True)
class ProductCard:
    """The minimum public data required to render a catalogue card."""

    slug: str
    title: str
    silk_type: str
    artisan_name: str | None
    price_minor: int
    currency: str
    available: bool
    primary_image: str | None
    is_sample: bool = False

    @property
    def display_price(self) -> str:
        """Format stored minor units without ever converting through float."""

        amount, remainder = divmod(self.price_minor, 100)
        formatted = f"{amount:,}" if remainder == 0 else f"{amount:,}.{remainder:02d}"
        return f"₹{formatted}" if self.currency == "INR" else f"{self.currency} {formatted}"

    @property
    def sample_label(self) -> str | None:
        """Expose sample data clearly to the storefront."""

        return "Sample" if self.is_sample else None


@dataclass(frozen=True)
class ProductVariant:
    """A public variant representation for a product detail page."""

    sku: str
    title: str | None
    price_minor: int
    compare_at_price_minor: int | None
    currency: str
    weight_grams: int | None
    available: bool


@dataclass(frozen=True)
class ProductDetail:
    """The public data required for one product detail page."""

    slug: str
    title: str
    description: str | None
    silk_type: str
    colour: str | None
    occasion: str | None
    artisan_name: str | None
    media: tuple[str, ...]
    variants: tuple[ProductVariant, ...]
    is_sample: bool
    sample_label: str | None


@dataclass(frozen=True)
class Page[T]:
    """A stable page of catalogue records and the matching total."""

    items: list[T]
    total: int
    page: int
    page_size: int

    @property
    def total_pages(self) -> int:
        return ceil(self.total / self.page_size) if self.total else 0
