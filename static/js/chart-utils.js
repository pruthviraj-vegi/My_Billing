/**
 * ChartUtils: Reusable chart creation and update utility for all dashboards
 * Supports both create (new chart) and update (existing chart) operations
 */

(function (window) {
    'use strict';

    // Default color palettes
    const DEFAULT_COLORS = [
        'rgba(37, 99, 235, 0.8)',   // Blue
        'rgba(16, 185, 129, 0.8)',   // Green
        'rgba(245, 158, 11, 0.8)',  // Yellow
        'rgba(239, 68, 68, 0.8)',   // Red
        'rgba(139, 92, 246, 0.8)',  // Purple
        'rgba(6, 182, 212, 0.8)',   // Cyan
        'rgba(132, 204, 22, 0.8)',  // Lime
        'rgba(249, 115, 22, 0.8)',  // Orange
        'rgba(236, 72, 153, 0.8)',  // Pink
        'rgba(99, 102, 241, 0.8)'   // Indigo
    ];

    const DEFAULT_COLORS_HOVER = DEFAULT_COLORS.map(c => c.replace('0.8', '1'));

    // Reusable Color Palettes - Use Charts.getColors('paletteName')
    const COLOR_PALETTES = {
        blue: {
            colors: [
                'rgba(37, 99, 235, 0.8)',
                'rgba(16, 185, 129, 0.8)',
                'rgba(245, 158, 11, 0.8)',
                'rgba(239, 68, 68, 0.8)',
                'rgba(139, 92, 246, 0.8)'
            ],
            hover: [
                'rgba(37, 99, 235, 1)',
                'rgba(16, 185, 129, 1)',
                'rgba(245, 158, 11, 1)',
                'rgba(239, 68, 68, 1)',
                'rgba(139, 92, 246, 1)'
            ]
        },
        cyan: {
            colors: [
                'rgba(6, 182, 212, 0.8)',
                'rgba(132, 204, 22, 0.8)',
                'rgba(249, 115, 22, 0.8)',
                'rgba(236, 72, 153, 0.8)',
                'rgba(99, 102, 241, 0.8)'
            ],
            hover: [
                'rgba(6, 182, 212, 1)',
                'rgba(132, 204, 22, 1)',
                'rgba(249, 115, 22, 1)',
                'rgba(236, 72, 153, 1)',
                'rgba(99, 102, 241, 1)'
            ]
        },
        green: {
            colors: [
                'rgba(34, 197, 94, 0.8)',
                'rgba(168, 85, 247, 0.8)',
                'rgba(251, 146, 60, 0.8)',
                'rgba(14, 165, 233, 0.8)',
                'rgba(244, 63, 94, 0.8)',
                'rgba(34, 211, 238, 0.8)',
                'rgba(251, 191, 36, 0.8)',
                'rgba(139, 69, 19, 0.8)'
            ],
            hover: [
                'rgba(34, 197, 94, 1)',
                'rgba(168, 85, 247, 1)',
                'rgba(251, 146, 60, 1)',
                'rgba(14, 165, 233, 1)',
                'rgba(244, 63, 94, 1)',
                'rgba(34, 211, 238, 1)',
                'rgba(251, 191, 36, 1)',
                'rgba(139, 69, 19, 1)'
            ]
        },
        default: {
            colors: DEFAULT_COLORS,
            hover: DEFAULT_COLORS_HOVER
        }
    };

    // Chart registry to track all created charts
    const chartRegistry = {};

    /**
     * Format currency for Indian locale
     * Reuses global formatCurrency if available, otherwise creates one
     */
    const formatCurrency = window.formatCurrency || function (amount) {
        const num = parseFloat(amount) || 0;
        return new Intl.NumberFormat('en-IN', {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        }).format(num);
    };

    /**
     * Format currency with ₹ symbol
     * Reuses formatCurrency (which may already include symbol from global)
     */
    function formatCurrencyWithSymbol(amount) {
        // If global formatCurrency already includes symbol, use it directly
        if (window.formatCurrency && window.formatCurrency(100).includes('₹')) {
            return formatCurrency(amount);
        }
        return '₹' + formatCurrency(amount);
    }

    /**
     * Destroy a chart if it exists
     */
    function destroyChart(chartKey) {
        if (chartRegistry[chartKey] && chartRegistry[chartKey].chart) {
            chartRegistry[chartKey].chart.destroy();
            chartRegistry[chartKey].chart = null;
        }
    }

    /**
     * Generate legend HTML for doughnut charts
     */
    function generateLegend(labels, values, colors, colorsHover, formatValue = null) {
        if (!labels || !values || labels.length === 0 || values.length === 0) {
            return '<p class="text-muted">No data available</p>';
        }

        const total = values.reduce((sum, val) => sum + parseFloat(val || 0), 0);
        const formatFn = formatValue || formatCurrencyWithSymbol;

        return labels.map((label, idx) => {
            const value = parseFloat(values[idx] || 0);
            const percentage = total > 0 ? ((value / total) * 100).toFixed(1) : 0;
            const color = colors[idx % colors.length];
            const colorHover = colorsHover[idx % colorsHover.length];

            return (
                '<div class="legend-item modern-legend">' +
                '<div class="legend-indicator">' +
                '<span class="legend-color" style="background: linear-gradient(135deg, ' + color + ', ' + colorHover + ')"></span>' +
                '</div>' +
                '<div class="legend-content">' +
                '<div class="legend-label">' + (label || 'Unknown') + '</div>' +
                '<div class="legend-stats">' +
                '<span class="legend-percentage">' + percentage + '%</span>' +
                '</div>' +
                '<div class="legend-amount">' + formatFn(value) + '</div>' +
                '</div>' +
                '</div>'
            );
        }).join('');
    }

    /**
     * Create or update a doughnut chart
     * @param {Object} config - Chart configuration
     * @param {string} config.chartKey - Unique key to track the chart
     * @param {string|HTMLElement} config.canvasId - Canvas element ID or element
     * @param {string|HTMLElement} config.legendId - Legend element ID or element
     * @param {Array} config.labels - Chart labels
     * @param {Array} config.values - Chart values
     * @param {Object} config.options - Optional chart options
     * @param {Array} config.colors - Optional custom colors
     * @param {Array} config.colorsHover - Optional custom hover colors
     * @param {Function} config.formatValue - Optional value formatter function
     * @param {Function} config.tooltipCallback - Optional custom tooltip callback
     * @returns {Chart|null} - Chart instance or null
     */
    function createOrUpdateDoughnutChart(config) {
        const {
            chartKey,
            canvasId,
            legendId,
            labels = [],
            values = [],
            options = {},
            colors = DEFAULT_COLORS,
            colorsHover = DEFAULT_COLORS_HOVER,
            formatValue = formatCurrencyWithSymbol,
            tooltipCallback = null
        } = config;

        if (!chartKey) {
            console.error('ChartUtils: chartKey is required');
            return null;
        }

        // Get canvas element
        const canvasEl = typeof canvasId === 'string'
            ? document.getElementById(canvasId)
            : canvasId;

        if (!canvasEl) {
            console.error(`ChartUtils: Canvas element not found: ${canvasId}`);
            return null;
        }

        // Get legend element
        const legendEl = typeof legendId === 'string'
            ? document.getElementById(legendId)
            : legendId;

        // Validate data
        if (!labels || labels.length === 0 || !values || values.length === 0) {
            if (legendEl) {
                legendEl.innerHTML = '<p class="text-muted">No data available</p>';
            }
            destroyChart(chartKey);
            return null;
        }

        // Destroy existing chart if updating
        const existingChart = chartRegistry[chartKey];
        if (existingChart && existingChart.chart) {
            existingChart.chart.destroy();
        }

        // Prepare chart data
        const chartData = {
            labels: labels,
            datasets: [{
                data: values.map(v => parseFloat(v || 0)),
                backgroundColor: colors.slice(0, labels.length),
                borderColor: 'rgba(255, 255, 255, 0.8)',
                borderWidth: 3,
                hoverBorderWidth: 4,
                hoverBackgroundColor: colorsHover.slice(0, labels.length),
                hoverOffset: 8
            }]
        };

        // Default tooltip callback
        const defaultTooltipCallback = (ctx) => {
            const total = values.reduce((sum, val) => sum + parseFloat(val || 0), 0);
            const value = parseFloat(ctx.raw || 0);
            const percentage = total > 0 ? ((value / total) * 100).toFixed(1) : 0;
            return [
                'Amount: ' + formatValue(value),
                'Percentage: ' + percentage + '%'
            ];
        };

        // Merge default options with custom options
        const chartOptions = {
            responsive: true,
            maintainAspectRatio: false,
            cutout: '60%',
            animation: {
                animateRotate: true,
                animateScale: true,
                duration: 1000,
                easing: 'easeOutQuart'
            },
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: 'rgba(30, 41, 59, 0.95)',
                    titleColor: '#ffffff',
                    bodyColor: '#ffffff',
                    borderColor: 'rgba(37, 99, 235, 0.3)',
                    borderWidth: 1,
                    cornerRadius: 8,
                    displayColors: true,
                    padding: 12,
                    callbacks: {
                        title: (ctx) => ctx[0].label,
                        label: tooltipCallback || defaultTooltipCallback
                    }
                }
            },
            elements: { arc: { borderWidth: 0 } },
            ...options
        };

        // Create chart
        const ctx = canvasEl.getContext('2d');
        const chart = new Chart(ctx, {
            type: 'doughnut',
            data: chartData,
            options: chartOptions
        });

        // Update legend
        if (legendEl) {
            legendEl.innerHTML = generateLegend(labels, values, colors, colorsHover, formatValue);
        }

        // Register chart
        chartRegistry[chartKey] = {
            chart: chart,
            config: config,
            type: 'doughnut'
        };

        return chart;
    }

    /**
     * Update existing chart with new data
     * @param {string} chartKey - Chart key to update
     * @param {Object} data - New data {labels, values}
     * @returns {Chart|null} - Updated chart instance or null
     */
    function updateChart(chartKey, data) {
        const chartInfo = chartRegistry[chartKey];
        if (!chartInfo) {
            console.warn(`ChartUtils: Chart not found for key: ${chartKey}`);
            return null;
        }

        const config = {
            ...chartInfo.config,
            labels: data.labels || chartInfo.config.labels,
            values: data.values || chartInfo.config.values
        };

        return createOrUpdateDoughnutChart(config);
    }

    /**
     * Get chart instance by key
     */
    function getChart(chartKey) {
        const chartInfo = chartRegistry[chartKey];
        return chartInfo ? chartInfo.chart : null;
    }

    /**
     * Destroy all charts
     */
    function destroyAllCharts() {
        Object.keys(chartRegistry).forEach(key => destroyChart(key));
        Object.keys(chartRegistry).forEach(key => delete chartRegistry[key]);
    }

    /**
     * Get reusable color palette by name
     * @param {string} paletteName - 'blue', 'cyan', 'green', or 'default'
     * @returns {Object} { colors, colorsHover }
     */
    function getColors(paletteName) {
        const palette = COLOR_PALETTES[paletteName] || COLOR_PALETTES.default;
        return {
            colors: palette.colors,
            colorsHover: palette.hover
        };
    }

    /**
     * Normalize data to standardized format
     */
    function normalizeData(data) {
        if (Array.isArray(data) && data.length && typeof data[0] === 'object') {
            return data.map(d => ({
                label: d.label ?? d.name ?? '',
                value: Number(d.value ?? d.count ?? 0),
                amount: d.amount
            }));
        }
        return [];
    }

    /**
     * Simple pie chart wrapper - alias for createPieChart
     */
    function pie(config) {
        const { key, canvasId, legendId, data, colors, colorsHover, options } = config;
        const standardized = normalizeData(data);
        return createPieChart({
            chartKey: key,
            canvasId,
            legendId,
            data: standardized,
            colors,
            colorsHover,
            options
        });
    }

    /**
     * Update chart by key
     */
    function updateChartSimple(key, payload) {
        const { data } = payload || {};
        const chartInfo = chartRegistry[key];
        if (!chartInfo) {
            console.warn(`Chart not found for key: ${key}`);
            return null;
        }
        const standardized = normalizeData(data || []);
        return createPieChart({
            chartKey: key,
            canvasId: chartInfo.config.canvasId,
            legendId: chartInfo.config.legendId,
            data: standardized,
            colors: chartInfo.config.colors,
            colorsHover: chartInfo.config.colorsHover
        });
    }

    // Chart binding registry - stores config for each bound chart
    const chartBindings = {};

    /**
     * Auto-detect canvas and legend from container element
     */
    function detectChartElements(containerId) {
        const container = document.getElementById(containerId);
        if (!container) {
            console.error(`ChartUtils: Container not found: ${containerId}`);
            return null;
        }

        // Find canvas (first canvas element inside container)
        const canvas = container.querySelector('canvas');
        if (!canvas) {
            console.error(`ChartUtils: Canvas not found in container: ${containerId}`);
            return null;
        }

        // Find legend (element with id ending in "Legend" or class "chart-legend")
        let legend = container.querySelector('[id$="Legend"]') ||
            container.querySelector('.chart-legend');

        return {
            canvasId: canvas.id || null,
            canvasEl: canvas,
            legendId: legend ? (legend.id || null) : null,
            legendEl: legend
        };
    }

    /**
     * Bind chart to container - auto-detects canvas and legend, stores config
     * @param {string} containerId - Container element ID
     * @param {Object} config - Chart configuration (key, colors, colorsHover, type, etc.)
     */
    function bindChart(containerId, config = {}) {
        const elements = detectChartElements(containerId);
        if (!elements) return null;

        const {
            key = containerId + '_chart',
            colors = DEFAULT_COLORS,
            colorsHover = DEFAULT_COLORS_HOVER,
            type = 'pie',  // 'pie', 'line', 'bar'
            options = {}
        } = config;

        // Store binding config
        chartBindings[containerId] = {
            key: key,
            canvasId: elements.canvasId,
            legendId: elements.legendId,
            colors: colors,
            colorsHover: colorsHover,
            type: type,
            options: options
        };

        // Helper: Update period info HTML
        function updatePeriodInfo(currentLabel, previousLabel) {
            const periodInfoEl = document.getElementById('periodInfo');
            if (periodInfoEl) {
                periodInfoEl.innerHTML = (
                    '<div class="period-comparison">' +
                    '<div class="period-item current-period">' +
                    '<div class="period-label">Current Period</div>' +
                    '<div class="period-range">' + (currentLabel || '') + '</div>' +
                    '</div>' +
                    '<div class="period-item previous-period">' +
                    '<div class="period-label">Previous Period</div>' +
                    '<div class="period-range">' + (previousLabel || '') + '</div>' +
                    '</div>' +
                    '</div>'
                );
            }
        }

        // Helper: Update chart summary HTML
        function updateChartSummary(currentTotal, previousTotal, formatType = 'amount') {
            const summaryEl = document.getElementById('chartSummary');
            if (!summaryEl) return;

            const change = currentTotal - previousTotal;
            const changePercent = previousTotal > 0 ? ((change / previousTotal) * 100) : 0;
            const changeClass = change >= 0 ? 'positive' : 'negative';
            const changeIcon = change >= 0 ? 'fas fa-arrow-up' : 'fas fa-arrow-down';
            const formattedCurrent = formatType === 'amount' ? formatCurrencyWithSymbol(currentTotal) : currentTotal;
            const formattedPrevious = formatType === 'amount' ? formatCurrencyWithSymbol(previousTotal) : previousTotal;
            const formattedChange = formatType === 'amount' ? formatCurrencyWithSymbol(Math.abs(change)) : Math.abs(change);

            summaryEl.innerHTML = (
                '<div class="summary-grid">' +
                '<div class="summary-item">' +
                '<div class="summary-label">Current Total</div>' +
                '<div class="summary-value">' + formattedCurrent + '</div>' +
                '</div>' +
                '<div class="summary-item">' +
                '<div class="summary-label">Previous Total</div>' +
                '<div class="summary-value">' + formattedPrevious + '</div>' +
                '</div>' +
                '<div class="summary-item ' + changeClass + '">' +
                '<div class="summary-label">Change</div>' +
                '<div class="summary-value">' +
                '<i class="' + changeIcon + '"></i>' +
                ' ' + formattedChange + ' (' + changePercent.toFixed(1) + '%)' +
                '</div>' +
                '</div>' +
                '</div>'
            );
        }

        // Helper: Update comparison chart with full data object (handles everything)
        function updateComparisonChart(comparisonData, metric = 'amount') {
            if (!comparisonData) return null;

            const currentData = comparisonData.current_period.data.map(i => i[metric]);
            const previousData = comparisonData.previous_period.data.map(i => i[metric]);
            const labels = comparisonData.current_period.data.map(i =>
                formatDateForChart(i.date, comparisonData.period_type)
            );

            // Calculate percentage change
            const percentageData = currentData.map((cur, idx) => {
                const prev = previousData[idx] || 0;
                if (prev === 0) return cur > 0 ? 100 : 0;
                return ((cur - prev) / prev) * 100;
            });

            // Update chart
            const chart = createLineBarChart({
                chartKey: chartBindings[containerId].key,
                canvasId: chartBindings[containerId].canvasId,
                type: chartBindings[containerId].type,
                labels: labels,
                datasets: [
                    {
                        label: comparisonData.current_period.label,
                        data: currentData
                    },
                    {
                        label: comparisonData.previous_period.label,
                        data: previousData,
                        borderDash: [5, 5]
                    },
                    {
                        label: 'Change %',
                        data: percentageData,
                        borderWidth: 2,
                        pointRadius: 4,
                        borderDash: [2, 2],
                        yAxisID: 'y1'
                    }
                ],
                options: {
                    formatYAxis: metric === 'amount' ? 'amount' : 'number',
                    ...chartBindings[containerId].options
                }
            });

            // Update period info and summary
            updatePeriodInfo(
                comparisonData.current_period.label,
                comparisonData.previous_period.label
            );

            const currentTotal = currentData.reduce((s, i) => s + i, 0);
            const previousTotal = previousData.reduce((s, i) => s + i, 0);
            updateChartSummary(currentTotal, previousTotal, metric);

            return chart;
        }

        // Create proxy object for easy updates
        const proxy = {
            update: function (data) {
                const binding = chartBindings[containerId];
                if (!binding) {
                    console.error(`Chart not bound: ${containerId}`);
                    return null;
                }

                // If data has comparison_data structure, use smart comparison update
                if (data.comparison_data && binding.type === 'line') {
                    const metric = data.metric || 'amount';
                    return updateComparisonChart(data.comparison_data, metric);
                }

                if (binding.type === 'pie') {
                    return createPieChart({
                        chartKey: binding.key,
                        canvasId: binding.canvasId,
                        legendId: binding.legendId,
                        data: data.data || data,
                        colors: binding.colors,
                        colorsHover: binding.colorsHover,
                        options: binding.options
                    });
                } else {
                    return createLineBarChart({
                        chartKey: binding.key,
                        canvasId: binding.canvasId,
                        type: binding.type,
                        labels: data.labels || [],
                        datasets: data.datasets || [],
                        options: { ...binding.options, ...data.options }
                    });
                }
            },
            updatePeriodInfo: updatePeriodInfo,
            updateSummary: updateChartSummary,
            getConfig: function () {
                return chartBindings[containerId];
            }
        };

        // Bind to window
        try {
            Object.defineProperty(window, containerId, {
                configurable: true,
                get: function () { return proxy; }
            });
        } catch (e) {
            window[containerId] = proxy;
        }

        return proxy;
    }

    /**
     * Get proxy object for legend ID binding (enables legendId.pichart())
     */
    function getProxyForId(legendId) {
        return {
            pichart: function ({ key, canvasId, data, colors, colorsHover, options }) {
                return pie({ key, canvasId, legendId, data, colors, colorsHover, options });
            },
            update: function ({ key, data }) {
                return updateChartSimple(key, { data });
            }
        };
    }

    /**
     * Bind legend IDs to window for easy access (legendId.pichart())
     * @param {Array<string>} ids - Array of legend element IDs
     */
    function bindIds(ids) {
        (ids || []).forEach(id => {
            try {
                Object.defineProperty(window, id, {
                    configurable: true,
                    get: function () { return getProxyForId(id); }
                });
            } catch (e) {
                // Fallback: attach directly if property definition fails
                window[id] = getProxyForId(id);
            }
        });
    }

    /**
     * Format number/currency compact (K, L, Cr)
     * Reuses existing formatCurrencyCompact or formatNumberCompact if available
     */
    const formatCompact = window.formatCurrencyCompact || window.formatNumberCompact || function (value) {
        if (value >= 10000000) return (value / 10000000).toFixed(1) + 'Cr';
        if (value >= 100000) return (value / 100000).toFixed(1) + 'L';
        if (value >= 1000) return (value / 1000).toFixed(1) + 'K';
        return value.toFixed(0);
    };

    /**
     * Format date for chart labels
     * Reuses existing formatDateForChart if available
     */
    const formatDateForChart = window.formatDateForChart || function (dateString, periodType) {
        const date = new Date(dateString);
        switch (periodType) {
            case 'daily':
            case 'monthly':
                return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
            case 'quarterly':
                return 'Week ' + Math.ceil(date.getDate() / 7);
            case 'yearly':
                return date.toLocaleDateString('en-US', { month: 'short' });
            default:
                return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
        }
    };

    /**
     * Generic Line/Bar Chart Function - Standardized data format
     * 
     * Data Format:
     * {
     *   chartKey: 'unique_chart_key',        // Required
     *   canvasId: 'canvasElementId',          // Required
     *   type: 'line' | 'bar',                // Required: chart type
     *   labels: ['Jan', 'Feb', ...],         // Required: X-axis labels
     *   datasets: [                           // Required: array of datasets
     *     {
     *       label: 'Current Period',
     *       data: [100, 200, 300],
     *       color: 'rgba(37, 99, 235, 0.8)',
     *       yAxisID: 'y',                     // Optional: 'y' or 'y1'
     *       borderDash: [5, 5]                // Optional: for dashed lines
     *     }
     *   ],
     *   options: {                            // Optional: chart options
     *     showLegend: false,
     *     formatYAxis: 'amount' | 'number' | 'percent',
     *     gridColor: 'rgba(148, 163, 184, 0.1)'
     *   }
     * }
     */
    function createLineBarChart(config) {
        const {
            chartKey,
            canvasId,
            type = 'line',
            labels = [],
            datasets = [],
            options = {}
        } = config;

        if (!chartKey || !canvasId || !labels.length || !datasets.length) {
            console.error('ChartUtils.createLineBarChart: chartKey, canvasId, labels, and datasets are required');
            return null;
        }

        const canvasEl = typeof canvasId === 'string'
            ? document.getElementById(canvasId)
            : canvasId;

        if (!canvasEl) {
            console.error(`ChartUtils.createLineBarChart: Canvas element not found: ${canvasId}`);
            return null;
        }

        // Destroy existing chart if updating
        destroyChart(chartKey);

        // Default colors for datasets
        const defaultColors = [
            { border: 'rgba(37, 99, 235, 0.8)', fill: 'rgba(37, 99, 235, 0.8)', hover: 'rgba(37, 99, 235, 1)' },
            { border: 'rgba(16, 185, 129, 0.8)', fill: 'rgba(16, 185, 129, 0.8)', hover: 'rgba(16, 185, 129, 1)' },
            { border: 'rgba(245, 158, 11, 0.8)', fill: 'rgba(245, 158, 11, 0.8)', hover: 'rgba(245, 158, 11, 1)' }
        ];

        // Prepare datasets
        const chartDatasets = datasets.map((dataset, idx) => {
            const defaultColor = defaultColors[idx % defaultColors.length];
            return {
                label: dataset.label || `Dataset ${idx + 1}`,
                data: dataset.data || [],
                borderColor: dataset.color || dataset.borderColor || defaultColor.border,
                backgroundColor: dataset.backgroundColor || dataset.fillColor || defaultColor.fill,
                borderWidth: dataset.borderWidth || (type === 'line' ? 3 : 1),
                fill: dataset.fill !== undefined ? dataset.fill : false,
                tension: dataset.tension !== undefined ? dataset.tension : (type === 'line' ? 0.4 : 0),
                pointRadius: dataset.pointRadius !== undefined ? dataset.pointRadius : (type === 'line' ? 6 : 0),
                pointHoverRadius: dataset.pointHoverRadius || (type === 'line' ? 8 : 0),
                pointBackgroundColor: dataset.pointColor || dataset.pointBackgroundColor || defaultColor.hover,
                pointBorderColor: dataset.pointBorderColor || defaultColor.hover,
                pointHoverBackgroundColor: dataset.pointHoverColor || defaultColor.hover,
                pointHoverBorderColor: defaultColor.hover,
                pointHoverBorderWidth: dataset.pointHoverBorderWidth || 2,
                borderDash: dataset.borderDash || [],
                yAxisID: dataset.yAxisID || 'y'
            };
        });

        const chartData = {
            labels: labels,
            datasets: chartDatasets
        };

        // Determine Y-axis format
        const formatYAxis = options.formatYAxis || 'number';
        const gridColor = options.gridColor || 'rgba(148, 163, 184, 0.1)';
        const showLegend = options.showLegend !== undefined ? options.showLegend : false;

        // Build scales config
        const scales = {
            x: {
                display: true,
                grid: { color: gridColor, drawBorder: false }
            },
            y: {
                type: 'linear',
                display: true,
                position: 'left',
                grid: { color: gridColor, drawBorder: false },
                ticks: {
                    callback: function (value) {
                        if (formatYAxis === 'amount') {
                            return formatCompact(value);
                        } else if (formatYAxis === 'percent') {
                            return value.toFixed(1) + '%';
                        }
                        return formatCompact(value);
                    }
                }
            }
        };

        // Add secondary Y-axis if any dataset uses y1
        const hasSecondaryAxis = datasets.some(d => d.yAxisID === 'y1');
        if (hasSecondaryAxis) {
            scales.y1 = {
                type: 'linear',
                display: true,
                position: 'right',
                grid: { drawOnChartArea: false },
                ticks: {
                    callback: function (value) {
                        return value.toFixed(1) + '%';
                    }
                }
            };
        }

        // Merge default options with custom options
        const chartOptions = {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { intersect: false, mode: 'index' },
            animation: { duration: 1000, easing: 'easeOutQuart' },
            plugins: {
                legend: { display: showLegend },
                tooltip: {
                    backgroundColor: 'rgba(30, 41, 59, 0.95)',
                    titleColor: '#ffffff',
                    bodyColor: '#ffffff',
                    borderColor: 'rgba(37, 99, 235, 0.3)',
                    borderWidth: 1,
                    cornerRadius: 8,
                    padding: 12,
                    displayColors: true,
                    callbacks: {
                        title: (ctx) => ctx[0].label,
                        label: (ctx) => {
                            const label = ctx.dataset.label;
                            const value = ctx.parsed.y;
                            if (formatYAxis === 'amount') {
                                return label + ': ' + formatCurrencyWithSymbol(value);
                            } else if (formatYAxis === 'percent') {
                                return label + ': ' + value.toFixed(1) + '%';
                            }
                            return label + ': ' + value;
                        }
                    }
                }
            },
            scales: scales,
            ...options.chartOptions
        };

        // Create chart
        const ctx = canvasEl.getContext('2d');
        const chart = new Chart(ctx, {
            type: type,
            data: chartData,
            options: chartOptions
        });

        // Register chart
        chartRegistry[chartKey] = {
            chart: chart,
            config: config,
            type: type
        };

        return chart;
    }

    /**
     * Generic Pie Chart Function - Standardized data format
     * 
     * Data Format:
     * {
     *   chartKey: 'unique_chart_key',        // Required: unique identifier
     *   canvasId: 'canvasElementId',          // Required: canvas element ID
     *   legendId: 'legendElementId',          // Optional: legend container ID
     *   data: [                               // Required: array of data items
     *     { label: 'Label1', value: 100, amount: 5000 },
     *     { label: 'Label2', value: 200, amount: 10000 }
     *   ],
     *   colors: [...],                        // Optional: custom colors (uses DEFAULT_COLORS if not provided)
     *   colorsHover: [...],                   // Optional: custom hover colors
     *   showCount: true,                      // Optional: show count in tooltip/legend (default: true)
     *   showAmount: true,                     // Optional: show amount in tooltip/legend (default: true)
     *   formatValue: function(amount) {...}   // Optional: custom value formatter
     * }
     * 
     * @param {Object} config - Chart configuration with standardized data format
     * @returns {Chart|null} - Chart instance or null
     */
    function createPieChart(config) {
        const {
            chartKey,
            canvasId,
            legendId,
            data = [],
            colors = DEFAULT_COLORS,
            colorsHover = DEFAULT_COLORS_HOVER,
            showCount = true,
            showAmount = true,
            formatValue = formatCurrencyWithSymbol,
            options = {}
        } = config;

        if (!chartKey || !canvasId || !data || data.length === 0) {
            console.error('ChartUtils.createPieChart: chartKey, canvasId, and data are required');
            return null;
        }

        // Extract labels and values from standardized data format
        const labels = data.map(item => item.label || item.name || 'Unknown');
        const values = data.map(item => parseFloat(item.value || item.count || 0));

        // Build tooltip callback
        const tooltipCallback = (ctx) => {
            const item = data[ctx.dataIndex];
            const total = values.reduce((sum, val) => sum + val, 0);
            const value = parseFloat(ctx.raw || 0);
            const percentage = total > 0 ? ((value / total) * 100).toFixed(1) : 0;

            const tooltipLines = [];
            if (showCount) {
                tooltipLines.push('Count: ' + (item.count || item.value || value));
            }
            if (showAmount && item.amount !== undefined) {
                tooltipLines.push('Amount: ' + formatValue(item.amount));
            }
            tooltipLines.push('Percentage: ' + percentage + '%');

            return tooltipLines;
        };

        // Generate legend with count and amount if available
        const generateCustomLegend = (labels, values, colors, colorsHover) => {
            if (!labels || !values || labels.length === 0 || values.length === 0) {
                return '<p class="text-muted">No data available</p>';
            }

            const total = values.reduce((sum, val) => sum + parseFloat(val || 0), 0);

            return labels.map((label, idx) => {
                const item = data[idx];
                const value = parseFloat(values[idx] || 0);
                const percentage = total > 0 ? ((value / total) * 100).toFixed(1) : 0;
                const color = colors[idx % colors.length];
                const colorHover = colorsHover[idx % colorsHover.length];

                let legendContent = '<div class="legend-label">' + (label || 'Unknown') + '</div>';
                legendContent += '<div class="legend-stats">';

                if (showCount) {
                    legendContent += '<span class="legend-count">' + (item.count || item.value || value) + '</span>';
                }
                legendContent += '<span class="legend-percentage">' + percentage + '%</span>';
                legendContent += '</div>';

                if (showAmount && item.amount !== undefined) {
                    legendContent += '<div class="legend-amount">' + formatValue(item.amount) + '</div>';
                }

                return (
                    '<div class="legend-item modern-legend">' +
                    '<div class="legend-indicator">' +
                    '<span class="legend-color" style="background: linear-gradient(135deg, ' + color + ', ' + colorHover + ')"></span>' +
                    '</div>' +
                    '<div class="legend-content">' + legendContent + '</div>' +
                    '</div>'
                );
            }).join('');
        };

        // Use the existing createOrUpdateDoughnutChart with custom legend
        const canvasEl = typeof canvasId === 'string'
            ? document.getElementById(canvasId)
            : canvasId;

        if (!canvasEl) {
            console.error(`ChartUtils.createPieChart: Canvas element not found: ${canvasId}`);
            return null;
        }

        const legendEl = typeof legendId === 'string'
            ? document.getElementById(legendId)
            : legendId;

        // Destroy existing chart if updating
        destroyChart(chartKey);

        // Prepare chart data
        const chartData = {
            labels: labels,
            datasets: [{
                data: values,
                backgroundColor: colors.slice(0, labels.length),
                borderColor: 'rgba(255, 255, 255, 0.8)',
                borderWidth: 3,
                hoverBorderWidth: 4,
                hoverBackgroundColor: colorsHover.slice(0, labels.length),
                hoverOffset: 8
            }]
        };

        // Merge default options
        const chartOptions = {
            responsive: true,
            maintainAspectRatio: false,
            cutout: '60%',
            animation: {
                animateRotate: true,
                animateScale: true,
                duration: 1000,
                easing: 'easeOutQuart'
            },
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: 'rgba(30, 41, 59, 0.95)',
                    titleColor: '#ffffff',
                    bodyColor: '#ffffff',
                    borderColor: 'rgba(37, 99, 235, 0.3)',
                    borderWidth: 1,
                    cornerRadius: 8,
                    displayColors: true,
                    padding: 12,
                    callbacks: {
                        title: (ctx) => ctx[0].label,
                        label: tooltipCallback
                    }
                }
            },
            elements: { arc: { borderWidth: 0 } },
            ...options
        };

        // Create chart
        const ctx = canvasEl.getContext('2d');
        const chart = new Chart(ctx, {
            type: 'doughnut',
            data: chartData,
            options: chartOptions
        });

        // Update legend with custom format
        if (legendEl) {
            legendEl.innerHTML = generateCustomLegend(labels, values, colors, colorsHover);
        }

        // Register chart
        chartRegistry[chartKey] = {
            chart: chart,
            config: config,
            type: 'doughnut'
        };

        return chart;
    }

    /**
     * Simple line/bar chart wrapper with defaults
     * Minimal config: { key, canvasId, labels, datasets }
     * Everything else uses smart defaults
     */
    function lineBar(config) {
        const {
            key,
            canvasId,
            type = 'line',
            labels = [],
            datasets = [],
            options = {}
        } = config;

        // If datasets is simple array format, convert to standard format
        const normalizedDatasets = datasets.map((dataset, idx) => {
            // If it's just an array of numbers, convert to dataset format
            if (Array.isArray(dataset) && typeof dataset[0] === 'number') {
                const defaultColors = [
                    { color: 'rgba(37, 99, 235, 0.8)', pointColor: 'rgba(37, 99, 235, 1)' },
                    { color: 'rgba(16, 185, 129, 0.8)', pointColor: 'rgba(16, 185, 129, 1)' },
                    { color: 'rgba(245, 158, 11, 0.8)', pointColor: 'rgba(245, 158, 11, 1)' }
                ];
                const color = defaultColors[idx % defaultColors.length];
                return {
                    label: `Dataset ${idx + 1}`,
                    data: dataset,
                    color: color.color,
                    pointColor: color.pointColor
                };
            }
            // If it's already an object, use it as-is (with defaults for missing fields)
            return {
                label: dataset.label || `Dataset ${idx + 1}`,
                data: dataset.data || dataset,
                color: dataset.color || (idx === 0 ? 'rgba(37, 99, 235, 0.8)' : idx === 1 ? 'rgba(16, 185, 129, 0.8)' : 'rgba(245, 158, 11, 0.8)'),
                pointColor: dataset.pointColor || dataset.color || 'rgba(37, 99, 235, 1)',
                borderDash: dataset.borderDash,
                yAxisID: dataset.yAxisID || 'y',
                ...dataset  // Allow overriding any defaults
            };
        });

        return createLineBarChart({
            chartKey: key,
            canvasId: canvasId,
            type: type,
            labels: labels,
            datasets: normalizedDatasets,
            options: {
                formatYAxis: options.formatYAxis || 'number',
                gridColor: options.gridColor || 'rgba(148, 163, 184, 0.1)',
                showLegend: options.showLegend !== undefined ? options.showLegend : false,
                ...options
            }
        });
    }

    // Public API - ChartUtils (core utilities)
    window.ChartUtils = {
        createOrUpdateDoughnutChart: createOrUpdateDoughnutChart,
        createPieChart: createPieChart,
        createLineBarChart: createLineBarChart,
        updateChart: updateChart,
        destroyChart: destroyChart,
        destroyAllCharts: destroyAllCharts,
        getChart: getChart,
        formatCurrency: formatCurrency,
        formatCurrencyWithSymbol: formatCurrencyWithSymbol,
        formatCompact: formatCompact,
        formatDateForChart: formatDateForChart,
        DEFAULT_COLORS: DEFAULT_COLORS,
        DEFAULT_COLORS_HOVER: DEFAULT_COLORS_HOVER
    };

    // Public API - Charts (simple facade for easy usage)
    window.Charts = {
        pie: pie,
        line: lineBar,
        bar: lineBar,
        update: updateChartSimple,
        bindIds: bindIds,
        bindChart: bindChart,  // Smart binding: auto-detects canvas/legend, stores config
        getColors: getColors
    };

})(window);

