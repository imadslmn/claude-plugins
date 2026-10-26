# Personal data taxonomy for Algerian projects

Use this to decide what the redactor must catch and what a "view object" may contain. Every entity type
has a placeholder class used by the gateway (`<CLASS_n>`). Regexes are starting points for
`scripts/pii_redactor.py`; tune them per project and keep fixtures for anything you change.

## Direct identifiers — always redact before egress

| Class | What | Format notes | Regex sketch |
|---|---|---|---|
| `PERSON` | Names, Latin and Arabic script, with or without titles (M., Mme, Dr, Si, Hadj, السيد, السيدة) | Regex alone is weak; combine a title-triggered regex with a small CPU NER classifier (GLiNER/spaCy, not an LLM) for free text | `(?:M\.|Mme|Mlle|Dr|Pr|Si|Hadj|السيد|السيدة|الدكتور)\s+[\p{L}'\-]+(?:\s+[\p{L}'\-]+){0,3}` |
| `PHONE` | Mobile 05/06/07 + 8 digits; landline 0 + area + 7 digits; international +213 / 00213 | Spaces, dots, dashes between groups are common | `(?:\+213|00213|0)[\s.\-]?[5-7](?:[\s.\-]?\d){8}` and `(?:\+213|00213|0)[\s.\-]?[2-4]\d(?:[\s.\-]?\d){7}` |
| `EMAIL` | Email addresses | | standard |
| `NIN` | Numéro d'identification national (CNIBE / passport) — 18 digits | Often starts with 1 or 2; appears on ID scans and HR records | `\b[12]\d{17}\b` |
| `NSS` | Numéro de sécurité sociale (CNAS/CASNOS) | Variable format, commonly 12 digits, sometimes with spaces | `\b\d{2}\s?\d{4}\s?\d{6}\b` (verify per client) |
| `NIF` | Numéro d'identification fiscale — 15 digits | Also identifies **companies**; treat as personal when the taxpayer is a natural person (sole trader, auto-entrepreneur) | `\b\d{15}\b` |
| `RC` | Registre de commerce number | Patterns like `16/00-1234567B23` or `23B1234567-16/00`; personal when the merchant is a natural person | `\b\d{2}/\d{2}-\d{7}[AB]\d{2}\b` and `\b\d{2}[AB]\d{7}-\d{2}/\d{2}\b` |
| `AI` | Article d'imposition — 11 digits | Tax ID shown on invoices | `\b\d{11}\b` (context-gated to "AI" / "Art" labels) |
| `BANK` | RIB (20 digits: 3 bank + 5 agency + 10 account + 2 key), CCP (`\d{7,10}` key `\d{2}`), IBAN DZ (`DZ` + 22 digits), card numbers | | `\b\d{3}\s?\d{5}\s?\d{10}\s?\d{2}\b`, `\bDZ\d{2}(?:\s?\d{4}){5}\d{2}\b`, `\bCCP\s*n?°?\s*\d{7,10}(?:\s*(?:clé|cle)?\s*\d{2})?` |
| `PLATE` | Vehicle plate `\d{5,6} \d{3} \d{2}` (number, year/category, wilaya) | | `\b\d{5,6}[\s\-]?\d{3}[\s\-]?\d{2}\b` |
| `ADDRESS` | Postal addresses, cités, lots, BP, wilaya + commune combos | Hard with regex; gate on keywords (rue, cité, lot, bloc, bt, n°, BP, حي, شارع) + CPU NER classifier | keyword-triggered span up to the next line/period |
| `DOB` | Dates of birth | Only when near "né(e) le", "date de naissance", "تاريخ الميلاد"; other dates are fine to send | context-gated date regex |
| `GEO` | Latitude/longitude pairs, GPS traces | Pointage app, delivery apps | `-?\d{1,2}\.\d{4,},\s*-?\d{1,3}\.\d{4,}` |
| `IP` / `DEVICE` | IPv4/6, IMEI (15 digits), push tokens, device IDs | | standard |
| `URL_PROFILE` | Social profile URLs, WhatsApp wa.me links with numbers | | `wa\.me/\d+`, `(?:facebook|instagram|linkedin)\.com/[\w.\-]+` |
| `IMAGE` / `AUDIO` | Photos of people, ID scans, voice notes | Not text — never send to a foreign vision/speech API; process locally | n/a |

## Indirect identifiers — redact or coarsen depending on context

- Employee / customer / patient / child internal IDs when a lookup table exists → replace with a
  per-request surrogate (`<ID_1>`), never the real key.
- Job title + company + city (e.g. "DRH chez X à Blida") identifies a single person → coarsen to role
  category or redact the company for small companies.
- Exact salary, exact dates of events (hire, dismissal, birth of a child), diagnoses, school class →
  coarsen (ranges, month precision) or strip the field from the view.
- Free text written by or about a person (support tickets, reviews, complaints, CV bodies, meeting
  notes) → assume it contains names and phones; run the full redactor plus a CPU NER classifier.

## Sensitive data — never leaves Algeria; handled by deterministic code, not AI

Health (certificates, allergies, diagnoses, prescriptions, sick leave reasons), biometric (face
templates, fingerprints, voice prints), religion, political opinion, union membership, ethnic origin,
criminal record, sexual life. For crèche/school projects also treat all child data as sensitive in
practice.

## Safe to send (no redaction needed, still document it)

Amounts, totals, VAT rates, product names and codes, quantities, generic dates not tied to a person
(invoice date, delivery date), categories, statuses, durations, counts, aggregates, templated text
with placeholders, public company names and public business addresses of legal entities (SARL, SPA,
EURL — not sole traders), generic questions, documentation, code.

## Fixture file (keep in `tests/fixtures/pii_dz.txt`)

Every project's redactor test should include at least these shapes and assert none survive egress:

```
Bonjour, je suis M. Karim Benaissa, tel 0550 12 34 56 ou +213 661 23 45 67, email k.benaissa@example.dz
NIN 109876543210987654 — NSS 15 0987 654321 — NIF 000016001234567 — RC 16/00-1234567B23
RIB 004 00123 1234567890 12 — IBAN DZ58 0040 0123 1234 5678 9012 34 — CCP 1234567 clé 45
Adresse : Cité 1200 logements, Bt 12, n°4, Bab Ezzouar, Alger. Né le 12/03/1988.
السيدة فاطمة بوعلام، الهاتف 0770123456، حي الياسمين، البليدة
Véhicule 123456 123 16. Position 36.7210, 3.1830.
```

## Placeholder grammar

`<CLASS_n>` with `n` starting at 1 per request, same value → same placeholder within a request.
Keep the vocabulary small (PERSON, PHONE, EMAIL, ID, BANK, ADDRESS, DOB, GEO, ORG, OTHER) so models
preserve them. Tell the model in the system prompt: "Tokens like <PERSON_1> are placeholders for
redacted values; keep them exactly as written in your answer."
