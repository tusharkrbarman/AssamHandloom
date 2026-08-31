import { adminPage } from "./admin";
import { AuthenticatedOwner, requireCsrf, requireOwner } from "./auth";
import { formatMoney } from "./catalogue";
import { enqueueOrderEmail } from "./email";
import { escapeHtml, HttpError, readForm, redirect } from "./http";
import { refundOrderPayment, RefundRow } from "./refunds";
import { settleOrderStock } from "./settlement";

const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

const STATUS_LABELS: Record<string, string> = {
  pending: "Awaiting payment",
  paid: "Paid",
  fulfilled: "Shipped",
  cancelled: "Cancelled",
  expired: "Expired",
};

const NEXT_ACTIONS: Record<string, Array<{ to: string; label: string }>> = {
  pending: [
    { to: "paid", label: "Mark as paid" },
    { to: "cancelled", label: "Cancel order" },
  ],
  paid: [
    { to: "fulfilled", label: "Mark as shipped" },
    { to: "cancelled", label: "Cancel order" },
  ],
  fulfilled: [],
  cancelled: [],
  expired: [],
};

const FILTERS = ["all", "pending", "paid", "fulfilled", "cancelled", "expired"] as const;

interface OrderListRow {
  id: string;
  email: string;
  ship_name: string;
  status: string;
  currency: string;
  total_minor: number;
  refunded_minor: number;
  created_at: string;
}

interface OrderDetailRow {
  id: string;
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
  updated_at: string;
}

interface OrderItemRow {
  product_title: string;
  variant_title: string;
  sku: string;
  quantity: number;
  unit_price_minor: number;
  currency: string;
  line_total_minor: number;
}

interface OrderPaymentRow {
  id: string;
  provider_order_id: string;
  provider_payment_id: string | null;
  amount_minor: number;
  currency: string;
  status: string;
  failure_reason: string | null;
}

function shortReference(orderId: string): string {
  return orderId.slice(0, 8).toUpperCase();
}

function shortTime(iso: string): string {
  return iso.slice(0, 16).replace("T", " ");
}

async function ordersListPage(
  env: Env,
  owner: AuthenticatedOwner,
  filter: (typeof FILTERS)[number],
): Promise<Response> {
  const statement =
    filter === "all"
      ? env.DB.prepare(
          `SELECT o.id, o.email, o.ship_name, o.status, o.currency, o.total_minor,
          COALESCE((SELECT SUM(r.amount_minor) FROM order_refunds r WHERE r.order_id = o.id AND r.status = 'processed'), 0) AS refunded_minor,
          o.created_at
          FROM orders o ORDER BY o.created_at DESC LIMIT 200`,
        )
      : env.DB.prepare(
          `SELECT o.id, o.email, o.ship_name, o.status, o.currency, o.total_minor,
          COALESCE((SELECT SUM(r.amount_minor) FROM order_refunds r WHERE r.order_id = o.id AND r.status = 'processed'), 0) AS refunded_minor,
          o.created_at
          FROM orders o WHERE o.status = ? ORDER BY o.created_at DESC LIMIT 200`,
        ).bind(filter);
  const result = await statement.all<OrderListRow>();
  const filters = FILTERS.map(
    (value) =>
      `<a href="/admin/orders${value === "all" ? "" : `?status=${value}`}"${
        value === filter ? ' aria-current="page"' : ""
      }>${value === "all" ? "All" : STATUS_LABELS[value]}</a>`,
  ).join(" · ");
  const rows = (result.results ?? [])
    .map(
      (order) => {
        const refunded = order.refunded_minor >= order.total_minor && order.total_minor > 0;
        return `<tr>
        <td><a href="/admin/orders/${order.id}">${escapeHtml(shortReference(order.id))}</a></td>
        <td>${escapeHtml(order.ship_name)}</td>
        <td>${escapeHtml(order.email)}</td>
        <td>${refunded ? "Refunded" : escapeHtml(STATUS_LABELS[order.status] ?? order.status)}</td>
        <td>${escapeHtml(formatMoney(order.total_minor, order.currency))}</td>
        <td>${escapeHtml(shortTime(order.created_at))}</td>
      </tr>`;
      },
    )
    .join("");
  return adminPage(
    "Orders",
    `<p>${filters}</p>
    <table><thead><tr><th>Reference</th><th>Customer</th><th>Email</th><th>Status</th><th>Total</th><th>Placed</th></tr></thead>
    <tbody>${rows || '<tr><td colspan="6">No orders yet.</td></tr>'}</tbody></table>`,
    owner,
  );
}

