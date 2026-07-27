# Shared UI Components

Framework: server-rendered Jinja templates with FastAPI. Components are custom
Jinja partials; there is no third-party component library.

## Icon macro

Path: `app/templates/components/icons.html`

```html
{% macro icon(symbol, label) -%}
<span class="icon" aria-hidden="true">{{ symbol }}</span><span class="visually-hidden">{{ label }}</span>
{%- endmacro %}
```

## Product card

Path: `app/templates/components/product_card.html`

```html
<article class="product-card">
  <a class="product-card__image{% if product.media | length > 1 %} has-secondary-image{% endif %}" href="/products/{{ product.slug }}" aria-label="View {{ product.title }}">
    {% if product.primary_media %}
      <img class="product-card__primary-image" src="{{ product.primary_media.url }}" alt="{{ product.primary_media.alt_text or (product.title ~ ' in ' ~ product.silk_type ~ ' silk') }}" width="720" height="900" loading="lazy">
      {% for image in product.media if image.display_order != product.primary_media.display_order %}{% if loop.first %}<img class="product-card__secondary-image" data-secondary-image src="{{ image.url }}" alt="" aria-hidden="true" width="720" height="900" loading="lazy">{% endif %}{% endfor %}
    {% else %}
      <span class="textile-placeholder" role="img" aria-label="Textile-colour study for {{ product.title }}">Textile-colour study</span>
    {% endif %}
  </a>
  <div class="product-card__body">
    <p class="eyebrow">{{ product.silk_type }}{% if product.artisan_name %} · {{ product.artisan_name }}{% endif %}</p>
    <h2><a href="/products/{{ product.slug }}">{{ product.title }}</a></h2>
    <p class="price">{{ product.display_price }}</p>
    <p class="availability {% if not product.available %}is-unavailable{% endif %}">{% if product.available %}Available{% else %}Currently unavailable{% endif %}</p>
    {% if product.sample_label %}<p class="sample-label">{{ product.sample_label }} catalogue item</p>{% endif %}
  </div>
</article>
```

## Product grid

Path: `app/templates/components/product_grid.html`

```html
<section id="catalogue-results" aria-live="polite" aria-label="Catalogue results">
  <div id="product-grid" class="product-grid">
    {% for product in page.items %}
      {% include "components/product_card.html" %}
    {% else %}
      <div class="empty-state">
        <p>No weaves matched your search.</p>
        <a class="text-link" href="/shop">Browse all weaves</a>
      </div>
    {% endfor %}
  </div>
  {% if not home %}{% include "components/pagination.html" %}{% endif %}
</section>
```

## Pagination

Path: `app/templates/components/pagination.html`

```html
{% if page.total_pages > 1 %}
<nav class="pagination" aria-label="Catalogue pages">
  {% if page.page > 1 %}<a href="{{ request.url.path }}?{{ pagination_query }}page={{ page.page - 1 }}" rel="prev">Previous</a>{% endif %}
  <span>Page {{ page.page }} of {{ page.total_pages }}</span>
  {% if page.page < page.total_pages %}<a href="{{ request.url.path }}?{{ pagination_query }}page={{ page.page + 1 }}" rel="next">Next</a>{% endif %}
</nav>
{% endif %}
```

## Provenance panel

Path: `app/templates/components/provenance.html`

```html
<section class="provenance" aria-labelledby="provenance-title">
  <p class="eyebrow">Provenance</p>
  <h2 id="provenance-title">Catalogue record</h2>
  <dl>
    <div><dt>Artisan</dt><dd>{{ product.artisan_name or "Verification pending" }}</dd></div>
    <div><dt>Region</dt><dd>Verification pending</dd></div>
    <div><dt>Motif</dt><dd>Verification pending</dd></div>
    <div><dt>Production details</dt><dd>Verification pending</dd></div>
  </dl>
  <p>General guidance: provenance details will be verified and added to each catalogue record.</p>
</section>
```
