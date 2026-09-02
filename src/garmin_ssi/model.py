"""Normalised dive record + diver identity. A parsed `.fit` maps into `Dive`;
the MySSI form builder only ever sees a `Dive` and an `Identity`."""

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
    dive_number: int | None = None
    water_type: str | None = None  # "fresh" | "salt" | None
    lat: float | None = None       # surface position (degrees), if the FIT has one
    lng: float | None = None


@dataclass
class Identity:
    """Static per-diver values baked into every logged dive. `user_master_id` is
    your MySSI member id (Profile screen)."""

    user_master_id: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    leader_id: str | None = None  # instructor / dive-leader SSI id, if you always log one
