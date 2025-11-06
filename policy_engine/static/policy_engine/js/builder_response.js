// policy_engine/static/policy_engine/js/builder_response.js
import { safeJSON } from "./utils.js";

/**
 * Initialize a response builder UI.
 * Supports: string, number, enum, bool, list[item_schema]
 * Enum & Bool fields support template mode (textarea) or select mode.
 */

function markDirty(inputEl) {
    const wrapper = inputEl.closest(".response-field");
    if (wrapper) wrapper.dataset.dirty = "true";
}

export function initResponseBuilder(containerId, hiddenSelector, schemaText, existingJsonText) {
    console.log(`🧰 Initializing Response Builder for ${containerId}`);
    const container = document.getElementById(containerId);
    if (!container) return null;

    const hidden = document.querySelector(hiddenSelector);
    if (!hidden) {
        console.warn(`⚠️ Hidden input not found for builder: ${hiddenSelector}`);
        return null;
    }

    const schema = safeJSON(schemaText) || {};
    const full = safeJSON(existingJsonText) || {};
    const existingData = (full && typeof full === "object" && full.result && typeof full.result === "object")
        ? full.result
        : full;

    console.log("📦 schema =", schema);
    console.log("📦 existingData =", existingData);

    container.dataset.restoring = "true";
    container.innerHTML = "";

    // -------------------------------------------------------------------------
    // Helpers
    // -------------------------------------------------------------------------
    function isJinjaString(v) {
        return typeof v === "string" && v.trim().starts_with?.("{{") || (typeof v === "string" && v.trim().startsWith("{{"));
    }

    // Find the actual input element for a field inside a scope element (wrapper card/group/field)
    function getValueInput(scopeEl, field) {
        // Preferred: inside a value-wrapper with matching data-field
        const wrapper = scopeEl.querySelector(`.value-wrapper[data-field="${field}"]`);
        if (wrapper) {
            return (
                wrapper.querySelector('.response-template-input:not(.d-none)') ||
                wrapper.querySelector('.response-input')
            );
        }
        // Fallback: direct inputs marked with data-field
        return (
            scopeEl.querySelector(`.response-template-input[data-field="${field}"]:not(.d-none)`) ||
            scopeEl.querySelector(`.response-input[data-field="${field}"]`)
        );
    }

    // -------------------------------------------------------------------------
    // Field builder helpers (ENUM & BOOL template support)
    // -------------------------------------------------------------------------
    function buildInput(field, meta) {
        const type = meta.type;
        const existingVal = (existingData && existingData[field]) ?? "";
        const inTemplate = isJinjaString(existingVal);

        if (type === "enum") {
            const choices = meta.choices || [];
            return `
            <div class="value-wrapper" data-field="${field}" data-type="enum" data-choices='${JSON.stringify(choices)}'>
                <div class="enum-mode enum-select-mode" style="${inTemplate ? "display:none;" : ""}">
                    <div class="d-flex gap-2">
                        <select class="form-select form-select-sm response-input" data-field="${field}">
                            <option value="">(unset)</option>
                            ${choices.map(v => `<option value="${v}" ${(!inTemplate && v === existingVal) ? "selected" : ""}>${v}</option>`).join("")}
                        </select>
                        <button type="button" class="btn btn-sm btn-outline-secondary enum-switch-template" data-field="${field}" title="Switch to template">
                            {{ }}
                        </button>
                    </div>
                </div>
                <div class="enum-mode enum-template-mode" style="${inTemplate ? "" : "display:none;"}">
                    <div class="d-flex gap-2">
                        <textarea class="form-control form-control-sm response-input" data-field="${field}" rows="2">${inTemplate ? existingVal : ""}</textarea>
                        <button type="button" class="btn btn-sm btn-outline-secondary enum-switch-select" data-field="${field}" title="Switch to select">
                            ⬇︎
                        </button>
                    </div>
                </div>
            </div>`;
        }

        if (type === "bool") {
            return `
            <div class="value-wrapper" data-field="${field}" data-type="bool">
                <div class="bool-select-mode" style="${inTemplate ? "display:none;" : ""}">
                    <div class="input-group input-group-sm">
                        <select class="form-select response-input" data-field="${field}" data-type="bool">
                            <option value="">(unset)</option>
                            <option value="true" ${(!inTemplate && existingVal === true) ? "selected" : ""}>true</option>
                            <option value="false" ${(!inTemplate && existingVal === false) ? "selected" : ""}>false</option>
                        </select>
                        <button type="button" class="btn btn-outline-secondary btn-sm bool-switch-template" title="Switch to template mode">
                            {{ }}
                        </button>
                    </div>
                </div>
                <div class="bool-template-mode" style="${inTemplate ? "" : "display:none;"}">
                    <textarea class="form-control form-control-sm response-template-input" rows="1" data-field="${field}" data-type="string" placeholder="{{ expression }}">${inTemplate ? existingVal : ""}</textarea>
                    <button type="button" class="btn btn-outline-secondary btn-sm mt-1 bool-switch-select" title="Switch back to dropdown">
                        ⬇
                    </button>
                </div>
            </div>`;
        }

        if (type === "number") {
            return `<input type="number" class="form-control form-control-sm response-input" data-field="${field}" data-type="number" value="${!isNaN(Number(existingVal)) ? existingVal : ""}">`;
        }

        if (type === "list" && meta.item_schema) {
            return buildListField(field, meta);
        }

        // string
        if (inTemplate) {
            return `
            <div class="value-wrapper" data-field="${field}" data-type="string">
                <textarea class="form-control form-control-sm response-template-input"
                          data-field="${field}"
                          rows="2">${existingVal}</textarea>
            </div>`;
        }
        return `<input type="text"
                       class="form-control form-control-sm response-input"
                       data-field="${field}"
                       data-type="string"
                       value="${existingVal ?? ""}">`;
    }

    function buildListField(field, meta) {
        const subId = `${containerId}-${field}-list`;
        return `
        <div class="nested-list border rounded p-2 bg-light mb-2" data-field="${field}">
            <div class="d-flex justify-content-between align-items-center mb-2">
                <strong>${field}</strong>
                <div class="d-flex gap-2 align-items-center">
                    <button type="button" class="btn btn-sm btn-outline-primary add-list-item" data-subid="${subId}">➕ Add Item</button>
                </div>
            </div>
            <div id="${subId}" class="nested-items"></div>
        </div>`;
    }

    function buildListItemForm(subSchema, index) {
        const fields = Object.entries(subSchema).map(([subField, subMeta]) => {
            const input = buildInput(subField, subMeta);
            return `
                <div class="mb-2">
                    <label class="form-label small fw-semibold">${subField}</label>
                    ${input}
                </div>`;
        }).join("");

        return `
        <div class="nested-item card card-body border mb-2">
            <div class="nested-item-header d-flex justify-content-between align-items-center">
                <div><span class="chevron">▾</span> <strong class="ms-1">Item #${index + 1}</strong></div>
                <button type="button" class="btn btn-sm btn-outline-danger remove-list-item">✖ Remove</button>
            </div>
            <div class="nested-body mt-2">${fields}</div>
        </div>`;
    }

    // -------------------------------------------------------------------------
    // Render UI fields
    // -------------------------------------------------------------------------
    Object.entries(schema).forEach(([field, meta]) => {
        container.insertAdjacentHTML(
            "beforeend",
            `<div class="response-field mb-2" data-field="${field}">
                <label class="form-label small fw-semibold">${field}</label>
                ${buildInput(field, meta)}
            </div>`
        );
    });

    // -------------------------------------------------------------------------
    // Service-type field-based visibility
    // -------------------------------------------------------------------------
    function applyFieldVisibility(serviceTypeValue) {
        container.querySelectorAll(".response-field").forEach(wrapper => {
            const field = wrapper.dataset.field;
            const meta = schema[field];
            if (!meta) return;
            const applies = meta.applies_to;
            wrapper.style.display = (!applies || applies.includes(serviceTypeValue)) ? "" : "none";
        });
    }

    const serviceTypeEl = container.querySelector(`[data-field="service_type"] select, [data-field="service_type"] .response-input`);
    if (serviceTypeEl) {
        const syncVisibility = () => applyFieldVisibility(serviceTypeEl.value?.trim() || "conference");
        serviceTypeEl.addEventListener("change", syncVisibility);
        serviceTypeEl.addEventListener("input", syncVisibility);
        syncVisibility();
    }

    // -------------------------------------------------------------------------
    // Restore existing data for list fields (top-level simple fields already restored in buildInput)
    // -------------------------------------------------------------------------
    Object.entries(existingData).forEach(([field, value]) => {
        const wrapper = container.querySelector(`[data-field="${field}"]`);
        const meta = schema[field];
        if (!wrapper || !meta) return;

        if (meta.type === "list" && meta.item_schema && Array.isArray(value)) {
            const subContainer = wrapper.querySelector(".nested-items");
            value.forEach((item, i) => {
                subContainer.insertAdjacentHTML("beforeend", buildListItemForm(meta.item_schema, i));
                const card = subContainer.lastElementChild;
                Object.entries(item).forEach(([k, v]) => {
                    const inputEl = getValueInput(card, k);
                    if (!inputEl) return;
                    if (inputEl.tagName === "SELECT") {
                        inputEl.value = String(v);
                    } else {
                        inputEl.value = v;
                    }
                });
            });
        }
    });

    //  Mark restored values dirty so they serialize
    Object.keys(existingData).forEach(field => {
        const wrapper = container.querySelector(`.response-field[data-field="${field}"]`);
        if (wrapper) wrapper.dataset.dirty = "true";
    });


    // -------------------------------------------------------------------------
    // Sync to hidden JSON
    // -------------------------------------------------------------------------
    function syncToJSON() {
        if (container.dataset.restoring === "true") return;

        const data = {};

        container.querySelectorAll(".response-field").forEach(fieldWrapper => {
            const field = fieldWrapper.dataset.field;
            const meta = schema[field];
            if (!meta) return;

            // LIST FIELDS
            if (meta.type === "list" && meta.item_schema) {
                const items = [];
                fieldWrapper.querySelectorAll(".nested-item").forEach(itemEl => {
                    const obj = {};
                    const subSchema = meta.item_schema || {};
                    Object.entries(subSchema).forEach(([subField, subMeta]) => {
                        const inputEl = getValueInput(itemEl, subField);
                        if (!inputEl) return;

                        let raw = (inputEl.value ?? "");
                        if (typeof raw === "string") raw = raw.trim();
                        if (raw === "") return; // skip empty subfields

                        const typ = subMeta?.type || "string";
                        let val = raw;
                        if (typ === "bool") {
                            // Keep template strings intact; else convert to boolean
                            val = isJinjaString(raw) ? raw : (raw === true || raw === "true");
                        } else if (typ === "number") {
                            val = Number(raw);
                        }
                        obj[subField] = val;
                    });
                    if (Object.keys(obj).length > 0) items.push(obj);
                });
                if (items.length > 0) data[field] = items;
                return;
            }

            // SIMPLE FIELDS
            const input = getValueInput(fieldWrapper, field);
            if (!input) return;
            // Only serialize fields the user edited
            if (!fieldWrapper.dataset.dirty) return;
            let raw = (input.value ?? "");
            if (typeof raw === "string") raw = raw.trim();

            // If ENUM and empty → do NOT store → Infinity default applies
            if (meta.type === "enum" && raw === "") {
                return; // Skip storing this value
            }

            let val = raw;

            // Only coerce if not template
            if (!isJinjaString(raw)) {
                if (meta.type === "bool") {
                    val = (raw === true || raw === "true");
                } else if (meta.type === "number") {
                    val = Number(raw);
                }
            }

            // Store remaining values normally
            data[field] = val;

        });

        hidden.value = JSON.stringify({
            status: "success",
            action: "continue",
            result: data
        }, null, 2);

        emitChange();
    }

    container.addEventListener("input", e => {
        const input = e.target.closest(".response-input, .response-template-input");
        if (input) markDirty(input);
        syncToJSON();
    });


    container.addEventListener("click", e => {
        const btn = e.target.closest("button");
        if (!btn) return;

        // LIST ADD / REMOVE
        if (btn.classList.contains("add-list-item")) {
            const subId = btn.dataset.subid;
            const field = btn.closest("[data-field]").dataset.field;
            const subSchema = schema[field]?.item_schema;
            const subContainer = document.getElementById(subId);
            const index = subContainer.children.length;
            subContainer.insertAdjacentHTML("beforeend", buildListItemForm(subSchema, index));
            syncToJSON();
            return;
        }
        if (btn.classList.contains("remove-list-item")) {
            btn.closest(".nested-item")?.remove();
            syncToJSON();
            return;
        }

        // ENUM: Dropdown → Template
        if (btn.classList.contains("enum-switch-template")) {
            const wrapper = btn.closest(".value-wrapper");
            wrapper.querySelector(".enum-select-mode").style.display = "none";
            wrapper.querySelector(".enum-template-mode").style.display = "";
            const ta = wrapper.querySelector("textarea.response-input[data-field]");
            const sel = wrapper.querySelector("select.response-input[data-field]");
            if (ta && sel && !ta.value) ta.value = sel.value ? `{{ '${sel.value}' }}` : "";
            syncToJSON();
            return;
        }
        // ENUM: Template → Dropdown
        if (btn.classList.contains("enum-switch-select")) {
            const wrapper = btn.closest(".value-wrapper");
            wrapper.querySelector(".enum-select-mode").style.display = "";
            wrapper.querySelector(".enum-template-mode").style.display = "none";
            syncToJSON();
            return;
        }

        // BOOL: Dropdown → Template
        if (btn.classList.contains("bool-switch-template")) {
            const wrapper = btn.closest(".value-wrapper");
            wrapper.querySelector(".bool-select-mode").style.display = "none";
            wrapper.querySelector(".bool-template-mode").style.display = "";
            const ta = wrapper.querySelector("textarea.response-template-input[data-field]");
            const sel = wrapper.querySelector("select.response-input[data-field]");
            if (ta && sel && !ta.value) {
                const v = sel.value;
                if (v === "true" || v === "false") {
                    ta.value = `{{ ${v} }}`;
                }
            }
            syncToJSON();
            return;
        }
        // BOOL: Template → Dropdown
        if (btn.classList.contains("bool-switch-select")) {
            const wrapper = btn.closest(".value-wrapper");
            wrapper.querySelector(".bool-select-mode").style.display = "";
            wrapper.querySelector(".bool-template-mode").style.display = "none";
            syncToJSON();
            return;
        }
    });

    // ENUM auto-switch on typing "{{" into select → move to textarea; and vice versa
    function fixEnumValueMode(e) {
        const target = e.target;
        if (!target.classList.contains("response-input")) return;

        const wrapper = target.closest(".value-wrapper");
        if (!wrapper) return;
        if ((wrapper.dataset.type || "") !== "enum") return;

        const choices = JSON.parse(wrapper.dataset.choices || "[]");
        const value = (target.value ?? "").trim();

        if (value.startsWith("{{") && target.tagName === "SELECT") {
            wrapper.querySelector(".enum-select-mode").style.display = "none";
            wrapper.querySelector(".enum-template-mode").style.display = "";
            const ta = wrapper.querySelector("textarea.response-input[data-field]");
            if (ta) ta.value = value;
            syncToJSON();
            return;
        }

        if (!value.startsWith("{{") && target.tagName === "TEXTAREA") {
            wrapper.querySelector(".enum-select-mode").style.display = "";
            wrapper.querySelector(".enum-template-mode").style.display = "none";
            // Try to match to an option; otherwise leave as unset
            const sel = wrapper.querySelector("select.response-input[data-field]");
            if (sel) {
                const match = choices.includes(value) ? value : "";
                sel.value = match;
            }
            syncToJSON();
            return;
        }
    }
    container.addEventListener("input", fixEnumValueMode);

    // Finish restore
    setTimeout(() => { delete container.dataset.restoring; syncToJSON(); }, 0);

    // Change notification API
    let changeHandler = () => {};
    function emitChange() { changeHandler(getValue()); }

    function getValue() {
        try { return JSON.parse(hidden.value || "{}"); }
        catch { return {}; }
    }

    console.log(`✅ Response Builder READY for ${containerId}`);

    return {
        getValue,
        onChange(fn) { if (typeof fn === "function") changeHandler = fn; }
    };
}
