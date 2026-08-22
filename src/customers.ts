import {
  activeLockout,
  authPage,
  formText,
  fromBase64Url,
  hmacKey,
  lockoutKey,
  normalizedEmail,
  passwordMatches,
  passwordRecord,
  randomToken,
  recordFailure,
  timingSafeTextEqual,
  toBase64Url,
  validPassword,
} from "./auth";
import { createOrderLink } from "./links";
import { escapeHtml, HttpError, readForm, redirect, requireSameOrigin } from "./http";

const COOKIE_NAME = "luit_member";
const SESSION_SECONDS = 30 * 24 * 60 * 60;
const encoder = new TextEncoder();

const STATUS_LABELS: Record<string, string> = {
  pending: "Awaiting payment",
  paid: "Payment received",
  fulfilled: "On its way",
  cancelled: "Cancelled",
  expired: "Expired",
};

interface CustomerRecord {
  id: string;
  email: string;
  session_version: number;
}

interface MemberSession {
  customerId: string;
  sessionVersion: number;
  expiresAt: number;
  csrf: string;
}

export interface AuthenticatedMember {
  customer: { id: string; email: string; sessionVersion: number };
  session: MemberSession;
}

function memberCookieValue(request: Request): string | null {
  const cookie = request.headers.get("cookie") ?? "";
  for (const part of cookie.split(";")) {
    const [name, ...value] = part.trim().split("=");
    if (name === COOKIE_NAME) {
      return value.join("=") || null;
    }
  }
  return null;
}

async function signedMemberValue(session: MemberSession, secret: string): Promise<string> {
  const payload = toBase64Url(encoder.encode(JSON.stringify(session)));
  const signature = new Uint8Array(
    await crypto.subtle.sign("HMAC", await hmacKey(secret), encoder.encode(payload)),
  );
  return `${payload}.${toBase64Url(signature)}`;
}

async function verifiedMemberValue(value: string, secret: string): Promise<MemberSession> {
  const segments = value.split(".");
  const payload = segments[0];
  const signature = segments[1];
  const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
  if (!payload || !signature || segments.length !== 2) {
    throw new HttpError(401, "invalid_session", "Please sign in again.");
  }
  const verified = await crypto.subtle.verify(
    "HMAC",
    await hmacKey(secret),
    fromBase64Url(signature),
    encoder.encode(payload),
  );
  if (!verified) {
    throw new HttpError(401, "invalid_session", "Please sign in again.");
  }
  let parsed: unknown;
  try {
    parsed = JSON.parse(new TextDecoder().decode(fromBase64Url(payload)));
  } catch {
    throw new HttpError(401, "invalid_session", "Please sign in again.");
  }
  if (
    !parsed ||
    typeof parsed !== "object" ||
    !("customerId" in parsed) ||
    typeof parsed.customerId !== "string" ||
    !uuidPattern.test(parsed.customerId) ||
    !("sessionVersion" in parsed) ||
    !Number.isSafeInteger(parsed.sessionVersion) ||
    !("expiresAt" in parsed) ||
    !Number.isSafeInteger(parsed.expiresAt) ||
    !("csrf" in parsed) ||
    typeof parsed.csrf !== "string" ||
    parsed.csrf.length < 32
  ) {
    throw new HttpError(401, "invalid_session", "Please sign in again.");
  }
  return parsed as MemberSession;
}

async function memberSessionCookie(session: MemberSession, env: Env): Promise<string> {
  const value = await signedMemberValue(session, env.COOKIE_SIGNING_KEY);
  return `${COOKIE_NAME}=${value}; Path=/; Max-Age=${SESSION_SECONDS}; HttpOnly; Secure; SameSite=Strict`;
}

function clearMemberCookie(): string {
  return `${COOKIE_NAME}=; Path=/; Max-Age=0; HttpOnly; Secure; SameSite=Strict`;
}

