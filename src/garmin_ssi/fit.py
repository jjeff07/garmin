"""Parse a Garmin dive `.fit` file (or a `.zip` containing one) into a `Dive`."""

from __future__ import annotations

import io
import zipfile
from datetime import timedelta
from pathlib import Path

from fitparse import FitFile

from .model import Dive


def _first(messages, name):
    for m in messages:
        if m.name == name:
            return m
    return None


def _all(messages, name):
    return [m for m in messages if m.name == name]


def _val(msg, field):
    if msg is None:
        return None
    try:
        return msg.get_value(field)
    except Exception:
        return None


def parse_fit_bytes(data: bytes) -> Dive:
    # download-service hands back a zip containing "<id>_ACTIVITY.fit"
    if data[:2] == b"PK":
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            fit_name = next(n for n in zf.namelist() if n.lower().endswith(".fit"))
            data = zf.read(fit_name)

    messages = list(FitFile(io.BytesIO(data)).get_messages())

    session = _first(messages, "session")
    activity = _first(messages, "activity")
    dive_settings = _first(messages, "dive_settings")
    summaries = _all(messages, "dive_summary")
    records = _all(messages, "record")

    start_utc = _val(session, "start_time")
    if start_utc is None:
        raise ValueError("FIT has no session.start_time")

    # FIT timestamps are UTC. activity.local_timestamp - activity.timestamp = tz offset.
    ts = _val(activity, "timestamp")
    local_ts = _val(activity, "local_timestamp")
    offset = (local_ts - ts) if (ts and local_ts) else timedelta(0)
    start_local = start_utc + offset

    # prefer the dive_summary that carries a dive_number (the per-session one)
    summ = None
    for s in summaries:
        if _val(s, "dive_number") is not None:
            summ = s
    summ = summ or (summaries[0] if summaries else None)

    max_depth = _val(summ, "max_depth")
    if max_depth is None and records:
        depths = [d for d in (_val(r, "depth") for r in records) if d is not None]
        max_depth = max(depths) if depths else None
    if max_depth is None:
        raise ValueError("FIT has no max depth")

    divetime_s = _val(session, "total_elapsed_time") or _val(summ, "bottom_time")

    temps = [t for t in (_val(r, "temperature") for r in records) if t is not None]
    water_temp = min(temps) if temps else _val(session, "avg_temperature")

    lat, lng = _surface_position(session, _first(messages, "lap"), records)

    return Dive(
        start_local=start_local,
        divetime_s=float(divetime_s),
        max_depth_m=float(max_depth),
        avg_depth_m=_val(summ, "avg_depth"),
        water_temp_c=None if water_temp is None else float(water_temp),
        air_temp_c=None,
        surface_interval_s=_val(summ, "surface_interval"),
        dive_number=_val(summ, "dive_number"),
        water_type=_val(dive_settings, "water_type"),
        name=_val(_first(messages, "sport"), "name"),
        lat=lat,
        lng=lng,
    )


_SEMI_TO_DEG = 180.0 / (2**31)


def _sc_to_deg(v):
    """FIT positions are int32 semicircles."""
    if v is None:
        return None
    d = v * _SEMI_TO_DEG
    return d if -90.0 <= d <= 360.0 else None  # sanity


def _surface_position(session, lap, records):
    """First usable lat/lng: session/lap start or end fix, bbox corner, else any
    record fix. A Descent only fixes GPS at the surface, so this is often absent."""
    for msg, la, lo in (
        (session, "start_position_lat", "start_position_long"),
        (lap, "start_position_lat", "start_position_long"),
        (session, "end_position_lat", "end_position_long"),
        (lap, "end_position_lat", "end_position_long"),
        (session, "nec_lat", "nec_long"),
        (session, "swc_lat", "swc_long"),
    ):
        lat, lng = _sc_to_deg(_val(msg, la)), _sc_to_deg(_val(msg, lo))
        if lat is not None and lng is not None:
            return lat, (lng - 360.0 if lng > 180.0 else lng)
    for r in records:
        lat, lng = _sc_to_deg(_val(r, "position_lat")), _sc_to_deg(_val(r, "position_long"))
        if lat is not None and lng is not None:
            return lat, (lng - 360.0 if lng > 180.0 else lng)
    return None, None


def parse_fit_file(path: str | Path) -> Dive:
    return parse_fit_bytes(Path(path).read_bytes())
