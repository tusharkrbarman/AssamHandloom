# Theme

## Compact token summary

- Palette: Muga gold `#bd8b2f`, warm ivory `#f7f1e6`, lac red `#7e1f2b`,
  betel green `#244d3b`, charcoal `#252320`, paper `#fffdf8`, border
  `#d8ccba`.
- Display type: Iowan Old Style → Baskerville → Times New Roman → serif.
- Body type: Inter → Avenir Next → Avenir → Segoe UI → sans-serif.
- Type scale: hero `clamp(2.2rem, 6vw, 5rem)`, section
  `clamp(1.8rem, 4vw, 3.2rem)`, eyebrow `0.76rem`.
- Spacing: four fluid steps from `clamp(0.5rem, 1vw, 0.8rem)` to
  `clamp(2.5rem, 7vw, 6rem)`.
- Corners: square; no border-radius system.
- Shadows: none; hierarchy comes from rules, color fields, and whitespace.
- Content width: `90rem`; reading width: `44rem`.
- Breakpoints: `72rem` and `48rem`.
- Motion: 180ms image crossfade; reduced-motion override.

## Raw source

Path: `app/static/css/site.css`

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
  --space-1: clamp(0.5rem, 1vw, 0.8rem);
  --space-2: clamp(1rem, 2vw, 1.5rem);
  --space-3: clamp(1.5rem, 4vw, 3rem);
  --space-4: clamp(2.5rem, 7vw, 6rem);
}

* { box-sizing: border-box; }
html { color: var(--color-charcoal); background: var(--color-paper); font-family: var(--font-body); line-height: 1.5; }
body { margin: 0; min-width: 20rem; }
img { display: block; max-width: 100%; }
a { color: inherit; text-decoration-thickness: 0.08em; text-underline-offset: 0.18em; }
button, input, select, textarea { font: inherit; }
button, input[type="submit"], .button { min-height: 2.75rem; }
h1, h2, h3 { font-family: var(--font-display); line-height: 1.08; }
h1 { font-size: clamp(2.2rem, 6vw, 5rem); letter-spacing: -0.03em; }
h2 { font-size: clamp(1.8rem, 4vw, 3.2rem); }
p { max-width: var(--reading-width); }

