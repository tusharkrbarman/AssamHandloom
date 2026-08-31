import { HttpError } from "./http";
import { razorpayConfig } from "./payments";

const RAZORPAY_REFUNDS_URL = "https://api.razorpay.com/v1/payments";

interface RazorpayRefundResponse {
  id?: unknown;
  status?: unknown;
  amount?: unknown;
}

export interface RefundRow {
  id: string;
  order_id: string;
  payment_id: string;
  provider_refund_id: string;
  amount_minor: number;
  currency: string;
  status: string;
  created_at: string;
}

function nowIso(): string {
  return new Date().toISOString();
}

async function postRefund(
  keyId: string,
  keySecret: string,
  providerPaymentId: string,
  amountMinor: number | null,
  receipt: string,
): Promise<{ refundId: string; status: string }> {
  let response: Response;
  try {
    response = await fetch(
      `${RAZORPAY_REFUNDS_URL}/${encodeURIComponent(providerPaymentId)}/refund`,
      {
        method: "POST",
        headers: {
          authorization: `Basic ${btoa(`${keyId}:${keySecret}`)}`,
          "content-type": "application/json",
        },
        body: JSON.stringify({
          ...(amountMinor === null ? {} : { amount: amountMinor }),
          receipt,
        }),
      },
    );
  } catch {
    throw new HttpError(
      502,
      "refund_provider_unavailable",
      "The payment provider could not be reached. Please try again shortly.",
    );
  }
  if (!response.ok) {
    throw new HttpError(
      502,
      "refund_failed",
      "The payment provider rejected the refund. Check the payment in the Razorpay dashboard.",
    );
  }
  let payload: RazorpayRefundResponse;
  try {
    payload = (await response.json()) as RazorpayRefundResponse;
  } catch {
    throw new HttpError(502, "refund_failed", "The payment provider responded unexpectedly.");
  }
  const refundId = typeof payload.id === "string" ? payload.id : "";
  const status = typeof payload.status === "string" ? payload.status.toLowerCase() : "";
  if (!refundId.startsWith("rfnd_") || !["processed", "pending", "failed"].includes(status)) {
    throw new HttpError(502, "refund_failed", "The payment provider responded unexpectedly.");
  }
  return { refundId, status };
}

export async function refundOrderPayment(
  db: D1Database,
  env: Env,
  orderId: string,
  amountMinorInput: number | null,
): Promise<RefundRow> {
  const config = razorpayConfig(env);
  if (!config) {
    throw new HttpError(503, "payments_disabled", "Online payments are not configured.");
  }
  const payment = await db
    .prepare(
      `SELECT id, provider_payment_id, amount_minor, currency FROM order_payments
      WHERE order_id = ? AND status = 'captured'
      ORDER BY created_at DESC LIMIT 1`,
    )
    .bind(orderId)
    .first<{
      id: string;
      provider_payment_id: string | null;
      amount_minor: number;
      currency: string;
    }>();
  if (!payment || !payment.provider_payment_id) {
    throw new HttpError(
      409,
      "no_captured_payment",
      "There is no captured online payment to refund on this order.",
    );
  }
  const refunded = await db
    .prepare(
      "SELECT COALESCE(SUM(amount_minor), 0) AS total FROM order_refunds WHERE order_id = ? AND status <> 'failed'",
    )
    .bind(orderId)
    .first<{ total: number }>();
  const refundedTotal = refunded?.total ?? 0;
  const remaining = payment.amount_minor - refundedTotal;
  if (remaining <= 0) {
    throw new HttpError(409, "already_refunded", "This payment has already been fully refunded.");
  }
  const target = amountMinorInput === null ? remaining : amountMinorInput;
  if (!Number.isSafeInteger(target) || target <= 0 || target > remaining) {
    throw new HttpError(
      422,
      "invalid_refund_amount",
      `Refund amount must be between 1 and ${remaining} paise.`,
    );
  }

  const existing = await db
    .prepare("SELECT COUNT(*) AS count FROM order_refunds WHERE order_id = ?")
    .bind(orderId)
    .first<{ count: number }>();
  const attempt = (existing?.count ?? 0) + 1;
  const receipt = `${orderId.replace(/-/g, "").slice(0, 30)}-${attempt}`;
  const { refundId, status } = await postRefund(
    config.keyId,
    config.keySecret,
    payment.provider_payment_id,
    target,
    receipt,
  );

  const row: RefundRow = {
    id: crypto.randomUUID(),
    order_id: orderId,
    payment_id: payment.id,
    provider_refund_id: refundId,
    amount_minor: target,
    currency: payment.currency,
    status,
    created_at: nowIso(),
  };
  await db
    .prepare(
      `INSERT INTO order_refunds (
        id, order_id, payment_id, provider_refund_id, amount_minor, currency, status, created_at
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)`,
    )
    .bind(
      row.id,
      row.order_id,
      row.payment_id,
      row.provider_refund_id,
      row.amount_minor,
      row.currency,
      row.status,
      row.created_at,
    )
    .run();
  return row;
}
