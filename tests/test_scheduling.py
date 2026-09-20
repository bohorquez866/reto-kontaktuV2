from __future__ import annotations

from src.scheduling import (
    add_business_days,
    format_iso,
    in_window,
    parse_dt,
    parse_spanish_callback,
    snap_to_window,
)


def test_snap_keeps_weekday_inside_window(campana):
    dt = parse_dt("2026-09-15T11:31:00+02:00", campana)
    assert format_iso(snap_to_window(dt, campana)) == "2026-09-15T11:31:00+02:00"


def test_snap_sunday_goes_to_monday_open(campana):
    dt = parse_dt("2026-09-20T11:00:00+02:00", campana)
    assert format_iso(snap_to_window(dt, campana)) == "2026-09-21T10:00:00+02:00"


def test_snap_after_weekday_close_goes_next_morning(campana):
    dt = parse_dt("2026-09-15T20:40:00+02:00", campana)
    assert format_iso(snap_to_window(dt, campana)) == "2026-09-16T10:00:00+02:00"


def test_snap_saturday_afternoon_goes_monday(campana):
    dt = parse_dt("2026-09-19T14:20:00+02:00", campana)
    assert format_iso(snap_to_window(dt, campana)) == "2026-09-21T10:00:00+02:00"


def test_window_ends_are_inclusive(campana):
    assert in_window(parse_dt("2026-09-15T10:00:00+02:00", campana), campana)
    assert in_window(parse_dt("2026-09-15T20:00:00+02:00", campana), campana)
    assert in_window(parse_dt("2026-09-19T14:00:00+02:00", campana), campana)


def test_business_days_skip_weekend(campana):
    tuesday = parse_dt("2026-09-15T16:42:00+02:00", campana)
    assert format_iso(add_business_days(tuesday, 3, campana)) == "2026-09-18T16:42:00+02:00"


def test_callback_manana_a_las_seis(campana):
    occurred = parse_dt("2026-09-15T17:05:00+02:00", campana)
    parsed = parse_spanish_callback("mañana a las seis", occurred)
    assert parsed is not None
    assert format_iso(parsed) == "2026-09-16T18:00:00+02:00"


def test_callback_de_la_manana_stays_morning(campana):
    occurred = parse_dt("2026-09-15T17:05:00+02:00", campana)
    parsed = parse_spanish_callback("mañana a las 10 de la mañana", occurred)
    assert parsed is not None
    assert format_iso(parsed) == "2026-09-16T10:00:00+02:00"


def test_callback_named_weekday(campana):
    occurred = parse_dt("2026-09-15T17:05:00+02:00", campana)
    parsed = parse_spanish_callback("el jueves a las 11", occurred)
    assert parsed is not None
    assert format_iso(parsed) == "2026-09-17T11:00:00+02:00"
