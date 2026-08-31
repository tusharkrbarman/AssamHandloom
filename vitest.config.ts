import {
  cloudflareTest,
  readD1Migrations,
} from "@cloudflare/vitest-pool-workers";
import { defineConfig } from "vitest/config";

export default defineConfig(async () => {
  const migrations = await readD1Migrations("./d1-migrations");
  const providerOrderAttempts = new Map<string, number>();
  return {
    plugins: [
      cloudflareTest({
        wrangler: { configPath: "./wrangler.jsonc" },
        miniflare: {
          outboundService: async (request: Request) => {
            const url = new URL(request.url);
            if (url.hostname === "api.razorpay.com" && url.pathname === "/v1/orders") {
              const body = (await request.json()) as { receipt?: string };
              const receipt =
                typeof body.receipt === "string" ? body.receipt.slice(0, 13) : "unknown";
              const attempt = (providerOrderAttempts.get(receipt) ?? 0) + 1;
              providerOrderAttempts.set(receipt, attempt);
              return Response.json(
                { id: `order_mock_${receipt}_${attempt}` },
                { status: 200 },
              );
            }
            const refundMatch = url.pathname.match(/^\/v1\/payments\/([^/]+)\/refund$/);
            if (url.hostname === "api.razorpay.com" && refundMatch) {
              const body = (await request.json()) as { amount?: number };
              return Response.json(
                {
                  id: `rfnd_mock_${refundMatch[1]}`,
                  status: "processed",
                  amount: body.amount ?? null,
                },
                { status: 200 },
              );
            }
            if (url.hostname === "api.resend.com" && url.pathname === "/emails") {
              const body = (await request.json()) as { to?: string[] };
              const recipient = Array.isArray(body.to) ? (body.to[0] ?? "") : "";
              if (recipient.startsWith("fail")) {
                return Response.json({ message: "mailbox unavailable" }, { status: 500 });
              }
              return Response.json({ id: "email_stub_1" }, { status: 200 });
            }
            return new Response(`unexpected outbound fetch to ${url.origin}`, { status: 599 });
          },
          bindings: {
            ADMIN_SETUP_TOKEN: "test-setup-token-with-at-least-32-characters",
            ADMIN_RECOVERY_TOKEN: "test-recovery-token-with-at-least-32-characters",
            COOKIE_SIGNING_KEY: "test-cookie-signing-key-with-at-least-32-characters",
            RAZORPAY_KEY_ID: "rzp_test_1234567890abcdef",
            RAZORPAY_KEY_SECRET: "test-key-secret-with-at-least-32-characters",
            RAZORPAY_WEBHOOK_SECRET: "test-webhook-secret-with-at-least-32-char",
            RESEND_API_KEY: "test-resend-api-key-1234567890",
            MAIL_FROM: "Luit & Loom <orders@test.example>",
            PUBLIC_BASE_URL: "https://orders.test.example",
            TEST_MIGRATIONS: migrations,
          },
        },
      }),
    ],
    test: {
      setupFiles: ["./test/apply-migrations.ts"],
      exclude: ["**/node_modules/**", "**/.worktrees/**"],
    },
  };
});
