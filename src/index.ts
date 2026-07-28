import { escapeHtml, html, HttpError, json } from "./http";

interface RequestLog {
  requestId: string;
  method: string;
  pathname: string;
  status: number;
  durationMs: number;
  errorCode?: string;
}

function errorPage(status: number, message: string, requestId: string): Response {
  return html(
    `<!doctype html>
<html lang="en-IN">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>${status} · Luit &amp; Loom</title></head>
<body><main><h1>${status}</h1><p>${escapeHtml(message)}</p><p>Reference: ${escapeHtml(requestId)}</p></main></body>
</html>`,
    status,
    { "cache-control": "no-store" },
  );
}

async function health(env: Env): Promise<Response> {
  try {
    const row = await env.DB.prepare("SELECT 1 AS ok").first<{ ok: number }>();
    if (row?.ok !== 1) {
      return json({ status: "unavailable" }, 503);
    }
    return json({ status: "ok" });
  } catch {
    return json({ status: "unavailable" }, 503);
  }
}

async function route(request: Request, env: Env): Promise<Response> {
  const url = new URL(request.url);
  if (request.method === "GET" && url.pathname === "/health") {
    return health(env);
  }
  return env.ASSETS.fetch(request);
}

export default {
  async fetch(request, env): Promise<Response> {
    const started = Date.now();
    const requestId = crypto.randomUUID();
    const pathname = new URL(request.url).pathname;
    let response: Response;
    let errorCode: string | undefined;

    try {
      response = await route(request, env);
    } catch (error) {
      if (error instanceof HttpError) {
        errorCode = error.code;
        response = pathname.startsWith("/api/")
          ? json({ error: { code: error.code, message: error.message } }, error.status)
          : errorPage(error.status, error.message, requestId);
      } else {
        errorCode = "internal_error";
        response = pathname.startsWith("/api/")
          ? json(
              { error: { code: "internal_error", message: "The request could not be completed." } },
              500,
            )
          : errorPage(500, "The request could not be completed.", requestId);
      }
    }

    const headers = new Headers(response.headers);
    headers.set("x-request-id", requestId);
    response = new Response(response.body, {
      status: response.status,
      statusText: response.statusText,
      headers,
    });

    const entry: RequestLog = {
      requestId,
      method: request.method,
      pathname,
      status: response.status,
      durationMs: Date.now() - started,
    };
    if (errorCode) {
      entry.errorCode = errorCode;
    }
    console.log(JSON.stringify(entry));
    return response;
  },
} satisfies ExportedHandler<Env>;
