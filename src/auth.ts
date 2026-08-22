import {
  escapeHtml,
  html,
  HttpError,
  readForm,
  redirect,
  requireSameOrigin,
} from "./http";

const COOKIE_NAME = "luit_admin";
const PASSWORD_ITERATIONS = 600_000;
const SESSION_SECONDS = 8 * 60 * 60;
const LOCKOUT_SECONDS = 15 * 60;
const encoder = new TextEncoder();

interface OwnerRecord {
  id: "owner";
  email: string;
  password_hash: string;
  password_salt: string;
  password_iterations: number;
  session_version: number;
}

interface LockoutRecord {
  failed_count: number;
  locked_until: string | null;
}

interface AdminSession {
  ownerId: "owner";
  sessionVersion: number;
  expiresAt: number;
  csrf: string;
}

export interface AuthenticatedOwner {
  owner: {
    id: "owner";
    email: string;
    sessionVersion: number;
  };
  session: AdminSession;
}

function formText(form: FormData, key: string): string {
  const value = form.get(key);
  return typeof value === "string" ? value : "";
}

function toBase64Url(bytes: Uint8Array): string {
  let binary = "";
  for (const byte of bytes) {
    binary += String.fromCharCode(byte);
  }
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
}

function fromBase64Url(value: string): Uint8Array {
  const base64 = value.replace(/-/g, "+").replace(/_/g, "/");
  const padded = base64.padEnd(Math.ceil(base64.length / 4) * 4, "=");
  try {
    return Uint8Array.from(atob(padded), (character) => character.charCodeAt(0));
  } catch {
    throw new HttpError(401, "invalid_session", "Please sign in again.");
  }
}

function randomToken(byteLength = 32): string {
  return toBase64Url(crypto.getRandomValues(new Uint8Array(byteLength)));
}

async function digest(value: string): Promise<Uint8Array> {
  return new Uint8Array(await crypto.subtle.digest("SHA-256", encoder.encode(value)));
}

function timingSafeBytesEqual(left: Uint8Array, right: Uint8Array): boolean {
  if (left.byteLength !== right.byteLength) return false;

  let difference = 0;
  for (let index = 0; index < left.byteLength; index += 1) {
    difference |= (left[index] ?? 0) ^ (right[index] ?? 0);
  }
  return difference === 0;
}

async function timingSafeTextEqual(left: string, right: string): Promise<boolean> {
  const [leftDigest, rightDigest] = await Promise.all([digest(left), digest(right)]);
  return timingSafeBytesEqual(leftDigest, rightDigest);
}

async function derivePassword(
  password: string,
  salt: Uint8Array,
  iterations: number,
): Promise<Uint8Array> {
  const key = await crypto.subtle.importKey(
    "raw",
    encoder.encode(password),
    "PBKDF2",
    false,
    ["deriveBits"],
  );
  return new Uint8Array(
    await crypto.subtle.deriveBits(
      { name: "PBKDF2", hash: "SHA-256", salt, iterations },
      key,
      256,
    ),
  );
}

async function passwordRecord(password: string): Promise<{
  hash: string;
  salt: string;
  iterations: number;
}> {
  const salt = crypto.getRandomValues(new Uint8Array(16));
  return {
    hash: toBase64Url(await derivePassword(password, salt, PASSWORD_ITERATIONS)),
    salt: toBase64Url(salt),
    iterations: PASSWORD_ITERATIONS,
  };
}

function normalizedEmail(value: string): string {
  const email = value.trim().toLowerCase();
  const parts = email.split("@");
  if (
    email.length < 3 ||
    email.length > 254 ||
    parts.length !== 2 ||
    !parts[0] ||
    !parts[1] ||
    /\s/.test(email)
  ) {
    throw new HttpError(422, "invalid_email", "Enter a valid email address.");
  }
  return email;
}

function validPassword(value: string): string {
  const length = [...value].length;
  if (length < 12 || length > 128) {
    throw new HttpError(
      422,
      "invalid_password",
      "The password must contain between 12 and 128 characters.",
    );
  }
  return value;
}

