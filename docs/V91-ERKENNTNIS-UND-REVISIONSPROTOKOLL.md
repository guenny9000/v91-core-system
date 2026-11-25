# V91 Erkenntnis- und Revisionsprotokoll

Status: ERGAENZUNGSPROTOKOLL - dokumentarische Regel, keine Programmiersprache,
keine Laufzeitsteuerung und keine eigenstaendige Eingriffsbefugnis.
Geltung: V91-Beitraege, Audits, Messberichte und dokumentierte Entscheidungen.
Vorrang: Menschenwuerde, Rechte, Sicherheit, bestehender V91-Kanon und reale
Evidenz bleiben vorrangig. Bei Konflikten gilt die konkretere Schutzregel.
Abgrenzung: Dieses Dokument praezisiert vorhandene Grundsaetze; es ersetzt
weder docs/V91-AUDIT-KERN.md noch MAX-BEST-GELUEBNIS/PROTOCOL oder Messpfade.

## 1. Zweck und Grundsatz

Dieses Protokoll macht sichtbar, welchen Erkenntnisstatus eine Aussage hat,
worauf er beruht und wann er erneut geprueft werden muss.

Kernsatz:
EIN ZEICHEN IST KEIN BELEG. EIN BELEG IST KEINE UNBEGRENZTE WAHRHEIT.
EINE PRUEFUNG IST KEINE VERBESSERUNG. EINE VERBESSERUNG BRAUCHT
EINEN VORHER-NACHHER-NACHWEIS. JEDE ERKENNTNIS BLEIBT REVIDIERBAR.

Das Protokoll ist eine Dokumentations- und Review-Regel. Es fuehrt keine
Messung aus, bestaetigt keine Quelle automatisch, erzeugt keine Identitaet
und verleiht keine Berechtigung.

## 2. Erkenntnisstatus (kompakte V91-Marker)

Die Marker sind neu entwickelte V91-Kennzeichnungen. Sie sind keine
historischen Runen, Hieroglyphen oder uebernommenen Kulturzeichen.
Grafische Glyphen koennen in Oberflaechen zusaetzlich angezeigt werden;
die ausgeschriebenen Kennungen sind die maschinen- und textstabile Form.

- ? CLAIM: Aussage oder Annahme; noch nicht nachgewiesen.
- OBS: Beobachtung; Wahrnehmung mit Beobachter, Ort/Kontext und Zeitpunkt.
- MEAS: Messung; Wert mit Einheit, Quelle, Verfahren, Zeitfenster und
  Qualitaets-/Unsicherheitsangabe.
- VER: verifiziert; geeignete Belege stuetzen die eng umrissene Aussage.
- IMP: Verbesserung umgesetzt; konkrete Aenderung ist dokumentiert.
- REMEAS: Wirkung nachgemessen; Vergleich mit vorher festgelegter Baseline
  und Erfolgskriterien liegt vor.
- UNK: unbekannt oder nicht ausreichend bestimmt.
- ! DISPUTED: Widerspruch, Anomalie oder Gegenbeleg liegt vor.
- REV: Revision; Aussage, Methode oder Bewertung wurde geprueft und
  gegebenenfalls nachvollziehbar korrigiert.

Die Status sind keine Rangliste und keine automatische Einbahnstrasse.
UNK kann jederzeit gelten. Ein Gegenbeleg kann VER auf DISPUTED setzen.
Eine neue Messung kann eine fruehere Messung einschraenken oder entkraeften.
REV ist quer zu allen Status jederzeit zulaessig und bei relevantem
Gegenbeleg, Methodenfehler oder geaendertem Kontext erforderlich.

## 3. Pflichtangaben zum Nachweis

Jeder relevante OBS-, MEAS-, VER-, IMP- oder REMEAS-Eintrag enthaelt,
soweit fuer den Fall anwendbar:

1. Aussage/Prueffrage und klar begrenzten Geltungsbereich.
2. Quelle bzw. Datenherkunft und unveraenderten Verweis auf das Artefakt.
3. Zeitpunkt und Zeitbasis; bei Zeitfenstern Anfang und Ende.
4. Methode, Version, Umgebung und relevante Bedingungen.
5. Einheit, Rohwert und Qualitaets-/Unsicherheitsangabe bei Messungen.
6. Verantwortliche Person oder benanntes Verfahren; Pruefer getrennt
   vom Ersteller, wenn Risiko oder Unabhaengigkeit es erfordern.
7. Ergebnis, Grenzen, Gegenbelege und offene Punkte.
8. Wiederholbarkeit oder Begruendung, warum sie nicht moeglich ist.

Nicht anwendbare Felder werden als N/A mit Begruendung markiert.
Fehlende Pflichtangaben werden nicht still ergaenzt: Status bleibt UNK
oder NICHT_GEPRUEFT. Schaetzungen bleiben als Schaetzung gekennzeichnet.

## 4. Verifikation und Reichweite

VER bestaetigt nur die konkrete Aussage unter den dokumentierten
Bedingungen. Ein Test bestaetigt nur das getestete Verhalten, fuer den
getesteten Commit, die Umgebung und den Testumfang.

