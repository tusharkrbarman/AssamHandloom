from __future__ import annotations

import os
import uuid
from collections.abc import Iterator
from contextlib import contextmanager

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine, make_url


def _schema_url(database_url: str, schema_name: str) -> str:
    url = make_url(database_url)
    return url.update_query_dict({"options": f"-csearch_path={schema_name}"}).render_as_string(
        hide_password=False
    )


def _alembic_config(schema_url: str) -> Config:
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", schema_url.replace("%", "%%"))
    return config


@contextmanager
def _legacy_schema() -> Iterator[tuple[Engine, Config]]:
    database_url = os.environ["TEST_DATABASE_URL"]
    schema_name = f"migration_{uuid.uuid4().hex}"
    admin_engine = create_engine(database_url)
    schema_engine: Engine | None = None
    try:
        with admin_engine.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema_name}"'))
        schema_url = _schema_url(database_url, schema_name)
        schema_engine = create_engine(schema_url)
        config = _alembic_config(schema_url)
        command.upgrade(config, "0003_sample_catalogue_ownership")
        yield schema_engine, config
    finally:
        if schema_engine is not None:
            schema_engine.dispose()
        with admin_engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema_name}" CASCADE'))
        admin_engine.dispose()


def _insert_case_only_legacy_duplicates(engine: Engine) -> tuple[uuid.UUID, uuid.UUID]:
    first_product_id = uuid.uuid4()
    duplicate_product_id = uuid.uuid4()
    first_variant_id = uuid.uuid4()
    duplicate_variant_id = uuid.uuid4()
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO products (id, slug, title, silk_type)
                VALUES
                    (:first_id, 'luit-dawn', 'First legacy product', 'Muga'),
                    (:duplicate_id, 'LUIT-DAWN', 'Duplicate legacy product', 'Muga')
                """
            ),
            {"first_id": first_product_id, "duplicate_id": duplicate_product_id},
        )
        connection.execute(
            text(
                """
                INSERT INTO variants (id, product_id, sku, price_minor, currency)
                VALUES
                    (:first_id, :product_id, 'RRG-MUGA-001', 100, 'INR'),
                    (:duplicate_id, :product_id, 'rrg-muga-001', 100, 'INR')
                """
            ),
            {
                "first_id": first_variant_id,
                "duplicate_id": duplicate_variant_id,
                "product_id": first_product_id,
            },
        )
    return duplicate_product_id, duplicate_variant_id


def _catalogue_index_names(engine: Engine) -> set[str]:
    inspector = inspect(engine)
    return {
        index["name"]
        for table_name in ("products", "variants")
        for index in inspector.get_indexes(table_name)
        if index["name"] is not None
    }


def test_canonical_key_migration_reports_legacy_duplicates_before_index_ddl() -> None:
    with _legacy_schema() as (engine, config):
        duplicate_product_id, duplicate_variant_id = _insert_case_only_legacy_duplicates(engine)

        with pytest.raises(RuntimeError) as captured:
            command.upgrade(config, "head")

        message = str(captured.value)
        assert "product slugs canonical values: luit-dawn" in message
        assert "variant SKUs canonical values: RRG-MUGA-001" in message
        assert "Resolve or rename" in message
        assert "rerun this migration" in message
        assert "uq_products_slug_canonical" not in _catalogue_index_names(engine)
        assert "uq_variants_sku_canonical" not in _catalogue_index_names(engine)

        with engine.begin() as connection:
            connection.execute(
                text("DELETE FROM variants WHERE id = :id"),
                {"id": duplicate_variant_id},
            )
            connection.execute(
                text("DELETE FROM products WHERE id = :id"),
                {"id": duplicate_product_id},
            )

        command.upgrade(config, "head")

        index_names = _catalogue_index_names(engine)
        assert "uq_products_slug_canonical" in index_names
        assert "uq_variants_sku_canonical" in index_names
        with engine.connect() as connection:
            assert (
                connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
                == "0004_canonical_catalogue_keys"
            )
