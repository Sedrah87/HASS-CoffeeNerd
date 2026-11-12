# CoffeeNørd für Home Assistant

Eigene Home-Assistant-Integration für Espresso- und Filter-Shots aus der CoffeeNørd-App.
Die App lädt Brews in die eigene HASS-Instanz hoch, statt sie zu visualizer.coffee zu schicken.
Dort stehen sie als Liste mit Filtern und mit Kurven für Gewicht, Fluss, Druck und Temperatur.

> **Stand:** Upload und Speicherung. Sensor, Event und Panel folgen, siehe [docs/plan-backend.md](docs/plan-backend.md).

## Installation (HACS)

1. HACS → ⋮ → *Benutzerdefinierte Repositories* → die URL dieses Repos mit Typ *Integration* hinzufügen.
2. *CoffeeNørd* installieren und Home Assistant neu starten.
3. *Einstellungen → Geräte & Dienste → Integration hinzufügen → CoffeeNørd*.

Voraussetzung: Home Assistant 2026.10 oder neuer.

## Upload testen

Ein Long-Lived Access Token wird unter *Profil → Sicherheit* erstellt.

```sh
curl -X POST "http://homeassistant.local:8123/api/coffeenord/shots" \
  -H "Authorization: Bearer $HASS_TOKEN" -H "Content-Type: application/json" \
  -d '{"schema_version": 1, "shot_id": "test-1", "brewed_at": 1762941151,
       "visualizer": {"bean": {"name": "Testbohne"}, "brew": {"grind_weight": 18,
       "brew_beverage_quantity": 36, "brew_time": 28}}}'
# → {"shot_id": "test-1", "status": "created"}
```

Ein zweiter, identischer Aufruf liefert `unchanged`. Mehrere Shots lassen sich mit
`POST /api/coffeenord/shots/batch` und `{"shots": [...]}` hochladen, höchstens 20 pro Aufruf.
Die Datenbank liegt unter `<config>/coffeenord/shots.db`.

## Entwicklung

```sh
uv venv --python 3.14 .venv
uv pip install --python .venv/bin/python -r requirements_test.txt
.venv/bin/ruff check . && .venv/bin/pytest
git config core.hooksPath .githooks   # Privatsphäre-Prüfung vor Commit und Push
```

## Lizenz

[PolyForm Noncommercial 1.0.0](LICENSE.md): Die Integration darf frei genutzt, verändert und
weitergegeben werden, aber nicht kommerziell.
