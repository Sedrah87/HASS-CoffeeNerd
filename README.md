# CoffeeNørd für Home Assistant

Eigene Home-Assistant-Integration für Espresso- und Filter-Shots aus der CoffeeNørd-App.
Die App lädt Brews in die eigene HASS-Instanz hoch, statt sie zu visualizer.coffee zu schicken.
Dort stehen sie als Liste mit Filtern und mit Kurven für Gewicht, Fluss, Druck und Temperatur.

> **Stand:** Grundgerüst. Upload, Speicherung und Panel folgen, siehe [docs/plan-backend.md](docs/plan-backend.md).

## Installation (HACS)

CoffeeNørd steht nicht in der HACS-Standardliste, weil die Lizenz nichtkommerziell ist.
Die Integration wird darum als benutzerdefiniertes Repository eingebunden:

1. HACS → ⋮ → *Benutzerdefinierte Repositories* → `https://github.com/Sedrah87/HASS-CoffeeNerd`
   mit Typ *Integration* hinzufügen.
2. *CoffeeNørd* installieren und Home Assistant neu starten.
3. *Einstellungen → Geräte & Dienste → Integration hinzufügen → CoffeeNørd*.

Voraussetzung: Home Assistant 2026.10 oder neuer.

## Entwicklung

```sh
uv venv --python 3.14 .venv
uv pip install --python .venv/bin/python -r requirements_test.txt
.venv/bin/ruff check . && .venv/bin/pytest
git config core.hooksPath .githooks   # Privatsphäre-Prüfung vor Commit und Push
```

## Mitmachen

Fehler und Wünsche bitte als Issue auf GitHub melden. Das GitHub-Repo ist ein Spiegel,
Pull Requests lassen sich dort nicht direkt übernehmen.

## Lizenz

[PolyForm Noncommercial 1.0.0](LICENSE.md): Die Integration darf frei genutzt, verändert und
weitergegeben werden, aber nicht kommerziell.
