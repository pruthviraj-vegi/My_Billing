/**
 * WordSuggestion - Flexible Autocomplete / Spell Suggestion System
 *
 * WHY THIS DESIGN?
 * ----------------
 * - Debouncing: avoids firing too many network requests on fast typing.
 * - AbortController: cancels stale fetches so only the latest query counts.
 * - Accessibility (ARIA): adds roles, aria-controls, aria-autocomplete for screen readers.
 * - Event-driven: supports both callback & custom events for integration flexibility.
 * - Cleanup: destroy() removes listeners, aborts fetches → prevents memory leaks.
 * - Safe keyboard navigation: handles Enter, Tab, Esc, Arrows gracefully.
 * - Configurable: accepts options for min length, debounce delay, etc.
 *
 * NOTE: Instead of relying on jQuery-style plugins (`$('#id')...`), this class is vanilla JS.
 * Use `initWordSuggestion(inputElement, url, options)` to initialize.
 */

class WordSuggestion {
    constructor(inputElement, suggestionUrl, options = {}) {
        this.input = inputElement;
        this.options = {
            debounceDelay: 300,
            minQueryLength: 2,
            maxSuggestions: 5,
            url: suggestionUrl || "",
            onSuggestionSelected: null, // optional callback
            allowSpaces: false, // configurable space handling
            ...options
        };

        this.suggestions = [];
        this.selectedIndex = -1;
        this.debounceTimer = null;
        this.dropdown = null;
        this.abortController = null;

        // Bind methods to instance
        this.boundHandleInput = (e) => this.handleInput(e);
        this.boundHandleKeydown = (e) => this.handleKeydown(e);
        this.boundHandleFocus = () => this.handleFocus();
        this.boundHandleBlur = (e) => this.handleBlur(e);
        this.boundHandleClickOutside = (e) => this.handleClickOutside(e);

        this.init();
    }

    // ----------- INIT -----------
    init() {
        // Store focus state before initialization
        const hadFocus = document.activeElement === this.input;

        this.createDropdown();
        this.bindEvents();

        // Restore focus if input had it before
        if (hadFocus) {
            this.input.focus();
        }
    }

    createDropdown() {
        this.dropdown = document.createElement('div');
        this.dropdown.className = 'word-suggestion-dropdown';
        this.dropdown.setAttribute('role', 'listbox');
        this.dropdown.setAttribute('aria-live', 'polite');
        this.dropdown.id = `dropdown-${Math.random().toString(36).substr(2, 9)
            }`;
        this.dropdown.style.display = 'none';

        this.input.setAttribute('aria-autocomplete', 'list');
        this.input.setAttribute('aria-controls', this.dropdown.id);

        // Find the best container for the dropdown
        // Prefer explicit containers or direct parent over modal body to keep it near the input
        const container = this.input.closest('.search-input-container') ||
            this.input.closest('.input-group') ||
            this.input.parentNode;

        // Set position relative on container to ensure dropdown is positioned correctly
        if (container) {
            const computedStyle = window.getComputedStyle(container);
            if (computedStyle.position === 'static') {
                container.style.position = 'relative';
            }
        }

        container.appendChild(this.dropdown);
    }

    bindEvents() {
        this.input.addEventListener('input', this.boundHandleInput);
        this.input.addEventListener('keydown', this.boundHandleKeydown);
        this.input.addEventListener('focus', this.boundHandleFocus);
        this.input.addEventListener('blur', this.boundHandleBlur);

        // Click handler will be attached only when dropdown is visible (optimized)
    }

    // ----------- HANDLERS -----------

    handleInput(e) {
        const query = e.target.value.trim();
        clearTimeout(this.debounceTimer);

        if (query.length < this.options.minQueryLength || (!this.options.allowSpaces && query.includes(' '))) {
            this.hideDropdown();
            return;
        }

        this.debounceTimer = setTimeout(() => {
            this.searchSuggestions(query);
        }, this.options.debounceDelay)





    }

    handleKeydown(e) {
        if (!this.dropdown.classList.contains('show'))
            return;



        switch (e.key) {
            case 'ArrowDown':
                e.preventDefault();
                this.navigateDown();
                break;
            case 'ArrowUp':
                e.preventDefault();
                this.navigateUp();
                break;
            case 'Enter':
            case 'Tab': // Tab also accepts suggestion
                e.preventDefault();
                this.selectSuggestion();
                break;
            case 'Escape':
                e.preventDefault();
                this.hideDropdown();
                break;
        }
    }

