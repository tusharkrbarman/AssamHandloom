import { HttpError } from "./http";

export function clientKey(request: Request, scope: string): string {
  const ip = request.headers.get("cf-connecting-ip")?.trim() ?? "unknown";
  return `${scope}:${ip}`;
}

export async function enforceRateLimit(
  env: Env,
  request: Request,
  scope: string,
): Promise<void> {
  const limiter = env.PUBLIC_RATE_LIMIT;
  if (!limiter) {
    return;
  }
  const result = await limiter.limit({ key: clientKey(request, scope) });
  if (!result.success) {
    throw new HttpError(
      429,
      "rate_limited",
      "Too many requests right now. Please try again shortly.",
    );
  }
}
