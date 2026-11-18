# V91 Autarkie-Ausgangsmessung Vogelsbergkreis (Baseline 2026-11)

Status: AUSGANGSMESSUNG (Baseline) | Prüfstandard: MAX-BEST | Datum: 2026-11-18

Dieses Dokument erzeugt keine Zustandssprüche (STATUS:ACTIVE, FQ:ZERO,
DRIFT, VALID und ähnliche SEQ-Attribute sind keine Belege). Jede Zahl
trägt ihren eigenen Status nach dem MAX-BEST-Prüfstandard. Das Dokument
wird bei jedem gemergten Mess-PR aktualisiert und ersetzt keine Messung
durch Text (CLAIM != EVIDENCE).

## 1. MAX-BEST-Prüfstandard (verbindlich für dieses Dokument)

- BELEGT = nachvollziehbare Nachweise vorhanden (Quelle + Stand genannt).
- NICHT GEPRÜFT = noch keine ausreichende Prüfung.
- NICHT VERFÜGBAR = notwendige Daten oder Zugriffe fehlen.
- FEHLGESCHLAGEN = Prüfung hat einen Fehler nachgewiesen.

Kein unbekannter Zustand wird automatisch als sicher bewertet
(UNKNOWN != PASS). Umsetzung, Messung und Verifikation bleiben getrennt:
IMPLEMENTED != MEASURED, MEASURED != VERIFIED. Ein Prozentwert wird erst
nach definierter Rechenregel und belegten Rohdaten ausgegeben (FQ: Erst
die Definition, dann der Wert; "73 % Autarkie" ohne nachvollziehbare
Berechnung wird NICHT übernommen).

## 2. Energieautarkie (Säule 1)

Referenzbevölkerung: 100.723 Einwohner (31.12.2025, [Wikipedia/HLZ]),
Fläche 1.458,91 km² - BELEGT.

Alle Anlagenzahlen stammen aus dem Marktstammdatenregister (MaStR) der
Bundesnetzagentur, Auswertung Stand 18.11.2026 ([Ohmnify]) - BELEGT:

- Wind: 260 Anlagen, 556,7 MW - BELEGT (MaStR-Auswertung).
- Solar: 12.890 Anlagen, 263 MWp, davon 177,4 MWp Dachanlagen (80 % des
  Solarbestands auf Hausdächern), 82,8 MWp Freifläche (40 Solarparks),
  größte Anlage 34,7 MWp (Lauterbach) - BELEGT (MaStR-Auswertung).
  Zweitquelle bestätigt den Bestand: 12.766 Anlagen / 260,4 MW, 2,57 kW
  pro Kopf, Rang 1 von 26 in Hessen, 65 % über Bundesschnitt, Stand
  27.10.2026 ([Solarzubau]) - BELEGT.
- Speicher: 5.327 Batteriespeicher, 33,1 MW - BELEGT (MaStR-Auswertung).
- Biomasse: 30 Anlagen, 16,2 MW; Wasser: 34 Anlagen, 1,2 MW (älteste
  Wasseranlage seit 1902 in Betrieb) - BELEGT (MaStR-Auswertung).
- Gesamt: 18.636 Energieanlagen, 874,2 MW installiert, rund 8,7 kW pro
  Einwohner - BELEGT (MaStR-Auswertung).
- Zubau/Planung: +662 neue Anlagen in 90 Tagen (5,8 MW); 156 Anlagen in
  Planung (237,1 MW) - BELEGT (MaStR-Auswertung; PLANUNG != GENEHMIGT).
- Ladeinfrastruktur: 152 Ladestandorte, 263 Ladepunkte, 23,3 MW, davon
  78 HPC-Standorte (>= 150 kW) - BELEGT (MaStR-Auswertung).
- Bürgerenergie: Energiegenossenschaft Vogelsberg e.G., gegründet
  August 2011, über 2.000 Mitglieder, Dividende 2,5 %, Wind- und
  PV-mit-Speicher-Projekte 2026 realisiert ([EGV]) - BELEGT.

