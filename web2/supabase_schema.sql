-- Supabase SQL Schema za Kopernikus-GIS Web App
-- Kreiraj ove tabele u Supabase SQL Editor-u

-- =============================================
-- 1. PARCELE (Geometrije)
-- =============================================
CREATE TABLE IF NOT EXISTS parcels (
    id SERIAL PRIMARY KEY,
    parcel_id VARCHAR(50) NOT NULL UNIQUE,
    cadastral_id VARCHAR(100),
    municipality VARCHAR(100),
    area_ha FLOAT,
    geometry JSONB NOT NULL,  -- GeoJSON geometry
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Index za brže pretragu
CREATE INDEX IF NOT EXISTS idx_parcels_parcel_id ON parcels(parcel_id);
CREATE INDEX IF NOT EXISTS idx_parcels_municipality ON parcels(municipality);

-- Primer insert (parcela 1427/2):
INSERT INTO parcels (parcel_id, cadastral_id, municipality, area_ha, geometry)
VALUES (
    '1427/2',
    'Kovin_1427_2',
    'Kovin',
    0.5,
    '{
        "type": "Polygon",
        "coordinates": [[[
            [21.1986, 44.8142],
            [21.2021, 44.8142],
            [21.2021, 44.8182],
            [21.1986, 44.8182],
            [21.1986, 44.8142]
        ]]]
    }'::jsonb
)
ON CONFLICT (parcel_id) DO NOTHING;

-- =============================================
-- 2. INDEX RESULTS (NDVI, NDMI, NDRE)
-- =============================================
CREATE TABLE IF NOT EXISTS index_results (
    id SERIAL PRIMARY KEY,
    parcel_id VARCHAR(50) NOT NULL,
    index_type VARCHAR(20) NOT NULL,  -- 'NDVI', 'NDMI', 'NDRE'
    acquisition_date DATE NOT NULL,
    mean_value FLOAT,
    min_value FLOAT,
    max_value FLOAT,
    std_dev FLOAT,
    valid_pixels INT,
    cloud_pixels INT,
    percentile_10 FLOAT,
    percentile_50 FLOAT,
    percentile_90 FLOAT,
    created_at TIMESTAMP DEFAULT NOW(),
    
    FOREIGN KEY (parcel_id) REFERENCES parcels(parcel_id) ON DELETE CASCADE
);

-- Index za brže pretragu
CREATE INDEX IF NOT EXISTS idx_index_results_parcel ON index_results(parcel_id);
CREATE INDEX IF NOT EXISTS idx_index_results_date ON index_results(acquisition_date);
CREATE INDEX IF NOT EXISTS idx_index_results_type ON index_results(index_type);

-- Primer insert:
INSERT INTO index_results (parcel_id, index_type, acquisition_date, mean_value, min_value, max_value, std_dev, valid_pixels, cloud_pixels, percentile_50)
VALUES 
    ('1427/2', 'NDRE', '2026-02-04', 0.168, 0.105, 0.255, 0.0245, 810, 0, 0.165),
    ('1427/2', 'NDRE', '2026-01-25', 0.108, -0.098, 0.339, 0.0312, 694, 116, 0.105),
    ('1427/2', 'NDVI', '2026-02-04', 0.277, 0.184, 0.430, 0.0521, 810, 0, 0.275),
    ('1427/2', 'NDMI', '2026-02-04', -0.019, -0.087, 0.118, 0.0432, 810, 0, -0.020)
ON CONFLICT DO NOTHING;

-- =============================================
-- 3. ZONE CLASSIFICATIONS (NDRE Zones)
-- =============================================
CREATE TABLE IF NOT EXISTS zone_classifications (
    id SERIAL PRIMARY KEY,
    parcel_id VARCHAR(50) NOT NULL,
    index_type VARCHAR(20) NOT NULL,
    acquisition_date DATE NOT NULL,
    zone_type VARCHAR(20) NOT NULL,  -- 'red', 'yellow', 'green'
    zone_label VARCHAR(100),
    percentage FLOAT,
    recommendation TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    
    FOREIGN KEY (parcel_id) REFERENCES parcels(parcel_id) ON DELETE CASCADE
);

-- Index
CREATE INDEX IF NOT EXISTS idx_zones_parcel ON zone_classifications(parcel_id);

