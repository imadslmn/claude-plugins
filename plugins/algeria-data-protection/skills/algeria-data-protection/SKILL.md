---
name: algeria-data-protection
description: >
  Architecture and compliance rules for any project handling personal data of people in Algeria
  (Law 18-07 as amended by Law 25-11, enforced by the ANPDP) while using AI/LLM APIs or cloud services
  outside Algeria. Use it every time you start a Solrus project, add or change an LLM call, build a
  prompt, set up RAG/embeddings, OCR, a chatbot (WhatsApp, web, voice), an n8n/automation workflow,
  logging/tracing/error tracking, backups or deployment — even if the user does not mention the law.
  Also use it when the user says "loi 18-07", "25-11", "ANPDP", "données personnelles", "RGPD algérien",
  "DPO", "transfert de données", "ZDR", "hébergement en Algérie", or asks for a privacy policy, DPA,
  registre des traitements, DPIA, or a data-protection section in a proposal / cahier des charges.
  Goal: personal data stays on Algerian servers, nothing identifying crosses the border inside an API
  call, and the paper trail the ANPDP expects exists in the repo from day one.
---

# Algeria data protection for AI-backed projects

## Why this exists

Algeria's Law 18-07 (amended July 2025 by Law 25-11) treats *any* communication of personal data to a
system outside the country as a cross-border transfer. Transfers to a non-adequate country (which, as of
late 2026, is effectively every country — the ANPDP has published no adequacy list, and the US and EU are
not on one) require **prior written ANPDP authorization** or a narrow statutory exception. Penalties are
criminal (fines and up to 5 years' imprisonment), and processors (sous-traitants, i.e. Solrus) carry
their own obligations and liability.

"Zero data retention" at the provider and "our server is in Algiers" do **not** change this. ZDR governs
what the provider does *after* receiving the data; the law is triggered the moment the data *leaves*.
The only configuration that avoids the transfer regime entirely is one where **no personal data is in the
request** that goes abroad.

So the architecture rule is simple to state and must be enforced mechanically:

> Personal data lives and is processed on Algerian infrastructure. Any call to a foreign API carries
> de-identified content only. One module in the codebase is allowed to make those calls, and it
> de-identifies before sending and re-identifies after receiving.

Everything below operationalizes that rule. Read `references/law-summary.md` when you need the legal
detail (articles, exceptions, obligations); read the other references when you reach that step.

## The three walls

Apply all three on every project. If a project cannot satisfy wall 2 for some flow, the flow goes to
the decision tree below — it is never silently shipped.

1. **Residency wall** — databases, file storage, vector stores, backups, queues, logs, error tracking,
   analytics, automation runners (n8n), and the application itself run on servers physically in Algeria.
   Foreign SaaS for any of these is a transfer.
2. **Egress wall** — a single `ai_gateway` module is the only code allowed to call a foreign AI
   provider. It strips or tokenizes personal data before the call and restores it after. Nothing else
   imports a provider SDK. The gateway logs metadata, never prompt content.
3. **Paper wall** — the repo carries a `compliance/` folder with the processing register, data-flow map,
   retention schedule, DPA references, privacy policy (FR + AR), consent copy, and breach procedure,
   kept current as the code changes. This is what an ANPDP inspection or a client's DPO will ask for.

## What counts as personal data here

Anything that identifies a natural person directly or indirectly. In Algerian projects the usual
suspects are: names (Arabic and Latin script), phone numbers (+213 / 05-06-07), email addresses,
postal addresses, NIN (numéro d'identification national, 18 digits), NSS (sécurité sociale), NIF, RC
number of a sole trader, CCP / RIB / IBAN DZ, licence plates, dates of birth, photos, voice recordings,
signatures, IP addresses, device IDs, geolocation (the pointage app!), employee IDs when a lookup table
exists, and free text that names people (support tickets, CVs, contracts, invoices from individuals).

**Sensitive data** (health, biometric, genetic, religion, political opinion, union membership, ethnic
origin, criminal record, sexual life) is a separate regime: processing needs ANPDP *authorization*
even domestically, and it should never leave Algeria under any mechanism. Crèche apps (children's
health/allergies), HR apps (medical certificates), and anything with face recognition or fingerprints
fall here. Treat children's data as sensitive in practice even where the law is silent.

A pseudonymized record (name replaced by a token, but a mapping exists somewhere) is **still personal
data** under the 2025 definitions. Only irreversibly anonymized content is outside the law. The gateway
therefore aims for the foreign provider receiving content that *it* cannot re-identify — which keeps the
legal position defensible — while the project still treats the overall processing as personal data
processing (declared, registered, secured).

Full taxonomy with regexes: `references/pii-algeria.md`.

## Decision tree for every data flow that leaves Algeria

Run this for each flow (LLM call, embedding, OCR, email/SMS provider, WhatsApp, analytics, error
tracking, backup). Write the outcome into `compliance/DATA-FLOWS.md`.

```
Does the payload contain personal data (per the taxonomy)?
├─ No ───────────────────────────────────────────────────────▶ OK. Document it. Done.
└─ Yes
   Can the task be done without the identifiers?
   (classify, summarize, extract amounts/dates, draft from a template, translate, answer from a KB)
   ├─ Yes ──▶ Route through ai_gateway with redaction/tokenization. ─▶ OK. Document the token classes sent.
   └─ No  (the task is *about* the person: "write to Mr X", "score this CV", "diagnose this child")
      Can the feature be redesigned so the model works on a de-identified view?
      (surrogate ids + attributes instead of identity; coarsened fields; the model produces a
       template and the Algerian side fills in the name; sensitive fields handled by rules, not AI)
      ├─ Yes ──▶ Redesign, then route through ai_gateway. ─▶ OK. Document the view sent.
      └─ No
         Is there a statutory exception that fits cleanly?
         (express, informed consent naming the transfer; necessity to perform a contract
          with that person; legal obligation; vital interest; court proceedings)
         ├─ Yes ──▶ Collect/record the consent or contract basis + ZDR + DPA.
         │          Still file the flow in the ANPDP declaration. Legal review before go-live.
         └─ No  ──▶ Client files an ANPDP authorization dossier for this flow.
                    The flow is feature-flagged OFF until written authorization exists.
                    Sensitive data (health, biometric, children's health): never on this branch;
                    do it without AI or not at all.
```

Never resolve the last branch by "we'll fix it later". Starting a transfer while the authorization is
pending is itself an offence, independently of the outcome.

**There is no self-hosted LLM in this posture.** Solrus does not run open-weight models in Algeria;
every model call goes to a foreign provider through the gateway. That makes the redesign branch and
the consent branch the only two ways to ship a feature that needs identity, so push hard on the
redesign branch first — most "about the person" tasks are really "about the attributes", and the
identity can be re-attached on the Algerian side after the model answers.

## Architecture: the egress gateway

Design and enforce the gateway as described in `references/gateway-pattern.md` (has Python and
TypeScript skeletons). The essentials:

- **One module, one allowlist.** `ai_gateway/` (or `services/ai_gateway.ts`) owns provider clients,
  API keys, model names, and a provider allowlist. Any other file importing `anthropic`, `openai`,
  `google.generativeai`, `mistralai`, `cohere`, `@anthropic-ai/sdk`, `langchain_*` provider classes,
  or calling their HTTP endpoints directly is a build failure. `scripts/audit_egress.py` checks this.
- **Redact before send.** Run the redactor over every string that will leave: system prompt, user
  content, tool results, few-shot examples, RAG chunks, document text. Replace each entity with a
  typed placeholder (`<PERSON_1>`, `<PHONE_2>`, `<NIN_1>`, `<ADDRESS_1>`, `<ORG_1>` for sole traders).
  Keep the placeholder→value map in memory (or a Redis in Algeria) keyed by request id, with a TTL of
  minutes, never written to the same log as the prompt.
- **Re-hydrate after receive.** Swap placeholders back in the response before it reaches the user or
  the database. Handle models that paraphrase placeholders (`<PERSON_1>'s phone` → still fine; `the
  person` → acceptable loss). Keep placeholders simple and few so small models keep them intact.
- **Structured data: send fields, not records.** When the task is "analyze this order/invoice/
  attendance", build a view object with only non-identifying fields (amounts, dates, categories,
  product codes, durations, counts) and opaque surrogate keys. Join back locally.
- **Documents and images.** OCR locally (Tesseract / PaddleOCR / docTR on the Algerian server), then
  redact the text, then send text. Do not send scans of IDs, contracts, CVs, or invoices from
  individuals to a vision API. If a vision model is required on a document that carries identity
  (an ID card, a signed contract), mask those regions locally first (OCR gives you the coordinates
  of what the redactor matched; black them out before the image leaves) or put the flow on the
  consent/authorization branch.
- **RAG / embeddings.** Redact chunks before they are embedded, whichever embedding API is used,
  so the vector store and the provider only ever hold de-identified text. Keep the vector store in
  Algeria (pgvector in the project's Postgres is enough for SME scale). Accept the retrieval hit on
  name-based queries; route "find everything about Mr X" through a plain DB lookup, not the index.
- **Free-text names and addresses.** Regex catches structured identifiers; for names in running
  text (Arabic and Latin, nicknames, places) add a small CPU NER library on the Algerian server
  (GLiNER, spaCy `fr`, or a fine-tuned token classifier — classifiers, not LLMs) and feed its spans
  into the redactor. Measure recall on the project's fixtures; where it is not good enough, coarsen
  the input instead (send the ticket category and the question, not the whole ticket).
- **Provider settings as policy.** Use the provider's zero-retention / no-training organisation
  setting, disable provider-side prompt logging, pin the data-processing region if offered, and keep
  the signed DPA in `compliance/dpa/`. These are *safeguards* that go in the dossier, not permissions.
- **Logging and tracing.** Log request id, model, token counts, latency, placeholder class counts,
  redactor version. Never log raw prompts or responses at INFO. Self-host Langfuse/Phoenix in
  Algeria if tracing is needed; never LangSmith/Helicone/cloud tracing. Same for Sentry: self-hosted
  GlitchTip/Sentry in Algeria, with PII scrubbing on.
- **Kill switch.** A single env var (`AI_EGRESS_ENABLED=false`) must make the gateway return a
  graceful "AI features paused" error and let the rest of the application keep working. A client
  inspection or incident should never require a code deploy to stop the flow, and no feature should
  be designed so that the app is unusable when the gateway is off.
- **Tests.** The redactor has a fixture file of Algerian-format samples (phone, NIN, NIF, RIB, Arabic
  names, mixed FR/AR text) and a test asserting none survive. The gateway has a test asserting that a
  request with those fixtures produces an outbound payload containing zero of them.

## Redesigning "about the person" features so they can cross the border

Since no model runs in Algeria, a feature that seems to need identity has to be reshaped until it
doesn't. The moves that work, in the order to try them:

1. **Surrogate + attributes.** Replace the person with `<ID_1>` and send only the attributes the
   task needs. "Score this candidate for the sales role" becomes "score this profile: 6 years B2B
   sales, French C1, Arabic native, wilaya 16, last role: key accounts" — no name, no phone, no
   date of birth, no photo. The ranking comes back keyed by surrogate; the Algerian side joins it.
2. **Template out, fill in locally.** "Write a payment reminder to Mr X about invoice F-0412" becomes
   "write a payment reminder for `<PERSON_1>` about invoice `<ID_1>` of 125 000 DZD, 30 days late";
   re-hydration puts the name back. The model never needed to know who.
3. **Coarsen what identifies indirectly.** Exact dates → month; exact salary → band; small company
   + title → role category; street address → wilaya/commune. Keep the fields that carry the signal.
4. **Rules, not AI, for sensitive fields.** Allergies, medical certificates, disciplinary records,
   biometric checks: handle with deterministic code on the Algerian server. The AI can work on the
   rest of the record with those fields stripped.
5. **Split the task.** If one prompt needs both identity and judgement, split it: the judgement
   step crosses the border de-identified, the identity-bearing step (lookup, notification, filing)
   stays in plain code.
6. **Consent as the last resort, and only for the person who can give it.** B2C flows (a customer
   chatting on WhatsApp, a parent using the crèche app) can carry an express, informed consent to the
   specific transfer, collected at onboarding and logged. Employee data under a power imbalance and
   children's data are weak ground for consent — keep those on moves 1–5.

Write the chosen move into `compliance/DATA-FLOWS.md` next to the flow, with the exact view or
placeholder classes that leave. If none of the six moves fits and the data is sensitive, the feature
is not built with AI.

## Common leak points to check on every project

These are where Solrus projects actually leak, independent of the LLM call:

- n8n Cloud, Make, Zapier → self-host n8n in Algeria. Credentials and execution logs hold full payloads.
- Meta WhatsApp Business API, Instagram/Facebook APIs → the channel itself is a transfer out of Algeria.
  Rely on the user-initiated-contact / contract-performance basis, say so in the privacy notice, keep
  the AI step de-identified, and do not enrich WhatsApp payloads with data the user didn't provide.
- Email/SMS providers (Mailgun, SendGrid, Twilio) → prefer an Algerian SMTP/SMS relay; if not possible,
  minimize to what the message needs and document the basis.
- Google Sheets / Drive / Notion as "the database" → not in Algeria. Replace with Postgres on the VPS.
- Cloud backups (S3, Backblaze, GitHub for data dumps) → backups are a transfer. Keep them in Algeria,
  encrypted, with keys held in Algeria.
- Analytics (GA4, Mixpanel, Hotjar) → self-hosted Plausible/Umami or nothing; never session replay.
- Error tracking, APM, LLM tracing → self-hosted in Algeria with scrubbing.
- Mobile apps (Flutter): crash reporting (Crashlytics), push (FCM holds device tokens — document it),
  geolocation sent to foreign map APIs → send coordinates only when required and never with identity.
- Dev/staging environments seeded with production dumps → seed with synthetic data only.
- Claude Code / Copilot sessions themselves: never paste production records or client dumps into
  prompts; use synthetic fixtures. Do not commit client databases to repos.

## Paper wall: the `compliance/` folder

Create it with the first commit of every project, from the templates in
`references/paper-trail-templates.md`:

```
compliance/
├── REGISTRE-DES-TRAITEMENTS.md   # one entry per processing activity (purpose, data, basis, recipients,
│                                 # retention, security, transfers) — the 25-11 register
├── DATA-FLOWS.md                 # every outbound flow + decision-tree outcome + token classes sent
├── RETENTION.md                  # per data category: duration, trigger, deletion mechanism
├── SECURITY-MEASURES.md          # encryption, access control, logging, backups, incident response
├── BREACH-PROCEDURE.md           # detection → containment → ANPDP notification (days, not weeks) → subjects
├── DPIA.md                       # only when profiling / sensitive data / large scale / children
├── privacy-policy.fr.md          # published on the product; AR version alongside
├── consent-copy.md               # exact wording shown at collection points
├── dpa/                          # signed DPAs with every processor (AI provider, hosting, SMS...)
└── anpdp/                        # declaration receipt, authorization requests and decisions
```

Roles to make explicit in the first page of `REGISTRE-DES-TRAITEMENTS.md`: the **client** is the
responsable du traitement (controller); **Solrus** is the sous-traitant (processor). The client files
the ANPDP declaration/authorization and designates the DPO; Solrus supplies the technical annexes and
keeps its own processor register. Put a data-processing annex in every Solrus proposal and contract
(template in the reference file) so this is agreed before development starts.

## Workflow when this skill triggers

1. **Project kickoff / proposal / CDC**: list the data categories and every system outside Algeria the
   project will touch. Run the decision tree per flow. Put the result and the architecture (gateway +
   residency + redesign moves) in the proposal's data-protection section. Flag any flow that needs an
   ANPDP authorization as a milestone with a lead time of 1–3 months, before the dependent feature.
2. **Scaffolding**: create `ai_gateway/`, `compliance/`, the redactor fixture tests, the egress audit in
   CI, and the kill switch env var. Pin the provider allowlist.
3. **Every new LLM/automation feature**: open `DATA-FLOWS.md`, add the flow, run the tree, implement
   via the gateway, add fixtures for any new PII shape the feature introduces.
4. **Before each release**: run `scripts/audit_egress.py`, re-read `DATA-FLOWS.md` against the diff,
   check logs for raw prompts, confirm backups/staging are in Algeria.
5. **Handover**: deliver the `compliance/` folder, the DPA set, and a one-page "ce qui quitte
   l'Algérie et pourquoi" summary to the client's DPO.

When a request conflicts with these rules (e.g. "just send the whole customer table to the model"),
say so, show the compliant alternative from the tree, and only proceed on the compliant path. Being
the vendor that can say "nothing identifying leaves the country" is a selling point; being the one
whose client gets an ANPDP notice is not.

## Scripts

- `scripts/audit_egress.py <repo>` — fails if provider SDKs or endpoints are used outside the gateway
  module, if raw prompt logging patterns are found, or if known foreign-SaaS hostnames appear in config.
  Run in CI.
- `scripts/pii_redactor.py` — reference implementation of a regex redactor for Algerian formats with
  placeholder mapping and re-hydration; import it as a starting point or port it. Run the file directly
  to see it on sample text.

## Limits of this skill

This encodes an engineering posture, not legal advice. ANPDP practice is evolving and not all
implementing texts are public. Before go-live of any project that still has a flow in the "exception"
or "authorization" branch, or that touches sensitive/children's data, get an Algerian lawyer with ANPDP
filing experience to review `compliance/`. Verify article numbers and deadlines in
`references/law-summary.md` against the Journal Officiel when citing them to a client.
