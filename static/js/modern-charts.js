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

            const palette = {
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
            };

            // Lighter shades matching stat-card icon colors (used for strokes and fill base)
            // Reference: bg-blue = bg rgba(59,130,246,0.15) + color #60a5fa
            var lightShades = [
                '#60a5fa', // blue light
                '#a78bfa', // purple light
                '#34d399', // green light
                '#f87171', // red light
                '#22d3ee', // cyan light
                '#f472b6', // pink light
                '#fbbf24', // yellow light
                '#818cf8', // indigo light
                '#2dd4bf', // teal light
                '#fb923c', // orange light
                '#a3e635', // lime light
                '#94a3b8', // slate
            ];

            function fade(hex) {
                var r = parseInt(hex.slice(1, 3), 16);
                var g = parseInt(hex.slice(3, 5), 16);
                var b = parseInt(hex.slice(5, 7), 16);
                return 'rgba(' + r + ',' + g + ',' + b + ',0.45)';
            }

            palette.doughnutStrokes = lightShades;
            palette.doughnutFills = lightShades.map(function(h) { return fade(h); });

            return palette;
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

                        const value = dataset.data[index];
                        const total = dataset.data.reduce((a, b) => a + b, 0);
                        const pctNum = total > 0 ? (value / total) * 100 : 0;

                        if (pctNum >= 3) {
                            const percentage = pctNum.toFixed(1) + '%';
                            const isDark = document.body.getAttribute('data-theme') === 'dark' ||
                                window.matchMedia('(prefers-color-scheme: dark)').matches;
                            ctx.save();
                            ctx.font = 'bold 10px Inter, sans-serif';
                            ctx.fillStyle = isDark ? '#ffffff' : '#1e293b';
                            ctx.shadowColor = isDark ? 'rgba(0, 0, 0, 0.4)' : 'rgba(255, 255, 255, 0.4)';
                            ctx.shadowBlur = isDark ? 3 : 0;
                            ctx.textAlign = 'center';
                            ctx.textBaseline = 'middle';
                            ctx.fillText(percentage, x, y);
                            ctx.shadowBlur = 0;
                            ctx.shadowColor = 'transparent';
                            ctx.restore();
                        }
                    });
                });
            }
        },


        // Initialize a Doughnut Chart
        initDoughnut: function (ctx) {
            const colors = this.getColors();
            return new Chart(ctx, {
                type: 'doughnut',
                data: {
                    labels: [],
                    datasets: [{
                        data: [],
                        backgroundColor: [],
                        borderColor: [],
                        borderWidth: 2,
                        borderRadius: 6,
                        hoverOffset: 10,
                        hoverBorderWidth: 2,
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
            chart.data.datasets[0].borderWidth = 2;
            chart.data.datasets[0].borderRadius = 6;
            chart.data.datasets[0].hoverOffset = 10;
            chart.data.datasets[0].hoverBorderWidth = 2;

            // Semi-transparent palette matching stat-card icon colors
            const fills = colors.doughnutFills;
            const strokes = colors.doughnutStrokes;

            let bgColors, borderColors;
            if (colorMap) {
                bgColors = labels.map(l => colorMap[l] || colors.slate);
                borderColors = labels.map(l => colorMap[l] || colors.slate);
            } else {
                bgColors = labels.map((_, i) => fills[i % fills.length]);
                borderColors = labels.map((_, i) => strokes[i % strokes.length]);
            }

            chart.data.datasets[0].backgroundColor = bgColors;
            chart.data.datasets[0].borderColor = borderColors;

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

                // Dim non-active segments
                function dimColor(c, alpha) {
                    if (!c) return c;
                    if (c.startsWith('#')) {
                        var r = parseInt(c.slice(1, 3), 16);
                        var g = parseInt(c.slice(3, 5), 16);
                        var b = parseInt(c.slice(5, 7), 16);
                        return 'rgba(' + r + ',' + g + ',' + b + ',' + alpha + ')';
                    }
                    return c.replace(/[\d.]+\)$/, alpha + ')');
                }

                if (idx === null) {
                    chart.setActiveElements([]);
                    chart.data.datasets[0].backgroundColor = bgColors;
                    chart.data.datasets[0].borderColor = borderColors;
                } else {
                    chart.setActiveElements([{ datasetIndex: 0, index: idx }]);
                    chart.data.datasets[0].backgroundColor = bgColors.map(function (c, i) {
                        return i === idx ? c : dimColor(c, 0.06);
                    });
                    chart.data.datasets[0].borderColor = borderColors.map(function (c, i) {
                        return i === idx ? c : dimColor(c, 0.25);
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
                    var fillColor = bgColors[index];
                    var strokeColor = borderColors[index];
                    var amount = item[keys.amount] || 0;
                    var formattedAmount = amount.toLocaleString('en-IN');

                    var div = document.createElement('div');
                    div.className = 'leg-item';
                    div.dataset.idx = index;
                    div.innerHTML = '<span class="leg-dot" style="background:' + strokeColor + '"></span>' +
                        '<span class="leg-name">' + item[keys.label] + '</span>' +
                        '<span class="leg-pct">' + pctStr + '</span>' +
                        '<span class="leg-val">&nbsp;' + formattedAmount + '</span>';

                    var track = document.createElement('div');
                    track.className = 'bar-track';
                    var fill = document.createElement('div');
                    fill.className = 'bar-fill';
                    fill.style.background = strokeColor;
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

            // Semi-transparent fills matching stat-card icon style (~0.45 alpha)
            const gradient = ctx.createLinearGradient(0, 0, 0, 400);
            gradient.addColorStop(0, colors.doughnutFills[0]);
            gradient.addColorStop(1, 'rgba(96, 165, 250, 0.0)');

            const previousBg = colors.doughnutFills[11];

            const blueLight = colors.doughnutStrokes[0];
            const greenLight = colors.doughnutStrokes[2];

            return new Chart(ctx, {
                type: 'line',
                data: {
                    labels: [],
                    datasets: [{
                        label: 'Present',
                        data: [],
                        borderColor: blueLight,
                        backgroundColor: gradient,
                        borderWidth: 2,
                        pointBackgroundColor: colors.tooltipBg,
                        pointBorderColor: blueLight,
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
                        backgroundColor: previousBg,
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
                        borderColor: greenLight,
                        backgroundColor: 'transparent',
                        borderWidth: 2,
                        borderDash: [4, 4],
                        pointBackgroundColor: colors.tooltipBg,
                        pointBorderColor: greenLight,
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
                            borderColor: blueLight,
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
                                color: greenLight,
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

            const colors = this.getColors();

            // Semi-transparent fills matching stat-card icon style
            const ctx = chart.canvas.getContext('2d');
            const gradient = ctx.createLinearGradient(0, 0, 0, 400);
            gradient.addColorStop(0, colors.doughnutFills[0]);
            gradient.addColorStop(1, 'rgba(96, 165, 250, 0.0)');

            const previousBg = colors.doughnutFills[11];

            chart.options.scales.y.grid.color = colors.grid;
            chart.options.plugins.tooltip.backgroundColor = colors.tooltipBg;
            chart.options.plugins.tooltip.titleColor = colors.textPrimary;
            chart.options.plugins.tooltip.bodyColor = colors.textSecondary;
            chart.options.plugins.tooltip.borderColor = colors.grid;

            chart.data.datasets[0].backgroundColor = gradient;
            chart.data.datasets[1].backgroundColor = previousBg;

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

                // Semi-transparent fills matching stat-card icon colors
                const stockInGradient = ctx.createLinearGradient(0, 0, 0, 400);
                stockInGradient.addColorStop(0, colors.doughnutFills[2]); // green light at 0.45
                stockInGradient.addColorStop(1, 'rgba(52, 211, 153, 0.0)');

                const stockOutGradient = ctx.createLinearGradient(0, 0, 0, 400);
                stockOutGradient.addColorStop(0, colors.doughnutFills[3]); // red light at 0.45
                stockOutGradient.addColorStop(1, 'rgba(248, 113, 113, 0.0)');

                chart.data.datasets[0].label = 'Stock In';
                chart.data.datasets[0].data = currentData;
                chart.data.datasets[0].borderColor = colors.doughnutStrokes[2]; // green light
                chart.data.datasets[0].backgroundColor = stockInGradient;

                chart.data.datasets[1].label = 'Stock Out';
                chart.data.datasets[1].data = previousData;
                chart.data.datasets[1].borderColor = colors.doughnutStrokes[3]; // red light
                chart.data.datasets[1].pointBorderColor = colors.doughnutStrokes[3];
                chart.data.datasets[1].backgroundColor = stockOutGradient;
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
            textSecondary: '#94a3b8',
            // Light shades for strokes (matching stat-card icon foreground colors)
            strokes: [
                '#60a5fa', '#a78bfa', '#34d399', '#f87171',
                '#22d3ee', '#f472b6', '#fbbf24',
                '#818cf8', '#2dd4bf', '#fb923c', '#a3e635',
                '#94a3b8',
            ],
            // Semi-transparent fills (~0.45 alpha) for readable chart segments
            fills: [
                'rgba(96, 165, 250, 0.45)', 'rgba(167, 139, 250, 0.45)',
                'rgba(52, 211, 153, 0.45)', 'rgba(248, 113, 113, 0.45)',
                'rgba(34, 211, 238, 0.45)', 'rgba(244, 114, 182, 0.45)',
                'rgba(251, 191, 36, 0.45)',
                'rgba(129, 140, 248, 0.45)', 'rgba(45, 212, 191, 0.45)',
                'rgba(251, 146, 96, 0.45)', 'rgba(163, 230, 53, 0.45)',
                'rgba(148, 163, 184, 0.45)',
            ],
        }
    };

    // Expose to window
    window.ModernCharts = ModernCharts;

})(window);
