import { env, SELF } from "cloudflare:test";
import { beforeEach, describe, expect, it } from "vitest";
import { routePayments } from "../src/payments";

const ORIGIN = "https://example.com";
const PRODUCT_ID = "product-payments";
const VARIANT_A = "aaaa1111-1111-4111-8111-111111111111";
const KEY_ID = "rzp_test_1234567890abcdef";
const KEY_SECRET = "test-key-secret-with-at-least-32-characters";
const WEBHOOK_SECRET = "test-webhook-secret-with-at-least-32-char";
const TOTAL_MINOR = 10000;

async function hmacHex(payload: string, secret: string): Promise<string> {
  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  return [...new Uint8Array(await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(payload)))]
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");
}

async function seedCatalogue(): Promise<void> {
  const now = new Date().toISOString();
  await env.DB.batch([
    env.DB
      .prepare(
        `INSERT INTO products (
          id, slug, title, description, silk_type, publication_state,
          featured_rank, created_at, updated_at
        ) VALUES (?, 'payments-saree', 'Payments Saree', '', 'Muga', 'published', 0, ?, ?)`,
      )
      .bind(PRODUCT_ID, now, now),
    env.DB
      .prepare(
        `INSERT INTO variants (
          id, product_id, sku, title, price_minor, currency,
          publication_state, created_at, updated_at
        ) VALUES (?, ?, 'PAY-A', 'Natural', 5000, 'INR', 'published', ?, ?)`,
      )
      .bind(VARIANT_A, PRODUCT_ID, now, now),
    env.DB
      .prepare("INSERT INTO inventory_items (variant_id, quantity, updated_at) VALUES (?, 3, ?)")
      .bind(VARIANT_A, now),
  ]);
}

beforeEach(() => seedCatalogue());

async function placeOrder(): Promise<{ orderId: string; token: string }> {
  const response = await SELF.fetch(`${ORIGIN}/checkout`, {
    method: "POST",
    redirect: "manual",
    headers: { origin: ORIGIN, "content-type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      items: JSON.stringify([{ variantId: VARIANT_A, quantity: 2 }]),
      email: "guest@example.com",
      name: "Guest Buyer",
      phone: "+91 98765 43210",
      address1: "12 Loom Lane",
      city: "Guwahati",
      state: "Assam",
      postal_code: "781001",
      country: "IN",
    }).toString(),
  });
  expect(response.status).toBe(303);
  const location = response.headers.get("location") ?? "";
  const [pathPart, query] = location.split("?");
  const orderId = pathPart?.split("/")[2] ?? "";
  const token = new URLSearchParams(query ?? "").get("token") ?? "";
  return { orderId, token };
}

async function startSession(orderId: string, token: string): Promise<Record<string, unknown>> {
  const response = await SELF.fetch(`${ORIGIN}/api/payments/session`, {
    method: "POST",
    headers: { origin: ORIGIN, "content-type": "application/json" },
    body: JSON.stringify({ orderId, token }),
  });
  expect(response.status).toBe(200);
  return (await response.json()) as Record<string, unknown>;
}

async function latestProviderOrderId(orderId: string): Promise<string> {
  const row = await env.DB.prepare(
    `SELECT provider_order_id FROM order_payments WHERE order_id = ?
    ORDER BY created_at DESC, id DESC LIMIT 1`,
  )
    .bind(orderId)
    .first<{ provider_order_id: string }>();
  return row?.provider_order_id ?? "";
}

async function verifyCallback(
  orderId: string,
  token: string,
  providerOrderId: string,
  providerPaymentId: string,
  signatureOverride?: string,
): Promise<Response> {
  const signature =
    signatureOverride ?? (await hmacHex(`${providerOrderId}|${providerPaymentId}`, KEY_SECRET));
  return SELF.fetch(`${ORIGIN}/api/payments/verify`, {
    method: "POST",
    headers: { origin: ORIGIN, "content-type": "application/json" },
    body: JSON.stringify({
      orderId,
      token,
      razorpayOrderId: providerOrderId,
      razorpayPaymentId: providerPaymentId,
      signature,
    }),
  });
}

