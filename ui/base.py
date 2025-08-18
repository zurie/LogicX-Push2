# ui/base.py
from dataclasses import dataclass
from typing import List, Optional, Tuple, Protocol, Literal

Assignment = Literal["TRACK","PAN","EQ","SEND","PLUGIN","INSTRUMENT"]
Subview = Literal["A","B"]

@dataclass
class UiHeader:
    assignment: Assignment
    subview: Subview
    bank_range: Tuple[int,int]   # 1-based (start,end)
    page_index: int              # 1-based
    page_count: int
    flip: bool
    focused_track: Optional[int] # 1..N or None

@dataclass
class StripBadge:
    rec: bool = False
    solo: bool = False
    mute: bool = False
    selected: bool = False

@dataclass
class StripVM:
    name: str
    color_rgb: Tuple[int,int,int]   # 0..255
    value_label: str                # e.g., "0.0 dB", "L12", etc.
    normalized: float               # 0..1 for rings/meters
    badge: StripBadge

@dataclass
class UiFrame:
    header: UiHeader
    strips: List[StripVM]           # len 0..8

class Renderer(Protocol):
    def render(self, cr, w: int, h: int) -> None: ...
    def on_resize(self, w: int, h: int) -> None: ...
