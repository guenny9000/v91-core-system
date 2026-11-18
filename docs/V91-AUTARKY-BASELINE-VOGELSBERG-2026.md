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

Sekundärauswertung von MaStR-Daten durch Ohmnify, Stand 18.11.2026 -
BELEGT als veröffentlichte Sekundärauswertung; ein unabhängig gezogener
Rohdatenexport der Bundesnetzagentur ist hier NICHT GEPRÜFT:

- Wind: 260 Anlagen, 556,7 MW - BELEGT (MaStR-Auswertung).
- Solar: 12.890 Anlagen, 263 MWp, davon 177,4 MWp Dachanlagen (80 % des
  Solarbestands auf Hausdächern), 82,8 MWp Freifläche (40 Solarparks),
  größte Anlage 34,7 MWp (Lauterbach) - BELEGT (MaStR-Auswertung).
  Zweitquelle nennt zum anderen Stichtag 27.10.2026: 12.766 Anlagen /
  260,4 MW, 2,57 kW pro Kopf, Rang 1 von 26 in Hessen, 65 % über
  Bundesschnitt ([Solarzubau]) - BELEGT als separate Sekundärangabe.
  Die Werte 263 MWp und 260,4 MW werden wegen Stichtag und Einheit
  nicht als identische Messgröße behandelt.
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

- Landwirtschaftliche Struktur - BELEGT als Registerauswertung des
  Hessischen Statistischen Landesamts für 2023 (Stichtag 1. Januar):
  1.108 aktive Betriebe, 64.276 ha landwirtschaftlich genutzte Fläche;
  darunter 245 Betriebe mit ökologischem Landbau und 16.099 ha Öko-LF.
  Das entspricht rechnerisch rund 22,1 % der erfassten Betriebe und
  25,0 % der erfassten LF. Die Registerauswertung hat Erfassungsgrenzen
  (u. a. 5 ha LF oder bestimmte Mindest-Viehbestände); sie ist daher
  keine Vollzählung aller kleinsten Erzeuger.
- Ausgewählte Ackerflächen 2023: Winterweizen 8.648 ha, Wintergerste
  4.683 ha, Winterraps 3.086 ha, Triticale 2.058 ha, Kartoffeln 25 ha.
  Das sind Flächenangaben, keine Erntemengen oder lokal verfügbare
  Lebensmittelmengen. Quelle: Hessisches Statistisches Landesamt,
  C I 11 - j/23, Tabelle 1 und Kulturarten-Tabelle.
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
  und Quellen - BELEGT als Mittelhessen-Wert, ausdrücklich KEINE
  Autarkiequote des Vogelsbergkreises ([RP Gießen]).
- Wasserbilanz Vogelsbergkreis 2024 - BELEGT (RP Gießen, Kreisübersicht):
  101.244 Einwohner als damalige Berechnungsbasis; Eigenförderung
  6.046.951 m³; Netzeinspeisung zur Eigenversorgung 6.080.532 m³;
  verkaufte Menge gesamt 4.800.715 m³ (davon Haushalte/Kleingewerbe
  4.328.431 m³ und Gewerbe/Industrie 472.284 m³); sonstiger
  Wasserverbrauch 1.279.817 m³; davon ausgewiesene Rohrnetzverluste
  686.331 m³; spezifischer Rohrnetzverlust 0,056 m³/(km*h);
  täglicher Verbrauch ohne Gewerbe/Industrie 117 l/(EW*Tag).
  Die Eigenförderung ist nicht mit lokaler Versorgungssicherheit oder
  Autarkie gleichzusetzen: Fremdbezüge, Fremdabgaben, Verbundsysteme,
  Wasserqualität, saisonale Verfügbarkeit und ökologische Grenzen sind
  zusätzlich zu bewerten. Die Wasserbilanz weist außerdem auf mögliche
  Schätzwerte und Erfassungsunterschiede bei einzelnen Positionen hin.
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

1. Wasserdaten auf kommunaler Ebene auswerten und mit Wasserrechten,
   Qualitätsdaten, Grundwasserständen und saisonaler Verfügbarkeit
   verknüpfen; Kreisaggregat allein reicht nicht für lokale Resilienz.
2. Agrarstruktur 2023 ist jetzt als Struktur-Baseline belegt. Nächster
   Schritt: Erntemengen, Verarbeitung, Lagerung, Direktvermarktung und
   regionale Nachfrage erfassen; keine Selbstversorgungsquote ohne
   vergleichbare Mengen- und Bedarfsdaten.
3. Jahresstromerzeugung/-verbrauch (Netzbetreiber/Kreis) anfordern ->
   Autarkie-Definition nachziehen, DANN Prozentwert ausgeben.
4. Operator-Vor-Ort-Messungen (Alsfeld) über v91_cli record in den
   Messstore (PR #147) -> Herkunft und Messquelle getrennt verifizieren.

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
- [Agrarstatistik Hessen 2023]: Hessisches Statistisches Landesamt,
  Landwirtschaftlich genutzte Fläche mit Viehhaltung und Haltungsplätze
  in Hessen 2023 (C I 11 - j/23), Tabellen 1 und Kulturarten -
  https://statistik.hessen.de/sites/statistik.hessen.de/files/2024-03/CI11_j23.pdf
- [Agraratlas]: Atlas Agrarstatistik -
  https://agraratlas.statistikportal.de/
- [GovData]: Landwirtschaftliche Betriebe und LF nach Größenklassen,
  Kreis-Tiefe -
  https://www.govdata.de/suche/daten/landwirtschaftliche-betriebe-und-deren-landwirtschaftlichgenutzte-flache-lf-nach-grossenklassen-1
- [OZ-Artikel]: Oberhessische Zeitung, Ertragsrückgangsmeldung -
  https://www.oberhessische-zeitung.de/vogelsbergkreis/landwirte-ernten-zehn-prozent-weniger-und-koennen-kaum-noch-ueberleben-94454746.html
