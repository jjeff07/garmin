"""garmin-ssi: fetch the latest Garmin dive, log it into the MySSI web logbook."""

from .model import Dive
from .ssi import build_ssi, Identity

__all__ = ["Dive", "build_ssi", "Identity"]
