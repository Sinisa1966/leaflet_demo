// Map Management – web3 (GeoServer WMS lejeri, prava geometrija parcele)

// Ugrađena geometrija parcele 1427/2 DUBOVAC – iz DKP katastra (fallback)
const PARCEL_1427_2_GEOM = {
    type: 'Feature',
    properties: { parcel_id: '1427/2', municipality: 'Kovin', area_ha: 4.46 },
    geometry: {
        type: 'MultiPolygon',
        coordinates: [[[[21.1992,44.8151],[21.199,44.8154],[21.1989,44.8155],[21.1986,44.8159],
                        [21.1987,44.8162],[21.1987,44.8163],[21.2002,44.8169],[21.202,44.8152],
                        [21.2,44.8142],[21.1996,44.8145],[21.1995,44.8147],[21.1992,44.8151]]]]
    }
};

class MapManager {
    constructor(containerId) {
        this.containerId = containerId;
        this.map         = null;
        this.parcelLayer = null;
        this.zoneLayer   = null;
        this.indexLayers  = {};
        this.wmsBase      = '';
        this.activeIndex  = 'NDRE';
    }

    async init() {
        this.map = L.map(this.containerId).setView(
            APP_CONFIG.map.center,
            APP_CONFIG.map.zoom
        );

        const tileOpts = {
            maxZoom: APP_CONFIG.map.maxZoom,
            minZoom: APP_CONFIG.map.minZoom
        };

        this.baseLayers = {
            'Satelit': L.tileLayer(
                'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
                { attribution: 'Tiles © Esri', ...tileOpts }
            ),
            'Google Earth': L.tileLayer(
                'https://mt{s}.google.com/vt/lyrs=s&x={x}&y={y}&z={z}',
                { subdomains: '0123', attribution: '© Google', ...tileOpts }
            ),
            'OSM': L.tileLayer(
                'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
                { attribution: '© OpenStreetMap contributors', ...tileOpts }
            )
        };
        this.baseLayers['Satelit'].addTo(this.map);

        // GeoServer WMS lejeri za NDVI, NDMI, NDRE
        const isLocal = (
            window.location.hostname === 'localhost' ||
            window.location.hostname === '127.0.0.1' ||
            window.location.protocol === 'file:'
        );
        this.wmsBase = (isLocal
            ? APP_CONFIG.geoserver.local
            : APP_CONFIG.geoserver.production)
            + `/${APP_CONFIG.geoserver.workspace}/wms`;
        const wmsBase = this.wmsBase;

        const wmsOpts = {
            format:      'image/png',
            transparent: true,
            styles:      '',   // prazan = default stil u GeoServeru (isti kao leaflet_demo.html)
            updateWhenIdle: true,
            updateWhenZooming: false
        };

        this.indexLayers.ndvi = L.tileLayer.wms(wmsBase, {
            ...wmsOpts,
            layers:      APP_CONFIG.wmsLayers.ndvi,
            attribution: 'Sentinel-2 NDVI',
            opacity:     0
        });
        this.indexLayers.ndmi = L.tileLayer.wms(wmsBase, {
            ...wmsOpts,
            layers:      APP_CONFIG.wmsLayers.ndmi,
            attribution: 'Sentinel-2 NDMI',
            opacity:     0
        });
        this.indexLayers.ndre = L.tileLayer.wms(wmsBase, {
            ...wmsOpts,
            layers:      APP_CONFIG.wmsLayers.ndre,
            attribution: 'Sentinel-2 NDRE',
            opacity:     0.7
        });
        this.indexLayers.ndreZones = L.tileLayer.wms(wmsBase, {
            ...wmsOpts,
            layers:      APP_CONFIG.wmsLayers.ndreZones,
            styles:      'ndre_zones_percentile_style',
            attribution: 'Sentinel-2 NDRE Zone',
            opacity:     0
        });

        this.indexLayers.ndvi.addTo(this.map);
        this.indexLayers.ndmi.addTo(this.map);
        this.indexLayers.ndre.addTo(this.map);
        this.indexLayers.ndreZones.addTo(this.map);

        const overlays = {
            'NDVI': this.indexLayers.ndvi,
            'NDMI': this.indexLayers.ndmi,
            'NDRE': this.indexLayers.ndre,
            'NDRE Zone': this.indexLayers.ndreZones
        };
        L.control.layers(this.baseLayers, overlays, {
            position: 'topright',
            collapsed: true
        }).addTo(this.map);

        this._bindOpacitySliders();
        this._setupClickHandler();

        this.map.whenReady(() => {
            this.loadParcelGeometry({ parcel_id: APP_CONFIG.defaultParcel });
        });

        console.log('Map initialized (web3, GeoServer WMS)');
    }

