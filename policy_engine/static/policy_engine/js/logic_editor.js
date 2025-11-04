// policy_engine/static/policy_engine/js/logic_editor.js
// Logic editor boot: per-tab var/autocomplete, condition JSON sync,
// response builders, recent-call loader, and Jinja var/filter autocomplete.

import { waitForSchemas } from "./utils.js";
import {
    renderGroupFromJSON,
    syncJSON,
    buildConditionRow,
    buildGroup,
    buildOperatorSelect
} from "./builder_conditions.js";
import { initResponseBuilder } from "./builder_response.js";

// Make operator builder available globally for dynamic refresh
window.buildOperatorSelect = buildOperatorSelect;
let participantBuilder = null;
let serviceBuilder = null;
////////////////////////////////////////////////////////////////////////////////
// Boot
////////////////////////////////////////////////////////////////////////////////
document.addEventListener("DOMContentLoaded", () => {
    console.log("🧠 Logic Editor Ready");

    // ---------------------------
    // Per-tab globals for suggestions & available vars
    // ---------------------------
    function setSuggestSources(tabType) {
        if (tabType === "service") {
            window.CURRENT_FIELD_SUGGESTIONS = window.SERVICE_FIELD_VALUES || {};
            window.CURRENT_AVAILABLE_VARS = window.SERVICE_AVAILABLE_VARS || [];
        } else {
            window.CURRENT_FIELD_SUGGESTIONS = window.PARTICIPANT_FIELD_VALUES || {};
            window.CURRENT_AVAILABLE_VARS = window.PARTICIPANT_AVAILABLE_VARS || [];
        }
    }

    function syncRejectUI() {
        ["participant", "service"].forEach(type => {
            const form = document.querySelector(`form input[name='logic_type'][value='${type}']`)?.closest("form");
            if (!form) return;

            const rejectInput = form.querySelector("input[name$='reject_reason'], textarea[name$='reject_reason']");
            const wrapper = form.querySelector(`.response-builder-wrapper[data-type='${type}']`);

            if (!rejectInput || !wrapper) return;

            if ((rejectInput.value || "").trim() !== "") {
                wrapper.style.display = "none"; // hide builder
            } else {
                wrapper.style.display = ""; // show builder
            }
        });
    }

    document.addEventListener("input", syncRejectUI);
    document.addEventListener("DOMContentLoaded", syncRejectUI);

    const activeTab = (new URLSearchParams(location.search)).get("tab") === "service" ? "service" : "participant";
    setSuggestSources(activeTab);

    // When user clicks the bootstrap tabs (they are links to ?tab=…)
    document.querySelectorAll(".nav-link").forEach(link => {
        link.addEventListener("click", () => {
            const isService = link.href.includes("tab=service");
            setSuggestSources(isService ? "service" : "participant");

            // ✅ Update condition schema reference on tab change
            window.CURRENT_CONDITION_SCHEMA = isService
                ? window.SERVICE_CONDITION_SCHEMA
                : window.PARTICIPANT_CONDITION_SCHEMA;
        });
    });

    // ---------------------------
    // Restore UI: conditions & response builders
    // ---------------------------
    waitForSchemas().then(() => {
        ["participant", "service"].forEach(type => {
            // Condition groups
            const schema = safeParseJSONFromTag(`${type}_condition_schema_json`, { fields: [] });
            if (!schema.fields) schema.fields = [];
            const saved = safeParseJSONFromTag(`${type}_conditions_json`, { combiner: "all", rules: [] });

            const container = document.getElementById(`${type}-conditions`);
            const hidden = document.querySelector(`input[name='${type}_conditions']`);
            if (!container || !hidden) return;

            const restored = renderGroupFromJSON(saved, schema);
            container.replaceWith(restored);
            restored.id = `${type}-conditions`;
            restored.classList.add("logic-condition-root");

            restored.addEventListener("input", () => syncJSON(restored, hidden));
            restored.addEventListener("click", e => {
                const btn = e.target.closest("button");
                if (!btn) return;

                const list = restored.querySelector(":scope > .conditions-list");
                if (!list) return;

                if (btn.classList.contains("add-condition")) {
                    list.insertAdjacentHTML("beforeend", buildConditionRow(schema, "", "equals", ""));
                }
                if (btn.classList.contains("add-group")) {
                    list.insertAdjacentHTML("beforeend", buildGroup());
                }
                if (btn.classList.contains("remove-condition")) {
                    btn.closest(".condition-row")?.remove();
                }
                if (btn.classList.contains("remove-group")) {
                    btn.closest(".condition-group")?.remove();
                }
                syncJSON(restored, hidden);
            });

            // Initial sync
            syncJSON(restored, hidden);
        });

        // ---------------------------
        // Response builders
        // ---------------------------
        ["participant", "service"].forEach(type => {
            const builderId = `${type}-response-builder`;
            const hiddenSelector = `input[name='${type}_response_json']`;
            const schemaText = getText(`${type}_response_schema_json`);
            const savedText = getText(`${type}_response_json_data`);

            const builder = initResponseBuilder(builderId, hiddenSelector, schemaText, savedText);

            // ⭐ STORE GLOBAL REF
            if (type === "participant") {
                participantBuilder = builder;
            } else {
                serviceBuilder = builder;
            }

            // Ensure hidden contains initial builder state
            if (builder?.getValue) {
                document.querySelector(hiddenSelector).value =
                    JSON.stringify(builder.getValue(), null, 2);
            }

            if (builder?.onChange) {
                builder.onChange(value => {
                    document.querySelector(hiddenSelector).value =
                        JSON.stringify(value, null, 2);
                });
            }
        });




        console.log(" UI restored and builders initialized");
    });

    // Register schemas globally so change-handler can access the correct types
    window.PARTICIPANT_CONDITION_SCHEMA = safeParseJSONFromTag("participant_condition_schema_json", { fields: [] });
    window.SERVICE_CONDITION_SCHEMA = safeParseJSONFromTag("service_condition_schema_json", { fields: [] });

    // Set current schema (default tab)
    window.CURRENT_CONDITION_SCHEMA = (activeTab === "service")
        ? window.SERVICE_CONDITION_SCHEMA
        : window.PARTICIPANT_CONDITION_SCHEMA;

    // Dynamically refresh operator + value input when field changes
    document.body.addEventListener("change", (event) => {
        if (!event.target.classList.contains("condition-field")) return;

        const row = event.target.closest(".condition-row");
        if (!row) return;

        const field = event.target.value;
        const schema = window.CURRENT_CONDITION_SCHEMA || { fields: [] };
        const schemaFields = schema.fields || [];

        // Determine type (schema or idp_attributes.* override to string)
        const effectiveType = field.startsWith("idp_attributes.")
            ? "string"
            : (schemaFields.find(f => f.name === field)?.type || "string");

        // --- Rebuild Operator Select ---
        const operatorSelectEl = row.querySelector(".condition-operator");
        const currentOperator = operatorSelectEl.value;

        const newOperator = window.buildOperatorSelect(field, schemaFields, currentOperator);
        operatorSelectEl.insertAdjacentHTML("afterend", newOperator);
        operatorSelectEl.remove();


        // --- Rebuild Value Input ---
        const valueEl = row.querySelector(".condition-value");
        const currentValue = valueEl.value;
        let newValueHTML = "";

        if (effectiveType === "bool") {
            newValueHTML = `
                <select class="form-select form-select-sm condition-value">
                    <option value="true" ${currentValue === "true" ? "selected" : ""}>true</option>
                    <option value="false" ${currentValue === "false" ? "selected" : ""}>false</option>
                </select>`;
        } else if (effectiveType === "number") {
            newValueHTML = `<input type="number" class="form-control form-control-sm condition-value" value="${currentValue}">`;
        } else {
            newValueHTML = `<input type="text" class="form-control form-control-sm condition-value" value="${currentValue}">`;
        }

        valueEl.outerHTML = newValueHTML;
    });


    // ---------------------------
    // Preview + Call Info Loader (both tabs)
    // ---------------------------
    document.addEventListener("click", e => {
        const btn = e.target.closest("button");
        if (!btn) return;

        // Load recent call info into test box
        if (btn.classList.contains("load-call-info")) {
            const type = btn.dataset.type;
            const raw = document.getElementById(`${type}-call-info-history`)?.value;
            if (!raw) return;
            const textarea = document.getElementById(`${type}-call-info`);
            try {
                textarea.value = JSON.stringify(JSON.parse(raw), null, 2);
            } catch {
                textarea.value = raw;
            }
            return;
        }

        // Preview logic (uses live builder state)
        if (btn.classList.contains("preview-logic")) {
            const type = btn.dataset.type;
            const form = btn.closest("form");
            const ruleId = document.getElementById("rule-id").value;

            const conditions = parseJSON(form.querySelector(`input[name='${type}_conditions']`)?.value) || {};

            // ✅ ALWAYS READ CURRENT BUILDER OUTPUT
            const builder = (type === "participant") ? participantBuilder : serviceBuilder;
            const liveResponseObj = builder?.getValue?.() || { status: "success", action: "continue", result: {} };
            const response = liveResponseObj; // <- use live builder result instead of stale hidden input

            let callInfo = {};
            try {
                callInfo = JSON.parse(document.getElementById(`${type}-call-info`).value || "{}");
            } catch {
                alert("⚠️ Invalid JSON in Call Info box");
                return;
            }

            fetch(`/policy-engine/${ruleId}/logic-preview/`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": document.querySelector("[name='csrfmiddlewaretoken']").value
                },
                body: JSON.stringify({ type, conditions, response, call_info: callInfo })
            })
            .then(r => r.json())
            .then(data => {
                const out = document.getElementById(`${type}-preview-result`);
                out.style.display = "block";

                const finalResponse = data.rendered_response ?? data;
                out.textContent = JSON.stringify(finalResponse, null, 2);
            });
        }


        // Per-condition Preview
        if (btn.classList.contains("preview-condition")) {
            const row = btn.closest(".condition-row");
            const field = row.querySelector(".condition-field")?.value || "";
            const operator = row.querySelector(".condition-operator")?.value || "equals";
            const value = row.querySelector(".condition-value")?.value || "";

            const form = btn.closest("form");
            const type = form.querySelector("input[name='logic_type']").value;
            let callInfo = {};

            try {
                callInfo = JSON.parse(document.getElementById(`${type}-call-info`).value || "{}");
            } catch {
                alert("⚠️ Invalid JSON in Test Call Info");
                return;
            }

            const ruleId = document.getElementById("rule-id").value;

            fetch(`/policy-engine/${ruleId}/condition-preview/`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": document.querySelector("[name='csrfmiddlewaretoken']").value
                },
                body: JSON.stringify({ field, operator, value, call_info: callInfo })
            })
            .then(r => r.json())
            .then(res => {
                row.querySelectorAll(".cond-preview-chip").forEach(el => el.remove());
                const chip = document.createElement("span");
                chip.className = `cond-preview-chip badge ${res.matched ? "bg-success" : "bg-danger"}`;
                chip.style.marginLeft = "8px";
                chip.textContent = res.matched ? "matched" : "no match";
                btn.insertAdjacentElement("afterend", chip);
            });
        }

    });

    // ---------------------------
    // Before submit: ensure JSON is synced
    // ---------------------------
    document.querySelectorAll("form").forEach(form => {
        form.addEventListener("submit", () => {
            const type = form.querySelector("input[name='logic_type']")?.value;
            if (!type) return;
            const root = form.querySelector(".logic-condition-root");
            const hidden = form.querySelector(`input[name='${type}_conditions']`);
            if (root && hidden) syncJSON(root, hidden);
        });
    });

    // ---------------------------
    // Track active editor (for chip insertion & autocomplete)
    // ---------------------------
    document.addEventListener("focusin", e => {
        if (isResponseInput(e.target)) {
            document.querySelectorAll(".response-json-editor-active")
                .forEach(el => el.classList.remove("response-json-editor-active"));
            e.target.classList.add("response-json-editor-active");
        }
    });

    // ---------------------------
    // Gentle suggestions for condition value inputs
    // ---------------------------
    document.addEventListener("input", e => {
        const input = e.target;
        if (!input || !input.closest(".condition-row")) return;
        if (!isConditionValueInput(input)) return;

        const row = input.closest(".condition-row");
        const fieldName = getConditionFieldName(row);
        if (!fieldName) return;

        const suggestions = (window.CURRENT_FIELD_SUGGESTIONS?.[fieldName]) || [];
        if (!Array.isArray(suggestions) || suggestions.length === 0) return;

        const listId = `dl-${fieldName}`;
        let dl = document.getElementById(listId);
        if (!dl) {
            dl = document.createElement("datalist");
            dl.id = listId;
            document.body.appendChild(dl);
        }
        dl.innerHTML = suggestions.slice(0, 50).map(v => `<option value="${escapeHtml(String(v))}"></option>`).join("");
        input.setAttribute("list", listId);
    });

    // ---------------------------
    // Chip variable insertion (from any tab)
    // ---------------------------
    document.addEventListener("click", e => {
        const btn = e.target.closest(".insert-var");
        if (!btn) return;

        const editor = document.querySelector(".response-json-editor-active, textarea:focus, input:focus");
        if (!editor) {
            alert("Click inside a response field first.");
            return;
        }
        insertVariableSmart(editor, btn.dataset.var);
    });

    // ---------------------------
    // Autocomplete for {{ var }} and | filter inside response editors
    // ---------------------------
    window.AVAILABLE_JINJA_FILTERS = [
        "upper", "lower", "title", "default", "replace", "split", "first", "last", "length", "trim"
    ];

    let acMenu = null;
    let activeEditor = null;

    function closeMenu() {
        if (acMenu) acMenu.remove();
        acMenu = null;
    }

    function openMenu(target, items) {
        closeMenu();
        if (!items || !items.length) return;

        acMenu = document.createElement("div");
        acMenu.className = "autocomplete-menu";
        acMenu.style.position = "fixed";
        acMenu.style.zIndex = "10000";
        acMenu.innerHTML = items.map(i => `
      <div class="autocomplete-item" data-insert="${i.insert}" title="${i.examples ? ('Examples: ' + i.examples.join(', ')) : ''}">
        ${i.label}
      </div>
    `).join("");

        document.body.appendChild(acMenu);
        const rect = target.getBoundingClientRect();
        acMenu.style.left = rect.left + "px";
        acMenu.style.top = (rect.bottom + 4) + "px";
    }

    document.addEventListener("keyup", e => {
        if (!isResponseInput(e.target)) return;
        activeEditor = e.target;

        const value = activeEditor.value;
        const pos = activeEditor.selectionStart ?? value.length;

        const ctx = detectJinjaContext(value, pos);

        if (ctx.type === "var") {
            const prefix = (ctx.rawPrefix || "").trim().toLowerCase();
            const pool = window.CURRENT_AVAILABLE_VARS || [];
            const matches = pool
                .filter(v => v.toLowerCase().startsWith(prefix))
                .slice(0, 100)
                .map(v => ({
                    label: `{{ ${v} }}`,
                    insert: `${v}`,
                    examples: exampleFor(v)
                }));

            openMenu(activeEditor, matches);
            return;
        }

        if (ctx.type === "filter") {
            const prefix = (ctx.rawPrefix || "").trim().toLowerCase();
            const matches = window.AVAILABLE_JINJA_FILTERS
                .filter(f => f.toLowerCase().startsWith(prefix))
                .slice(0, 50)
                .map(f => ({ label: f, insert: f }));
            openMenu(activeEditor, matches);
            return;
        }

        closeMenu();
    });

    document.addEventListener("click", e => {
        const item = e.target.closest(".autocomplete-item");
        if (!item || !activeEditor) {
            if (!e.target.closest(".autocomplete-menu")) closeMenu();
            return;
        }

        const value = activeEditor.value;
        const pos = activeEditor.selectionStart ?? value.length;
        const insert = item.dataset.insert || "";

        const ctx = detectJinjaContext(value, pos);
        let before = value.slice(0, pos);
        let after = value.slice(pos);

        if (ctx.type === "var") {
            // Replace from `{{ <prefix>` up to cursor with the chosen var
            before = before.replace(/{{\s*[^}|]*$/, "{{ ");
            const hasClosing = /^\s*}}/.test(after);
            const inserted = insert + (hasClosing ? "" : " }}");
            activeEditor.value = before + inserted + after;
            const newPos = (before + insert).length + (hasClosing ? 0 : 3);
            activeEditor.selectionStart = activeEditor.selectionEnd = newPos;
            activeEditor.dispatchEvent(new Event("input", { bubbles: true }));
            closeMenu();
            return;
        }

        if (ctx.type === "filter") {
            before = before.replace(/\|\s*[a-zA-Z_]*/, `| ${insert}`);
            activeEditor.value = before + after;
            const newPos = before.length;
            activeEditor.selectionStart = activeEditor.selectionEnd = newPos;
            activeEditor.dispatchEvent(new Event("input", { bubbles: true }));
            closeMenu();
            return;
        }

        // Fallback
        activeEditor.value = before + insert + after;
        const newPos = before.length + insert.length;
        activeEditor.selectionStart = activeEditor.selectionEnd = newPos;
        activeEditor.dispatchEvent(new Event("input", { bubbles: true }));
        closeMenu();
    });

});