function validSecret(value: string): string {
  if (value.length < 32 || value.length > 512) {
    throw new HttpError(403, "invalid_credentials", "The supplied credentials are invalid.");
  }
  return value;
}

async function hmacKey(secret: string): Promise<CryptoKey> {
  if (secret.length < 32) {
    throw new HttpError(500, "invalid_configuration", "Authentication is unavailable.");
  }
  return crypto.subtle.importKey(
    "raw",
    encoder.encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign", "verify"],
  );
}

async function signedSessionValue(session: AdminSession, secret: string): Promise<string> {
  const payload = toBase64Url(encoder.encode(JSON.stringify(session)));
  const signature = new Uint8Array(
    await crypto.subtle.sign("HMAC", await hmacKey(secret), encoder.encode(payload)),
  );
  return `${payload}.${toBase64Url(signature)}`;
}

function cookieValue(request: Request): string | null {
  const cookie = request.headers.get("cookie") ?? "";
  for (const part of cookie.split(";")) {
    const [name, ...value] = part.trim().split("=");
    if (name === COOKIE_NAME) {
      return value.join("=") || null;
    }
  }
  return null;
}

async function verifiedSessionValue(
  value: string,
  secret: string,
): Promise<AdminSession> {
  const segments = value.split(".");
  const payload = segments[0];
  const signature = segments[1];
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
    !("ownerId" in parsed) ||
    parsed.ownerId !== "owner" ||
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
  return parsed as AdminSession;
}

export async function sessionCookie(
  session: AdminSession,
  env: Env,
): Promise<string> {
  const value = await signedSessionValue(session, env.COOKIE_SIGNING_KEY);
  return `${COOKIE_NAME}=${value}; Path=/admin; Max-Age=${SESSION_SECONDS}; HttpOnly; Secure; SameSite=Strict`;
}

export function clearSessionCookie(): string {
  return `${COOKIE_NAME}=; Path=/admin; Max-Age=0; HttpOnly; Secure; SameSite=Strict`;
}

async function ownerRecord(db: D1Database): Promise<OwnerRecord | null> {
  return db
    .prepare(
      `SELECT
        id, email, password_hash, password_salt, password_iterations, session_version
      FROM owner
      WHERE id = 'owner'`,
    )
    .first<OwnerRecord>();
}

export async function requireOwner(
  request: Request,
  env: Env,
): Promise<AuthenticatedOwner> {
  const value = cookieValue(request);
  if (!value) {
    throw new HttpError(401, "authentication_required", "Please sign in.");
  }
  const session = await verifiedSessionValue(value, env.COOKIE_SIGNING_KEY);
  if (session.expiresAt <= Math.floor(Date.now() / 1000)) {
    throw new HttpError(401, "session_expired", "Please sign in again.");
  }
  const owner = await ownerRecord(env.DB);
  if (!owner || owner.session_version !== session.sessionVersion) {
    throw new HttpError(401, "invalid_session", "Please sign in again.");
  }
  return {
    owner: {
      id: "owner",
      email: owner.email,
      sessionVersion: owner.session_version,
    },
    session,
  };
}

export async function requireCsrf(
  request: Request,
  session: AdminSession,
  form: FormData,
): Promise<void> {
  requireSameOrigin(request);
  const submitted = formText(form, "csrf");
  if (!submitted || !(await timingSafeTextEqual(submitted, session.csrf))) {
    throw new HttpError(403, "invalid_csrf", "The form has expired. Please try again.");
  }
}

async function lockoutKey(request: Request, email: string): Promise<string> {
  const source = request.headers.get("CF-Connecting-IP") ?? "unknown";
  return toBase64Url(await digest(`${email}\u0000${source}`));
}

async function activeLockout(
  db: D1Database,
  key: string,
  now: Date,
): Promise<boolean> {
  const row = await db
    .prepare("SELECT failed_count, locked_until FROM login_lockouts WHERE key_hash = ?")
    .bind(key)
    .first<LockoutRecord>();
  return Boolean(row?.locked_until && Date.parse(row.locked_until) > now.getTime());
}

