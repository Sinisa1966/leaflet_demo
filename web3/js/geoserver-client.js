// GeoServer/parcel_server Client
// Zamenjuje supabase-client.js – isti interfejs, drugi backend

class GeoServerClient {
    constructor() {
        this.parcelServerUrl = null;
        this.geoserverUrl    = null;
        this.isInitialized   = false;
        this._csvCache       = {};
        this._latestDate     = null;
    }

    // ─── Init ────────────────────────────────────────────────────────────────

    init() {
        const isLocal = (
            window.location.hostname === 'localhost' ||
            window.location.hostname === '127.0.0.1' ||
            window.location.protocol === 'file:'
        );
        this.parcelServerUrl = isLocal
            ? APP_CONFIG.parcelServer.local
            : APP_CONFIG.parcelServer.production;
        this.geoserverUrl = isLocal
            ? APP_CONFIG.geoserver.local
            : APP_CONFIG.geoserver.production;

        this.isInitialized = true;
        console.log('✅ GeoServer client inicijalizovan');
        console.log('   parcel_server:', this.parcelServerUrl);
        console.log('   geoserver:', this.geoserverUrl);
        return true;
    }

    // ─── Health check ─────────────────────────────────────────────────────────
    // Proverava GeoServer WFS (brzo, samo capabilities)

    async healthCheck() {
        try {
            const url = `${this.geoserverUrl}/${APP_CONFIG.geoserver.workspace}/ows`
                + `?service=WFS&version=1.0.0&request=GetCapabilities`;
            const resp = await fetch(url, { signal: AbortSignal.timeout(8000) });
            return resp.ok;
        } catch (e) {
            console.warn('GeoServer health check neuspešan:', e.message);
            // Ne blokira app – nastavlja sa učitavanjem
            return true;
        }
    }

    // ─── Parcela info ─────────────────────────────────────────────────────────
    // Pokušava: 1) lokalni GeoJSON  2) GeoServer WFS

