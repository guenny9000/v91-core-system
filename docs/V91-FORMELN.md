# V91-Leitformeln fuer Lernflaeche & Mitwirkung (Fremd-Entwurf-Modell)

Status: FREMD-ENTWURF-MODELL, BETREIBER-UEBERGABE 25.11.2026.
KANONISCHE ALLEINVERBINDLICHE Formelreferenz seit der
Konsolidierung #548 -> hier: die zusaetzlichen Abschnitte aus
FORMELN.md (#548) sind kontrolliert integriert, die Wurzel-
datei ist seitdem NUR noch Verweis (NO_DUPLICATE, KLARUNG
der Gegenpruefung 25.11.2026).
FORMELN == LEITBILD != MESSUNG. Alle Groessen sind EINGABE/ANGABE des
Betreibers, KEINE automatisch gemessenen Werte. Es gibt KEINEN zweiten
Rechner: max_best_rechner (PR #525) bleibt ALLEINVERBINDLICH; diese
Formeln werden von KEINEM Modul automatisch ausgewertet [NO_DUPLICATE].
Behauptungen ueber implementierte Auswertung oder Messwerte sind
FALSCH und werden durch Tests verriegelt.

## 1. Aktives Mitwirken & Verantwortung

W_t = alpha * A_t + beta * M_t + gamma * D_t - delta * S_t

- W_t: Wirksamkeit und Wertbeitrag zum Zeitpunkt t
- A_t: Aktives Mitwirken und eigenstaendiges Mitdenken
- M_t: Kooperative Mitarbeit und Unterstuetzung im Verbund
- D_t: Demut und Ruecksicht auf die Schoepfung
- S_t: Vermeidbarer Schaden, Verschwendung, Reibungsverlust
- Domain: alpha > 0, beta > 0, gamma > 0, delta > 0

## 2. Dankbarkeit & Demut als Stabilitaetsfaktor

G_t = (1 + lambda * Dankbarkeit_t) / (1 + kappa * Uebermut_t) * Demut_t

- G_t: Nachhaltiger Ausrichtungswert
- Domain: Dankbarkeit_t in [0,1], Demut_t in (0,1], Uebermut_t >= 0,
  lambda > 0, kappa > 0

## 3. Kontinuierliche Verbesserung (das Beste geben)

B_(n+1) = B_n + eta_n * (O_real - B_n)

- B_n: Qualitaets-/Reifegrad im Schritt n
- O_real: Unter aktuellen Bedingungen erreichbares Optimum
- Domain: eta_n in (0,1]

## 4. Struktur & Vertraelligkeit im Bestand

Q_repo = Sum(I_geprueft) / (1 + Sum(R_unnoetig) + Sum(F_ungeprueft))

- I_geprueft: verifizierte Inhalte, Tests, nachvollziehbare Schritte
- R_unnoetig: Redundanzen, Duplikate, ueberfluessige Komplexitaet
- F_ungeprueft: offene, nicht gepruefte Annahmen

## 5. ehrliche Grenzen

- ANGABE != BEWEIS: Faktorwerte sind Betreiber-ANGABEN.
- FORMELN != ENTSCHEIDUNG:ENTSCHEIDEN bleibt max_best_rechner/Allowlist.
- Kein Weltmechanismus: Reichweite = eigenes Wirkungskreis-Dokument.

## 5. Zulaessige Menge (Optimierung mit Nebenbedingungen)

Optimiert wird NUR innerhalb der zulaessigen Handlungsmenge:

x* = argmax W(x) fuer x aus F

F enthaelt AUSSCHLIESSLICH Handlungen, die die festgelegten Rechte-,
Einwilligungs-, Sicherheits- und Befugnisbedingungen erfuellen. Ein
hoher Summenwert wiegt UNVERAEUSSLICHE Rechte oder harte
Sicherheitsbedingungen NIEMALS auf (MENSCHENWUERDE > SICHERHEIT >
RECHTE, ZAHLEN_BINDEN_NICHT).

## 6. Schadensbegrenzung

P(a) = H_ohne - H_mit(a) - C(a) - R(a)

- P(a): erwarteter Netto-Schutzbeitrag einer Massnahme a
- H_ohne: erwarteter Schaden ohne Massnahme
- H_mit(a): erwarteter verbleibender Schaden mit Massnahme
- C(a): Nebenwirkungen und Eingriffskosten
- R(a): Risiko der Massnahme selbst
- Domain: Schaetzungen benoetigen Quelle, Unsicherheit,
  Zeithorizont; ein positiver Schaetzungswert erteilt KEINE
  Befugnis (BEFUeGNIS_BLEIBT_GEBUNDEN, REVERSE > FINAL).

## 7. Ressourcen-Effizienz

E = N_nuetzlich / R_eingesetzt

- N_nuetzlich: BELEGTER Nutzenindikator
- R_eingesetzt: konkret benannte Ressource (kWh, Sekunden, GB)
- Unterschiedliche Einheiten duerfen NICHT ohne offengelegte
  Umrechnung gemischt werden; fehlender Zaehler/Nenner oder
  fehlende Messung => E NICHT defininiert (NICHT_GEPRUEFT,
  NIEMALS 0-Ersatz).

## 8. Mathematische Mindestregeln

1. KEINE Division durch null.
2. Einheiten und Normierung offenlegen.
3. Messwerte, Schaetzungen und Simulationen TRENNEN.
4. Gewichtungen vor dem Vergleich festlegen, NICHT nachtraeglich
   passend machen (KEIN_NACHFITTEN).
5. Unsicherheit und fehlende Daten SICHTBAR halten.
6. Optimierung NUR innerhalb der zulaessigen Handlungsmenge.
7. Eine Formel beschreibt ein MODELL; sie erteilt KEINE
   Berechtigung und beweist KEINE Tatsache.

## Ausfuehrbarkeit der Leitformeln (25.11.2026, P6)

Die vier Leitformeln (W_t, G_t, B_n, Q_repo) sind maschinenpruefbar
ausfuehrbar in controller/max_best_leitformeln.py. Die Pruefdisziplin
wird REUSE aus controller/max_best_rechner.py uebernommen
(Unknown-Propagation als NICHT_GEPRUEFT, fail-closed Domains, KEIN
stilles Clampen, KEINE Personenbewertung). FORMEL != MESSUNG bleibt:
alle Eingaben sind ANGABEN; das Modul misst nichts und entscheidet
nichts (RECHNEN != ENTSCHEIDEN, ZAHLEN_BINDEN_NICHT unveraendert).
