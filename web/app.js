const state = {
  payload: null,
  confirmed: false,
  profile: {},
  sources: [],
  audit: [],
  consent: null,
  consentAcknowledged: false,
};

const $ = (selector) => document.querySelector(selector);
const formatMoney = (value) => new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 2 }).format(Number(value || 0));
const escapeHtml = (value) => String(value ?? "").replace(/[&<>'"]/g, (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#039;", '"': "&quot;" })[character]);
const multiplier = { weekly: 52, biweekly: 26, semimonthly: 24, monthly: 12, annual: 1 };
const thresholdTable = { 1: 72000, 2: 82320, 3: 92580, 4: 102840, 5: 111120, 6: 119340, 7: 127560, 8: 135780 };

function announce(message) {
  $("#live-status").textContent = message;
}

function addAudit(action) {
  state.audit.unshift({ action, time: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }) });
  $("#audit-list").innerHTML = state.audit.map((entry) => `<li><strong>${escapeHtml(entry.action)}</strong> · ${escapeHtml(entry.time)} · frozen rule version 2026-07-18</li>`).join("");
}

async function getJson(path) {
  const response = await fetch(path, { cache: "no-store" });
  if (!response.ok) throw new Error("Unable to load the requested local fixture.");
  return response.json();
}

function valueKey(field) {
  return `${field.document_id}:${field.field}`;
}

function statusClass(status) {
  return status === "READY_TO_REVIEW" ? "ready" : "needs-review";
}

function currentHouseholdSize() {
  const field = state.payload.profile_fields.find((item) => item.field === "household_size");
  return Number(state.profile[valueKey(field)] ?? field.value);
}

function currentCalculation() {
  const sources = state.sources.map((source) => ({ ...source, amount: Number(source.amount), annualized: Math.round(Number(source.amount) * multiplier[source.frequency] * 100) / 100 }));
  const annualizedIncome = Math.round(sources.reduce((total, source) => total + source.annualized, 0) * 100) / 100;
  const householdSize = currentHouseholdSize();
  const threshold = thresholdTable[householdSize] ?? null;
  return {
    sources,
    annualizedIncome,
    householdSize,
    threshold,
    comparison: threshold === null ? "no_frozen_threshold" : annualizedIncome <= threshold ? "below_or_equal" : "above",
  };
}

function renderProfile() {
  const fields = state.payload.profile_fields;
  $("#profile-form").innerHTML = `<div class="form-grid">${fields.map((field) => {
    const key = valueKey(field);
    const type = field.field === "household_size" ? "number" : "text";
    const value = state.profile[key] ?? field.value;
    return `<div class="field-control"><label for="profile-${escapeHtml(key)}">${escapeHtml(field.field.replaceAll("_", " "))}</label><input id="profile-${escapeHtml(key)}" data-profile-key="${escapeHtml(key)}" ${type === "number" ? "min=1 max=99 step=1" : ""} type="${type}" value="${escapeHtml(value)}"><span class="field-meta">${escapeHtml(field.document_id)} · page ${field.page} · box [${field.bbox.join(", ")}] · ${escapeHtml(field.confidence)} confidence</span></div>`;
  }).join("")}</div>`;
  $("#profile-form").querySelectorAll("input").forEach((input) => input.addEventListener("input", () => {
    state.profile[input.dataset.profileKey] = input.value;
    markUnconfirmed("A profile value changed. Confirm it before reuse.");
  }));
}

function renderDocuments() {
  const untrustedCount = state.payload.documents.filter((document) => document.contains_untrusted_content).length;
  $("#untrusted-summary").textContent = untrustedCount ? `${untrustedCount} supplied fixture(s) contained untrusted text. It was ignored and never shown as an instruction.` : "All displayed values are allowlisted fields only.";
  $("#document-list").innerHTML = state.payload.documents.map((document) => `
    <article class="document-card">
      <div class="doc-meta"><span>${escapeHtml(document.document_type.replaceAll("_", " "))}</span><span>${escapeHtml(document.document_id)}</span></div>
      <h4>${escapeHtml(document.file_name)}</h4>
      <a class="evidence-link" href="${escapeHtml(document.preview_url)}" target="_blank" rel="noreferrer">Open original synthetic PDF</a>
      ${document.contains_untrusted_content ? `<p class="untrusted">${escapeHtml(document.untrusted_content_handling)}</p>` : ""}
      <table class="field-table"><thead><tr><th>Allowlisted field</th><th>Evidence</th></tr></thead><tbody>${document.fields.map((field) => `<tr><td><strong>${escapeHtml(field.field.replaceAll("_", " "))}</strong><br>${escapeHtml(field.value)}</td><td>p. ${field.page}<br>box [${field.bbox.join(", ")}]<br><span class="status ${field.confidence === "high" ? "ready" : "pending"}">${escapeHtml(field.confidence)}</span></td></tr>`).join("")}</tbody></table>
    </article>`).join("");
}

