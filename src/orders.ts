import { formatMoney } from "./catalogue";
import {
  escapeHtml,
  HttpError,
  json,
  readForm,
  redirect,
  requireSameOrigin,
} from "./http";
import { razorpayConfig } from "./payments";
import { enqueueOrderEmail } from "./email";
import { verifyOrderLink } from "./links";
import { optionalMemberEmail } from "./customers";
import { shell } from "./storefront";

const MAX_LINES = 20;
const MAX_QUANTITY_PER_LINE = 10;
const RESERVATION_MINUTES = 30;
const COUNTRIES: ReadonlySet<string> = new Set(["AU", "CA", "DE", "GB", "IN", "SG", "US"]);
const STATUS_LABELS: Record<string, string> = {
  pending: "Awaiting payment",
  paid: "Payment received",
  fulfilled: "On its way",
  cancelled: "Cancelled",
  expired: "Expired",
};

interface CartInputLine {
  variantId: string;
  quantity: number;
}

interface QuotedLine {
  variantId: string;
  sku: string;
  productTitle: string;
  variantTitle: string;
  quantity: number;
  unitPriceMinor: number;
  unitPriceFormatted: string;
  lineTotalMinor: number;
  lineTotalFormatted: string;
  available: boolean;
}

interface CartQuote {
  currency: string;
  lines: QuotedLine[];
  subtotalMinor: number;
  subtotalFormatted: string;
  allAvailable: boolean;
}

interface CheckoutInput {
  items: CartInputLine[];
  email: string;
  name: string;
  phone: string;
  address1: string;
  address2: string | null;
  city: string;
  state: string;
  postalCode: string;
  country: string;
}

interface OrderRecord {
  id: string;
  status: string;
  statusLabel: string;
  currency: string;
  subtotalMinor: number;
  subtotalFormatted: string;
  shippingMinor: number;
  totalMinor: number;
  totalFormatted: string;
  shipName: string;
  shipAddress1: string;
  shipAddress2: string | null;
  shipCity: string;
  shipState: string;
  shipPostalCode: string;
  shipCountry: string;
  createdAt: string;
}

interface OrderItemSnapshot {
  productTitle: string;
  variantTitle: string;
  sku: string;
  quantity: number;
  unitPriceMinor: number;
  unitPriceFormatted: string;
  lineTotalMinor: number;
  lineTotalFormatted: string;
}

interface VariantStockRow {
  id: string;
  sku: string;
  variant_title: string;
  product_title: string;
  price_minor: number;
  currency: string;
  quantity: number;
  reserved: number;
}

interface OrderRow {
  id: string;
  token: string;
  email: string;
  status: string;
  currency: string;
  subtotal_minor: number;
  shipping_minor: number;
  total_minor: number;
  ship_name: string;
  ship_phone: string;
  ship_address1: string;
  ship_address2: string | null;
  ship_city: string;
  ship_state: string;
  ship_postal_code: string;
  ship_country: string;
  created_at: string;
}

interface OrderItemRow {
  product_title: string;
  variant_title: string;
  sku: string;
  unit_price_minor: number;
  currency: string;
  quantity: number;
  line_total_minor: number;
}

function nowIso(): string {
  return new Date().toISOString();
}

