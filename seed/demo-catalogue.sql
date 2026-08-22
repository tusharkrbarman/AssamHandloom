PRAGMA foreign_keys = ON;

INSERT OR IGNORE INTO products (
  id, slug, title, description, silk_type, colour, occasion,
  publication_state, featured_rank, archived_at, created_at, updated_at
) VALUES
('dea11001-0000-4000-8000-000000000001', 'muga-bridal-saree',
 'Golden Muga Bridal Saree',
 'Handwoven in Sualkuchi from natural golden Muga silk with a fine kingkhap border. The sheen deepens with every wear.',
 'Muga', 'Natural gold', 'Wedding', 'published', 1, NULL,
 '2026-08-22T09:00:00.000Z', '2026-08-22T09:00:00.000Z'),
('dea11002-0000-4000-8000-000000000002', 'pat-mekhela-chador',
 'Pat Silk Mekhela Chador',
 'A two-piece ceremonial drape in mulberry Pat silk, woven on a traditional loom with a contrasting red border.',
 'Paat', 'White & red', 'Ceremonial', 'published', 2, NULL,
 '2026-08-22T09:00:00.000Z', '2026-08-22T09:00:00.000Z'),
('dea11003-0000-4000-8000-000000000003', 'eri-shawl',
 'Handspun Eri Peace-Silk Shawl',
 'Warm, matte Eri silk spun without harming the silkworm. A quiet everyday wrap that softens beautifully over years.',
 'Eri', 'Natural beige', 'Everyday', 'published', 3, NULL,
 '2026-08-22T09:00:00.000Z', '2026-08-22T09:00:00.000Z'),
('dea11004-0000-4000-8000-000000000004', 'muga-endi-half-silk-saree',
 'Muga Endi Half-Silk Saree',
 'Muga warp meets hand-spun Eri weft in this lighter half-silk drape, finished with a mustard-gold body and deep pallu.',
 'Muga Endi', 'Mustard gold', 'Festive', 'published', 4, NULL,
 '2026-08-22T09:00:00.000Z', '2026-08-22T09:00:00.000Z'),
('dea11005-0000-4000-8000-000000000005', 'sualkuchi-cotton-saree',
 'Sualkuchi Handloom Cotton Saree',
 'Breathable handloom cotton from the weavers of Sualkuchi, with temple-border detailing and generous pleat fall.',
 'Cotton', 'Indigo', 'Everyday', 'published', 5, NULL,
 '2026-08-22T09:00:00.000Z', '2026-08-22T09:00:00.000Z'),
('dea11006-0000-4000-8000-000000000006', 'japi-motif-muga-saree',
 'Japi Motif Muga Saree',
 'Loom-to-order Muga saree carrying woven japi motifs along the border. Currently at the design stage.',
 'Muga', 'Golden', 'Wedding', 'draft', 0, NULL,
 '2026-08-22T09:00:00.000Z', '2026-08-22T09:00:00.000Z');

INSERT OR IGNORE INTO variants (
  id, product_id, sku, title, price_minor, currency, weight_grams,
  publication_state, created_at, updated_at
) VALUES
('dea12001-0000-4000-8000-000000000001', 'dea11001-0000-4000-8000-000000000001',
 'MUGA-NATURAL-GOLD', 'Natural gold', 2450000, 'INR', 720, 'published',
 '2026-08-22T09:00:00.000Z', '2026-08-22T09:00:00.000Z'),
('dea12001-0000-4000-8000-000000000002', 'dea11001-0000-4000-8000-000000000001',
 'MUGA-IVORY-WEAVE', 'Ivory weave', 2590000, 'INR', 740, 'published',
 '2026-08-22T09:00:00.000Z', '2026-08-22T09:00:00.000Z'),
('dea12002-0000-4000-8000-000000000003', 'dea11002-0000-4000-8000-000000000002',
 'PAAT-WHITE-RED', 'White with red border', 1580000, 'INR', 650, 'published',
 '2026-08-22T09:00:00.000Z', '2026-08-22T09:00:00.000Z'),
('dea12003-0000-4000-8000-000000000004', 'dea11003-0000-4000-8000-000000000003',
 'ERI-NATURAL-BEIGE', 'Natural beige', 320000, 'INR', 420, 'published',
 '2026-08-22T09:00:00.000Z', '2026-08-22T09:00:00.000Z'),
('dea12003-0000-4000-8000-000000000005', 'dea11003-0000-4000-8000-000000000003',
 'ERI-INDIGO-DYED', 'Indigo dyed', 340000, 'INR', 430, 'published',
 '2026-08-22T09:00:00.000Z', '2026-08-22T09:00:00.000Z'),
('dea12004-0000-4000-8000-000000000006', 'dea11004-0000-4000-8000-000000000004',
 'ENDI-MUSTARD-GOLD', 'Mustard gold', 980000, 'INR', 690, 'published',
 '2026-08-22T09:00:00.000Z', '2026-08-22T09:00:00.000Z'),
