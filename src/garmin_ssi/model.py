"""Normalised dive record. Every source (dive-summary JSON, activity detail, FIT)
maps into this shape; the SSI builder only ever sees a `Dive`."""

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

    activity_id: int | None = None
    avg_depth_m: float | None = None
    water_temp_c: float | None = None
    air_temp_c: float | None = None
    surface_interval_s: int | None = None
    dive_number: int | None = None
    water_type: str | None = None  # "fresh" | "salt" | None
    name: str | None = None
    lat: float | None = None       # surface position (degrees), if the FIT/Garmin has one
    lng: float | None = None

    def to_public_dict(self) -> dict:
        """Metadata block published alongside the SSI string (for debugging / the watch UI)."""
        return {
            "activityId": self.activity_id,
            "diveNumber": self.dive_number,
            "startLocal": self.start_local.isoformat(),
            "divetimeMin": round(self.divetime_s / 60),
            "maxDepthM": round(self.max_depth_m, 1),
            "waterTempC": None if self.water_temp_c is None else round(self.water_temp_c),
            "name": self.name,
        }
