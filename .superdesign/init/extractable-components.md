# Extractable Components

## SiteHeader

- Source: `app/templates/components/header.html`
- Category: layout
- Description: Global wordmark, primary navigation, search, preview utilities, and mobile disclosure.
- Extractable props: `activeItem` (string, default `"home"`), `searchValue` (string, default `""`), `mobileOpen` (boolean, default `false`)
- Hardcoded: wordmark, navigation labels, utility labels, icon symbols, CSS classes

## SiteFooter

- Source: `app/templates/components/footer.html`
- Category: layout
- Description: Global brand statement, guidance links, and preview disclaimer.
- Extractable props: none
- Hardcoded: all copy, URLs, wordmark, CSS classes

## ProductCard

- Source: `app/templates/components/product_card.html`
- Category: basic
- Description: Product image, silk and artisan eyebrow, title, price, availability, and sample label.
- Extractable props: `title`, `silkType`, `artisanName`, `price`, `available`, `sampleLabel`, `imageUrl`
- Hardcoded: card anatomy, image ratio, hover treatment, labels, CSS classes

## ProductGrid

- Source: `app/templates/components/product_grid.html`
- Category: basic
- Description: Responsive catalogue grid with product cards and an empty state.
- Extractable props: `productCount` (number, default `4`), `showEmptyState` (boolean, default `false`)
- Hardcoded: grid structure, empty-state copy, CSS classes

## ProvenancePanel

- Source: `app/templates/components/provenance.html`
- Category: basic
- Description: Definition-list panel for artisan, region, motif, and production details.
- Extractable props: `artisan`, `region`, `motif`, `productionDetails`
- Hardcoded: section headings, verification copy, CSS classes
