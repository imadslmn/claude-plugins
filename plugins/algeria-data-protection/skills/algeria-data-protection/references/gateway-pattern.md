# The egress gateway pattern

One module owns every call to a foreign AI provider. Everything else in the codebase talks to the
gateway, never to the provider. The gateway de-identifies on the way out, re-identifies on the way
back, refuses to send anything identifying, and emits audit metadata. There is no self-hosted model:
every task either crosses the border de-identified or does not run.

## Responsibilities

1. **Provider allowlist and credentials** — the only place API keys, base URLs and model names live.
2. **Task registry** — task types are declared once (`tasks.yaml`) with the input classes they are
   allowed to carry and the legal basis the flow relies on. A call site names a task; it cannot
   pick a model or bypass redaction.
3. **Redaction** — every outbound string passes through the redactor; structured inputs are
   projected to a view object first.
4. **Egress assertion** — before sending, the gateway re-scans the final payload (system + messages +
   tool results) with the redactor in *detect* mode. If anything is detected, the call is refused
   (not silently redacted a second time — that would mean a code path bypassed step 3). Tasks whose
   registry entry declares `basis: consent` or `basis: anpdp_authorization` may carry identity, and
   the gateway checks that the consent record / authorization flag exists for that subject before
   sending.
5. **Re-hydration** — placeholders are restored in the response text and in any structured output
   fields that may contain them.
6. **Audit metadata** — request id, task type, model, redactor version, counts per placeholder
   class, basis used, token usage, latency. No content.
7. **Kill switch** — `AI_EGRESS_ENABLED=false` makes every call raise a typed `AIFeaturesPaused`
   error that the application handles gracefully (feature hidden, "temporarily unavailable" state,
   queued for later). Nothing core to the product may depend on the gateway being up.

## Task registry example

```yaml
# ai_gateway/tasks.yaml
invoice_extract:
  basis: deidentified         # nothing identifying leaves; the default and the goal
  input_classes: [amounts, dates, product_lines, ORG_placeholder]
  description: "Extract line items and totals from OCR text of a supplier invoice"
ticket_classify:
  basis: deidentified
  input_classes: [free_text_redacted]
candidate_score:
  basis: deidentified         # redesigned: surrogate id + attributes, no identity (see SKILL.md)
  input_classes: [profile_view]
whatsapp_reply:
  basis: consent              # B2C: user-initiated chat, consent captured in the welcome flow
  input_classes: [free_text_redacted, first_name]
  consent_scope: "whatsapp_assistant_v2"
payroll_anomaly_explain:
  basis: anpdp_authorization  # ships OFF until compliance/anpdp/ holds the written authorization
  input_classes: [employee_view]
  enabled: false
```

The registry is also what goes into `compliance/DATA-FLOWS.md`; generate the markdown table from
the YAML in CI so the two cannot drift apart.

## Python skeleton (FastAPI projects)

```python
# ai_gateway/__init__.py
import os, uuid, logging
from dataclasses import dataclass, field
from .redactor import Redactor, DetectedPII     # port of scripts/pii_redactor.py (+ NER spans)
from .providers import FOREIGN                  # the ONLY file importing a provider SDK
from .tasks import TASKS                        # loaded from tasks.yaml
from .consent import has_consent                # reads the project's consent log (Algerian DB)

log = logging.getLogger("ai_gateway")
EGRESS_ENABLED = os.getenv("AI_EGRESS_ENABLED", "true").lower() == "true"

class AIFeaturesPaused(Exception): ...
class EgressBlocked(Exception): ...

@dataclass
class GatewayResult:
    text: str
    request_id: str
    meta: dict = field(default_factory=dict)

def complete(task: str, *, system: str, user: str, context: list[str] = (),
             subject_id: str | None = None) -> GatewayResult:
    if not EGRESS_ENABLED:
        raise AIFeaturesPaused("AI egress disabled by configuration")
    spec = TASKS[task]
    if not spec.enabled:
        raise AIFeaturesPaused(f"task {task} is not enabled (basis: {spec.basis})")
    rid = uuid.uuid4().hex

    red = Redactor(version="2026.10")
    sys_r, usr_r = red.redact(system), red.redact(user)
    ctx_r = [red.redact(c) for c in context]

    leaks: list[DetectedPII] = red.detect("\n".join([sys_r, usr_r, *ctx_r]))
    if leaks and spec.basis == "deidentified":
        log.error("ai_gateway.egress_blocked", extra={"rid": rid, "task": task,
                  "classes": sorted({l.cls for l in leaks})})
        raise EgressBlocked(f"{len(leaks)} identifiers would leave Algeria; refusing call")
    if spec.basis == "consent" and not has_consent(subject_id, spec.consent_scope):
        raise EgressBlocked(f"no recorded consent for subject under scope {spec.consent_scope}")

    sys_r += "\nTokens like <PERSON_1> are placeholders for redacted values; keep them exactly as written."
    out = FOREIGN.chat(system=sys_r, user=usr_r, context=ctx_r, model=spec.model)
    text = red.rehydrate(out.text)

    log.info("ai_gateway", extra={"rid": rid, "task": task, "basis": spec.basis, "model": spec.model,
             "placeholders": red.counts(), "redactor": red.version, "usage": out.usage})
    return GatewayResult(text, rid, {"placeholders": red.counts(), "usage": out.usage})
```

