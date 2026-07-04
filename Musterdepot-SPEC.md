# Musterdepot — Spezifikation

Fachliche und technische Spezifikation für ein Web-Tool zur Verwaltung mehrerer
**Aktien-Musterdepots** (Paper-Portfolios). Diese Datei ist die
Umsetzungsvorlage: Claude Code implementiert die App **zusammen mit dem Skill
`web-app`** — der Skill liefert Tech-Stack, Struktur und Konventionen, diese Spec
liefert die Domäne, die Features und die App-spezifischen Entscheidungen.

> **Wichtig für die Umsetzung:** Zuerst `web-app/SKILL.md` und die passenden
> `references/*.md` lesen. Diese Spec dupliziert die Skill-Vorgaben bewusst
> **nicht** (3-Schichten, `create_app()`-Factory, SQLAlchemy 2.0 + Repository +
> Alembic, MCP-Server, PWA, Tests, Deployment) — sie verweist darauf und
> beschreibt nur, was für diese App gilt.

---

## 1. Zweck & Abgrenzung

Ein Einzelnutzer verwaltet mehrere **Musterdepots**, um Anlage-Ideen ohne echtes
Geld zu verfolgen. Käufe und Verkäufe werden hypothetisch erfasst und laufend mit
aktuellen Börsenkursen bewertet. Das Tool ist ein **Tracking- und
Simulationswerkzeug** — es führt **keine echten Orders aus**, gibt **keine
Anlageberatung** und ist keine Steuersoftware.

## 2. Rahmenentscheidungen (verbindlich)

Diese Punkte wurden bei der Spezifikation festgelegt und steuern die Umsetzung:

| Thema | Entscheidung |
|---|---|
| Instrumententypen | **Alle**: Aktien, ETFs sowie Hebelprodukte (Optionsscheine, Knock-Outs/Turbos, Faktor-Zertifikate). |
| Kursquelle | **Abstrahiert** über eine `PriceProvider`-Schnittstelle mit Routing nach Instrumentenkategorie. Initial: **FMP** für Aktien/ETF, **pytr (Trade Republic)** für Hebelprodukte. Beliebig erweiterbar. |
| Fremdwährung | **Abstrahiert** über eine `ExchangeRateProvider`-Schnittstelle (austauschbare Module, im Setup wählbar/konfigurierbar). Initial: **FMP**. Beliebig erweiterbar. |
| Nutzer/Auth | **Einzelnutzer, kein Login.** Kein LDAP, keine Rollen. Später nachrüstbar (Skill unterstützt das). |
| PWA | **Ja** — installierbar, offline-fähige App-Shell (PWA-Schicht des Skills, `references/pwa.md`). |
| Sprache | **Deutsch** für alle Nutzertexte, Domänenbegriffe und DB-Spalten. |
| Config | `pydantic-settings` (Empfehlung des Skills). |
| Persistenz | SQLAlchemy 2.0 + Repository + Alembic; SQLite (dev) / MariaDB (prod). |

## 3. Domänenbegriffe

- **Depot** — ein Musterdepot mit Eröffnungsdatum, Barbestand und Positionen.
- **Instrument / Wertpapier** — ein handelbarer Wert, identifiziert über ISIN/WKN,
  mit einer **Kategorie** (Aktie, ETF, Optionsschein, …).
- **Kauf / Tranche** — ein einzelner Kaufvorgang (Stück, Kurs, Datum, Spesen).
  Mehrere Käufe desselben Instruments bilden zusammen eine Position.
- **Position** — die aggregierte Sicht auf alle offenen Tranchen eines Instruments
  in einem Depot (aufklappbar in die einzelnen Tranchen).
- **Verkauf** — ein Verkaufsvorgang; erzeugt einen **realisierten Gewinn/Verlust**.
- **Ein-/Auszahlung** — Bargeldbewegung, die den Barbestand verändert.
- **Dividende** — erhaltene Ausschüttung zu einem Wertpapier; wird dem Barbestand
  gutgeschrieben.
- **Steuer beim Verkauf** — beim Verkauf gezahlte Steuer; wird vom Barbestand
  abgezogen.
- **Steuerverrechnung** — depotweite Steuergutschrift/-erstattung; wird dem
  Barbestand gutgeschrieben.
- **Kurs** — ein zeitgestempelter Preis eines Instruments von einer Quelle.
- **Bewertung** — automatische Tages-Momentaufnahme des Depotwerts (für den
  Verlaufs-Chart).
- **Snapshot** — vom Nutzer manuell erstellte, benannte Momentaufnahme eines Depots,
  die mit anderen Snapshots verglichen werden kann.
- **Depot-Übersicht** — Start-Dashboard über **alle** Depots mit den wichtigsten
  KPIs, inkl. Anlegen/Bearbeiten/Löschen von Depots.

## 4. Datenmodell

Deklarative SQLAlchemy-2.0-Entities (`Mapped[...]`), deutsche Spaltennamen. Kein
Raw-SQL im Request-Pfad (siehe `references/persistence.md`). Geldbeträge und
Kurse als `Decimal` (nie `float`). Repository-Pattern je Aggregat.

### 4.1 `Depot`
- `id`, `name` (eindeutig), `eroeffnet_am` (Datum), `basiswaehrung` (Default `EUR`),
  `notiz` (optional), `angelegt_am`.
- Anzeige-Voreinstellungen (für Chart & Performance, s. 5.5): `default_zeitraum`
  (Enum `SEIT_EROEFFNUNG` | `1M` | `3M` | `6M` | `YTD` | `1J` | `BENUTZERDEFINIERT`,
  Default `SEIT_EROEFFNUNG`) und `default_bezugsbasis` (Enum `NUR_WERTPAPIERE` |
  `INKL_BARBESTAND`, Default `INKL_BARBESTAND`).
- **Barbestand ist abgeleitet** (nicht gespeichert): Summe aller Cash-Bewegungen
  des Depots (siehe 5.2).

