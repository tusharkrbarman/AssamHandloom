import { HttpError } from "./http";

export type PublicationState = "draft" | "published";
export type ProductSort = "featured" | "newest" | "price_asc" | "price_desc";

export interface ProductListQuery {
  search: string | null;
  silkType: string | null;
  colour: string | null;
  occasion: string | null;
  availableOnly: boolean;
  sort: ProductSort;
  page: number;
  pageSize: number;
  collectionSlug: string | null;
}

export interface ProductCard {
  id: string;
  slug: string;
  title: string;
  silkType: string;
  colour: string | null;
  priceMinor: number;
  currency: string;
  available: boolean;
  mediaId: string | null;
  altText: string | null;
}

export interface ProductDetail extends ProductCard {
  description: string;
  occasion: string | null;
  variants: Array<{
    id: string;
    sku: string;
    title: string;
    priceMinor: number;
    currency: string;
    weightGrams: number | null;
    available: boolean;
  }>;
  media: Array<{
    id: string;
    altText: string;
  }>;
}

export interface CollectionSummary {
  id: string;
  slug: string;
  title: string;
  description: string;
}

export interface Page<T> {
  items: T[];
  page: number;
  pageSize: number;
  total: number;
}

interface ProductCardRow {
  id: string;
  slug: string;
  title: string;
  silk_type: string;
  colour: string | null;
  price_minor: number;
  currency: string;
  available: number;
  media_id: string | null;
  alt_text: string | null;
}

interface ProductDetailRow extends ProductCardRow {
  description: string;
  occasion: string | null;
}

interface VariantRow {
  id: string;
  sku: string;
  title: string;
  price_minor: number;
  currency: string;
  weight_grams: number | null;
  available: number;
}

interface MediaRow {
  id: string;
  alt_text: string;
}

interface CountRow {
  total: number;
}

const SORTS: ReadonlySet<string> = new Set([
  "featured",
  "newest",
  "price_asc",
  "price_desc",
]);

function positiveInteger(value: string | null, fallback: number): number {
  if (value === null || !/^\d+$/.test(value)) {
    return fallback;
  }
  return Math.max(1, Number.parseInt(value, 10));
}

function normalized(value: string | null): string | null {
  const result = (value ?? "").trim().replace(/\s+/g, " ");
  return result || null;
}

export function parseProductListQuery(
  url: URL,
  strictSort = false,
  collectionSlug: string | null = null,
): ProductListQuery {
  const requestedSort = url.searchParams.get("sort") ?? "featured";
  if (strictSort && !SORTS.has(requestedSort)) {
    throw new HttpError(422, "invalid_sort", "The requested sort value is not supported.");
  }
  const sort = (SORTS.has(requestedSort) ? requestedSort : "featured") as ProductSort;
  return {
    search: normalized(url.searchParams.get("search") ?? url.searchParams.get("q")),
    silkType: normalized(url.searchParams.get("silk_type")),
    colour: normalized(url.searchParams.get("colour")),
    occasion: normalized(url.searchParams.get("occasion")),
    availableOnly: ["1", "true", "yes", "on"].includes(
      (url.searchParams.get("available_only") ?? "").toLowerCase(),
    ),
    sort,
    page: positiveInteger(url.searchParams.get("page"), 1),
    pageSize: Math.min(24, positiveInteger(url.searchParams.get("page_size"), 12)),
    collectionSlug,
  };
}

function escapedLike(value: string): string {
  return value.replace(/[\\%_]/g, (character) => `\\${character}`);
}

