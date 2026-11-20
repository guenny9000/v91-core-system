# R3-Messwert-Ledger (docs/ledgers)

Verbindliche Konvention fuer reale Messwert-Ledger der Pilot-Initiativen.

## Zweck

Dieses Verzeichnis enthaelt die R3-Stufe der Messkette:
R2-Messmatrix-Datasets (docs/messmatrix) definieren Kriterien,
die Ledger hier enthalten NUR dokumentierte reale Beobachtungen.
MATRIZ != WIRKUNG; OBSERVED != ERFOLG; UNKNOWN bleibt UNKNOWN.

## Konventionen (fail-closed)

1. Eine Datei je Initiative: `docs/ledgers/{initiative_id}.jsonl`
   (initiative_id identisch zur Messmatrix-Datei der Initiative).
2. Eintraege werden NUR ueber `controller/messwerte_ingest.py`
   (`MesswertLedger.append`) erzeugt. Hand-Editierte Dateien brechen
   die SHA-256-Kette und schliessen das Tor GATE_2_LEDGER.
3. Jeder Eintrag benoetigt: initiative_id, indicator (exakter
   Indikatorname aus der Messmatrix), value (Zahl, nicht-negativ),
   measured_at (ISO-8601 innerhalb baseline_at..target_at,
   Grenzen inklusiv), source (https://, http://, doi:, /path oder
   ledger::), optional note, measured_by.
4. Kein Eintrag ohne dokumentierte Quelle. Keine Schaetzungen,
   keine Hochrechnungen, keine Werte aus abweichender Belichtung
   (etwa Wochenwert gegen kumulative Baseline), es sei denn, die
   Abweichung ist im note exakt benannt.
5. Kein Eintrag fuer Indikatoren, die es in der Messmatrix nicht
   gibt. KEIN_INDIKATOR != MESSUNG_ERZWINGEN: Eine Zahl, die zu
   keinem definierten Indikator passt, wird nicht eingespeist.
6. Ausgeschlossen bleiben: Zusagen ohne Verausgabung (KOSTEN),
   Zielwerte ohne Ist-Messung (ZIELWERT != ERGEBNIS), Werte aus
   Sekundaerquellen mit abweichender Definition, waehrend eine
   Primaerquelle fehlt.
7. SIGNATUR != WAHRHEIT: Strukturgueltigkeit ist keine
   Wahrheitsgarantie. Das Assessment (controller/wirkungs_assessment.
   py) prueft Tore, keine Kausalitaet und keine Quellenwahrheit.
8. Loeschen oder Umordnen von Eintraegen ist verboten
   (append-only). Korrekturen erfolgen als neuer Eintrag.

## Werkzeuge

- Anhaengen: `MesswertLedger(path).append(payload, record)`
- Kettenpruefung: `MesswertLedger(path).verify_chain()`
- Tor-Pruefung und Fortschritt:
  `controller/wirkungs_assessment.py assess(dataset, ledger)`
- Aggregation: `controller/wirkungs_index.py build-index
  --dataset-dir docs/messmatrix --ledger-dir docs/ledgers`

## Realstand (21.11.2026)

Ledger existieren fuer Pilot E (frieden, WIRKUNG_BEOBACHTET,
Fortschritt 0.0) und Pilot C (gesundheit, Pilot bleibt
WIRKUNG_UNKNOWN, ein RESILIENZ-Wert beobachtet). Alle anderen
Piloten haben keinen Ledger und bleiben damit WIRKUNG_UNKNOWN.
WIRKUNG_BEOBACHTET ist niemals WIRKUNG_NACHGEWIESEN.