function parseCartItems(value: unknown): CartInputLine[] {
  if (!Array.isArray(value) || value.length === 0 || value.length > MAX_LINES) {
    throw new HttpError(
      422,
      "invalid_cart",
      `The bag must contain between 1 and ${MAX_LINES} distinct items.`,
    );
  }
  const quantities = new Map<string, { id: string; quantity: number }>();
  for (const entry of value) {
    if (typeof entry !== "object" || entry === null) {
      throw new HttpError(422, "invalid_cart", "The bag could not be read.");
    }
    const record = entry as Record<string, unknown>;
    const variantId = typeof record.variantId === "string" ? record.variantId.trim() : "";
    if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(variantId)) {
      throw new HttpError(422, "invalid_cart", "A bag item reference is invalid.");
    }
    const quantity =
      typeof record.quantity === "number" ? Math.floor(record.quantity) : Number.NaN;
    if (!Number.isSafeInteger(quantity) || quantity < 1 || quantity > MAX_QUANTITY_PER_LINE) {
      throw new HttpError(
        422,
        "invalid_cart",
        `Each item quantity must be between 1 and ${MAX_QUANTITY_PER_LINE}.`,
      );
    }
    const key = variantId.toLowerCase();
    const existing = quantities.get(key);
    if (existing) {
      existing.quantity += quantity;
      if (existing.quantity > MAX_QUANTITY_PER_LINE) {
        throw new HttpError(
          422,
          "invalid_cart",
          `Each item is limited to ${MAX_QUANTITY_PER_LINE} per order.`,
        );
      }
    } else {
      quantities.set(key, { id: variantId, quantity });
    }
  }
  return [...quantities.values()].map(({ id, quantity }) => ({ variantId: id, quantity }));
}

async function readJson(request: Request): Promise<unknown> {
  const contentType = request.headers.get("content-type")?.toLowerCase() ?? "";
  if (!contentType.startsWith("application/json")) {
    throw new HttpError(415, "unsupported_media_type", "A JSON body is required.");
  }
  try {
    return await request.json();
  } catch {
    throw new HttpError(400, "invalid_json", "The request body could not be read.");
  }
}

function parseCheckoutFields(form: FormData): CheckoutInput {
  let items: CartInputLine[];
  try {
    items = parseCartItems(JSON.parse((form.get("items") ?? "").toString() || "null"));
  } catch (error) {
    if (error instanceof HttpError) throw error;
    throw new HttpError(422, "invalid_cart", "Your bag could not be read.");
  }
  const text = (name: string, maximum: number, label: string, minimumLength = 2): string => {
    const clean = (form.get(name) ?? "").toString().trim().replace(/\s+/g, " ");
    if (clean.length < minimumLength || clean.length > maximum) {
      throw new HttpError(422, "invalid_checkout_field", `${label} is invalid.`);
    }
    return clean;
  };
  const optionalText = (name: string, maximum: number): string | null => {
    const clean = (form.get(name) ?? "").toString().trim().replace(/\s+/g, " ");
    if (!clean) return null;
    if (clean.length > maximum) {
      throw new HttpError(422, "invalid_checkout_field", "The address line is too long.");
    }
    return clean;
  };
  const email = (form.get("email") ?? "").toString().trim();
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(email) || email.length > 254) {
    throw new HttpError(422, "invalid_checkout_field", "Email is invalid.");
  }
  const phone = text("phone", 20, "Phone", 6);
  if (!/^[+0-9][0-9 ()-]+$/.test(phone)) {
    throw new HttpError(422, "invalid_checkout_field", "Phone is invalid.");
  }
  const country = (form.get("country") ?? "IN").toString().trim().toUpperCase();
  if (!COUNTRIES.has(country)) {
    throw new HttpError(422, "unsupported_country", "We do not currently ship there.");
  }
  return {
    items,
    email,
    name: text("name", 160, "Full name"),
    phone,
    address1: text("address1", 200, "Address"),
    address2: optionalText("address2", 200),
    city: text("city", 100, "City"),
    state: text("state", 100, "State"),
    postalCode: text("postal_code", 20, "Postal code", 3),
    country,
  };
}

