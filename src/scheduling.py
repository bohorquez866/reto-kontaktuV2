from __future__ import annotations

import re
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

DAY_KEYS = (
    "lunes",
    "martes",
    "miercoles",
    "jueves",
    "viernes",
    "sabado",
    "domingo",
)

WEEKDAY_ALIASES = {
    "lunes": 0,
    "martes": 1,
    "miercoles": 2,
    "miércoles": 2,
    "jueves": 3,
    "viernes": 4,
    "sabado": 5,
    "sábado": 5,
    "domingo": 6,
}

HOUR_WORDS = {
    "una": 1,
    "dos": 2,
    "tres": 3,
    "cuatro": 4,
    "cinco": 5,
    "seis": 6,
    "siete": 7,
    "ocho": 8,
    "nueve": 9,
    "diez": 10,
    "once": 11,
    "doce": 12,
}


def tz_of(campana: dict) -> ZoneInfo:
    return ZoneInfo(campana["campana"]["zona_horaria"])


def parse_dt(value: str, campana: dict) -> datetime:
    dt = datetime.fromisoformat(value)
    zone = tz_of(campana)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=zone)
    return dt.astimezone(zone)


def format_iso(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


def _franja(day: datetime, campana: dict) -> tuple[datetime, datetime] | None:
    key = DAY_KEYS[day.weekday()]
    bounds = campana["ventana_llamadas"][key]
    if not bounds:
        return None
    start = datetime.combine(day.date(), time.fromisoformat(bounds[0]), tzinfo=day.tzinfo)
    end = datetime.combine(day.date(), time.fromisoformat(bounds[1]), tzinfo=day.tzinfo)
    return start, end


def snap_to_window(dt: datetime, campana: dict) -> datetime:
    for offset in range(0, 14):
        day = dt + timedelta(days=offset)
        franja = _franja(day, campana)
        if franja is None:
            continue
        start, end = franja
        if offset == 0:
            if dt > end:
                continue
            if dt < start:
                return start
            return dt
        return start
    raise RuntimeError("no hay franja de llamadas en los próximos 14 días")


def in_window(dt: datetime, campana: dict) -> bool:
    franja = _franja(dt, campana)
    if franja is None:
        return False
    start, end = franja
    return start <= dt <= end


def add_hours(dt: datetime, hours: float) -> datetime:
    return dt + timedelta(hours=hours)


def add_minutes(dt: datetime, minutes: int) -> datetime:
    return dt + timedelta(minutes=minutes)


def add_natural_days(dt: datetime, days: int) -> datetime:
    return dt + timedelta(days=days)


def add_business_days(dt: datetime, days: int, campana: dict) -> datetime:
    habiles = set(campana["dias_habiles"])
    remaining = days
    current = dt
    while remaining > 0:
        current = current + timedelta(days=1)
        if DAY_KEYS[current.weekday()] in habiles:
            remaining -= 1
    return current


def _next_named_weekday(occurred: datetime, weekday: int, hour: int, minute: int) -> datetime:
    days_ahead = (weekday - occurred.weekday()) % 7
    candidate = datetime.combine(
        occurred.date() + timedelta(days=days_ahead),
        time(hour, minute),
        tzinfo=occurred.tzinfo,
    )
    if days_ahead == 0 and candidate <= occurred:
        candidate = candidate + timedelta(days=7)
    return candidate


def parse_spanish_callback(raw: str, occurred: datetime) -> datetime | None:
    text = (raw or "").lower().strip()
    if not text:
        return None

    tomorrow = "mañana" in text and "de la mañana" not in text

    hour: int | None = None
    minute = 0
    numeric = re.search(r"\b(\d{1,2})(?::(\d{2}))?\b", text)
    if numeric:
        hour = int(numeric.group(1))
        minute = int(numeric.group(2) or 0)
    else:
        for word, value in HOUR_WORDS.items():
            if re.search(rf"\b{word}\b", text):
                hour = value
                break
    if hour is None:
        return None
    if hour > 23:
        return None

    morning = "de la mañana" in text
    afternoon = any(token in text for token in ("de la tarde", "de la noche", "p.m", "pm"))
    if hour <= 12 and not morning:
        if afternoon or hour <= 7:
            if hour < 12:
                hour += 12

    weekday = None
    for name, index in WEEKDAY_ALIASES.items():
        if re.search(rf"\b{name}\b", text):
            weekday = index
            break

    if weekday is not None:
        return _next_named_weekday(occurred, weekday, hour, minute)

    day = occurred.date() + timedelta(days=1) if tomorrow else occurred.date()
    candidate = datetime.combine(day, time(hour, minute), tzinfo=occurred.tzinfo)
    if not tomorrow and candidate <= occurred:
        candidate = candidate + timedelta(days=1)
    return candidate


def resolve_callback_when(
    raw: str | None,
    iso_value: str | None,
    occurred: datetime,
    campana: dict,
) -> datetime | None:
    if iso_value:
        try:
            return parse_dt(iso_value, campana)
        except ValueError:
            pass
    if raw:
        return parse_spanish_callback(raw, occurred)
    return None
