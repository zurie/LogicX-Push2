import definitions
import mido
import push2_python
import time
import os
import json

from display_utils import show_text


class TrackSelectionMode(definitions.PyshaMode):

    tracks_info = []
    track_button_names_a = [
        push2_python.constants.BUTTON_LOWER_ROW_1,
        push2_python.constants.BUTTON_LOWER_ROW_2,
        push2_python.constants.BUTTON_LOWER_ROW_3,
        push2_python.constants.BUTTON_LOWER_ROW_4,
        push2_python.constants.BUTTON_LOWER_ROW_5,
        push2_python.constants.BUTTON_LOWER_ROW_6,
        push2_python.constants.BUTTON_LOWER_ROW_7,
        push2_python.constants.BUTTON_LOWER_ROW_8
    ]
    track_button_names_b = [
        push2_python.constants.BUTTON_1_32T,
        push2_python.constants.BUTTON_1_32,
        push2_python.constants.BUTTON_1_16T,
        push2_python.constants.BUTTON_1_16,
        push2_python.constants.BUTTON_1_8T,
        push2_python.constants.BUTTON_1_8,
        push2_python.constants.BUTTON_1_4T,
        push2_python.constants.BUTTON_1_4
    ]
    track_selection_button_a = False
    track_selection_button_a_pressing_time = 0
    selected_track = 0
    track_selection_quick_press_time = 0.400
    pyramidi_channel = 15

    def initialize(self, settings=None):
        if settings is not None:
            self.pyramidi_channel = settings.get('pyramidi_channel', self.pyramidi_channel)
        
        self.create_tracks()

    def create_tracks(self):
        """This method creates 64 tracks corresponding to the Pyramid tracks that I use in my live setup.
        Instrument names are assigned according to the way I have them configured in the 64 tracks of Pyramid.
        Instrument names per track are loaded from "track_listing.json" file, and should correspond to instrument
        definition filenames from "instrument_definitions" folder.
        """
        tmp_instruments_data = {}

        if os.path.exists(definitions.TRACK_LISTING_PATH):
            track_instruments = json.load(open(definitions.TRACK_LISTING_PATH))
            for i, instrument_short_name in enumerate(track_instruments):
                if instrument_short_name not in tmp_instruments_data:
                    try:
                        instrument_data = json.load(open(os.path.join(definitions.INSTRUMENT_DEFINITION_FOLDER, '{}.json'.format(instrument_short_name))))
                        tmp_instruments_data[instrument_short_name] = instrument_data
                    except FileNotFoundError:
                        # No definition file for instrument exists
                        instrument_data = {}
                else:
                    instrument_data = tmp_instruments_data[instrument_short_name]
                color = instrument_data.get('color', None)
                if color is None:
                    if instrument_short_name != '-':
                        color = definitions.COLORS_NAMES[i % 8]
                    else:
                        color = definitions.GRAY_DARK
                self.tracks_info.append({
                    'track_name': '{0}{1}'.format((i % 16) + 1, ['A', 'B', 'C', 'D'][i//16]),
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
        else:
            # Create 64 empty tracks
            for i in range(0, 64):
                self.tracks_info.append({
                        'track_name': '{0}{1}'.format((i % 16) + 1, ['A', 'B', 'C', 'D'][i//16]),
                        'instrument_name': '-',
                        'instrument_short_name': '-',
                        'midi_channel': -1,
                        'color': definitions.ORANGE,
                        'default_layout': definitions.LAYOUT_MELODIC,
                        'illuminate_local_notes': True,
                    })

    def get_settings_to_save(self):
        return {
            'pyramidi_channel': self.pyramidi_channel,
        }

    def set_pyramidi_channel(self, channel, wrap=False):
        self.pyramidi_channel = channel
        if self.pyramidi_channel < 0:
            self.pyramidi_channel = 0 if not wrap else 15
        elif self.pyramidi_channel > 15:
            self.pyramidi_channel = 15 if not wrap else 0

    def get_all_distinct_instrument_short_names(self):
        return list(set([track['instrument_short_name'] for track in self.tracks_info]))

    def get_current_track_info(self):
        return self.tracks_info[self.selected_track]

    def get_current_track_instrument_short_name(self):
        return self.get_current_track_info()['instrument_short_name']

    def get_track_color(self, i):
        return self.tracks_info[i]['color']
    
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
        elif self.get_current_track_info()['default_layout'] == definitions.LAYOUT_CHROMATIC:
            self.app.set_chromatic_mode()

    def clean_currently_notes_being_played(self):
        if self.app.is_mode_active(self.app.melodic_mode):
            self.app.melodic_mode.remove_all_notes_being_played()
        elif self.app.is_mode_active(self.app.rhyhtmic_mode):
            self.app.rhyhtmic_mode.remove_all_notes_being_played()

    def send_select_track_to_pyramid(self, track_idx):
        # Follows pyramidi specification (Pyramid configured to receive on ch 16)
        msg = mido.Message('control_change', control=0, value=track_idx + 1, channel=self.pyramidi_channel)
        self.app.send_midi_to_pyramid(msg)

    def select_track(self, track_idx):
        # Selects a track and activates its melodic/rhythmic layout
        # Note that if this is called from a mode from the same xor group with melodic/rhythmic modes,
        # that other mode will be deactivated.
        self.selected_track = track_idx
        self.send_select_track_to_pyramid(self.selected_track)
        self.load_current_default_layout()
        self.clean_currently_notes_being_played()
        try:
            self.app.midi_cc_mode.new_track_selected()
            self.app.preset_selection_mode.new_track_selected()
            self.app.pyramid_track_triggering_mode.new_track_selected()
        except AttributeError:
            # Might fail if MIDICCMode/PresetSelectionMode/PyramidTrackTriggeringMode not initialized
            pass
        
    def activate(self):
        self.update_buttons()
        self.update_pads()

    def deactivate(self):
        for button_name in self.track_button_names_a + self.track_button_names_b:
            self.push.buttons.set_button_color(button_name, definitions.BLACK)

    def update_buttons(self):
        for count, name in enumerate(self.track_button_names_a):
            color = self.tracks_info[count]['color']
            self.push.buttons.set_button_color(name, color)

        for count, name in enumerate(self.track_button_names_b):
            if self.track_selection_button_a:
                color = self.tracks_info[self.track_button_names_a.index(self.track_selection_button_a)]['color']
                equivalent_track_num = self.track_button_names_a.index(self.track_selection_button_a) + count * 8
                if self.selected_track == equivalent_track_num:
                    self.push.buttons.set_button_color(name, definitions.WHITE)
                    self.push.buttons.set_button_color(name, color, animation=definitions.DEFAULT_ANIMATION)
                else:
                    self.push.buttons.set_button_color(name, color)
            else:
                color = self.get_current_track_color()
                equivalent_track_num = (self.selected_track % 8) + count * 8
                if self.selected_track == equivalent_track_num:
                    self.push.buttons.set_button_color(name, definitions.WHITE)
                    self.push.buttons.set_button_color(name, color, animation=definitions.DEFAULT_ANIMATION)
                else:
                    self.push.buttons.set_button_color(name, color)

    def update_display(self, ctx, w, h):

        # Draw track selector labels
        height = 20
        for i in range(0, 8):
            track_color = self.tracks_info[i]['color']
            if self.selected_track % 8 == i:
                background_color = track_color
                font_color = definitions.BLACK
            else:
                background_color = definitions.BLACK
                font_color = track_color
            instrument_short_name = self.tracks_info[i]['instrument_short_name']
            show_text(ctx, i, h - height, instrument_short_name, height=height,
                      font_color=font_color, background_color=background_color)
 
    def on_button_pressed_raw(self, button_name):
        if button_name in self.track_button_names_a:
            self.track_selection_button_a = button_name
            self.track_selection_button_a_pressing_time = time.time()
            self.app.buttons_need_update = True
            return True

        elif button_name in self.track_button_names_b:
            if self.track_selection_button_a:
                # While pressing one of the track selection a buttons
                self.select_track(self.track_button_names_a.index(
                    self.track_selection_button_a) + self.track_button_names_b.index(button_name) * 8)
                self.app.buttons_need_update = True
                self.app.pads_need_update = True
                self.track_selection_button_a = False
                self.track_selection_button_a_pressing_time = 0
                return True
            else:
                # No track selection a button being pressed...
                self.select_track(self.selected_track % 8 + 8 * self.track_button_names_b.index(button_name))
                self.app.buttons_need_update = True
                self.app.pads_need_update = True
                return True

    def on_button_released_raw(self, button_name):
        if button_name in self.track_button_names_a:
            if self.track_selection_button_a:
                if time.time() - self.track_selection_button_a_pressing_time < self.track_selection_quick_press_time:
                    # Only switch to track if it was a quick press
                    self.select_track(self.track_button_names_a.index(button_name))
                self.track_selection_button_a = False
                self.track_selection_button_a_pressing_time = 0
                self.app.buttons_need_update = True
                self.app.pads_need_update = True
                return True
