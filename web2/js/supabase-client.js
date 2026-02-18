// Supabase Client - Database Operations
// Handles all communication with Supabase

class SupabaseClient {
    constructor() {
        this.client = null;
        this.isInitialized = false;
    }

    /**
     * Initialize Supabase client
     */
    init() {
        if (!SUPABASE_CONFIG.url || !SUPABASE_CONFIG.anonKey) {
            console.error('Supabase credentials nisu konfigurisani!');
            console.error('Edituj js/config.js i dodaj svoje credentials.');
            return false;
        }

        if (SUPABASE_CONFIG.url === 'YOUR_SUPABASE_URL') {
            console.error('Molim te, zameni YOUR_SUPABASE_URL u config.js sa pravim URL-om!');
            return false;
        }

        try {
            this.client = supabase.createClient(
                SUPABASE_CONFIG.url,
                SUPABASE_CONFIG.anonKey
            );
            this.isInitialized = true;
            console.log('✅ Supabase client initialized');
            return true;
        } catch (error) {
            console.error('❌ Greška pri inicijalizaciji Supabase:', error);
            return false;
        }
    }

    /**
     * Get parcel info by ID
     */
    async getParcelInfo(parcelId) {
        if (!this.isInitialized) {
            throw new Error('Supabase nije inicijalizovan');
        }

        const { data, error } = await this.client
            .from('parcels')
            .select('*')
            .eq('parcel_id', parcelId)
            .single();

        if (error) {
            console.error('Greška pri učitavanju parcele:', error);
            return null;
        }

        return data;
    }

    /**
     * Get latest index results for parcel
     */
    async getLatestIndexResults(parcelId) {
        if (!this.isInitialized) {
            throw new Error('Supabase nije inicijalizovan');
        }

        const { data, error } = await this.client
            .from('latest_index_results')
            .select('*')
            .eq('parcel_id', parcelId);

        if (error) {
            console.error('Greška pri učitavanju rezultata:', error);
            return [];
        }

        return data || [];
    }

    /**
     * Get time series data for specific index
     */
    async getTimeSeriesData(parcelId, indexType, daysBack = 1825) {
        if (!this.isInitialized) {
            throw new Error('Supabase nije inicijalizovan');
        }

        const fromDate = new Date();
        fromDate.setDate(fromDate.getDate() - daysBack);

        const { data, error } = await this.client
            .from('index_results')
            .select('*')
            .eq('parcel_id', parcelId)
            .eq('index_type', indexType)
            .gte('acquisition_date', fromDate.toISOString().split('T')[0])
            .order('acquisition_date', { ascending: true });

        if (error) {
            console.error('Greška pri učitavanju vremenske serije:', error);
            return [];
        }

        return data || [];
    }

    /**
     * Get all index results for parcel (for table)
     */
    async getAllIndexResults(parcelId, limit = 50) {
        if (!this.isInitialized) {
            throw new Error('Supabase nije inicijalizovan');
        }

        const { data, error } = await this.client
            .from('index_results')
            .select('*')
            .eq('parcel_id', parcelId)
            .order('acquisition_date', { ascending: false })
            .limit(limit);

        if (error) {
            console.error('Greška pri učitavanju svih rezultata:', error);
            return [];
        }

        return data || [];
    }

    /**
     * Get zone classifications
     */
    async getZoneClassifications(parcelId, indexType) {
        if (!this.isInitialized) {
            throw new Error('Supabase nije inicijalizovan');
        }

        const { data, error } = await this.client
            .from('zone_classifications')
            .select('*')
            .eq('parcel_id', parcelId)
            .eq('index_type', indexType)
            .order('acquisition_date', { ascending: false })
            .limit(1);

        if (error) {
            console.error('Greška pri učitavanju zona:', error);
            return [];
        }

        return data || [];
    }

    /**
     * Get zone geometries (GeoJSON)
     */
    async getZoneGeometries(parcelId, indexType) {
        if (!this.isInitialized) {
            throw new Error('Supabase nije inicijalizovan');
        }

        const { data, error } = await this.client
            .from('zone_geometries')
            .select('*')
            .eq('parcel_id', parcelId)
            .eq('index_type', indexType)
            .order('acquisition_date', { ascending: false })
            .limit(3);  // red, yellow, green

        if (error) {
            console.error('Greška pri učitavanju zone geometrija:', error);
            return [];
        }

        return data || [];
    }

    /**
     * Get metadata
     */
    async getMetadata(key) {
        if (!this.isInitialized) {
            throw new Error('Supabase nije inicijalizovan');
        }

        const { data, error } = await this.client
            .from('metadata')
            .select('value')
            .eq('key', key)
            .single();

        if (error) {
            console.error('Greška pri učitavanju metadata:', error);
            return null;
        }

        return data?.value;
    }

    /**
     * Health check
     */
    async healthCheck() {
        if (!this.isInitialized) {
            return false;
        }

        try {
            const { error } = await this.client
                .from('metadata')
                .select('key')
                .limit(1);

            return !error;
        } catch (e) {
            return false;
        }
    }
}

// Global instance
const supabaseClient = new SupabaseClient();
