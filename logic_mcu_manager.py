# logic_mcu_manager.py
# LogicMCUManager with Assign translation normalization at input

import re, mido, threading, time
import definitions
from typing import Optional

_PAN_RE = re.compile(r'^(?:[+\-]?\d{1,3}|C)$')
_TAP_OFF_DELAY = 0.001  # 1 ms tap


class LogicMCUManager:
    MCU_NOTE_CURSOR_UP = 96
    MCU_NOTE_CURSOR_DOWN = 97
    MCU_NOTE_CURSOR_LEFT = 98
    MCU_NOTE_CURSOR_RIGHT = 99
    # === Full Mackie Control Button Map (with VPOT push and custom codes) ===
    BUTTON_MAP = {
        # --- Channel strip buttons ---
        **{i: f"REC[{i + 1}]" for i in range(0, 8)},  # 0–7
        **{i: f"SOLO[{i - 7}]" for i in range(8, 16)},  # 8–15
        **{i: f"MUTE[{i - 15}]" for i in range(16, 24)},  # 16–23
        **{i: f"SELECT[{i - 23}]" for i in range(24, 32)},  # 24–31

        # --- VPOT push (encoders as buttons) ---
        **{i + 32: f"VPOT_PUSH[{i + 1}]" for i in range(0, 8)},  # 32–39

        # --- Function keys (F1–F8) ---
        40: "F1", 41: "F2", 42: "F3", 43: "F4",
        44: "F5", 45: "F6", 46: "F7", 47: "F8",

        # --- Assign / Edit block ---
        48: "ASSIGN_TRACK",
        49: "ASSIGN_SEND",
        50: "ASSIGN_PAN",
        51: "ASSIGN_PLUGIN",
        52: "ASSIGN_EQ",
        53: "ASSIGN_INSTRUMENT",

        # --- Automation ---
        54: "AUTO_READ_OFF",
        55: "AUTO_WRITE",
        56: "AUTO_TRIM",
        57: "AUTO_TOUCH",
        58: "AUTO_LATCH",
        59: "AUTO_GROUP",

        # --- Marker / Edit block ---
        60: "MARKER",
        61: "NUDGE",
        62: "CYCLE",
        63: "DROP",
        64: "REPLACE",
        65: "CLICK",
        66: "SOLO_CLEAR",
        67: "SCRUB",

        # --- Bank / Channel Navigation ---
        68: "BANK_LEFT",
        69: "BANK_RIGHT",
        70: "CHANNEL_LEFT",
        71: "CHANNEL_RIGHT",

        # --- Zoom & Scrub mode ---
        72: "ZOOM",
        73: "SCRUB_MODE",

        # --- Transport ---
        91: "REW",
        92: "FFWD",
        93: "STOP",
        94: "PLAY",
        95: "RECORD",

        # --- Cursor Keys ---
        96: "ARROW_UP",
        97: "ARROW_DOWN",
        98: "ARROW_LEFT",
        99: "ARROW_RIGHT",

        # Custom extensions (optional in your rig)
        100: "LOOP_ON_OFF",
        101: "PUNCH",
        113: "MARKER_PREV",
        114: "MARKER_NEXT",
        115: "MARKER_SET",
        118: "SETUP",
        119: "USER",
        120: "MIX",
    }

    # preferred reverse lookup
    PREFERRED = {"ZOOM": 72, "SCRUB": 67, "SCRUB_MODE": 73}
    BUTTON_CODE = {}
    for code, name in BUTTON_MAP.items():
        if name not in BUTTON_CODE or PREFERRED.get(name) == code:
            BUTTON_CODE[name] = code

    # ──────────────────────────────────────────────────────────────────────────
    # Assign translation tables (keep in sync with mackie_control_mode)
    # ──────────────────────────────────────────────────────────────────────────
    _MCU_OFFICIAL = {
        "PAGE_LEFT":   44,
        "PAGE_RIGHT":  45,
        "BANK_LEFT":   46,
        "BANK_RIGHT":  47,
        "TRACK":       48,
        "SEND":        49,
        "PAN":         50,
        "PLUGIN":      51,
        "EQ":          52,
        "INSTRUMENT":  53,
    }
    _MASCHINE_LOGIC = {
        "TRACK":      40,
        "INSTRUMENT": 41,
        "PAN":        42,
        "PLUGIN":     43,
        "EQ":         44,
        "DYNAMICS":   45,
        "BANK_LEFT":  46,
        "BANK_RIGHT": 47,
    }
    _ASSIGN_ALIAS = {
        "TRACK":      {_MCU_OFFICIAL["TRACK"],      _MASCHINE_LOGIC.get("TRACK", -1)},
        "SEND":       {_MCU_OFFICIAL["SEND"]},
        "PAN":        {_MCU_OFFICIAL["PAN"],        _MASCHINE_LOGIC.get("PAN", -1)},
        "PLUGIN":     {_MCU_OFFICIAL["PLUGIN"],     _MASCHINE_LOGIC.get("PLUGIN", -1)},
        "EQ":         {_MCU_OFFICIAL["EQ"],         _MASCHINE_LOGIC.get("EQ", -1)},
        "INSTRUMENT": {_MCU_OFFICIAL["INSTRUMENT"], _MASCHINE_LOGIC.get("INSTRUMENT", -1)},
        "BANK_LEFT":  {_MCU_OFFICIAL["BANK_LEFT"],  _MASCHINE_LOGIC.get("BANK_LEFT", -1)},
        "BANK_RIGHT": {_MCU_OFFICIAL["BANK_RIGHT"], _MASCHINE_LOGIC.get("BANK_RIGHT", -1)},
        "PAGE_LEFT":  {_MCU_OFFICIAL["PAGE_LEFT"]},
        "PAGE_RIGHT": {_MCU_OFFICIAL["PAGE_RIGHT"]},
    }
    for k in list(_ASSIGN_ALIAS.keys()):
        _ASSIGN_ALIAS[k] = {n for n in _ASSIGN_ALIAS[k] if isinstance(n, int) and n >= 0}
    _ASSIGN_RAW_TO_ACTION = {}
    for action, ids in _ASSIGN_ALIAS.items():
        for i in ids:
            _ASSIGN_RAW_TO_ACTION.setdefault(i, set()).add(action)
    _ACTION_TO_OFFICIAL = {name: code for name, code in _MCU_OFFICIAL.items()}

    @classmethod
    def _resolve_assign_action(cls, raw_id: int, *, page_mode: bool = False) -> Optional[str]:
        actions = cls._ASSIGN_RAW_TO_ACTION.get(raw_id)
        if not actions:
            return None
        if raw_id == 44:  # EQ vs PAGE_LEFT
            if page_mode and "PAGE_LEFT" in actions:
                return "PAGE_LEFT"
            return "EQ" if "EQ" in actions else next(iter(actions))
        if raw_id == 45:  # DYNAMICS vs PAGE_RIGHT
            if page_mode and "PAGE_RIGHT" in actions:
                return "PAGE_RIGHT"
            return "DYNAMICS" if "DYNAMICS" in actions else next(iter(actions))
        for pref in ("TRACK","SEND","PAN","PLUGIN","EQ","INSTRUMENT","BANK_LEFT","BANK_RIGHT","PAGE_LEFT","PAGE_RIGHT"):
            if pref in actions:
                return pref
        return next(iter(actions))

    def _translate_assign_alias(self, note: int) -> int:
        """Normalize Maschine/Logic assign notes (e.g., 40, 42, 44, 45) to official MCU notes before BUTTON_MAP lookup."""
        try:
            action = self._resolve_assign_action(note, page_mode=False)
            if not action:
                return note
            official = self._ACTION_TO_OFFICIAL.get(action)
            return official if official is not None else note
        except Exception:
            return note

    # ──────────────────────────────────────────────────────────────────────────
    # Init / state
    # ──────────────────────────────────────────────────────────────────────────
    def __init__(self, app, port_name="IAC Driver LogicMCU_In", enabled=True, update_interval=0.05):
        self.input_port = None
        self.output_port = None
        self.button_press_times = {}
        self.modifiers = {"shift": False, "select": False}
        self.app = app
        self.enabled = enabled
        self.port_name = port_name
        self.update_interval = update_interval
        self.lcd = [bytearray(b' ' * 56), bytearray(b' ' * 56)]
        self._lcd_top = bytearray(b' ' * 56)
        self._lcd_bot = bytearray(b' ' * 56)
        self.debug_mcu = getattr(app, "debug_mcu", False)

        self._listeners = {"track_state": [], "pan": [], "pan_text": [], "transport": [], "meter": []}

        self.transport = {"play": False, "stop": True, "record": False, "ffwd": False, "rew": False}
        self._transport_dirty = True
        self._transport_seen = False
        self.on_transport_change = None
        self.on_button = None
        self.on_fader = None
        self.on_vpot = None
        self.on_vpot_display = None
        self.on_track_state = None
        self._last_vpot_idx = None
        self.vpot_pos = [0] * 8
        self.listener_thread = None
        self.running = False
        self._last_led_req = 0.0
        self._led_req_interval = 0.3
        self._led_req_bank = None
        self._lcd_pan_ts = [0.0] * 8
        self.pan_string = [""] * 8
        self.last_update_time = 0
        self.pending_update = False

        self.track_colors = [definitions.MIXER_PALETTE[i % len(definitions.MIXER_PALETTE)] for i in range(8)]

        self.track_names = [""] * 8
        self.mute_states = [False] * 64
        self.solo_states = [False] * 64
        self.rec_states = [False] * 64
        self.meter_levels = [0] * 64
        self.select_states = [False] * 8
        self.fader_levels = [0] * 8
        self.pan_levels = [0.0] * 8
        self.pan_text = [None] * 8
        self.vpot_ring = [6] * 8

        self.selected_track_idx = None
        self.playhead = 0.0

        if not hasattr(self.app, "mcu"):
            self.app.mcu = self
        if not hasattr(self.app, "mcu_manager"):
            self.app.mcu_manager = self
        if not hasattr(self.app, "buttons_need_update"):
            self.app.buttons_need_update = False

    # ──────────────────────────────────────────────────────────────────────────
    # Lifecycle
    # ──────────────────────────────────────────────────────────────────────────
    def start(self):
        if not self.enabled:
            if self.debug_mcu:
                print("[MCU] Disabled, not starting")
            return
        try:
            self.input_port = mido.open_input(self.port_name)
            mcu_out_name = self.port_name.replace("_In", "_Out")
            self.output_port = mido.open_output(mcu_out_name)
            self.output_port.send(mido.Message('sysex', data=definitions.MCU_DEVICE_INQUIRY))
            self.running = True
            self.listener_thread = threading.Thread(target=self.listen_loop, daemon=True)
            self.listener_thread.start()
            self.pending_update = True
        except Exception as e:
            print("[MCU] Could not open port:", e)

    def stop(self):
        self.running = False
        if self.input_port:
            self.input_port.close()
            self.input_port = None
            if self.debug_mcu:
                print("[MCU] Input port closed")
        if self.output_port:
            self.output_port.close()
            self.output_port = None
            if self.debug_mcu:
                print("[MCU] Output port closed")

    # ──────────────────────────────────────────────────────────────────────────
    # Events
    # ──────────────────────────────────────────────────────────────────────────
    def add_listener(self, event_type: str, callback):
        self._listeners.setdefault(event_type, []).append(callback)

    def _fire(self, evt, **kw):
        for fn in self._listeners.get(evt, []):
            fn(**kw)

    def send_mcu_button(self, button_type):
        if not self.output_port:
            print("[MCU] No output port available to send", button_type)
            return
        button_type = button_type.upper()
        if button_type in ("SOLO", "MUTE", "REC") and self.selected_track_idx is None:
            print(f"[MCU] No selected track to send {button_type}")
            return
        if button_type == "SOLO":
            note_num = 8 + self.selected_track_idx
        elif button_type == "MUTE":
            note_num = 16 + self.selected_track_idx
        elif button_type == "REC":
            note_num = 0 + self.selected_track_idx
        elif button_type == "PLAY":
            note_num = 94
        elif button_type == "STOP":
            note_num = 93
        elif button_type == "RECORD":
            note_num = 95
        elif button_type == "FFWD":
            note_num = 92
        elif button_type == "REW":
            note_num = 91
        else:
            print("[MCU] Unknown button type:", button_type)
            return
        self.output_port.send(mido.Message("note_on", note=note_num, velocity=127, channel=0))
        self.output_port.send(mido.Message("note_on", note=note_num, velocity=0, channel=0))
        if self.debug_mcu:
            print(f"[MCU] Sent {button_type} (note {note_num})")

    # ──────────────────────────────────────────────────────────────────────────
    # Main listen loop
    # ──────────────────────────────────────────────────────────────────────────
    def listen_loop(self):
        print("[MCU] Starting listen loop")
        for msg in self.input_port:
            if not self.running:
                if self.debug_mcu:
                    print("[MCU] Stopping listen loop")
                break

            if msg.type == 'sysex':
                payload = bytes(msg.data)
                self.handle_sysex(payload)

            elif msg.type in ("note_on", "note_off"):
                pressed = (msg.type == "note_on" and msg.velocity > 0)

                # Normalize Maschine/Logic assign IDs before BUTTON_MAP lookup
                try:
                    msg_note = self._translate_assign_alias(msg.note)
                except Exception:
                    msg_note = msg.note

                handled = self.handle_button(msg_note, pressed)
                if handled is False and hasattr(self.app, "on_push2_midi_message"):
                    self.app.on_push2_midi_message(msg)

            elif msg.type == "control_change":
                self.handle_cc(msg.control, msg.value)

            elif msg.type == "pitchwheel":
                self.handle_pitchbend(msg.channel, msg.pitch)

            elif msg.type in ("aftertouch", "polytouch", "channel_pressure"):
                # Ticks disabled for now
                continue
                # idx = self._last_vpot_idx
                # if idx is None or not (0 <= idx <= 7):
                #     continue
                #
                # val  = int(msg.value)                 # 0..127
                # slot = min(7, max(0, val // 16))      # 8 ticks for your UI
                # ring = min(11, max(0, int(round(val * 11 / 127.0))))  # 0..11
                #
                # self.vpot_pos[idx] = slot
                # if self.vpot_ring[idx] != ring:
                #     self.vpot_ring[idx] = ring
                #     if self.on_vpot_display:
                #         try: self.on_vpot_display(idx, ring)
                #         except Exception: pass
                #
                # if getattr(self.app, "mc_mode", None) and self.app.is_mode_active(self.app.mc_mode):
                #     if hasattr(self.app.mc_mode, "set_pan_tick"):
                #         try: self.app.mc_mode.set_pan_tick(idx, slot)
                #         except Exception: pass
                #     self.app.mc_mode.update_strip_values()
                #
                # self.pending_update = True
                # continue

            # Throttle updates
            now = time.time()
            if now - self.last_update_time >= self.update_interval:
                if self.pending_update:
                    self.flush_updates()
                    self.last_update_time = now
                    self.pending_update = False

    def flush_updates(self):
        if getattr(self.app, "buttons_need_update", False) and self.selected_track_idx is not None:
            if hasattr(self.app, "update_push2_mute_solo"):
                self.app.update_push2_mute_solo(track_idx=self.selected_track_idx)
            self.app.buttons_need_update = False

        if getattr(self, "_transport_dirty", False):
            if hasattr(self.app, "update_play_button_color"):
                self.app.update_play_button_color(self.transport.get("play", False))
            if hasattr(self.app, "update_record_button_color"):
                self.app.update_record_button_color(self.transport.get("record", False))
            self._transport_dirty = False

    # ──────────────────────────────────────────────────────────────────────────
    # SysEx handling (trimmed to your handlers)
    # ──────────────────────────────────────────────────────────────────────────
    def request_bank_led_states(self, selected_idx: int):
        try:
            port = self.output_port or getattr(self.app, "midi_out", None)
            if not port:
                return
            bank_start = (selected_idx // 8) * 8
            now = time.time()
            if getattr(self, "_led_req_bank", None) == bank_start and (now - getattr(self, "_last_led_req", 0)) < getattr(self, "_led_req_interval", 0.3):
                return
            self._led_req_bank = bank_start
            self._last_led_req = now
            for ch in range(bank_start, bank_start + 8):
                msg = mido.Message('sysex', data=definitions.MCU_SYSEX_PREFIX[:4] + [0x20, ch, 0x07])
                port.send(msg)
        except Exception as e:
            if self.debug_mcu:
                print(f"[MCU] Failed to request bank LED states: {e}")

    def handle_sysex(self, data: bytes):
        try:
            if not (len(data) >= 5 and list(data[:3]) == definitions.MCU_SYSEX_PREFIX_ANY and data[3] in definitions.ACCEPTED_MCU_MODEL_IDS):
                if self.debug_mcu:
                    print("[MCU] Ignoring non-Mackie sysex:", data[:8], "…")
                return
            cmd = data[4]

            if cmd == 0x1A and len(data) >= 6 and data[5] == 0x00:
                try:
                    model = data[3]
                    reply = mido.Message('sysex', data=[0x00, 0x00, 0x66, model, 0x1B, *definitions.SERIAL_BYTES])
                    if self.output_port:
                        self.output_port.send(reply)
                except Exception as e:
                    if self.debug_mcu:
                        print("[MCU] Failed to send serial reply:", e)
                return

            if len(data) >= 7 and cmd == 0x0E and data[6] == 0x03:
                track_index = data[5]
                self.selected_track_idx = track_index
                self.pending_update = True
                self.request_bank_led_states(track_index)

                if getattr(self.app, "mc_mode", None):
                    self.app.mc_mode.update_strip_values()
                # fall through; there may be more content in this SysEx

            payload = data[4:]

            # Host keepalive / ping (0x00): ACK with 0x13 00
            if cmd == 0x00:
                try:
                    self.output_port.send(mido.Message('sysex', data=definitions.MCU_SYSEX_PREFIX[:4] + [0x13, 0x00]))
                except Exception as e:
                    if self.debug_mcu:
                        print("[MCU] Failed to send ACK:", e)
                return

            # Standard Mackie blocks
            if 0x10 <= cmd <= 0x17 and len(payload) == 9:  # meters
                self._handle_meter_dump(payload)
                return
            if cmd == 0x12:  # scribble-strip text
                self._handle_display_text(payload)
                return
            if cmd == 0x20:
                # # payload = [0x20, ch, val]
                # if len(payload) < 3:
                #     return
                # ch  = int(payload[1])
                # val = int(payload[2])
                #
                # # NEW: 0x07 = selector for which v‑pot the next channel-pressure belongs to
                # if 0 <= ch <= 7 and val == 0x07:
                #     self._last_vpot_idx = ch
                #     if self.debug_mcu:
                #         print(f"[MCU] VPOT selector → idx {ch}")
                #     return
                #
                # # Ring echo case (some hosts send 0x20 ch pos directly)
                # if 0 <= ch <= 7 and 0 <= val <= 11:
                #     self.vpot_ring[ch] = val
                #     if self.on_vpot_display:
                #         try:
                #             self.on_vpot_display(ch, val)
                #         except Exception:
                #             import logging; logging.exception("on_vpot_display failed")
                #     return
                #
                # # Channel LED bits for ch >= 8
                # if ch >= 8:
                #     self._handle_channel_led([ch, val])
                return
            if cmd == 0x21:  # transport bits
                self._handle_transport(payload)
                return
            if cmd == 0x72:  # time
                self._handle_time(payload[1:])
                return

            # Official 9-byte ring echo
            if len(data) == 9 and data[1:4] == b'\x00\x00\x66' and data[4] == 0x14 and data[5] == 0x20:
                ch = int(data[6]) & 0x07
                pos = max(0, min(11, int(data[7])))
                self.vpot_ring[ch] = pos
                if self.on_vpot_display:
                    try:
                        self.on_vpot_display(ch, pos)
                    except Exception:
                        import logging;
                        logging.exception("on_vpot_display failed")
                return

        except Exception as e:
            if self.debug_mcu:
                print("[MCU] Failed to parse SysEx:", e)

    def request_channel_led_state(self, track_idx):
        try:
            port = self.output_port or getattr(self.app, "midi_out", None)
            if port:
                msg = mido.Message('sysex', data=definitions.MCU_SYSEX_PREFIX[:4] + [0x20, track_idx, 0x07])
                port.send(msg)
                if self.debug_mcu:
                    print(f"[MCU] Requested LED state for channel {track_idx + 1}")
        except Exception as e:
            if self.debug_mcu:
                print(f"[MCU] Failed to request channel LED state: {e}")

    def current_bank_start(self):
        return 0 if self.selected_track_idx is None else (self.selected_track_idx // 8) * 8

    def get_visible_track_names(self):
        """
        Return a list of 8 track names for the currently visible bank (always padded).
        """
        start = self.current_bank_start()
        names = (self.track_names + [""] * 8)
        return names[start:start + 8]

    def get_visible_pan_values(self):
        start = self.current_bank_start()
        pans = (self.pan_levels + [0.0] * 8)
        return pans[start:start + 8]

    def _handle_display_text(self, payload):
        if len(payload) < 2:
            return
        pos = int(payload[1])
        data = bytes(payload[2:])

        # --- FIX: support cross-line writes (one 0x12 frame can carry TOP+BOTTOM)
        p = pos
        remaining = data

        if pos == 0:
            self._lcd_top[:] = b' ' * 56
            self._lcd_bot[:] = b' ' * 56

        while remaining:
            if p < 56:
                n = min(56 - p, len(remaining))
                if n > 0:
                    self._lcd_top[p:p + n] = remaining[:n]
                p += n
                remaining = remaining[n:]
            else:
                p2 = p - 56
                if p2 >= 56:
                    # out of range; drop the rest safely
                    break
                n = min(56 - p2, len(remaining))
                if n > 0:
                    self._lcd_bot[p2:p2 + n] = remaining[:n]
                p += n
                remaining = remaining[n:]

        # --- TOP: names (7×8)
        top = bytes(self._lcd_top)
        cells_top = [top[i:i + 7].decode('ascii', 'ignore').strip() for i in range(0, 56, 7)]
        names_changed = False
        has_any_name = any(cells_top[:8])
        if has_any_name:
            for i, cell in enumerate(cells_top[:8]):
                if not cell or cell.lower() in definitions.OVERLAY_TOKENS:
                    continue
                if cell != self.track_names[i]:
                    self.track_names[i] = cell
                    names_changed = True
            if names_changed and getattr(self.app, "mc_mode", None) and self.app.is_mode_active(self.app.mc_mode):
                self.app.mc_mode.set_visible_names(self.track_names)

        # --- BOTTOM: pans ("+40", "-12", "0", "C")
        bot = bytes(self._lcd_bot)
        cells_bot = [bot[i:i + 7].decode('ascii', 'ignore').strip() for i in range(0, 56, 7)]

        _PAN_RE = re.compile(r'^(?:[+\-]?\d{1,3}|C)$')
        for i, cell in enumerate(cells_bot[:8]):
            if not cell:
                continue
            if cell == "C":
                v = 0
            elif _PAN_RE.match(cell):
                try:
                    v = max(-64, min(63, int(cell)))
                except ValueError:
                    continue
            else:
                continue
            self.pan_text[i] = v
            self.pan_levels[i] = float(v)
            self._fire("pan_text", channel_idx=i, value=float(v))
            self._fire("pan", channel_idx=i, value=float(v))

        if getattr(self.app, "mc_mode", None) and self.app.is_mode_active(self.app.mc_mode):
            self.app.mc_mode.update_strip_values()
        self.pending_update = True

    def _handle_channel_led(self, payload):
        if len(payload) < 2:
            return
        ch, bits = int(payload[0]), int(payload[1])
        if ch < 0:
            return
        if ch >= len(self.mute_states):
            grow = ch + 1 - len(self.mute_states)
            self.mute_states.extend([False] * grow)
            self.solo_states.extend([False] * grow)
            self.rec_states.extend([False] * grow)

        # prev -> new
        prev_rec, prev_solo, prev_mute = self.rec_states[ch], self.solo_states[ch], self.mute_states[ch]
        new_rec = bool(bits & 0x04)  # record-arm
        new_solo = bool(bits & 0x02)  # solo
        new_mute = bool(bits & 0x10)  # mute

        self.rec_states[ch] = new_rec
        self.solo_states[ch] = new_solo
        self.mute_states[ch] = new_mute

        changed = (prev_rec != new_rec) or (prev_solo != new_solo) or (prev_mute != new_mute)

        # broadcast
        self._fire("track_state", channel_idx=ch, rec=new_rec, solo=new_solo, mute=new_mute)
        if self.debug_mcu:
            print(f"[MCU] Ch{ch + 1} mute={new_mute} solo={new_solo} rec={new_rec}")
        if self.on_track_state:
            self.on_track_state(ch, new_rec, new_solo, new_mute)

        # Only update LEDs if something actually changed
        if changed and ch == self.selected_track_idx and hasattr(self.app, "update_push2_mute_solo"):
            self.app.update_push2_mute_solo(track_idx=ch)
            self.app.buttons_need_update = False  # just repainted it
        elif changed:
            self.app.buttons_need_update = True

        self.pending_update = True

    def _handle_transport(self, payload):
        if len(payload) < 2:
            return

        bits = int(payload[1])

        # Logic MCU 0x21 bitfield: 0x01=STOP, 0x02=PLAY, 0x04=RECORD, 0x10=FFWD, 0x20=REW
        play = bool(bits & 0x02)
        stop = bool(bits & 0x01)
        record = bool(bits & 0x04)
        ffwd = bool(bits & 0x10)
        rew = bool(bits & 0x20)
        if play and stop:
            stop = False
        new_transport = {"play": play, "stop": stop, "record": record, "ffwd": ffwd, "rew": rew}
        if new_transport != self.transport:
            self.transport = new_transport
            self._transport_dirty = True
            if self.on_transport_change:
                self.on_transport_change(self.transport)
            self.emit_event("transport", state=self.transport)
        else:
            self._transport_dirty = True

    def _handle_time(self, payload):
        self.playhead = payload

    def emit_event(self, event_type, **kwargs):
        if event_type == "pan" and hasattr(self.app, "on_pan"):
            self.app.on_pan(kwargs.get("channel_idx"), kwargs.get("value"))
        if event_type == "button" and self.on_button:
            self.on_button(kwargs.get("label"), kwargs.get("pressed"))
        if event_type == "transport" and self.on_transport_change:
            self.on_transport_change(kwargs.get("state"))
        if event_type == "fader" and self.on_fader:
            self.on_fader(kwargs.get("channel_idx"), kwargs.get("level"))
        if event_type == "vpot" and self.on_vpot:
            self.on_vpot(kwargs.get("idx"), kwargs.get("value"))
        if event_type == "track_state" and self.on_track_state:
            self.on_track_state(kwargs.get("channel_idx"), kwargs.get("rec"), kwargs.get("solo"), kwargs.get("mute"))
        for cb in self._listeners.get(event_type, []):
            try:
                cb(**kwargs)
            except Exception as e:
                if self.debug_mcu:
                    print(f"[MCU] listener for '{event_type}' raised:", e)

    # Normalize Maschine/Logic assign notes to official actions before lookup
    def _translate_assign_alias(self, note: int) -> int:
        # Use the same translation as the Mix mode (prefer official outbound note)
        action = _resolve_assign_action(note, page_mode=False)  # no page context at input
        if not action:
            return note
        official = _ACTION_TO_OFFICIAL.get(action)
        return official if official is not None else note

    # ---------------- Realtime Handlers ----------------
    def handle_button(self, note, pressed):

        label = self.BUTTON_MAP.get(note)

        if label:

            if label == "MIX":
                now = time.time()
                if pressed:
                    self.button_press_times["MIX"] = now
                    return True
                else:
                    pressed_time = self.button_press_times.get("MIX", now)
                    duration = now - pressed_time
                    long_press = duration >= definitions.BUTTON_LONG_PRESS_TIME

                    if hasattr(self.app, "logic_interface"):
                        self.app.logic_interface.mix(
                            shift=self.modifiers["shift"],
                            select=self.modifiers["select"],
                            long_press=long_press
                        )
                    return True

            if label == "USER" and pressed:
                if hasattr(self.app, "toggle_and_rotate_help_mode"):
                    self.app.toggle_and_rotate_help_mode()
                    self.app.buttons_need_update = True
                return True

            # --- Rec/Solo/Mute states ---
            if label.startswith("REC["):
                idx = int(label[4:-1]) - 1
                self.rec_states[idx] = pressed
                if self.selected_track_idx is None:
                    self.selected_track_idx = idx
                self._fire("track_state", channel_idx=idx,
                           rec=self.rec_states[idx],
                           solo=self.solo_states[idx],
                           mute=self.mute_states[idx])
                self.app.buttons_need_update = True
                self.pending_update = True
                if idx == self.selected_track_idx and hasattr(self.app, "update_push2_mute_solo"):
                    self.app.update_push2_mute_solo(track_idx=idx)

            elif label.startswith("SOLO["):
                idx = int(label[5:-1]) - 1
                self.solo_states[idx] = pressed
                if self.selected_track_idx is None:
                    self.selected_track_idx = idx
                self._fire("track_state", channel_idx=idx,
                           rec=self.rec_states[idx],
                           solo=self.solo_states[idx],
                           mute=self.mute_states[idx])
                self.app.buttons_need_update = True
                self.pending_update = True
                if idx == self.selected_track_idx:
                    self.app.update_push2_mute_solo(track_idx=idx)

            elif label.startswith("MUTE["):
                idx = int(label[5:-1]) - 1
                self.mute_states[idx] = pressed
                if self.selected_track_idx is None:
                    self.selected_track_idx = idx
                self._fire("track_state", channel_idx=idx,
                           rec=self.rec_states[idx],
                           solo=self.solo_states[idx],
                           mute=self.mute_states[idx])
                self.app.buttons_need_update = True
                self.pending_update = True
                if idx == self.selected_track_idx:
                    self.app.update_push2_mute_solo(track_idx=idx)

            # --- Track SELECT buttons ---
            if label.startswith("SELECT[") and pressed:
                try:
                    self.selected_track_idx = int(label.split("[")[1].strip("]")) - 1
                    self.request_bank_led_states(self.selected_track_idx)

                    if self.solo_states[self.selected_track_idx] and hasattr(self.app, "set_push2_solo_led"):
                        self.app.set_push2_solo_led(True)
                    if self.mute_states[self.selected_track_idx] and hasattr(self.app, "set_push2_mute_led"):
                        self.app.set_push2_mute_led(True)
                    if self.debug_mcu:
                        print(f"[MCU] Selected track index set to {self.selected_track_idx + 1}")
                    if hasattr(self.app, "update_push2_mute_solo"):
                        self.app.update_push2_mute_solo(track_idx=self.selected_track_idx)
                    try:
                        self._fire("track_state", channel_idx=self.selected_track_idx)
                    except Exception as _e:
                        if self.debug_mcu:
                            print("[MCU] (debug) failed to fire track_state on SELECT:", _e)
                except Exception as e:
                    if self.debug_mcu:
                        print("[MCU] Failed to parse selected track:", e)

            # --- Transport buttons ---
            if label in ["PLAY", "STOP", "RECORD", "FFWD", "REW"]:
                key = label.lower()
                self.transport[key] = pressed
                self._transport_seen = True
                self._transport_dirty = True
                if self.on_transport_change:
                    self.on_transport_change(self.transport)
                self.emit_event("transport", state=self.transport)

            # Fire generic button event
            if self.on_button:
                self.on_button(label, pressed)
            self.emit_event("button", label=label, pressed=pressed)
            self.pending_update = True
            return True  # MCU handled

        else:
            # Forward unhandled buttons (like User, Setup, Scale, Note) to Push 2 handler
            if hasattr(self.app, "on_push2_midi_message"):
                try:
                    msg_type = "note_on" if pressed else "note_off"
                    msg = mido.Message(msg_type, note=note, velocity=127 if pressed else 0)
                    self.app.on_push2_midi_message(msg)
                    if self.debug_mcu:
                        print(f"[MCU] Forwarded note {note} ({'pressed' if pressed else 'released'}) to Push2 handler")
                except Exception as e:
                    if self.debug_mcu:
                        print(f"[MCU] Failed to forward to Push2 handler: {e}")
            self.emit_event("button_unknown", note=note, pressed=pressed)
            return False

    # ──────────────────────────────────────────────────────────────
    # Scribble-strip helpers (top/bottom per visible bank, 8×7 each)
    # ──────────────────────────────────────────────────────────────
    def get_visible_lcd_lines(self):
        """
        Read-only view of current 8-channel LCD cells.
        Returns (top, bottom) as two lists of 8 strings (<=7 chars each).
        Never mutates state; does not emit events.
        """
        # Ensure buffers exist
        if not hasattr(self, "_lcd_top"):
            self._lcd_top = bytearray(b" " * 56)
        if not hasattr(self, "_lcd_bot"):
            self._lcd_bot = bytearray(b" " * 56)

        top = bytes(self._lcd_top)
        bot = bytes(self._lcd_bot)

        def cells(b):
            return [b[i:i + 7].decode("ascii", "ignore").rstrip()
                    for i in range(0, 56, 7)][:8]

        return cells(top), cells(bot)

    # ──────────────────────────────────────────────────────────────
    # Master fader helpers (MCU “Master” is on MIDI channel 9 ⇒ idx 8)
    # ──────────────────────────────────────────────────────────────
    def _ensure_fader_slots(self, n):
        if len(self.fader_levels) < n:
            self.fader_levels.extend([0.0] * (n - len(self.fader_levels)))

    def get_master_level(self) -> float:
        """Linear 0..1."""
        self._ensure_fader_slots(9)
        return float(self.fader_levels[8])

    def set_master_level(self, level: float):
        """Linear 0..1. Sends MCU pitchbend on channel 9."""
        self._ensure_fader_slots(9)
        level = max(0.0, min(1.0, float(level)))
        self.fader_levels[8] = level
        if self.output_port:
            pb = int(level * 16383) - 8192  # −8192..+8191
            # Channel 8 == “9th” channel = Master fader on MCU
            self.output_port.send(mido.Message("pitchwheel", pitch=pb, channel=8))

    def nudge_master_level(self, steps: int, step_size: float = 1 / 200.0):
        """
        Relative master change in small steps; positive raises, negative lowers.
        Default ~0.5% per detent (tweak step_size to taste).
        """
        cur = self.get_master_level()
        self.set_master_level(cur + steps * step_size)

    def handle_midi_message(self, msg):
        if msg.type in ("note_on", "note_off"):
            self.handle_button(msg.note, msg.velocity > 0)
        elif msg.type == "sysex":
            self.handle_sysex(list(msg.data))

    def handle_cc(self, control, value):
        # --- VPOTs (Pan) 48..55: use CC only to refresh the ring (keep numbers from LCD)
        if 48 <= control <= 55:
            # ch  = control - 48
            # val = int(value)
            # ring = (val * 12) // 128
            # if 0 <= ch <= 7 and self.vpot_ring[ch] != ring:
            #     self.vpot_ring[ch] = ring
            #     if self.on_vpot_display:
            #         try: self.on_vpot_display(ch, ring)
            #         except Exception: pass
            return

        # --- Faders 72..79 ---
        if 72 <= control <= 79:
            idx = control - 72
            level = value / 127.0
            self.fader_levels[idx] = level
            self.emit_event("fader", channel_idx=idx, level=level)
            return

        # if self.debug_mcu:
        #     print(f"[MCU] CC {control} = {value}")

    def handle_pitchbend(self, channel, pitch):
        """
        Logic → MCU fader refresh.
        `pitch` comes in as –8192…+8191 (mido already signed-decodes it).
        """
        level = max(0.0, min(1.0, (pitch + 8192) / 16383.0))

        if channel >= len(self.fader_levels):
            self.fader_levels.extend([0.0] * (channel + 1 - len(self.fader_levels)))
        prev = self.fader_levels[channel]
        self.fader_levels[channel] = level

        if self.on_fader:
            self.on_fader(channel, level)

        # --- Master: channel 8 → toast unconditionally
        if channel == 8:
            try:
                import math
                # dB from your existing helper if present
                def _db_from_level(lv):
                    if hasattr(definitions, "pb_to_db"):
                        return definitions.pb_to_db(int(lv * 16383))
                    # fallback label if pb_to_db is unavailable
                    return None

                new_db = _db_from_level(level)
                old_db = _db_from_level(prev)

                # only toast on ~0.1 dB moves (or if we have no dB helper, toast on ~0.5% moves)
                should_toast = False
                label = None
                if new_db is not None and old_db is not None:
                    def _safe(v):
                        return -90.0 if math.isinf(v) else v

                    if abs(_safe(new_db) - _safe(old_db)) >= 0.1:
                        label = "-∞ dB" if new_db == float("-inf") else f"{new_db:+.1f} dB"
                        should_toast = True
                else:
                    if abs(level - prev) >= 0.005:
                        pct = round(level * 100.0, 1)
                        label = f"{pct:.1f}%"
                        should_toast = True

                if should_toast and hasattr(self.app, "add_display_notification"):
                    self.app.add_display_notification(f"MASTER {label}")
            except Exception:
                pass

        if getattr(self.app, "mc_mode", None) and self.app.is_mode_active(self.app.mc_mode):
            self.app.mc_mode.update_encoders()
            self.app.mc_mode.update_strip_values()

        self.pending_update = True

    # === Inside class LogicMCUManager ===
    # Place near the top of the class (constants)

    def _send_note(self, note: int, vel: int = 127):
        """Low-level: send a Note On/Off (vel 0) on channel 1 to MCU Out."""
        if not self.output_port:
            return
        self.output_port.send(mido.Message('note_on', channel=0, note=note, velocity=vel))

    def _tap_note(self, note: int):
        """Momentary press for MCU-style buttons (Note On then Note Off)."""
        self._send_note(note, 127)
        time.sleep(_TAP_OFF_DELAY)
        self._send_note(note, 0)

    def cursor_up(self):
        self._tap_note(self.MCU_NOTE_CURSOR_UP)

    def cursor_down(self):
        self._tap_note(self.MCU_NOTE_CURSOR_DOWN)

    def cursor_left(self):
        self._tap_note(self.MCU_NOTE_CURSOR_LEFT)

    def cursor_right(self):
        self._tap_note(self.MCU_NOTE_CURSOR_RIGHT)

    # --- Meter -----------------------------------------------------------------
    def _handle_meter_dump(self, payload):
        """
        Logic sends:  F0 00 00 66 14 1n v1 v2 v3 v4 v5 v6 v7 v8 F7
                       |  |  |  |  |  |__ eight 7-bit levels
                       |  |  |  |  +-- 0x1n : n = 0…7 bank number
        """
        bank = payload[0] & 0x0F
        for i, lvl in enumerate(payload[1:9]):  # eight bytes
            idx = bank * 8 + i
            if idx >= len(self.meter_levels):
                self.meter_levels.extend([0] * (idx + 1 - len(self.meter_levels)))
            self.meter_levels[idx] = lvl
            self._fire("meter", channel_idx=i, value=lvl)