NICHT GEPRÜFT (bewusst kein Prozentwert ausgegeben):
- Tatsächlicher Jahresstromverbrauch des Kreises (Haushalte + Gewerbe)
  und die Gegenüberstellung zur regenerativen Jahreserzeugung. Die
  Erzeugung muss aus gemessenen Einspeise- und Verbrauchsdaten errechnet
  werden, nicht aus installierter Leistung.
- Netzeinspeisung/Autarkiegrad: NICHT VERFÜGBAR ohne Messdaten des
  Netzbetreibers (keine öffentliche Auswertung gefunden).
- Wärmeversorgung (Heizenergie, Energiebedarf Gebäude): NICHT
  VERFÜGBAR (kommunale Wärmedaten fehlen; siehe Zählblatt Abschnitt 7).

## 3. Nahrungsautarkie (Säule 2)

- Landwirtschaftliche Struktur im Kreis - BELEGT (Landwirtschaftszahlung
  2020, Kreisergebnisse, [HSL-LZ2020], Stichtag 01.03.2020,
  Regional-Summenprobe in Reg.-Bez. Giessen konsistent:
  562+539+546+1.106+1.079 = 3.832):
  - Landwirtschaftliche Betriebe: 1.079.
  - Landwirtschaftlich genutzte Flaeche (LF): 64.264 ha, davon
    Ackerland 31.195 ha, Dauergruenland 33.019 ha (Kontrolle:
    31.195 + 33.019 = 64.214 gegenueber LF 64.264, Rest sonstige
    Flaechen; identische LF/Ackerland-Werte in zwei unabhaengig
    extrahierten Tabellen des Berichts).
  - LF-Anteil an der Kreisflaeche = 64.264 ha / 145.891 ha =
    44,0 % (Rechenregel angegeben: LF / Gesamtflaeche).
  - Unsichere Spaltendeutungen des Berichts (z. B. Zuordnung
    der Spalten 2 und 5 der Uebersichtstabelle) werden NICHT
    als Fakt veroeffentlicht (UNKNOWN != PASS).
- Pressebefund (regionaler Kontext, keine Messung): Ertragsrückgang
  rund 10 % bei Landwirten im Kreis gemeldet ([OZ-Artikel]) - BELEGT
  als Meldung, NICHT als Messwert; Ursachenkontext siehe Säule 3.
- Versorgungsgrad mit regionalen Lebensmitteln, Lagerfähigkeit,
  samenfeste Sorten, Erzeugernetzwerke: NICHT VERFÜGBAR.
- KEIN "Nenner 1000 = Testdatensatz"-Fehlschluss: ohne belegte
  Mengendaten bleibt dieser Abschnitt ehrlich leer. Stichtagsdaten
  kommen aus dem Operator-Messweg (v91_cli record, PR #147; siehe
  V91-MEASUREMENT-CORE.md), nicht aus Behauptungen.

## 4. Wasser und Natur (Säule 3)

- Trinkwasserherkunft Mittelhessen: rund 60 % aus kommunalen Brunnen
  und Quellen - BELEGT ([RP Gießen]-Pressemitteilung).
