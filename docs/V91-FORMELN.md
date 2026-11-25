# V91-Leitformeln fuer Lernflaeche & Mitwirkung (Fremd-Entwurf-Modell)

Status: FREMD-ENTWURF-MODELL, BETREIBER-UEBERGABE 25.11.2026.
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
