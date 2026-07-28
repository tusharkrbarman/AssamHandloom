import {
  formatMoney,
  getProduct,
  listCollections,
  listProducts,
  type Page,
  parseProductListQuery,
  type ProductCard,
  type ProductDetail,
  type ProductListQuery,
} from "./catalogue";
import { escapeHtml, html, HttpError, json } from "./http";

const EDITORIAL_PAGES: Record<string, { title: string; body: string }> = {
  "/artisans": {
    title: "Artisans",
    body: "Verified maker profiles will be introduced only with consent and confirmed public details.",
  },
  "/our-story": {
    title: "Our story",
    body: "Luit & Loom presents Assamese handloom with care. Orders and live checkout are not available in Phase 1.",
  },
  "/journal": {
    title: "Journal",
    body: "Understanding Assam silk, identifying authentic Muga, and caring for handwoven sarees are planned editorial notes.",
  },
  "/pages/silk-guide": {
    title: "Silk guide",
    body: "Muga, Pat, and Eri have distinct qualities. This introduction does not replace verified product facts.",
  },
  "/pages/care": {
    title: "Care guide",
    body: "Care instructions must be verified for each real textile before purchase.",
  },
  "/pages/shipping": {
    title: "Shipping",
    body: "Shipping terms will be published before checkout opens. Phase 1 does not accept orders.",
  },
  "/pages/returns": {
    title: "Returns",
    body: "Returns information will be confirmed before checkout opens.",
  },
  "/pages/contact": {
    title: "Contact",
    body: "Contact channels will be announced with the live commerce release.",
  },
  "/pages/faq": {
    title: "Frequently asked questions",
    body: "Phase 1 manages the catalogue and inventory. Checkout and customer orders are not available yet.",
  },
};

function header(): string {
  return `<header class="site-header">
  <div class="container header-row">
    <a class="wordmark" href="/" aria-label="Luit and Loom home">Luit <span>&amp;</span> Loom</a>
    <nav class="primary-nav" aria-label="Primary navigation">
      <ul>
        <li><a href="/shop">Shop all</a></li>
        <li><a href="/shop?silk_type=Muga">Muga</a></li>
        <li><a href="/shop?silk_type=Pat">Pat</a></li>
        <li><a href="/shop?silk_type=Eri">Eri</a></li>
        <li><a href="/artisans">Artisans</a></li>
      </ul>
    </nav>
    <div class="header-utilities">
      <form class="site-search" role="search" action="/search" method="get">
        <label class="visually-hidden" for="site-search">Search Luit &amp; Loom</label>
        <svg class="site-search__icon" aria-hidden="true" viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"></circle><path d="m20 20-3.2-3.2"></path></svg>
        <input id="site-search" name="search" type="search" placeholder="Find your weave" autocomplete="off">
        <button class="visually-hidden" type="submit">Search</button>
      </form>
      <details class="mobile-disclosure">
        <summary class="disclosure-button">Browse</summary>
        <nav class="mobile-navigation" aria-label="Mobile navigation">
          <a href="/shop">Shop all weaves</a><a href="/collections">Collections</a><a href="/artisans">Artisans</a><a href="/our-story">Our story</a><a href="/journal">Journal</a><a href="/search">Search</a>
        </nav>
      </details>
    </div>
  </div>
</header>`;
}

function footer(): string {
  return `<footer class="site-footer">
  <div class="container footer-grid">
    <div class="footer-brand"><a class="wordmark" href="/">Luit <span>&amp;</span> Loom</a><p>Contemporary Assamese handloom, considered with care.</p></div>
    <nav aria-label="Discover"><h2>Discover</h2><ul><li><a href="/shop">Shop all</a></li><li><a href="/artisans">The artisans</a></li><li><a href="/our-story">Our story</a></li><li><a href="/journal">Journal</a></li></ul></nav>
    <nav aria-label="Footer navigation"><h2>Guidance</h2><ul><li><a href="/pages/silk-guide">Silk Guide</a></li><li><a href="/pages/care">Care Guide</a></li><li><a href="/pages/shipping">Shipping</a></li><li><a href="/pages/returns">Returns</a></li><li><a href="/pages/contact">Contact</a></li><li><a href="/pages/faq">FAQ</a></li></ul></nav>
    <div class="footer-status"><h2>Store status</h2><p class="footer-note">Phase 1 catalogue management. Checkout is not yet available.</p></div>
  </div>
</footer>`;
}

