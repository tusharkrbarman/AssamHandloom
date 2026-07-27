# Quiet Commerce Fidelity Correction

## Approved target

Match the approved Superdesign draft “Luit & Loom - Polished Heritage
Storefront” (`9000d22f-745d-4a1e-913b-7810f08f164a`). This is a fidelity
correction, not a new visual direction.

## Root cause

The first implementation translated the draft into the existing CSS system
loosely. It preserved the palette and section order, but compressed spacing,
omitted imagery and iconography, and changed several responsive proportions.
The demo seed also continued to serve text-only placeholder images.

## Corrections

- Restore the draft’s roomy 5.5rem header, compact five-item navigation,
  icon-led utilities, ivory search field, and desktop visibility breakpoints.
- Keep the original 5rem fluid hero type, use a photographic sample image,
  enlarge both actions, and preserve the gold overlapping caption.
- Add four restrained line icons to the trust strip and restore its 2rem
  vertical rhythm.
- Use a four-column featured grid with 2rem gutters, borderless cards, small
  metadata, and price/availability on one row.
- Restore the 5/7 material split, roomier material cards, 7/5 artisan split,
  centered newsletter composition, and 4/2/2/4 footer proportions.
- Replace the four home-page sample media URLs with the photographic references
  used by the approved draft. They remain explicitly marked as sample
  placeholders in data and alt text.
- Load Inter for body copy while retaining the exact existing serif stack.

## Constraints

- Remain a read-only demo; no cart, wishlist, newsletter, checkout, or account
  behavior is added.
- Preserve truthful sample and verification disclosures.
- Preserve square corners, the existing seven-color palette, accessible labels,
  focus styles, reduced motion, and mobile navigation.
- Add no JavaScript dependency and no new Python dependency.

## Verification

- Render the home page with four representative sample cards.
- Check desktop and mobile structural classes and accessible labels.
- Run lint, type checks, database-free unit checks, and the full CI suite.

