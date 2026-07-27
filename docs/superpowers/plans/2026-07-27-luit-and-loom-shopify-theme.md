# Luit & Loom Shopify Theme Implementation Plan

> **Status:** Superseded. Do not execute this plan. The project no longer uses Shopify; a FastAPI commerce implementation plan will replace it after the new design specification is reviewed.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and launch a bespoke Shopify Online Store 2.0 theme for Luit & Loom, with an artistic Assamese silk storefront, provenance-rich catalogue, real Shopify checkout, inventory, orders, and international-market readiness.

**Architecture:** Shopify owns products, metaobjects, inventory, customers, checkout, payments, orders, fulfilment, Markets, and reporting. The repository contains a buildless Online Store 2.0 theme using Liquid, JSON templates, CSS, and small ES modules; merchant content is supplied through section settings, product metafields, and artisan metaobjects. Theme behaviour is progressively enhanced, so core browsing, cart, and purchase flows remain usable if JavaScript is unavailable.

**Tech Stack:** Shopify Online Store 2.0, Liquid, JSON templates, CSS custom properties, ES2022 modules, Shopify Ajax APIs, Shopify CLI 3+, Theme Check, Vitest, jsdom, and Playwright for connected-store acceptance tests.

## Global Constraints

- The brand name is **Luit & Loom** and the tagline is **Woven by Assam. Worn with meaning.**
- The visual position is premium contemporary: authentic Assamese heritage presented with modern refinement.
- The palette is Muga gold, warm ivory, deep lac red, betel-leaf green, and charcoal.
- Use restrained Assamese textile geometry; do not use generic gold gradients, crowded festival graphics, or ornamental excess.
- INR is the store currency and India is the primary market.
- Checkout, raw payment data, inventory, orders, refunds, and fulfilment stay inside Shopify.
- Product provenance is first-class structured information, not secondary promotional copy.
- Generated imagery and sample identities must never be presented as actual inventory or documentary evidence.
- Theme-controlled experiences target WCAG 2.2 AA.
- Support keyboard use, visible focus, labelled controls, reduced motion, and touch targets of at least 44 by 44 CSS pixels.
- All images below the first viewport use responsive Shopify image URLs and lazy loading.
- No application dependency is added unless the same requirement cannot be met reliably with Shopify or theme code.
- No live-order launch occurs until all launch gates in the approved specification are satisfied.

---

## File Map

### Theme foundation

- `layout/theme.liquid` — shared HTML document, metadata, skip link, CSS/JS loading, and header/footer section groups.
- `config/settings_schema.json` — merchant-controlled brand, typography, colour, layout, social, and commerce settings.
- `config/settings_data.json` — safe initial theme defaults only; no store secrets or live merchant content.
- `locales/en.default.json` — all customer-facing interface strings.
- `.shopifyignore` — excludes documentation, tests, fixtures, scripts, and local tooling from theme uploads.
- `.theme-check.yml` — recommended Shopify checks and project exclusions.
- `package.json` — local quality scripts only; theme runtime remains buildless.

### Shared presentation and behaviour

- `assets/base.css` — tokens, reset, typography, layout primitives, accessibility, forms, buttons, drawers, and responsive rules.
- `assets/theme.js` — disclosure, drawer, focus trap, market selector, and reduced-motion-safe enhancement.
- `assets/cart.js` — cart add/update/remove, section rendering, error recovery, and live-region announcements.
- `assets/filters.js` — collection filter URL serialization and section refresh.
- `assets/wishlist.js` — device-local product-handle wishlist with storage failure fallback.
- `snippets/meta-tags.liquid` — canonical, SEO, Open Graph, and product structured metadata.
- `snippets/icon.liquid` — accessible icon mapping using text-safe inline markup.
- `snippets/price.liquid` — consistent money and compare-at rendering.
- `snippets/product-card.liquid` — product image, hover image, silk type, artisan, price, availability, and wishlist control.
- `snippets/pagination.liquid` — accessible pagination.
- `snippets/product-provenance.liquid` — structured silk, motif, origin, artisan, authenticity, and care facts.

### Site chrome

- `sections/header-group.json` and `sections/footer-group.json` — merchant-reorderable global section groups.
- `sections/announcement-bar.liquid` — concise market-aware assurance message.
- `sections/header.liquid` — desktop and mobile navigation, search, account, wishlist, cart, and market selector.
- `sections/footer.liquid` — policies, guidance, newsletter, social links, and trust details.

### Homepage

- `templates/index.json` — approved homepage sequence.
- `sections/hero-editorial.liquid` — cinematic hero with two clear actions.
- `sections/featured-collection.liquid` — curated product grid.
- `sections/silk-story.liquid` — “Why Assam silk” editorial introduction.
- `sections/silk-collection-cards.liquid` — Muga, Pat, and Eri paths.
- `sections/artisan-feature.liquid` — featured artisan and making process.
- `sections/craft-assurances.liquid` — authenticity, shipping, returns, and care.
- `sections/occasion-edit.liquid` — occasion-led recommendations.
- `sections/editorial-newsletter.liquid` — newsletter invitation.

### Commerce and discovery

- `templates/collection.json` and `sections/main-collection.liquid` — native storefront filters, sorting, result count, product grid, and empty state.
- `templates/product.json` and `sections/main-product.liquid` — media, product form, stock, dispatch, service options, and provenance.
- `sections/product-recommendations.liquid` — related sarees using Shopify recommendations.
- `templates/cart.json` and `sections/main-cart.liquid` — line editing, notes, market messaging, and checkout.
- `templates/search.json` and `sections/main-search.liquid` — predictive-compatible search results and empty state.
- `templates/page.wishlist.json` and `sections/main-wishlist.liquid` — device-local wishlist display.

### Editorial and customer support