### 4.2 `Instrument`
- `id`, `isin` (eindeutig), `wkn` (optional), `name`, `kategorie` (Enum, s.u.),
  `waehrung` (Default `EUR`), `referenzboerse` (z. B. „Stuttgart"), `symbol`
  (Provider-Ticker-Mapping, z. B. FMP-Symbol; optional, wird aufgelöst/gecacht),
  `basiswert` (optional, bei Hebelprodukten das Underlying), `angelegt_am`.
- **`kategorie`** (Enum): `AKTIE`, `ETF`, `OPTIONSSCHEIN`, `KNOCKOUT`, `FAKTOR`,
  `SONSTIGES`.
- **`kursgruppe`** (abgeleitet aus `kategorie`, steuert das Provider-Routing):
  `AKTIEN_ETF` (Aktie, ETF) oder `HEBELPRODUKT` (Optionsschein, Knock-Out, Faktor).

### 4.3 `Kauf` (Tranche)
- `id`, `depot_id` → Depot, `instrument_id` → Instrument, `stueck` (Decimal),
  `kaufkurs` (Decimal), `kauf_zeitpunkt` (Datetime — **editierbar**, Datum + optional
  Uhrzeit), `spesen` (Decimal, Default 0), `boerse` (optional), `angelegt_am`,
  `geaendert_am`.
- Abgeleitet: `kaufwert = stueck * kaufkurs + spesen`.
- Offene Stückzahl je Tranche ergibt sich aus FIFO-Verrechnung mit Verkäufen
  (siehe 5.3); optional Konsum je Tranche materialisieren für Performance.
- Der `kauf_zeitpunkt` bestimmt die FIFO-Reihenfolge; eine nachträgliche Änderung
  löst Neuberechnung aus (siehe 4.11 / 5.6).

### 4.4 `Verkauf`
- `id`, `depot_id`, `instrument_id`, `stueck`, `verkaufskurs`, `verkauf_zeitpunkt`
  (Datetime — **editierbar**), `spesen` (Default 0), `steuer` (Decimal, Default 0 —
  beim Verkauf gezahlte Steuer, mindert den Barbestand), `boerse` (optional),
  `angelegt_am`, `geaendert_am`.
- `realisierter_gewinn` (Decimal) — beim Verkauf aus den FIFO-verrechneten
  Einstandskosten berechnet und gespeichert (Nachvollziehbarkeit). Die `steuer`
  fließt **nicht** in `realisierter_gewinn` ein, sondern nur in den Barbestand und
  die Steuern-KPI (5.4).

### 4.5 `Zahlung` (Ein-/Auszahlung)
- `id`, `depot_id`, `typ` (Enum `EINZAHLUNG` | `AUSZAHLUNG`), `betrag` (Decimal > 0),
  `zeitpunkt` (Datetime — **editierbar**), `notiz` (optional), `angelegt_am`,
  `geaendert_am`.

### 4.6 `Kurs`
- `id`, `instrument_id`, `kurs` (Decimal), `waehrung`, `boerse`, `zeitstempel`
  (Datetime), `quelle` (Enum `FMP` | `PYTR` | `MANUELL` | …), `vortagesschluss`
  (Decimal, optional — Basis der Tagesveränderung).
- **Historie** wird behalten (Zeitreihe der abgerufenen Momentankurse je Instrument);
  der jeweils jüngste `Kurs` ist der „aktuelle Kurs" (Basis für akt./ges.
  Veränderung). Die separate **Tagesschluss-Reihe** für die Mini-Charts „seit Kauf"
  liegt in `Schlusskurs` (siehe 6.9).

### 4.7 `DepotBewertung` (automatischer Tages-Snapshot)
- `id`, `depot_id`, `datum` (eindeutig je Depot), `depotbestand`, `barbestand`,
  `gesamtwert`.
- Wird täglich vom Kurs-/Bewertungsjob geschrieben → speist „Entwicklung seit
  Eröffnung" und die zeitraumbezogene Performance (5.5). Enthält bewusst
  **beide** Reihen (`depotbestand` und `gesamtwert`), damit die Bezugsbasis-
  Umschaltung ohne Neuberechnung funktioniert.

### 4.8 `Dividende`
- `id`, `depot_id`, `instrument_id` → Instrument, `betrag` (Decimal > 0 — dem
  Barbestand gutgeschriebener Betrag), `zeitpunkt` (Datetime — **editierbar**),
  `notiz` (optional), `angelegt_am`, `geaendert_am`.
- Optionale Zusatzfelder für Nachvollziehbarkeit: `betrag_je_anteil`,
  `stueck_zum_zeitpunkt` (rein informativ; maßgeblich ist `betrag`).

### 4.9 `Steuerverrechnung`
- `id`, `depot_id`, `betrag` (Decimal > 0 — dem Barbestand gutgeschriebene
  Steuererstattung/-verrechnung), `zeitpunkt` (Datetime — **editierbar**),
  `notiz` (optional), `angelegt_am`, `geaendert_am`.
- Depotweit (kein Instrumentbezug). Das Gegenstück — gezahlte Steuer — hängt am
  jeweiligen `Verkauf.steuer` (4.4).

### 4.10 `DepotSnapshot` (manueller Vergleichs-Snapshot)
- `id`, `depot_id`, `name` (Nutzer-Label), `erstellt_am`, `notiz` (optional).
- Eingefrorene KPIs zum Erstellzeitpunkt: `depotbestand`, `barbestand`,
  `gesamtwert`, `realisierter_gewinn`, `unrealisierter_gewinn`, `dividenden`,
  `steuern`, `gesamtgewinn`, `gesamtergebnis`.
- `positionen_json` — eingefrorene Positionsdetails (Instrument, Stück,
  Einstandswert, Wert, Gewichtung) für den detaillierten Vergleich.
- Abgegrenzt von `DepotBewertung`: `DepotBewertung` ist die automatische tägliche
  Zeitreihe; `DepotSnapshot` ist eine manuell benannte Momentaufnahme, die zwei
  Zustände direkt vergleichbar macht.

### 4.11 Editierbarkeit & Neuberechnung
Alle Buchungsentitäten (`Kauf`, `Verkauf`, `Zahlung`, `Dividende`,
`Steuerverrechnung`) sind **nachträglich editier- und löschbar**, inklusive des
Zeitpunkts. Da Barbestand, FIFO-Verrechnung, realisierte Gewinne und die
KPI-/Bewertungsreihen daraus abgeleitet sind, löst jede Änderung eine
**Neuberechnung** aus (Details in 5.6). `geaendert_am` dokumentiert die letzte
Änderung. `DepotSnapshot`-Datensätze sind bewusst **unveränderlich** (eingefrorener
Vergleichszustand).

### 4.12 Beziehungen
```
Depot 1─* Kauf *─1 Instrument 1─* Kurs
Instrument 1─* Schlusskurs   (Tagesschluss-Reihe für Mini-Charts, 6.9)
Depot 1─* Verkauf *─1 Instrument
Depot 1─* Zahlung
Depot 1─* Dividende *─1 Instrument
Depot 1─* Steuerverrechnung
Depot 1─* DepotBewertung
Depot 1─* DepotSnapshot
Position = abgeleitete Aggregation der offenen Käufe je (Depot, Instrument)

KursEinstellung      (global, je Kursgruppe genau eine; Definition in 6.6)
WaehrungsEinstellung (global, genau eine; Definition in 6.10)
```

## 5. Berechnungslogik (verbindlich)

Diese Formeln sind das Herz der App und gehören als Requirements-Tests abgesichert
(siehe 10). Alle Beträge `Decimal`, kaufmännische Rundung auf 2 Nachkommastellen
erst bei der Anzeige.