function capturedEvent(
  providerOrderId: string,
  providerPaymentId: string,
  amountMinor: number,
): string {
  return JSON.stringify({
    event: "payment.captured",
    payload: {
      payment: {
        entity: {
          id: providerPaymentId,
          order_id: providerOrderId,
          amount: amountMinor,
          currency: "INR",
        },
      },
    },
  });
}

function refundEvent(
  event: "refund.processed" | "refund.failed",
  providerRefundId: string,
  providerPaymentId: string,
  amountMinor = TOTAL_MINOR,
): string {
  return JSON.stringify({
    event,
    payload: {
      refund: {
        entity: {
          id: providerRefundId,
          payment_id: providerPaymentId,
          amount: amountMinor,
          currency: "INR",
          status: event === "refund.processed" ? "processed" : "failed",
        },
      },
    },
  });
}

async function sendWebhook(raw: string, signature?: string): Promise<Response> {
  return SELF.fetch(`${ORIGIN}/api/webhooks/razorpay`, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "x-razorpay-signature": signature ?? (await hmacHex(raw, WEBHOOK_SECRET)),
    },
    body: raw,
  });
}

describe("payment sessions", () => {
  it("creates a provider order and returns checkout parameters", async () => {
    const { orderId, token } = await placeOrder();
    const session = await startSession(orderId, token);
    expect(session.keyId).toBe(KEY_ID);
    expect(session.razorpayOrderId).toBe(`order_mock_${orderId.slice(0, 13)}_1`);
    expect(session.amountMinor).toBe(TOTAL_MINOR);
    expect(session.currency).toBe("INR");

    const rows = await env.DB.prepare(
      "SELECT COUNT(*) AS count FROM order_payments WHERE order_id = ? AND status = 'created'",
    )
      .bind(orderId)
      .first<number>("count");
    expect(rows).toBe(1);
  });

  it("reuses an existing open session instead of creating another provider order", async () => {
    const { orderId, token } = await placeOrder();
    const first = await startSession(orderId, token);
    const second = await startSession(orderId, token);
    expect(second.razorpayOrderId).toBe(first.razorpayOrderId);

    const rows = await env.DB.prepare(
      "SELECT COUNT(*) AS count FROM order_payments WHERE order_id = ?",
    )
      .bind(orderId)
      .first<number>("count");
    expect(rows).toBe(1);
  });

  it("rejects sessions for unknown tokens", async () => {
    const { orderId } = await placeOrder();
    const response = await SELF.fetch(`${ORIGIN}/api/payments/session`, {
      method: "POST",
      headers: { origin: ORIGIN, "content-type": "application/json" },
      body: JSON.stringify({ orderId, token: "44444444-4444-4444-8444-444444444444" }),
    });
    expect(response.status).toBe(404);
  });

  it("requires a same-origin header", async () => {
    const { orderId, token } = await placeOrder();
    const response = await SELF.fetch(`${ORIGIN}/api/payments/session`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ orderId, token }),
    });
    expect(response.status).toBe(403);
  });

  it("returns 503 payments_disabled when secrets are absent", async () => {
    const stripped = { ...env } as Record<string, unknown>;
    stripped.RAZORPAY_KEY_ID = "";
    stripped.RAZORPAY_KEY_SECRET = "";
    stripped.RAZORPAY_WEBHOOK_SECRET = "";
    const request = new Request(`${ORIGIN}/api/payments/session`, {
      method: "POST",
      headers: { origin: ORIGIN, "content-type": "application/json" },
      body: JSON.stringify({ orderId: "x", token: "y" }),
    });
    await expect(routePayments(request, stripped as unknown as Env)).rejects.toMatchObject({
      status: 503,
      code: "payments_disabled",
    });
  });

  it("expires an order instead of starting payment after its reservation lapses", async () => {
    const { orderId, token } = await placeOrder();
    await env.DB.prepare("UPDATE inventory_reservations SET expires_at = ? WHERE order_id = ?")
      .bind(new Date(Date.now() - 60_000).toISOString(), orderId)
      .run();

    const response = await SELF.fetch(`${ORIGIN}/api/payments/session`, {
      method: "POST",
      headers: { origin: ORIGIN, "content-type": "application/json" },
      body: JSON.stringify({ orderId, token }),
    });
    expect(response.status).toBe(409);
    expect((await response.json()) as object).toMatchObject({
      error: { code: "reservation_expired" },
    });
    expect(
      await env.DB.prepare("SELECT status FROM orders WHERE id = ?")
        .bind(orderId)
        .first<string>("status"),
    ).toBe("expired");
    expect(
      await env.DB.prepare("SELECT state FROM inventory_reservations WHERE order_id = ?")
        .bind(orderId)
        .first<string>("state"),
    ).toBe("released");
  });

  it.each(["/api/payments/session", "/api/payments/verify"])(
    "rate-limits %s before doing payment work",
    async (path) => {
      const limitedEnv = {
        ...env,
        PUBLIC_RATE_LIMIT: { limit: async () => ({ success: false }) },
      } as unknown as Env;
      const request = new Request(`${ORIGIN}${path}`, {
        method: "POST",
        headers: { origin: ORIGIN, "content-type": "application/json" },
        body: "{}",
      });
      await expect(routePayments(request, limitedEnv)).rejects.toMatchObject({
        status: 429,
        code: "rate_limited",
      });
    },
  );
});