    handleFocus() {
        if (this.suggestions.length > 0) {
            this.showDropdown();
        }
    }

    handleBlur(e) { // Close only if clicked outside both input and dropdown
        setTimeout(() => {
            if (!this.dropdown.contains(document.activeElement) && document.activeElement !== this.input) {
                this.hideDropdown();
            }
        }, 150);
    }

    handleClickOutside(e) {
        if (!this.input.contains(e.target) && !this.dropdown.contains(e.target)) {
            this.hideDropdown();
        }
    }

    // ----------- DATA FETCHING -----------

    async searchSuggestions(query) {
        if (this.abortController)
            this.abortController.abort();



        this.abortController = new AbortController();
        this.showLoading();

        try {
            const response = await fetch(`${this.options.url
                }?q=${encodeURIComponent(query)
                }`, { signal: this.abortController.signal });

            if (!response.ok)
                throw new Error(`HTTP ${response.status
                    }`);



            const data = await response.json();
            this.suggestions = data.data || [];
            this.selectedIndex = -1;

            if (this.suggestions.length > 0) {
                this.renderSuggestions();
                this.showDropdown();
            } else {
                this.showEmptyState();
                this.showDropdown();
            }
        } catch (error) {
            if (error.name !== 'AbortError') {
                console.error('Error fetching suggestions:', error);
                this.showErrorState();
                this.showDropdown();
            }
        }
    }

    // ----------- RENDER -----------

    renderSuggestions() {
        this.dropdown.innerHTML = '';
        this.suggestions.forEach((suggestion, index) => {
            const item = this.createSuggestionItem(suggestion, index);
            this.dropdown.appendChild(item);
        });
    }

    createSuggestionItem(suggestion, index) {
        const item = document.createElement('div');
        item.className = 'word-suggestion-item';
        item.dataset.index = index;
        item.setAttribute('role', 'option');
        item.setAttribute('aria-selected', index === this.selectedIndex);

        const wordSpan = document.createElement('span');
        wordSpan.className = 'suggestion-word';
        wordSpan.textContent = suggestion;

        item.appendChild(wordSpan);

        item.addEventListener('click', () => this.selectSuggestion(index));
        item.addEventListener('mouseenter', () => {
            this.selectedIndex = index;
            this.updateSelection();
        });

        return item;
    }

    showLoading() {
        this.dropdown.innerHTML = `
            <div class="word-suggestion-loading">
                <i class="fas fa-spinner fa-spin"></i>
                Finding suggestions...
            </div>
        `;
        this.showDropdown();
    }

    showEmptyState() {
        // Fix XSS vulnerability by using textContent
        const emptyDiv = document.createElement('div');
        emptyDiv.className = 'word-suggestion-empty';
        emptyDiv.innerHTML = '<i class="fas fa-search"></i>';

        const p = document.createElement('p');
        p.textContent = `No suggestions found for "${this.input.value}"`;
        emptyDiv.appendChild(p);

        this.dropdown.innerHTML = '';
        this.dropdown.appendChild(emptyDiv);
    }

    showErrorState() {
        this.dropdown.innerHTML = `
            <div class="word-suggestion-empty">
                <i class="fas fa-exclamation-triangle"></i>
                <p>Error loading suggestions. Please try again.</p>
            </div>
        `;
    }

    // ----------- NAVIGATION -----------

    navigateDown() {
        if (this.suggestions.length === 0)
            return;



        this.selectedIndex = (this.selectedIndex + 1) % this.suggestions.length;
        this.updateSelection();
    }

    navigateUp() {
        if (this.suggestions.length === 0)
            return;



        this.selectedIndex = (this.selectedIndex - 1 + this.suggestions.length) % this.suggestions.length;
        this.updateSelection();
    }

    updateSelection() {
        const items = this.dropdown.querySelectorAll('.word-suggestion-item');
        items.forEach((item, index) => {
            const isSelected = index === this.selectedIndex;
            item.classList.toggle('selected', isSelected);
            item.setAttribute('aria-selected', isSelected);
        });
    }

    // ----------- SELECTION -----------

