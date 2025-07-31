from typing import NamedTuple

import push2_python
import colorsys
import threading

from functools import wraps

from push2_python.constants import ANIMATION_STATIC

VERSION = '1.1.1'

DELAYED_ACTIONS_APPLY_TIME = 1.0  # Encoder changes won't be applied until this time has passed since last moved
isPlaying = 0.0  # instead of False
isMetronome = 0.0
isRecording = 0.0

LAYOUT_MELODIC = 'lmelodic'
LAYOUT_RHYTHMIC = 'lrhythmic'
LAYOUT_SLICES = 'lslices'

NOTIFICATION_TIME = 3
HELP_TIME = 30

BLACK_RGB = [5, 5, 5]
GRAY_DARK_RGB = [30, 30, 30]
GRAY_LIGHT_RGB = [180, 180, 180]
WHITE_RGB = [255, 255, 255]

YELLOW_RGB = [255, 255, 0]
TANGERINE_RGB = [255, 204, 0]
ORANGE_RGB = [255, 153, 0]
PINK_RGB = [255, 0, 255]

RED_RGB = [255, 0, 0]
RED_DARK_RGB = [50, 0, 0]
PURPLE_RGB = [153, 0, 255]
BROWN_RGB = [153, 102, 0]

LIME_RGB = [153, 255, 0]
GREEN_RGB = [0, 255, 0]
GREEN_DARK_RGB = [0, 50, 0]

SKYBLUE_RGB = [0, 255, 255]
BLUE_RGB = [0, 0, 255]
ROYALBLUE_RGB = [0, 153, 255]

PROTEUS_RGB = [102, 51, 204]
KARMA_RGB = [127, 29, 78]
XV_RGB = [118, 101, 50]
EM1_RGB = [61, 57, 46]

BLACK = 'black'
GRAY_DARK = 'gray_dark'
GRAY_LIGHT = 'gray_light'
WHITE = 'white'
YELLOW = 'yellow'
TANGERINE = 'tangerine'
ORANGE = 'orange'
RED = 'red'
RED_DARK = 'red_dark'
PINK = 'PINK'
PURPLE = 'purple'
BROWN = 'brown'
LIME = 'lime'
GREEN = 'green'
GREEN_DARK = 'green_dark'
SKYBLUE = 'skyblue'
BLUE = 'blue'
ROYALBLUE = 'royalblue'

# Custom Music instruments color
PROTEUS = 'proteus'
KARMA = 'karma'
XV = 'xv'
EM1 = 'em1'

COLORS_NAMES = [ROYALBLUE,
                SKYBLUE,
                GREEN,
                GREEN_DARK,
                LIME,
                BROWN,
                PURPLE,
                RED,
                RED_DARK,
                PINK,
                ORANGE,
                TANGERINE,
                YELLOW,
                BLUE,
                PROTEUS,
                KARMA,
                XV,
                EM1,
                WHITE,
                GRAY_LIGHT,
                GRAY_DARK,
                BLACK]

SCALE_NAME = 'Major'


class Scale:
    def __init__(self, name, notes):
        self.name = name
        self.notes = notes

    def __repr__(self):
        return "Scale name:% s notes:% s" % (self.name, self.notes)

    def __str__(self):
        return "From str method of Scale: name is % s, " \
               "notes are % s" % (self.name, self.notes)


