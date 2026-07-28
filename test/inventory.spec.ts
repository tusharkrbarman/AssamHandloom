import { env } from "cloudflare:workers";
import { SELF } from "cloudflare:test";
import { beforeEach, describe, expect, it } from "vitest";

import { sessionCookie } from "../src/auth";
import { adjustInventory } from "../src/inventory";

const ORIGIN = "https://example.com";
const VARIANT_ID = "variant-stock";
const CSRF = "csrf-token-with-at-least-thirty-two-characters";

beforeEach(async () => {
  const now = new Date().toISOString();
  await env.DB.batch([
    env.DB
      .prepare(
        `INSERT INTO products (
          id, slug, title, description, silk_type, publication_state,
          featured_rank, created_at, updated_at
        ) VALUES ('product-stock', 'stock-saree', 'Stock Saree', '', 'Muga',
          'draft', 0, ?, ?)`,
      )
      .bind(now, now),
    env.DB
      .prepare(
        `INSERT INTO variants (
          id, product_id, sku, title, price_minor, currency,
          publication_state, created_at, updated_at
        ) VALUES (?, 'product-stock', 'STOCK-001', 'Standard', 10000, 'INR',
          'draft', ?, ?)`,
      )
      .bind(VARIANT_ID, now, now),
    env.DB
      .prepare(
        "INSERT INTO inventory_items (variant_id, quantity, updated_at) VALUES (?, 0, ?)",
      )
      .bind(VARIANT_ID, now),
  ]);
});

async function quantity(): Promise<number | null> {
  return env.DB.prepare(
    "SELECT quantity FROM inventory_items WHERE variant_id = ?",
  )
    .bind(VARIANT_ID)
    .first<number>("quantity");
}

describe("inventory adjustments", () => {
  it("is idempotent, non-negative, and immutable", async () => {
    const firstKey = crypto.randomUUID();
    const first = await adjustInventory(env.DB, {
      variantId: VARIANT_ID,
      delta: 3,
      reason: "Initial stock",
      idempotencyKey: firstKey,
    });
    expect(await quantity()).toBe(3);
    expect(
      (
        await adjustInventory(env.DB, {
          variantId: VARIANT_ID,
          delta: 3,
          reason: "Retry",
          idempotencyKey: firstKey,
        })
      ).id,
    ).toBe(first.id);
    expect(await quantity()).toBe(3);
    expect(
      await env.DB.prepare("SELECT COUNT(*) AS count FROM inventory_adjustments").first(
        "count",
      ),
    ).toBe(1);

    await expect(
      adjustInventory(env.DB, {
        variantId: VARIANT_ID,
        delta: -4,
        reason: "Impossible sale",
        idempotencyKey: crypto.randomUUID(),
      }),
    ).rejects.toMatchObject({ status: 409, code: "insufficient_stock" });
    expect(await quantity()).toBe(3);

    await adjustInventory(env.DB, {
      variantId: VARIANT_ID,
      delta: -3,
      reason: "Stock correction",
      idempotencyKey: crypto.randomUUID(),
    });
    expect(await quantity()).toBe(0);

    await expect(
      env.DB.prepare("UPDATE inventory_adjustments SET reason = 'changed' WHERE id = ?")
        .bind(first.id)
        .run(),
    ).rejects.toThrow(/inventory_adjustments_immutable/);
    await expect(
      env.DB.prepare("DELETE FROM inventory_adjustments WHERE id = ?").bind(first.id).run(),
    ).rejects.toThrow(/inventory_adjustments_immutable/);
  });

  it("applies concurrent retries only once", async () => {
    const idempotencyKey = crypto.randomUUID();
    const input = {
      variantId: VARIANT_ID,
      delta: 2,
      reason: "Received stock",
      idempotencyKey,
    };
    const [left, right] = await Promise.all([
      adjustInventory(env.DB, input),
      adjustInventory(env.DB, input),
    ]);
    expect(left.id).toBe(right.id);
    expect(await quantity()).toBe(2);
    expect(
      await env.DB.prepare("SELECT COUNT(*) AS count FROM inventory_adjustments").first(
        "count",
      ),
    ).toBe(1);
  });

  it("rejects anonymous and CSRF-invalid adjustment requests", async () => {
    const path = `${ORIGIN}/admin/inventory/${VARIANT_ID}/adjust`;
    const anonymous = await SELF.fetch(path, {
      method: "POST",
      redirect: "manual",
      headers: {
        origin: ORIGIN,
        "content-type": "application/x-www-form-urlencoded",
      },
      body: new URLSearchParams({
        delta: "1",
        reason: "Received stock",
        idempotency_key: crypto.randomUUID(),
      }),
    });
    expect(anonymous.status).toBe(303);

    const now = new Date().toISOString();
    await env.DB.prepare(
      `INSERT INTO owner (
        id, email, password_hash, password_salt, password_iterations,
        session_version, created_at, updated_at
      ) VALUES ('owner', 'owner@example.com', 'unused', 'unused', 600000, 1, ?, ?)`,
    )
      .bind(now, now)
      .run();
    const cookie = await sessionCookie(
      {
        ownerId: "owner",
        sessionVersion: 1,
        expiresAt: Math.floor(Date.now() / 1000) + 3600,
        csrf: CSRF,
      },
      env,
    );
    const invalidCsrf = await SELF.fetch(path, {
      method: "POST",
      redirect: "manual",
      headers: {
        cookie,
        origin: ORIGIN,
        "content-type": "application/x-www-form-urlencoded",
      },
      body: new URLSearchParams({
        csrf: "wrong",
        delta: "1",
        reason: "Received stock",
        idempotency_key: crypto.randomUUID(),
      }),
    });
    expect(invalidCsrf.status).toBe(403);
    expect(await quantity()).toBe(0);
  });
});
