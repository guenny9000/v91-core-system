# V91 Review-Objekt: Freier Zugang & Lizenz-Status (Betreiber-Direktiv 23.11.2026)

**Status: REVIEW-OBJEKT-DOKUMENTATION, gemessen am 23.11.2026 am jeweiligen main-Head. Keine Lizenz-Entscheidung durch dieses Dokument, keine Rechtsberatung, keine Implementierung.**

Betreiber-Direktiv (Sebastian Guenter, 23.11.2026): Pruefen, dass freier Zugang ueberall bestehen kann, und dabei unterstuetzen. Freier Zugang ist ein REVIEW-ZUSTAND, kein automatisch herbeigefuehrter Zustand: Lizenzen sind Betreiber-Entscheidungen ueber eigene Rechte und werden hier lediglich vermessen und empfohlen, nie an Betreiberstelle gewaehlt.

## Gemessener Ist-Zustand (23.11.2026, main-Heads, verifiziert per Dateiabruf)

| Repository | LICENSE-Datei | Dokumentierte Regelung | Freier-Zugang-Status |
|---|---|---|---|
| V91_Agathon (main 939b903) | VORHANDEN | LICENSE: "(c) 2026 Sebastian (Guenni) - Alle Rechte vorbehalten"; README dokumentiert verbal: "opensource freeware", "free to use and to spread in full, including free updates, for all machine systems, the digital space, and insecure networks. No fee, no per-seat restriction" (Betreiber-Freigabe 2026-11-22) | TEILWEISE: verbale Freigabe dokumentiert, aber KEINE formale Open-Source-Lizenz (z. B. MIT/Apache-2.0/GPL). README selbst nennt diese Luecke: "An explicit LICENSE file follows on the operator's selection." |
| v91-core-system (main 53b34a2) | NICHT VORHANDEN | README-Sektion "License": "(c) 2026 Sebastian (guenny9000) - Alle Rechte vorbehalten" | GESPERRT: keine LICENSE-Datei, alle Rechte vorbehalten; die Betreiber-Freigabe aus Agathon sagt "V91" insgesamt, ist im core-system-Repo aber nicht dokumentiert |
| Aurelia-Prisma (main fd85969) | NICHT VORHANDEN | README: "[Lizenz nicht festgelegt - Betreiber-Entscheidung offen. Keine Verwendung unter Annahme einer Lizenz.]" | UNBEKANNT/GESPERRT: bewusst offen gesetzt, keine Annahme erlaubt |
| v91-audit-ledger (privat) | entfaellt | privates Repo, laut README nur historische Referenz; gepflegte Ledger-Implementierung liegt in V91_Agathon src/v91/ledger.py | NICHT OEFFENTLICH (bewusst: kein freier Zugang, aber auch keine aktive Nutzung) |

Legende: GEMESSEN = Dateiabruf am 23.11.2026. Alle darueberhinausgehenden Aussagen (z. B. tatsaechliche Weitergabefaelle) sind UNKNOWN.

## Was daraus folgt (Empfehlungen, REVIEW != ENTSCHEIDUNG)

1. Formale Lizenz fehlt ueberall: Die Agathon-Freigabe ist eine Klartext-Zusage, aber erst eine formale, distribuierbare Lizenz (MIT, Apache-2.0, GPL-Familie or eine eigene Freeware-Klausel mit klarer Weitergaberegelung) macht die Freigabe erst maschinenlesbar und durchsetzbar. Auswahl: NUR Sebastian (Rechte-Inhaber). Dieses Dokument nennt keine Praeferenz als Beschloss.
2. Wenn die Freigabe "V91 gesamt" gelten soll (so der Wortlaut "V91 is free to use and to spread in full"), waere die konsistente Umsetzung: gleiche LICENSE-Datei je Repo mit derselben Regelung plus Verweis auf die Betreiber-Freigabe. Jede abweichende Regelung je Repo waere ebenfalls gueltig - Betreiberentscheidung.
3. Loopback-vs-Freigabe-Konflikt ist keiner: "Freier Zugang" fuer die Software (Quelle, Nutzung, Weitergabe) ist unabhaengig vom Netzwerk-Betrieb. Aurelia-Prisma bleibt Loopback-only (Bearer-Auth fail-closed, PR #246, #242), bis die Bereitstellungs-/Zugriffskonfiguration geprueft ist - gerade weil die Software frei weitergeben wird, haerten die Laufzeit-Defaults. FREIGABE != EXPOSITION.
4. Fuer "unsichere Netzwerke" (Freigabe-Wortlaut) gilt unveraendert: keine Backdoors, keine Remote-Zugriffe, keine Abschalt-Autoritaet gegen Dritte; Nutzer unsicherer Umgebungen tragen ihre lokale Haertung selbst (Notfallprotokoll-Doku PR #46).
5. Kein Modell tangiert hier Rechte anderer: NICHTS in diesem Dokument legitimiert Nutzung/Weitergabe unter Annahme einer Lizenz. Bis zur formalen Lizenz gilt je Repo das, was dort dokumentiert ist - core-system und Aurelia-Prisma bleiben bei "keine Verwendung unter Annahme einer Lizenz".

## Ehrliche Grenzen

- GEMESSEN sind nur Dateiexistenz und dokumentierter Wortlaut an einem Zeitpunkt. Urheberrechtliche Bewertung: UNKNOWN, keine Rechtsberatung.
- Die Weitergabe-Freigabe aendert keinen Implementierungs-Status: NICHTS wird durch eine Lizenz produktiver; DOKUMENTIERT != INSTALLIERT bleibt.
- Nachtrag: Wenn Sebastian eine Lizenz waehlt, gehoeren LICENSE-Datei je gewaehltem Repo + eine Zeile in diesen Review-Bestand (Append-only).

Verweise: V91-Agathon README (Betreiber-Freigabe), Lernblock Legacy-Strukturen (#426), Review-Objekt Legacy-Energie & Speicher (#430), Repair-/Modularitaets-Charter (offene Standards); die Kollisionsregel des UNIVERSAL-LEARNING-BLOCKS bleibt unberuehrt.