describe("checkout verification", () => {
  it("marks the order paid and permanently deducts reserved stock on a valid callback", async () => {
    const { orderId, token } = await placeOrder();
    await startSession(orderId, token);
    const providerOrderId = await latestProviderOrderId(orderId);

    const response = await verifyCallback(orderId, token, providerOrderId, "pay_verify_ok");
    expect(response.status).toBe(200);
    const body = (await response.json()) as { status: string };
    expect(body.status).toBe("paid");

    const order = await env.DB.prepare("SELECT status FROM orders WHERE id = ?")
      .bind(orderId)
      .first<{ status: string }>();
    expect(order?.status).toBe("paid");

    const active = await env.DB.prepare(
      "SELECT COUNT(*) AS count FROM inventory_reservations WHERE order_id = ? AND state = 'active'",
    )
      .bind(orderId)
      .first<number>("count");
    expect(active).toBe(0);
    const consumed = await env.DB.prepare(
      "SELECT COUNT(*) AS count FROM inventory_reservations WHERE order_id = ? AND state = 'consumed'",
    )
      .bind(orderId)
      .first<number>("count");
    expect(consumed).toBe(1);
    expect(
      await env.DB.prepare("SELECT quantity FROM inventory_items WHERE variant_id = ?")
        .bind(VARIANT_A)
        .first<number>("quantity"),
    ).toBe(1);
    const adjustment = await env.DB.prepare(
      "SELECT delta, actor FROM inventory_adjustments WHERE variant_id = ? ORDER BY created_at DESC LIMIT 1",
    )
      .bind(VARIANT_A)
      .first<{ delta: number; actor: string }>();
    expect(adjustment).toMatchObject({ delta: -2, actor: "payment" });

    const page = await SELF.fetch(`${ORIGIN}/orders/${orderId}?token=${token}`);
    const html = await page.text();
    expect(html).toContain("Payment received");
    expect(html).not.toContain('id="pay-now"');
  });

  it("rejects callbacks with forged signatures", async () => {
    const { orderId, token } = await placeOrder();
    await startSession(orderId, token);
    const providerOrderId = await latestProviderOrderId(orderId);
    const response = await verifyCallback(
      orderId,
      token,
      providerOrderId,
      "pay_forge",
      "00".repeat(32),
    );
    expect(response.status).toBe(400);
    const payload = (await response.json()) as { error: { code: string } };
    expect(payload.error.code).toBe("invalid_payment_signature");
    const order = await env.DB.prepare("SELECT status FROM orders WHERE id = ?")
      .bind(orderId)
      .first<{ status: string }>();
    expect(order?.status).toBe("pending");
  });

  it("treats replays of an already-captured callback as success", async () => {
    const { orderId, token } = await placeOrder();
    await startSession(orderId, token);
    const providerOrderId = await latestProviderOrderId(orderId);
    const first = await verifyCallback(orderId, token, providerOrderId, "pay_replay");
    const second = await verifyCallback(orderId, token, providerOrderId, "pay_replay");
    expect(first.status).toBe(200);
    expect(second.status).toBe(200);
  });

  it("refuses a different payment id once captured", async () => {
    const { orderId, token } = await placeOrder();
    await startSession(orderId, token);
    const providerOrderId = await latestProviderOrderId(orderId);
    const first = await verifyCallback(orderId, token, providerOrderId, "pay_first");
    const second = await verifyCallback(orderId, token, providerOrderId, "pay_second");
    expect(first.status).toBe(200);
    expect(second.status).toBe(409);
  });

  it("records a late capture for review without selling released stock", async () => {
    const { orderId, token } = await placeOrder();
    await startSession(orderId, token);
    const providerOrderId = await latestProviderOrderId(orderId);
    await env.DB.prepare("UPDATE inventory_reservations SET expires_at = ? WHERE order_id = ?")
      .bind(new Date(Date.now() - 60_000).toISOString(), orderId)
      .run();

    const response = await sendWebhook(
      capturedEvent(providerOrderId, "pay_late_capture", TOTAL_MINOR),
    );
    expect(response.status).toBe(200);
    expect(
      await env.DB.prepare("SELECT status FROM orders WHERE id = ?")
        .bind(orderId)
        .first<string>("status"),
    ).toBe("expired");
    expect(
      await env.DB.prepare("SELECT status FROM order_payments WHERE order_id = ?")
        .bind(orderId)
        .first<string>("status"),
    ).toBe("captured");
    expect(
      await env.DB.prepare("SELECT quantity FROM inventory_items WHERE variant_id = ?")
        .bind(VARIANT_A)
        .first<number>("quantity"),
    ).toBe(3);
  });

  it("tells checkout when a verified payment needs manual review", async () => {
    const { orderId, token } = await placeOrder();
    await startSession(orderId, token);
    const providerOrderId = await latestProviderOrderId(orderId);
    await env.DB.prepare("UPDATE inventory_reservations SET expires_at = ? WHERE order_id = ?")
      .bind(new Date(Date.now() - 60_000).toISOString(), orderId)
      .run();

    const response = await verifyCallback(
      orderId,
      token,
      providerOrderId,
      "pay_late_checkout",
    );
    expect(response.status).toBe(409);
    expect((await response.json()) as object).toMatchObject({
      error: { code: "payment_requires_review" },
    });
  });
});