function shell(
  request: Request,
  title: string,
  content: string,
  status = 200,
): Response {
  const url = new URL(request.url);
  const canonical = `${url.origin}${url.pathname}`;
  return html(`<!doctype html>
<html lang="en-IN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>${escapeHtml(title)}</title>
  <meta name="description" content="Luit &amp; Loom presents contemporary Assamese handloom with care and clarity.">
  <link rel="canonical" href="${escapeHtml(canonical)}">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&amp;display=swap">
  <link rel="stylesheet" href="/css/site.css">
</head>
<body>
  <a class="skip-link" href="#main-content">Skip to main content</a>
  ${header()}
  <main id="main-content" tabindex="-1">${content}</main>
  ${footer()}
</body>
</html>`, status, status >= 400 ? { "cache-control": "no-store" } : undefined);
}

function image(product: ProductCard, priority = false): string {
  if (!product.mediaId) {
    return `<span class="textile-placeholder" role="img" aria-label="Textile-colour study for ${escapeHtml(product.title)}">Textile-colour study</span>`;
  }
  return `<img class="product-card__primary-image" src="/media/${escapeHtml(product.mediaId)}" alt="${escapeHtml(product.altText || `${product.title} in ${product.silkType} silk`)}" width="720" height="900"${priority ? "" : ' loading="lazy"'}>`;
}

function productCard(product: ProductCard): string {
  return `<article class="product-card">
  <a class="product-card__image" href="/products/${escapeHtml(product.slug)}" aria-label="View ${escapeHtml(product.title)}">${image(product)}</a>
  <div class="product-card__body">
    <p class="eyebrow">${escapeHtml(product.silkType)}</p>
    <h2><a href="/products/${escapeHtml(product.slug)}">${escapeHtml(product.title)}</a></h2>
    <div class="product-card__meta-row">
      <p class="price">${escapeHtml(formatMoney(product.priceMinor, product.currency))}</p>
      <p class="availability${product.available ? "" : " is-unavailable"}">${product.available ? "Available" : "Currently unavailable"}</p>
    </div>
  </div>
</article>`;
}

function pageCount(page: Page<ProductCard>): number {
  return Math.ceil(page.total / page.pageSize);
}

function pageHref(url: URL, page: number): string {
  const query = new URLSearchParams(url.searchParams);
  query.set("page", String(page));
  return `${url.pathname}?${query.toString()}`;
}

function productGrid(
  page: Page<ProductCard>,
  url: URL,
  includePagination = true,
  limit?: number,
): string {
  const products = limit === undefined ? page.items : page.items.slice(0, limit);
  const cards = products.length
    ? products.map(productCard).join("")
    : `<div class="empty-state"><p>No weaves matched your search.</p><a class="text-link" href="/shop">Browse all weaves</a></div>`;
  const pages = pageCount(page);
  const pagination =
    includePagination && pages > 1
      ? `<nav class="pagination" aria-label="Catalogue pages">
        ${page.page > 1 ? `<a href="${escapeHtml(pageHref(url, page.page - 1))}" rel="prev">Previous</a>` : ""}
        <span>Page ${page.page} of ${pages}</span>
        ${page.page < pages ? `<a href="${escapeHtml(pageHref(url, page.page + 1))}" rel="next">Next</a>` : ""}
      </nav>`
      : "";
  return `<section id="catalogue-results" aria-live="polite" aria-label="Catalogue results"><div id="product-grid" class="product-grid">${cards}</div>${pagination}</section>`;
}

function selected(value: string | null, expected: string): string {
  return value === expected ? " selected" : "";
}

