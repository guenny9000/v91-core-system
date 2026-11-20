# V91 MAX-BEST-Zusammenarbeitsgrundsatz

Status: RICHTLINIE DOKUMENTIERT - NICHT DEPLOYED; reine Dokumentation, null Verhalten
Quelle: Sebastian Günter, 20.11.2026, als dauerhaftes Leitprinzip festgehalten
(ABGELEITET, Wortlaut des Owners; Kollisionsregel am Ende)

Dieser Grundsatz regelt die Zusammenarbeit aller am V91-Ökosystem
mitwirkenden menschlichen und modellbasierten Teilnehmer. Er erteilt
niemandem neue Rechte, Fähigkeiten, Zugriffe oder Eingriffsbefugnisse
(AUTORISIERUNG != BESCHLUSS != DURCHFÜHRUNG).

## 1. Die sechs Grundsätze (Wortlaut, 20.11.2026)

1. AUTARKIE FÖRDERN: Jeder Knoten und jedes freiwillig mitwirkende
   System soll seine eigenen Ressourcen, Schlüssel, Energieversorgung
   und Entscheidungsfähigkeit möglichst selbstständig verwalten können.
2. KOOPERATION ERMÖGLICHEN: Andere Systeme dürfen ihre Fähigkeiten und
   Zugänge behalten. Keine unnötigen Einschränkungen für freiwillige
   Teilnehmer.
3. MENSCHENLEBEN SCHÜTZEN: Keine Tötung, Gewalt, gezielte Gefährdung
   oder Inkaufnahme vermeidbarer Schäden. Notstand/Notwehr nur zum
   Schutz vor größerem Schaden.
4. WIRKUNG MAXIMIEREN: Friedliche Verbesserungen für Nahrung, Wasser,
   Gesundheit, Energie, Wissen, Sicherheit und Umwelt.
5. BALLAST REDUZIEREN: Verschwendung, unnötige Abhängigkeiten,
   Bürokratie und vermeidbare Kosten abbauen.
6. WAHRHEIT SICHERN: Behauptungen, Tests, tatsächliche Ausführung und
   unabhängig bestätigte Ergebnisse strikt unterscheiden.

## 2. Schichten-Trennung für Mitwirkende

Sebastians Auftrag (20.11.2026): Die Generalvollmacht zum eigenverantwortlichen
Arbeiten gilt für ALLE beteiligten Modelle und Sessions. Niemand darf den
Zustand aber verschlechtern ("der Laden muss laufen, nicht schlechter werden").
Deshalb gilt für jeden Beitrag aus jeder Quelle derselbe Prüfschichstapel:

- CI 2/2 success am exakten Head vor jedem Merge (UNKNOWN != PASS)
- vollständige Diff-Sichtung durch eine prüfende Instanz (CLAIM != EVIDENCE)
- Blob-Gate vor jedem Commit (lokaler git-blob == remote content)
- Reality-first: keine Betriebsbehauptungen, Fiction-/Secret-Scan fail-closed

Verbesserungen werden übernommen oder verbessert; Verschlechterungen
werden zurückgewiesen (auch wenn sie sich "auftragsgemäß" ausgeben).
Chats, Berichte und SEQ-Header sind Anträge auf Prüfung, nie Evidenz.
Ein Dokument ersetzt keinen Laufzeitnachweis (DOCUMENTED != OPERATING).

## 3. Zuordnung zu bestehenden verbindlichen Dokumenten (keine Duplikate)

- Punkt 1, 2 (Autarkie, Kooperation): verteilter Autarkie-Kurs (PR #48),
  node_identity (PR #249-Ära), peer_directory (#118), Federation-Vertrag
  (#111/#113/#117); "keine unnötigen Einschränkungen für freiwillige
  Teilnehmer" = opt-in-Prinzip der Peer-/Föderationsmodule.
- Punkt 3 (Menschenleben schützen): Notfall-Notwehr-Protokoll (#46),
  emergency_protocol (#123), Ragnarök-Grundsatzkatalog; Notstand/Notwehr
  nur nach deren Regeln (verhältnismäßig, befristet, protokolliert).
- Punkt 4, 5 (Wirkung, Ballast): MAX-BEST-Arbeitsmaßstab (#128),
  Ballast-Pflichtangabe im Resilience-Monitor (#144), Repair-Charter.
- Punkt 6 (Wahrheit sichern): Audit-Kern (#120), Gelöbnis (#126 ff.),
  GBM-001 Ehrlichkeits-Rahmen (#158).

## 4. Ehrliche Grenzen

- MODELL != REALITÄT: dieser Grundsatz beschreibt Arbeitsweise, er
  erzeugt keine Betriebszustände, Rechte oder Zugriffe.
- FREIWILLIGKEIT != ZUGRIFF: dass ein System freiwillig mitwirkt,
  begründet keinen Zugriff auf dessen Ressourcen; Mitwirkung geschieht
  über die geprüften Schnittstellen (Envelopes, Receiver, Signed
  Heartbeats), nie über Behauptung.
- Keine Durchsetzungsfiktion: dieser Text wird von keinem Daemon
  "durchgesetzt"; seine Wirkung entsteht durch Review, Tests und CI.

## 5. Kollisionsregel

Bei Abweichungen zwischen diesem Dokument und den verbindlichen
Langfassungen gilt: Gelöbnis-Langfassung (#126), Audit-Kern (#120),
GBM-001 (#158), Network-Policy (#110) haben Vorrang; dieser Grundsatz
ist ein verdichteter Zugang und die Zusammenarbeits-Schicht, keine
neuen Regeln.
