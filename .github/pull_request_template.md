# V91 MAX-BEST - PR Gate-Check (RealRun, FAIL-CLOSED)

Leitsatz: So viel Autarkie wie sinnvoll. So viel Kooperation wie wirksam.
So viel Verbesserung wie nachweisbar.
CLAIM != EVIDENCE. UNKNOWN != PASS. FILE_EXISTS != VERIFIED_IMPROVEMENT.
SIMULATION != REALRUN. Dokumentiertes Detail: docs/V91-MAX-BEST-REALRUN-ZYKLUSCHECK.md
(betreiberbestaetigte dauerhafte Arbeitsgrundlage), Governance-Gate #96,
Promotion-Gates #145/#146, governance-gate-Workflow (.github/workflows/governance_ci.yml).

## Pflicht vor dem Merge (Abendstandard, kein blindes Merging)

- [ ] Vollstaendige Diff-Sichtung: jede geaenderte Zeile gelesen (INSPECT BEFORE MODIFY).
- [ ] CI 3/3 success AM EXAKTEN HEAD (check-runs am SHA geprueft, nie nur Badge).
- [ ] REUSE vor Neubau geprueft (NO_DUPLICATE_SYSTEMS): kein zweites Gate-, Ledger-,
      Validierungs- oder Regel-System; existierende Bausteine referenziert.
- [ ] KEINE_FIKTIVEN_NACHWEISE: keine erfundenen Zahlen, Daemonen, Dateien, Logs.
- [ ] Aenderungslog-Zeile angehaengt (docs/archive/V91-ARCHITEKTUR-AENDERUNGSLOG.md,
      append-only, PR-Nummer erst nach PR-Anlage, VIBE-Marke frisch gelookupt).

## Wo steht der Nachweis? (BELEG statt Behauptung)

Fallback ohne Artefakt: alle hier bindenden Regeln bleiben unveraendert,
auch wenn dieses Template nicht ausgefuellt wird.

- Artefakt (Mess-/Test-/Benchmark-Datei) + SHA-256:
  ______________________________________________
- commit_sha des geprueften Standes: ______________________________
- Bei Bedarf: Nachweisdatei via controller/evidenz_collector.py erzeugt
  (v91.evidence_collector.v1, Integritaet != Wirkung, SCRIPTED != INSTALLED).

## Vier-Fragen-Abschlussblock (aus dem RealRun-Zykluscheck)

1. GRENZE: Wurde eine Grenze respektiert oder erweitert (begruenden)?
2. VERSCHWENDUNG: Wurde Doppelarbeit/Unnoetiges vermieden (REUSE gezeigt)?
3. BELEG: Was genau ist der belegte (nicht behauptete) Fortschritt?
4. UEBERGABE: Was bleibt offen, wer/wie wird es aufgegriffen?

Ehrliche Grenze: Ein gruener CI-Lauf ist KEINE Produktionsfreigabe
(CI_PASS != PRODUCTION). Reale Eingriffe bleiben allowlist-pflichtig je Aktion.