function filters(url: URL, query: ProductListQuery): string {
  return `<form class="catalogue-filters" method="get" action="${escapeHtml(url.pathname)}" aria-label="Filter the catalogue">
  <div><label for="catalogue-search">Search</label><input id="catalogue-search" name="search" value="${escapeHtml(query.search)}"></div>
  <div><label for="silk-type">Weave (silk type)</label><select id="silk-type" name="silk_type"><option value="">All silks</option><option value="Muga"${selected(query.silkType, "Muga")}>Muga</option><option value="Pat"${selected(query.silkType, "Pat")}>Pat</option><option value="Eri"${selected(query.silkType, "Eri")}>Eri</option></select></div>
  <div><label for="catalogue-colour">Colour</label><select id="catalogue-colour" name="colour"><option value="">All colours</option><option value="Red"${selected(query.colour, "Red")}>Red</option><option value="Ivory"${selected(query.colour, "Ivory")}>Ivory</option><option value="Green"${selected(query.colour, "Green")}>Green</option></select></div>
  <div><label for="catalogue-occasion">Occasion</label><select id="catalogue-occasion" name="occasion"><option value="">All occasions</option><option value="Wedding"${selected(query.occasion, "Wedding")}>Wedding</option><option value="Everyday"${selected(query.occasion, "Everyday")}>Everyday</option></select></div>
  <div><label for="catalogue-sort">Price &amp; sort</label><select id="catalogue-sort" name="sort"><option value="featured"${selected(query.sort, "featured")}>Featured</option><option value="newest"${selected(query.sort, "newest")}>Newest</option><option value="price_asc"${selected(query.sort, "price_asc")}>Price: low to high</option><option value="price_desc"${selected(query.sort, "price_desc")}>Price: high to low</option></select></div>
  <div><input id="available-only" type="checkbox" name="available_only" value="true"${query.availableOnly ? " checked" : ""}><label for="available-only">Available now</label></div>
  <button type="submit">Apply filters</button>
</form>`;
}

function homeContent(page: Page<ProductCard>, url: URL): string {
  const hero = page.items[0];
  const heroVisual = hero
    ? `<a href="/products/${escapeHtml(hero.slug)}">${image(hero, true)}</a>`
    : `<span class="textile-placeholder" role="img" aria-label="Assamese silk textile-colour study">Textile-colour study</span>`;
  const heroCaption = hero
    ? `${escapeHtml(hero.title)} · ${escapeHtml(hero.silkType)} silk`
    : "Material-led pieces, considered with care";
  return `<section class="home-hero editorial-grid">
  <div class="home-hero__copy">
    <p class="eyebrow">Heritage series · Collector's edition</p>
    <h1>Woven by Assam.<br>Worn with meaning.</h1>
    <p class="hero-deck">Quietly expressive silk, traced to the people and practices that make it.</p>
    <div class="action-row"><a class="button" href="/shop?sort=newest">Shop new arrivals</a><a class="button button--secondary" href="/our-story">View our story</a></div>
  </div>
  <figure class="home-hero__visual">${heroVisual}<figcaption><span class="eyebrow">The Luit edit</span><span>${heroCaption}</span></figcaption></figure>
</section>
<section class="trust-strip" aria-label="Catalogue assurances">
  <p><svg class="trust-strip__icon" aria-hidden="true" viewBox="0 0 24 24"><path d="M12 3 20 6v6c0 5-3.4 8-8 9-4.6-1-8-4-8-9V6l8-3Z"></path><path d="m9 12 2 2 4-4"></path></svg><strong>Material named</strong><span>Muga, Pat, and Eri</span></p>
  <p><svg class="trust-strip__icon" aria-hidden="true" viewBox="0 0 24 24"><circle cx="12" cy="8" r="4"></circle><path d="M4.5 21a7.5 7.5 0 0 1 15 0"></path></svg><strong>Maker context</strong><span>Shared when verified</span></p>
  <p class="trust-strip__lower trust-strip__new-row"><svg class="trust-strip__icon" aria-hidden="true" viewBox="0 0 24 24"><path d="M12 22c4-3 7-7 7-12-5 0-9 3-9 8"></path><path d="M12 22C8 18 5 14 5 9c5 0 9 3 9 8"></path></svg><strong>Availability shown</strong><span>Clear catalogue status</span></p>
  <p class="trust-strip__lower"><svg class="trust-strip__icon" aria-hidden="true" viewBox="0 0 24 24"><path d="M4 7h16v13H4z"></path><path d="m4 7 4-4h8l4 4M9 11h6"></path></svg><strong>Care guidance</strong><span>Specific to each weave</span></p>
</section>
<section class="home-section featured-weaves">
  <div class="section-heading"><div><p class="eyebrow">Featured weaves</p><h2>Small editions, held in view</h2></div><a href="/shop">Browse full catalogue <span aria-hidden="true">→</span></a></div>
  ${productGrid(page, url, false, 4)}
</section>
<section class="home-section material-feature" aria-labelledby="collection-edit-title">
  <div class="material-feature__copy"><p class="eyebrow">Why Assam silk</p><h2 id="collection-edit-title">Three traditions, one spirit.</h2><p>Muga carries a natural gold. Pat has a luminous clarity. Eri offers a softer, breathable hand. We begin with the material and keep its character present.</p><a class="button button--secondary" href="/pages/silk-guide">Explore our silk guide</a></div>
  <div class="collection-cards"><a class="muga-card" href="/shop?silk_type=Muga"><span>Muga</span><small>Natural gold, ceremonial ease</small></a><a class="pat-card" href="/shop?silk_type=Pat"><span>Pat</span><small>Light, luminous, precise</small></a><a class="eri-card" href="/shop?silk_type=Eri"><span>Eri</span><small>Soft structure, everyday warmth</small></a></div>
</section>
<section class="home-section artisan-feature">
  <div><p class="eyebrow">Featured artisan</p><h2>Maker stories are introduced with care.</h2><p>Artisan names and production notes expand only after verification and consent.</p><a href="/artisans">Meet the artisans <span aria-hidden="true">→</span></a></div>
  <div class="artisan-feature__study" aria-hidden="true"><div><span>Luit &amp; Loom</span></div></div>
</section>
`;
}

