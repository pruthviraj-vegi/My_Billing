function animateCounter(element, startValue, endValue, duration = 1000) {
  // Changed to accept element instead of elementId
  const startTime = performance.now();
  const difference = endValue - startValue;

  function update(currentTime) {
    const elapsed = currentTime - startTime;
    const progress = Math.min(elapsed / duration, 1);

    // Easing function for smooth animation
    const easeOutQuad = 1 - Math.pow(1 - progress, 2);

    const currentValue = startValue + difference * easeOutQuad;

    // Format as currency (Indian format)
    // Check if decimal part is zero
    const hasDecimal = currentValue % 1 !== 0;
    const formattedValue = currentValue.toLocaleString("en-IN", {
      maximumFractionDigits: hasDecimal ? 2 : 0,
      minimumFractionDigits: hasDecimal ? 2 : 0,
    });

    element.textContent = formattedValue;
    element.setAttribute("data-count", currentValue.toFixed(2));

    if (progress < 1) {
      requestAnimationFrame(update);
    }
  }

  requestAnimationFrame(update);
}

// Initialize all counting numbers
document.addEventListener("DOMContentLoaded", function () {
  initializeCounters();
});

function initializeCounters() {
  const countingElements = document.getElementsByClassName("counting-number");
  Array.from(countingElements).forEach((element) => {
    const initialValue = parseFloat(element.getAttribute("data-count")) || 0;
    animateCounter(element, 0, initialValue);
  });
}

// Update specific counter by ID
function updateCount(elementId, newValue) {
  const element = document.getElementById(elementId);
  if (!element) {
    console.error(`Element with ID '${elementId}' not found`);
    return;
  }

  // Convert newValue to number if it's a string
  const numericValue =
    typeof newValue === "string"
      ? parseFloat(newValue.replace(/[^0-9.-]+/g, ""))
      : parseFloat(newValue);

  if (isNaN(numericValue)) {
    console.error(`Invalid value provided for counter: ${newValue}`);
    return;
  }

  const currentValue = parseFloat(element.getAttribute("data-count")) || 0;
  animateCounter(element, currentValue, numericValue);
}

// Update all counters with new values
function updateAllCounters(valuesObject) {
  Object.entries(valuesObject).forEach(([elementId, newValue]) => {
    updateCount(elementId, newValue);
  });
}
