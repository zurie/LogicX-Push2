# pad_meter.py
# ---------------------------------------------------------------------------
# Paint Logic’s 0-127 level meters on Ableton Push-2’s 8×8 pad grid.
# ---------------------------------------------------------------------------
import definitions
import push2_python.constants as C

# ---------------------------------------------------------------------------
# Build a lookup table of Push-2 pad constants.
# Real hardware: rows 0-7 (0 = bottom)  /  columns 1-8 (left→right)
# On the web-sim or stripped constants tables some values may be missing,
# so we fall back to “None” – the update() method handles that.
# ---------------------------------------------------------------------------
def _pad_const(row: int, col: int):
    try:
        return getattr(C, f"BUTTON_ROW_{row}_COL_{col}")
    except AttributeError:
        return None


# in pad_meter.py, at top:
_PAD = [
    [ _pad_const(r, c+1)   for r in range(8) ]   # r=0..7 map to hardware rows 0..7
    for c in range(8)                            # c=0..7 columns left→right
]


class PadMeter:
    """
    Simple “bar-graph” meter painter.

    Call `update(levels)` with an iterable of 8 values (0-127) whenever
    you receive new meter data from Logic.  The class keeps an internal
    cache so it only sends colour updates when something actually
    changes, minimising MIDI traffic.
    """

    def __init__(self, push):
        self.push = push
        self._last = {}            # pad-id  → last colour sent
        self._pad = [ col[::-1] for col in _PAD ]


# -----------------------------------------------------------------------
    # Colour helpers
    # -----------------------------------------------------------------------
    @staticmethod
    def _row_colour(row: int, lit: int):
        if row >= lit:
            return definitions.BLACK
        if row < 4:
            return definitions.GREEN
        if row < 6:
            return definitions.YELLOW
        if row < 7:
            return definitions.ORANGE
        return definitions.RED

    # -----------------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------------
    def update(self, levels):
        """
        `levels` – sequence of eight 0-127 integers (one per visible track).
        """
        for col, val in enumerate(levels[:8]):
            lit_rows = min(8, (val + 15) // 16)        # 0…8 rows lit
            for logical_row in range(8):
                # map bottom-up logical_row → hardware row by flipping
                pad_row   = 7 - logical_row
                colour    = self._row_colour(logical_row, lit_rows)
                pad_const = self._pad[col][pad_row]      # may be None in sim
                pad_id = pad_const if pad_const is not None else (pad_row, col)

                if self._last.get(pad_id) != colour:
                    self.push.pads.set_pad_color(pad_id, colour)
                    self._last[pad_id] = colour
