# mcu_state.py
from __future__ import annotations
from dataclasses import dataclass
from threading import RLock
from typing import Callable, List, Optional, Tuple

# Canonical mode names (keep consistent across the app)
MODE_TRACK_VOLUME = "Track/Volume"
MODE_SEND = "Send"
MODE_PAN_SURR = "Pan/Surround"
MODE_PLUGIN = "Plugin"
MODE_EQ = "EQ"
MODE_DYNAMICS = "Dynamics"


@dataclass(frozen=True)
class McuSnapshot:
    mode: Optional[str]
    submode: Optional[str]
    ring_modes: Tuple[int, ...]  # raw 8 bytes from 0x72
    flip: bool
    zoom: bool
    scrub: bool
    mod_shift: bool
    mod_ctrl: bool
    mod_option: bool
    mod_alt: bool


class McuState:
    """
    Process-wide, ultra-light global MCU state with zero external deps.
    - Fast reads: O(1) (no locking for snapshot retrieval)
    - Changes emit to subscribers (GUI, pads, etc.)
    """
    __slots__ = (
        "_mode", "_submode", "_ring_modes",
        "_flip", "_zoom", "_scrub",
        "_mod_shift", "_mod_ctrl", "_mod_option", "_mod_alt",
        "_listeners", "_lock",
    )
    _instance: "McuState" = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            # init
            cls._instance._mode = None
            cls._instance._submode = None
            cls._instance._ring_modes = tuple()
            cls._instance._flip = False
            cls._instance._zoom = False
            cls._instance._scrub = False
            cls._instance._mod_shift = False
            cls._instance._mod_ctrl = False
            cls._instance._mod_option = False
            cls._instance._mod_alt = False
            cls._instance._listeners: List[Callable[[McuSnapshot], None]] = []
            cls._instance._lock = RLock()
        return cls._instance

    # ---------- GET ----------
    def snapshot(self) -> McuSnapshot:
        # Lockless read of immutable tuple + simple fields
        return McuSnapshot(
            self._mode, self._submode, self._ring_modes,
            bool(self._flip), bool(self._zoom), bool(self._scrub),
            bool(self._mod_shift), bool(self._mod_ctrl),
            bool(self._mod_option), bool(self._mod_alt),
        )

    def mode(self) -> Optional[str]:
        return self._mode

    def submode(self) -> Optional[str]:
        return self._submode

    def ring_modes(self) -> Tuple[int, ...]:
        return self._ring_modes

    def flip(self) -> bool:
        return bool(self._flip)

    def zoom(self) -> bool:
        return bool(self._zoom)

    def scrub(self) -> bool:
        return bool(self._scrub)

    def mod_shift(self) -> bool:
        return bool(self._mod_shift)

    def mod_ctrl(self) -> bool:
        return bool(self._mod_ctrl)

    def mod_option(self) -> bool:
        return bool(self._mod_option)

    def mod_alt(self) -> bool:
        return bool(self._mod_alt)

    # ---------- SUBSCRIBE ----------
    def subscribe(self, cb: Callable[[McuSnapshot], None]) -> None:
        with self._lock:
            if cb not in self._listeners:
                self._listeners.append(cb)

    def unsubscribe(self, cb: Callable[[McuSnapshot], None]) -> None:
        with self._lock:
            if cb in self._listeners:
                self._listeners.remove(cb)

    # ---------- SET (internal: called by detector wiring) ----------
    def _set_mode_sub(self, mode: Optional[str], sub: Optional[str]) -> None:
        changed = (mode != self._mode) or (sub != self._submode)
        if not changed:
            return
        with self._lock:
            self._mode, self._submode = mode, sub
            snap = self.snapshot()
            for cb in list(self._listeners):
                try:
                    cb(snap)
                except Exception:
                    # Never let a listener crash the state manager
                    pass

    def _set_ring_modes(self, rings: Tuple[int, ...]) -> None:
        if rings == self._ring_modes:
            return
        with self._lock:
            self._ring_modes = rings
            snap = self.snapshot()
            for cb in list(self._listeners):
                try:
                    cb(snap)
                except Exception:
                    pass

    # Convenience accessor

    def _set_flip(self, flip: bool) -> None:
        if bool(flip) == bool(getattr(self, '_flip', False)):
            return
        with self._lock:
            self._flip = bool(flip)
            snap = self.snapshot()
            for cb in list(self._listeners):
                try:
                    cb(snap)
                except Exception:
                    pass

    # --- other LEDs (host-driven) ---
    def _set_zoom(self, val: bool) -> None:
        if bool(val) == bool(self._zoom): return
        with self._lock:
            self._zoom = bool(val)
            snap = self.snapshot()
            for cb in list(self._listeners):
                try:
                    cb(snap)
                except Exception:
                    pass

    def _set_scrub(self, val: bool) -> None:
        if bool(val) == bool(self._scrub): return
        with self._lock:
            self._scrub = bool(val)
            snap = self.snapshot()
            for cb in list(self._listeners):
                try:
                    cb(snap)
                except Exception:
                    pass

    def _set_modifiers(self, *, shift=None, ctrl=None, option=None, alt=None) -> None:
        changed = False
        if shift is not None and bool(shift) != bool(self._mod_shift): self._mod_shift = bool(shift); changed = True
        if ctrl is not None and bool(ctrl) != bool(self._mod_ctrl):  self._mod_ctrl = bool(ctrl);  changed = True
        if option is not None and bool(option) != bool(self._mod_option): self._mod_option = bool(option);changed = True
        if alt is not None and bool(alt) != bool(self._mod_alt):   self._mod_alt = bool(alt);   changed = True
        if not changed: return
        with self._lock:
            snap = self.snapshot()
            for cb in list(self._listeners):
                try:
                    cb(snap)
                except Exception:
                    pass


def MCU_STATE() -> McuState:
    return McuState()
