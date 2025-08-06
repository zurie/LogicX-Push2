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


_PAD = [[_pad_const(7 - r, c + 1)          # flip so r=0 is the BOTTOM row
         for r in range(8)]                # rows 0-7
        for c in range(8)]                # columns 0-7  (we keep 0-based)


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
        self._pad = _PAD           # shortcut

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
            for row in range(8):
                colour = self._row_colour(row, lit_rows)
                pad_const = self._pad[col][row]        # may be None on sim
                pad_id = pad_const if pad_const is not None else (row, col)

                if self._last.get(pad_id) != colour:
                    self.push.pads.set_pad_color(pad_id, colour)
                    self._last[pad_id] = colour
