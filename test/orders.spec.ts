import { env } from "cloudflare:workers";
import { SELF } from "cloudflare:test";
import { beforeEach, describe, expect, it } from "vitest";

const ORIGIN = "https://example.com";
const PRODUCT_ID = "product-commerce";
const VARIANT_A = "11111111-1111-4111-8111-111111111111";
const VARIANT_B = "22222222-2222-4222-8222-222222222222";
const VARIANT_DRAFT = "33333333-3333-4333-8333-333333333333";

function bag(items: Array<{ variantId: string; quantity: number }>): string {
  return JSON.stringify(items);
}

function checkoutBody(overrides: Record<string, string> = {}): URLSearchParams {
  return new URLSearchParams({
    items: bag([
      { variantId: VARIANT_A, quantity: 2 },
      { variantId: VARIANT_B, quantity: 1 },
    ]),
    email: "guest@example.com",
    name: "Guest Buyer",
    phone: "+91 98765 43210",
    address1: "12 Loom Lane",
    city: "Guwahati",
    state: "Assam",
    postal_code: "781001",
    country: "IN",
    ...overrides,
  });
}

async function seedCatalogue(): Promise<void> {
  const now = new Date().toISOString();
  await env.DB.batch([
    env.DB
      .prepare(
        `INSERT INTO products (
          id, slug, title, description, silk_type, publication_state,
          featured_rank, created_at, updated_at
        ) VALUES (?, 'commerce-saree', 'Commerce Saree', '', 'Muga', 'published', 0, ?, ?)`,
      )
      .bind(PRODUCT_ID, now, now),
    env.DB
      .prepare(
        `INSERT INTO variants (
          id, product_id, sku, title, price_minor, currency,
          publication_state, created_at, updated_at
        ) VALUES (?, ?, 'COM-A', 'Natural', 5000, 'INR', 'published', ?, ?)`,
      )
      .bind(VARIANT_A, PRODUCT_ID, now, now),
    env.DB
      .prepare(
        `INSERT INTO variants (
          id, product_id, sku, title, price_minor, currency,
          publication_state, created_at, updated_at
        ) VALUES (?, ?, 'COM-B', 'Dyed', 2500, 'INR', 'published', ?, ?)`,
      )
      .bind(VARIANT_B, PRODUCT_ID, now, now),
    env.DB
      .prepare(
        `INSERT INTO variants (
          id, product_id, sku, title, price_minor, currency,
          publication_state, created_at, updated_at
        ) VALUES (?, ?, 'COM-DRAFT', 'Hidden', 1000, 'INR', 'draft', ?, ?)`,
      )
      .bind(VARIANT_DRAFT, PRODUCT_ID, now, now),
    env.DB
      .prepare(
        "INSERT INTO inventory_items (variant_id, quantity, updated_at) VALUES (?, 3, ?)",
      )
      .bind(VARIANT_A, now),
    env.DB
      .prepare(
        "INSERT INTO inventory_items (variant_id, quantity, updated_at) VALUES (?, 5, ?)",
      )
      .bind(VARIANT_B, now),
  ]);
}

beforeEach(() => seedCatalogue());

describe("cart quote", () => {
  it("prices lines server-side and hides unpublished variants", async () => {
    const quote = await quoteViaApi([
      { variantId: VARIANT_A, quantity: 2 },
      { variantId: VARIANT_B, quantity: 1 },
      { variantId: VARIANT_DRAFT, quantity: 1 },
    ]);
    expect(quote.status).toBe(404);

    const ok = await quoteViaApi([
      { variantId: VARIANT_A, quantity: 2 },
      { variantId: VARIANT_B, quantity: 1 },
    ]);
    expect(ok.status).toBe(200);
    const body = (await ok.json()) as {
      subtotalMinor: number;
      subtotalFormatted: string;
      allAvailable: boolean;
      currency: string;
    };
    expect(body.subtotalMinor).toBe(12500);
    expect(body.subtotalFormatted).toContain("125");
    expect(body.allAvailable).toBe(true);
    expect(body.currency).toBe("INR");
  });

  it("rejects requests without a same-origin header", async () => {
    const response = await SELF.fetch(`${ORIGIN}/api/cart/quote`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ items: [{ variantId: VARIANT_A, quantity: 1 }] }),
    });
    expect(response.status).toBe(403);
  });

  it("rejects malformed bags", async () => {
    const response = await SELF.fetch(`${ORIGIN}/api/cart/quote`, {
      method: "POST",
      headers: { origin: ORIGIN, "content-type": "application/json" },
      body: JSON.stringify({ items: [] }),
    });
    expect(response.status).toBe(422);
    const payload = (await response.json()) as { error: { code: string } };
    expect(payload.error.code).toBe("invalid_cart");
  });

  it("flags quantities beyond stock as unavailable without failing", async () => {
    const response = await quoteViaApi([{ variantId: VARIANT_A, quantity: 10 }]);
    expect(response.status).toBe(200);
    const body = (await response.json()) as { allAvailable: boolean };
    expect(body.allAvailable).toBe(false);
  });

  async function quoteViaApi(
    items: Array<{ variantId: string; quantity: number }>,
  ): Promise<Response> {
    return SELF.fetch(`${ORIGIN}/api/cart/quote`, {
      method: "POST",
      headers: { origin: ORIGIN, "content-type": "application/json" },
      body: JSON.stringify({ items }),
    });
  }
});

