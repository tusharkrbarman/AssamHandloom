import { env } from "cloudflare:workers";
import { SELF } from "cloudflare:test";
import { beforeEach, describe, expect, it } from "vitest";

async function seedCatalogue(): Promise<void> {
  const created = "2026-07-28T00:00:00.000Z";
  await env.DB.batch([
    env.DB
      .prepare(
        `INSERT INTO products (
          id, slug, title, description, silk_type, colour, occasion,
          publication_state, featured_rank, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
      )
      .bind(
        "product-published",
        "luit-dawn",
        "Luit Dawn",
        "A luminous Muga silk study.",
        "Muga",
        "Gold",
        "Wedding",
        "published",
        1,
        created,
        created,
      ),
    env.DB
      .prepare(
        `INSERT INTO variants (
          id, product_id, sku, title, price_minor, currency, weight_grams,
          publication_state, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
      )
      .bind(
        "variant-published",
        "product-published",
        "MUGA-001",
        "Standard",
        185000,
        "INR",
        600,
        "published",
        created,
        created,
      ),
    env.DB
      .prepare(
        "INSERT INTO inventory_items (variant_id, quantity, updated_at) VALUES (?, ?, ?)",
      )
      .bind("variant-published", 1, created),
    env.DB
      .prepare(
        `INSERT INTO products (
          id, slug, title, description, silk_type, colour, occasion,
          publication_state, featured_rank, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
      )
      .bind(
        "product-draft",
        "hidden-weave",
        "Hidden Weave",
        "Owner-only draft.",
        "Pat",
        "Ivory",
        "Everyday",
        "draft",
        2,
        created,
        created,
      ),
    env.DB
      .prepare(
        `INSERT INTO variants (
          id, product_id, sku, title, price_minor, currency, weight_grams,
          publication_state, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
      )
      .bind(
        "variant-draft",
        "product-draft",
        "PAT-001",
        "Standard",
        95000,
        "INR",
        500,
        "published",
        created,
        created,
      ),
    env.DB
      .prepare(
        "INSERT INTO inventory_items (variant_id, quantity, updated_at) VALUES (?, ?, ?)",
      )
      .bind("variant-draft", 1, created),
    env.DB
      .prepare(
        `INSERT INTO collections (
          id, slug, title, description, publication_state, display_order,
          created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)`,
      )
      .bind(
        "collection-river",
        "river-edit",
        "River Edit",
        "A material conversation.",
        "published",
        1,
        created,
        created,
      ),
    env.DB
      .prepare(
        "INSERT INTO collection_products (collection_id, product_id) VALUES (?, ?)",
      )
      .bind("collection-river", "product-published"),
  ]);
}

beforeEach(seedCatalogue);

describe("Quiet Commerce storefront", () => {
  it("keeps the approved homepage and publication boundary", async () => {
    const response = await SELF.fetch("https://example.com/");
    const body = await response.text();
    expect(response.status).toBe(200);
    expect(body).toContain("Woven by Assam.");
    expect(body).toContain("Worn with meaning.");
    expect(body).toContain("Luit Dawn");
    expect(body).not.toContain("Hidden Weave");
  });

  it("keeps API and HTML visibility aligned while normalizing queries", async () => {
    const api = await SELF.fetch(
      "https://example.com/api/v1/catalog/products?search=%20%20Luit%20%20Dawn%20&page_size=99",
    );
    const payload = (await api.json()) as {
      items: Array<{ title: string }>;
      pageSize: number;
    };
    expect(api.status).toBe(200);
    expect(payload.items.map(({ title }) => title)).toEqual(["Luit Dawn"]);
    expect(payload.pageSize).toBe(24);

    const html = await SELF.fetch("https://example.com/shop?search=Luit");
    const body = await html.text();
    expect(body).toContain("Luit Dawn");
    expect(body).not.toContain("Hidden Weave");
  });

  it("rejects invalid API sorting but safely defaults HTML sorting", async () => {
    const api = await SELF.fetch(
      "https://example.com/api/v1/catalog/products?sort=unknown",
    );
    expect(api.status).toBe(422);
    expect(await api.json()).toMatchObject({
      error: { code: "invalid_sort" },
    });

    const page = await SELF.fetch("https://example.com/shop?sort=unknown");
    expect(page.status).toBe(200);
    expect(await page.text()).toContain("Luit Dawn");
  });

  it("supports published collections and branded not-found recovery", async () => {
    const collection = await SELF.fetch(
      "https://example.com/collections/river-edit",
    );
    const collectionBody = await collection.text();
    expect(collection.status).toBe(200);
    expect(collectionBody).toContain("River Edit");
    expect(collectionBody).toContain("Luit Dawn");

    const missing = await SELF.fetch(
      "https://example.com/products/not-a-product",
    );
    expect(missing.status).toBe(404);
    expect(await missing.text()).toContain("We couldn’t find that weave");
  });

  it("preserves the accessible shell and local stylesheet", async () => {
    const response = await SELF.fetch("https://example.com/");
    const body = await response.text();
    expect((body.match(/<main\b/g) ?? []).length).toBe(1);
    expect(body).toContain('href="#main-content"');
    expect(body).toContain('aria-label="Primary navigation"');
    expect(body).toContain('<details class="mobile-disclosure">');
    expect(body).toContain('role="search"');
    expect(body).toContain('href="/css/site.css"');
    const scripts = body.match(/<script\b[^>]*>/gi) ?? [];
    expect(scripts).toEqual(['<script src="/js/bag.js" defer>']);
  });
});
