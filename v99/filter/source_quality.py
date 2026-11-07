"""V99 Quellen-Qualitaet (advisorisch, lokal, Phase-7-Vorarbeit).

Zweck: Signal von Rauschen trennen – NUR fuer eigene Datenpipelines.

Explizite Grenzen:
- Kein Zugriff auf externe Plattformen, keine Abschaltung, keine Uberwachung
  Dritter. Ein BLOCKED_LOCAL-Status ist eine lokale Konsum-Entscheidung,
  keine Wirkung gegen die Quelle.
- DETECTION != AUTHORIZATION: Ein Status berechtigt zu nichts ausser
  zur Sortierung im eigenen Datenstrom.
- CLAIM != EVIDENCE: Ohne Evidenz bleibt alles UNVERIFIED, egal wie
  vertrauenswuerdig die Quelle eingestuft ist.
- EVIDENCE_SUPPLIED != EVIDENCE_VALID: Seit dem Evidenz-Vertrag v2
  (Issue #51) unterscheidet validate_evidence=True() zwischen
  'es wurde etwas mitgeliefert' und 'die mitgelieferten Eintraege sind
  strukturell gueltige, abrufbare Referenzen'. Ein nicht-leerer String
  ohne Referenzstruktur ist KEIN valider Beleg.
- VALIDATED != INDEPENDENT: Unabhaengigkeit einer Bestaetigung ist lokal
  nicht pruefbar und bleibt UNKNOWN_NOT_VERIFIABLE_LOCALLY.
- Die Vertrauenseinstufung ist Sebastians persoenliche, bewusste
  Konfiguration – kein objektiver Wahrheitsbeweise ueber Dritte.
"""
from dataclasses import dataclass
import json
import re

VALID_TRUST_LEVELS = frozenset({"TRUSTED", "UNVERIFIED", "BLOCKED_LOCAL"})

VERDICT_QUARANTINE = "QUARANTINE_LOCAL"
VERDICT_ACCEPT = "ACCEPT_LOCAL"
VERDICT_REVIEW = "REVIEW_REQUIRED"

EVIDENCE_INDEPENDENCE_UNKNOWN = "UNKNOWN_NOT_VERIFIABLE_LOCALLY"

_VALID_REFERENCE_KINDS = frozenset({"url", "doi", "sha256", "path", "citation", "ledger_id"})
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _is_valid_reference(entry) -> bool:
    """Strukturelle Referenzpruefung – KEIN Abruf, KEINE echtheits-/Unabhaengigkeitspruefung."""
    if isinstance(entry, dict):
        kind = entry.get("kind")
        value = entry.get("value")
        if not isinstance(kind, str) or kind.strip().lower() not in _VALID_REFERENCE_KINDS:
            return False
        return isinstance(value, str) and value.strip() != ""
    if isinstance(entry, str):
        s = entry.strip()
        if not s:
            return False
        if s.startswith(("http://", "https://", "doi:", "DOI:", "/")):
            return True
        if _SHA256_RE.match(s):
            return True
        return "::" in s  # schematisierte Referenz, z. B. 'ledger::<id>'
    return False


@dataclass(frozen=True)
class SourceVerdict:
    source: str
    trust: str
    verdict: str
    reason: str
    has_evidence: bool
    evidence_supplied: bool = False
    evidence_reference_valid: bool = False
    evidence_independent: str = EVIDENCE_INDEPENDENCE_UNKNOWN

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "trust": self.trust,
            "verdict": self.verdict,
            "reason": self.reason,
            "has_evidence": self.has_evidence,
            "evidence_supplied": self.evidence_supplied,
            "evidence_reference_valid": self.evidence_reference_valid,
            "evidence_independent": self.evidence_independent,
        }


