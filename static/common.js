// Common utility functions
function halfLifeToDecayFactor(halfLifeMinutes) {
  if (halfLifeMinutes <= 0) {
    return 0;
  }
  return Math.pow(2, -1 / halfLifeMinutes / 60);
}

function decayFactorToHalfLife(decayFactor) {
  return -Math.log(2) / Math.log(decayFactor) / 60;
}

// Common API helper functions
async function apiGet(endpoint) {
  const response = await fetch(endpoint);
  return await response.json();
}

async function apiPost(endpoint, data) {
  return await fetch(endpoint, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(data),
  });
}

// Common table utilities
function createTableCell(content, className) {
  const td = document.createElement("td");
  td.innerText = content;
  if (className) {
    td.classList.add(className);
  }
  return td;
}

function formatValue(value, digits = 2) {
  return (typeof value === "number" ? value.toFixed(digits) : value) ?? "-";
}

// Make formatValue available globally
window.formatValue = formatValue;

// Common form utilities
function getFormValue(id, isCheckbox = false) {
  const element = document.getElementById(id);
  return isCheckbox ? element.checked : Number(element.value);
}

function setFormValue(id, value, isCheckbox = false) {
  const element = document.getElementById(id);
  if (isCheckbox) {
    element.checked = value !== false;
  } else {
    element.value = value;
  }
}
