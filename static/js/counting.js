function animateCounter(element, startValue, endValue, duration = 1000) {
  // Ensure non-negative start/end values and prevent float precision artifacts like -0.00
  const safeStart = Math.max(0, startValue || 0);
  const safeEnd = Math.max(0, endValue || 0);
  const startTime = performance.now();
  const difference = safeEnd - safeStart;
  const prefix = element.getAttribute("data-prefix") || "";
  const suffix = element.getAttribute("data-suffix") || "";

  // Pre-compute locale options objects to avoid recreation on each frame
  const localeOptsWithDecimals = { maximumFractionDigits: 2, minimumFractionDigits: 2 };
  const localeOptsNoDecimals = { maximumFractionDigits: 0, minimumFractionDigits: 0 };

  function update(currentTime) {
    const elapsed = currentTime - startTime;
    const progress = Math.min(elapsed / duration, 1);

    // Easing function for smooth animation
    const easeOutQuad = 1 - (1 - progress) * (1 - progress);

    let currentValue = safeStart + difference * easeOutQuad;
    if (Math.abs(currentValue) < 0.001 || currentValue < 0) {
      currentValue = 0;
    }

    // Format as currency (Indian format)
    const hasDecimal = currentValue % 1 !== 0;
    const formattedValue = currentValue.toLocaleString("en-IN",
      hasDecimal ? localeOptsWithDecimals : localeOptsNoDecimals
    );

    element.textContent = prefix + formattedValue + suffix;
    element.setAttribute("data-count", currentValue.toFixed(2));

    if (progress < 1) {
      requestAnimationFrame(update);
    } else {
      // Ensure final value is exact
      element.textContent = prefix + safeEnd.toLocaleString("en-IN",
        safeEnd % 1 !== 0 ? localeOptsWithDecimals : localeOptsNoDecimals
      ) + suffix;
      element.setAttribute("data-count", safeEnd.toFixed(2));
    }
  }

  requestAnimationFrame(update);
}

// Initialize all counting numbers
document.addEventListener("DOMContentLoaded", initializeCounters);

function initializeCounters() {
  const countingElements = document.getElementsByClassName("counting-number");
  for (const element of countingElements) {
    const initialValue = Math.max(0, parseFloat(element.getAttribute("data-count")) || 0);
    animateCounter(element, 0, initialValue);
  }
}

// Update specific counter by ID
function updateCount(elementId, newValue) {
  const element = document.getElementById(elementId);
  if (!element) {
    console.error(`Element with ID '${elementId}' not found`);
    return;
  }

  const numericValue = typeof newValue === "string"
    ? Math.max(0, parseFloat(newValue.replace(/[^0-9.-]+/g, "")) || 0)
    : Math.max(0, Number(newValue) || 0);

  if (isNaN(numericValue)) {
    console.error(`Invalid value provided for counter: ${newValue}`);
    return;
  }

  const currentValue = Math.max(0, parseFloat(element.getAttribute("data-count")) || 0);
  animateCounter(element, currentValue, numericValue);
}

// Update all counters with new values
function updateAllCounters(valuesObject) {
  for (const [elementId, newValue] of Object.entries(valuesObject)) {
    updateCount(elementId, newValue);
  }
}