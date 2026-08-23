import { AuthenticatedOwner, requireCsrf, requireOwner } from "./auth";
import {
  archiveProduct,
  ProductInput,
  PublicationState,
  saveCollection,
  saveProduct,
  saveVariant,
  setCollectionProducts,
} from "./catalogue";
import { escapeHtml, html, HttpError, readForm, redirect } from "./http";

interface ProductRow {
  id: string;
  slug: string;
  title: string;
  description: string;
  silk_type: string;
  colour: string | null;
  occasion: string | null;
  publication_state: PublicationState;
  featured_rank: number;
  archived_at: string | null;
}

interface VariantRow {
  id: string;
  product_id: string;
  sku: string;
  title: string;
  price_minor: number;
  currency: string;
  weight_grams: number | null;
  publication_state: PublicationState;
}

interface CollectionRow {
  id: string;
  slug: string;
  title: string;
  description: string;
  publication_state: PublicationState;
  display_order: number;
  selected?: number;
}

interface MediaRow {
  id: string;
  alt_text: string;
}

function text(form: FormData, key: string): string {
  const value = form.get(key);
  return typeof value === "string" ? value : "";
}

function integer(form: FormData, key: string): number {
  const value = text(form, key);
  return /^-?\d+$/.test(value) ? Number.parseInt(value, 10) : Number.NaN;
}

function optionalInteger(form: FormData, key: string): number | null {
  return text(form, key).trim() === "" ? null : integer(form, key);
}

function state(form: FormData): PublicationState {
  return text(form, "publication_state") as PublicationState;
}

function stateOptions(selected: PublicationState): string {
  return ["draft", "published"]
    .map(
      (value) =>
        `<option value="${value}"${value === selected ? " selected" : ""}>${value}</option>`,
    )
    .join("");
}

export function adminPage(
  title: string,
  body: string,
  authenticated: AuthenticatedOwner,
  status = 200,
): Response {
  return html(
    `<!doctype html>
<html lang="en-IN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>${escapeHtml(title)} · Luit &amp; Loom</title>
  <link rel="stylesheet" href="/css/site.css">
</head>
<body>
  <a class="skip-link" href="#main-content">Skip to main content</a>
  <header class="site-header"><div class="container header-inner">
    <a class="wordmark" href="/">Luit <span>&amp;</span> Loom</a>
    <nav aria-label="Owner navigation">
      <a href="/admin">Products</a> <a href="/admin/orders">Orders</a> <a href="/admin/collections">Collections</a>
      <a href="/admin/inventory">Inventory</a>
      <form method="post" action="/admin/logout" style="display:inline">
        <input type="hidden" name="csrf" value="${escapeHtml(authenticated.session.csrf)}">
        <button type="submit">Sign out</button>
      </form>
    </nav>
  </div></header>
  <main id="main-content" class="container editorial-page" tabindex="-1">
    <p class="eyebrow">Store owner</p>
    <h1>${escapeHtml(title)}</h1>
    ${body}
  </main>
</body>
</html>`,
    status,
    { "cache-control": "no-store" },
  );
}

function productInput(form: FormData, id: string | null): ProductInput {
  return {
    id,
    slug: text(form, "slug"),
    title: text(form, "title"),
    description: text(form, "description"),
    silkType: text(form, "silk_type"),
    colour: text(form, "colour") || null,
    occasion: text(form, "occasion") || null,
    publicationState: state(form),
    featuredRank: integer(form, "featured_rank"),
  };
}

function productForm(product: ProductRow | null, csrf: string): string {
  return `<form method="post">
    <input type="hidden" name="csrf" value="${escapeHtml(csrf)}">
    <label>Slug <input name="slug" required pattern="[a-z0-9]+(?:-[a-z0-9]+)*" value="${escapeHtml(product?.slug)}"></label>
    <label>Title <input name="title" required maxlength="160" value="${escapeHtml(product?.title)}"></label>
    <label>Description <textarea name="description" maxlength="5000">${escapeHtml(product?.description)}</textarea></label>
    <label>Silk type <input name="silk_type" required maxlength="80" value="${escapeHtml(product?.silk_type)}"></label>
    <label>Colour <input name="colour" maxlength="80" value="${escapeHtml(product?.colour)}"></label>
    <label>Occasion <input name="occasion" maxlength="80" value="${escapeHtml(product?.occasion)}"></label>
    <label>Publication <select name="publication_state">${stateOptions(product?.publication_state ?? "draft")}</select></label>
    <label>Featured rank <input name="featured_rank" type="number" min="0" required value="${product?.featured_rank ?? 0}"></label>
    <button type="submit">Save product</button>
  </form>`;
}