('dea12005-0000-4000-8000-000000000007', 'dea11005-0000-4000-8000-000000000005',
 'COTTON-INDIGO-IKAT', 'Indigo ikat', 460000, 'INR', 580, 'published',
 '2026-08-22T09:00:00.000Z', '2026-08-22T09:00:00.000Z'),
('dea12005-0000-4000-8000-000000000008', 'dea11005-0000-4000-8000-000000000005',
 'COTTON-RUST-RED', 'Rust red', 480000, 'INR', 580, 'published',
 '2026-08-22T09:00:00.000Z', '2026-08-22T09:00:00.000Z');

INSERT OR IGNORE INTO inventory_items (
  variant_id, quantity, version, updated_at
) VALUES
('dea12001-0000-4000-8000-000000000001', 4, 0, '2026-08-22T09:00:00.000Z'),
('dea12001-0000-4000-8000-000000000002', 2, 0, '2026-08-22T09:00:00.000Z'),
('dea12002-0000-4000-8000-000000000003', 6, 0, '2026-08-22T09:00:00.000Z'),
('dea12003-0000-4000-8000-000000000004', 8, 0, '2026-08-22T09:00:00.000Z'),
('dea12003-0000-4000-8000-000000000005', 5, 0, '2026-08-22T09:00:00.000Z'),
('dea12004-0000-4000-8000-000000000006', 3, 0, '2026-08-22T09:00:00.000Z'),
('dea12005-0000-4000-8000-000000000007', 7, 0, '2026-08-22T09:00:00.000Z'),
('dea12005-0000-4000-8000-000000000008', 6, 0, '2026-08-22T09:00:00.000Z');

INSERT OR IGNORE INTO inventory_adjustments (
  id, variant_id, delta, reason, idempotency_key, actor, created_at
) VALUES
('dea14001-0000-4000-8000-000000000001', 'dea12001-0000-4000-8000-000000000001',
 4, 'Initial demo stock', 'demo-seed-muga-natural-gold', 'seed', '2026-08-22T09:00:00.000Z'),
('dea14001-0000-4000-8000-000000000002', 'dea12001-0000-4000-8000-000000000002',
 2, 'Initial demo stock', 'demo-seed-muga-ivory-weave', 'seed', '2026-08-22T09:00:00.000Z'),
('dea14001-0000-4000-8000-000000000003', 'dea12002-0000-4000-8000-000000000003',
 6, 'Initial demo stock', 'demo-seed-paat-white-red', 'seed', '2026-08-22T09:00:00.000Z'),
('dea14001-0000-4000-8000-000000000004', 'dea12003-0000-4000-8000-000000000004',
 8, 'Initial demo stock', 'demo-seed-eri-natural-beige', 'seed', '2026-08-22T09:00:00.000Z'),
('dea14001-0000-4000-8000-000000000005', 'dea12003-0000-4000-8000-000000000005',
 5, 'Initial demo stock', 'demo-seed-eri-indigo-dyed', 'seed', '2026-08-22T09:00:00.000Z'),
('dea14001-0000-4000-8000-000000000006', 'dea12004-0000-4000-8000-000000000006',
 3, 'Initial demo stock', 'demo-seed-endi-mustard-gold', 'seed', '2026-08-22T09:00:00.000Z'),
('dea14001-0000-4000-8000-000000000007', 'dea12005-0000-4000-8000-000000000007',
 7, 'Initial demo stock', 'demo-seed-cotton-indigo-ikat', 'seed', '2026-08-22T09:00:00.000Z'),
('dea14001-0000-4000-8000-000000000008', 'dea12005-0000-4000-8000-000000000008',
 6, 'Initial demo stock', 'demo-seed-cotton-rust-red', 'seed', '2026-08-22T09:00:00.000Z');

INSERT OR IGNORE INTO collections (
  id, slug, title, description, publication_state, display_order,
  created_at, updated_at
) VALUES
('dea13001-0000-4000-8000-000000000001', 'weddings-ceremonies',
 'Weddings & Ceremonies',
 'Heirloom-grade silks reserved for the days that matter most.',
 'published', 0, '2026-08-22T09:00:00.000Z', '2026-08-22T09:00:00.000Z'),
('dea13002-0000-4000-8000-000000000002', 'everyday-weaves',
 'Everyday Weaves',
 'Quietly durable drapes and wraps made for regular wear.',
 'published', 1, '2026-08-22T09:00:00.000Z', '2026-08-22T09:00:00.000Z');

INSERT OR IGNORE INTO collection_products (
  collection_id, product_id, display_order
) VALUES
('dea13001-0000-4000-8000-000000000001', 'dea11001-0000-4000-8000-000000000001', 0),
('dea13001-0000-4000-8000-000000000001', 'dea11002-0000-4000-8000-000000000002', 1),
('dea13002-0000-4000-8000-000000000002', 'dea11003-0000-4000-8000-000000000003', 0),
('dea13002-0000-4000-8000-000000000002', 'dea11004-0000-4000-8000-000000000004', 1),
('dea13002-0000-4000-8000-000000000002', 'dea11005-0000-4000-8000-000000000005', 2);
