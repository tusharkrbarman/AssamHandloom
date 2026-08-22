import { env, SELF } from "cloudflare:test";
import { beforeEach, describe, expect, it } from "vitest";

const ORIGIN = "https://example.com";
const PRODUCT_ID = "product-members";
const VARIANT_A = "dddd1111-1111-4111-8111-111111111111";

async function seedCatalogue(): Promise<void> {
  const now = new Date().toISOString();
  await env.DB.batch([
    env.DB
      .prepare(
        `INSERT INTO products (
          id, slug, title, description, silk_type, publication_state,
          featured_rank, created_at, updated_at
        ) VALUES (?, 'members-saree', 'Members Saree', '', 'Muga', 'published', 0, ?, ?)`,
      )
      .bind(PRODUCT_ID, now, now),
    env.DB
      .prepare(
        `INSERT INTO variants (
          id, product_id, sku, title, price_minor, currency,
          publication_state, created_at, updated_at
        ) VALUES (?, ?, 'MEM-A', 'Natural', 5000, 'INR', 'published', ?, ?)`,
      )
      .bind(VARIANT_A, PRODUCT_ID, now, now),
    env.DB
      .prepare("INSERT INTO inventory_items (variant_id, quantity, updated_at) VALUES (?, 5, ?)")
      .bind(VARIANT_A, now),
  ]);
}

beforeEach(() => seedCatalogue());

function memberCookie(response: Response): string {
  const raw = response.headers.get("set-cookie") ?? "";
  expect(raw).toContain("luit_member=");
  return raw.split(";")[0] ?? "";
}

async function registerMember(
  email = "member@example.com",
  password = "weaving-in-the-brahmaputra-valley",
): Promise<Response> {
  return SELF.fetch(`${ORIGIN}/account/register`, {
    method: "POST",
    redirect: "manual",
    headers: { origin: ORIGIN, "content-type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({ email, password }).toString(),
  });
}

async function loginMember(
  email = "member@example.com",
  password = "weaving-in-the-brahmaputra-valley",
): Promise<Response> {
  return SELF.fetch(`${ORIGIN}/account/login`, {
    method: "POST",
    redirect: "manual",
    headers: { origin: ORIGIN, "content-type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({ email, password }).toString(),
  });
}

describe("registration", () => {
  it("creates an account and signs the member straight in", async () => {
    const response = await registerMember();
    expect(response.status).toBe(303);
    expect(response.headers.get("location")).toBe("/account");
    expect(memberCookie(response)).toContain("luit_member=");

    const row = await env.DB
      .prepare("SELECT email, session_version FROM customers WHERE lower(email) = ?")
      .bind("member@example.com")
      .first<{ email: string; session_version: number }>();
    expect(row?.email.toLowerCase()).toBe("member@example.com");
    expect(row?.session_version).toBe(1);
  });

  it("refuses duplicate registrations without leaking sessions", async () => {
    await registerMember();
    const second = await registerMember();
    expect(second.status).toBe(409);
    const payload = await second.text();
    expect(payload).toMatch(/already exists/i);
    expect(second.headers.get("set-cookie") ?? "").not.toContain("luit_member=");
  });

  it("enforces the same password policy as admin accounts", async () => {
    const weak = await registerMember("weak@example.com", "short");
    expect(weak.status).toBe(422);
  });

  it("requires a same-origin header", async () => {
    const response = await SELF.fetch(`${ORIGIN}/account/register`, {
      method: "POST",
      redirect: "manual",
      headers: { "content-type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({
        email: "member@example.com",
        password: "weaving-in-the-brahmaputra-valley",
      }).toString(),
    });
    expect(response.status).toBe(403);
  });
});

describe("member sessions", () => {
  it("logs in with valid credentials and shows order history", async () => {
    await registerMember();
    const login = await loginMember();
    expect(login.status).toBe(303);

    const account = await SELF.fetch(`${ORIGIN}/account`, {
      headers: { cookie: memberCookie(login) },
    });
    expect(account.status).toBe(200);
    const html = await account.text();
    expect(html).toContain("member@example.com");
    expect(html).toMatch(/No orders yet/);
  });

  it("rejects wrong passwords and records failures", async () => {
    await registerMember();
    const bad = await loginMember("member@example.com", "totally-wrong-password-here");
    expect(bad.status).toBe(401);
    const lockout = await env.DB
      .prepare("SELECT failed_count FROM login_lockouts")
      .all<{ failed_count: number }>();
    expect(lockout.results?.length ?? 0).toBeGreaterThanOrEqual(1);
  });

  it("locks the source after five failures", async () => {
    await registerMember();
    for (let attempt = 0; attempt < 5; attempt += 1) {
      await loginMember("member@example.com", "totally-wrong-password-here");
    }
    const evenCorrect = await loginMember();
    expect(evenCorrect.status).toBe(429);
  });

  it("redirects anonymous visits to the login page", async () => {
    const response = await SELF.fetch(`${ORIGIN}/account`, { redirect: "manual" });
    expect(response.status).toBe(303);
    expect(response.headers.get("location")).toBe("/account/login");
  });

  it("invalidates sessions after a password change bumps the version", async () => {
    await registerMember();
    const login = await loginMember();
    const cookie = memberCookie(login);
    await env.DB
      .prepare("UPDATE customers SET session_version = session_version + 1 WHERE lower(email) = ?")
      .bind("member@example.com")
      .run();
    const stale = await SELF.fetch(`${ORIGIN}/account`, {
      redirect: "manual",
      headers: { cookie },
    });
    expect(stale.status).toBe(303);
  });

  it("signs out via csrf-protected logout", async () => {
    await registerMember();
    const login = await loginMember();
    const cookie = memberCookie(login);
    const page = await SELF.fetch(`${ORIGIN}/account`, { headers: { cookie } });
    const html = await page.text();
    const csrfMatch = /name="csrf" value="([^"]+)"/.exec(html);
    const csrf = csrfMatch?.[1] ?? "";

    const withoutCsrf = await SELF.fetch(`${ORIGIN}/account/logout`, {
      method: "POST",
      redirect: "manual",
      headers: { origin: ORIGIN, cookie, "content-type": "application/x-www-form-urlencoded" },
      body: "csrf=wrong",
    });
    expect(withoutCsrf.status).toBe(403);

    const out = await SELF.fetch(`${ORIGIN}/account/logout`, {
      method: "POST",
      redirect: "manual",
      headers: { origin: ORIGIN, cookie, "content-type": "application/x-www-form-urlencoded" },
      body: `csrf=${encodeURIComponent(csrf)}`,
    });
    expect(out.status).toBe(303);
    expect(out.headers.get("location")).toBe("/");
  });
});