function variantForm(variant: VariantRow | null, csrf: string, action: string): string {
  return `<form method="post" action="${action}">
    <input type="hidden" name="csrf" value="${escapeHtml(csrf)}">
    <label>SKU <input name="sku" required maxlength="80" value="${escapeHtml(variant?.sku)}"></label>
    <label>Variant title <input name="title" required maxlength="160" value="${escapeHtml(variant?.title ?? "Standard")}"></label>
    <label>Price in paise <input name="price_minor" type="number" min="0" required value="${variant?.price_minor ?? 0}"></label>
    <label>Currency <input name="currency" required pattern="[A-Z]{3}" maxlength="3" value="${escapeHtml(variant?.currency ?? "INR")}"></label>
    <label>Weight in grams <input name="weight_grams" type="number" min="1" value="${variant?.weight_grams ?? ""}"></label>
    <label>Publication <select name="publication_state">${stateOptions(variant?.publication_state ?? "draft")}</select></label>
    <button type="submit">Save variant</button>
  </form>`;
}

function collectionForm(collection: CollectionRow | null, csrf: string): string {
  return `<form method="post">
    <input type="hidden" name="csrf" value="${escapeHtml(csrf)}">
    <label>Slug <input name="slug" required pattern="[a-z0-9]+(?:-[a-z0-9]+)*" value="${escapeHtml(collection?.slug)}"></label>
    <label>Title <input name="title" required maxlength="160" value="${escapeHtml(collection?.title)}"></label>
    <label>Description <textarea name="description" maxlength="5000">${escapeHtml(collection?.description)}</textarea></label>
    <label>Publication <select name="publication_state">${stateOptions(collection?.publication_state ?? "draft")}</select></label>
    <label>Display order <input name="display_order" type="number" min="0" required value="${collection?.display_order ?? 0}"></label>
    <button type="submit">Save collection</button>
  </form>`;
}

async function dashboard(env: Env, owner: AuthenticatedOwner): Promise<Response> {
  const result = await env.DB.prepare(
    `SELECT id, slug, title, publication_state, archived_at
    FROM products ORDER BY updated_at DESC`,
  ).all<Pick<ProductRow, "id" | "slug" | "title" | "publication_state" | "archived_at">>();
  const rows = result.results
    .map(
      (product) => `<tr>
        <td><a href="/admin/products/${product.id}">${escapeHtml(product.title)}</a></td>
        <td>${escapeHtml(product.slug)}</td>
        <td>${product.archived_at ? "archived" : escapeHtml(product.publication_state)}</td>
      </tr>`,
    )
    .join("");
  return adminPage(
    "Products",
    `<p><a href="/admin/products/new">Add product</a></p>
    <table><thead><tr><th>Product</th><th>Slug</th><th>Status</th></tr></thead>
    <tbody>${rows || '<tr><td colspan="3">No products yet.</td></tr>'}</tbody></table>`,
    owner,
  );
}