.container { width: min(100% - 2rem, var(--content-width)); margin-inline: auto; }
main { min-height: 58vh; padding-block: var(--space-4); }
main > * { width: min(100% - 2rem, var(--content-width)); margin-inline: auto; }
.editorial-grid { display: grid; gap: var(--space-3); grid-template-columns: repeat(12, 1fr); }
.card { border: 1px solid var(--color-border); background: var(--color-paper); padding: var(--space-2); }
.eyebrow { color: var(--color-lac); font-size: 0.76rem; font-weight: 700; letter-spacing: 0.12em; margin: 0 0 var(--space-1); text-transform: uppercase; }
.button { align-items: center; background: var(--color-charcoal); color: var(--color-paper); display: inline-flex; padding: 0.5rem 1rem; text-decoration: none; }
.action-row { align-items: center; display: flex; flex-wrap: wrap; gap: var(--space-2); }
.home-hero { align-items: end; min-height: 34rem; }
.home-hero__copy { grid-column: 1 / span 8; padding-block: var(--space-4); }
.home-hero__note { background: var(--color-ivory); border-top: 4px solid var(--color-muga); grid-column: 9 / -1; margin-bottom: var(--space-4); padding: var(--space-2); }
.home-section { margin-top: var(--space-4); }
.section-heading { display: flex; flex-wrap: wrap; justify-content: space-between; gap: var(--space-2); }
.product-grid { display: grid; gap: var(--space-2); grid-template-columns: repeat(auto-fit, minmax(15rem, 1fr)); }
.product-card { background: var(--color-paper); border-top: 1px solid var(--color-charcoal); display: flex; flex-direction: column; min-width: 0; }
.product-card__image { background: var(--color-ivory); display: block; overflow: hidden; }
.product-card__image { position: relative; }.product-card__image img { aspect-ratio: 4 / 5; object-fit: cover; }
.product-card__secondary-image { inset: 0; opacity: 0; position: absolute; transition: opacity 180ms ease; }
@media (hover: hover) and (pointer: fine) { .has-secondary-image:hover .product-card__secondary-image, .has-secondary-image:focus-visible .product-card__secondary-image { opacity: 1; } }
.textile-placeholder { align-items: end; background: repeating-linear-gradient(90deg, #b78732 0 2px, #f1e6cf 2px 7px, #7e1f2b 7px 8px, #244d3b 8px 11px); color: var(--color-paper); display: flex; font-size: 0.75rem; min-height: 16rem; padding: var(--space-1); text-shadow: 0 1px 2px var(--color-charcoal); }
.product-card__body { padding-top: var(--space-1); }
.product-card h2 { font-size: 1.5rem; margin: 0; }
.product-card p { margin: 0.25rem 0; }
.price { font-weight: 700; }
.availability { color: var(--color-betel); font-size: 0.85rem; }
.availability.is-unavailable { color: var(--color-lac); }
.sample-label { color: var(--color-lac); font-size: 0.85rem; }
.catalogue-intro { max-width: var(--reading-width); }
.catalogue-filters { align-items: end; border-block: 1px solid var(--color-border); display: flex; flex-wrap: wrap; gap: var(--space-1) var(--space-2); margin-block: var(--space-3); padding-block: var(--space-2); }
.catalogue-filters > div { display: grid; gap: 0.25rem; }
.catalogue-filters input, .catalogue-filters select { border: 1px solid var(--color-border); min-height: 2.75rem; padding: 0.35rem; }
.catalogue-filters button, .product-detail button { background: var(--color-charcoal); border: 1px solid var(--color-charcoal); color: var(--color-paper); padding-inline: 0.8rem; }
.pagination { align-items: center; display: flex; gap: var(--space-2); justify-content: center; margin-top: var(--space-3); }
.empty-state { border-block: 1px solid var(--color-border); grid-column: 1 / -1; padding: var(--space-3); }
.split-feature { align-items: start; border-top: 1px solid var(--color-border); display: grid; gap: var(--space-3); grid-template-columns: 1fr 1fr; padding-top: var(--space-3); }
.collection-cards, .assurance-grid { display: grid; gap: var(--space-2); grid-template-columns: repeat(3, 1fr); }
.collection-cards a { background: var(--color-ivory); border-bottom: 3px solid var(--color-muga); display: grid; min-height: 12rem; padding: var(--space-2); text-decoration: none; }
.collection-cards .pat-card { border-color: var(--color-betel); }.collection-cards .eri-card { border-color: var(--color-lac); }
.collection-cards span { font-family: var(--font-display); font-size: 2rem; }.collection-cards small { align-self: end; }
.artisan-feature, .newsletter-invitation { background: var(--color-charcoal); color: var(--color-ivory); padding: var(--space-3); }.newsletter-invitation { background: var(--color-betel); margin-top: var(--space-4); }.artisan-feature .eyebrow, .newsletter-invitation .eyebrow { color: var(--color-muga); }
.assurance-grid article { border-top: 2px solid var(--color-muga); padding-top: var(--space-1); }
.product-detail { display: grid; gap: var(--space-3); grid-template-columns: 1.2fr 0.8fr; }
.product-detail__gallery { background: var(--color-ivory); }.product-detail__gallery img { aspect-ratio: 4 / 5; object-fit: cover; }.product-detail__placeholder { min-height: 32rem; }
.product-detail__summary { align-self: start; position: sticky; top: 1rem; }.product-detail__summary h1 { margin-top: 0; }
.specifications, .provenance, .product-care, .related-products { border-top: 1px solid var(--color-border); grid-column: 1 / -1; padding-top: var(--space-2); }
.specifications dl, .provenance dl { display: grid; gap: var(--space-1); grid-template-columns: repeat(2, minmax(0, 1fr)); }.specifications dl div, .provenance dl div { border-bottom: 1px solid var(--color-border); padding-bottom: var(--space-1); }.specifications dt, .provenance dt { font-weight: 700; }.specifications dd, .provenance dd { margin: 0; }

.skip-link { background: var(--color-charcoal); color: var(--color-paper); left: 1rem; padding: 0.75rem 1rem; position: fixed; top: -5rem; z-index: 20; }
.skip-link:focus { top: 1rem; }
.visually-hidden { clip: rect(0 0 0 0); clip-path: inset(50%); height: 1px; overflow: hidden; position: absolute; white-space: nowrap; width: 1px; }
:focus-visible { outline: 3px solid var(--color-lac); outline-offset: 3px; }

.site-header { border-bottom: 1px solid var(--color-border); background: var(--color-paper); position: relative; }
.site-header::after { background: repeating-linear-gradient(90deg, var(--color-muga) 0 1px, transparent 1px 7px, var(--color-betel) 7px 8px, transparent 8px 14px); content: ""; display: block; height: 3px; opacity: 0.75; }
.header-row { align-items: center; display: flex; flex-wrap: wrap; gap: var(--space-1) var(--space-2); min-height: 5rem; padding-block: var(--space-1); }
.wordmark { align-items: center; display: inline-flex; font-family: var(--font-display); font-size: 1.45rem; font-weight: 700; letter-spacing: 0.03em; min-height: 2.75rem; text-decoration: none; white-space: nowrap; }
.wordmark span { color: var(--color-lac); font-style: italic; }
.primary-nav { flex: 1 1 30rem; }
.primary-nav ul, .site-footer ul { display: flex; flex-wrap: wrap; gap: 0.2rem 1rem; list-style: none; margin: 0; padding: 0; }
.primary-nav a { display: inline-flex; align-items: center; min-height: 2.75rem; font-size: 0.9rem; text-decoration: none; }
.primary-nav a:hover { color: var(--color-lac); }
.header-utilities { align-items: center; display: flex; flex: 1 1 28rem; flex-wrap: wrap; gap: 0.4rem; justify-content: flex-end; }
.site-search { align-items: center; display: flex; gap: 0.35rem; }
.site-search label { font-size: 0.8rem; font-weight: 600; }
.site-search input { border: 1px solid var(--color-border); border-radius: 0; min-height: 2.75rem; padding: 0.45rem 0.65rem; width: 10rem; }
.site-search button, .disclosure-button { border: 1px solid var(--color-charcoal); background: var(--color-charcoal); color: var(--color-paper); cursor: pointer; padding-inline: 0.8rem; }
.utility-placeholder { align-items: center; border-left: 1px solid var(--color-border); display: inline-flex; flex-wrap: wrap; gap: 0.2rem; min-height: 2.75rem; padding-left: 0.5rem; }
.utility-placeholder small { color: var(--color-lac); display: block; flex-basis: 100%; font-size: 0.62rem; line-height: 1.1; }
.icon { color: var(--color-betel); font-family: var(--font-display); font-size: 1.1rem; }
.disclosure-button { display: none; }
.mobile-navigation { background: var(--color-ivory); border-bottom: 1px solid var(--color-border); padding-block: var(--space-1); }
.mobile-navigation nav { display: flex; flex-wrap: wrap; gap: 1rem; }
.mobile-navigation a { align-items: center; display: inline-flex; min-height: 2.75rem; }
.disclosure-backdrop { background: rgb(37 35 32 / 0.45); border: 0; inset: 0; position: fixed; z-index: 5; }

.site-footer { background: var(--color-charcoal); color: var(--color-ivory); padding-block: var(--space-3); }
.footer-grid { display: grid; gap: var(--space-2); grid-template-columns: repeat(3, minmax(0, 1fr)); }
.site-footer a { align-items: center; display: inline-flex; min-height: 2.75rem; }
.footer-note { color: var(--color-border); font-size: 0.9rem; }

@media (max-width: 72rem) {
  .header-utilities { justify-content: flex-start; }
}

@media (max-width: 48rem) {
  .header-row { align-items: flex-start; }
  .primary-nav { flex-basis: 100%; order: 3; }
  .primary-nav ul { gap: 0.1rem 0.75rem; }
  .site-search { flex: 1 1 100%; }
  .site-search input { flex: 1; width: auto; }
  .utility-placeholder { font-size: 0.8rem; }
  .disclosure-button { display: inline-block; }
  .footer-grid { grid-template-columns: 1fr; }
  .home-hero__copy, .home-hero__note { grid-column: 1 / -1; }.home-hero__note { margin-bottom: 0; }.split-feature, .product-detail { grid-template-columns: 1fr; }.collection-cards, .assurance-grid { grid-template-columns: 1fr; }.product-detail__summary { position: static; }
}

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { animation-duration: 0.01ms !important; animation-iteration-count: 1 !important; scroll-behavior: auto !important; transition-duration: 0.01ms !important; }
}
```
