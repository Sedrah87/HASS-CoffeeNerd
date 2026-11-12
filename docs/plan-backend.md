# Detailplan: Backend und erste Version

Stand: 2026-11-12. Ziel der ersten Version: Die CoffeeNørd-App lädt Brews in die eigene
Home-Assistant-Instanz hoch. Dort gibt es eine Shot-Liste mit Filtern und eine Detailansicht mit Kurven.

Festgelegt:
- Lizenz: PolyForm Noncommercial 1.0.0
- Diagramme: ECharts
- keine Shot-Bilder
- kein Code aus der App (GPLv3) oder aus visualizer.coffee, gemeinsam ist nur das JSON-Format

## Umfang

| In Version 1 | Später (Schema ist vorbereitet) |
|---|---|
| Shots annehmen, einzeln und als Batch (Upsert) | mehrere Shots übereinanderlegen |
| Speicherung in SQLite | Lovelace-Karte |
| Sensor „letzter Shot“, Event `coffeenord_shot_received` | Notizen und Bewertung in HASS bearbeiten |
| Panel „Shots“: Liste, Filter, Detailansicht mit Kurven | Export, Teilen per Link (`share_token`) |
| Shot löschen (nur Admin) | Shot-Bilder |

## Repo-Aufbau

```
custom_components/coffeenord/
  __init__.py        Setup: Datenbank öffnen, Views, WebSocket und Panel registrieren
  manifest.json      domain coffeenord, config_flow, single_config_entry, iot_class local_push
  config_flow.py     Einrichtung ohne Eingaben (nur eine Instanz)
  const.py
  models.py          Payload prüfen (voluptuous) und in Zusammenfassung + Kurven umrechnen
  store.py           SQLite-Zugriff, läuft im Executor und blockiert den Event-Loop nicht
  http.py            HomeAssistantView für den Upload
  websocket.py       WebSocket-Commands für das Panel
  sensor.py          sensor.coffeenord_letzter_shot
  frontend/          gebautes Panel-Bundle (aus frontend/ erzeugt, wird mit eingecheckt)
  translations/      de.json, en.json
frontend/            Quellcode des Panels (TypeScript, Lit, ECharts, Vite)
tests/               pytest mit pytest-homeassistant-custom-component
hacs.json, README.md, THIRD_PARTY_NOTICES.md
```

## Schnittstelle App → HASS

Authentifizierung: HASS-Long-Lived-Token als `Authorization: Bearer …`. Das ist derselbe Token
wie für die Mühlen-Steckdose, also kein eigenes Login.

`POST /api/coffeenord/shots` (ein Shot) und `POST /api/coffeenord/shots/batch` (`{"shots": [...]}`,
höchstens 20 pro Request). Ein Shot ist ein Umschlag um das vorhandene Visualizer-JSON:

```json
{
  "schema_version": 1,
  "shot_id": "<brew.config.uuid>",
  "brewed_at": 1762941151,
  "updated_at": 1762941300,
  "visualizer": { "bean": {}, "brew": {}, "mill": {}, "preparation": {}, "water": {},
                  "brewFlow": {}, "application": "COFFEENORD" },
  "bean2": { "name": "...", "roaster": "...", "weight_in": 9.0 }
}
```

- `shot_id` ist Pflicht und bleibt dauerhaft der Schlüssel. Ein erneuter Upload überschreibt den Shot.
  Ist `updated_at` nicht neuer als der gespeicherte Wert, wird nichts geändert (`unchanged`).
- `brewed_at` und `updated_at` sind Unix-Sekunden aus `brew.config`. Die Kurven enthalten in
  `timestamp` nur die Uhrzeit, darum kommt das Datum ausschließlich aus `brewed_at`.
- `bean2` gibt es nur bei Blend-Shots, weil das Visualizer-Format nur eine Bohne kennt.
- `brewFlow` darf fehlen oder leer sein, z. B. bei alten Filter-Brews oder ohne Waage. Der Shot
  wird trotzdem gespeichert, dann eben ohne Kurven.
- Unbekannte Felder werden nicht abgelehnt, sie bleiben im Rohdatensatz erhalten. So kann die App
  neue Felder senden, ohne dass die Integration vorher angepasst werden muss.
- Antwort: `{"shot_id": "...", "status": "created" | "updated" | "unchanged"}`. Beim Batch kommt
  eine Liste mit einem Eintrag pro Shot zurück. Fehlerhafte Shots bekommen `"status": "error"`
  mit Grund, die übrigen werden trotzdem gespeichert.
- Grenzen: höchstens 2 MB pro Shot und 20 Shots pro Batch, sonst antwortet die Integration mit HTTP 413.

## Speicherung

SQLite unter `<config>/coffeenord/shots.db` im WAL-Modus. Alle Zugriffe laufen über
`hass.async_add_executor_job`.

Tabelle `shots`:

| Spalte | Inhalt |
|---|---|
| `id` TEXT PK | Brew-UUID |
| `schema_version` INT | Version des Payloads |
| `brewed_at`, `updated_at`, `received_at` INT | Unix-Sekunden |
| `bean_name`, `bean_roaster`, `bean2_name` | für Filter und Liste |
| `mill_name`, `preparation_name`, `preparation_style` | für Filter und Liste |
| `grind_size`, `dose_g`, `yield_g`, `brew_time_s`, `ratio`, `tds`, `ey`, `rating` | Kennzahlen |
| `peak_pressure`, `has_curves` | aus den Kurven berechnet |
| `curves` TEXT | aufbereitete Kurven als JSON (siehe unten) |
| `payload` TEXT | vollständiger Rohdatensatz, wie hochgeladen |
| `share_token` TEXT NULL UNIQUE | für späteres Teilen, vorerst immer leer |

