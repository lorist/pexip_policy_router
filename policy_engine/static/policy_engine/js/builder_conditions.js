// policy_engine/static/policy_engine/js/builder_conditions.js

import { safeJSON } from "./utils.js";

/**
 * Determine the *effective* type for operator selection.
 * IdP attributes are ALWAYS treated as strings (even if values look boolean).
 */
function getEffectiveType(fieldName, schemaFields) {
    if (fieldName.startsWith("idp_attributes.")) {
        return "string";
    }
    const fieldInfo = schemaFields.find(f => f.name === fieldName);
    return fieldInfo?.type || "string";  // fallback to string
}

/**
 * Operator sets per effective type.
 */
const OPERATOR_SETS = {
    string: [
        "equals",
        "not_equals",
        "contains",
        "not_contains",
        "starts_with",
        "ends_with",
        "regex_match",
        "in_list",
        // Template / Jinja awareness
        "template_equals",
        "template_contains",
        "template_regex_match",
        "template_boolean"
    ],

    number: [
        "equals", "not_equals",
        ">", "<", ">=", "<=",
    ],

    bool: [
        "is_true",
        "is_false",
        "equals",
        "not_equals"
    ]
};

const OPERATOR_LABELS = {
    equals: "equals",
    not_equals: "not equals",
    contains: "contains",
    not_contains: "does not contain",
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

    // Template-based operators
    template_equals: "Template equals (Jinja allowed)",
    template_contains: "Template contains (Jinja allowed)",
    template_regex_match: "Template regex (Jinja allowed)",
    template_boolean: "Template boolean (expression must render true)"
};

// ----------------------------------------------
// FIELD SELECT
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
// OPERATOR SELECT (patched)
// ----------------------------------------------
export function buildOperatorSelect(field, schemaFields, selected = "equals") {
    const effectiveType = getEffectiveType(field, schemaFields);
    const ops = OPERATOR_SETS[effectiveType] || OPERATOR_SETS.string;

    return `
    <select class="form-select form-select-sm condition-operator">
        ${ops.map(o =>
            `<option value="${o}" ${o === selected ? "selected" : ""}>
                ${OPERATOR_LABELS[o] || o}
            </option>`
        ).join("")}
    </select>`;
}

// ----------------------------------------------
// CONDITION ROW (input now depends on type)
// ----------------------------------------------
export function buildConditionRow(schema, field = "", operator = "equals", value = "") {
    const schemaFields = schema.fields || [];
    const effectiveType = getEffectiveType(field, schemaFields);

    const datalistId = `suggest-${field}-${Math.random().toString(36).slice(2, 8)}`;
    const suggestions = (window.CURRENT_FIELD_SUGGESTIONS || {})[field] || [];
    const datalist = suggestions.map(v => `<option value="${v}"></option>`).join("");

    let valueInput = "";

    if (operator.startsWith("template_")) {
        valueInput = `<textarea class="form-control form-control-sm condition-value" rows="2"
            placeholder="{% if remote_display_name|lower == 'bob' %}true{% endif %}">${value || ""}</textarea>`;
    } else if (effectiveType === "bool") {
        valueInput = `
            <select class="form-select form-select-sm condition-value">
                <option value="true" ${value === "true" ? "selected" : ""}>true</option>
                <option value="false" ${value === "false" ? "selected" : ""}>false</option>
            </select>`;
    } else if (effectiveType === "number") {
        valueInput = `<input type="number" class="form-control form-control-sm condition-value" value="${value || ""}">`;
    } else {
        valueInput = `<input type="text" class="form-control form-control-sm condition-value"
            value="${value || ""}" list="${datalistId}">`;
    }

    return `
    <div class="condition-row d-flex align-items-start mb-2">
      <div class="flex-grow-1 me-2">${buildFieldSelect(schemaFields, field)}</div>
      <div class="me-2">${buildOperatorSelect(field, schemaFields, operator)}</div>

      <div class="flex-grow-1 me-2 position-relative">
        ${valueInput}
        <datalist id="${datalistId}">${datalist}</datalist>
      </div>

      <button type="button" class="btn btn-sm btn-outline-secondary preview-condition" title="Preview">👁</button>
      <button type="button" class="btn btn-sm btn-outline-danger remove-condition">✖</button>
    </div>`;
}

// ----------------------------------------------
// GROUP + SYNC + RESTORE (unchanged)
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