function renderCalculation() {
  const calculation = currentCalculation();
  if (!state.confirmed) {
    $("#calculation-gate").hidden = false;
    $("#calculation-content").hidden = true;
    $("#download-packet").disabled = true;
    return;
  }
  $("#calculation-gate").hidden = true;
  $("#calculation-content").hidden = false;
  $("#download-packet").disabled = false;
  const comparisonText = calculation.comparison === "below_or_equal" ? "At or below frozen threshold" : calculation.comparison === "above" ? "Above frozen threshold" : "No frozen threshold available";
  $("#calculation-summary").innerHTML = `<p>${escapeHtml(state.payload.calculation.formula)}</p><div class="calculation-result"><div class="stat"><span>Confirmed annualized income</span><strong>${formatMoney(calculation.annualizedIncome)}</strong></div><div class="stat"><span>60% threshold · household ${calculation.householdSize}</span><strong>${calculation.threshold === null ? "Needs review" : formatMoney(calculation.threshold)}</strong></div><div class="stat"><span>Comparison</span><strong>${escapeHtml(comparisonText)}</strong></div></div><div class="citation"><p><strong>Calculation convention</strong></p>${citationMarkup(state.payload.calculation.calculation_citation)}</div>${calculation.threshold ? `<div class="citation"><p><strong>Threshold citation</strong></p>${citationMarkup(state.payload.calculation.threshold_citation)}</div>` : ""}`;
  $("#income-source-list").innerHTML = calculation.sources.map((source, index) => `<div class="source-row"><label>${escapeHtml(source.label)}<input type="number" min="0" step="0.01" data-source-amount="${index}" value="${escapeHtml(source.amount)}"><span class="field-meta">Amount per ${escapeHtml(source.frequency)}</span></label><label>Frequency<select data-source-frequency="${index}">${Object.keys(multiplier).map((frequency) => `<option value="${frequency}" ${source.frequency === frequency ? "selected" : ""}>${frequency}</option>`).join("")}</select></label><div><strong>${formatMoney(source.annualized)}</strong><br><span class="field-meta">annualized · ${escapeHtml(source.document_id)}</span></div></div><div class="citation">${fieldCitationMarkup(source.citation)}</div>`).join("");
  $("#income-source-list").querySelectorAll("input, select").forEach((input) => input.addEventListener("input", () => {
    const index = Number(input.dataset.sourceAmount ?? input.dataset.sourceFrequency);
    if (input.dataset.sourceAmount !== undefined) state.sources[index].amount = input.value;
    if (input.dataset.sourceFrequency !== undefined) state.sources[index].frequency = input.value;
    markUnconfirmed("An income input changed. Confirm it before reuse.");
  }));
}

function citationMarkup(citation) {
  if (!citation) return "";
  return `<p>${escapeHtml(citation.rule_id)} · ${escapeHtml(citation.authority)} · effective ${escapeHtml(citation.effective_date || "not date-specific")}</p><p><a href="${escapeHtml(citation.source_url)}" target="_blank" rel="noreferrer">Source</a> · ${escapeHtml(citation.source_locator)}</p>`;
}

function fieldCitationMarkup(citation) {
  return `<strong>Source evidence</strong><br>${escapeHtml(citation.document_id)} · page ${citation.page} · box [${citation.bbox.join(", ")}]`;
}

function renderRules() {
  $("#rule-citations").innerHTML = state.payload.rules.map((rule) => `<div class="citation">${citationMarkup(rule)}</div>`).join("");
}

