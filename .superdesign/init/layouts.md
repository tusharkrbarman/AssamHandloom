# Shared Layouts

## Base document

Path: `app/templates/base.html`

```html
<!doctype html>
<html lang="en-IN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{% block page_title %}Luit &amp; Loom{% endblock %}</title>
  <meta name="description" content="Luit &amp; Loom presents contemporary Assamese handloom with care and clarity.">
  <link rel="canonical" href="{{ canonical_url }}">
  <link rel="stylesheet" href="{{ url_for('static', path='css/site.css') }}">
  <script src="{{ url_for('static', path='vendor/htmx-2.0.4.min.js') }}" defer></script>
  <script src="{{ url_for('static', path='js/site.js') }}" defer></script>
</head>
<body>
  <a class="skip-link" href="#main-content">Skip to main content</a>
  {% include "components/header.html" %}
  <main id="main-content" tabindex="-1">
    {% block content %}{% endblock %}
  </main>
  {% include "components/footer.html" %}
</body>
</html>
```

## Site header

Path: `app/templates/components/header.html`

```html
{% from "components/icons.html" import icon %}
<header class="site-header">
  <div class="container header-row">
    <a class="wordmark" href="/" aria-label="Luit and Loom home">Luit <span>&amp;</span> Loom</a>
    <nav class="primary-nav" aria-label="Primary navigation">
      <ul>
        <li><a href="/shop?sort=newest">New Arrivals</a></li>
        <li><a href="/shop">Shop</a></li>
        <li><a href="/shop?silk_type=Muga">Muga Silk</a></li>
        <li><a href="/shop?silk_type=Pat">Pat Silk</a></li>
        <li><a href="/shop?silk_type=Eri">Eri Silk</a></li>
        <li><a href="/artisans">Artisans</a></li>
        <li><a href="/our-story">Our Story</a></li>
        <li><a href="/journal">Journal</a></li>
      </ul>
    </nav>
    <div class="header-utilities">
      <form class="site-search" role="search" action="/search" method="get">
        <label for="site-search">Search Luit &amp; Loom</label>
        <input id="site-search" name="search" type="search" placeholder="Search weaves" autocomplete="off">
        <button type="submit">Search</button>
      </form>
      <span class="utility-placeholder" aria-label="Wishlist. Coming in checkout phase">{{ icon('♡', 'Wishlist') }}<span>Wishlist</span><small>Coming in checkout phase</small></span>
      <span class="utility-placeholder" aria-label="Cart, zero items. Coming in checkout phase">{{ icon('Bag', 'Cart') }}<span>Cart (0)</span><small>Coming in checkout phase</small></span>
      <button class="disclosure-button" type="button" data-disclosure-button aria-controls="mobile-navigation" aria-expanded="false">Browse</button>
    </div>
  </div>
  <div id="mobile-navigation" class="mobile-navigation" hidden>
    <nav class="container" aria-label="Mobile navigation">
      <a href="/shop">Shop all weaves</a>
      <a href="/collections">Collections</a>
      <a href="/artisans">Artisans</a>
      <a href="/our-story">Our story</a>
      <a href="/journal">Journal</a>
      <a href="/search">Search</a>
    </nav>
  </div>
  <button class="disclosure-backdrop" type="button" data-disclosure-backdrop aria-label="Close navigation" hidden></button>
</header>
```

## Site footer

Path: `app/templates/components/footer.html`

```html
<footer class="site-footer">
  <div class="container footer-grid">
    <div>
      <a class="wordmark" href="/">Luit <span>&amp;</span> Loom</a>
      <p>Contemporary Assamese handloom, considered with care.</p>
    </div>
    <nav aria-label="Footer navigation">
      <ul>
        <li><a href="/pages/silk-guide">Silk Guide</a></li>
        <li><a href="/pages/care">Care Guide</a></li>
        <li><a href="/pages/shipping">Shipping</a></li>
        <li><a href="/pages/returns">Returns</a></li>
        <li><a href="/pages/contact">Contact</a></li>
        <li><a href="/pages/faq">FAQ</a></li>
      </ul>
    </nav>
    <p class="footer-note">Phase 1 catalogue preview. Checkout is not yet available.</p>
  </div>
</footer>
```
