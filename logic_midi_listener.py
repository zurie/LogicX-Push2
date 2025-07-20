import mido
import threading
import time
import definitions

class LogicMidiListener:
    """
    Listens for MIDI Clock + MMC from Logic via IAC Driver to determine Play/Stop/Record state.
    Updates definitions.isPlaying and definitions.isRecording for Push2 LED updates.
    Calls play_state_callback(True/False) and record_state_callback(True/False) for Push2 LED updates.
    """

    def __init__(self, midi_port_name='IAC Driver Default', play_state_callback=None, record_state_callback=None):
        self.midi_port_name = midi_port_name
        self.play_state_callback = play_state_callback
        self.record_state_callback = record_state_callback
        self.running = False
        self.thread = None
        self.last_clock_time = time.time()
        self.clock_timeout = 1.0
        self._last_clock_log = 0

    def start(self):
        if self.running:
            print("[LogicMidiListener] Already running.")
            return
        self.running = True
        self.thread = threading.Thread(target=self._listen_loop, daemon=True)
        self.thread.start()
        print(f"[LogicMidiListener] Started MIDI listener on: {self.midi_port_name}")

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join()
        print("[LogicMidiListener] Stopped MIDI listener.")

    def _listen_loop(self):
        try:
            with mido.open_input(self.midi_port_name) as inport:
                print(f"[LogicMidiListener] Listening on: {self.midi_port_name}")
                while self.running:
                    for msg in inport.iter_pending():
                        self._handle_message(msg)
                    if time.time() - self.last_clock_time > self.clock_timeout:
                        if definitions.isPlaying != 0.0:
                            definitions.isPlaying = 0.0
                            print("[LogicMidiListener] Logic Stopped (Clock timeout)")
                            if self.play_state_callback:
                                self.play_state_callback(False)
                    time.sleep(0.01)
        except IOError:
            print(f"[LogicMidiListener] Could not open MIDI input: {self.midi_port_name}")

    def _handle_message(self, msg):
        now = time.time()

        # Debug print raw message for learning MCP
        # print(f"[MCP DEBUG] Received message: {msg}")

        # MIDI Clock detection for Play
        if msg.type == 'clock':
            self.last_clock_time = now
            if definitions.isPlaying != 1.0:
                definitions.isPlaying = 1.0
                print("[LogicMidiListener] Logic is Playing (Clock detected)")
                if self.play_state_callback:
                    self.play_state_callback(True)
            if now - self._last_clock_log >= 1.0:
                self._last_clock_log = now

        # MCP Transport: Play
        elif msg.type == 'start':
            definitions.isPlaying = 1.0
            print("[LogicMidiListener] MCP Play received.")
            if self.play_state_callback:
                self.play_state_callback(True)

        # MCP Transport: Stop
        elif msg.type == 'stop':
            definitions.isPlaying = 0.0
            print("[LogicMidiListener] MCP Stop received.")
            if self.play_state_callback:
                self.play_state_callback(False)

        # MCP Transport: Record Arm toggle
        elif msg.type in ['note_on', 'note_off'] and msg.channel == 0:
            if msg.note == 95:  # 0x5F, MCP Record toggle
                if msg.type == 'note_on' and msg.velocity > 0:
                    if definitions.isRecording != 1.0:
                        definitions.isRecording = 1.0
                        print("[LogicMidiListener] MCP Record ON received.")
                        if self.record_state_callback:
                            self.record_state_callback(True)
                else:
                    if definitions.isRecording != 0.0:
                        definitions.isRecording = 0.0
                        print("[LogicMidiListener] MCP Record OFF received.")
                        if self.record_state_callback:
                            self.record_state_callback(False)


if __name__ == "__main__":
    def test_play_callback(is_playing):
        if is_playing:
            print("TEST: Logic is playing (callback).")
        else:
            print("TEST: Logic stopped (callback).")

    def test_record_callback(is_recording):
        if is_recording:
            print("TEST: Logic started recording (callback).")
        else:
            print("TEST: Logic stopped recording (callback).")

    listener = LogicMidiListener(play_state_callback=test_play_callback, record_state_callback=test_record_callback)
    listener.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        listener.stop()
