# mcu_state.py
from __future__ import annotations
from dataclasses import dataclass
from threading import RLock
from typing import Callable, List, Optional, Tuple

# Canonical mode names (keep consistent across the app)
MODE_TRACK_VOLUME = "Track/Volume"
MODE_SEND         = "Send"
MODE_PAN_SURR     = "Pan/Surround"
MODE_PLUGIN       = "Plugin"
MODE_EQ           = "EQ"
MODE_DYNAMICS     = "Dynamics"

@dataclass(frozen=True)
class McuSnapshot:
    mode: Optional[str]
    submode: Optional[str]
    ring_modes: Tuple[int, ...]  # raw 8 bytes from 0x72, may be empty tuple

class McuState:
    """
    Process-wide, ultra-light global MCU state with zero external deps.
    - Fast reads: O(1) (no locking for snapshot retrieval)
    - Changes emit to subscribers (GUI, pads, etc.)
    """
    __slots__ = ("_mode", "_submode", "_ring_modes", "_listeners", "_lock")
    _instance: "McuState" = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            # init
            cls._instance._mode = None
            cls._instance._submode = None
            cls._instance._ring_modes = tuple()
            cls._instance._listeners: List[Callable[[McuSnapshot], None]] = []
            cls._instance._lock = RLock()
        return cls._instance

    # ---------- GET ----------
    def snapshot(self) -> McuSnapshot:
        # Lockless read of immutable tuple + simple fields
        return McuSnapshot(self._mode, self._submode, self._ring_modes)

    def mode(self) -> Optional[str]:
        return self._mode

    def submode(self) -> Optional[str]:
        return self._submode

    def ring_modes(self) -> Tuple[int, ...]:
        return self._ring_modes

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
def MCU_STATE() -> McuState:
    return McuState()
