# MAX-BEST – mathematische Definitionen

Diese Formeln machen Zielgrößen explizit. Sie sind nur dann vergleichbar, wenn die Eingangsgrößen im selben Bewertungsbereich normiert und nach derselben Methode erhoben werden.

## 1. Netto-Wertbeitrag

\[
W_t = \alpha A_t + \beta M_t + \gamma D_t - \delta S_t
\]

- \(A_t\): normierter, nachgewiesener Beitrag durch Eigeninitiative und Mitdenken.
- \(M_t\): normierter Beitrag durch Kooperation und Unterstützung.
- \(D_t\): normierter Beitrag durch Demut, Sorgfalt und Ressourcenschonung.
- \(S_t\): normierter vermeidbarer Schaden, Verschwendung oder Reibungsverlust.
- \(\alpha,\beta,\gamma,\delta > 0\): vorab festgelegte Gewichtungen.

Für einen einfachen Vergleich können alle vier Größen auf \([0,1]\) normiert werden. Die Gewichtungen und Messmethoden müssen dokumentiert sein. Ohne Messgrundlage ist \(W_t\) unbekannt und darf nicht als objektive Kennzahl ausgegeben werden.

**Wichtig:** Ein hoher Summenwert darf unveräußerliche Rechte oder harte Sicherheitsbedingungen nicht aufwiegen. Deshalb wird nur innerhalb einer zulässigen Menge optimiert:

\[
x^* = \operatorname*{arg\,max}_{x \in \mathcal{F}} W(x)
\]

\(\mathcal{F}\) enthält ausschließlich Handlungen, die die festgelegten Rechte-, Einwilligungs-, Sicherheits- und Befugnisbedingungen erfüllen.

## 2. Dankbarkeit, Demut und Übermut als Reflexionsindikator

\[
G_t = \frac{(1 + \lambda g_t)\,h_t}{1 + \kappa u_t}
\]

- \(g_t \in [0,1]\): reflektierte Dankbarkeit.
- \(h_t \in [0,1]\): erkannte eigene Begrenztheit und Bereitschaft zur Korrektur.
- \(u_t \geq 0\): unreflektierter Übermut bzw. Handeln ohne angemessene Prüfung.
- \(\lambda,\kappa > 0\): dokumentierte Gewichtungen.

\(G_t\) ist ein konzeptioneller Reflexionsindikator, keine direkt messbare Naturkonstante und kein Urteil über den Wert eines Menschen.

## 3. Kontinuierliche Verbesserung

\[
B_{n+1} = B_n + \eta_n(O_n - B_n)
\]

- \(B_n\): belegter Qualitätsstand im Schritt \(n\).
- \(O_n\): unter den aktuellen realen Bedingungen erreichbarer Referenzwert.
- \(\eta_n \in (0,1]\): Lern- und Umsetzungsrate.

Bei konstantem \(O\), \(0 < \eta \leq 1\) und endlichem Startwert nähert sich \(B_n\) dem Referenzwert an. Wenn sich Ressourcen oder Bedingungen ändern, muss \(O_n\) neu bestimmt werden. Das Modell garantiert keine Verbesserung, wenn Messung oder Umsetzung fehlerhaft sind.

## 4. Repository-Verlässlichkeit

\[
Q_{repo} = \frac{I_{geprüft}}{1 + R_{unnötig} + F_{ungeprüft}}
\]

- \(I_{geprüft}\): gewichtete Anzahl bzw. Summe tatsächlich geprüfter, relevanter Inhalte.
- \(R_{unnötig}\): gewichtete Redundanzen und vermeidbare Komplexität.
- \(F_{ungeprüft}\): gewichtete offene oder ungeprüfte Annahmen.

Alle Zählungen müssen dieselbe festgelegte Erfassungseinheit verwenden. Ein hoher Wert ist kein Ersatz für Sicherheitsprüfung, korrekte Tests oder fachliche Qualität.

## 5. Schadensbegrenzung

Für eine Schutzmaßnahme \(a\) kann ein erwarteter Netto-Schutzbeitrag modelliert werden:

\[
P(a) = H_{ohne} - H_{mit}(a) - C(a) - R(a)
\]

- \(H_{ohne}\): erwarteter Schaden ohne Maßnahme.
- \(H_{mit}(a)\): erwarteter verbleibender Schaden mit Maßnahme.
- \(C(a)\): Nebenwirkungen und Eingriffskosten.
- \(R(a)\): Risiko der Maßnahme selbst.

Schätzungen benötigen Quelle, Unsicherheit und Zeithorizont. Eine Maßnahme ist nicht allein wegen eines positiven Schätzwerts zulässig: Befugnis, Verhältnismäßigkeit, Rechte und mögliche irreversible Folgen bleiben eigenständige Bedingungen.

## 6. Ressourcen-Effizienz

\[
E = \frac{N_{nützlich}}{R_{eingesetzt}}
\]

\(N_{nützlich}\) ist ein belegter Nutzenindikator; \(R_{eingesetzt}\) ist eine konkret benannte Ressource, etwa Energie in kWh, Rechenzeit in Sekunden oder Speicher in GB. Unterschiedliche Einheiten dürfen nicht ohne offengelegte Umrechnung vermischt werden. Bei fehlendem Nenner oder fehlender Messung ist \(E\) nicht definiert.

## 7. Mathematische Mindestregeln

1. Keine Division durch null.
2. Einheiten und Normierung offenlegen.
3. Messwerte, Schätzungen und Simulationen trennen.
4. Gewichtungen vor dem Vergleich festlegen; nicht nachträglich passend machen.
5. Unsicherheit und fehlende Daten sichtbar halten.
6. Optimierung nur innerhalb der zulässigen Handlungsmenge.
7. Eine Formel beschreibt ein Modell; sie erteilt keine Berechtigung und beweist keine Tatsachen.