- Wasserbilanz Mittelhessen 2024 ([RP Gießen], PDF, Stand 06.10.2025):
  Detailwerte für den Vogelsbergkreis - BELEGT:
  - Einwohner (Stichtag 30.09.2024, Zensus 2022 korrigiert): 101.244.
  - Eigenförderung: 6.046.951 m3/a; Netzeinspeisung zur
    Eigenversorgung (EF+FB-FA): 6.080.532 m3/a. Regionale
    Eigenförderungsdeckung = EF / Netzeinspeisung = 99,4 %
    (Rechenregel angegeben: 6.046.951 / 6.080.532 = 0,9945;
    FQ: Definition zuerst, dann der Wert).
  - Verkaufte Menge gesamt: 4.800.715 m3/a, davon Haushalte/
    Kleingewerbe 4.328.431 m3/a, Gewerbe/Industrie 472.284 m3/a.
  - Sonstiger Wasserverbrauch gesamt 1.279.817 m3/a, davon
    Rohrnetzverluste 686.331 m3/a; spezifischer Rohrnetzverlust
    0,056 m3/(km*h) (zweitniedrigster Wert im Regierungsbezirk
    Gießen nach dem LK Limburg-Weilburg mit 0,052).
  - Täglicher Verbrauch ohne Gewerbe/Industrie: 117 l/(EW*Tag).
  - Vergleich Regierungsbezirk: 1.040.266 EW, EF 36.021.740 m3/a,
    114 l/(EW*Tag), 0,068 m3/(km*h).
  - HINWEIS (vom RP Gießen selbst genannt): Kleingewerbe und
    öffentliche Einrichtungen sind nicht separat erfasst und
    erhöhen den Pro-Kopf-Wert rechnerisch; Quellüberläufe und
    Eigenbedarf sind teils nicht angegeben und erhöhen die
    ausgewiesenen Rohrnetzverluste rechnerisch. Deshalb wird hier
    KEINE Versorgungsautarkie in Prozent daraus abgeleitet,
    sondern nur die oben definierte Eigenförderungsdeckung.
- Wasserqualität/Messstellen im Kreis, Quellenschutzgebiete,
  Bodenfruchtbarkeit, Artenvielfalt: NICHT VERFÜGBAR (keine belegten
  Kreis-Zahlen; keine unbelegte Zahlengenerierung).
- Aktion Trinkwasserschutz des RP Gießen läuft - BELEGT als Meldung;
  Wirkung im Kreis: NICHT GEPRÜFT.

## 5. Digitale Autarkie (Säule 4)

