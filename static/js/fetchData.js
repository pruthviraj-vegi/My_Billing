/**
 * Optimized AJAX Table Utility
 * by ChatGPT (optimized 2025)
 */
const tableAjaxConfigs = {};
const tableAbortControllers = {};

// --- Utility ---
const debounceTable = (fn, delay = 300) => {
    let timer;
    return (...args) => {
        clearTimeout(timer);
        timer = setTimeout(() => fn.apply(this, args), delay);
    };
};

const collectFormData = (form, defaultParams = {}, table = null) => {
    const params = new URLSearchParams();
    form.querySelectorAll("input, select, textarea").forEach(input => {
        if (input.name && input.value.trim() !== "") params.append(input.name, input.value.trim());
    });
    Object.entries(defaultParams).forEach(([k, v]) => {
        if (v !== undefined && v !== null && `${v}`.trim() !== "") params.set(k, `${v}`.trim());
    });
    // Include table sort if table is provided
    if (table && table.dataset.sort) params.append("sort", table.dataset.sort);
    return params;
};

// --- Loading Spinner ---
function showTableLoading(table, text = "Loading...") {
    if (!table) return;
    table.style.opacity = "0.6";
    table.setAttribute("aria-busy", "true");
    let spinner = document.getElementById(`${table.id}-loading`);
    if (!spinner) {
        spinner = document.createElement("div");
        spinner.id = `${table.id}-loading`;
        spinner.className = "table-spinner";
        spinner.innerHTML = `<i class="fas fa-spinner fa-spin"></i><span>${text}</span>`;
        (table.closest('.table-container') || table.parentElement).appendChild(spinner);
    }
    spinner.style.display = "flex";
}

function hideTableLoading(table) {
    if (!table) return;
    table.style.opacity = "1";
    table.setAttribute("aria-busy", "false");
    const spinner = document.getElementById(`${table.id}-loading`);
    if (spinner) spinner.style.display = "none";
}

// --- Core Table Loader ---
async function loadTableData(formId, tableId, fetchUrl, options = {}, page = 1) {
    const form = document.getElementById(formId);
    const table = document.getElementById(tableId);
    if (!form || !table || !fetchUrl) return false;

    const tableBody = table.querySelector("tbody");
    const paginationId = `${tableId}_pagination`;
    let paginationWrapper = document.getElementById(paginationId) ||
        (() => {
            const wrap = document.createElement("div");
            wrap.id = paginationId;
            wrap.className = "pagination-wrapper";
            (table.closest(".table-container") || table.parentElement).appendChild(wrap);
            return wrap;
        })();

    // Cancel any running request
    tableAbortControllers[tableId]?.abort();
    const abortController = new AbortController();
    tableAbortControllers[tableId] = abortController;

    showTableLoading(table, options.loadingText);

    try {
        const params = collectFormData(form, options.defaultParams, table);
        params.append("page", page);

        const method = options.method?.toUpperCase() || "GET";
        const req = {
            method,
            headers: { "X-Requested-With": "XMLHttpRequest" },
            signal: abortController.signal
        };
        const url = method === "POST" ? fetchUrl : `${fetchUrl}?${params}`;
        if (method === "POST") {
            req.body = params;
            req.headers["Content-Type"] = "application/x-www-form-urlencoded";
        }

        const res = await fetch(url, req);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        if (!data.success) throw new Error("Backend error");

        // Replace table + pagination
        tableBody.innerHTML = data.html || "";
        updatePagination(paginationWrapper, data.pagination, (page) =>
            loadTableData(formId, tableId, fetchUrl, options, page)
        );

        table.dispatchEvent(new CustomEvent("tableDataLoaded", { detail: { data } }));
        options.onSuccess?.(data, table);
        return true;
    } catch (err) {
        if (err.name === "AbortError") return false;
        console.error("Table Load Error:", err);
        showTableError(table, err, options, formId, tableId, fetchUrl);
        options.onError?.(err, table);
        return false;
    } finally {
        hideTableLoading(table);
    }
}

// --- Helpers ---
function showTableError(table, error, options, formId, tableId, fetchUrl) {
    const tbody = table.querySelector("tbody");
    const cols = table.querySelector("thead tr")?.children.length || 1;
    tbody.innerHTML = "";
    const row = document.createElement("tr");
    row.innerHTML = `<td colspan="${cols}" class="text-center">${options.errorText || "Error loading data."}
        <button class="btn btn-sm btn-outline-primary retry-btn">${options.retryText || "Retry"}</button>
    </td>`;
    tbody.appendChild(row);
    row.querySelector(".retry-btn").addEventListener("click", () =>
        loadTableData(formId, tableId, fetchUrl, options)
    );
}

