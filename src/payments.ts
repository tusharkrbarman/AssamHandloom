import { HttpError, json, requireSameOrigin } from "./http";

const RAZORPAY_ORDERS_URL = "https://api.razorpay.com/v1/orders";

interface RazorpaySecrets {
  RAZORPAY_KEY_ID?: string;
  RAZORPAY_KEY_SECRET?: string;
  RAZORPAY_WEBHOOK_SECRET?: string;
}

export interface RazorpayConfig {
  keyId: string;
  keySecret: string;
  webhookSecret: string;
}

interface PayableOrder {
  id: string;
  totalMinor: number;
  currency: string;
}

interface OrderPaymentRow {
  id: string;
  order_id: string;
  provider_order_id: string;
  provider_payment_id: string | null;
  amount_minor: number;
  currency: string;
  status: string;
}

interface RazorpayOrderResponse {
  id?: unknown;
}

function nowIso(): string {
  return new Date().toISOString();
}

export function razorpayConfig(env: Env): RazorpayConfig | null {
  const secrets = env as Env & RazorpaySecrets;
  const keyId = secrets.RAZORPAY_KEY_ID?.trim() ?? "";
  const keySecret = secrets.RAZORPAY_KEY_SECRET?.trim() ?? "";
  const webhookSecret = secrets.RAZORPAY_WEBHOOK_SECRET?.trim() ?? "";
  if (!keyId || !keySecret || !webhookSecret) {
    return null;
  }
  return { keyId, keySecret, webhookSecret };
}

function toHex(buffer: ArrayBuffer): string {
  return [...new Uint8Array(buffer)]
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");
}

async function hmacHex(payload: string, secret: string): Promise<string> {
  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  return toHex(await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(payload)));
}

function signaturesMatch(expected: string, received: string): boolean {
  if (!expected || expected.length !== received.length) {
    return false;
  }
  let difference = 0;
  for (let index = 0; index < expected.length; index += 1) {
    difference |= expected.charCodeAt(index) ^ received.charCodeAt(index);
  }
  return difference === 0;
}

function requireText(value: unknown, code: string, message: string): string {
  const text = typeof value === "string" ? value.trim() : "";
  if (!text) {
    throw new HttpError(422, code, message);
  }
  return text;
}

async function readJsonBody(request: Request): Promise<Record<string, unknown>> {
  const contentType = request.headers.get("content-type")?.toLowerCase() ?? "";
  if (!contentType.startsWith("application/json")) {
    throw new HttpError(415, "unsupported_media_type", "A JSON body is required.");
  }
  try {
    const parsed: unknown = await request.json();
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
      throw new HttpError(422, "invalid_request", "The request body could not be read.");
    }
    return parsed as Record<string, unknown>;
  } catch (error) {
    if (error instanceof HttpError) throw error;
    throw new HttpError(400, "invalid_json", "The request body could not be read.");
  }
}

async function loadPayableOrder(
  db: D1Database,
  orderId: unknown,
  token: unknown,
): Promise<PayableOrder> {
  const id = typeof orderId === "string" ? orderId.trim() : "";
  const value = typeof token === "string" ? token.trim() : "";
  const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
  if (!uuidPattern.test(id) || !uuidPattern.test(value)) {
    throw new HttpError(404, "not_found", "That order could not be found.");
  }
  const order = await db
    .prepare("SELECT id, status, total_minor, currency FROM orders WHERE id = ? AND token = ?")
    .bind(id, value)
    .first<{ id: string; status: string; total_minor: number; currency: string }>();
  if (!order) {
    throw new HttpError(404, "not_found", "That order could not be found.");
  }
  if (order.status !== "pending") {
    throw new HttpError(409, "payment_not_pending", "This order is not awaiting payment.");
  }
  return { id: order.id, totalMinor: order.total_minor, currency: order.currency };
}

async function createProviderOrder(config: RazorpayConfig, order: PayableOrder): Promise<string> {
  let response: Response;
  try {
    response = await fetch(RAZORPAY_ORDERS_URL, {
      method: "POST",
      headers: {
        authorization: `Basic ${btoa(`${config.keyId}:${config.keySecret}`)}`,
        "content-type": "application/json",
      },
      body: JSON.stringify({
        amount: order.totalMinor,
        currency: order.currency,
        receipt: order.id,
        notes: { order_id: order.id },
      }),
    });
  } catch {
    throw new HttpError(
      502,
      "payment_provider_unavailable",
      "The payment provider could not be reached. Please try again shortly.",
    );
  }
  if (!response.ok) {
    throw new HttpError(
      502,
      "payment_provider_unavailable",
      "The payment provider rejected the request. Please try again shortly.",
    );
  }
  let payload: RazorpayOrderResponse;
  try {
    payload = (await response.json()) as RazorpayOrderResponse;
  } catch {
    throw new HttpError(502, "payment_provider_unavailable", "The payment provider responded unexpectedly.");
  }
  const providerOrderId = typeof payload.id === "string" ? payload.id : "";
  if (!providerOrderId.startsWith("order_")) {
    throw new HttpError(502, "payment_provider_unavailable", "The payment provider responded unexpectedly.");
  }
  return providerOrderId;
}

