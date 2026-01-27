/**
 * Optimized CartManager
 * Handles cart CRUD, barcode scanning, and real-time totals
 * Optimized for performance, readability, and maintainability
 */

class CartManager {
    // Constants for timing and configuration
    static DOM_READY_DELAY = 50;
    static ANIMATION_DURATION = 300;
    static DEBOUNCE_DELAY = 300;
    static REDIRECT_DELAY = 1500;
    static RETRY_ATTEMPTS = 3;
    static RETRY_DELAY = 1000;
    constructor() {
        this.initGlobals();
        this.initDOM();
        this.initListeners();
        this.focusBarcode();

        // Request management
        this.abortController = null;
        this.pendingRequests = new Set();
        this.isProcessingBarcode = false;

        // Offline detection
        this.isOnline = navigator.onLine;
        this.requestQueue = [];
        this.initOfflineDetection();

        // Debounced functions
        this.debouncedRecalculate = this.debounce(() => this.recalculateTotals(), 100);
        this.debouncedBarcodeSubmit = this.debounce((e) => this._handleBarcodeSubmit(e), 300);

        if (this.dom.totalSelling && this.dom.body) {
            setTimeout(() => this.recalculateTotals(), CartManager.DOM_READY_DELAY);
        }
    }

    /*** ───────── INITIALIZATION ───────── ***/
    /**
     * Initialize global configuration from window.CART_DATA
     * @private
     */
    initGlobals() {
        if (!window.CART_DATA) {
            console.error('[CartManager] CART_DATA missing. Make sure the template is properly loaded.');
            return;
        }

        const { CART_DATA } = window;
        this.csrf = CART_DATA.csrfToken;
        this.cartId = CART_DATA.cartId;
        this.urls = CART_DATA.urls;

        this.formatter = new Intl.NumberFormat('en-IN', {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        });
    }

    /**
     * Cache DOM elements for performance
     * @private
     */
    initDOM() {
        this.dom = {
            form: document.getElementById('barcodeForm'),
            input: document.getElementById('barcodeInput'),
            body: document.getElementById('cartItemsBody'),
            totalItems: document.getElementById('totalItems'),
            totalAmount: document.getElementById('totalAmount'),
            totalSelling: document.getElementById('totalSellingPrice'),
            archiveBtn: document.getElementById('archiveCartBtn'),
            clearBtn: document.getElementById('clearCartBtn'),
            priceHeader: document.getElementById('priceColumnHeader'),
            remainingStock: document.getElementById('remainingStock'),
        };

        // Initialize price toggle state (removed global pollution)
        this.priceToggleState = false;
    }

    initListeners() {
        const { form, body, archiveBtn, clearBtn } = this.dom;

        if (form) {
            form.addEventListener('submit', e => this.onBarcodeSubmit(e));
        }

        if (body) {
            body.addEventListener('click', e => this.onTableClick(e));
            body.addEventListener('keydown', e => this.onInputKey(e));
            body.addEventListener('input', e => this.onRealTimeUpdate(e));
        }

        if (archiveBtn) {
            archiveBtn.addEventListener('click', () => {
                this.confirm('Archive Cart', 'Are you sure you want to archive this cart? This action cannot be undone.', () => this.archiveCart());
            });
        }

        if (clearBtn) {
            clearBtn.addEventListener('click', () => {
                this.confirm('Clear Cart', 'Are you sure you want to clear all items from this cart? This action cannot be undone.', () => this.clearCart());
            });
        }

        this.initDropdown();
        this.initPriceToggle();
    }

    /*** ───────── OFFLINE DETECTION ───────── ***/
    /**
     * Initialize offline detection and event listeners
     * @private
     */
    initOfflineDetection() {
        // Listen for online/offline events
        window.addEventListener('online', () => {
            this.isOnline = true;
            this.notify('Connection restored', 'success');
            this.updateOfflineIndicator();
            this.processQueue();
        });

        window.addEventListener('offline', () => {
            this.isOnline = false;
            this.notify('You are offline. Changes will be queued.', 'warning');
            this.updateOfflineIndicator();
        });

        // Initial indicator update
        this.updateOfflineIndicator();
    }

    /**
     * Update visual offline indicator
     * @private
     */
    updateOfflineIndicator() {
        let indicator = document.getElementById('offlineIndicator');

        if (!this.isOnline) {
            if (!indicator) {
                indicator = document.createElement('div');
                indicator.id = 'offlineIndicator';
                indicator.style.cssText = `
                    position: fixed;
                    top: 10px;
                    right: 10px;
                    background: #ff9800;
                    color: white;
                    padding: 8px 16px;
                    border-radius: 4px;
                    z-index: 9999;
                    font-size: 14px;
                    box-shadow: 0 2px 8px rgba(0,0,0,0.2);
                `;
                indicator.innerHTML = '<i class="fas fa-wifi" style="margin-right: 8px;"></i>Offline Mode';
                document.body.appendChild(indicator);
            }
        } else {
            if (indicator) {
                indicator.remove();
            }
        }
    }