- `templates/page.json`, `sections/main-page.liquid` — general content pages.
- `templates/blog.json`, `sections/main-blog.liquid` — journal index.
- `templates/article.json`, `sections/main-article.liquid` — editorial article.
- `templates/metaobject/artisan.json`, `sections/main-artisan.liquid` — artisan profile pages.
- `templates/404.json`, `sections/main-404.liquid` — useful not-found recovery.
- `templates/password.json`, `sections/main-password.liquid` — prelaunch page.

### Store data and operations

- `data/river-reed-gold.json` — twelve clearly marked sample catalogue records and four sample artisan records.
- `scripts/validate-catalog.mjs` — schema and launch-safety validation for catalogue content.
- `scripts/generate-products-csv.mjs` — deterministic Shopify product CSV generation for merchant review/import.
- `scripts/lib/catalog-schema.mjs` — catalogue validation and normalized field contracts.
- `operations/shopify-setup.md` — exact metafield, metaobject, Markets, payment, shipping, tax, notification, and launch configuration.
- `operations/content-verification.csv` — row-by-row sign-off for imagery, price, stock, artisan identity, provenance, and customs data.

### Tests and automation

- `tests/theme/cart.test.js` — cart state and failure recovery.
- `tests/theme/filters.test.js` — URL and filter behaviour.
- `tests/theme/wishlist.test.js` — storage and wishlist rendering.
- `tests/catalog/catalog.test.js` — sample catalogue completeness and safety labels.
- `tests/acceptance/storefront.spec.js` — connected-store keyboard, responsive, product, cart, and checkout-handoff smoke tests.
- `.github/workflows/theme-quality.yml` — Theme Check, unit tests, catalogue validation, and package verification.

---

### Task 1: Establish the buildless theme foundation

**Files:**
- Create: `.gitignore`
- Create: `.shopifyignore`
- Create: `.theme-check.yml`
- Create: `package.json`
- Create: `vitest.config.mjs`
- Create: `layout/theme.liquid`
- Create: `config/settings_schema.json`
- Create: `config/settings_data.json`
- Create: `locales/en.default.json`
- Create: `assets/base.css`
- Create: `assets/theme.js`

**Interfaces:**
- Consumes: the global brand and accessibility constraints above.
- Produces: CSS tokens such as `--color-muga`, `--color-lac`, `--space-*`, `--font-display`, and `--font-body`; a `window.LuitLoom` namespace; Shopify section-group hooks named `header-group` and `footer-group`.

- [ ] **Step 1: Write the foundation validation**

Create `tests/theme/foundation.test.js`:

```js
import { describe, expect, it } from 'vitest';
import fs from 'node:fs';

const read = (path) => fs.readFileSync(path, 'utf8');

describe('theme foundation', () => {
  it('loads Shopify content, canonical metadata, and the two global groups', () => {
    const layout = read('layout/theme.liquid');
    expect(layout).toContain('{{ content_for_header }}');
    expect(layout).toContain('{{ content_for_layout }}');
    expect(layout).toContain("{% sections 'header-group' %}");
    expect(layout).toContain("{% sections 'footer-group' %}");
    expect(layout).toContain("{% render 'meta-tags' %}");
  });

  it('defines the approved palette and accessibility primitives', () => {
    const css = read('assets/base.css');
    for (const token of ['--color-muga', '--color-ivory', '--color-lac', '--color-betel', '--color-charcoal']) {
      expect(css).toContain(token);
    }
    expect(css).toContain(':focus-visible');
    expect(css).toContain('@media (prefers-reduced-motion: reduce)');
  });
});
```

- [ ] **Step 2: Run the foundation test and verify failure**

Run: `npm install && npm test -- tests/theme/foundation.test.js`

Expected: FAIL because the theme foundation files do not exist.

- [ ] **Step 3: Add local tooling**

Create `package.json` with:

```json
{
  "name": "luit-and-loom-theme",
  "private": true,
  "type": "module",
  "scripts": {
    "test": "vitest run",
    "test:watch": "vitest",
    "check:theme": "shopify theme check --fail-level error",
    "check:catalog": "node scripts/validate-catalog.mjs",
    "package:theme": "shopify theme package",
    "verify": "npm run test && npm run check:catalog && npm run check:theme"
  },
  "devDependencies": {
    "@shopify/cli": "^3.0.0",
    "@shopify/theme": "^3.0.0",
    "jsdom": "^26.0.0",
    "vitest": "^3.0.0"
  }
}
```

Configure Vitest for Node by default and jsdom per-file where DOM behaviour is tested. Exclude `node_modules`, `.shopify`, and packaged ZIP files from Git and theme uploads. Use `extends: theme-check:recommended` in `.theme-check.yml`.

- [ ] **Step 4: Implement the minimum valid Shopify document and design tokens**

`layout/theme.liquid` must:

- Use `request.locale.iso_code` for the document language.
- Render `meta-tags`.
- output `content_for_header` inside `<head>`.
- Include a skip link targeting `#MainContent`.
- Render `header-group`, `<main id="MainContent">`, and `footer-group`.
- Load `base.css` synchronously and `theme.js` as a deferred module.
- Add `template-{{ template.name | handle }}` and brand colour classes to `<body>`.

Use these initial palette values in `assets/base.css`:

```css
:root {
  --color-muga: #bd8b2f;
  --color-ivory: #f7f1e6;
  --color-lac: #7e1f2b;
  --color-betel: #244d3b;
  --color-charcoal: #252320;
  --color-paper: #fffdf8;
  --color-border: #d8ccba;
  --font-display: "Iowan Old Style", "Baskerville", "Times New Roman", serif;
  --font-body: Inter, "Avenir Next", Avenir, "Segoe UI", sans-serif;
  --content-width: 90rem;
  --reading-width: 44rem;
  --radius-sm: .25rem;
  --radius-pill: 999px;
  --shadow-soft: 0 1rem 3rem rgb(37 35 32 / 8%);
}
```

