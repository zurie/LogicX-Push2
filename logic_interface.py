import definitions
import push2_python
from logic_keystrokes import press_command, COMMANDS

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
        self.last_received_tracks_raw_state = ""
        self.parsed_state = {}

    @staticmethod
    def handle_button_press(button_name, shift=False, select=False, long=False):
        path = f"/push2/{button_name}"
        if shift and select:
            path += "_shift_select"
        elif shift:
            path += "_shift"
        elif select:
            path += "_select"
        if long:
            path += "_long"
        press_command(path)

    def update_button(self, value, attribute, button, on_color, off_color):
        is_active = value == 1.0
        setattr(definitions, attribute, is_active)
        self.get_buttons_state()
        color = on_color if is_active else off_color
        self.app.push.buttons.set_button_color(button, color)

    def update_stop(self, *values):
        definitions.isRecording = 0.0
        self.get_buttons_state()

    def update_play_button(self, *values):
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

    # === Modifier-aware static command methods ===

    @staticmethod
    def automate(shift=False, select=False):
        press_command('/push2/automate', shift=shift, select=select)

    @staticmethod
    def repeat(shift=False, select=False):
        press_command('/push2/repeat', shift=shift, select=select)

    @staticmethod
    def layout(shift=False, select=False):
        press_command('/push2/layout', shift=shift, select=select)

    @staticmethod
    def session(shift=False, select=False):
        press_command('/push2/session', shift=shift, select=select)

    @staticmethod
    def convert(shift=False, loop=False):
        press_command("/push2/convert", shift=shift, loop=loop)

    @staticmethod
    def add_track(shift=False, select=False):
        press_command('/push2/add_track', shift=shift, select=select)

    @staticmethod
    def device(shift=False, select=False):
        press_command('/push2/device', shift=shift, select=select)

    @staticmethod
    def mix(shift=False, select=False):
        press_command('/push2/mix', shift=shift, select=select)

    @staticmethod
    def browse(shift=False, select=False):
        press_command('/push2/browse', shift=shift, select=select)

    @staticmethod
    def clip(shift=False, select=False):
        press_command('/push2/clip', shift=shift, select=select)

    @staticmethod
    def fixed_length(shift=False, select=False):
        press_command('/push2/fixed_length', shift=shift, select=select)

    @staticmethod
    def new(shift=False, select=False):
        press_command("/push2/new", shift=shift, select=select)

    @staticmethod
    def new_next(shift=False, select=False):
        press_command("/push2/new_next", shift=shift, select=select)

    @staticmethod
    def duplicate(shift=False, select=False):
        press_command("/push2/duplicate", shift=shift, select=select)

    @staticmethod
    def double_loop(shift=False, select=False):
        press_command('/push2/double_loop', shift=shift, select=select)

    @staticmethod
    def double(shift=False, select=False):
        press_command('/push2/double', shift=shift, select=select)

    @staticmethod
    def stop_clip(shift=False, select=False):
        press_command('/push2/stop_clip', shift=shift, select=select)

    @staticmethod
    def mute(shift=False, select=False):
        press_command('/push2/mute', shift=shift, select=select)

    @staticmethod
    def mute_off(shift=False, select=False):
        press_command('/push2/mute_off', shift=shift, select=select)

    @staticmethod
    def solo(shift=False, select=False):
        press_command('/push2/solo', shift=shift, select=select)

    @staticmethod
    def solo_lock(shift=False, select=False):
        press_command('/push2/solo_lock', shift=shift, select=select)

    @staticmethod
    def undo(shift=False, select=False):
        press_command('/push2/undo', shift=shift, select=select)

    @staticmethod
    def redo(shift=False, select=False):
        press_command('/push2/redo', shift=shift, select=select)

    @staticmethod
    def delete(shift=False, select=False):
        press_command('/push2/delete', shift=shift, select=select)

    @staticmethod
    def pause(shift=False, select=False):
        press_command('/push2/stop', shift=shift, select=select)

    @staticmethod
    def play(shift=False, select=False):
        press_command('/push2/play', shift=shift, select=select)

    def record(self):
        press_command('/push2/record')
        definitions.isRecording = not definitions.isRecording
        color = definitions.RED if definitions.isRecording else definitions.GREEN
        self.app.push.buttons.set_button_color(push2_python.constants.BUTTON_RECORD, color)

    def stop(self):
        press_command('/push2/stop')

    @staticmethod
    def arrow_keys(direction, shift=False, select=False):
        key = f"/push2/{direction}"
        if shift and select:
            key += "_shift_select"
        elif shift:
            key += "_shift"
        elif select:
            key += "_select"
        press_command(key)

    @staticmethod
    def quantize(index, quantize=False, shift=False, loop=False, repeat=False, off=False):
        # Mapping from constant label to normalized key
        label_to_key = {
            "1/32t": "1_32T",
            "1/32": "1_32",
            "1/16t": "1_16T",
            "1/16": "1_16",
            "1/8t":  "1_8T",
            "1/8":   "1_8",
            "1/4t":  "1_4T",
            "1/4":   "1_4"
        }

        label = str(index).lower()
        normalized = label_to_key.get(label)

        if not normalized:
            print(f"[WARN] Unknown quantize label: {label}")
            return

        path = f"/push2/quantize/{normalized}_quantize"
        press_command(path)

    @staticmethod
    def metronome_on_off():
        press_command('/push2/metronome')

    def get_buttons_state(self):
        self.app.push.buttons.set_button_color(
            push2_python.constants.BUTTON_RECORD,
            definitions.GREEN if not definitions.isRecording else definitions.RED
        )
        self.app.push.buttons.set_button_color(
            push2_python.constants.BUTTON_METRONOME,
            definitions.OFF_BTN_COLOR if not definitions.isMetronome else definitions.WHITE
        )
        self.app.midi_cc_mode.update_buttons()
        return definitions.isPlaying, definitions.isMetronome, definitions.isRecording