async function loadVariantStock(
  db: D1Database,
  items: CartInputLine[],
): Promise<Map<string, VariantStockRow>> {
  const placeholders = items.map(() => "?").join(", ");
  const result = await db
    .prepare(
      `WITH active_reserved AS (
        SELECT variant_id, SUM(quantity) AS reserved
        FROM inventory_reservations
        WHERE state = 'active' AND expires_at > ?
        GROUP BY variant_id
      )
      SELECT
        v.id,
        v.sku,
        v.title AS variant_title,
        p.title AS product_title,
        v.price_minor,
        v.currency,
        COALESCE(stock.quantity, 0) AS quantity,
        COALESCE(ar.reserved, 0) AS reserved
      FROM variants v
      JOIN products p ON p.id = v.product_id
      LEFT JOIN inventory_items stock ON stock.variant_id = v.id
      LEFT JOIN active_reserved ar ON ar.variant_id = v.id
      WHERE v.id IN (${placeholders})
        AND v.publication_state = 'published'
        AND p.publication_state = 'published'
        AND p.archived_at IS NULL`,
    )
    .bind(nowIso(), ...items.map((item) => item.variantId))
    .all<VariantStockRow>();
  return new Map(result.results.map((row) => [row.id.toLowerCase(), row]));
}

export async function quoteCart(db: D1Database, items: CartInputLine[]): Promise<CartQuote> {
  const stock = await loadVariantStock(db, items);
  const lines: QuotedLine[] = [];
  let currency: string | null = null;
  for (const item of items) {
    const row = stock.get(item.variantId.toLowerCase());
    if (!row) {
      throw new HttpError(404, "cart_item_unavailable", "An item in your bag is no longer offered.");
    }
    currency = currency ?? row.currency;
    if (currency !== row.currency) {
      throw new HttpError(409, "mixed_currency", "Your bag mixes currencies; please review it.");
    }
    const availableQuantity = Math.max(0, row.quantity - row.reserved);
    lines.push({
      variantId: row.id,
      sku: row.sku,
      productTitle: row.product_title,
      variantTitle: row.variant_title,
      quantity: item.quantity,
      unitPriceMinor: row.price_minor,
      unitPriceFormatted: formatMoney(row.price_minor, row.currency),
      lineTotalMinor: row.price_minor * item.quantity,
      lineTotalFormatted: formatMoney(row.price_minor * item.quantity, row.currency),
      available: availableQuantity >= item.quantity,
    });
  }
  const subtotalMinor = lines.reduce((sum, line) => sum + line.lineTotalMinor, 0);
  const resolvedCurrency = currency ?? "INR";
  return {
    currency: resolvedCurrency,
    lines,
    subtotalMinor,
    subtotalFormatted: formatMoney(subtotalMinor, resolvedCurrency),
    allAvailable: lines.every((line) => line.available),
  };
}

async function createOrderRecord(
  db: D1Database,
  input: CheckoutInput,
): Promise<{ orderId: string; token: string }> {
  const quote = await quoteCart(db, input.items);
  if (!quote.allAvailable) {
    throw new HttpError(
      409,
      "insufficient_stock",
      "One or more weaves in your bag just sold out. Please review your bag.",
    );
  }
  const orderId = crypto.randomUUID();
  const token = crypto.randomUUID();
  const createdAt = nowIso();
  const expiresAt = new Date(Date.now() + RESERVATION_MINUTES * 60_000).toISOString();
  try {
    await db.batch([
      db
        .prepare(
          `INSERT INTO orders (
            id, token, email, status, currency, subtotal_minor, shipping_minor, total_minor,
            ship_name, ship_phone, ship_address1, ship_address2, ship_city, ship_state,
            ship_postal_code, ship_country, created_at, updated_at
          ) VALUES (?, ?, ?, 'pending', ?, ?, 0, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
        )
        .bind(
          orderId,
          token,
          input.email,
          quote.currency,
          quote.subtotalMinor,
          quote.subtotalMinor,
          input.name,
          input.phone,
          input.address1,
          input.address2,
          input.city,
          input.state,
          input.postalCode,
          input.country,
          createdAt,
          createdAt,
        ),
      ...quote.lines.map((line) =>
        db
          .prepare(
            `INSERT INTO order_items (
              id, order_id, variant_id, product_title, variant_title, sku,
              unit_price_minor, currency, quantity, line_total_minor, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
          )
          .bind(
            crypto.randomUUID(),
            orderId,
            line.variantId,
            line.productTitle,
            line.variantTitle,
            line.sku,
            line.unitPriceMinor,
            quote.currency,
            line.quantity,
            line.lineTotalMinor,
            createdAt,
          ),
      ),
      ...quote.lines.map((line) =>
        db
          .prepare(
            `INSERT INTO inventory_reservations (
              id, order_id, variant_id, quantity, state, expires_at, created_at
            ) VALUES (?, ?, ?, ?, 'active', ?, ?)`,
          )
          .bind(crypto.randomUUID(), orderId, line.variantId, line.quantity, expiresAt, createdAt),
      ),
    ]);
  } catch (error) {
    if (error instanceof Error && /reservation_exceeds_available/.test(error.message)) {
      throw new HttpError(
        409,
        "insufficient_stock",
        "One or more weaves in your bag just sold out. Please review your bag.",
      );
    }
    throw new HttpError(409, "order_conflict", "Your order could not be completed. Please retry.");
  }
  return { orderId, token };
}

