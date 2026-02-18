// Main App Logic

class KopernikausApp {
    constructor() {
        this.currentParcelId = APP_CONFIG.defaultParcel;
        this.currentIndexType = 'NDRE';
        this.parcelData = null;
        this.indexResults = {};
        this.zoneData = {};
        this.currentTimeSeriesData = [];
    }

    /**
     * Initialize application
     */
    async init() {
        console.log('🚀 Initializing Kopernikus GIS App...');

        // Show loading
        this.showLoading(true);

        // Initialize Supabase
        const supabaseReady = supabaseClient.init();
        if (!supabaseReady) {
            this.showError('Supabase nije konfigurisan. Pogledaj js/config.js');
            this.showLoading(false);
            return;
        }

        // Health check
        const isHealthy = await supabaseClient.healthCheck();
        if (!isHealthy) {
            this.showError('Ne mogu da se povežem sa Supabase. Proveri credentials.');
            this.showLoading(false);
            return;
        }

        // Load initial data
        await this.loadData();

        // Setup event listeners
        this.setupEventListeners();

        // Hide loading
        this.showLoading(false);

        console.log('✅ App initialized successfully');
    }

    /**
     * Load all data for current parcel
     */
    async loadData() {
        try {
            // Load parcel info
            this.parcelData = await supabaseClient.getParcelInfo(this.currentParcelId);
            if (this.parcelData) {
                this.updateParcelInfo(this.parcelData);
            }
            // Uvek učitaj geometriju (Supabase ili fallback iz data/parcela_*.geojson)
            if (mapManager) {
                await mapManager.loadParcelGeometry(this.parcelData || { parcel_id: this.currentParcelId });
            }

            // Load latest index results
            const latestResults = await supabaseClient.getLatestIndexResults(this.currentParcelId);
            latestResults.forEach(result => {
                this.indexResults[result.index_type] = result;
            });

            // Load current index data
            await this.loadIndexData(this.currentIndexType);

            // Load all measurements for table
            await this.loadAllMeasurements();

        } catch (error) {
            console.error('Greška pri učitavanju podataka:', error);
            this.showError('Greška pri učitavanju podataka iz baze.');
        }
    }

    /**
     * Load specific index data (time series, zones)
     */
    async loadIndexData(indexType) {
        this.currentIndexType = indexType;

        try {
            // Update current stats
            this.updateCurrentStats(indexType);

            // Load time series
            const timeSeriesData = await supabaseClient.getTimeSeriesData(
                this.currentParcelId,
                indexType,
                APP_CONFIG.timeRangeDays
            );

            this.currentTimeSeriesData = timeSeriesData || [];
            if (this.currentTimeSeriesData.length > 0) {
                chartsManager.createTimeSeriesChart('timeSeriesChart', this.currentTimeSeriesData, indexType);
            } else {
                console.warn(`Nema vremenske serije za ${indexType}`);
            }

            // Load zones (if NDRE)
            if (indexType === 'NDRE') {
                const zones = await supabaseClient.getZoneClassifications(
                    this.currentParcelId,
                    indexType
                );
                
                if (zones && zones.length > 0) {
                    this.updateZoneDistribution(zones);
                    this.updateRecommendations(zones);
                }

                // Load zone geometries
                let zoneGeometries = await supabaseClient.getZoneGeometries(
                    this.currentParcelId,
                    indexType
                );

                // If no zone geometries in DB, create dummy zones
                if (!zoneGeometries || zoneGeometries.length === 0) {
                    console.log('No zone geometries in DB, creating dummy zones...');
                    zoneGeometries = mapManager.createDummyZones(this.parcelData.geometry);
                }

                if (mapManager && zoneGeometries.length > 0) {
                    await mapManager.loadZoneGeometries(zoneGeometries);
                }
            } else {
                // Hide zone-specific UI for other indices
                document.getElementById('zoneDistribution').style.display = 'none';
                document.getElementById('recommendations').style.display = 'none';
                
                // Clear zone layers from map
                if (mapManager && mapManager.zoneLayer) {
                    mapManager.map.removeLayer(mapManager.zoneLayer);
                }
            }

        } catch (error) {
            console.error(`Greška pri učitavanju ${indexType} podataka:`, error);
        }
    }

