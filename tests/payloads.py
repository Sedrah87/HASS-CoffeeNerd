"""Synthetische Test-Payloads im Upload-Format (keine Daten aus der App übernommen)."""

from __future__ import annotations

import copy
from typing import Any

BASE_SHOT: dict[str, Any] = {
    "schema_version": 1,
    "shot_id": "3f1c2a4e-0000-4000-8000-000000000001",
    "brewed_at": 1762941151,
    "updated_at": 1762941300,
    "visualizer": {
        "application": "COFFEENORD",
        "bean": {"name": "Testbohne", "roaster": "Teströsterei"},
        "brew": {
            "grind_size": "2.5",
            "grind_weight": 18,
            "brew_quantity": 0,
            "brew_beverage_quantity": 36.4,
            "brew_time": 28,
            "brew_time_milliseconds": 500,
            "tds": 0,
            "ey": 0,
            "rating": 4,
        },
        "mill": {"name": "Testmühle"},
        "preparation": {"name": "Siebträger", "style_type": "ESPRESSO"},
        "water": {"name": "Leitungswasser"},
        "brewFlow": {
            "weight": [
                {"brew_time": "0.0", "timestamp": "10:00:00.000", "actual_weight": 0},
                {
                    "brew_time": "10.0",
                    "timestamp": "10:00:10.000",
                    "actual_weight": 12.5,
                },
                {
                    "brew_time": "28.5",
                    "timestamp": "10:00:28.500",
                    "actual_weight": 36.4,
                },
            ],
            "realtimeFlow": [
                {"brew_time": "10.0", "timestamp": "10:00:10.000", "flow_value": 1.8},
            ],
            "pressureFlow": [
                {
                    "brew_time": "5.0",
                    "timestamp": "10:00:05.000",
                    "actual_pressure": 8.7,
                },
                {
                    "brew_time": "15.0",
                    "timestamp": "10:00:15.000",
                    "actual_pressure": 9.1,
                },
            ],
            "temperatureFlow": [],
        },
    },
}


def make_shot(**overrides: Any) -> dict[str, Any]:
    """Kopie des Basis-Shots mit überschriebenen Feldern auf oberster Ebene."""
    shot = copy.deepcopy(BASE_SHOT)
    shot.update(overrides)
    return shot
