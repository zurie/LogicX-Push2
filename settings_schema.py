from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, fields
from typing import Optional

logger = logging.getLogger(__name__)

VALID_GUI_PROFILES = {"legacy", "mackie_v2", "mackie_v3"}


@dataclass
class Settings:
    """All persistent app settings — single source of truth for keys, types, and defaults."""

    # MIDI routing
    midi_in_default_channel: int = 0
    midi_out_default_channel: int = 0
    default_midi_in_device_name: Optional[str] = None
    default_midi_out_device_name: Optional[str] = None
    default_notes_midi_in_device_name: Optional[str] = None
    default_midi_port_name: str = "IAC Driver Default"
    mcu_port_name: Optional[str] = None

    # Display / performance
    use_push2_display: bool = True
    target_frame_rate: int = 60
    gui_profile: str = "legacy"

    # App behaviour
    debug_logs: bool = False
    collapse_scale: bool = False
    use_mcu: bool = True
    debug_mcu: bool = False
    solo_off_confirm_time: float = 2.0
    bank_reassert_delay: float = 0.2

    # Melodic mode (persisted by MelodicMode.get_settings_to_save)
    use_poly_at: bool = True
    root_midi_note: int = 64
    channel_at_range_start: int = 401
    channel_at_range_end: int = 800
    poly_at_max_range: int = 40
    poly_at_curve_bending: int = 50

    def __post_init__(self):
        self.midi_in_default_channel = max(0, min(15, int(self.midi_in_default_channel)))
        self.midi_out_default_channel = max(0, min(15, int(self.midi_out_default_channel)))

        if self.target_frame_rate <= 0:
            logger.warning("target_frame_rate must be > 0; resetting to 60")
            self.target_frame_rate = 60

        if self.gui_profile not in VALID_GUI_PROFILES:
            logger.warning("Unknown gui_profile %r; falling back to 'legacy'", self.gui_profile)
            self.gui_profile = "legacy"

        self.root_midi_note = max(0, min(127, int(self.root_midi_note)))
        self.poly_at_max_range = max(0, min(127, int(self.poly_at_max_range)))
        self.poly_at_curve_bending = max(0, min(100, int(self.poly_at_curve_bending)))

        if self.channel_at_range_end <= self.channel_at_range_start:
            logger.warning(
                "channel_at_range_end (%d) <= channel_at_range_start (%d); adjusting",
                self.channel_at_range_end, self.channel_at_range_start,
            )
            self.channel_at_range_end = self.channel_at_range_start + 1

    @classmethod
    def from_dict(cls, d: dict) -> Settings:
        """Build a Settings from a raw dict, silently ignoring unknown keys."""
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in d.items() if k in known})

    def to_dict(self) -> dict:
        """Serialize to a plain dict suitable for json.dump."""
        return asdict(self)
