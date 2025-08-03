import mido
import threading
import time


class LogicMCUManager:
    SOLO_OFF_CONFIRM_TIME = 2  # seconds

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
    }

    def __init__(self, app, port_name="IAC Driver LogicMCU_In", enabled=True, update_interval=0.05):
        self.app = app
        self.enabled = enabled
        self.port_name = port_name
        self.update_interval = update_interval  # Minimum time between display updates (50ms default)

        self.debug_mcu = getattr(app, "debug_mcu", False)
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

        # Track/LED state caches
        self.track_names = [""] * 8
        self.mute_states = [False] * 8
        self.solo_states = [False] * 8
        self.rec_states = [False] * 8
        self.select_states = [False] * 8
        self.fader_levels = [0] * 8
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
        except Exception as e:
            print("[MCU] Could not open port:", e)

    def stop(self):
        self.running = False
        if self.input_port:
            self.input_port.close()
            self.input_port = None
            if self.debug_mcu:
                print("[MCU] Input port closed")

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
        """
        Unified SysEx handler for Logic MCU:
        - Detects track selection via GUI/arrow keys
        - Immediately updates Push 2 LEDs from cached state
        - Requests LED refresh for all tracks in the current bank
        - Handles standard MCU SysEx commands
        """
        try:
            # --- Track selection via GUI/Arrow ---
            if (
                    len(data) >= 8
                    and data[0:5] == [0xF0, 0x00, 0x00, 0x66, 0x14]
                    and data[5] == 0x0E
                    and data[7] == 0x03
            ):
                track_index = data[6]  # 0-based in visible bank
                self.selected_track_idx = track_index
                bank_start = (track_index // 8) * 8
                bank_tracks = list(range(bank_start, bank_start + 8))

                if self.debug_mcu:
                    print(f"[MCU] (GUI/Arrow) Selected track index set to {track_index + 1} (Bank {bank_start+1}-{bank_start+8})")

                # 1️⃣ Instant Push2 LED update from cache for ALL tracks in bank
                if hasattr(self.app, "update_push2_mute_solo"):
                    for ch in bank_tracks:
                        self.app.update_push2_mute_solo(track_idx=ch)

                # 2️⃣ Request LED state for ALL 8 tracks in this bank
                for ch in bank_tracks:
                    self.request_channel_led_state(ch)

                # 3️⃣ Delay and then reassert SOLO/MUTE states for ALL tracks in bank
                def delayed_bank_reassert():
                    time.sleep(0.2)  # allow Logic's own LED updates to finish
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
                                print(f"[SOLO DEBUG] Reasserted Track {ch+1} - solo={self.solo_states[ch]} mute={self.mute_states[ch]}")

                threading.Thread(target=delayed_bank_reassert, daemon=True).start()
                return  # ✅ End of track-selection handling

            # --- Standard MCU SysEx Handling ---
            if not self.enabled or data[:4] != (0, 0, 102, 20):
                return

            payload = data[4:]
            cmd = payload[0]

            if cmd == 0x12:
                self._handle_display_text(payload[1:])
            elif cmd == 0x20:
                self._handle_channel_led(payload[1:])
            elif cmd == 0x21:
                self._handle_transport(payload[1:])
            elif cmd == 0x0E:
                self._handle_vpot(payload[1:])
            elif cmd == 0x72:
                self._handle_time(payload[1:])

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
        text = bytes(payload).decode("ascii", errors="ignore").strip()
        self.track_names = [text[i:i + 7].strip() for i in range(0, len(text), 7)]
        print("[MCU] Track names:", self.track_names)
        # Force Push2 mute/solo LED refresh after big state dump
        if hasattr(self.app, "update_push2_mute_solo"):
            self.app.update_push2_mute_solo()
        self.pending_update = True

    def _handle_channel_led(self, payload):
        ch, bits = payload[0], payload[1]
        now = time.time()

        # Record arm
        self.rec_states[ch] = bool(bits & 0x04)

        # Solo LED with debounce for OFF
        new_solo = bool(bits & 0x08)
        if new_solo != self.solo_states[ch]:
            if not new_solo:
                last_pending = getattr(self, "_solo_off_pending", {}).get(ch)
                if last_pending and (now - last_pending) > self.SOLO_OFF_CONFIRM_TIME:
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

        # Mute LED
        self.mute_states[ch] = bool(bits & 0x10)

        if self.debug_mcu:
            print(f"[MCU] Ch{ch + 1} mute={self.mute_states[ch]} solo={self.solo_states[ch]} rec={self.rec_states[ch]}")

        # Fire track state callback
        if self.on_track_state:
            self.on_track_state(ch, self.rec_states[ch], self.solo_states[ch], self.mute_states[ch])

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

    def _handle_vpot(self, payload):
        idx, val = payload[0], payload[1]
        self.vpot_rings[idx] = val
        if self.on_vpot:
            self.on_vpot(idx, val)
            self.pending_update = True

    def _handle_time(self, payload):
        self.playhead = payload

    def emit_event(self, event_type, **kwargs):
        """Generic event dispatcher."""
        if event_type == "button" and self.on_button:
            self.on_button(kwargs.get("label"), kwargs.get("pressed"))
        elif event_type == "transport" and self.on_transport_change:
            self.on_transport_change(kwargs.get("state"))
        elif event_type == "fader" and self.on_fader:
            self.on_fader(kwargs.get("channel_idx"), kwargs.get("level"))
        elif event_type == "vpot" and self.on_vpot:
            self.on_vpot(kwargs.get("idx"), kwargs.get("value"))
        elif event_type == "track_state" and self.on_track_state:
            self.on_track_state(kwargs.get("channel_idx"), kwargs.get("rec"), kwargs.get("solo"), kwargs.get("mute"))

    # ---------------- Realtime Handlers ----------------
    def handle_button(self, note, pressed):
        label = self.BUTTON_MAP.get(note)

        if label:
            # --- Push 2 Setup/User buttons in MCU mode ---
            if label == "SETUP" and pressed:
                if hasattr(self.app, "toggle_and_rotate_settings_mode"):
                    self.app.toggle_and_rotate_settings_mode()
                    self.app.buttons_need_update = True
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
            self.mute_states[track_idx] = (value == 127)
            if self.debug_mcu:
                print(f"[MCU] Mute[{track_idx + 1}] = {self.mute_states[track_idx]}")
            if track_idx == self.selected_track_idx and hasattr(self.app, "update_push2_mute_solo"):
                self.app.update_push2_mute_solo(track_idx=track_idx)

        # --- SOLO CC messages ---
        elif 64 <= control <= 71:
            track_idx = control - 64
            now = time.time()
            new_solo = (value == 127)

            if new_solo != self.solo_states[track_idx]:
                if not new_solo:
                    last_pending = getattr(self, "_solo_off_pending", {}).get(track_idx)
                    if last_pending and (now - last_pending) > self.SOLO_OFF_CONFIRM_TIME:
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

    def handle_pitchbend(self, channel, value):
        return None