class SourceTrustRegistry:
    """Laedt eine bewusste, lokale Vertrauenskonfiguration (JSON)."""

    def __init__(self, config: dict):
        if not isinstance(config, dict) or not isinstance(config.get("sources"), dict):
            raise ValueError("Quellen-Vertrauenskonfiguration benoetigt ein 'sources'-Objekt")
        self._sources: dict = {}
        for name, entry in config["sources"].items():
            if not isinstance(name, str) or not name.strip():
                raise ValueError("Quellenname muss nicht-leer sein")
            if not isinstance(entry, dict) or entry.get("trust") not in VALID_TRUST_LEVELS:
                raise ValueError(f"Quelle '{name}' benoetigt trust in {sorted(VALID_TRUST_LEVELS)}")
            self._sources[name.strip().lower()] = {
                "trust": entry["trust"],
                "note": entry.get("note", ""),
            }

    @classmethod
    def from_file(cls, path: str) -> "SourceTrustRegistry":
        with open(path, "r", encoding="utf-8") as handle:
            return cls(json.load(handle))

    def trust_of(self, source: str) -> str:
        if not isinstance(source, str) or not source.strip():
            return "UNVERIFIED"
        entry = self._sources.get(source.strip().lower())
        return entry["trust"] if entry else "UNVERIFIED"

    def note_of(self, source: str) -> str:
        entry = self._sources.get(source.strip().lower()) if isinstance(source, str) else None
        return entry["note"] if entry else ""

    def classify(self, source: str, evidence=None, validate_evidence: bool = False) -> SourceVerdict:
        """Bewertet EINEN Datenpunkt fuer die eigene Pipeline.

        Evidenz-Vertrag v2 (additiv, Issue #51):
        - validate_evidence=False (Default): exaktes Legacy-Verhalten,
          has_evidence == evidence_supplied.
        - validate_evidence=True: gelieferte Eintraege muessen strukturell
          gueltige Referenzen sein (URL, DOI, SHA-256, Pfad, citation,
          ledger_id oder schematisierte Referenz). TRUSTED + ungueltige
          Referenzen => REVIEW_REQUIRED statt stiller Aufnahme.
        - evidence_independent bleibt immer UNKNOWN_NOT_VERIFIABLE_LOCALLY:
          Unabhaengigkeit ist lokal nicht pruefbar. VALIDATED != INDEPENDENT.

        Regeln (fail-closed, ratlos bleibt ratlos):
        - BLOCKED_LOCAL: lokale Konsum-Quarantaene, egal was sonst kommt.
        - UNVERIFIED-Quelle: REVIEW_REQUIRED, nie still akzeptiert.
        - TRUSTED-Quelle ohne Evidenz: trotzdem REVIEW_REQUIRED
          (CLAIM != EVIDENCE).
        - TRUSTED-Quelle MIT gueltiger Evidenz-Referenz: ACCEPT_LOCAL –
          akzeptiert heisst hier nur 'in die eigene Pipeline aufnehmen',
          nicht 'wahr' und nicht 'unabhaengig bestaetigt'.
        """
        trust = self.trust_of(source)
        supplied = evidence is not None and bool(evidence)
        valid = False
        if validate_evidence and supplied:
            entries = list(evidence) if isinstance(evidence, (list, tuple)) else [evidence]
            valid = bool(entries) and all(_is_valid_reference(e) for e in entries)
        if trust == "BLOCKED_LOCAL":
            verdict = VERDICT_QUARANTINE
            reason = "Quelle ist bewusst lokal gesperrt (eigene Konsumentscheidung, kein Zugriff auf die Quelle selbst)."
        elif trust == "TRUSTED" and validate_evidence and valid:
            verdict = VERDICT_ACCEPT
            reason = "Vertrauenswuerdige Quelle mit strukturell gueltiger Evidenz-Referenz; lokale Aufnahme, kein Wahrheits- oder Unabhaengigkeitsbeweis."
        elif trust == "TRUSTED" and validate_evidence and supplied and not valid:
            verdict = VERDICT_REVIEW
            reason = "EVIDENCE_SUPPLIED != EVIDENCE_VALID: gelieferte Evidenz ist keine strukturell gueltige Referenz (URL/DOI/SHA-256/Pfad/citation/ledger_id)."
        elif trust == "TRUSTED" and not validate_evidence and supplied:
            verdict = VERDICT_ACCEPT
            reason = "Vertrauenswuerdige Quelle mit gelieferter Evidenz (Legacy-Vertrag, unvalidiert); lokale Aufnahme, kein Wahrheitsbeweis."
        elif trust == "TRUSTED":
            verdict = VERDICT_REVIEW
            reason = "CLAIM != EVIDENCE: vertrauenswuerdige Quelle, aber keine Evidenz beigefuegt."
        elif trust == "UNVERIFIED":
            verdict = VERDICT_REVIEW
            reason = "Quelle nicht bewusst eingestuft; bleibt zur Pruefung, wird nie still akzeptiert."
        else:
            verdict = VERDICT_REVIEW
            reason = "UNKNOWN bleibt UNKNOWN."
        return SourceVerdict(source=source, trust=trust, verdict=verdict,
                              reason=reason, has_evidence=supplied,
                              evidence_supplied=supplied,
                              evidence_reference_valid=valid,
                              evidence_independent=EVIDENCE_INDEPENDENCE_UNKNOWN)

    def filter_stream(self, items, validate_evidence: bool = False) -> dict:
        """Sortiert einen Strom eigene Daten in akzeptiert/quarantaene/pruefung.

        items: Liste von dicts mit Schluesseln 'source' und optional
        'evidence'. Kein Netzwerkzugriff, keine Nebenwirkungen.
        """
        accepted, quarantined, review = [], [], []
        for item in items:
            if not isinstance(item, dict) or not isinstance(item.get("source"), str):
                review.append({"item": item, "verdict": None,
                              "reason": "Malformed item: benoetigt ein 'source'-Feld."})
                continue
            verdict = self.classify(item["source"], item.get("evidence"),
                                   validate_evidence=validate_evidence)
            bucket = {VERDICT_ACCEPT: accepted,
                      VERDICT_QUARANTINE: quarantined,
                      VERDICT_REVIEW: review}[verdict.verdict]
            bucket.append({"item": item, "verdict": verdict.to_dict()})
        return {"accepted_local": accepted,
                "quarantined_local": quarantined,
                "review_required": review}
