# Locale Guidelines

All frontend-generated UI labels, help text, validation messages, action text, empty states, pagination controls, and error-state copy must go through i18n keys. This follows the project rule that frontend and backend changes must consider multilingual support and must not hardcode Chinese or English user-facing messages.

External agent CLI payloads are treated as data, not UI copy. Values returned by tools such as `claude plugin list --json`, plugin manifest descriptions, marketplace names, plugin errors, dependency names, and README content may pass through verbatim because translating or rewriting them would change the source data being inspected.
