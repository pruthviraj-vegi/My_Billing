// DashboardCharts: reusable charts module for invoice dashboard and others
// Vanilla JS, attaches a global with configurable element IDs and data keys
(function (window) {
    const DEFAULT_IDS = {
        // stats
        totalInvoices: 'totalInvoices',
        totalAmount: 'totalAmount',
        netAmount: 'netAmount',
        totalProfit: 'totalProfit',
        totalDiscount: 'totalDiscount',

        // filter and containers
        dateFilter: 'dateFilter',
        dashboardLoading: 'dashboardLoading',
        dashboardContent: 'dashboardContent',
        dashboardError: 'dashboardError',

        // charts
        paymentStatusChart: 'paymentStatusChart',
        paymentStatusLegend: 'paymentStatusLegend',
        paymentTypeChart: 'paymentTypeChart',
        paymentTypeLegend: 'paymentTypeLegend',
        categoryChart: 'categoryChart',
        categoryLegend: 'categoryLegend',
        comparisonChart: 'comparisonChart',
        periodInfo: 'periodInfo',
        chartSummary: 'chartSummary',
        comparisonMetric: 'comparisonMetric'
    };

    const chartColors = {
        paymentStatus: [
            'rgba(37, 99, 235, 0.8)',
            'rgba(16, 185, 129, 0.8)',
            'rgba(245, 158, 11, 0.8)',
            'rgba(239, 68, 68, 0.8)',
            'rgba(139, 92, 246, 0.8)'
        ],
        paymentStatusHover: [
            'rgba(37, 99, 235, 1)',
            'rgba(16, 185, 129, 1)',
            'rgba(245, 158, 11, 1)',
            'rgba(239, 68, 68, 1)',
            'rgba(139, 92, 246, 1)'
        ],
        paymentType: [
            'rgba(6, 182, 212, 0.8)',
            'rgba(132, 204, 22, 0.8)',
            'rgba(249, 115, 22, 0.8)',
            'rgba(236, 72, 153, 0.8)',
            'rgba(99, 102, 241, 0.8)'
        ],
        paymentTypeHover: [
            'rgba(6, 182, 212, 1)',
            'rgba(132, 204, 22, 1)',
            'rgba(249, 115, 22, 1)',
            'rgba(236, 72, 153, 1)',
            'rgba(99, 102, 241, 1)'
        ],
        category: [
            'rgba(34, 197, 94, 0.8)',
            'rgba(168, 85, 247, 0.8)',
            'rgba(251, 146, 60, 0.8)',
            'rgba(14, 165, 233, 0.8)',
            'rgba(244, 63, 94, 0.8)',
            'rgba(34, 211, 238, 0.8)',
            'rgba(251, 191, 36, 0.8)',
            'rgba(139, 69, 19, 0.8)'
        ],
        categoryHover: [
            'rgba(34, 197, 94, 1)',
            'rgba(168, 85, 247, 1)',
            'rgba(251, 146, 60, 1)',
            'rgba(14, 165, 233, 1)',
            'rgba(244, 63, 94, 1)',
            'rgba(34, 211, 238, 1)',
            'rgba(251, 191, 36, 1)',
            'rgba(139, 69, 19, 1)'
        ],
        comparison: {
            current: 'rgba(37, 99, 235, 0.8)',
            currentHover: 'rgba(37, 99, 235, 1)',
            previous: 'rgba(16, 185, 129, 0.8)',
            previousHover: 'rgba(16, 185, 129, 1)',
            grid: 'rgba(148, 163, 184, 0.1)',
            text: 'rgba(30, 41, 59, 0.8)'
        }
    };

    const state = {
        ids: { ...DEFAULT_IDS },
        fetchUrl: '',
        currentFilter: 'today',
        charts: {
            paymentStatus: null,
            paymentType: null,
            category: null,
            comparison: null
        }
    };

    function byId(id) { return document.getElementById(id); }

    function formatCurrency(amount) {
        return new Intl.NumberFormat('en-IN', {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        }).format(amount);
    }

    function formatCurrencyCompact(amount) {
        if (amount >= 10000000) return (amount / 10000000).toFixed(1) + 'Cr';
        if (amount >= 100000) return (amount / 100000).toFixed(1) + 'L';
        if (amount >= 1000) return (amount / 1000).toFixed(1) + 'K';
        return amount.toFixed(0);
    }

    function formatNumberCompact(number) {
        if (number >= 10000000) return (number / 10000000).toFixed(1) + 'Cr';
        if (number >= 100000) return (number / 100000).toFixed(1) + 'L';
        if (number >= 1000) return (number / 1000).toFixed(1) + 'K';
        return number.toFixed(0);
    }

    function formatDateForChart(dateString, periodType) {
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
    }

    // Public: fetch and update all UI
    async function loadDashboardData() {
        const loadingEl = byId(state.ids.dashboardLoading);
        const errorEl = byId(state.ids.dashboardError);
        const dateFilter = byId(state.ids.dateFilter);

        if (errorEl) errorEl.style.display = 'none';
        if (dateFilter) {
            dateFilter.style.opacity = '0.7';
            dateFilter.disabled = true;
        }

        try {
            const params = new URLSearchParams({ date_filter: dateFilter ? dateFilter.value : state.currentFilter });
            const response = await fetch(state.fetchUrl + '?' + params.toString());
            if (!response.ok) throw new Error('HTTP ' + response.status);
            const data = await response.json();
            if (!data.success) throw new Error(data.error || 'Failed to load');

            updateStats(data.stats);
            updatePaymentAnalytics(data.payment_status_breakdown, data.payment_type_breakdown);
            updateCategoryAnalytics(data.category_breakdown);
            updateComparisonChart(data.comparison_data);
        } catch (err) {
            console.error('Dashboard loading error:', err);
            if (errorEl) errorEl.style.display = 'block';
        } finally {
            if (dateFilter) {
                dateFilter.style.opacity = '1';
                dateFilter.disabled = false;
            }
        }
    }

    function updateStats(stats) {
        const ids = state.ids;
        const map = {
            totalInvoices: stats.total_invoices,
            totalAmount: formatCurrency(stats.total_amount),
            netAmount: formatCurrency(stats.net_amount),
            totalProfit: formatCurrency(stats.total_profit),
            totalDiscount: formatCurrency(stats.total_discount)
        };
        Object.keys(map).forEach(key => {
            const el = byId(ids[key]);
            if (el) el.textContent = map[key];
        });
    }

    function destroyChart(refName) {
        if (state.charts[refName]) {
            state.charts[refName].destroy();
            state.charts[refName] = null;
        }
    }

    function updatePaymentAnalytics(statusBreakdown, typeBreakdown) {
        destroyChart('paymentStatus');
        destroyChart('paymentType');

        if (statusBreakdown && statusBreakdown.length) createPaymentStatusChart(statusBreakdown);
        else if (byId(state.ids.paymentStatusLegend)) byId(state.ids.paymentStatusLegend).innerHTML = '<p class="text-muted">No payment data available</p>';

        if (typeBreakdown && typeBreakdown.length) createPaymentTypeChart(typeBreakdown);
        else if (byId(state.ids.paymentTypeLegend)) byId(state.ids.paymentTypeLegend).innerHTML = '<p class="text-muted">No payment type data available</p>';
    }

    function updateCategoryAnalytics(categoryBreakdown) {
        destroyChart('category');
        if (categoryBreakdown && categoryBreakdown.length) createCategoryChart(categoryBreakdown);
        else if (byId(state.ids.categoryLegend)) byId(state.ids.categoryLegend).innerHTML = '<p class="text-muted">No category data available</p>';
    }

    /**
     * Generic pie chart creator - converts data to standardized format
     * Uses ChartUtils.createPieChart with standardized data structure
     */
    function createPieChart(config) {
        if (!(window.ChartUtils && ChartUtils.createPieChart)) return null;
        return ChartUtils.createPieChart(config);
    }

    function createPaymentStatusChart(data) {
        // Convert to standardized format: { label, value, amount }
        const standardizedData = data.map(item => ({
            label: item.payment_status,
            value: item.count,
            amount: item.amount
        }));

        state.charts.paymentStatus = createPieChart({
            chartKey: 'invoice_payment_status',
            canvasId: state.ids.paymentStatusChart,
            legendId: state.ids.paymentStatusLegend,
            data: standardizedData,
            colors: chartColors.paymentStatus,
            colorsHover: chartColors.paymentStatusHover
        });
    }

    function createPaymentTypeChart(data) {
        // Convert to standardized format: { label, value, amount }
        const standardizedData = data.map(item => ({
            label: item.payment_type,
            value: item.count,
            amount: item.amount
        }));

        state.charts.paymentType = createPieChart({
            chartKey: 'invoice_payment_type',
            canvasId: state.ids.paymentTypeChart,
            legendId: state.ids.paymentTypeLegend,
            data: standardizedData,
            colors: chartColors.paymentType,
            colorsHover: chartColors.paymentTypeHover
        });
    }

    function createCategoryChart(data) {
        // Convert to standardized format: { label, value, amount }
        const standardizedData = data.map(item => ({
            label: item.category_name,
            value: item.count,
            amount: item.amount
        }));

        state.charts.category = createPieChart({
            chartKey: 'invoice_category',
            canvasId: state.ids.categoryChart,
            legendId: state.ids.categoryLegend,
            data: standardizedData,
            colors: chartColors.category,
            colorsHover: chartColors.categoryHover
        });
    }

    function updateComparisonChart(comparisonData) {
        if (!comparisonData) return;
        destroyChart('comparison');

        const metricSelect = byId(state.ids.comparisonMetric);
        const metric = metricSelect ? metricSelect.value : 'amount';

        const ctx = byId(state.ids.comparisonChart).getContext('2d');
        const currentData = comparisonData.current_period.data.map(i => i[metric]);
        const previousData = comparisonData.previous_period.data.map(i => i[metric]);
        const labels = comparisonData.current_period.data.map(i => formatDateForChart(i.date, comparisonData.period_type));

        const percentageData = currentData.map((cur, idx) => {
            const prev = previousData[idx] || 0;
            if (prev === 0) return cur > 0 ? 100 : 0;
            return ((cur - prev) / prev) * 100;
        });

        const chartData = {
            labels: labels,
            datasets: [
                {
                    label: comparisonData.current_period.label,
                    data: currentData,
                    borderColor: chartColors.comparison.current,
                    backgroundColor: chartColors.comparison.current,
                    borderWidth: 3,
                    fill: false,
                    tension: 0.4,
                    pointBackgroundColor: chartColors.comparison.currentHover,
                    pointBorderColor: chartColors.comparison.currentHover,
                    pointRadius: 6,
                    pointHoverRadius: 8,
                    pointHoverBackgroundColor: chartColors.comparison.currentHover,
                    pointHoverBorderColor: chartColors.comparison.currentHover,
                    pointHoverBorderWidth: 2,
                    yAxisID: 'y'
                },
                {
                    label: comparisonData.previous_period.label,
                    data: previousData,
                    borderColor: chartColors.comparison.previous,
                    backgroundColor: chartColors.comparison.previous,
                    borderWidth: 3,
                    fill: false,
                    tension: 0.4,
                    pointBackgroundColor: chartColors.comparison.previousHover,
                    pointBorderColor: chartColors.comparison.previousHover,
                    pointRadius: 6,
                    pointHoverRadius: 8,
                    pointHoverBackgroundColor: chartColors.comparison.previousHover,
                    pointHoverBorderColor: chartColors.comparison.previousHover,
                    pointHoverBorderWidth: 2,
                    borderDash: [5, 5],
                    yAxisID: 'y'
                },
                {
                    label: 'Change %',
                    data: percentageData,
                    borderColor: 'rgba(245, 158, 11, 0.8)',
                    backgroundColor: 'rgba(245, 158, 11, 0.8)',
                    borderWidth: 2,
                    fill: false,
                    tension: 0.4,
                    pointBackgroundColor: 'rgba(245, 158, 11, 1)',
                    pointBorderColor: 'rgba(245, 158, 11, 1)',
                    pointRadius: 4,
                    pointHoverRadius: 6,
                    pointHoverBackgroundColor: 'rgba(245, 158, 11, 1)',
                    pointHoverBorderColor: 'rgba(245, 158, 11, 1)',
                    pointHoverBorderWidth: 2,
                    borderDash: [2, 2],
                    yAxisID: 'y1'
                }
            ]
        };

        state.charts.comparison = new Chart(ctx, {
            type: 'line',
            data: chartData,
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: { intersect: false, mode: 'index' },
                animation: { duration: 1000, easing: 'easeOutQuart' },
                plugins: {
                    legend: { display: false },
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
                            title: ctx => ctx[0].label,
                            label: ctx => {
                                const label = ctx.dataset.label;
                                const value = ctx.parsed.y;
                                if (label === 'Change %') return value.toFixed(1) + '%';
                                return (metric === 'amount') ? formatCurrency(value) : value;
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        display: true,
                        grid: { color: chartColors.comparison.grid, drawBorder: false }
                    },
                    y: {
                        type: 'linear',
                        display: true,
                        position: 'left',
                        grid: { color: chartColors.comparison.grid, drawBorder: false },
                        ticks: {
                            callback: function (value) {
                                return (metric === 'amount') ? formatCurrencyCompact(value) : formatNumberCompact(value);
                            }
                        }
                    },
                    y1: {
                        type: 'linear',
                        display: true,
                        position: 'right',
                        grid: { drawOnChartArea: false },
                        ticks: { callback: value => value.toFixed(1) + '%' }
                    }
                }
            }
        });

        updatePeriodInfo(comparisonData);
        updateChartSummary(comparisonData, metric);
    }

    function updatePeriodInfo(data) {
        const el = byId(state.ids.periodInfo);
        if (!el) return;
        el.innerHTML = (
            '<div class="period-comparison">' +
            '<div class="period-item current-period">' +
            '<div class="period-label">Current Period</div>' +
            '<div class="period-range">' + data.current_period.label + '</div>' +
            '</div>' +
            '<div class="period-item previous-period">' +
            '<div class="period-label">Previous Period</div>' +
            '<div class="period-range">' + data.previous_period.label + '</div>' +
            '</div>' +
            '</div>'
        );
    }

    function updateChartSummary(data, metric) {
        const el = byId(state.ids.chartSummary);
        if (!el) return;
        const currentTotal = data.current_period.data.reduce((s, i) => s + i[metric], 0);
        const previousTotal = data.previous_period.data.reduce((s, i) => s + i[metric], 0);
        const change = currentTotal - previousTotal;
        const changePercent = previousTotal > 0 ? ((change / previousTotal) * 100) : 0;
        const changeClass = change >= 0 ? 'positive' : 'negative';
        const changeIcon = change >= 0 ? 'fas fa-arrow-up' : 'fas fa-arrow-down';
        const formattedCurrent = metric === 'amount' ? formatCurrency(currentTotal) : currentTotal;
        const formattedPrevious = metric === 'amount' ? formatCurrency(previousTotal) : previousTotal;
        const formattedChange = metric === 'amount' ? formatCurrency(Math.abs(change)) : Math.abs(change);

        el.innerHTML = (
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

    function attachEvents() {
        const dateFilter = byId(state.ids.dateFilter);
        if (dateFilter) dateFilter.addEventListener('change', loadDashboardData);

        const comparisonMetric = byId(state.ids.comparisonMetric);
        if (comparisonMetric) comparisonMetric.addEventListener('change', () => {
            // re-render with latest metric using last fetched data path: trigger full refresh to keep simple
            // If you want to avoid refetch, store last response and reuse; keeping lean here
            loadDashboardData();
        });
    }

    function init(config) {
        state.fetchUrl = config.fetchUrl;
        state.currentFilter = config.currentFilter || state.currentFilter;
        state.ids = { ...DEFAULT_IDS, ...(config.elementIds || {}) };

        // Set initial filter value if present
        const dateFilter = byId(state.ids.dateFilter);
        if (dateFilter && state.currentFilter) dateFilter.value = state.currentFilter;

        attachEvents();
        loadDashboardData();
    }

    window.DashboardCharts = {
        init: init,
        reload: loadDashboardData
    };
})(window);


