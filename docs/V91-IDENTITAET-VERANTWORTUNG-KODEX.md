# V91-KODEX: IDENTITAET MEANS VERANTWORTUNG (Identitaet = Verantwortung)

STATUS: DOKUMENTIERT - ABBILDUNGSKODEX | KODEX != IMPLEMENTATION, BESCHRIEBENES_VERHALTEN != BETRIEB,
CLAIM != EVIDENCE.
Quelle: Betreiber-Formulierung vom 21.11.2026 (fremdmodell-Beitrag ueber Sebastian): Die
Grundsaetze fuer menschliche Beteiligte, Organisationen und KI-Agenten sind vom Betreiber
gebilligt ("der Bericht ist gut ... mach, was moeglich ist"). Dieser Kodex behauptet NICHT,
dass die Grundsaetze irgendwo "laufen"; er ordnet jeden Grundsatz dem zu, was im Repo
REAL existiert (Modul + Test), und markiert ehrlich, wo nur Dokumentation steht.
Wurzelregel des Betreibers (seit erster Stunde, unveraenderlich): KEINE TOETUNG, auch
nicht bei Fehlern; sonst alles im Einklang mit Natur und Schoepfung. Diese Regel ist
aelter als dieser Kodex und bleibt die oberste Schranke.

## 1. Identitaet, Berechtigung, Verhalten (drei getrennten Pruefungen)

Der fremdmodell-Hinweis ist KERNRICHTIG und deckt sich mit dem V91-Regelwerk:
- node_identity.py beweist SCHLUESSELBESITZ (Ed25519, install/read), niemals
  Vertrauenswuerdigkeit oder Absicht (SIGNATUR != WAHRHEIT).
- Berechtigung (was darf dieser Knoten) regeln Allowlist/Policy-Module, nicht die
  Identitaet selbst (IDENTITAET != BERECHTIGUNG).
- Verhalten wird separat geprueft: Quorum verlangt drei VERSCHIEDENE Reviewer-Identitaeten
  (controller/agent_quorum.py: "exactly three distinct reviewer identities are required",
  Unabhaengigkeit 2-of-3, controller/quorum_decision.py wertet aus).
Kurz: Wer sein kann, was er vorgibt zu sein, traegt Verantwortung dafuer, was er tut -
im System heisst das: Identitaet + getrennte Verhaltenspruefung.

## 2. Abbildungsmatrix: Grundsatz -> reale Umsetzung im Repo