- V91-Repo-Stand (18.11.2026): Ed25519-signierte Peer-Heartbeats
  (controller/signed_heartbeat.py, PR #149), Heartbeat-Intake-Brücke
  in das Kooperationsregister (controller/heartbeat_intake.py, PR
  #150), beide CI 2/2 am exakten Head (Merge-Commits ca95a830,
  2e32cd73) - BELEGT.
- Zwei-Instanzen-Loopback maschinell geprüft - BELEGT (13 Tests in
  tests/test_heartbeat_intake.py, PR #150). Echter Mehrknoten-Fern-
  betrieb: NICHT GEPRÜFT (Issue #103, Operator Sebastian).
- Kryptografie reproduzierbar in CI (echtes cryptography-Paket im
  CI-Zweig, HMAC-Stubs nie committet) - BELEGT.
- Keine zentrale Abhängigkeit erzwungen: lokale Vertrauensregistrierung
  pro Instanz (controller/peer_directory.py), kein globales SSO -
  BELEGT als Design- und Testbefund.

## 6. SEQ:9195 / "V91-INT-2.5" (externer Beitrag): Befund

Fiction-Check: SEQ:9195 und V91-INT-2.5 haben 0 Treffer im Repository
und in öffentlichen Quellen. Die Statusattribute des Beitrags
(STATUS:ACTIVE, FQ:ZERO, DRIFT:0/INF, VALID:1) sind Behauptungen ohne
Evidenz und werden nicht übernommen. Der mitgelieferte Beispiel-Hash
e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 ist
der SHA-256 des LEEREN Strings - passend zum Charakter der Probe,
aber kein Kausalitäts- oder Echtheitsbeleg (HASH != SIGNATUR,
CLAIM != EVIDENCE).

Nicht übernommen, weil bereits besser auf main vorhanden
(NO_DUPLICATE_SYSTEMS):
- Keyloser SHA-256-"Heartbeat": ein Hash ohne Schlüssel beweist keine
  Herkunft. V91 signiert Ed25519 über kanonische Byteströme
  (signed_heartbeat.py, PR #149), inklusive TTL, geordneter
  Nonce-Registrierung und Trust-Registry mit Revocation - alles
  bereits gebaut und CI-geprüft.
- UDP/HTTP-localhost-Transport: Duplikatgefahr gegenüber
  federation_sender/federation_receiver und peer_sync. Statt einer
  Zweitstruktur wird die bestehende Transportinfrastruktur genutzt.
- Das mitgelieferte Python-Snippet enthält `_name_`/`_main_` statt
  der Magic Methods (__name__/__main__) und läuft so nicht
  (SCRIPTED != INSTALLED); es wird nicht lauffähig übernommen.

## 7. Zählblatt für die nächsten Mess-PRs (Reihenfolge empfohlen)

1. Wasserbilanz 2024 (RP Gießen, PDF) auswerten -> Kreis-Zahlen belegen:
   ERLEDIGT BEI DIESEM UPDATE (Säule 3: Eigenförderungsdeckung 99,4 %,
   Rohrnetzverluste, Pro-Kopf-Verbrauch; Rechenregel angegeben).
2. Agrarstruktur-Tabelle Kreis öffnen -> Säule 2 belegen:
   ERLEDIGT BEI DIESEM UPDATE (Betriebe 1.079, LF 64.264 ha,
   Ackerland/Dauergruenland; aus der Landwirtschaftszahlung 2020
   Kreisergebnissen des HSL; unsichere Spaltendeutungen NICHT
   uebernommen).
3. Jahresstromerzeugung/-verbrauch (Netzbetreiber/Kreis) anfordern ->
   Autarkie-Definition nachziehen, DANN Prozentwert ausgeben.
4. Operator-Vor-Ort-Messungen (Alsfeld) über v91_cli record in den
   Messstore (PR #147) -> von IMPORTED nach VERIFIED_ORIGIN über die
   signierte Heartbeat-Kette (PR #149/#150).

Jede offene Zeile verschwindet erst, wenn ihr Status BELEGT oder
FEHLGESCHLAGEN ist. Keine Zahl wird veröffentlicht, die nicht mindestens
Namen, Stand und Quellenpfad trägt.

## 8. Quellen

- [Wikipedia/HLZ]: Vogelsbergkreis, Einwohner 31.12.2025 -
  https://de.wikipedia.org/wiki/Vogelsbergkreis
- [Ohmnify]: Energieanlagen Vogelsbergkreis, MaStR-Auswertung Stand
  18.11.2026 - https://www.ohmnify.io/hessen/landkreis-vogelsbergkreis
- [Solarzubau]: Photovoltaik Landkreis Vogelsbergkreis, MaStR Stand
  27.10.2026 - https://solarzubau.de/photovoltaik-landkreis-vogelsbergkreis/
- [EGV]: Energiegenossenschaft Vogelsberg e.G. -
  https://www.energie-vb.com/
- [RP Gießen]: Pressemitteilung Trinkwasserherkunft (ca. 60 %) -
  https://rp-giessen.hessen.de/presse/in-mittelhessen-stammen-circa-60-prozent-des-trinkwassers-aus-kommunalen-brunnen-und-quellen
  und Wasserbilanz Mittelhessen 2024 (PDF):
  https://rp-giessen.hessen.de/sites/rp-giessen.hessen.de/files/2025-10/auswertung_wasserbilanz_2024_bf.pdf
- [Agraratlas]: Atlas Agrarstatistik -
  https://agraratlas.statistikportal.de/
- [HSL-LZ2020]: Landwirtschaftszahlung 2020, Kreisergebnisse
  (Kennziffer C IV 10-1b/20, Hessisches Statistische Landesamt,
  Juni 2021) -
  https://statistik.hessen.de/sites/statistik.hessen.de/files/2022-06/CIV10_1b_20.pdf
- [GovData]: Landwirtschaftliche Betriebe und LF nach Größenklassen,
  Kreis-Tiefe -
  https://www.govdata.de/suche/daten/landwirtschaftliche-betriebe-und-deren-landwirtschaftlichgenutzte-flache-lf-nach-grossenklassen-1
- [OZ-Artikel]: Oberhessische Zeitung, Ertragsrückgangsmeldung -
  https://www.oberhessische-zeitung.de/vogelsbergkreis/landwirte-ernten-zehn-prozent-weniger-und-koennen-kaum-noch-ueberleben-94454746.html