Add a reset, fluid type scale, `.container`, `.prose`, `.button`, `.button--secondary`, `.visually-hidden`, `.skip-link`, `.focus-trap`, and reduced-motion override. Keep body text at a minimum of 16px and interactive controls at least 44px tall.

- [ ] **Step 5: Run foundation checks**

Run: `npm test -- tests/theme/foundation.test.js && npm run check:theme`

Expected: both commands PASS with no Theme Check errors.

- [ ] **Step 6: Commit the foundation**

Run:

```bash
git add .gitignore .shopifyignore .theme-check.yml package.json package-lock.json vitest.config.mjs layout config locales assets tests/theme/foundation.test.js
git commit -m "feat: establish Luit and Loom theme foundation"
```

---

### Task 2: Build global navigation, search access, and footer

**Files:**
- Create: `sections/header-group.json`
- Create: `sections/footer-group.json`
- Create: `sections/announcement-bar.liquid`
- Create: `sections/header.liquid`
- Create: `sections/footer.liquid`
- Create: `snippets/icon.liquid`
- Modify: `assets/base.css`
- Modify: `assets/theme.js`
- Modify: `locales/en.default.json`
- Test: `tests/theme/navigation.test.js`

**Interfaces:**
- Consumes: `window.LuitLoom`, shared buttons, containers, focus styles, Shopify `linklists`, `localization`, `routes`, `cart`, and `customer`.
- Produces: `<site-header>`, `<menu-drawer>`, `<search-drawer>`, and `[data-market-selector]`; dispatches `luit:drawer-opened` and `luit:drawer-closed`.

- [ ] **Step 1: Write the disclosure and focus tests**

Create a jsdom test that imports `assets/theme.js`, mounts a button with `aria-controls="MenuDrawer"`, and asserts:

```js
expect(trigger.getAttribute('aria-expanded')).toBe('false');
trigger.click();
expect(trigger.getAttribute('aria-expanded')).toBe('true');
expect(drawer.hidden).toBe(false);
document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
expect(trigger.getAttribute('aria-expanded')).toBe('false');
expect(document.activeElement).toBe(trigger);
```

Also assert that opening a second drawer closes the first and that a missing target does not throw.

- [ ] **Step 2: Run the navigation test and verify failure**

Run: `npm test -- tests/theme/navigation.test.js`

Expected: FAIL because drawer behaviour and global sections do not exist.

- [ ] **Step 3: Implement the section groups and accessible header**

The header group contains `announcement-bar` followed by `header`; the footer group contains `footer`.

The header must provide:

- Logo or text fallback “Luit & Loom”.
- Primary menu setting with the approved default navigation entered during store setup.
- Mobile menu drawer with a labelled close button.
- Search drawer linking to `routes.search_url` and using `q` as the field name.
- Account link using `routes.account_url` when customer accounts are enabled.
- Wishlist link to `/pages/wishlist`.
- Cart link with an aria-live item count.
- Shopify localization form using `localization.available_countries`.

All icon-only controls render an accessible label. `snippets/icon.liquid` accepts `name` and `label`; decorative instances output `aria-hidden="true"`.

- [ ] **Step 4: Implement disclosure behaviour**

Register one delegated click handler for `[aria-controls][data-drawer-trigger]`. On open:

- Set `aria-expanded="true"`.
- Remove `hidden` from the target.
- Add `overflow: hidden` to the document root.
- Focus the first focusable control in the drawer.

On Escape, backdrop click, or explicit close:

- Set `aria-expanded="false"`.
- Restore `hidden`.
- Remove scroll lock.
- Return focus to the trigger.

Trap Tab and Shift+Tab within an open modal drawer. Do not trap focus for non-modal desktop disclosures.

- [ ] **Step 5: Implement footer and responsive presentation**

The footer exposes menu settings for Shop, Learn, and Help; contact email; newsletter form; social links; copyright; and the tagline. Use a subtle woven-rule CSS pattern composed from borders and gradients, not an authored SVG illustration.

At widths below 750px, use an off-canvas menu and stacked footer accordions. At and above 990px, show inline primary navigation and multi-column footer content.

- [ ] **Step 6: Verify and commit**

Run: `npm test -- tests/theme/navigation.test.js && npm run check:theme`

Expected: PASS.

Run:

```bash
git add sections snippets/icon.liquid assets/base.css assets/theme.js locales/en.default.json tests/theme/navigation.test.js
git commit -m "feat: add accessible global storefront navigation"
```

---

### Task 3: Create the editorial homepage system

**Files:**
- Create: `templates/index.json`
- Create: `sections/hero-editorial.liquid`
- Create: `sections/featured-collection.liquid`
- Create: `sections/silk-story.liquid`
- Create: `sections/silk-collection-cards.liquid`
- Create: `sections/artisan-feature.liquid`
- Create: `sections/craft-assurances.liquid`
- Create: `sections/occasion-edit.liquid`
- Create: `sections/editorial-newsletter.liquid`
- Modify: `assets/base.css`
- Test: `tests/theme/homepage.test.js`

**Interfaces:**
- Consumes: Shopify section settings, collections, images, URLs, metaobject references, product-card snippet, and shared layout tokens.
- Produces: merchant-reorderable sections with presets; the default sequence specified in the approved design.

- [ ] **Step 1: Write structural tests**

Read each section as text and assert that it contains:

- A `{% schema %}` block.
- A `"presets"` entry.
- Image rendering through `image_url` and `image_tag` where image settings exist.
- No hard-coded store domain.

Assert that `templates/index.json` orders the section types exactly as:

```json
[
  "hero-editorial",
  "featured-collection",
  "silk-story",
  "silk-collection-cards",
  "artisan-feature",
  "craft-assurances",
  "occasion-edit",
  "editorial-newsletter"
]
```

- [ ] **Step 2: Run the homepage tests and verify failure**

Run: `npm test -- tests/theme/homepage.test.js`

Expected: FAIL because homepage sections are absent.

