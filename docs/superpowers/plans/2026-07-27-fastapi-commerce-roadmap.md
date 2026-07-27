# Luit & Loom FastAPI Commerce Roadmap

**Source specification:** `docs/superpowers/specs/2026-07-27-luit-and-loom-fastapi-commerce-design.md`

The production store is divided into four independently testable implementation plans.

1. **Foundation and public catalogue**
   - FastAPI application, PostgreSQL, migrations, catalogue domain, sample data, brand system, homepage, collection, search, and product pages.
   - Exit condition: a responsive, accessible, read-only store can browse the 12-piece sample catalogue from PostgreSQL.

2. **Cart, checkout, payments, and orders**
   - Server-authoritative cart pricing, inventory reservations, guest checkout, Razorpay adapter, webhooks, orders, refunds, shipping, tax, coupons, jobs, and passwordless order access.
   - Exit condition: test-mode customers can complete an idempotent order without overselling unique inventory.

3. **Staff administration and provenance**
   - Staff authentication, Argon2id, TOTP, roles, catalogue/inventory/order workflows, editorial controls, artisan evidence, provenance verification, certificates, QR lookup, and audit history.
   - Exit condition: authorized staff can operate the store and issue public authenticity certificates without exposing private evidence.

4. **Production hardening and launch**
   - Application containerization, web/worker/scheduler runtime packaging, object storage, transactional email, privacy workflows, international configuration, deployment roles, backups, monitoring, security headers, rate limits, operational recovery, accessibility acceptance, and launch evidence.
   - Exit condition: every launch gate in the approved specification has evidence and the containerized application is deployable without Shopify.

Each phase receives its own task-level implementation plan and review cycle. Later phases build only on reviewed interfaces from earlier phases.