    selectSuggestion(index = null) {
        const selectedIndex = index !== null ? index : this.selectedIndex;
        if (selectedIndex < 0 || selectedIndex >= this.suggestions.length)
            return;



        const suggestion = this.suggestions[selectedIndex];
        const currentValue = this.input.value;

        this.input.value = suggestion;
        this.hideDropdown();

        // Fire input-specific event
        this.input.dispatchEvent(new CustomEvent('wordSelected', {
            detail: {
                originalWord: currentValue,
                suggestedWord: suggestion,
                fullText: this.input.value
            }
        }));

        if (typeof this.options.onSuggestionSelected === 'function') {
            this.options.onSuggestionSelected(suggestion, this.input);
        }
    }

    // ----------- UTILS -----------

    showDropdown() {
        this.dropdown.classList.add('show');
        this.dropdown.style.display = 'block';
        // Only attach click handler when dropdown is visible (performance optimization)
        document.addEventListener('click', this.boundHandleClickOutside);
    }

    hideDropdown() {
        this.dropdown.classList.remove('show');
        this.dropdown.style.display = 'none';
        // Remove click handler when dropdown is hidden (performance optimization)
        document.removeEventListener('click', this.boundHandleClickOutside);
    }

    // ----------- PUBLIC METHODS -----------

    setUrl(url) {
        this.options.url = url;
    }

    clear() {
        this.input.value = '';
        this.suggestions = [];
        this.selectedIndex = -1;
        this.hideDropdown();
    }

    destroy() {
        if (this.dropdown)
            this.dropdown.remove();



        if (this.debounceTimer)
            clearTimeout(this.debounceTimer);



        if (this.abortController)
            this.abortController.abort();



        this.input.removeEventListener('input', this.boundHandleInput);
        this.input.removeEventListener('keydown', this.boundHandleKeydown);
        this.input.removeEventListener('focus', this.boundHandleFocus);
        this.input.removeEventListener('blur', this.boundHandleBlur);
        document.removeEventListener('click', this.boundHandleClickOutside);
    }
}

// Helper function
function initWordSuggestion(inputElement, suggestionUrl, options = {}) {
    if (!inputElement || !suggestionUrl) {
        console.error('WordSuggestion: inputElement and suggestionUrl are required');
        return null;
    }
    const instance = new WordSuggestion(inputElement, suggestionUrl, options);
    inputElement.wordSuggestion = instance;
    return instance;
}

// Make function globally available
window.initWordSuggestion = initWordSuggestion;

// Lightweight jQuery wrapper for word suggestions (only if jQuery not available)
if (typeof window.$ === 'undefined') {
    function $(selector) {
        const elements = typeof selector === "string" ? document.querySelectorAll(selector) : [selector];
        return {
            wordSuggestion: function (options = {}) {
                elements.forEach((element) => {
                    if (!element) return;

                    const config = {
                        url: options.url || "",
                        placeholder: options.placeholder || "Type to search...",
                        minLength: options.minLength || 2,
                        debounceDelay: options.debounceDelay || 300,
                        maxSuggestions: options.maxSuggestions || 5,
                        onSelect: options.onSelect || null,
                        ...options
                    };

                    if (!config.url) {
                        console.error("WordSuggestion: URL is required");
                        return;
                    }

                    initWordSuggestion(element, config.url, {
                        debounceDelay: config.debounceDelay,
                        minQueryLength: config.minLength,
                        maxSuggestions: config.maxSuggestions,
                        onSuggestionSelected: config.onSelect
                    });
                });
                return this;
            }
        };
    }
    window.$ = $;
} else {
    // Extend existing jQuery with wordSuggestion plugin
    window.$.fn.wordSuggestion = function (options = {}) {
        return this.each(function () {
            const element = this;
            const config = {
                url: options.url || "",
                placeholder: options.placeholder || "Type to search...",
                minLength: options.minLength || 2,
                debounceDelay: options.debounceDelay || 300,
                maxSuggestions: options.maxSuggestions || 5,
                onSelect: options.onSelect || null,
                ...options
            };

            if (!config.url) {
                console.error("WordSuggestion: URL is required");
                return;
            }

            initWordSuggestion(element, config.url, {
                debounceDelay: config.debounceDelay,
                minQueryLength: config.minLength,
                maxSuggestions: config.maxSuggestions,
                onSuggestionSelected: config.onSelect
            });
        });
    };
}

// Export for modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = WordSuggestion;
}
