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

    def track_select(self, track_number):
        self.osc_sender.send_message('/track/select', [track_number])

    def clip_play_stop(self, track_number, clip_number):
        self.osc_sender.send_message('/clip/playStop', [track_number, clip_number])

    def clip_clear(self, track_number, clip_number):
        self.osc_sender.send_message('/clip/clear', [track_number, clip_number])

    def clip_double(self, track_number, clip_number):
        self.osc_sender.send_message('/clip/double', [track_number, clip_number])

    def get_clip_state(self, track_num, clip_num):
        if 'clips' in self.parsed_state:
            try:
                return self.parsed_state['clips'][track_num][clip_num]
            except IndexError:
                return "snE"
        else:
            return 'snE'

    def automate(self):
        self.osc_sender.send_message('/push2/automate', [])

    def scene_play(self, scene_number):
        self.osc_sender.send_message('/scene/play', [scene_number])

    def scene_duplicate(self, scene_number):
        self.osc_sender.send_message('/scene/duplicate', [scene_number])

    def global_pause(self):
        self.osc_sender.send_message('/logic/transport/pause', [1.00])

    def global_play_stop(self):
        if definitions.isPlaying:
            self.osc_sender.send_message('/logic/transport/stop', [1.00])
        else:
            self.osc_sender.send_message('/logic/transport/play', [1.00])

    def global_record(self):
        self.osc_sender.send_message('/logic/transport/record', [1.00])

    def global_up(self):
        self.osc_sender.send_message('/push2/up', [])

    def global_down(self):
        self.osc_sender.send_message('/push2/down', [])

    def global_left(self):
        self.osc_sender.send_message('/push2/left', [])

    def global_right(self):
        self.osc_sender.send_message('/push2/right', [])

    def global_mute(self):
        self.osc_sender.send_message('/push2/mute', [])

    def global_mute_off(self):
        self.osc_sender.send_message('/push2/mute_off', [])

    def global_solo(self):
        self.osc_sender.send_message('/push2/solo', [])

    def global_solo_lock(self):
        self.osc_sender.send_message('/push2/solo_lock', [])

    def metronome_on_off(self):
        self.osc_sender.send_message('/logic/transport/click', [1.00])
        # self.app.add_display_notification("Metronome: {0}".format('On' if not definitions.isMetronome else 'Off'))

    def get_buttons_state(self):
        if definitions.isPlaying:
            is_playing = True
        else:
            is_playing = False

        if definitions.isMetronome:
            metronome_on = True
            self.push.buttons.set_button_color(push2_python.constants.BUTTON_METRONOME, definitions.WHITE)
        else:
            metronome_on = False
            self.push.buttons.set_button_color(push2_python.constants.BUTTON_METRONOME, definitions.OFF_BTN_COLOR)

        if definitions.isRecording:
            is_recording = True
        else:
            is_recording = False

        if is_playing:
            self.push.buttons.set_button_color(push2_python.constants.BUTTON_PLAY, definitions.GREEN)
        else:
            self.push.buttons.set_button_color(push2_python.constants.BUTTON_PLAY, definitions.LIME)

        self.push.buttons.set_button_color(push2_python.constants.BUTTON_RECORD,
                                           definitions.GREEN if not is_recording else definitions.RED)
        self.push.buttons.set_button_color(push2_python.constants.BUTTON_METRONOME,
                                           definitions.BLACK if not metronome_on else definitions.WHITE)

        return is_playing, metronome_on, is_recording

    def get_selected_scene(self):
        return self.parsed_state.get('selectedScene', 0)

    def get_bpm(self):
        return self.parsed_state.get('bpm', 120)

    def set_bpm(self, bpm):
        self.osc_sender.send_message('/transport/setBpm', [float(bpm)])

    def toUTF8(self, utf8):
        return utf8.decode("utf-8")

    def bpm_lights(self, value):
        beat = self.toUTF8(value)
        beats = beat.split()
        if int(float(beats[2])) == 1:
            self.push.buttons.set_button_color(push2_python.constants.BUTTON_PLAY, definitions.GREEN)
        else:
            self.push.buttons.set_button_color(push2_python.constants.BUTTON_PLAY, definitions.GREEN_DARK)
        if definitions.isRecording:
            if int(float(beats[1])) % 4:
                self.push.buttons.set_button_color(push2_python.constants.BUTTON_RECORD, definitions.RED)
            else:
                self.push.buttons.set_button_color(push2_python.constants.BUTTON_RECORD, definitions.RED_DARK)