function updatePagination(wrapper, html, onClick) {
    if (!wrapper) return;
    if (!html || !html.trim()) {
        wrapper.innerHTML = "";
        return;
    }
    wrapper.innerHTML = html;
    wrapper.onclick = e => {
        const link = e.target.closest("a[data-page]");
        if (!link) return;
        e.preventDefault();
        const page = link.dataset.page;
        onClick(page);
    };
}

// --- Table Initialization ---
function initTableAjax(formId, tableId, url, options = {}, includeInputs = false) {
    tableAjaxConfigs[tableId] = { formId, tableId, fetchUrl: url, options };
    const form = document.getElementById(formId);
    if (!form) return;

    form.addEventListener("submit", e => {
        e.preventDefault();
        loadTableData(formId, tableId, url, options);
    });

    const selector = includeInputs ? "input, select, textarea" : "select, textarea";
    form.querySelectorAll(selector).forEach(input =>
        input.addEventListener("input", debounceTable(() =>
            loadTableData(formId, tableId, url, options), options.debounceDelay || 400)
        )
    );

    if (options.autoLoad !== false) loadTableData(formId, tableId, url, options);
}

function reloadTable(id) {
    const cfg = tableAjaxConfigs[id];
    if (cfg) loadTableData(cfg.formId, cfg.tableId, cfg.fetchUrl, cfg.options);
}

// --- Sorting ---
function initTableSorting(id) {
    const table = document.getElementById(id);
    if (!table) return;
    table.querySelectorAll("th[data-sort]").forEach(th => {
        th.style.cursor = "pointer";
        th.addEventListener("click", () => {
            const f = th.dataset.sort;
            const s = table.dataset.sort;
            table.dataset.sort = s === f ? `-${f}` : s === `-${f}` ? "" : f;
            updateSortIndicators(table);
            reloadTable(id);
        });
    });
}

function updateSortIndicators(table) {
    const s = table.dataset.sort;
    table.querySelectorAll("th[data-sort]").forEach(th => {
        const f = th.dataset.sort;
        th.classList.toggle("asc", s === f);
        th.classList.toggle("desc", s === `-${f}`);
    });
}

// --- PDF Download Helpers ---
function getTableQueryParams(formId, tableId, options = {}) {
    const form = document.getElementById(formId);
    const table = document.getElementById(tableId);
    if (!form || !table) return new URLSearchParams();

    const params = collectFormData(form, options.defaultParams || {}, table);

    return params;
}

function generatePDFUrl(formId, tableId, pdfBaseUrl, options = {}) {
    const params = getTableQueryParams(formId, tableId, options);
    return `${pdfBaseUrl}?${params.toString()}`;
}

function downloadTablePDF(formId, tableId, pdfBaseUrl, options = {}) {
    const pdfUrl = generatePDFUrl(formId, tableId, pdfBaseUrl, options);
    window.open(pdfUrl, '_blank');
}

// --- Extend $ wrapper with ajax method ---
(function () {
    const original$ = window.$;
    if (typeof original$ === 'function') {
        // Extend existing $ function to add ajax method
        window.$ = function (selector) {
            const result = original$(selector);
            // If result is an object with methods (from wordSuggestion.js), extend it
            if (result && typeof result === 'object' && !Array.isArray(result)) {
                result.ajax = function (options = {}) {
                    const form = typeof selector === "string" ? document.querySelector(selector) : selector;
                    if (!form || form.tagName !== "FORM") {
                        console.error("Table AJAX: Element must be a form");
                        return this;
                    }
                    const config = {
                        tableId: options.tableId || "",
                        url: options.url || "",
                        placeholder: options.placeholder || "Loading...",
                        method: options.method || "GET",
                        debounceDelay: options.debounceDelay || 400,
                        includeInputs: options.includeInputs || false,
                        autoLoad: options.autoLoad !== false,
                        sortable: options.sortable !== false,
                        onSuccess: options.onSuccess || null,
                        onError: options.onError || null,
                        defaultParams: options.defaultParams || {},
                        ...options
                    };
                    if (!config.tableId || !config.url) {
                        console.error("Table AJAX: tableId and url are required");
                        return this;
                    }
                    initTableAjax(form.id, config.tableId, config.url, {
                        method: config.method,
                        debounceDelay: config.debounceDelay,
                        loadingText: config.placeholder,
                        autoLoad: config.autoLoad,
                        onSuccess: config.onSuccess,
                        onError: config.onError,
                        defaultParams: config.defaultParams
                    }, config.includeInputs);
                    if (config.sortable) {
                        initTableSorting(config.tableId);
                    }
                    return this;
                };
            }
            return result;
        };
    }
})();

// --- Global expose ---
window.loadTableData = loadTableData;
window.initTableAjax = initTableAjax;
window.reloadTable = reloadTable;
window.initTableSorting = initTableSorting;
window.updateSortIndicators = updateSortIndicators;
window.getTableQueryParams = getTableQueryParams;
window.generatePDFUrl = generatePDFUrl;
window.downloadTablePDF = downloadTablePDF;
