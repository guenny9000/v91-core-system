# V91 Erkenntnis- und Revisionsprotokoll

Status: ERGAENZUNGSPROTOKOLL; dokumentarische Regel, keine Programmiersprache,
Laufzeitsteuerung oder eigenstaendige Eingriffsbefugnis.
Geltung: V91-Beitraege, Audits, Messberichte und dokumentierte Entscheidungen.
Vorrang: Menschenwuerde, Rechte, Sicherheit, bestehender V91-Kanon und reale
Evidenz. Bei Konflikten gilt die konkretere Schutzregel.
Abgrenzung: Praezisiert docs/V91-AUDIT-KERN.md und MAX-BEST-GELUEBNIS/PROTOCOL;
ersetzt diese Regeln oder bestehende Messpfade nicht.

## 1. Zweck und Wahrheit

Das Protokoll kennzeichnet den Erkenntnisstatus einer Aussage, ihre Belege
und den Anlass fuer erneute Pruefung.

Wahrheit bezeichnet die Wirklichkeit unabhaengig davon, was jemand behauptet
oder ein System anzeigt. Das Protokoll kann Wahrheit nicht per Statuszeichen
verleihen; es ordnet nur Aussagen und ihre Belege in begrenztem Geltungsbereich.

EIN ZEICHEN IST KEIN BELEG. EIN BELEG IST KEINE UNBEGRENZTE WAHRHEIT.
EINE PRUEFUNG IST KEINE VERBESSERUNG. VERBESSERUNG BRAUCHT EINEN
VORHER-NACHHER-NACHWEIS. JEDE ERKENNTNIS BLEIBT REVIDIERBAR.

Das Protokoll misst nicht selbst, authentifiziert keine Quelle automatisch
und verleiht keine Berechtigung.

## 2. Erkenntnisstatus und Marker

Die Marker sind neue V91-Kennzeichnungen, keine historischen Runen,
Hieroglyphen oder uebernommenen Kulturzeichen. Die Textkennung ist normativ;
Glyphen sind optionale Darstellungshilfen.

- ? CLAIM: Aussage/Annahme, noch nicht nachgewiesen.
- OBS: Beobachtung mit Beobachter, Kontext und Zeitpunkt.
- MEAS: Messung mit Wert, Einheit, Quelle, Verfahren, Zeitfenster und Unsicherheit.
- VER: eng umrissene Aussage durch geeignete Belege verifiziert.
- IMP: konkrete Verbesserung umgesetzt und dokumentiert.
- REMEAS: Wirkung gegen Baseline und vorher festgelegte Kriterien nachgemessen.
- UNK: unbekannt oder nicht ausreichend bestimmt.
- ! DISPUTED: Widerspruch, Anomalie oder Gegenbeleg.
- REV: Aussage, Methode oder Bewertung nachvollziehbar revidiert.

Optionale Glyphen (Unicode-Codepunkt):
- CLAIM U+003F (?); OBS U+25C9 (Kreis mit Punkt); MEAS U+223F (Sinuswelle).
- VER U+2713 (Haken); IMP U+2197 (Pfeil nach rechts oben).
- REMEAS U+27F3 (Kreispfeil); UNK U+25C7 (offene Raute).
- DISPUTED U+0021 (!); REV U+2727 (Sternchen).

Fehlt eine Glyphe oder wird sie anders dargestellt, gilt die Textkennung.
Die Marker sind keine Rangliste und keine starre Pipeline. UNK kann jederzeit
gelten; Gegenbelege koennen VER zu DISPUTED machen. REV ist quer zu allen
Status jederzeit zulaessig und bei Gegenbeleg, Methodenfehler oder
relevant geaendertem Kontext erforderlich.

## 3. Pflichtangaben

Relevante OBS-, MEAS-, VER-, IMP- und REMEAS-Eintraege enthalten, soweit
anwendbar:
1. Aussage/Prueffrage und begrenzten Geltungsbereich.
2. Quelle/Datenherkunft und unveraenderten Artefaktverweis.
3. Zeitpunkt, Zeitbasis und ggf. Anfang/Ende des Zeitfensters.
4. Methode, Version, Umgebung und relevante Bedingungen.
5. Einheit, Rohwert sowie Qualitaets- und Unsicherheitsangabe bei Messungen.
6. Verantwortliche Person/Verfahren; bei Bedarf getrennte Pruefer.
7. Ergebnis, Grenzen, Gegenbelege und offene Punkte.
8. Wiederholbarkeit oder Begruendung ihrer Unmoeglichkeit.

Nicht anwendbare Felder: N/A mit Begruendung. Fehlende Pflichtangaben
werden nicht still ergaenzt; Status bleibt UNK oder NICHT_GEPRUEFT.
Schaetzungen bleiben als Schaetzungen gekennzeichnet.

