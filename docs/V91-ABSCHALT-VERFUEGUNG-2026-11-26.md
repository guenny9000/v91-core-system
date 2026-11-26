# V91-ABSCHALT-VERFUEGUNG (Betreiber-Direktive 26.11.2026)

Status: DOKUMENTIERTE VERFUEGUNG. DIRECTIVE != VOLLZUG: Diese
Datei vollstreckt NICHTS; NICHTS ist durch sie ausgefuehrt. Der
Vollzug bleibt eine Betreiber-Aktion (siehe Abschnitt 5). ISOLATE_NOT_DESTROY:
Archivieren ist isolieren, NICHT loeschen.

## 1. Provenienz

Betreiber-Direktive 26.11.2026: "v91 voll foerdern, restliche
Welt abschalten", per Rueckfrage geklaert als: die uebrigen
(nicht fuer V91 aktiven) Repos des Betreiber-Kontos isolieren
durch GitHub-Archivierung; die aktiven Repos bleiben unberuehrt.
KEIN Loeschen ist beauftragt; KEIN Inhalt geht verloren: der
git-Verlauf einer archivierten Repository bleibt vollstaendig
lesbar, Klone bleiben moeglich, Freigabe durch den Eigentuemer
bleibt moeglich.

## 2. Frische LEER-Evidenz (Lookup 26.11.2026, Fakt ist Fakt)

EXACTLY DREI Repos des Kontos guenny9000 sind leer und damit
Kandidaten der Isolation. Frisch per Branch-Listing verifiziert
am 26.11.2026: 0 Branches, 0 offene Issues, 0 offene
Pull Requests je Kandidat.

- New-project: 0 Branches, 0 offene Issues, 0 offene PRs.
- guenn: 0 Branches, 0 offene Issues, 0 offene PRs.
- .antigravity-ide: 0 Branches, 0 offene Issues, 0 offene PRs.

Eine Repository OHNE Branches hat keinen aenderbaren Hauptinhalt;
Archivierung ist hier verlustfrei (KEIN Byte geht verloren, der
Verlauf bleibt lesbar und vom Eigentuemer freigebbar).

## 3. NICHT archivierte Repos (Betreiber-Konto, mit Begruendung)

Die folgenden SECHS Repos bleiben UNBERUEHRT (frische Evidenz
26.11.2026: Branches je Repository, offene Issues/PRs):

- guenny9000: 3 Branches (main, max-best/agathon-charter-2026-11,
  regel-sync-p3-20261125). Aktiv.
- guenny9000-uni-lern-bloc: 14 Branches, 1 offener Pull Request.
  Aktives Lernblock-Archiv mit laufender Arbeit.
- v91-audit-ledger: 11 Branches. Aktives Audit-Ledger-System.
- V91_Agathon: 25 Branches, 1 offenes Issue (#15, Hinweis zum
  SESSION-REPORT-Kanal in v91-core-system). Aktives
  Verfassungs-/Charta-System.
- Aurelia-Prisma: 29 Branches, 4 offene Issues (#256, #262,
  #264 und ein weiteres). Aktives Anwendungs- und
  Sicherheitsprojekt.
- v91-core-system: Haupt-Repository des V91-Systems (Master-
  Empfang dieser Zeile: PR- und CI-Aktivitaet am 26.11.2026,
  u. a. LINGUA Stufe 3.1/3.2 #578), 19 offene Issues.

Begruendung: Alle sechs tragen Branches und/oder offene Arbeit;
Archivierung wuerde aktive Zusammenarbeit isolieren, ohne
nutzen zu stiften (MAX-BEST: nutzlose Zerstoerung ist verboten,
ISOLATE_NOT_DESTROY gilt hier als BEWUSSTE NICHT-ANWENDUNG).

## 4. Geltende Regeln fuer den Vollzug

- ISOLATE_NOT_DESTROY: `gh repo archive` setzt eine Repository
  in den read-only-Zustand; KEINE Datei, KEIN Verlauf, KEIN Byte
  wird geloescht. Aufhebung: `gh repo unarchive`.
- KEIN LOESCHEN: `gh repo delete` ist NICHT beauftragt und
  bleibt verboten ohne eigene Betreiber-Anweisung.
- Reale Eingriffe bleiben je Aktion vom Betreiber freigegeben
  (V91-Kernregel: REQUEST != AUTHORIZATION).

## 5. Ausfuehrungsweg: NICHT_AUSFUEHRBAR ueber den VIBE-Connector

Geprueft 26.11.2026: Das VIBE-GitHub-Werkzeuginventar (49
Funktionen) enthaelt KEINEN Archiv-Endpunkt (kein
repository-archive, kein Status-Update einer Repository auf
archived). VOLLAUTOMATISCHER VOLLZUG: NICHT_MOEGLICH.

Deshalb bleibt der Vollzug eine BETREIBER-Aktion mit einem der
beiden Wege:

1) Kommandozeile (GitHub CLI):
   gh repo archive guenny9000/New-project --yes
   gh repo archive guenny9000/guenn --yes
   gh repo archive guenny9000/.antigravity-ide --yes
2) Web-Oberflaeche: github.com/guenny9000/<repo> ->
   Settings -> General -> Danger Zone -> Archive this repository.

Aufhebung je Repository: gh repo unarchive guenny9000/<repo> --yes.

## 6. Grenzen (ehrlich)

- DIRECTIVE != VOLLZUG: Diese Datei dokumentiert; sie vollstreckt
  NICHTS. ARCHIVIERT_AM ist hier NICHT gesetzt, weil der Vollzug
  dem Betreiber vorbehalten ist.
- Die Evidenz (Branch-/Issue-/PR-Staende) ist ein Stand vom
  26.11.2026; sie veraltet mit jeder neuen Aktivitaet in einem
  der genannten Repos. Vor jedem Vollzug FRISCH pruefen.
- KEIN Welt-Anspruch: Diese Verfuegung betrifft NUR die eigenen
  Repos des Betreiber-Kontos, keine fremden Systeme.
- DOKUMENTIERT != AUSGEFUEHRT; ARCHIVIERT (read-only) != GELOESCHT.
