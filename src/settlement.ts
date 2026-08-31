export type SettlementOutcome = "paid" | "already_paid" | "expired";

function nowIso(): string {
  return new Date().toISOString();
}

export async function expirePendingOrder(
  db: D1Database,
  orderId: string,
  at = nowIso(),
): Promise<void> {
  await db.batch([
    db
      .prepare(
        `UPDATE inventory_reservations SET state = 'released'
        WHERE order_id = ? AND state = 'active'
          AND EXISTS (SELECT 1 FROM orders WHERE id = ? AND status = 'pending')`,
      )
      .bind(orderId, orderId),
    db
      .prepare(
        `UPDATE orders SET status = 'expired', updated_at = ?
        WHERE id = ? AND status = 'pending'
          AND NOT EXISTS (
            SELECT 1 FROM inventory_reservations
            WHERE order_id = ? AND state = 'active'
          )`,
      )
      .bind(at, orderId, orderId),
  ]);
}

export async function settleOrderStock(
  db: D1Database,
  orderId: string,
  actor: "owner" | "payment",
): Promise<SettlementOutcome> {
  const at = nowIso();
  const [claim] = await db.batch([
    db
      .prepare(
        `UPDATE orders SET status = 'paid', updated_at = ?
        WHERE id = ? AND status = 'pending'
          AND EXISTS (
            SELECT 1 FROM inventory_reservations WHERE order_id = ?
          )
          AND NOT EXISTS (
            SELECT 1
            FROM inventory_reservations reservation
            LEFT JOIN inventory_items stock ON stock.variant_id = reservation.variant_id
            WHERE reservation.order_id = ?
              AND (
                reservation.state <> 'active'
                OR reservation.expires_at <= ?
                OR stock.variant_id IS NULL
                OR stock.quantity < reservation.quantity
              )
          )`,
      )
      .bind(at, orderId, orderId, orderId, at),
    db
      .prepare(
        `INSERT INTO inventory_adjustments (
          id, variant_id, delta, reason, idempotency_key, actor, created_at
        )
        SELECT
          'sale:' || reservation.id,
          reservation.variant_id,
          -reservation.quantity,
          'Order ' || reservation.order_id || ' paid',
          'sale:' || reservation.id,
          ?,
          ?
        FROM inventory_reservations reservation
        JOIN orders order_record ON order_record.id = reservation.order_id
        WHERE reservation.order_id = ?
          AND reservation.state = 'active'
          AND order_record.status = 'paid'`,
      )
      .bind(actor, at, orderId),
    db
      .prepare(
        `UPDATE inventory_items
        SET quantity = quantity - (
          SELECT reservation.quantity
          FROM inventory_reservations reservation
          JOIN inventory_adjustments adjustment
            ON adjustment.id = 'sale:' || reservation.id
          WHERE reservation.order_id = ?
            AND reservation.variant_id = inventory_items.variant_id
            AND reservation.state = 'active'
          LIMIT 1
        ), version = version + 1, updated_at = ?
        WHERE EXISTS (
          SELECT 1
          FROM inventory_reservations reservation
          JOIN inventory_adjustments adjustment
            ON adjustment.id = 'sale:' || reservation.id
          WHERE reservation.order_id = ?
            AND reservation.variant_id = inventory_items.variant_id
            AND reservation.state = 'active'
        )`,
      )
      .bind(orderId, at, orderId),
    db
      .prepare(
        `UPDATE inventory_reservations SET state = 'consumed'
        WHERE order_id = ? AND state = 'active'
          AND EXISTS (
            SELECT 1 FROM inventory_adjustments
            WHERE id = 'sale:' || inventory_reservations.id
          )`,
      )
      .bind(orderId),
  ]);

  if ((claim?.meta.changes ?? 0) > 0) {
    return "paid";
  }
  const status = await db.prepare("SELECT status FROM orders WHERE id = ?")
    .bind(orderId)
    .first<string>("status");
  if (status === "paid" || status === "fulfilled") {
    return "already_paid";
  }
  if (status === "pending") {
    await expirePendingOrder(db, orderId, at);
  }
  return "expired";
}
