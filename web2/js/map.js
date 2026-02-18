// Map Management - Leaflet Integration

// Ugrađena geometrija parcele 1427/2 (iz web2/data/parcela_1427_2.geojson) – fallback ako fetch ne uspe
const PARCEL_1427_2_GEOM = {
    type: 'Feature',
    properties: { parcel_id: '1427/2', municipality: 'Kovin', area_ha: 0.5 },
    geometry: {
        type: 'Polygon',
        coordinates: [[[21.1986, 44.8142], [21.2021, 44.8142], [21.2021, 44.8182], [21.1986, 44.8182], [21.1986, 44.8142]]]
    }
};

// Bounds parcele 1427/2 za L.imageOverlay [[south, west], [north, east]]
const PARCEL_1427_2_BOUNDS = [[44.8142, 21.1986], [44.8182, 21.2021]];

class MapManager {
    constructor(containerId) {
        this.containerId = containerId;
        this.map = null;
        this.parcelLayer = null;
        this.zoneLayer = null;
        this.currentZones = [];
        this.indexLayers = {};  // NDVI, NDMI, NDRE WMS
    }

    /**
     * Initialize map
     */
    async init() {
        // Create map
        this.map = L.map(this.containerId).setView(
            APP_CONFIG.map.center,
            APP_CONFIG.map.zoom
        );

        const tileOpts = {
            maxZoom: APP_CONFIG.map.maxZoom,
            minZoom: APP_CONFIG.map.minZoom
        };

        // Pozadinske slojevi: Satelit, Google Earth, OSM
        this.baseLayers = {
            'Satelit': L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
                attribution: 'Tiles © Esri',
                ...tileOpts
            }),
            'Google Earth': L.tileLayer('https://mt{s}.google.com/vt/lyrs=s&x={x}&y={y}&z={z}', {
                subdomains: '0123',
                attribution: '© Google',
                ...tileOpts
            }),
            'OSM': L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                attribution: '© OpenStreetMap contributors',
                ...tileOpts
            })
        };

        // Podrazumevano: Satelit
        this.baseLayers['Satelit'].addTo(this.map);

        // NDVI, NDMI, NDRE iz PNG (L.imageOverlay)
        this._createIndexLayers(APP_CONFIG.defaultParcel);

        const overlays = {
            'NDVI': this.indexLayers.ndvi,
            'NDMI': this.indexLayers.ndmi,
            'NDRE': this.indexLayers.ndre
        };
        L.control.layers(this.baseLayers, overlays, {
            position: 'topright',
            collapsed: true
        }).addTo(this.map);

        this.indexLayers.ndvi.setOpacity(0.3);
        this.indexLayers.ndvi.addTo(this.map);
        this.indexLayers.ndmi.addTo(this.map);
        this.indexLayers.ndre.addTo(this.map);

        this._bindOpacitySliders();

        // Učitaj parcelu 1427/2 odmah i podesi zoom da se vidi u okviru prozora
        this.map.whenReady(() => {
            this.loadParcelGeometry({ parcel_id: APP_CONFIG.defaultParcel });
        });

        console.log('✅ Map initialized');
    }

    /**
     * Povezuje klizače transparentnosti sa NDVI, NDMI, NDRE lejerima
     */
    _bindOpacitySliders() {
        const bind = (id, layer) => {
            const el = document.getElementById(id);
            if (!el || !layer) return;
            el.addEventListener('input', () => {
                const opacity = parseInt(el.value, 10) / 100;
                if (layer.setOpacity) layer.setOpacity(opacity);
                if (opacity > 0 && !this.map.hasLayer(layer)) layer.addTo(this.map);
            });
        };
        bind('ndviOpacity', this.indexLayers.ndvi);
        bind('ndmiOpacity', this.indexLayers.ndmi);
        bind('ndreOpacity', this.indexLayers.ndre);
    }

    /**
     * Kreira NDVI, NDMI, NDRE lejere iz PNG (L.imageOverlay) – gradijent kao na GeoServeru.
     * PNG: data/ndvi_1427_2.png, data/ndmi_1427_2.png, data/ndre_zones_1427_2.png
     */
    _createIndexLayers(parcelId) {
        const safeId = String(parcelId || '1427_2').replace(/\//g, '_');
        const bounds = (safeId === '1427_2') ? PARCEL_1427_2_BOUNDS : [[44.8142, 21.1986], [44.8182, 21.2021]];

        this.indexLayers.ndvi = L.imageOverlay(`data/ndvi_${safeId}.png`, bounds, { opacity: 0 });
        this.indexLayers.ndmi = L.imageOverlay(`data/ndmi_${safeId}.png`, bounds, { opacity: 0 });
        this.indexLayers.ndre = L.imageOverlay(`data/ndre_zones_${safeId}.png`, bounds, { opacity: 0 });

        this.indexLayers.ndvi.setOpacity(0.3);
        this.indexLayers.ndmi.setOpacity(0);
        this.indexLayers.ndre.setOpacity(0);
    }

    /**
     * Normalize geometry from Supabase to valid GeoJSON for Leaflet
     * Supabase/PostgREST can return coordinates in unexpected format
     */
    normalizeParcelGeometry(geometry) {
        if (!geometry) return null;
        // If already a Feature, extract geometry and normalize
        const geom = geometry.type === 'Feature' ? geometry.geometry : geometry;
        if (!geom || !geom.coordinates) return null;

        let coords = geom.coordinates;

        // GeoJSON Polygon: coordinates = [ ring1, ring2, ... ], ring = [ [lng,lat], [lng,lat], ... ]
        // If first element is a number, array was flattened - convert back to pairs
        if (coords.length > 0 && typeof coords[0] === 'number') {
            const ring = [];
            for (let i = 0; i < coords.length; i += 2) {
                ring.push([coords[i], coords[i + 1]]);
            }
            coords = [ring];
        }
        // If we have one ring but it's not nested (array of pairs became flat)
        else if (coords.length > 0 && Array.isArray(coords[0]) && coords[0].length > 2 && typeof coords[0][0] === 'number') {
            const flat = coords[0];
            const ring = [];
            for (let i = 0; i < flat.length; i += 2) {
                ring.push([flat[i], flat[i + 1]]);
            }
            coords = [ring];
        }
        // Ensure Polygon has array of rings (array of array of [lng,lat])
        else if (coords.length > 0 && Array.isArray(coords[0]) && !Array.isArray(coords[0][0])) {
            coords = [coords];
        }

        // Ensure every position is [lng, lat] (2 numbers). If any element has 4 numbers, split into two points.
        coords = coords.map(function(ring) {
            if (!Array.isArray(ring)) return ring;
            var out = [];
            for (var i = 0; i < ring.length; i++) {
                var pos = ring[i];
                if (Array.isArray(pos) && pos.length === 2 && typeof pos[0] === 'number') {
                    out.push([pos[0], pos[1]]);
                } else if (Array.isArray(pos) && pos.length === 4) {
                    out.push([pos[0], pos[1]], [pos[2], pos[3]]);
                }
            }
            return out;
        });

        return {
            type: 'Feature',
            properties: {},
            geometry: {
                type: geom.type || 'Polygon',
                coordinates: coords
            }
        };
    }

    /**
     * Load parcel geometry (iz Supabase ili lokalnog GeoJSON fallback)
     */
    async loadParcelGeometry(parcelData) {
        let geoFeature = null;
        let parcelId = parcelData ? parcelData.parcel_id : APP_CONFIG.defaultParcel;
        let municipality = parcelData ? parcelData.municipality : 'Kovin';
        let areaHa = parcelData ? parcelData.area_ha : 0.5;

        if (parcelData && parcelData.geometry) {
            geoFeature = this.normalizeParcelGeometry(parcelData.geometry);
        }

        // Fallback 1: ugrađena geometrija za parcelu 1427/2 (bilo koji format ID-a)
        const is1427_2 = String(parcelId || '').replace(/\//g, '_') === '1427_2';
        if (!geoFeature && is1427_2) {
            geoFeature = PARCEL_1427_2_GEOM;
            municipality = geoFeature.properties.municipality || municipality;
            areaHa = geoFeature.properties.area_ha || areaHa;
        }

        // Fallback 2: učitaj iz lokalnog GeoJSON (data/parcela_*.geojson)
        if (!geoFeature) {
            const safeId = (parcelId || '1427_2').replace(/\//g, '_');
            try {
                const resp = await fetch(`data/parcela_${safeId}.geojson`);
                if (resp.ok) {
                    const fc = await resp.json();
                    if (fc && fc.features && fc.features.length > 0) {
                        geoFeature = fc.features[0];
                        if (geoFeature.properties) {
                            municipality = geoFeature.properties.municipality || municipality;
                            areaHa = geoFeature.properties.area_ha || areaHa;
                        }
                    }
                }
            } catch (e) {
                console.warn('Fallback GeoJSON nije učitan:', e);
            }
        }

        if (!geoFeature) {
            console.error('Nema geometrije za parcelu ' + parcelId);
            return;
        }

        // Tek sada ukloni stari sloj (da ne nestane ako drugi poziv nema geoFeature)
        if (this.parcelLayer) {
            this.map.removeLayer(this.parcelLayer);
            this.parcelLayer = null;
        }

        // Add parcel boundary – jako vidljive granice (crveno + žuto kao highlight)
        this.parcelLayer = L.geoJSON(geoFeature, {
            style: {
                color: '#FF0000',
                weight: 5,
                opacity: 1,
                fillColor: '#FFD700',
                fillOpacity: 0.25
            },
            onEachFeature: (feature, layer) => {
                layer.bindPopup(`
                    <strong>Parcela ${parcelId}</strong><br>
                    Opština: ${municipality}<br>
                    Površina: ${areaHa} ha
                `);
            }
        }).addTo(this.map);
        this.parcelLayer.bringToFront();  // Granice uvek iznad NDVI/NDMI/NDRE

        // Fit map to parcel bounds; if bounds invalid or empty layer, use default center/zoom
        try {
            if (this.parcelLayer.getLayers().length === 0) {
                this.map.setView(APP_CONFIG.map.center, APP_CONFIG.map.zoom);
            } else {
                const bounds = this.parcelLayer.getBounds();
                const sw = bounds.getSouthWest();
                const ne = bounds.getNorthEast();
                const hasArea = sw && ne &&
                    isFinite(sw.lat) && isFinite(sw.lng) && isFinite(ne.lat) && isFinite(ne.lng) &&
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

        console.log('✅ Parcel geometry loaded');
    }

    /**
     * Normalize one Polygon geometry so every position is [lng, lat] (2 numbers).
     * Supabase/PostgREST can return positions as 4-number arrays.
     */
    normalizeZoneGeometry(geometry) {
        if (!geometry || !geometry.coordinates) return null;
        const coords = geometry.coordinates;
        const outRings = [];
        for (let r = 0; r < coords.length; r++) {
            const ring = coords[r];
            if (!Array.isArray(ring)) continue;
            const outRing = [];
            for (let i = 0; i < ring.length; i++) {
                const pos = ring[i];
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

    /**
     * Load zone geometries (NDRE zones)
     */
    async loadZoneGeometries(zoneData) {
        // Remove existing zone layer
        if (this.zoneLayer) {
            this.map.removeLayer(this.zoneLayer);
        }

        if (!zoneData || zoneData.length === 0) {
            console.log('No zone data to display');
            return;
        }

        // Create feature collection from all zones; normalize each feature's geometry
        const features = [];
        
        zoneData.forEach(zone => {
            if (zone.geometry && zone.geometry.features) {
                zone.geometry.features.forEach(feature => {
                    const geom = feature.geometry;
                    const normalized = this.normalizeZoneGeometry(geom);
                    if (!normalized) return;
                    features.push({
                        type: 'Feature',
                        properties: {
                            ...(feature.properties || {}),
                            zone_type: zone.zone_type
                        },
                        geometry: normalized
                    });
                });
            }
        });

        if (features.length === 0) {
            console.log('No features in zone data');
            return;
        }

        // Add zones to map
        this.zoneLayer = L.geoJSON({
            type: 'FeatureCollection',
            features: features
        }, {
            style: (feature) => {
                const zoneType = feature.properties.zone_type || feature.properties.zone;
                const color = APP_CONFIG.zoneColors[zoneType] || '#999';
                
                return {
                    fillColor: color,
                    weight: 1,
                    opacity: 0.8,
                    color: color,
                    fillOpacity: 0.5
                };
            },
            onEachFeature: (feature, layer) => {
                const zoneType = feature.properties.zone_type || feature.properties.zone;
                const value = feature.properties.value || 'N/A';
                
                const zoneName = {
                    'red': 'Problematična zona',
                    'yellow': 'Umerena zona',
                    'green': 'Dobra zona'
                }[zoneType] || zoneType;

                layer.bindPopup(`
                    <strong>${zoneName}</strong><br>
                    NDRE: ${typeof value === 'number' ? value.toFixed(3) : value}
                `);
            }
        }).addTo(this.map);

        console.log(`✅ Loaded ${features.length} zone features`);
    }

    /**
     * Create dummy zone geometries (ako nema u bazi)
     */
    createDummyZones(parcelGeometry) {
        if (!parcelGeometry || !parcelGeometry.coordinates) {
            return [];
        }

        // Use same normalization as parcel so we get valid [lng,lat] pairs
        const normalized = this.normalizeParcelGeometry({ type: 'Polygon', coordinates: parcelGeometry.coordinates });
        if (!normalized || !normalized.geometry || !normalized.geometry.coordinates) {
            return [];
        }

        const coords = normalized.geometry.coordinates[0];
        if (!coords || coords.length < 4) {
            return [];
        }

        // Calculate bounds (coords are now [lng, lat] pairs)
        const lngs = coords.map(c => c[0]);
        const lats = coords.map(c => c[1]);
        const minLng = Math.min(...lngs);
        const maxLng = Math.max(...lngs);
        const minLat = Math.min(...lats);
        const maxLat = Math.max(...lats);

        // Split parcel into 3 horizontal zones
        const latStep = (maxLat - minLat) / 3;

        const zones = [
            {
                zone_type: 'red',
                geometry: {
                    type: 'FeatureCollection',
                    features: [{
                        type: 'Feature',
                        properties: { zone: 'red', value: 0.12 },
                        geometry: {
                            type: 'Polygon',
                            coordinates: [[
                                [minLng, minLat],
                                [maxLng, minLat],
                                [maxLng, minLat + latStep],
                                [minLng, minLat + latStep],
                                [minLng, minLat]
                            ]]
                        }
                    }]
                }
            },
            {
                zone_type: 'yellow',
                geometry: {
                    type: 'FeatureCollection',
                    features: [{
                        type: 'Feature',
                        properties: { zone: 'yellow', value: 0.17 },
                        geometry: {
                            type: 'Polygon',
                            coordinates: [[
                                [minLng, minLat + latStep],
                                [maxLng, minLat + latStep],
                                [maxLng, minLat + latStep * 2],
                                [minLng, minLat + latStep * 2],
                                [minLng, minLat + latStep]
                            ]]
                        }
                    }]
                }
            },
            {
                zone_type: 'green',
                geometry: {
                    type: 'FeatureCollection',
                    features: [{
                        type: 'Feature',
                        properties: { zone: 'green', value: 0.22 },
                        geometry: {
                            type: 'Polygon',
                            coordinates: [[
                                [minLng, minLat + latStep * 2],
                                [maxLng, minLat + latStep * 2],
                                [maxLng, maxLat],
                                [minLng, maxLat],
                                [minLng, minLat + latStep * 2]
                            ]]
                        }
                    }]
                }
            }
        ];

        return zones;
    }

    /**
     * Clear all layers
     */
    clearLayers() {
        if (this.parcelLayer) {
            this.map.removeLayer(this.parcelLayer);
        }
        if (this.zoneLayer) {
            this.map.removeLayer(this.zoneLayer);
        }
    }
}

// Global instance
let mapManager;

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', () => {
    mapManager = new MapManager('map');
    mapManager.init();
});