async function loadOrder(
  db: D1Database,
  orderId: string,
  token: string | null,
): Promise<{ order: OrderRecord; items: OrderItemSnapshot[] }> {
  if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(orderId)) {
    throw new HttpError(404, "not_found", "That order could not be found.");
  }
  const order = await db.prepare("SELECT * FROM orders WHERE id = ?").bind(orderId).first<OrderRow>();
  if (!order || (token !== null && order.token !== token)) {
    throw new HttpError(404, "not_found", "That order could not be found.");
  }
  const itemResult = await db
    .prepare(
      `SELECT product_title, variant_title, sku, unit_price_minor, currency, quantity, line_total_minor
      FROM order_items WHERE order_id = ?
      ORDER BY created_at ASC, id ASC`,
    )
    .bind(orderId)
    .all<OrderItemRow>();
  const items = itemResult.results.map((row) => ({
    productTitle: row.product_title,
    variantTitle: row.variant_title,
    sku: row.sku,
    quantity: row.quantity,
    unitPriceMinor: row.unit_price_minor,
    unitPriceFormatted: formatMoney(row.unit_price_minor, row.currency),
    lineTotalMinor: row.line_total_minor,
    lineTotalFormatted: formatMoney(row.line_total_minor, row.currency),
  }));
  return {
    order: {
      id: order.id,
      status: order.status,
      statusLabel: STATUS_LABELS[order.status] ?? "Processing",
      currency: order.currency,
      subtotalMinor: order.subtotal_minor,
      subtotalFormatted: formatMoney(order.subtotal_minor, order.currency),
      shippingMinor: order.shipping_minor,
      totalMinor: order.total_minor,
      totalFormatted: formatMoney(order.total_minor, order.currency),
      shipName: order.ship_name,
      shipAddress1: order.ship_address1,
      shipAddress2: order.ship_address2,
      shipCity: order.ship_city,
      shipState: order.ship_state,
      shipPostalCode: order.ship_postal_code,
      shipCountry: order.ship_country,
      createdAt: order.created_at,
    },
    items,
  };
}

function cartContent(): string {
  return `<section class="commerce-page">
  <p class="eyebrow">Your bag</p>
  <h1>Review your weaves</h1>
  <div id="cart-root"><p class="empty-state">Opening your bag…</p></div>
  <noscript><p class="empty-state">Please enable JavaScript to use the bag, or browse the <a href="/shop">catalogue</a>.</p></noscript>
</section>`;
}

function countryOptions(selected: string): string {
  return [...COUNTRIES]
    .sort()
    .map(
      (code) =>
        `<option value="${code}"${code === selected ? " selected" : ""}>${code === "IN" ? "India" : code}</option>`,
    )
    .join("");
}

