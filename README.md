# Pexip Policy Router & Advanced Policy Engine

A **Django-based external policy orchestration layer** for **Pexip Infinity**.  
It allows administrators to define **routing, override, and dynamic transformation rules** for both:

- **Service Policy** (`/policy/v1/service/configuration`)
- **Participant Policy** (`/policy/v1/participant/properties`)

Rules may:
- Proxy to upstream systems
- Apply **dynamic Jinja-based policy transformations**
- Perform **conditional routing** using a graphical policy logic builder
- Use **IdP attributes** for entitlement-based access decisions

---

## ✨ Major Capabilities

| Capability | Description |
|-----------|-------------|
| **Regex Rule Routing** | Match calls by `local_alias`, `protocol`, and `call_direction` |
| **Upstream Proxying** | Forward requests to remote policy systems with optional Basic Auth |
| **Local Override Responses** | Return custom JSON without proxying upstream |
| **Advanced Logic Engine** | Visual UI for nested AND/OR conditions |
| **Jinja Template Support** | Render dynamic values from call information & IdP claims |
| **Per-Rule Response Modes** | Continue, Reject (with reason), Redirect (to new alias) |
| **Identity Attributes Registry** | Manage user attributes made available to logic & templating |
| **CSV Import/Export** | Full configuration portability (rules, logic, identities) |
| **Condition Preview Tools** | Test a single rule or full logic outcome with real call data |
| **Audit Logging** | Records every request, matched rule, and resulting response |

---

## 🧠 Policy Logic Editor

The **Logic Editor** provides:
- Nested groups with **Match All (AND)** / **Match Any (OR)**
- Field-aware operator selection based on detected type:
  - `string`, `number`, `bool`, and **IdP attributes**
- Real-time **value suggestions**, based on previous call data
- Support for advanced **template operators**:
  - `template_equals`
  - `template_contains`
  - `template_regex_match`
  - `template_boolean`

Example logic:

```
IF idp_attributes.role == "doctor"
AND protocol == "sip"
THEN redirect to: meeting@hospital.example.com
```

### Available Response Modes

| Mode | Description |
|------|-------------|
| **Continue** | Return standard policy response (optionally templated) |
| **Reject** | Reject the call with a custom message |
| **Redirect** | Send the caller to a new alias |

---

## 🔐 Identity Attributes (New)

You may define **IdP attribute names** once, and they become:

- Autocomplete suggestions in the **Logic Editor**
- Accessible in **Jinja templates** via:  
  `idp_attributes.<name>`

Examples:

| Name | Description |
|------|-------------|
| `role` | Access class (doctor / nurse / patient / admin) |
| `location` | Facility / hospital site code |
| `license_class` | Professional credential category |

### Included in CSV Import/Export ✅
Identity attributes now **persist across environments**.

---

## 🧪 Testing & Preview Tools

| Tool | Description |
|------|-------------|
| **Single Condition Preview** | Test one field/operator/value pair with a real call |
| **Full Logic Preview** | Show match result & final rendered response |
| **Recent Call Samples** | Pick any logged call to preview logic against |

These tools **do not affect production behavior** — they are safe for testing.

---

## 🗂 CSV Import / Export (Updated)

The CSV includes:

| Type | Included |
|------|---------|
| Rule metadata | ✅ |
| Participant & Service logic enable state | ✅ |
| Nested logic **conditions** (JSON) | ✅ |
| Response templates (JSON) | ✅ |
| **Identity Attributes list** | ✅ |

This allows **full restore or migration between environments**.

---

## 📈 UI & Workflow Enhancements

| Feature | Description |
|---------|-------------|
| Drag-and-Drop Rule Priority | Reorder instantly |
| Rule Usage Metrics | Track match count & timestamp |
| Duplicate Regex Detection | Highlights overlapping rule patterns |
| Rich Log Viewer | Filter by rule, alias, protocol, host, date |
| Syntax Highlighted JSON | Pretty-print request/response logs |
| Rule Duplication | One-click copy |

---

## 📦 Installation (Development)

```bash
git clone https://github.com/your-org/pexip-policy-router.git
cd pexip-policy-router

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

python manage.py migrate
python manage.py createsuperuser
python manage.py runserver 0.0.0.0:8000
```

---

## 🌐 Web UI

| Page | URL |
|------|-----|
| Rule List | `/rules/` |
| Policy Logic Editor | `/policy-engine/<rule_id>/` |
| Identity Attributes | `/identity-attributes/` |
| Logs | `/logs/` |
| CSV Import/Export | `/manage-rules/` |

---

## ✅ Running Tests

```bash
pytest -v
```

---

## 🚀 Deployment Notes

The application runs well under:
- Docker
- Kubernetes
- Azure Web App (Linux)
- Traditional VM / bare-metal with systemd

See `DeployAzureWebApp.md` for production deployment guidance.

---

## License

Commercial usage license customized per organization.  
Contact your Pexip Solutions Architect.
