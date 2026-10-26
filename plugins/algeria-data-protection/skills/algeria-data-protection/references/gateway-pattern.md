# The egress gateway pattern

One module owns every call to a foreign AI provider. Everything else in the codebase talks to the
gateway, never to the provider. The gateway de-identifies on the way out, re-identifies on the way
back, decides between the foreign lane and the local lane, and emits audit metadata.

## Responsibilities

1. **Provider allowlist and credentials** — the only place API keys and base URLs live.
2. **Lane selection** — `foreign` (ZDR API abroad) or `local` (open-weight model in Algeria), chosen
   per *task type*, not per call site. Task types are declared once in a registry with their lane and
   their allowed input classes.
3. **Redaction** — every outbound string passes through the redactor; structured inputs are
   projected to a view object first.
4. **Egress assertion** — before sending, the gateway re-scans the final payload (system + messages +
   tool results) with the redactor in *detect* mode. If anything is detected, the call is refused
   (not silently redacted a second time — that would mean a code path bypassed step 3).
5. **Re-hydration** — placeholders are restored in the response text and in any structured output
   fields that may contain them.
6. **Audit metadata** — request id, task type, lane, model, redactor version, counts per placeholder
   class, token usage, latency. No content.
7. **Kill switch** — `AI_EGRESS_ENABLED=false` forces every task type to the local lane or to a
   `ServiceUnavailable` error if no local lane is configured.

## Task registry example

```yaml
# ai_gateway/tasks.yaml
invoice_extract:
  lane: foreign            # text already OCR'd locally, identifiers redacted
  input_classes: [amounts, dates, product_lines, ORG_placeholder]
  description: "Extract line items and totals from OCR text of a supplier invoice"
ticket_classify:
  lane: foreign
  input_classes: [free_text_redacted]
cv_score:
  lane: local              # the task is about the person; cannot be de-identified
  input_classes: [free_text_raw]
child_incident_summary:
  lane: local              # children's + health data: never leaves
  input_classes: [free_text_raw]
```

The registry is also what goes into `compliance/DATA-FLOWS.md`, so the two cannot drift apart
(generate the markdown table from the YAML in CI).

## Python skeleton (FastAPI projects)

```python
# ai_gateway/__init__.py
import os, uuid, logging
from dataclasses import dataclass, field
from .redactor import Redactor, DetectedPII          # port of scripts/pii_redactor.py
from .providers import FOREIGN, LOCAL                 # the only files importing provider SDKs
from .tasks import TASKS                              # loaded from tasks.yaml

log = logging.getLogger("ai_gateway")
EGRESS_ENABLED = os.getenv("AI_EGRESS_ENABLED", "true").lower() == "true"

class EgressBlocked(Exception): ...

@dataclass
class GatewayResult:
    text: str
    request_id: str
    lane: str
    meta: dict = field(default_factory=dict)

def complete(task: str, *, system: str, user: str, context: list[str] = ()) -> GatewayResult:
    spec = TASKS[task]
    rid = uuid.uuid4().hex
    lane = spec.lane if EGRESS_ENABLED else "local"

    if lane == "local":
        out = LOCAL.chat(system=system, user=user, context=list(context), model=spec.local_model)
        log.info("ai_gateway", extra={"rid": rid, "task": task, "lane": lane, "model": spec.local_model})
        return GatewayResult(out.text, rid, lane, {"usage": out.usage})

    red = Redactor(version="2026.10")
    sys_r = red.redact(system)
    usr_r = red.redact(user)
    ctx_r = [red.redact(c) for c in context]

    # Final assertion: nothing identifying survives in the exact payload that will leave.
    leaks: list[DetectedPII] = red.detect("\n".join([sys_r, usr_r, *ctx_r]))
    if leaks:
        log.error("ai_gateway.egress_blocked", extra={"rid": rid, "task": task,
                  "classes": sorted({l.cls for l in leaks})})
        raise EgressBlocked(f"{len(leaks)} identifiers would leave Algeria; refusing call")

    sys_r += "\nTokens like <PERSON_1> are placeholders for redacted values; keep them exactly as written."
    out = FOREIGN.chat(system=sys_r, user=usr_r, context=ctx_r, model=spec.foreign_model)
    text = red.rehydrate(out.text)

    log.info("ai_gateway", extra={"rid": rid, "task": task, "lane": lane, "model": spec.foreign_model,
             "placeholders": red.counts(), "redactor": red.version, "usage": out.usage})
    return GatewayResult(text, rid, lane, {"placeholders": red.counts(), "usage": out.usage})
```

