import { env } from "cloudflare:workers";
import { SELF } from "cloudflare:test";
import { describe, expect, it, vi } from "vitest";

import { requireOwner, sessionCookie } from "../src/auth";
import { HttpError } from "../src/http";

const ORIGIN = "https://example.com";
const EMAIL = "owner@example.com";
const PASSWORD = "correct horse silk loom";
const NEW_PASSWORD = "new correct horse silk loom";

function post(
  path: string,
  fields: Record<string, string>,
  cookie?: string,
  source = "203.0.113.10",
): Promise<Response> {
  const headers = new Headers({
    "content-type": "application/x-www-form-urlencoded",
    "cf-connecting-ip": source,
    origin: ORIGIN,
  });
  if (cookie) headers.set("cookie", cookie);
  return SELF.fetch(`${ORIGIN}${path}`, {
    method: "POST",
    headers,
    body: new URLSearchParams(fields),
    redirect: "manual",
  });
}

async function setup(): Promise<void> {
  const response = await post("/admin/setup", {
    token: env.ADMIN_SETUP_TOKEN,
    email: EMAIL,
    password: PASSWORD,
  });
  expect(response.status).toBe(303);
}

async function login(password = PASSWORD, source?: string): Promise<string> {
  const response = await post(
    "/admin/login",
    { email: EMAIL, password },
    undefined,
    source,
  );
  expect(response.status).toBe(303);
  return response.headers.get("set-cookie")?.split(";", 1)[0] ?? "";
}

describe("owner authentication", () => {
  it("allows setup once with the deployment token", async () => {
    expect(
      (
        await post("/admin/setup", {
          token: "wrong-token-that-is-still-long-enough",
          email: EMAIL,
          password: PASSWORD,
        })
      ).status,
    ).toBe(403);
    expect(
      await env.DB.prepare("SELECT COUNT(*) AS count FROM owner").first("count"),
    ).toBe(0);

    await setup();
    expect(
      (
        await post("/admin/setup", {
          token: env.ADMIN_SETUP_TOKEN,
          email: EMAIL,
          password: PASSWORD,
        })
      ).status,
    ).toBe(409);
  });

  it("issues a secure signed session and rejects tampering", async () => {
    await setup();
    const cookie = await login();
    expect(cookie).toContain("luit_admin=");

    const authenticated = await requireOwner(
      new Request(`${ORIGIN}/admin`, { headers: { cookie } }),
      env,
    );
    expect(authenticated.owner.email).toBe(EMAIL);

    const tampered = `${cookie.slice(0, -1)}${cookie.endsWith("A") ? "B" : "A"}`;
    await expect(
      requireOwner(new Request(`${ORIGIN}/admin`, { headers: { cookie: tampered } }), env),
    ).rejects.toMatchObject({ status: 401 });
  });

  it("locks repeated failures to their email and source", async () => {
    await setup();
    for (let attempt = 0; attempt < 5; attempt += 1) {
      expect(
        (await post("/admin/login", { email: EMAIL, password: "wrong password!" })).status,
      ).toBe(401);
    }
    expect(
      (await post("/admin/login", { email: EMAIL, password: PASSWORD })).status,
    ).toBe(429);
    expect(await login(PASSWORD, "198.51.100.20")).toContain("luit_admin=");
  });

  it("requires same-origin CSRF on logout", async () => {
    await setup();
    const cookie = await login();
    const authenticated = await requireOwner(
      new Request(`${ORIGIN}/admin`, { headers: { cookie } }),
      env,
    );

    expect(
      (await post("/admin/logout", { csrf: "wrong" }, cookie)).status,
    ).toBe(403);
    const response = await post(
      "/admin/logout",
      { csrf: authenticated.session.csrf },
      cookie,
    );
    expect(response.status).toBe(303);
    expect(response.headers.get("set-cookie")).toContain("Max-Age=0");
  });

  it("recovery invalidates sessions without exposing secrets", async () => {
    const log = vi.spyOn(console, "log").mockImplementation(() => undefined);
    await setup();
    const oldCookie = await login();
    const response = await post("/admin/recover", {
      token: env.ADMIN_RECOVERY_TOKEN,
      email: EMAIL,
      password: NEW_PASSWORD,
    });
    expect(response.status).toBe(303);
    await expect(
      requireOwner(new Request(`${ORIGIN}/admin`, { headers: { cookie: oldCookie } }), env),
    ).rejects.toBeInstanceOf(HttpError);
    expect(await login(NEW_PASSWORD)).toContain("luit_admin=");
    expect(log.mock.calls.flat().join(" ")).not.toContain(env.ADMIN_RECOVERY_TOKEN);
    log.mockRestore();
  });

  it("rejects expired sessions", async () => {
    await setup();
    const cookie = await sessionCookie(
      {
        ownerId: "owner",
        sessionVersion: 1,
        expiresAt: Math.floor(Date.now() / 1000) - 1,
        csrf: "csrf-token-with-at-least-thirty-two-characters",
      },
      env,
    );
    await expect(
      requireOwner(new Request(`${ORIGIN}/admin`, { headers: { cookie } }), env),
    ).rejects.toMatchObject({ status: 401, code: "session_expired" });
  });
});
