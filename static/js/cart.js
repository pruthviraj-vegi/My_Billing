/**
 * Optimized CartManager
 * Handles cart CRUD, barcode scanning, and real-time totals
 * Optimized for performance, readability, and maintainability
 */

class CartManager {
    constructor() {
        this.initGlobals();
        this.initDOM();
        this.initListeners();
        this.focusBarcode();

        if (this.dom.totalSelling && this.dom.body) {
            setTimeout(() => this.recalculateTotals(), 50);
        }
    }

    /*** ───────── INITIALIZATION ───────── ***/
    initGlobals() {
        if (!window.CART_DATA) {
            console.error('CART_DATA missing. Make sure the template is properly loaded.');
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
        };

        // Initialize price toggle state
        this.priceToggleState = false;
        window.cartPriceToggleState = false; // Keep global for backward compatibility
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

    /*** ───────── HELPERS ───────── ***/
    format(num) {
        const n = typeof num === 'string' ? parseFloat(num.replace(/[^\d.-]/g, '')) : parseFloat(num);
        return isNaN(n) || !isFinite(n) ? '0.00' : this.formatter.format(n);
    }

    calcDiscount(selling, price) {
        return selling > 0 ? Math.max(0, ((selling - price) / selling) * 100) : 0;
    }

    async api(url, method = 'GET', body = null) {
        try {
            const opts = {
                method,
                headers: {
                    'X-CSRFToken': this.csrf,
                    'Content-Type': 'application/json',
                },
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
            // Re-throw for caller to handle - they can provide context-specific messages
            throw err;
        }
    }

    focusBarcode() {
        this.dom.input?.focus();
    }

    notify(msg, type = 'info') {
        if (typeof showNotification === 'function') {
            showNotification(msg, type);
        } else {
            console.log(`[${type.toUpperCase()}] ${msg}`);
        }
    }

    /*** ───────── PRICE TOGGLE ───────── ***/
    initPriceToggle() {
        // Initialize price display format after DOM is ready
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => this.formatPriceDisplays());
        } else {
            // DOM already loaded
            setTimeout(() => this.formatPriceDisplays(), 50);
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

    animatePriceChange(element, startValue, endValue, duration = 300) {
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

    togglePriceDisplay() {
        this.priceToggleState = !this.priceToggleState;
        window.cartPriceToggleState = this.priceToggleState; // Keep global for backward compatibility

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
                this.animatePriceChange(displaySpan, currentPrice, targetPrice, 300);
            }
        });
    }

    /*** ───────── UI EVENTS ───────── ***/
    async onBarcodeSubmit(e) {
        e.preventDefault();
        const code = this.dom.input.value.trim();

        // Simple validation - no guard needed for barcode scanner
        if (!code) {
            this.notify('Please enter a barcode', 'error');
            this.focusBarcode();
            return;
        }

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

            if (data.cart_total !== undefined) {
                this.updateTotals(data.cart_total);
            } else {
                this.recalculateTotals();
            }
        } catch (err) {
            console.error('Error in barcode submission:', err);
            this.notify(`Error adding product to cart: ${err.message}`, 'error');
        } finally {
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

        this.recalculateTotals();
    }

    /*** ───────── CRUD OPS ───────── ***/
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

        if (!qty || !price || qty <= 0 || price < 0) {
            return this.notify('Please enter valid quantity and price', 'error');
        }

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

