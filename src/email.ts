import { formatMoney } from "./catalogue";
import { escapeHtml } from "./http";
import { createOrderLink } from "./links";

const RESEND_ENDPOINT = "https://api.resend.com/emails";
const MAX_ATTEMPTS = 5;
const BACKOFF_CAP_MINUTES = 60;

export type OutboxKind = "order_confirmation" | "order_paid" | "order_shipped";

interface MailSecrets {
  RESEND_API_KEY?: string;
  MAIL_FROM?: string;
  PUBLIC_BASE_URL?: string;
}

interface MailConfig {
  apiKey: string;
  from: string;
  baseUrl: string;
}

interface OutboxRow {
  id: string;
  kind: OutboxKind;
  order_id: string;
  to_email: string;
  status: string;
  attempts: number;
}

interface OrderEmailRow {
  id: string;
  email: string;
  status: string;
  currency: string;
  subtotal_minor: number;
  shipping_minor: number;
  total_minor: number;
  ship_name: string;
  ship_city: string;
  created_at: string;
}

interface OrderItemEmailRow {
  product_title: string;
  variant_title: string;
  sku: string;
  quantity: number;
  unit_price_minor: number;
  line_total_minor: number;
}

function nowIso(): string {
  return new Date().toISOString();
}

export function mailConfig(env: Env): MailConfig | null {
  const secrets = env as Env & MailSecrets;
  const apiKey = secrets.RESEND_API_KEY?.trim() ?? "";
  const from = secrets.MAIL_FROM?.trim() ?? "";
  if (!apiKey || !from) {
    return null;
  }
  return { apiKey, from, baseUrl: secrets.PUBLIC_BASE_URL?.trim() ?? "" };
}

export async function enqueueOrderEmail(
  db: D1Database,
  env: Env,
  kind: OutboxKind,
  orderId: string,
): Promise<void> {
  if (!mailConfig(env)) {
    return;
  }
  const order = await db
    .prepare("SELECT email FROM orders WHERE id = ?")
    .bind(orderId)
    .first<{ email: string }>();
  if (!order) {
    return;
  }
  const at = nowIso();
  await db
    .prepare(
      `INSERT OR IGNORE INTO email_outbox (
        id, kind, order_id, to_email, status, attempts, next_attempt_at, created_at, updated_at
      ) VALUES (?, ?, ?, ?, 'queued', 0, ?, ?, ?)`,
    )
    .bind(crypto.randomUUID(), kind, orderId, order.email, at, at, at)
    .run();
}

function shortReference(orderId: string): string {
  return orderId.slice(0, 8).toUpperCase();
}

async function buildOrderEmail(
  db: D1Database,
  env: Env,
  kind: OutboxKind,
  orderId: string,
): Promise<{ subject: string; html: string }> {
  const order = await db
    .prepare(
      `SELECT id, email, status, currency, subtotal_minor, shipping_minor,
        total_minor, ship_name, ship_city, created_at FROM orders WHERE id = ?`,
    )
    .bind(orderId)
    .first<OrderEmailRow>();
  if (!order) {
    throw new Error("order_missing");
  }
  const items = await db
    .prepare(
      `SELECT product_title, variant_title, sku, quantity, unit_price_minor, line_total_minor
      FROM order_items WHERE order_id = ? ORDER BY created_at ASC, id ASC`,
    )
    .bind(orderId)
    .all<OrderItemEmailRow>();
  const reference = shortReference(orderId);
  const rowsHtml = (items.results ?? [])
    .map(
      (item) => `<tr>
        <td style="padding:6px 12px 6px 0">${escapeHtml(item.product_title)} · ${escapeHtml(item.variant_title)}</td>
        <td style="padding:6px 12px">${item.quantity}</td>
        <td style="padding:6px 0 6px 12px; text-align:right">${escapeHtml(formatMoney(item.line_total_minor, order.currency))}</td>
      </tr>`,
    )
    .join("");
  const subject =
    kind === "order_confirmation"
      ? `Your Luit & Loom order ${reference}`
      : kind === "order_paid"
        ? `Payment received — Luit & Loom order ${reference}`
        : `Your Luit & Loom order ${reference} has shipped`;
  let actionHtml = "";
  if (kind === "order_confirmation" && order.status === "pending") {
    const baseUrl = mailConfig(env)?.baseUrl.replace(/\/$/, "") ?? "";
    if (baseUrl) {
      const linkQuery = await createOrderLink(env, orderId);
      actionHtml = `<p><a href="${baseUrl}/orders/${linkQuery}">View your order and complete payment</a></p>`;
    }
  }
  const intro =
    kind === "order_confirmation"
      ?       `<p>Hello ${escapeHtml(order.ship_name)}, thank you for your order. We have reserved your weaves and will confirm once payment is complete.</p>`
      : kind === "order_paid"
        ? `<p>Hello ${escapeHtml(order.ship_name)}, we have received your payment. Your weaves are confirmed and will be prepared for dispatch.</p>`
        : `<p>Hello ${escapeHtml(order.ship_name)}, your order has been dispatched and is on its way to ${escapeHtml(order.ship_city)}. Thank you for supporting handwoven silk.</p>`;
  const html = `<div style="font-family:Georgia,serif; max-width:560px; margin:0 auto">
    <h2 style="font-weight:normal">Luit &amp; Loom</h2>
    ${intro}
    ${actionHtml}
    <table style="border-collapse:collapse; width:100%">
      <thead><tr>
        <th scope="col" style="text-align:left; padding:6px 12px 6px 0">Item</th>
        <th scope="col" style="text-align:left; padding:6px 12px">Qty</th>
        <th scope="col" style="text-align:right; padding:6px 0 6px 12px">Total</th>
      </tr></thead>
      <tbody>${rowsHtml}</tbody>
    </table>
    <p style="text-align:right">Subtotal ${escapeHtml(formatMoney(order.subtotal_minor, order.currency))}<br>
    Shipping ${order.shipping_minor === 0 ? "Free" : escapeHtml(formatMoney(order.shipping_minor, order.currency))}<br>
    <strong>Total ${escapeHtml(formatMoney(order.total_minor, order.currency))}</strong></p>
    <p>Order reference <strong>${reference}</strong>.</p>
  </div>`;
  return { subject, html };
}

