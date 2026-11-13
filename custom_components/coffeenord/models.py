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
        vol.Optional("analysis"): vol.Any(None, dict),
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
    shape: str | None = None
    main_flow: float | None = None
    grind_hint: str | None = None
    analysis: dict[str, Any] = field(default_factory=dict)
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


# Bis zu dieser Zeit nach Shotbeginn wird ein Tarieren der Waage erkannt (Sekunden).
TARE_WINDOW_S = 10.0
# Unter diesem Gewicht gilt die Waage als tariert (Gramm).
TARE_MAX_G = 1.0
# Fluss-Kurve → zugehörige Gewichts-Kurve (gleiche Waage).
FLOW_OF_WEIGHT = {"flow": "weight", "flow2": "weight2"}


def _clock(value: Any) -> float | None:
    """Uhrzeit "HH:MM:SS.mmm" in Sekunden seit Mitternacht, sonst None."""
    if not isinstance(value, str):
        return None
    try:
        hours, minutes, seconds = value.split(":")
        result = int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    except ValueError:
        return None
    return result if math.isfinite(result) else None


def _raw_points(points: Any, value_key: str) -> list[tuple[Any, Any, float]]:
    """(timestamp, brew_time, wert) aller Messpunkte mit gültigem Wert."""
    if not isinstance(points, list):
        return []
    result = []
    for point in points:
        if not isinstance(point, dict):
            continue
        try:
            value = float(point[value_key])
        except KeyError, TypeError, ValueError:
            continue
        if math.isfinite(value):
            result.append((point.get("timestamp"), point.get("brew_time"), value))
    return result


def _curves(flow: dict[str, Any]) -> dict[str, list[list[float]]]:
    """Kurven als [[sekunden, wert], ...], Sekunden ab dem ersten Messpunkt des Shots.

    Die Zeit kommt aus timestamp (Uhrzeit des Messpunkts). brew_time taugt dafür nicht:
    Es ist "Sekunde.Zähler", auf "0.9" folgt "0.10", als Zahl gelesen springt die Kurve
    zurück. Nur wenn in einer Reihe timestamps fehlen, wird brew_time als Zahl genommen.
    """
    raw = {
        name: _raw_points(flow.get(source), value_key)
        for name, (source, value_key) in CURVE_SOURCES.items()
    }
    clocks = {
        name: [_clock(timestamp) for timestamp, _, _ in points]
        for name, points in raw.items()
    }
    # Uhrzeit nur, wenn alle Reihen sie haben, gemischt gäbe es keine gemeinsame Achse.
    use_clock = any(raw.values()) and all(
        None not in values for values in clocks.values()
    )
    reference = next((values[0] for values in clocks.values() if values), None)

    curves: dict[str, list[list[float]]] = {}
    for name, points in raw.items():
        series: list[list[float]] = []
        if use_clock and reference is not None:
            for clock, (_, _, value) in zip(clocks[name], points, strict=True):
                seconds = clock - reference
                # Shot über Mitternacht: Uhrzeit springt von 23:59 auf 00:00.
                if seconds < -43200:
                    seconds += 86400
                elif seconds > 43200:
                    seconds -= 86400
                series.append([seconds, value])
        else:
            for _, brew_time, value in points:
                try:
                    seconds = float(brew_time)
                except TypeError, ValueError:
                    continue
                if math.isfinite(seconds):
                    series.append([seconds, value])
        series.sort(key=lambda point: point[0])
        if series:
            curves[name] = series

    # Bei der Uhrzeit beginnt der Shot mit dem frühesten Messpunkt aller Reihen bei 0 s.
    if use_clock and curves:
        offset = min(series[0][0] for series in curves.values())
        for series in curves.values():
            for point in series:
                point[0] = round(point[0] - offset, 3)

    _cut_before_tare(curves)
    for name in FLOW_OF_WEIGHT:
        for point in curves.get(name, []):
            # Negativer Fluss entsteht nur beim Tarieren oder Abnehmen der Tasse.
            point[1] = max(point[1], 0.0)
    return {name: series for name, series in curves.items() if series}


def _cut_before_tare(curves: dict[str, list[list[float]]]) -> None:
    """Messpunkte vor dem Tarieren entfernen (Gewicht und Fluss derselben Waage).

    Steht beim Start noch die Tasse auf der Waage, beginnt das Gewicht z. B. bei 170 g
    und fällt nach dem Tarieren auf 0. Das wäre eine Spitze im Diagramm, und der daraus
    berechnete Fluss läge bei mehreren hundert g/s im Minus.
    """
    for flow_name, weight_name in FLOW_OF_WEIGHT.items():
        weight = curves.get(weight_name)
        if not weight or abs(weight[0][1]) < TARE_MAX_G:
            continue
        tare = next(
            (
                seconds
                for seconds, value in weight
                if abs(value) < TARE_MAX_G and seconds <= TARE_WINDOW_S
            ),
            None,
        )
        if tare is None:
            continue
        curves[weight_name] = [point for point in weight if point[0] >= tare]
        if flow_name in curves:
            curves[flow_name] = [
                point for point in curves[flow_name] if point[0] >= tare
            ]


# Kennzahlen der Shot-Auswertung, die die App mitschickt. Die Integration rechnet
# selbst nichts aus, sie zeigt nur an.
ANALYSIS_NUMBERS = (
    "first_drip_s",
    "end_s",
    "main_flow",
    "first_third_flow",
    "last_third_flow",
    "peak_flow",
    "max_rise_2s",
)
ANALYSIS_TEXTS = ("shape", "grind_hint", "anomaly_reason")
# Profil ohne verwertbare Kurve, gilt hier als „keine Auswertung“.
SHAPE_UNKNOWN = "UNKNOWN"


def _analysis(data: dict[str, Any]) -> dict[str, Any]:
    """Auswertung aus der App: nur bekannte Felder, leere Werte fallen weg.

    0 bedeutet hier nicht „fehlt“ (Fluss 0 ist ein Messwert), darum nicht _number().
    """
    result: dict[str, Any] = {}
    for key in ANALYSIS_NUMBERS:
        value = data.get(key)
        if isinstance(value, bool) or not isinstance(value, int | float):
            continue
        if math.isfinite(value):
            result[key] = round(float(value), 2)
    for key in ANALYSIS_TEXTS:
        if (text := _text(data.get(key))) is not None:
            result[key] = text
    if result.get("shape") == SHAPE_UNKNOWN:
        del result["shape"]
    if isinstance(version := data.get("version"), int) and not isinstance(
        version, bool
    ):
        result["version"] = version
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

    curves = _curves(flow)

    dose = _number(brew.get("grind_weight"))
    # Getränkemenge (Waage) bevorzugen, sonst die eingegebene Menge.
    yield_g = _number(brew.get("brew_beverage_quantity")) or _number(
        brew.get("brew_quantity")
    )
    ratio = round(yield_g / dose, 2) if dose and yield_g else None
    pressure = curves.get("pressure")
    analysis = _analysis(_dict(envelope.get("analysis")))

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
        shape=analysis.get("shape"),
        main_flow=analysis.get("main_flow"),
        grind_hint=analysis.get("grind_hint"),
        analysis=analysis,
        curves=curves,
        payload=data,
    )
