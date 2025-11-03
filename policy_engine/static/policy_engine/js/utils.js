// policy_engine/static/policy_engine/js/utils.js

/**
 * Safe JSON parser — returns a parsed object or {} if invalid.
 * Accepts strings, objects, or undefined/null values.
 */
export function safeJSON(input) {
    if (!input) return {};
    if (typeof input === "object") return input;

    try {
        const cleaned = input
            .trim()                       // remove whitespace around JSON
            .replace(/&quot;/g, '"')
            .replace(/&#x27;/g, "'")
            .replace(/\s*\n\s*/g, "");    // remove indentation & newline padding

        return JSON.parse(cleaned);
    } catch (err) {
        console.warn("⚠️ Failed to parse JSON:", err, input);
        return {};
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