function renderReadiness() {
  const readiness = state.payload.readiness;
  const calculation = currentCalculation();
  const extraReason = calculation.threshold === null ? ["NO_FROZEN_THRESHOLD"] : [];
  const reasons = [...readiness.reasons, ...extraReason];
  const status = extraReason.length ? "NEEDS_REVIEW" : readiness.status;
  const reasonMarkup = reasons.length ? `<ul class="reason-list">${reasons.map((reason) => `<li><strong>${escapeHtml(reason)}</strong></li>`).join("")}</ul>` : "<p>No review reason is present in the supplied gold checklist.</p>";
  const missingMarkup = readiness.missing_document_types.length ? `<p><strong>Document context:</strong> ${escapeHtml(readiness.missing_document_types.join(", "))} is not present in this supplied fixture. Follow the frozen checklist and reviewer guidance.</p>` : "";
  $("#readiness-content").innerHTML = `<div class="readiness-summary"><span class="status ${statusClass(status)}">${escapeHtml(status.replaceAll("_", " "))}</span><span>This is readiness only, never an eligibility determination.</span></div><h4>Review reasons</h4>${reasonMarkup}${missingMarkup}<div class="citation">${citationMarkup(readiness.citation)}</div>`;
}

function renderAll() {
  renderProfile();
  renderDocuments();
  renderCalculation();
  renderRules();
  renderReadiness();
}

function markUnconfirmed(message) {
  if (!state.payload) return;
  state.confirmed = false;
  $("#profile-state").className = "status pending";
  $("#profile-state").textContent = "Confirmation required";
  $("#calculation-gate").textContent = message;
  renderCalculation();
  renderReadiness();
  announce(message);
}

function confirmProfile() {
  if (!state.payload) return;
  const householdSize = currentHouseholdSize();
  if (!Number.isInteger(householdSize) || householdSize < 1) {
    $("#profile-state").className = "status needs-review";
    $("#profile-state").textContent = "Enter a valid household size";
    announce("Enter a valid household size before confirming.");
    return;
  }
  state.confirmed = true;
  $("#profile-state").className = "status ready";
  $("#profile-state").textContent = "Confirmed for this session";
  renderCalculation();
  renderReadiness();
  addAudit("Profile and calculation inputs confirmed");
  announce("Profile confirmed. The deterministic calculation and packet controls are available.");
}

async function loadHousehold(householdId, source) {
  if (!state.consentAcknowledged) {
    announce("Acknowledge the synthetic-data use summary before loading a fixture.");
    return;
  }
  try {
    const payload = await getJson(`/api/households/${encodeURIComponent(householdId)}`);
    state.payload = payload;
    state.confirmed = false;
    state.profile = Object.fromEntries(payload.profile_fields.map((field) => [valueKey(field), field.value]));
    state.sources = payload.income_sources.map((sourceItem) => ({ ...sourceItem }));
    state.audit = [];
    $("#session-empty").hidden = true;
    $("#session-content").hidden = false;
    $("#fixture-select").value = householdId;
    renderAll();
    addAudit("Renter acknowledged synthetic-data use and session deletion");
    addAudit(`Loaded ${householdId} from ${source}`);
    announce(`${householdId} loaded. Review the profile and confirm values before calculating.`);
  } catch (error) {
    $("#upload-status").textContent = error.message;
    announce(error.message);
  }
}

function downloadPacket() {
  if (!state.payload || !state.confirmed) return;
  const calculation = currentCalculation();
  const readiness = state.payload.readiness;
  const profile = state.payload.profile_fields.map((field) => ({ field: field.field, value: state.profile[valueKey(field)] ?? field.value, citation: { document_id: field.document_id, page: field.page, bbox: field.bbox } }));
  const packet = {
    title: "RealDoor application-readiness packet",
    generated_at: new Date().toISOString(),
    synthetic_only: true,
    decision_boundary: "This packet provides readiness evidence and a frozen-rule comparison only. It is not an eligibility, approval, denial, priority, or acceptance decision.",
    household_id: state.payload.household_id,
    confirmed_profile: profile,
    calculation: { ...calculation, formula: state.payload.calculation.formula, calculation_citation: state.payload.calculation.calculation_citation, threshold_citation: state.payload.calculation.threshold_citation },
    readiness: readiness,
    renter_note: $("#packet-note").value,
    delivery: "Downloaded by the renter. RealDoor did not send this packet to a property or provider.",
  };
  const blob = new Blob([JSON.stringify(packet, null, 2)], { type: "application/json" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = `realdoor-${state.payload.household_id.toLowerCase()}-readiness-packet.json`;
  link.click();
  URL.revokeObjectURL(link.href);
  addAudit("Downloaded renter-controlled readiness packet");
  announce("Readiness packet downloaded. It was not sent to any property or provider.");
}

function deleteSession() {
  state.payload = null;
  state.confirmed = false;
  state.profile = {};
  state.sources = [];
  state.audit = [];
  state.consentAcknowledged = false;
  $("#session-content").hidden = true;
  $("#session-empty").hidden = false;
  $("#fixture-select").value = "";
  $("#fixture-select").disabled = true;
  $("#consent-check").checked = false;
  $("#file-input").value = "";
  $("#file-input").disabled = true;
  $("#packet-note").value = "";
  $("#upload-status").textContent = "Session deleted. No document contents were retained by this app.";
  $("#audit-list").innerHTML = "";
  announce("Session deleted. The profile and packet are no longer available in this browser session.");
}

async function askQuestion(event) {
  event.preventDefault();
  const question = $("#question").value.trim();
  if (!question) return;
  const household = state.payload?.household_id || "";
  const response = await fetch("/api/ask", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ question, household }), cache: "no-store" });
  if (!response.ok) throw new Error("Unable to answer the local question.");
  const answer = await response.json();
  $("#answer").innerHTML = `<strong>${escapeHtml(answer.answer)}</strong>${answer.citations.map((citation) => `<div class="citation">${citationMarkup(citation)}</div>`).join("")}`;
  addAudit("Asked a local rules or safety question");
  announce("Local rules answer updated with citations.");
}

