#!/usr/bin/env python3
"""
Egress audit for Algeria data-protection posture (Law 18-07 / 25-11).

Scans a repository and fails when:
  ERROR  - a foreign AI provider SDK is imported, or its API host referenced, outside the gateway
           module (default: any path segment named ai_gateway / ai-gateway / aiGateway)
  ERROR  - the gateway module itself is missing while provider usage exists
Warns when:
  WARN   - a log/print call appears to emit prompt/message/response content
  WARN   - a known foreign SaaS host (tracing, error tracking, analytics, automation, storage,
           messaging) appears in code or config — each needs an entry in compliance/DATA-FLOWS.md
  WARN   - compliance/ folder or DATA-FLOWS.md is missing

Usage:
    python3 audit_egress.py <repo> [--gateway NAME ...] [--strict] [--json]
Exit code 1 on errors (and on warnings with --strict).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build", ".next",
             "coverage", ".mypy_cache", ".pytest_cache", "vendor", ".idea", ".vscode"}
CODE_EXT = {".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".dart", ".go", ".php", ".rb"}
CONFIG_EXT = {".yaml", ".yml", ".json", ".toml", ".ini", ".cfg", ".conf", ".env", ".xml", ".tf"}
ALL_EXT = CODE_EXT | CONFIG_EXT

PY_IMPORT = re.compile(
    r"^\s*(?:from|import)\s+(anthropic|openai|google\.generativeai|google\.genai|mistralai|cohere|groq|"
    r"together|replicate|litellm|voyageai|langchain_anthropic|langchain_openai|langchain_google_genai|"
    r"langchain_mistralai|langchain_cohere|llama_index\.llms\.(?:anthropic|openai)|instructor)\b", re.M)
JS_IMPORT = re.compile(
    r"""(?:from\s+|require\(\s*)['"](@anthropic-ai/sdk|openai|@google/generative-ai|@google/genai|"""
    r"""@mistralai/mistralai|cohere-ai|groq-sdk|@langchain/(?:openai|anthropic|google-genai|mistralai|cohere)|"""
    r"""@ai-sdk/[\w\-]+|together-ai|replicate|voyageai)['"]""")
DART_IMPORT = re.compile(r"""import\s+'package:(?:dart_openai|anthropic_sdk_dart|google_generative_ai)/""")
PROVIDER_HOSTS = re.compile(
    r"api\.anthropic\.com|api\.openai\.com|generativelanguage\.googleapis\.com|aiplatform\.googleapis\.com|"
    r"api\.mistral\.ai|api\.cohere\.(?:ai|com)|api\.groq\.com|api\.together\.xyz|openrouter\.ai|"
    r"api\.deepseek\.com|api\.voyageai\.com|api\.replicate\.com|bedrock[\w\-]*\.amazonaws\.com|"
    r"[\w\-]+\.openai\.azure\.com", re.I)

PROMPT_LOG = re.compile(
    r"\b(?:logger|log|logging|console|print)\s*(?:\.\s*(?:info|debug|warn|warning|error|log|trace))?\s*\("
    r"[^\n]{0,160}\b(?:prompt|messages|completion|user_input|user_message|response\.(?:content|text)|"
    r"raw_text|transcript)\b", re.I)

# host -> short reason; anything here is a transfer or a residency break unless documented
SAAS_HOSTS = {
    r"(?:ingest\.)?sentry\.io": "error tracking abroad — self-host Sentry/GlitchTip in DZ",
    r"api\.smith\.langchain\.com|langsmith": "LLM tracing abroad — self-host Langfuse/Phoenix in DZ",
    r"helicone\.ai|portkey\.ai|api\.braintrust": "LLM proxy/tracing abroad",
    r"cloud\.langfuse\.com": "Langfuse cloud — self-host instead",
    r"hooks\.zapier\.com|make\.com/|\.n8n\.cloud": "automation SaaS abroad — self-host n8n in DZ",
    r"google-analytics\.com|googletagmanager\.com|mixpanel\.com|hotjar\.com|(?:app|us|eu)\.posthog\.com|amplitude\.com":
        "analytics abroad — Plausible/Umami self-hosted or none",
    r"\.supabase\.co|firebaseio\.com|firestore\.googleapis\.com|\.mongodb\.net|planetscale|neon\.tech|upstash":
        "managed database abroad — residency wall",
    r"s3[\.\-][\w\-]*amazonaws\.com|backblazeb2\.com|storage\.googleapis\.com|blob\.core\.windows\.net|r2\.cloudflarestorage\.com":
        "object storage/backups abroad — residency wall",
    r"api\.mailgun\.net|api\.sendgrid\.com|api\.twilio\.com|api\.brevo\.com|api\.resend\.com":
        "email/SMS provider abroad — minimise + document basis",
    r"sheets\.googleapis\.com|docs\.googleapis\.com|api\.notion\.com|api\.airtable\.com":
        "Google Sheets/Docs/Notion/Airtable as data store — residency wall",
    r"graph\.facebook\.com|graph\.instagram\.com": "Meta/WhatsApp API — channel transfer; document the basis in DATA-FLOWS.md",
    r"datadoghq\.com|newrelic\.com|logtail\.com|betterstack\.com|logs\.logdna": "APM/log shipping abroad",
    r"crashlytics|firebase-crashlytics": "mobile crash reports abroad — scrub PII, document",
    r"pinecone\.io|weaviate\.(?:cloud|io)|qdrant\.(?:tech|io)/cloud|cloud\.qdrant": "vector DB abroad — self-host in DZ",
}
SAAS_RX = [(re.compile(k, re.I), v) for k, v in SAAS_HOSTS.items()]


def is_gateway_path(path: str, names: list[str]) -> bool:
    parts = {p.lower() for p in re.split(r"[\\/]", path)}
    stems = {os.path.splitext(p)[0] for p in parts}
    return any(n.lower() in parts or n.lower() in stems for n in names)


def iter_files(root: str):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for f in filenames:
            ext = os.path.splitext(f)[1].lower()
            if ext in ALL_EXT or f.startswith(".env"):
                yield os.path.join(dirpath, f)


def scan(root: str, gateway_names: list[str]):
    errors, warnings = [], []
    provider_usage_in_gateway = False
    for path in iter_files(root):
        rel = os.path.relpath(path, root)
        try:
            with open(path, encoding="utf-8", errors="ignore") as fh:
                text = fh.read()
        except OSError:
            continue
        in_gw = is_gateway_path(rel, gateway_names)
        ext = os.path.splitext(path)[1].lower()

        hits = []
        if ext in CODE_EXT:
            for rx in (PY_IMPORT, JS_IMPORT, DART_IMPORT):
                hits += [m.group(0).strip() for m in rx.finditer(text)]
        hits += [m.group(0) for m in PROVIDER_HOSTS.finditer(text)]
        for h in sorted(set(hits)):
            if in_gw:
                provider_usage_in_gateway = True
            else:
                errors.append({"file": rel, "kind": "provider_outside_gateway", "detail": h})

        if ext in CODE_EXT:
            for m in PROMPT_LOG.finditer(text):
                line = text.count("\n", 0, m.start()) + 1
                warnings.append({"file": rel, "kind": "possible_prompt_logging", "line": line,
                                 "detail": m.group(0)[:120]})

        for rx, reason in SAAS_RX:
            m = rx.search(text)
            if m:
                warnings.append({"file": rel, "kind": "foreign_saas_host", "detail": m.group(0),
                                 "reason": reason})

    if errors and not provider_usage_in_gateway:
        errors.append({"file": "-", "kind": "gateway_missing",
                       "detail": f"no provider usage found inside a module named {gateway_names}"})

    comp = os.path.join(root, "compliance")
    if not os.path.isdir(comp):
        warnings.append({"file": "compliance/", "kind": "paper_trail_missing", "detail": "folder absent"})
    elif not os.path.exists(os.path.join(comp, "DATA-FLOWS.md")):
        warnings.append({"file": "compliance/DATA-FLOWS.md", "kind": "paper_trail_missing", "detail": "file absent"})
    return errors, warnings


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("repo")
    ap.add_argument("--gateway", action="append", default=None,
                    help="module/dir name allowed to call providers (repeatable)")
    ap.add_argument("--strict", action="store_true", help="treat warnings as errors")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    names = a.gateway or ["ai_gateway", "ai-gateway", "aiGateway"]
    errors, warnings = scan(a.repo, names)

    if a.json:
        print(json.dumps({"errors": errors, "warnings": warnings}, indent=2, ensure_ascii=False))
    else:
        for e in errors:
            print(f"ERROR  {e['file']}: {e['kind']} — {e['detail']}")
        for w in warnings:
            loc = f"{w['file']}:{w['line']}" if "line" in w else w["file"]
            extra = f" ({w['reason']})" if "reason" in w else ""
            print(f"WARN   {loc}: {w['kind']} — {w['detail']}{extra}")
        print(f"\n{len(errors)} error(s), {len(warnings)} warning(s). Gateway module(s): {names}")
    return 1 if errors or (a.strict and warnings) else 0


if __name__ == "__main__":
    sys.exit(main())
