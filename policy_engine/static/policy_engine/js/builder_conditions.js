// policy_engine/static/policy_engine/js/builder_conditions.js

import { safeJSON } from "./utils.js";

const OPERATOR_SETS = {
    string: [
        "equals",
        "not_equals",
        "contains",
        "starts_with",
        "ends_with",
        "regex_match",
        "in_list",

        // Template-based comparison (full Jinja allowed)
        "template_equals",
        "template_contains",
        "template_starts_with",
        "template_regex_match",
        "template_boolean"
    ],

    number: ["equals", "not_equals", ">", "<", ">=", "<="],

    bool: ["is_true", "is_false"],

    default: ["equals", "not_equals"]
};


const OPERATOR_LABELS = {
    equals: "equals",
    not_equals: "not equals",
    contains: "contains",
    starts_with: "starts with",
    ends_with: "ends with",
    regex_match: "matches regex",
    in_list: "is in comma-separated list",

    ">": "greater than",
    "<": "less than",
    ">=": "≥ greater or equal",
    "<=": "≤ less or equal",

    is_true: "is true",
    is_false: "is false",

    // Template operators
    template_equals: "Template: equals (Jinja allowed)",
    template_contains: "Template: contains (Jinja allowed)",
    template_starts_with: "Template: starts with (Jinja allowed)",
    template_regex_match: "Template: regex match (Jinja allowed)",
    template_boolean: "Template: boolean expression (must render 'true')"
};

// ----------------------------------------------
// Field Selector
// ----------------------------------------------
function buildFieldSelect(schemaFields, selected = "") {
    return `
    <select class="form-select form-select-sm condition-field">
        ${schemaFields.map(f =>
        `<option value="${f.name}" ${f.name === selected ? "selected" : ""}>${f.label}</option>`
    ).join("")}
    </select>`;
}

// ----------------------------------------------
// Operator Selector
// ----------------------------------------------
function buildOperatorSelect(field, schemaFields, selected = "equals") {
    const fieldInfo = schemaFields.find(f => f.name === field);
    const type = fieldInfo?.type || "string";
    const ops = OPERATOR_SETS[type] || OPERATOR_SETS.default;

    return `
    <select class="form-select form-select-sm condition-operator">
        ${ops.map(o =>
            `<option value="${o}" ${o === selected ? "selected" : ""}>${OPERATOR_LABELS[o] || o}</option>`
        ).join("")}
    </select>`;
}


// ----------------------------------------------
// Condition Row
// ----------------------------------------------
export function buildConditionRow(schema, field = "", operator = "equals", value = "") {
    const schemaFields = schema.fields || [];

    const datalistId = `suggest-${field}-${Math.random().toString(36).slice(2, 8)}`;
    const suggestions = (window.CURRENT_FIELD_SUGGESTIONS || {})[field] || [];
    const datalist = suggestions.map(v => `<option value="${v}"></option>`).join("");

    const isTemplate = operator === "template";

    return `
    <div class="condition-row d-flex align-items-start mb-2">
      <div class="flex-grow-1 me-2">
        ${buildFieldSelect(schemaFields, field)}
      </div>

      <div class="me-2">
        ${buildOperatorSelect(field, schemaFields, operator)}
      </div>

      <div class="flex-grow-1 me-2 position-relative">
        ${isTemplate
            ? `<textarea class="form-control form-control-sm condition-value" rows="2"
                  placeholder="{% if remote_display_name|lower == 'bob' %}true{% endif %}">${value || ""}</textarea>`
            : `<input type="text" class="form-control form-control-sm condition-value"
                  value="${value || ""}" list="${datalistId}">`
        }
        <datalist id="${datalistId}">${datalist}</datalist>
      </div>

      <button type="button" class="btn btn-sm btn-outline-secondary preview-condition"
              title="Preview this condition against Test Call Info">👁</button>

      <button type="button" class="btn btn-sm btn-outline-danger remove-condition">✖</button>
    </div>`;
}



// ----------------------------------------------
// Group Builder
// ----------------------------------------------
export function buildGroup() {
    return `
    <div class="condition-group border rounded p-2 mb-2 bg-white">
        <div class="d-flex align-items-center justify-content-between mb-2">
            <div>
                <label class="me-2 fw-semibold">Match:</label>
                <select class="form-select form-select-sm w-auto group-combiner">
                    <option value="all">All (AND)</option>
                    <option value="any">Any (OR)</option>
                </select>
            </div>
            <div>
                <button type="button" class="btn btn-sm btn-outline-secondary add-condition">➕ Condition</button>
                <button type="button" class="btn btn-sm btn-outline-info add-group">➕ Group</button>
                <button type="button" class="btn btn-sm btn-outline-danger remove-group">✖</button>
            </div>
        </div>
        <div class="conditions-list"></div>
    </div>`;
}


// ----------------------------------------------
// Sync Back to Hidden JSON
// ----------------------------------------------
export function parseGroup(groupEl) {
    const combiner = groupEl.querySelector(".group-combiner")?.value || "all";
    const rules = [];

    groupEl.querySelectorAll(":scope > .conditions-list > *").forEach(el => {
        if (el.classList.contains("condition-row")) {
            rules.push({
                field: el.querySelector(".condition-field")?.value || "",
                operator: el.querySelector(".condition-operator")?.value || "equals",
                value: el.querySelector(".condition-value")?.value || ""
            });
        } else if (el.classList.contains("condition-group")) {
            rules.push(parseGroup(el));
        }
    });

    return { combiner, rules };
}

export function syncJSON(rootGroup, hiddenInput) {
    hiddenInput.value = JSON.stringify(parseGroup(rootGroup), null, 2);
}


// ----------------------------------------------
// Restore Saved JSON
// ----------------------------------------------
export function renderGroupFromJSON(data, schema) {
    const schemaFields = schema.fields || [];
    const groupEl = document.createElement("div");
    groupEl.innerHTML = buildGroup().trim();
    const group = groupEl.firstElementChild;

    group.querySelector(".group-combiner").value = data.combiner || "all";
    const list = group.querySelector(".conditions-list");

    (data.rules || []).forEach(rule => {
        if (rule.rules) {
            list.appendChild(renderGroupFromJSON(rule, schema));
        } else {
            const row = document.createElement("div");
            row.innerHTML = buildConditionRow(schema, rule.field, rule.operator, rule.value).trim();
            list.appendChild(row.firstElementChild);
        }
    });

    return group;
}
