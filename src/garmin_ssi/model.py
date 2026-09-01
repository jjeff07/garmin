"""Normalised dive record. A parsed `.fit` maps into this shape; the MySSI
form builder only ever sees a `Dive`."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class Dive:
    # local wall-clock start of the dive (tz-aware preferred; naive is treated as local)
    start_local: datetime
    # total dive duration, descent to surfacing, in seconds
    divetime_s: float
    # max depth in metres
    max_depth_m: float

    avg_depth_m: float | None = None
    water_temp_c: float | None = None
    air_temp_c: float | None = None
    surface_interval_s: int | None = None
    dive_number: int | None = None
    water_type: str | None = None  # "fresh" | "salt" | None
    name: str | None = None
    lat: float | None = None       # surface position (degrees), if the FIT has one
    lng: float | None = None
