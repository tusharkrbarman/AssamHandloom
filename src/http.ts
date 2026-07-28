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

export function redirect(location: string, status: 303 | 307 = 303): Response {
  return new Response(null, { status, headers: { location } });
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
