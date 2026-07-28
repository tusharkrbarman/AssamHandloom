import { env } from "cloudflare:workers";
import { SELF } from "cloudflare:test";
import { describe, expect, it } from "vitest";

const REQUIRED_TABLES = [
  "admin_audit_events",
  "collection_products",
  "collections",
  "inventory_adjustments",
  "inventory_items",
  "login_lockouts",
  "owner",
  "product_media",
  "products",
  "variants",
];

describe("Worker foundation", () => {
  it("reports Worker and D1 health", async () => {
    const response = await SELF.fetch("https://example.com/health");
    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({ status: "ok" });
    expect(response.headers.get("x-request-id")).toBeTruthy();
  });

  it("applies every Phase 1 table to an empty D1 database", async () => {
    const result = await env.DB.prepare(
      "SELECT name FROM sqlite_schema WHERE type = 'table' ORDER BY name",
    ).all<{ name: string }>();
    const tableNames = result.results.map(({ name }) => name);
    expect(tableNames).toEqual(expect.arrayContaining(REQUIRED_TABLES));
  });
});
