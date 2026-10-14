document.cookie = "tz_offset_minutes=" + new Date().getTimezoneOffset() + "; path=/; samesite=lax";

function moneyFromCents(cents) {
  const sign = cents < 0 ? "-" : "";
  const abs = Math.abs(cents);
  const whole = Math.floor(abs / 100).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  return sign + whole + "." + String(abs % 100).padStart(2, "0");
}

function centsFrom(text) {
  const cleaned = String(text).trim();
  if (!/^\d+(\.\d{1,2})?$/.test(cleaned)) return null;
  const [whole, fraction = ""] = cleaned.split(".");
  return Number(whole) * 100 + Number(fraction.padEnd(2, "0"));
}

function refreshLines() {
  const rows = document.querySelectorAll("#line-rows .line");
  rows.forEach((row) => {
    const button = row.querySelector(".remove-line");
    if (button) button.disabled = rows.length === 1;
  });
  const add = document.getElementById("add-line");
  if (add) add.disabled = rows.length >= 10;
}

function refreshTotals() {
  const rows = document.querySelectorAll("#line-rows .line");
  if (!rows.length) return;
  let totalCents = 0;
  let valid = true;
  rows.forEach((row) => {
    const qtyText = row.querySelector("[name=quantity]").value.trim();
    const priceCents = centsFrom(row.querySelector("[name=unit_price]").value);
    const out = row.querySelector("[data-testid=line-total]");
    if (!/^[1-9]\d*$/.test(qtyText) || priceCents === null || priceCents <= 0) {
      valid = false;
      if (out) out.textContent = "—";
      return;
    }
    const amount = priceCents * Number(qtyText);
    totalCents += amount;
    if (out) out.textContent = moneyFromCents(amount);
  });
  const totalNode = document.getElementById("invoice-total");
  const balanceNode = document.getElementById("balance");
  const warning = document.getElementById("balance-warning");
  const paidField = document.getElementById("amount-paid");
  const paidText = paidField ? paidField.value.trim() : "";
  const paidCents = paidText === "" ? 0 : centsFrom(paidText);
  const paidOk = paidCents !== null && paidCents >= 0;
  if (totalNode) totalNode.textContent = valid ? moneyFromCents(totalCents) : "—";
  if (balanceNode) balanceNode.textContent = valid && paidOk ? moneyFromCents(totalCents - paidCents) : "—";
  if (warning) warning.hidden = !(valid && paidOk && paidCents > totalCents);
  refreshLines();
}

function applyCustomer(picker, fromUser) {
  const option = picker.selectedOptions[0];
  const name = document.getElementById("customer-name");
  const email = document.getElementById("customer-email");
  const city = document.getElementById("customer-city");
  if (!option || !option.value) {
    if (fromUser && name) name.value = "";
    if (fromUser && email) email.value = "";
    if (city) city.textContent = "City comes from the saved customer. A typed customer is not linked to a city.";
    return;
  }
  if (name) name.value = option.dataset.name || "";
  if (email) email.value = option.dataset.email || "";
  if (city) city.textContent = option.dataset.city || "";
}

const customerPicker = document.querySelector("[data-customer-picker]");
if (customerPicker) {
  customerPicker.addEventListener("change", () => applyCustomer(customerPicker, true));
  applyCustomer(customerPicker, false);
}

document.getElementById("add-line")?.addEventListener("click", () => {
  const rows = document.getElementById("line-rows");
  const template = document.getElementById("line-template");
  if (!rows || !template || rows.children.length >= 10) return;
  rows.appendChild(template.content.cloneNode(true));
  refreshTotals();
});

document.getElementById("line-rows")?.addEventListener("click", (event) => {
  const button = event.target.closest(".remove-line");
  if (!button || button.disabled) return;
  button.closest(".line")?.remove();
  refreshTotals();
});

document.getElementById("line-rows")?.addEventListener("input", refreshTotals);
document.getElementById("amount-paid")?.addEventListener("input", refreshTotals);

const notes = document.getElementById("notes");
const notesCount = document.getElementById("notes-count");
if (notes && notesCount) {
  const update = () => { notesCount.textContent = String(notes.value.length); };
  notes.addEventListener("input", update);
  update();
}

document.querySelectorAll("form[data-confirm]").forEach((form) => {
  form.addEventListener("submit", (event) => {
    if (form.dataset.confirmed === "yes") return;
    event.preventDefault();
    if (!window.confirm(form.dataset.confirm)) return;
    form.dataset.confirmed = "yes";
    form.querySelectorAll("button").forEach((button) => { button.disabled = true; });
    form.submit();
  });
});

document.querySelectorAll("form[data-once]").forEach((form) => {
  form.addEventListener("submit", () => {
    window.setTimeout(() => {
      form.querySelectorAll("button[type=submit]").forEach((button) => { button.disabled = true; });
    }, 0);
  });
});

refreshTotals();