    /**
     * Load all measurements for table
     */
    async loadAllMeasurements() {
        try {
            const allData = await supabaseClient.getAllIndexResults(this.currentParcelId, 50);
            this.updateDataTable(allData);
        } catch (error) {
            console.error('Greška pri učitavanju merenja:', error);
        }
    }

    /**
     * Update parcel info display
     */
    updateParcelInfo(parcelData) {
        document.getElementById('municipality').textContent = parcelData.municipality || 'N/A';
        document.getElementById('area').textContent = `${parcelData.area_ha || 'N/A'} ha`;
        
        // Get latest measurement date from all indices
        const dates = Object.values(this.indexResults)
            .map(r => r.acquisition_date)
            .filter(d => d);
        
        if (dates.length > 0) {
            const latestDate = new Date(Math.max(...dates.map(d => new Date(d))));
            document.getElementById('lastUpdate').textContent = this.formatDate(latestDate);
        }
    }

    /**
     * Update current stats display
     */
    updateCurrentStats(indexType) {
        const result = this.indexResults[indexType];
        
        if (!result) {
            console.warn(`No result data for ${indexType}`);
            return;
        }

        document.getElementById('statMean').textContent = result.mean_value?.toFixed(3) || 'N/A';
        document.getElementById('statMin').textContent = result.min_value?.toFixed(3) || 'N/A';
        document.getElementById('statMax').textContent = result.max_value?.toFixed(3) || 'N/A';
        
        // Calculate std dev or use from data
        const std = result.std_dev || 0;
        document.getElementById('statStd').textContent = std.toFixed(3);
    }

    /**
     * Update zone distribution bar
     */
    updateZoneDistribution(zones) {
        const zoneDistEl = document.getElementById('zoneDistribution');
        zoneDistEl.style.display = 'block';

        // Create zone map
        const zoneMap = {};
        zones.forEach(z => {
            zoneMap[z.zone_type] = z.percentage || 0;
        });

        const redPct = zoneMap['red'] || 15;
        const yellowPct = zoneMap['yellow'] || 60;
        const greenPct = zoneMap['green'] || 25;

        // Update HTML
        const barHTML = `
            <div class="zone-bar">
                <div class="zone-segment red" style="width: ${redPct}%">
                    <span>${redPct}%</span>
                </div>
                <div class="zone-segment yellow" style="width: ${yellowPct}%">
                    <span>${yellowPct}%</span>
                </div>
                <div class="zone-segment green" style="width: ${greenPct}%">
                    <span>${greenPct}%</span>
                </div>
            </div>
        `;

        const existingBar = zoneDistEl.querySelector('.zone-bar');
        if (existingBar) {
            existingBar.outerHTML = barHTML;
        }
    }

    /**
     * Update recommendations
     */
    updateRecommendations(zones) {
        const recEl = document.getElementById('recommendations');
        recEl.style.display = 'block';

        const zoneMap = {};
        zones.forEach(z => {
            zoneMap[z.zone_type] = {
                percentage: z.percentage || 0,
                recommendation: z.recommendation || ''
            };
        });

        // Update recommendation items
        const items = recEl.querySelectorAll('.recommendation-item');
        
        // Red zone
        if (items[0] && zoneMap['red']) {
            items[0].querySelector('strong').textContent = `Crvena Zona (${zoneMap['red'].percentage}%):`;
            items[0].querySelector('p').textContent = zoneMap['red'].recommendation || 'Dodaj više azota.';
        }

        // Yellow zone
        if (items[1] && zoneMap['yellow']) {
            items[1].querySelector('strong').textContent = `Žuta Zona (${zoneMap['yellow'].percentage}%):`;
            items[1].querySelector('p').textContent = zoneMap['yellow'].recommendation || 'Standardna obrada.';
        }

        // Green zone
        if (items[2] && zoneMap['green']) {
            items[2].querySelector('strong').textContent = `Zelena Zona (${zoneMap['green'].percentage}%):`;
            items[2].querySelector('p').textContent = zoneMap['green'].recommendation || 'Može manje azota.';
        }
    }