async function recordFailure(
  db: D1Database,
  key: string,
  now: Date,
): Promise<void> {
  const current = await db
    .prepare("SELECT failed_count, locked_until FROM login_lockouts WHERE key_hash = ?")
    .bind(key)
    .first<LockoutRecord>();
  const expired = current?.locked_until && Date.parse(current.locked_until) <= now.getTime();
  const failures = expired ? 1 : (current?.failed_count ?? 0) + 1;
  const lockedUntil =
    failures >= 5
      ? new Date(now.getTime() + LOCKOUT_SECONDS * 1000).toISOString()
      : null;
  await db
    .prepare(
      `INSERT INTO login_lockouts (key_hash, failed_count, locked_until, updated_at)
      VALUES (?, ?, ?, ?)
      ON CONFLICT(key_hash) DO UPDATE SET
        failed_count = excluded.failed_count,
        locked_until = excluded.locked_until,
        updated_at = excluded.updated_at`,
    )
    .bind(key, failures, lockedUntil, now.toISOString())
    .run();
}

async function passwordMatches(password: string, owner: OwnerRecord | null): Promise<boolean> {
  const salt = owner ? fromBase64Url(owner.password_salt) : new Uint8Array(16);
  const iterations = owner?.password_iterations ?? PASSWORD_ITERATIONS;
  const actual = await derivePassword(password, salt, iterations);
  const expected = owner ? fromBase64Url(owner.password_hash) : new Uint8Array(32);
  return timingSafeBytesEqual(actual, expected);
}

function authPage(title: string, body: string): Response {
  return html(`<!doctype html>
<html lang="en-IN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>${escapeHtml(title)} · Luit &amp; Loom</title>
  <link rel="stylesheet" href="/css/site.css">
</head>
<body>
  <a class="skip-link" href="#main-content">Skip to main content</a>
  <main id="main-content" class="container editorial-page" tabindex="-1">
    <a class="wordmark" href="/">Luit <span>&amp;</span> Loom</a>
    ${body}
  </main>
</body>
</html>`, 200, { "cache-control": "no-store" });
}

function setupPage(): Response {
  return authPage(
    "Owner setup",
    `<h1>Owner setup</h1>
    <p>Create the single store-owner account. This page closes after setup.</p>
    <form method="post" action="/admin/setup">
      <label for="setup-token">Setup token</label><input id="setup-token" name="token" type="password" required autocomplete="off">
      <label for="setup-email">Email</label><input id="setup-email" name="email" type="email" required autocomplete="username">
      <label for="setup-password">Password</label><input id="setup-password" name="password" type="password" minlength="12" maxlength="128" required autocomplete="new-password">
      <button type="submit">Create owner</button>
    </form>`,
  );
}

function loginPage(): Response {
  return authPage(
    "Owner sign in",
    `<h1>Owner sign in</h1>
    <form method="post" action="/admin/login">
      <label for="login-email">Email</label><input id="login-email" name="email" type="email" required autocomplete="username">
      <label for="login-password">Password</label><input id="login-password" name="password" type="password" required autocomplete="current-password">
      <button type="submit">Sign in</button>
    </form>
    <p><a href="/admin/recover">Recover owner access</a></p>`,
  );
}

function recoveryPage(): Response {
  return authPage(
    "Recover owner access",
    `<h1>Recover owner access</h1>
    <p>Use the separate recovery token stored in Cloudflare.</p>
    <form method="post" action="/admin/recover">
      <label for="recovery-token">Recovery token</label><input id="recovery-token" name="token" type="password" required autocomplete="off">
      <label for="recovery-email">Owner email</label><input id="recovery-email" name="email" type="email" required autocomplete="username">
      <label for="recovery-password">New password</label><input id="recovery-password" name="password" type="password" minlength="12" maxlength="128" required autocomplete="new-password">
      <button type="submit">Reset password</button>
    </form>`,
  );
}