- [ ] **Step 3: Implement the hero and collection-led sections**

The hero schema includes desktop image, mobile image, eyebrow, heading, body, primary label/link, secondary label/link, text position, overlay strength, and colour scheme. Default copy:

- Eyebrow: `Assam, woven slowly`
- Heading: `Woven by Assam. Worn with meaning.`
- Body: `Handwoven Muga, Pat and Eri silk sarees, traced to their makers and made to endure.`
- Primary label: `Shop the collection`
- Secondary label: `Meet the artisans`

Do not output empty anchors. The mobile image uses a `<picture>` source below 750px. The heading remains real text rather than text embedded in imagery.

`featured-collection` accepts a collection, title, introduction, product limit from 2–8, and “View all” label. Render the shared `product-card` snippet.

`silk-collection-cards` supports three to six blocks; default card headings are Muga Silk, Pat Silk, and Eri Silk. Every card accepts collection, image override, short description, and link label.

- [ ] **Step 4: Implement story and trust sections**

`silk-story` provides an editorial image, heading, rich text, link, and a compact three-fact list.

`artisan-feature` accepts an artisan metaobject reference and manual fallbacks for name, image, region, quotation, and link. If no real artisan is selected, render only neutral sample copy in theme-editor design mode; render nothing on the live storefront.

`craft-assurances` supports icon, heading, and body blocks. Default headings are `Traceable craft`, `Considered delivery`, `Thoughtful returns`, and `Care for a lifetime`.

`occasion-edit` supports image-led blocks for Wedding, Celebration, Heirloom Gifting, and Quiet Evenings.

`editorial-newsletter` uses Shopify’s customer form with contact tag `newsletter` and announces success or field errors without moving focus unexpectedly.

- [ ] **Step 5: Add editorial layout and responsive rules**

Use asymmetric but grid-aligned editorial layouts, ample ivory space, Muga accents for rules and microcopy, lac only for high-emphasis actions, and betel for trust areas. Disable parallax and autoplay. Use only opacity and transform transitions that are removed under reduced motion.

- [ ] **Step 6: Verify and commit**

Run: `npm test -- tests/theme/homepage.test.js && npm run check:theme`

Expected: PASS.

Run:

```bash
git add templates/index.json sections assets/base.css tests/theme/homepage.test.js
git commit -m "feat: build the Luit and Loom editorial homepage"
```

---

### Task 4: Implement product cards, collection filters, and sorting

**Files:**
- Create: `snippets/price.liquid`
- Create: `snippets/product-card.liquid`
- Create: `snippets/pagination.liquid`
- Create: `sections/main-collection.liquid`
- Create: `templates/collection.json`
- Create: `assets/filters.js`
- Modify: `assets/base.css`
- Modify: `locales/en.default.json`
- Test: `tests/theme/filters.test.js`
- Test: `tests/theme/product-card.test.js`

**Interfaces:**
- Consumes: Shopify `collection`, `collection.filters`, `collection.sort_options`, `product`, product metafields `custom.silk_type` and `custom.artisan`, and `routes`.
- Produces: `serializeFilterForm(form): URLSearchParams`, `refreshCollection(url): Promise<void>`, and a consistent `[data-product-card]` contract reused across home, collection, recommendations, and wishlist.

- [ ] **Step 1: Write filter serialization tests**

Cover:

```js
expect(serializeFilterForm(form).toString()).toBe(
  'filter.p.m.custom.silk_type=Muga&filter.v.availability=1&sort_by=price-ascending'
);
```

Also verify:

- unchecked checkboxes are omitted;
- clearing filters preserves `sort_by`;
- price min/max values survive;
- `refreshCollection` replaces only `[data-collection-results]`;
- a failed fetch reveals `[data-filter-error]` and leaves current results intact.

- [ ] **Step 2: Run tests and verify failure**

Run: `npm test -- tests/theme/filters.test.js tests/theme/product-card.test.js`

Expected: FAIL because the modules and snippets do not exist.

- [ ] **Step 3: Implement price and product-card snippets**

`price.liquid` accepts `product`, displays `price_varies`, compare-at price only when greater than price, and a screen-reader sale label.

`product-card.liquid` accepts `product`, `show_artisan`, and `show_secondary_image`. It renders:

- Primary image with width candidates 320, 480, 640, and 800.
- Secondary image only when present and hover is supported.
- Product title and canonical URL.
- `custom.silk_type`.
- Artisan display name from `custom.artisan.value.name`.
- Price.
- `Low stock` when tracked quantity is between 1 and the configurable threshold.
- `Sold out` when unavailable.
- Wishlist toggle with `data-product-handle`.

Cards must remain complete and navigable without JavaScript.

- [ ] **Step 4: Implement native Shopify filters**

Use `collection.filters`; do not invent filter values in theme code. Render list, boolean, and price-range filters. Use native query parameter names from each `filter.param_name` and `value.param_name`.

On mobile, filters open in a modal drawer. On desktop, they appear in a labelled sidebar. The result count uses an aria-live region. Sorting submits through the same form.

Use section rendering by requesting the current collection URL with `section_id={{ section.id }}`. Update browser history only after a successful response.

- [ ] **Step 5: Add empty, loading, and recovery states**

While refreshing, set `aria-busy="true"` on results but keep existing cards visible. On zero products, show `No sarees match these filters` with a clear-all link. On network failure, show `We couldn’t update the collection. Your current results are still here.` and a retry button.

- [ ] **Step 6: Verify and commit**

Run: `npm test -- tests/theme/filters.test.js tests/theme/product-card.test.js && npm run check:theme`

Expected: PASS.

Run:

```bash
git add snippets sections/main-collection.liquid templates/collection.json assets/filters.js assets/base.css locales/en.default.json tests/theme
git commit -m "feat: add product discovery and collection filtering"
```

---

### Task 5: Build the provenance-rich product page