SCALES = (
    Scale(name='Major',            notes=[1, 0, 1, 0, 1, 1, 0, 1, 0, 1, 0, 1]),
    Scale(name='Minor',            notes=[1, 0, 1, 1, 0, 1, 0, 1, 1, 0, 1, 0]),
    Scale(name='Dorian',           notes=[1, 0, 1, 1, 0, 1, 0, 1, 0, 1, 1, 0]),
    Scale(name='Mixolydian',       notes=[1, 0, 1, 0, 1, 1, 0, 1, 0, 1, 1, 0]),
    Scale(name='Lydian',           notes=[1, 0, 1, 0, 1, 0, 1, 1, 0, 1, 0, 1]),
    Scale(name='Phrygian',         notes=[1, 1, 0, 1, 0, 1, 0, 1, 1, 0, 1, 0]),
    Scale(name='Locrian',          notes=[1, 1, 0, 1, 1, 0, 0, 1, 1, 0, 1, 0]),
    Scale(name='Diminished',       notes=[1, 1, 0, 1, 1, 0, 1, 1, 0, 1, 1, 0]),
    Scale(name='Whole half',       notes=[1, 0, 1, 1, 0, 1, 1, 0, 1, 1, 0, 1]),
    Scale(name='Whole Tone',       notes=[1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0]),
    Scale(name='Minor Blues',      notes=[1, 0, 0, 1, 0, 1, 1, 1, 0, 0, 1, 0]),
    Scale(name='Minor Pentatonic', notes=[1, 0, 0, 1, 0, 1, 0, 1, 0, 0, 1, 0]),
    Scale(name='Major Pentatonic', notes=[1, 0, 1, 0, 1, 0, 0, 1, 0, 1, 0, 0]),
    Scale(name='Harmonic Minor',   notes=[1, 0, 1, 1, 0, 1, 0, 1, 1, 0, 0, 1]),
    Scale(name='Melodic Minor',    notes=[1, 0, 1, 1, 0, 1, 0, 1, 0, 1, 0, 1]),
    Scale(name='Super Locrian',    notes=[1, 1, 1, 1, 0, 1, 0, 1, 0, 1, 0, 0]),
    Scale(name='Bhairav',          notes=[1, 1, 0, 0, 1, 1, 0, 1, 1, 0, 0, 1]),
    Scale(name='Hungarian Minor',  notes=[1, 0, 1, 1, 0, 0, 1, 1, 1, 0, 0, 1]),
    Scale(name='Minor Gypsy',      notes=[1, 1, 0, 0, 1, 1, 0, 1, 1, 0, 1, 0]),
    Scale(name='Hirojoshi',        notes=[1, 0, 1, 1, 0, 0, 0, 1, 1, 0, 0, 0]),
    Scale(name='In Sen',           notes=[1, 1, 0, 0, 0, 1, 0, 1, 0, 0, 1, 0]),
    Scale(name='Iwato',            notes=[1, 1, 0, 0, 0, 1, 1, 0, 0, 0, 1, 0]),
    Scale(name='Kumoi',            notes=[1, 0, 1, 1, 0, 0, 0, 1, 0, 1, 0, 0]),
    Scale(name='Pelog',            notes=[1, 1, 0, 1, 1, 0, 0, 1, 1, 0, 0, 0]),
    Scale(name='Spanish',          notes=[1, 1, 0, 1, 1, 1, 1, 0, 1, 0, 1, 0])
)


def get_color_rgb(color_name):
    return globals().get('{0}_RGB'.format(color_name.upper()), [0, 0, 0])


def get_color_rgb_float(color_name):
    return [x / 255 for x in get_color_rgb(color_name)]


# Create darker1 and darker2 versions of each color in COLOR_NAMES, add new colors back to COLOR_NAMES
to_add_in_color_names = []
for name in COLORS_NAMES:

    # Create darker 1
    color_mod = 0.35  # < 1 means make colour darker, > 1 means make colour brighter
    c = colorsys.rgb_to_hls(*get_color_rgb_float(name))
    darker_color = colorsys.hls_to_rgb(c[0], max(0, min(1, color_mod * c[1])), c[2])
    new_color_name = f'{name}_darker1'
    globals()[new_color_name.upper()] = new_color_name
    if new_color_name not in COLORS_NAMES:
        to_add_in_color_names.append(new_color_name)
    new_color_rgb_name = f'{name}_darker1_rgb'
    globals()[new_color_rgb_name.upper()] = list([c * 255 for c in darker_color])

    # Create darker 2
    color_mod = 0.05  # < 1 means make colour darker, > 1 means make colour brighter
    c = colorsys.rgb_to_hls(*get_color_rgb_float(name))
    darker_color = colorsys.hls_to_rgb(c[0], max(0, min(1, color_mod * c[1])), c[2])
    new_color_name = f'{name}_darker2'
    globals()[new_color_name.upper()] = new_color_name
    if new_color_name not in COLORS_NAMES:
        to_add_in_color_names.append(new_color_name)
    new_color_rgb_name = f'{name}_darker2_rgb'
    globals()[new_color_rgb_name.upper()] = list([c * 255 for c in darker_color])

COLORS_NAMES += to_add_in_color_names  # Update list of color names with darkified versiond of existing colors

FONT_COLOR_DELAYED_ACTIONS = ORANGE
FONT_COLOR_DISABLED = GRAY_LIGHT
CENTER_LABELS = True
OFF_BTN_COLOR = GRAY_DARK
NOTE_ON_COLOR = PINK

DEFAULT_ANIMATION = push2_python.constants.ANIMATION_PULSING_QUARTER

INSTRUMENT_DEFINITION_FOLDER = 'instrument_definitions'
DEVICE_DEFINITION_FOLDER = 'device_definitions'
TRACK_LISTING_PATH = 'track_listing.json'
HELP_DOCS_PATH = 'button_docs.json'

BUTTON_LONG_PRESS_TIME = 0.25
BUTTON_DOUBLE_PRESS_TIME = 0.2


# -- Timer for delayed actions

