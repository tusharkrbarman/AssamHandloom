from contextlib import nullcontext

from app.inventory import adjust_inventory


VARIANT_ID = "123e4567-e89b-12d3-a456-426614174000"
KEY = "123e4567-e89b-42d3-a456-426614174000"


class InventoryCursor:
    def __init__(self) -> None:
        self.rowcount = 1
        self.statements: list[tuple[str, tuple[object, ...]]] = []
        self.calls = 0

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        return None

    def execute(self, statement: str, params: tuple[object, ...] = ()) -> None:
        self.calls += 1
        self.statements.append((statement, params))

    def fetchone(self):
        statement = self.statements[-1][0]
        if "FROM inventory_adjustments" in statement:
            return None
        if "FROM inventory_items" in statement:
            return {"quantity": 2}
        return None


class InventoryConnection:
    def __init__(self) -> None:
        self.cursor_instance = InventoryCursor()

    def cursor(self):
        return self.cursor_instance

    def transaction(self):
        return nullcontext()


class InventoryPool:
    def __init__(self) -> None:
        self.connection_instance = InventoryConnection()

    def connection(self):
        return nullcontext(self.connection_instance)


def test_inventory_adjustment_is_audited_and_idempotent_key_is_used() -> None:
    pool = InventoryPool()
    result = adjust_inventory(pool, VARIANT_ID, 3, " received ", KEY)  # type: ignore[arg-type]

    assert result["variantId"] == VARIANT_ID
    assert result["delta"] == 3
    assert result["idempotencyKey"] == KEY
    assert any("INSERT INTO inventory_adjustments" in statement for statement, _params in pool.connection_instance.cursor_instance.statements)