async function productPage(
  env: Env,
  owner: AuthenticatedOwner,
  id: string | null,
): Promise<Response> {
  if (!id) {
    return adminPage("New product", productForm(null, owner.session.csrf), owner);
  }
  const product = await env.DB.prepare("SELECT * FROM products WHERE id = ?")
    .bind(id)
    .first<ProductRow>();
  if (!product) throw new HttpError(404, "product_not_found", "Product not found.");
  const [variantResult, collectionResult, mediaResult] = await env.DB.batch([
    env.DB.prepare("SELECT * FROM variants WHERE product_id = ? ORDER BY created_at").bind(id),
    env.DB
      .prepare(
        `SELECT collection.*, membership.product_id IS NOT NULL AS selected
        FROM collections collection
        LEFT JOIN collection_products membership
          ON membership.collection_id = collection.id AND membership.product_id = ?
        ORDER BY collection.display_order, collection.id`,
      )
      .bind(id),
    env.DB
      .prepare(
        "SELECT id, alt_text FROM product_media WHERE product_id = ? ORDER BY display_order, id",
      )
      .bind(id),
  ]);
  if (!variantResult || !collectionResult || !mediaResult) {
    throw new HttpError(500, "catalogue_read_failed", "Product details are unavailable.");
  }
  const variants = variantResult.results as unknown as VariantRow[];
  const collections = collectionResult.results as unknown as CollectionRow[];
  const media = mediaResult.results as unknown as MediaRow[];
  const variantForms = variants
    .map((variant) =>
      variantForm(variant, owner.session.csrf, `/admin/variants/${variant.id}`),
    )
    .join("");
  const memberships = collections
    .map(
      (collection) => `<label><input type="checkbox" name="product_id" value="${collection.id}"${collection.selected ? " checked" : ""}> ${escapeHtml(collection.title)}</label>`,
    )
    .join("");
  const mediaCards = media
    .map(
      (item) => `<figure>
        <img src="/admin/media/${item.id}/content" alt="${escapeHtml(item.alt_text)}" width="240" height="300">
        <figcaption>${escapeHtml(item.alt_text)}</figcaption>
        <form method="post" action="/admin/media/${item.id}/delete">
          <input type="hidden" name="csrf" value="${escapeHtml(owner.session.csrf)}">
          <button type="submit">Delete image</button>
        </form>
      </figure>`,
    )
    .join("");
  return adminPage(
    product.title,
    `${productForm(product, owner.session.csrf)}
    <h2>Variants</h2>
    ${variantForms}
    <h3>Add variant</h3>
    ${variantForm(null, owner.session.csrf, `/admin/products/${id}/variants`)}
    <h2>Images</h2>
    ${mediaCards || "<p>No images yet.</p>"}
    <form method="post" action="/admin/products/${id}/media" enctype="multipart/form-data">
      <input type="hidden" name="csrf" value="${escapeHtml(owner.session.csrf)}">
      <label>Image <input name="image" type="file" accept="image/jpeg,image/png,image/webp" required></label>
      <label>Alternative text <input name="alt_text" maxlength="300" required></label>
      <button type="submit">Add image</button>
    </form>
    <h2>Collections</h2>
    <form method="post" action="/admin/products/${id}/collections">
      <input type="hidden" name="csrf" value="${escapeHtml(owner.session.csrf)}">
      ${memberships || "<p>Create a collection first.</p>"}
      <button type="submit">Save collections</button>
    </form>
    <h2>Archive</h2>
    <form method="post" action="/admin/products/${id}/archive">
      <input type="hidden" name="csrf" value="${escapeHtml(owner.session.csrf)}">
      <button type="submit">Archive product</button>
    </form>`,
    owner,
  );
}

async function collectionsPage(
  env: Env,
  owner: AuthenticatedOwner,
  id: string | null = null,
): Promise<Response> {
  const collections = await env.DB.prepare(
    "SELECT * FROM collections ORDER BY display_order, id",
  ).all<CollectionRow>();
  const selected = id
    ? collections.results.find((collection) => collection.id === id) ?? null
    : null;
  if (id && !selected) {
    throw new HttpError(404, "collection_not_found", "Collection not found.");
  }
  const links = collections.results
    .map(
      (collection) =>
        `<li><a href="/admin/collections/${collection.id}">${escapeHtml(collection.title)}</a> · ${escapeHtml(collection.publication_state)}</li>`,
    )
    .join("");
  return adminPage(
    selected ? `Edit ${selected.title}` : "Collections",
    `<ul>${links || "<li>No collections yet.</li>"}</ul>
    <h2>${selected ? "Edit collection" : "Add collection"}</h2>
    ${collectionForm(selected, owner.session.csrf)}`,
    owner,
  );
}