    _bindOpacitySliders() {
        const bind = (id, layer) => {
            const el = document.getElementById(id);
            if (!el || !layer) return;
            el.addEventListener('input', () => {
                const opacity = parseInt(el.value, 10) / 100;
                layer.setOpacity(opacity);
                if (opacity > 0 && !this.map.hasLayer(layer)) layer.addTo(this.map);
            });
        };
        bind('ndviOpacity', this.indexLayers.ndvi);
        bind('ndmiOpacity', this.indexLayers.ndmi);
        bind('ndreOpacity', this.indexLayers.ndre);
        bind('ndreZonesOpacity', this.indexLayers.ndreZones);
    }

    normalizeParcelGeometry(geometry) {
        if (!geometry) return null;
        const geom = geometry.type === 'Feature' ? geometry.geometry : geometry;
        if (!geom || !geom.coordinates) return null;

        let coords = geom.coordinates;

        if (geom.type === 'MultiPolygon') {
            return { type: 'Feature', properties: {}, geometry: geom };
        }

        if (coords.length > 0 && typeof coords[0] === 'number') {
            const ring = [];
            for (let i = 0; i < coords.length; i += 2) ring.push([coords[i], coords[i + 1]]);
            coords = [ring];
        } else if (coords.length > 0 && Array.isArray(coords[0]) && coords[0].length > 2 && typeof coords[0][0] === 'number') {
            const ring = [];
            for (let i = 0; i < coords[0].length; i += 2) ring.push([coords[0][i], coords[0][i + 1]]);
            coords = [ring];
        } else if (coords.length > 0 && Array.isArray(coords[0]) && !Array.isArray(coords[0][0])) {
            coords = [coords];
        }

        coords = coords.map(ring => {
            if (!Array.isArray(ring)) return ring;
            const out = [];
            for (let i = 0; i < ring.length; i++) {
                const pos = ring[i];
                if (Array.isArray(pos) && pos.length === 2 && typeof pos[0] === 'number') {
                    out.push([pos[0], pos[1]]);
                } else if (Array.isArray(pos) && pos.length === 4) {
                    out.push([pos[0], pos[1]], [pos[2], pos[3]]);
                }
            }
            return out;
        });

        return { type: 'Feature', properties: {}, geometry: { type: geom.type || 'Polygon', coordinates: coords } };
    }

