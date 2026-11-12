"""Upload-Payload prüfen und in Zusammenfassung und Kurven umrechnen.

Der Payload ist ein Umschlag um das Visualizer-JSON der App
(siehe docs/plan-backend.md).
Unbekannte Felder werden nicht abgelehnt, der Rohdatensatz wird vollständig gespeichert.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import voluptuous as vol

from .const import SCHEMA_VERSION

ENVELOPE_SCHEMA = vol.Schema(
    {
        vol.Required("schema_version"): vol.All(
            int, vol.Range(min=1, max=SCHEMA_VERSION)
        ),
        vol.Required("shot_id"): vol.All(str, vol.Strip, vol.Length(min=1, max=128)),
        vol.Required("brewed_at"): vol.All(vol.Coerce(int), vol.Range(min=0)),
        vol.Optional("updated_at"): vol.All(vol.Coerce(int), vol.Range(min=0)),
        vol.Required("visualizer"): dict,
        vol.Optional("bean2"): vol.Any(None, dict),
    },
    extra=vol.ALLOW_EXTRA,
)

# Kurve im Ergebnis → (Liste in brewFlow, Wertfeld je Messpunkt)
CURVE_SOURCES: dict[str, tuple[str, str]] = {
    "weight": ("weight", "actual_weight"),
    "weight2": ("weightSecond", "actual_weight"),
    "flow": ("realtimeFlow", "flow_value"),
    "flow2": ("realtimeFlowSecond", "flow_value"),
    "pressure": ("pressureFlow", "actual_pressure"),
    "temperature": ("temperatureFlow", "actual_temperature"),
}


@dataclass(slots=True)
class Shot:
    """Ein geprüfter Shot, bereit zum Speichern."""

    id: str
    schema_version: int
    brewed_at: int
    updated_at: int
    bean_name: str | None = None
    bean_roaster: str | None = None
    bean2_name: str | None = None
    mill_name: str | None = None
    preparation_name: str | None = None
    preparation_style: str | None = None
    grind_size: str | None = None
    dose_g: float | None = None
    yield_g: float | None = None
    brew_time_s: float | None = None
    ratio: float | None = None
    tds: float | None = None
    ey: float | None = None
    rating: float | None = None
    peak_pressure: float | None = None
    curves: dict[str, list[list[float]]] = field(default_factory=dict)
    payload: dict[str, Any] = field(default_factory=dict)

    @property
    def has_curves(self) -> bool:
        return bool(self.curves)


def _text(value: Any) -> str | None:
    """Nicht leere Zeichenkette oder None."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _number(value: Any) -> float | None:
    """Zahl oder None.

    In der App bedeutet 0 „nicht erfasst“ (Dosis, Ausbeute, TDS, Bewertung …),
    darum gilt 0 hier ebenfalls als fehlend.
    """
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except TypeError, ValueError:
        return None
    if not math.isfinite(number) or number == 0:
        return None
    return number


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _curve(points: Any, value_key: str) -> list[list[float]]:
    """Messpunkte in [[sekunden, wert], ...] umwandeln.

    Die Zeit kommt aus brew_time (Sekunden, in der App als String, z. B. "12.3").
    timestamp enthält nur die Uhrzeit ohne Datum und wird darum nicht verwendet.
    Ungültige Punkte werden übersprungen.
    """
    if not isinstance(points, list):
        return []
    result: list[list[float]] = []
    for point in points:
        if not isinstance(point, dict):
            continue
        try:
            seconds = float(point["brew_time"])
            value = float(point[value_key])
        except KeyError, TypeError, ValueError:
            continue
        if math.isfinite(seconds) and math.isfinite(value):
            result.append([seconds, value])
    return result


def _brew_time(brew: dict[str, Any]) -> float | None:
    """Brühzeit in Sekunden: brew_time (ganze Sekunden) plus brew_time_milliseconds."""
    seconds = _number(brew.get("brew_time")) or 0.0
    milliseconds = _number(brew.get("brew_time_milliseconds")) or 0.0
    total = seconds + milliseconds / 1000
    return total or None


def parse_shot(data: Any) -> Shot:
    """Payload prüfen und einen Shot daraus machen.

    Wirft vol.Invalid bei ungültigen Daten.
    """
    if not isinstance(data, dict):
        raise vol.Invalid("Shot muss ein JSON-Objekt sein")
    envelope = ENVELOPE_SCHEMA(data)

    visualizer = envelope["visualizer"]
    bean = _dict(visualizer.get("bean"))
    brew = _dict(visualizer.get("brew"))
    mill = _dict(visualizer.get("mill"))
    preparation = _dict(visualizer.get("preparation"))
    bean2 = _dict(envelope.get("bean2"))
    flow = _dict(visualizer.get("brewFlow"))

    curves: dict[str, list[list[float]]] = {}
    for name, (source, value_key) in CURVE_SOURCES.items():
        points = _curve(flow.get(source), value_key)
        if points:
            curves[name] = points

    dose = _number(brew.get("grind_weight"))
    # Getränkemenge (Waage) bevorzugen, sonst die eingegebene Menge.
    yield_g = _number(brew.get("brew_beverage_quantity")) or _number(
        brew.get("brew_quantity")
    )
    ratio = round(yield_g / dose, 2) if dose and yield_g else None
    pressure = curves.get("pressure")

    brewed_at = envelope["brewed_at"]
    return Shot(
        id=envelope["shot_id"],
        schema_version=envelope["schema_version"],
        brewed_at=brewed_at,
        updated_at=envelope.get("updated_at", brewed_at),
        bean_name=_text(bean.get("name")),
        bean_roaster=_text(bean.get("roaster")),
        bean2_name=_text(bean2.get("name")),
        mill_name=_text(mill.get("name")),
        preparation_name=_text(preparation.get("name")),
        preparation_style=_text(preparation.get("style_type")),
        grind_size=_text(brew.get("grind_size")),
        dose_g=dose,
        yield_g=yield_g,
        brew_time_s=_brew_time(brew),
        ratio=ratio,
        tds=_number(brew.get("tds")),
        ey=_number(brew.get("ey")),
        rating=_number(brew.get("rating")),
        peak_pressure=max(value for _, value in pressure) if pressure else None,
        curves=curves,
        payload=data,
    )
