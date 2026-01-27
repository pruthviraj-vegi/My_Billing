function animateCounter(element, startValue, endValue, duration = 1000) {
  const startTime = performance.now();
  const difference = endValue - startValue;

  // Pre-compute locale options objects to avoid recreation on each frame
  const localeOptsWithDecimals = { maximumFractionDigits: 2, minimumFractionDigits: 2 };
  const localeOptsNoDecimals = { maximumFractionDigits: 0, minimumFractionDigits: 0 };

  function update(currentTime) {
    const elapsed = currentTime - startTime;
    const progress = Math.min(elapsed / duration, 1);

    // Easing function for smooth animation
    const easeOutQuad = 1 - (1 - progress) * (1 - progress); // Avoid Math.pow for simple squares

    const currentValue = startValue + difference * easeOutQuad;

    // Format as currency (Indian format)
    // Use modulo check only once per frame
    const hasDecimal = currentValue % 1 !== 0;
    const formattedValue = currentValue.toLocaleString("en-IN",
      hasDecimal ? localeOptsWithDecimals : localeOptsNoDecimals
    );

    element.textContent = formattedValue;
    element.setAttribute("data-count", currentValue.toFixed(2));

    if (progress < 1) {
      requestAnimationFrame(update);
    } else {
      // Ensure final value is exact
      element.textContent = endValue.toLocaleString("en-IN",
        endValue % 1 !== 0 ? localeOptsWithDecimals : localeOptsNoDecimals
      );
      element.setAttribute("data-count", endValue.toFixed(2));
    }
  }

  requestAnimationFrame(update);
}

// Initialize all counting numbers
document.addEventListener("DOMContentLoaded", initializeCounters);

function initializeCounters() {
  const countingElements = document.getElementsByClassName("counting-number");
  // Use for...of loop (slightly cleaner and potentially faster)
  for (const element of countingElements) {
    const initialValue = parseFloat(element.getAttribute("data-count")) || 0;
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

  // Simplify value parsing
  const numericValue = typeof newValue === "string"
    ? parseFloat(newValue.replace(/[^0-9.-]+/g, ""))
    : Number(newValue);

  if (isNaN(numericValue)) {
    console.error(`Invalid value provided for counter: ${newValue}`);
    return;
  }

  const currentValue = parseFloat(element.getAttribute("data-count")) || 0;
  animateCounter(element, currentValue, numericValue);
}

// Update all counters with new values
function updateAllCounters(valuesObject) {
  for (const [elementId, newValue] of Object.entries(valuesObject)) {
    updateCount(elementId, newValue);
  }
}