# Key Page Dependency Trees

## `/` — Home

Entry: `app/templates/storefront/home.html`

Dependencies:

- `app/templates/base.html`
  - `app/templates/components/header.html`
    - `app/templates/components/icons.html`
  - `app/templates/components/footer.html`
  - `app/static/css/site.css`
  - `app/static/js/site.js`
- `app/templates/components/product_grid.html`
  - `app/templates/components/product_card.html`
  - `app/templates/components/pagination.html`

## `/shop` and `/search` — Catalogue listing

Entry: `app/templates/catalog/list.html`

Dependencies:

- `app/templates/base.html`
  - `app/templates/components/header.html`
    - `app/templates/components/icons.html`
  - `app/templates/components/footer.html`
  - `app/static/css/site.css`
  - `app/static/js/site.js`
- `app/templates/components/product_grid.html`
  - `app/templates/components/product_card.html`
  - `app/templates/components/pagination.html`

## `/collections/{slug}` — Collection listing

Entry: `app/templates/catalog/list.html`

Dependencies are identical to `/shop`; collection context changes the heading
and product query.

## `/products/{slug}` — Product detail

Entry: `app/templates/catalog/product.html`

Dependencies:

- `app/templates/base.html`
  - `app/templates/components/header.html`
    - `app/templates/components/icons.html`
  - `app/templates/components/footer.html`
  - `app/static/css/site.css`
  - `app/static/js/site.js`
- `app/templates/components/provenance.html`
- `app/templates/components/product_card.html`

## Editorial and guidance pages

Entry: `app/templates/storefront/page.html`

Dependencies:

- `app/templates/base.html`
  - `app/templates/components/header.html`
    - `app/templates/components/icons.html`
  - `app/templates/components/footer.html`
  - `app/static/css/site.css`
  - `app/static/js/site.js`
