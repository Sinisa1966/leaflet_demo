// Supabase Configuration
// VAŽNO: Zameni sa svojim Supabase credentials

const SUPABASE_CONFIG = {
    // Tvoj Supabase Project URL
    url: 'https://krvfjthxzwnvsuvtlwam.supabase.co',
    
    // Tvoj Supabase Anon/Public Key (sigurno je za client-side)
    anonKey: 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImtydmZqdGh4endudnN1dnRsd2FtIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Njk1NDMzMjAsImV4cCI6MjA4NTExOTMyMH0.gEYzSDr7Sp6lzFfZAlMzrZLHyMFFZclZdhApZTyShto',
    
    // Opciono: Custom API endpoint ako koristiš Edge Functions
    apiEndpoint: null
};

// App Configuration
const APP_CONFIG = {
    // Default parcela za prikaz
    defaultParcel: '1427/2',
    
    // Map configuration
    map: {
        center: [44.8162, 21.2004],  // Centar parcele 1427/2 (lat, lng)
        zoom: 15,
        minZoom: 10,
        maxZoom: 18,
        // GeoServer WMS – lokalno (localhost)
        geoserverWms: 'http://localhost:8083/geoserver/moj_projekat/wms',
        // GeoServer WMS – produkcija (postavi pre deploy-a ako GeoServer nije na lokalnom!)
        geoserverWmsProduction: null   // npr. 'https://geoserver.tvoj-domain.com/geoserver/moj_projekat/wms'
    },
    
    // Index types
    indices: [
        { value: 'NDRE', label: 'NDRE (Red Edge)', color: '#FF6B6B' },
        { value: 'NDVI', label: 'NDVI (Vegetacija)', color: '#4ECDC4' },
        { value: 'NDMI', label: 'NDMI (Vlaga)', color: '#45B7D1' }
    ],
    
    // Zone colors
    zoneColors: {
        red: '#FF4444',
        yellow: '#FFD700',
        green: '#44FF44'
    },
    
    // Chart colors
    chartColors: {
        NDRE: '#FF6B6B',
        NDVI: '#4ECDC4',
        NDMI: '#45B7D1'
    },
    
    // Time range for data (days) — 5 godina
    timeRangeDays: 5 * 365
};

// Export config (za ES6 modules)
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { SUPABASE_CONFIG, APP_CONFIG };
}
