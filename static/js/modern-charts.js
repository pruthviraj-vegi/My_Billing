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
            const hasDarkTheme = document.body.getAttribute('data-theme') === 'dark';
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

                        // Get percentage — only label segments >= 4% to avoid crowding
                        const value = dataset.data[index];
                        const total = dataset.data.reduce((a, b) => a + b, 0);
                        const pctNum = total > 0 ? (value / total) * 100 : 0;

                        if (pctNum >= 3) {
                            const percentage = pctNum.toFixed(1) + '%';
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


        // Initialize a Doughnut Chart
        initDoughnut: function (ctx) {
            const colors = this.getColors();
            const borderColor = colors.doughnutBorder;
            return new Chart(ctx, {
                type: 'doughnut',
                data: {
                    labels: [],
                    datasets: [{
                        data: [],
                        backgroundColor: [],
                        borderColor: borderColor,
                        borderWidth: 2,
                        borderRadius: 6,
                        hoverOffset: 10,
                        hoverBorderWidth: 2,
                        hoverBorderColor: borderColor
                    }]
                },
                options: {
                    responsive: false,
                    cutout: '64%',
                    animation: { animateRotate: true, duration: 900, easing: 'easeInOutQuart' },
                    plugins: {
                        legend: { display: false },
                        tooltip: { enabled: false }
                    }
                },
                plugins: [this.doughnutLabelPlugin]
            });
        },

        // Update Doughnut Chart Data and Legend
        updateDoughnut: function (chart, legendId, items, keys, colorMap = null) {
            // keys: { label, count, amount, percentage (optional) }
            if (!items || !chart) return;

            const colors = this.getColors();
            const labels = items.map(d => d[keys.label]);
            const counts = items.map(d => d[keys.count]);
            const amounts = items.map(d => d[keys.amount] || 0);
            const totalAmount = amounts.reduce((a, b) => a + b, 0);

            chart.data.labels = labels;
            chart.data.datasets[0].data = amounts;
            chart.data.datasets[0].borderColor = colors.doughnutBorder;
            chart.data.datasets[0].borderWidth = 2;
            chart.data.datasets[0].borderRadius = 6;
            chart.data.datasets[0].hoverOffset = 10;
            chart.data.datasets[0].hoverBorderWidth = 2;
            chart.data.datasets[0].hoverBorderColor = colors.doughnutBorder;

            // Color palette
            const defaultPalette = [
                '#378ADD', '#1D9E75', '#EF9F27', '#D85A30', '#D4537E',
                '#7F77DD', '#639922', '#BA7517', '#993556', '#534AB7',
                '#3B6D11', '#854F0B', '#A32D2D', '#0F6E56'
            ];

            let bgColors;
            if (colorMap) {
                bgColors = labels.map(l => colorMap[l] || colors.slate);
            } else {
                bgColors = labels.map((_, i) => defaultPalette[i % defaultPalette.length]);
            }

            chart.data.datasets[0].backgroundColor = bgColors;

            // Hover callback: highlight legend items and update center-info
            const canvasEl = chart.canvas;
            const chartId = canvasEl.id;
            // Derive center-info element IDs from the legend container ID pattern
            const prefix = legendId.replace('Legend', '').replace('legend', '');
            // Look for center-info elements (pmCenterLabel, pmCenterPct, pmCenterVal)
            // We'll search for them near the canvas container
            const donutWrap = canvasEl.closest('.donut-wrap');
            const cLabelEl = donutWrap ? donutWrap.querySelector('.center-label') : null;
            const cPctEl = donutWrap ? donutWrap.querySelector('.center-pct') : null;
            const cValEl = donutWrap ? donutWrap.querySelector('.center-val') : null;

            const formattedTotal = '₹' + totalAmount.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

            // Update center with total initially
            if (cLabelEl) cLabelEl.textContent = 'total value';
            if (cPctEl) cPctEl.textContent = '';
            if (cValEl) cValEl.textContent = formattedTotal;
            // setActive helper for hover interaction
            function setActive(idx) {
                const legendContainer = document.getElementById(legendId);
                if (!legendContainer) return;
                legendContainer.querySelectorAll('.leg-item').forEach(function (el, i) {
                    el.style.opacity = idx === null ? '1' : (i === idx ? '1' : '0.3');
                });

                // Highlight the chart segment and dim others
                if (idx === null) {
                    chart.setActiveElements([]);
                    chart.data.datasets[0].backgroundColor = bgColors;
                } else {
                    chart.setActiveElements([{ datasetIndex: 0, index: idx }]);
                    // Dim non-active segments
                    chart.data.datasets[0].backgroundColor = bgColors.map(function (c, i) {
                        if (i === idx) return c;
                        // Convert hex to rgba with 30% opacity
                        var r = parseInt(c.slice(1, 3), 16);
                        var g = parseInt(c.slice(3, 5), 16);
                        var b = parseInt(c.slice(5, 7), 16);
                        return 'rgba(' + r + ',' + g + ',' + b + ',0.25)';
                    });
                }
                chart.update('none');

                if (idx === null) {
                    if (cLabelEl) cLabelEl.textContent = 'total value';
                    if (cPctEl) cPctEl.textContent = '';
                    if (cValEl) cValEl.textContent = formattedTotal;
                } else {
                    const item = items[idx];
                    let pct;
                    if (keys.percentage && item[keys.percentage] !== undefined) {
                        pct = item[keys.percentage];
                    } else {
                        pct = totalAmount > 0 ? ((item[keys.amount] || 0) / totalAmount * 100).toFixed(1) : '0';
                    }
                    if (cLabelEl) cLabelEl.textContent = item[keys.label];
                    if (cPctEl) cPctEl.textContent = pct + '%';
                    if (cValEl) cValEl.textContent = '₹' + (item[keys.amount] || 0).toLocaleString('en-IN');
                }
            }

            // Chart hover callback
            chart.options.onHover = function (e, els) {
                if (els.length) setActive(els[0].index);
                else setActive(null);
            };

            // Mouse leave on canvas resets
            canvasEl.onmouseleave = function () { setActive(null); };

            chart.update();

            // Compute max percentage for bar scaling
            const percentages = items.map(function (item) {
                if (keys.percentage && item[keys.percentage] !== undefined) {
                    return parseFloat(item[keys.percentage]);
                }
                return totalAmount > 0 ? ((item[keys.amount] || 0) / totalAmount * 100) : 0;
            });
            const maxPct = Math.max.apply(null, percentages) || 1;

            // Generate Legend with bar-track style
            const legendContainer = document.getElementById(legendId);
            if (legendContainer) {
                legendContainer.innerHTML = '';

                items.forEach(function (item, index) {
                    var pct = percentages[index];
                    var pctStr = pct.toFixed(1) + '%';
                    var color = bgColors[index];
                    var amount = item[keys.amount] || 0;
                    var formattedAmount = amount.toLocaleString('en-IN');

                    var div = document.createElement('div');
                    div.className = 'leg-item';
                    div.dataset.idx = index;
                    div.innerHTML = '<span class="leg-dot" style="background:' + color + '"></span>' +
                        '<span class="leg-name">' + item[keys.label] + '</span>' +
                        '<span class="leg-pct">' + pctStr + '</span>' +
                        '<span class="leg-val">&nbsp;' + formattedAmount + '</span>';

                    var track = document.createElement('div');
                    track.className = 'bar-track';
                    var fill = document.createElement('div');
                    fill.className = 'bar-fill';
                    fill.style.background = color;
                    fill.style.width = '0';
                    track.appendChild(fill);
                    div.appendChild(track);
                    legendContainer.appendChild(div);

                    // Animate bar fill
                    setTimeout(function () {
                        fill.style.width = (pct / maxPct * 100) + '%';
                    }, 300 + index * 40);

                    // Hover events on legend items
                    div.addEventListener('mouseenter', function () { setActive(index); });
                    div.addEventListener('mouseleave', function () { setActive(null); });
                });
            }
        },

        // Initialize Revenue/Comparison Chart
        initRevenueChart: function (ctx) {
            const colors = this.getColors();

            // Detect dark mode for gradient opacity
            const bgSurface = colors.tooltipBg;
            const hasDarkTheme = document.body.getAttribute('data-theme') === 'dark';
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
                                        const value = context.parsed.y.toFixed(2) + '%';
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
                                callback: function (value) { return value.toFixed(2) + '%'; }
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
            const hasDarkTheme = document.body.getAttribute('data-theme') === 'dark';
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

            // Detect dual-series mode (stock_in vs stock_out)
            const cData = comparisonData.current_period ? comparisonData.current_period.data : [];
            const isDualSeries = cData.length > 0 && cData[0].stock_out !== undefined;

            if (isDualSeries) {
                // Stock In vs Stock Out mode — both series come from current_period
                chart.data.labels = cData.map(d => {
                    const date = new Date(d.date);
                    return date.toLocaleDateString('en-US', { day: 'numeric', month: 'short' });
                });
                currentData = cData.map(d => d.amount);       // Stock In
                previousData = cData.map(d => d.stock_out);    // Stock Out

                chart.data.datasets[0].label = 'Stock In';
                chart.data.datasets[0].data = currentData;
                chart.data.datasets[0].borderColor = colors.green;

                chart.data.datasets[1].label = 'Stock Out';
                chart.data.datasets[1].data = previousData;
                chart.data.datasets[1].borderColor = colors.red;
                chart.data.datasets[1].pointBorderColor = colors.red;
            } else {
                // Original current vs previous period mode
                if (comparisonData.current_period) {
                    chart.data.labels = cData.map(d => {
                        const date = new Date(d.date);
                        return date.toLocaleDateString('en-US', { day: 'numeric', month: 'short' });
                    });
                    currentData = cData.map(d => d.amount);
                    chart.data.datasets[0].data = currentData;
                }

                if (comparisonData.previous_period) {
                    const pData = comparisonData.previous_period.data;
                    previousData = pData.map(d => d.amount);
                    chart.data.datasets[1].data = previousData;
                }
            }

            // Calculate Growth %
            const growthData = currentData.map((curr, index) => {
                const prev = previousData[index] || 0;
                if (isDualSeries) {
                    // Dual-series: growth = (stockOut - stockIn) / stockIn
                    // Positive when selling more than buying (good)
                    if (curr === 0) return 0;
                    return ((prev - curr) / curr) * 100;
                }
                if (prev === 0) return 0;
                return ((curr - prev) / prev) * 100;
            });
            chart.data.datasets[2].data = growthData;

            chart.update();

            return { currentData, previousData };
        },

        // Update Summary Stats Header
        updateSummaryStats: function (currentData, previousData, elementIds, options) {
            // elementIds: { current: 'id', previous: 'id', change: 'id' }
            // options: { inverted: true } — when higher previousData (stock out) is positive
            const opts = options || {};
            const totalCurrent = currentData.reduce((a, b) => a + b, 0);
            const totalPrevious = previousData.reduce((a, b) => a + b, 0);
            let totalChange;
            if (opts.inverted) {
                // Stock mode: positive when stockOut > stockIn
                totalChange = totalCurrent > 0 ? ((totalPrevious - totalCurrent) / totalCurrent) * 100 : 0;
            } else {
                totalChange = totalPrevious > 0 ? ((totalCurrent - totalPrevious) / totalPrevious) * 100 : 0;
            }

            const currentEl = document.getElementById(elementIds.current);
            if (currentEl) currentEl.textContent = totalCurrent.toLocaleString('en-IN');

            const previousEl = document.getElementById(elementIds.previous);
            if (previousEl) previousEl.textContent = totalPrevious.toLocaleString('en-IN');

            const changeEl = document.getElementById(elementIds.change);
            if (changeEl) {
                changeEl.textContent = (totalChange >= 0 ? '+' : '') + totalChange.toFixed(2) + '%';
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