export async function requireMember(
  request: Request,
  env: Env,
): Promise<AuthenticatedMember> {
  const value = memberCookieValue(request);
  if (!value) {
    throw new HttpError(401, "authentication_required", "Please sign in.");
  }
  const session = await verifiedMemberValue(value, env.COOKIE_SIGNING_KEY);
  if (session.expiresAt <= Math.floor(Date.now() / 1000)) {
    throw new HttpError(401, "session_expired", "Please sign in again.");
  }
  const customer = await env.DB
    .prepare("SELECT id, email, session_version FROM customers WHERE id = ?")
    .bind(session.customerId)
    .first<CustomerRecord>();
  if (!customer || customer.session_version !== session.sessionVersion) {
    throw new HttpError(401, "invalid_session", "Please sign in again.");
  }
  return {
    customer: { id: customer.id, email: customer.email, sessionVersion: customer.session_version },
    session,
  };
}

export async function optionalMemberEmail(request: Request, env: Env): Promise<string | null> {
  try {
    const authenticated = await requireMember(request, env);
    return authenticated.customer.email;
  } catch {
    return null;
  }
}

function accountPage(content: string): Response {
  return authPage("Your account", content);
}

function loginForm(message?: string): string {
  return `<h1>Sign in</h1>
  ${message ? `<p class="form-alert" role="alert">${escapeHtml(message)}</p>` : ""}
  <form method="post" action="/account/login">
    <label for="member-login-email">Email</label><input id="member-login-email" name="email" type="email" required autocomplete="username">
    <label for="member-login-password">Password</label><input id="member-login-password" name="password" type="password" required autocomplete="current-password">
    <button type="submit">Sign in</button>
  </form>
  <p>New here? <a href="/account/register">Create an account</a></p>`;
}

function loginPage(message?: string): Response {
  return authPage("Sign in", loginForm(message));
}

function registerPage(message?: string): Response {
  return authPage(
    "Create your account",
    `<h1>Create your account</h1>
    <p>Track your orders and check out faster.</p>
    ${message ? `<p class="form-alert" role="alert">${escapeHtml(message)}</p>` : ""}
    <form method="post" action="/account/register">
      <label for="register-email">Email</label><input id="register-email" name="email" type="email" required autocomplete="username">
      <label for="register-password">Password</label><input id="register-password" name="password" type="password" minlength="12" maxlength="128" required autocomplete="new-password">
      <button type="submit">Create account</button>
    </form>
    <p>Already have an account? <a href="/account/login">Sign in</a></p>`,
  );
}

async function register(request: Request, env: Env): Promise<Response> {
  requireSameOrigin(request);
  const form = await readForm(request);
  const email = normalizedEmail(formText(form, "email"));
  const password = validPassword(formText(form, "password"));
  const existing = await env.DB
    .prepare("SELECT id FROM customers WHERE email = ?")
    .bind(email)
    .first<{ id: string }>();
  if (existing) {
    throw new HttpError(409, "account_exists", "An account with this email already exists. Try signing in.");
  }
  const record = await passwordRecord(password);
  const now = new Date().toISOString();
  await env.DB
    .prepare(
      `INSERT INTO customers (
        id, email, password_hash, password_salt, password_iterations,
        session_version, created_at, updated_at
      ) VALUES (?, ?, ?, ?, ?, 1, ?, ?)`,
    )
    .bind(crypto.randomUUID(), email, record.hash, record.salt, record.iterations, now, now)
    .run();
  return loginMember(env, email, password);
}

async function loginMember(
  env: Env,
  email: string,
  password: string,
): Promise<Response> {
  const customer = await env.DB
    .prepare(
      `SELECT id, email, password_hash, password_salt, password_iterations, session_version
      FROM customers WHERE email = ?`,
    )
    .bind(email)
    .first<
      CustomerRecord & {
        password_hash: string;
        password_salt: string;
        password_iterations: number;
      }
    >();
  const matches = await passwordMatches(password, customer);
  if (!customer || !matches) {
    throw new HttpError(401, "invalid_credentials", "Email or password is incorrect.");
  }
  const session: MemberSession = {
    customerId: customer.id,
    sessionVersion: customer.session_version,
    expiresAt: Math.floor(Date.now() / 1000) + SESSION_SECONDS,
    csrf: randomToken(),
  };
  return redirect("/account", 303, {
    "set-cookie": await memberSessionCookie(session, env),
  });
}