`ai_gateway/providers.py` is the only file allowed to `import anthropic` / `import openai` / call
`https://api.*`. It sets the organisation's ZDR / no-training options, disables provider logging
where offered, pins the processing region if the provider lets you, and reads keys from the
environment.

The `consent` basis is deliberately narrow: the subject must have given an express, logged consent
naming the transfer and the purpose, and the call must carry only the fields `input_classes` lists
(a first name for a friendly reply, not the whole profile). Redaction still runs on everything
else in the prompt.

## TypeScript skeleton (Node/Next.js projects)

```ts
// src/services/ai-gateway/index.ts
import { Redactor } from "./redactor";
import { foreign } from "./providers";          // only file importing @anthropic-ai/sdk, openai…
import { TASKS } from "./tasks";
import { hasConsent } from "./consent";

const EGRESS = process.env.AI_EGRESS_ENABLED !== "false";
export class AIFeaturesPaused extends Error {}
export class EgressBlocked extends Error {}

export async function complete(task: keyof typeof TASKS,
  input: { system: string; user: string; context?: string[]; subjectId?: string }) {
  if (!EGRESS) throw new AIFeaturesPaused("AI egress disabled");
  const spec = TASKS[task];
  if (!spec.enabled) throw new AIFeaturesPaused(`task ${task} not enabled (basis ${spec.basis})`);
  const rid = crypto.randomUUID();

  const red = new Redactor("2026.10");
  const system = red.redact(input.system) + "\nTokens like <PERSON_1> are placeholders; keep them exactly as written.";
  const user = red.redact(input.user);
  const context = (input.context ?? []).map((c) => red.redact(c));

  const leaks = red.detect([system, user, ...context].join("\n"));
  if (leaks.length && spec.basis === "deidentified") {
    audit({ rid, task, blocked: true, classes: [...new Set(leaks.map((l) => l.cls))] });
    throw new EgressBlocked(`${leaks.length} identifiers would leave Algeria`);
  }
  if (spec.basis === "consent" && !(await hasConsent(input.subjectId, spec.consentScope))) {
    throw new EgressBlocked(`no recorded consent for scope ${spec.consentScope}`);
  }

  const out = await foreign.chat({ system, user, context, model: spec.model });
  audit({ rid, task, basis: spec.basis, model: spec.model, placeholders: red.counts(), usage: out.usage });
  return { text: red.rehydrate(out.text), rid };
}

function audit(e: Record<string, unknown>) { console.log(JSON.stringify({ evt: "ai_gateway", ...e })); }
```

## Structured inputs: project, don't pass

Bad: `complete("order_analyze", user=json.dumps(order))` — the order row has the customer's name,
phone and address.

Good:

```python
view = {
  "order_id": surrogate(order.id, rid),        # per-request opaque id
  "lines": [{"sku": l.sku, "qty": l.qty, "unit_price": l.price} for l in order.lines],
  "total": order.total, "currency": "DZD",
  "wilaya": order.wilaya,                      # coarse geography is fine; street address is not
  "customer_segment": order.customer.segment,  # not the customer
}
result = complete("order_analyze", system=PROMPT, user=json.dumps(view))
```

Surrogates are mapped back on the Algerian side; the provider never sees a real key. Build these
view objects as typed functions (`order_view(order)`, `candidate_view(candidate)`) so a reviewer can
read in one place exactly what leaves for each task.

## Agent loops and tool results

In an agentic flow the model sees tool results (DB rows, API responses) on every turn. Those go
through the same projection + redaction as user text before each model call; the gateway applies
it inside the loop, and tools that return identity-bearing rows must return views instead. A tool
named `get_customer` that hands the model a full record is the most common way a compliant design
quietly stops being one.

## n8n workflows

n8n is self-hosted in Algeria. Foreign-provider nodes (OpenAI, Anthropic, HTTP Request to api.*) are
only allowed in a sub-workflow named `AI Gateway` that receives already-redacted text — preferably
by calling the project's FastAPI gateway over the LAN so there is one implementation and one audit
log. Execution data retention in n8n: set `EXECUTIONS_DATA_SAVE_ON_SUCCESS=none` or prune
aggressively; execution logs store full payloads, including inputs before redaction.

## Model-side hygiene

- Keep placeholders rare and short; models mangle `<CUSTOMER_PHONE_NUMBER_12>` more than `<PHONE_2>`.
- When the task output is structured (JSON), validate the schema after re-hydration; a placeholder
  that was not restored means the model altered it — retry once with a stricter instruction, then
  fail the request rather than returning a half-identified answer.
- Few-shot examples in prompts are the most common place for real customer data to sneak in. Build
  examples from synthetic fixtures only.
- Free-text NER (names, addresses) runs on the Algerian server as a small CPU classifier (GLiNER,
  spaCy `fr`), never by sending the text to the provider "to find the names first".
