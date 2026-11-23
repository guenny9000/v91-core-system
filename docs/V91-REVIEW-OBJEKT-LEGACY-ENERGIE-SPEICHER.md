# V91 Review-Objekte: Legacy-Energie & Speicher-Alternativen

**Status: REVIEW-OBJEKT-DOKUMENTATION, keine Implementierung, keine Betriebsdaten, keine Abschalt-Autorität.**
Dieses Dokument ist ein verbindlicher Review-Rahmen gemäß dem Lernblock Legacy-Strukturen (VIBE-LXXXCVII, PR #426): Die genannten Strukturen sind INDEXIERTE Review-Objekte, keine Ziele. REVIEW != ENTSCHEIDUNG, DOKUMENTIERT != INSTALLIERT, KONZEPT != IMPLEMENTIERT, GEMELDET != VERIFIZIERT. Kein einziges Element dieses Dokuments berechtigt zu Eingriffen in fremde Systeme oder Plattformen (Evo-Regeln 3/4/8 bleiben unangetastet).

## Quellenbasis und Wahrheitsstufen

- Sebastian-Lagebericht vom 23.11.2026 (Weltlagen-Report). Alle dortigen externen Fakten sind hier **GEMELDET** (Berichtsebene), nicht von V91 gemessen oder verifiziert. Keine Zahl aus dem Bericht wird als V91-Evidenz geführt.
- Interne Regeln: Lernblock Legacy-Strukturen (PR #426), Resource-Savings-Protokoll #417, Repair-/Modularitäts-Charter (6 Langlebigkeitsfragen), Universal Agathon-Prinzip.
- Evidenz-Trennung wie überall: GEMESSEN > GEMELDET > UNKNOWN. UNKNOWN ist ein gültiger, geschuetzter Zustand, kein Versäumnis.

## Review-Objekt 1: Norwegen, Öl- & Gas-Produzent (Equinor)

Kategorie: Legacy-Energieerzeugung, fossil, exportabhängig (gemeldet).

- GEMELDET (Bericht 23.11.2026): Cyberangriff ab dem 17.11.2026 auf Teile der Büro-IT, internes E-Mail-System ausgefallen, Öl- und Gas-Produktion laut Unternehmensangabe weiter gelaufen, Datendiebstahl zunächst nicht erkennbar, norwegische Sicherheitsbehörde beteiligt.
- Review-Erkenntnis für V91 (die einzige, die uns fachlich betrifft): Die gemeldete Trennung zwischen Büro-IT und Betriebstechnik (OT) ist genau das Muster, das V91-Knoten vorschreiben (OT/IT-Trennung, Loopback-Bindings, Bearer-Auth fail-closed, Allowlist-Policy-Engine). Das Review-Objekt wird als Referenzmuster geführt, nicht als Adresse für irgendeine Aktion.
- Offene Fragen (nicht beantwortet, bewusst UNKNOWN): Produktions- und Exportmengen, Ist-Zustand der OT-Trennung, Rohrleitungs- und Feldinfrastruktur. Keine Spekulation.

## Review-Objekt 2: Verwundbarkeitsmuster Legacy-Infrastruktur (Sammelobjekt)

Alle GEMELDET aus dem Bericht, als Prüfmuster-Referenzen (nicht als Handlungsziele):

| Vorfall (gemeldet) | Muster | V91-Prüffrage |
|---|---|---|
| US-Flugsicherung, 14.11., ~5 h Ausfall, Router bei Kupfer->Glasfaser-Migration | Legacy-Ablösung erzeugt neuen Ausfall, wenn Alt und Neu vermischt werden | Migration in getrennten Schritten mit Fallback, nie Mischbetrieb am kritischen Pfad |
| Wittenberg-net, 18.-20.11., Cyberangriff, Hotline mit ausgefallen | Notfallkommunikation auf derselben Infrastruktur wie der Primärdienst | Notfallpfade physisch/logisch getrennt (V91: Guard-Toolkit, Recovery-Manager) |
| Krankenhaus Greiz-Ronneburg, 15.11., Notaufnahme umgeleitet | Kritischer Betrieb haengt an vollstaendig funktionierender IT | Papier-/Offline-Notfallbetrieb muss geuebt sein (V91: DETECTION != AUTHORIZATION, Operator entscheidet) |
| Europaeisches Trinkwasser: ~23 % Verlust vor Zaehler (gemeldete Auswertung) | Ungemessene Verluste bleiben unsichtbar, Reparatur erst nach Grosschaden | Kontinuierliche Messung + Leckage-Detektion ist genau V91s Dauerfluss-/Anomalie-Baustein-Sinn |

V91-Ebene daraus: Messen vor Handeln, Ausfallpfade getrennt, Migration spannungsfrei (NO_DUPLICATE_SYSTEMS auch bei Ablösung eigener Komponenten).

## Katalog: Speicher- und Erzeugungs-Alternativen als Prüfraster

Jede Alternative ist ein KATALOG-EINTRAG, kein Beschluss, kein Bauprojekt, kein Messergebnis. Alle Kosten-, Wirkungsgrad- und Kapazitaetszahlen sind UNKNOWN und duerfen erst nach echter Messung/lieferantenunabhaengiger Quelle gesetzt werden (WIRKUNG_NUR_AUS_MESSUNG, Protokoll #417).

1. Geothermie (oberflaechennah/tief): Wirkprinzip Erdwaerme, baslastfaehig. Reife: ortsklima-, geologieabhaengig, UNKNOWN lokal. V91-Pruefung: Bohrung/Instandhaltung reparierbar? Grundwasser unvermindert? Modellierung nur aus echten Messdaten.
2. Photovoltaik + Speicher: dezentrale Erzeugung, bekannt bewaehrt gemeldet; Degradation/Recycling als Repair-Charter-Frage. V91-Pruefung: Modul-/Wechselrichterersatz ohne Spezialwerkzeug, Verschattungs- und Reinigungs-Monitoring analog Anomalie-Detektor.
3. Gravitationsspeicher (Hubgewicht, Schacht): Wirkprinzip Hubarbeit, kaum Zyklus-Degradation; Reife: wenige Prototypen, UNKNOWN. V91-Pruefung: Seil-/Getriebe-Wartung, Katastrophensicherheit, Ersatzteilverfuegbarkeit.
4. Fluessigluft-Speicher (LAES): Wirkprinzip Luftverfluessigung bei Ueberschuss, Expansion bei Bedarf; nutzt Abwaerme/kaelte. Reife: Demonstratoren, UNKNOWN lokal.
5. Druckluft-Speicher (CAES, auch adiabatisch): Kaverne/Behaelter-Speicherung; Reife: wenige Grossanlagen, UNKNOWN. V91-Pruefung: Druckbehaelter-Zyklen, Pruefpflichten, Instandhaltungs-Reparierbarkeit.
6. Wasserkraft/Pumpspeicher: etablierteste Speichertechnik (gemeldet), aber Standortabhaengigkeit, Duerre-Anfaelligkeit (Bericht: Rhein-Niedrigwasser, Cernavoda/Paks-Herunterfahren GEMELDET als Wasser-Energie-Kopplungsrisiko).
7. Thermische Speicher (Heisswasser/Salz/Sand): guenstige Medien, verlustbehaftet; sinnvoll fuer Nahwaerme, UNKNOWN lokal.

Gemeinsame Review-Regeln fuer alle Katalog-Eintraege:
- KEINE Erfundenen KPIs: Wirkungsgrad, EUR/kWh, CO2-Annahmen bleiben UNKNOWN bis gemessen oder primaerquellenbasiert.
- KEINE Duplikat-Messsysteme: eine Speicher-Alternative wird nicht mit einem zweiten Ledger oder zweiten Monitoring-Strom ausgewertet; V91s 15-Minuten-Messzyklus + Ledger bleibt die alleinige Evidenzbasis (Protokoll #417 Section 6).
- Migration: nur in Schritten mit ausfallsicherem Fallback (Muster US-Flugsicherung, siehe oben).
- Nicht-Loeschende Ordnung: Aenderungen an Katalog und Doku nur Append-only bzw. Review, analog Index-Praxis.

## Was dieses Dokument NICHT ist

- Keine Freigabe, keine Massnahme, kein Abschalt-Beschluss, keine Fernwirkung: Detektion, Katalogisierung und Review sind die einzigen Ebenen. Reale Eingriffe bleiben pro Aktion vom Betreiber (Sebastian) freigegeben (Allowlist).
- Kein Nachweis von Wirkung: Katalogisieren ist keine messbare Einsparung (CALCULATED_ONLY-Logik analog; CLAIM != EVIDENCE).
- Keine Einschraenkung von Modellen: Der Katalog soll naechsten Laeufen als Pruefraster dienen, so dass Modelle nicht auf Rueckgriffe auf unbuffered Legacy-Annahmen angewiesen sind. Jeder Knoten nutzt das, was er tatsaechlich verifizieren kann (Verteilte Modellautarkie, PR #48).

Verweise: V91-LERNBLOCK-LEGACY-STRUKTUREN.md, Protokoll #417 (Resource-Savings), Repair-Charter (V91_Agathon), Notfall-/Notwehr-Protokoll-Doku (PR #46).