            this.recalculateTotals();

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
            }

            this.updateTotals(data.cart_total);
            this.recalculateTotals();
        } catch (err) {
            // console.error('Error updating item:', err);
            this.rollbackItemUpdate(id, originalValues);
            this.notify(err.message || 'Update failed - values restored', 'error');
        } finally {
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = '<i class="fas fa-save"></i>';
            }
            this.focusBarcode();
        }
    }

    async deleteItem(id) {
        if (!confirm('Are you sure you want to remove this item?')) return;

        const row = document.getElementById(`cart-item-${id}`);
        if (!row) {
            return this.notify('Item not found', 'error');
        }

        const btn = row.querySelector('.delete-item-btn');
        if (btn) {
            btn.disabled = true;
            btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
        }

        row.style.opacity = '0.5';

        try {
            const data = await this.api(this.urls.manageItem.replace('0', id), 'DELETE');

            if (data.status !== 'success') {
                row.style.opacity = '1';
                if (btn) {
                    btn.disabled = false;
                    btn.innerHTML = '<i class="fas fa-trash"></i>';
                }
                throw new Error(data.message || 'Delete failed');
            }

            row.remove();
            this.updateTotals(data.cart_total);
            this.recalculateTotals();
            this.notify('Item removed successfully', 'success');
        } catch (err) {
            console.error('Error deleting item:', err);
            row.style.opacity = '1';
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = '<i class="fas fa-trash"></i>';
            }
            this.notify(err.message || 'Network error - item not removed', 'error');
        } finally {
            this.focusBarcode();
        }
    }

    /*** ───────── UI UPDATES ───────── ***/
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
        const isShowingPurchasePrice = this.priceToggleState || window.cartPriceToggleState || false;
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
                       data-item-id="${id}" min="0.01" step="0.01" 
                       title="Press Enter to update">
            </td>
            <td>
                <input type="number" class="form-input price-input" value="${price}" 
                       data-item-id="${id}" min="0" step="0.01" 
                       title="Press Enter to update">
            </td>
            <td class="discount-cell">${calculatedDiscount.toFixed(2)}%</td>
            <td class="amount-cell">${this.format(amount)}</td>
            <td>
                <button type="button" class="btn btn-primary update-item-btn" data-item-id="${id}" 
                        title="Save changes">
                    <i class="fas fa-save"></i>
                </button>
                <button type="button" class="btn btn-danger delete-item-btn" data-item-id="${id}" 
                        title="Remove item">
                    <i class="fas fa-trash"></i>
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

    updateTotals(total) {
        this.dom.totalAmount.textContent = this.format(total);
        // Update cart button total if it exists
        const cartButtonTotal = document.getElementById(`cart-button-total-${this.cartId}`);
        if (cartButtonTotal) {
            cartButtonTotal.textContent = this.format(total);
        }
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
     * @deprecated Use recalculateTotals() instead
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
    async archiveCart() {
        try {
            const data = await this.api(this.urls.archiveCart, 'POST');
            if (data.status === 'success') {
                this.notify('Cart archived successfully', 'success');
                setTimeout(() => (window.location.href = '/cart/'), 1500);
            } else {
                this.notify(data.message || 'Failed to archive cart', 'error');
            }
        } catch (err) {
            console.error('Error archiving cart:', err);
            this.notify('Failed to archive cart', 'error');
        }
    }

    async clearCart() {
        try {
            const data = await this.api(this.urls.clearCart, 'POST');
            if (data.status === 'success') {
                this.notify('Cart cleared successfully', 'success');
                if (this.dom.body) {
                    this.dom.body.innerHTML = '';
                }
                this.updateTotals(0);
                this.recalculateTotals();
            } else {
                this.notify(data.message || 'Failed to clear cart', 'error');
            }
        } catch (err) {
            console.error('Error clearing cart:', err);
            this.notify('Failed to clear cart', 'error');
        }
    }

    /*** ───────── UI UTILITIES ───────── ***/
    confirm(title, msg, cb) {
        const modal = document.getElementById('confirmModal');
        if (!modal) return cb();

        const modalTitle = modal.querySelector('.modal-title') || document.getElementById('confirmModalLabel');
        const modalBody = modal.querySelector('.modal-body') || document.getElementById('confirmModalBody');
        const confirmBtn = modal.querySelector('#confirmActionBtn') || document.getElementById('confirmActionBtn');

        if (!modalTitle || !modalBody || !confirmBtn) return cb();

        modalTitle.textContent = title;
        modalBody.textContent = msg;

        // Simplified: Use onclick for cleaner lifecycle
        confirmBtn.onclick = () => {
            cb();
            const bootstrapModal = bootstrap.Modal.getInstance(modal);
            if (bootstrapModal) {
                bootstrapModal.hide();
            }
        };

        // Show modal
        const bootstrapModal = new bootstrap.Modal(modal);
        bootstrapModal.show();
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