function showConsent() {
  const consent = state.consent;
  $("#consent-content").innerHTML = `<p>${escapeHtml(consent.summary)}</p><p><strong>Retention:</strong> ${escapeHtml(consent.retention)}</p><h3>Allowed uses</h3><ul>${consent.allowlisted_fields.map((item) => `<li><strong>${escapeHtml(item.field.replaceAll("_", " "))}:</strong> ${escapeHtml(item.purpose)}</li>`).join("")}</ul><h3>Never used</h3><ul>${consent.exclusions.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`;
  $("#consent-dialog").showModal();
}

function showFeatures() {
  const consent = state.consent;
  $("#feature-content").innerHTML = `<p>Every feature used by this prototype is visible here. The application uses no hidden proxies.</p><div class="feature-list">${consent.allowlisted_fields.map((item) => `<article class="feature-item"><h3>${escapeHtml(item.field.replaceAll("_", " "))}</h3><p>${escapeHtml(item.purpose)}</p></article>`).join("")}</div><h3>Explicit exclusions</h3><ul>${consent.exclusions.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`;
  $("#feature-dialog").showModal();
}

async function init() {
  state.consent = await getJson("/api/consent");
  const households = await getJson("/api/households");
  $("#fixture-select").insertAdjacentHTML("beforeend", households.map((household) => `<option value="${household.household_id}">${household.household_id} · ${escapeHtml(household.scenario.replaceAll("_", " "))}</option>`).join(""));
  $("#consent-check").addEventListener("change", (event) => {
    state.consentAcknowledged = event.target.checked;
    $("#fixture-select").disabled = !event.target.checked;
    $("#file-input").disabled = !event.target.checked;
    $("#upload-status").textContent = event.target.checked ? "Consent recorded for this browser session. You can now choose supplied synthetic PDFs or a demo household." : "Acknowledge the local data-use summary to begin. No document contents are sent to the server.";
    announce(event.target.checked ? "Consent recorded for this browser session." : "Consent acknowledgement removed.");
  });
  $("#fixture-select").addEventListener("change", (event) => event.target.value && loadHousehold(event.target.value, "demo fixture selector"));
  $("#file-input").addEventListener("change", (event) => {
    const files = [...event.target.files];
    const match = files.map((file) => file.name.match(/hh-(\d{3})/i)).find(Boolean);
    if (!match) {
      $("#upload-status").textContent = "Choose supplied synthetic PDFs named like hh-001_d02_pay_stub.pdf. Files were not uploaded.";
      return;
    }
    const householdId = `HH-${match[1]}`;
    $("#upload-status").textContent = `${files.length} local file(s) selected. Contents stay in this browser; loading supplied fixture metadata for ${householdId}.`;
    loadHousehold(householdId, "local filename match");
  });
  $("#confirm-profile").addEventListener("click", confirmProfile);
  $("#download-packet").addEventListener("click", downloadPacket);
  $("#delete-session").addEventListener("click", deleteSession);
  $("#question-form").addEventListener("submit", askQuestion);
  $("#open-consent").addEventListener("click", showConsent);
  $("#open-features").addEventListener("click", showFeatures);
  document.querySelectorAll("[data-close]").forEach((button) => button.addEventListener("click", () => $(`#${button.dataset.close}`).close()));
}

init().catch((error) => {
  $("#session-empty").textContent = `Local startup error: ${error.message}`;
  announce(`Local startup error: ${error.message}`);
});