    /**
     * Queue request for later execution when offline
     * @param {string} url - API endpoint
     * @param {string} method - HTTP method
     * @param {Object|null} body - Request body
     * @private
     */
    queueRequest(url, method, body) {
        this.requestQueue.push({ url, method, body, timestamp: Date.now() });
        console.log(`[CartManager] Request queued (${this.requestQueue.length} in queue)`);
    }

    /**
     * Process queued requests when back online
     * @private
     */
    async processQueue() {
        if (this.requestQueue.length === 0) return;

        this.notify(`Processing ${this.requestQueue.length} queued request(s)...`, 'info');
        const queue = [...this.requestQueue];
        this.requestQueue = [];

        for (const request of queue) {
            try {
                await this.api(request.url, request.method, request.body);
            } catch (err) {
                console.error('[CartManager] Failed to process queued request:', err);
                // Re-queue failed requests
                this.requestQueue.push(request);
            }
        }

        if (this.requestQueue.length === 0) {
            this.notify('All queued requests processed', 'success');
            // Refresh the page to sync with server
            setTimeout(() => window.location.reload(), 1000);
        }
    }



    /*** ───────── HELPERS ───────── ***/
    /**
     * Show stock warning if stock is low or negative
     * @param {number} remainingStock - Remaining stock quantity
     * @param {string} productName - Product name for context
     * @private
     */
    showStockWarning(remainingStock, productName = 'Product') {
        if (remainingStock === undefined || remainingStock === null) return;

        if (remainingStock < 0) {
            this.notify(`Warning: ${productName} is oversold (stock: ${remainingStock})`, 'warning');
        } else if (remainingStock === 0) {
            this.notify(`Warning: ${productName} is out of stock`, 'warning');
        } else if (remainingStock < 10) {
            this.notify(`Warning: ${productName} stock is low (${remainingStock} remaining)`, 'warning');
        }
    }

