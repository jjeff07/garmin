"""Parse a Garmin dive `.fit` file into a `Dive`.

Used for `refresh.py --from-fit <file>` (fully offline, no Garmin auth) and,
in the workflow, to fill in water temperature that the dive-summary JSON omits.
"""

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

    return Dive(
        start_local=start_local,
        divetime_s=float(divetime_s),
        max_depth_m=float(max_depth),
        activity_id=None,  # the Connect activity id is not in the FIT; comes from the JSON
        avg_depth_m=_val(summ, "avg_depth"),
        water_temp_c=None if water_temp is None else float(water_temp),
        air_temp_c=None,
        surface_interval_s=_val(summ, "surface_interval"),
        dive_number=_val(summ, "dive_number"),
        water_type=_val(dive_settings, "water_type"),
        name=_val(_first(messages, "sport"), "name"),
    )


def parse_fit_file(path: str | Path) -> Dive:
    return parse_fit_bytes(Path(path).read_bytes())
