from oscpy.client import OSCClient
from oscpy.server import OSCThreadServer
import definitions
import threading
import asyncio
import time
import push2_python

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
    app = None
    count = 0
    osc_sender = None
    osc_server = None

    state_transport_check_thread = None
    state_tracks_check_thread = None

    last_received_tracks_raw_state = ""
    parsed_state = {}

    def __init__(self, app):
        self.app = app

        self.osc_sender = OSCClient(osc_send_host, osc_send_port, encoding='utf8')

        self.osc_server = OSCThreadServer()
        sock = self.osc_server.listen(address='0.0.0.0', port=osc_receive_port, default=True)
        self.osc_server.bind(b'/stateFromLogic/play', self.update_play_button)
        self.osc_server.bind(b'/stateFromLogic/click', self.update_metronome_button)
        self.osc_server.bind(b'/stateFromLogic/beats', self.bpm_lights)
        self.osc_server.bind(b'/stateFromLogic/record', self.update_record_button)

        # self.run_get_state_transport_thread()
        # self.run_get_state_tracks_thread()

    def run_get_state_transport_thread(self):
        self.state_transport_check_thread = threading.Thread(target=self.check_transport_state)
        self.state_transport_check_thread.start()

    def run_get_state_tracks_thread(self):
        self.state_tracks_check_thread = threading.Thread(target=self.check_tracks_state)
        self.state_tracks_check_thread.start()

    def check_transport_state(self):
        while True:
            time.sleep(1.0 / transport_state_fps)
            self.osc_sender.send_message('/state/transport', [])

    def check_tracks_state(self):
        while True:
            time.sleep(1.0 / tracks_state_fps)
            self.osc_sender.send_message('/state/tracks', [])

    def update_play_button(self, value):
        definitions.isPlaying = True if value == 1.0 else False
        self.app.logic_interface.get_buttons_state()

    def update_metronome_button(self, value):
        definitions.isMetronome = True if value == 1.0 else False
        self.app.logic_interface.get_buttons_state()

    def update_record_button(self, value):
        definitions.isRecording = True if value == 1.0 else False
        self.app.logic_interface.get_buttons_state()

    def automate(self):
        self.osc_sender.send_message('/push2/automate', [])

    def repeat(self):
        self.osc_sender.send_message('/push2/repeat', [])

    def layout(self):
        self.osc_sender.send_message('/push2/layout', [])

    def session(self):
        self.osc_sender.send_message('/push2/session', [])

    def add_track(self):
        self.osc_sender.send_message('/push2/add_track', [])

    def device(self):
        self.osc_sender.send_message('/push2/device', [])

    def mix(self):
        self.osc_sender.send_message('/push2/mix', [])

    def browse(self):
        self.osc_sender.send_message('/push2/browse', [])

    def clip(self):
        self.osc_sender.send_message('/push2/clip', [])

    def fixed_length(self):
        self.osc_sender.send_message('/push2/fixed_length', [])

    def new(self):
        self.osc_sender.send_message('/push2/new', [])

    def new_next(self):
        self.osc_sender.send_message('/push2/new_next', [])

    def duplicate(self):
        self.osc_sender.send_message('/push2/duplicate', [])

    def quantize(self, index, quantize, shift, loop, repeat, off):
        if index == '1/32t':
            if quantize:
                self.osc_sender.send_message('/push2/quantize/1_32T_quantize', [])
            elif shift:
                self.osc_sender.send_message('/push2/quantize/1_32T_shift', [])
            elif repeat:
                self.osc_sender.send_message('/push2/quantize/1_32T', [])
            elif loop:
                self.osc_sender.send_message('/push2/quantize/1_32T_loop', [])
            elif off:
                self.osc_sender.send_message('/push2/quantize/1_32T_off', [])
        elif index == '1/32':
            if quantize:
                self.osc_sender.send_message('/push2/quantize/1_32_quantize', [])
            elif shift:
                self.osc_sender.send_message('/push2/quantize/1_32_shift', [])
            elif repeat:
                self.osc_sender.send_message('/push2/quantize/1_32', [])
            elif loop:
                self.osc_sender.send_message('/push2/quantize/1_32_loop', [])
            elif off:
                self.osc_sender.send_message('/push2/quantize/1_32_off', [])
        elif index == '1/16t':
            if quantize:
                self.osc_sender.send_message('/push2/quantize/1_16T_quantize', [])
            elif shift:
                self.osc_sender.send_message('/push2/quantize/1_16T_shift', [])
            elif repeat:
                self.osc_sender.send_message('/push2/quantize/1_16T', [])
            elif loop:
                self.osc_sender.send_message('/push2/quantize/1_16T_loop', [])
            elif off:
                self.osc_sender.send_message('/push2/quantize/1_16T_off', [])
        elif index == '1/16':
            if quantize:
                self.osc_sender.send_message('/push2/quantize/1_16_quantize', [])
            elif shift:
                self.osc_sender.send_message('/push2/quantize/1_16_shift', [])
            elif repeat:
                self.osc_sender.send_message('/push2/quantize/1_16', [])
            elif loop:
                self.osc_sender.send_message('/push2/quantize/1_16_loop', [])
            elif off:
                self.osc_sender.send_message('/push2/quantize/1_16_off', [])
        elif index == '1/8t':
            if quantize:
                self.osc_sender.send_message('/push2/quantize/1_8T_quantize', [])
            elif shift:
                self.osc_sender.send_message('/push2/quantize/1_8T_shift', [])
            elif repeat:
                self.osc_sender.send_message('/push2/quantize/1_8T', [])
            elif loop:
                self.osc_sender.send_message('/push2/quantize/1_8T_loop', [])
            elif off:
                self.osc_sender.send_message('/push2/quantize/1_8T_off', [])
        elif index == '1/8':
            if quantize:
                self.osc_sender.send_message('/push2/quantize/1_8_quantize', [])
            elif shift:
                self.osc_sender.send_message('/push2/quantize/1_8_shift', [])
            elif repeat:
                self.osc_sender.send_message('/push2/quantize/1_8', [])
            elif loop:
                self.osc_sender.send_message('/push2/quantize/1_8_loop', [])
            elif off:
                self.osc_sender.send_message('/push2/quantize/1_8_off', [])
        elif index == '1/4t':
            if quantize:
                self.osc_sender.send_message('/push2/quantize/1_4T_quantize', [])
            elif shift:
                self.osc_sender.send_message('/push2/quantize/1_4T_shift', [])
            elif repeat:
                self.osc_sender.send_message('/push2/quantize/1_4T', [])
            elif loop:
                self.osc_sender.send_message('/push2/quantize/1_4T_loop', [])
            elif off:
                self.osc_sender.send_message('/push2/quantize/1_4T_off', [])
        elif index == '1/4':
            if quantize:
                self.osc_sender.send_message('/push2/quantize/1_4_quantize', [])
            elif shift:
                self.osc_sender.send_message('/push2/quantize/1_4_shift', [])
            elif repeat:
                self.osc_sender.send_message('/push2/quantize/1_4', [])
            elif loop:
                self.osc_sender.send_message('/push2/quantize/1_4_loop', [])
            elif off:
                self.osc_sender.send_message('/push2/quantize/1_4_off', [])

    def double_loop(self):
        self.osc_sender.send_message('/push2/double_loop', [])

    def double(self):
        self.osc_sender.send_message('/push2/double', [])

    def convert(self):
        self.osc_sender.send_message('/push2/convert', [])

    def stop_clip(self):
        self.osc_sender.send_message('/push2/stop_clip', [])

    def mute(self):
        self.osc_sender.send_message('/push2/mute', [])

    def mute_off(self):
        self.osc_sender.send_message('/push2/mute_off', [])

    def solo(self):
        self.osc_sender.send_message('/push2/solo', [])

    def solo_lock(self):
        self.osc_sender.send_message('/push2/solo_lock', [])

    def undo(self):
        self.osc_sender.send_message('/push2/undo', [])

    def repeat_off(self):
        self.osc_sender.send_message('/push2/repeat_off', [])

    def redo(self):
        self.osc_sender.send_message('/push2/redo', [])

    def delete(self):
        self.osc_sender.send_message('/push2/delete', [])

    def pause(self):
        self.osc_sender.send_message('/logic/transport/pause', [1.00])

    def play(self):
        if definitions.isPlaying:
            self.osc_sender.send_message('/logic/transport/stop', [1.00])
        else:
            self.osc_sender.send_message('/logic/transport/play', [1.00])

    def record(self):
        self.osc_sender.send_message('/logic/transport/record', [1.00])

    def arrow_keys(self, direction, shift, loop):
        if direction == 'up':
            if shift:
                self.osc_sender.send_message('/push2/up_shift', [])
            elif loop:
                self.osc_sender.send_message('/push2/up_loop', [])
            else:
                self.osc_sender.send_message('/push2/up', [])
        if direction == 'down':
            if shift:
                self.osc_sender.send_message('/push2/down_shift', [])
            elif loop:
                self.osc_sender.send_message('/push2/down_loop', [])
            else:
                self.osc_sender.send_message('/push2/down', [])
        if direction == 'left':
            if shift:
                self.osc_sender.send_message('/push2/left_shift', [])
            elif loop:
                self.osc_sender.send_message('/push2/left_loop', [])
            else:
                self.osc_sender.send_message('/push2/left', [])
        if direction == 'right':
            if shift:
                self.osc_sender.send_message('/push2/right_shift', [])
            elif loop:
                self.osc_sender.send_message('/push2/right_loop', [])
            else:
                self.osc_sender.send_message('/push2/right', [])

    def metronome_on_off(self):
        self.osc_sender.send_message('/logic/transport/click', [1.00])

    def get_buttons_state(self):
        if definitions.isPlaying:
            is_playing = True
        else:
            is_playing = False

        if definitions.isMetronome:
            metronome_on = True
        else:
            metronome_on = False

        if definitions.isRecording:
            is_recording = True
        else:
            is_recording = False

        self.push.buttons.set_button_color(push2_python.constants.BUTTON_PLAY,
                                           definitions.LIME if not is_playing else definitions.GREEN)
        self.push.buttons.set_button_color(push2_python.constants.BUTTON_RECORD,
                                           definitions.GREEN if not is_recording else definitions.RED)
        self.push.buttons.set_button_color(push2_python.constants.BUTTON_METRONOME,
                                           definitions.OFF_BTN_COLOR if not metronome_on else definitions.WHITE)
        self.app.midi_cc_mode.update_buttons()
        return is_playing, metronome_on, is_recording

    def get_bpm(self):
        return self.parsed_state.get('bpm', 120)

    def set_bpm(self, bpm):
        self.osc_sender.send_message('/transport/setBpm', [float(bpm)])

    def bpm_lights(self, value):
        beat = to_utf8(value)
        beats = beat.split()
        if int(float(beats[1])) % 2:
            self.push.buttons.set_button_color(push2_python.constants.BUTTON_PLAY, definitions.GREEN)
            for button_name in bpm_button_names:
                self.set_button_color_if_expression(button_name, definitions.isRecording, definitions.RED,
                                                    definitions.GREEN)
        else:
            for button_name in bpm_button_names:
                self.push.buttons.set_button_color(button_name, definitions.BLACK)

            self.push.buttons.set_button_color(push2_python.constants.BUTTON_PLAY, definitions.GREEN_DARK)
        if definitions.isRecording:
            if int(float(beats[1])) % 4:
                self.push.buttons.set_button_color(push2_python.constants.BUTTON_RECORD, definitions.RED)
            else:
                self.push.buttons.set_button_color(push2_python.constants.BUTTON_RECORD, definitions.RED_DARK)
        return True