**Files:**
- Create: `snippets/product-provenance.liquid`
- Create: `sections/main-product.liquid`
- Create: `sections/product-recommendations.liquid`
- Create: `templates/product.json`
- Modify: `assets/cart.js`
- Modify: `assets/base.css`
- Modify: `locales/en.default.json`
- Test: `tests/theme/product.test.js`

**Interfaces:**
- Consumes: product variants, media, `product.metafields.custom.*`, referenced artisan metaobject, `product_form_id`, Shopify product form, cart endpoint, and product recommendations endpoint.
- Produces: `[data-product-form]`, `[data-variant-id]`, `[data-product-status]`, and the provenance definition list used by product and artisan experiences.

- [ ] **Step 1: Write product contract tests**

Assert that `main-product.liquid` contains:

- `{% form 'product'`
- a variant ID control named `id`
- `name="quantity"`
- a submit control
- `product.selected_or_first_available_variant`
- dispatch and availability live regions
- a render of `product-provenance`

Assert that the provenance snippet references the exact metafield keys listed in `operations/shopify-setup.md`.

- [ ] **Step 2: Run the product test and verify failure**

Run: `npm test -- tests/theme/product.test.js`

Expected: FAIL because the product components do not exist.

- [ ] **Step 3: Implement media, product form, and availability**

The gallery renders all image and video media with thumbnails or an accessible compact selector. Do not autoplay video. The product form includes:

- Variant options where variants exist.
- Quantity only when inventory policy allows more than one.
- Hidden properties for `Fall and pico` and `Gift message` only when those settings are enabled.
- Price, inventory state, dispatch window, and add-to-cart button.
- Dynamic checkout buttons only when enabled by the merchant.

Unique products display `Only one woven` rather than an artificial urgency countdown. Sold-out products replace purchase controls with a notify/contact path and related products.

- [ ] **Step 4: Implement provenance**

Render available values in a semantic definition list:

- Silk type: `custom.silk_type`
- Weave: `custom.weave_technique`
- Dimensions: `custom.dimensions`
- Weight: `custom.saree_weight`
- Blouse piece: `custom.blouse_piece`
- Motif: `custom.motif_name` and `custom.motif_meaning`
- Region: `custom.weaving_region`
- Making time: `custom.production_time`
- Authenticity ID: `custom.authenticity_identifier`
- Care: `custom.care_instructions`
- Dispatch: `custom.dispatch_window`
- Country of origin: `custom.country_of_origin`

If `custom.artisan` references an artisan metaobject, render its verified name, portrait, region, short biography, and profile URL. Omit missing facts; never substitute an invented fact on the live storefront.

- [ ] **Step 5: Add related products**

Request Shopify product recommendations with `intent=related`. Render a maximum of four results through `product-card`. If the request has no results, omit the section entirely.

- [ ] **Step 6: Verify and commit**

Run: `npm test -- tests/theme/product.test.js && npm run check:theme`

Expected: PASS.

Run:

```bash
git add snippets/product-provenance.liquid sections/main-product.liquid sections/product-recommendations.liquid templates/product.json assets/cart.js assets/base.css locales/en.default.json tests/theme/product.test.js
git commit -m "feat: add provenance-rich saree product pages"
```

---

### Task 6: Implement resilient cart and checkout handoff

**Files:**
- Create: `sections/main-cart.liquid`
- Create: `templates/cart.json`
- Modify: `assets/cart.js`
- Modify: `assets/base.css`
- Modify: `locales/en.default.json`
- Test: `tests/theme/cart.test.js`

**Interfaces:**
- Consumes: Shopify `/cart/add.js`, `/cart/change.js`, `/cart.js`, section rendering response, line keys, cart note, `routes.cart_url`, and `routes.cart_add_url`.
- Produces: `addItem(form): Promise<CartResult>`, `changeLine(key, quantity): Promise<CartResult>`, `announceCart(message)`, and `luit:cart-updated`.

- [ ] **Step 1: Write cart behaviour tests**

Mock fetch and verify:

- Add-to-cart sends `FormData` to the localized cart-add route.
- A successful add dispatches `luit:cart-updated`.
- Quantity zero removes a line.
- A `422` stock response shows the Shopify description and preserves the form.
- Network failure shows `We couldn’t update your bag. Please try again.`
- Repeated clicks are ignored while a request is active.
- Focus moves to the cart status message only for an error, not for routine success.

- [ ] **Step 2: Run the cart test and verify failure**

Run: `npm test -- tests/theme/cart.test.js`

Expected: FAIL because cart functions are absent.

- [ ] **Step 3: Implement progressive cart enhancement**

Without JavaScript, product forms post normally to Shopify. With JavaScript:

- Intercept valid product forms.
- Disable the submit control and set `aria-busy`.
- Add the selected item.
- Update header cart count.
- Announce success.
- Offer `View bag` and `Checkout`.
- Restore the form on failure.

Use the server response as the source of truth; do not calculate inventory or totals in the browser.

- [ ] **Step 4: Implement the cart page**

Render:

- Line image, title, variant, properties, unit price, quantity, line total, and remove control.
- Cart note using Shopify’s `note` field.
- Subtotal.
- Shipping and tax caveat.
- International duties statement controlled by a theme setting.
- Checkout button posting to Shopify.
- Empty cart with links to Muga, Pat, Eri, and New Arrivals.

Update lines through `/cart/change.js`. If Shopify adjusts a requested quantity because stock changed, announce the actual quantity and show alternatives.

- [ ] **Step 5: Verify and commit**

Run: `npm test -- tests/theme/cart.test.js && npm run check:theme`

Expected: PASS.

Run:

```bash
git add sections/main-cart.liquid templates/cart.json assets/cart.js assets/base.css locales/en.default.json tests/theme/cart.test.js
git commit -m "feat: add resilient cart and Shopify checkout handoff"
```

---

### Task 7: Add search, wishlist, editorial, artisan, and recovery pages

