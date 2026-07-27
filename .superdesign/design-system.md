# Luit & Loom Design System

## Product context

Luit & Loom is a premium contemporary storefront devoted exclusively to
Assamese silk sarees. The current release is an honest, read-only catalogue
preview with twelve sample products; checkout, accounts, and live inventory are
not yet enabled.

Primary jobs:

- Discover Muga, Pat, and Eri silk sarees.
- Understand material, maker, availability, and provenance context.
- Move from editorial storytelling into catalogue browsing without losing trust.

Key pages: home, catalogue listing/search, collection listing, product detail,
artisan/editorial pages, silk/care/shipping guidance.

## Visual direction

Preserve premium contemporary Assamese heritage: quiet, material-led, refined,
editorial, and specific. The site should feel like a small independent textile
house and cultural journal—not a generic luxury marketplace or festive wedding
template.

Polish through hierarchy, proportion, rhythm, responsive composition, clearer
actions, and subtle textile-derived rules. Avoid decorative clutter, gradients
outside the existing woven placeholder, floating glass effects, rounded SaaS
cards, heavy drop shadows, neon colors, generic gold-on-black luxury styling,
and ornamental motifs used without purpose.

## Color

Use only this palette:

- Muga gold: `#bd8b2f` — restrained accent, rules, textile cues.
- Warm ivory: `#f7f1e6` — secondary surface.
- Lac red: `#7e1f2b` — eyebrow text, active emphasis, alerts.
- Betel green: `#244d3b` — editorial fields and positive availability.
- Charcoal: `#252320` — primary text and high-contrast surfaces.
- Paper: `#fffdf8` — primary background.
- Border: `#d8ccba` — fine dividers.

Maintain accessible contrast. Large dark fields should remain rare and
editorial; do not turn the entire site dark.

## Typography

- Display: `"Iowan Old Style", "Baskerville", "Times New Roman", serif`.
- Body: `Inter, "Avenir Next", Avenir, "Segoe UI", sans-serif`.
- Hero headings use fluid serif type up to `5rem`, tight tracking, and a compact
  line height.
- Section headings use fluid serif type up to `3.2rem`.
- Eyebrows use small uppercase sans-serif, weight 700, `0.12em` tracking.
- Body copy stays comfortably readable with a maximum width around `44rem`.

Do not introduce new fonts.

## Layout and spacing

- Maximum canvas: `90rem`; standard outer gutter: at least `1rem` per side.
- Use a twelve-column editorial grid for hero and narrative layouts.
- Use fluid spacing based on four steps from roughly `0.5rem` to `6rem`.
- Preserve generous vertical intervals between sections and tighter grouping
  inside components.
- Product imagery stays at a 4:5 ratio.
- Desktop catalogue grids should feel intentionally aligned rather than
  maximally dense.
- Mobile collapses to a clear single column with actions remaining at least
  `2.75rem` high.

## Components

- Square corners throughout.
- Buttons: charcoal fill with paper text for primary actions; editorial text
  links for secondary actions.
- Cards: hierarchy through image, typography, rules, and whitespace—not shadows.
- Header: wordmark, compact navigation, search, and restrained utility status.
- Product cards: 4:5 image, material/artisan eyebrow, serif title, price,
  availability, and sample status.
- Section dividers: 1px border or a restrained Muga-gold rule.
- Focus: 3px lac-red outline with 3px offset.

## Motion

- Use only short, meaningful transitions around 180ms.
- Existing product-image crossfade is the primary motion pattern.
- Respect `prefers-reduced-motion`; no parallax, autoplay, or decorative loops.

## Accessibility and trust

- Preserve semantic landmarks, heading order, labels, skip link, visible focus,
  meaningful alt text, and 44px-equivalent interactive targets.
- Preview limitations must remain clear but visually calm.
- Disabled checkout and sample content must never look operational or verified.