    async loadParcelGeometry(parcelData) {
        let geoFeature = null;
        const parcelId   = parcelData ? parcelData.parcel_id : APP_CONFIG.defaultParcel;
        let municipality = parcelData ? parcelData.municipality : 'Kovin';
        let areaHa       = parcelData ? parcelData.area_ha : 4.46;

        if (parcelData && parcelData.geometry) {
            geoFeature = this.normalizeParcelGeometry(parcelData.geometry);
        }

        // Fallback 1: ugrađena geometrija za 1427/2
        if (!geoFeature && String(parcelId).replace(/\//g, '_') === '1427_2') {
            geoFeature   = PARCEL_1427_2_GEOM;
            municipality = geoFeature.properties.municipality || municipality;
            areaHa       = geoFeature.properties.area_ha      || areaHa;
        }

        // Fallback 2: lokalni GeoJSON
        if (!geoFeature) {
            const safeId = String(parcelId).replace(/\//g, '_');
            try {
                const resp = await fetch(`data/parcela_${safeId}.geojson`);
                if (resp.ok) {
                    const fc = await resp.json();
                    if (fc && fc.features && fc.features.length > 0) {
                        geoFeature   = fc.features[0];
                        municipality = geoFeature.properties.municipality || municipality;
                        areaHa       = geoFeature.properties.area_ha      || areaHa;
                    }
                }
            } catch (e) { /* nastavlja */ }
        }

        if (!geoFeature) {
            console.error('Nema geometrije za parcelu', parcelId);
            return;
        }

        if (this.parcelLayer) {
            this.map.removeLayer(this.parcelLayer);
            this.parcelLayer = null;
        }

        this.parcelLayer = L.geoJSON(geoFeature, {
            style: {
                color:       '#FF0000',
                weight:      5,
                opacity:     1,
                fillColor:   'transparent',
                fillOpacity: 0
            },
            interactive: false
        }).addTo(this.map);
        this.parcelLayer.bringToFront();

        try {
            if (this.parcelLayer.getLayers().length === 0) {
                this.map.setView(APP_CONFIG.map.center, APP_CONFIG.map.zoom);
            } else {
                const bounds = this.parcelLayer.getBounds();
                const sw = bounds.getSouthWest();
                const ne = bounds.getNorthEast();
                const hasArea = sw && ne &&
                    isFinite(sw.lat) && isFinite(sw.lng) &&
                    isFinite(ne.lat) && isFinite(ne.lng) &&
                    (sw.lat !== ne.lat || sw.lng !== ne.lng);
                if (hasArea) {
                    this.map.fitBounds(bounds, { padding: [80, 80], maxZoom: 17 });
                } else {
                    this.map.setView(APP_CONFIG.map.center, APP_CONFIG.map.zoom);
                }
            }
        } catch (e) {
            this.map.setView(APP_CONFIG.map.center, APP_CONFIG.map.zoom);
        }

        console.log('Parcel geometry loaded');
    }

    normalizeZoneGeometry(geometry) {
        if (!geometry || !geometry.coordinates) return null;
        const outRings = [];
        for (const ring of geometry.coordinates) {
            if (!Array.isArray(ring)) continue;
            const outRing = [];
            for (const pos of ring) {
                if (Array.isArray(pos) && pos.length === 2 && typeof pos[0] === 'number') {
                    outRing.push([pos[0], pos[1]]);
                } else if (Array.isArray(pos) && pos.length === 4) {
                    outRing.push([pos[0], pos[1]], [pos[2], pos[3]]);
                }
            }
            if (outRing.length > 0) outRings.push(outRing);
        }
        if (outRings.length === 0) return null;
        return { type: geometry.type || 'Polygon', coordinates: outRings };
    }

    async loadZoneGeometries(zoneData) {
        if (this.zoneLayer) {
            this.map.removeLayer(this.zoneLayer);
        }
        if (!zoneData || zoneData.length === 0) return;

        const features = [];
        zoneData.forEach(zone => {
            if (zone.geometry && zone.geometry.features) {
                zone.geometry.features.forEach(feature => {
                    const normalized = this.normalizeZoneGeometry(feature.geometry);
                    if (!normalized) return;
                    features.push({
                        type: 'Feature',
                        properties: { ...(feature.properties || {}), zone_type: zone.zone_type },
                        geometry: normalized
                    });
                });
            }
        });

        if (features.length === 0) return;

        this.zoneLayer = L.geoJSON(
            { type: 'FeatureCollection', features },
            {
                style: feature => {
                    const zt    = feature.properties.zone_type || feature.properties.zone;
                    const color = APP_CONFIG.zoneColors[zt] || '#999';
                    return { fillColor: color, weight: 1, opacity: 0.8, color, fillOpacity: 0.5 };
                },
                onEachFeature: (feature, layer) => {
                    const zt    = feature.properties.zone_type || feature.properties.zone;
                    const value = feature.properties.value || 'N/A';
                    const name  = { red: 'Problematična zona', yellow: 'Umerena zona', green: 'Dobra zona' }[zt] || zt;
                    layer.bindPopup(`<strong>${name}</strong><br>NDRE: ${typeof value === 'number' ? value.toFixed(3) : value}`);
                }
            }
        ).addTo(this.map);
    }

    createDummyZones(parcelGeometry) {
        if (!parcelGeometry || !parcelGeometry.coordinates) return [];

        const geom = parcelGeometry.type === 'MultiPolygon'
            ? { type: 'Polygon', coordinates: parcelGeometry.coordinates[0] }
            : parcelGeometry;

        const normalized = this.normalizeParcelGeometry(geom);
        if (!normalized || !normalized.geometry || !normalized.geometry.coordinates) return [];

        const coords = normalized.geometry.coordinates[0];
        if (!coords || coords.length < 4) return [];

        const lngs = coords.map(c => c[0]);
        const lats = coords.map(c => c[1]);
        const minLng = Math.min(...lngs), maxLng = Math.max(...lngs);
        const minLat = Math.min(...lats), maxLat = Math.max(...lats);
        const latStep = (maxLat - minLat) / 3;

        return ['red', 'yellow', 'green'].map((zt, i) => ({
            zone_type: zt,
            geometry: {
                type: 'FeatureCollection',
                features: [{
                    type: 'Feature',
                    properties: { zone: zt, value: [0.12, 0.17, 0.22][i] },
                    geometry: {
                        type: 'Polygon',
                        coordinates: [[
                            [minLng, minLat + latStep * i],
                            [maxLng, minLat + latStep * i],
                            [maxLng, minLat + latStep * (i + 1)],
                            [minLng, minLat + latStep * (i + 1)],
                            [minLng, minLat + latStep * i]
                        ]]
                    }
                }]
            }
        }));
    }

    _setupClickHandler() {
        this.map.on('click', async (e) => {
            const idx = this.activeIndex;
            const valueLayerMap = {
                NDVI: APP_CONFIG.wmsLayers.ndviValue,
                NDMI: APP_CONFIG.wmsLayers.ndmiValue,
                NDRE: APP_CONFIG.wmsLayers.ndreValue
            };
            const valueLayer = valueLayerMap[idx];
            if (!valueLayer) return;

            const size = this.map.getSize();
            const bounds = this.map.getBounds();
            const bbox = [
                bounds.getSouthWest().lng, bounds.getSouthWest().lat,
                bounds.getNorthEast().lng, bounds.getNorthEast().lat
            ].join(',');

            const point = this.map.latLngToContainerPoint(e.latlng);
            const url = this.wmsBase
                + '?SERVICE=WMS&VERSION=1.1.1&REQUEST=GetFeatureInfo'
                + '&LAYERS=' + encodeURIComponent(valueLayer)
                + '&QUERY_LAYERS=' + encodeURIComponent(valueLayer)
                + '&STYLES=raster'
                + '&BBOX=' + bbox
                + '&WIDTH=' + size.x
                + '&HEIGHT=' + size.y
                + '&SRS=EPSG:4326'
                + '&INFO_FORMAT=application/json'
                + '&X=' + Math.round(point.x)
                + '&Y=' + Math.round(point.y);

            try {
                const resp = await fetch(url);
                if (!resp.ok) {
                    L.popup().setLatLng(e.latlng)
                        .setContent(`<strong>${idx}</strong><br>Greška pri čitanju vrednosti`)
                        .openOn(this.map);
                    return;
                }
                const data = await resp.json();
                const value = this._extractValue(data);
                const html = this._buildPopupHtml(idx, value, e.latlng);
                L.popup().setLatLng(e.latlng).setContent(html).openOn(this.map);
            } catch (err) {
                console.warn('GetFeatureInfo greška:', err);
                L.popup().setLatLng(e.latlng)
                    .setContent(`<strong>${idx}</strong><br>n/a`)
                    .openOn(this.map);
            }
        });
    }

    _extractValue(gfiData) {
        if (!gfiData || !gfiData.features || gfiData.features.length === 0) return null;
        const props = gfiData.features[0].properties || {};
        const raw = props.GRAY_INDEX ?? props.gray_index ?? props.BAND_1 ?? props.band_1 ?? null;
        if (raw === null || raw === undefined) return null;
        const v = parseFloat(raw);
        if (isNaN(v) || v === -999 || v === -9999) return null;
        if (v === 0) return null;
        return v;
    }

    _buildPopupHtml(indexType, value, latlng) {
        const lat = latlng.lat.toFixed(6);
        const lng = latlng.lng.toFixed(6);
        if (value === null) {
            return `<strong>${indexType} Vrednost:</strong> n/a<br>`
                + `<small style="color:#888">Van rastera ili NoData</small><br>`
                + `<small style="color:#aaa">${lat}, ${lng}</small>`;
        }
        const formatted = value.toFixed(4);
        let interpretation = '';
        let color = '#333';

        if (indexType === 'NDVI') {
            if (value < 0.2)       { interpretation = 'Golo tlo / bez vegetacije'; color = '#8B4513'; }
            else if (value < 0.4)  { interpretation = 'Slaba vegetacija';          color = '#DAA520'; }
            else if (value < 0.6)  { interpretation = 'Umerena vegetacija';        color = '#9ACD32'; }
            else if (value < 0.8)  { interpretation = 'Gusta vegetacija';          color = '#228B22'; }
            else                   { interpretation = 'Veoma gusta vegetacija';    color = '#006400'; }
        } else if (indexType === 'NDMI') {
            if (value < -0.2)      { interpretation = 'Suvo zemljište';            color = '#8B4513'; }
            else if (value < 0)    { interpretation = 'Niska vlažnost';            color = '#DAA520'; }
            else if (value < 0.2)  { interpretation = 'Umerena vlažnost';          color = '#4682B4'; }
            else if (value < 0.4)  { interpretation = 'Visoka vlažnost';           color = '#1E90FF'; }
            else                   { interpretation = 'Veoma visoka vlažnost';     color = '#0000CD'; }
        } else if (indexType === 'NDRE') {
            if (value < 0.14)      { interpretation = 'Problematična zona';        color = '#FF4444'; }
            else if (value < 0.19) { interpretation = 'Umerena zona';              color = '#DAA520'; }
            else                   { interpretation = 'Dobra zona';                color = '#44FF44'; }
        }

        return `<div style="min-width:180px">`
            + `<strong>${indexType} Vrednost:</strong> <span style="font-size:16px;color:${color}">${formatted}</span><br>`
            + `<strong>Tumačenje:</strong> <span style="color:${color}">${interpretation}</span><br>`
            + `<small style="color:#aaa">${lat}, ${lng}</small>`
            + `</div>`;
    }

    showIndexLayer(indexType) {
        this.activeIndex = indexType;
        const key = indexType.toLowerCase();
        const opacityMap = { ndvi: 0, ndmi: 0, ndre: 0, ndreZones: 0 };
        opacityMap[key] = 0.7;

        Object.entries(this.indexLayers).forEach(([k, layer]) => {
            layer.setOpacity(opacityMap[k] || 0);
        });

        const sliderMap = { ndvi: 'ndviOpacity', ndmi: 'ndmiOpacity', ndre: 'ndreOpacity', ndreZones: 'ndreZonesOpacity' };
        Object.entries(sliderMap).forEach(([k, id]) => {
            const el = document.getElementById(id);
            if (el) el.value = (opacityMap[k] || 0) * 100;
        });
    }

    refreshWmsLayers() {
        const ts = Date.now();
        Object.values(this.indexLayers).forEach(layer => {
            if (layer && layer.setParams) {
                layer.setParams({ _ts: ts }, /* noRedraw */ false);
            }
        });
        console.log('[map] WMS lejeri osveženi (cache-bust ts=' + ts + ')');
    }

    // Prikazuje/sakriva indikator "osvežavam rastere..." na mapi
    showRasterStatus(message) {
        let el = document.getElementById('rasterStatusBanner');
        if (!el) {
            el = document.createElement('div');
            el.id = 'rasterStatusBanner';
            el.style.cssText = [
                'position:absolute', 'bottom:8px', 'left:50%', 'transform:translateX(-50%)',
                'background:rgba(0,0,0,0.72)', 'color:#fff', 'padding:5px 14px',
                'border-radius:16px', 'font-size:12px', 'z-index:1000',
                'pointer-events:none', 'white-space:nowrap'
            ].join(';');
            document.getElementById('map').style.position = 'relative';
            document.getElementById('map').appendChild(el);
        }
        if (message) {
            el.textContent = message;
            el.style.display = 'block';
        } else {
            el.style.display = 'none';
        }
    }

    clearLayers() {
        if (this.parcelLayer) this.map.removeLayer(this.parcelLayer);
        if (this.zoneLayer)   this.map.removeLayer(this.zoneLayer);
    }
}

let mapManager;

document.addEventListener('DOMContentLoaded', () => {
    mapManager = new MapManager('map');
    mapManager.init();
});