**Files:**
- Create: `sections/main-search.liquid`
- Create: `templates/search.json`
- Create: `assets/wishlist.js`
- Create: `sections/main-wishlist.liquid`
- Create: `templates/page.wishlist.json`
- Create: `sections/main-page.liquid`
- Create: `templates/page.json`
- Create: `sections/main-blog.liquid`
- Create: `templates/blog.json`
- Create: `sections/main-article.liquid`
- Create: `templates/article.json`
- Create: `sections/main-artisan.liquid`
- Create: `templates/metaobject/artisan.json`
- Create: `sections/main-404.liquid`
- Create: `templates/404.json`
- Create: `sections/main-password.liquid`
- Create: `templates/password.json`
- Modify: `assets/base.css`
- Modify: `locales/en.default.json`
- Test: `tests/theme/wishlist.test.js`

**Interfaces:**
- Consumes: Shopify search, blogs, articles, pages, artisan metaobjects, product-card, and device `localStorage`.
- Produces: `WishlistStore` with `list(): string[]`, `has(handle): boolean`, `toggle(handle): string[]`, and `clear(): void`; dispatches `luit:wishlist-updated`.

- [ ] **Step 1: Write wishlist tests**

Test:

```js
const store = new WishlistStore(storage);
expect(store.list()).toEqual([]);
expect(store.toggle('muga-river-gold')).toEqual(['muga-river-gold']);
expect(store.has('muga-river-gold')).toBe(true);
expect(store.toggle('muga-river-gold')).toEqual([]);
```

Also cover corrupt JSON, unavailable storage, duplicate handles, and a maximum of 100 handles.

- [ ] **Step 2: Run the wishlist test and verify failure**

Run: `npm test -- tests/theme/wishlist.test.js`

Expected: FAIL because `WishlistStore` does not exist.

- [ ] **Step 3: Implement wishlist and search**

Wishlist buttons persist product handles only; no customer personal data is stored. If storage is unavailable, the button remains operable for the current page and announces that saving is unavailable.

The wishlist page fetches product cards through Shopify’s predictive search or section-rendering endpoint in batches. Unavailable products remain identifiable and link to recommendations.

Search results separate products, articles, and pages. Product results use `product-card`. The no-results state offers spelling guidance and collection links.

- [ ] **Step 4: Implement editorial and artisan templates**

General pages use a constrained reading width with optional lead image. Blog and article templates expose title, date, author setting, featured image, content, and related article navigation.

The artisan metaobject page renders only verified fields:

- `name`
- `portrait`
- `region`
- `village`
- `biography`
- `craft_speciality`
- `years_weaving`
- `quote`
- `products`

The 404 page offers search and primary collection links. The password page uses the brand name, tagline, launch message, email signup, and merchant access form.

- [ ] **Step 5: Verify and commit**

Run: `npm test -- tests/theme/wishlist.test.js && npm run check:theme`

Expected: PASS.

Run:

```bash
git add sections templates assets/wishlist.js assets/base.css locales/en.default.json tests/theme/wishlist.test.js
git commit -m "feat: add search wishlist stories and artisan pages"
```

---

### Task 8: Add SEO, structured data, consent hooks, and performance controls

**Files:**
- Create: `snippets/meta-tags.liquid`
- Modify: `layout/theme.liquid`
- Modify: `config/settings_schema.json`
- Modify: `assets/base.css`
- Modify: `assets/theme.js`
- Test: `tests/theme/metadata.test.js`

**Interfaces:**
- Consumes: Shopify `page_title`, `page_description`, `canonical_url`, `request`, `shop`, `product`, `article`, `settings`, and customer privacy APIs.
- Produces: canonical tags, Open Graph and X metadata, JSON-LD for Organization/Product/Article/BreadcrumbList, and `data-analytics-event` hooks.

- [ ] **Step 1: Write metadata tests**

Assert:

- Exactly one canonical tag is rendered by the snippet.
- JSON-LD is serialized through Liquid’s `json` filter.
- Product availability uses the selected variant.
- No price or URL is concatenated into JSON manually.
- Social image output is conditional on a valid image.
- Theme JS does not load nonessential analytics before consent.

- [ ] **Step 2: Run metadata tests and verify failure**

Run: `npm test -- tests/theme/metadata.test.js`

Expected: FAIL because metadata support is absent.

- [ ] **Step 3: Implement metadata and structured data**

Generate:

- Organization data on the homepage.
- Product data on product pages with title, image, description, SKU when present, brand, offers, currency, price, URL, and availability.
- Article data on article pages.
- BreadcrumbList on collection, product, blog, and article pages.

Use Shopify’s canonical URL. Respect merchant-entered SEO titles and descriptions. Product social copy must use actual product data.

- [ ] **Step 4: Add consent-aware event hooks**

Expose semantic events for:

- `view_item`
- `search`
- `filter`
- `add_to_wishlist`
- `add_to_cart`
- `begin_checkout`

Theme code dispatches browser `CustomEvent` objects only. The merchant’s approved Shopify pixels subscribe through Shopify’s customer privacy system; no hard-coded third-party tracker is added to the theme.

- [ ] **Step 5: Enforce performance rules**

Use one critical CSS file, defer module scripts, reserve image aspect ratios, lazy-load below-fold images, avoid autoplay, and preconnect only to Shopify-owned origins already needed by the page. Do not preload more than the hero image and the primary display font if a merchant-hosted font is later supplied.

- [ ] **Step 6: Verify and commit**

Run: `npm test -- tests/theme/metadata.test.js && npm run check:theme`

Expected: PASS.

Run:

```bash
git add snippets/meta-tags.liquid layout/theme.liquid config/settings_schema.json assets tests/theme/metadata.test.js
git commit -m "feat: add search metadata privacy and performance controls"
```

---

### Task 9: Create and validate the River, Reed & Gold sample catalogue

