/**
 * Interactive Calendar Page Logic
 * Renders calendar grid, computes KPI metrics, handles dropdown month/year jumping,
 * filtering by status, in-month text search, and detailed sidebar inspection.
 */

(function () {
  const ssrEl = document.getElementById('calendar-data');
  if (!ssrEl) return;

  /** @type {Record<string, {amount: number, completed: number, events: Array<{invoice_number: string, customer_name: string, amount: number, status: string, status_display: string, url: string}>}>} */
  let calendarData;
  try {
    calendarData = JSON.parse(ssrEl.textContent);
  } catch (e) {
    console.error('Calendar: failed to parse SSR data', e);
    return;
  }

  const monthKpiEl = document.getElementById('month-kpi');
  let monthKpi = null;
  if (monthKpiEl) {
    try {
      monthKpi = JSON.parse(monthKpiEl.textContent);
    } catch (e) {
      console.error('Calendar: failed to parse month KPI data', e);
    }
  }

  const now = new Date();
  const todayStr = now.getFullYear() + '-'
    + String(now.getMonth() + 1).padStart(2, '0') + '-'
    + String(now.getDate()).padStart(2, '0');

  // Controls
  const monthSelect = document.getElementById('monthSelect');
  const yearSelect = document.getElementById('yearSelect');
  const filterBtns = document.querySelectorAll('.cal-filter-btn');
  const searchInput = document.getElementById('calSearchInput');
  const searchClear = document.getElementById('calSearchClear');

  const params = new URLSearchParams(window.location.search);
  const yearNum = parseInt(params.get('year'), 10) || (yearSelect ? parseInt(yearSelect.value, 10) : 0) || now.getFullYear();
  const month1 = parseInt(params.get('month'), 10) || (monthSelect ? parseInt(monthSelect.value, 10) : 0) || (now.getMonth() + 1);

  // ── DOM References ──
  const grid = document.getElementById('calGrid');
  const pageHeaderAnalyticsBtn = document.getElementById('pageHeaderAnalyticsBtn');
  const analyticsBtnLabel = document.getElementById('analyticsBtnLabel');

  // Modal elements
  const dateInvoicesModalEl = document.getElementById('dateInvoicesModal');
  const modalLabel = document.getElementById('dateInvoicesModalLabel');
  const modalSubTitle = document.getElementById('modalSubTitle');
  const modalMetricPercentage = document.getElementById('modalMetricPercentage');
  const modalSalesAmount = document.getElementById('modalSalesAmount');
  const modalMetricBar = document.getElementById('modalMetricBar');
  const modalEventsCountBadge = document.getElementById('modalEventsCountBadge');
  const modalEventsList = document.getElementById('modalEventsList');
  const modalAnalyticsLink = document.getElementById('modalAnalyticsLink');

  // KPI elements
  const kpiTotalBilling = document.getElementById('kpiTotalBilling');
  const kpiTotalInvoices = document.getElementById('kpiTotalInvoices');
  const kpiPaidAmount = document.getElementById('kpiPaidAmount');
  const kpiPendingAmount = document.getElementById('kpiPendingAmount');

  // Active Filter State
  let activeFilter = 'ALL';
  let activeSearchQuery = '';
  let selectedKey = null;

  // Range Selection State
  let rangeStart = null;
  let rangeEnd = null;

  // ── Helpers ──
  const dateKey = (y, m1, d) =>
    y + '-' + String(m1).padStart(2, '0') + '-' + String(d).padStart(2, '0');

  function daysInMonth(y, m1) {
    return new Date(y, m1, 0).getDate();
  }

  function firstDayOfWeek(y, m1) {
    return new Date(y, m1 - 1, 1).getDay();
  }

  function statusBadgeClass(status) {
    if (status === 'PAID') return 'bg-success';
    if (status === 'UNPAID') return 'bg-danger';
    if (status === 'PARTIALLY_PAID') return 'bg-warning text-dark';
    return 'bg-secondary';
  }

  function statusBorderClass(status) {
    if (status === 'PAID') return 'event-success';
    if (status === 'UNPAID') return 'event-danger';
    if (status === 'PARTIALLY_PAID') return 'event-warning';
    return '';
  }

  // ── Month & Year Dropdown Listeners ──
  if (monthSelect) {
    monthSelect.addEventListener('change', function () {
      navigateTo(yearSelect ? yearSelect.value : yearNum, this.value);
    });
  }

  if (yearSelect) {
    yearSelect.addEventListener('change', function () {
      navigateTo(this.value, monthSelect ? monthSelect.value : month1);
    });
  }

  function navigateTo(year, month) {
    window.location.href = '?year=' + year + '&month=' + month;
  }

  // ── Filter Buttons ──
  filterBtns.forEach(function (btn) {
    btn.addEventListener('click', function () {
      filterBtns.forEach(function (b) { b.classList.remove('active'); });
      this.classList.add('active');
      activeFilter = this.dataset.filter || 'ALL';
      applyFilters();
    });
  });

  // ── Search Input ──
  if (searchInput) {
    searchInput.addEventListener('input', function () {
      activeSearchQuery = this.value.trim().toLowerCase();
      if (searchClear) {
        searchClear.style.display = activeSearchQuery ? 'block' : 'none';
      }
      applyFilters();
    });
  }

  if (searchClear) {
    searchClear.addEventListener('click', function () {
      if (searchInput) searchInput.value = '';
      activeSearchQuery = '';
      this.style.display = 'none';
      applyFilters();
    });
  }

  // ── Calculate Top KPI Bar Metrics ──
  function calculateKpis() {
    if (activeFilter === 'ALL' && !activeSearchQuery && monthKpi) {
      const grandGrossBilling = Math.max(0, monthKpi.total_billing || 0);
      const grandTotalInvoices = Math.max(0, monthKpi.total_invoices || 0);
      const grandPaidAmount = Math.max(0, monthKpi.paid_amount || 0);
      const grandPendingAmount = Math.max(0, monthKpi.pending_amount || 0);

      if (typeof updateAllCounters === "function") {
        updateAllCounters({
          kpiTotalBilling: grandGrossBilling,
          kpiTotalInvoices: grandTotalInvoices,
          kpiPaidAmount: grandPaidAmount,
          kpiPendingAmount: grandPendingAmount
        });
      } else {
        if (kpiTotalBilling) kpiTotalBilling.textContent = formatNumber(grandGrossBilling);
        if (kpiTotalInvoices) kpiTotalInvoices.textContent = grandTotalInvoices;
        if (kpiPaidAmount) kpiPaidAmount.textContent = formatNumber(grandPaidAmount);
        if (kpiPendingAmount) kpiPendingAmount.textContent = formatNumber(grandPendingAmount);
      }
      return;
    }

    let grandGrossBilling = 0;
    let grandTotalInvoices = 0;
    let grandPaidAmount = 0;
    let grandPendingAmount = 0;

    const monthPrefix = dateKey(yearNum, month1, 1).substring(0, 7);

    Object.entries(calendarData).forEach(function ([dateStr, dayData]) {
      if (!dateStr.startsWith(monthPrefix)) return;
      if (!dayData || !dayData.events) return;
      dayData.events.forEach(function (ev) {
        let statusMatch = true;
        if (activeFilter === 'PAID') statusMatch = (ev.status === 'PAID');
        if (activeFilter === 'PENDING') statusMatch = (ev.status !== 'PAID');

        let searchMatch = true;
        if (activeSearchQuery !== '') {
          const invNum = (ev.invoice_number || '').toLowerCase();
          const custName = (ev.customer_name || '').toLowerCase();
          searchMatch = invNum.includes(activeSearchQuery) || custName.includes(activeSearchQuery);
        }

        if (!statusMatch || !searchMatch) return;

        const net = ev.amount || 0;
        const paid = ev.paid_amount !== undefined ? ev.paid_amount : (ev.status === 'PAID' ? net : 0);
        const pending = Math.max(0, net - paid);

        grandGrossBilling += net;
        grandTotalInvoices += 1;
        grandPaidAmount += paid;
        grandPendingAmount += pending;
      });
    });

    grandGrossBilling = Math.max(0, grandGrossBilling);
    grandTotalInvoices = Math.max(0, grandTotalInvoices);
    grandPaidAmount = Math.max(0, grandPaidAmount);
    grandPendingAmount = Math.max(0, grandPendingAmount);

    if (typeof updateAllCounters === "function") {
      updateAllCounters({
        kpiTotalBilling: grandGrossBilling,
        kpiTotalInvoices: grandTotalInvoices,
        kpiPaidAmount: grandPaidAmount,
        kpiPendingAmount: grandPendingAmount
      });
    } else {
      if (kpiTotalBilling) kpiTotalBilling.textContent = formatNumber(grandGrossBilling);
      if (kpiTotalInvoices) kpiTotalInvoices.textContent = grandTotalInvoices;
      if (kpiPaidAmount) kpiPaidAmount.textContent = formatNumber(grandPaidAmount);
      if (kpiPendingAmount) kpiPendingAmount.textContent = formatNumber(grandPendingAmount);
    }
  }

  // ── Build Calendar Grid ──
  function buildGrid() {
    grid.innerHTML = '';
    const fragment = document.createDocumentFragment();
    const totalDays = daysInMonth(yearNum, month1);
    const startDay = firstDayOfWeek(yearNum, month1);
    const prevMonth1 = month1 === 1 ? 12 : month1 - 1;
    const prevYear = month1 === 1 ? yearNum - 1 : yearNum;
    const prevTotal = daysInMonth(prevYear, prevMonth1);

    for (let i = startDay - 1; i >= 0; i--) {
      const dayNum = prevTotal - i;
      const key = dateKey(prevYear, prevMonth1, dayNum);
      fragment.appendChild(makeCell(dayNum, true, key));
    }

    for (let d = 1; d <= totalDays; d++) {
      const key = dateKey(yearNum, month1, d);
      fragment.appendChild(makeCell(d, false, key));
    }

    const filled = startDay + totalDays;
    const rem = filled <= 35 ? 35 - filled : 42 - filled;
    const nextMonth1 = month1 === 12 ? 1 : month1 + 1;
    const nextYear = month1 === 12 ? yearNum + 1 : yearNum;
    for (let d = 1; d <= rem; d++) {
      const key = dateKey(nextYear, nextMonth1, d);
      fragment.appendChild(makeCell(d, true, key));
    }

    grid.appendChild(fragment);
    calculateKpis();
  }

  function makeCell(day, isOther, key) {
    const cell = document.createElement('div');
    cell.className = 'cal-cell';
    if (isOther) cell.classList.add('other-month');

    if (key) {
      cell.dataset.date = key;
      if (key === todayStr) cell.classList.add('today');

      const dayData = calendarData[key];
      if (dayData && dayData.events.length > 0) {
        const totalCount = dayData.events.length;
        const paidEvents = dayData.events.filter(e => e.status === 'PAID');
        const pendingEvents = dayData.events.filter(e => e.status !== 'PAID');
        const totalAmount = dayData.amount || 0;

        let dotsHtml = '';
        if (paidEvents.length > 0) {
          dotsHtml += '<span class="status-dot dot-paid" title="' + paidEvents.length + ' Paid"></span>';
        }
        if (pendingEvents.length > 0) {
          dotsHtml += '<span class="status-dot dot-pending" title="' + pendingEvents.length + ' Pending"></span>';
        }

        cell.innerHTML =
          '<div class="cell-top-row">' +
            '<span class="cell-date">' + day + '</span>' +
            '<span class="cell-dot-count">' + paidEvents.length + '/' + totalCount + '</span>' +
          '</div>' +
          '<div class="cell-status-indicators">' + dotsHtml + '</div>' +
          '<span class="cell-sales">' + formatNumber(totalAmount) + '</span>';

        cell.addEventListener('click', function () { selectSingleDate(cell, key); });
      } else {
        cell.innerHTML =
          '<div class="cell-top-row">' +
            '<span class="cell-date">' + day + '</span>' +
          '</div>';
        cell.addEventListener('click', function () { selectSingleDate(cell, key); });
      }
    } else {
      cell.innerHTML = '<span class="cell-date">' + day + '</span>';
    }
    return cell;
  }

  // ── Apply Filters (Status & Search) ──
  function applyFilters() {
    const cells = grid.querySelectorAll('.cal-cell[data-date]');
    cells.forEach(function (cell) {
      const key = cell.dataset.date;
      const dayData = calendarData[key];

      if (!dayData || !dayData.events.length) {
        if (activeFilter !== 'ALL' || activeSearchQuery !== '') {
          cell.classList.add('filtered-out');
        } else {
          cell.classList.remove('filtered-out');
        }
        return;
      }

      let matches = dayData.events.filter(function (ev) {
        let statusMatch = true;
        if (activeFilter === 'PAID') statusMatch = (ev.status === 'PAID');
        if (activeFilter === 'PENDING') statusMatch = (ev.status !== 'PAID');

        let searchMatch = true;
        if (activeSearchQuery !== '') {
          const invNum = (ev.invoice_number || '').toLowerCase();
          const custName = (ev.customer_name || '').toLowerCase();
          searchMatch = invNum.includes(activeSearchQuery) || custName.includes(activeSearchQuery);
        }

        return statusMatch && searchMatch;
      });

      if (matches.length > 0) {
        cell.classList.remove('filtered-out');
      } else {
        cell.classList.add('filtered-out');
      }
    });

    if (selectedKey && dateInvoicesModalEl && dateInvoicesModalEl.classList.contains('show')) {
      openDateInvoicesModal(selectedKey);
    }
  }

  // ── Date Invoices Modal Handling ──
  function selectSingleDate(cell, key) {
    selectedKey = key;
    grid.querySelectorAll('.cal-cell.selected').forEach(function (c) { c.classList.remove('selected'); });
    cell.classList.add('selected');
    openDateInvoicesModal(key);
  }

  function openDateInvoicesModal(key) {
    const parts = key.split('-');
    const dateObj = new Date(parseInt(parts[0], 10), parseInt(parts[1], 10) - 1, parseInt(parts[2], 10));
    const formattedDate = dateObj.toLocaleDateString('en-IN', {
      weekday: 'short', day: 'numeric', month: 'short', year: 'numeric'
    });

    if (modalLabel) modalLabel.textContent = formattedDate;
    if (modalSubTitle) modalSubTitle.textContent = 'Date Breakdown & Invoices';

    if (modalAnalyticsLink) {
      modalAnalyticsLink.href = '/calendar/details/?start=' + key + '&end=' + key;
    }

    const dayData = calendarData[key];
    const events = (dayData && dayData.events) ? dayData.events : [];
    let dayTotalAmount = dayData ? (dayData.amount || 0) : 0;
    let dayCompleted = dayData ? (dayData.completed || 0) : 0;

    let filtered = events.filter(function (ev) {
      let statusMatch = true;
      if (activeFilter === 'PAID') statusMatch = (ev.status === 'PAID');
      if (activeFilter === 'PENDING') statusMatch = (ev.status !== 'PAID');
      let searchMatch = true;
      if (activeSearchQuery !== '') {
        searchMatch = (ev.invoice_number || '').toLowerCase().includes(activeSearchQuery) ||
                      (ev.customer_name || '').toLowerCase().includes(activeSearchQuery);
      }
      return statusMatch && searchMatch;
    });

    if (modalSalesAmount) {
      modalSalesAmount.textContent = formatNumber(dayCompleted) + ' / ' + formatNumber(dayTotalAmount);
    }
    const pct = dayTotalAmount > 0 ? (dayCompleted / dayTotalAmount) * 100 : 0;
    if (modalMetricBar) modalMetricBar.style.width = pct.toFixed(1) + '%';
    if (modalMetricPercentage) modalMetricPercentage.textContent = Math.round(pct) + '% Paid';
    if (modalEventsCountBadge) modalEventsCountBadge.textContent = filtered.length;

    renderModalEvents(filtered);

    if (dateInvoicesModalEl && typeof bootstrap !== 'undefined') {
      const bsModal = bootstrap.Modal.getOrCreateInstance(dateInvoicesModalEl);
      bsModal.show();
    }
  }

  function renderModalEvents(events) {
    if (!modalEventsList) return;

    if (!events.length) {
      modalEventsList.innerHTML =
        '<div class="events-placeholder p-4 text-center text-muted">' +
          '<i class="fa-solid fa-folder-open fs-3 mb-2 opacity-50"></i>' +
          '<p class="small mb-0">No invoices generated for this date or matching active filter.</p>' +
        '</div>';
      return;
    }

    let html = '';
    events.forEach(function (ev) {
      const borderCls = statusBorderClass(ev.status);
      const badgeCls = statusBadgeClass(ev.status);

      html +=
        '<a href="' + (ev.url || '#') + '" class="cal-modal-event-item ' + borderCls + '">' +
          '<div class="d-flex justify-content-between align-items-center mb-1">' +
            '<span class="cal-modal-event-inv"><i class="fa-solid fa-file-lines me-1 text-primary"></i>' + escapeHtml(ev.invoice_number) + '</span>' +
            '<span class="badge ' + badgeCls + ' px-2 py-1" style="font-size: 0.68rem;">' + escapeHtml(ev.status_display || ev.status) + '</span>' +
          '</div>' +
          '<div class="d-flex justify-content-between align-items-center mt-1">' +
            '<span class="cal-modal-event-cust"><i class="fa-solid fa-user me-1"></i>' + escapeHtml(ev.customer_name) + '</span>' +
            '<span class="cal-modal-event-amt">' + formatNumber(ev.amount) + '</span>' +
          '</div>' +
        '</a>';
    });

    modalEventsList.innerHTML = html;
  }

  function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str || '';
    return div.innerHTML;
  }

  // ── Boot ──
  if (pageHeaderAnalyticsBtn) {
    const startStr = dateKey(yearNum, month1, 1);
    const endStr = dateKey(yearNum, month1, daysInMonth(yearNum, month1));
    pageHeaderAnalyticsBtn.href = '/calendar/details/?start=' + startStr + '&end=' + endStr;
  }
  calculateKpis();
  buildGrid();

})();
