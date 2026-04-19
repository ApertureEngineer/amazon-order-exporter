# amazon-order-exporter

Kleines privates Python-Repo, um Produktdaten aus dem Amazon-Bestellverlauf eines normalen Privatkontos nach Excel zu exportieren.

## Ziel

Dieses Repo lädt **nur Bestelldaten und Produkttitel**.

Es macht **keine** fachliche Klassifizierung wie `Privat` / `Gewerbe`. Diese Zuordnung kann später manuell oder in einem separaten Repo erfolgen.

## Features

- manueller Login mit lokaler Session-Datei
- Export eines Geschäftsjahres oder eines frei gewählten Datumsbereichs
- Produkttitel aus Bestellübersicht und Bestelldetails
- Ausgabe nach Excel (`orders`, `items`) und CSV
- Debug-HTML optional für Selektor-Anpassungen

## Setup

```bash
python -m venv .venv
```

### Windows

```bash
.venv\Scripts\activate
pip install -e .
playwright install chromium
```

### Linux / macOS

```bash
source .venv/bin/activate
pip install -e .
playwright install chromium
```

## 1) Session speichern

```bash
amazon-order-exporter login --domain amazon.de
```

Dann öffnet sich Chromium. Du meldest dich einmal manuell an und bestätigst anschließend im Terminal mit Enter.

Die Session wird lokal gespeichert unter:

```text
.secrets/amazon_state.json
```

## 2) Export eines Jahres

```bash
amazon-order-exporter export --year 2025 --domain amazon.de --output data/output/amazon_orders_2025.xlsx
```

## 3) Export eines Datumsbereichs

```bash
amazon-order-exporter export --date-from 2025-01-01 --date-to 2025-12-31 --domain amazon.de --output data/output/amazon_orders_2025.xlsx
```

## Ergebnis

Die Excel-Datei enthält zwei Sheets:

- `orders`: eine Zeile pro Bestellung
- `items`: eine Zeile pro Produkt

Typische Spalten:

- `order_id`
- `order_date`
- `order_total_text`
- `status_text`
- `detail_url`
- `item_title`
- `product_url`

Zusätzlich werden CSV-Dateien erzeugt:

- `amazon_orders_2025.orders.csv`
- `amazon_orders_2025.items.csv`

## Hinweise

- Amazon ändert gelegentlich HTML und Button-Texte. Dann müssen in `scraper.py` Selektoren angepasst werden.
- Das Repo speichert **keine Zugangsdaten**, sondern nur den angemeldeten Browser-Status.
- `.secrets/` gehört nicht ins Remote-Repo.

## Nächste sinnvolle Schritte

- erster Realtest mit 2025
- falls nötig Selektoren feinjustieren
- danach Import in dein Haushaltsbuch
