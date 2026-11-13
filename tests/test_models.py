"""Tests für die Prüfung und Umrechnung des Upload-Payloads."""

import pytest
import voluptuous as vol

from custom_components.coffeenord.models import parse_shot

from .payloads import make_shot


def test_parse_summary() -> None:
    shot = parse_shot(make_shot())

    assert shot.id == "3f1c2a4e-0000-4000-8000-000000000001"
    assert shot.brewed_at == 1762941151
    assert shot.updated_at == 1762941300
    assert shot.bean_name == "Testbohne"
    assert shot.bean_roaster == "Teströsterei"
    assert shot.mill_name == "Testmühle"
    assert shot.preparation_style == "ESPRESSO"
    assert shot.grind_size == "2.5"
    assert shot.dose_g == 18
    assert shot.yield_g == 36.4
    assert shot.brew_time_s == 28.5
    assert shot.ratio == 2.02
    assert shot.rating == 4
    assert shot.peak_pressure == 9.1


def test_zero_means_not_recorded() -> None:
    shot = parse_shot(make_shot())

    # tds und ey sind 0 → nicht erfasst
    assert shot.tds is None
    assert shot.ey is None


def test_yield_falls_back_to_brew_quantity() -> None:
    payload = make_shot()
    payload["visualizer"]["brew"]["brew_beverage_quantity"] = 0
    payload["visualizer"]["brew"]["brew_quantity"] = 250

    shot = parse_shot(payload)

    assert shot.yield_g == 250
    assert shot.ratio == 13.89


def test_curves_in_seconds_from_shot_start() -> None:
    shot = parse_shot(make_shot())

    assert shot.curves["weight"] == [[0.0, 0.0], [10.0, 12.5], [28.5, 36.4]]
    assert shot.curves["flow"] == [[10.0, 1.8]]
    assert shot.curves["pressure"] == [[5.0, 8.7], [15.0, 9.1]]
    # leere Reihen werden weggelassen
    assert "temperature" not in shot.curves
    assert shot.has_curves


def test_invalid_points_are_skipped() -> None:
    payload = make_shot()
    payload["visualizer"]["brewFlow"]["weight"] = [
        {"brew_time": "1.0", "actual_weight": 1},
        {"brew_time": "abc", "actual_weight": 2},
        {"actual_weight": 3},
        "kein Objekt",
    ]

    shot = parse_shot(payload)

    assert shot.curves["weight"] == [[1.0, 1.0]]


def test_shot_without_flow_is_accepted() -> None:
    payload = make_shot()
    del payload["visualizer"]["brewFlow"]

    shot = parse_shot(payload)

    assert shot.curves == {}
    assert not shot.has_curves
    assert shot.peak_pressure is None


def test_blend_second_bean() -> None:
    shot = parse_shot(make_shot(bean2={"name": "Zweite Bohne", "weight_in": 9}))

    assert shot.bean2_name == "Zweite Bohne"


def test_updated_at_defaults_to_brewed_at() -> None:
    payload = make_shot()
    del payload["updated_at"]

    assert parse_shot(payload).updated_at == payload["brewed_at"]


def test_unknown_fields_are_kept_in_payload() -> None:
    payload = make_shot(neues_feld={"x": 1})

    assert parse_shot(payload).payload["neues_feld"] == {"x": 1}


@pytest.mark.parametrize(
    "overrides",
    [
        {"shot_id": ""},
        {"shot_id": "   "},
        {"schema_version": 2},
        {"schema_version": 0},
        {"brewed_at": "gestern"},
        {"visualizer": "kein Objekt"},
    ],
)
def test_invalid_envelope(overrides: dict) -> None:
    with pytest.raises(vol.Invalid):
        parse_shot(make_shot(**overrides))


@pytest.mark.parametrize(
    "missing", ["shot_id", "schema_version", "brewed_at", "visualizer"]
)
def test_missing_required_field(missing: str) -> None:
    payload = make_shot()
    del payload[missing]

    with pytest.raises(vol.Invalid):
        parse_shot(payload)


def test_payload_must_be_object() -> None:
    with pytest.raises(vol.Invalid):
        parse_shot([make_shot()])


def _point(clock: str, brew_time: str, key: str, value: float) -> dict:
    return {"timestamp": clock, "brew_time": brew_time, key: value}


def test_curves_use_timestamp_not_brew_time() -> None:
    """brew_time ist "Sekunde.Zähler": "0.10" kommt nach "0.9", nicht davor."""
    payload = make_shot()
    payload["visualizer"]["brewFlow"] = {
        "weight": [
            _point("08:00:00.000", "0.0", "actual_weight", 0),
            _point("08:00:00.900", "0.9", "actual_weight", 0.5),
            _point("08:00:01.000", "0.10", "actual_weight", 0.6),
            _point("08:00:01.100", "1.1", "actual_weight", 0.8),
        ],
    }

    shot = parse_shot(payload)

    assert shot.curves["weight"] == [
        [0.0, 0.0],
        [0.9, 0.5],
        [1.0, 0.6],
        [1.1, 0.8],
    ]


def test_curves_share_one_time_axis() -> None:
    payload = make_shot()
    payload["visualizer"]["brewFlow"] = {
        "weight": [_point("08:00:00.500", "0.1", "actual_weight", 0)],
        "pressureFlow": [_point("08:00:00.200", "0.0", "actual_pressure", 1.5)],
    }

    shot = parse_shot(payload)

    assert shot.curves["pressure"] == [[0.0, 1.5]]
    assert shot.curves["weight"] == [[0.3, 0.0]]


def test_curves_over_midnight() -> None:
    payload = make_shot()
    payload["visualizer"]["brewFlow"] = {
        "weight": [
            _point("23:59:59.500", "0.0", "actual_weight", 0),
            _point("00:00:00.500", "1.0", "actual_weight", 2),
        ],
    }

    shot = parse_shot(payload)

    assert shot.curves["weight"] == [[0.0, 0.0], [1.0, 2.0]]


def test_points_before_tare_are_removed() -> None:
    """Die Tasse steht noch auf der Waage, nach dem Tarieren fällt das Gewicht auf 0."""
    payload = make_shot()
    payload["visualizer"]["brewFlow"] = {
        "weight": [
            _point("08:00:00.000", "0.0", "actual_weight", 170),
            _point("08:00:00.200", "0.1", "actual_weight", 0),
            _point("08:00:05.000", "5.0", "actual_weight", 3),
        ],
        "realtimeFlow": [
            _point("08:00:00.000", "0.0", "flow_value", 0),
            _point("08:00:00.200", "0.1", "flow_value", -287.5),
            _point("08:00:05.000", "5.0", "flow_value", 1.2),
        ],
        "pressureFlow": [_point("08:00:00.100", "0.0", "actual_pressure", 0.7)],
    }

    shot = parse_shot(payload)

    assert shot.curves["weight"] == [[0.2, 0.0], [5.0, 3.0]]
    # negativer Fluss vom Tarieren wird zu 0
    assert shot.curves["flow"] == [[0.2, 0.0], [5.0, 1.2]]
    assert shot.curves["pressure"] == [[0.1, 0.7]]


def test_weight_without_tare_is_kept() -> None:
    """Startet die Aufnahme mitten im Shot, steigt das Gewicht von Anfang an."""
    payload = make_shot()
    payload["visualizer"]["brewFlow"] = {
        "weight": [
            _point("08:00:00.000", "0.0", "actual_weight", 2),
            _point("08:00:01.000", "1.0", "actual_weight", 4),
        ],
    }

    shot = parse_shot(payload)

    assert shot.curves["weight"] == [[0.0, 2.0], [1.0, 4.0]]
