import { env } from "cloudflare:workers";
import { SELF } from "cloudflare:test";
import { beforeEach, describe, expect, it } from "vitest";

import { sessionCookie } from "../src/auth";
import {
  deleteProductMedia,
  detectImageType,
  uploadProductMedia,
} from "../src/media";

const ORIGIN = "https://example.com";
const PRODUCT_ID = "11111111-1111-4111-8111-111111111111";

const IMAGES = [
  {
    type: "image/jpeg",
    name: "saree.jpg",
    bytes: new Uint8Array([0xff, 0xd8, 0xff, 0x00]),
  },
  {
    type: "image/png",
    name: "saree.png",
    bytes: new Uint8Array([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
  },
  {
    type: "image/webp",
    name: "saree.webp",
    bytes: new TextEncoder().encode("RIFF1234WEBP"),
  },
] as const;

beforeEach(async () => {
  const now = new Date().toISOString();
  await env.DB.prepare(
    `INSERT INTO products (
      id, slug, title, description, silk_type, publication_state,
      featured_rank, created_at, updated_at
    ) VALUES (?, 'media-saree', 'Media Saree', '', 'Muga', 'draft', 0, ?, ?)`,
  )
    .bind(PRODUCT_ID, now, now)
    .run();
});

describe("product media", () => {
  it("detects and stores only matching supported image signatures", async () => {
    for (const image of IMAGES) {
      expect(detectImageType(image.bytes)?.contentType).toBe(image.type);
      await uploadProductMedia(
        env.DB,
        env.MEDIA,
        PRODUCT_ID,
        new File([image.bytes], image.name, { type: image.type }),
        `${image.type} silk detail`,
      );
    }
    expect((await env.MEDIA.list()).objects).toHaveLength(3);
    expect(
      await env.DB.prepare("SELECT COUNT(*) AS count FROM product_media").first("count"),
    ).toBe(3);

    await expect(
      uploadProductMedia(
        env.DB,
        env.MEDIA,
        PRODUCT_ID,
        new File([IMAGES[0].bytes], "wrong.png", { type: "image/png" }),
        "Mismatched image",
      ),
    ).rejects.toMatchObject({ status: 415, code: "invalid_image" });
    await expect(
      uploadProductMedia(
        env.DB,
        env.MEDIA,
        PRODUCT_ID,
        new File([new TextEncoder().encode("<script>alert(1)</script>")], "attack.jpg", {
          type: "image/jpeg",
        }),
        "Executable payload",
      ),
    ).rejects.toMatchObject({ status: 415, code: "invalid_image" });
    await expect(
      uploadProductMedia(
        env.DB,
        env.MEDIA,
        PRODUCT_ID,
        new File([IMAGES[0].bytes], "missing-alt.jpg", { type: "image/jpeg" }),
        "",
      ),
    ).rejects.toMatchObject({ status: 422, code: "invalid_alt_text" });
    await expect(
      uploadProductMedia(
        env.DB,
        env.MEDIA,
        PRODUCT_ID,
        new File([new Uint8Array(8_388_609)], "large.jpg", { type: "image/jpeg" }),
        "Oversized image",
      ),
    ).rejects.toMatchObject({ status: 413, code: "image_too_large" });
  });

  it("removes an R2 object when D1 metadata cannot be written", async () => {
    await expect(
      uploadProductMedia(
        env.DB,
        env.MEDIA,
        "22222222-2222-4222-8222-222222222222",
        new File([IMAGES[0].bytes], "orphan.jpg", { type: "image/jpeg" }),
        "Orphan candidate",
      ),
    ).rejects.toMatchObject({ status: 422, code: "media_write_failed" });
    expect((await env.MEDIA.list()).objects).toHaveLength(0);
  });

  it("keeps drafts private, serves published media safely, and deletes metadata first", async () => {
    const media = await uploadProductMedia(
      env.DB,
      env.MEDIA,
      PRODUCT_ID,
      new File([IMAGES[1].bytes], "saree.png", { type: "image/png" }),
      "Gold Muga silk weave",
    );
    expect((await SELF.fetch(`${ORIGIN}/media/${media.id}`)).status).toBe(404);

    const now = new Date().toISOString();
    await env.DB.prepare(
      `INSERT INTO owner (
        id, email, password_hash, password_salt, password_iterations,
        session_version, created_at, updated_at
      ) VALUES ('owner', 'owner@example.com', 'unused', 'unused', 600000, 1, ?, ?)`,
    )
      .bind(now, now)
      .run();
    const cookie = await sessionCookie(
      {
        ownerId: "owner",
        sessionVersion: 1,
        expiresAt: Math.floor(Date.now() / 1000) + 3600,
        csrf: "csrf-token-with-at-least-thirty-two-characters",
      },
      env,
    );
    expect(
      (
        await SELF.fetch(`${ORIGIN}/admin/media/${media.id}/content`, {
          headers: { cookie },
        })
      ).status,
    ).toBe(200);

    await env.DB.prepare(
      "UPDATE products SET publication_state = 'published' WHERE id = ?",
    )
      .bind(PRODUCT_ID)
      .run();
    const published = await SELF.fetch(`${ORIGIN}/media/${media.id}`);
    expect(published.status).toBe(200);
    expect(published.headers.get("content-type")).toBe("image/png");
    expect(published.headers.get("cache-control")).toBe(
      "public, max-age=31536000, immutable",
    );
    expect(published.headers.get("etag")).toBeTruthy();
    expect(published.headers.get("x-content-type-options")).toBe("nosniff");

    await deleteProductMedia(env.DB, env.MEDIA, media.id, "test-request");
    expect((await SELF.fetch(`${ORIGIN}/media/${media.id}`)).status).toBe(404);
    expect(
      await env.DB.prepare("SELECT COUNT(*) AS count FROM product_media").first("count"),
    ).toBe(0);
  });
});
