// policy_engine/static/policy_engine/js/builder_response.js
import { safeJSON } from "./utils.js";

/**
 * Initialize a response builder UI.
 * Supports: string, number, enum, bool, list[item_schema]
 * Now with: Enum <select> <-> <textarea> auto-switch for Jinja template mode.
 */
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
    // Field builder helpers (PATCHED ENUM LOGIC)
    // -------------------------------------------------------------------------
    function buildInput(field, meta) {
        const type = meta.type;
        const existingVal = (existingData && existingData[field]) || "";
        const isTemplate = typeof existingVal === "string" && existingVal.trim().startsWith("{{");

        if (type === "enum") {
            const choices = meta.choices || [];

            return `
            <div class="value-wrapper" data-field="${field}" data-type="enum" data-choices='${JSON.stringify(choices)}'>
                <div class="enum-mode enum-select-mode" style="${isTemplate ? "display:none;" : ""}">
                    <div class="d-flex gap-2">
                        <select class="form-select form-select-sm response-input" data-field="${field}">
                            <option value="">(unset)</option>
                            ${choices.map(v => `<option value="${v}" ${v === existingVal ? "selected" : ""}>${v}</option>`).join("")}
                        </select>
                        <button type="button" class="btn btn-sm btn-outline-secondary enum-switch-template" data-field="${field}">
                            {{ }}
                        </button>
                    </div>
                </div>

                <div class="enum-mode enum-template-mode" style="${isTemplate ? "" : "display:none;"}">
                    <div class="d-flex gap-2">
                        <textarea class="form-control form-control-sm response-input" data-field="${field}" rows="2">${isTemplate ? existingVal : ""}</textarea>
                        <button type="button" class="btn btn-sm btn-outline-secondary enum-switch-select" data-field="${field}">
                            ⬇︎
                        </button>
                    </div>
                </div>
            </div>`;
        }

        if (type === "bool") {
            return `
            <div class="value-wrapper" data-field="${field}">
                <div class="bool-select-mode">
                    <div class="input-group input-group-sm">
                        <select class="form-select response-input" data-field="${field}" data-type="bool">
                            <option value="">(unset)</option>
                            <option value="true">true</option>
                            <option value="false">false</option>
                        </select>
                        <button type="button" class="btn btn-outline-secondary btn-sm bool-switch-template" title="Switch to template mode">
                            {{ }}
                        </button>
                    </div>
                </div>
                <div class="bool-template-mode" style="display:none;">
                    <textarea class="form-control form-control-sm response-template-input" rows="1" data-field="${field}" data-type="string" placeholder="{{ expression }}"></textarea>
                    <button type="button" class="btn btn-outline-secondary btn-sm mt-1 bool-switch-select" title="Switch back to dropdown">
                        ⬇
                    </button>
                </div>
            </div>`;
        }


        if (type === "number") {
            return `<input type="number" class="form-control form-control-sm response-input" data-field="${field}" data-type="number">`;
        }

        if (type === "list" && meta.item_schema) {
            return buildListField(field, meta);
        }

        return `<input type="text" class="form-control form-control-sm response-input" data-field="${field}" data-type="string">`;
    }


    function buildListField(field, meta) {
        const subId = `${containerId}-${field}-list`;
        return `
        <div class="nested-list border rounded p-2 bg-light mb-2" data-field="${field}">
            <div class="d-flex justify-content-between align-items-center mb-2">
                <strong>${field}</strong>
                <button type="button" class="btn btn-sm btn-outline-primary add-list-item" data-subid="${subId}">➕ Add Item</button>
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
    // Restore existing data
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
                    const inputEl = card.querySelector(`[data-field="${k}"]`);
                    if (inputEl) inputEl.value = v;
                });
            });
        } else {
            const input = wrapper.querySelector(".response-input");
            if (input) input.value = value;
        }
    });

    // -------------------------------------------------------------------------
    // Sync to hidden JSON
    // -------------------------------------------------------------------------
    function syncToJSON() {
        if (container.dataset.restoring === "true") return;

        const data = {};
        container.querySelectorAll(".response-field").forEach(wrapper => {
            const field = wrapper.dataset.field;
            const meta = schema[field];
            if (!meta) return;

            if (meta.type === "list") {
                const list = [];
                wrapper.querySelectorAll(".nested-item").forEach(itemEl => {
                    const obj = {};
                    Object.entries(meta.item_schema).forEach(([k, subMeta]) => {
                        const i = itemEl.querySelector(`[data-field="${k}"]`);
                        if (!i || i.value.trim() === "") return;
                        let val = i.value.trim();
                        if (subMeta.type === "bool") val = (val === "true");
                        else if (subMeta.type === "number") val = Number(val);
                        obj[k] = val;
                    });
                    if (Object.keys(obj).length) list.push(obj);
                });
                if (list.length) data[field] = list;
            } else {
                const input = wrapper.querySelector(".response-input");
                if (!input || input.value.trim() === "") return;
                let val = input.value.trim();
                if (meta.type === "bool") val = (val === "true");
                else if (meta.type === "number") val = Number(val);
                data[field] = val;
            }
        });

        hidden.value = JSON.stringify(data, null, 2);
        emitChange();
    }

    container.addEventListener("input", syncToJSON);

    container.addEventListener("click", e => {
        const btn = e.target.closest("button");
        if (!btn) return;

        // -------------------------------------------------
        // LIST ADD / REMOVE (existing behavior)
        // -------------------------------------------------
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

        // -------------------------------------------------
        // NEW: ENUM MODE SWITCH: Dropdown → Jinja template
        // -------------------------------------------------
        if (btn.classList.contains("enum-switch-template")) {
            const wrapper = btn.closest(".value-wrapper");
            wrapper.querySelector(".enum-select-mode").style.display = "none";
            wrapper.querySelector(".enum-template-mode").style.display = "";
            syncToJSON();
            return;
        }

        // -------------------------------------------------
        // NEW: ENUM MODE SWITCH: Template → Dropdown
        // -------------------------------------------------
        if (btn.classList.contains("enum-switch-select")) {
            const wrapper = btn.closest(".value-wrapper");
            wrapper.querySelector(".enum-select-mode").style.display = "";
            wrapper.querySelector(".enum-template-mode").style.display = "none";
            syncToJSON();
            return;
        }
        // -------------------------------------------------
        // NEW: BOOL MODE SWITCH: Dropdown → Template
        // -------------------------------------------------
        if (btn.classList.contains("bool-switch-template")) {
            const wrapper = btn.closest(".value-wrapper");
            wrapper.querySelector(".bool-select-mode").style.display = "none";
            wrapper.querySelector(".bool-template-mode").style.display = "";
            syncToJSON();
            return;
        }

        // -------------------------------------------------
        // NEW: BOOL MODE SWITCH: Template → Dropdown
        // -------------------------------------------------
        if (btn.classList.contains("bool-switch-select")) {
            const wrapper = btn.closest(".value-wrapper");
            wrapper.querySelector(".bool-select-mode").style.display = "";
            wrapper.querySelector(".bool-template-mode").style.display = "none";
            syncToJSON();
            return;
        }

    });


    // -------------------------------------------------------------------------
    // NEW: Auto-switch ENUM <select> <-> <textarea> based on Jinja syntax
    // -------------------------------------------------------------------------
    function fixEnumValueMode(e) {
        const target = e.target;
        if (!target.classList.contains("response-input")) return;

        const wrapper = target.closest(".value-wrapper");
        if (!wrapper) return;

        const field = wrapper.dataset.field;
        const type = wrapper.dataset.type;
        if (type !== "enum") return;

        const choices = JSON.parse(wrapper.dataset.choices || "[]");
        const value = target.value.trim();

        if (value.startsWith("{{") && target.tagName === "SELECT") {
            wrapper.innerHTML = `
                <textarea class="form-control form-control-sm response-input" data-field="${field}" rows="2">${value}</textarea>
            `;
            syncToJSON();
            return;
        }

        if (!value.startsWith("{{") && target.tagName === "TEXTAREA") {
            wrapper.innerHTML = `
                <select class="form-select form-select-sm response-input" data-field="${field}">
                    <option value="">(unset)</option>
                    ${choices.map(v => `<option value="${v}" ${v === value ? "selected" : ""}>${v}</option>`).join("")}
                </select>
            `;
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
