import mido
import threading
import time
import definitions


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
        119: "USER",  # Push 2 User button
        120: "MIX"
    }

    def __init__(self, app, port_name="IAC Driver LogicMCU_In", enabled=True, update_interval=0.05):
        self.button_press_times = None
        self.app = app
        self.enabled = enabled
        self.port_name = port_name
        self.update_interval = update_interval  # Minimum time between display updates (50ms default)

        self.debug_mcu = getattr(app, "debug_mcu", False)
        self._listeners = {"track_state": [], "pan": [], "transport": []}
        self.transport = {"play": False, "stop": True, "record": False, "ffwd": False, "rew": False}
        self._solo_off_pending = {}
        # Callback hooks
        self.on_transport_change = None
        self.on_button = None
        self.on_fader = None
        self.on_vpot = None
        self.on_track_state = None

        self.input_port = None
        self.output_port = None
        self.listener_thread = None
        self.running = False

        # State cache for throttling
        self.last_update_time = 0
        self.pending_update = False
        # Simple MCU track‑type colours (8‑color rotating palette)

        self.track_colors = [definitions.MIXER_PALETTE[i % len(definitions.MIXER_PALETTE)] for i in range(8)]
        # Track/LED state caches
        self.track_names = [""] * 8
        self.mute_states = [False] * 8
        self.solo_states = [False] * 8
        self.rec_states = [False] * 8
        self.select_states = [False] * 8
        self.fader_levels = [0] * 8
        self.pan_levels = [0] * 8
        self.vpot_rings = [0] * 9
        self.selected_track_idx = None
        self.playhead = 0.0

    def start(self):
        if not self.enabled:
            if self.debug_mcu:
                print("[MCU] Disabled, not starting")
            return
        try:
            self.input_port = mido.open_input(self.port_name)
            mcu_out_name = self.port_name.replace("_In", "_Out")
            self.output_port = mido.open_output(mcu_out_name)
            self.running = True
            self.listener_thread = threading.Thread(target=self.listen_loop, daemon=True)
            self.listener_thread.start()
            print("[MCU] Listening on", self.port_name)
            print("[MCU] Sending on", mcu_out_name)
            # right after self.output_port = mido.open_output(...)
            # tell Logic “hey, I’m a Mackie Control”
            self.output_port.send(
                mido.Message('sysex', data=[0x00, 0x00, 0x66, 0x14, 0x00])
            )
        except Exception as e:
            print("[MCU] Could not open port:", e)

    def stop(self):
        self.running = False
        if self.input_port:
            self.input_port.close()
            self.input_port = None
            if self.debug_mcu:
                print("[MCU] Input port closed")

    def add_listener(self, event_type: str, callback):
        """Register a callback for generic events (pan, track_state …)."""
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

            if msg.type == "sysex":
                self.handle_sysex(bytes(msg.data))
            elif msg.type in ("note_on", "note_off"):
                pressed = msg.type == "note_on" and msg.velocity > 0
                handled = self.handle_button(msg.note, pressed)

                # If MCU didn't handle it, pass it through to Push 2 handler
                if handled is False and hasattr(self.app, "on_push2_midi_message"):
                    self.app.on_push2_midi_message(msg)
            elif msg.type == "control_change":
                self.handle_cc(msg.control, msg.value)
            elif msg.type == "pitchwheel":
                self.handle_pitchbend(msg.channel, msg.pitch)

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

    # ---------------- SysEx Handlers ----------------
    def handle_sysex(self, data):
        try:
            # --- Track selection via GUI/Arrow ---
            if (
                    len(data) >= 8
                    and list(data[:5]) == [0xF0, 0x00, 0x00, 0x66, 0x14]
                    and data[5] == 0x0E
                    and data[7] == 0x03
            ):
                print("*** Bank changed -> selected_track_idx:",
                      self.selected_track_idx, "(waiting for LED dump)")
                track_index = data[6]  # 0-based in visible bank
                self.selected_track_idx = track_index
                bank_start = (track_index // 8) * 8
                bank_tracks = list(range(bank_start, bank_start + 8))
                self._fire("selected_track", idx=track_index)
                if self.debug_mcu:
                    print(
                        f"[MCU] (GUI/Arrow) Selected track index set to {track_index + 1} (Bank {bank_start + 1}-{bank_start + 8})"
                    )
                # --- NEW: wipe the old colours so Push won’t show them ---
                self.solo_states = [False] * 8
                self.mute_states = [False] * 8
                self.pending_update = True  # repaint ASAP
                if hasattr(self.app, "update_push2_mute_solo"):
                    for ch in bank_tracks:
                        self.app.update_push2_mute_solo(track_idx=ch)
                for ch in bank_tracks:
                    self.request_channel_led_state(ch)

                def delayed_bank_reassert():
                    time.sleep(self.app.bank_reassert_delay)
                    if self.output_port:
                        for ch in bank_tracks:
                            solo_note = 8 + ch
                            mute_note = 16 + ch
                            self.output_port.send(mido.Message(
                                "note_on", note=solo_note,
                                velocity=127 if self.solo_states[ch] else 0, channel=0
                            ))
                            self.output_port.send(mido.Message(
                                "note_on", note=mute_note,
                                velocity=127 if self.mute_states[ch] else 0, channel=0
                            ))
                            if self.debug_mcu:
                                print(
                                    f"[SOLO DEBUG] Reasserted Track {ch + 1} - solo={self.solo_states[ch]} mute={self.mute_states[ch]}"
                                )

                threading.Thread(target=delayed_bank_reassert, daemon=True).start()
                # Don't return: Standard MCU messages may follow in same event!

            # --- Standard MCU SysEx Handling ---
            if not self.enabled:
                print("[DEBUG] MCU is not enabled; skipping SysEx")
                return
            # print(f"[DEBUG] handle_sysex raw data: {data!r}")

            # Accept Mackie MCU SysEx: 00 00 66 14 ...
            if not (len(data) > 3 and list(data[:4]) == [0x00, 0x00, 0x66, 0x14]):
                print(f"[DEBUG] Skipping SysEx, bad header: {data[:8]!r}")
                return

            payload = data[4:]
            if not payload:
                print("[DEBUG] SysEx: No payload after header!")
                return

            cmd = payload[0]

            if cmd == 0x12:
                self._handle_display_text(payload)
            elif cmd == 0x20:
                self._handle_channel_led(payload[1:])
            elif cmd == 0x21:
                self._handle_transport(payload[1:])
            elif cmd == 0x0E:
                self._handle_vpot(payload[1:])
            elif cmd == 0x72:
                self._handle_time(payload[1:])
            else:
                if self.debug_mcu:
                    print(f"[MCU] Unhandled SysEx cmd: 0x{cmd:02X}, payload: {payload}")

        except Exception as e:
            if self.debug_mcu:
                print("[MCU] Failed to parse SysEx:", e)

    def request_channel_led_state(self, track_idx):
        try:
            if self.input_port and self.input_port.closed is False:
                # MCU LED request: F0 00 00 66 14 20 <channel> F7
                # <channel> is 0-based
                msg = mido.Message('sysex', data=[0x00, 0x00, 0x66, 0x14, 0x20, track_idx])
                if self.app and getattr(self.app, 'midi_out', None):
                    self.app.midi_out.send(msg)
                    if self.debug_mcu:
                        print(f"[MCU] Requested LED state for channel {track_idx + 1}")
        except Exception as e:
            if self.debug_mcu:
                print(f"[MCU] Failed to request channel LED state: {e}")

    def _handle_display_text(self, payload):
        # print("[DEBUG] Entered _handle_display_text")
        # print(f"[DEBUG] RAW DISPLAY TEXT PAYLOAD: {payload}")

        if len(payload) >= 2:
            offset = payload[1]
            text_bytes = payload[2:]
            text_bytes = text_bytes + b' ' * (56 - len(text_bytes))
            text_bytes = text_bytes[:56]  # Always 56 bytes
            text = text_bytes.decode("ascii", errors="ignore")
            track_names = [text[i:i + 7].strip() for i in range(0, 56, 7)]
            # print(f"[MCU] Track names (offset {offset}):", track_names)

            # 1. Ignore all offsets except 0
            if offset > 0:
                return

            # 2. Ignore if all names are empty or '-'
            if all(n.strip() in ['', '-'] for n in track_names):
                return

            # A ctually apply the names
            self.track_names = (track_names + [''] * 8)[:8]
            if self.app.is_mode_active(self.app.track_mode):
                self.app.track_mode.update_strip_values()   # refresh the screen
            if hasattr(self.app, "update_push2_mute_solo"):
                self.app.update_push2_mute_solo()
            self.pending_update = True
            if self.app.is_mode_active(self.app.track_mode):
                self.app.track_mode.activate()
        else:
            print("[DEBUG] No strips in payload; ignoring.")

    def _handle_channel_led(self, payload):
        print(f"<< LED dump for ch {payload[0]} ({'new' if payload[0] == 0 else ''})")

        ch, bits = payload[0], payload[1]
        now = time.time()

        # Record arm
        self.rec_states[ch] = bool(bits & 0x04)
        new_solo = bool(bits & 0x08)
        self.mute_states[ch] = bool(bits & 0x10)
        if new_solo != self.solo_states[ch]:
            if not new_solo:
                last_pending = getattr(self, "_solo_off_pending", {}).get(ch)
                if last_pending and (now - last_pending) > self.app.solo_off_confirm_time:
                    self.solo_states[ch] = False
                    self._solo_off_pending.pop(ch, None)
                    if self.debug_mcu:
                        print(f"[SOLO DEBUG] Confirmed OFF (Track {ch + 1})")
                else:
                    self._solo_off_pending = getattr(self, "_solo_off_pending", {})
                    self._solo_off_pending[ch] = now
                    if self.debug_mcu:
                        print(f"[SOLO DEBUG] OFF pending (Track {ch + 1})")
            else:
                self.solo_states[ch] = True
                if hasattr(self, "_solo_off_pending") and ch in self._solo_off_pending:
                    self._solo_off_pending.pop(ch, None)
        else:
            if hasattr(self, "_solo_off_pending") and ch in self._solo_off_pending:
                self._solo_off_pending.pop(ch, None)
        # fire event for anybody interested ---------------------------------
        self._fire("track_state", channel_idx=ch,
                   rec=self.rec_states[ch],
                   solo=self.solo_states[ch],
                   mute=self.mute_states[ch])
        # Mute LED
        self.mute_states[ch] = bool(bits & 0x10)

        if self.debug_mcu:
            print(f"[MCU] Ch{ch + 1} mute={self.mute_states[ch]} solo={self.solo_states[ch]} rec={self.rec_states[ch]}")

        # keep legacy callback & UI flag ------------------------------------
        if hasattr(self, "on_track_state") and self.on_track_state:
            self.on_track_state(ch, self.rec_states[ch],
                                self.solo_states[ch], self.mute_states[ch])
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
            "play": bool(bits & 0x01),
            "stop": bool(bits & 0x02),
            "record": bool(bits & 0x04),
            "ffwd": bool(bits & 0x10),
            "rew": bool(bits & 0x20),
        }

        if new_transport != self.transport:
            self.transport = new_transport
            if self.debug_mcu:
                print("[MCU] Transport update:", self.transport)
            if self.on_transport_change:
                self.on_transport_change(self.transport)
            self.emit_event("transport", state=self.transport)
            self.pending_update = True

    # ───────────────────────────────────────────────────────────────────────
    #  VPOT / PAN                                                            ─
    # ───────────────────────────────────────────────────────────────────────
    def _handle_vpot(self, payload):
        """Store ring LED value; actual pan comes from CC 48-55."""
        idx, ring_val = payload[0], payload[1]
        self.vpot_rings[idx] = ring_val

        # forward raw ring value to any callback
        if self.on_vpot:
            self.on_vpot(idx, ring_val)

        # --------------------------------------------------------------------

    def _handle_time(self, payload):
        self.playhead = payload

    def emit_event(self, event_type, **kwargs):
        """Dispatch to the old dedicated hooks *and* any add_listener() hooks."""
        # 1. dedicated single-slot callbacks (kept for backward-compat)
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

        # 2. broadcast to any listeners registered via add_listener()
        for cb in self._listeners.get(event_type, []):
            try:
                cb(**kwargs)
            except Exception as e:
                if self.debug_mcu:
                    print(f"[MCU] listener for '{event_type}' raised:", e)

    def get_visible_track_names(self):
        """
        Return a list of 8 track names for the currently visible bank.
        """
        bank_start = 0
        if self.selected_track_idx is not None:
            bank_start = (self.selected_track_idx // 8) * 8
        # Always return 8 names, padding with blanks if needed
        names = (self.track_names + [""] * 8)  # pad in case too short
        return names[bank_start:bank_start + 8]

    def update_track_names_from_sysex(self, payload):
        """
        Robustly split a 56-char MCU track name field into 8 names, stripping spaces.
        """
        # Payload is expected as bytes
        text = bytes(payload).decode("ascii", errors="ignore")
        # MCU gives 7 chars per name, 8 names = 56 chars
        track_names = [text[i:i + 7].strip() for i in range(0, 56, 7)]
        # If payload shorter than 56, pad with empty strings
        if len(track_names) < 8:
            track_names += [""] * (8 - len(track_names))
        self.track_names = track_names[:8]
        print("[MCU] Track names updated:", self.track_names)

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
                    pressed_time = self.button_press_times.get("MIX", 0)
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
                if idx == self.selected_track_idx and hasattr(self.app, "update_push2_mute_solo"):
                    self.app.update_push2_mute_solo(track_idx=idx)

            elif label.startswith("SOLO["):
                idx = int(label[5:-1]) - 1
                self.solo_states[idx] = pressed
                if idx == self.selected_track_idx:
                    self.app.update_push2_mute_solo(track_idx=idx)

            elif label.startswith("MUTE["):
                idx = int(label[5:-1]) - 1
                self.mute_states[idx] = pressed
                if idx == self.selected_track_idx:
                    self.app.update_push2_mute_solo(track_idx=idx)

            # --- Track SELECT buttons ---
            if label.startswith("SELECT[") and pressed:
                try:
                    self.selected_track_idx = int(label.split("[")[1].strip("]")) - 1
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
            return True  # ✅ MCU handled this button

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
            return False  # ✅ Unhandled by MCU, passed on

    # ---------------- Main MIDI Event Loop ----------------
    def handle_midi_message(self, msg):
        if msg.type in ("note_on", "note_off"):
            self.handle_button(msg.note, msg.velocity > 0)
        elif msg.type == "sysex":
            self.handle_sysex(list(msg.data))

    def handle_cc(self, control, value):
        # --- MUTE CC messages ---
        if 48 <= control <= 55:
            track_idx = control - 48

            if value in (0, 127):
                # MUTE LED (unchanged)
                self.mute_states[track_idx] = (value == 127)
                if track_idx == self.selected_track_idx and hasattr(self.app, "update_push2_mute_solo"):
                    self.app.update_push2_mute_solo(track_idx=track_idx)
                if self.debug_mcu:
                    print(f"[MCU] Mute[{track_idx + 1}] = {self.mute_states[track_idx]}")
            else:
                # -------- PAN DETENT TABLE --------
                # Logic sends only 11 distinct values for pan on MCU:
                PAN_CC_MAP = {
                    17: -64,
                    18: -64,  # sometimes reported at hard‑left too
                    19: -51,
                    20: -38,
                    21: -25,
                    22: 0,
                    23: +13,
                    24: +26,
                    25: +38,
                    26: +51,
                    27: +64,
                }
                pan_val = PAN_CC_MAP.get(value, 0)
                self.pan_levels[track_idx] = pan_val

                if self.debug_mcu:
                    print(f"[MCU] Pan[{track_idx + 1}] = {pan_val}")

                self.emit_event("pan", channel_idx=track_idx, value=pan_val)
                if getattr(self.app, "track_mode", None) and self.app.is_mode_active(self.app.track_mode):
                    self.app.track_mode.update_strip_values()
                    self.app.track_mode.update_buttons()

        # --- SOLO CC messages ---
        elif 64 <= control <= 71:
            track_idx = control - 64
            now = time.time()
            new_solo = (value == 127)

            if new_solo != self.solo_states[track_idx]:
                if not new_solo:
                    last_pending = getattr(self, "_solo_off_pending", {}).get(track_idx)
                    if last_pending and (now - last_pending) > self.app.solo_off_confirm_time:
                        self.solo_states[track_idx] = False
                        self._solo_off_pending.pop(track_idx, None)
                        if self.debug_mcu:
                            print(f"[SOLO DEBUG] Confirmed OFF (Track {track_idx + 1}) [CC]")
                    else:
                        self._solo_off_pending = getattr(self, "_solo_off_pending", {})
                        self._solo_off_pending[track_idx] = now
                        if self.debug_mcu:
                            print(f"[SOLO DEBUG] OFF pending (Track {track_idx + 1}) [CC]")
                else:
                    self.solo_states[track_idx] = True
                    if hasattr(self, "_solo_off_pending") and track_idx in self._solo_off_pending:
                        self._solo_off_pending.pop(track_idx, None)
            else:
                if hasattr(self, "_solo_off_pending") and track_idx in self._solo_off_pending:
                    self._solo_off_pending.pop(track_idx, None)

            if self.debug_mcu:
                print(f"[MCU] Solo[{track_idx + 1}] = {self.solo_states[track_idx]}")

            if track_idx == self.selected_track_idx and hasattr(self.app, "update_push2_mute_solo"):
                self.app.update_push2_mute_solo(track_idx=track_idx)

        # --- Faders ---
        elif 72 <= control <= 79:
            idx = control - 72
            level = value / 127.0
            self.fader_levels[idx] = level
            self.emit_event("fader", channel_idx=idx, level=level)
        else:
            if self.debug_mcu:
                print(f"[MCU] CC {control} = {value}")

    def handle_pitchbend(self, channel, pitch):
        """
        Logic → MCU fader refresh.
        `pitch` comes in as –8192…+8191 (mido already signed-decodes it).
        """
        level = max(0.0, min(1.0, (pitch + 8192) / 16383.0))

        # grow the cache list if Logic sends master (ch-8) or extenders
        if channel >= len(self.fader_levels):
            self.fader_levels.extend([0.0] * (channel + 1 - len(self.fader_levels)))
        self.fader_levels[channel] = level

        # callback for anyone listening
        if self.on_fader:
            self.on_fader(channel, level)

        # live UI refresh while Track-Control mode is showing
        if getattr(self.app, "track_mode", None) and self.app.is_mode_active(self.app.track_mode):
            self.app.track_mode.update_encoders()
            self.app.track_mode.update_strip_values()

        self.pending_update = True
