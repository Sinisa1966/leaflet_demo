// Main App Logic – web3 (GeoServer + parcel_server, bez Supabase)

class KopernikausApp {
    constructor() {
        this.currentParcelId     = APP_CONFIG.defaultParcel;
        this.currentIndexType    = 'NDRE';
        this.parcelData          = null;
        this.indexResults        = {};
        this.currentTimeSeriesData = [];
    }

    async init() {
        console.log('Initializing Kopernikus GIS App (web3)...');

        supabaseClient.init();  // uvek uspeva – samo postavlja URL-ove
        this.setupEventListeners();

        // ── 1. Parcela geometrija + mapa – brzo, prikaži odmah ────────────────
        this.showLoading(true, 'Učitavam parcelu...');
        try {
            this.parcelData = await supabaseClient.getParcelInfo(this.currentParcelId);
            if (this.parcelData) this.updateParcelInfo(this.parcelData);
            if (mapManager) {
                await mapManager.loadParcelGeometry(
                    this.parcelData || { parcel_id: this.currentParcelId }
                );
            }
        } catch (e) {
            console.warn('Parcela geometrija – greška:', e.message);
        }

        // ── Skloni loading – mapa i WMS lejer su odmah vidljivi ──────────────
        this.showLoading(false);

        // ── 2. Statistike + grafikon (ima prioritet – CSV iz keša, brzo) ──────
        // ── 3. Raster refresh tek NAKON statistika (ne blokira CSV pozive) ────
        this._loadStatsAndCharts().finally(() => {
            if (mapManager) mapManager.showRasterStatus('⬇ Osvežavam satelitske slike...');
            supabaseClient.refreshAllRasterLayers(this.currentParcelId)
                .then(() => {
                    if (mapManager) {
                        mapManager.refreshWmsLayers();
                        mapManager.showRasterStatus('✓ Satelitske slike osvežene');
                        setTimeout(() => mapManager.showRasterStatus(null), 3000);
                    }
                })
                .catch(e => {
                    console.warn('Raster refresh neuspešan:', e.message);
                    if (mapManager) mapManager.showRasterStatus(null);
                });
        });

        console.log('App inicijalizovana – mapa vidljiva, statistike se učitavaju...');
    }

    async _loadStatsAndCharts() {
        try {
            const latestResults = await supabaseClient.getLatestIndexResults(this.currentParcelId);
            latestResults.forEach(result => {
                this.indexResults[result.index_type] = result;
            });
            if (this.parcelData) this.updateParcelInfo(this.parcelData);

            await this.loadIndexData(this.currentIndexType);
            await this.loadAllMeasurements();
        } catch (error) {
            console.error('Greška pri učitavanju statistika:', error);
        }
    }

    // Zadržano radi kompatibilnosti – sada je unutar init()
    async loadData() {
        await this._loadStatsAndCharts();
    }

    async loadIndexData(indexType, showOverlay = false) {
        this.currentIndexType = indexType;

        try {
            this.updateCurrentStats(indexType);

            if (showOverlay) this.showLoading(true, `Učitavam vremensku seriju ${indexType}...`);
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

            if (indexType === 'NDRE') {
                const zones = await supabaseClient.getZoneClassifications(
                    this.currentParcelId,
                    indexType
                );
                if (zones && zones.length > 0) {
                    this.updateZoneDistribution(zones);
                    this.updateRecommendations(zones);
                }
            } else {
                document.getElementById('zoneDistribution').style.display = 'none';
                document.getElementById('recommendations').style.display  = 'none';
            }

        } catch (error) {
            console.error(`Greška pri učitavanju ${indexType}:`, error);
        }
    }

    async loadAllMeasurements() {
        try {
            const allData = await supabaseClient.getAllIndexResults(this.currentParcelId, 50);
            this.updateDataTable(allData);
        } catch (error) {
            console.error('Greška pri učitavanju merenja:', error);
        }
    }

    updateParcelInfo(parcelData) {
        document.getElementById('municipality').textContent = parcelData.municipality || 'N/A';
        document.getElementById('area').textContent = parcelData.area_ha
            ? `${parcelData.area_ha} ha`
            : 'N/A';

        const dates = Object.values(this.indexResults)
            .map(r => r.acquisition_date)
            .filter(d => d);
        if (dates.length > 0) {
            const latestDate = new Date(Math.max(...dates.map(d => new Date(d))));
            document.getElementById('lastUpdate').textContent = this.formatDate(latestDate);
        }
    }

    updateCurrentStats(indexType) {
        const result = this.indexResults[indexType];
        if (!result) {
            ['statMean', 'statMin', 'statMax', 'statMedian', 'statStd'].forEach(id => {
                document.getElementById(id).textContent = 'N/A';
            });
            return;
        }

        document.getElementById('statMean').textContent   = result.mean_value?.toFixed(3)  || 'N/A';
        document.getElementById('statMin').textContent    = result.min_value?.toFixed(3)   || 'N/A';
        document.getElementById('statMax').textContent    = result.max_value?.toFixed(3)   || 'N/A';
        document.getElementById('statMedian').textContent = result.percentile_50 != null
            ? Number(result.percentile_50).toFixed(3) : 'N/A';
        document.getElementById('statStd').textContent    = result.std_dev != null
            ? Number(result.std_dev).toFixed(3) : 'N/A';
    }

