import {
  cloudflareTest,
  readD1Migrations,
} from "@cloudflare/vitest-pool-workers";
import { defineConfig } from "vitest/config";

export default defineConfig(async () => {
  const migrations = await readD1Migrations("./d1-migrations");
  return {
    plugins: [
      cloudflareTest({
        wrangler: { configPath: "./wrangler.jsonc" },
        miniflare: {
          bindings: {
            ADMIN_SETUP_TOKEN: "test-setup-token-with-at-least-32-characters",
            ADMIN_RECOVERY_TOKEN: "test-recovery-token-with-at-least-32-characters",
            COOKIE_SIGNING_KEY: "test-cookie-signing-key-with-at-least-32-characters",
            TEST_MIGRATIONS: migrations,
          },
        },
      }),
    ],
    test: {
      setupFiles: ["./test/apply-migrations.ts"],
    },
  };
});
