# Luit & Loom

An Assamese silk saree store with the Quiet Commerce storefront, a private
single-owner dashboard, D1 catalogue and inventory data, and R2 product images.
Checkout, payments, customer order links, and email are intentionally reserved
for the next phase.

[![Deploy to Cloudflare](https://deploy.workers.cloudflare.com/button)](https://deploy.workers.cloudflare.com/?url=https://github.com/tusharkrbarman/AssamHandloom)

## Deploy to Cloudflare

1. Select the button above and sign in to Cloudflare.
2. Choose the Worker name, D1 database name, and R2 bucket name.
3. Provide three different random values of at least 32 characters for
   `ADMIN_SETUP_TOKEN`, `ADMIN_RECOVERY_TOKEN`, and `COOKIE_SIGNING_KEY`.
4. Keep the detected deploy command, `pnpm run deploy`. It applies every pending
   D1 migration before publishing the Worker.
5. After deployment, open `/admin/setup` once and create the store owner using
   `ADMIN_SETUP_TOKEN`.
6. Add products, variants, stock, collections, and images through `/admin`.
7. Open `/health`; `{"status":"ok"}` confirms that the Worker can reach D1.

Keep the recovery token separate from the setup and cookie-signing values. If
owner access is lost, open `/admin/recover`; a successful recovery invalidates
all older owner sessions.

The production catalogue starts empty. The bundled River, Reed & Gold records
belong only to the older preview and are not loaded into D1.

## Run the Cloudflare store locally

You need Node.js 24 and pnpm 11.

```powershell
pnpm install --frozen-lockfile
Copy-Item .dev.vars.example .dev.vars
pnpm run db:migrate:local
pnpm run dev
```

Replace every value in `.dev.vars` with a different local secret of at least
32 characters, then open the local URL shown by Wrangler. Create the owner at
`/admin/setup`.

Run all Worker checks with:

```powershell
pnpm run verify
```

## Current Phase 1 scope

- Quiet Commerce catalogue, search, filters, collections, and product pages
- Single-owner setup, login, recovery, signed sessions, CSRF protection, and
  login lockout
- Product, variant, collection, publication, and archive management
- Atomic non-negative inventory adjustments with immutable history
- JPEG, PNG, and WebP uploads to R2 with public/draft visibility controls

Not included yet: cart, checkout, payments, customer accounts or passwordless
order links, orders, email, refunds, tax automation, and shipping integrations.