function listingContent(
  url: URL,
  page: Page<ProductCard>,
  query: ProductListQuery,
  collectionTitle: string | null,
): string {
  const title = collectionTitle ?? (url.pathname === "/search" ? "Search the catalogue" : "Shop the catalogue");
  return `<section class="catalogue-intro">
  <p class="eyebrow">Assamese handloom, considered slowly</p>
  <h1>${escapeHtml(title)}</h1>
  <p>${collectionTitle ? "A gathering of weaves selected around one material conversation." : "Each listing is a transparent starting point for a future collection release."}</p>
</section>
${filters(url, query)}
${productGrid(page, url)}`;
}

function productContent(product: ProductDetail, related: ProductCard[]): string {
  const gallery = product.media.length
    ? product.media
        .map(
          (media, index) =>
            `<img src="/media/${escapeHtml(media.id)}" alt="${escapeHtml(media.altText || `${product.title} textile detail`)}" width="1000" height="1250"${index > 0 ? ' loading="lazy"' : ""}>`,
        )
        .join("")
    : `<div class="textile-placeholder product-detail__placeholder" role="img" aria-label="Textile-colour study for ${escapeHtml(product.title)}">Textile-colour study</div>`;
  const firstVariant = product.variants[0];
  return `<article class="product-detail">
  <div class="product-detail__gallery" aria-label="${escapeHtml(product.title)} gallery">${gallery}</div>
  <div class="product-detail__summary">
    <p class="eyebrow">${escapeHtml(product.silkType)}${product.colour ? ` · ${escapeHtml(product.colour)}` : ""}</p>
    <h1>${escapeHtml(product.title)}</h1>
    <p>${escapeHtml(product.description || "A considered handloom catalogue entry, shared with material and maker context.")}</p>
    <p class="price">${firstVariant ? escapeHtml(formatMoney(firstVariant.priceMinor, firstVariant.currency)) : "Price on request"}</p>
    <p>${product.available ? "Available" : "Currently unavailable"}</p>
  </div>
  <section class="specifications" aria-labelledby="specifications-title"><h2 id="specifications-title">Specifications</h2><dl><div><dt>Silk</dt><dd>${escapeHtml(product.silkType)}</dd></div><div><dt>Dimensions</dt><dd>Verification pending</dd></div><div><dt>Care</dt><dd>Request product-specific care guidance before purchase.</dd></div><div><dt>Occasion</dt><dd>${escapeHtml(product.occasion || "Verification pending")}</dd></div></dl></section>
  <section class="provenance" aria-labelledby="provenance-title"><p class="eyebrow">Provenance</p><h2 id="provenance-title">Catalogue record</h2><dl><div><dt>Artisan</dt><dd>Verification pending</dd></div><div><dt>Region</dt><dd>Verification pending</dd></div><div><dt>Motif</dt><dd>Verification pending</dd></div><div><dt>Production details</dt><dd>Verification pending</dd></div></dl><p>Provenance details are added only after verification.</p></section>
  <section class="product-care" aria-labelledby="shipping-title"><h2 id="shipping-title">Shipping, returns &amp; care</h2><p>Shipping, returns, and product-specific care details will be verified before checkout opens.</p></section>
  ${related.length ? `<section class="related-products" aria-labelledby="related-title"><h2 id="related-title">More in ${escapeHtml(product.silkType)}</h2><div class="product-grid">${related.map(productCard).join("")}</div></section>` : ""}
</article>`;
}