function visibleProductFilters(query: ProductListQuery): {
  where: string;
  bindings: Array<string | number>;
} {
  const clauses = [
    "p.publication_state = 'published'",
    "p.archived_at IS NULL",
  ];
  const bindings: Array<string | number> = [];

  if (query.search) {
    const value = `%${escapedLike(query.search)}%`;
    clauses.push(
      "(p.title LIKE ? ESCAPE '\\' OR p.description LIKE ? ESCAPE '\\' OR p.silk_type LIKE ? ESCAPE '\\')",
    );
    bindings.push(value, value, value);
  }
  if (query.silkType) {
    clauses.push("p.silk_type = ?");
    bindings.push(query.silkType);
  }
  if (query.colour) {
    clauses.push("p.colour = ?");
    bindings.push(query.colour);
  }
  if (query.occasion) {
    clauses.push("p.occasion = ?");
    bindings.push(query.occasion);
  }
  if (query.availableOnly) {
    clauses.push(
      `EXISTS (
        SELECT 1
        FROM variants available_variant
        JOIN inventory_items available_stock
          ON available_stock.variant_id = available_variant.id
        WHERE available_variant.product_id = p.id
          AND available_variant.publication_state = 'published'
          AND available_stock.quantity > 0
      )`,
    );
  }
  if (query.collectionSlug) {
    clauses.push(
      `EXISTS (
        SELECT 1
        FROM collection_products membership
        JOIN collections collection ON collection.id = membership.collection_id
        WHERE membership.product_id = p.id
          AND collection.slug = ?
          AND collection.publication_state = 'published'
      )`,
    );
    bindings.push(query.collectionSlug);
  }
  return { where: clauses.join(" AND "), bindings };
}

function productOrder(sort: ProductSort): string {
  switch (sort) {
    case "newest":
      return "p.created_at DESC, p.id ASC";
    case "price_asc":
      return "chosen_variant.price_minor ASC, p.id ASC";
    case "price_desc":
      return "chosen_variant.price_minor DESC, p.id ASC";
    default:
      return "p.featured_rank ASC, p.created_at DESC, p.id ASC";
  }
}

function toProductCard(row: ProductCardRow): ProductCard {
  return {
    id: row.id,
    slug: row.slug,
    title: row.title,
    silkType: row.silk_type,
    colour: row.colour,
    priceMinor: row.price_minor,
    currency: row.currency,
    available: row.available === 1,
    mediaId: row.media_id,
    altText: row.alt_text,
  };
}

export async function listProducts(
  db: D1Database,
  query: ProductListQuery,
): Promise<Page<ProductCard>> {
  const { where, bindings } = visibleProductFilters(query);
  const visibleVariantJoin = `JOIN variants chosen_variant ON chosen_variant.id = (
    SELECT candidate.id
    FROM variants candidate
    WHERE candidate.product_id = p.id
      AND candidate.publication_state = 'published'
    ORDER BY candidate.price_minor ASC, candidate.id ASC
    LIMIT 1
  )`;
  const count = await db
    .prepare(`SELECT COUNT(*) AS total FROM products p ${visibleVariantJoin} WHERE ${where}`)
    .bind(...bindings)
    .first<CountRow>();
  const total = count?.total ?? 0;
  const offset = (query.page - 1) * query.pageSize;
  const statement = db
    .prepare(
      `SELECT
        p.id,
        p.slug,
        p.title,
        p.silk_type,
        p.colour,
        chosen_variant.price_minor,
        chosen_variant.currency,
        EXISTS (
          SELECT 1
          FROM variants available_variant
          JOIN inventory_items available_stock
            ON available_stock.variant_id = available_variant.id
          WHERE available_variant.product_id = p.id
            AND available_variant.publication_state = 'published'
            AND available_stock.quantity > 0
        ) AS available,
        primary_media.id AS media_id,
        primary_media.alt_text
      FROM products p
      ${visibleVariantJoin}
      LEFT JOIN product_media primary_media ON primary_media.id = (
        SELECT media.id
        FROM product_media media
        WHERE media.product_id = p.id
        ORDER BY media.display_order ASC, media.id ASC
        LIMIT 1
      )
      WHERE ${where}
      ORDER BY ${productOrder(query.sort)}
      LIMIT ? OFFSET ?`,
    )
    .bind(...bindings, query.pageSize, offset);
  const result = await statement.all<ProductCardRow>();
  return {
    items: result.results.map(toProductCard),
    page: query.page,
    pageSize: query.pageSize,
    total,
  };
}