function checkoutForm(
  fields?: Partial<CheckoutInput>,
  paymentsEnabled = false,
): string {
  const value = (name: keyof CheckoutInput): string => escapeHtml(String(fields?.[name] ?? ""));
  return `<form class="checkout-form" method="post" action="/checkout">
  <input type="hidden" name="items" id="checkout-items" value="">
  <div class="checkout-grid">
    <fieldset>
      <legend>Contact</legend>
      <label>Email<input name="email" type="email" autocomplete="email" required value="${value("email")}"></label>
      <label>Full name<input name="name" autocomplete="name" required value="${value("name")}"></label>
      <label>Phone<input name="phone" type="tel" autocomplete="tel" required value="${value("phone")}"></label>
    </fieldset>
    <fieldset>
      <legend>Shipping address</legend>
      <label>Address line 1<input name="address1" autocomplete="address-line1" required value="${value("address1")}"></label>
      <label>Address line 2 (optional)<input name="address2" autocomplete="address-line2" value="${value("address2")}"></label>
      <label>City<input name="city" autocomplete="address-level2" required value="${value("city")}"></label>
      <label>State<input name="state" autocomplete="address-level1" required value="${value("state")}"></label>
      <label>Postal code<input name="postal_code" autocomplete="postal-code" required value="${value("postalCode")}"></label>
      <label>Country<select name="country" autocomplete="country">${countryOptions(fields?.country ?? "IN")}</select></label>
    </fieldset>
    <aside class="checkout-summary">
      <h2>Order summary</h2>
      <div id="checkout-summary"><p class="empty-state">Reviewing your bag…</p></div>
    </aside>
  </div>
  <p class="order-note">Your weaves are held for ${RESERVATION_MINUTES} minutes once you place the order.
  ${paymentsEnabled
    ? "You can pay securely as soon as your order is placed."
    : "Online payments are not active yet — placing the order reserves stock and costs nothing."}</p>
  <button class="button" type="submit">Place order</button>
</form>`;
}

function checkoutContent(
  fields: Partial<CheckoutInput> | undefined,
  message: string | undefined,
  paymentsEnabled: boolean,
): string {
  return `<section class="commerce-page">
  <p class="eyebrow">Checkout preview</p>
  <h1>Complete your order</h1>
  ${message ? `<p class="form-alert" role="alert">${escapeHtml(message)}</p>` : ""}
  ${checkoutForm(fields, paymentsEnabled)}
  <noscript><p class="empty-state">This checkout needs JavaScript to attach your bag.</p></noscript>
</section>`;
}

function orderConfirmationContent(
  order: OrderRecord,
  items: OrderItemSnapshot[],
  paymentsEnabled: boolean,
): string {
  const rows = items
    .map(
      (item) => `<tr>
      <td>${escapeHtml(item.productTitle)} · ${escapeHtml(item.variantTitle)}<br><small>${escapeHtml(item.sku)}</small></td>
      <td>${item.quantity}</td>
      <td>${escapeHtml(item.unitPriceFormatted)}</td>
      <td>${escapeHtml(item.lineTotalFormatted)}</td>
    </tr>`,
    )
    .join("");
  return `<section class="commerce-page order-confirmation">
  <p class="eyebrow">Order received</p>
  <h1>Thank you — your weaves are reserved.</h1>
  <p>Reference <strong>${escapeHtml(order.id.slice(0, 8).toUpperCase())}</strong> ·
  Status: <strong>${escapeHtml(order.statusLabel)}</strong> · Placed ${escapeHtml(order.createdAt.slice(0, 10))}</p>
  <table class="bag-table">
    <thead><tr><th scope="col">Item</th><th scope="col">Qty</th><th scope="col">Each</th><th scope="col">Total</th></tr></thead>
    <tbody>${rows}</tbody>
  </table>
  <dl class="summary-totals">
    <div><dt>Subtotal</dt><dd>${escapeHtml(order.subtotalFormatted)}</dd></div>
    <div><dt>Shipping</dt><dd>${order.shippingMinor === 0 ? "Free" : escapeHtml(formatMoney(order.shippingMinor, order.currency))}</dd></div>
    <div><dt>Total</dt><dd>${escapeHtml(order.totalFormatted)}</dd></div>
  </dl>
  <section aria-labelledby="ship-to-title"><h2 id="ship-to-title">Delivering to</h2>
  <p>${escapeHtml(order.shipName)}<br>${escapeHtml(order.shipAddress1)}${order.shipAddress2 ? `<br>${escapeHtml(order.shipAddress2)}` : ""}<br>
  ${escapeHtml(order.shipCity)}, ${escapeHtml(order.shipState)} ${escapeHtml(order.shipPostalCode)}<br>${escapeHtml(order.shipCountry)}</p></section>
  ${
    paymentsEnabled && order.status === "pending"
      ? `<section class="pay-section" aria-labelledby="pay-title"><h2 id="pay-title">Complete payment</h2>
  <p class="order-note">Your weaves stay reserved for ${RESERVATION_MINUTES} minutes. Finish payment to confirm this order.</p>
  <button class="button" type="button" id="pay-now" data-order-id="${escapeHtml(order.id)}">Pay now</button>
  <p class="form-alert" id="pay-error" role="alert" hidden></p></section>
  <script src="https://checkout.razorpay.com/v1/checkout.js" defer></script>
  <script src="/js/pay.js" defer></script>`
      : `<p class="order-note">Online payments open with our next release. We will email a secure payment link to
  complete this order before the reservation window closes.</p>`
  }
</section>`;
}

