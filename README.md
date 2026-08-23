# Luit & Loom

An Assamese silk saree store with the Quiet Commerce storefront, a private
single-owner dashboard, D1 catalogue, inventory, and order data, R2 product
images, Razorpay checkout with transactional email, and optional customer
accounts.

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

### Optional integrations

Without extra secrets the store still works: checkout creates a pending order
and reports that online payments are unavailable, and no order email is queued.

- To sell online, add `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, and
  `RAZORPAY_WEBHOOK_SECRET` as Worker secrets (`wrangler secret put NAME` or in
  the Cloudflare dashboard), then point a Razorpay webhook at
  `/api/webhooks/razorpay` on your deployment using the same webhook secret.
- To send order email, add `RESEND_API_KEY` and `MAIL_FROM`. Also set
  `PUBLIC_BASE_URL` so pending-order confirmation emails include the
  passwordless order link.

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
`/admin/setup`. Uncomment the Razorpay and email lines to exercise those flows
locally.

Run all Worker checks with:

```powershell
pnpm run verify
```

## Current scope

- Quiet Commerce catalogue, search, filters, collections, and product pages
- Single-owner setup, login, recovery, signed sessions, CSRF protection, and
  login lockout
- Product, variant, collection, publication, and archive management
- Atomic non-negative inventory adjustments with immutable history
- JPEG, PNG, and WebP uploads to R2 with public/draft visibility controls
- Browser bag and guest checkout with server-side price and availability checks
- Orders with immutable product and price snapshots and time-limited inventory
  reservations in D1
- Razorpay checkout with signature-validated, idempotent webhooks
- Signed, expiring passwordless order links
- Order confirmation and payment-received email through a retrying Resend
  outbox
- A five-minute maintenance cron that releases expired reservations, expires
  abandoned pending orders, and drains the email outbox
- Owner order desk at `/admin/orders`: review orders, customer addresses, and
  payments; mark paid or shipped (with a shipped notification), or cancel
- Optional customer accounts with order history

Not included yet: refunds, coupons, reviews, shipping or tax automation,
delivery status emails beyond shipping, and staff roles beyond the single owner.
