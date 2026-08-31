import { SELF } from "cloudflare:test";
import { describe, expect, it } from "vitest";

import { HttpError } from "../src/http";
import { enforceRateLimit } from "../src/ratelimit";

describe("security headers", () => {
  it("adds CSP and hardening headers to every response", async () => {
    const response = await SELF.fetch("https://example.com/");
    expect(response.status).toBe(200);
    const csp = response.headers.get("content-security-policy") ?? "";
    expect(csp).toContain("default-src 'self'");
    expect(csp).toContain("frame-ancestors 'none'");
    expect(csp).toContain("script-src 'self' https://checkout.razorpay.com");
    expect(response.headers.get("x-content-type-options")).toBe("nosniff");
    expect(response.headers.get("x-frame-options")).toBe("DENY");
    expect(response.headers.get("referrer-policy")).toBe("strict-origin-when-cross-origin");
    expect(response.headers.get("strict-transport-security")).toContain("max-age=");
  });

  it("does not load fonts blocked by the storefront CSP", async () => {
    const response = await SELF.fetch("https://example.com/");
    const html = await response.text();
    expect(html).not.toContain("fonts.googleapis.com");
    expect(html).not.toContain("fonts.gstatic.com");
  });
});

describe("rate limiting", () => {
  it("throws 429 when the binding rejects the request", async () => {
    const env = {
      PUBLIC_RATE_LIMIT: {
        limit: async () => ({ success: false }),
      },
    } as unknown as Env;
    const request = new Request("https://example.com/checkout", {
      method: "POST",
      headers: { "cf-connecting-ip": "203.0.113.9" },
    });
    await expect(enforceRateLimit(env, request, "checkout")).rejects.toMatchObject({
      status: 429,
      code: "rate_limited",
    } satisfies Partial<HttpError>);
  });

  it("passes requests through when the binding allows them", async () => {
    const env = {
      PUBLIC_RATE_LIMIT: {
        limit: async () => ({ success: true }),
      },
    } as unknown as Env;
    const request = new Request("https://example.com/checkout", { method: "POST" });
    await expect(enforceRateLimit(env, request, "checkout")).resolves.toBeUndefined();
  });

  it("is a no-op when no binding is configured", async () => {
    const env = {} as unknown as Env;
    const request = new Request("https://example.com/checkout", { method: "POST" });
    await expect(enforceRateLimit(env, request, "checkout")).resolves.toBeUndefined();
  });
});