export function renderStorefrontError(
  request: Request,
  status: number,
  requestId: string,
): Response {
  const content =
    status === 404
      ? `<h1>We couldn’t find that weave</h1><p>Try a <a href="/search">search</a> or explore <a href="/collections">collections</a>.</p>`
      : `<h1>Our loom needs a moment</h1><p>Please try again shortly.</p><p>Reference: ${escapeHtml(requestId)}</p>`;
  return shell(request, `${status} · Luit & Loom`, content, status);
}

export async function routeStorefront(
  request: Request,
  env: Env,
): Promise<Response | null> {
  if (request.method !== "GET") {
    return null;
  }
  const url = new URL(request.url);
  if (url.pathname === "/") {
    const query = parseProductListQuery(url);
    const page = await listProducts(env.DB, query);
    return shell(request, "Luit & Loom", homeContent(page, url));
  }
  if (url.pathname === "/api/v1/catalog/products") {
    const query = parseProductListQuery(url, true);
    return json(await listProducts(env.DB, query));
  }
  if (url.pathname === "/shop" || url.pathname === "/search") {
    const query = parseProductListQuery(url);
    const page = await listProducts(env.DB, query);
    return shell(
      request,
      `${url.pathname === "/search" ? "Search" : "Shop"} · Luit & Loom`,
      listingContent(url, page, query, null),
    );
  }
  if (url.pathname === "/collections") {
    const collections = await listCollections(env.DB);
    const items = collections.length
      ? collections
          .map(
            (collection) =>
              `<li><a href="/collections/${escapeHtml(collection.slug)}">${escapeHtml(collection.title)}</a></li>`,
          )
          .join("")
      : "<li>No collections are available.</li>";
    return shell(request, "Collections · Luit & Loom", `<h1>Collections</h1><ul>${items}</ul>`);
  }
  const collectionMatch = /^\/collections\/([a-z0-9-]+)$/.exec(url.pathname);
  if (collectionMatch) {
    const slug = collectionMatch[1] ?? "";
    const collection = (await listCollections(env.DB)).find((item) => item.slug === slug);
    if (!collection) {
      throw new HttpError(404, "not_found", "The requested collection was not found.");
    }
    const query = parseProductListQuery(url, false, slug);
    const page = await listProducts(env.DB, query);
    return shell(
      request,
      `${collection.title} · Luit & Loom`,
      listingContent(url, page, query, collection.title),
    );
  }
  const productMatch = /^\/products\/([a-z0-9-]+)$/.exec(url.pathname);
  if (productMatch) {
    const product = await getProduct(env.DB, productMatch[1] ?? "");
    if (!product) {
      throw new HttpError(404, "not_found", "The requested product was not found.");
    }
    const relatedQuery = parseProductListQuery(new URL(request.url));
    relatedQuery.silkType = product.silkType;
    relatedQuery.pageSize = 4;
    const relatedPage = await listProducts(env.DB, relatedQuery);
    const related = relatedPage.items.filter((item) => item.id !== product.id).slice(0, 3);
    return shell(
      request,
      `${product.title} · Luit & Loom`,
      productContent(product, related),
    );
  }
  const editorial = EDITORIAL_PAGES[url.pathname];
  if (editorial) {
    return shell(
      request,
      `${editorial.title} · Luit & Loom`,
      `<article class="editorial-page"><p class="eyebrow">Luit &amp; Loom · Phase 1</p><h1>${escapeHtml(editorial.title)}</h1><p>${escapeHtml(editorial.body)}</p></article>`,
    );
  }
  return null;
}
