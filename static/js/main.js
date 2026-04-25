// Main JavaScript file for ÉnergieData Cameroun application

console.log("✅ Main.js loaded");

// Initialize tooltips and popovers if using Bootstrap
document.addEventListener("DOMContentLoaded", function () {
  // Initialize Bootstrap tooltips
  const tooltips = document.querySelectorAll('[data-bs-toggle="tooltip"]');
  tooltips.forEach((tooltip) => {
    new bootstrap.Tooltip(tooltip);
  });

  // Initialize Bootstrap popovers
  const popovers = document.querySelectorAll('[data-bs-toggle="popover"]');
  popovers.forEach((popover) => {
    new bootstrap.Popover(popover);
  });
});

// Utility: Format number as currency (FCFA)
function formatCurrency(value) {
  return new Intl.NumberFormat("fr-CM", {
    style: "currency",
    currency: "XAF",
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value);
}

// Utility: Format number with thousand separators
function formatNumber(value) {
  return new Intl.NumberFormat("fr-CM").format(value);
}

// API: Make GET request with error handling
async function apiGet(endpoint) {
  try {
    const response = await fetch(endpoint);
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    return await response.json();
  } catch (error) {
    console.error("API Error:", error);
    throw error;
  }
}

// API: Make POST request with error handling
async function apiPost(endpoint, data) {
  try {
    const response = await fetch(endpoint, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(data),
    });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    return await response.json();
  } catch (error) {
    console.error("API Error:", error);
    throw error;
  }
}

// Show notification
function showNotification(message, type = "info") {
  const alertClass = `alert-${type}`;
  const alertHtml = `
        <div class="alert ${alertClass} alert-dismissible fade show" role="alert">
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
    `;

  const container =
    document.querySelector("#notification-container") || document.body;
  const div = document.createElement("div");
  div.innerHTML = alertHtml;
  container.insertBefore(div.firstElementChild, container.firstChild);
}

// Show success notification
function showSuccess(message) {
  showNotification(message, "success");
}

// Show error notification
function showError(message) {
  showNotification(message, "danger");
}

// Show warning notification
function showWarning(message) {
  showNotification(message, "warning");
}

// Validation: Check if field is empty
function isFieldEmpty(value) {
  return !value || value.trim() === "";
}

// Validation: Check if email is valid
function isValidEmail(email) {
  const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  return re.test(email);
}

// Validation: Check if number is positive
function isPositiveNumber(value) {
  return !isNaN(value) && Number(value) > 0;
}

console.log("✅ Utility functions loaded");