    /**
     * Debounce utility to limit function execution frequency
     * @param {Function} func - Function to debounce
     * @param {number} wait - Delay in milliseconds
     * @returns {Function} Debounced function
     * @private
     */
    debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }

    /**
     * Format number to Indian currency format
     * @param {number|string} num - Number to format
     * @returns {string} Formatted number string
     */
    format(num) {
        const n = typeof num === 'string' ? parseFloat(num.replace(/[^\d.-]/g, '')) : parseFloat(num);
        return isNaN(n) || !isFinite(n) ? '0.00' : this.formatter.format(n);
    }

    /**
     * Calculate discount percentage
     * @param {number} selling - Selling price
     * @param {number} price - Actual price
     * @returns {number} Discount percentage
     */
    calcDiscount(selling, price) {
        return selling > 0 ? Math.max(0, ((selling - price) / selling) * 100) : 0;
    }

    /**
     * Parse error message and provide context-specific feedback
     * @param {Error} err - Error object
     * @param {string} operation - Operation being performed
     * @returns {string} User-friendly error message
     * @private
     */
    parseErrorMessage(err, operation = 'operation') {
        const message = err.message || 'Unknown error';

        // Map common error patterns to user-friendly messages
        if (message.includes('NetworkError') || message.includes('Failed to fetch')) {
            return `Network error during ${operation}. Please check your connection.`;
        }
        if (message.includes('timeout')) {
            return `Request timed out during ${operation}. Please try again.`;
        }
        if (message.includes('401') || message.includes('Unauthorized')) {
            return `Session expired. Please refresh the page and log in again.`;
        }
        if (message.includes('403') || message.includes('Forbidden')) {
            return `You don't have permission to perform this ${operation}.`;
        }
        if (message.includes('404') || message.includes('Not Found')) {
            return `Item not found. It may have been deleted.`;
        }
        if (message.includes('500') || message.includes('Internal Server Error')) {
            return `Server error during ${operation}. Please contact support if this persists.`;
        }
        if (message.includes('failed after')) {
            return `${operation} failed after multiple attempts. Please try again later.`;
        }

        // Return original message if no pattern matches
        return `${operation} failed: ${message}`;
    }

    /**
     * Retry wrapper with exponential backoff
     * @param {Function} fn - Async function to retry
     * @param {number} attempt - Current attempt number
     * @returns {Promise<Object>} Result from function
     * @private
     */
    async retryWithBackoff(fn, attempt = 1) {
        try {
            return await fn();
        } catch (err) {
            // Don't retry if request was cancelled or if we've exhausted attempts
            if (err.message === 'Request cancelled' || attempt >= CartManager.RETRY_ATTEMPTS) {
                if (attempt >= CartManager.RETRY_ATTEMPTS) {
                    throw new Error(`${err.message} (failed after ${CartManager.RETRY_ATTEMPTS} attempts)`);
                }
                throw err;
            }

            // Exponential backoff: 1s, 2s, 4s
            const delay = CartManager.RETRY_DELAY * Math.pow(2, attempt - 1);
            console.log(`[CartManager] Retry attempt ${attempt}/${CartManager.RETRY_ATTEMPTS} after ${delay}ms`);

            await new Promise(resolve => setTimeout(resolve, delay));
            return this.retryWithBackoff(fn, attempt + 1);
        }
    }

    /**
     * Make API request with AbortController support and retry logic
     * @param {string} url - API endpoint
     * @param {string} method - HTTP method
     * @param {Object|null} body - Request body
     * @returns {Promise<Object>} API response data
     * @throws {Error} On network or API errors
     */
    async api(url, method = 'GET', body = null) {
        // Check if offline and queue request
        if (!this.isOnline) {
            this.queueRequest(url, method, body);
            throw new Error('You are offline. Request has been queued.');
        }

        return this.retryWithBackoff(async () => {
            // Cancel previous request if exists
            if (this.abortController) {
                this.abortController.abort();
            }

            this.abortController = new AbortController();
            const requestId = Date.now();
            this.pendingRequests.add(requestId);

            try {
                const opts = {
                    method,
                    headers: {
                        'X-CSRFToken': this.csrf,
                        'Content-Type': 'application/json',
                    },
                    signal: this.abortController.signal,
                };
                if (body) opts.body = JSON.stringify(body);

                const res = await fetch(url, opts);
                const data = await res.json();

                // Check for API-level errors
                if (!res.ok || data.status === 'error') {
                    throw new Error(data.message || res.statusText || `HTTP ${res.status}`);
                }

                return data;
            } catch (err) {
                if (err.name === 'AbortError') {
                    console.log('[CartManager] Request cancelled');
                    throw new Error('Request cancelled');
                }
                console.error('[CartManager] API Error:', err);
                throw err;
            } finally {
                this.pendingRequests.delete(requestId);
                if (this.pendingRequests.size === 0) {
                    this.abortController = null;
                }
            }
        });
    }

    /**
     * Focus barcode input only if user is not actively typing elsewhere
     */
    focusBarcode() {
        // Check if user is currently focused on an input element
        const activeElement = document.activeElement;
        const isTypingElsewhere = activeElement &&
            (activeElement.tagName === 'INPUT' ||
                activeElement.tagName === 'TEXTAREA' ||
                activeElement.isContentEditable);

        // Only auto-focus if user is not typing elsewhere
        if (!isTypingElsewhere) {
            this.dom.input?.focus();
        }
    }

    /**
     * Show notification to user
     * @param {string} msg - Notification message
     * @param {string} type - Notification type (info, success, error, warning)
     */
    notify(msg, type = 'info') {
        if (typeof showNotification === 'function') {
            showNotification(msg, type);
        } else {
            console.log(`[CartManager ${type.toUpperCase()}] ${msg}`);
        }
    }

    /*** ───────── PRICE TOGGLE ───────── ***/
    /**
     * Initialize price toggle functionality (F9 key)
     * @private
     */
    initPriceToggle() {
        // Initialize price display format after DOM is ready
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => this.formatPriceDisplays());
        } else {
            // DOM already loaded
            setTimeout(() => this.formatPriceDisplays(), CartManager.DOM_READY_DELAY);
        }

        // Listen for F9 key press
        document.addEventListener('keydown', (e) => {
            if (e.keyCode === 120 || e.key === 'F9') {
                e.preventDefault();
                this.togglePriceDisplay();
            }
        });
    }

    formatPriceDisplays() {
        const priceCells = document.querySelectorAll('.price-toggle-cell .price-display');
        priceCells.forEach(span => {
            const value = parseFloat(span.textContent.replace(/[^\d.-]/g, '')) || 0;
            span.textContent = this.formatPriceAnimation(value);
        });
    }

    formatPriceAnimation(value) {
        return value.toLocaleString('en-IN', {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        });
    }

    animatePriceChange(element, startValue, endValue, duration = CartManager.ANIMATION_DURATION) {
        const startTime = performance.now();
        const difference = endValue - startValue;

        const update = (currentTime) => {
            const elapsed = currentTime - startTime;
            const progress = Math.min(elapsed / duration, 1);

            // Easing function for smooth animation
            const easeOutQuad = 1 - Math.pow(1 - progress, 2);
            const currentValue = startValue + difference * easeOutQuad;

            element.textContent = this.formatPriceAnimation(currentValue);

            if (progress < 1) {
                requestAnimationFrame(update);
            } else {
                element.textContent = this.formatPriceAnimation(endValue);
            }
        };

        requestAnimationFrame(update);
    }

    /**
     * Toggle between selling price and purchase price display
     * Triggered by F9 key
     */
    togglePriceDisplay() {
        this.priceToggleState = !this.priceToggleState;

        const header = this.dom.priceHeader;
        const priceCells = document.querySelectorAll('.price-toggle-cell');

        // Update header
        if (header) {
            header.textContent = this.priceToggleState ? 'Purchase Price' : 'Selling Price';
        }

        // Update all price cells
        priceCells.forEach(cell => {
            const sellingPrice = parseFloat(cell.getAttribute('data-selling-price')) || 0;
            const purchasePrice = parseFloat(cell.getAttribute('data-purchase-price')) || 0;
            const displaySpan = cell.querySelector('.price-display');

            if (displaySpan) {
                const targetPrice = this.priceToggleState ? purchasePrice : sellingPrice;
                // Get current displayed value (remove currency symbols and parse)
                const currentText = displaySpan.textContent.replace(/[^\d.-]/g, '');
                const currentPrice = parseFloat(currentText) || 0;

                // Animate the price change
                this.animatePriceChange(displaySpan, currentPrice, targetPrice, CartManager.ANIMATION_DURATION);
            }
        });
    }

    /*** ───────── UI EVENTS ───────── ***/
    /**
     * Handle barcode form submission with debouncing to prevent race conditions
     * @param {Event} e - Submit event
     */
    async onBarcodeSubmit(e) {
        e.preventDefault();

        // Prevent rapid successive scans (race condition fix)
        if (this.isProcessingBarcode) {
            console.log('[CartManager] Barcode scan in progress, ignoring duplicate request');
            return;
        }

        const code = this.dom.input.value.trim();

        // Input validation
        if (!code) {
            this.notify('Please enter a barcode', 'error');
            this.focusBarcode();
            return;
        }

        this.isProcessingBarcode = true;

        try {
            const data = await this.api(this.urls.scanBarcode, 'POST', {
                barcode: code,
                cart_id: Number(this.cartId),
                quantity: 1,
            });

            if (data.status !== 'success') {
                this.notify(data.message || 'Failed to add item', 'error');
                return;
            }

            this.dom.input.value = '';

            if (!data.cart_item) {
                this.notify('Invalid response structure', 'error');
                return;
            }

            if (data.type === 'Create') {
                this.addCartRow(data.cart_item);
                this.notify('Item added successfully', 'success');
            } else if (data.type === 'Update') {
                this.updateCartRow(data.cart_item);
                this.notify('Item updated successfully', 'success');
            }

            // Update totals (removed duplicate call)
            if (data.cart_total !== undefined) {
                this.updateTotals(data.cart_total);
            }

            if (data.remaining_stock !== undefined) {
                this.dom.remainingStock.textContent = data.remaining_stock;
                // Show stock warning (non-blocking)
                const productName = data.cart_item?.product_variant?.simple_name || 'Product';
                this.showStockWarning(data.remaining_stock, productName);
            }
        } catch (err) {
            if (err.message !== 'Request cancelled') {
                console.error('[CartManager] Error in barcode submission:', err);
                this.notify(`Error adding product to cart: ${err.message}`, 'error');
            }
        } finally {
            this.isProcessingBarcode = false;
            this.focusBarcode();
        }
    }

    onInputKey(e) {
        if (e.key === 'Enter' && e.target.matches('.quantity-input, .price-input')) {
            e.preventDefault();
            const itemId = e.target.dataset.itemId;
            if (itemId) {
                this.updateItem(itemId);
            }
        }
    }

    onTableClick(e) {
        const btn = e.target.closest('.update-item-btn, .delete-item-btn');
        if (!btn) return;

        const itemId = btn.dataset.itemId;
        if (!itemId) return;

        if (btn.classList.contains('update-item-btn')) {
            this.updateItem(itemId);
        } else if (btn.classList.contains('delete-item-btn')) {
            this.deleteItem(itemId);
        }
    }

    /**
     * Handle real-time updates to quantity/price inputs with debouncing
     * @param {Event} e - Input event
     */
    onRealTimeUpdate(e) {
        const el = e.target;
        if (!el.matches('.quantity-input, .price-input')) return;

        const row = el.closest('tr');
        if (!row) return;

        const qtyInput = row.querySelector('.quantity-input');
        const priceInput = row.querySelector('.price-input');
        const discountCell = row.querySelector('.discount-cell');
        const amountCell = row.querySelector('.amount-cell');
        const priceToggleCell = row.querySelector('.price-toggle-cell');

        if (!qtyInput || !priceInput || !discountCell || !amountCell) return;

        const qty = parseFloat(qtyInput.value) || 0;
        const price = parseFloat(priceInput.value) || 0;
        const sell = parseFloat(priceToggleCell?.dataset.sellingPrice) || 0;

        // Calculate and update amount
        const newAmount = qty * price;
        const roundedAmount = Math.round(newAmount * 100) / 100;
        amountCell.textContent = this.format(roundedAmount);

        // Calculate and update discount
        const discount = this.calcDiscount(sell, price);
        discountCell.textContent = `${discount.toFixed(2)}%`;

        // Debounced total recalculation for performance
        this.debouncedRecalculate();
    }

    /*** ───────── CRUD OPS ───────── ***/
    /**
     * Update cart item with optimistic UI updates and rollback on failure
     * @param {string|number} id - Cart item ID
     */
    async updateItem(id) {
        const row = document.getElementById(`cart-item-${id}`);
        if (!row) {
            return this.notify('Item not found', 'error');
        }

        const qtyInput = row.querySelector('.quantity-input');
        const priceInput = row.querySelector('.price-input');
        const amountCell = row.querySelector('.amount-cell');
        const discountCell = row.querySelector('.discount-cell');

        if (!qtyInput || !priceInput || !amountCell) {
            return this.notify('Invalid form inputs', 'error');
        }

        const qty = parseFloat(qtyInput.value);
        const price = parseFloat(priceInput.value);

        // Enhanced validation
        if (!qty || !price || qty <= 0 || price < 0) {
            return this.notify('Please enter valid quantity and price (quantity > 0, price ≥ 0)', 'error');
        }

        // Disable inputs during update to prevent race conditions
        qtyInput.disabled = true;
        priceInput.disabled = true;

        // Store original values for rollback
        const originalValues = {
            quantity: qtyInput.value,
            price: priceInput.value,
            amount: amountCell.textContent,
            discount: discountCell ? discountCell.textContent : '0%',
            totalAmount: this.dom.totalAmount.textContent,
        };

        const btn = row.querySelector('.update-item-btn');
        if (btn) {
            btn.disabled = true;
            btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
        }


        try {
            // Optimistic UI update
            const newAmount = qty * price;
            const roundedAmount = Math.round(newAmount * 100) / 100;
            qtyInput.value = qty;
            priceInput.value = price;
            amountCell.textContent = this.format(roundedAmount);

            // Calculate and update discount optimistically
            if (discountCell) {
                const sellingPrice = parseFloat(row.querySelector('.price-toggle-cell')?.dataset.sellingPrice) || 0;
                if (sellingPrice > 0) {
                    const discount = this.calcDiscount(sellingPrice, price);
                    discountCell.textContent = `${discount.toFixed(2)}%`;
                }
            }

            const data = await this.api(this.urls.manageItem.replace('0', id), 'PUT', { quantity: qty, price });

            // Update with server response data
            if (data.cart_item) {
                if (amountCell) {
                    amountCell.textContent = this.format(data.cart_item.amount);
                }

                // Update discount percentage if available
                if (data.cart_item.discount_percentage !== undefined && discountCell) {
                    discountCell.textContent = `${data.cart_item.discount_percentage}%`;
                }
                if (data.remaining_stock !== undefined) {
                    this.dom.remainingStock.textContent = this.format(data.remaining_stock);
                    // Show stock warning (non-blocking)
                    const variantName = row.querySelector('td:nth-child(3)')?.textContent || 'Product';
                    this.showStockWarning(data.remaining_stock, variantName.trim());
                }
            }

            // Update totals (removed duplicate recalculateTotals call)
            this.updateTotals(data.cart_total);
            this.notify('Item updated successfully', 'success');
        } catch (err) {
            console.error('[CartManager] Error updating item:', err);
            this.rollbackItemUpdate(id, originalValues);
            this.notify(err.message || 'Update failed - values restored', 'error');
        } finally {
            // Re-enable inputs
            qtyInput.disabled = false;
            priceInput.disabled = false;

            if (btn) {
                btn.disabled = false;
                btn.innerHTML = '<i class="fas fa-save"></i>';
            }
            this.focusBarcode();
        }
    }

    /**
     * Delete cart item with confirmation
     * @param {string|number} id - Cart item ID
     */
    async deleteItem(id) {
        // Use custom modal for consistency
        this.confirm(
            'Remove Item',
            'Are you sure you want to remove this item from the cart?',
            () => this.performDelete(id)
        );
    }

    /**
     * Perform the actual delete operation
     * @param {string|number} id - Cart item ID
     * @private
     */
    async performDelete(id) {
        const row = document.getElementById(`cart-item-${id}`);
        if (!row) {
            return this.notify('Item not found', 'error');
        }

        try {
            // Delete from backend immediately
            const data = await this.api(this.urls.manageItem.replace('0', id), 'DELETE');

            if (data.status === 'success') {
                // Remove from DOM
                row.remove();

                // Update totals
                this.updateTotals(data.cart_total);
                this.notify('Item removed successfully', 'success');
                console.log(`[CartManager] Item ${id} deleted`);
            } else {
                this.notify(data.message || 'Failed to delete item', 'error');
            }
        } catch (err) {
            console.error('[CartManager] Error deleting item:', err);
            this.notify(this.parseErrorMessage(err, 'delete'), 'error');
        } finally {
            this.focusBarcode();
        }
    }

    /*** ───────── UI UPDATES ───────── ***/
    /**
     * Update existing cart row with new item data
     * @param {Object} item - Cart item data
     */
    updateCartRow(item) {
        const row = document.getElementById(`cart-item-${item.id}`);
        if (!row) {
            return this.addCartRow(item);
        }

        const qtyInput = row.querySelector('.quantity-input');
        const priceInput = row.querySelector('.price-input');
        const amountCell = row.querySelector('.amount-cell');
        const discountCell = row.querySelector('.discount-cell');
        const priceToggleCell = row.querySelector('.price-toggle-cell');

        if (qtyInput) qtyInput.value = item.quantity;
        if (priceInput) priceInput.value = item.price;
        if (amountCell) amountCell.textContent = this.format(item.amount);

        if (discountCell) {
            if (item.discount_percentage !== undefined) {
                discountCell.textContent = `${item.discount_percentage}%`;
            } else {
                const selling = parseFloat(priceToggleCell?.dataset.sellingPrice) || 0;
                const discount = this.calcDiscount(selling, item.price);
                discountCell.textContent = `${discount.toFixed(2)}%`;
            }
        }

        this.recalculateTotals();
    }

    /**
     * Add new cart row to the table
     * @param {Object} data - Cart item data with product variant information
     */
    addCartRow(data) {
        const {
            id,
            quantity,
            price,
            amount,
            product_variant: {
                barcode = 'N/A',
                brand = 'N/A',
                simple_name: variantName = 'N/A',
                mrp: sellingPrice = data.price || '0.00',
                purchase_price: purchasePrice = '0.00',
                discount_percentage: discount = 0,
            } = {},
        } = data;

        // Calculate discount if not provided
        let calculatedDiscount = discount;
        if (sellingPrice > 0 && data.price) {
            calculatedDiscount = this.calcDiscount(sellingPrice, data.price);
        }

        // Get current price toggle state (default to selling price)
        const isShowingPurchasePrice = this.priceToggleState;
        const displayPrice = isShowingPurchasePrice ? parseFloat(purchasePrice) : parseFloat(sellingPrice);
        const priceDisplay = this.formatPriceAnimation(displayPrice);

        const row = document.createElement('tr');
        row.id = `cart-item-${id}`;
        row.innerHTML = `
            <td>${barcode}</td>
            <td>${brand}</td>
            <td>${variantName}</td>
            <td class="price-toggle-cell"
                data-selling-price="${sellingPrice}"
                data-purchase-price="${purchasePrice}">
                <span class="price-display">${priceDisplay}</span>
            </td>
            <td>
                <input type="number" class="form-input quantity-input" value="${quantity}" 
                       data-item-id="${id}" min="0.01" step="1" 
                       title="Press Enter to update" aria-label="Quantity">
            </td>
            <td>
                <input type="number" class="form-input price-input" value="${price}" 
                       data-item-id="${id}" min="0" step="1" 
                       title="Press Enter to update" aria-label="Price">
            </td>
            <td class="discount-cell">${calculatedDiscount.toFixed(2)}%</td>
            <td class="amount-cell">${this.format(amount)}</td>
            <td>
                <button type="button" class="btn btn-primary update-item-btn" data-item-id="${id}" 
                        title="Save changes" aria-label="Save item changes">
                    <i class="fas fa-save" aria-hidden="true"></i>
                </button>
                <button type="button" class="btn btn-danger delete-item-btn" data-item-id="${id}" 
                        title="Remove item" aria-label="Remove item from cart">
                    <i class="fas fa-trash" aria-hidden="true"></i>
                </button>
            </td>
        `;

        // Add new items at the top
        if (this.dom.body.firstChild) {
            this.dom.body.insertBefore(row, this.dom.body.firstChild);
        } else {
            this.dom.body.appendChild(row);
        }

        this.recalculateTotals();
    }

    /**
     * Update total amount displays
     * @param {number} total - New total amount
     */
    updateTotals(total) {
        this.dom.totalAmount.textContent = this.format(total);
        // Update cart button total if it exists
        const cartButtonTotal = document.getElementById(`cart-button-total-${this.cartId}`);
        if (cartButtonTotal) {
            cartButtonTotal.textContent = this.format(total);
        }
        // Recalculate derived totals (quantity, selling price)
        this.recalculateTotals();
    }

    /**
     * Unified method to recalculate all totals (quantity and selling price)
     * More efficient than separate methods - single DOM scan
     */
    recalculateTotals() {
        if (!this.dom.body) return;

        const rows = this.dom.body.querySelectorAll('tr');

        if (rows.length === 0) {
            if (this.dom.totalItems) this.dom.totalItems.textContent = '0';
            if (this.dom.totalSelling) this.dom.totalSelling.textContent = this.format(0);
            return;
        }

        let totalQty = 0;
        let totalSelling = 0;

        rows.forEach(row => {
            const qtyInput = row.querySelector('.quantity-input');
            const priceToggleCell = row.querySelector('.price-toggle-cell');

            if (qtyInput && priceToggleCell) {
                const qty = parseFloat(qtyInput.value) || 0;
                const sell = parseFloat(priceToggleCell.dataset.sellingPrice) || 0;

                if (!isNaN(qty)) {
                    totalQty += qty;
                }
                if (!isNaN(qty) && !isNaN(sell) && qty > 0 && sell > 0) {
                    totalSelling += qty * sell;
                }
            }
        });

        // Round and format
        const roundedQty = Math.round(totalQty * 100) / 100;
        const roundedSelling = Math.round(totalSelling * 100) / 100;

        if (this.dom.totalItems) {
            this.dom.totalItems.textContent = roundedQty.toFixed(2);
        }
        if (this.dom.totalSelling) {
            this.dom.totalSelling.textContent = this.format(isNaN(roundedSelling) || !isFinite(roundedSelling) ? 0 : roundedSelling);
        }
    }

    /**
     * Legacy method for backward compatibility - returns totals data
     * @deprecated This method is kept for backward compatibility only.
     * Use recalculateTotals() for UI updates. This will be removed in future versions.
     * @returns {Object} Object containing totalItems, totalQuantity, and quantity arrays
     */
    calculateTotals() {
        if (!this.dom.body) {
            return { totalItems: 0, totalQuantity: 0, quantityInputs: [], quantities: [] };
        }

        const rows = this.dom.body.querySelectorAll('tr');
        const allQuantityInputs = this.dom.body.querySelectorAll('.quantity-input');
        const quantityInputsArray = Array.from(allQuantityInputs);

        const quantities = quantityInputsArray.map(input => parseFloat(input.value) || 0);
        const totalQuantity = quantities.reduce((sum, qty) => sum + qty, 0);

        return {
            totalItems: rows.length,
            totalQuantity,
            quantityInputs: quantityInputsArray,
            quantities,
        };
    }

    rollbackItemUpdate(itemId, originalValues) {
        if (!originalValues) return;

        const row = document.getElementById(`cart-item-${itemId}`);
        if (!row) {
            console.warn(`Rollback failed: Item ${itemId} not found`);
            return;
        }

        const qtyInput = row.querySelector('.quantity-input');
        const priceInput = row.querySelector('.price-input');
        const amountCell = row.querySelector('.amount-cell');
        const discountCell = row.querySelector('.discount-cell');

        if (qtyInput && originalValues.quantity) {
            qtyInput.value = originalValues.quantity;
        }
        if (priceInput && originalValues.price) {
            priceInput.value = originalValues.price;
        }
        if (amountCell && originalValues.amount) {
            amountCell.textContent = originalValues.amount;
        }
        if (discountCell && originalValues.discount) {
            discountCell.textContent = originalValues.discount;
        }
        if (originalValues.totalAmount) {
            this.dom.totalAmount.textContent = originalValues.totalAmount;
            // Also update cart button total
            const cartButtonTotal = document.getElementById(`cart-button-total-${this.cartId}`);
            if (cartButtonTotal) {
                cartButtonTotal.textContent = originalValues.totalAmount;
            }
        }

        console.warn(`Rolled back update for item ${itemId}`);
        this.recalculateTotals();
    }

    /*** ───────── CART ACTIONS ───────── ***/
    /**
     * Archive current cart and redirect to cart list
     */
    async archiveCart() {
        // Disable buttons to prevent double-click
        if (this.dom.archiveBtn) {
            this.dom.archiveBtn.disabled = true;
            this.dom.archiveBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Archiving...';
        }

        try {
            const data = await this.api(this.urls.archiveCart, 'POST');
            if (data.status === 'success') {
                this.notify('Cart archived successfully', 'success');
                setTimeout(() => (window.location.href = '/cart/'), CartManager.REDIRECT_DELAY);
            } else {
                this.notify(data.message || 'Failed to archive cart', 'error');
                if (this.dom.archiveBtn) {
                    this.dom.archiveBtn.disabled = false;
                    this.dom.archiveBtn.innerHTML = '<i class="fas fa-archive"></i> Archive Cart';
                }
            }
        } catch (err) {
            console.error('[CartManager] Error archiving cart:', err);
            this.notify('Failed to archive cart. Please try again.', 'error');
            if (this.dom.archiveBtn) {
                this.dom.archiveBtn.disabled = false;
                this.dom.archiveBtn.innerHTML = '<i class="fas fa-archive"></i> Archive Cart';
            }
        }
    }

    /**
     * Clear all items from current cart
     */
    async clearCart() {
        // Disable buttons to prevent double-click
        if (this.dom.clearBtn) {
            this.dom.clearBtn.disabled = true;
            this.dom.clearBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Clearing...';
        }

        try {
            const data = await this.api(this.urls.clearCart, 'POST');
            if (data.status === 'success') {
                this.notify('Cart cleared successfully', 'success');
                if (this.dom.body) {
                    this.dom.body.innerHTML = '';
                }
                this.updateTotals(0);
            } else {
                this.notify(data.message || 'Failed to clear cart', 'error');
            }
        } catch (err) {
            console.error('[CartManager] Error clearing cart:', err);
            this.notify('Failed to clear cart. Please try again.', 'error');
        } finally {
            // Re-enable button
            if (this.dom.clearBtn) {
                this.dom.clearBtn.disabled = false;
                this.dom.clearBtn.innerHTML = '<i class="fas fa-trash"></i> Clear Cart';
            }
        }
    }

    /*** ───────── UI UTILITIES ───────── ***/
    /**
     * Show confirmation modal with custom message
     * @param {string} title - Modal title
     * @param {string} msg - Confirmation message
     * @param {Function} cb - Callback to execute on confirmation
     */
    confirm(title, msg, cb) {
        const modal = document.getElementById('confirmModal');
        if (!modal) {
            // Fallback to native confirm if modal not available
            if (window.confirm(`${title}\n\n${msg}`)) {
                cb();
            }
            return;
        }

        const modalTitle = modal.querySelector('.modal-title') || document.getElementById('confirmModalLabel');
        const modalBody = modal.querySelector('.modal-body') || document.getElementById('confirmModalBody');
        const confirmBtn = modal.querySelector('#confirmActionBtn') || document.getElementById('confirmActionBtn');

        if (!modalTitle || !modalBody || !confirmBtn) {
            // Fallback if modal structure is incomplete
            if (window.confirm(`${title}\n\n${msg}`)) {
                cb();
            }
            return;
        }

        modalTitle.textContent = title;
        modalBody.textContent = msg;

        // Remove previous event listener to prevent memory leak
        const newConfirmBtn = confirmBtn.cloneNode(true);
        confirmBtn.parentNode.replaceChild(newConfirmBtn, confirmBtn);

        // Add new event listener
        newConfirmBtn.addEventListener('click', () => {
            cb();
            this.hideModal(modal);
        });

        // Show modal with Bootstrap or fallback
        this.showModal(modal);
    }

    /**
     * Show modal using Bootstrap or fallback
     * @param {HTMLElement} modal - Modal element
     * @private
     */
    showModal(modal) {
        if (typeof bootstrap !== 'undefined' && bootstrap.Modal) {
            const bootstrapModal = new bootstrap.Modal(modal);
            bootstrapModal.show();
        } else {
            // Fallback: manual modal display
            modal.style.display = 'block';
            modal.classList.add('show');
            document.body.classList.add('modal-open');

            // Create backdrop
            const backdrop = document.createElement('div');
            backdrop.className = 'modal-backdrop fade show';
            backdrop.id = 'customModalBackdrop';
            document.body.appendChild(backdrop);
        }
    }

    /**
     * Hide modal using Bootstrap or fallback
     * @param {HTMLElement} modal - Modal element
     * @private
     */
    hideModal(modal) {
        if (typeof bootstrap !== 'undefined' && bootstrap.Modal) {
            const bootstrapModal = bootstrap.Modal.getInstance(modal);
            if (bootstrapModal) {
                bootstrapModal.hide();
            }
        } else {
            // Fallback: manual modal hide
            modal.style.display = 'none';
            modal.classList.remove('show');
            document.body.classList.remove('modal-open');

            // Remove backdrop
            const backdrop = document.getElementById('customModalBackdrop');
            if (backdrop) {
                backdrop.remove();
            }
        }
    }

    initDropdown() {
        const toggle = document.getElementById('cartOptionsDropdown');
        const menu = document.querySelector('.cart-dropdown .dropdown-menu');
        if (!toggle || !menu) return;

        // Try Bootstrap first
        if (typeof bootstrap !== 'undefined') {
            new bootstrap.Dropdown(toggle);
            return;
        }

        // Fallback: manual dropdown toggle
        toggle.addEventListener('click', e => {
            e.preventDefault();
            e.stopPropagation();

            const isOpen = menu.classList.contains('show');

            // Close all other dropdowns
            document.querySelectorAll('.dropdown-menu.show').forEach(m => m.classList.remove('show'));

            // Toggle current dropdown
            if (!isOpen) {
                menu.classList.add('show');
            }
        });

        // Close dropdown when clicking outside
        document.addEventListener('click', e => {
            if (!toggle.contains(e.target) && !menu.contains(e.target)) {
                menu.classList.remove('show');
            }
        });

        // Close dropdown when pressing Escape
        document.addEventListener('keydown', e => {
            if (e.key === 'Escape') {
                menu.classList.remove('show');
            }
        });
    }
}

// Initialize cart manager when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.cartManager = new CartManager();
});