**Files:**
- Create: `data/river-reed-gold.json`
- Create: `scripts/lib/catalog-schema.mjs`
- Create: `scripts/validate-catalog.mjs`
- Create: `scripts/generate-products-csv.mjs`
- Create: `tests/catalog/catalog.test.js`
- Create: `operations/content-verification.csv`
- Modify: `package.json`

**Interfaces:**
- Consumes: the 12-product collection mix and launch-safety rules from the specification.
- Produces: `validateCatalog(data): ValidationResult`, `normalizeProduct(product): ProductRow`, and `dist/catalog/river-reed-gold-products.csv`.

- [ ] **Step 1: Write catalogue safety tests**

Tests must assert:

- Exactly 12 products.
- Four Muga, four Pat, two Eri, and two silk-blend products.
- Every product has a unique handle, title, type, story, motif, dimensions, care, INR price, sample stock state, and `sample: true`.
- Every artisan has `sample: true`.
- Every product image has `placeholder: true`.
- No record can set `publish: true` while any sample or placeholder flag remains.
- International products require origin, weight, and HS code before `publish: true`.

- [ ] **Step 2: Run catalogue tests and verify failure**

Run: `npm test -- tests/catalog/catalog.test.js`

Expected: FAIL because catalogue files do not exist.

- [ ] **Step 3: Define the inaugural sample catalogue**

Use these twelve working product names and categories:

1. Luit Dawn — Muga
2. Sualkuchi Gold — Muga
3. Xorai Light — Muga
4. Monsoon Reed — Muga
5. Kopou Ivory — Pat
6. Jaapi Vermilion — Pat
7. Dikhow Moon — Pat
8. Bihu Ember — Pat
9. Eri Mist — Eri
10. Forest Quiet — Eri
11. River Reed — silk blend
12. Lac Horizon — silk blend

All associated artisan names, portraits, villages, prices, inventory, and provenance remain explicitly marked as samples until merchant verification. Copy can describe the design inspiration, but it must not claim a real individual made a sample product.

- [ ] **Step 4: Implement validation and CSV generation**

`validateCatalog` returns:

```js
{
  valid: boolean,
  errors: Array<{ path: string, code: string, message: string }>
}
```

The generator refuses to create import output when validation fails. It outputs UTF-8 CSV with Shopify-compatible product columns, metafields represented as documented columns, and `Status` set to `draft` for all sample records. Escape commas, quotation marks, and line breaks according to RFC 4180.

`operations/content-verification.csv` includes one row per product and columns:

```text
handle,real_photos_verified,price_verified,stock_verified,artisan_consent_verified,provenance_verified,care_verified,origin_verified,hs_code_verified,shipping_weight_verified,approved_by,approved_at
```

- [ ] **Step 5: Verify and commit**

Run: `npm test -- tests/catalog/catalog.test.js && npm run check:catalog`

Expected: PASS and a clear message that all 12 records remain draft samples.

Run:

```bash
git add data scripts tests/catalog operations/content-verification.csv package.json package-lock.json
git commit -m "feat: add validated inaugural sample catalogue"
```

---

### Task 10: Document and configure Shopify commerce operations

**Files:**
- Create: `operations/shopify-setup.md`
- Create: `operations/launch-checklist.md`
- Create: `operations/notification-copy.md`
- Create: `operations/policies-input-sheet.md`
- Test: `tests/operations/operations.test.js`

**Interfaces:**
- Consumes: merchant’s verified Shopify account, eligible payment providers, shipping partners, tax advice, policy decisions, and actual product records.
- Produces: exact store configuration, verified metafield/metaobject definitions, notification copy, and a binary launch checklist.

- [ ] **Step 1: Write operations completeness tests**

Assert that `operations/shopify-setup.md` contains exact entries for:

- Store currency and primary market.
- India, North America, United Kingdom, Europe, and Rest of World Markets.
- Every product metafield key used by Liquid.
- Every artisan metaobject key used by Liquid.
- Payments, third-party transaction fees, COD controls, PayPal eligibility, refunds, and test mode.
- Shipping profiles, delivery estimates, return addresses, HS codes, origin, and duties.
- Inventory tracking, one-of-a-kind quantity, overselling disabled, and fulfilment.
- Customer accounts, domain, email authentication, privacy, pixels, and notifications.

Assert that the launch checklist has no ambiguous state: every item begins with `- [ ]` and contains an evidence field.

- [ ] **Step 2: Run operations tests and verify failure**

Run: `npm test -- tests/operations/operations.test.js`

Expected: FAIL because operations documents do not exist.

- [ ] **Step 3: Define structured Shopify data**

Document product metafields under namespace `custom` using the exact keys from Task 5. Define the artisan metaobject with the exact fields from Task 7 and enable storefront access and renderable pages.

Set validation types:

- Single-line text for classification and IDs.
- Rich text for motif meaning, biography, and care.
- Dimension and weight values where Shopify types support them.
- Metaobject reference for artisan.
- URL/file reference for supporting media.

- [ ] **Step 4: Define payment and market setup**

The merchant must choose an eligible provider shown in the live India-based Shopify admin. Record:

- Gateway processing fee.
- Shopify third-party transaction fee.
- Domestic methods.
- International card eligibility.
- Settlement currency.
- Refund path.
- Chargeback path.
- Test-mode evidence.

Set INR as store currency before the first real sale. Configure the five approved Markets and state explicitly that local-currency checkout is not promised unless the activated provider and Shopify configuration support it. Add destination-specific duties language and DDP/DDU terms.

- [ ] **Step 5: Define shipping, inventory, tax, policy, and communications**

Document domestic and international shipping zones, parcel weights, insurance, signature requirements for high-value orders, tracking, return address, delivery estimates, and free-shipping thresholds.

Disable overselling. Unique sarees use quantity one. Made-to-order products use an explicit production window and distinct inventory policy.

Prepare brand-consistent notification copy for order confirmation, shipping, delivery, cancellation, refund, return received, and payment failure. Do not claim a dispatch time not present in the product or shipping profile.

