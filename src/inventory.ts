import { adminPage } from "./admin";
import { AuthenticatedOwner, requireCsrf, requireOwner } from "./auth";
import { escapeHtml, HttpError, readForm, redirect } from "./http";

interface InventoryItem {
  variantId: string;
  sku: string;
  productTitle: string;
  quantity: number;
}

interface InventoryAdjustmentInput {
  variantId: string;
  delta: number;
  reason: string;
  idempotencyKey: string;
}

interface InventoryRow {
  variant_id: string;
  sku: string;
  product_title: string;
  quantity: number;
}

interface AdjustmentRow {
  id: string;
  variant_id: string;
  delta: number;
  reason: string;
  idempotency_key: string;
  created_at: string;
}

export async function listInventory(db: D1Database): Promise<InventoryItem[]> {
  const result = await db
    .prepare(
      `SELECT
        variant.id AS variant_id, variant.sku, product.title AS product_title,
        stock.quantity
      FROM inventory_items stock
      JOIN variants variant ON variant.id = stock.variant_id
      JOIN products product ON product.id = variant.product_id
      WHERE product.archived_at IS NULL
      ORDER BY product.title, variant.sku`,
    )
    .all<InventoryRow>();
  return result.results.map((row) => ({
    variantId: row.variant_id,
    sku: row.sku,
    productTitle: row.product_title,
    quantity: row.quantity,
  }));
}

async function adjustmentByKey(
  db: D1Database,
  idempotencyKey: string,
): Promise<AdjustmentRow | null> {
  return db
    .prepare("SELECT * FROM inventory_adjustments WHERE idempotency_key = ?")
    .bind(idempotencyKey)
    .first<AdjustmentRow>();
}

export async function adjustInventory(
  db: D1Database,
  input: InventoryAdjustmentInput,
): Promise<AdjustmentRow> {
  if (!Number.isSafeInteger(input.delta) || input.delta === 0) {
    throw new HttpError(422, "invalid_inventory_delta", "Stock change must be a non-zero integer.");
  }
  const reason = input.reason.trim().replace(/\s+/g, " ");
  if (reason.length < 3 || reason.length > 200) {
    throw new HttpError(422, "invalid_inventory_reason", "Reason must be 3 to 200 characters.");
  }
  if (
    !/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(
      input.idempotencyKey,
    )
  ) {
    throw new HttpError(422, "invalid_idempotency_key", "The stock form has expired.");
  }

  const existing = await adjustmentByKey(db, input.idempotencyKey);
  if (existing) return existing;

  const id = crypto.randomUUID();
  const createdAt = new Date().toISOString();
  try {
    const [insert] = await db.batch([
      db
        .prepare(
          `INSERT INTO inventory_adjustments (
            id, variant_id, delta, reason, idempotency_key, actor, created_at
          )
          SELECT ?1, ?2, ?3, ?4, ?5, 'owner', ?6
          WHERE EXISTS (
            SELECT 1 FROM inventory_items
            WHERE variant_id = ?2 AND quantity + ?3 >= 0
          )`,
        )
        .bind(
          id,
          input.variantId,
          input.delta,
          reason,
          input.idempotencyKey,
          createdAt,
        ),
      db
        .prepare(
          `UPDATE inventory_items
          SET quantity = quantity + ?2, updated_at = ?3
          WHERE variant_id = ?1
            AND EXISTS (
              SELECT 1 FROM inventory_adjustments
              WHERE id = ?4 AND variant_id = ?1
            )`,
        )
        .bind(input.variantId, input.delta, createdAt, id),
    ]);
    if (!insert || insert.meta.changes === 0) {
      throw new HttpError(409, "insufficient_stock", "That change would make stock negative.");
    }
  } catch (error) {
    const duplicate = await adjustmentByKey(db, input.idempotencyKey);
    if (duplicate) return duplicate;
    if (error instanceof HttpError) throw error;
    throw new HttpError(409, "inventory_conflict", "Stock changed before this request completed.");
  }

  const adjustment = await adjustmentByKey(db, input.idempotencyKey);
  if (!adjustment) {
    throw new HttpError(500, "inventory_write_failed", "The stock change could not be confirmed.");
  }
  return adjustment;
}

