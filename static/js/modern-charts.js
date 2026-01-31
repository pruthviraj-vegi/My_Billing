/**
 * ModernCharts: Reusable chart components for modern dashboard design
 * Dependencies: Chart.js 4.x
 */

(function (window) {
    'use strict';

    const ModernCharts = {
        // Get Theme Colors from CSS Variables
        getColors: function () {
            const style = getComputedStyle(document.body);
            const bgSurface = style.getPropertyValue('--bg-surface').trim() || '#1e293b';

            // Detect dark mode - check multiple sources
            const hasDarkTheme = document.documentElement.getAttribute('data-theme') === 'dark';
            const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
            const isDarkColor = bgSurface === '#1e293b' || bgSurface.toLowerCase().includes('1e293b') ||
                bgSurface === '#334155' || bgSurface.toLowerCase().includes('334155');
            const isDarkMode = hasDarkTheme || (prefersDark && !hasDarkTheme && isDarkColor) || isDarkColor;

            // Border color for doughnut charts - white in light mode, dark surface in dark mode
            // In light mode, use white to blend seamlessly with white background (no awkward black border)
            // In dark mode, use the dark surface color for a subtle dark border
            const doughnutBorder = isDarkMode ? bgSurface : '#ffffff'; // White for light mode to blend with background

            return {
                blue: style.getPropertyValue('--primary').trim() || '#3b82f6',
                green: style.getPropertyValue('--success').trim() || '#10b981',
                yellow: style.getPropertyValue('--warning').trim() || '#f59e0b',
                red: style.getPropertyValue('--danger').trim() || '#ef4444',
                purple: style.getPropertyValue('--chart-purple').trim() || '#8b5cf6',
                cyan: style.getPropertyValue('--chart-cyan').trim() || '#06b6d4',
                pink: style.getPropertyValue('--chart-pink').trim() || '#ec4899',
                slate: style.getPropertyValue('--secondary').trim() || '#94a3b8',
                grid: style.getPropertyValue('--border-color').trim() || 'rgba(148, 163, 184, 0.1)',
                textPrimary: style.getPropertyValue('--text-primary').trim() || '#f8fafc',
                textSecondary: style.getPropertyValue('--text-secondary').trim() || '#94a3b8',
                tooltipBg: bgSurface,
                doughnutBorder: doughnutBorder
            };
        },

        // Format number to Indian currency format (Crores, Lakhs, Thousands)
        formatIndianCurrency: function (value) {
            if (value === 0) return '0';

            const absValue = Math.abs(value);
            const sign = value < 0 ? '-' : '';

            if (absValue >= 10000000) {
                // Crores (1,00,00,000+)
                return sign + (absValue / 10000000).toFixed(1) + 'Cr';
            } else if (absValue >= 100000) {
                // Lakhs (1,00,000+)
                return sign + (absValue / 100000).toFixed(1) + 'L';
            } else if (absValue >= 1000) {
                // Thousands (1,000+)
                return sign + (absValue / 1000).toFixed(1) + 'K';
            } else {
                // Less than 1000
                return sign + absValue.toFixed(0);
            }
        },

        // Custom Plugin to draw text inside doughnut segments
        doughnutLabelPlugin: {
            id: 'doughnutLabel',
            afterDatasetsDraw(chart, args, options) {
                const { ctx, data } = chart;
                chart.data.datasets.forEach((dataset, i) => {
                    chart.getDatasetMeta(i).data.forEach((datapoint, index) => {
                        const { x, y } = datapoint.tooltipPosition();

                        // Get percentage
                        const value = dataset.data[index];
                        const total = dataset.data.reduce((a, b) => a + b, 0);
                        const percentage = total > 0 ? ((value / total) * 100).toFixed(1) + '%' : '0%';

                        if (value > 0) { // Only draw if value exists
                            ctx.save();
                            ctx.font = 'bold 10px Inter, sans-serif';
                            ctx.fillStyle = '#ffffff';
                            ctx.textAlign = 'center';
                            ctx.textBaseline = 'middle';
                            ctx.fillText(percentage, x, y);
                            ctx.restore();
                        }
                    });
                });
            }
        },

        // Custom Plugin to draw total amount in the center of doughnut chart
        centerTextPlugin: {
            id: 'centerText',
            afterDatasetsDraw(chart, args, options) {
                const { ctx, chartArea: { left, top, right, bottom, width, height } } = chart;

                // Calculate center position
                const centerX = (left + right) / 2;
                const centerY = (top + bottom) / 2;

                // Get total amount from chart data
                const total = chart.data.datasets[0].data.reduce((a, b) => a + b, 0);

                // Don't show anything if total is null or 0
                if (!total || total === 0) {
                    return;
                }

                // Get colors from CSS variables for theme support
                const style = getComputedStyle(document.body);
                const textColor = style.getPropertyValue('--text-primary').trim() || '#f8fafc';

                ctx.save();

                // Format and draw the total amount (without label)
                const formattedTotal = total.toLocaleString('en-IN', {
                    minimumFractionDigits: 2,
                    maximumFractionDigits: 2
                });

                ctx.font = 'bold 16px Inter, sans-serif';
                ctx.fillStyle = textColor;
                ctx.textAlign = 'center';
                ctx.textBaseline = 'middle';
                ctx.fillText(formattedTotal, centerX, centerY);

                ctx.restore();
            }
        },

        // Initialize a Doughnut Chart
        initDoughnut: function (ctx) {
            const colors = this.getColors();
            // Use background color for border to create gap effect
            const borderColor = colors.tooltipBg;
            return new Chart(ctx, {
                type: 'doughnut',
                data: {
                    labels: [],
                    datasets: [{
                        data: [],
                        backgroundColor: [],
                        borderWidth: 3, // Add border for gap between segments
                        borderColor: borderColor // Use background color to create gap
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    cutout: '60%',
                    plugins: {
                        legend: { display: false },
                        tooltip: { enabled: false }
                    }
                },
                plugins: [this.doughnutLabelPlugin, this.centerTextPlugin]
            });
        },

        // Update Doughnut Chart Data and Legend
        updateDoughnut: function (chart, legendId, items, keys, colorMap = null) {
            // keys: { label: 'key_for_label', count: 'key_for_count', amount: 'key_for_amount', percentage: 'key_for_percentage' (optional) }
            if (!items || !chart) return;

            const colors = this.getColors();
            const labels = items.map(d => d[keys.label]);
            const counts = items.map(d => d[keys.count]);
            const amounts = items.map(d => d[keys.amount] || 0);

            chart.data.labels = labels;
            // Use amounts for chart display (pie size based on financial value, not count)
            chart.data.datasets[0].data = amounts;
            chart.data.datasets[0].borderWidth = 3; // Add border for gap between segments
            chart.data.datasets[0].borderColor = colors.tooltipBg; // Use background color to create gap

            // Generate colors
            const defaultColors = [
                colors.blue, colors.green, colors.yellow,
                colors.red, colors.purple, colors.pink, colors.cyan
            ];

            let bgColors;
            if (colorMap) {
                bgColors = labels.map(l => colorMap[l] || colors.slate);
            } else {
                bgColors = labels.map((_, i) => defaultColors[i % defaultColors.length]);
            }

            chart.data.datasets[0].backgroundColor = bgColors;
            chart.update();

            // Generate Legend
            const legendContainer = document.getElementById(legendId);
            if (legendContainer) {
                legendContainer.innerHTML = '';

                items.forEach((item, index) => {
                    // Use backend-calculated percentage if available, otherwise fallback to calculation
                    let percentage;
                    if (keys.percentage && item[keys.percentage] !== undefined) {
                        // Use backend percentage
                        percentage = item[keys.percentage] + '%';
                    } else {
                        // Fallback: calculate percentage (for backward compatibility)
                        const total = counts.reduce((a, b) => a + b, 0);
                        percentage = total > 0 ? ((item[keys.count] / total) * 100).toFixed(1) + '%' : '0%';
                    }

                    const color = bgColors[index];
                    const amount = item[keys.amount] || 0;
                    const formattedAmount = amount.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

                    // New Design Structure
                    const itemHtml = `
                        <div class="legend-item">
                            <div class="legend-dot" style="background-color: ${color}"></div>
                            <div class="legend-content">
                                <div class="legend-label">
                                    ${item[keys.label]} — ${item[keys.count]} (${percentage})
                                </div>
                                <div class="legend-amount">${formattedAmount}</div>
                            </div>
                        </div>
                        ${index < items.length - 1 ? '<hr class="legend-separator">' : ''}
                    `;
                    legendContainer.insertAdjacentHTML('beforeend', itemHtml);
                });
            }
        },

        // Initialize Revenue/Comparison Chart
        initRevenueChart: function (ctx) {
            const colors = this.getColors();

            // Detect dark mode for gradient opacity
            const bgSurface = colors.tooltipBg;
            const hasDarkTheme = document.documentElement.getAttribute('data-theme') === 'dark';
            const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
            const isDarkColor = bgSurface === '#1e293b' || bgSurface.toLowerCase().includes('1e293b') ||
                bgSurface === '#334155' || bgSurface.toLowerCase().includes('334155');
            const isDarkMode = hasDarkTheme || (prefersDark && !hasDarkTheme && isDarkColor) || isDarkColor;

            // Gradient opacity - lighter in light mode, darker in dark mode
            const gradientOpacity = isDarkMode ? 0.5 : 0.15; // Much lighter in light mode
            const gradient = ctx.createLinearGradient(0, 0, 0, 400);
            gradient.addColorStop(0, `rgba(59, 130, 246, ${gradientOpacity})`);
            gradient.addColorStop(1, 'rgba(59, 130, 246, 0.0)');

            // Previous period background - lighter in light mode
            const previousBgOpacity = isDarkMode ? 0.2 : 0.08; // Much lighter in light mode
            const previousBackground = `rgba(148, 163, 184, ${previousBgOpacity})`;

            return new Chart(ctx, {
                type: 'line',
                data: {
                    labels: [],
                    datasets: [{
                        label: 'Present',
                        data: [],
                        borderColor: colors.blue,
                        backgroundColor: gradient,
                        borderWidth: 2,
                        pointBackgroundColor: colors.tooltipBg,
                        pointBorderColor: colors.blue,
                        pointBorderWidth: 2,
                        pointRadius: 5,
                        pointHoverRadius: 8,
                        pointStyle: 'circle',
                        fill: true,
                        tension: 0.4,
                        order: 2,
                        yAxisID: 'y'
                    },
                    {
                        label: 'Past',
                        data: [],
                        borderColor: colors.slate,
                        backgroundColor: previousBackground, // Theme-aware background
                        borderWidth: 2,
                        pointBackgroundColor: colors.tooltipBg,
                        pointBorderColor: colors.slate,
                        pointBorderWidth: 2,
                        pointRadius: 4,
                        pointHoverRadius: 7,
                        pointStyle: 'circle',
                        fill: true,
                        tension: 0.4,
                        order: 3,
                        yAxisID: 'y'
                    },
                    {
                        label: 'Growth %',
                        data: [],
                        borderColor: colors.green,
                        backgroundColor: 'transparent',
                        borderWidth: 2,
                        borderDash: [4, 4],
                        pointBackgroundColor: colors.tooltipBg,
                        pointBorderColor: colors.green,
                        pointBorderWidth: 2,
                        pointRadius: 3,
                        pointHoverRadius: 5,
                        fill: false,
                        tension: 0.4,
                        order: 1,
                        yAxisID: 'y1'
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: {
                        mode: 'index',
                        intersect: false,
                    },
                    plugins: {
                        legend: { display: false },
                        tooltip: {
                            enabled: true,
                            backgroundColor: colors.tooltipBg,
                            titleColor: colors.textPrimary,
                            bodyColor: colors.textPrimary,
                            borderColor: colors.blue,
                            borderWidth: 2,
                            padding: 14,
                            cornerRadius: 12,
                            displayColors: true,
                            usePointStyle: true,
                            boxWidth: 8,
                            boxHeight: 8,
                            boxPadding: 6,
                            titleFont: {
                                size: 13,
                                weight: 'bold'
                            },
                            bodyFont: {
                                size: 14,
                                weight: 'bold',
                                family: "'Inter', sans-serif"
                            },
                            callbacks: {
                                label: function (context) {
                                    const label = context.dataset.label || '';
                                    if (context.dataset.yAxisID === 'y1') {
                                        const value = context.parsed.y.toFixed(1) + '%';
                                        return label + ':  ' + value;
                                    } else {
                                        // Show full amount in tooltip with Indian format - highlighted
                                        const value = context.parsed.y;
                                        const formattedValue = value.toLocaleString('en-IN');
                                        return label + ':  ' + formattedValue;
                                    }
                                },
                                labelColor: function (context) {
                                    // Make the color box match the line color
                                    return {
                                        borderColor: context.dataset.borderColor,
                                        backgroundColor: context.dataset.borderColor,
                                        borderWidth: 2,
                                        borderRadius: 4
                                    };
                                }
                            }
                        }
                    },
                    scales: {
                        y: {
                            type: 'linear',
                            display: true,
                            position: 'left',
                            grid: { color: colors.grid, drawBorder: false },
                            ticks: {
                                color: colors.slate,
                                callback: function (value) {
                                    return ModernCharts.formatIndianCurrency(value);
                                }
                            }
                        },
                        y1: {
                            type: 'linear',
                            display: true,
                            position: 'right',
                            grid: { drawOnChartArea: false },
                            ticks: {
                                color: colors.green,
                                callback: function (value) { return value + '%'; }
                            }
                        },
                        x: {
                            grid: { display: false },
                            ticks: { color: colors.slate }
                        }
                    }
                }
            });
        },

        // Update Revenue Chart Data
        updateRevenueChart: function (chart, comparisonData) {
            if (!comparisonData || !chart) return;

            // Refresh colors in case theme changed
            const colors = this.getColors();

            // Detect dark mode for gradient opacity
            const bgSurface = colors.tooltipBg;
            const hasDarkTheme = document.documentElement.getAttribute('data-theme') === 'dark';
            const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
            const isDarkColor = bgSurface === '#1e293b' || bgSurface.toLowerCase().includes('1e293b') ||
                bgSurface === '#334155' || bgSurface.toLowerCase().includes('334155');
            const isDarkMode = hasDarkTheme || (prefersDark && !hasDarkTheme && isDarkColor) || isDarkColor;

            // Update gradient with theme-aware opacity
            const gradientOpacity = isDarkMode ? 0.5 : 0.15;
            const ctx = chart.canvas.getContext('2d');
            const gradient = ctx.createLinearGradient(0, 0, 0, 400);
            gradient.addColorStop(0, `rgba(59, 130, 246, ${gradientOpacity})`);
            gradient.addColorStop(1, 'rgba(59, 130, 246, 0.0)');

            // Update previous period background with theme-aware opacity
            const previousBgOpacity = isDarkMode ? 0.2 : 0.08;
            const previousBackground = `rgba(148, 163, 184, ${previousBgOpacity})`;

            // Update chart options with new colors
            chart.options.scales.y.grid.color = colors.grid;
            chart.options.plugins.tooltip.backgroundColor = colors.tooltipBg;
            chart.options.plugins.tooltip.titleColor = colors.textPrimary;
            chart.options.plugins.tooltip.bodyColor = colors.textSecondary;
            chart.options.plugins.tooltip.borderColor = colors.grid;

            // Update dataset colors with theme-aware values
            chart.data.datasets[0].backgroundColor = gradient; // Current period gradient
            chart.data.datasets[1].backgroundColor = previousBackground; // Previous period background

            // Update point backgrounds
            chart.data.datasets.forEach(dataset => {
                dataset.pointBackgroundColor = colors.tooltipBg;
            });

            let currentData = [];
            let previousData = [];

            // Current Period
            if (comparisonData.current_period) {
                const cData = comparisonData.current_period.data;
                chart.data.labels = cData.map(d => {
                    const date = new Date(d.date);
                    return date.toLocaleDateString('en-US', { day: 'numeric', month: 'short' });
                });
                currentData = cData.map(d => d.amount);
                chart.data.datasets[0].data = currentData;
            }

            // Previous Period
            if (comparisonData.previous_period) {
                const pData = comparisonData.previous_period.data;
                previousData = pData.map(d => d.amount);
                chart.data.datasets[1].data = previousData;
            }

            // Calculate Growth %
            const growthData = currentData.map((curr, index) => {
                const prev = previousData[index] || 0;
                if (prev === 0) return 0;
                return ((curr - prev) / prev) * 100;
            });
            chart.data.datasets[2].data = growthData;

            chart.update();

            return { currentData, previousData };
        },

        // Update Summary Stats Header
        updateSummaryStats: function (currentData, previousData, elementIds) {
            // elementIds: { current: 'id', previous: 'id', change: 'id' }
            const totalCurrent = currentData.reduce((a, b) => a + b, 0);
            const totalPrevious = previousData.reduce((a, b) => a + b, 0);
            const totalChange = totalPrevious > 0 ? ((totalCurrent - totalPrevious) / totalPrevious) * 100 : 0;

            const currentEl = document.getElementById(elementIds.current);
            if (currentEl) currentEl.textContent = totalCurrent.toLocaleString('en-IN');

            const previousEl = document.getElementById(elementIds.previous);
            if (previousEl) previousEl.textContent = totalPrevious.toLocaleString('en-IN');

            const changeEl = document.getElementById(elementIds.change);
            if (changeEl) {
                changeEl.textContent = (totalChange >= 0 ? '+' : '') + totalChange.toFixed(1) + '%';
                changeEl.className = 'stat-change ' + (totalChange >= 0 ? 'text-success' : 'text-danger');
            }
        },

        // Expose colors for external use if needed
        colors: {
            blue: '#3b82f6',
            green: '#10b981',
            yellow: '#f59e0b',
            red: '#ef4444',
            purple: '#8b5cf6',
            cyan: '#06b6d4',
            pink: '#ec4899',
            slate: '#94a3b8',
            grid: 'rgba(148, 163, 184, 0.1)',
            textPrimary: '#f8fafc',
            textSecondary: '#94a3b8'
        }
    };

    // Expose to window
    window.ModernCharts = ModernCharts;

})(window);
