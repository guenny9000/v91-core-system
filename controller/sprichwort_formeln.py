"""
V91-SYSTEM-HEADER (AGATHON-SEALED v2.4)
---------------------------------------------------------------------
STATUS: ACTIVE | VERIFICATION: REQUIRED (CLAIM != EVIDENCE)
AXIOM: Schöpfung dient dem Erhalt, der Regeneration und der Zukunft.
---------------------------------------------------------------------
Sprichwort-/Redewendung-Formel-Registry (VIBE-LXXV, Betreiber-Auftrag
22.11.2026 abends: THEOLOGIE/UEBERLIEFERUNG als formalisierbare Reihe).

Ueberlieferte Texte (Bibel, Antike, Sprichwoerter, Maerchen, Mythen,
Psalm-Prinzipien) enthalten strukturelle Einsichten, die sich als
mathematische Formeln notieren lassen (Betreiber-Beispiele:
"Wer andern eine Grube graebt, faellt selbst hinein" = reziproker
Schadensoperator eines wiederholten Spiels; "Sorgen verschiebe ich
auf morgen" = Verzugs-/Diskontstruktur). Diese Registry macht solche
Strukturen deterministisch importierbar: Andere Module, Modelle und
Agenten koennen sie lesen, pruefen und lernen (LERNEN > DOGMA).
41 Eintraege: 11 Vorbilder dieser Reihe plus die 30 vom Betreiber
am 22.11.2026 spaet gelieferten Redewendungen (vollstaendig).

Ehrliche Grenzen dieses Moduls:
- ANALOGIE != BEWEIS: Eine Formel beschreibt die STRUKTUR der
  Ueberlieferung, nicht ihre Wahrheit (FORMEL != FAKT).
- SPRICHWORT != GESETZ: Ueberlieferte Einsichten sind heuristische
  Muster mit Gueltigkeitsbedingungen, keine Naturgesetze; jede
  Zeile nennt ihre Grenzen.
- QUELLE != VERIFIZIERT: Herkunftsangaben folgen der Ueberlieferungs-
  tradition; sie sind keine historische Pruefung.
- THEOLOGIE != ENTSCHEIDUNG: Dieses Modul bemisst keine Wahrheit
  und entscheidet nichts.
- NO_DUPLICATE_SYSTEMS: Fail-closed-Error und Struktur-Gate-Pattern
  (Pflichtfelder, doppelte IDs, KEINE_STUMME_KORREKTUR) folgen dem
  REUSE aus controller.kreislauf_status (PR #363); die Registry
  erzeugt keine truth-Dateien, Reports sind FIFO-Ausgabe.
- SCRIPTED != INSTALLED: kein Daemon, kein Netz, keine Credentials,
  reine Standardbibliothek.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from controller.kreislauf_status import KreislaufInputError

FELDER = ("id", "redewendung", "formel", "erklaerung", "quelle",
          "bereich", "grenzen")
BEREICHE = ("BIBEL", "ANTIKE", "SPRICHWORT", "MAERCHEN", "MYTHOS",
            "PSALM")

VERDICT_REGISTRIERT = "REGISTRIERT"
VERDICT_ABGELEHNT = "ABGELEHNT"

EXIT_REGISTRIERT, EXIT_ABGELEHNT, EXIT_INPUT_ERROR = 0, 1, 3

GRENZEN = ("ANALOGIE != BEWEIS; SPRICHWORT != GESETZ; FORMEL != FAKT;"
           " QUELLE != VERIFIZIERT; THEOLOGIE != ENTSCHEIDUNG;"
           " SCRIPTED != INSTALLED")


def _non_empty(wert: Any) -> bool:
    return isinstance(wert, str) and wert.strip() != ""


def _keine_json_konstante(name: str) -> Any:
    """Bare NaN/Infinity im JSON sind keine Formeln (NaN != MESSWERT)."""
    raise KreislaufInputError("JSON-konstante %s unzulaessig" % name)


def _ascii_ok(text: str) -> bool:
    """Registry-Inhalt ist ASCII-pure (TRANSCRIPTION != VERLUST)."""
    return all(32 <= ord(z) <= 126 or z == "\n" for z in text)


# --- Die Registry: strukturelle Einsichten aus Ueberlieferungen ------
# Jede Zeile: id, redewendung (ueberliefert), formel (mathematische
# Struktur in ASCII-Notation), erklaerung, quelle, bereich, grenzen.

DEFAULT_FORMELN: List[Dict[str, str]] = [
    {   # Betreiber-Beispiel 22.11.2026
        "id": "grube-reziprok",
        "redewendung":
            "Wer andern eine Grube graebt, faellt selbst hinein",
        "formel": (
            "wiederholtes Spiel: schaedigt a den b in Runde t, dann"
            " ist die Rueckschlagsrate r(a) monoton steigend in t;"
            " Erwartungsnutzen E[S(a, T)] <= E[S(a, 0)] fuer grosses"
            " T"),
        "erklaerung": (
            "Ausbeutung zahlt sich im wiederholten Spiel nicht aus,"
            " weil Gegenparteien reagieren (Reziprozitaet;"
            " TIT-FOR-TAT schlaegt Ausbeutung langfristig)"),
        "quelle":
            "Sprueche 26,27; Sirach 27,26; deutsches Sprichwort",
        "bereich": "BIBEL",
        "grenzen": (
            "gilt nur bei wiederholter Interaktion und"
            " Reaktionsfaehigkeit der Gegenpartei; im anonymen"
            " Einmalspiel ohne Reputationsfluss schwaecht der"
            " Effekt"),
    },
    {   # Betreiber-Beispiel 22.11.2026
        "id": "verzug-diskont",
        "redewendung":
            "Sorgen, die man auf morgen schiebt, wachsen",
        "formel": (
            "K_gesamt(t) = K_aufwand + K_verzug(t) mit"
            " K_verzug(t) = mu * (t - t_0) fuer t > t_0 und"
            " mu >= 0 monoton wachsend; Aufschub erzeugt Zins,"
            " keinen Erlass"),
        "erklaerung": (
            "Aufgeschobene Problemsuche bleibt liegen und"
            " verteuert sich; V91-Analogon: der Morgen-Audit"
            " existiert, weil Verzug Kosten erzeugt"),
        "quelle": "deutsches Sprichwort; Volksmund",
        "bereich": "SPRICHWORT",
        "grenzen": (
            "mu darf 0 sein, wenn die Sorge wirklich entfaellt;"
            " blindes Sofort-Handeln ist die gegenlaeufige"
            " Fehlform (STABILITAET > AKTIONISMUS)"),
    },
    {
        "id": "krug-bruch",
        "redewendung":
            "Der Krug geht so lange zum Brunnen, bis er bricht",
        "formel": (
            "P(mindestens ein Bruch nach n Terminen) ="
            " 1 - Produkt_i((1 - p_i)); fuer p_i > 0 und"
            " n -> unendlich strebt der Grenzwert gegen 1"
            " (Montmort-Struktur)"),
        "erklaerung": (
            "Ein kleines Restrisiko, das man wiederholt"
            " eingeht, wird bei unbegrenzter Wiederholung fast"
            " sicher eintreten; Restrisiko != Risikofrei"),
        "quelle": "franzoesisches Sprichwort seit dem 16. Jh.",
        "bereich": "SPRICHWORT",
        "grenzen": (
            "exakt nur bei unabhaengigen Ereignissen;"
            " Reparatur oder Risikominderung zwischen den Runden"
            " aendert die Formel"),
    },
    {
        "id": "goldene-regel-universalisierung",
        "redewendung": (
            "Was du nicht willst, das man dir tu, das fueg auch"
            " keinem andern zu"),
        "formel": (
            "Universalisierung: Handlung h ist zulaessig, wenn"
            " fuer jede Partei a die Bewertung im Rollentausch"
            " erhalten bleibt: U(a, h) gleich"
            " U(rolle_getauscht(a), h); sonst abzulehnen"),
        "erklaerung": (
            "Eine Handlung, die im Rollentausch allen schadet,"

            " ist nicht zulaessig; strukturelle Verwandtschaft"
            " zum kategorischen Imperativ und zur"
            " Universalisierungsbedingung in Ethik und"
            " Spieltheorie"),
        "quelle": "Tobit 4,16; Bergpredigt Mt 7,12; Hillel (Antike)",
        "bereich": "BIBEL",
        "grenzen": (
            "ist nur eine formale Bedingung, keine vollstaendige"
            " Ethik; Grenzfaelle mit Befugnisfragen bleiben"
            " Einzelfall-Pruefung (PRIORITAET != BEFUGNIS)"),
    },
    {
        "id": "hochmut-sturz",
        "redewendung":
            "Hochmut kommt vor dem Fall",
        "formel": (
            "d(t) = geschaetzte_faehigkeit(t) - reale_faehigkeit(t);"
            " die Sturzrate P(sturz bis t + T) waechst monoton mit"
            " d; bei d = 0 ist die erwartete Sturzrate minimal"),
        "erklaerung": (

            "Selbst-Ueberschaetzung fuehrt zu Plaenen, welche die"
            " Realitaet nicht tragen; V91-Analogon: Ansprueche"
            " sind an gemessene Faehigkeit zu koppeln"
            " (WAHRHEIT > MEINUNG, CLAIM != EVIDENCE)"),
        "quelle": "Sprueche 16,18; Sprichwort",
        "bereich": "BIBEL",
        "grenzen": (
            "kein deterministisches Gesetz (MESSWERT != URSACHE);"
            " es gibt Ausreisser in beiden Richtungen, die Formel"
            " beschreibt eine Tendenz"),
    },
    {
        "id": "rastet-rostet",
        "redewendung":
            "Wer rastet, der rostet",
        "formel": (
            "Faehigkeit ohne Nutzung zerfaellt exponentiell:"
            " F(t + dt) = F(t) * e ** (-lambda * dt);"
            " regelmaessiges Ueben haelt F(t) >= F_0"),
        "erklaerung": (
            "Ungeuebte Faehigkeiten und ungepruefte Systeme"
            " verfallen; V91-Analogon: ungepruefte Notfallplaene"
            " verfallen still (SCRIPTED != INSTALLED,"
            " Backups testen)"),
        "quelle": "deutsches Sprichwort",
        "bereich": "SPRICHWORT",
        "grenzen": (
            "Zerfall nur ohne jegliche Restauration; schon kleine"
            " regelmaessige Reaktivierung haelt den Bestand"
            " (Zyklen beachten)"),
    },
    {
        "id": "gemeinsam-leichter",
        "redewendung":
            "Viele Haende machen leichte Arbeit",
        "formel": (
            "T_n = T_1 * (b + (1 - b) / n) nach Amdahl; solange"
            " der parallelisierbare Anteil (1 - b) > 0 ist, gilt"
            " T_n < T_1; bei b = 1 wirkt die Handvermehrung gegen"
            " null"),
        "erklaerung": (
            "Teilbare Arbeit wird durch Beteiligung schneller oder"
            " leichter; die Aufteilbarkeit ist vorher zu messen und"
            " nicht nur anzunehmen"),
        "quelle": "Erasmus von Rotterdam, Adagia (1508)",
        "bereich": "ANTIKE",
        "grenzen": (
            "die Koordinationskosten und die serialisierbare"
            " Restquote b koennen den Vorteil aufzehren"
            " (Brooks'sches Gesetz als Gegenextrem)"),
    },
    {
        "id": "stille-wasser-tief",
        "redewendung":
            "Stille Wasser laufen tief",
        "formel": (
            "Beobachtungsmodell: messbare_Aktivitaet(a) !="
            " Kapazitaet(a); Schaetzung wird nur mit zusaetzlicher"
            " Messung belastbar, nicht mit Zaehlung der"
            " sichtbaren Aktivitaet"),
        "erklaerung": (
            "Ruhe ist ein schlechter Schaetzer fuer Kapazitaet;"
            " V91-Analogon: messen statt vermuten"
            " (CLAIM != EVIDENCE, UNKNOWN != PASS)"),
        "quelle": "deutsches Sprichwort (seit dem 16. Jh.)",
        "bereich": "SPRICHWORT",
        "grenzen": (
            "die Gegenprobe gilt: Ruhe ist auch als Nichtexistenz"
            " moeglich; nur eine Messung trennt beides"),
    },
    {
        "id": "apfel-stamm",
        "redewendung":
            "Der Apfel faellt nicht weit vom Stamm",
        "formel": (
            "Markov-Struktur P(Zustand des Nachkommen | Zustand des"
            " Vorgaengers) konzentriert sich um aehnliche"
            " Zustaende; Uebergangsmatrix M mit"
            " M[v, aehnlich] > M[v, fern]"),
        "erklaerung": (
            "Praegung haelt Nachkommen-Zustaende in der Naehe des"
            " Ausgangszustands; Uebertragung auf Tradition, Werte"
            " und Kulturwandel"),
        "quelle": "deutsches Sprichwort",
        "bereich": "SPRICHWORT",
        "grenzen": (
            "kein Schicksal: Uebergangswahrscheinlichkeiten"
            " aendern sich mit Umgebung und Entscheidung"
            " (LERNEN > DOGMA)"),
    },
    {
        "id": "psalm-erholung",
        "redewendung": (
            "Er erquicket meine Seele (Psalm-Prinzip Ruhe und"
            " Erneuerung)"),
        "formel": (
            "Regenerationsgleichung S(t + 1) = S(t) - L(t) +"
            " rho * R(t) mit R(t) >= 0; ohne Ruheanteil R(t) > 0"
            " faellt S monoton gegen Erschoepfung"),
        "erklaerung": (
            "Lebendige Systeme brauchen Erholungszyklen;"
            " V91-Analogon: Morgen-Audit und Pruefzyklen sind der"
            " Ruhe- und Erneuerungsanteil des Dauerbetriebs"),
        "quelle": "Psalm 23,2-3",
        "bereich": "PSALM",
        "grenzen": (
            "rho ist kontextabhaengig (Mensch, Tier, Technik"
            " unterschiedlich); die Struktur ist keine"
            " medizinische Aussage"),
    },
    {
        "id": "gleich-gesellt",
        "redewendung":
            "Gleich und gleich gesellt sich gern",
        "formel": (
            "Homophilie: P(Kante(u, v) | aehnlich(u, v)) >"
            " P(Kante(u, v) | unaehnlich(u, v)); daraus bildet"

            " sich eine Modularitaet Q > 0 nach Clusterbildung"),
        "erklaerung": (
            "Aehnlichkeit erhoeht"
            " Verbindungs-Wahrscheinlichkeit und erzeugt Cluster;"
            " Uebertragung auf Gruppen, Teams und Netzwerke"),
        "quelle":
            "deutsches Sprichwort; vgl. lat. simile simili gaudet",
        "bereich": "SPRICHWORT",
        "grenzen": (
            "Homophilie kann Vielfalt verringern"
            " (BLINDFLECK-Risiko); Diversitaet ist die"
            " gegenlaeufige Struktur mit eigenem Nutzen"),
    },
    {
        "id": "zeit-heilt-wunden",
        "redewendung": "Die Zeit heilt alle Wunden",
        "formel": (
            "Belastung klingt ab: S(t) = S_0 * e ** (-lambda * t)"
            " mit lambda > 0; S(t) strebt fuer t -> unendlich gegen"
            " null"),
        "erklaerung": (
            "Viele Belastungen klingen mit zeitlichem Abstand ab;"
            " Abstand reduziert die aktive Belastung, nicht die"
            " Erinnerung"),
        "quelle": "deutsches Sprichwort; vgl. frz. Sprichwort",
        "bereich": "SPRICHWORT",
        "grenzen": (
            "gilt nicht fuer alle Wunden: manche Belastungen"
            " bleiben konstant oder wachsen; heilen ist kein"
            " Automatismus (LERNEN != Warten)"),
    },
    {
        "id": "alles-fliesst",
        "redewendung": "Alles fliesst",
        "formel": (
            "Zustaende aendern sich stetig: x(t + dt) ungleich"
            " x(t) fuer dt > 0 in lebendigen Systemen; Statik ist"
            " die Ausnahme, nicht die Regel"),
        "erklaerung": (
            "Systeme sind fluessige Zustaende, keine festen"
            " Bloecke; V91-Analogon: Messzyklen existieren, weil"
            " der Zustand sich zwischen Messungen bewegt"),
        "quelle": "Heraklit, panta rhei (Antike)",
        "bereich": "ANTIKE",
        "grenzen": (
            "nicht alles aendert sich gleich schnell; schematische Ausnahmen gibt es (Stabilisierung durch Zyklen ist moeglich, Stillstand nicht)"),
    },
    {
        "id": "aufgeschoben-nicht-aufgehoben",
        "redewendung": "Aufgeschoben ist nicht aufgehoben",
        "formel": (
            "Verschiebung: Aufgabe A mit Faelligkeit t_0 wird auf"
            " t_1 > t_0 verlegt; Verpflichtung W(A) bleibt"
            " unveraendert positiv, nur der Termin aendert sich"),
        "erklaerung": (
            "Eine vertagte Aufgabe bleibt eine offene Pflicht;"
            " Verzug verschiebt Lasten, er loescht sie nicht"
            " (vgl. verzug-diskont)"),
        "quelle": "deutsches Sprichwort; vgl. nl. uitstel is afstel",
        "bereich": "SPRICHWORT",
        "grenzen": (
            "manche Aufgaben entfallen wirklich durch"
            " Kontextaenderung; Pruefung noetig, sonst bleibt W(A)"
            " zu Unrecht im Buch"),
    },
    {
        "id": "morgenstund-gold",
        "redewendung": "Morgenstund hat Gold im Mund",
        "formel": (
            "frueher Start verlaengert die wirksame Zeit:"
            " E(start) = integral(t_start, T, w(t) dt) mit"
            " w(t) > 0; E faellt monoton mit spaeterem t_start"),
        "erklaerung": (
            "Fruehe Nutzung einer begrenzten Tageszeit hebt den"
            " moeglichen Ertrag; produktive Zyklen frueh anlegen"),
        "quelle": "deutsches Sprichwort seit dem 17. Jh.",
        "bereich": "SPRICHWORT",
        "grenzen": (
            "w(t) ist personenabhaengig (Chronotyp); fuer"
            " Nachtmenschen ist die Funktion gespiegelt, das"
            " Prinzip bleibt"),
    },
    {
        "id": "kommt-zeit-kommt-rat",
        "redewendung": "Kommt Zeit, kommt Rat",
        "formel": (
            "Loesungsmenge waechst mit Suchzeit:"
            " L(t) enthalten in L(t + 1); R(t) = |L(t)| monoton"
            " nicht fallend, Solvabilitaet waechst mit t"),
        "erklaerung": (
            "Mit mehr Suchzeit waechst die Zahl gefundener"
            " Loesungsansaetze; Warten allein erzeugt aber keine"
            " Loesung ohne Suche"),
        "quelle": "deutsches Sprichwort",
        "bereich": "SPRICHWORT",
        "grenzen": (
            "R(t) waechst nur bei aktiver Suche oder eintreffender"
            " Information; reines Warten haelt R konstant"
            " (WARTEN != SUCHEN)"),
    },
    {
        "id": "widerhall",
        "redewendung": "Wie man in den Wald hineinruft, so schallt"
                       " es heraus",
        "formel": (
            "Rueckkopplung: Rueckmeldung y = k * x mit k > 0;"
            " Signal x praegt Antwort y proportional"
            " (Echo-Struktur)"),
        "erklaerung": (
            "Verhalten praegt Gegenreaktion; V91-Analogon:"
            " Agenten-Konsens und Peer-Protokolle antworten"
            " deterministisch auf Eingaben"),
        "quelle": "deutsches Sprichwort",
        "bereich": "SPRICHWORT",
        "grenzen": (
            "k > 0 gilt nur fuer reagierende Systeme; unbelebte"
            " oder ueberlastete Gegenparteien schwaechen die"
            " Kopplung"),
    },
    {
        "id": "wind-sturm",
        "redewendung": "Wer Wind saet, wird Sturm ernten",
        "formel": (
            "ueberproportionale Rueckkopplung: y = k * x mit k > 1"
            " (Verstaerkung); kleine Ursache x erzeugt grosse"
            " Wirkung y (Resonanz bei k gross)"),
        "erklaerung": (
            "Eskalationsdynamik: kleine Provokation wird"
            " verstaerkt zurueckgegeben; Gegenreaktionen"
            " uebersteigen den Ausloeser"),
        "quelle": "Hosea 8,7; deutsches Sprichwort",
        "bereich": "BIBEL",
        "grenzen": (
            "k > 1 nur bei kritischen Systemen (Resonanz); viele"
            " Rueckkopplungen daempfen (k < 1) statt zu"
            " verstaerken"),
    },
    {
        "id": "rose-dornen",
        "redewendung": "Keine Rose ohne Dornen",
        "formel": (
            "Nutzen-Nebenwirkung-Kopplung: fuer jeden Nutzen N > 0"
            " existiert mindestens ein gekoppelter Nachteil"
            " D >= 1; Paar (N, D) ist nicht entkoppelt"
            " waehlbar"),
        "erklaerung": (
            "Jede Loesung bringt Nebenwirkungen; V91-Analogon:"
            " jede Erweiterung bringt Wartungslast"
            " (Wartungslast ist die Copplung selbst)"),
        "quelle": "deutsches Sprichwort; vgl. lat. nulla rosa sine" 
                  " spinis",
        "bereich": "SPRICHWORT",
        "grenzen": (
            "D ist nicht immer sichtbar; nicht jedes Paar ist"
            " streng gekoppelt, manche Nachteile sind minimal"
            " (D nahe 0)"),
    },
    {
        "id": "vorsicht-porzellankiste",
        "redewendung": "Vorsicht ist die Mutter der Porzellankiste",
        "formel": (
            "P(schaden | vorsichtiges Handeln) <"
            " P(schaden | ruecksichtsloses Handeln); Sorgfalt"
            " senkt die Eintrittswahrscheinlichkeit"),
        "erklaerung": (
            "Massvolles Vorgehen reduziert die Bruchrisiken;"
            " V91-Analogon: fail-closed-Pruefungen vor jedem"
            " Merge senken Fehlerwahrscheinlichkeit"),
        "quelle": "deutsches Sprichwort",
        "bereich": "SPRICHWORT",
        "grenzen": (
            "Vorsicht hat Kosten (Zeit, Chance); uebertriebene"
            " Vorsicht ist Blockade (STABILITAET > AKTIONISMUS"
            " gilt in beide Richtungen)"),
    },
    {
        "id": "ausnahmen-bestaetigen",
        "redewendung": "Ausnahmen bestaetigen die Regel",
        "formel": (
            "Ausnahme e ausserhalb der Menge G definiert die"
            " Grenze von G: G bleibt als Normalmenge"
            " unbeeinflusst, die Abweichung e kennzeichnet"
            " die Gueltigkeitsbereich-Grenze"),
        "erklaerung": (
            "Eine Abweichung widerlegt die Grundgesamtheit nicht,"
            " sondern schaerft ihre Gueltigkeitsgrenzen; erst"
            " haeufige Abweichungen verschieben G"),
        "quelle":
            "deutsches Sprichwort; vgl. lat. exceptio firmat" 
            " regulam",
        "bereich": "SPRICHWORT",
        "grenzen": (
            "oft als Ausrede benutzt; eine Ausnahme allein beweist"
            " keine Regel (BEHAUPTUNG != NACHWEIS), haeufige"
            " Ausnahmen widerlegen sie"),
    },
    {
        "id": "kleinvieh-mist",
        "redewendung": "Kleinvieh macht auch Mist",
        "formel": (
            "Summation kleiner Beitraege: K_gesamt ="
            " Summe_i(k_i) mit k_i klein, aber n gross;"
            " Grenzwert waechst linear mit n"),
        "erklaerung": (
            "Viele kleine Beitraege ergeben ein grosses"
            " Gesamtergebnis; V91-Analogon: 15-Minuten-Messzyklen"
            " summieren sich zur Langzeit-Evidenz"),
        "quelle": "deutsches Sprichwort",
        "bereich": "SPRICHWORT",
        "grenzen": (
            "lineare Summation gilt ohne Verlustraten; Verwaltung"
            " vieler kleiner Posten kann den Ertrag aufzehren"
            " (viele Haende vs. viele Koeche beachten)"),
    },
    {
        "id": "viel-hilft-nicht-immer-viel",
        "redewendung": "Viel hilft nicht immer viel",
        "formel": (
            "Nutzenfunktion mit Optimum: U(x) steigt bis"
            " x_opt und faellt fuer x > x_opt (Overshooting,"
            " Toxizitaet, Overspend)"),
        "erklaerung": (
            "Hoehere Dosierung oder Mittelmenge verbessert nicht"
            " unbegrenzt; jede Loesung hat ein"
            " Wirkungsoptimum"),
        "quelle": "deutsches Sprichwort",
        "bereich": "SPRICHWORT",
        "grenzen": (
            "x_opt muss gemessen werden, nicht geschaetzt; das"
            " Optimum verschiebt sich mit Kontext (CLAIM !="
            " EVIDENCE)"),
    },
    {
        "id": "kluegere-gibt-nach",
        "redewendung": "Der Kluegere gibt nach",
        "formel": (
            "Konfliktkosten-Gewichtung: Akteur a mit hoeherer"
            " Bewertung der Konfliktkosten K beendet die"
            " Eskalationsspirale frueher: t_aus(a) faellt"
            " monoton mit K-Gewichtung"),
        "erklaerung": (
            "Nachgeben ist Kostenminimierung, nicht Schwaeche;"
            " der Ausstieg aus einer Eskalationsspirale ist"
            " rational"),
        "quelle": "deutsches Sprichwort",
        "bereich": "SPRICHWORT",
        "grenzen": (
            "Nachgeben ist kein Allheilmittel: gegen systematische"
            " Ausbeutung zahlt sich dauerhaftes Nachgeben nicht"
            " aus (vgl. grube-reziprok)"),
    },
    {
        "id": "doppelt-genaehaelt",
        "redewendung": "Doppelt genaeht haelt besser",
        "formel": (
            "Redundanz unabhaengiger Stufen: P(ausfall von zwei"
            " Stufen) = p ** 2 < p fuer p < 1; Redundanz senkt"
            " die Gesamtausfallwahrscheinlichkeit"),
        "erklaerung": (
            "Doppelte Absicherung reduziert das Ausfallrisiko;"
            " V91-Analogon: Hash-Kette + Pruefzyklen sind"
            " gestaffelte Sicherungsebenen"),
        "quelle": "deutsches Sprichwort (Naehsprichwort)",
        "bereich": "SPRICHWORT",
        "grenzen": (
            "gilt nur bei unabhaengigen Stufen; gemeinsame"
            " Fehlerursachen (Correlated Failure) zerstoeren"
            " den Vorteil (p bleibt p, nicht p**2)"),
    },
    {
        "id": "pfennig-taler",
        "redewendung": "Wer den Pfennig nicht ehrt, ist des Talers"
                       " nicht wert",
        "formel": (
            "Zinsen und Disziplin: V(t + 1) = V(t) + epsilon mit"
            " epsilon klein aber konstant; V waechst linear,"
            " mit Zins e ** (r * t) sogar exponentiell"),
        "erklaerung": (
            "Vermoegen entsteht durch diszipliniertes Ansammeln"
            " kleiner Betraege; Nachlaessigkeit bei kleinen Posten"
            " verspielt den Grosse-Ertrag"),
        "quelle": "deutsches Sprichwort",
        "bereich": "SPRICHWORT",
        "grenzen": (
            "klein heisst nicht beliebig: Summation lohnt nur"
            " bei Perspektive (Zeitraum, Zins); ohne Ziel"
            " ist jeder Pfennig nur ein Pfennig"),
    },
    {
        "id": "schein-truegt",
        "redewendung": "Der Schein truegt",
        "formel": (
            "Beobachtungsmodell: Messwert y_dach = y_wahr + b +"
            " messfehler mit Bias b ungleich 0 moeglich;"
            " Schaetzung ohne Messung ist nicht belastbar"),
        "erklaerung": (
            "Der beobachtete Eindruck weicht vom wahren Zustand ab;"
            " V91-Analogon: CLAIM != EVIDENCE, UNKNOWN != PASS"),
        "quelle": "deutsches Sprichwort",
        "bereich": "SPRICHWORT",
        "grenzen": (
            "nicht jede Beobachtung truegt; kalibrierte Messung"
            " reduziert b, bleibt aber mit messfehler"
            " behaftet"),
    },
    {
        "id": "wald-baeume",
        "redewendung": "Man sieht den Wald vor lauter Baeumen nicht",
        "formel": (
            "Skalenproblem: Detaildichte d hoch => Uebersicht U"
            " faellt; Mustererkennung benoetigt ein Groessenfenster"
            " W_opt, U(d) hat ein Maximum bei mittlerem d"),
        "erklaerung": (
            "Zu viele Details verdecken den Gesamtzusammenhang;"
            " Wechsel der Betrachtungsskala stellt Uebersicht"
            " wieder her"),
        "quelle": "deutsches Sprichwort",
        "bereich": "SPRICHWORT",
        "grenzen": (
            "Uebersicht schwaecht Detailkenntnis (Wahl der"
            " Skala ist abhaengig von der Fragestellung)"),
    },
    {
        "id": "vertrauen-kontrolle",
        "redewendung": "Vertrauen ist gut, Kontrolle ist besser",
        "formel": (
            "P(undetected Fehler | mit Kontrolle) <"
            " P(undetected Fehler | ohne Kontrolle); zusaetzliche"
            " Verifikation senkt die Restirrtumsrate strikt"),
        "erklaerung": (
            "Verifikation erhoeht oder stabilisiert das"
            " Sicherheitsniveau; V91-Analogon: CI 2/2 vor jedem"
            " Merge, Hash-Kette gegen Manipulation"),
        "quelle":
            "deutsches Sprichwort; vgl. russ. doverjaj," 
            " no proverjaj",
        "bereich": "SPRICHWORT",
        "grenzen": (
            "Kontrolle hat Kosten und kann Vertrauen zerstoeren;"
            " unbegrenzte Kontrolle ohne Vertrauen ist"
            " handlungsunfaehig (BALANCE-Optimum)"),
    },
    {
        "id": "unwissenheit-strafe",
        "redewendung": "Unwissenheit schuetzt vor Strafe nicht",
        "formel": (
            "Normanwendung unabhaengig vom Kenntnisstand:"
            " P(Folge | Regelverletzung) = P(Folge |"
            " Regelverletzung, unwissend); Regel gilt ohne"
            " Ausnahme fuer Uninformierte"),
        "erklaerung": (
            "Regeln und Naturgesetze wirken ohne Ruecksicht auf"
            " Wissen; V91-Analogon: Manipulationsschutz verweigert"
            " bei Kettenbruch, egal wer es verursachte"),
        "quelle": "rechtlicher Grundsatz; deutsches Sprichwort",
        "bereich": "SPRICHWORT",
        "grenzen": (
            "Rechtssysteme kennen Tatbestandsmerkmale wie"
            " Fahrlaessigkeit; die Formel gilt strikt fuer"
            " Naturgesetze, weniger strikt fuer Recht"),
    },
    {
        "id": "uebung-meister",
        "redewendung": "Uebung macht den Meister",
        "formel": (
            "Lernkurve: F(n) = F_max * (1 - e ** (-nu * n));"
            " die Fertigkeit waechst degressiv mit den"
            " Wiederholungen n und naehert sich F_max an"),
        "erklaerung": (
            "Wiederholung erhoeht die Faehigkeit mit abnehmendem"
            " Zuwachs; V91-Analogon: wiederholte Pruefzyklen"
            " stabilisieren Systeme (vgl. rastet-rostet)"),
        "quelle": "deutsches Sprichwort",
        "bereich": "SPRICHWORT",
        "grenzen": (
            "F_max ist individuell begrenzt; falsche Uebung"
            " festigt Fehler (QUALITAET der Uebung zaehlt, nicht"
            " nur die Anzahl n)"),
    },
    {
        "id": "koeche-brei",
        "redewendung": "Viele Koeche verderben den Brei",
        "formel": (
            "Koordinationsschaden: Abstimmungsfehler wachsen"
            " ueberlinear mit der Zahl der Beteiligten m"
            " (Reibungsflaeche ~ m * (m - 1) / 2);"
            " Ergebnisqualitaet Q faellt ab m > m_opt"),
        "erklaerung": (
            "Zu viele Beteiligte ohne klare Zustendigkeit"
            " senken das Ergebnis; Gegenstruktur zu"
            " gemeinsam-leichter (beide gelten, je nach"
            " Teilbarkeit und Fuehrung)"),
        "quelle": "deutsches Sprichwort; vgl. engl. too many cooks",
        "bereich": "SPRICHWORT",
        "grenzen": (
            "mit klarer Rollenteilung steigt m_opt stark;"
            " das Problem ist ungeklaerte Zustaendigkeit, nicht"
            " die Zahl allein"),
    },
    {
        "id": "geteiltes-leid",
        "redewendung": "Geteiltes Leid ist halbes Leid",
        "formel": (
            "Lastenverteilung: subjektive Last je Person"
            " S_individual = S_gesamt / m faellt mit der Zahl der"
            " Traeger m (Zuspruch senkt zusaetzlich den"
            " Skalenfaktor)"),
        "erklaerung": (
            "Auf mehrere Schultern verteilt sinkt die Last pro"
            " Person; Mitteilen entlastet, auch wenn S_gesamt"
            " konstant bleibt"),
        "quelle": "deutsches Sprichwort",
        "bereich": "SPRICHWORT",
        "grenzen": (
            "manche Lasten sind nicht teilbar (manche Krankheiten tragen Einzelne allein); schlechtes Zuhoeren vermehrt die Last"
            " (QUALITAET des Teilens zaehlt)"),
    },
    {
        "id": "wille-weg",
        "redewendung": "Wo ein Wille ist, ist auch ein Weg",
        "formel": (
            "Zielbindung: bei ausreichendem Handlungswillen"
            " W >= W_0 existiert mindestens ein gangbarer"
            " Loesungspfad p im Loesungsgraph (Existenzbehauptung"
            " unter Aufwandsrestriktion)"),
        "erklaerung": (
            "Ausreichende Zielsetzung oeffnet Suchraum und"
            " Durchhaltevermoegen; der Weg ist oft nicht der"
            " zuerst geplante (Umwege zaehlen mit)"),
        "quelle":
            "deutsches Sprichwort; vgl. engl. where there is a" 
            " will",
        "bereich": "SPRICHWORT",
        "grenzen": (
            "kein Naturgesetz: physische und Befugnisgrenzen"
            " bleiben; bei Unmoeglichem ist auch Wille"
            " nur Wunschdenken (REALITAET > WUNSCHDENKEN)"),
    },
    {
        "id": "baerenfell",
        "redewendung": "Man soll das Fell des Baeren nicht verteilen,"
                       " bevor er erlegt ist",
        "formel": (
            "Unsicherer Ertrag X darf nicht wie sicher verplant"
            " werden: verplanbar ist nur E[X] mit Risikomarge oder"
            " nachgewiesene Werte; Budget B <= E[X] - Sicherheits-%"
            " ist Leichtsinn"),
        "erklaerung": (
            "Unsichere Ertraege sind keine verfuegbaren Groessen;"
            " V91-Analogon: SCRIPTED != INSTALLED, erwartete"
            " Wirkung bleibt UNKNOWN bis gemessen"),
        "quelle": "deutsches Sprichwort",
        "bereich": "SPRICHWORT",
        "grenzen": (
            "vollstaendiger Verzicht auf Planung mit Erwartungs-"
            " werten lahmt; die Marge ist das Mass, nicht die"
            " Verweigerung"),
    },
    {
        "id": "gleiches-zieht-gleiches",
        "redewendung": "Gleiches zieht Gleiches an",
        "formel": (
            "Attraktionsmodell: Annaeherungsrate A(u, v) faellt"
            " monoton mit Merkmalsdistanz d(u, v)"
            " (A hoch bei d klein); Spezialfall der Homophilie"
            " (vgl. gleich-gesellt)"),
        "erklaerung": (
            "Geringe Merkmalsdistanz beguenstigt Naehe und"
            " Kopplung; Uebertragung auf Gruppen, Resonanz und"
            " Teambildung"),
        "quelle":
            "deutsches Sprichwort; vgl. engl. like attracts like",
        "bereich": "SPRICHWORT",
        "grenzen": (
            "kein kosmisches Gesetz, nur ein soziales Muster;"
            " Gegenbeispiele (komplementaere Paarung) existieren,"
            " empirie bleibt entscheidend"),
    },
    {
        "id": "wurst-zwei-enden",
        "redewendung": "Alles hat ein Ende, nur die Wurst hat zwei",
        "formel": (
            "Prozessmodel: Zeitabhaengige Prozesse sind"
            " Intervalle I = [t_start, t_ende] mit endlichem"
            " Ende; die Wurst als Spezialfall hat zwei"
            " Endpunkte (Intervall-Grenzen), kein Unendliches"),
        "erklaerung": (
            "Begrenztheit von Prozessen als Grundstruktur; die"
            " Wurst-Pointe ironisiert die Ding-Analogie"
            " (Sprachwitzformel, kein Gesetz)"),
        "quelle": "deutsches Sprichwort (Scherzformel)",
        "bereich": "SPRICHWORT",
        "grenzen": (
            "Scherzformel: die Witz-Struktur darf nicht als"
            " Regelanwendung gelesen werden (EMOJI != GEHALT"
            " gilt hier ebenfalls: WITZ != THESE)"),
    },
    {
        "id": "ton-musik",
        "redewendung": "Der Ton macht die Musik",
        "formel": (
            "Wirkungsmodulation: Antwort y = alpha * x, wobei"
            " alpha die Wirkung des Inhalts x verstaerkt (alpha"
            " > 1), daempft (0 < alpha < 1) oder umkehrt"
            " (alpha < 0)"),
        "erklaerung": (
            "Die Art der Vermittlung praegt die Wirkung des"
            " Inhalts; V91-Analogon: Meaning von Reports haengt"
            " an Klarheit und Formatting (ASCII-Reports als"
            " bewusste Tonwahl)"),
        "quelle": "deutsches Sprichwort",
        "bereich": "SPRICHWORT",
        "grenzen": (
            "kein vollstaendiges Modell: Inhalt und Ton wirken"
            " zusammen, alpha wird vom Empfaenger"
            " mitbestimmt (Empfang != Sendung)"),
    },
    {
        "id": "not-erfinderisch",
        "redewendung": "Not macht erfinderisch",
        "formel": (
            "Restriktionsnutzen: eingeengter Loesungsraum"
            " C (weniger Ressourcen, haertere Randbedingungen)"
            " stimuliert die Zahl alternativer Loesungsansaetze"
            " N(C); bei C eng steigt N(C) gegen festgefahrenes Denken"),
        "erklaerung": (
            "Knappheit erzeugt alternative Loesungsstrategien;"
            " Wegfall des Selbstverstaendlichen oeffnet neue"
            " Pfade (Constraint-Driven Innovation)"),
        "quelle": "deutsches Sprichwort",
        "bereich": "SPRICHWORT",
        "grenzen": (
            "uebertriebene Not blockiert statt zu befluegeln"
            " (Untergrenze beachten); Erfindung braucht"
            " noch Faehigkeit und Raum zum Ausprobieren"),
    },
    {
        "id": "spatz-taube",
        "redewendung": "Besser den Spatz in der Hand als die Taube"
                       " auf dem Dach",
        "formel": (
            "Sicherheitspreis: Nutzen(sicherer kleiner Gewinn) ="
            " G_s > p * G_g = Erwartungswert unsichere Grosschance;"
            " nimm G_s, wenn p < G_s / G_g (Risikoaversion"
            " mit Schwelle)"),
        "erklaerung": (
            "Ein kleiner, sicherer Gewinn schlaegt im"
            " Erwartungswert eine unsichere groessere Chance"
            " unter der Schwelle; V91-Analogon: Merge nur mit CI"
            " 2/2 statt Hoffnungsmerge"),
        "quelle": "deutsches Sprichwort",
        "bereich": "SPRICHWORT",
        "grenzen": (
            "bei risikoneutralen Zielen oder grossem Portfolio"
            " kann p * G_g ueberwiegen; Punkt-Entscheidung,"
            " kein Moralgesetz"),
    },
    {
        "id": "ende-gut-alles-gut",
        "redewendung": "Ende gut, alles gut",
        "formel": (
            "Peak-End-Bewertung: Gesamtwert W = Summe_i(w_i *"
            " r_i) mit Endgewicht w_Ende gross; der"
            " Abschlusszustand praegt die Bewertung des"
            " Verlaufs ueberproportional"),
        "erklaerung": (
            "Der Abschlusszustand bestimmt massgeblich die"
            " Gesamtbewertung; deshalb: Abschluesse saeubern,"
            " Abschluesse ehrlich und verifiziert"
            " (Post-Merge-Verify als Ritual)"),
        "quelle": "deutsches Sprichwort; vgl. Shakespeare-Ende",
        "bereich": "SPRICHWORT",
        "grenzen": (
            "Peak-End ist eine Bewertungsverzerrung, kein"
            " Qualitaetsmass; ein schlechter Verlauf mit gutem"
            " Ende bleibt ein schlechter Verlauf"
            " (BEWERTUNG != VERLAUF)"),
    },
]


def pruefe(formeln: List[Any]) -> Dict[str, Any]:
    """Struktur-Gate: Pflichtfelder, Bereich, ASCII, doppelte IDs.

    Sammelt alle Gruende, nichts wird still korrigiert
    (KEINE_STUMME_KORREKTUR). Eine Formel-Zeile ohne Grenzen ist
    ehrlich unvollstaendig (SPRICHWORT != GESETZ).
    """
    fehlerhafte: List[Dict[str, Any]] = []
    gesehen: Dict[str, int] = {}
    for eintrag in formeln:
        if not isinstance(eintrag, dict):
            fehlerhafte.append({
                "id": "<kein objekt>",
                "gruende": ["eintrag ist kein objekt"],
            })
            continue
        mid = eintrag.get("id")
        if not _non_empty(mid):
            mid = "<ohne id>"
        gesehen[mid] = gesehen.get(mid, 0) + 1
    doppelte = {mid for mid, n in gesehen.items() if n > 1}

    for eintrag in formeln:
        if not isinstance(eintrag, dict):
            continue
        mid = eintrag.get("id") if _non_empty(eintrag.get("id")) \
            else "<ohne id>"
        gruende: List[str] = []
        for feld in FELDER:
            wert = eintrag.get(feld)
            if not _non_empty(wert):
                gruende.append("feld %s fehlt oder ist leer" % feld)
        bereich = eintrag.get("bereich")
        if _non_empty(bereich) and bereich not in BEREICHE:
            gruende.append("bereich %r nicht zulaessig (%s)"
                           % (bereich, "|".join(BEREICHE)))
        if mid in doppelte:
            gruende.append("doppelte id %r (keine zweit-registrierung)"
                           % mid)
        for feld in ("redewendung", "formel", "erklaerung", "grenzen"):
            wert = eintrag.get(feld)
            if _non_empty(wert) and not _ascii_ok(wert):
                gruende.append("feld %s ist nicht ascii-pure" % feld)
        if gruende:
            fehlerhafte.append({"id": mid, "gruende": gruende})

    gueltig = len(formeln) - len(fehlerhafte)
    verdict = (VERDICT_REGISTRIERT
               if formeln and not fehlerhafte else VERDICT_ABGELEHNT)
    return {
        "formeln_gesamt": len(formeln),
        "formeln_gueltig": gueltig,
        "formeln_ungueltig": len(fehlerhafte),
        "fehlerhafte": fehlerhafte,
        "verdict": verdict,
        "grenzen": GRENZEN,
    }


def format_text_report(report: Dict[str, Any]) -> str:
    """Lesbarer, ASCII-pure, deterministischer Bericht."""
    lines = [
        "V91 Sprichwort-/Redewendung-Formel-Registry (VIBE-LXXV)",
        "verdict  : %s" % report["verdict"],
        "formeln  : %d gesamt, %d gueltig, %d ungueltig" % (
            report["formeln_gesamt"], report["formeln_gueltig"],
            report["formeln_ungueltig"]),
        "",
    ]
    for eintrag in report.get("eintraege", []):
        lines.append("id          : %s" % eintrag["id"])
        lines.append("redewendung : %s" % eintrag["redewendung"])
        lines.append("formel      : %s" % eintrag["formel"])
        lines.append("erklaerung  : %s" % eintrag["erklaerung"])
        lines.append("quelle      : %s" % eintrag["quelle"])
        lines.append("bereich     : %s" % eintrag["bereich"])
        lines.append("grenzen     : %s" % eintrag["grenzen"])
        lines.append("")
    for fehler in report["fehlerhafte"]:
        lines.append("ABGELEHNT : %s" % fehler["id"])
        for grund in fehler["gruende"]:
            lines.append("  - %s" % grund)
        lines.append("")
    lines.append("grenze: %s" % report["grenzen"])
    return "\n".join(lines) + "\n"


def _write_reports(report: Dict[str, Any], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "sprichwort_formeln.txt").write_text(
        format_text_report(report), encoding="ascii")
    payload = json.dumps(report, indent=2, sort_keys=True,
                         ensure_ascii=True) + "\n"
    (out_dir / "sprichwort_formeln.json").write_text(
        payload, encoding="ascii")


def lade_ergaenzung(path: Optional[Path]) -> List[Dict[str, Any]]:
    """Laedt eine Ergaenzungs-Datei (JSON mit formeln-Liste).

    Die Ergaenzung fliesst NICHT in die Registry ein; sie wird nur
    geprueft und im Report gezaehlt (GATE != SPEICHER; weitere
    Agenten lernen aus der Registry, nicht aus einer Kopie).
    """
    if path is None:
        return []
    if not path.is_file():
        raise KreislaufInputError("ergaenzung fehlt: %s" % path)
    try:
        with path.open("r", encoding="ascii") as handle:
            daten = json.load(handle,
                              parse_constant=_keine_json_konstante)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise KreislaufInputError("ergaenzung kein gueltiges JSON: %s"
                                  % exc) from exc
    if not isinstance(daten, dict) or not isinstance(
            daten.get("formeln"), list):
        raise KreislaufInputError(
            "ergaenzung braucht formeln-liste (objekt mit schluessel"
            " formeln)")
    return daten["formeln"]


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Sprichwort-/Redewendung-Formel-Registry"
                    " (advisory, ANALOGIE != BEWEIS,"
                    " THEOLOGIE != ENTSCHEIDUNG)")
    parser.add_argument("--ergaenzung", default=None,
                        help="JSON-Datei mit zusaetzlichen formeln"
                             " (nur Pruefung, keine Speicherung)")
    parser.add_argument("--report-dir", default=None,
                        help="Verzeichnis fuer txt/json-Reports")
    args = parser.parse_args(argv)
    try:
        zusaetzliche = lade_ergaenzung(
            Path(args.ergaenzung) if args.ergaenzung else None)
    except KreislaufInputError as exc:
        sys.stderr.write("INPUT_ERROR: %s\n" % exc)
        return EXIT_INPUT_ERROR

    formeln = list(DEFAULT_FORMELN) + zusaetzliche
    report = pruefe(formeln)
    report["eintraege"] = [
        {feld: eintrag[feld] for feld in FELDER if feld in eintrag}
        for eintrag in formeln if isinstance(eintrag, dict)
    ]
    if args.report_dir:
        _write_reports(report, Path(args.report_dir))
    sys.stdout.write(format_text_report(report))
    if report["verdict"] == VERDICT_REGISTRIERT:
        return EXIT_REGISTRIERT
    return EXIT_ABGELEHNT


if __name__ == "__main__":
    raise SystemExit(main())