    updateZoneDistribution(zones) {
        const zoneDistEl = document.getElementById('zoneDistribution');
        zoneDistEl.style.display = 'block';

        const zoneMap = {};
        zones.forEach(z => { zoneMap[z.zone_type] = z.percentage || 0; });

        const redPct    = zoneMap['red']    || 0;
        const yellowPct = zoneMap['yellow'] || 0;
        const greenPct  = zoneMap['green']  || 0;

        const setBar = (id, pct) => {
            const el = document.getElementById(id);
            if (!el) return;
            el.style.width = pct + '%';
            el.querySelector('span').textContent = pct > 5 ? pct + '%' : '';
        };
        setBar('zoneRed', redPct);
        setBar('zoneYellow', yellowPct);
        setBar('zoneGreen', greenPct);
    }

    updateRecommendations(zones) {
        const recEl = document.getElementById('recommendations');
        recEl.style.display = 'block';

        const zoneMap = {};
        zones.forEach(z => {
            zoneMap[z.zone_type] = {
                percentage:     z.percentage || 0,
                recommendation: z.recommendation || ''
            };
        });

        const items = recEl.querySelectorAll('.recommendation-item');
        if (items[0] && zoneMap['red']) {
            items[0].querySelector('strong').textContent = `Crvena Zona (${zoneMap['red'].percentage}%):`;
            items[0].querySelector('p').textContent = zoneMap['red'].recommendation;
        }
        if (items[1] && zoneMap['yellow']) {
            items[1].querySelector('strong').textContent = `Žuta Zona (${zoneMap['yellow'].percentage}%):`;
            items[1].querySelector('p').textContent = zoneMap['yellow'].recommendation;
        }
        if (items[2] && zoneMap['green']) {
            items[2].querySelector('strong').textContent = `Zelena Zona (${zoneMap['green'].percentage}%):`;
            items[2].querySelector('p').textContent = zoneMap['green'].recommendation;
        }
    }

    downloadTimeSeriesCsv() {
        const data = this.currentTimeSeriesData;
        if (!data || data.length === 0) {
            this.showError('Nema podataka za preuzimanje.');
            return;
        }
        const headers = ['datum', 'prosek', 'median', 'min', 'max', 'validni_pikseli', 'oblaci'];
        const rows = data.map(d => [
            d.acquisition_date || '',
            d.mean_value       != null ? d.mean_value       : '',
            d.percentile_50    != null ? d.percentile_50    : '',
            d.min_value        != null ? d.min_value        : '',
            d.max_value        != null ? d.max_value        : '',
            d.valid_pixels     ?? '',
            d.cloud_pixels     ?? ''
        ]);
        const csv  = [headers.join(',')].concat(rows.map(r => r.join(','))).join('\n');
        const blob = new Blob(['\ufeff' + csv], { type: 'text/csv;charset=utf-8' });
        const a    = document.createElement('a');
        a.href     = URL.createObjectURL(blob);
        a.download = `vremenska_serija_${this.currentParcelId.replace(/\//g, '_')}_${this.currentIndexType}_5god.csv`;
        a.click();
        URL.revokeObjectURL(a.href);
    }

    updateDataTable(data) {
        const tbody = document.getElementById('dataTableBody');
        if (!data || data.length === 0) {
            tbody.innerHTML = '<tr><td colspan="8" class="loading">Nema podataka</td></tr>';
            return;
        }

        tbody.innerHTML = data.map(row => `
            <tr>
                <td>${this.formatDate(row.acquisition_date)}</td>
                <td><strong>${row.index_type}</strong></td>
                <td>${row.mean_value?.toFixed(3)    || 'N/A'}</td>
                <td>${row.percentile_50 != null ? Number(row.percentile_50).toFixed(3) : 'N/A'}</td>
                <td>${row.min_value?.toFixed(3)     || 'N/A'}</td>
                <td>${row.max_value?.toFixed(3)     || 'N/A'}</td>
                <td>${row.valid_pixels || 'N/A'}</td>
                <td>${row.cloud_pixels || '0'}</td>
            </tr>
        `).join('');

        document.getElementById('totalMeasurements').textContent = data.length;
    }

    setupEventListeners() {
        const downloadBtn = document.getElementById('downloadTimeSeriesBtn');
        if (downloadBtn) {
            downloadBtn.addEventListener('click', () => this.downloadTimeSeriesCsv());
        }

        document.querySelectorAll('.index-btn').forEach(btn => {
            btn.addEventListener('click', async (e) => {
                const button    = e.currentTarget;
                const indexType = button.dataset.index;

                document.querySelectorAll('.index-btn').forEach(b => b.classList.remove('active'));
                button.classList.add('active');

                if (mapManager) mapManager.showIndexLayer(indexType);

                this.showLoading(true, `Učitavam ${indexType}...`);
                await this.loadIndexData(indexType, true);
                this.showLoading(false);
            });
        });
    }

    showLoading(show, message) {
        const overlay = document.getElementById('loadingOverlay');
        if (show) {
            if (message) {
                const msgEl = document.getElementById('loadingMessage');
                if (msgEl) msgEl.innerHTML = message + '<br><small>Može potrajati 30–90 sekundi</small>';
            }
            overlay.classList.add('active');
        } else {
            overlay.classList.remove('active');
        }
    }

    showError(message) {
        alert(`Greška: ${message}`);
        console.error(message);
    }

    formatDate(date) {
        const d     = new Date(date);
        const day   = d.getDate();
        const month = d.getMonth() + 1;
        const year  = d.getFullYear();
        return `${day}. ${this.getMonthName(month)} ${year}.`;
    }

    getMonthName(month) {
        return ['januar','februar','mart','april','maj','jun',
                'jul','avgust','septembar','oktobar','novembar','decembar'][month - 1];
    }
}

document.addEventListener('DOMContentLoaded', async () => {
    const app = new KopernikausApp();
    await app.init();
});