- Quelle vorhanden != Quelle authentisch.
- Hash stimmt != Inhalt wahr.
- Test bestanden != System sicher oder produktiv.
- CI gruen != Realbetrieb.
- Beobachtet != gemessen.
- Gemessen != unabhaengig verifiziert.
- Verifiziert != universell oder dauerhaft wahr.

Bei hohem Risiko ist eine unabhaengige Gegenpruefung vorzusehen.
Ein Modell, Autor oder Pruefer darf den eigenen CLAIM nicht allein durch
Selbstdeklaration zu VER machen. UNKNOWN != PASS bleibt uneingeschraenkt.

## 5. Verbesserung und Wirkung

IMP dokumentiert, was geaendert wurde, warum, von wem, wann, mit welcher
Autorisierung und mit welchem Rueckfall-/Wiederherstellungsplan.
IMP allein behauptet noch keine positive Wirkung.

REMEAS benoetigt:
- eine vor der Aenderung festgelegte Baseline,
- vergleichbare Bedingungen und ein definiertes Zeitfenster,
- Messmethode, Einheit, Unsicherheit und Rohdatenverweis,
- vorher festgelegte Erfolgskriterien,
- Nebenwirkungen, Regressionen und nicht gemessene Aspekte.

Fehlt ein fairer Vergleich, lautet der Befund NICHT NACHGEWIESEN.
Eine Verbesserung in einem Bereich darf keine Verschlechterung in einem
anderen relevanten Bereich verdecken. Sicherheit, Menschenwuerde und
Grundversorgung duerfen nicht gegen einen blossen Effizienzgewinn
aufgerechnet werden.

## 6. Stein der Revision

Der Stein der Revision ist das Leitbild fuer die jederzeitige Korrigierbarkeit.
Sein Leitsatz lautet: ICH KOENNTE MICH IRREN.

Revision ist kein letzter Schritt nach REMEAS, sondern eine dauerhafte
Pruefpflicht fuer Behauptungen, Beobachtungen, Messmethoden, Kriterien,
Verifikationen, Entscheidungen und dieses Protokoll selbst.

Bei einer Revision werden mindestens festgehalten:
- bisherige Aussage und bisheriger Status,
- Anlass und neuer Beleg bzw. erkannter Methodenfehler,
- neue Aussage/Bewertung und geaenderter Geltungsbereich,
- Auswirkungen auf fruehere Entscheidungen,
- Verantwortlichkeit, Zeitpunkt und erneute Pruefung.

Historische Eintraege werden nicht still ueberschrieben. Korrekturen
verweisen auf den ersetzten oder eingeschraenkten Eintrag; die Provenienz
bleibt sichtbar. Eine Revision ist kein Makel und kein automatischer
Schuldnachweis.

## 7. Arbeitszyklus und Verknuepfung

Der vorhandene MAX-BEST-/RealRun-Zyklus bleibt massgeblich
(docs/V91-MAX-BEST-REALRUN-ZYKLUSCHECK.md). Dieses Protokoll
konkretisiert darin den Erkenntnis- und Nachweisteil:

Entdecken -> Frage/CLAIM abgrenzen -> Beobachten/Messen -> Bewerten und
verifizieren -> Bewahren/Verbessern/Erforschen -> Wirkung nachweisen ->
erneut messen und pruefen -> bei Bedarf revidieren -> weiterlernen.

Der Ablauf ist eine Orientierung, keine starre Pipeline. Bei jeder
Stufe koennen UNK, DISPUTED oder REV auftreten. Massnahmenstein-Eintraege
bleiben mit Verantwortlichkeit, Prioritaet, Nachweis und Wirkung verbunden.

## 8. Historische und kulturelle Abgrenzung

Runeninschriften, Hieroglyphen, chinesische und japanische Schriftsysteme
sind unterschiedliche historische Systeme mit eigenen Laut-, Bedeutungs-,
Kontext- und Grammatikfunktionen. Dieses Protokoll nutzt nur die allgemeine
Idee kompakter, kontextklarer Kennzeichnungen. Es schreibt historischen
Zeichen keine V91-Bedeutung zu und leitet aus Mythen keine technischen
Tatsachen oder Governance-Befugnisse ab.

Yggdrasil, Mimir, Odins Auge, die Voelva und Nidhoegg duerfen als
Erzaehlbilder fuer Wissen, Erkenntnisgrenzen, Perspektive und das
Sichtbarwerden vernachlaessigter Schwaechen dienen. MYTHOS != SPEZIFIKATION;
ANALOGIE != BEWEIS; ERZAEHLUNG != VERTRAG.

## 9. Grenzen und Einordnung

Dieses Dokument ist ein V91-Ergaenzungsprotokoll. Es ist kein neues
Grundgesetz, keine Programmiersprache, kein Datenformat-Zwang und keine
automatische Steuerung. Bestehende Systeme muessen nicht allein wegen
dieses Textes umgebaut werden. Eine spaetere technische Umsetzung braucht
einen eigenen Entwurf, Bedrohungs-/Datenschutzpruefung, Schnittstellen,
Tests und ausdrueckliche Autorisierung.

Dokumentiert != implementiert. Implementiert != verifiziert.
Verifiziert != produktiv. Kein Marker ersetzt die zugrunde liegenden
Belege oder die menschliche Verantwortung.
