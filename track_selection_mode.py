import math

import definitions
import push2_python
import os
import json

from display_utils import show_text


class TrackSelectionMode(definitions.LogicMode):
    tracks_info = []
    master_button = push2_python.constants.BUTTON_MASTER

    track_button_names = [
        push2_python.constants.BUTTON_LOWER_ROW_1,
        push2_python.constants.BUTTON_LOWER_ROW_2,
        push2_python.constants.BUTTON_LOWER_ROW_3,
        push2_python.constants.BUTTON_LOWER_ROW_4,
        push2_python.constants.BUTTON_LOWER_ROW_5,
        push2_python.constants.BUTTON_LOWER_ROW_6,
        push2_python.constants.BUTTON_LOWER_ROW_7,
        push2_python.constants.BUTTON_LOWER_ROW_8
    ]
    selected_track = 0
    total_pages = 0
    page = 1
    buttons_used = [master_button]

    def initialize(self, settings=None):
        if settings is not None:
            pass

        self.create_tracks()

    def create_tracks(self):
        tmp_instruments_data = {}

        if os.path.exists(definitions.TRACK_LISTING_PATH):
            track_instruments = json.load(open(definitions.TRACK_LISTING_PATH))
            for i, instrument_short_name in enumerate(track_instruments):
                if instrument_short_name not in tmp_instruments_data:
                    try:
                        instrument_data = json.load(open(os.path.join(definitions.INSTRUMENT_DEFINITION_FOLDER,
                                                                      '{}.json'.format(instrument_short_name))))
                        tmp_instruments_data[instrument_short_name] = instrument_data
                    except FileNotFoundError:
                        # No definition file for instrument exists
                        instrument_data = {}
                else:
                    instrument_data = tmp_instruments_data[instrument_short_name]
                color = instrument_data.get('color', None)
                if color is None:
                    if instrument_short_name != '-':
                        color = definitions.COLORS_NAMES[i]
                    else:
                        color = definitions.GRAY_DARK
                self.tracks_info.append({
                    'track_name': '{0}{1}'.format((i % 16) + 1, ['A', 'B', 'C', 'D'][i // 16]),
                    'instrument_name': instrument_data.get('instrument_name', '-'),
                    'instrument_short_name': instrument_short_name,
                    'midi_channel': instrument_data.get('midi_channel', -1),
                    'color': color,
                    'n_banks': instrument_data.get('n_banks', 1),
                    'bank_names': instrument_data.get('bank_names', None),
                    'default_layout': instrument_data.get('default_layout', definitions.LAYOUT_MELODIC),
                    'illuminate_local_notes': instrument_data.get('illuminate_local_notes', True),
                })
            print('Created {0} tracks!'.format(len(self.tracks_info)))
            print('Created {0} tracks!'.format(self.tracks_info))
        else:
            # Create 64 empty tracks
            for i in range(0, len(self.tracks_info)):
                self.tracks_info.append({
                    'track_name': '{0}{1}'.format((i % 16) + 1, ['A', 'B', 'C', 'D'][i // 16]),
                    'instrument_name': '-',
                    'instrument_short_name': '-',
                    'midi_channel': -1,
                    'color': definitions.ORANGE,
                    'default_layout': definitions.LAYOUT_MELODIC,
                    'illuminate_local_notes': True,
                })

    def get_settings_to_save(self):
        return {}

    def get_all_distinct_instrument_short_names(self):
        return list(set([track['instrument_short_name'] for track in self.tracks_info]))

    def get_current_track_info(self):
        return self.tracks_info[self.selected_track]

    def get_current_track_instrument_short_name(self):
        return self.get_current_track_info()['instrument_short_name']

    def get_track_color(self, i):
        return self.tracks_info[i]['color']

    def get_total_pages(self):
        x = len(self.tracks_info) / 8
        self.total_pages = x
        return math.ceil(x)

    def increment_track_pages(self):
        current_page = self.page
        if current_page + 1 <= self.get_total_pages():
            self.page = self.page + 1
        else:
            self.page = 1
        self.update_buttons()

    def get_current_page_start(self):
        return (self.get_total_pages() - 1) * 8

    def get_current_track_color(self):
        return self.get_track_color(self.selected_track)

    def get_current_track_color_rgb(self):
        return definitions.get_color_rgb_float(self.get_current_track_color())

    def load_current_default_layout(self):
        if self.get_current_track_info()['default_layout'] == definitions.LAYOUT_MELODIC:
            self.app.set_melodic_mode()
        elif self.get_current_track_info()['default_layout'] == definitions.LAYOUT_RHYTHMIC:
            self.app.set_rhythmic_mode()
        elif self.get_current_track_info()['default_layout'] == definitions.LAYOUT_SLICES:
            self.app.set_slice_notes_mode()

    def clean_currently_notes_being_played(self):
        if self.app.is_mode_active(self.app.melodic_mode):
            self.app.melodic_mode.remove_all_notes_being_played()
        elif self.app.is_mode_active(self.app.rhyhtmic_mode):
            self.app.rhyhtmic_mode.remove_all_notes_being_played()

    def select_track(self, track_idx):
        # Selects a track and activates its melodic/rhythmic layout
        # Note that if this is called from a mode from the same xor group with melodic/rhythmic modes,
        # that other mode will be deactivated.
        if self.page == 2:
            self.selected_track = track_idx + 8
        elif self.page == 3:
            self.selected_track = track_idx + 16
        else:
            self.selected_track = track_idx
        self.load_current_default_layout()
        self.clean_currently_notes_being_played()
        try:
            self.app.midi_cc_mode.new_track_selected()
            self.app.preset_selection_mode.new_track_selected()
        except AttributeError:
            # Might fail if MIDICCMode/PresetSelectionMode/PyramidTrackTriggeringMode not initialized
            pass

    def activate(self):
        self.update_buttons()
        self.update_pads()

    def deactivate(self):
        for button_name in self.track_button_names:
            self.push.buttons.set_button_color(button_name, definitions.BLACK)

    def update_buttons(self):
        self.set_all_lower_row_buttons_off()
        for count, name in enumerate(self.track_button_names):
            if self.page == 1:
                self.app.buttons_need_update = True
                if count < len(self.tracks_info):
                    color = self.tracks_info[count]['color']
                else:
                    color = 'black'
            elif self.page == 2:
                self.app.buttons_need_update = True
                if count + 8 < len(self.tracks_info):
                    color = self.tracks_info[count+8]['color']
                else:
                    color = 'black'
            elif self.page == 3:
                self.app.buttons_need_update = True
                if count + 16 < len(self.tracks_info):
                    color = self.tracks_info[count+16]['color']
                else:
                    color = 'black'

            self.push.buttons.set_button_color(name, color)
        self.set_button_color(self.master_button)
        # Settings button, to toggle settings mode

        self.set_button_color_if_pressed(self.master_button, animation=definitions.DEFAULT_ANIMATION)

    def set_all_lower_row_buttons_off(self):
        self.push.buttons.set_button_color(push2_python.constants.BUTTON_LOWER_ROW_1, definitions.OFF_BTN_COLOR)
        self.push.buttons.set_button_color(push2_python.constants.BUTTON_LOWER_ROW_2, definitions.OFF_BTN_COLOR)
        self.push.buttons.set_button_color(push2_python.constants.BUTTON_LOWER_ROW_3, definitions.OFF_BTN_COLOR)
        self.push.buttons.set_button_color(push2_python.constants.BUTTON_LOWER_ROW_4, definitions.OFF_BTN_COLOR)
        self.push.buttons.set_button_color(push2_python.constants.BUTTON_LOWER_ROW_5, definitions.OFF_BTN_COLOR)
        self.push.buttons.set_button_color(push2_python.constants.BUTTON_LOWER_ROW_6, definitions.OFF_BTN_COLOR)
        self.push.buttons.set_button_color(push2_python.constants.BUTTON_LOWER_ROW_7, definitions.OFF_BTN_COLOR)
        self.push.buttons.set_button_color(push2_python.constants.BUTTON_LOWER_ROW_8, definitions.OFF_BTN_COLOR)

    def update_display(self, ctx, w, h):
        # Draw track selector labels
        height = 20
        if self.page == 1:
            for i in range(0, len(self.tracks_info) if not len(self.tracks_info) > 8 else 8):
                track_color = self.tracks_info[i]['color']
                if self.selected_track % 24 == i:
                    background_color = track_color
                    font_color = definitions.BLACK
                else:
                    background_color = definitions.BLACK
                    font_color = track_color
                instrument_short_name = self.tracks_info[i]['instrument_short_name']
                show_text(ctx, i, h - height, instrument_short_name, height=height,
                          font_color=font_color, background_color=background_color)
        elif self.page == 2:
            for i in range(8, len(self.tracks_info) if not len(self.tracks_info) > 16 else 16):
                track_color = self.tracks_info[i]['color']
                if self.selected_track % 24 == i:
                    background_color = track_color
                    font_color = definitions.BLACK
                else:
                    background_color = definitions.BLACK
                    font_color = track_color
                instrument_short_name = self.tracks_info[i]['instrument_short_name']
                show_text(ctx, i-8, h - height, instrument_short_name, height=height,
                          font_color=font_color, background_color=background_color)
        elif self.page == 3:
            for i in range(16, len(self.tracks_info) if not len(self.tracks_info) > 24 else 24):
                track_color = self.tracks_info[i]['color']
                if self.selected_track % 24 == i:
                    background_color = track_color
                    font_color = definitions.BLACK
                else:
                    background_color = definitions.BLACK
                    font_color = track_color
                instrument_short_name = self.tracks_info[i]['instrument_short_name']
                show_text(ctx, i-16, h - height, instrument_short_name, height=height,
                          font_color=font_color, background_color=background_color)

    def on_button_pressed(self, button_name, quantize=False, shift=False, select=False, long_press=False, double_press=False):
        if button_name in self.track_button_names:
            track_idx = self.track_button_names.index(button_name)
            if long_press:
                pass
            else:
                if not shift:
                    # If button shift not pressed, select the track
                    if track_idx + 8 >= len(self.tracks_info) and self.page == 2:
                        pass
                    elif track_idx + 16 >= len(self.tracks_info) and self.page == 3:
                        pass
                    else:
                        self.select_track(self.track_button_names.index(button_name))
                else:
                    pass
            self.app.buttons_need_update = True
            self.app.pads_need_update = True
            return True
        elif button_name == self.master_button:
            self.increment_track_pages()
