/**
 * Simple Visual Select to Styled Dropdown Converter
 * Converts a plain select to a styled dropdown with custom date inputs
 * 
 * Handles everything automatically - just pass the select ID and optional callback
 * 
 * Usage:
 *   // Basic usage
 *   convertSelectToStyledDropdown('dateFilter')
 * 
 *   // With onChange callback
 *   convertSelectToStyledDropdown('dateFilter', {
 *     onChange: function(data) {
 *       // data contains: { value, text, fromDate, toDate, type }
 *       // value: selected option value (e.g., 'today', 'this_month', 'custom')
 *       // text: selected option text (e.g., 'Today', 'This Month', 'Custom Date')
 *       // fromDate: ISO date string (yyyy-mm-dd) if custom date selected, null otherwise
 *       // toDate: ISO date string (yyyy-mm-dd) if custom date selected, null otherwise
 *       // type: 'quick_select' | 'custom_date' | 'programmatic_change'
 *       
 *       console.log('Date filter changed:', data);
 *       // Your code to update data/reload dashboard/etc.
 *     }
 *   })
 */

function convertSelectToStyledDropdown(selectId, options = {}) {
    // Extract callback function from options
    const onChangeCallback = options.onChange || options.onChangeCallback || null;

    // Helper function to call callback with data
    const triggerCallback = (data) => {
        if (onChangeCallback && typeof onChangeCallback === 'function') {
            try {
                onChangeCallback(data);
            } catch (error) {
                console.error('Error in onChange callback:', error);
            }
        }
    };

    // Wait for DOM to be ready
    const init = () => {
        const selectElement = document.getElementById(selectId);
        if (!selectElement) {
            console.error(`Select element with ID "${selectId}" not found`);
            return null;
        }

        // Track cleanup functions
        const cleanup = [];

        // Get all options from select
        const selectOptions = Array.from(selectElement.options).map(opt => ({
            value: opt.value,
            text: opt.text,
            selected: opt.selected
        }));

        // Get selected option text - use current value if set, otherwise find selected option
        const currentValue = selectElement.value;
        let selectedOption = null;
        if (currentValue) {
            selectedOption = selectOptions.find(opt => opt.value === currentValue);
        }
        if (!selectedOption) {
            selectedOption = selectOptions.find(opt => opt.selected) || selectOptions[0];
        }
        const selectedText = selectedOption ? selectedOption.text : '';

        // Get parent container
        const parent = selectElement.parentNode;
        const wrapper = document.createElement('div');
        wrapper.className = 'multipleSelection';
        // Ensure wrapper has relative positioning for dropdown
        wrapper.style.position = 'relative';

        // Generate unique IDs
        const dateSelectBoxId = selectId + '_selectBox_' + Date.now();
        const checkBoxesId = selectId + '_checkBoxes_' + Date.now();
        const fromDateInputId = selectId + '_fromDate_' + Date.now();
        const toDateInputId = selectId + '_toDate_' + Date.now();
        const submitButtonId = selectId + '_submitButton_' + Date.now();

        // Create the styled dropdown HTML structure with custom date inputs
        wrapper.innerHTML = `
    <div class="selectBox" id="${dateSelectBoxId}">
      <p class="mb-0">
        <i class="fas fa-calendar me-1 select-icon"></i>
        <span class="date-filter-label">${selectedText}</span>
      </p>
      <span class="down-icon"><i class="fas fa-chevron-down"></i></span>
    </div>
    <div id="${checkBoxesId}" class="date-dropdown-panel" style="display: none;">
      <div class="selectBox-cont selectBox-cont-one h-auto">
        <div class="date-list" style="width: 100%;">
          <ul style="display: flex; flex-direction: column; gap: 0.5rem; width: 100%; padding: 0; margin: 0; list-style: none;">
            ${selectOptions.map(opt => `
              <li style="width: 100%; margin: 0;">
                <a href="#" class="btn date-btn" data-value="${opt.value}" style="width: 100%; display: block; text-align: center; padding: 0.5rem 1rem; font-size: 0.875rem; border: 1px solid var(--border-color, #e2e8f0); background: var(--bg-surface, #ffffff); color: var(--text-primary, #1e293b); text-decoration: none; border-radius: 6px; transition: all 0.2s ease;">${opt.text}</a>
              </li>
            `).join('')}
          </ul>
        </div>
        <div class="date-list" style="width: 100%; margin-top: 0.75rem;">
          <ul style="display: flex; flex-direction: column; gap: 0.5rem; width: 100%; padding: 0; margin: 0; list-style: none;">
            <li style="display: flex; gap: 0.5rem; width: 100%; margin: 0;">
              <div class="date-picker" style="flex: 1; min-width: 120px;">
                <div class="form-custom cal-icon">
                  <input class="form-input" type="text" id="${fromDateInputId}" placeholder="From: dd-mm-yyyy" readonly>
                </div>
              </div>
              <div class="date-picker pe-0" style="flex: 1; min-width: 120px;">
                <div class="form-custom cal-icon">
                  <input class="form-input" type="text" id="${toDateInputId}" placeholder="To: dd-mm-yyyy" readonly>
                </div>
              </div>
            </li>
            <li class="student-submit" style="width: 100%; margin: 0;">
              <button id="${submitButtonId}" type="button" class="btn btn-primary" style="width: 100%;">Submit</button>
            </li>
          </ul>
        </div>
      </div>
    </div>
  `;

        // Replace select with styled dropdown
        parent.replaceChild(wrapper, selectElement);

        // Create hidden select to maintain form compatibility
        const hiddenSelect = document.createElement('select');
        hiddenSelect.name = selectElement.name || selectId;
        hiddenSelect.id = selectId + '_hidden';
        hiddenSelect.style.display = 'none';

        // Add all options to hidden select (don't copy selected state - will be set explicitly)
        selectOptions.forEach(opt => {
            const option = document.createElement('option');
            option.value = opt.value;
            option.text = opt.text;
            // Don't set selected here - will be set explicitly based on currentFilter or original value
            hiddenSelect.appendChild(option);
        });

        wrapper.appendChild(hiddenSelect);

        // Get DOM elements
        const dateSelectBox = document.getElementById(dateSelectBoxId);
        const checkBoxes = document.getElementById(checkBoxesId);
        const dateButtons = checkBoxes.querySelectorAll('.date-btn');
        const label = wrapper.querySelector('.date-filter-label');
        const fromDateInput = document.getElementById(fromDateInputId);
        const toDateInput = document.getElementById(toDateInputId);
        const submitButton = document.getElementById(submitButtonId);

        // Initialize DatePickers (if DatePicker is available)
        let fromDatePicker = null;
        let toDatePicker = null;

        const initializeDatePickers = () => {
            if (typeof DatePicker === 'undefined') {
                console.warn('DatePicker.js not loaded - custom date inputs will not work');
                return;
            }

            if (!fromDatePicker && fromDateInput) {
                try {
                    fromDatePicker = new DatePicker(`#${fromDateInputId}`, {
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
                    // Update stored reference
                    if (window[selectId + '_styled']) {
                        window[selectId + '_styled'].fromDatePicker = fromDatePicker;
                    }
                } catch (error) {
                    console.error('Error initializing from date picker:', error);
                }
            }

            if (!toDatePicker && toDateInput) {
                try {
                    toDatePicker = new DatePicker(`#${toDateInputId}`, {
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
                    // Update stored reference
                    if (window[selectId + '_styled']) {
                        window[selectId + '_styled'].toDatePicker = toDatePicker;
                    }
                } catch (error) {
                    console.error('Error initializing to date picker:', error);
                }
            }
        };

        // Function to adjust dropdown position to stay within viewport
        const adjustDropdownPosition = () => {
            if (!checkBoxes || !dateSelectBox) return;

            // Reset all positioning styles first
            checkBoxes.style.left = '';
            checkBoxes.style.right = '';
            checkBoxes.style.top = '';
            checkBoxes.style.bottom = '';
            checkBoxes.style.maxHeight = '';
            checkBoxes.style.overflowY = '';
            checkBoxes.style.marginTop = '0.5rem';
            checkBoxes.style.marginBottom = '';

            // Force a reflow to get accurate measurements
            void checkBoxes.offsetHeight;

            const selectBoxRect = dateSelectBox.getBoundingClientRect();
            const dropdownRect = checkBoxes.getBoundingClientRect();
            const viewportWidth = window.innerWidth;
            const viewportHeight = window.innerHeight;

            // Calculate horizontal adjustments
            let leftAdjust = 0;
            if (dropdownRect.right > viewportWidth - 10) {
                // Dropdown goes off right edge - shift left
                leftAdjust = viewportWidth - dropdownRect.right - 10;
            } else if (dropdownRect.left < 10) {
                // Dropdown goes off left edge - shift right
                leftAdjust = 10 - dropdownRect.left;
            }

            if (leftAdjust !== 0) {
                const currentLeft = parseFloat(getComputedStyle(checkBoxes).left) || 0;
                checkBoxes.style.left = `${currentLeft + leftAdjust}px`;
            }

            // Calculate vertical adjustments
            const spaceBelow = viewportHeight - selectBoxRect.bottom;
            const spaceAbove = selectBoxRect.top;
            const dropdownHeight = dropdownRect.height;
            const minSpace = 20; // Minimum space from viewport edge

            if (spaceBelow < dropdownHeight + minSpace && spaceAbove > spaceBelow) {
                // Not enough space below, show above instead
                checkBoxes.style.top = 'auto';
                checkBoxes.style.bottom = '100%';
                checkBoxes.style.marginTop = '';
                checkBoxes.style.marginBottom = '0.5rem';
            } else {
                // Show below (default) - limit height if needed
                if (spaceBelow < dropdownHeight + minSpace) {
                    const maxHeight = spaceBelow - minSpace;
                    if (maxHeight > 100) { // Only limit if reasonable height
                        checkBoxes.style.maxHeight = `${maxHeight}px`;
                        checkBoxes.style.overflowY = 'auto';
                    }
                }
            }
        };

        // Toggle dropdown
        const dateSelectBoxClickHandler = (e) => {
            e.stopPropagation();
            const isActive = checkBoxes.style.display === 'block';
            checkBoxes.style.display = isActive ? 'none' : 'block';
            dateSelectBox.classList.toggle('active', !isActive);

            // Adjust position when opening
            if (!isActive) {
                // Small delay to ensure display is set
                setTimeout(() => {
                    adjustDropdownPosition();
                    initializeDatePickers();
                }, 10);
            }
        };

        if (dateSelectBox && checkBoxes) {
            dateSelectBox.addEventListener('click', dateSelectBoxClickHandler);
            cleanup.push(() => dateSelectBox.removeEventListener('click', dateSelectBoxClickHandler));
        }

        // Debounce utility for performance
        function debounce(func, wait) {
            let timeout;
            return function executedFunction(...args) {
                clearTimeout(timeout);
                timeout = setTimeout(() => func.apply(this, args), wait);
            };
        }

        // Debounced position adjustment (100ms delay for better performance)
        const debouncedAdjustPosition = debounce(() => {
            if (checkBoxes?.style.display === 'block') {
                adjustDropdownPosition();
            }
        }, 100);

        // Adjust position on window resize (debounced)
        const resizeHandler = () => {
            if (checkBoxes?.style.display === 'block') {
                debouncedAdjustPosition();
            }
        };
        window.addEventListener('resize', resizeHandler);
        cleanup.push(() => window.removeEventListener('resize', resizeHandler));

        // Adjust position on scroll (debounced)
        const scrollHandler = () => {
            if (checkBoxes?.style.display === 'block') {
                debouncedAdjustPosition();
            }
        };
        window.addEventListener('scroll', scrollHandler, true);
        cleanup.push(() => window.removeEventListener('scroll', scrollHandler, true));

        // Close dropdown when clicking outside (but not on datepicker)
        const closeHandler = (e) => {
            const isDatepickerClick = e.target.closest('.datepicker-container') ||
                e.target.closest('.datepicker-popup') ||
                e.target.closest('.datepicker-calendar') ||
                e.target.closest('.datepicker-day') ||
                e.target === fromDateInput ||
                e.target === toDateInput ||
                e.target.closest('.datepicker-input-wrapper');

            if (checkBoxes && dateSelectBox &&
                !checkBoxes.contains(e.target) &&
                !dateSelectBox.contains(e.target) &&
                !isDatepickerClick) {
                if (checkBoxes.style.display === 'block') {
                    checkBoxes.style.display = 'none';
                    dateSelectBox.classList.remove('active');
                }
            }
        };
        document.addEventListener('click', closeHandler);
        cleanup.push(() => document.removeEventListener('click', closeHandler));

        // Prevent dropdown from closing when clicking on date inputs
        const stopPropagationHandler = (e) => e.stopPropagation();

        [fromDateInput, toDateInput].filter(Boolean).forEach(input => {
            input.addEventListener('click', stopPropagationHandler);
            cleanup.push(() => input.removeEventListener('click', stopPropagationHandler));
        });

        // Helper: Convert dd-mm-yyyy to yyyy-mm-dd
        const convertToBackendFormat = (dateStr) => {
            if (!dateStr) return '';
            const parts = dateStr.split('-');
            if (parts.length === 3) {
                return `${parts[2]}-${parts[1]}-${parts[0]}`;
            }
            return dateStr;
        };

        // Handle option button clicks
        const buttonHandlers = new Map();

        dateButtons.forEach(btn => {
            const handler = (e) => {
                e.preventDefault();
                const value = btn.getAttribute('data-value');
                const text = btn.textContent.trim();

                // Update hidden select value
                hiddenSelect.value = value;

                // Update label (VISUAL ONLY)
                if (label) {
                    label.textContent = text;
                }

                // Close dropdown
                checkBoxes.style.display = 'none';
                dateSelectBox.classList.remove('active');

                // Mark as internal change to prevent duplicate callback
                isInternalChange = true;

                // Trigger change event on hidden select (so existing JS handlers can listen if needed)
                hiddenSelect.dispatchEvent(new Event('change', { bubbles: true }));

                // Call callback function with data
                triggerCallback({
                    value: value,
                    text: text,
                    fromDate: null,
                    toDate: null,
                    type: 'quick_select'
                });
            };
            btn.addEventListener('click', handler);
            buttonHandlers.set(btn, handler);
        });

        cleanup.push(() => {
            buttonHandlers.forEach((handler, btn) => {
                btn.removeEventListener('click', handler);
            });
            buttonHandlers.clear();
        });

        // Handle custom date submit button
        const submitButtonClickHandler = (e) => {
            e.preventDefault();

            if (fromDateInput && toDateInput && fromDateInput.value && toDateInput.value) {
                // Get ISO dates
                const fromDate = fromDateInput.getAttribute('data-iso-date') ||
                    convertToBackendFormat(fromDateInput.value);
                const toDate = toDateInput.getAttribute('data-iso-date') ||
                    convertToBackendFormat(toDateInput.value);

                // Find or create "custom" option (prefer 'custom' over 'full_date')
                let customOption = Array.from(hiddenSelect.options).find(opt =>
                    opt.value === 'custom'
                );

                // If no 'custom' option, check for 'full_date' and update it
                if (!customOption) {
                    customOption = Array.from(hiddenSelect.options).find(opt =>
                        opt.value === 'full_date'
                    );
                    if (customOption) {
                        // Update existing 'full_date' option to 'custom'
                        customOption.value = 'custom';
                        customOption.text = 'Custom Date';
                    }
                }

                // Create new option if still not found
                if (!customOption) {
                    customOption = document.createElement('option');
                    customOption.value = 'custom';
                    customOption.text = 'Custom Date';
                    hiddenSelect.appendChild(customOption);
                }

                // Set custom option as selected
                hiddenSelect.value = 'custom';

                // Always update label to "Custom Date"
                if (label) {
                    label.textContent = 'Custom Date';
                }

                // Also update the option text to ensure consistency
                customOption.text = 'Custom Date';

                // Close dropdown
                checkBoxes.style.display = 'none';
                dateSelectBox.classList.remove('active');

                // Store custom dates in data attributes for reference
                hiddenSelect.setAttribute('data-from-date', fromDate);
                hiddenSelect.setAttribute('data-to-date', toDate);

                // Mark as internal change to prevent duplicate callback
                isInternalChange = true;

                // Trigger change event
                hiddenSelect.dispatchEvent(new Event('change', { bubbles: true }));

                // Call callback function with custom date data
                triggerCallback({
                    value: 'custom',
                    text: 'Custom Date',
                    fromDate: fromDate,
                    toDate: toDate,
                    type: 'custom_date'
                });
            }
        };

        if (submitButton) {
            submitButton.addEventListener('click', submitButtonClickHandler);
            cleanup.push(() => submitButton.removeEventListener('click', submitButtonClickHandler));
        }

        // Track if change was triggered by our handlers (to avoid duplicate callbacks)
        let isInternalChange = false;

        // Also listen to programmatic changes on hidden select (only if not triggered internally)
        const hiddenSelectChangeHandler = () => {
            // Skip if this change was triggered by our internal handlers
            if (isInternalChange) {
                isInternalChange = false;
                return;
            }

            const selectedOption = hiddenSelect.options[hiddenSelect.selectedIndex];
            if (selectedOption) {
                const fromDate = hiddenSelect.getAttribute('data-from-date');
                const toDate = hiddenSelect.getAttribute('data-to-date');

                triggerCallback({
                    value: hiddenSelect.value,
                    text: selectedOption.text,
                    fromDate: fromDate || null,
                    toDate: toDate || null,
                    type: 'programmatic_change'
                });
            }
        };
        hiddenSelect.addEventListener('change', hiddenSelectChangeHandler);
        cleanup.push(() => hiddenSelect.removeEventListener('change', hiddenSelectChangeHandler));

        // Auto-update label when hidden select value changes (for programmatic changes)
        const hiddenSelectLabelUpdateHandler = () => {
            if (label && hiddenSelect.selectedIndex >= 0) {
                const selectedOption = hiddenSelect.options[hiddenSelect.selectedIndex];
                if (selectedOption) {
                    label.textContent = selectedOption.text;
                }
            }
        };
        hiddenSelect.addEventListener('change', hiddenSelectLabelUpdateHandler);
        cleanup.push(() => hiddenSelect.removeEventListener('change', hiddenSelectLabelUpdateHandler));

        // Destroy method to clean up all resources
        const destroy = () => {
            // Run all cleanup functions
            cleanup.forEach(fn => {
                try {
                    fn();
                } catch (error) {
                    console.error('Error during cleanup:', error);
                }
            });

            // Destroy DatePicker instances
            if (fromDatePicker && typeof fromDatePicker.destroy === 'function') {
                try {
                    fromDatePicker.destroy();
                } catch (error) {
                    console.error('Error destroying fromDatePicker:', error);
                }
            }
            if (toDatePicker && typeof toDatePicker.destroy === 'function') {
                try {
                    toDatePicker.destroy();
                } catch (error) {
                    console.error('Error destroying toDatePicker:', error);
                }
            }

            // Remove global reference
            delete window[selectId + '_styled'];
        };

        // Store reference globally for easy access (accessible as window.dateFilter_styled, etc.)
        const instance = {
            wrapper: wrapper,
            hiddenSelect: hiddenSelect,
            dateSelectBox: dateSelectBox,
            checkBoxes: checkBoxes,
            label: label,
            fromDateInput: fromDateInput,
            toDateInput: toDateInput,
            submitButton: submitButton,
            fromDatePicker: fromDatePicker,
            toDatePicker: toDatePicker,
            destroy: destroy
        };

        window[selectId + '_styled'] = instance;

        // Return instance with destroy method
        return instance;
    };

    // If DOM is ready, init immediately, otherwise wait
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        // Small delay to ensure select is in DOM
        setTimeout(() => init(), 10);
    }
}

// Export for use
if (typeof window !== 'undefined') {
    window.convertSelectToStyledDropdown = convertSelectToStyledDropdown;
}


