/**
 * Optimized AJAX Table Utility
 * by ChatGPT (optimized 2025)
 * Refactored to fix critical issues: debounce binding, optional forms, memory leaks, timeouts
 */
const tableAjaxConfigs = {};
const tableAbortControllers = {};
const tableEventListeners = {}; // Track listeners for cleanup

// Allowed HTTP methods
const ALLOWED_METHODS = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE'];

// --- Utility ---
const debounceTable = (fn, delay = 300) => {
    let timer;
    return (...args) => {
        clearTimeout(timer);
        timer = setTimeout(() => fn(...args), delay); // Fixed: removed incorrect this binding
    };
};

/**
 * Collect form data or use direct parameters
 * @param {HTMLElement|string|null} formOrId - Form element, form ID, or null
 * @param {Object} defaultParams - Default parameters to include
 * @param {HTMLElement} table - Table element for sort data
 * @returns {URLSearchParams}
 */
const collectFormData = (formOrId, defaultParams = {}, table = null) => {
    const params = new URLSearchParams();

    // Support form element, form ID string, or null
    let form = null;
    if (typeof formOrId === 'string') {
        form = document.getElementById(formOrId);
    } else if (formOrId instanceof HTMLFormElement) {
        form = formOrId;
    }

    // Collect form data if form exists
    if (form && form.tagName === 'FORM') {
        form.querySelectorAll("input, select, textarea").forEach(input => {
            if (input.name && input.value.trim() !== "") {
                params.append(input.name, input.value.trim());
            }
        });
    }

    // Add default parameters (fixed: handle false and 0 correctly)
    Object.entries(defaultParams).forEach(([k, v]) => {
        if (v !== undefined && v !== null) {
            // Only exclude empty strings, not false or 0
            const strValue = String(v);
            if (strValue.trim() !== "" || v === false || v === 0) {
                params.set(k, strValue);
            }
        }
    });

    // Include table sort if table is provided
    if (table && table.dataset.sort) {
        params.append("sort", table.dataset.sort);
    }

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
        spinner.setAttribute("role", "status");
        spinner.setAttribute("aria-live", "polite");
        spinner.setAttribute("aria-atomic", "true");
        spinner.innerHTML = `<i class="fas fa-spinner fa-spin" aria-hidden="true"></i><span>${text}</span>`;
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

/**
 * Fetch with timeout wrapper
 * @param {string} url - URL to fetch
 * @param {Object} options - Fetch options
 * @param {number} timeout - Timeout in milliseconds
 * @returns {Promise<Response>}
 */
async function fetchWithTimeout(url, options = {}, timeout = 30000) {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeout);

    try {
        const response = await fetch(url, {
            ...options,
            signal: options.signal ?
                AbortSignal.any([options.signal, controller.signal]) :
                controller.signal
        });
        clearTimeout(timeoutId);
        return response;
    } catch (error) {
        clearTimeout(timeoutId);
        if (error.name === 'AbortError' && !options.signal?.aborted) {
            throw new Error('Request timeout');
        }
        throw error;
    }
}