describe("razorpay webhooks", () => {
  it("captures the order from a signed webhook and replays safely", async () => {
    const { orderId, token } = await placeOrder();
    await startSession(orderId, token);
    const providerOrderId = await latestProviderOrderId(orderId);

    const raw = capturedEvent(providerOrderId, "pay_hook_ok", TOTAL_MINOR);
    const first = await sendWebhook(raw);
    expect(first.status).toBe(200);
    const replay = await sendWebhook(raw);
    expect(replay.status).toBe(200);

    const order = await env.DB.prepare("SELECT status FROM orders WHERE id = ?")
      .bind(orderId)
      .first<{ status: string }>();
    expect(order?.status).toBe("paid");
    const payments = await env.DB.prepare(
      "SELECT COUNT(*) AS count FROM order_payments WHERE provider_order_id = ?",
    )
      .bind(providerOrderId)
      .first<number>("count");
    expect(payments).toBe(1);
  });

  it("rejects unsigned or malformed webhooks", async () => {
    const raw = capturedEvent("order_hook_bad", "pay_hook_bad", TOTAL_MINOR);
    const forged = await sendWebhook(raw, "00".repeat(32));
    expect(forged.status).toBe(400);
    const malformed = await SELF.fetch(`${ORIGIN}/api/webhooks/razorpay`, {
      method: "POST",
      headers: {
        "content-type": "application/json",
        "x-razorpay-signature": "zz-not-hex",
      },
      body: raw,
    });
    expect(malformed.status).toBe(400);
  });

  it("reports amount mismatches without changing the order", async () => {
    const { orderId, token } = await placeOrder();
    await startSession(orderId, token);
    const providerOrderId = await latestProviderOrderId(orderId);

    const response = await sendWebhook(capturedEvent(providerOrderId, "pay_hook_amount", 999));
    expect(response.status).toBe(409);
    const order = await env.DB.prepare("SELECT status FROM orders WHERE id = ?")
      .bind(orderId)
      .first<{ status: string }>();
    expect(order?.status).toBe("pending");
  });

  it("records failures and issues a fresh session afterwards", async () => {
    const { orderId, token } = await placeOrder();
    await startSession(orderId, token);
    const originalProviderOrderId = await latestProviderOrderId(orderId);

    const failureRaw = JSON.stringify({
      event: "payment.failed",
      payload: {
        payment: {
          entity: {
            id: "pay_hook_fail",
            order_id: originalProviderOrderId,
            error_description: "Card declined by issuer.",
          },
        },
      },
    });
    const response = await sendWebhook(failureRaw);
    expect(response.status).toBe(200);
    const failed = await env.DB
      .prepare("SELECT status, failure_reason FROM order_payments WHERE provider_order_id = ?")
      .bind(originalProviderOrderId)
      .first<{ status: string; failure_reason: string }>();
    expect(failed?.status).toBe("failed");
    expect(failed?.failure_reason).toContain("declined");

    const retrySession = await startSession(orderId, token);
    const retryProviderOrderId = await latestProviderOrderId(orderId);
    expect(retryProviderOrderId).not.toBe(originalProviderOrderId);
    expect(retrySession.razorpayOrderId).toBe(retryProviderOrderId);
  });

  it.each([
    ["refund.processed", "processed"],
    ["refund.failed", "failed"],
  ] as const)("reconciles %s events", async (event, expectedStatus) => {
    const { orderId, token } = await placeOrder();
    await startSession(orderId, token);
    const providerOrderId = await latestProviderOrderId(orderId);
    const providerPaymentId = `pay_${expectedStatus}`;
    expect(
      (await sendWebhook(capturedEvent(providerOrderId, providerPaymentId, TOTAL_MINOR))).status,
    ).toBe(200);
    const paymentId = await env.DB.prepare("SELECT id FROM order_payments WHERE order_id = ?")
      .bind(orderId)
      .first<string>("id");
    const providerRefundId = `rfnd_${expectedStatus}`;
    await env.DB.prepare(
      `INSERT INTO order_refunds (
        id, order_id, payment_id, provider_refund_id, amount_minor, currency, status, created_at
      ) VALUES (?, ?, ?, ?, ?, 'INR', 'pending', ?)`,
    )
      .bind(crypto.randomUUID(), orderId, paymentId, providerRefundId, TOTAL_MINOR, new Date().toISOString())
      .run();

    const response = await sendWebhook(
      refundEvent(event, providerRefundId, providerPaymentId),
    );
    expect(response.status).toBe(200);
    expect(
      await env.DB.prepare("SELECT status FROM order_refunds WHERE provider_refund_id = ?")
        .bind(providerRefundId)
        .first<string>("status"),
    ).toBe(expectedStatus);
  });

  it("rejects a mismatched refund event without changing the refund", async () => {
    const { orderId, token } = await placeOrder();
    await startSession(orderId, token);
    const providerOrderId = await latestProviderOrderId(orderId);
    const providerPaymentId = "pay_refund_mismatch";
    await sendWebhook(capturedEvent(providerOrderId, providerPaymentId, TOTAL_MINOR));
    const paymentId = await env.DB.prepare("SELECT id FROM order_payments WHERE order_id = ?")
      .bind(orderId)
      .first<string>("id");
    await env.DB.prepare(
      `INSERT INTO order_refunds (
        id, order_id, payment_id, provider_refund_id, amount_minor, currency, status, created_at
      ) VALUES (?, ?, ?, 'rfnd_mismatch', ?, 'INR', 'pending', ?)`,
    )
      .bind(crypto.randomUUID(), orderId, paymentId, TOTAL_MINOR, new Date().toISOString())
      .run();

    const response = await sendWebhook(
      refundEvent("refund.processed", "rfnd_mismatch", providerPaymentId, 1),
    );
    expect(response.status).toBe(409);
    expect(
      await env.DB.prepare("SELECT status FROM order_refunds WHERE provider_refund_id = 'rfnd_mismatch'")
        .first<string>("status"),
    ).toBe("pending");
  });
});
