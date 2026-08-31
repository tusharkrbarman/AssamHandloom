import { env } from "cloudflare:workers";
import { SELF } from "cloudflare:test";
import { describe, expect, it } from "vitest";

import { requireOwner } from "../src/auth";

const ORIGIN = "https://example.com";
const EMAIL = "owner@example.com";
const PASSWORD = "correct horse silk loom";
const PRODUCT_ID = "product-admin-orders";
const VARIANT_A = "51111111-1111-4111-8111-111111111111";

function request(
  path: string,
  method = "GET",
  fields?: Record<string, string>,
  cookie?: string,
): Promise<Response> {
  const headers = new Headers({ origin: ORIGIN });
  if (cookie) headers.set("cookie", cookie);
  let body: URLSearchParams | undefined;
  if (fields) {
    body = new URLSearchParams(fields);
    headers.set("content-type", "application/x-www-form-urlencoded");
  }
  return SELF.fetch(`${ORIGIN}${path}`, { method, headers, body, redirect: "manual" });
}

async function ownerSession(): Promise<{ cookie: string; csrf: string }> {
  expect(
    (
      await request("/admin/setup", "POST", {
        token: env.ADMIN_SETUP_TOKEN,
        email: EMAIL,
        password: PASSWORD,
      })
    ).status,
  ).toBe(303);
  const login = await request("/admin/login", "POST", {
    email: EMAIL,
    password: PASSWORD,
  });
  expect(login.status).toBe(303);
  const cookie = login.headers.get("set-cookie")?.split(";", 1)[0] ?? "";
  const authenticated = await requireOwner(
    new Request(`${ORIGIN}/admin`, { headers: { cookie } }),
    env,
  );
  return { cookie, csrf: authenticated.session.csrf };
}

async function seedAndCheckout(): Promise<string> {
  const now = new Date().toISOString();
  await env.DB.batch([
    env.DB
      .prepare(
        `INSERT INTO products (
          id, slug, title, description, silk_type, publication_state,
          featured_rank, created_at, updated_at
        ) VALUES (?, 'order-desk-saree', 'Order Desk Saree', '', 'Muga', 'published', 0, ?, ?)`,
      )
      .bind(PRODUCT_ID, now, now),
    env.DB
      .prepare(
        `INSERT INTO variants (
          id, product_id, sku, title, price_minor, currency,
          publication_state, created_at, updated_at
        ) VALUES (?, ?, 'DESK-001', 'Natural', 5000, 'INR', 'published', ?, ?)`,
      )
      .bind(VARIANT_A, PRODUCT_ID, now, now),
    env.DB
      .prepare("INSERT INTO inventory_items (variant_id, quantity, updated_at) VALUES (?, 4, ?)")
      .bind(VARIANT_A, now),
  ]);
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
    }),
  });
  expect(response.status).toBe(303);
  return (response.headers.get("location") ?? "").split("?")[0]?.split("/")[2] ?? "";
}

