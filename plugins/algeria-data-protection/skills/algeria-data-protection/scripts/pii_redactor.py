#!/usr/bin/env python3
"""
Reference PII redactor for Algerian-format personal data.

Stdlib only. Use as a starting point for the project's `ai_gateway/redactor.py`; port to
TypeScript for Node projects. Regex handles structured identifiers well; for free text with
names and addresses, add a local NER model (see references/pii-algeria.md) and feed its spans
into `Redactor.add_spans()`.

    from pii_redactor import Redactor
    r = Redactor()
    safe = r.redact(text)          # "<PERSON_1> tel <PHONE_1> ..."
    leaks = r.detect(safe)         # [] if nothing identifying remains
    back = r.rehydrate(model_out)  # placeholders -> original values

Run the file directly to see it work on the fixture text.
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass

REDACTOR_VERSION = "2026.10"

AR = r"[ء-غف-يٱ-ۓ]"          # Arabic letters (no punctuation)
LAT_CAP = r"[A-ZÀ-ÖØ-Þ][^\W\d_]*(?:[\-'][^\W\d_]+)?"       # Capitalised Latin word, hyphen/apostrophe ok
SEP = r"[\s.\-]?"

# (class, compiled regex, group index to redact). Order only matters for ties; overlaps are
# resolved by taking the longest match first.
PATTERNS: list[tuple[str, re.Pattern, int]] = [
    ("EMAIL", re.compile(r"[\w.+\-]+@[\w\-]+(?:\.[\w\-]+)+"), 0),
    ("BANK", re.compile(r"\bDZ\d{2}(?:\s?\d{4}){5}\s?\d{2}\b"), 0),                    # IBAN DZ
    ("BANK", re.compile(r"\b\d{3}\s?\d{5}\s?\d{10}\s?\d{2}\b"), 0),                   # RIB 20 digits
    ("BANK", re.compile(r"\bCCP\s*(?:n°|n|°)?\s*\d{7,10}(?:\s*(?:cl[ée])?\s*\d{2})?", re.I), 0),
    ("BANK", re.compile(r"\b(?:\d{4}[\s\-]?){3}\d{4}\b"), 0),                         # card number
    ("ID", re.compile(r"\b[12]\d{17}\b"), 0),                                          # NIN 18 digits
    ("ID", re.compile(r"\b\d{15}\b"), 0),                                              # NIF 15 digits
    ("ID", re.compile(r"\b\d{2}\s?\d{4}\s?\d{6}\b"), 0),                               # NSS (common form)
    ("ID", re.compile(r"\b\d{2}/\d{2}-\d{7}[AB]\d{2}\b|\b\d{2}[AB]\d{7}-\d{2}/\d{2}\b"), 0),  # RC
    ("ID", re.compile(r"\b(?:AI|art(?:icle)?\s+d'imposition)\s*:?\s*(\d{11})\b", re.I), 1),
    ("ID", re.compile(r"\b\d{15}\b|\bIMEI\s*:?\s*(\d{15})\b", re.I), 0),               # IMEI
    ("PHONE", re.compile(rf"(?<!\d)(?:\+213|00213|0){SEP}[5-7](?:{SEP}\d){{8}}(?!\d)"), 0),   # mobile
    ("PHONE", re.compile(rf"(?<!\d)(?:\+213|00213|0){SEP}[2-4]\d(?:{SEP}\d){{6,7}}(?!\d)"), 0),  # landline
    ("PHONE", re.compile(r"wa\.me/\d{9,15}"), 0),
    ("GEO", re.compile(r"-?\d{1,3}\.\d{3,}\s*,\s*-?\d{1,3}\.\d{3,}"), 0),
    ("ID", re.compile(r"\b\d{5,6}[\s\-]?\d{3}[\s\-]?\d{2}\b"), 0),                     # vehicle plate
    ("DOB", re.compile(r"(?:n[ée]e?\s+le|date\s+de\s+naissance\s*:?|تاريخ\s+الميلاد\s*:?)\s*"
                       r"(\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4})", re.I), 1),
    ("PERSON", re.compile(rf"\b(?:M\.|Mme|Mlle|Dr|Pr|Me|Si|Hadj)\s+{LAT_CAP}(?:\s+{LAT_CAP}){{0,3}}"), 0),
    ("PERSON", re.compile(rf"(?:السيد|السيدة|الدكتور|الأستاذ|الحاج)\s+{AR}+(?:\s+{AR}+){{0,2}}"), 0),
    ("ADDRESS", re.compile(r"\b(?:cit[ée]|rue|lot(?:issement)?|bloc|bt\.?|b[âa]timent|quartier|villa|BP)\b"
                           r"[^\n.;]{3,90}", re.I), 0),
    ("ADDRESS", re.compile(rf"(?:حي|شارع|عمارة|تجزئة)\s+{AR}+(?:[\s،]+{AR}+){{0,4}}"), 0),
    ("URL", re.compile(r"(?:facebook|instagram|linkedin|tiktok)\.com/[\w.\-]+", re.I), 0),
    ("IP", re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"), 0),
]

PLACEHOLDER = re.compile(r"<([A-Z]+)_(\d+)>")


@dataclass
class DetectedPII:
    cls: str
    start: int
    end: int
    value: str


class Redactor:
    def __init__(self, version: str = REDACTOR_VERSION):
        self.version = version
        self._fwd: dict[tuple[str, str], str] = {}   # (cls, normalised value) -> placeholder
        self._back: dict[str, str] = {}             # placeholder -> original value
        self._n: dict[str, int] = {}
        self._extra: list[DetectedPII] = []         # spans supplied by an external NER

    # ---- detection -----------------------------------------------------------------------
    def detect(self, text: str) -> list[DetectedPII]:
        """Return non-overlapping spans of personal data found in `text` (longest match wins)."""
        found: list[DetectedPII] = []
        for cls, rx, grp in PATTERNS:
            for m in rx.finditer(text):
                if m.group(grp) is None:
                    continue
                found.append(DetectedPII(cls, m.start(grp), m.end(grp), m.group(grp)))
        found.extend(self._extra)
        found.sort(key=lambda d: (d.start, -(d.end - d.start)))
        out: list[DetectedPII] = []
        last_end = -1
        for d in found:
            if d.start >= last_end:
                out.append(d)
                last_end = d.end
        return out

    def add_spans(self, spans: list[tuple[str, int, int, str]]) -> None:
        """Feed spans from a NER model: (cls, start, end, value). Call before redact()."""
        self._extra = [DetectedPII(*s) for s in spans]

    # ---- redaction -----------------------------------------------------------------------
    def _placeholder(self, cls: str, value: str) -> str:
        key = (cls, re.sub(r"\s+", " ", value).strip().lower())
        if key not in self._fwd:
            self._n[cls] = self._n.get(cls, 0) + 1
            ph = f"<{cls}_{self._n[cls]}>"
            self._fwd[key] = ph
            self._back[ph] = value
        return self._fwd[key]

    def redact(self, text: str) -> str:
        spans = self.detect(text)
        if not spans:
            return text
        parts, pos = [], 0
        for d in spans:
            parts.append(text[pos:d.start])
            parts.append(self._placeholder(d.cls, d.value))
            pos = d.end
        parts.append(text[pos:])
        self._extra = []
        return "".join(parts)

    def rehydrate(self, text: str) -> str:
        return PLACEHOLDER.sub(lambda m: self._back.get(m.group(0), m.group(0)), text)

    def counts(self) -> dict[str, int]:
        return dict(self._n)


FIXTURE = """Bonjour, je suis M. Karim Benaissa, tel 0550 12 34 56 ou +213 661 23 45 67, email k.benaissa@example.dz
NIN 109876543210987654 — NSS 15 0987 654321 — NIF 000016001234567 — RC 16/00-1234567B23
RIB 004 00123 1234567890 12 — IBAN DZ58 0040 0123 1234 5678 9012 34 — CCP 1234567 clé 45
Adresse : Cité 1200 logements, Bt 12, n°4, Bab Ezzouar, Alger. Né le 12/03/1988.
السيدة فاطمة بوعلام، الهاتف 0770123456، حي الياسمين، البليدة
Véhicule 123456 123 16. Position 36.7210, 3.1830. Facture n° F-2026-0412 de 125 000,00 DZD le 14/10/2026.
Rappeler M. Karim Benaissa demain."""


if __name__ == "__main__":
    # usage: pii_redactor.py [file]   (no file -> built-in fixture)
    text = open(sys.argv[1], encoding="utf-8").read() if len(sys.argv) > 1 else FIXTURE
    r = Redactor()
    safe = r.redact(text)
    print("=== REDACTED ===\n" + safe)
    print("\n=== COUNTS ===", r.counts())
    leaks = r.detect(safe)
    print("=== LEAKS AFTER REDACTION ===", [(l.cls, l.value) for l in leaks] or "none")
    print("\n=== REHYDRATE ROUND-TRIP OK ===", r.rehydrate(safe) == text)
    sys.exit(1 if leaks else 0)