-- Primer insert (za NDRE zone):
INSERT INTO zone_classifications (parcel_id, index_type, acquisition_date, zone_type, zone_label, percentage, recommendation)
VALUES 
    ('1427/2', 'NDRE', '2026-02-04', 'red', 'Problematična zona (< 0.14)', 15.0, 'Dodaj više azota'),
    ('1427/2', 'NDRE', '2026-02-04', 'yellow', 'Umerena zona (0.14-0.19)', 60.0, 'Standardna obrada'),
    ('1427/2', 'NDRE', '2026-02-04', 'green', 'Dobra zona (≥ 0.19)', 25.0, 'Može manje azota')
ON CONFLICT DO NOTHING;

-- =============================================
-- 4. ZONE GEOMETRIES (GeoJSON za zone)
-- =============================================
CREATE TABLE IF NOT EXISTS zone_geometries (
    id SERIAL PRIMARY KEY,
    parcel_id VARCHAR(50) NOT NULL,
    index_type VARCHAR(20) NOT NULL,
    acquisition_date DATE NOT NULL,
    zone_type VARCHAR(20) NOT NULL,
    geometry JSONB NOT NULL,  -- GeoJSON FeatureCollection
    created_at TIMESTAMP DEFAULT NOW(),
    
    FOREIGN KEY (parcel_id) REFERENCES parcels(parcel_id) ON DELETE CASCADE
);

-- Index
CREATE INDEX IF NOT EXISTS idx_zone_geom_parcel ON zone_geometries(parcel_id);

-- Primer insert (simplified zone geometry):
INSERT INTO zone_geometries (parcel_id, index_type, acquisition_date, zone_type, geometry)
VALUES (
    '1427/2',
    'NDRE',
    '2026-02-04',
    'red',
    '{
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "properties": {"zone": "red", "value": 0.12},
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[
                    [21.1986, 44.8142],
                    [21.1995, 44.8142],
                    [21.1995, 44.8155],
                    [21.1986, 44.8155],
                    [21.1986, 44.8142]
                ]]]
            }
        }]
    }'::jsonb
)
ON CONFLICT DO NOTHING;

-- =============================================
-- 5. METADATA (Latest updates, system info)
-- =============================================
CREATE TABLE IF NOT EXISTS metadata (
    id SERIAL PRIMARY KEY,
    key VARCHAR(100) NOT NULL UNIQUE,
    value TEXT,
    updated_at TIMESTAMP DEFAULT NOW()
);

INSERT INTO metadata (key, value)
VALUES 
    ('last_update', NOW()::TEXT),
    ('version', '2026-02-09'),
    ('total_parcels', '1'),
    ('data_source', 'Copernicus Sentinel-2')
ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = NOW();

-- =============================================
-- 6. ENABLE ROW LEVEL SECURITY (opciono, za public read)
-- =============================================
ALTER TABLE parcels ENABLE ROW LEVEL SECURITY;
ALTER TABLE index_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE zone_classifications ENABLE ROW LEVEL SECURITY;
ALTER TABLE zone_geometries ENABLE ROW LEVEL SECURITY;
ALTER TABLE metadata ENABLE ROW LEVEL SECURITY;

-- Public read policy (svi mogu da čitaju)
CREATE POLICY "Allow public read access" ON parcels FOR SELECT USING (true);
CREATE POLICY "Allow public read access" ON index_results FOR SELECT USING (true);
CREATE POLICY "Allow public read access" ON zone_classifications FOR SELECT USING (true);
CREATE POLICY "Allow public read access" ON zone_geometries FOR SELECT USING (true);
CREATE POLICY "Allow public read access" ON metadata FOR SELECT USING (true);

-- =============================================
-- 7. HELPER VIEWS
-- =============================================

-- View: Latest index results per parcel
CREATE OR REPLACE VIEW latest_index_results AS
SELECT DISTINCT ON (parcel_id, index_type)
    parcel_id,
    index_type,
    acquisition_date,
    mean_value,
    min_value,
    max_value,
    valid_pixels,
    cloud_pixels
FROM index_results
ORDER BY parcel_id, index_type, acquisition_date DESC;

-- View: Parcel summary
CREATE OR REPLACE VIEW parcel_summary AS
SELECT 
    p.parcel_id,
    p.municipality,
    p.area_ha,
    p.geometry,
    (SELECT COUNT(*) FROM index_results WHERE parcel_id = p.parcel_id) as total_measurements,
    (SELECT MAX(acquisition_date) FROM index_results WHERE parcel_id = p.parcel_id) as latest_measurement
FROM parcels p;

-- =============================================
-- DONE! 
-- =============================================
-- Nakon kreiranja tabela, popuni podatke korišćenjem:
-- python web2/export_to_supabase.py