describe("owner order desk", () => {
  it("redirects anonymous requests to sign in", async () => {
    const response = await request("/admin/orders");
    expect(response.status).toBe(303);
    expect(response.headers.get("location")).toBe("/admin/login");
  });

  it("lists placed orders and shows the fulfilment detail", async () => {
    const { cookie } = await ownerSession();
    const orderId = await seedAndCheckout();

    const list = await request("/admin/orders", "GET", undefined, cookie);
    expect(list.status).toBe(200);
    const listHtml = await list.text();
    expect(listHtml).toContain(orderId.slice(0, 8).toUpperCase());
    expect(listHtml).toContain("guest@example.com");
    expect(listHtml).toContain("Awaiting payment");

    const detail = await request(`/admin/orders/${orderId}`, "GET", undefined, cookie);
    expect(detail.status).toBe(200);
    const detailHtml = await detail.text();
    expect(detailHtml).toContain("Guest Buyer");
    expect(detailHtml).toContain("12 Loom Lane");
    expect(detailHtml).toContain("Guwahati");
    expect(detailHtml).toContain("+91 98765 43210");
    expect(detailHtml).toContain("Order Desk Saree · Natural");
    expect(detailHtml).toContain("Mark as paid");

    const filtered = await request("/admin/orders?status=paid", "GET", undefined, cookie);
    expect((await filtered.text())).not.toContain("guest@example.com");
  });

  it("marks a pending order paid and permanently deducts its reserved stock", async () => {
    const { cookie, csrf } = await ownerSession();
    const orderId = await seedAndCheckout();

    const response = await request(
      `/admin/orders/${orderId}/status`,
      "POST",
      { csrf, status: "paid" },
      cookie,
    );
    expect(response.status).toBe(303);

    const order = await env.DB.prepare("SELECT status FROM orders WHERE id = ?")
      .bind(orderId)
      .first<{ status: string }>();
    expect(order?.status).toBe("paid");
    const activeReservations = await env.DB.prepare(
      "SELECT COUNT(*) AS count FROM inventory_reservations WHERE order_id = ? AND state = 'active'",
    )
      .bind(orderId)
      .first<number>("count");
    expect(activeReservations).toBe(0);
    const consumedReservations = await env.DB.prepare(
      "SELECT COUNT(*) AS count FROM inventory_reservations WHERE order_id = ? AND state = 'consumed'",
    )
      .bind(orderId)
      .first<number>("count");
    expect(consumedReservations).toBe(1);
    expect(
      await env.DB.prepare("SELECT quantity FROM inventory_items WHERE variant_id = ?")
        .bind(VARIANT_A)
        .first<number>("quantity"),
    ).toBe(2);
  });

  it("queues a shipped email when an order is fulfilled", async () => {
    const { cookie, csrf } = await ownerSession();
    const orderId = await seedAndCheckout();
    expect(
      (
        await request(
          `/admin/orders/${orderId}/status`,
          "POST",
          { csrf, status: "paid" },
          cookie,
        )
      ).status,
    ).toBe(303);

    expect(
      (
        await request(
          `/admin/orders/${orderId}/status`,
          "POST",
          { csrf, status: "fulfilled" },
          cookie,
        )
      ).status,
    ).toBe(303);

    const order = await env.DB.prepare("SELECT status FROM orders WHERE id = ?")
      .bind(orderId)
      .first<{ status: string }>();
    expect(order?.status).toBe("fulfilled");
    const queued = await env.DB.prepare(
      "SELECT COUNT(*) AS count FROM email_outbox WHERE order_id = ? AND kind = 'order_shipped' AND status = 'queued'",
    )
      .bind(orderId)
      .first<number>("count");
    expect(queued).toBe(1);
  });

  it("rejects transitions that skip steps and posts without CSRF", async () => {
    const { cookie, csrf } = await ownerSession();
    const orderId = await seedAndCheckout();

    const skipped = await request(
      `/admin/orders/${orderId}/status`,
      "POST",
      { csrf, status: "fulfilled" },
      cookie,
    );
    expect(skipped.status).toBe(409);

    const noCsrf = await request(
      `/admin/orders/${orderId}/status`,
      "POST",
      { status: "paid" },
      cookie,
    );
    expect(noCsrf.status).toBe(403);

    const untouched = await env.DB.prepare("SELECT status FROM orders WHERE id = ?")
      .bind(orderId)
      .first<{ status: string }>();
    expect(untouched?.status).toBe("pending");
  });

  it("releases reservations when a pending order is cancelled", async () => {
    const { cookie, csrf } = await ownerSession();
    const orderId = await seedAndCheckout();

    expect(
      (
        await request(
          `/admin/orders/${orderId}/status`,
          "POST",
          { csrf, status: "cancelled" },
          cookie,
        )
      ).status,
    ).toBe(303);

    const released = await env.DB.prepare(
      "SELECT COUNT(*) AS count FROM inventory_reservations WHERE order_id = ? AND state = 'released'",
    )
      .bind(orderId)
      .first<number>("count");
    expect(released).toBe(1);

    const repeat = await request(
      `/admin/orders/${orderId}/status`,
      "POST",
      { csrf, status: "cancelled" },
      cookie,
    );
    expect(repeat.status).toBe(409);
  });

  it("issues a full refund against a captured payment and flags the list", async () => {
    const { cookie, csrf } = await ownerSession();
    const orderId = await seedAndCheckout();
    await request(`/admin/orders/${orderId}/status`, "POST", { csrf, status: "paid" }, cookie);
    const now = new Date().toISOString();
    await env.DB
      .prepare(
        `INSERT INTO order_payments (
          id, order_id, provider, provider_order_id, provider_payment_id,
          amount_minor, currency, status, created_at, updated_at
        ) VALUES (?, ?, 'razorpay', 'order_mock_desk1', 'pay_mock_desk1', 10000, 'INR', 'captured', ?, ?)`,
      )
      .bind(crypto.randomUUID(), orderId, now, now)
      .run();

    const detailBefore = await request(`/admin/orders/${orderId}`, "GET", undefined, cookie);
    expect((await detailBefore.text())).toContain("Issue refund");

    const refund = await request(
      `/admin/orders/${orderId}/refund`,
      "POST",
      { csrf },
      cookie,
    );
    expect(refund.status).toBe(303);

    const row = await env.DB
      .prepare(
        "SELECT amount_minor, currency, status FROM order_refunds WHERE order_id = ?",
      )
      .bind(orderId)
      .first<{ amount_minor: number; currency: string; status: string }>();
    expect(row?.amount_minor).toBe(10000);
    expect(row?.currency).toBe("INR");
    expect(row?.status).toBe("processed");

    const detailAfter = await request(`/admin/orders/${orderId}`, "GET", undefined, cookie);
    const detailHtml = await detailAfter.text();
    expect(detailHtml).toContain("rfnd_mock_");
    expect(detailHtml).not.toContain("Issue refund");

    const list = await request("/admin/orders", "GET", undefined, cookie);
    expect((await list.text())).toContain("Refunded");
  });

  it("validates partial refunds and refuses orders without captured payments", async () => {
    const { cookie, csrf } = await ownerSession();
    const orderId = await seedAndCheckout();

    const noPayment = await request(
      `/admin/orders/${orderId}/refund`,
      "POST",
      { csrf },
      cookie,
    );
    expect(noPayment.status).toBe(409);

    const now = new Date().toISOString();
    await env.DB
      .prepare(
        `INSERT INTO order_payments (
          id, order_id, provider, provider_order_id, provider_payment_id,
          amount_minor, currency, status, created_at, updated_at
        ) VALUES (?, ?, 'razorpay', 'order_mock_desk2', 'pay_mock_desk2', 10000, 'INR', 'captured', ?, ?)`,
      )
      .bind(crypto.randomUUID(), orderId, now, now)
      .run();
    const paymentId = await env.DB.prepare("SELECT id FROM order_payments WHERE order_id = ?")
      .bind(orderId)
      .first<string>("id");
    await env.DB.prepare(
      `INSERT INTO order_refunds (
        id, order_id, payment_id, provider_refund_id, amount_minor, currency, status, created_at
      ) VALUES (?, ?, ?, 'rfnd_failed_attempt', 9000, 'INR', 'failed', ?)`,
    )
      .bind(crypto.randomUUID(), orderId, paymentId, now)
      .run();

    const tooBig = await request(
      `/admin/orders/${orderId}/refund`,
      "POST",
      { csrf, amount_minor: "20000" },
      cookie,
    );
    expect(tooBig.status).toBe(422);

    const partial = await request(
      `/admin/orders/${orderId}/refund`,
      "POST",
      { csrf, amount_minor: "4000" },
      cookie,
    );
    expect(partial.status).toBe(303);
    const total = await env.DB
      .prepare("SELECT COALESCE(SUM(amount_minor), 0) AS total FROM order_refunds WHERE order_id = ? AND status <> 'failed'")
      .bind(orderId)
      .first<number>("total");
    expect(total).toBe(4000);
  });

  it("shows late captured payments as refundable manual-review cases", async () => {
    const { cookie } = await ownerSession();
    const orderId = await seedAndCheckout();
    const now = new Date().toISOString();
    await env.DB.batch([
      env.DB.prepare("UPDATE orders SET status = 'expired', updated_at = ? WHERE id = ?").bind(now, orderId),
      env.DB.prepare("UPDATE inventory_reservations SET state = 'released' WHERE order_id = ?").bind(orderId),
      env.DB.prepare(
        `INSERT INTO order_payments (
          id, order_id, provider, provider_order_id, provider_payment_id,
          amount_minor, currency, status, created_at, updated_at
        ) VALUES (?, ?, 'razorpay', 'order_late_desk', 'pay_late_desk', 10000, 'INR', 'captured', ?, ?)`,
      ).bind(crypto.randomUUID(), orderId, now, now),
    ]);

    const detail = await request(`/admin/orders/${orderId}`, "GET", undefined, cookie);
    const html = await detail.text();
    expect(html).toContain("Payment requires review");
    expect(html).toContain("Issue refund");
  });
});