////////////////////////////////////////////////////////////////////////////////
// Helpers
////////////////////////////////////////////////////////////////////////////////
function getText(tagId) {
    const el = document.getElementById(tagId);
    return el ? el.textContent.trim() : "";
}

function safeParseJSONFromTag(tagId, fallback) {
    try {
        const el = document.getElementById(tagId);
        if (!el) return fallback;
        const txt = (el.textContent || "").trim();
        return txt ? JSON.parse(txt) : fallback;
    } catch {
        return fallback;
    }
}


function parseJSON(text) {
    try { return JSON.parse(text || ""); } catch { return null; }
}

function isResponseInput(el) {
    if (!el) return false;
    if (el.classList?.contains("response-input")) return true;
    if (el.tagName === "TEXTAREA") return true;
    if (el.tagName === "INPUT" && (el.type === "text" || el.type === "number")) return true;
    return false;
}

function isConditionValueInput(el) {
    if (!el) return false;
    if (el.classList?.contains("condition-value")) return true;
    if (el.tagName === "INPUT" && el.type === "text") return true;
    return false;
}

function getConditionFieldName(rowEl) {
    if (!rowEl) return null;
    const sel =
        rowEl.querySelector("select[name$='[field]']") ||
        rowEl.querySelector("select.condition-field") ||
        rowEl.querySelector("select[data-role='field']");
    if (!sel) return null;
    const val = sel.value || "";
    return val.trim() || null;
}