describe("checkout orders", () => {
  it("creates an order with snapshots and active reservations atomically", async () => {
    const response = await SELF.fetch(`${ORIGIN}/checkout`, {
      method: "POST",
      redirect: "manual",
      headers: {
        origin: ORIGIN,
        "content-type": "application/x-www-form-urlencoded",
      },
      body: checkoutBody(),
    });
    expect(response.status).toBe(303);
    const location = response.headers.get("location") ?? "";
    expect(location).toMatch(/^\/orders\/[0-9a-f-]{36}\?token=[0-9a-f-]{36}$/);
    const orderId = location.split("?")[0]?.split("/")[2] ?? "";

    const order = await env.DB.prepare(
      "SELECT status, total_minor, shipping_minor FROM orders WHERE id = ?",
    )
      .bind(orderId)
      .first<{ status: string; total_minor: number; shipping_minor: number }>();
    expect(order?.status).toBe("pending");
    expect(order?.total_minor).toBe(12500);
    expect(order?.shipping_minor).toBe(0);

    const items = await env.DB.prepare(
      "SELECT sku, unit_price_minor, quantity FROM order_items WHERE order_id = ? ORDER BY sku",
    )
      .bind(orderId)
      .all<{ sku: string; unit_price_minor: number; quantity: number }>();
    expect(items.results ?? []).toEqual([
      { sku: "COM-A", unit_price_minor: 5000, quantity: 2 },
      { sku: "COM-B", unit_price_minor: 2500, quantity: 1 },
    ]);

    const reservations = await env.DB.prepare(
      "SELECT COUNT(*) AS count FROM inventory_reservations WHERE order_id = ? AND state = 'active'",
    )
      .bind(orderId)
      .first<number>("count");
    expect(reservations).toBe(2);
  });

  it("refuses to oversell and leaves no partial order behind", async () => {
    const first = await SELF.fetch(`${ORIGIN}/checkout`, {
      method: "POST",
      redirect: "manual",
      headers: {
        origin: ORIGIN,
        "content-type": "application/x-www-form-urlencoded",
      },
      body: checkoutBody({
        items: bag([{ variantId: VARIANT_A, quantity: 3 }]),
      }),
    });
    expect(first.status).toBe(303);

    const second = await SELF.fetch(`${ORIGIN}/checkout`, {
      method: "POST",
      redirect: "manual",
      headers: {
        origin: ORIGIN,
        "content-type": "application/x-www-form-urlencoded",
      },
      body: checkoutBody(),
    });
    expect(second.status).toBe(409);
    const html = await second.text();
    expect(html).toMatch(/sold out|review your bag/i);

    const orderCount = await env.DB.prepare("SELECT COUNT(*) AS count FROM orders").first<number>(
      "count",
    );
    expect(orderCount).toBe(1);
    const reservationCount = await env.DB.prepare(
      "SELECT COUNT(*) AS count FROM inventory_reservations WHERE state = 'active'",
    ).first<number>("count");
    expect(reservationCount).toBe(1);
  });

  it("re-renders checkout with a validation message for bad fields", async () => {
    const response = await SELF.fetch(`${ORIGIN}/checkout`, {
      method: "POST",
      redirect: "manual",
      headers: {
        origin: ORIGIN,
        "content-type": "application/x-www-form-urlencoded",
      },
      body: checkoutBody({ email: "not-an-email" }),
    });
    expect(response.status).toBe(422);
    const html = await response.text();
    expect(html).toMatch(/Email is invalid/);
    const orders = await env.DB.prepare("SELECT COUNT(*) AS count FROM orders").first<number>(
      "count",
    );
    expect(orders).toBe(0);
  });

  it("requires a same-origin header for checkout posts", async () => {
    const response = await SELF.fetch(`${ORIGIN}/checkout`, {
      method: "POST",
      redirect: "manual",
      headers: { "content-type": "application/x-www-form-urlencoded" },
      body: checkoutBody(),
    });
    expect(response.status).toBe(403);
  });

  it("frees reserved stock when reservations expire", async () => {
    const first = await SELF.fetch(`${ORIGIN}/checkout`, {
      method: "POST",
      redirect: "manual",
      headers: {
        origin: ORIGIN,
        "content-type": "application/x-www-form-urlencoded",
      },
      body: checkoutBody({
        items: bag([{ variantId: VARIANT_A, quantity: 3 }]),
      }),
    });
    expect(first.status).toBe(303);

    await env.DB
      .prepare(
        "UPDATE inventory_reservations SET expires_at = ? WHERE variant_id = ?",
      )
      .bind(new Date(Date.now() - 60_000).toISOString(), VARIANT_A)
      .run();

    const retry = await SELF.fetch(`${ORIGIN}/checkout`, {
      method: "POST",
      redirect: "manual",
      headers: {
        origin: ORIGIN,
        "content-type": "application/x-www-form-urlencoded",
      },
      body: checkoutBody({
        items: bag([{ variantId: VARIANT_A, quantity: 3 }]),
      }),
    });
    expect(retry.status).toBe(303);
  });

  it("shows the confirmation page only for the correct token", async () => {
    const response = await SELF.fetch(`${ORIGIN}/checkout`, {
      method: "POST",
      redirect: "manual",
      headers: {
        origin: ORIGIN,
        "content-type": "application/x-www-form-urlencoded",
      },
      body: checkoutBody(),
    });
    const location = response.headers.get("location") ?? "";
    const [path, query] = location.split("?");
    const token = new URLSearchParams(query ?? "").get("token") ?? "";

    const good = await SELF.fetch(`${ORIGIN}${path}?token=${token}`, { redirect: "manual" });
    expect(good.status).toBe(200);
    const html = await good.text();
    expect(html).toContain("Commerce Saree · Natural");
    expect(html).toContain("Awaiting payment");

    const bad = await SELF.fetch(`${ORIGIN}${path}?token=44444444-4444-4444-8444-444444444444`, {
      redirect: "manual",
    });
    expect(bad.status).toBe(404);
  });

  it("keeps price snapshots when the catalogue changes later", async () => {
    const response = await SELF.fetch(`${ORIGIN}/checkout`, {
      method: "POST",
      redirect: "manual",
      headers: {
        origin: ORIGIN,
        "content-type": "application/x-www-form-urlencoded",
      },
      body: checkoutBody(),
    });
    const location = response.headers.get("location") ?? "";
    const [path, query] = location.split("?");
    const token = new URLSearchParams(query ?? "").get("token") ?? "";

    await env.DB.prepare("UPDATE variants SET price_minor = 99999 WHERE id = ?")
      .bind(VARIANT_A)
      .run();

    const confirmation = await SELF.fetch(`${ORIGIN}${path}?token=${token}`);
    const html = await confirmation.text();
    expect(html).not.toContain("99999");
  });

  it("protects active reservations from deletion or identity edits", async () => {
    const response = await SELF.fetch(`${ORIGIN}/checkout`, {
      method: "POST",
      redirect: "manual",
      headers: {
        origin: ORIGIN,
        "content-type": "application/x-www-form-urlencoded",
      },
      body: checkoutBody({
        items: bag([{ variantId: VARIANT_A, quantity: 1 }]),
      }),
    });
    expect(response.status).toBe(303);

    await expect(
      env.DB.prepare(
        "DELETE FROM inventory_reservations WHERE variant_id = ? AND state = 'active'",
      )
        .bind(VARIANT_A)
        .run(),
    ).rejects.toThrow(/inventory_reservations_active_delete/);

    await expect(
      env.DB.prepare(
        "UPDATE inventory_reservations SET quantity = 9 WHERE variant_id = ? AND state = 'active'",
      )
        .bind(VARIANT_A)
        .run(),
    ).rejects.toThrow(/inventory_reservations_identity_immutable/);
  });
});