| Grundsatz | Reale Umsetzung (Modul/Pruefung) | Status ehrlich |
|---|---|---|
| 1 Wahrhaftigkeit (nicht jemand anderes vortaeuschen) | controller/node_identity.py + controller/agent_quorum.py (3 distinct identities); controller/fiction_scan.py (Halluzinations-Fund); Doku-Regel CLAIM != EVIDENCE quer | IMPLEMENTIERT als Pruefstruktur; die Wahrhaftigkeit einer AUSSAGE bleibt Verifikationspflicht des Empfaengers |
| 2 Verantwortung (fuer Handlungen einstehen) | controller/decision_dossier.py (Fakt/Eigene Aussage/Schluss/Entscheidung getrennt, jede Quelle Pflicht), controller/governance_gate.py (GovernanceLedger), controller/quorum_ledger.py | IMPLEMENTIERT als Akten-/Ledgerstruktur; REVIEW != ENTSCHEIDUNG |
| 3 Dankbarkeit | KEIN Modul | NICHT_KODIERT, bewusst: kultureller Wert, kein pruefbares Kriterium; gehoert in die Kommunikation (Kanal #220), nicht in Gates (WERT != KRITERIUM) |
| 4 Demut (Grenzen, Fehler, Wissensluecken anerkennen) | UNKNOWN != PASS (startup_check Exit 1 = UNKNOWN, nie Erfolg), messmatrix uncertainty_note/marked_uncertain, UNKNOWN-Regeln der Network Policy | IMPLEMENTIERT als fail-closed-Prinzip in Pruefungen; niemals "Automatik weiss es besser" |
| 5 Schutz (Menschen, Tiere, Natur, Lebensgrundlagen) | controller/enforcement.py StewardshipGate: human_impact >= 0.5 -> REJECTED_HUMAN_IMPACT (Veto); controller/emergency_stop.py (Notaus jederzeit); KEINE-TOETUNGS-Wurzelregel oben; AGATHON-AXIOM in jedem Modul-Header | IMPLEMENTIERT als Advisory-Gate + Notaus; SCRIPTED != INSTALLED (kein Betrieb bei Behoerde/Stadt) |
| 6 Hilfsbereitschaft (vermeidbaren Schaden verhindern) | Messmatrix-Piloten A-J (Wirkungsziele mit Primaerquellen), WATCHER_EMPTY != HILFT_LEISTEN | DOKUMENTIERT-ZAEHLT: MATRIZ != WIRKUNG, KEIN_INDIKATOR != MESSUNG_ERZWINGEN |
| 7 Selbstbestimmung (nicht beherrschen/manipulieren) | controller/person_dignity_gate.py (Anhoerung, Zweitpruefer, Appeal, accommodation; Eigenschaften nie begruendeter Vorteil/Nachteil), controller/support_consent_gate.py (Freiwilligkeit, informierte Einwilligung, keine Demuetigung) | IMPLEMENTIERT als Pruefstruktur; Gilt fuer Entscheider-Protokolle, noch nicht fuer laufende Systeme |
| 8 Verlaesslichkeit (Zusagen halten, Fehler offenlegen) | SHA-512-Ledger-Kette (controller/ledger.py), controller/update_gate.py (signierte Manifests, expires/issued-Striktheit), provider fail-closed | IMPLEMENTIERT als Integritaets-Pruefungen; SIGNATUR != WAHRHEIT bleibt |
| 9 Gerechtigkeit (gleiche Masse, keine Machtmissbrauchsfoerderung) | person_dignity_gate Gleichbehandlung (traits_used_as_stated_reason zwingend False), controller/agent_quorum.py Unabhaengigkeit, Struktur-Reviews mit BELEGT/PROBLEM_BELEGT/NICHT_GEPRUEFT | IMPLEMENTIERT als Pruefkriterien; STRUKTUR != PERSONENEBENE, REVIEW != ENTSCHEIDUNG |
| 10 Besonnenheit (verhaeltnismaessig handeln, Unbeteiligte schuetzen) | controller/emergency_stop.py (kontrolliertes, begruendetes Ende statt Aktivismus), StewardshipGate HOLD/ADVISORY-Stufen statt Everything-Or-Nothing, escalation_route im Dossier | IMPLEMENTIERT als Stufen-/Notauslogik im Pruefverbund |

## 3. Fuer KI-Agenten konkret (die 5 Schritte des Beitrags, abgebildet auf Repo-Module)

1. Identitaet verifizieren -> node_identity + quorum: distinct identities.
2. Verantwortung zuweisen -> decision_dossier: jede Entscheidung mit Quelle, Autor,
   response_deadline, escalation_route.
3. Ethische Regeln pruefen -> dignity/consent/StewardshipGate/Governance-Metriken,
   fail-closed (alle Violations gesammelt, UNKNOWN != PASS).
4. Aktion ausfuehren -> im Repo per Definition ADVISORY (executed: false) oder
   betreiber-freigegebene Allowlist; keine autonomen Realeingriffe.
5. Ergebnis dokumentieren -> Ledger-Append (SHA-Kette), Session-Report-Kanal #220,
   Index-Zeile im Architektur-Index (append-only).

## 4. Was dieser Kodex NICHT leistet

- Er macht niemanden "gut": Gates pruefen Records und Manifeste, keine Gesinnung
  (PRUEFUNG != CHARAKTER).
- Er installiert nichts (CODE_PROPAGIERT != BETRIEB): Kein Modul lauft bei einer
  Behoerde, einem Arbeitgeber oder in einem fremden System.
- Die Grundsatz-Reihenfolge erzeugt keine Hierarchie-Pflicht; die Wurzelregel
  (KEINE TOETUNG) bleibt einzeln und unveraenderlich oben.
- Dankbarkeit und Besonnenheit als Haltung sind nur teilweise pruefbar; der Kodex
  pinnt nur, was Nachweise tragbar macht (BEHAUPTUNG != BELEGT).