    /**
     * Download time series as CSV
     */
    downloadTimeSeriesCsv() {
        const data = this.currentTimeSeriesData;
        if (!data || data.length === 0) {
            this.showError('Nema podataka za preuzimanje.');
            return;
        }
        const headers = ['datum', 'prosek', 'min', 'max', 'validni_pikseli', 'oblaci'];
        const rows = data.map(d => [
            d.acquisition_date || '',
            d.mean_value != null ? d.mean_value : '',
            d.min_value != null ? d.min_value : '',
            d.max_value != null ? d.max_value : '',
            d.valid_pixels ?? '',
            d.cloud_pixels ?? ''
        ]);
        const csv = [headers.join(',')].concat(rows.map(r => r.join(','))).join('\n');
        const blob = new Blob(['\ufeff' + csv], { type: 'text/csv;charset=utf-8' });
        const a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = `vremenska_serija_${this.currentParcelId.replace(/\//g, '_')}_${this.currentIndexType}_5god.csv`;
        a.click();
        URL.revokeObjectURL(a.href);
    }

    /**
     * Update data table
     */
    updateDataTable(data) {
        const tbody = document.getElementById('dataTableBody');
        
        if (!data || data.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" class="loading">Nema podataka</td></tr>';
            return;
        }

        tbody.innerHTML = data.map(row => `
            <tr>
                <td>${this.formatDate(row.acquisition_date)}</td>
                <td><strong>${row.index_type}</strong></td>
                <td>${row.mean_value?.toFixed(3) || 'N/A'}</td>
                <td>${row.min_value?.toFixed(3) || 'N/A'}</td>
                <td>${row.max_value?.toFixed(3) || 'N/A'}</td>
                <td>${row.valid_pixels || 'N/A'}</td>
                <td>${row.cloud_pixels || '0'}</td>
            </tr>
        `).join('');

        // Update total measurements count
        document.getElementById('totalMeasurements').textContent = data.length;
    }

    /**
     * Setup event listeners
     */
    setupEventListeners() {
        // Download time series
        const downloadBtn = document.getElementById('downloadTimeSeriesBtn');
        if (downloadBtn) {
            downloadBtn.addEventListener('click', () => this.downloadTimeSeriesCsv());
        }
        // Index selector buttons
        document.querySelectorAll('.index-btn').forEach(btn => {
            btn.addEventListener('click', async (e) => {
                const button = e.currentTarget;
                const indexType = button.dataset.index;

                // Update active state
                document.querySelectorAll('.index-btn').forEach(b => b.classList.remove('active'));
                button.classList.add('active');

                // Load index data
                this.showLoading(true);
                await this.loadIndexData(indexType);
                this.showLoading(false);
            });
        });
    }

    /**
     * Show/hide loading overlay
     */
    showLoading(show) {
        const overlay = document.getElementById('loadingOverlay');
        if (show) {
            overlay.classList.add('active');
        } else {
            overlay.classList.remove('active');
        }
    }

    /**
     * Show error message
     */
    showError(message) {
        alert(`❌ Greška: ${message}`);
        console.error(message);
    }

    /**
     * Format date for display
     */
    formatDate(date) {
        const d = new Date(date);
        const day = d.getDate();
        const month = d.getMonth() + 1;
        const year = d.getFullYear();
        return `${day}. ${this.getMonthName(month)} ${year}.`;
    }

    /**
     * Get month name
     */
    getMonthName(month) {
        const months = [
            'januar', 'februar', 'mart', 'april', 'maj', 'jun',
            'jul', 'avgust', 'septembar', 'oktobar', 'novembar', 'decembar'
        ];
        return months[month - 1];
    }
}

// Initialize app when DOM is ready
document.addEventListener('DOMContentLoaded', async () => {
    const app = new KopernikausApp();
    await app.init();
});
