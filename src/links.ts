const LINK_TTL_SECONDS = 7 * 24 * 60 * 60;
const LINK_PURPOSE = "order-link-v1";

function toHex(buffer: ArrayBuffer): string {
  return [...new Uint8Array(buffer)]
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");
}

async function hmacHex(payload: string, secret: string): Promise<string> {
  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  return toHex(await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(payload)));
}

function hexEquals(expected: string, received: string): boolean {
  if (expected.length !== received.length) {
    return false;
  }
  let difference = 0;
  for (let index = 0; index < expected.length; index += 1) {
    difference |= expected.charCodeAt(index) ^ received.charCodeAt(index);
  }
  return difference === 0;
}

async function linkSignature(env: Env, orderId: string, expiresAt: number): Promise<string> {
  return hmacHex(`${LINK_PURPOSE}:${orderId}:${expiresAt}`, env.COOKIE_SIGNING_KEY);
}

export async function createOrderLink(
  env: Env,
  orderId: string,
  ttlSeconds = LINK_TTL_SECONDS,
): Promise<string> {
  const expiresAt = Math.floor(Date.now() / 1000) + ttlSeconds;
  const signature = await linkSignature(env, orderId, expiresAt);
  return `${orderId}?exp=${expiresAt}&sig=${signature}`;
}

export async function verifyOrderLink(
  env: Env,
  orderId: string,
  expiresAt: unknown,
  signature: unknown,
): Promise<boolean> {
  if (typeof expiresAt !== "number" || !Number.isSafeInteger(expiresAt)) {
    return false;
  }
  if (expiresAt <= Math.floor(Date.now() / 1000)) {
    return false;
  }
  if (typeof signature !== "string" || !/^[0-9a-f]{64}$/i.test(signature)) {
    return false;
  }
  const expected = await linkSignature(env, orderId, expiresAt);
  return hexEquals(expected, signature.toLowerCase());
}