function actionForms(
  order: OrderDetailRow,
  csrf: string,
): string {
  const actions = NEXT_ACTIONS[order.status] ?? [];
  return actions
    .map(
      (action) => `<form method="post" action="/admin/orders/${order.id}/status">
        <input type="hidden" name="csrf" value="${escapeHtml(csrf)}">
        <input type="hidden" name="status" value="${action.to}">
        <button type="submit">${escapeHtml(action.label)}</button>
      </form>`,
    )
    .join(" ");
}

async function orderDetailPage(
  env: Env,
  owner: AuthenticatedOwner,
  orderId: string,
): Promise<Response> {
  if (!UUID_PATTERN.test(orderId)) {
    throw new HttpError(404, "not_found", "That order could not be found.");
  }
  const [orderResult, itemResult, paymentResult, refundResult] = await env.DB.batch([
    env.DB.prepare("SELECT * FROM orders WHERE id = ?").bind(orderId),
    env.DB.prepare(
      `SELECT product_title, variant_title, sku, quantity, unit_price_minor, currency, line_total_minor
      FROM order_items WHERE order_id = ? ORDER BY created_at ASC, id ASC`,
    ).bind(orderId),
    env.DB.prepare(
      `SELECT id, provider_order_id, provider_payment_id, amount_minor, currency, status, failure_reason
      FROM order_payments WHERE order_id = ? ORDER BY created_at DESC`,
    ).bind(orderId),
    env.DB.prepare(
      `SELECT id, payment_id, provider_refund_id, amount_minor, currency, status, created_at
      FROM order_refunds WHERE order_id = ? ORDER BY created_at DESC`,
    ).bind(orderId),
  ]);
  const order = orderResult?.results?.[0] as unknown as OrderDetailRow | undefined;
  if (!order) {
    throw new HttpError(404, "not_found", "That order could not be found.");
  }
  const items = (itemResult?.results ?? []) as unknown as OrderItemRow[];
  const payments = (paymentResult?.results ?? []) as unknown as OrderPaymentRow[];
  const refunds = (refundResult?.results ?? []) as unknown as RefundRow[];
  const refundedTotal = refunds
    .filter((refund) => refund.status !== "failed")
    .reduce((sum, refund) => sum + refund.amount_minor, 0);
  const capturedPayment = payments.find(
    (payment) => payment.status === "captured" && payment.provider_payment_id,
  );
  const canRefund =
    capturedPayment !== undefined &&
    refundedTotal < (capturedPayment?.amount_minor ?? 0);
  const paymentReview =
    capturedPayment !== undefined && !["paid", "fulfilled"].includes(order.status)
      ? '<p role="alert"><strong>Payment requires review.</strong> Money was captured after this order closed; refund it unless fulfilment is confirmed manually.</p>'
      : "";

  const itemRows = items
    .map(
      (item) => `<tr>
        <td>${escapeHtml(item.product_title)} · ${escapeHtml(item.variant_title)}<br><small>${escapeHtml(item.sku)}</small></td>
        <td>${item.quantity}</td>
        <td>${escapeHtml(formatMoney(item.unit_price_minor, item.currency))}</td>
        <td>${escapeHtml(formatMoney(item.line_total_minor, item.currency))}</td>
      </tr>`,
    )
    .join("");
  const paymentRows = payments
    .map(
      (payment) => `<tr>
        <td>${escapeHtml(payment.provider_order_id)}</td>
        <td>${escapeHtml(payment.provider_payment_id ?? "—")}</td>
        <td>${escapeHtml(payment.status)}</td>
        <td>${escapeHtml(formatMoney(payment.amount_minor, payment.currency))}</td>
        <td>${escapeHtml(payment.failure_reason ?? "")}</td>
      </tr>`,
    )
    .join("");
  const refundRows = refunds
    .map(
      (refund) => `<tr>
        <td>${escapeHtml(refund.provider_refund_id)}</td>
        <td>${escapeHtml(refund.status)}</td>
        <td>${escapeHtml(formatMoney(refund.amount_minor, refund.currency))}</td>
        <td>${escapeHtml(shortTime(refund.created_at))}</td>
      </tr>`,
    )
    .join("");
  const refundSection =
    capturedPayment === undefined
      ? "<p>No captured online payment to refund.</p>"
      : `${refundRows
          ? `<table><thead><tr><th>Refund</th><th>Status</th><th>Amount</th><th>Time</th></tr></thead>
          <tbody>${refundRows}</tbody></table>`
          : "<p>No refunds issued yet.</p>"
        }${
          canRefund && capturedPayment
            ? `<form method="post" action="/admin/orders/${order.id}/refund">
          <input type="hidden" name="csrf" value="${escapeHtml(owner.session.csrf)}">
          <label>Amount in paise <input name="amount_minor" type="number" min="1" max="${capturedPayment.amount_minor - refundedTotal}" placeholder="leave blank for full refund"></label>
          <button type="submit">Issue refund</button>
        </form>`
            : ""
        }`;
  return adminPage(
    `Order ${shortReference(order.id)}`,
    `<p>Status <strong>${escapeHtml(STATUS_LABELS[order.status] ?? order.status)}</strong> ·
    Placed ${escapeHtml(shortTime(order.created_at))} · Updated ${escapeHtml(shortTime(order.updated_at))}</p>
    <h2>Fulfilment</h2>
    ${actionForms(order, owner.session.csrf) || "<p>This order is closed; no further changes are available.</p>"}
    <h2>Items</h2>
    <table><thead><tr><th>Item</th><th>Qty</th><th>Each</th><th>Total</th></tr></thead>
    <tbody>${itemRows || '<tr><td colspan="4">No items recorded.</td></tr>'}</tbody></table>
    <p>Subtotal ${escapeHtml(formatMoney(order.subtotal_minor, order.currency))}<br>
    Shipping ${order.shipping_minor === 0 ? "Free" : escapeHtml(formatMoney(order.shipping_minor, order.currency))}<br>
    <strong>Total ${escapeHtml(formatMoney(order.total_minor, order.currency))}</strong></p>
    <h2>Customer</h2>
    <p><a href="mailto:${escapeHtml(order.email)}">${escapeHtml(order.email)}</a><br>${escapeHtml(order.ship_phone)}</p>
    <h2>Shipping address</h2>
    <p>${escapeHtml(order.ship_name)}<br>${escapeHtml(order.ship_address1)}${
      order.ship_address2 ? `<br>${escapeHtml(order.ship_address2)}` : ""
    }<br>${escapeHtml(order.ship_city)}, ${escapeHtml(order.ship_state)} ${escapeHtml(order.ship_postal_code)}<br>${escapeHtml(order.ship_country)}</p>
    <h2>Payments</h2>
    <table><thead><tr><th>Provider order</th><th>Payment</th><th>Status</th><th>Amount</th><th>Note</th></tr></thead>
    <tbody>${paymentRows || '<tr><td colspan="5">No online payments recorded.</td></tr>'}</tbody></table>
    <h2>Refunds</h2>
    ${paymentReview}
    ${refundSection}
    <p><a href="/admin/orders">Back to all orders</a></p>`,
    owner,
  );
}