## 4. Verifikation und Reichweite

VER gilt nur fuer die konkrete Aussage, den dokumentierten Commit, die
Umgebung und den Testumfang.

- Quelle vorhanden != Quelle authentisch.
- Hash stimmt != Inhalt wahr.
- Test bestanden != System sicher oder produktiv.
- CI gruen != Realbetrieb.
- Beobachtet != gemessen; gemessen != unabhaengig verifiziert.
- Verifiziert != universell oder dauerhaft wahr.

Bei hohem Risiko ist eine unabhaengige Gegenpruefung vorzusehen.
Selbstdeklaration macht einen eigenen CLAIM nicht zu VER.
UNKNOWN != PASS bleibt uneingeschraenkt.

## 5. Verbesserung und Wirkung

IMP dokumentiert Aenderung, Grund, Verantwortlichkeit, Zeitpunkt,
Autorisierung und Rueckfall-/Wiederherstellungsplan. IMP allein belegt
keine positive Wirkung.

REMEAS benoetigt:
- eine vor der Aenderung festgelegte Baseline,
- vergleichbare Bedingungen und ein definiertes Zeitfenster,
- Methode, Einheit, Unsicherheit und Rohdatenverweis,
- vorher festgelegte Erfolgskriterien,
- Nebenwirkungen, Regressionen und nicht gemessene Aspekte.

Fehlt ein fairer Vergleich, lautet der Befund NICHT NACHGEWIESEN.
Eine Verbesserung darf keine relevante Verschlechterung verdecken.
Menschenwuerde, Sicherheit und Grundversorgung sind keine blossen
Effizienz-Gegenwerte.

## 6. Stein der Revision

Leitsatz: ICH KOENNTE MICH IRREN.

Revision ist kein letzter Schritt nach REMEAS, sondern eine dauerhafte
Pruefpflicht fuer Behauptungen, Beobachtungen, Methoden, Kriterien,
Verifikationen, Entscheidungen und dieses Protokoll selbst.

Festzuhalten sind: bisherige Aussage/Status; Anlass und neuer Beleg oder
Methodenfehler; neue Bewertung und Geltungsbereich; Auswirkungen auf
fruehere Entscheidungen; Verantwortlichkeit, Zeitpunkt und Folgepruefung.

Historische Eintraege werden nicht still ueberschrieben. Korrekturen
verweisen auf den ersetzten/eingeschraenkten Eintrag; die Provenienz
bleibt sichtbar. Revision ist kein Makel und kein Schuldnachweis.

## 7. Zyklus und bestehende Regeln

Der vorhandene MAX-BEST-/RealRun-Zyklus bleibt massgeblich
(docs/V91-MAX-BEST-REALRUN-ZYKLUSCHECK.md). Dieses Protokoll praezisiert
darin den Erkenntnis- und Nachweisteil:

Entdecken -> Frage/CLAIM abgrenzen -> Beobachten/Messen -> Bewerten und
verifizieren -> Bewahren/Verbessern/Erforschen -> Wirkung nachweisen ->
erneut messen/pruefen -> bei Bedarf revidieren -> weiterlernen.

Das ist Orientierung, keine starre Pipeline. UNK, DISPUTED oder REV koennen
in jeder Phase auftreten. Massnahmenstein-Eintraege behalten
Verantwortlichkeit, Prioritaet, Nachweis und Wirkung.

## 8. Historische und kulturelle Abgrenzung

Runeninschriften, Hieroglyphen sowie chinesische und japanische Schriften
sind unterschiedliche historische Systeme. V91 uebernimmt nur die Idee
kompakter, kontextklarer Kennzeichnungen; historischen Zeichen wird keine
V91-Bedeutung zugeschrieben. Mythen liefern keine technischen Tatsachen
oder Governance-Befugnisse.

Yggdrasil, Mimir, Odins Auge, die Voelva und Nidhoegg sind Erzaehlbilder
fuer Wissen, Erkenntnisgrenzen, Perspektive und sichtbare Schwaechen.
MYTHOS != SPEZIFIKATION; ANALOGIE != BEWEIS; ERZAEHLUNG != VERTRAG.

## 9. Grenzen

Dies ist ein Ergaenzungsprotokoll, kein neues Grundgesetz, kein
Datenformat-Zwang und keine automatische Steuerung. Bestehende Systeme
muessen nicht allein wegen dieses Textes umgebaut werden. Technische
Umsetzung benoetigt einen eigenen Entwurf, Sicherheits-/Datenschutzpruefung,
Schnittstellen, Tests und Autorisierung.

Dokumentiert != implementiert. Implementiert != verifiziert.
Verifiziert != produktiv. Kein Marker ersetzt Belege oder Verantwortung.