async function mutate(
  request: Request,
  env: Env,
  owner: AuthenticatedOwner,
  path: string,
): Promise<Response | null> {
  const form = await readForm(request);
  await requireCsrf(request, owner.session, form);

  if (path === "/admin/products/new") {
    const id = await saveProduct(env.DB, productInput(form, null));
    return redirect(`/admin/products/${id}`);
  }

  const productMatch = path.match(/^\/admin\/products\/([^/]+)$/);
  if (productMatch?.[1]) {
    const id = await saveProduct(env.DB, productInput(form, productMatch[1]));
    return redirect(`/admin/products/${id}`);
  }

  const archiveMatch = path.match(/^\/admin\/products\/([^/]+)\/archive$/);
  if (archiveMatch?.[1]) {
    await archiveProduct(env.DB, archiveMatch[1]);
    return redirect("/admin");
  }

  const createVariantMatch = path.match(/^\/admin\/products\/([^/]+)\/variants$/);
  if (createVariantMatch?.[1]) {
    await saveVariant(env.DB, {
      id: null,
      productId: createVariantMatch[1],
      sku: text(form, "sku"),
      title: text(form, "title"),
      priceMinor: integer(form, "price_minor"),
      currency: text(form, "currency"),
      weightGrams: optionalInteger(form, "weight_grams"),
      publicationState: state(form),
    });
    return redirect(`/admin/products/${createVariantMatch[1]}`);
  }

  const variantMatch = path.match(/^\/admin\/variants\/([^/]+)$/);
  if (variantMatch?.[1]) {
    const variant = await env.DB
      .prepare("SELECT product_id FROM variants WHERE id = ?")
      .bind(variantMatch[1])
      .first<{ product_id: string }>();
    if (!variant) throw new HttpError(404, "variant_not_found", "Variant not found.");
    await saveVariant(env.DB, {
      id: variantMatch[1],
      productId: variant.product_id,
      sku: text(form, "sku"),
      title: text(form, "title"),
      priceMinor: integer(form, "price_minor"),
      currency: text(form, "currency"),
      weightGrams: optionalInteger(form, "weight_grams"),
      publicationState: state(form),
    });
    return redirect(`/admin/products/${variant.product_id}`);
  }

  const membershipMatch = path.match(/^\/admin\/products\/([^/]+)\/collections$/);
  if (membershipMatch?.[1]) {
    const ids = form
      .getAll("product_id")
      .filter((value): value is string => typeof value === "string");
    await setCollectionProducts(env.DB, membershipMatch[1], ids);
    return redirect(`/admin/products/${membershipMatch[1]}`);
  }

  if (path === "/admin/collections") {
    const id = await saveCollection(env.DB, {
      id: null,
      slug: text(form, "slug"),
      title: text(form, "title"),
      description: text(form, "description"),
      publicationState: state(form),
      displayOrder: integer(form, "display_order"),
    });
    return redirect(`/admin/collections/${id}`);
  }

  const collectionMatch = path.match(/^\/admin\/collections\/([^/]+)$/);
  if (collectionMatch?.[1]) {
    const id = await saveCollection(env.DB, {
      id: collectionMatch[1],
      slug: text(form, "slug"),
      title: text(form, "title"),
      description: text(form, "description"),
      publicationState: state(form),
      displayOrder: integer(form, "display_order"),
    });
    return redirect(`/admin/collections/${id}`);
  }
  return null;
}

export async function routeAdmin(request: Request, env: Env): Promise<Response | null> {
  const path = new URL(request.url).pathname;
  if (!path.startsWith("/admin")) return null;

  let owner: AuthenticatedOwner;
  try {
    owner = await requireOwner(request, env);
  } catch (error) {
    if (error instanceof HttpError && error.status === 401) {
      return redirect("/admin/login");
    }
    throw error;
  }

  try {
    if (request.method === "POST") {
      const response = await mutate(request, env, owner, path);
      if (response) return response;
    }
    if (request.method === "GET") {
      if (path === "/admin") return dashboard(env, owner);
      if (path === "/admin/products/new") return productPage(env, owner, null);
      const productMatch = path.match(/^\/admin\/products\/([^/]+)$/);
      if (productMatch?.[1]) return productPage(env, owner, productMatch[1]);
      if (path === "/admin/collections") return collectionsPage(env, owner);
      const collectionMatch = path.match(/^\/admin\/collections\/([^/]+)$/);
      if (collectionMatch?.[1]) return collectionsPage(env, owner, collectionMatch[1]);
    }
    return adminPage("Not found", "<p>The owner page was not found.</p>", owner, 404);
  } catch (error) {
    if (error instanceof HttpError) {
      return adminPage(
        "Could not save",
        `<p role="alert">${escapeHtml(error.message)}</p><p><a href="${escapeHtml(path)}">Go back</a></p>`,
        owner,
        error.status,
      );
    }
    throw error;
  }
}