Dazu eine Tabelle `meta` (`key`, `value`) mit `db_version`, damit spätere Schema-Änderungen per
Migration laufen. Indizes auf `brewed_at`, `bean_name`, `mill_name` und `preparation_name`.

Aufbereitete Kurven: Jede Reihe wird als `[[sekunden, wert], ...]` gespeichert, mit `sekunden` aus
`brew_time` als Zahl. Reihen: `weight` (`actual_weight`), `flow` (`realtimeFlow.flow_value`),
`pressure` (`actual_pressure`), `temperature` (`actual_temperature`), dazu bei Bedarf `weight2`
und `flow2`. `ratio` wird nur berechnet, wenn Dosis und Ausbeute größer als 0 sind.

## WebSocket-Commands (für das Panel)

- `coffeenord/shots/list`: Filter (`bean`, `mill`, `preparation`, `from`, `to`), `limit`
  (Standard 50) und `offset`, sortiert nach `brewed_at` absteigend. Liefert nur die Zusammenfassung
  ohne Kurven, dazu die Gesamtanzahl.
- `coffeenord/shots/get`: ein Shot mit Zusammenfassung und Kurven.
- `coffeenord/filters`: die vorhandenen Bohnen, Mühlen und Zubereitungen für die Auswahllisten.
- `coffeenord/shots/delete`: nur für Admins.

## Sensor und Event

- `sensor.coffeenord_letzter_shot`: Der Zustand ist der Zeitpunkt des neuesten Shots
  (`device_class: timestamp`). Als Attribute kommen Bohne, Mühle, Zubereitung, Dosis, Ausbeute,
  Zeit, Ratio, Mahlgrad und Spitzendruck dazu.
- Event `coffeenord_shot_received` mit `shot_id` und den Kennzahlen. Es wird **nur für neue Shots
  ausgelöst, deren `brewed_at` höchstens 1 Stunde zurückliegt**. Der Erst-Import Hunderter alter
  Brews würde sonst Automationen (z. B. „Maschine in den Standby“) hundertfach starten.

## Panel „Shots“

Das Panel ist über `panel_custom` in der Seitenleiste registriert und nur für Admins sichtbar.
Es wird mit Lit und ECharts gebaut, Vite erzeugt daraus ein einzelnes Bundle. Die Liste hat Filter
oben und lädt beim Scrollen nach. Die Detailansicht zeigt die Kennzahlen und darunter ein Diagramm:
Gewicht und Fluss auf der linken Achse, Druck und Temperatur auf der rechten, mit Zoom und Tooltip.
Shots ohne Kurven zeigen nur die Kennzahlen. Die Oberfläche ist auf Deutsch und Englisch verfügbar,
die Sprache richtet sich nach HASS.

## Qualität und CI

- Python: `ruff` und `pytest` mit `pytest-homeassistant-custom-component`. Getestet werden die
  Payload-Prüfung, die Kurvenaufbereitung, Upsert und `unchanged`, Batch mit fehlerhaften Einträgen,
  die Grenzen, die 1-Stunden-Regel fürs Event und die WebSocket-Filter.
- Frontend: `tsc`, `eslint`, Build.
- Lizenzprüfung der Abhängigkeiten mit `pip-licenses` und `license-checker`. Erlaubt sind nur
  MIT, BSD, Apache-2.0 und ISC, alles andere lässt den Build scheitern.
- Die GitLab-CI bekommt eine Stage `testen` zwischen `pruefen` und `spiegeln`. `hassfest` und die
  HACS-Validierung laufen als GitHub Action auf dem Spiegel.
- `THIRD_PARTY_NOTICES.md` mit den Lizenzhinweisen von ECharts, Lit und den übrigen Abhängigkeiten.

## Reihenfolge

1. **Gerüst:** manifest, Config Flow, `hacs.json`, README, Tooling, CI-Stage `testen`.
2. **Upload und Speicherung:** `models.py`, `store.py`, `http.py` mit Tests.
   Danach lassen sich Shots schon per `curl` hochladen.
3. **Sensor, Event und WebSocket-Commands** mit Tests.
4. **Panel:** Liste, Filter, Detailansicht mit ECharts.
5. **App-Seite** (in Beanconqueror, eigener Branch `feature/hass-visualizer`): HASS als Upload-Ziel
   mit URL und Token aus der Mühlen-Steckdose. Der Upload wird in `customInformation.hass_shot_uploaded_at`
   gemerkt, unabhängig von `visualizer_id`. Dazu kommt „Alle Brews nach Home Assistant hochladen (N)“
   per Batch mit Fortschritt und Zusammenfassung. Brews ohne Kurven werden auch hochgeladen.
   HASS ist wie Sync und Webhook vom Kill-Switch ausgenommen.

Getestet wird jeder Schritt an der eigenen HASS-Instanz. Dafür wird `custom_components/coffeenord`
dorthin kopiert und HASS neu gestartet.

## Noch zu prüfen

- Die Mindestversion von Home Assistant und die passende Python-Version beim Anlegen des Gerüsts
  festlegen, und zwar nach dem aktuellen HA-Release, nicht aus dem Gedächtnis.
- Vor Schritt 5 mit einem echten Export prüfen, ob `brew_time` in allen Kurven Sekunden als String
  enthält. In den Testdaten ist das so (`"0.1"`), bei älteren Brews ist es nicht sicher.
