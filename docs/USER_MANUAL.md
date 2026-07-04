# Finance Dashboard — Benutzerhandbuch

Kurzer Ablauf-Walkthrough für Endnutzer. (Die Oberfläche ist deutsch; weitere
Sprachen lassen sich unter **Einstellungen → Sprache** wählen, sobald
Übersetzungsdateien vorliegen.)

## 1. Depot anlegen

Auf der **Übersicht** (Startseite) → „Neues Depot": Name, Eröffnungsdatum,
Basiswährung (Standard EUR) und die Anzeige-Voreinstellungen für Chart-Zeitraum
und Bezugsbasis festlegen. Die Übersicht zeigt alle Depots mit ihren
wichtigsten Kennzahlen und den Gesamtsummen; per Klick auf den Namen wird ein
Depot zum aktiven Depot.

## 2. Geld einzahlen

Im Tab **Transaktionen** → „Ein-/Auszahlung erfassen": Typ *Einzahlung*,
Betrag, Zeitpunkt. Der **Barbestand** wird immer aus den Buchungen abgeleitet —
Käufe sind nur möglich, wenn sie gedeckt sind (sofern Überziehen nicht per
Konfiguration erlaubt ist).

## 3. Wertpapier kaufen („Wert hinzufügen")

Im Tab **Bestand** → „Wert hinzufügen". Wertpapier aus der Liste wählen oder
über „Wertpapier anlegen" neu erfassen (ISIN, Name, Kategorie — die Kategorie
steuert, welcher Kursanbieter zuständig ist). Dann Stück, Kaufkurs, Zeitpunkt,
Spesen, Börse.

**Kaufdatum in der Vergangenheit?** Die App fragt nach, ob der Mini-Chart
„seit Kauf" mit historischen Tagesschlusskursen vorbefüllt werden soll.
„Ja" lädt die Historie über den Anbieter (für Aktien/ETF meist verfügbar, für
Hebelprodukte oft nicht); „Nein" lässt den Chart ab jetzt wachsen.

## 4. Kurse

- **Kurs-Setup** (Hauptnavigation): je Kursgruppe (Aktien/ETF, Hebelprodukte)
  den Anbieter wählen, Zugangsdaten hinterlegen (verschlüsselt gespeichert,
  Geheimnisse werden nur maskiert angezeigt) und das Abfrageintervall setzen.
  Für Trade Republic: „Login anstoßen" → 4-stelligen Bestätigungscode aus der
  TR-App/SMS eingeben → Status „angemeldet".
- **Verfügbarkeitstest**: prüft für ein Depot jeden Wert, ob ein Kurs
  abrufbar ist — ohne etwas zu speichern.
- **„Kurse aktualisieren"** (Dashboard/Bestand): holt sofort frische Kurse
  für alle Werte des Depots. Einzelne Fehler stoppen die übrigen nicht.
- Fällt ein Anbieter aus, bleibt der letzte Kurs mit Zeitstempel sichtbar und
  wird als **„veraltet"** markiert.

## 5. Verkaufen, Dividenden, Steuern

- **Verkauf** (Tab „Verkäufe" oder Kontextmenü einer Position): Teil- oder
  Gesamtverkauf; der **realisierte Gewinn** wird per FIFO aus den ältesten
  Tranchen berechnet und gespeichert. Spesen und **gezahlte Steuer** mindern
  den Barbestand; die Steuer fließt in die Steuern-Kennzahl, nicht in den
  realisierten Gewinn.
- **Dividende** je Wertpapier erfassen → Gutschrift auf den Barbestand und
  eigene Dividenden-Kennzahl.
- **Steuerverrechnung** (depotweit) → Gutschrift auf den Barbestand;
  Steuern-KPI = gezahlte Steuern − Verrechnungen.

## 6. Buchungen ändern

Jede Buchung (Kauf, Verkauf, Zahlung, Dividende, Steuerverrechnung) kann über
den Tab **Transaktionen** oder die aufgeklappte Positionszeile **bearbeitet
oder gelöscht** werden — einschließlich des Zeitpunkts. Alle abgeleiteten
Werte (Barbestand, FIFO, realisierte Gewinne, Bewertungsreihe) werden danach
automatisch neu berechnet. Änderungen, die Verkäufe ungedeckt machen oder den
Barbestand überziehen würden, werden abgelehnt.

## 7. Dashboard, Chart & Kennzahlen

Das Depot-Dashboard zeigt die KPI-Kacheln („Mehr Details" blendet realisierten/
unrealisierten Gewinn, Dividenden, Steuern und Gesamtergebnis ein) und den
**Wertverlaufs-Chart**. Zeitraum (seit Eröffnung, 1M/3M/6M/YTD/1J oder
benutzerdefiniert) und Bezugsbasis (nur Wertpapiere / inkl. Barbestand) sind
umschaltbar und steuern auch die „Performance im Zeitraum". Hinweis: Ein-/
Auszahlungen im Zeitraum verzerren die einfache Wertdifferenz.

## 8. Snapshots

Tab **Snapshots**: benannten Snapshot erstellen (friert alle Kennzahlen und
Positionen ein). Zwei Snapshots per Auswahl **vergleichen** — Differenzen je
Kennzahl und je Position. Snapshots sind unveränderlich.

## 9. Export

Auf Übersicht, Bestand, Verkäufen, Transaktionen und im Snapshot-Vergleich:
**xlsx**, **CSV** oder **Drucken/PDF** (öffnet eine Druckansicht; über den
Druckdialog des Browsers als PDF speichern).

## 10. App installieren (PWA)

Die App ist installierbar („Zum Startbildschirm hinzufügen" bzw.
Installieren-Symbol im Browser). Offline steht die App-Hülle samt
Offline-Hinweisseite zur Verfügung; Daten benötigen eine Verbindung.
