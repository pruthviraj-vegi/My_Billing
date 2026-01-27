/**
 * Optimized Visual Select to Styled Dropdown Converter
 * 
 * Key improvements:
 * - Better performance with DocumentFragment and RAF
 * - Proper state management
 * - Memory leak prevention with WeakMap
 * - Enhanced error handling and validation
 * - Improved accessibility with ARIA attributes
 * 
 * Usage:
 *   const dropdown = convertSelectToStyledDropdown('dateFilter', {
 *     onChange: (data) => {
 *       // data: { value, text, fromDate, toDate, type }
 *       console.log('Selection changed:', data);
 *     },
 *     onError: (error) => {
 *       console.error('Dropdown error:', error);
 *     }
 *   });
 * 
 *   // Clean up when done
 *   dropdown.destroy();
 */

(function () {
    'use strict';

    // Store instances using WeakMap to prevent memory leaks
    const instances = new WeakMap();

    // Shared RAF ID pool for position updates
    const rafIds = new WeakMap();

    // State management
    const createState = (initialValue) => ({
        currentValue: initialValue,
        isOpen: false,
        isInternalChange: false,
        customDates: { from: null, to: null }
    });

    // Utility: Request Animation Frame wrapper
    const scheduleUpdate = (element, callback) => {
        const existingRaf = rafIds.get(element);
        if (existingRaf) cancelAnimationFrame(existingRaf);

        const rafId = requestAnimationFrame(() => {
            callback();
            rafIds.delete(element);
        });

        rafIds.set(element, rafId);
    };

    // Utility: Date validation and conversion
    const dateUtils = {
        isValid: (dateStr) => {
            if (!dateStr) return false;
            const date = new Date(dateStr);
            return date instanceof Date && !isNaN(date.getTime());
        },

        convertToISO: (ddmmyyyy) => {
            if (!ddmmyyyy) return null;
            const parts = ddmmyyyy.split('-');
            if (parts.length !== 3) return null;

            const [day, month, year] = parts.map(p => parseInt(p, 10));
            if (isNaN(day) || isNaN(month) || isNaN(year)) return null;
            if (month < 1 || month > 12 || day < 1 || day > 31) return null;

            const iso = `${year}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
            return this.isValid(iso) ? iso : null;
        },

        validateRange: (fromDate, toDate) => {
            if (!fromDate || !toDate) return false;
            return new Date(fromDate) <= new Date(toDate);
        }
    };

    // Build DOM structure using DocumentFragment for better performance
    const buildDropdownStructure = (selectOptions, selectedText, ids) => {
        const fragment = document.createDocumentFragment();

        // Create wrapper
        const wrapper = document.createElement('div');
        wrapper.className = 'multipleSelection';
        wrapper.style.position = 'relative';

        // Create select box
        const selectBox = document.createElement('div');
        selectBox.className = 'selectBox';
        selectBox.id = ids.selectBox;
        selectBox.setAttribute('role', 'combobox');
        selectBox.setAttribute('aria-expanded', 'false');
        selectBox.setAttribute('aria-haspopup', 'listbox');
        selectBox.setAttribute('tabindex', '0');

        const selectBoxContent = document.createElement('p');
        selectBoxContent.className = 'mb-0';
        selectBoxContent.innerHTML = `<i class="fas fa-calendar me-1 select-icon"></i><span class="date-filter-label">${selectedText}</span>`;

        const downIcon = document.createElement('span');
        downIcon.className = 'down-icon';
        downIcon.innerHTML = '<i class="fas fa-chevron-down"></i>';

        selectBox.appendChild(selectBoxContent);
        selectBox.appendChild(downIcon);

        // Create dropdown panel
        const panel = document.createElement('div');
        panel.id = ids.panel;
        panel.className = 'date-dropdown-panel';
        panel.style.display = 'none';
        panel.setAttribute('role', 'listbox');

        const panelContent = document.createElement('div');
        panelContent.className = 'selectBox-cont selectBox-cont-one h-auto';

        // Build quick select options
        const quickSelectList = document.createElement('div');
        quickSelectList.className = 'date-list';
        quickSelectList.style.width = '100%';

        const ul = document.createElement('ul');
        ul.style.cssText = 'display: flex; flex-direction: column; gap: 0.5rem; width: 100%; padding: 0; margin: 0; list-style: none;';

        selectOptions.forEach(opt => {
            const li = document.createElement('li');
            li.style.cssText = 'width: 100%; margin: 0;';

            const btn = document.createElement('a');
            btn.href = '#';
            btn.className = 'btn date-btn';
            btn.setAttribute('data-value', opt.value);
            btn.setAttribute('role', 'option');
            btn.textContent = opt.text;
            btn.style.cssText = 'width: 100%; display: block; text-align: center; padding: 0.5rem 1rem; font-size: 0.875rem; border: 1px solid var(--border-color, #e2e8f0); background: var(--bg-surface, #ffffff); color: var(--text-primary, #1e293b); text-decoration: none; border-radius: 6px; transition: all 0.2s ease;';

            li.appendChild(btn);
            ul.appendChild(li);
        });

        quickSelectList.appendChild(ul);
        panelContent.appendChild(quickSelectList);

        // Build custom date inputs
        const customDateList = document.createElement('div');
        customDateList.className = 'date-list';
        customDateList.style.cssText = 'width: 100%; margin-top: 0.75rem;';

        const customUl = document.createElement('ul');
        customUl.style.cssText = 'display: flex; flex-direction: column; gap: 0.5rem; width: 100%; padding: 0; margin: 0; list-style: none;';

        // Date inputs row
        const dateRow = document.createElement('li');
        dateRow.style.cssText = 'display: flex; gap: 0.5rem; width: 100%; margin: 0;';

        const fromPicker = document.createElement('div');
        fromPicker.className = 'date-picker';
        fromPicker.style.cssText = 'flex: 1; min-width: 120px;';
        fromPicker.innerHTML = `<div class="form-custom cal-icon"><input class="form-input" type="text" id="${ids.fromDate}" placeholder="From: dd-mm-yyyy" readonly aria-label="From date"></div>`;

        const toPicker = document.createElement('div');
        toPicker.className = 'date-picker pe-0';
        toPicker.style.cssText = 'flex: 1; min-width: 120px;';
        toPicker.innerHTML = `<div class="form-custom cal-icon"><input class="form-input" type="text" id="${ids.toDate}" placeholder="To: dd-mm-yyyy" readonly aria-label="To date"></div>`;

        dateRow.appendChild(fromPicker);
        dateRow.appendChild(toPicker);

        // Submit button row
        const submitRow = document.createElement('li');
        submitRow.className = 'student-submit';
        submitRow.style.cssText = 'width: 100%; margin: 0;';

        const submitBtn = document.createElement('button');
        submitBtn.id = ids.submit;
        submitBtn.type = 'button';
        submitBtn.className = 'btn btn-primary';
        submitBtn.style.width = '100%';
        submitBtn.textContent = 'Submit';

        submitRow.appendChild(submitBtn);

        customUl.appendChild(dateRow);
        customUl.appendChild(submitRow);
        customDateList.appendChild(customUl);
        panelContent.appendChild(customDateList);

        panel.appendChild(panelContent);

        wrapper.appendChild(selectBox);
        wrapper.appendChild(panel);
        fragment.appendChild(wrapper);

        return { fragment, wrapper, selectBox, panel };
    };

    // Main converter function
    function convertSelectToStyledDropdown(selectId, options = {}) {
        const { onChange, onError } = options;

        // Error handler wrapper
        const handleError = (error, context) => {
            console.error(`[Dropdown ${selectId}] ${context}:`, error);
            if (onError && typeof onError === 'function') {
                try {
                    onError({ error, context, selectId });
                } catch (e) {
                    console.error('Error in onError callback:', e);
                }
            }
        };

        // Callback wrapper with error handling
        const triggerCallback = (data) => {
            if (!onChange || typeof onChange !== 'function') return;

            try {
                onChange(data);
            } catch (error) {
                handleError(error, 'onChange callback');
            }
        };

        const init = () => {
            const selectElement = document.getElementById(selectId);
            if (!selectElement) {
                handleError(new Error(`Element not found`), 'Initialization');
                return null;
            }

            // Check if already initialized
            if (instances.has(selectElement)) {
                console.warn(`Dropdown already initialized for #${selectId}`);
                return instances.get(selectElement);
            }

            // Extract options
            const selectOptions = Array.from(selectElement.options).map(opt => ({
                value: opt.value,
                text: opt.text,
                selected: opt.selected
            }));

            if (selectOptions.length === 0) {
                handleError(new Error('No options found in select'), 'Initialization');
                return null;
            }

            // Get initial selection
            const currentValue = selectElement.value;
            const selectedOption = selectOptions.find(opt =>
                opt.value === currentValue || opt.selected
            ) || selectOptions[0];

            // Generate unique IDs
            const timestamp = Date.now();
            const ids = {
                selectBox: `${selectId}_box_${timestamp}`,
                panel: `${selectId}_panel_${timestamp}`,
                fromDate: `${selectId}_from_${timestamp}`,
                toDate: `${selectId}_to_${timestamp}`,
                submit: `${selectId}_submit_${timestamp}`
            };

            // Create state
            const state = createState(selectedOption.value);

            // Build DOM
            const { fragment, wrapper, selectBox, panel } = buildDropdownStructure(
                selectOptions,
                selectedOption.text,
                ids
            );

            // Replace original select
            const parent = selectElement.parentNode;
            parent.replaceChild(wrapper, selectElement);

            // Create hidden select for form compatibility
            const hiddenSelect = document.createElement('select');
            hiddenSelect.name = selectElement.name || selectId;
            hiddenSelect.id = `${selectId}_hidden`;
            hiddenSelect.style.display = 'none';

            selectOptions.forEach(opt => {
                const option = document.createElement('option');
                option.value = opt.value;
                option.text = opt.text;
                if (opt.value === state.currentValue) {
                    option.selected = true;
                }
                hiddenSelect.appendChild(option);
            });

            wrapper.appendChild(hiddenSelect);

            // Get DOM references
            const label = wrapper.querySelector('.date-filter-label');
            const fromDateInput = document.getElementById(ids.fromDate);
            const toDateInput = document.getElementById(ids.toDate);
            const submitButton = document.getElementById(ids.submit);
            const dateButtons = panel.querySelectorAll('.date-btn');

            // Event listeners cleanup array
            const listeners = [];

            // DatePicker instances
            let fromDatePicker = null;
            let toDatePicker = null;

            // Initialize DatePickers
            const initDatePickers = () => {
                if (typeof DatePicker === 'undefined') return;

                if (!fromDatePicker && fromDateInput) {
                    try {
                        fromDatePicker = new DatePicker(`#${ids.fromDate}`, {
                            mode: 'single',
                            format: 'd-m-Y',
                            showIcon: true,
                            iconPosition: 'right',
                            clickOpens: true,
                            allowInput: false,
                            closeOnSelect: false,
                            onChange: (date) => {
                                if (date) {
                                    const isoDate = date.toISOString().split('T')[0];
                                    fromDateInput.setAttribute('data-iso-date', isoDate);
                                }
                            }
                        });
                    } catch (error) {
                        handleError(error, 'DatePicker initialization (from)');
                    }
                }

                if (!toDatePicker && toDateInput) {
                    try {
                        toDatePicker = new DatePicker(`#${ids.toDate}`, {
                            mode: 'single',
                            format: 'd-m-Y',
                            showIcon: true,
                            iconPosition: 'right',
                            clickOpens: true,
                            allowInput: false,
                            closeOnSelect: false,
                            onChange: (date) => {
                                if (date) {
                                    const isoDate = date.toISOString().split('T')[0];
                                    toDateInput.setAttribute('data-iso-date', isoDate);
                                }
                            }
                        });
                    } catch (error) {
                        handleError(error, 'DatePicker initialization (to)');
                    }
                }
            };

            // Position adjustment using RAF
            const adjustPosition = () => {
                if (!panel || !selectBox || panel.style.display !== 'block') return;

                // Reset positioning
                panel.style.left = '';
                panel.style.right = '';
                panel.style.top = '';
                panel.style.bottom = '';
                panel.style.maxHeight = '';
                panel.style.overflowY = '';
                panel.style.marginTop = '0.5rem';
                panel.style.marginBottom = '';

                const selectBoxRect = selectBox.getBoundingClientRect();
                const panelRect = panel.getBoundingClientRect();
                const viewportWidth = window.innerWidth;
                const viewportHeight = window.innerHeight;
                const minSpace = 20;

                // Horizontal adjustment
                let leftAdjust = 0;
                if (panelRect.right > viewportWidth - minSpace) {
                    leftAdjust = viewportWidth - panelRect.right - minSpace;
                } else if (panelRect.left < minSpace) {
                    leftAdjust = minSpace - panelRect.left;
                }

                if (leftAdjust !== 0) {
                    const currentLeft = parseFloat(getComputedStyle(panel).left) || 0;
                    panel.style.left = `${currentLeft + leftAdjust}px`;
                }

                // Vertical adjustment
                const spaceBelow = viewportHeight - selectBoxRect.bottom;
                const spaceAbove = selectBoxRect.top;
                const panelHeight = panelRect.height;

                if (spaceBelow < panelHeight + minSpace && spaceAbove > spaceBelow) {
                    // Show above
                    panel.style.top = 'auto';
                    panel.style.bottom = '100%';
                    panel.style.marginTop = '';
                    panel.style.marginBottom = '0.5rem';
                } else if (spaceBelow < panelHeight + minSpace) {
                    // Limit height
                    const maxHeight = spaceBelow - minSpace;
                    if (maxHeight > 100) {
                        panel.style.maxHeight = `${maxHeight}px`;
                        panel.style.overflowY = 'auto';
                    }
                }
            };

            // Toggle dropdown
            const toggleDropdown = (forceClose = false) => {
                const shouldOpen = forceClose ? false : !state.isOpen;

                state.isOpen = shouldOpen;
                panel.style.display = shouldOpen ? 'block' : 'none';
                selectBox.classList.toggle('active', shouldOpen);
                selectBox.setAttribute('aria-expanded', String(shouldOpen));

                if (shouldOpen) {
                    scheduleUpdate(panel, () => {
                        adjustPosition();
                        initDatePickers();
                    });
                }
            };

            // Select box click
            const handleSelectBoxClick = (e) => {
                e.stopPropagation();
                toggleDropdown();
            };
            selectBox.addEventListener('click', handleSelectBoxClick);
            listeners.push(() => selectBox.removeEventListener('click', handleSelectBoxClick));

            // Keyboard support
            const handleKeydown = (e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    toggleDropdown();
                } else if (e.key === 'Escape' && state.isOpen) {
                    toggleDropdown(true);
                }
            };
            selectBox.addEventListener('keydown', handleKeydown);
            listeners.push(() => selectBox.removeEventListener('keydown', handleKeydown));

            // Window resize/scroll handlers
            const handlePositionUpdate = () => {
                if (state.isOpen) {
                    scheduleUpdate(panel, adjustPosition);
                }
            };

            window.addEventListener('resize', handlePositionUpdate);
            window.addEventListener('scroll', handlePositionUpdate, true);
            listeners.push(() => {
                window.removeEventListener('resize', handlePositionUpdate);
                window.removeEventListener('scroll', handlePositionUpdate, true);
            });

            // Click outside to close
            const handleOutsideClick = (e) => {
                const isDatepickerClick = e.target.closest('.datepicker-container') ||
                    e.target.closest('.datepicker-popup') ||
                    e.target === fromDateInput ||
                    e.target === toDateInput;

                if (!panel.contains(e.target) &&
                    !selectBox.contains(e.target) &&
                    !isDatepickerClick &&
                    state.isOpen) {
                    toggleDropdown(true);
                }
            };
            document.addEventListener('click', handleOutsideClick);
            listeners.push(() => document.removeEventListener('click', handleOutsideClick));

            // Prevent dropdown close on date input click
            const stopProp = (e) => e.stopPropagation();
            [fromDateInput, toDateInput].filter(Boolean).forEach(input => {
                input.addEventListener('click', stopProp);
                listeners.push(() => input.removeEventListener('click', stopProp));
            });

            // Quick select buttons
            dateButtons.forEach(btn => {
                const handleBtnClick = (e) => {
                    e.preventDefault();

                    const value = btn.getAttribute('data-value');
                    const text = btn.textContent.trim();

                    state.currentValue = value;
                    state.isInternalChange = true;

                    hiddenSelect.value = value;
                    if (label) label.textContent = text;

                    toggleDropdown(true);

                    hiddenSelect.dispatchEvent(new Event('change', { bubbles: true }));

                    triggerCallback({
                        value,
                        text,
                        fromDate: null,
                        toDate: null,
                        type: 'quick_select'
                    });
                };

                btn.addEventListener('click', handleBtnClick);
                listeners.push(() => btn.removeEventListener('click', handleBtnClick));
            });

            // Custom date submit
            const handleSubmit = (e) => {
                e.preventDefault();

                if (!fromDateInput?.value || !toDateInput?.value) {
                    handleError(new Error('Both dates required'), 'Custom date submission');
                    return;
                }

                const fromDate = fromDateInput.getAttribute('data-iso-date') ||
                    dateUtils.convertToISO(fromDateInput.value);
                const toDate = toDateInput.getAttribute('data-iso-date') ||
                    dateUtils.convertToISO(toDateInput.value);

                if (!fromDate || !toDate) {
                    handleError(new Error('Invalid date format'), 'Custom date submission');
                    return;
                }

                if (!dateUtils.validateRange(fromDate, toDate)) {
                    handleError(new Error('From date must be before To date'), 'Custom date submission');
                    return;
                }

                state.customDates = { from: fromDate, to: toDate };
                state.isInternalChange = true;

                // Find or create custom option
                let customOption = Array.from(hiddenSelect.options).find(opt =>
                    opt.value === 'custom' || opt.value === 'full_date'
                );

                if (!customOption) {
                    customOption = document.createElement('option');
                    customOption.value = 'custom';
                    customOption.text = 'Custom Date';
                    hiddenSelect.appendChild(customOption);
                } else if (customOption.value === 'full_date') {
                    customOption.value = 'custom';
                    customOption.text = 'Custom Date';
                }

                hiddenSelect.value = 'custom';
                if (label) label.textContent = 'Custom Date';

                hiddenSelect.setAttribute('data-from-date', fromDate);
                hiddenSelect.setAttribute('data-to-date', toDate);

                toggleDropdown(true);

                hiddenSelect.dispatchEvent(new Event('change', { bubbles: true }));

                triggerCallback({
                    value: 'custom',
                    text: 'Custom Date',
                    fromDate,
                    toDate,
                    type: 'custom_date'
                });
            };

            if (submitButton) {
                submitButton.addEventListener('click', handleSubmit);
                listeners.push(() => submitButton.removeEventListener('click', handleSubmit));
            }

            // Listen for programmatic changes
            const handleHiddenSelectChange = () => {
                if (state.isInternalChange) {
                    state.isInternalChange = false;
                    return;
                }

                const selectedOption = hiddenSelect.options[hiddenSelect.selectedIndex];
                if (!selectedOption) return;

                if (label) label.textContent = selectedOption.text;

                const fromDate = hiddenSelect.getAttribute('data-from-date');
                const toDate = hiddenSelect.getAttribute('data-to-date');

                triggerCallback({
                    value: hiddenSelect.value,
                    text: selectedOption.text,
                    fromDate: fromDate || null,
                    toDate: toDate || null,
                    type: 'programmatic_change'
                });
            };

            hiddenSelect.addEventListener('change', handleHiddenSelectChange);
            listeners.push(() => hiddenSelect.removeEventListener('change', handleHiddenSelectChange));

            // Destroy method
            const destroy = () => {
                // Clean up listeners
                listeners.forEach(cleanup => {
                    try {
                        cleanup();
                    } catch (error) {
                        handleError(error, 'Cleanup');
                    }
                });

                // Destroy DatePickers
                [fromDatePicker, toDatePicker].forEach(picker => {
                    if (picker?.destroy) {
                        try {
                            picker.destroy();
                        } catch (error) {
                            handleError(error, 'DatePicker cleanup');
                        }
                    }
                });

                // Cancel any pending RAF
                const rafId = rafIds.get(panel);
                if (rafId) {
                    cancelAnimationFrame(rafId);
                    rafIds.delete(panel);
                }

                // Remove from instances map
                instances.delete(selectElement);

                // Restore original select
                if (wrapper.parentNode) {
                    wrapper.parentNode.replaceChild(selectElement, wrapper);
                }
            };

            // Create instance
            const instance = {
                wrapper,
                hiddenSelect,
                selectBox,
                panel,
                label,
                fromDateInput,
                toDateInput,
                submitButton,
                destroy,
                getState: () => ({ ...state }),
                getValue: () => hiddenSelect.value,
                setValue: (value) => {
                    const option = Array.from(hiddenSelect.options).find(opt => opt.value === value);
                    if (option) {
                        hiddenSelect.value = value;
                        hiddenSelect.dispatchEvent(new Event('change', { bubbles: true }));
                    }
                }
            };

            // Store instance
            instances.set(selectElement, instance);

            return instance;
        };

        // Initialize
        if (document.readyState === 'loading') {
            return new Promise(resolve => {
                document.addEventListener('DOMContentLoaded', () => resolve(init()));
            });
        } else {
            return init();
        }
    }

    // Export
    if (typeof window !== 'undefined') {
        window.convertSelectToStyledDropdown = convertSelectToStyledDropdown;
    }

    if (typeof module !== 'undefined' && module.exports) {
        module.exports = convertSelectToStyledDropdown;
    }
})();