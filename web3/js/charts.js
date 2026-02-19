// Charts Management - Chart.js Integration

class ChartsManager {
    constructor() {
        this.timeSeriesChart = null;
    }

    /**
     * Create time series chart (x = datum, y = vrednost). X os uvek pokazuje poslednjih 5 godina.
     */
    createTimeSeriesChart(canvasId, data, indexType) {
        if (this.timeSeriesChart) {
            this.timeSeriesChart.destroy();
            this.timeSeriesChart = null;
        }

        const ctx = document.getElementById(canvasId);
        if (!ctx) {
            console.error('Canvas element not found:', canvasId);
            return;
        }

        // Opseg x ose: uvek poslednjih 5 godina
        const now = new Date();
        const fiveYearsAgo = new Date(now);
        fiveYearsAgo.setFullYear(fiveYearsAgo.getFullYear() - 5);

        // Podaci u obliku { x: datum, y: vrednost } za vremensku osu
        const meanData = data.map(d => ({
            x: new Date(d.acquisition_date).getTime(),
            y: d.mean_value != null ? Number(d.mean_value) : null
        }));
        const medianData = data
            .filter(d => d.percentile_50 != null)
            .map(d => ({
                x: new Date(d.acquisition_date).getTime(),
                y: Number(d.percentile_50)
            }));
        const minData = data.map(d => ({
            x: new Date(d.acquisition_date).getTime(),
            y: d.min_value != null ? Number(d.min_value) : null
        }));
        const maxData = data.map(d => ({
            x: new Date(d.acquisition_date).getTime(),
            y: d.max_value != null ? Number(d.max_value) : null
        }));

        const color = APP_CONFIG.chartColors[indexType] || '#3498DB';
        const pointRadius = data.length > 100 ? 2 : 6;
        const pointHoverRadius = data.length > 100 ? 4 : 8;

        // Y os: fiksni opseg po indeksu da se i jedna tačka lepo vidi
        const yRange = this.getYRangeForIndex(indexType);

        // Provera da li je time scale dostupan (date adapter može da ne učita sa file://)
        let useTimeScale = false;
        try {
            useTimeScale = !!(typeof Chart !== 'undefined' && Chart.registry && Chart.registry.getScale('time'));
        } catch (e) { useTimeScale = false; }

        // Za category fallback (bez time adaptera): labels + niz y vrednosti
        const labels = data.map(d => this.formatDate(d.acquisition_date));
        const meanValues = data.map(d => d.mean_value != null ? Number(d.mean_value) : null);
        const medianValues = data.map(d => d.percentile_50 != null ? Number(d.percentile_50) : null);
        const minValues = data.map(d => d.min_value != null ? Number(d.min_value) : null);
        const maxValues = data.map(d => d.max_value != null ? Number(d.max_value) : null);

        const hasMedian = medianData.length > 0;

        const timeScaleDatasets = [
            {
                label: `${indexType} - Prosek`,
                data: meanData,
                borderColor: color,
                backgroundColor: this.hexToRgba(color, 0.1),
                borderWidth: 3,
                fill: true,
                tension: 0.4,
                pointRadius,
                pointHoverRadius
            },
            ...(hasMedian ? [{
                label: `${indexType} - Median`,
                data: medianData,
                borderColor: color,
                backgroundColor: 'transparent',
                borderWidth: 1.5,
                borderDash: [5, 4],
                fill: false,
                tension: 0.4,
                pointRadius: 0,
                pointHoverRadius: 3
            }] : []),
            {
                label: `${indexType} - Minimum`,
                data: minData,
                borderColor: this.hexToRgba(color, 0.3),
                backgroundColor: 'transparent',
                borderWidth: 1,
                borderDash: [5, 5],
                fill: false,
                tension: 0.4,
                pointRadius: data.length > 100 ? 1 : 4
            },
            {
                label: `${indexType} - Maximum`,
                data: maxData,
                borderColor: this.hexToRgba(color, 0.3),
                backgroundColor: 'transparent',
                borderWidth: 1,
                borderDash: [5, 5],
                fill: false,
                tension: 0.4,
                pointRadius: data.length > 100 ? 1 : 4
            }
        ];

        const categoryDatasets = [
            { label: `${indexType} - Prosek`, data: meanValues, borderColor: color, backgroundColor: this.hexToRgba(color, 0.1), borderWidth: 3, fill: true, tension: 0.4, pointRadius, pointHoverRadius },
            ...(hasMedian ? [{ label: `${indexType} - Median`, data: medianValues, borderColor: color, backgroundColor: 'transparent', borderWidth: 1.5, borderDash: [5, 4], fill: false, tension: 0.4, pointRadius: 0, pointHoverRadius: 3 }] : []),
            { label: `${indexType} - Minimum`, data: minValues, borderColor: this.hexToRgba(color, 0.3), backgroundColor: 'transparent', borderWidth: 1, borderDash: [5, 5], fill: false, tension: 0.4, pointRadius: data.length > 100 ? 1 : 4 },
            { label: `${indexType} - Maximum`, data: maxValues, borderColor: this.hexToRgba(color, 0.3), backgroundColor: 'transparent', borderWidth: 1, borderDash: [5, 5], fill: false, tension: 0.4, pointRadius: data.length > 100 ? 1 : 4 }
        ];

        const chartData = useTimeScale
            ? { datasets: timeScaleDatasets }
            : { labels, datasets: categoryDatasets };

        this.timeSeriesChart = new Chart(ctx, {
            type: 'line',
            data: chartData,
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    title: {
                        display: false
                    },
                    legend: {
                        display: true,
                        position: 'top'
                    },
                    tooltip: {
                        mode: 'index',
                        intersect: false,
                        callbacks: {
                            title: function(context) {
                                if (useTimeScale && context[0] && context[0].raw && context[0].raw.x != null) {
                                    return new Date(context[0].raw.x).toLocaleDateString('sr-RS', { year: 'numeric', month: 'long', day: 'numeric' });
                                }
                                if (context[0] && data[context[0].dataIndex]) {
                                    return new Date(data[context[0].dataIndex].acquisition_date).toLocaleDateString('sr-RS', { year: 'numeric', month: 'long', day: 'numeric' });
                                }
                                return context[0] && context[0].label ? context[0].label : '';
                            },
                            label: function(context) {
                                let label = context.dataset.label || '';
                                if (label) label += ': ';
                                if (context.parsed.y !== null) label += context.parsed.y.toFixed(3);
                                return label;
                            }
                        }
                    }
                },
                scales: useTimeScale ? {
                    x: {
                        type: 'time',
                        display: true,
                        title: { display: true, text: 'Datum (poslednjih 5 godina)' },
                        min: fiveYearsAgo.getTime(),
                        max: now.getTime(),
                        time: {
                            unit: data.length > 24 ? 'month' : 'day',
                            displayFormats: { day: 'd.M.yy', week: 'd.M', month: 'MMM yyyy', year: 'yyyy' }
                        },
                        ticks: { maxRotation: 45, minRotation: 45, maxTicksLimit: 14 }
                    },
                    y: {
                        display: true,
                        title: {
                            display: true,
                            text: `${indexType} vrednost`
                        },
                        min: yRange.min,
                        max: yRange.max,
                        ticks: {
                            callback: function(value) {
                                return value.toFixed(2);
                            }
                        }
                    }
                } : {
                    x: {
                        type: 'category',
                        display: true,
                        title: { display: true, text: 'Datum (poslednjih 5 godina)' },
                        ticks: { maxRotation: 45, minRotation: 45, maxTicksLimit: 14 }
                    },
                    y: {
                        display: true,
                        title: { display: true, text: `${indexType} vrednost` },
                        min: yRange.min,
                        max: yRange.max,
                        ticks: { callback: v => v.toFixed(2) }
                    }
                },
                interaction: {
                    mode: 'nearest',
                    axis: 'x',
                    intersect: false
                }
            }
        });

        console.log(`✅ Chart created for ${indexType} with ${data.length} data points (x: 5 godina)`);
    }

    /**
     * Y os min/max po tipu indeksa (da se i jedna tačka lepo vidi)
     */
    getYRangeForIndex(indexType) {
        switch (indexType) {
            case 'NDVI':
                return { min: -0.2, max: 1.0 };
            case 'NDRE':
                return { min: 0, max: 0.5 };
            case 'NDMI':
                return { min: -0.5, max: 0.5 };
            default:
                return { min: -0.2, max: 1.0 };
        }
    }

    /**
     * Format date for display
     */
    formatDate(dateString) {
        const date = new Date(dateString);
        const day = date.getDate();
        const month = date.getMonth() + 1;
        const year = date.getFullYear();
        return `${day}.${month}.${year}`;
    }

    /**
     * Convert hex color to rgba
     */
    hexToRgba(hex, alpha) {
        const r = parseInt(hex.slice(1, 3), 16);
        const g = parseInt(hex.slice(3, 5), 16);
        const b = parseInt(hex.slice(5, 7), 16);
        return `rgba(${r}, ${g}, ${b}, ${alpha})`;
    }

    /**
     * Destroy all charts
     */
    destroy() {
        if (this.timeSeriesChart) {
            this.timeSeriesChart.destroy();
            this.timeSeriesChart = null;
        }
    }
}

// Global instance
const chartsManager = new ChartsManager();