async function setup(request: Request, env: Env): Promise<Response> {
  requireSameOrigin(request);
  const form = await readForm(request);
  const token = validSecret(formText(form, "token"));
  if (!(await timingSafeTextEqual(token, env.ADMIN_SETUP_TOKEN))) {
    throw new HttpError(403, "invalid_credentials", "The supplied credentials are invalid.");
  }
  if (await ownerRecord(env.DB)) {
    throw new HttpError(409, "setup_unavailable", "Owner setup is already complete.");
  }
  const email = normalizedEmail(formText(form, "email"));
  const password = validPassword(formText(form, "password"));
  const record = await passwordRecord(password);
  const now = new Date().toISOString();
  await env.DB
    .prepare(
      `INSERT INTO owner (
        id, email, password_hash, password_salt, password_iterations,
        session_version, created_at, updated_at
      ) VALUES ('owner', ?, ?, ?, ?, 1, ?, ?)`,
    )
    .bind(email, record.hash, record.salt, record.iterations, now, now)
    .run();
  return redirect("/admin/login?setup=complete");
}

async function login(request: Request, env: Env): Promise<Response> {
  requireSameOrigin(request);
  const form = await readForm(request);
  const email = normalizedEmail(formText(form, "email"));
  const password = validPassword(formText(form, "password"));
  const key = await lockoutKey(request, email);
  const now = new Date();
  if (await activeLockout(env.DB, key, now)) {
    throw new HttpError(429, "login_locked", "Sign in is temporarily unavailable.");
  }
  const owner = await ownerRecord(env.DB);
  if (!owner || owner.email !== email || !(await passwordMatches(password, owner))) {
    if (!owner || owner.email !== email) {
      await passwordMatches(password, null);
    }
    await recordFailure(env.DB, key, now);
    throw new HttpError(401, "invalid_credentials", "Email or password is incorrect.");
  }
  await env.DB
    .prepare("DELETE FROM login_lockouts WHERE key_hash = ?")
    .bind(key)
    .run();
  const session: AdminSession = {
    ownerId: "owner",
    sessionVersion: owner.session_version,
    expiresAt: Math.floor(Date.now() / 1000) + SESSION_SECONDS,
    csrf: randomToken(),
  };
  return redirect("/admin", 303, {
    "set-cookie": await sessionCookie(session, env),
  });
}

async function recover(request: Request, env: Env): Promise<Response> {
  requireSameOrigin(request);
  const form = await readForm(request);
  const token = validSecret(formText(form, "token"));
  const email = normalizedEmail(formText(form, "email"));
  const password = validPassword(formText(form, "password"));
  const owner = await ownerRecord(env.DB);
  const tokenMatches = await timingSafeTextEqual(token, env.ADMIN_RECOVERY_TOKEN);
  if (!owner || owner.email !== email || !tokenMatches) {
    throw new HttpError(403, "invalid_credentials", "The supplied credentials are invalid.");
  }
  const record = await passwordRecord(password);
  const now = new Date().toISOString();
  await env.DB
    .prepare(
      `UPDATE owner
      SET password_hash = ?, password_salt = ?, password_iterations = ?,
          session_version = session_version + 1, updated_at = ?
      WHERE id = 'owner'`,
    )
    .bind(record.hash, record.salt, record.iterations, now)
    .run();
  return redirect("/admin/login?recovered=complete");
}

async function logout(request: Request, env: Env): Promise<Response> {
  const authenticated = await requireOwner(request, env);
  const form = await readForm(request);
  await requireCsrf(request, authenticated.session, form);
  return new Response(null, {
    status: 303,
    headers: {
      location: "/admin/login",
      "set-cookie": clearSessionCookie(),
    },
  });
}

export async function routeAuth(
  request: Request,
  env: Env,
): Promise<Response | null> {
  const path = new URL(request.url).pathname;
  if (path === "/admin/setup") {
    if (request.method === "GET") {
      return setupPage();
    }
    if (request.method === "POST") {
      return setup(request, env);
    }
  }
  if (path === "/admin/login") {
    if (request.method === "GET") {
      return loginPage();
    }
    if (request.method === "POST") {
      return login(request, env);
    }
  }
  if (path === "/admin/recover") {
    if (request.method === "GET") {
      return recoveryPage();
    }
    if (request.method === "POST") {
      return recover(request, env);
    }
  }
  if (path === "/admin/logout" && request.method === "POST") {
    return logout(request, env);
  }
  return null;
}