`ai_gateway/providers.py` is the only file allowed to `import anthropic` / `import openai` / call
`https://api.*`. It sets the organisation's ZDR / no-training options, disables provider logging
where offered, and reads keys from the environment. The local provider wraps vLLM/Ollama on the
Algerian host.

## TypeScript skeleton (Node/Next.js projects)

```ts
// src/services/ai-gateway/index.ts
import { Redactor } from "./redactor";
import { foreign, local } from "./providers";     // only file importing @anthropic-ai/sdk, openai…
import { TASKS } from "./tasks";

const EGRESS = process.env.AI_EGRESS_ENABLED !== "false";

export async function complete(task: keyof typeof TASKS, input: { system: string; user: string; context?: string[] }) {
  const spec = TASKS[task];
  const rid = crypto.randomUUID();
  const lane = EGRESS ? spec.lane : "local";

  if (lane === "local") {
    const out = await local.chat({ ...input, model: spec.localModel });
    audit({ rid, task, lane, model: spec.localModel, usage: out.usage });
    return { text: out.text, rid, lane };
  }

  const red = new Redactor("2026.10");
  const system = red.redact(input.system) + "\nTokens like <PERSON_1> are placeholders; keep them exactly as written.";
  const user = red.redact(input.user);
  const context = (input.context ?? []).map((c) => red.redact(c));

  const leaks = red.detect([system, user, ...context].join("\n"));
  if (leaks.length) {
    audit({ rid, task, lane, blocked: true, classes: [...new Set(leaks.map((l) => l.cls))] });
    throw new Error(`EgressBlocked: ${leaks.length} identifiers would leave Algeria`);
  }

  const out = await foreign.chat({ system, user, context, model: spec.foreignModel });
  audit({ rid, task, lane, model: spec.foreignModel, placeholders: red.counts(), usage: out.usage });
  return { text: red.rehydrate(out.text), rid, lane };
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

Surrogates are mapped back on the Algerian side; the provider never sees a real key.

## n8n workflows

n8n is self-hosted in Algeria. Foreign-provider nodes (OpenAI, Anthropic, HTTP Request to api.*) are
only allowed in a sub-workflow named `AI Gateway` that receives already-redacted text from a
`Code` node running the redactor (port `scripts/pii_redactor.py` to JS, or call the FastAPI gateway
over the LAN — the second is better: one implementation, one audit log). Execution data retention in
n8n: set `EXECUTIONS_DATA_SAVE_ON_SUCCESS=none` or prune aggressively; execution logs store full
payloads including inputs before redaction.

## Model-side hygiene

- Keep placeholders rare and short; small models mangle `<CUSTOMER_PHONE_NUMBER_12>` more than
  `<PHONE_2>`.
- When the task output is structured (JSON), validate the schema after re-hydration; a placeholder
  that was not restored means the model altered it — treat as a soft failure and retry once with a
  stricter instruction, then fall back to local.
- Few-shot examples in prompts are the most common place for real customer data to sneak in. Build
  examples from synthetic fixtures only.
- Tool results (DB rows, API responses) that the model will see go through the same redaction as user
  text; the gateway applies it in the agent loop before each model turn.

## Local lane deployment notes

- vLLM on a GPU VPS in Algeria (or the client's server) behind the same `ai_gateway` interface;
  Ollama is fine for small loads.
- Keep the model weights, the vector DB and the gateway on the same private network; expose nothing
  but the application.
- Same audit log format as the foreign lane so `DATA-FLOWS.md` can be generated from one source.