### 5.1 Position & Kennzahlen je Position
- `offene_stueck` = Σ gekaufte Stück − Σ verkaufte Stück (FIFO) des Instruments im Depot.
- `einstandswert` = Σ (offene Tranchen: `stueck * kaufkurs`) + anteilige Spesen.
- `positionswert` (= „Wert in EUR") = `offene_stueck * aktueller_kurs`.
- `tagesveraenderung_eur` (= „akt. EUR") = `offene_stueck * (aktueller_kurs − vortagesschluss)`.
- `tagesveraenderung_pct` (= „akt. %") = `aktueller_kurs / vortagesschluss − 1`.
- `gesamtveraenderung_eur` (= „ges. EUR") = `positionswert − einstandswert`.
- `gesamtveraenderung_pct` (= „ges. %") = `gesamtveraenderung_eur / einstandswert`.
- `gewichtung` = `positionswert / depotbestand`.

### 5.2 Barbestand (Cash-Ledger)
```
barbestand =  Σ Einzahlungen
            − Σ Auszahlungen
            − Σ (Kaufwert inkl. Spesen)
            + Σ (Verkaufserlös − Spesen − Steuer)
            + Σ Dividenden
            + Σ Steuerverrechnungen
```
Deckungsprüfung: Kauf/Auszahlung nur, wenn gedeckt (Konfig-Flag
`barbestand_ueberziehen_erlauben`, Default aus). Jede der Summanden-Quellen ist
editierbar (4.11) → Barbestand ist stets neu berechenbar.

### 5.3 Realisierter Gewinn (FIFO)
Beim Verkauf werden die ältesten offenen Tranchen zuerst verrechnet:
`realisierter_gewinn` = `verkauf_erloes − Σ (verrechnete Einstandskosten) − verkauf_spesen`,
wobei `verkauf_erloes = stueck * verkaufskurs`. FIFO ist Default; als Konfig-Option
`verrechnungsmethode` (FIFO | DURCHSCHNITT) vorsehen.

### 5.4 Depot-Kennzahlen (Dashboard)
- `depotbestand` = Σ `positionswert` aller offenen Positionen.
- `gesamtwert` = `depotbestand + barbestand`.
- `realisierter_gewinn` (Depot) = Σ `Verkauf.realisierter_gewinn`.
- `unrealisierter_gewinn` (= „Performance") = Σ `gesamtveraenderung_eur` der Positionen;
  Prozent = `unrealisierter_gewinn / Σ einstandswert`.
- `gesamtgewinn` = `realisierter_gewinn + unrealisierter_gewinn` (reiner
  Kursgewinn, ohne Dividenden/Steuern — Definition wie im Referenz-Screenshot).
- `dividenden` (eigene KPI) = `Σ Dividende.betrag`.
- `steuern` (eigene KPI) = `Σ Verkauf.steuer − Σ Steuerverrechnung.betrag`
  (netto gezahlte Steuern; positiv = per saldo gezahlt, negativ = per saldo
  erstattet).
- `gesamtergebnis` (Netto-Gesamtrendite) = `gesamtgewinn + dividenden − steuern`.
- `aktuell` = `Σ tagesveraenderung_eur` der Positionen; Prozent = `aktuell / (depotbestand − aktuell)`.

> Konsistenzprüfung aus dem Referenz-Screenshot: `Gesamtgewinn = Realisierter
> Gewinn + Performance` (z. B. `1.695,53 + (−87,71) = 1.607,82`). Diese Identität
> als Test verankern (`REQ-CALC-GESAMT`). Dividenden und Steuern werden bewusst
> **als eigene KPIs** geführt und fließen erst in `gesamtergebnis` zusammen —
> `gesamtgewinn` bleibt unverändert der reine Kursgewinn.

### 5.5 Zeitraum & Bezugsbasis (Chart + Performance)
Für den Wertverlaufs-Chart **und** die Performance-Kennzahlen sind zwei
Einstellungen wählbar (pro Depot, Default aus 4.1; im UI umschaltbar, Auswahl in
der Session gemerkt):

- **Zeitraum:** `SEIT_EROEFFNUNG`, `1M`, `3M`, `6M`, `YTD`, `1J` oder ein
  benutzerdefiniertes Von–Bis. Bestimmt Start-/Endpunkt der ausgewerteten Reihe.
- **Bezugsbasis:**
  - `NUR_WERTPAPIERE` → Auswertung auf der `depotbestand`-Reihe (nur der Kurswert
    der Wertpapiere).
  - `INKL_BARBESTAND` → Auswertung auf der `gesamtwert`-Reihe (Wertpapiere +
    Barbestand).

Datenquelle ist die `DepotBewertung`-Zeitreihe (4.7), die beide Reihen führt — die
Umschaltung wählt nur die Reihe, es ist keine Neuberechnung nötig.

Performance im Zeitraum:
- `wert_start` / `wert_ende` = Wert der gewählten Reihe am Zeitraum-Anfang/-Ende.
- `performance_eur` = `wert_ende − wert_start`; `performance_pct` =
  `wert_ende / wert_start − 1`.

> **Achtung Cashflows:** Ein-/Auszahlungen (und bei `INKL_BARBESTAND` auch
> Dividenden/Steuern) im Zeitraum verzerren die naive Differenz. Erste Version:
> einfache Wertdifferenz mit sichtbarem Hinweis; eine cashflow-bereinigte
> (zeitgewichtete) Rendite ist als Ausbaustufe vorgesehen (siehe 13).

### 5.6 Neuberechnung bei nachträglichen Änderungen
Da Buchungen editierbar sind (4.11), muss abgeleiteter Zustand konsistent bleiben:
- **Sofort neu berechnet** (aus den Buchungen, kein gespeicherter Zustand):
  Barbestand, offene Positionen/FIFO, Positionskennzahlen, Depot-KPIs.
- **`Verkauf.realisierter_gewinn`** wird bei jeder Änderung an betroffenen Käufen/
  Verkäufen desselben Instruments neu ermittelt (FIFO-Reihenfolge nach
  `*_zeitpunkt`).
- **`DepotBewertung`-Zeitreihe:** bei Änderungen an vergangenen Buchungen betroffene
  Tage neu bewerten. Die **historische Bewertung nutzt ausschließlich die
  Tagesschlusskurse** (`Schlusskurs`, 6.9) — es werden keine feineren Intraday-Kurse
  vorgehalten. Ein Wiederaufbau-Lauf (`scripts/bewertungen_neu_aufbauen.py`) baut die
  Reihe ab einem Stichtag aus den `Schlusskurs`-Werten neu auf (bei Fremdwährung mit
  dem jeweiligen Tages-Wechselkurs, 5.7). Fehlt für ein Instrument/Tag ein
  Schlusskurs, wird der letzte bekannte Schlusskurs fortgeschrieben.
- **`DepotSnapshot`** bleibt unverändert (eingefrorener Vergleichszustand).

### 5.7 Fremdwährungsumrechnung
Alle KPIs und Positionswerte werden in der **Basiswährung des Depots**
(`Depot.basiswaehrung`, Default `EUR`) ausgewiesen. Weicht die Währung eines
Instruments (`Instrument.waehrung`) davon ab, werden Kurse/Werte über den
konfigurierten **Fremdwährungs-Provider** (6.10) umgerechnet:
- **Aktuelle Werte:** Umrechnung mit dem jüngsten Wechselkurs (gecacht, Intervall
  konfigurierbar).
- **Historische Bewertung** (Bewertungsreihe/Mini-Chart, 5.6/6.9): mit dem
  **Tages-Wechselkurs** des jeweiligen Tages, sofern der Provider ihn liefert; sonst
  Fortschreibung des letzten bekannten Kurses.
- Fällt der FX-Provider aus, gilt der letzte bekannte Kurs (Kennzeichnung „veraltet");
  ist gar kein Kurs vorhanden, wird der Wert unkonvertiert mit Hinweis angezeigt.

## 6. Kursanbindung — `PriceProvider`-Abstraktion

Kern der App-Architektur. Die Kursbeschaffung ist **vollständig abstrahiert**, damit
weitere Anbieter ohne Eingriff in die Fach- oder UI-Schicht ergänzt werden können.

### 6.1 Schnittstelle
```python
# domain/kurse/price_provider.py
from typing import Protocol
from dataclasses import dataclass
from datetime import datetime, date
from decimal import Decimal

@dataclass(frozen=True)
class Quote:
    kurs: Decimal
    waehrung: str
    boerse: str | None
    zeitstempel: datetime
    vortagesschluss: Decimal | None

class PriceProvider(Protocol):
    name: str                                   # "fmp", "pytr", …
    def get_quote(self, instrument) -> Quote | None: ...
    def get_history(self, instrument, von: date, bis: date) -> list[tuple[date, Decimal]]: ...
```

### 6.2 Routing nach Kategorie
Ein `KursService` (in `services/kurse/`) wählt den Provider anhand von
`instrument.kursgruppe`:

```
kursgruppe == AKTIEN_ETF     → in KursEinstellung[AKTIEN_ETF]   gewählter Provider (initial: fmp)
kursgruppe == HEBELPRODUKT   → in KursEinstellung[HEBELPRODUKT] gewählter Provider (initial: pytr)
```

Provider werden über eine **Registry** (`name → Implementierung`) registriert. Die
**Zuordnung Kursgruppe → Provider, die Credentials und das Abfrageintervall werden
zur Laufzeit über die Setup-Seite (6.6) gepflegt** und in der Entität
`KursEinstellung` gespeichert; die `.env`-Werte (11) dienen nur als Bootstrap-/
Fallback-Default, solange keine `KursEinstellung` existiert. Neue Anbieter = neue
Implementierung + Registry-Eintrag (inkl. Metadaten, 6.6), sonst nichts.

### 6.3 `FmpPriceProvider` (Aktien/ETF)
- Nutzt die FMP-API. ISIN → Symbol via `lookup_isin`/`search_stock`, Ergebnis auf
  `Instrument.symbol` cachen. `get_quote` liefert `price`, `previousClose`
  (→ `vortagesschluss`), `exchange`, `timestamp`.
- **Bekannte Grenze:** Der freie FMP-Tarif deckt US-Listings/OTC ab; native
  deutsche Börsenplätze (`*.DE`) erfordern FMP-Premium (HTTP 402). Strategie:
  bevorzugt das verfügbare Symbol (OTC/US) nutzen; Premium-Bedarf in der README
  als Betriebs-/Kostenhinweis vermerken. `get_history` über den FMP-Historien-Endpoint.

### 6.4 `PytrPriceProvider` (Hebelprodukte)
- Nutzt **pytr** (inoffizieller Trade-Republic-Client). Preis je **ISIN** über die
  Websocket-Subscription (`ticker`/`instrument`); Momentaufnahme entnehmen, dann
  wieder abmelden.
- **Auth:** benötigt echte TR-Zugangsdaten (Telefonnummer + PIN) und 2FA; Session/
  Keyfile serverseitig persistieren (`~/.pytr/credentials` bzw. konfigurierbarer
  Pfad). Zugangsdaten **nur aus der Env/Secrets**, niemals loggen.
- **Async-Brücke:** pytr ist async (websockets). Der Provider kapselt einen
  Event-Loop/Session-Manager und stellt der (synchronen) Service-Schicht eine
  einfache `get_quote`-Methode bereit. Verbindungen bündeln, nicht pro Kurs neu
  aufbauen.
- **Risiken (als Härtungspunkte dokumentieren):** inoffizielle/private API →
  ToS-Fragen, mögliche Änderungen/Abbrüche, Rate-Limits. Nur moderate Poll-Frequenz;
  robust gegen Ausfälle (Fehler → letzter bekannter Kurs bleibt stehen, Status
  „veraltet").

### 6.5 Aktualisierung, Cache, Fehlerverhalten
- **Cache/TTL:** aktueller Kurs wird mit `KURS_CACHE_TTL` (z. B. 60 s) gecacht;
  Anzeige nutzt den jüngsten `Kurs`-Datensatz.
- **Batch-Job:** `scripts/kurse_aktualisieren.py` aktualisiert alle Instrumente in
  offenen Positionen, schreibt nach Börsenschluss je Instrument einen `Schlusskurs`
  (Mini-Charts, 6.9) und zusätzlich täglich eine `DepotBewertung`. Das
  **Abfrageintervall** kommt je Kursgruppe aus `KursEinstellung.abfrage_intervall_sekunden`
  (Setup-Seite, 6.6). Betrieb per Cron/systemd-Timer/NSSM (siehe
  `references/deployment.md`); nicht im Request-Pfad blockierend abrufen.
- **Fehler:** Provider-Ausfall → kein harter Fehler im UI; letzter Kurs mit
  Zeitstempel + „veraltet"-Kennzeichnung anzeigen. Fehler zählen/loggen (ohne Secrets).

### 6.6 Kurs-Setup-Seite (Provider-Konfiguration)
Über das Dashboard erreichbare Setup-Seite. Je **Kursgruppe** (`AKTIEN_ETF`,
`HEBELPRODUKT`) konfigurierbar:
- **Anbieterauswahl** aus den für diese Kursgruppe registrierten Providern.
- **Credentials** hinterlegen (je Provider unterschiedliche Felder — die Registry
  liefert die Feld-Deskriptoren, s. u.).
- **Automatisches Abfrageintervall** (Sekunden/Minuten) für den Batch-Job (6.5).
- Aktiv/inaktiv je Kursgruppe.

Persistiert in Entität **`KursEinstellung`** (global, je Kursgruppe genau eine):
- `id`, `kursgruppe` (eindeutig: `AKTIEN_ETF` | `HEBELPRODUKT`), `provider_name`,
  `credentials_verschluesselt` (verschlüsselte JSON-Zugangsdaten),
  `abfrage_intervall_sekunden`, `aktiv`, `geaendert_am`.

**Provider-Registry mit Metadaten** — jeder Provider deklariert für die Setup-Seite:
- `name`, `anzeigename`, unterstützte Kursgruppen,
- `benoetigte_credentials`: Liste von Feld-Deskriptoren (`schluessel`, `label`,
  `geheim: bool`), damit das UI die Eingabefelder dynamisch rendert:
  - **FMP:** `api_key` (geheim).
  - **pytr:** `telefonnummer`, `pin` (geheim) — zzgl. Authentifizierungs-Flow (s. u.).

**pytr-Authentifizierung als Teil des Setups (verbindlich):** Die Anmeldung bei
Trade Republic wird direkt über die Setup-Seite abgewickelt (der Provider stellt die
nötigen Schritte über die Registry-Metadaten/Service-Hooks bereit):
1. Telefonnummer + PIN eingeben und **Login anstoßen** → Trade Republic sendet einen
   4-stelligen **Bestätigungscode** (App/SMS).
2. Code auf der Setup-Seite eingeben → Session/Keyfile wird **serverseitig**
   angelegt und gehalten (Keyfile-Pfad `PYTR_KEYFILE`; Zugangsdaten verschlüsselt).
3. **Status-Anzeige** „angemeldet / abgelaufen" mit Aktion **„neu anmelden"**, wenn
   die Session abläuft. Ein Verbindungs-/Statustest ist direkt aufrufbar.
Der 2FA-Code selbst wird **nicht** dauerhaft gespeichert.

**Sicherheit (verbindlich):** Credentials werden **verschlüsselt at rest** abgelegt
(symmetrisch, Schlüssel `CREDENTIALS_ENC_KEY` aus der Env — **nicht** in der DB).
Geheime Felder werden im UI **nie zurückgegeben**, nur maskiert („••••") angezeigt;
Speichern überschreibt ein Geheimnis nur bei Neueingabe. Niemals ins Log.

### 6.7 Verfügbarkeitstest (Depot durchtesten)
Test-Funktion (auf der Setup-Seite, optional auch in der Depotansicht): Für ein
gewähltes Depot werden **alle** Instrumente über den je Kursgruppe konfigurierten
Provider abgefragt und das Ergebnis **pro Wertpapier** angezeigt:
- Status (OK / Fehler / nicht verfügbar), abgerufener Kurs + Zeitstempel + Quelle;
  bei Fehler die Ursache (z. B. „Symbol nicht gefunden", „Auth fehlgeschlagen",
  „Premium erforderlich").
- Der Test **schreibt keine** Kurse/Bewertungen — reine Verfügbarkeitsprüfung.
- Zweck: Konfiguration/Credentials und Abdeckung (v. a. Hebelprodukte) vor dem
  Live-Betrieb verifizieren.

Service: `services/kurse.depot_testen(depot_id) -> list[Testergebnis]`.

### 6.8 Manuelle Aktualisierung
In der **Depotansicht** ein Button **„Kurse aktualisieren"**: ruft die Kurse aller
Instrumente des aktuellen Depots sofort über die konfigurierten Provider ab, speichert
den jüngsten `Kurs` je Instrument und aktualisiert KPIs/Anzeige — unabhängig vom
automatischen Intervall. Läuft nicht blockierend, mit Status-/Fortschrittsanzeige;
Fehler je Instrument werden gemeldet, ohne die übrigen zu stoppen.
Service: `services/kurse.depot_aktualisieren(depot_id)`.

### 6.9 Mini-Charts: Tagesschluss-Historie & Backfill
Der Mini-Chart „seit Kauf" je Wertpapier wird aus einer **Tagesschluss-Zeitreihe**
je Instrument gespeist, beginnend beim **Kaufdatum** (`kauf_zeitpunkt` der ältesten
offenen Tranche der Position).

Datenmodell **`Schlusskurs`** (Tagesschlusskurs):
- `id`, `instrument_id` → Instrument, `datum` (eindeutig je Instrument),
  `schlusskurs` (Decimal), `quelle` (`FMP` | `PYTR` | `MANUELL`).

Aufbau der Reihe:
- **Laufender Betrieb:** Der tägliche Batch-Job (6.5) schreibt nach Börsenschluss je
  Instrument in offenen Positionen einen `Schlusskurs` → der Mini-Chart wächst ab dem
  Kaufzeitpunkt Tag für Tag.
- **Kauf mit Datum in der Vergangenheit:** Liegt `kauf_zeitpunkt` vor heute, **fragt
  die App beim Erfassen/Bearbeiten nach**, ob der Mini-Chart mit **historischen
  Tagesschlusskursen** (Kaufdatum → heute) vorbefüllt werden soll:
  - **Ja →** `PriceProvider.get_history(instrument, kaufdatum, heute)` abrufen und die
    Tagesschlusskurse als `Schlusskurs`-Reihe speichern (Backfill).
  - **Nein →** Reihe bleibt leer und füllt sich **ab jetzt** mit Tagesschlusskursen.
- **Verfügbarkeit:** Historie ist für Aktien/ETF (FMP) i. d. R. vorhanden; für
  Hebelprodukte (pytr) oft **lückenhaft/nicht verfügbar**. Kann der Provider keine
  Historie liefern, wird das gemeldet und automatisch auf „vorwärts füllen"
  zurückgefallen (kein harter Fehler).
- **Idempotenz:** `Schlusskurs` ist je (Instrument, Datum) eindeutig; erneuter
  Backfill/Batch überschreibt bzw. überspringt bestehende Tage.

Services: `services/kurse.schlusskurse_backfill(instrument_id, von, bis)` und
`services/kurse.mini_chart(instrument_id, ab_datum) -> list[(datum, kurs)]`.

### 6.10 Fremdwährung — `ExchangeRateProvider`-Abstraktion
Analog zur Kursanbindung: austauschbare **Fremdwährungs-Provider**, die im
Setup-Bereich (6.6) gewählt und konfiguriert werden. Initial: **FMP**.

Schnittstelle:
```python
# domain/waehrung/exchange_rate_provider.py
from typing import Protocol
from datetime import date
from decimal import Decimal

class ExchangeRateProvider(Protocol):
    name: str                                        # "fmp", …
    def get_rate(self, von: str, nach: str, am: date | None = None) -> Decimal | None: ...
    def get_rate_history(self, von: str, nach: str, ab: date, bis: date) -> list[tuple[date, Decimal]]: ...
```

- **Registry + Metadaten** wie bei den Kursanbietern (`name`, `anzeigename`,
  `benoetigte_credentials`). FMP: `api_key` (geheim).
- **Konfiguration** in Entität **`WaehrungsEinstellung`** (global, genau eine):
  `id`, `provider_name`, `credentials_verschluesselt`, `abfrage_intervall_sekunden`,
  `aktiv`, `geaendert_am`. Verschlüsselung/Maskierung der Credentials wie in 6.6.
- **Nutzung:** `services/waehrung.umrechnen(betrag, von, nach, am=None)` liefert die
  Umrechnung (5.7); Kurse werden gecacht (Intervall aus `WaehrungsEinstellung`).
- **Fehlerverhalten:** wie bei Kursen — letzter bekannter Kurs + „veraltet", kein
  harter Fehler.
- **Erweiterbarkeit:** neuer FX-Anbieter = neue Implementierung + Registry-Eintrag,
  im Setup auswählbar. Keine Änderung an Fach-/UI-Schicht nötig.

## 7. Features / Funktionsumfang

**Depot-Übersicht (Start-Dashboard über alle Depots)**
- Einstiegsseite: Liste **aller** Depots mit den wichtigsten KPIs je Depot
  (Gesamtwert, Depotbestand, Barbestand, Gesamtgewinn, Performance, Gesamtergebnis)
  und Gesamtsummen über alle Depots.
- Depots hier **anlegen, bearbeiten, löschen**; per Klick/Dropdown ins Einzeldepot
  wechseln (aktuelles Depot in der Session gemerkt).

**Einzeldepot-Dashboard**
- KPI-Kacheln (5.4) inkl. der eigenen KPIs **Dividenden** und **Steuern**, mit
  „Mehr/Weniger Details"-Umschaltung.
- Wertverlaufs-Chart (Chart.js) aus `DepotBewertung` mit **einstellbarem Zeitraum**
  und **Bezugsbasis** (nur Wertpapiere / inkl. Barbestand) — dieselbe Auswahl steuert
  die zeitraumbezogenen Performance-Kennzahlen (5.5).

**Positionen & Handel**
- „Wert hinzufügen" (Kauf): Instrument per ISIN/WKN/Name suchen oder neu anlegen
  (Kategorie wählen), dann Stück, Kaufkurs, Zeitpunkt, Spesen, Börse.
- **Mini-Chart „seit Kauf"**: startet beim Kaufdatum. Liegt das Kaufdatum in der
  Vergangenheit, **fragt die App nach**, ob mit historischen Tagesschlusskursen
  vorbefüllt werden soll; andernfalls Aufbau ab jetzt mit Tagesschlusskursen (6.9).
- Tranchen-genaue Positionsführung; Positionszeile aufklappbar in die Einzelkäufe.
- Verkauf (Teil-/Gesamt) mit realisiertem Gewinn (FIFO); Spesen und **gezahlte
  Steuer** erfassbar.
- **Dividende** je Wertpapier erfassen → Gutschrift auf den Barbestand, fließt in
  die Dividenden-KPI.
- **Steuerverrechnung** je Depot erfassen → Gutschrift auf den Barbestand, fließt in
  die Steuern-KPI.
- Ein-/Auszahlungen (verändern den Barbestand).
- Kontextmenü je Zeile: nachkaufen, verkaufen, bearbeiten, löschen, Details.

**Bearbeiten von Buchungen**
- **Jede** Buchung (Kauf, Verkauf, Zahlung, Dividende, Steuerverrechnung) ist
  nachträglich **editier- und löschbar**, inklusive Zeitpunkt (Kauf-/Verkaufs-
  zeitpunkt). Änderungen lösen die Neuberechnung aller abgeleiteten Werte aus (5.6).

**Snapshots & Vergleich**
- Benannte **Snapshots** eines Depots manuell erstellen (friert KPIs + Positionen
  ein) und **zwei Snapshots vergleichen** (Differenz der KPIs und je Position).

**Ansichten (Tabs)**
- **Bestand** — offene Positionen (aggregiert, aufklappbar) mit allen Spalten aus
  dem Screenshot (Stück, Kaufkurs/Datum, Kaufwert/Spesen, Mini-Chart, aktueller
  Kurs/Börse/Zeit, akt. EUR/%, ges. EUR/%, Wert/Gewichtung).
- **Verkäufe** — alle Verkäufe mit realisiertem Gewinn und gezahlter Steuer.
- **Transaktionen** — chronologisches Gesamt-Ledger (Käufe, Verkäufe,
  Ein-/Auszahlungen, Dividenden, Steuerverrechnungen); jede Zeile editierbar.
- Sortierung/Filter; Spaltenauswahl in den Einstellungen.

**Setup: Kurse, Fremdwährung & Aktualisierung**
- **Setup-Seite** (übers Dashboard erreichbar): je Wertpapier-Kategorie einen der
  verfügbaren Kursanbieter wählen, Credentials hinterlegen (verschlüsselt) und das
  automatische Abfrageintervall festlegen (6.6); ebenso einen **Fremdwährungs-
  Provider** wählen/konfigurieren (6.10).
- **pytr-Anmeldung** direkt im Setup: Login anstoßen, 2FA-Code eingeben,
  Session-Status sehen und bei Bedarf neu anmelden (6.6).
- **Verfügbarkeitstest**: alle Werte eines gewählten Depots abfragen und je
  Wertpapier anzeigen, ob ein Kurs verfügbar ist (6.7).
- **Manueller „Kurse aktualisieren"-Button** in der Depotansicht (6.8), zusätzlich
  zum geplanten Batch-Job.

**Daten & Export**
- Kursaktualisierung manuell auslösbar + geplanter Batch-Job.
- Export/Download als **xlsx** (openpyxl), **CSV** und **PDF** (Jinja-Template +
  Print-CSS) — Bestand, Verkäufe, Transaktionen, Depotübersicht, Snapshot-Vergleich.
- Einstellungen: Verrechnungsmethode, Standard-Zeitraum & -Bezugsbasis, Spaltenwahl,
  Kurs-TTL, Provider-Zuordnung je Kursgruppe.

**Optional / später** (Nicht-Ziele der ersten Version, siehe 12): Benchmark-Vergleich,
cashflow-bereinigte (zeitgewichtete) Rendite, Kurs-Alarme, Broker-/CSV-Import.

## 8. Seiten, Routen & Services

Dünne Blueprints → Service-Packages → Repositories (siehe `references/architecture.md`).
Feature-Blueprints sind depot-scoped (`/depots/<int:depot_id>/…`), analog dem
`get_project_or_404`-Muster (hier `get_depot_or_404`).

**Blueprints (`blueprints/`)**
- `uebersicht` — **Start-Dashboard über alle Depots** (KPIs je Depot + Gesamtsummen),
  Depot anlegen/bearbeiten/löschen. Nicht depot-scoped (Wurzel `/`).
- `depots` — Einzeldepot-Dashboard (KPIs + Chart mit Zeitraum/Bezugsbasis),
  Depot-Wechsel, Depot-Einstellungen.
- `bestand` — Positions-/Tranchenansicht (Tab „Bestand").
- `kaeufe` — „Wert hinzufügen" (Kauf erfassen/bearbeiten/löschen, inkl. Zeitpunkt).
- `verkaeufe` — Verkauf erfassen/bearbeiten (inkl. Spesen, Steuer); Tab „Verkäufe".
- `zahlungen` — Ein-/Auszahlungen (erfassen/bearbeiten/löschen).
- `dividenden` — Dividende je Wertpapier erfassen/bearbeiten/löschen.
- `steuern` — Steuerverrechnungen erfassen/bearbeiten/löschen.
- `transaktionen` — Gesamt-Ledger (Tab „Transaktionen"), Einstieg zum Bearbeiten.
- `snapshots` — Snapshot erstellen, auflisten, zwei Snapshots vergleichen.
- `instrumente` — Instrumentensuche/-anlage (ISIN/WKN/Name), Kategorie-Zuordnung.
- `kurse` — manuellen „Kurse aktualisieren"-Button der Depotansicht bedienen (6.8),
  Kursstatus.
- `kurs_setup` — Setup-Seite: Kursanbieter je Kursgruppe (6.6), pytr-Anmeldung/2FA,
  Fremdwährungs-Provider (6.10), Credentials/Intervall + Verfügbarkeitstest (6.7).
  Nicht depot-scoped; vom Dashboard verlinkt.
- `export` — xlsx/CSV/PDF-Downloads.
- `einstellungen` — App-/Anzeige-Einstellungen.
- `pwa` — Service Worker + Offline-Seite (siehe `references/pwa.md`).

**Service-Packages (`services/`)** — je Feature `__init__.py` (Re-Export) +
`service.py` (über Repositories) + `helpers.py` (parse/validate/format):
- `services/depots/` — CRUD, `depot_kennzahlen(depot_id)`,
  `verlauf(depot_id, zeitraum, bezugsbasis)`, `alle_depots_kennzahlen()` (Übersicht).
- `services/positionen/` — Aggregation offener Tranchen, Positionskennzahlen (5.1).
- `services/kaeufe/`, `services/verkaeufe/` — Erfassen/Bearbeiten inkl. FIFO-Verrechnung.
- `services/zahlungen/` — Cash-Buchungen, `barbestand(depot_id)`.
- `services/dividenden/` — Dividenden erfassen/bearbeiten, `dividenden_summe(depot_id)`.
- `services/steuern/` — Steuerverrechnungen + `steuern_saldo(depot_id)` (5.4).
- `services/snapshots/` — `snapshot_erstellen(depot_id)`, `vergleich(a_id, b_id)`.
- `services/instrumente/` — Suche/Anlage, Kategorie→Kursgruppe.
- `services/kurse/` — `KursService` (Provider-Routing + Registry/Metadaten, Cache),
  `aktueller_kurs`, `kurshistorie`, `bewertung_schreiben`,
  `bewertungen_neu_aufbauen(depot_id, ab)`; Konfiguration:
  `einstellung_lesen / einstellung_speichern(kursgruppe, …)` (Credentials ver-/entschlüsseln),
  `depot_testen(depot_id)` (6.7), `depot_aktualisieren(depot_id)` (6.8),
  `schlusskurse_backfill(instrument_id, von, bis)` und
  `mini_chart(instrument_id, ab_datum)` (6.9); pytr-Anmeldung/Session-Handling (6.6).
- `services/waehrung/` — `ExchangeRateProvider`-Routing + Registry/Metadaten,
  `umrechnen(betrag, von, nach, am=None)`, Cache, Konfiguration lesen/speichern
  (6.10).
- `services/export/` — xlsx/CSV/PDF-Aufbereitung.

Übergreifend: ein `services/neuberechnung/` (oder Methode in den Buchungs-Services)
kapselt die Neuberechnung nach Änderungen (5.6). Konvention `count_incomplete_<feature>`
aus dem Skill sinngemäß, z. B. `services/kurse.veraltete_kurse(depot_id) -> int` für
ein „Kurse veraltet"-Badge.

## 9. MCP-Server

Verpflichtend (siehe `references/mcp-server.md`). Da Einzelnutzer ohne Login, wird
das per-User-Bearer-Modell auf **einen statischen Bearer-Key aus der Env**
(`MUSTERDEPOT_MCP_KEY`) reduziert; weiterhin nur hinter TLS betreiben. Der Server
importiert die Service-Schicht direkt (nie HTTP zur Web-App).

**Tools (inkrementell freischalten):**
- Read: `list_depots`, `uebersicht` (KPIs aller Depots + Gesamtsummen),
  `get_depot(depot_id)` (KPIs inkl. Dividenden/Steuern), `list_positionen(depot_id)`,
  `list_verkaeufe(depot_id)`, `list_transaktionen(depot_id)`,
  `list_dividenden(depot_id)`, `list_snapshots(depot_id)`, `get_kurs(isin)`,
  `get_wechselkurs(von, nach)`, `whoami` (Verbindungstest).
- Reporting: `depot_zusammenfassung(depot_id)`, `gewichtung(depot_id)`,
  `performance(depot_id, zeitraum, bezugsbasis)`,
  `snapshot_vergleich(a_id, b_id)`, `kurse_testen(depot_id)` (Verfügbarkeitstest, 6.7).
- Writes (Phase 2): `kauf_erfassen`, `verkauf_erfassen` (inkl. Steuer),
  `einzahlung`, `auszahlung`, `dividende_erfassen`, `steuerverrechnung_erfassen`,
  `buchung_bearbeiten`, `buchung_loeschen`, `snapshot_erstellen`,
  `instrument_anlegen`, `kurse_aktualisieren` — wiederverwenden die
  `parse_*`/`validate_*` der jeweiligen Services (gleiche Validierung + Neuberechnung
  wie das UI).

## 10. Tests & Requirements

Volle Pyramide + Requirements-Traceability (siehe `references/testing.md`). Wichtige
Requirement-IDs (nicht abschließend):
- `REQ-CALC-FIFO` — realisierter Gewinn per FIFO korrekt (inkl. Teilverkäufe, Spesen).
- `REQ-CALC-POS` — Positionskennzahlen (Wert, akt./ges. EUR & %, Gewichtung).
- `REQ-CALC-GESAMT` — `Gesamtgewinn = Realisierter + Unrealisierter Gewinn`.
- `REQ-CALC-ERGEBNIS` — `Gesamtergebnis = Gesamtgewinn + Dividenden − Steuern`.
- `REQ-CASH-LEDGER` — Barbestand = Cash-Ledger inkl. Dividenden (+), Verkaufssteuer
  (−) und Steuerverrechnung (+); Deckungsprüfung bei Kauf/Auszahlung.
- `REQ-DIV-KPI` — Dividende schreibt Barbestand gut und erscheint in der Dividenden-KPI.
- `REQ-TAX-KPI` — Verkaufssteuer mindert Barbestand, Steuerverrechnung schreibt gut;
  Steuern-KPI = gezahlt − verrechnet.
- `REQ-RANGE-BASIS` — Zeitraum- und Bezugsbasis-Umschaltung liefert korrekte
  Chart-/Performance-Werte aus der `DepotBewertung`-Reihe (beide Basen).
- `REQ-EDIT-RECALC` — nachträgliche Änderung/Löschung einer Buchung (inkl. Zeitpunkt)
  berechnet Barbestand, FIFO und realisierte Gewinne korrekt neu.
- `REQ-SNAPSHOT` — Snapshot friert KPIs/Positionen ein; Vergleich zweier Snapshots
  liefert korrekte Differenzen; Snapshot bleibt unverändert.
- `REQ-UEBERSICHT` — Depot-Übersicht summiert KPIs je Depot und über alle Depots korrekt.
- `REQ-PRICE-ROUTING` — Aktien/ETF → FMP, Hebelprodukt → pytr (Kategorie steuert Provider).
- `REQ-PRICE-FALLBACK` — Provider-Ausfall → letzter Kurs + „veraltet", kein Absturz.
- `REQ-PRICE-EXT` — neuer Provider ist ohne Änderung an Services/UI registrierbar (Fake-Provider-Test).
- `REQ-KURS-SETUP` — Provider/Intervall je Kursgruppe persistiert; Credentials
  verschlüsselt gespeichert, geheime Felder werden nie im Klartext zurückgegeben.
- `REQ-KURS-TEST` — Verfügbarkeitstest fragt alle Depot-Instrumente ab, meldet Status
  je Wertpapier und schreibt dabei keine Kurse/Bewertungen.
- `REQ-KURS-MANUELL` — manueller Refresh aktualisiert alle Kurse des Depots sofort;
  Einzelfehler blockieren die übrigen nicht.
- `REQ-CHART-FORWARD` — Mini-Chart füllt sich im Betrieb ab Kaufdatum mit
  Tagesschlusskursen (`Schlusskurs`), eindeutig je (Instrument, Datum).
- `REQ-CHART-BACKFILL` — bei Kaufdatum in der Vergangenheit wird nachgefragt; „Ja"
  befüllt historische Tagesschlusskurse, „Nein"/fehlende Historie fällt sauber auf
  Vorwärtsfüllen zurück.
- `REQ-FX-PROVIDER` — Fremdwährungs-Provider ist im Setup wählbar/konfigurierbar und
  ohne Änderung an Fach-/UI-Schicht austauschbar (Fake-Provider-Test).
- `REQ-FX-CONVERT` — Instrument in Fremdwährung wird korrekt in die Depot-Basiswährung
  umgerechnet; Provider-Ausfall → letzter Kurs + „veraltet".
- `REQ-REVAL-CLOSE` — Neuaufbau der Bewertungsreihe nach Änderung zurückliegender
  Buchungen nutzt ausschließlich `Schlusskurs` (+ Tages-FX); fehlende Tage werden
  fortgeschrieben.
- `REQ-SEC-CREDS` — TR-Zugangsdaten/Keys erscheinen nicht in Logs/Fehlermeldungen
  und liegen in der DB nur verschlüsselt (Schlüssel aus der Env).
- `REQ-PWA-01/02/03` — Manifest, `sw.js` (Header), Offline-Seite erreichbar (siehe `pwa.md`).

Provider gegen **Fakes** testen (kein echter FMP-/TR-Zugriff in der CI). Dual-Backend
(SQLite/MariaDB) wie im Skill.

## 11. Konfiguration (`.env`)

```dotenv
# Datenbank & App
DB_BACKEND=sqlite
DB_URL=sqlite:///./musterdepot.sqlite
SECRET_KEY=<zufällig, 32 Byte>
LOG_LEVEL=INFO

# Verschlüsselung der in der DB gespeicherten Provider-Credentials (Setup-Seite 6.6)
CREDENTIALS_ENC_KEY=<32-Byte-Schlüssel, nur in der Env>

# Kurs-Provider — Routing, Credentials und Intervall werden vorrangig über die
# Setup-Seite (6.6) in der DB (KursEinstellung) gepflegt. Die folgenden Werte sind
# nur Bootstrap-/Fallback-Defaults, solange keine KursEinstellung existiert.
PROVIDER_AKTIEN_ETF=fmp
PROVIDER_HEBELPRODUKT=pytr
KURS_CACHE_TTL=60

# FMP (Fallback/Bootstrap) — für Kurse (Aktien/ETF) und Fremdwährung
FMP_API_KEY=<key>

# Fremdwährungs-Provider (Fallback/Bootstrap; vorrangig via Setup-Seite 6.10)
FX_PROVIDER=fmp

# pytr / Trade Republic (Fallback/Bootstrap; Secrets! nie ins Log)
PYTR_PHONE_NO=+49...
PYTR_PIN=<pin>
PYTR_KEYFILE=/srv/musterdepot/.pytr/credentials

# MCP-Server
MUSTERDEPOT_MCP_KEY=<statischer Bearer-Key>
MUSTERDEPOT_MCP_HOST=127.0.0.1
MUSTERDEPOT_MCP_PORT=8000
```

Zusätzliche Laufzeit-Abhängigkeiten gegenüber dem Skill-`requirements.txt`:
`pytr` (Trade-Republic-Client) und ein HTTP-Client für FMP (z. B. `httpx`).

## 12. Nicht-Ziele (erste Version)

- Keine echten Orders/Broker-Anbindung; reines Musterdepot.
- Keine Anlageberatung, keine Kauf-/Verkaufsempfehlungen.
- **Keine automatische Steuerberechnung.** Steuern werden vom Nutzer erfasst
  (Verkaufssteuer, Steuerverrechnung) — die App rechnet keine Abgeltungssteuer aus.
- Keine automatische Dividenden-Ermittlung; Dividenden werden manuell erfasst
  (die Beträge kommen vom Nutzer, nicht aus einer Datenquelle).
- Keine Mehrbenutzer-/Rechteverwaltung (Einzelnutzer).
- Kein Benchmark, keine Kurs-Alarme, keine cashflow-bereinigte Rendite (spätere
  Ausbaustufen).

## 13. Offene Punkte

- **FX/Fremdwährung:** Umrechnung ist über austauschbare `ExchangeRateProvider`
  (6.10, initial FMP) gelöst; offen bleibt nur, wie tief **historische Tages-
  Wechselkurse** für den Neuaufbau vorgehalten werden.
- **Kurshistorie für Hebelprodukte:** Der Backfill (6.9) funktioniert für Aktien/ETF
  (FMP-Historie); für Warrants/Knock-Outs (pytr) ist Historie oft nicht abrufbar —
  dann füllt sich der Mini-Chart erst mit der Laufzeit der App (Tagesschlusskurse).
  Wie tief Historie generell vorgehalten wird, bleibt festzulegen.
- **Trade-Republic-Stabilität/ToS:** Abhängigkeit von einer inoffiziellen API; Fallback
  auf manuelle Kurspflege als Notnagel vorsehen (Provider `MANUELL` existiert im
  `Kurs.quelle`-Enum bereits).
- **pytr-Session-Lebensdauer:** Der Anmelde-/2FA-Ablauf ist im Setup abgebildet
  (6.6); offen bleibt die konkrete Session-Lebensdauer und wie oft ein Re-Login
  praktisch nötig wird.
- **FMP-Premium:** deutsche Börsenplätze nur im Bezahltarif — Betriebsentscheidung.
- **Zeitgewichtete Rendite:** naive Wertdifferenz im Zeitraum (5.5) wird durch
  Ein-/Auszahlungen (und bei `INKL_BARBESTAND` durch Dividenden/Steuern) verzerrt;
  eine cashflow-bereinigte Kennzahl (z. B. TWR/MWR) ist als Ausbaustufe offen.
- **Neuaufbau der Bewertungsreihe:** Grundsatz ist geklärt — der Neuaufbau nutzt
  ausschließlich die vorgehaltenen **Tagesschlusskurse** (`Schlusskurs`, 5.6/6.9);
  offen bleibt nur die Rückreichweite bei lückenhafter Hebelprodukt-Historie.

## 14. Umsetzungsreihenfolge (Mapping auf den Skill-Workflow)

1. Namen/Domäne fixieren (Tool-Name `Musterdepot`), Config = pydantic-settings,
   **kein** Auth, **PWA = ja**.
2. Grundgerüst (`create_app()`, `run.py`, `wsgi.py`, requirements, `.env.example`, CI).
3. Persistenz: Entities (4), Repositories, Alembic `0001_initial`.
4. Config (pydantic-settings). Kein Auth-Setup.
5. Durchstich „Kauf → Bestand": Instrument anlegen → Kauf erfassen → Positionsansicht
   mit Kennzahlen (5.1) und Depot-KPIs (5.4).
6. Kursanbindung: `PriceProvider`-Abstraktion + Registry (inkl. Metadaten),
   `FmpPriceProvider`, `PytrPriceProvider` (inkl. Anmelde-/2FA-Flow), `KursService`-
   Routing, Cache; `ExchangeRateProvider` (FMP) + Fremdwährungsumrechnung (5.7/6.10);
   Setup-Seite (Kurs- & FX-Provider, Credentials verschlüsselt, Intervall),
   Verfügbarkeitstest, manueller Refresh-Button; Batch-Job + `Schlusskurs` +
   `DepotBewertung`.
7. Verkauf (FIFO, inkl. Steuer), Zahlungen, Dividenden, Steuerverrechnungen; Barbestand-
   Ledger (5.2) und KPIs Dividenden/Steuern/Gesamtergebnis (5.4).
8. Bearbeiten/Löschen aller Buchungen (inkl. Zeitpunkt) + Neuberechnung (5.6);
   Tabs Verkäufe/Transaktionen.
9. Zeitraum- & Bezugsbasis-Umschaltung für Chart und Performance (5.5).
10. Depot-Übersicht (Start-Dashboard über alle Depots, CRUD) + Snapshots & Vergleich.
11. Export (inkl. Snapshot-Vergleich).
12. PWA (Manifest, Service Worker, Icons, `base.html`, Access-Allowlist — hier
    trivial, da kein Login).
13. MCP-Server (Read → Reporting → Writes) mit statischem Bearer-Key.
14. Tests (10) inkl. Provider-Fakes; README + `docs/`.
15. Deployment/CI; Kurs-/Bewertungsjob als Dienst einrichten.