    async getParcelInfo(parcelId) {
        const safeId = String(parcelId).replace(/\//g, '_');

        // 1) Lokalni GeoJSON
        try {
            const resp = await fetch(`data/parcela_${safeId}.geojson`);
            if (resp.ok) {
                const fc = await resp.json();
                if (fc && fc.features && fc.features.length > 0) {
                    const f = fc.features[0];
                    return {
                        parcel_id:   parcelId,
                        municipality: f.properties.municipality || 'N/A',
                        area_ha:     f.properties.area_ha || null,
                        geometry:    f.geometry
                    };
                }
            }
        } catch (e) { /* nastavlja na WFS */ }

        // 2) GeoServer WFS
        try {
            const safeQ  = String(parcelId).replace(/'/g, "''");
            const katOp  = APP_CONFIG.defaultKatOpstina;
            const cql    = `brparcele='${safeQ}' AND kat_opst_1 ILIKE '${katOp}'`;
            const params = new URLSearchParams({
                service:      'WFS',
                version:      '1.0.0',
                request:      'GetFeature',
                typeName:     `${APP_CONFIG.geoserver.workspace}:${APP_CONFIG.defaultLayer}`,
                outputFormat: 'application/json',
                srsName:      'EPSG:4326',
                maxFeatures:  '1',
                CQL_FILTER:   cql
            });
            const resp = await fetch(
                `${this.geoserverUrl}/${APP_CONFIG.geoserver.workspace}/ows?${params}`
            );
            if (resp.ok) {
                const fc = await resp.json();
                if (fc && fc.features && fc.features.length > 0) {
                    const f      = fc.features[0];
                    const area_m2 = f.properties.povrsina || 0;
                    return {
                        parcel_id:    parcelId,
                        municipality: f.properties.opstina__1 || f.properties.opstina_im || 'N/A',
                        area_ha:      area_m2 ? Math.round(area_m2 / 100) / 100 : null,
                        geometry:     f.geometry
                    };
                }
            }
        } catch (e) {
            console.warn('WFS getParcelInfo neuspešan:', e.message);
        }

        return null;
    }

    // ─── CSV fetch + cache ────────────────────────────────────────────────────

    async _fetchCsv(parcelId, indexType) {
        const cacheKey = `${parcelId}_${indexType}`;
        const cached   = this._csvCache[cacheKey];
        // Keširanje 10 minuta
        if (cached && (Date.now() - cached.timestamp < 10 * 60 * 1000)) {
            return cached.rows;
        }

        const endpoint = { NDVI: '/csv', NDMI: '/ndmi_csv', NDRE: '/ndre_csv' }[indexType];
        if (!endpoint) return [];

        const params = new URLSearchParams({
            parcel:      parcelId,
            days:        String(APP_CONFIG.timeRangeDays),
            cloud:       '100',
            layer:       APP_CONFIG.defaultLayer,
            kat_opstina: APP_CONFIG.defaultKatOpstina
        });

        try {
            const resp = await fetch(`${this.parcelServerUrl}${endpoint}?${params}`);
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            const payload = await resp.json();
            if (!payload.ok || !payload.csv) {
                console.warn(`${indexType} CSV: server ok=false ili nema csv polja`);
                return [];
            }
            if (payload.stdout) {
                const dm = payload.stdout.match(/LATEST_DATE=(\d{4}-\d{2}-\d{2})/);
                if (dm) this._latestDate = dm[1];
            }
            const rows = this._parseCsv(payload.csv);
            this._csvCache[cacheKey] = { rows, timestamp: Date.now() };
            return rows;
        } catch (e) {
            console.error(`Greška pri učitavanju ${indexType} CSV:`, e.message);
            return [];
        }
    }

    _parseCsv(text) {
        if (!text || !text.trim()) return [];
        const lines   = text.trim().split(/\r?\n/);
        if (lines.length < 2) return [];
        const headers = lines[0].split(',').map(h => h.trim());
        return lines.slice(1).filter(l => l.trim()).map(line => {
            const cols = line.split(',');
            const row  = {};
            headers.forEach((key, idx) => {
                row[key] = cols[idx] !== undefined ? cols[idx].trim() : '';
            });
            return row;
        });
    }

    _toNumber(value) {
        if (value === '' || value === undefined || value === null) return null;
        const n = Number(value);
        return Number.isFinite(n) ? n : null;
    }

    _csvRowToResult(row, parcelId, indexType) {
        const dateStr = (row['C0/date'] || '').split('T')[0];
        if (!dateStr) return null;
        const mean = this._toNumber(row['C0/mean']);
        if (mean === null) return null;

        const sampleCount = parseInt(row['C0/sampleCount'] || '0') || 0;
        const noDataCount = parseInt(row['C0/noDataCount'] || '0') || 0;

        return {
            parcel_id:       parcelId,
            index_type:      indexType,
            acquisition_date: dateStr,
            mean_value:      mean,
            min_value:       this._toNumber(row['C0/min']),
            max_value:       this._toNumber(row['C0/max']),
            percentile_50:   this._toNumber(row['C0/median']),
            percentile_10:   this._toNumber(row['C0/p10']),
            percentile_90:   this._toNumber(row['C0/p90']),
            std_dev:         this._toNumber(row['C0/stDev']),
            valid_pixels:    Math.max(0, sampleCount - noDataCount),
            cloud_pixels:    noDataCount
        };
    }

    // ─── Javni metodi (isti interfejs kao supabase-client.js) ─────────────────

    async getLatestIndexResults(parcelId) {
        // Paralelni fetch sva 3 indeksa
        const [ndviRows, ndmiRows, ndreRows] = await Promise.all([
            this._fetchCsv(parcelId, 'NDVI'),
            this._fetchCsv(parcelId, 'NDMI'),
            this._fetchCsv(parcelId, 'NDRE')
        ]);

        const results = [];
        [[ndviRows, 'NDVI'], [ndmiRows, 'NDMI'], [ndreRows, 'NDRE']].forEach(([rows, idx]) => {
            const valid = rows
                .map(r => this._csvRowToResult(r, parcelId, idx))
                .filter(r => r !== null)
                .sort((a, b) => new Date(b.acquisition_date) - new Date(a.acquisition_date));
            if (valid.length > 0) results.push(valid[0]);
        });
        return results;
    }

    async getTimeSeriesData(parcelId, indexType, daysBack = 1825) {
        const rows   = await this._fetchCsv(parcelId, indexType);
        const cutoff = new Date(Date.now() - daysBack * 86400000)
            .toISOString().split('T')[0];
        return rows
            .map(r => this._csvRowToResult(r, parcelId, indexType))
            .filter(r => r !== null && r.acquisition_date >= cutoff)
            .sort((a, b) => new Date(a.acquisition_date) - new Date(b.acquisition_date));
    }

    async getAllIndexResults(parcelId, limit = 50) {
        const [ndviRows, ndmiRows, ndreRows] = await Promise.all([
            this._fetchCsv(parcelId, 'NDVI'),
            this._fetchCsv(parcelId, 'NDMI'),
            this._fetchCsv(parcelId, 'NDRE')
        ]);

        const all = [];
        [[ndviRows, 'NDVI'], [ndmiRows, 'NDMI'], [ndreRows, 'NDRE']].forEach(([rows, idx]) => {
            rows.forEach(r => {
                const result = this._csvRowToResult(r, parcelId, idx);
                if (result) all.push(result);
            });
        });
        return all
            .sort((a, b) => new Date(b.acquisition_date) - new Date(a.acquisition_date))
            .slice(0, limit);
    }

    async getZoneClassifications(parcelId, indexType) {
        if (indexType !== 'NDRE') return [];

        try {
            const params = new URLSearchParams({
                parcel:      parcelId,
                layer:       APP_CONFIG.defaultLayer,
                kat_opstina: APP_CONFIG.defaultKatOpstina
            });
            const resp = await fetch(`${this.parcelServerUrl}/zone_stats?${params}`);
            if (resp.ok) {
                const data = await resp.json();
                if (data.ok && data.total > 0) {
                    return [
                        { zone_type: 'red',    percentage: data.red_pct,    recommendation: 'Dodaj više azota. NDRE ispod 0.14 ukazuje na deficit azota.' },
                        { zone_type: 'yellow', percentage: data.yellow_pct, recommendation: 'Standardna obrada. NDRE u optimalnom opsegu 0.14–0.19.' },
                        { zone_type: 'green',  percentage: data.green_pct,  recommendation: 'Može manje azota. NDRE ≥ 0.19 – dobro zdravlje useva.' }
                    ];
                }
            }
        } catch (e) {
            console.warn('zone_stats greška:', e.message);
        }
        return [];
    }

    // ─── Refresh rasterskih lejera ────────────────────────────────────────────
    // Poziva parcel_server /run, /ndmi, /ndre → download GeoTIFF → upload GeoServer

    async refreshRasterLayer(parcelId, indexType) {
        const endpoint = { NDVI: '/run', NDMI: '/ndmi', NDRE: '/ndre', NDRE_VALUE: '/ndre_value' }[indexType];
        if (!endpoint) return null;

        const params = new URLSearchParams({
            parcel:      parcelId,
            days:        '30',
            cloud:       '80',
            layer:       APP_CONFIG.defaultLayer,
            kat_opstina: APP_CONFIG.defaultKatOpstina
        });
        if (this._latestDate) {
            params.set('date', this._latestDate);
        }

        console.log(`[refresh] Pokrećem ${indexType} raster download (date=${this._latestDate || 'auto'})...`);
        const resp = await fetch(`${this.parcelServerUrl}${endpoint}?${params}`);
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const payload = await resp.json();
        console.log(`[refresh] ${indexType} done:`, (payload.stdout || '').split('\n').slice(-2).join(' | '));
        return payload;
    }

    async refreshAllRasterLayers(parcelId) {
        const results = await Promise.allSettled([
            this.refreshRasterLayer(parcelId, 'NDVI'),
            this.refreshRasterLayer(parcelId, 'NDMI'),
            this.refreshRasterLayer(parcelId, 'NDRE'),
            this.refreshRasterLayer(parcelId, 'NDRE_VALUE')
        ]);
        const names = ['NDVI', 'NDMI', 'NDRE', 'NDRE_VALUE'];
        results.forEach((r, i) => {
            if (r.status === 'rejected') console.warn(`[refresh] ${names[i]} neuspešan:`, r.reason?.message);
        });
        return results;
    }

    // Zone geometrije – iz lokalnog GeoJSON fajla
    async getZoneGeometries(parcelId, indexType) {
        if (indexType !== 'NDRE') return [];
        const safeId = String(parcelId).replace(/\//g, '_');
        try {
            const resp = await fetch(`data/ndre_zones_${safeId}.geojson`);
            if (!resp.ok) return [];
            const fc = await resp.json();
            if (!fc || !fc.features) return [];

            const zoneTypes = ['red', 'yellow', 'green'];
            return zoneTypes.map(zt => ({
                zone_type: zt,
                geometry: {
                    type: 'FeatureCollection',
                    features: fc.features.filter(
                        f => (f.properties.zone_type || f.properties.zone) === zt
                    )
                }
            })).filter(z => z.geometry.features.length > 0);
        } catch (e) {
            return [];
        }
    }
}

// Isti naziv kao u web2 da app.js radi bez izmena
const supabaseClient = new GeoServerClient();
