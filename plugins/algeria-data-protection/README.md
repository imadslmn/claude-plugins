# algeria-data-protection

A Claude Code skill that keeps AI-backed projects compliant with Algeria's personal-data law
(Law 18-07 as amended by Law 25-11, enforced by the ANPDP) while still using LLM APIs hosted
outside Algeria.

## Install

One step (Claude Code 2.1.275 or later):

```
/plugin install algeria-data-protection --marketplace imadslmn/claude-plugins
```

Or in two steps:

```
/plugin marketplace add imadslmn/claude-plugins
/plugin install algeria-data-protection@solrus
```

## The problem it solves

Under the law, sending personal data to a system outside Algeria is a cross-border transfer that
needs prior ANPDP authorization or a narrow statutory exception. A provider's zero-data-retention
setting does not change that: the transfer happens the moment the request leaves. The only
configuration that avoids the transfer regime is one where no personal data is in the request.

## What the skill makes Claude do

- **Residency wall** — databases, storage, backups, logs, tracing, automation runners (n8n) stay on
  Algerian infrastructure.
- **Egress wall** — one `ai_gateway` module is the only code allowed to call a foreign AI provider.
  It replaces names, phones, NIN/NIF/RC, bank identifiers, addresses and other identifiers with
  typed placeholders before the call, asserts nothing identifying remains in the outbound payload,
  and restores the values after the response.
- **No self-hosted model** — tasks that seem to be *about* a person (CV scoring, reminders,
  reports) are redesigned so the model works on surrogates and attributes and the identity is
  re-attached on the Algerian side; sensitive fields (health, biometric, children's health) are
  handled by deterministic code, never by AI.
- **Paper wall** — a `compliance/` folder in every repo: processing register, data-flow map,
  retention schedule, breach procedure, DPIA triggers, privacy policy (FR/AR), consent copy, and a
  processor annex for proposals and contracts.
- A decision tree Claude runs on every outbound flow (LLM, embeddings, OCR, WhatsApp, SMS,
  analytics, backups) and records in `compliance/DATA-FLOWS.md`.

## Contents

```
skills/algeria-data-protection/
├── SKILL.md                              # the posture, decision tree, architecture rules, workflow
├── references/law-summary.md             # 18-07 / 25-11 for engineers, articles marked (v) to verify
├── references/pii-algeria.md             # taxonomy + regexes for Algerian identifiers, test fixture
├── references/gateway-pattern.md         # Python (FastAPI) and TypeScript gateway skeletons, n8n rules
├── references/paper-trail-templates.md   # French templates for the compliance/ folder
├── scripts/pii_redactor.py               # working stdlib redactor with placeholder round-trip
└── scripts/audit_egress.py               # CI check: no provider SDK/host outside the gateway
```

## Usage

The skill triggers automatically when you start a project, add an LLM call, set up RAG, build a
chatbot, configure logging or deployment, or mention the law, the ANPDP, a DPO, a privacy policy
or a data-protection section for a proposal. Invoke it directly with
`/algeria-data-protection:algeria-data-protection`.

Run the audit in CI from the installed plugin path, or copy the script into the repo:

```bash
python3 scripts/audit_egress.py . --strict
python3 scripts/pii_redactor.py            # demo on the built-in fixture
```

## Caveats

This is an engineering posture, not legal advice. Article numbers marked (v) in the law summary
should be checked against the Journal Officiel before being quoted to a client or regulator, and
the ANPDP breach-notification deadline is cited inconsistently in secondary sources. Have a lawyer
with ANPDP filing experience review the `compliance/` folder before go-live.

Maintained by [Solrus](https://solrus.pro), Algiers. MIT license.
