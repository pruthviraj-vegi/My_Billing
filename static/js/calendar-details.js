(function () {
  "use strict";

  function formatDateToISO(d) {
    if (!d) return "";
    var y = d.getFullYear();
    var m = String(d.getMonth() + 1).padStart(2, '0');
    var day = String(d.getDate()).padStart(2, '0');
    return y + '-' + m + '-' + day;
  }

  function formatDateToDMY(val) {
    if (!val) return "";
    if (typeof val === 'string') {
      val = val.trim();
      var isoMatch = val.match(/^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})/);
      if (isoMatch) {
        var y = isoMatch[1];
        var m = String(parseInt(isoMatch[2], 10)).padStart(2, '0');
        var d = String(parseInt(isoMatch[3], 10)).padStart(2, '0');
        return d + '-' + m + '-' + y;
      }
      var dmyMatch = val.match(/^(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})/);
      if (dmyMatch) {
        var d2 = String(parseInt(dmyMatch[1], 10)).padStart(2, '0');
        var m2 = String(parseInt(dmyMatch[2], 10)).padStart(2, '0');
        var y2 = dmyMatch[3];
        return d2 + '-' + m2 + '-' + y2;
      }
    }
    var dObj = val instanceof Date ? val : parseISODate(val);
    if (!isNaN(dObj.getTime())) {
      var year = dObj.getFullYear();
      var month = String(dObj.getMonth() + 1).padStart(2, '0');
      var dayStr = String(dObj.getDate()).padStart(2, '0');
      return dayStr + '-' + month + '-' + year;
    }
    return String(val);
  }

  function normalizeDateStr(str) {
    if (!str) return null;
    str = String(str).trim();
    if (!str) return null;

    // ISO format: YYYY-MM-DD or YYYY/MM/DD or YYYY.MM.DD
    var isoMatch = str.match(/^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})/);
    if (isoMatch) {
      var y = parseInt(isoMatch[1], 10);
      var m = String(parseInt(isoMatch[2], 10)).padStart(2, '0');
      var d = String(parseInt(isoMatch[3], 10)).padStart(2, '0');
      return y + '-' + m + '-' + d;
    }

    // DD-MM-YYYY or DD/MM/YYYY or DD.MM.YYYY
    var dmyMatch = str.match(/^(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})/);
    if (dmyMatch) {
      var d = String(parseInt(dmyMatch[1], 10)).padStart(2, '0');
      var m = String(parseInt(dmyMatch[2], 10)).padStart(2, '0');
      var y = parseInt(dmyMatch[3], 10);
      return y + '-' + m + '-' + d;
    }

    // Fallback: Date parse
    var parsed = new Date(str);
    if (!isNaN(parsed.getTime())) {
      return formatDateToISO(parsed);
    }
    return null;
  }

  function parseISODate(isoStr) {
    if (!isoStr) return new Date();
    if (isoStr instanceof Date) return isoStr;
    var norm = normalizeDateStr(isoStr);
    if (norm) {
      var parts = norm.split('-').map(function (n) { return parseInt(n, 10); });
      if (parts.length === 3 && !isNaN(parts[0]) && !isNaN(parts[1]) && !isNaN(parts[2])) {
        return new Date(parts[0], parts[1] - 1, parts[2]);
      }
    }
    var d = new Date(isoStr);
    return isNaN(d.getTime()) ? new Date() : d;
  }

  function setInputValue(input, isoDate) {
    if (!input || !isoDate) return;
    var dmy = formatDateToDMY(isoDate);
    input.value = dmy;
    input.setAttribute("data-iso-date", isoDate);
    if (input._animatedDatePickerInstance) {
      var d = parseISODate(isoDate);
      input._animatedDatePickerInstance.selectedDate = d;
      input._animatedDatePickerInstance.viewYear = d.getFullYear();
      input._animatedDatePickerInstance.viewMonth = d.getMonth();
    }
  }

  var urlParams = new URLSearchParams(window.location.search);
  var rawStart = urlParams.get("start");
  var rawEnd = urlParams.get("end");

  var startDate = normalizeDateStr(rawStart);
  var endDate = normalizeDateStr(rawEnd);

  var now = new Date();
  if (!startDate && !endDate) {
    var firstDay = new Date(now.getFullYear(), now.getMonth(), 1);
    var lastDay = new Date(now.getFullYear(), now.getMonth() + 1, 0);
    startDate = formatDateToISO(firstDay);
    endDate = formatDateToISO(lastDay);
  } else if (!startDate) {
    startDate = endDate;
  } else if (!endDate) {
    endDate = startDate;
  }

  if (startDate > endDate) {
    var tmpDate = startDate;
    startDate = endDate;
    endDate = tmpDate;
  }

  /* ── DOM refs ── */
  var rangeLabel = document.getElementById("detailsRangeLabel");
  var dayBadge = document.getElementById("detailsDayBadge");
  var loadEl = document.getElementById("detailsLoading");

  var fromInput = document.getElementById("detailsFromDate");
  var toInput = document.getElementById("detailsToDate");
  var applyBtn = document.getElementById("detailsApplyRangeBtn");
  var presetBtns = document.querySelectorAll(".range-preset-btn");

  setInputValue(fromInput, startDate);
  setInputValue(toInput, endDate);

  var activeCharts = [];

  function destroyAllCharts() {
    for (var i = 0; i < activeCharts.length; i++) {
      try { activeCharts[i].destroy(); } catch (e) { /* ignore */ }
    }
    activeCharts = [];
  }

  /* ── Fetch ── */
  function fetchData(cb) {
    if (loadEl) loadEl.style.display = "flex";
    fetch("/calendar/details-api/?start=" + encodeURIComponent(startDate) + "&end=" + encodeURIComponent(endDate))
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (loadEl) loadEl.style.display = "none";
        cb(data);
      })
      .catch(function () {
        if (loadEl) loadEl.style.display = "none";
      });
  }

  function updateSelectedRange(s, e) {
    s = normalizeDateStr(s) || s;
    e = normalizeDateStr(e) || e;
    if (s > e) {
      var tmp = s;
      s = e;
      e = tmp;
    }
    startDate = s;
    endDate = e;

    setInputValue(fromInput, s);
    setInputValue(toInput, e);

    // Update URL without page reload
    var sDMY = formatDateToDMY(s);
    var eDMY = formatDateToDMY(e);
    var newUrl = window.location.pathname + "?start=" + encodeURIComponent(sDMY) + "&end=" + encodeURIComponent(eDMY);
    window.history.replaceState({ path: newUrl }, "", newUrl);

    var startDt = parseISODate(s);
    var endDt = parseISODate(e);
    var dayDiff = Math.round((endDt.getTime() - startDt.getTime()) / 86400000) + 1;

    if (rangeLabel) {
      rangeLabel.textContent =
        startDt.toLocaleDateString("en-IN", { weekday: "short", day: "numeric", month: "short", year: "numeric" }) +
        "  —  " +
        endDt.toLocaleDateString("en-IN", { weekday: "short", day: "numeric", month: "short", year: "numeric" });
    }
    if (dayBadge) {
      dayBadge.textContent = dayDiff + " day" + (dayDiff !== 1 ? "s" : "");
      dayBadge.style.display = "inline";
    }

    fetchData(function (data) {
      if (!data || !data.success) return;
      destroyAllCharts();
      populateKPIs(data.stats);
      buildPaymentDoughnut(data.payment_status_breakdown);
      buildCategoryDoughnut(data.categories);
      buildDailyTrend(data.daily_trend);
      buildCustomersPie(data.top_customers);
    });
  }

  if (applyBtn) {
    applyBtn.addEventListener("click", function () {
      var fVal = fromInput ? (fromInput.getAttribute("data-iso-date") || fromInput.value) : "";
      var tVal = toInput ? (toInput.getAttribute("data-iso-date") || toInput.value) : "";
      if (!fVal || !tVal) return;
      var s = normalizeDateStr(fVal);
      var e = normalizeDateStr(tVal);
      if (!s || !e) return;
      if (s > e) {
        var tmp = s;
        s = e;
        e = tmp;
      }
      updateSelectedRange(s, e);
    });
  }

  presetBtns.forEach(function (btn) {
    var clickHandler = typeof debounce === 'function'
      ? debounce(function () {
          var preset = this.dataset.preset;
          var today = new Date();
          var s, e;
          if (preset === "today") {
            s = formatDateToISO(today);
            e = formatDateToISO(today);
          } else if (preset === "this_month") {
            s = formatDateToISO(new Date(today.getFullYear(), today.getMonth(), 1));
            e = formatDateToISO(new Date(today.getFullYear(), today.getMonth() + 1, 0));
          } else if (preset === "last_30") {
            var prior30 = new Date();
            prior30.setDate(today.getDate() - 29);
            s = formatDateToISO(prior30);
            e = formatDateToISO(today);
          }
          updateSelectedRange(s, e);
        }, 200)
      : function () {
          var preset = this.dataset.preset;
          var today = new Date();
          var s, e;
          if (preset === "today") {
            s = formatDateToISO(today);
            e = formatDateToISO(today);
          } else if (preset === "this_month") {
            s = formatDateToISO(new Date(today.getFullYear(), today.getMonth(), 1));
            e = formatDateToISO(new Date(today.getFullYear(), today.getMonth() + 1, 0));
          } else if (preset === "last_30") {
            var prior30 = new Date();
            prior30.setDate(today.getDate() - 29);
            s = formatDateToISO(prior30);
            e = formatDateToISO(today);
          }
          updateSelectedRange(s, e);
        };

    btn.addEventListener("click", clickHandler);
  });

  /* ── KPI cards ── */
  function populateKPIs(stats) {
    if (typeof updateAllCounters === "function") {
      updateAllCounters({
        kpiTotalInvoices: stats.total_invoices,
        kpiTotalAmount: stats.total_amount,
        kpiNetAmount: stats.net_amount,
        kpiGrossProfit: stats.gross_profit,
        kpiNetProfit: stats.net_profit,
        kpiMargin: stats.margin,
        kpiAvgInvoiceAmount: stats.avg_invoice_amount,
        kpiAvgInvoicesPerDay: stats.avg_invoices_per_day
      });
    } else {
      var setText = function (id, text) {
        var el = document.getElementById(id);
        if (el) el.textContent = text;
      };
      setText("kpiTotalInvoices", stats.total_invoices);
      setText("kpiTotalAmount", formatNumber(stats.total_amount));
      setText("kpiNetAmount", formatNumber(stats.net_amount));
      setText("kpiGrossProfit", formatNumber(stats.gross_profit));
      setText("kpiNetProfit", formatNumber(stats.net_profit));
      setText("kpiMargin", stats.margin + "%");
      setText("kpiAvgInvoiceAmount", formatNumber(stats.avg_invoice_amount));
      setText("kpiAvgInvoicesPerDay", stats.avg_invoices_per_day);
    }
  }

  /* ── Payment doughnut ── */
  function buildPaymentDoughnut(breakdown) {
    var canvas = document.getElementById("paymentDoughnutChart");
    var legendId = "paymentDoughnutLegend";
    if (!canvas) return;

    if (!breakdown || breakdown.length === 0) {
      var legEl = document.getElementById(legendId);
      if (legEl) legEl.innerHTML = '<div class="p-3 text-muted text-center" style="font-size:12px;">No payment breakdown data</div>';
      return;
    }

    var chart = ModernCharts.initDoughnut(canvas);
    activeCharts.push(chart);

    var colorMap = {
      "Paid": { fill: "rgba(52, 211, 153, 0.45)", stroke: "#34d399" },
      "Unpaid": { fill: "rgba(248, 113, 113, 0.45)", stroke: "#f87171" },
      "Partially Paid": { fill: "rgba(251, 191, 36, 0.45)", stroke: "#fbbf24" }
    };

    ModernCharts.updateDoughnut(
      chart,
      legendId,
      breakdown,
      { label: "status", count: "count", amount: "amount", percentage: "percentage" },
      colorMap
    );
  }

  /* ── Category doughnut ── */
  function buildCategoryDoughnut(categories) {
    var canvas = document.getElementById("categoryDoughnutChart");
    var legendId = "categoryDoughnutLegend";
    if (!canvas) return;

    if (!categories || categories.length === 0) {
      var legEl = document.getElementById(legendId);
      if (legEl) legEl.innerHTML = '<div class="p-3 text-muted text-center" style="font-size:12px;">No category data</div>';
      return;
    }

    var chart = ModernCharts.initDoughnut(canvas);
    activeCharts.push(chart);

    ModernCharts.updateDoughnut(
      chart,
      legendId,
      categories,
      { label: "name", count: "count", amount: "amount", percentage: "percentage" }
    );
  }

  /* ── Daily trend ── */
  function buildDailyTrend(trend) {
    var canvas = document.getElementById("dailyTrendChart");
    if (!canvas) return;
    if (!trend || trend.length === 0) {
      var parent = canvas.parentNode;
      if (parent) parent.innerHTML = '<div class="d-flex align-items-center justify-content-center h-100 text-muted" style="font-size:12px;">No daily trend data</div>';
      return;
    }

    var colors = ModernCharts.getColors();
    var labels = trend.map(function (t) {
      var d = new Date(t.date + "T00:00:00");
      return d.toLocaleDateString("en-IN", { day: "numeric", month: "short" });
    });

    var chart = new Chart(canvas, {
      type: "bar",
      data: {
        labels: labels,
        datasets: [
          {
            label: "Revenue",
            data: trend.map(function (t) { return t.amount; }),
            backgroundColor: colors.doughnutFills[0],
            borderColor: colors.doughnutStrokes[0],
            borderWidth: 1.5,
            borderRadius: 4,
            order: 2,
          },
          {
            label: "Profit",
            data: trend.map(function (t) { return t.profit; }),
            type: "line",
            borderColor: colors.green,
            backgroundColor: colors.doughnutFills[2] || "rgba(16, 185, 129, 0.15)",
            borderWidth: 2,
            pointRadius: 3,
            pointBackgroundColor: colors.green,
            tension: 0.3,
            fill: true,
            order: 1,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { intersect: false, mode: "index" },
        plugins: {
          legend: { labels: { color: colors.textSecondary, usePointStyle: true, padding: 16, font: { size: 11 } } },
        },
        scales: {
          x: { ticks: { color: colors.textSecondary, font: { size: 10 }, maxRotation: 45 }, grid: { display: false } },
          y: { ticks: { color: colors.textSecondary, font: { size: 10 }, callback: function (v) { return formatNumber(v); } }, grid: { color: colors.grid } },
        },
      },
    });
    activeCharts.push(chart);
  }

  /* ── Top Customers Pie ── */
  function buildCustomersPie(customers) {
    var canvas = document.getElementById("customersDoughnutChart");
    var legendId = "customersDoughnutLegend";
    if (!canvas) return;

    if (!customers || customers.length === 0) {
      var legEl = document.getElementById(legendId);
      if (legEl) legEl.innerHTML = '<div class="p-3 text-muted text-center" style="font-size:12px;">No customer data</div>';
      return;
    }

    var top8 = customers.slice(0, 8);
    var othersAmt = 0;
    var othersCount = 0;
    for (var i = 8; i < customers.length; i++) {
      othersAmt += customers[i].amount;
      othersCount += (customers[i].count || 1);
    }

    var items = top8.map(function (c) {
      return { name: c.name, amount: c.amount, count: c.count || 1 };
    });

    if (othersAmt > 0) {
      items.push({ name: "Others", amount: othersAmt, count: othersCount });
    }

    var chart = ModernCharts.initDoughnut(canvas);
    activeCharts.push(chart);

    ModernCharts.updateDoughnut(
      chart,
      legendId,
      items,
      { label: "name", count: "count", amount: "amount" }
    );
  }

  /* ── Boot ── */
  updateSelectedRange(startDate, endDate);
})();