function field(form: FormData, name: string): string {
  const value = form.get(name);
  return typeof value === "string" ? value : "";
}

async function inventoryPage(
  env: Env,
  owner: AuthenticatedOwner,
): Promise<Response> {
  const [items, history] = await Promise.all([
    listInventory(env.DB),
    env.DB
      .prepare(
        `SELECT adjustment.*, variant.sku
        FROM inventory_adjustments adjustment
        JOIN variants variant ON variant.id = adjustment.variant_id
        ORDER BY adjustment.created_at DESC LIMIT 100`,
      )
      .all<AdjustmentRow & { sku: string }>(),
  ]);
  const rows = items
    .map(
      (item) => `<tr>
        <td>${escapeHtml(item.sku)}</td><td>${escapeHtml(item.productTitle)}</td>
        <td>${item.quantity}</td>
        <td><form method="post" action="/admin/inventory/${item.variantId}/adjust">
          <input type="hidden" name="csrf" value="${escapeHtml(owner.session.csrf)}">
          <input type="hidden" name="idempotency_key" value="${crypto.randomUUID()}">
          <label>Change <input name="delta" type="number" required></label>
          <label>Reason <input name="reason" minlength="3" maxlength="200" required></label>
          <button type="submit">Adjust</button>
        </form></td>
      </tr>`,
    )
    .join("");
  const historyRows = history.results
    .map(
      (item) =>
        `<tr><td>${escapeHtml(item.sku)}</td><td>${item.delta}</td><td>${escapeHtml(item.reason)}</td><td>${escapeHtml(item.created_at)}</td></tr>`,
    )
    .join("");
  return adminPage(
    "Inventory",
    `<table><thead><tr><th>SKU</th><th>Product</th><th>Quantity</th><th>Adjust</th></tr></thead>
    <tbody>${rows || '<tr><td colspan="4">No variants yet.</td></tr>'}</tbody></table>
    <h2>Adjustment history</h2>
    <table><thead><tr><th>SKU</th><th>Change</th><th>Reason</th><th>Time</th></tr></thead>
    <tbody>${historyRows || '<tr><td colspan="4">No adjustments yet.</td></tr>'}</tbody></table>`,
    owner,
  );
}

export async function routeInventory(
  request: Request,
  env: Env,
): Promise<Response | null> {
  const path = new URL(request.url).pathname;
  if (!path.startsWith("/admin/inventory")) return null;

  let owner: AuthenticatedOwner;
  try {
    owner = await requireOwner(request, env);
  } catch (error) {
    if (error instanceof HttpError && error.status === 401) return redirect("/admin/login");
    throw error;
  }

  try {
    if (request.method === "GET" && path === "/admin/inventory") {
      return inventoryPage(env, owner);
    }
    const match = path.match(/^\/admin\/inventory\/([^/]+)\/adjust$/);
    if (request.method === "POST" && match?.[1]) {
      const form = await readForm(request);
      await requireCsrf(request, owner.session, form);
      await adjustInventory(env.DB, {
        variantId: match[1],
        delta: /^-?\d+$/.test(field(form, "delta"))
          ? Number.parseInt(field(form, "delta"), 10)
          : Number.NaN,
        reason: field(form, "reason"),
        idempotencyKey: field(form, "idempotency_key"),
      });
      return redirect("/admin/inventory");
    }
    return adminPage("Not found", "<p>The inventory page was not found.</p>", owner, 404);
  } catch (error) {
    if (error instanceof HttpError) {
      return adminPage(
        "Could not adjust inventory",
        `<p role="alert">${escapeHtml(error.message)}</p><p><a href="/admin/inventory">Go back</a></p>`,
        owner,
        error.status,
      );
    }
    throw error;
  }
}
