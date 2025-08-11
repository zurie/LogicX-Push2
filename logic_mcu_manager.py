import re
import mido
import threading
import time
import definitions

_PAN_RE = re.compile(r'^(?:[+\-]?\d{1,3}|C)$')

class LogicMCUManager:
    BUTTON_MAP = {
        # --- Channel strip buttons ---
        **{i: f"REC[{i + 1}]" for i in range(0, 8)},
        **{i: f"SOLO[{i - 7}]" for i in range(8, 16)},
        **{i: f"MUTE[{i - 15}]" for i in range(16, 24)},
        **{i: f"SELECT[{i - 23}]" for i in range(24, 32)},

        # --- Function keys ---
        32: "F1", 33: "F2", 34: "F3", 35: "F4",
        36: "F5", 37: "F6", 38: "F7", 39: "F8",

        # --- Modifier keys / edit block ---
        40: "SHIFT", 41: "OPTION", 42: "CONTROL", 43: "COMMAND",
        44: "ALT", 45: "UNDO",

        # --- Automation ---
        46: "READ", 47: "WRITE", 48: "TRIM", 49: "TOUCH",
        50: "LATCH", 51: "GROUP",

        # --- Marker & Nudge ---
        52: "MARKER", 53: "NUDGE", 54: "CYCLE", 55: "DROP",
        56: "REPLACE", 57: "CLICK", 58: "SOLO", 59: "SCRUB",

        # --- Transport ---
        93: "stop",
        94: "play",
        95: "record",
        91: "rew",
        92: "ffwd",

        # --- Extra / Logic mappings ---
        100: "LOOP_ON_OFF", 101: "PUNCH",
        113: "MARKER_PREV", 114: "MARKER_NEXT", 115: "MARKER_SET",
        118: "SETUP",  # Push 2 Setup button
        119: "USER",   # Push 2 User button
        120: "MIX"
    }

    def __init__(self, app, port_name="IAC Driver LogicMCU_In", enabled=True, update_interval=0.05):
        self.input_port = None
        self.output_port = None
        self.button_press_times = {}
        self.modifiers = {"shift": False, "select": False}
        self.app = app
        self.enabled = enabled
        self.port_name = port_name
        self.update_interval = update_interval  # Minimum time between display updates (50ms default)
        self.lcd = [bytearray(b' ' * 56), bytearray(b' ' * 56)]  # 2×56
        self._lcd_top = bytearray(b' ' * 56)
        self._lcd_bot = bytearray(b' ' * 56)
        self.debug_mcu = getattr(app, "debug_mcu", False)

        # listeners (extensible; add_listener uses setdefault)
        self._listeners = {"track_state": [], "pan": [], "pan_text": [], "transport": [], "meter": []}

        self.transport = {"play": False, "stop": True, "record": False, "ffwd": False, "rew": False}

        # Callback hooks (legacy single-slot style)
        self.on_transport_change = None
        self.on_button = None
        self.on_fader = None
        self.on_vpot = None            # raw ring from 0x0E (optional legacy)
        self.on_vpot_display = None    # official ring echo: fn(ch:int, pos:int)
        self.on_track_state = None
        self._last_vpot_idx = None                  # 0..7
        self.vpot_pos = [0]*8                       # 0..7 (tick slots)
        self.listener_thread = None
        self.running = False
        self._last_led_req = 0.0
        self._led_req_interval = 0.3
        self._led_req_bank = None
        self._lcd_pan_ts = [0.0] * 8     # when we last accepted pan from LCD (per strip)
        self.pan_string  = [""]  * 8
        # State cache for throttling
        self.last_update_time = 0
        self.pending_update = False

        # Simple MCU track‑type colours (8‑color rotating palette)
        self.track_colors = [definitions.MIXER_PALETTE[i % len(definitions.MIXER_PALETTE)] for i in range(8)]

        # Track/LED state caches
        self.track_names    = [""] * 8
        self.mute_states    = [False] * 64
        self.solo_states    = [False] * 64
        self.rec_states     = [False] * 64
        self.meter_levels   = [0] * 64
        self.select_states  = [False] * 8
        self.fader_levels   = [0] * 8
        self.pan_levels     = [0.0] * 8        # −64..+63 (float)
        self.pan_text       = [None] * 8       # what the LCD shows (int)
        self.vpot_ring      = [6] * 8          # 0..11, 6 = detent

        self.selected_track_idx = None
        self.playhead = 0.0

        if not hasattr(self.app, "mcu"):
            self.app.mcu = self
        if not hasattr(self.app, "mcu_manager"):
            self.app.mcu_manager = self

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

    def add_listener(self, event_type: str, callback):
        """Register a callback for generic events (pan, pan_text, track_state, meter, transport …)."""
        self._listeners.setdefault(event_type, []).append(callback)

    def _fire(self, evt, **kw):
        for fn in self._listeners.get(evt, []):
            fn(**kw)

    def send_mcu_button(self, button_type):
        if not self.output_port:
            print("[MCU] No output port available to send", button_type)
            return

        button_type = button_type.upper()

        # Track-specific buttons require a selected track
        if button_type in ("SOLO", "MUTE", "REC") and self.selected_track_idx is None:
            print(f"[MCU] No selected track to send {button_type}")
            return

        if button_type == "SOLO":
            note_num = 8 + self.selected_track_idx
        elif button_type == "MUTE":
            note_num = 16 + self.selected_track_idx
        elif button_type == "REC":  # record arm
            note_num = 0 + self.selected_track_idx
        elif button_type == "PLAY":
            note_num = 94
        elif button_type == "STOP":
            note_num = 93
        elif button_type == "RECORD":  # transport record
            note_num = 95
        elif button_type == "FFWD":
            note_num = 92
        elif button_type == "REW":
            note_num = 91
        else:
            print("[MCU] Unknown button type:", button_type)
            return

        msg_press = mido.Message("note_on", note=note_num, velocity=127, channel=0)
        msg_release = mido.Message("note_on", note=note_num, velocity=0, channel=0)
        self.output_port.send(msg_press)
        self.output_port.send(msg_release)

        if self.debug_mcu:
            if button_type in ("SOLO", "MUTE", "REC"):
                print(f"[MCU] Sent {button_type} for track {self.selected_track_idx + 1} (note {note_num})")
            else:
                print(f"[MCU] Sent {button_type} (note {note_num})")

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
                # Treat NOTE 0–23 (REC/SOLO/MUTE) + 24–31 (SELECT) as authoritative LED/state from Logic.
                pressed = (msg.type == "note_on" and msg.velocity > 0)
                handled = self.handle_button(msg.note, pressed)
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
        """Push all pending updates to Push 2 display in one go."""
        if hasattr(self.app, "update_push2_mute_solo") and self.selected_track_idx is not None:
            self.app.update_push2_mute_solo(track_idx=self.selected_track_idx)
        if hasattr(self.app, "update_play_button_color"):
            self.app.update_play_button_color(self.transport.get("play", False))
        if hasattr(self.app, "update_record_button_color"):
            self.app.update_record_button_color(self.transport.get("record", False))

    def request_bank_led_states(self, selected_idx: int):
        """Ask Logic for LED state for the 8 strips in the current bank, throttled."""
        try:
            port = self.output_port or getattr(self.app, "midi_out", None)
            if not port:
                return
            bank_start = (selected_idx // 8) * 8
            now = time.time()
            if self._led_req_bank == bank_start and (now - self._last_led_req) < self._led_req_interval:
                return  # throttle duplicate requests

            self._led_req_bank = bank_start
            self._last_led_req = now

            for ch in range(bank_start, bank_start + 8):
                msg = mido.Message('sysex', data=definitions.MCU_SYSEX_PREFIX[:4] + [0x20, ch, 0x07])
                port.send(msg)

            if self.debug_mcu:
                print(f"[MCU] Requested LED states for bank {bank_start + 1}-{bank_start + 8}")
        except Exception as e:
            if self.debug_mcu:
                print(f"[MCU] Failed to request bank LED states: {e}")

    # ---------------- SysEx Handlers ----------------
    def handle_sysex(self, data: bytes):
        try:
            # Validate Mackie header
            if not (len(data) >= 5 and list(data[:3]) == definitions.MCU_SYSEX_PREFIX_ANY and data[3] in definitions.ACCEPTED_MCU_MODEL_IDS):
                if self.debug_mcu:
                    print("[MCU] Ignoring non-Mackie sysex:", data[:8], "…")
                return

            cmd = data[4]

            # --- Selection notification: 0x0E <index> 0x03
            if len(data) >= 7 and cmd == 0x0E and data[6] == 0x03:
                track_index = data[5]
                self.selected_track_idx = track_index
                if self.debug_mcu:
                    print("*** Bank/selection → selected_track_idx:", track_index)
                self.pending_update = True

                # request LEDs for bank (throttled)
                self.request_bank_led_states(track_index)

                if getattr(self.app, "mc_mode", None):
                    self.app.mc_mode.update_strip_values()
                # fall through; there may be more content in this SysEx

            payload = data[4:]

            # Host keepalive / ping (0x00): ACK with 0x13 00
            if cmd == 0x00:
                try:
                    self.output_port.send(mido.Message('sysex', data=definitions.MCU_SYSEX_PREFIX[:4] + [0x13, 0x00]))
                    if self.debug_mcu:
                        print("[MCU] → ACK 0x13 00")
                except Exception as e:
                    if self.debug_mcu:
                        print("[MCU] Failed to send ACK:", e)
                return

            # Standard Mackie blocks
            if 0x10 <= cmd <= 0x17 and len(payload) == 9:   # meters
                self._handle_meter_dump(payload)
                return
            if cmd == 0x12:                                 # scribble-strip text
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
            if cmd == 0x21:                                 # transport bits
                self._handle_transport(payload)
                return
            if cmd == 0x72:                                 # time
                self._handle_time(payload[1:])
                return

            # Official 9-byte ring echo
            if len(data) == 9 and data[1:4] == b'\x00\x00\x66' and data[4] == 0x14 and data[5] == 0x20:
                ch  = int(data[6]) & 0x07
                pos = max(0, min(11, int(data[7])))
                self.vpot_ring[ch] = pos
                if self.on_vpot_display:
                    try: self.on_vpot_display(ch, pos)
                    except Exception: import logging; logging.exception("on_vpot_display failed")
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

        # If Logic sends a full 112-byte frame starting at 0, clear old buffers first
        if p == 0 and len(remaining) >= 112:
            self._lcd_top[:] = b' ' * 56
            self._lcd_bot[:] = b' ' * 56

        while remaining:
            if p < 56:
                n = min(56 - p, len(remaining))
                if n > 0:
                    self._lcd_top[p:p+n] = remaining[:n]
                p += n
                remaining = remaining[n:]
            else:
                p2 = p - 56
                if p2 >= 56:
                    # out of range; drop the rest safely
                    break
                n = min(56 - p2, len(remaining))
                if n > 0:
                    self._lcd_bot[p2:p2+n] = remaining[:n]
                p += n
                remaining = remaining[n:]

        # --- TOP: names (7×8)
        top = bytes(self._lcd_top)
        cells_top = [top[i:i+7].decode('ascii','ignore').strip() for i in range(0,56,7)]
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
        cells_bot = [bot[i:i+7].decode('ascii','ignore').strip() for i in range(0,56,7)]

        # (optional) debug so you can verify we actually caught the 0,10,20,... frame
        if self.debug_mcu:
            try:
                print("[MCU] LCD pans:", " | ".join(cells_bot[:8]))
            except Exception:
                pass

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

            self.pan_text[i]   = v
            self.pan_levels[i] = float(v)
            self._fire("pan_text", channel_idx=i, value=float(v))
            self._fire("pan",      channel_idx=i, value=float(v))

        if getattr(self.app, "mc_mode", None) and self.app.is_mode_active(self.app.mc_mode):
            self.app.mc_mode.update_strip_values()
        self.pending_update = True


    def _handle_channel_led(self, payload):
        if len(payload) < 2: return
        ch, bits = int(payload[0]), int(payload[1])
        if ch < 0:
            return
        if ch >= len(self.mute_states):
            grow = ch + 1 - len(self.mute_states)
            self.mute_states.extend([False] * grow)
            self.solo_states.extend([False] * grow)
            self.rec_states.extend([False] * grow)

        self.rec_states[ch]  = bool(bits & 0x04)  # record-arm
        self.solo_states[ch] = bool(bits & 0x02)  # solo
        self.mute_states[ch] = bool(bits & 0x10)  # mute

        # broadcast
        self._fire("track_state", channel_idx=ch,
                   rec=self.rec_states[ch],
                   solo=self.solo_states[ch],
                   mute=self.mute_states[ch])

        if self.debug_mcu:
            print(f"[MCU] Ch{ch + 1} mute={self.mute_states[ch]} solo={self.solo_states[ch]} rec={self.rec_states[ch]}")

        if hasattr(self, "on_track_state") and self.on_track_state:
            self.on_track_state(ch, self.rec_states[ch], self.solo_states[ch], self.mute_states[ch])

        self.app.buttons_need_update = True
        self.pending_update = True

        if ch == self.selected_track_idx:
            self.app.update_push2_mute_solo(track_idx=ch)
            if hasattr(self.app, "update_play_button_color"):
                self.app.update_play_button_color(self.transport["play"])
            if hasattr(self.app, "update_record_button_color"):
                self.app.update_record_button_color(self.transport["record"])

        self.pending_update = True

    def _handle_transport(self, payload):
        if len(payload) < 2:
            return
        bits = payload[1]
        new_transport = {
            "play":   bool(bits & 0x01),
            "stop":   bool(bits & 0x02),
            "record": bool(bits & 0x04),
            "ffwd":   bool(bits & 0x10),
            "rew":    bool(bits & 0x20),
        }
        if new_transport != self.transport:
            self.transport = new_transport
            if self.debug_mcu:
                print("[MCU] Transport update:", self.transport)
            if self.on_transport_change:
                self.on_transport_change(self.transport)
            self.emit_event("transport", state=self.transport)
            self.pending_update = True


    def _handle_time(self, payload):
        self.playhead = payload

    def emit_event(self, event_type, **kwargs):
        """Dispatch to the old dedicated hooks *and* any add_listener() hooks."""
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
            self.on_track_state(
                kwargs.get("channel_idx"),
                kwargs.get("rec"),
                kwargs.get("solo"),
                kwargs.get("mute"),
            )

        for cb in self._listeners.get(event_type, []):
            try:
                cb(**kwargs)
            except Exception as e:
                if self.debug_mcu:
                    print(f"[MCU] listener for '{event_type}' raised:", e)

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
                except Exception as e:
                    if self.debug_mcu:
                        print("[MCU] Failed to parse selected track:", e)

            # --- Transport buttons ---
            if label in ["play", "stop", "record", "ffwd", "rew"]:
                self.transport[label] = pressed
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

        if self.debug_mcu:
            print(f"[MCU] CC {control} = {value}")

    def handle_pitchbend(self, channel, pitch):
        """
        Logic → MCU fader refresh.
        `pitch` comes in as –8192…+8191 (mido already signed-decodes it).
        """
        level = max(0.0, min(1.0, (pitch + 8192) / 16383.0))

        if channel >= len(self.fader_levels):
            self.fader_levels.extend([0.0] * (channel + 1 - len(self.fader_levels)))
        self.fader_levels[channel] = level

        if self.on_fader:
            self.on_fader(channel, level)

        if getattr(self.app, "mc_mode", None) and self.app.is_mode_active(self.app.mc_mode):
            self.app.mc_mode.update_encoders()
            self.app.mc_mode.update_strip_values()

        self.pending_update = True

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
