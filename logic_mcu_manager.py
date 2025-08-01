import mido
import threading


class LogicMCUManager:
    BUTTON_MAP = {
        # --- Channel strip buttons ---
        **{i: f"REC[{i+1}]" for i in range(0, 8)},
        **{i: f"SOLO[{i-7}]" for i in range(8, 16)},
        **{i: f"MUTE[{i-15}]" for i in range(16, 24)},
        **{i: f"SELECT[{i-23}]" for i in range(24, 32)},

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
    }

    def __init__(self, app, port_name="IAC Driver LogicMCU_In", enabled=True):
        self.app = app
        self.enabled = enabled
        self.port_name = port_name

        # Transport state
        self.transport = {"play": False, "stop": True, "record": False, "ffwd": False, "rew": False}

        # Callback hooks (event-driven)
        self.on_transport_change = None   # (transport_dict)
        self.on_button = None             # (label, pressed)
        self.on_fader = None              # (channel_idx, level)
        self.on_vpot = None               # (idx, value)
        self.on_track_state = None        # (channel_idx, rec, solo, mute)

        # MIDI plumbing
        self.input_port = None
        self.listener_thread = None
        self.running = False

        # Internal state cache
        self.track_names = [""] * 8
        self.mute_states = [False] * 8
        self.solo_states = [False] * 8
        self.rec_states = [False] * 8
        self.select_states = [False] * 8
        self.fader_levels = [0] * 8
        self.vpot_rings = [0] * 9
        self.playhead = 0.0

    # ---------------- Lifecycle ----------------
    def start(self):
        if not self.enabled:
            print("[MCU] Disabled, not starting")
            return
        try:
            self.input_port = mido.open_input(self.port_name)
            self.running = True
            self.listener_thread = threading.Thread(target=self.listen_loop, daemon=True)
            self.listener_thread.start()
            print("[MCU] Listening on", self.port_name)
        except Exception as e:
            print("[MCU] Could not open port:", e)

    def stop(self):
        self.running = False
        if self.input_port:
            self.input_port.close()
            self.input_port = None
            print("[MCU] Input port closed")

    def listen_loop(self):
        print("[MCU] Starting listen loop")
        for msg in self.input_port:
            if not self.running:
                print("[MCU] Stopping listen loop")
                break

            if msg.type == "sysex":
                self.handle_sysex(msg.data)
            elif msg.type in ("note_on", "note_off"):
                pressed = msg.type == "note_on" and msg.velocity > 0
                self.handle_button(msg.note, pressed)
            elif msg.type == "control_change":
                self.handle_cc(msg.control, msg.value)
            elif msg.type == "pitchwheel":
                self.handle_pitchbend(msg.channel, msg.pitch)

    # ---------------- SysEx Handlers ----------------
    def handle_sysex(self, data):
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

    def _handle_display_text(self, payload):
        text = bytes(payload).decode("ascii", errors="ignore").strip()
        self.track_names = [text[i:i+7].strip() for i in range(0, len(text), 7)]
        print("[MCU] Track names:", self.track_names)

    def _handle_channel_led(self, payload):
        ch, bits = payload[0], payload[1]
        self.mute_states[ch] = not bool(bits & 0x01)
        self.solo_states[ch] = not bool(bits & 0x02)
        self.rec_states[ch] = not bool(bits & 0x04)
        print(f"[MCU] Ch{ch+1} mute={self.mute_states[ch]} solo={self.solo_states[ch]} rec={self.rec_states[ch]}")

        if self.on_track_state:
            self.on_track_state(ch, self.rec_states[ch], self.solo_states[ch], self.mute_states[ch])

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
            print("[MCU] Transport update:", self.transport)
            if self.on_transport_change:
                self.on_transport_change(self.transport)
            self.emit_event("transport", state=self.transport)

    def _handle_vpot(self, payload):
        idx, val = payload[0], payload[1]
        self.vpot_rings[idx] = val
        print(f"[MCU] VPot {idx} = {val}")
        if self.on_vpot:
            self.on_vpot(idx, val)

    def _handle_time(self, payload):
        self.playhead = payload
        print("[MCU] Playhead raw:", payload)

    def emit_event(self, event_type, **kwargs):
        """Generic event dispatcher."""
        if event_type == "button" and self.on_button:
            self.on_button(kwargs.get("label"), kwargs.get("pressed"))
        elif event_type == "transport" and self.on_transport_change:
            self.on_transport_change(kwargs.get("state"))

    # ---------------- Realtime Handlers ----------------
    def handle_button(self, note, pressed):
        label = self.BUTTON_MAP.get(note)
        if label:
            # Update transport state for known transport buttons
            if label in ["play", "stop", "record", "ffwd", "rew"]:
                self.transport[label] = pressed
                if self.on_transport_change:
                    self.on_transport_change(self.transport)
                self.emit_event("transport", state=self.transport)

            if self.on_button:
                self.on_button(label, pressed)
            self.emit_event("button", label=label, pressed=pressed)
        else:
            self.emit_event("button_unknown", note=note, pressed=pressed)

    def handle_cc(self, control, value):
        if 64 <= control <= 71:  # VPots
            idx = control - 64
            self.vpot_rings[idx] = value
            print(f"[MCU] VPot {idx} = {value}")
            if self.on_vpot:
                self.on_vpot(idx, value)
        elif 72 <= control <= 79:  # Faders
            idx = control - 72
            level = value / 127.0
            self.fader_levels[idx] = level
            print(f"[MCU] Fader {idx+1} = {level:.3f}")
            if self.on_fader:
                self.on_fader(idx, level)
        else:
            print(f"[MCU] CC {control} = {value}")

    def handle_pitchbend(self, channel, value):
        print(f"[MCU] Pitchbend channel={channel+1} value={value}")
