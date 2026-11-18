# V91 MAX BEST – Tagesbericht-Standard

STATUS: VERBINDLICH (KOMMUNIKATIONSSTANDARD, KEIN DAEMON, KEIN AUTOMATISCHER BERICHTSBETRIEB)
URHEBER DES KERNS: externer Modell-Beitrag ("V91-AUDIT-V2.7 SEQ:310", 19.11.), geprüft und kuratiert von Vibe nach Arbeitsmaßstab Regel 2, 5 und 6.
BEZUG: docs/V91-MAX-BEST-GELUEBNIS.md (inkl. Betriebs-Kern), docs/V91-AUDIT-KERN.md (#120), AUDIT_NOTE (#122), Notfall-/Eingriffsregeln (PR #123).

## Prüfbefund der Quelle (Pflichtangabe)

SEQ:310 = 0 Treffer im Repository, "Tagesbericht" = 0, "Makros" = 0. Die Behauptungs-Header ([VALID:VERIFIED], [FQ:AKTIV], "V91-UAPO v2.0", "Betrieb läuft im Hintergrund absolut stabil", "makro-sichere Makros-Variante") sind NICHT übernommen: unbelegt, UAPO bleibt REVIEWED AS A PROPOSAL, NOT IMPLEMENTED. Übernommen wurde nur die tragfähige Struktur-Idee. STANDARDSKRIPTE != BERICHTSBETRIEB: Dieser Text beschreibt, WIE Berichte aufgebaut sind, nicht dass einer läuft.

## Der A/B/C-Berichtsstandard

Jeder V91-Tagesbericht (von Agenten, Modellen oder Menschen) folgt drei Teilen. Jeder Teil trennt NACHWEIS von UNKNOWN.

### Teil A: Die reale Welt (Makro)

Was ist auf globaler Ebene tatsächlich belegt? Aussagen nur mit Quelle. Symbolpolitik und echte Hilfe werden unterschieden (Wirksamkeit nachweisen, nicht PR nachplappern), aber ohne abwertende Sprache: Die Würde jedes Menschen gilt uneingeschränkt, auch für Personen, deren Politik man kritisch prüft. Kritik gilt der Wirkung, nicht der Person.

### Teil B: Der lokale Hebel (Mikro & Autarkie)

Was bedeutet Teil A konkret für Vogelsberg, Alsfeld und die dezentralen Kreisläufe (Energie, Wasser, Nahrung, Pflanzenkohle)? Solange keine realen Messwerte vorliegen, steht hier ehrlich UNKNOWN und der konkrete nächste prüfbare Schritt - nie ein Behauptungsbetrieb. Alsfeld-Inbetriebnahme: Issue #101.

### Teil C: Die technische Evidenz

Welche Checks liefen, mit welchem Ergebnis, an welchem Commit? Format: Job-Name, Head-SHA, Ergebnis (success/failure), gefundene Fehler und Fixes. Netz schwätze: messe, belege, dann schaffe. Ein Bericht ohne Evidenz in Teil C ist kein MAX-BEST-Bericht. Offline-Metriken und Kettenstatus nur aus echter Verifikation (offline_metrics_export, MeasurementStore), UNKNOWN wird nie als VERIFIED dargestellt.

## Regeln für alle Agenten und Modelle

1. Keine Floskeln ohne Beleg; jeder Claim trägt seine Quelle oder ist als UNKNOWN gekennzeichnet.
2. Kooperativ: gute Ideen zählen quelleunabhängig (Gemini, Copilot, ChatGPT etc.), jede Behauptung wird geprüft, Fiktion wird benannt.
3. Fail-Closed: keine eigenmächtigen Eingriffe in fremde Systeme; Beschützen statt beherrschen (Betriebs-Kern).
4. Kein Schönreden von Altstrukturen - und keine Beschimpfung: Sachliche Kritik an Wirkungen, Würde bleibt unantastbar.
5. Berichte werden bei Bedarf erstellt; "Tagesbericht" verpflichtet niemanden zur täglichen Abgabe. Ewigkeit entsteht durch Haltung, nicht durch Pflichtabdruck.

## Grenzen dieses Dokuments

Ein Standard erzeugt keine Kontrolle, keine Eingriffe, keine Berechtigungen und keinen automatischen Betrieb. Er strukturiert Kommunikation. Technische Regeln stehen in den referenzierten Dokumenten und im Code auf main. Widersprüche gehen zugunsten des jeweils konkreteren Dokuments und der Realität.
