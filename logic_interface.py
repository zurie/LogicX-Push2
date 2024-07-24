from oscpy.client import OSCClient
from oscpy.server import OSCThreadServer
import definitions
import threading
import time
import push2_python
import atexit

osc_send_host = "127.0.0.1"
osc_send_port = 8000
osc_receive_port = 9004

tracks_state_fps = 4.0
transport_state_fps = 10.0
bpm_button_names = [
    push2_python.constants.BUTTON_UPPER_ROW_1,
    push2_python.constants.BUTTON_UPPER_ROW_2,
    push2_python.constants.BUTTON_UPPER_ROW_3,
    push2_python.constants.BUTTON_UPPER_ROW_4,
    push2_python.constants.BUTTON_UPPER_ROW_5,
    push2_python.constants.BUTTON_UPPER_ROW_6,
    push2_python.constants.BUTTON_UPPER_ROW_7,
    push2_python.constants.BUTTON_UPPER_ROW_8
]


def to_utf8(utf8):
    return utf8.decode("utf-8")


class LogicInterface(definitions.LogicMode):
    def __init__(self, app):
        self.app = app
        self.osc_sender = OSCClient(osc_send_host, osc_send_port, encoding='utf8')
        self.osc_server = OSCThreadServer(default_handler=self.handle_logic_message)
        self.osc_server.listen(address='0.0.0.0', port=osc_receive_port, default=True)
        self.setup_osc_bindings()

        self.state_transport_check_thread = threading.Thread(target=self.check_transport_state)
        self.state_tracks_check_thread = threading.Thread(target=self.check_tracks_state)

        self.last_received_tracks_raw_state = ""
        self.parsed_state = {}

        # Ensure the OSC server is stopped when the program exits
        atexit.register(self.cleanup)

    def setup_osc_bindings(self):
        self.osc_server.bind(b'/stateFromLogic/play', self.update_play_button)
        self.osc_server.bind(b'/stateFromLogic/stop', self.update_stop)
        self.osc_server.bind(b'/stateFromLogic/click', self.update_metronome_button)
        self.osc_server.bind(b'/stateFromLogic/beats', self.bpm_lights)
        self.osc_server.bind(b'/stateFromLogic/record', self.update_record_button)

    def start_threads(self):
        self.state_transport_check_thread.start()
        self.state_tracks_check_thread.start()

    def check_transport_state(self):
        while True:
            time.sleep(1.0 / transport_state_fps)
            self.osc_sender.send_message('/state/transport', [])

    def check_tracks_state(self):
        while True:
            time.sleep(1.0 / tracks_state_fps)
            self.osc_sender.send_message('/state/tracks', [])

    def update_button(self, value, attribute, button, on_color, off_color):
        is_active = value == 1.0
        setattr(definitions, attribute, is_active)
        self.app.logic_interface.get_buttons_state()
        color = on_color if is_active else off_color
        self.app.push.buttons.set_button_color(button, color)  # Ensure push is referenced through app

    def update_stop(self, *values):
        definitions.isPlaying = 0.0
        definitions.isRecording = 0.0
        self.app.logic_interface.get_buttons_state()

    def update_play_button(self, *values):
        definitions.isPlaying = 1.0
        value = values[0] if values else 0.0
        self.update_button(value, 'isPlaying', push2_python.constants.BUTTON_PLAY, definitions.GREEN, definitions.LIME)

    def update_metronome_button(self, value):
        self.update_button(value, 'isMetronome', push2_python.constants.BUTTON_METRONOME, definitions.WHITE,
                           definitions.OFF_BTN_COLOR)

    def update_record_button(self, *values):
        definitions.isRecording = 1.0
        value = values[0] if values else 0.0
        self.update_button(value, 'isRecording', push2_python.constants.BUTTON_RECORD, definitions.RED,
                           definitions.GREEN)

    def send_message(self, address, args=None):
        if args is None:
            args = []
        self.osc_sender.send_message(address, args)

    def automate(self):
        self.send_message('/push2/automate')

    def repeat(self):
        self.send_message('/push2/repeat')

    def layout(self):
        self.send_message('/push2/layout')

    def session(self):
        self.send_message('/push2/session')

    def add_track(self):
        self.send_message('/push2/add_track')

    def device(self):
        self.send_message('/push2/device')

    def mix(self):
        self.send_message('/push2/mix')

    def browse(self):
        self.send_message('/push2/browse')

    def clip(self):
        self.send_message('/push2/clip')

    def fixed_length(self):
        self.send_message('/push2/fixed_length')

    def new(self):
        self.send_message('/push2/new')

    def new_next(self):
        self.send_message('/push2/new_next')

    def duplicate(self):
        self.send_message('/push2/duplicate')

    def double_loop(self):
        self.send_message('/push2/double_loop')

    def double(self):
        self.send_message('/push2/double')

    def convert(self):
        self.send_message('/push2/convert')

    def stop_clip(self):
        self.send_message('/push2/stop_clip')

    def mute(self):
        self.send_message('/push2/mute')

    def mute_off(self):
        self.send_message('/push2/mute_off')

    def solo(self):
        self.send_message('/push2/solo')

    def solo_lock(self):
        self.send_message('/push2/solo_lock')

    def undo(self):
        self.send_message('/push2/undo')

    def repeat_off(self):
        self.send_message('/push2/repeat_off')

    def redo(self):
        self.send_message('/push2/redo')

    def delete(self):
        self.send_message('/push2/delete')

    def pause(self):
        self.send_message('/push2/pause', [])

    def stop(self):
        self.send_message('/push2/stop', [])

    def play(self):
        if definitions.isPlaying:
            self.send_message('/push2/stop', [1.0])
            definitions.isPlaying = 0.0
        else:
            self.send_message('/push2/play', [1.0])
            definitions.isPlaying = 1.0
        self.get_buttons_state()  # Update button states

    def record(self):
        if definitions.isRecording:
            self.send_message('/push2/record_off', [1.0])
            definitions.isRecording = 0.0
        else:
            self.send_message('/push2/record_on', [1.0])
            definitions.isRecording = 1.0
        self.get_buttons_state()  # Update button states

    def arrow_keys(self, direction, shift, loop):
        if direction in ['up', 'down', 'left', 'right']:
            suffix = "_shift" if shift else "_loop" if loop else ""
            self.send_message(f'/push2/{direction}{suffix}')

    def metronome_on_off(self):
        self.send_message('/push2/click', [])

    def get_buttons_state(self):
        is_playing = definitions.isPlaying
        metronome_on = definitions.isMetronome
        is_recording = definitions.isRecording

        self.app.push.buttons.set_button_color(push2_python.constants.BUTTON_PLAY,
                                               definitions.LIME if not is_playing else definitions.GREEN)
        self.app.push.buttons.set_button_color(push2_python.constants.BUTTON_RECORD,
                                               definitions.GREEN if not is_recording else definitions.RED)
        self.app.push.buttons.set_button_color(push2_python.constants.BUTTON_METRONOME,
                                               definitions.OFF_BTN_COLOR if not metronome_on else definitions.WHITE)
        self.app.midi_cc_mode.update_buttons()
        return is_playing, metronome_on, is_recording

    def get_bpm(self):
        return self.parsed_state.get('bpm', 120)

    def set_bpm(self, bpm):
        self.send_message('/transport/setBpm', [float(bpm)])

    def bpm_lights(self, value):
        beat = to_utf8(value).split()
        beat_num = int(float(beat[1]))
        is_even = beat_num % 2 == 0
        self.app.push.buttons.set_button_color(push2_python.constants.BUTTON_PLAY,
                                               definitions.GREEN if is_even else definitions.GREEN_DARK)

        for button_name in bpm_button_names:
            color = definitions.RED if definitions.isRecording else definitions.GREEN if is_even else definitions.BLACK
            self.app.push.buttons.set_button_color(button_name, color)

        if definitions.isRecording:
            record_color = definitions.RED if beat_num % 4 else definitions.RED_DARK
            self.app.push.buttons.set_button_color(push2_python.constants.BUTTON_RECORD, record_color)

        return True

    def quantize(self, index, quantize, shift, loop, repeat, off):
        actions = ["quantize", "shift", "repeat", "loop", "off"]
        time_values = ["1_32T", "1_32", "1_16T", "1_16", "1_8T", "1_8", "1_4T", "1_4"]

        if index in time_values:
            action = next((action for action in actions if locals()[action]), None)
            if action:
                self.send_message(f'/push2/quantize/{index.replace("/", "_")}_{action}')

    def handle_logic_message(self, address, *values):
        print(f"Received message on {address}: {values}")
        # Handle the message based on the address and values

    def cleanup(self):
        self.osc_server.stop_all()
