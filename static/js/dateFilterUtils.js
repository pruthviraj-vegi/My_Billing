/**
 * ============================================================================
 * DATE FILTER UTILITY FUNCTIONS
 * ============================================================================
 * Reusable functions for handling date filter operations across the application.
 * 
 * BENEFITS:
 * - ✅ NO CODE DUPLICATION - Date logic in one place
 * - ✅ EASIER MAINTENANCE - Changes in one function apply everywhere
 * - ✅ CONSISTENT VALIDATION - Same validation rules across all features
 * - ✅ REUSABLE - Easy to add new features (email, print, etc.)
 * - ✅ BETTER ERROR HANDLING - Centralized error messages
 * - ✅ TESTABLE - Each function can be unit tested independently
 * ============================================================================
 */

/**
 * Get date filter data from the styled dropdown and custom date inputs
 * @returns {Object} Result object with isValid, data, and error properties
 */
function getDateFilterData() {
    const styledRef = window.reportDateFilter_styled;
    const hiddenSelect = styledRef?.hiddenSelect ||
        document.getElementById('reportDateFilter') ||
        document.getElementById('reportDateFilter_hidden');

    if (!hiddenSelect) {
        return {
            isValid: false,
            error: 'Date filter not found. Please refresh the page.',
            data: null
        };
    }

    const selectedValue = hiddenSelect.value;
    const requestData = {
        date_filter: selectedValue
    };

    // Validate custom dates if selected
    if (selectedValue === 'custom') {
        const customFromDate = document.getElementById('customFromDate');
        const customToDate = document.getElementById('customToDate');

        const fromDate = customFromDate?.getAttribute('data-iso-date');
        const toDate = customToDate?.getAttribute('data-iso-date');

        if (!fromDate || !toDate) {
            return {
                isValid: false,
                error: 'Please select both From and To dates for custom date range.',
                data: null
            };
        }

        // Validate date order
        if (new Date(fromDate) > new Date(toDate)) {
            return {
                isValid: false,
                error: 'From date must be before or equal to To date.',
                data: null
            };
        }

        requestData.from_date = fromDate;
        requestData.to_date = toDate;
    }

    return {
        isValid: true,
        error: null,
        data: requestData
    };
}

/**
 * Set button loading state with custom text
 * @param {HTMLElement} button - The button element
 * @param {boolean} isLoading - Whether to show loading state
 * @param {string} loadingText - Text to show during loading (optional)
 */
function setButtonLoading(button, isLoading, loadingText = 'Loading...') {
    if (!button) {
        console.error('Button element not provided to setButtonLoading');
        return;
    }

    // Store original state on first call
    if (!button.hasAttribute('data-original-text')) {
        button.setAttribute('data-original-text', button.innerHTML);
        button.setAttribute('data-original-disabled', button.disabled);
    }

    if (isLoading) {
        button.innerHTML = `<i class="fas fa-spinner fa-spin"></i> ${loadingText}`;
        button.disabled = true;
        button.classList.add('disabled');
    } else {
        const originalText = button.getAttribute('data-original-text');
        const originalDisabled = button.getAttribute('data-original-disabled') === 'true';

        button.innerHTML = originalText;
        button.disabled = originalDisabled;
        button.classList.remove('disabled');

        // Clean up attributes
        button.removeAttribute('data-original-text');
        button.removeAttribute('data-original-disabled');
    }
}

/**
 * Build URL with date filter query parameters
 * @param {string} baseUrl - The base URL
 * @param {Object} filterData - The filter data object from getDateFilterData()
 * @returns {string} Complete URL with query parameters
 */
function buildDateFilterUrl(baseUrl, filterData) {
    if (!baseUrl || !filterData) {
        console.error('Invalid parameters for buildDateFilterUrl');
        return baseUrl;
    }

    const separator = baseUrl.includes('?') ? '&' : '?';
    let url = `${baseUrl}${separator}date_filter=${encodeURIComponent(filterData.date_filter)}`;

    if (filterData.from_date) {
        url += `&from_date=${encodeURIComponent(filterData.from_date)}`;
    }

    if (filterData.to_date) {
        url += `&to_date=${encodeURIComponent(filterData.to_date)}`;
    }

    return url;
}

/**
 * Handle fetch response with proper error handling
 * @param {Response} response - The fetch response object
 * @returns {Promise<Object>} Parsed JSON data
 * @throws {Error} If response is not ok or JSON parsing fails
 */
async function handleFetchResponse(response) {
    if (!response.ok) {
        // Try to parse error message from response
        try {
            const data = await response.json();
            throw new Error(data.error || data.message || `Server error: ${response.status}`);
        } catch (jsonError) {
            // If JSON parsing fails, throw generic error
            throw new Error(`Server error: ${response.status} ${response.statusText}`);
        }
    }

    return await response.json();
}

/**
 * Get CSRF token from cookies or DOM
 * @returns {string|null} CSRF token value
 */
function getCsrfToken() {
    // Try to get from cookie first
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, 10) === 'csrftoken=') {
                cookieValue = decodeURIComponent(cookie.substring(10));
                break;
            }
        }
    }

    // Fallback: Get from form input
    if (!cookieValue) {
        const csrfInput = document.querySelector('[name=csrfmiddlewaretoken]');
        if (csrfInput) {
            cookieValue = csrfInput.value;
        }
    }

    return cookieValue;
}

/**
 * Show user-friendly error alert based on error type
 * @param {string} action - The action that failed (e.g., 'send PDF statement')
 * @param {Error} error - The error object
 */
function showErrorAlert(action, error) {
    console.error(`Error ${action}:`, error);

    let errorMessage = `❌ Failed to ${action}.\n\n`;

    if (error.message.includes('Failed to fetch') || error.message.includes('NetworkError')) {
        errorMessage += 'Network error: Please check your internet connection and try again.';
    } else if (error.message.includes('403')) {
        errorMessage += 'Permission denied: You may not have access to this feature.';
    } else if (error.message.includes('404')) {
        errorMessage += 'Service not found: Please contact support.';
    } else if (error.message.includes('500')) {
        errorMessage += 'Server error: Please try again later or contact support.';
    } else {
        errorMessage += error.message || 'An unexpected error occurred.';
    }

    alert(errorMessage);
}
