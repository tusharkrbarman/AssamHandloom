import { adminPage } from "./admin";
import { AuthenticatedOwner, requireCsrf, requireOwner } from "./auth";
import { escapeHtml, HttpError, readForm, redirect } from "./http";

const MAX_IMAGE_BYTES = 8_388_608;
const UUID =
  /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

interface ImageType {
  contentType: "image/jpeg" | "image/png" | "image/webp";
  extension: "jpg" | "png" | "webp";
}

export interface ProductMedia {
  id: string;
  productId: string;
  objectKey: string;
  altText: string;
  contentType: ImageType["contentType"];
  byteSize: number;
}

interface MediaRow {
  id: string;
  product_id: string;
  object_key: string;
  alt_text: string;
  content_type: ImageType["contentType"];
  byte_size: number;
}

export function detectImageType(bytes: Uint8Array): ImageType | null {
  if (bytes[0] === 0xff && bytes[1] === 0xd8 && bytes[2] === 0xff) {
    return { contentType: "image/jpeg", extension: "jpg" };
  }
  if (
    bytes[0] === 0x89 &&
    bytes[1] === 0x50 &&
    bytes[2] === 0x4e &&
    bytes[3] === 0x47 &&
    bytes[4] === 0x0d &&
    bytes[5] === 0x0a &&
    bytes[6] === 0x1a &&
    bytes[7] === 0x0a
  ) {
    return { contentType: "image/png", extension: "png" };
  }
  const ascii = String.fromCharCode(...bytes.slice(0, 12));
  if (ascii.slice(0, 4) === "RIFF" && ascii.slice(8, 12) === "WEBP") {
    return { contentType: "image/webp", extension: "webp" };
  }
  return null;
}

export async function uploadProductMedia(
  db: D1Database,
  bucket: R2Bucket,
  productId: string,
  file: File,
  altText: string,
): Promise<ProductMedia> {
  if (!UUID.test(productId)) {
    throw new HttpError(422, "invalid_product", "The product is invalid.");
  }
  if (file.size > MAX_IMAGE_BYTES) {
    throw new HttpError(413, "image_too_large", "Images must be 8 MiB or smaller.");
  }
  if (file.size === 0) {
    throw new HttpError(415, "invalid_image", "The file is not a supported image.");
  }
  const cleanAlt = altText.trim().replace(/\s+/g, " ");
  if (!cleanAlt || cleanAlt.length > 300) {
    throw new HttpError(422, "invalid_alt_text", "Alternative text is required.");
  }
  const bytes = new Uint8Array(await file.arrayBuffer());
  const detected = detectImageType(bytes);
  if (!detected || file.type !== detected.contentType) {
    throw new HttpError(415, "invalid_image", "The file is not a supported image.");
  }

  const id = crypto.randomUUID();
  const objectKey = `products/${productId}/${id}.${detected.extension}`;
  await bucket.put(objectKey, bytes, {
    httpMetadata: {
      contentType: detected.contentType,
      contentDisposition: "inline",
      cacheControl: "public, max-age=31536000, immutable",
    },
  });
  try {
    await db
      .prepare(
        `INSERT INTO product_media (
          id, product_id, object_key, alt_text, content_type,
          byte_size, display_order, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, 0, ?)`,
      )
      .bind(
        id,
        productId,
        objectKey,
        cleanAlt,
        detected.contentType,
        file.size,
        new Date().toISOString(),
      )
      .run();
  } catch {
    await bucket.delete(objectKey);
    throw new HttpError(422, "media_write_failed", "The image could not be saved.");
  }
  return {
    id,
    productId,
    objectKey,
    altText: cleanAlt,
    contentType: detected.contentType,
    byteSize: file.size,
  };
}

