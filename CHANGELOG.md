# Changelog

## algeria-data-protection

### 1.1.0 — 2026-10-26
- No self-hosted model anywhere in the posture: the "local lane" is removed. Every call crosses the
  border through the gateway or does not run.
- Decision tree gains a "redesign the feature" branch with six concrete moves (surrogate +
  attributes, template out / fill locally, coarsening, rules for sensitive fields, task splitting,
  B2C consent as last resort). Sensitive data is handled by deterministic code, never by AI.
- Task registry now declares a legal `basis` per task (deidentified / consent / anpdp_authorization)
  and the gateway enforces it (egress assertion, consent-record check, `enabled` flag).
- Kill switch raises a typed `AIFeaturesPaused` error instead of falling back to a local model.
- Free-text NER is a small CPU classifier (GLiNER / spaCy), explicitly not an LLM.

### 1.0.0 — 2026-10-26
- Initial release: SKILL.md (three walls, decision tree, gateway rules, local lane, leak points,
  compliance folder, workflow), law summary for 18-07 / 25-11, Algerian PII taxonomy with fixture,
  gateway skeletons (Python, TypeScript, n8n), French paper-trail templates, `pii_redactor.py`,
  `audit_egress.py`.
