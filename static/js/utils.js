/**
 * Global Frontend Utilities for My_Billing application.
 * Contains shared helpers: debounce, formatCurrency, showNotification, escapeHtml, onClickOutside, and date utilities.
 */

/**
 * Standardized debounce function.
 * Delays invoking func until after wait milliseconds have elapsed since the last time it was invoked.
 */
function debounce(func, wait = 300) {
  let timeout;
  return function executedFunction(...args) {
    const context = this;
    const later = () => {
      timeout = null;
      func.apply(context, args);
    };
    clearTimeout(timeout);
    timeout = setTimeout(later, wait);
  };
}

/**
 * Formats a numeric value into a currency string formatted for Indian Rupees (₹).
 */
function formatCurrency(amount, locale = 'en-IN', currency = 'INR') {
  const numericAmount = parseFloat(amount) || 0;
  return new Intl.NumberFormat(locale, {
    style: 'currency',
    currency: currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(numericAmount);
}

/**
 * Formats a numeric value into a decimal string without currency symbol.
 */
function formatNumber(amount, locale = 'en-IN', decimals = 2) {
  const numericAmount = parseFloat(amount) || 0;
  return new Intl.NumberFormat(locale, {
    style: 'decimal',
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(numericAmount);
}

/**
 * Unified notification system to display toast/alert messages.
 */
function showNotification(message, type = 'info', duration = 3000) {
  let container = document.getElementById('toast-container');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toast-container';
    container.style.cssText = `
      position: fixed;
      top: 20px;
      right: 20px;
      z-index: 9999;
      display: flex;
      flex-direction: column;
      gap: 10px;
      max-width: 350px;
    `;
    document.body.appendChild(container);
  }

  const toast = document.createElement('div');
  const bgColors = {
    success: '#10b981',
    error: '#ef4444',
    warning: '#f59e0b',
    info: '#3b82f6',
  };

  toast.style.cssText = `
    background-color: ${bgColors[type] || bgColors.info};
    color: #ffffff;
    padding: 12px 16px;
    border-radius: 6px;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    font-size: 0.875rem;
    font-weight: 500;
    transition: opacity 0.3s ease, transform 0.3s ease;
    opacity: 0;
    transform: translateY(-10px);
  `;
  toast.textContent = message;
  container.appendChild(toast);

  requestAnimationFrame(() => {
    toast.style.opacity = '1';
    toast.style.transform = 'translateY(0)';
  });

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(-10px)';
    setTimeout(() => {
      if (toast.parentNode) {
        toast.parentNode.removeChild(toast);
      }
    }, 300);
  }, duration);
}

/**
 * Sanitizes and escapes HTML characters to prevent XSS.
 */
function escapeHtml(str) {
  if (typeof str !== 'string') return str || '';
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

/**
 * Listens for click events outside the target element and triggers a callback.
 */
function onClickOutside(element, callback) {
  if (!element || typeof callback !== 'function') return () => {};

  const listener = (event) => {
    if (!element.contains(event.target)) {
      callback(event);
    }
  };

  document.addEventListener('click', listener);
  document.addEventListener('touchstart', listener);

  return () => {
    document.removeEventListener('click', listener);
    document.removeEventListener('touchstart', listener);
  };
}

/**
 * Date calculation helpers
 */
function daysInMonth(year, month) {
  return new Date(year, month + 1, 0).getDate();
}

function firstDayOfWeek(year, month) {
  return new Date(year, month, 1).getDay();
}

function dateKey(date) {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, '0');
  const d = String(date.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
}

/**
 * Formats date into Indian locale format (e.g. "27 Jul 2026").
 */
function formatDate(date) {
  if (!date) return '';
  return new Intl.DateTimeFormat('en-IN', {
    year: 'numeric',
    month: 'short',
    day: 'numeric'
  }).format(new Date(date));
}

/**
 * Standardized throttle function.
 */
function throttle(func, limit = 200) {
  let inThrottle;
  return function executedFunction(...args) {
    const context = this;
    if (!inThrottle) {
      func.apply(context, args);
      inThrottle = true;
      setTimeout(() => (inThrottle = false), limit);
    }
  };
}

/**
 * Copy text to clipboard with fallback and toast notification.
 */
function copyToClipboard(text) {
  function fallbackCopy(t) {
    const textarea = document.createElement('textarea');
    textarea.value = t;
    textarea.style.position = 'fixed';
    textarea.style.opacity = '0';
    document.body.appendChild(textarea);
    textarea.select();
    document.execCommand('copy');
    document.body.removeChild(textarea);
    if (typeof showNotification === 'function') {
      showNotification('Copied to clipboard!', 'success');
    }
  }

  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard
      .writeText(text)
      .then(() => {
        if (typeof showNotification === 'function') {
          showNotification('Copied to clipboard!', 'success');
        }
      })
      .catch(() => fallbackCopy(text));
  } else {
    fallbackCopy(text);
  }
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    debounce,
    throttle,
    formatCurrency,
    formatNumber,
    formatDate,
    showNotification,
    escapeHtml,
    onClickOutside,
    copyToClipboard,
    daysInMonth,
    firstDayOfWeek,
    dateKey,
  };
}