- [ ] **Step 6: Verify and commit**

Run: `npm test -- tests/operations/operations.test.js`

Expected: PASS.

Run:

```bash
git add operations tests/operations
git commit -m "docs: define Shopify operations and launch controls"
```

---

### Task 11: Add continuous quality checks and connected-store acceptance tests

**Files:**
- Create: `.github/workflows/theme-quality.yml`
- Create: `playwright.config.mjs`
- Create: `tests/acceptance/storefront.spec.js`
- Modify: `package.json`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: local unit tests, Theme Check, catalogue validation, `SHOPIFY_STORE_URL`, and an unpublished development theme preview.
- Produces: repeatable pull-request checks and a browser acceptance report.

- [ ] **Step 1: Write acceptance tests**

The Playwright suite must cover:

```js
test('keyboard shopper can reach a product and Shopify checkout', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('link', { name: /skip to content/i }).focus();
  await page.keyboard.press('Enter');
  await expect(page.locator('#MainContent')).toBeFocused();
  await page.getByRole('link', { name: /shop the collection/i }).click();
  await page.getByRole('link', { name: /luit dawn/i }).click();
  await page.getByRole('button', { name: /add to bag/i }).click();
  await page.getByRole('link', { name: /view bag/i }).click();
  await expect(page.getByText(/luit dawn/i)).toBeVisible();
  await page.getByRole('button', { name: /checkout/i }).click();
  await expect(page).toHaveURL(/\/checkouts?\//);
});
```

Add tests for mobile navigation, filter/no-results recovery, sold-out state, reduced motion, missing optional metafields, and international duties messaging. Use actual development-store handles supplied by environment variables rather than hard-coded production data.

- [ ] **Step 2: Configure CI**

On pushes and pull requests:

1. Install the pinned Node LTS declared in `.nvmrc`.
2. Run `npm ci`.
3. Run unit tests.
4. Run catalogue validation.
5. Run Theme Check.
6. Run `shopify theme package`.
7. Upload the package as a workflow artifact.

Do not run connected-store Playwright tests without the required encrypted variables.

- [ ] **Step 3: Run local verification**

Run: `npm run verify && npm run package:theme`

Expected: all unit tests and Theme Check PASS; a Shopify theme ZIP is created without `tests`, `docs`, `operations`, `data`, `.github`, or local tooling.

- [ ] **Step 4: Run connected acceptance tests**

After the merchant supplies development-store access:

Run:

```bash
shopify theme dev --store "$SHOPIFY_STORE" --theme-editor-sync
npx playwright test
```

Expected: all acceptance tests PASS against the unpublished development theme. Checkout navigation may stop at Shopify’s secure checkout; no real order is submitted in this suite.

- [ ] **Step 5: Commit quality automation**

Run:

```bash
git add .github playwright.config.mjs tests/acceptance package.json package-lock.json .gitignore .nvmrc
git commit -m "test: add theme quality and storefront acceptance checks"
```

---

### Task 12: Verify launch gates and publish through Shopify

**Files:**
- Modify: `operations/content-verification.csv`
- Modify: `operations/launch-checklist.md`
- Create: `operations/launch-evidence.md`

**Interfaces:**
- Consumes: approved real catalogue, verified merchant settings, successful test orders, successful theme package, and connected-store acceptance report.
- Produces: an unpublished Shopify theme approved for publication, then a published live theme only after explicit merchant approval.

- [ ] **Step 1: Replace and verify sample commerce data**

For every product, record evidence for:

- Real photography matching the exact sale item.
- Final price.
- Actual stock.
- Artisan identity and consent.
- Provenance claims.
- Care instructions.
- Country of origin.
- HS code.
- Shipping weight.

No record may be published while `sample`, `placeholder`, or an unsigned verification field remains.

- [ ] **Step 2: Complete merchant launch gates**

Attach evidence in `operations/launch-evidence.md` for:

- Shopify merchant verification.
- Payment-gateway approval and payout verification.
- Domain and sender-email authentication.
- Taxes and international duties configuration.
- Domestic and international shipping tests.
- Policy approval.
- Successful payment, failed payment, cancellation, refund, fulfilment, and tracking tests.
- Accessibility and responsive acceptance results.

- [ ] **Step 3: Push an unpublished theme**

Run:

```bash
shopify theme push --unpublished --store "$SHOPIFY_STORE"
```

Expected: Shopify returns an unpublished theme ID and preview URL. Record the preview URL in the launch evidence without storing credentials.

- [ ] **Step 4: Perform final merchant review**

Review the unpublished theme with the merchant on mobile and desktop. Verify primary navigation, all collection filters, each real product, cart, checkout handoff, policies, market messaging, emails, and tracking.

Any failed gate keeps the theme unpublished.

- [ ] **Step 5: Publish only with explicit approval**

After the merchant approves the exact unpublished theme:

```bash
shopify theme publish --theme "$SHOPIFY_THEME_ID" --store "$SHOPIFY_STORE"
```

Expected: Shopify confirms the theme is live.

- [ ] **Step 6: Commit the launch record**

Run:

```bash
git add operations/content-verification.csv operations/launch-checklist.md operations/launch-evidence.md
git commit -m "chore: record Luit and Loom launch verification"
```

---

## Implementation Sequence and Review Gates

1. Tasks 1–2 establish the theme shell and accessibility contract.
2. Tasks 3–5 produce the brand, discovery, and product experience.
3. Tasks 6–8 complete customer journeys, content, privacy, SEO, and resilience.
4. Tasks 9–10 prepare catalogue and merchant operations without enabling unverified sales.
5. Task 11 proves code and connected-store behaviour.
6. Task 12 requires merchant evidence and explicit approval before publication.

Each task ends in a focused commit. Do not combine tasks into one unreviewable change. Do not publish a theme, import live products, activate payments, or enable real orders as a side effect of implementation.
