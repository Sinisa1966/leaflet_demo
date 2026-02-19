// Konfiguracija za web3 – GeoServer + parcel_server (bez Supabase)

const APP_CONFIG = {
    // Parcela koja se prikazuje
    defaultParcel: '1427/2',
    defaultLayer: 'kovin_dkp_pg',
    defaultKatOpstina: 'DUBOVAC',

    // parcel_server URL (pokreće Sentinel Hub download skripte)
    parcelServer: {
        local:      'http://localhost:5010',
        production: 'http://89.167.39.148:8088/parcel'
    },

    // GeoServer URL
    geoserver: {
        local:      'http://localhost:8083/geoserver',
        production: 'http://89.167.39.148:8088/geoserver',
        workspace:  'moj_projekat'
    },

    // GeoServer WMS lejeri za parcelu 1427/2 (postavi prave nazive iz GeoServera)
    // Ako lejer ne postoji, WMS tile je prazan – bez greške
    wmsLayers: {
        ndvi: 'moj_projekat:ndvi_parcela_1427_2_DUBOVAC',
        ndmi: 'moj_projekat:ndmi_parcela_1427_2_DUBOVAC',
        ndre: 'moj_projekat:ndre_parcela_1427_2_DUBOVAC',
        ndreZones: 'moj_projekat:ndre_value_parcela_1427_2_DUBOVAC'
    },

    // Mapa
    map: {
        center: [44.8156, 21.2003],
        zoom: 16,
        minZoom: 10,
        maxZoom: 18
    },

    // Indeksi
    indices: [
        { value: 'NDRE', label: 'NDRE (Red Edge)',   color: '#FF6B6B' },
        { value: 'NDVI', label: 'NDVI (Vegetacija)', color: '#4ECDC4' },
        { value: 'NDMI', label: 'NDMI (Vlaga)',      color: '#45B7D1' }
    ],

    zoneColors: {
        red:    '#FF4444',
        yellow: '#FFD700',
        green:  '#44FF44'
    },

    chartColors: {
        NDRE: '#FF6B6B',
        NDVI: '#4ECDC4',
        NDMI: '#45B7D1'
    },

    // Vremenski opseg za podatke (dani) — 5 godina
    timeRangeDays: 5 * 365
};
