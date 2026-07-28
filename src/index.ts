import { routeAdmin } from "./admin";
import { routeAuth } from "./auth";
import { HttpError, json } from "./http";
import { renderStorefrontError, routeStorefront } from "./storefront";

interface RequestLog {
  requestId: string;
  method: string;
  pathname: string;
  status: number;
  durationMs: number;
  errorCode?: string;
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
  const auth = await routeAuth(request, env);
  if (auth) {
    return auth;
  }
  const admin = await routeAdmin(request, env);
  if (admin) {
    return admin;
  }
  const storefront = await routeStorefront(request, env);
  if (storefront) {
    return storefront;
  }
  const asset = await env.ASSETS.fetch(request);
  return asset.status === 404 && request.method === "GET"
    ? renderStorefrontError(request, 404, crypto.randomUUID())
    : asset;
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
          : renderStorefrontError(request, error.status, requestId);
      } else {
        errorCode = "internal_error";
        response = pathname.startsWith("/api/")
          ? json(
              { error: { code: "internal_error", message: "The request could not be completed." } },
              500,
            )
          : renderStorefrontError(request, 500, requestId);
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