// --- Core Table Loader ---
async function loadTableData(formId, tableId, fetchUrl, options = {}, page = 1) {
    // Form is now optional - can be null/undefined
    const form = formId ? document.getElementById(formId) : null;
    const table = document.getElementById(tableId);
    if (!table || !fetchUrl) return false;

    const tableBody = table.querySelector("tbody");
    if (!tableBody) {
        console.error(`Table ${tableId} must have a tbody element`);
        return false;
    }

    const paginationId = `${tableId}_pagination`;
    let paginationWrapper = document.getElementById(paginationId) ||
        (() => {
            const wrap = document.createElement("div");
            wrap.id = paginationId;
            wrap.className = "pagination-wrapper";
            wrap.style.display = "none";
            (table.closest(".table-container") || table.parentElement).appendChild(wrap);
            return wrap;
        })();

    // Cancel any running request
    tableAbortControllers[tableId]?.abort();
    const abortController = new AbortController();
    tableAbortControllers[tableId] = abortController;

    // Show loading state in table body
    const cols = table.querySelector("thead tr")?.children.length || 1;
    const loadingText = options.loadingText || "Loading...";
    tableBody.innerHTML = `
        <tr>
            <td colspan="${cols}" class="text-center loading-cell" role="status" aria-live="polite">
                <div class="loading">
                    <i class="fas fa-spinner fa-spin" aria-hidden="true"></i>
                    ${loadingText}
                </div>
            </td>
        </tr>
    `;

    try {
        const params = collectFormData(formId, options.defaultParams || {}, table);
        params.append("page", page);

        // Validate HTTP method
        const method = (options.method?.toUpperCase() || "GET");
        if (!ALLOWED_METHODS.includes(method)) {
            throw new Error(`Invalid HTTP method: ${method}`);
        }

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

        const timeout = options.timeout || 30000;
        const res = await fetchWithTimeout(url, req, timeout);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        if (!data.success) throw new Error("Backend error");

        // Basic XSS protection: validate html is a string before inserting
        const htmlContent = data.html || "";
        if (typeof htmlContent !== 'string') {
            throw new Error("Invalid HTML content received");
        }

        // Replace table + pagination
        tableBody.innerHTML = htmlContent;
        updatePagination(paginationWrapper, data.pagination, (page) =>
            loadTableData(formId, tableId, fetchUrl, options, page)
        );

        // Focus management for accessibility
        const firstFocusable = tableBody.querySelector('a, button, input, select, textarea, [tabindex]:not([tabindex="-1"])');
        if (firstFocusable && options.focusAfterLoad !== false) {
            firstFocusable.focus();
        }

        table.dispatchEvent(new CustomEvent("tableDataLoaded", { detail: { data } }));
        options.onSuccess?.(data, table);
        return true;
    } catch (err) {
        if (err.name === "AbortError") return false;
        console.error("Table Load Error:", err);
        showTableError(table, err, options, formId, tableId, fetchUrl);
        options.onError?.(err, table);
        return false;
    }
}

// --- Helpers ---
function showTableError(table, error, options, formId, tableId, fetchUrl) {
    const tbody = table.querySelector("tbody");
    const cols = table.querySelector("thead tr")?.children.length || 1;
    tbody.innerHTML = "";
    const row = document.createElement("tr");
    const errorText = options.errorText || "Error loading data.";
    const retryText = options.retryText || "Retry";
    row.innerHTML = `<td colspan="${cols}" class="text-center" role="alert">
        ${errorText}
        <button class="btn btn-sm btn-outline-primary retry-btn" aria-label="${retryText}">${retryText}</button>
    </td>`;
    tbody.appendChild(row);

    // Clean up old retry button listener if exists
    const retryBtn = row.querySelector(".retry-btn");
    if (retryBtn) {
        // Store listener reference for cleanup
        const listener = () => loadTableData(formId, tableId, fetchUrl, options);
        retryBtn.addEventListener("click", listener);

        // Store for cleanup
        if (!tableEventListeners[tableId]) {
            tableEventListeners[tableId] = [];
        }
        tableEventListeners[tableId].push({ element: retryBtn, event: 'click', handler: listener });
    }
}

function updatePagination(wrapper, html, onClick) {
    if (!wrapper) return;
    if (!html || !html.trim()) {
        wrapper.innerHTML = "";
        wrapper.style.display = "none";
        return;
    }
    wrapper.style.display = "flex";
    wrapper.innerHTML = html;

    // Remove old click listener if exists (prevent memory leak)
    if (wrapper._paginationClickHandler) {
        wrapper.removeEventListener("click", wrapper._paginationClickHandler);
    }

    // Create new click handler
    wrapper._paginationClickHandler = e => {
        const link = e.target.closest("a[data-page]");
        if (!link) return;
        e.preventDefault();
        const page = link.dataset.page;
        onClick(page);
    };

    wrapper.addEventListener("click", wrapper._paginationClickHandler);
}