export async function getProduct(
  db: D1Database,
  slug: string,
): Promise<ProductDetail | null> {
  const row = await db
    .prepare(
      `SELECT
        p.id,
        p.slug,
        p.title,
        p.description,
        p.silk_type,
        p.colour,
        p.occasion,
        chosen_variant.price_minor,
        chosen_variant.currency,
        EXISTS (
          SELECT 1
          FROM variants available_variant
          JOIN inventory_items available_stock
            ON available_stock.variant_id = available_variant.id
          WHERE available_variant.product_id = p.id
            AND available_variant.publication_state = 'published'
            AND available_stock.quantity > 0
        ) AS available,
        primary_media.id AS media_id,
        primary_media.alt_text
      FROM products p
      JOIN variants chosen_variant ON chosen_variant.id = (
        SELECT candidate.id
        FROM variants candidate
        WHERE candidate.product_id = p.id
          AND candidate.publication_state = 'published'
        ORDER BY candidate.price_minor ASC, candidate.id ASC
        LIMIT 1
      )
      LEFT JOIN product_media primary_media ON primary_media.id = (
        SELECT media.id
        FROM product_media media
        WHERE media.product_id = p.id
        ORDER BY media.display_order ASC, media.id ASC
        LIMIT 1
      )
      WHERE p.slug = ?
        AND p.publication_state = 'published'
        AND p.archived_at IS NULL`,
    )
    .bind(slug)
    .first<ProductDetailRow>();
  if (!row) {
    return null;
  }
  const batch = await db.batch([
    db
      .prepare(
        `SELECT
          variant.id,
          variant.sku,
          variant.title,
          variant.price_minor,
          variant.currency,
          variant.weight_grams,
          COALESCE(stock.quantity, 0) > 0 AS available
        FROM variants variant
        LEFT JOIN inventory_items stock ON stock.variant_id = variant.id
        WHERE variant.product_id = ?
          AND variant.publication_state = 'published'
        ORDER BY variant.price_minor ASC, variant.id ASC`,
      )
      .bind(row.id),
    db
      .prepare(
        `SELECT id, alt_text
        FROM product_media
        WHERE product_id = ?
        ORDER BY display_order ASC, id ASC`,
      )
      .bind(row.id),
  ]);
  const variantResult = batch[0];
  const mediaResult = batch[1];
  if (!variantResult || !mediaResult) {
    throw new HttpError(500, "catalogue_read_failed", "The product details are unavailable.");
  }
  const variants = (variantResult.results as unknown as VariantRow[]).map((variant) => ({
    id: variant.id,
    sku: variant.sku,
    title: variant.title,
    priceMinor: variant.price_minor,
    currency: variant.currency,
    weightGrams: variant.weight_grams,
    available: variant.available === 1,
  }));
  const media = (mediaResult.results as unknown as MediaRow[]).map((item) => ({
    id: item.id,
    altText: item.alt_text,
  }));
  return {
    ...toProductCard(row),
    description: row.description,
    occasion: row.occasion,
    variants,
    media,
  };
}

export async function listCollections(db: D1Database): Promise<CollectionSummary[]> {
  const result = await db
    .prepare(
      `SELECT id, slug, title, description
      FROM collections
      WHERE publication_state = 'published'
      ORDER BY display_order ASC, id ASC`,
    )
    .all<CollectionSummary>();
  return result.results;
}

export function formatMoney(priceMinor: number, currency: string): string {
  if (!Number.isSafeInteger(priceMinor) || priceMinor < 0) {
    throw new HttpError(500, "invalid_price", "The product price is unavailable.");
  }
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency,
    minimumFractionDigits: priceMinor % 100 === 0 ? 0 : 2,
    maximumFractionDigits: 2,
  }).format(priceMinor / 100);
}
