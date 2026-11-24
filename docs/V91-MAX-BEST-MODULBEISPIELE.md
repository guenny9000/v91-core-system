# V91 / MAX-BEST: Modulbeispiele zum Mathematischen Kern

Version 1.0 | 24.11.2026 | Passt zu docs/V91-MAX-BEST-MATHEMATISCHER-KERN.md
(#523) und dessen ausfuehrbarer Form controller/max_best_rechner.py (#525).
Betreiber-Beauftragung: erster Offizier, 24.11.2026 abends.

STATUS: MODELL - BEISPIELE | BEISPIEL != MESSUNG, TUPEL != BETRIEB,
DOKUMENTIERT != INSTALLIERT. Kein Beispiel behauptet, dass ein
Modul diese Regeln bereits technisch umsetzt oder dass echte
Messwerte vorliegen. UMSETZUNG NICHT BEHAUPTET (CLAIM != EVIDENCE);
ohne Messwerte bleibt jeder Modul-Status NICHT GEPRUEFT.

## 1. Zweck und Abgrenzung (NO_DUPLICATE_SYSTEMS)

Der Kern definiert die Form M_i = (Z_i, R_i, E_i, A_i, W_i) und die
Formeln. Dieses Dokument fuellt die Form NUR mit je einem Beispiel-
Tupel fuer drei Module und legt die einheitliche Nachweisblock-
Schnittstelle fest. Die Formeln werden NICHT wiederholt (Verweis auf
Kern Abschnitt 2 und docs/V91-MAX-BEST-RECHENBEISPIELE.md); die
qualitativen Regeln bleiben in docs/V91-AUDIT-KERN.md und der
Agenten-Arbeitsarchitektur alleinverbindlich.

## 2. Beispiel-Modul Energie (Messpfad-Beispiel)

    M_Energie = (Z, R, E, A, W)
    Z Ziel:       sichere, messbare Energieversorgung
                  (Grundversorgung vor Komfort)
    R Ressourcen: Verbrauch <= verfuegbare Kapazitaet
                  (Kern: Summe(R_i) <= R_verfuegbar)
    E Evidenz:    Messreihen der Controller-Messpipeline
                  (measurement_core/ingest/store); ohne Messdaten
                  bleibt der Zustand NICHT GEPRUEFT
    A Aktionen:   autorisiert: Lesen, Pruefen, Protokollieren;
                  Eingriffe nur nach Betreiber-Freigabe
                  (REQUEST != AUTHORIZATION)
    W Wirkung:    Messgroessen Effizienz und Verfuegbarkeit (Kern
                  Abschnitt 2); Kontrolle ueber Tests und Ledger

## 3. Beispiel-Modul Digital/Betrieb (Integritaets-Beispiel)

    M_Digital = (Z, R, E, A, W)
    Z Ziel:       Integritaet und Wiederherstellbarkeit
                  (RECOVERY > OPTIMIZATION)
    R Ressourcen: Ledger-Groesse, Laufzeit-Budgets, Test-Kapazitaet
    E Evidenz:    verify_chain()-Laeufe, CI-Ergebnisse, fsync-Ledger;
                  ein Hash allein beweist weder Wahrheit noch
                  ordnungsgemaesse Ausfuehrung (Kern Abschnitt 6)
    A Aktionen:   autorisiert: Lesen, Pruefen, Isolieren
                  (ISOLATE_NOT_DESTROY); KEINE Loeschung, KEIN
                  Rebase (aendert SHAs, bricht die Hash-Kette,
                  NICHT WORM-kompatibel)
    W Wirkung:    Manipulation wird erkannt (Kettenbruch bleibt
                  ehrlich FEHLGESCHLAGEN); je Eingriff gilt ein
                  dokumentierter Wiederherstellungspfad

## 4. Beispiel-Modul Ressourcen und Kreislauf

    M_Ressourcen = (Z, R, E, A, W)
    Z Ziel:       Verbrauch im Rahmen der Regenerationsfaehigkeit
                  (ERHALTEN > ERSETZEN, wo Erhalten besser ist)
    R Ressourcen: Verbrauch <= Regeneration; kein Modul erkauft
                  Verbesserung durch Schaden in einem anderen
                  (Kern Abschnitt 4)
    E Evidenz:    Inventar- und Zaehldaten (z. B. seed_inventory
                  Keimprobe mit zur Rate passender Evidenz); ohne
                  Zaehlung NICHT GEPRUEFT
    A Aktionen:   autorisiert: Inventur, Pruefung, Dokumentation;
                  Abbau-Entscheide bleiben Betreiber-Entscheid
    W Wirkung:    Messgroessen Bestandsaenderung, Verlustrate,
                  Regenerationsfaehigkeit (Nachhaltigkeit, Kern
                  Abschnitt 7)

## 5. Einheitlicher Nachweisblock (Schnittstelle, VERWEIS statt Zweit-Vertrag)

Jedes Modul pflegt EINEN Nachweisblock mit genau diesen Feldern:

    Ziel:                     was das Modul erreichen soll (Z_i)
    Messgroesse:              woran Wirkung gemessen wird (W_i)
    Belegquelle:              woher der Beleg stammt (E_i)
    Status:                   BELEGT | IN ARBEIT | VORSCHLAG |
                              NICHT GEPRUEFT | NICHT VERFUEGBAR |
                              FEHLGESCHLAGEN | VERBESSERT
    Wiederherstellungspfad:   wie der Ausgangszustand zurueckkehrt
                              (Kern Abschnitt 5)

Das ist KEIN zweiter Vertrag: verbindliche maschinenlesbare Schnitt-
stelle bleibt controller/uas_record.py (113.0.0: origin,
authorization, risk_level, rollback, evidence) laut
docs/V91-UAS-VERTRAG-KANON.md. Der Nachweisblock ordnet Modul-Doku
begrifflich zu (KANON == ABLEITUNG != ZWEITE_WAHRHEIT).

## 6. Kern/Detail-Trennung (64-KiB-Ziel)

Der mathematische Kern bleibt verdichtet (< 8 KiB, verriegelt in
tests/test_max_best_math_kern.py). Modulbeispiele und Details wohnen
hier bzw. in den zustaendigen Dokumenten, nicht im Kern. Das
Architektur-Index-Verschlanungskziel (Betreiber-Frage "unter 64 kB")
wird hier NICHT durch Loeschen von Chronologie beansprucht; das bleibt
eine eigene Betreiber-Strukturentscheidung.

## 7. Verweise statt Duplikate

- docs/V91-MAX-BEST-MATHEMATISCHER-KERN.md - Form und Formeln
- docs/V91-MAX-BEST-RECHENBEISPIELE.md - ausfuehrbare Beispiele
- docs/V91-UAS-VERTRAG-KANON.md - verbindliche Feld-Schnittstelle
- docs/V91-AUDIT-KERN.md - Ebenen-Trennung, Wahrheitsregel
- docs/V91-ARCHITEKTUR-INDEX.md - verbindliches Verzeichnis

## 8. Grenzen

BEISPIEL != MESSUNG: diese Tupel sind Struktur-Vorfuehrung, keine
Betriebsdaten. Kein Modul der Repos wird hiermit als umgesetzt,
gemessen oder verbessert behauptet. Ohne echte Daten bleibt jeder
Modul-Status NICHT GEPRUEFT; die technische Umsetzung ist NICHT
BEHAUPTET und bleibt Aufgabe der Module mit eigenen Tests.