describe("member orders", () => {
  it("lists orders placed with the member email and links via signed URLs", async () => {
    await registerMember();
    const login = await loginMember();
    const cookie = memberCookie(login);

    const checkout = await SELF.fetch(`${ORIGIN}/checkout`, {
      method: "POST",
      redirect: "manual",
      headers: { origin: ORIGIN, cookie, "content-type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({
        items: JSON.stringify([{ variantId: VARIANT_A, quantity: 1 }]),
        email: "member@example.com",
        name: "Member Buyer",
        phone: "+91 98765 43210",
        address1: "12 Loom Lane",
        city: "Guwahati",
        state: "Assam",
        postal_code: "781001",
        country: "IN",
      }).toString(),
    });
    expect(checkout.status).toBe(303);

    const account = await SELF.fetch(`${ORIGIN}/account`, { headers: { cookie } });
    const html = await account.text();
    expect(html).toMatch(/Awaiting payment/);
    const linkMatch = /href="(\/orders\/[0-9a-f-]{36}\?exp=\d+&amp;sig=[0-9a-f]{64})"/.exec(html);
    const linkPath = linkMatch?.[1];
    expect(linkPath).toBeTruthy();

    const orderPage = await SELF.fetch(`${ORIGIN}${linkPath?.replace("&amp;", "&")}`);
    expect(orderPage.status).toBe(200);
    expect(await orderPage.text()).toContain("Members Saree · Natural");
  });

  it("prefills the checkout email for signed-in members", async () => {
    await registerMember();
    const login = await loginMember();
    const page = await SELF.fetch(`${ORIGIN}/checkout`, { headers: { cookie: memberCookie(login) } });
    const html = await page.text();
    expect(html).toContain('value="member@example.com"');
  });

  it("never exposes other customers' orders", async () => {
    await registerMember("owner-one@example.com");
    const stranger = await registerMember("stranger@example.com");

    await SELF.fetch(`${ORIGIN}/checkout`, {
      method: "POST",
      redirect: "manual",
      headers: { origin: ORIGIN, "content-type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({
        items: JSON.stringify([{ variantId: VARIANT_A, quantity: 1 }]),
        email: "owner-one@example.com",
        name: "Owner One",
        phone: "+91 98765 43210",
        address1: "12 Loom Lane",
        city: "Guwahati",
        state: "Assam",
        postal_code: "781001",
        country: "IN",
      }).toString(),
    });

    const account = await SELF.fetch(`${ORIGIN}/account`, {
      headers: { cookie: memberCookie(stranger) },
    });
    const html = await account.text();
    expect(html).toMatch(/No orders yet/);
  });
});