export async function getMediaResponse(
  db: D1Database,
  bucket: R2Bucket,
  mediaId: string,
  ownerPreview = false,
): Promise<Response> {
  const row = await db
    .prepare(
      `SELECT media.*
      FROM product_media media
      JOIN products product ON product.id = media.product_id
      WHERE media.id = ?
        ${ownerPreview ? "" : "AND product.publication_state = 'published' AND product.archived_at IS NULL"}`,
    )
    .bind(mediaId)
    .first<MediaRow>();
  if (!row) throw new HttpError(404, "media_not_found", "Image not found.");

  const object = await bucket.get(row.object_key);
  if (!object) throw new HttpError(404, "media_not_found", "Image not found.");
  const headers = new Headers();
  object.writeHttpMetadata(headers);
  headers.set("etag", object.httpEtag);
  headers.set("x-content-type-options", "nosniff");
  return new Response(object.body, { headers });
}

export async function deleteProductMedia(
  db: D1Database,
  bucket: R2Bucket,
  mediaId: string,
  requestId: string,
): Promise<ProductMedia> {
  const row = await db
    .prepare("SELECT * FROM product_media WHERE id = ?")
    .bind(mediaId)
    .first<MediaRow>();
  if (!row) throw new HttpError(404, "media_not_found", "Image not found.");
  await db.prepare("DELETE FROM product_media WHERE id = ?").bind(mediaId).run();
  try {
    await bucket.delete(row.object_key);
  } catch {
    console.log(
      JSON.stringify({
        requestId,
        errorCode: "media_object_delete_failed",
        objectKey: row.object_key,
      }),
    );
  }
  return {
    id: row.id,
    productId: row.product_id,
    objectKey: row.object_key,
    altText: row.alt_text,
    contentType: row.content_type,
    byteSize: row.byte_size,
  };
}

function field(form: FormData, name: string): string {
  const value = form.get(name);
  return typeof value === "string" ? value : "";
}

export async function routeMedia(request: Request, env: Env): Promise<Response | null> {
  const path = new URL(request.url).pathname;
  const publicMatch = path.match(/^\/media\/([^/]+)$/);
  if (request.method === "GET" && publicMatch?.[1]) {
    return getMediaResponse(env.DB, env.MEDIA, publicMatch[1]);
  }
  if (!path.startsWith("/admin/") || !path.includes("/media")) return null;

  let owner: AuthenticatedOwner;
  try {
    owner = await requireOwner(request, env);
  } catch (error) {
    if (error instanceof HttpError && error.status === 401) return redirect("/admin/login");
    throw error;
  }

  try {
    const contentMatch = path.match(/^\/admin\/media\/([^/]+)\/content$/);
    if (request.method === "GET" && contentMatch?.[1]) {
      return getMediaResponse(env.DB, env.MEDIA, contentMatch[1], true);
    }

    const uploadMatch = path.match(/^\/admin\/products\/([^/]+)\/media$/);
    if (request.method === "POST" && uploadMatch?.[1]) {
      const form = await readForm(request);
      await requireCsrf(request, owner.session, form);
      const file = form.get("image");
      if (!(file instanceof File)) {
        throw new HttpError(415, "invalid_image", "Choose a supported image.");
      }
      await uploadProductMedia(
        env.DB,
        env.MEDIA,
        uploadMatch[1],
        file,
        field(form, "alt_text"),
      );
      return redirect(`/admin/products/${uploadMatch[1]}`);
    }

    const deleteMatch = path.match(/^\/admin\/media\/([^/]+)\/delete$/);
    if (request.method === "POST" && deleteMatch?.[1]) {
      const form = await readForm(request);
      await requireCsrf(request, owner.session, form);
      const media = await deleteProductMedia(
        env.DB,
        env.MEDIA,
        deleteMatch[1],
        request.headers.get("x-request-id") ?? crypto.randomUUID(),
      );
      return redirect(`/admin/products/${media.productId}`);
    }
    return adminPage("Not found", "<p>The media page was not found.</p>", owner, 404);
  } catch (error) {
    if (error instanceof HttpError) {
      return adminPage(
        "Could not save image",
        `<p role="alert">${escapeHtml(error.message)}</p><p><a href="/admin">Go back</a></p>`,
        owner,
        error.status,
      );
    }
    throw error;
  }
}