async function ensureProviderOrder(
  db: D1Database,
  config: RazorpayConfig,
  order: PayableOrder,
): Promise<OrderPaymentRow> {
  const captured = await db
    .prepare("SELECT id FROM order_payments WHERE order_id = ? AND status = 'captured' LIMIT 1")
    .bind(order.id)
    .first<{ id: string }>();
  if (captured) {
    throw new HttpError(409, "already_paid", "This order has already been paid.");
  }
  const existing = await db
    .prepare(
      `SELECT id, order_id, provider_order_id, provider_payment_id, amount_minor, currency, status
      FROM order_payments WHERE order_id = ? AND status = 'created'
      ORDER BY created_at DESC LIMIT 1`,
    )
    .bind(order.id)
    .first<OrderPaymentRow>();
  if (existing && existing.amount_minor === order.totalMinor && existing.currency === order.currency) {
    return existing;
  }
  const providerOrderId = await createProviderOrder(config, order);
  const createdAt = nowIso();
  const row: OrderPaymentRow = {
    id: crypto.randomUUID(),
    order_id: order.id,
    provider_order_id: providerOrderId,
    provider_payment_id: null,
    amount_minor: order.totalMinor,
    currency: order.currency,
    status: "created",
  };
  await db
    .prepare(
      `INSERT INTO order_payments (
        id, order_id, provider, provider_order_id, provider_payment_id,
        amount_minor, currency, status, created_at, updated_at
      ) VALUES (?, ?, 'razorpay', ?, NULL, ?, ?, 'created', ?, ?)`,
    )
    .bind(
      row.id,
      row.order_id,
      row.provider_order_id,
      row.amount_minor,
      row.currency,
      createdAt,
      createdAt,
    )
    .run();
  return row;
}

async function findPaymentByCheckoutReference(
  db: D1Database,
  orderId: string,
  token: string,
  providerOrderId: string,
): Promise<OrderPaymentRow> {
  const row = await db
    .prepare(
      `SELECT p.id, p.order_id, p.provider_order_id, p.provider_payment_id,
        p.amount_minor, p.currency, p.status
      FROM order_payments p
      JOIN orders o ON o.id = p.order_id
      WHERE p.provider_order_id = ? AND o.id = ? AND o.token = ?
      LIMIT 1`,
    )
    .bind(providerOrderId, orderId, token)
    .first<OrderPaymentRow>();
  if (!row) {
    throw new HttpError(404, "payment_not_found", "That payment reference could not be found.");
  }
  return row;
}

export async function applyCapturedPayment(
  db: D1Database,
  payment: OrderPaymentRow,
  providerPaymentId: string,
): Promise<"captured" | "already_captured"> {
  if (payment.status === "captured") {
    if (payment.provider_payment_id === providerPaymentId) {
      return "already_captured";
    }
    throw new HttpError(409, "payment_conflict", "This order was already paid with a different payment.");
  }
  const at = nowIso();
  await db.batch([
    db
      .prepare(
        `UPDATE order_payments
        SET provider_payment_id = ?, status = 'captured', failure_reason = NULL, updated_at = ?
        WHERE id = ? AND status <> 'captured'`,
      )
      .bind(providerPaymentId, at, payment.id),
    db
      .prepare("UPDATE orders SET status = 'paid', updated_at = ? WHERE id = ? AND status = 'pending'")
      .bind(at, payment.order_id),
    db
      .prepare("UPDATE inventory_reservations SET state = 'consumed' WHERE order_id = ? AND state = 'active'")
      .bind(payment.order_id),
  ]);
  return "captured";
}

interface RazorpayEventPayload {
  event?: unknown;
  payload?: {
    payment?: { entity?: Record<string, unknown> | null };
    order?: { entity?: Record<string, unknown> | null };
  } | null;
}

function eventText(record: Record<string, unknown>, key: string): string {
  const value = record[key];
  return typeof value === "string" ? value.trim() : "";
}