/**
 * Cleanup function to remove event listeners and abort controllers for a table
 * @param {string} tableId - Table ID to clean up
 */
function cleanupTable(tableId) {
    // Abort any pending requests
    tableAbortControllers[tableId]?.abort();
    delete tableAbortControllers[tableId];

    // Remove event listeners
    if (tableEventListeners[tableId]) {
        tableEventListeners[tableId].forEach(({ element, event, handler }) => {
            element.removeEventListener(event, handler);
        });
        delete tableEventListeners[tableId];
    }

    // Remove pagination click handler
    const paginationWrapper = document.getElementById(`${tableId}_pagination`);
    if (paginationWrapper && paginationWrapper._paginationClickHandler) {
        paginationWrapper.removeEventListener("click", paginationWrapper._paginationClickHandler);
        delete paginationWrapper._paginationClickHandler;
    }

    // Remove config
    delete tableAjaxConfigs[tableId];
}

// --- Table Initialization ---
function initTableAjax(formId, tableId, url, options = {}, includeInputs = false) {
    // Clean up any existing configuration for this table
    cleanupTable(tableId);

    tableAjaxConfigs[tableId] = { formId, tableId, fetchUrl: url, options };

    // Form is now optional - only attach listeners if form exists
    const form = formId ? document.getElementById(formId) : null;
    if (form && form.tagName === 'FORM') {
        // Store submit handler for cleanup
        const submitHandler = e => {
            e.preventDefault();
            loadTableData(formId, tableId, url, options);
        };
        form.addEventListener("submit", submitHandler);

        if (!tableEventListeners[tableId]) {
            tableEventListeners[tableId] = [];
        }
        tableEventListeners[tableId].push({ element: form, event: 'submit', handler: submitHandler });

        const selector = includeInputs ? "input, select, textarea" : "select, textarea";
        form.querySelectorAll(selector).forEach(input => {
            const debouncedHandler = debounceTable(() =>
                loadTableData(formId, tableId, url, options), options.debounceDelay || 400);
            input.addEventListener("input", debouncedHandler);

            if (!tableEventListeners[tableId]) {
                tableEventListeners[tableId] = [];
            }
            tableEventListeners[tableId].push({ element: input, event: 'input', handler: debouncedHandler });
        });
    }

    if (options.autoLoad !== false) {
        loadTableData(formId, tableId, url, options);
    }
}

function reloadTable(id) {
    const cfg = tableAjaxConfigs[id];
    if (cfg) loadTableData(cfg.formId, cfg.tableId, cfg.fetchUrl, cfg.options);
}

// --- Sorting ---
function initTableSorting(id) {
    const table = document.getElementById(id);
    if (!table) return;

    // Clean up old sort listeners
    if (table._sortListeners) {
        table._sortListeners.forEach(({ element, handler }) => {
            element.removeEventListener("click", handler);
        });
    }
    table._sortListeners = [];

    table.querySelectorAll("th[data-sort]").forEach(th => {
        th.style.cursor = "pointer";
        th.setAttribute("role", "button");
        th.setAttribute("tabindex", "0");
        th.setAttribute("aria-label", `Sort by ${th.dataset.sort}`);

        const clickHandler = () => {
            const f = th.dataset.sort;
            const s = table.dataset.sort;
            table.dataset.sort = s === f ? `-${f}` : s === `-${f}` ? "" : f;
            updateSortIndicators(table);
            reloadTable(id);
        };

        th.addEventListener("click", clickHandler);
        th.addEventListener("keydown", (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                clickHandler();
            }
        });

        table._sortListeners.push({ element: th, handler: clickHandler });
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
    const form = formId ? document.getElementById(formId) : null;
    const table = document.getElementById(tableId);
    if (!table) return new URLSearchParams();

    const params = collectFormData(formId, options.defaultParams || {}, table);

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
window.cleanupTable = cleanupTable; // Expose cleanup function