function escapeHtml(s) {
    return s.replace(/[&<>"']/g, c => (
        { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
    ));
}

function insertVariableSmart(editor, variableName) {
    const pos = editor.selectionStart ?? editor.value.length;
    const val = editor.value;

    const ctx = detectJinjaContext(val, pos);

    if (ctx.type === "var") {
        const before = val.slice(0, ctx.startOfVarContent);
        const after = val.slice(pos);
        const hasClosing = /^\s*}}/.test(after);
        const inserted = variableName + (hasClosing ? "" : " }}");
        editor.value = before + inserted + after;
        const newPos = (before + variableName).length + (hasClosing ? 0 : 3);
        editor.selectionStart = editor.selectionEnd = newPos;
        editor.dispatchEvent(new Event("input", { bubbles: true }));
        return;
    }

    const insertText = `{{ ${variableName} }}`;
    editor.value = val.slice(0, pos) + insertText + val.slice(pos);
    const newPos = pos + insertText.length;
    editor.selectionStart = editor.selectionEnd = newPos;
    editor.dispatchEvent(new Event("input", { bubbles: true }));
}

function detectJinjaContext(text, cursorPos) {
    const left = text.slice(0, cursorPos);
    const mVar = left.match(/{{\s*([^}|]*)$/);
    if (mVar) {
        const startIndex = left.lastIndexOf("{{");
        const startOfVarContent = startIndex + 2;
        const rawPrefix = mVar[1] || "";
        return { type: "var", startIndex, startOfVarContent, rawPrefix };
    }
    const mFilter = left.match(/\|\s*([a-zA-Z_]*)$/);
    if (mFilter) {
        return { type: "filter", rawPrefix: mFilter[1] || "" };
    }
    return { type: "none" };
}

function exampleFor(varName) {
    // Try both participant/service example pools (server provides only one dict today).
    // If you later split per-tab, you can branch by CURRENT_AVAILABLE_VARS membership.
    const examples = window.call_info_example_values || {};
    const val = examples[varName];
    if (!val) return null;
    return Array.isArray(val) ? val.slice(0, 2) : [String(val)];
}

function syncActionUI() {
    ["participant", "service"].forEach(type => {
        const form = document.querySelector(`form input[name='logic_type'][value='${type}']`)?.closest("form");
        if (!form) return;

        const action = form.querySelector(`select[name='${type}-action'], [name='action']`)?.value;
        const rejectBlock = form.querySelector(`.reject-fields[data-type='${type}']`);
        const responseWrapper = form.querySelector(`.response-wrapper[data-type='${type}']`);

        const isReject = action === "reject";

        if (rejectBlock) rejectBlock.style.display = isReject ? "" : "none";
        if (responseWrapper) responseWrapper.style.display = isReject ? "none" : "";
    });
}

document.addEventListener("input", syncActionUI);
document.addEventListener("DOMContentLoaded", syncActionUI);

document.addEventListener("input", function (e) {
    const sel = e.target.closest(".action-selector");
    if (!sel) return;

    const type = sel.dataset.type;
    const mode = sel.value; // allow | reject | redirect

    document.querySelector(`.${type}-response-block`).style.display = (mode === "allow") ? "" : "none";
    document.querySelector(`.${type}-reject-block`).style.display = (mode === "reject") ? "" : "none";
    document.querySelector(`.${type}-redirect-block`).style.display = (mode === "redirect") ? "" : "none";
});

document.addEventListener("DOMContentLoaded", () => {
  const modal = new bootstrap.Modal(document.getElementById("recentCallModal"));
  const list = document.getElementById("recent-call-list");
  const search = document.getElementById("recent-call-search");

  let itemsCache = [];
  let currentType = null; // <--- TRACK WHICH TAB WE’RE APPLYING TO

  document.querySelectorAll(".load-recent-call-info").forEach(btn => {
    btn.addEventListener("click", async () => {
      currentType = btn.dataset.type; // "participant" or "service"

      try {
        const res = await fetch("/policy-engine/recent-call-info/");
        const { items } = await res.json();

        if (!items || !items.length) {
          alert("No recent calls found.");
          return;
        }

        itemsCache = items;
        search.value = "";
        renderList(itemsCache);

        modal.show();

      } catch (err) {
        console.error(err);
        alert("Error loading call info — check logs.");
      }
    });
  });


  function renderList(data) {
    list.innerHTML = data.map((ci, i) => {
      const call = ci || {};

      const who =
        call.remote_display_name ||
        call.remote_alias ||
        call.participant_uuid ||
        "Unknown";

      const service =
        call.unique_service_name ||
        call.service_name ||
        call.service_tag ||
        "";

      const proto = call.protocol || "";
      const loc = call.location || call.system_location_name || "";
      const dir = call.call_direction || "";

      const tooltip = JSON.stringify(ci, null, 2)
        .replace(/"/g, '&quot;')
        .replace(/\n/g, '&#10;');

      return `
        <li class="list-group-item list-group-item-action recent-call-item py-2"
            data-index="${i}"
            title="${tooltip}">
          <div class="small">
            <strong>${who}</strong>
            ${service ? `<span class="text-muted"> · ${service}</span>` : ""}
            <div class="text-muted small">
              ${proto ? `protocol: ${proto}` : ""}
              ${loc ? ` · location: ${loc}` : ""}
              ${dir ? ` · direction: ${dir}` : ""}
            </div>
          </div>
        </li>
      `;
    }).join("");

    // Click → Insert JSON
    list.querySelectorAll(".recent-call-item").forEach((el) => {
      el.addEventListener("click", () => {
        const textarea = document.getElementById(`${currentType}-call-info`);
        if (!textarea) return;
        textarea.value = JSON.stringify(itemsCache[el.dataset.index], null, 2);
        modal.hide();
      });
    });

    // Tooltip activate
    list.querySelectorAll('[title]').forEach(el => {
      new bootstrap.Tooltip(el);
    });
  }


  // Live search filter
  search.addEventListener("input", () => {
    const q = search.value.toLowerCase();
    const filtered = itemsCache.filter(ci =>
      JSON.stringify(ci).toLowerCase().includes(q)
    );
    renderList(filtered);
  });
});