async function handleWebhook(request: Request, env: Env): Promise<Response> {
  const config = razorpayConfig(env);
  if (!config) {
    throw new HttpError(503, "payments_disabled", "Online payments are not available yet.");
  }
  const raw = await request.text();
  const signature = request.headers.get("x-razorpay-signature") ?? "";
  const expected = await hmacHex(raw, config.webhookSecret);
  if (!signaturesMatch(expected, signature)) {
    throw new HttpError(400, "invalid_webhook_signature", "Webhook signature verification failed.");
  }
  let event: RazorpayEventPayload;
  try {
    event = JSON.parse(raw) as RazorpayEventPayload;
  } catch {
    throw new HttpError(400, "invalid_webhook_payload", "The webhook payload could not be read.");
  }
  const type = typeof event.event === "string" ? event.event : "";

  if (type === "payment.failed") {
    const entity = event.payload?.payment?.entity;
    const providerOrderId = entity ? eventText(entity, "order_id") : "";
    if (providerOrderId.startsWith("order_")) {
      await env.DB.prepare(
        `UPDATE order_payments
        SET status = 'failed', failure_reason = ?, updated_at = ?
        WHERE provider_order_id = ? AND status <> 'captured'`,
      )
        .bind(eventText(entity ?? {}, "error_description") || "Payment failed.", nowIso(), providerOrderId)
        .run();
    }
    return json({ received: true });
  }

  if (type === "payment.captured" || type === "order.paid") {
    const paymentEntity = event.payload?.payment?.entity ?? null;
    const orderEntity = event.payload?.order?.entity ?? null;
    const source = paymentEntity ?? orderEntity;
    if (!source) {
      return json({ received: true });
    }
    const providerPaymentId = paymentEntity ? eventText(paymentEntity, "id") : "";
    const providerOrderId =
      eventText(source, "order_id") || (type === "order.paid" ? eventText(source, "id") : "");
    if (!providerPaymentId.startsWith("pay_")) {
      return json({ received: true });
    }
    const row = await env.DB.prepare(
      `SELECT id, order_id, provider_order_id, provider_payment_id, amount_minor, currency, status
      FROM order_payments WHERE provider_order_id = ? LIMIT 1`,
    )
      .bind(providerOrderId)
      .first<OrderPaymentRow>();
    if (!row) {
      return json({ received: true });
    }
    const amount = typeof source.amount === "number" ? Math.floor(source.amount) : Number.NaN;
    const currency = eventText(source, "currency").toUpperCase();
    if (amount !== row.amount_minor || currency !== row.currency) {
      throw new HttpError(409, "payment_amount_mismatch", "The reported payment does not match this order.");
    }
    await applyCapturedPayment(env.DB, row, providerPaymentId);
  }

  return json({ received: true });
}

export async function routePayments(request: Request, env: Env): Promise<Response | null> {
  const path = new URL(request.url).pathname;

  if (request.method === "POST" && path === "/api/payments/session") {
    requireSameOrigin(request);
    const config = razorpayConfig(env);
    if (!config) {
      throw new HttpError(503, "payments_disabled", "Online payments are not available yet.");
    }
    const body = await readJsonBody(request);
    const order = await loadPayableOrder(env.DB, body.orderId, body.token);
    const payment = await ensureProviderOrder(env.DB, config, order);
    return json({
      keyId: config.keyId,
      razorpayOrderId: payment.provider_order_id,
      amountMinor: payment.amount_minor,
      currency: payment.currency,
    });
  }

  if (request.method === "POST" && path === "/api/payments/verify") {
    requireSameOrigin(request);
    const config = razorpayConfig(env);
    if (!config) {
      throw new HttpError(503, "payments_disabled", "Online payments are not available yet.");
    }
    const body = await readJsonBody(request);
    const orderId = requireText(body.orderId, "invalid_request", "The payment reference is incomplete.");
    const token = requireText(body.token, "invalid_request", "The payment reference is incomplete.");
    const razorpayOrderId = requireText(
      body.razorpayOrderId,
      "invalid_callback",
      "The payment confirmation is incomplete.",
    );
    const razorpayPaymentId = requireText(
      body.razorpayPaymentId,
      "invalid_callback",
      "The payment confirmation is incomplete.",
    );
    const signature = requireText(
      body.signature,
      "invalid_callback",
      "The payment confirmation is incomplete.",
    );
    const payment = await findPaymentByCheckoutReference(env.DB, orderId, token, razorpayOrderId);
    const expected = await hmacHex(`${razorpayOrderId}|${razorpayPaymentId}`, config.keySecret);
    if (!signaturesMatch(expected, signature)) {
      throw new HttpError(400, "invalid_payment_signature", "We could not confirm this payment. No money was captured by us.");
    }
    await applyCapturedPayment(env.DB, payment, razorpayPaymentId);
    return json({ status: "paid" });
  }

  if (request.method === "POST" && path === "/api/webhooks/razorpay") {
    return handleWebhook(request, env);
  }

  return null;
}
