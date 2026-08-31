const ESCAPES: Record<string, string> = {
  "&": "&amp;",
  "<": "&lt;",
  ">": "&gt;",
  '"': "&quot;",
  "'": "&#39;",
};

export class HttpError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    message: string,
  ) {
    super(message);
  }
}

export function html(
  body: string,
  status = 200,
  initialHeaders?: HeadersInit,
): Response {
  const headers = new Headers(initialHeaders);
  headers.set("content-type", "text/html; charset=utf-8");
  return new Response(body, { status, headers });
}

export function json(value: unknown, status = 200): Response {
  return Response.json(value, {
    status,
    headers: { "cache-control": "no-store" },
  });
}

export function redirect(
  location: string,
  status: 303 | 307 = 303,
  initialHeaders?: HeadersInit,
): Response {
  const headers = new Headers(initialHeaders);
  headers.set("location", location);
  return new Response(null, { status, headers });
}

export function escapeHtml(value: unknown): string {
  return String(value ?? "").replace(/[&<>"']/g, (character) => ESCAPES[character] ?? "");
}

export async function readForm(request: Request): Promise<FormData> {
  const contentType = request.headers.get("content-type")?.toLowerCase() ?? "";
  if (
    !contentType.startsWith("application/x-www-form-urlencoded") &&
    !contentType.startsWith("multipart/form-data")
  ) {
    throw new HttpError(415, "unsupported_media_type", "A form submission is required.");
  }
  try {
    return await request.formData();
  } catch {
    throw new HttpError(400, "invalid_form", "The submitted form could not be read.");
  }
}

export function requireSameOrigin(request: Request): void {
  const origin = request.headers.get("origin");
  if (!origin || origin !== new URL(request.url).origin) {
    throw new HttpError(403, "invalid_origin", "The request origin is not allowed.");
  }
}

const CONTENT_SECURITY_POLICY = [
  "default-src 'self'",
  "base-uri 'none'",
  "object-src 'none'",
  "frame-ancestors 'none'",
  "form-action 'self'",
  "img-src 'self' data:",
  "font-src 'self'",
  "script-src 'self' https://checkout.razorpay.com",
  "style-src 'self' 'unsafe-inline'",
  "connect-src 'self' https://api.razorpay.com",
  "frame-src https://api.razorpay.com https://checkout.razorpay.com",
].join("; ");

export function applySecurityHeaders(response: Response): Response {
  const headers = new Headers(response.headers);
  headers.set("content-security-policy", CONTENT_SECURITY_POLICY);
  headers.set("x-content-type-options", "nosniff");
  headers.set("x-frame-options", "DENY");
  headers.set("referrer-policy", "strict-origin-when-cross-origin");
  headers.set("permissions-policy", "camera=(), microphone=(), geolocation=()");
  headers.set("strict-transport-security", "max-age=31536000");
  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers,
  });
}