async function renderCheckoutWithError(
  request: Request,
  form: FormData,
  error: HttpError,
  paymentsEnabled: boolean,
): Promise<Response> {
  let fields: Partial<CheckoutInput>;
  try {
    fields = parseCheckoutFields(form);
  } catch {
    fields = {};
  }
  return shell(request, "Checkout · Luit & Loom", checkoutContent(fields, error.message, paymentsEnabled), error.status);
}

export async function routeOrders(request: Request, env: Env): Promise<Response | null> {
  const url = new URL(request.url);
  const path = url.pathname;
  const paymentsEnabled = razorpayConfig(env) !== null;

  if (request.method === "GET" && path === "/cart") {
    return shell(request, "Your bag · Luit & Loom", cartContent());
  }

  if (request.method === "POST" && path === "/api/cart/quote") {
    requireSameOrigin(request);
    const body = await readJson(request);
    const items = parseCartItems((body as Record<string, unknown> | null)?.items);
    return json(await quoteCart(env.DB, items));
  }

  if (request.method === "GET" && path === "/checkout") {
    const memberEmail = await optionalMemberEmail(request, env);
    return shell(
      request,
      "Checkout · Luit & Loom",
      checkoutContent(memberEmail ? { email: memberEmail } : undefined, undefined, paymentsEnabled),
    );
  }

  if (request.method === "POST" && path === "/checkout") {
    requireSameOrigin(request);
    const form = await readForm(request);
    try {
      const fields = parseCheckoutFields(form);
      const { orderId, token } = await createOrderRecord(env.DB, fields);
      await enqueueOrderEmail(env.DB, env, "order_confirmation", orderId);
      return redirect(`/orders/${orderId}?token=${token}`);
    } catch (error) {
      if (error instanceof HttpError) {
        return renderCheckoutWithError(request, form, error, paymentsEnabled);
      }
      throw error;
    }
  }

  const orderMatch = /^\/orders\/([0-9a-f-]{36})$/i.exec(path);
  if (request.method === "GET" && orderMatch?.[1]) {
    const orderId = orderMatch[1];
    const tokenParam = url.searchParams.get("token");
    let authorized = tokenParam !== null;
    if (!authorized) {
      const expiresAt = Number(url.searchParams.get("exp"));
      authorized = await verifyOrderLink(
        env,
        orderId,
        expiresAt,
        url.searchParams.get("sig"),
      );
    }
    if (!authorized) {
      throw new HttpError(404, "not_found", "That order could not be found.");
    }
    const { order, items } = await loadOrder(env.DB, orderId, tokenParam);
    return shell(
      request,
      `Order ${order.id.slice(0, 8).toUpperCase()} · Luit & Loom`,
      orderConfirmationContent(order, items, paymentsEnabled),
    );
  }

  return null;
}
