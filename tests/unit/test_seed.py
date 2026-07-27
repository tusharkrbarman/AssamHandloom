from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from app.seed import CatalogueValidationError, validate_catalogue


def _catalogue() -> dict[str, Any]:
    return json.loads(
        (Path(__file__).parents[2] / "app" / "data" / "river-reed-gold.json").read_text(
            encoding="utf-8"
        )
    )


def test_catalogue_validation_requires_all_sample_safety_markers(tmp_path: Path) -> None:
    catalogue = _catalogue()
    products = catalogue["products"]
    assert isinstance(products, list)
    products[0]["media"][0]["is_placeholder"] = False
    path = tmp_path / "catalogue.json"
    path.write_text(json.dumps(catalogue), encoding="utf-8")

    with pytest.raises(CatalogueValidationError, match="placeholder"):
        validate_catalogue(path)


def test_catalogue_validation_rejects_duplicate_stable_identifiers(tmp_path: Path) -> None:
    catalogue = _catalogue()
    products = catalogue["products"]
    assert isinstance(products, list)
    products[1]["slug"] = products[0]["slug"]
    path = tmp_path / "catalogue.json"
    path.write_text(json.dumps(catalogue), encoding="utf-8")

    with pytest.raises(CatalogueValidationError, match="unique"):
        validate_catalogue(path)


def test_catalogue_validation_rejects_casefolded_duplicate_media_orders(tmp_path: Path) -> None:
    catalogue = _catalogue()
    products = catalogue["products"]
    assert isinstance(products, list)
    products[0]["media"].append({**products[0]["media"][0], "url": "https://example.test/other"})
    path = tmp_path / "catalogue.json"
    path.write_text(json.dumps(catalogue), encoding="utf-8")

    with pytest.raises(CatalogueValidationError, match="display_order"):
        validate_catalogue(path)


def test_catalogue_validation_rejects_casefold_duplicate_stable_identifiers(tmp_path: Path) -> None:
    catalogue = _catalogue()
    products = catalogue["products"]
    assert isinstance(products, list)
    products[1]["slug"] = products[0]["slug"].upper()
    path = tmp_path / "catalogue.json"
    path.write_text(json.dumps(catalogue), encoding="utf-8")

    with pytest.raises(CatalogueValidationError, match="unique"):
        validate_catalogue(path)