async function handleRefund(
  request: Request,
  env: Env,
  owner: AuthenticatedOwner,
  orderId: string,
): Promise<Response> {
  const form = await readForm(request);
  await requireCsrf(request, owner.session, form);
  const raw = form.get("amount_minor");
  const amountMinor =
    typeof raw === "string" && raw.trim() !== "" && /^-?\d+$/.test(raw.trim())
      ? Number.parseInt(raw.trim(), 10)
      : null;
  await refundOrderPayment(env.DB, env, orderId, amountMinor);
  return redirect(`/admin/orders/${orderId}`);
}

export async function changeOrderStatus(
  db: D1Database,
  orderId: string,
  next: string,
): Promise<void> {
  const validTargets = new Set(
    Object.values(NEXT_ACTIONS).flatMap((actions) => actions.map((action) => action.to)),
  );
  if (!UUID_PATTERN.test(orderId) || !validTargets.has(next)) {
    throw new HttpError(422, "invalid_order_status", "That status change is not offered.");
  }
  const order = await db
    .prepare("SELECT status FROM orders WHERE id = ?")
    .bind(orderId)
    .first<{ status: string }>();
  if (!order) {
    throw new HttpError(404, "not_found", "That order could not be found.");
  }
  const permitted = (NEXT_ACTIONS[order.status] ?? []).some((action) => action.to === next);
  if (!permitted) {
    throw new HttpError(
      409,
      "invalid_status_transition",
      `An order marked ${STATUS_LABELS[order.status] ?? order.status} cannot move there.`,
    );
  }
  const at = new Date().toISOString();
  if (next === "paid") {
    const outcome = await settleOrderStock(db, orderId, "owner");
    if (outcome !== "paid") {
      throw new HttpError(
        409,
        "reservation_expired",
        "The reservation is no longer available, so this order cannot be marked paid.",
      );
    }
    return;
  }
  const update = await db
    .prepare("UPDATE orders SET status = ?, updated_at = ? WHERE id = ? AND status = ?")
    .bind(next, at, orderId, order.status)
    .run();
  if ((update.meta.changes ?? 0) === 0) {
    throw new HttpError(409, "order_conflict", "The order changed before this update completed.");
  }
  if (next === "cancelled") {
    await db
      .prepare("UPDATE inventory_reservations SET state = 'released' WHERE order_id = ? AND state = 'active'")
      .bind(orderId)
      .run();
  }
}