async function sendViaResend(config: MailConfig, to: string, subject: string, html: string): Promise<void> {
  let response: Response;
  try {
    response = await fetch(RESEND_ENDPOINT, {
      method: "POST",
      headers: {
        authorization: `Bearer ${config.apiKey}`,
        "content-type": "application/json",
      },
      body: JSON.stringify({ from: config.from, to: [to], subject, html }),
    });
  } catch (error) {
    throw error instanceof Error ? error : new Error("resend_unreachable");
  }
  if (!response.ok) {
    throw new Error(`resend_status_${response.status}`);
  }
}

export async function processOutbox(
  db: D1Database,
  env: Env,
  limit = 25,
): Promise<{ sent: number; retried: number; failed: number }> {
  const summary = { sent: 0, retried: 0, failed: 0 };
  const config = mailConfig(env);
  if (!config) {
    return summary;
  }
  const due = await db
    .prepare(
      `SELECT id, kind, order_id, to_email, status, attempts FROM email_outbox
      WHERE status = 'queued' AND next_attempt_at <= ?
      ORDER BY next_attempt_at ASC LIMIT ?`,
    )
    .bind(nowIso(), limit)
    .all<OutboxRow>();
  for (const row of due.results ?? []) {
    try {
      const { subject, html } = await buildOrderEmail(db, env, row.kind, row.order_id);
      await sendViaResend(config, row.to_email, subject, html);
      await db
        .prepare("UPDATE email_outbox SET status = 'sent', sent_at = ?, last_error = NULL, updated_at = ? WHERE id = ?")
        .bind(nowIso(), nowIso(), row.id)
        .run();
      summary.sent += 1;
    } catch (error) {
      const attempts = row.attempts + 1;
      const message = error instanceof Error ? error.message.slice(0, 300) : "unknown_error";
      if (attempts >= MAX_ATTEMPTS) {
        await db
          .prepare("UPDATE email_outbox SET status = 'failed', attempts = ?, last_error = ?, updated_at = ? WHERE id = ?")
          .bind(attempts, message, nowIso(), row.id)
          .run();
        summary.failed += 1;
      } else {
        const backoffMinutes = Math.min(BACKOFF_CAP_MINUTES, 2 ** attempts);
        const nextAttemptAt = new Date(Date.now() + backoffMinutes * 60_000).toISOString();
        await db
          .prepare("UPDATE email_outbox SET attempts = ?, next_attempt_at = ?, last_error = ?, updated_at = ? WHERE id = ?")
          .bind(attempts, nextAttemptAt, message, nowIso(), row.id)
          .run();
        summary.retried += 1;
      }
    }
  }
  return summary;
}