def delay(delay=0.):
    """
    Decorator delaying the execution of a function for a while.
    Adapted from: https://codeburst.io/javascript-like-settimeout-functionality-in-python-18c4773fa1fd
    """

    def wrap(f):
        @wraps(f)
        def delayed(*args, **kwargs):
            timer = threading.Timer(delay, f, args=args, kwargs=kwargs)
            timer.start()

        return delayed

    return wrap


class Timer():
    """
    Adapted from: https://codeburst.io/javascript-like-settimeout-functionality-in-python-18c4773fa1fd
    """
    toClearTimer = False

    def setTimeout(self, fn, args, time):
        isInvokationCancelled = False

        @delay(time)
        def some_fn():
            if self.toClearTimer is False:
                fn(*args)
            else:
                # Invokation is cleared!
                pass

        some_fn()
        return isInvokationCancelled

    def setClearTimer(self):
        self.toClearTimer = True


class LogicMode(object):
    """
    """

    name = ''
    xor_group = None
    buttons_used = []

    def __init__(self, app, settings=None):
        self.app = app
        self.initialize(settings=settings)

    @property
    def push(self):
        return self.app.push

    # Method run only once when the mode object is created, may receive settings dictionary from main app
    def initialize(self, settings=None):
        pass

    # Method to return a dictionary of properties to store in a settings file, and that will be passed to
    # initialize method when object created
    def get_settings_to_save(self):
        return {}

    # Methods that are run before the mode is activated and when it is deactivated
    def activate(self):
        pass

    def deactivate(self):
        # Default implementation is to set all buttons used (if any) to black
        self.set_buttons_to_color(self.buttons_used, BLACK)

    # Method called at every iteration in the main loop to see if any actions need to be performed at the end of the iteration
    # This is used to avoid some actions unncessesarily being repeated many times
    def check_for_delayed_actions(self):
        pass

    # Method called when MIDI messages arrive from Logic MIDI input
    def on_midi_in(self, msg, source=None):
        pass

    # Push2 update methods
    def update_pads(self):
        pass

    def update_buttons(self):
        pass

    def update_display(self, ctx, w, h):
        pass

    # Some update helper methods
    def set_button_color(self, button_name, color=WHITE, animation=ANIMATION_STATIC, animation_end_color=BLACK):
        self.push.buttons.set_button_color(button_name, color, animation=animation,
                                           animation_end_color=animation_end_color)

    def set_button_color_if_pressed(self, button_name, color=WHITE, off_color=OFF_BTN_COLOR, animation=ANIMATION_STATIC,
                                    animation_end_color=BLACK):
        if not self.app.is_button_being_pressed(button_name):
            self.push.buttons.set_button_color(button_name, off_color)
        else:
            self.push.buttons.set_button_color(button_name, color, animation=animation,
                                               animation_end_color=animation_end_color)

    def set_button_color_if_expression(self, button_name, expression, color=WHITE, false_color=OFF_BTN_COLOR,
                                       animation=ANIMATION_STATIC, animation_end_color=BLACK,
                                       also_include_is_pressed=False):
        if also_include_is_pressed:
            expression = expression or self.app.is_button_being_pressed(button_name)
        if not expression:
            self.push.buttons.set_button_color(button_name, false_color)
        else:
            self.push.buttons.set_button_color(button_name, color, animation=animation,
                                               animation_end_color=animation_end_color)

    def set_buttons_to_color(self, button_names, color=WHITE, animation=ANIMATION_STATIC, animation_end_color=BLACK):
        for button_name in button_names:
            self.push.buttons.set_button_color(button_name, color, animation=animation,
                                               animation_end_color=animation_end_color)
        return True

    def set_buttons_need_update_if_button_used(self, button_name):
        if button_name in self.buttons_used:
            self.app.buttons_need_update = True

    # Push2 action callbacks (these methods should return True if some action was carried out, otherwise return None)
    def on_encoder_rotated(self, encoder_name, increment):
        pass

    def on_button_pressed_raw(self, button_name):
        pass

    def on_button_released_raw(self, button_name):
        pass

    def on_pad_pressed_raw(self, pad_n, pad_ij, velocity):
        pass

    def on_pad_released_raw(self, pad_n, pad_ij, velocity):
        pass

    def on_pad_aftertouch(self, pad_n, pad_ij, velocity):
        pass

    def on_touchstrip(self, value):
        pass

    def on_sustain_pedal(self, sustain_on):
        pass

    # Processed Push2 action callbacks that allow to easily diferentiate between actions like "button single press", "button double press", "button long press", "button single press + shift"...
    def on_button_pressed(self, button_name, loop=False, quantize=False, shift=False, select=False, long_press=False,
                          double_press=False):
        pass

    def on_pad_pressed(self, pad_n, pad_ij, velocity, loop=False, quantize=False, shift=False, select=False,
                       long_press=False, double_press=False):
        pass