async function handleStatusChange(
  request: Request,
  env: Env,
  owner: AuthenticatedOwner,
  orderId: string,
): Promise<Response> {
  const form = await readForm(request);
  await requireCsrf(request, owner.session, form);
  const next = form.get("status");
  await changeOrderStatus(env.DB, orderId, typeof next === "string" ? next : "");
  if (next === "fulfilled") {
    await enqueueOrderEmail(env.DB, env, "order_shipped", orderId);
  }
  return redirect(`/admin/orders/${orderId}`);
}

export async function routeAdminOrders(
  request: Request,
  env: Env,
): Promise<Response | null> {
  const path = new URL(request.url).pathname;
  if (!path.startsWith("/admin/orders")) return null;

  let owner: AuthenticatedOwner;
  try {
    owner = await requireOwner(request, env);
  } catch (error) {
    if (error instanceof HttpError && error.status === 401) return redirect("/admin/login");
    throw error;
  }

  try {
    if (request.method === "GET" && path === "/admin/orders") {
      const requested = new URL(request.url).searchParams.get("status") ?? "all";
      const filter = (FILTERS as readonly string[]).includes(requested)
        ? (requested as (typeof FILTERS)[number])
        : "all";
      return ordersListPage(env, owner, filter);
    }
    const statusMatch = path.match(/^\/admin\/orders\/([0-9a-f-]+)\/status$/i);
    if (request.method === "POST" && statusMatch?.[1]) {
      return handleStatusChange(request, env, owner, statusMatch[1]);
    }
    const refundMatch = path.match(/^\/admin\/orders\/([0-9a-f-]+)\/refund$/i);
    if (request.method === "POST" && refundMatch?.[1]) {
      return handleRefund(request, env, owner, refundMatch[1]);
    }
    const detailMatch = path.match(/^\/admin\/orders\/([0-9a-f-]+)$/i);
    if (request.method === "GET" && detailMatch?.[1]) {
      return orderDetailPage(env, owner, detailMatch[1]);
    }
    return adminPage("Not found", "<p>The orders page was not found.</p>", owner, 404);
  } catch (error) {
    if (error instanceof HttpError) {
      return adminPage(
        "Could not update the order",
        `<p role="alert">${escapeHtml(error.message)}</p><p><a href="/admin/orders">Go back</a></p>`,
        owner,
        error.status,
      );
    }
    throw error;
  }
}
