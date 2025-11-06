// policy_engine/static/policy_engine/js/utils.js

/**
 * Safe JSON parser — returns a parsed object or {} if invalid.
 * Accepts strings, objects, or undefined/null values.
 */

export function safeJSON(text, fallback = {}) {
  try {
    return JSON.parse((text || "").trim() || "{}");
  } catch (err) {
    try {
      let raw = (text || "").trim();
      if (!raw) return fallback;

      // 1) Temporarily protect any Jinja blocks so we don't touch them
      const keeps = [];
      raw = raw.replace(/{{[\s\S]*?}}/g, (m) => {
        keeps.push(m);
        return `__JINJA_${keeps.length - 1}__`;
      });

      // 2) Convert Python-ish to JSON-ish
      raw = raw
        .replace(/'([^']*)'/g, '"$1"')         // single → double quotes
        .replace(/\bTrue\b/g, "true")
        .replace(/\bFalse\b/g, "false")
        .replace(/\bNone\b/g, "null");

      // 3) Restore Jinja blocks
      raw = raw.replace(/__JINJA_(\d+)__/g, (_, i) => keeps[Number(i)]);

      return JSON.parse(raw);
    } catch (err2) {
      console.warn("⚠️ Failed to parse JSON:", err, "\n", text);
      return fallback;
    }
  }
}



/**
 * Waits for a DOM element to exist before resolving.
 * Useful for dynamic tabs or forms.
 */
export function waitForElement(selector, maxRetries = 20, interval = 200) {
    return new Promise((resolve, reject) => {
        let attempts = 0;
        const timer = setInterval(() => {
            const el = document.querySelector(selector);
            if (el) {
                clearInterval(timer);
                resolve(el);
            } else if (++attempts >= maxRetries) {
                clearInterval(timer);
                reject(new Error(`Element not found: ${selector}`));
            }
        }, interval);
    });
}

/**
 * Waits for multiple JSON schemas to load.
 * Typically used before initializing builders.
 */
export async function waitForSchemas(...ids) {
    const results = {};
    for (const id of ids) {
        const el = await waitForElement(`#${id}`);
        const text = el.textContent || "{}";
        results[id] = safeJSON(text);
    }
    return results;
}
