import { env } from "cloudflare:workers";
import { SELF } from "cloudflare:test";
import { describe, expect, it } from "vitest";

import { requireOwner } from "../src/auth";

const ORIGIN = "https://example.com";
const EMAIL = "owner@example.com";
const PASSWORD = "correct horse silk loom";

function request(
  path: string,
  method = "GET",
  fields?: Record<string, string | string[]>,
  cookie?: string,
): Promise<Response> {
  const headers = new Headers({ origin: ORIGIN });
  if (cookie) headers.set("cookie", cookie);
  let body: URLSearchParams | undefined;
  if (fields) {
    body = new URLSearchParams();
    for (const [key, value] of Object.entries(fields)) {
      for (const item of Array.isArray(value) ? value : [value]) body.append(key, item);
    }
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

function productFields(
  csrf: string,
  publicationState: "draft" | "published" = "draft",
): Record<string, string> {
  return {
    csrf,
    slug: "muga-dawn",
    title: "Muga Dawn",
    description: "A handwoven Muga silk saree.",
    silk_type: "Muga",
    colour: "Gold",
    occasion: "Wedding",
    publication_state: publicationState,
    featured_rank: "1",
  };
}

describe("owner catalogue management", () => {
  it("redirects an anonymous owner request to sign in", async () => {
    const response = await request("/admin");
    expect(response.status).toBe(303);
    expect(response.headers.get("location")).toBe("/admin/login");
  });

  it("validates catalogue writes and preserves public visibility rules", async () => {
    const { cookie, csrf } = await ownerSession();

    const created = await request(
      "/admin/products/new",
      "POST",
      productFields(csrf),
      cookie,
    );
    expect(created.status).toBe(303);
    const product = await env.DB.prepare(
      "SELECT id, publication_state FROM products WHERE slug = 'muga-dawn'",
    ).first<{ id: string; publication_state: string }>();
    expect(product?.publication_state).toBe("draft");

    const duplicate = {
      ...productFields(csrf),
      slug: "MUGA-DAWN",
      title: "Duplicate",
    };
    expect(
      (await request("/admin/products/new", "POST", duplicate, cookie)).status,
    ).toBe(409);
    expect((await request("/products/muga-dawn")).status).toBe(404);

    const variantPath = `/admin/products/${product?.id}/variants`;
    expect(
      (
        await request(
          variantPath,
          "POST",
          {
            csrf,
            sku: "MUGA-001",
            title: "Standard",
            price_minor: "-1",
            currency: "INR",
            weight_grams: "600",
            publication_state: "published",
          },
          cookie,
        )
      ).status,
    ).toBe(422);
    expect(
      (
        await request(
          variantPath,
          "POST",
          {
            csrf,
            sku: "MUGA-001",
            title: "Standard",
            price_minor: "185000",
            currency: "inr",
            weight_grams: "600",
            publication_state: "published",
          },
          cookie,
        )
      ).status,
    ).toBe(422);

    expect(
      (
        await request(
          variantPath,
          "POST",
          {
            csrf,
            sku: "MUGA-001",
            title: "Standard",
            price_minor: "185000",
            currency: "INR",
            weight_grams: "600",
            publication_state: "published",
          },
          cookie,
        )
      ).status,
    ).toBe(303);
    expect(
      await env.DB.prepare(
        `SELECT inventory.quantity
        FROM inventory_items inventory
        JOIN variants variant ON variant.id = inventory.variant_id
        WHERE variant.sku = 'MUGA-001'`,
      ).first("quantity"),
    ).toBe(0);

    expect(
      (
        await request(
          `/admin/products/${product?.id}`,
          "POST",
          productFields(csrf, "published"),
          cookie,
        )
      ).status,
    ).toBe(303);
    expect((await request("/products/muga-dawn")).status).toBe(200);

    expect(
      (
        await request(
          `/admin/products/${product?.id}/archive`,
          "POST",
          { csrf },
          cookie,
        )
      ).status,
    ).toBe(303);
    expect((await request("/products/muga-dawn")).status).toBe(404);
    expect(
      await env.DB.prepare("SELECT COUNT(*) AS count FROM products WHERE id = ?")
        .bind(product?.id)
        .first("count"),
    ).toBe(1);
  });

  it("replaces collection membership and records safe audit events", async () => {
    const { cookie, csrf } = await ownerSession();
    await request("/admin/products/new", "POST", productFields(csrf), cookie);
    const productId = await env.DB.prepare(
      "SELECT id FROM products WHERE slug = 'muga-dawn'",
    ).first<string>("id");

    for (const collection of [
      { slug: "wedding-edit", title: "Wedding Edit", order: "1" },
      { slug: "golden-silks", title: "Golden Silks", order: "2" },
    ]) {
      expect(
        (
          await request(
            "/admin/collections",
            "POST",
            {
              csrf,
              slug: collection.slug,
              title: collection.title,
              description: "",
              publication_state: "published",
              display_order: collection.order,
            },
            cookie,
          )
        ).status,
      ).toBe(303);
    }
    const collections = await env.DB.prepare(
      "SELECT id FROM collections ORDER BY display_order",
    ).all<{ id: string }>();
    const ids = collections.results.map((row) => row.id);
    expect(
      (
        await request(
          `/admin/products/${productId}/collections`,
          "POST",
          { csrf, product_id: ids },
          cookie,
        )
      ).status,
    ).toBe(303);
    expect(
      await env.DB.prepare(
        "SELECT COUNT(*) AS count FROM collection_products WHERE product_id = ?",
      )
        .bind(productId)
        .first("count"),
    ).toBe(2);

    await request(
      `/admin/products/${productId}/collections`,
      "POST",
      { csrf, product_id: [ids[1] ?? ""] },
      cookie,
    );
    expect(
      await env.DB.prepare(
        "SELECT COUNT(*) AS count FROM collection_products WHERE product_id = ?",
      )
        .bind(productId)
        .first("count"),
    ).toBe(1);

  });
});
