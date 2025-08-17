# mcu_mode_detector.py
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Tuple
import re

RING_MODE_NAME = {
    0x01: "single",
    0x02: "boostcut",
    0x03: "trim",
    0x04: "wrap",
    0x05: "spread",
    0x06: "fill",
    0x07: "spread2",
}

MODE_KEYWORDS = {
    "volume": "Track/Volume",
    "trkfmt": "Track/Volume",
    "pan": "Pan/Surround",
    "surround": "Pan/Surround",
    "plug": "Plugin",
    "plugin": "Plugin",
    "eq": "EQ",
    "dyn": "Dynamics",
    "dynamics": "Dynamics",
    "send": "Send",
}
ASSIGN_TO_MODE = {
    40: "Track/Volume",  # IN/OUT
    41: "Send",
    42: "Pan/Surround",
    43: "Plugin",
    # 44..47 are page/bank in your app → do not map to a mode
}


def _norm_sub(token: str) -> str:
    t = token.lower()
    if t.startswith("volum"): return "Volume"
    if t.startswith("pan"):   return "Pan"
    if t.startswith("send"):  return "Send"
    if t.startswith("surro"): return "Surround"
    return token.capitalize() if token else None


@dataclass
class MackieModeDetector:
    log: Callable[[str], None] = print
    on_mode_changed: Optional[Callable[[Optional[str], Optional[str]], None]] = None
    on_ring_changed: Optional[Callable[[Tuple[int, ...]], None]] = None
    # Expected mode set by assignment (40..43)
    expected_mode: Optional[str] = None

    # Coverage for each char slot on both rows
    _top_cov: List[bool] = field(default_factory=lambda: [False] * 56)
    _bot_cov: List[bool] = field(default_factory=lambda: [False] * 56)

    # Epoch: increments on each assignment press; cell0_written flags if we saw 0..6 written in this epoch
    _lcd_epoch: int = 0
    _epoch_cell0_written: bool = False
    current_mode: Optional[str] = None
    submode: Optional[str] = None
    last_ring_modes: Optional[Tuple[int, ...]] = None

    # ---- LCD 0x12 ----
    def handle_lcd_sysex(self, data: bytes):
        if not (len(data) >= 7 and data[4] == 0x12):
            return self.current_mode, self.submode

        pos = data[6]
        text_bytes = data[7:-1]
        text = ''.join(chr(b) if 32 <= b <= 126 else ' ' for b in text_bytes)

        target = self._classify_lcd_chunk(text)

        self._reset_for_new_frame(target, pos)

        if target == "top":
            p = 0 if pos > 0x37 else int(pos)
            self._write_line(self.top_line, p, text, self._top_cov)   # pass coverage!
        else:
            p = 0 if pos > 0x37 else max(0, int(pos) - 0x18 if pos >= 0x18 else int(pos))
            self._write_line(self.bot_line, p, text, self._bot_cov)

        # Infer, then commit via gate (no timers)
        inferred_mode = self._infer_mode_from_lcd()
        inferred_sub  = self._infer_submode_from_lcd()
        self._commit_mode_no_timer(inferred_mode, inferred_sub)
        return self.current_mode, self.submode

    def notify_assignment_pressed(self, code: int) -> None:
        if code not in (40, 41, 42, 43):
            return
        self.expected_mode = ASSIGN_TO_MODE.get(code, self.expected_mode)
        # wipe current LCD buffers/coverage so old text can't contaminate cell0
        self.top_line = [" "] * 56
        self.bot_line = [" "] * 56
        self._top_cov = [False] * 56
        self._bot_cov = [False] * 56

    # ---- VPOT 0x72 ----
    def handle_vpot_ring_sysex(self, data: bytes):
        if not (len(data) >= 7 and data[4] == 0x72):
            return self.current_mode, self.submode

        ring_bytes = tuple(data[5:-1])
        if ring_bytes != self.last_ring_modes:
            self.last_ring_modes = ring_bytes
            if self.on_ring_changed:
                self.on_ring_changed(ring_bytes)

            names = [RING_MODE_NAME.get(b & 0x0F, f"0x{b & 0x0F:X}") for b in ring_bytes]
            wrap_like = sum(n in ("wrap", "spread", "spread2") for n in names)
            vol_like = sum(n in ("boostcut", "fill", "trim") for n in names)

            sub_before = self.submode

            # Only refine submode if mode agrees or is unknown
            if (self.current_mode in (None, "Pan/Surround")) and wrap_like >= 5:
                self.submode = "Pan"
            elif (self.current_mode in (None, "Track/Volume")) and vol_like >= 5:
                self.submode = "Volume"

            if self.submode != sub_before and self.on_mode_changed:
                self.on_mode_changed(self.current_mode, self.submode)

        return self.current_mode, self.submode

    # -------------- helpers --------------
    def _classify_lcd_chunk(self, text: str) -> str:
        t = text.lower()
        # Bottom-line giveaways
        if "channel strip parameter" in t or "parameter:" in t:
            return "bottom"
        # Header line like: "Volume Pan TrkFmt Input Output Auto DisplP Setup"
        if "volume" in t and "pan" in t and "trk" in t:
            return "top"
        # Values line often includes dB/numbers; could still be top (names) + bottom (values)
        if "db" in t:
            # If it also contains mode tokens, let it be top; else bottom
            if any(k in t for k in ("volume", "pan", "plugin", "plug", "eq", "dyn", "send", "trkfmt")):
                return "top"
            return "bottom"
        # Otherwise: if any strong mode keyword → top; else default to top
        if any(k in t for k in
               ("volume", "pan", "plugin", "plug", "eq", "dyn", "dynamics", "send", "surround", "trkfmt")):
            return "top"
        return "top"

    def _write_line(self, buf: List[str], pos: int, text: str, cov: List[bool]) -> None:
        p = max(0, min(55, pos))
        end = min(56, p + len(text))
        for i in range(p, end):
            buf[i] = text[i - p]
            cov[i] = True

    def _first_cell_fully_covered(self) -> bool:
        return all(self._top_cov[i] for i in range(7))  # chars 0..6

    def _reset_for_new_frame(self, target: str, pos: int) -> None:
        if target == "top" and pos == 0:
            self.top_line = [" "] * 56
            self._top_cov = [False] * 56
        elif target == "bottom" and (pos == 0 or pos >= 0x18):
            self.bot_line = [" "] * 56
            self._bot_cov = [False] * 56

    def _coverage(self, cov: List[bool]) -> float:
        return sum(1 for b in cov if b) / 56.0

    def _top_text(self) -> str:
        return ''.join(self.top_line).rstrip()

    def _bot_text(self) -> str:
        return ''.join(self.bot_line).rstrip()

    def _first_block_token(self) -> str:
        top = self._top_text().strip().split()
        return (top[0] if top else "").lower()

    # REPLACE your _infer_mode_from_lcd with this
    def _infer_mode_from_lcd(self) -> Optional[str]:
        """
        Decide MODE strictly from the first 7-char cell (chars 0..6) of the top row.
        That cell says 'Volume', 'Pan', 'PlugIn', 'EQ', 'Dyn', 'Send', etc.
        """
        # Require cell0 to be fully written before trusting it
        try:
            cell0_covered = all(self._top_cov[i] for i in range(7))
        except Exception:
            cell0_covered = False

        if not cell0_covered:
            # while cell0 is incomplete, stick to the button hint/current
            return self.expected_mode or self.current_mode

        cell0 = ''.join(self.top_line[:7]).strip().lower()

        if cell0.startswith('vol') or cell0.startswith('trk'):   # 'Volume' or 'TrkFmt'
            return 'Track/Volume'
        if cell0.startswith('pan') or cell0.startswith('sur'):   # 'Pan' or 'Surround'
            return 'Pan/Surround'
        if cell0.startswith('send'):
            return 'Send'
        if cell0.startswith('plug'):
            return 'Plugin'
        if cell0.startswith('eq'):
            return 'EQ'
        if cell0.startswith('dyn'):
            return 'Dynamics'

        # Fallback to our hint/current if cell is weird/blank
        return self.expected_mode or self.current_mode

    def _infer_submode_from_lcd(self) -> Optional[str]:
        bot = self._bot_text().lower()
        top = self._top_text().lower()

        # Only letters after "parameter:", drop digits/symbols; require ≥3 letters
        m = re.search(r'parameter:\s*([a-z]{3,})', self._bot_text(), re.I)
        if m:
            w = m.group(1).lower()
            if   w.startswith('vol'): return 'Volume'
            if   w.startswith('pan'): return 'Pan'
            if   w.startswith('sur'): return 'Surround'
            if   w.startswith('sen'): return 'Send'

        if "send" in top or "send" in bot:
            for token in ("a", "b", "c", "d", "e", "f", "1", "2", "3", "4", "5", "6", "7", "8"):
                if f"send{token}" in top.replace(" ", "") or f"send{token}" in bot.replace(" ", ""):
                    return f"Send {token.upper()}"
            return "Send"

        if "surround" in top or "surround" in bot: return "Surround"
        if "pan" in top or "pan" in bot: return "Pan"
        if "volume" in top or "volume" in bot: return "Volume"

        if any(k in bot for k in ("freq", "gain", "q", "band")):            return "EQ"
        if any(k in bot for k in ("threshold", "ratio", "attack", "release", "makeup")): return "Dynamics"

        return self.submode

    def _commit_mode_no_timer(self, inferred_mode: Optional[str], inferred_sub: Optional[str]) -> None:
        # normalize chopped sub tokens (no 'Pa')
        if isinstance(inferred_sub, str):
            s = inferred_sub.lower()
            if   s.startswith('vol'): inferred_sub = 'Volume'
            elif s.startswith('pan'): inferred_sub = 'Pan'
            elif s.startswith('sur'): inferred_sub = 'Surround'
            elif s.startswith('sen'): inferred_sub = 'Send'

        # If we don't have a real mode yet (cell0 not complete), keep the hint/current
        cell0_covered = all(self._top_cov[i] for i in range(7))
        new_mode = inferred_mode if cell0_covered and inferred_mode else (self.expected_mode or self.current_mode)
        new_sub  = inferred_sub if inferred_sub else self.submode

        if (new_mode, new_sub) == (self.current_mode, self.submode):
            return

        self.current_mode, self.submode = new_mode, new_sub
        self.log(f"[MCU] Mode: {self.current_mode or '?'} | Sub: {self.submode or '-'}")
        if self.on_mode_changed:
            self.on_mode_changed(self.current_mode, self.submode)