async function login(request: Request, env: Env): Promise<Response> {
  requireSameOrigin(request);
  const form = await readForm(request);
  const email = normalizedEmail(formText(form, "email"));
  const password = validPassword(formText(form, "password"));
  const key = await lockoutKey(request, "member", email);
  const now = new Date();
  if (await activeLockout(env.DB, key, now)) {
    throw new HttpError(429, "login_locked", "Sign in is temporarily unavailable.");
  }
  try {
    return await loginMember(env, email, password);
  } catch (error) {
    if (error instanceof HttpError && error.code === "invalid_credentials") {
      await recordFailure(env.DB, key, now);
    }
    throw error;
  }
}

interface MemberOrderRow {
  id: string;
  status: string;
  currency: string;
  total_minor: number;
  created_at: string;
}

function formatInr(minor: number, currency: string): string {
  return new Intl.NumberFormat("en-IN", { style: "currency", currency }).format(minor / 100);
}

async function accountContent(env: Env, member: AuthenticatedMember): Promise<string> {
  const orders = await env.DB
    .prepare(
      `SELECT id, status, currency, total_minor, created_at FROM orders
      WHERE lower(email) = ? ORDER BY created_at DESC LIMIT 50`,
    )
    .bind(member.customer.email)
    .all<MemberOrderRow>();
  const rows = (
    await Promise.all(
      (orders.results ?? []).map(async (order) => {
        const label = STATUS_LABELS[order.status] ?? "Processing";
        const linkQuery = await createOrderLink(env, order.id, 60 * 60);
        return `<tr>
        <td><a href="/orders/${escapeHtml(linkQuery)}">${escapeHtml(order.id.slice(0, 8).toUpperCase())}</a></td>
        <td>${escapeHtml(order.created_at.slice(0, 10))}</td>
        <td>${escapeHtml(label)}</td>
        <td>${escapeHtml(formatInr(order.total_minor, order.currency))}</td>
      </tr>`;
      }),
    )
  ).join("");
  const orderSection = rows
    ? `<table class="bag-table">
        <thead><tr><th scope="col">Order</th><th scope="col">Placed</th><th scope="col">Status</th><th scope="col">Total</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>`
    : `<p class="empty-state">No orders yet. <a href="/shop">Find your first weave</a>.</p>`;
  return `<section class="commerce-page">
    <p class="eyebrow">Your account</p>
    <h1>Welcome back</h1>
    <p>Signed in as <strong>${escapeHtml(member.customer.email)}</strong></p>
    <h2>Order history</h2>
    ${orderSection}
    <form method="post" action="/account/logout">
      <input type="hidden" name="csrf" value="${escapeHtml(member.session.csrf)}">
      <button class="text-link" type="submit">Sign out</button>
    </form>
  </section>`;
}

async function logout(request: Request, env: Env): Promise<Response> {
  requireSameOrigin(request);
  const member = await requireMember(request, env);
  const form = await readForm(request);
  const submitted = formText(form, "csrf");
  if (!submitted || !(await timingSafeTextEqual(submitted, member.session.csrf))) {
    throw new HttpError(403, "invalid_csrf", "The form has expired. Please try again.");
  }
  return redirect("/", 303, { "set-cookie": clearMemberCookie() });
}

export async function routeCustomers(
  request: Request,
  env: Env,
): Promise<Response | null> {
  const path = new URL(request.url).pathname;

  if (path === "/account/login") {
    if (request.method === "GET") {
      return loginPage();
    }
    if (request.method === "POST") {
      try {
        return await login(request, env);
      } catch (error) {
        if (error instanceof HttpError) {
          return new Response(loginPage(error.message).body, {
            status: error.status,
            headers: { "cache-control": "no-store", "content-type": "text/html; charset=utf-8" },
          });
        }
        throw error;
      }
    }
  }

  if (path === "/account/register") {
    if (request.method === "GET") {
      return registerPage();
    }
    if (request.method === "POST") {
      try {
        return await register(request, env);
      } catch (error) {
        if (error instanceof HttpError) {
          return new Response(registerPage(error.message).body, {
            status: error.status,
            headers: { "cache-control": "no-store", "content-type": "text/html; charset=utf-8" },
          });
        }
        throw error;
      }
    }
  }

  if (path === "/account/logout" && request.method === "POST") {
    return logout(request, env);
  }

  if (path === "/account" || path === "/account/") {
    if (request.method !== "GET") {
      return null;
    }
    try {
      const member = await requireMember(request, env);
      return accountPage(await accountContent(env, member));
    } catch {
      return redirect("/account/login");
    }
  }

  return null;
}
