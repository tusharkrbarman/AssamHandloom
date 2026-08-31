import { env, SELF } from "cloudflare:test";
import { beforeEach, describe, expect, it } from "vitest";
import { processOutbox, enqueueOrderEmail } from "../src/email";
import { createOrderLink } from "../src/links";
import { runMaintenance } from "../src/maintenance";

const ORIGIN = "https://example.com";
const PRODUCT_ID = "product-postpurchase";
const VARIANT_A = "cccc1111-1111-4111-8111-111111111111";
const KEY_SECRET = "test-key-secret-with-at-least-32-characters";

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
        ) VALUES (?, 'postpurchase-saree', 'Postpurchase Saree', '', 'Muga', 'published', 0, ?, ?)`,
      )
      .bind(PRODUCT_ID, now, now),
    env.DB
      .prepare(
        `INSERT INTO variants (
          id, product_id, sku, title, price_minor, currency,
          publication_state, created_at, updated_at
        ) VALUES (?, ?, 'PP-A', 'Natural', 5000, 'INR', 'published', ?, ?)`,
      )
      .bind(VARIANT_A, PRODUCT_ID, now, now),
    env.DB
      .prepare("INSERT INTO inventory_items (variant_id, quantity, updated_at) VALUES (?, 3, ?)")
      .bind(VARIANT_A, now),
  ]);
}

beforeEach(() => seedCatalogue());

async function placeOrder(email = "guest@example.com"): Promise<{ orderId: string; token: string }> {
  const response = await SELF.fetch(`${ORIGIN}/checkout`, {
    method: "POST",
    redirect: "manual",
    headers: { origin: ORIGIN, "content-type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      items: JSON.stringify([{ variantId: VARIANT_A, quantity: 2 }]),
      email,
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

async function capturePayment(
  orderId: string,
  token: string,
  knownProviderOrderId?: string,
): Promise<Response> {
  let providerOrderId = knownProviderOrderId ?? "";
  if (!providerOrderId) {
    const session = await SELF.fetch(`${ORIGIN}/api/payments/session`, {
      method: "POST",
      headers: { origin: ORIGIN, "content-type": "application/json" },
      body: JSON.stringify({ orderId, token }),
    });
    expect(session.status).toBe(200);
    const sessionBody = (await session.json()) as { razorpayOrderId: string };
    providerOrderId = sessionBody.razorpayOrderId;
  }
  const signature = await hmacHex(`${providerOrderId}|pay_pp_ok`, KEY_SECRET);
  return SELF.fetch(`${ORIGIN}/api/payments/verify`, {
    method: "POST",
    headers: { origin: ORIGIN, "content-type": "application/json" },
    body: JSON.stringify({
      orderId,
      token,
      razorpayOrderId: providerOrderId,
      razorpayPaymentId: "pay_pp_ok",
      signature,
    }),
  });
}

async function latestProviderOrderId(orderId: string): Promise<string> {
  const row = await env.DB
    .prepare(
      "SELECT provider_order_id FROM order_payments WHERE order_id = ? ORDER BY created_at DESC LIMIT 1",
    )
    .bind(orderId)
    .first<{ provider_order_id: string }>();
  return row?.provider_order_id ?? "";
}

function outboxRows(orderId?: string): Promise<
  Array<{ kind: string; status: string; attempts: number; to_email: string; next_attempt_at: string }>
> {
  const base =
    "SELECT kind, status, attempts, to_email, next_attempt_at FROM email_outbox";
  const statement = orderId
    ? `${base} WHERE order_id = ? ORDER BY kind`
    : `${base} ORDER BY kind`;
  const query = orderId ? env.DB.prepare(statement).bind(orderId) : env.DB.prepare(statement);
  return query
    .all<{ kind: string; status: string; attempts: number; to_email: string; next_attempt_at: string }>()
    .then((result) => result.results ?? []);
}

describe("signed order links", () => {
  it("opens the order page without exposing the token", async () => {
    const { orderId } = await placeOrder();
    const link = await createOrderLink(env, orderId);
    const response = await SELF.fetch(`${ORIGIN}/orders/${link}`, { redirect: "manual" });
    expect(response.status).toBe(200);
    const html = await response.text();
    expect(html).toContain("Postpurchase Saree · Natural");
  });

  it("rejects tampered signatures", async () => {
    const { orderId } = await placeOrder();
    const link = await createOrderLink(env, orderId);
    const tampered = link.replace(/sig=([0-9a-f])/, (_match, first: string) =>
      `sig=${first === "0" ? "1" : "0"}`,
    );
    expect(tampered).not.toBe(link);
    const response = await SELF.fetch(`${ORIGIN}/orders/${tampered}`, { redirect: "manual" });
    expect(response.status).toBe(404);
  });

  it("rejects expired links", async () => {
    const { orderId } = await placeOrder();
    const expiredLink = await createOrderLink(env, orderId, -60);
    const response = await SELF.fetch(`${ORIGIN}/orders/${expiredLink}`, { redirect: "manual" });
    expect(response.status).toBe(404);
  });

  it("still accepts the direct token and refuses bare visits", async () => {
    const { orderId, token } = await placeOrder();
    const good = await SELF.fetch(`${ORIGIN}/orders/${orderId}?token=${token}`);
    expect(good.status).toBe(200);
    const bare = await SELF.fetch(`${ORIGIN}/orders/${orderId}`, { redirect: "manual" });
    expect(bare.status).toBe(404);
  });
});

describe("email outbox", () => {
  it("queues exactly one confirmation at checkout", async () => {
    const { orderId } = await placeOrder();
    const rows = await outboxRows(orderId);
    expect(rows.length).toBe(1);
    expect(rows[0]?.kind).toBe("order_confirmation");
    expect(rows[0]?.status).toBe("queued");
    expect(rows[0]?.to_email).toBe("guest@example.com");
  });

  it("ignores duplicate enqueues for the same order and kind", async () => {
    const { orderId } = await placeOrder();
    await enqueueOrderEmail(env.DB, env, "order_confirmation", orderId);
    const rows = await outboxRows(orderId);
    expect(rows.length).toBe(1);
  });

  it("sends queued mail through the provider and marks it sent", async () => {
    const { orderId } = await placeOrder();
    const summary = await processOutbox(env.DB, env);
    expect(summary.sent).toBe(1);
    const row = await env.DB
      .prepare("SELECT status, sent_at, last_error FROM email_outbox WHERE order_id = ?")
      .bind(orderId)
      .first<{ status: string; sent_at: string | null; last_error: string | null }>();
    expect(row?.status).toBe("sent");
    expect(row?.sent_at).not.toBeNull();
    expect(row?.last_error).toBeNull();

    const secondPass = await processOutbox(env.DB, env);
    expect(secondPass.sent).toBe(0);
  });

  it("includes a signed pay link for unpaid confirmations", async () => {
    await placeOrder("linkcheck@example.com");
    const summary = await processOutbox(env.DB, env);
    expect(summary.sent).toBe(1);
  });

  it("backs off when the provider fails and eventually gives up", async () => {
    const { orderId } = await placeOrder("fail@example.com");
    const firstAttempt = await processOutbox(env.DB, env);
    expect(firstAttempt.retried).toBe(1);

    const row = await env.DB
      .prepare("SELECT status, attempts, next_attempt_at FROM email_outbox WHERE order_id = ?")
      .bind(orderId)
      .first<{ status: string; attempts: number; next_attempt_at: string }>();
    expect(row?.status).toBe("queued");
    expect(row?.attempts).toBe(1);
    expect(row!.next_attempt_at > new Date().toISOString()).toBe(true);

    await env.DB
      .prepare(
        "UPDATE email_outbox SET attempts = 4, next_attempt_at = ? WHERE order_id = ?",
      )
      .bind(new Date(Date.now() - 1000).toISOString(), orderId)
      .run();
    const finalAttempt = await processOutbox(env.DB, env);
    expect(finalAttempt.failed).toBe(1);
    const failedRow = await env.DB
      .prepare("SELECT status, attempts FROM email_outbox WHERE order_id = ?")
      .bind(orderId)
      .first<{ status: string; attempts: number }>();
    expect(failedRow?.status).toBe("failed");
    expect(failedRow?.attempts).toBe(5);
  });

  it("does nothing when mail is not configured", async () => {
    const stripped = { ...env } as Record<string, unknown>;
    stripped.RESEND_API_KEY = "";
    stripped.MAIL_FROM = "";
    const summary = await processOutbox(env.DB, stripped as unknown as Env);
    expect(summary.sent).toBe(0);
  });
});

describe("paid notifications", () => {
  it("queues the payment-received email once after capture", async () => {
    const { orderId, token } = await placeOrder();
    const capture = await capturePayment(orderId, token);
    expect(capture.status).toBe(200);

    let kinds = (await outboxRows(orderId)).map((row) => row.kind).sort();
    expect(kinds).toEqual(["order_confirmation", "order_paid"]);

    const replayProviderOrderId = await latestProviderOrderId(orderId);
    const replay = await capturePayment(orderId, token, replayProviderOrderId);
    expect(replay.status).toBe(200);
    kinds = (await outboxRows(orderId)).map((row) => row.kind).sort();
    expect(kinds).toEqual(["order_confirmation", "order_paid"]);
  });
});

describe("maintenance sweep", () => {
  it("releases expired reservations and expires abandoned orders", async () => {
    const { orderId } = await placeOrder();
    const stale = new Date(Date.now() - 25 * 60 * 60 * 1000).toISOString();
    await env.DB.batch([
      env.DB
        .prepare("UPDATE inventory_reservations SET expires_at = ? WHERE order_id = ?")
        .bind(new Date(Date.now() - 60_000).toISOString(), orderId),
      env.DB.prepare("UPDATE orders SET created_at = ?, updated_at = ? WHERE id = ?").bind(
        stale,
        stale,
        orderId,
      ),
    ]);

    const summary = await runMaintenance(env);
    expect(summary.releasedReservations).toBeGreaterThanOrEqual(1);
    expect(summary.expiredOrders).toBeGreaterThanOrEqual(1);

    const reservation = await env.DB
      .prepare("SELECT state FROM inventory_reservations WHERE order_id = ?")
      .bind(orderId)
      .first<{ state: string }>();
    expect(reservation?.state).toBe("released");

    const order = await env.DB
      .prepare("SELECT status FROM orders WHERE id = ?")
      .bind(orderId)
      .first<{ status: string }>();
    expect(order?.status).toBe("expired");
  });

  it("expires recent unpaid orders as soon as their reservation lapses", async () => {
    const { orderId } = await placeOrder();
    await env.DB
      .prepare("UPDATE inventory_reservations SET expires_at = ?")
      .bind(new Date(Date.now() - 60_000).toISOString())
      .run();

    const summary = await runMaintenance(env);
    expect(summary.expiredOrders).toBeGreaterThanOrEqual(1);
    const order = await env.DB
      .prepare("SELECT status FROM orders WHERE id = ?")
      .bind(orderId)
      .first<{ status: string }>();
    expect(order?.status).toBe("expired");
  });
});
