"""V99 Quellen-Qualitaet (advisorisch, lokal, Phase-7-Vorarbeit).

Zweck: Signal von Rauschen trennen – NUR fuer eigene Datenpipelines.

Explizite Grenzen:
- Kein Zugriff auf externe Plattformen, keine Abschaltung, keine Ueberwachung
  Dritter. Ein BLOCKED_LOCAL-Status ist eine lokale Konsum-Entscheidung,
  keine Wirkung gegen die Quelle selbst.
- DETECTION != AUTHORIZATION: Ein Status berechtigt zu nichts ausser
  zur Sortierung im eigenen Datenstrom.
- CLAIM != EVIDENCE: Ohne Evidenz bleibt alles UNVERIFIED, egal wie
  vertrauenswuerdig die Quelle eingestuft ist.
- Die Vertrauenseinstufung ist eine bewusste lokale Konfiguration – kein
  objektiver Wahrheitsbeweis ueber Dritte.
- EVIDENCE_SUPPLIED != EVIDENCE_VALIDATED: Ein nicht-leeres Objekt ist
  nur ein eingereichter Hinweis. Bis ein Validator Referenz, Frische,
  Abrufbarkeit und Unabhaengigkeit nachweist, bleibt die Bewertung offen.
"""
from dataclasses import dataclass
import json

VALID_TRUST_LEVELS = frozenset({"TRUSTED", "UNVERIFIED", "BLOCKED_LOCAL"})

VERDICT_QUARANTINE = "QUARANTINE_LOCAL"
VERDICT_ACCEPT = "ACCEPT_LOCAL"
VERDICT_REVIEW = "REVIEW_REQUIRED"


@dataclass(frozen=True)
class SourceVerdict:
    source: str
    trust: str
    verdict: str
    reason: str
    has_evidence: bool
    evidence_reference_valid: bool = False
    independently_corroborated: bool = False

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "trust": self.trust,
            "verdict": self.verdict,
            "reason": self.reason,
            # Backward-compatible field: means supplied, not validated.
            "has_evidence": self.has_evidence,
            "evidence_supplied": self.has_evidence,
            "evidence_reference_valid": self.evidence_reference_valid,
            "independently_corroborated": self.independently_corroborated,
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

    def classify(self, source: str, evidence=None) -> SourceVerdict:
        """Bewertet EINEN Datenpunkt fuer die eigene Pipeline.

        Regeln (fail-closed, ratlos bleibt ratlos):
        - BLOCKED_LOCAL: lokale Konsum-Quarantaene, egal was sonst kommt.
        - UNVERIFIED-Quelle: REVIEW_REQUIRED, nie still akzeptiert.
        - TRUSTED-Quelle ohne Evidenz: REVIEW_REQUIRED.
        - TRUSTED-Quelle mit eingereichter Evidenz: ebenfalls REVIEW_REQUIRED,
          bis ein separater Validator Referenz, Frische, Abrufbarkeit und
          unabhaengige Bestaetigung tatsaechlich geprueft hat.
        - ACCEPT_LOCAL bleibt als API-Konstante erhalten, wird hier aber
          bewusst nicht vergeben: ein Validator ist noch nicht implementiert.
        """
        trust = self.trust_of(source)
        evidence_supplied = evidence is not None and bool(evidence)
        evidence_reference_valid = False
        independently_corroborated = False

        if trust == "BLOCKED_LOCAL":
            verdict = VERDICT_QUARANTINE
            reason = "Quelle ist bewusst lokal gesperrt (eigene Konsumentscheidung, kein Zugriff auf die Quelle selbst)."
        elif trust == "TRUSTED" and evidence_supplied:
            verdict = VERDICT_REVIEW
            reason = (
                "EVIDENCE_SUPPLIED_NOT_VALIDATED: Evidenz wurde eingereicht, "
                "aber Referenz, Frische, Abrufbarkeit und Unabhaengigkeit "
                "wurden nicht geprueft."
            )
        elif trust == "TRUSTED":
            verdict = VERDICT_REVIEW
            reason = "CLAIM != EVIDENCE: vertrauenswuerdige Quelle, aber keine Evidenz beigefuegt."
        elif trust == "UNVERIFIED":
            verdict = VERDICT_REVIEW
            reason = "Quelle nicht bewusst eingestuft; bleibt zur Pruefung, wird nie still akzeptiert."
        else:
            verdict = VERDICT_REVIEW
            reason = "UNKNOWN bleibt UNKNOWN."

        return SourceVerdict(
            source=source,
            trust=trust,
            verdict=verdict,
            reason=reason,
            has_evidence=evidence_supplied,
            evidence_reference_valid=evidence_reference_valid,
            independently_corroborated=independently_corroborated,
        )

    def filter_stream(self, items) -> dict:
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
            verdict = self.classify(item["source"], item.get("evidence"))
            bucket = {VERDICT_ACCEPT: accepted,
                      VERDICT_QUARANTINE: quarantined,
                      VERDICT_REVIEW: review}[verdict.verdict]
            bucket.append({"item": item, "verdict": verdict.to_dict()})
        return {"accepted_local": accepted,
                "quarantined_local": quarantined,
                "review_required": review}
