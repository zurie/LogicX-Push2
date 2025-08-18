# ui/ring_styles.py
from typing import Literal, Tuple

RingType = Literal["ARC", "TICS", "DOTS"]
Role = Literal["VPOT", "FADER"]  # who’s controlling what after Flip


def resolve_ring(assignment: str, role: Role) -> Tuple[RingType, str]:
    """
    Returns (ring_type, palette_key)
    palette_key: e.g., "green" or "default"
    Rules:
      - PAN => TICS + green (always)
      - VOLUME/EQ/PLUGIN => ARC
      - SENDS => DOTS
    """
    a = assignment.upper()
    if a == "PAN":
        return "TICS", "green"
    if a in ("TRACK", "EQ", "PLUGIN", "INSTRUMENT"):
        return "ARC", "default"
    if a == "SEND":
        return "DOTS", "default"
    return "ARC", "default"
