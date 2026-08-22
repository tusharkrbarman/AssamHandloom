import { processOutbox } from "./email";

const ABANDONED_ORDER_GRACE_MS = 24 * 60 * 60 * 1000;

export interface MaintenanceSummary {
  releasedReservations: number;
  expiredOrders: number;
  emailsSent: number;
  emailsRetried: number;
  emailsFailed: number;
}

export async function runMaintenance(env: Env): Promise<MaintenanceSummary> {
  const now = new Date();
  const at = now.toISOString();

  const released = await env.DB
    .prepare(
      "UPDATE inventory_reservations SET state = 'released' WHERE state = 'active' AND expires_at <= ?",
    )
    .bind(at)
    .run();

  const cutoff = new Date(now.getTime() - ABANDONED_ORDER_GRACE_MS).toISOString();
  const expired = await env.DB
    .prepare(
      `UPDATE orders SET status = 'expired', updated_at = ?
      WHERE status = 'pending'
        AND created_at <= ?
        AND NOT EXISTS (
          SELECT 1 FROM inventory_reservations r
          WHERE r.order_id = orders.id AND r.state = 'active'
        )`,
    )
    .bind(at, cutoff)
    .run();

  const outbox = await processOutbox(env.DB, env);

  return {
    releasedReservations: released.meta.changes ?? 0,
    expiredOrders: expired.meta.changes ?? 0,
    emailsSent: outbox.sent,
    emailsRetried: outbox.retried,
    emailsFailed: outbox.failed,
  };
}
