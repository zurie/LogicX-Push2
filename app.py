import json
import os
import time
import traceback

import cairocffi as cairo
import platform
import definitions
import mido
import numpy
import push2_python

from collections import defaultdict
from logic_midi_listener import LogicMidiListener
from splash_screen import draw_splash_screen
from logic_mcu_manager import LogicMCUManager
from melodic_mode import MelodicMode
from track_selection_mode import TrackSelectionMode
from rhythmic_mode import RhythmicMode
from slice_notes_mode import SliceNotesMode
from settings_mode import SettingsMode
from help_mode import HelpMode
from repeat_mode import RepeatMode
from mackie_control_mode import MackieControlMode

from scalemenu_mode import ScaleMenuMode
from main_controls_mode import MainControlsMode
from midi_cc_mode import MIDICCMode
from preset_selection_mode import PresetSelectionMode
from logic_interface import LogicInterface
from display_utils import show_notification, show_help


class LogicApp(object):
    # debug
    debug_logs = False

    # Collapse Scale
    collapse_scale = True

    # midi
    midi_out = None
    available_midi_out_device_names = []
    midi_out_channel = 0  # 0-15
    midi_out_tmp_device_idx = None  # This is to store device names while rotating encoders

    midi_in = None
    available_midi_in_device_names = []
    midi_in_channel = 0  # 0-15
    midi_in_tmp_device_idx = None  # This is to store device names while rotating encoders

    notes_midi_in = None  # MIDI input device only used to receive note messages and illuminate pads/keys
    notes_midi_in_tmp_device_idx = None  # This is to store device names while rotating encoders

    # push
    push = None
    use_push2_display = None
    target_frame_rate = None

    # frame rate measurements
    actual_frame_rate = 0
    current_frame_rate_measurement = 0
    current_frame_rate_measurement_second = 0

    # other state vars
    active_modes = []
    previously_active_mode_for_xor_group = {}
    pads_need_update = True
    buttons_need_update = True

    # notifications
    notification_text = None
    notification_time = 0

    # help
    help_title = help_hotkey = help_description = help_color = help_path = None
    help_time = 0

    # fixing issue with 2 lumis and alternating channel pressure values
    last_cp_value_received = 0
    last_cp_value_received_time = 0
    _last_tick = 0
    _channels_this_tick = set()
    # interface with logic
    logic_interface = None

    def __init__(self):
        self._last_mcu_row_state = None
        self.display_dirty = None
        self.melodic_mode = None

        self.main_controls_mode = None
        self._last_mcu_transport = None
        if os.path.exists('settings.json'):
            settings = json.load(open('settings.json'))
        else:
            settings = {}
        self.settings = settings
        self.logic_interface = LogicInterface(self)
        self.shift_held = False
        self.select_held = False
        self.quantize_held = False
        self.quantize_used_as_modifier = False
        self.debug_logs = settings.get("debug_logs", False)
        self.collapse_scale = settings.get("collapse_scale", False)
        self.solo_off_confirm_time = settings.get("solo_off_confirm_time", 2.0)
        self.bank_reassert_delay = settings.get("bank_reassert_delay", 0.2)
        self.use_mcu = settings.get("use_mcu", True)
        self.debug_mcu = settings.get("debug_mcu", False)

        self.set_midi_in_channel(settings.get('midi_in_default_channel', 0))
        self.set_midi_out_channel(settings.get('midi_out_default_channel', 0))
        self.target_frame_rate = settings.get('target_frame_rate', 60)
        self.use_push2_display = settings.get('use_push2_display', True)

        self.init_midi_in(device_name=settings.get('default_midi_in_device_name', None))
        self.init_midi_out(device_name=settings.get('default_midi_out_device_name', None))
        self.init_notes_midi_in(device_name=settings.get('default_notes_midi_in_device_name', None))
        self.init_push()

        if settings.get("use_mcu", False):
            # after you create the MCU manager:
            self.mcu_manager = LogicMCUManager(self, port_name=self.settings.get("mcu_port_name"))
            # hook incoming Push encoders (v-pots) into our MackieControlMode
            self.mcu_manager.on_vpot = self._on_mcu_vpot

            # start listening…
            self.mcu_manager.start()

            # Optional: hook transport changes to update button colors
            def handle_transport_change(state):
                definitions.isPlaying = 1.0 if state.get("play") else 0.0
                definitions.isRecording = 1.0 if state.get("record") else 0.0
                self.update_play_button_color(state.get("play"))
                self.update_record_button_color(state.get("record"))

            self.mcu_manager.on_transport_change = handle_transport_change

        else:
            # --- Logic MIDI listener (non-MCU mode)
            self.logic_listener = LogicMidiListener(
                midi_port_name=settings.get("default_midi_port_name", "IAC Driver Default"),
                play_state_callback=self.update_play_button_color,
                record_state_callback=self.update_record_button_color
            )
            self.logic_listener.start()

        self.init_modes(settings)

    def _on_mcu_vpot(self, idx: int, value: int):
        global _last_tick, _channels_this_tick

        # ── 1. ignore LED pattern bytes (b5-4 ≠ 00)
        if value & 0x30:
            return

        # ── 2. ignore bursts touching several channels in same tick
        now_tick = int(time.time() * 1000)  # coarse 1 ms resolution
        if now_tick != _last_tick:
            _last_tick = now_tick
            _channels_this_tick.clear()
        if idx in _channels_this_tick:
            return  # duplicate within same tick
        _channels_this_tick.add(idx)
        if len(_channels_this_tick) > 1:
            return  # more than one channel updated – treat as refresh

        # ── genuine human turn → translate to ±1 step
        direction = -1 if value & 0x40 else +1
        encoder_name = MackieControlMode.encoder_names[idx]
        if self.is_mode_active(self.mc_mode):
            self.mc_mode.on_encoder_rotated(encoder_name, direction)

    # ───────────────────────────────────────────────────────────
    # MODE INIT
    def init_modes(self, settings):
        self.main_controls_mode = MainControlsMode(self, settings=settings)
        self.active_modes.append(self.main_controls_mode)

        self.melodic_mode = MelodicMode(self, settings=settings)
        self.rhyhtmic_mode = RhythmicMode(self, settings=settings)
        self.slice_notes_mode = SliceNotesMode(self, settings=settings)
        self.set_melodic_mode()
        self.track_selection_mode = TrackSelectionMode(self, settings=settings)
        self.preset_selection_mode = PresetSelectionMode(self, settings=settings)
        self.midi_cc_mode = MIDICCMode(self, settings=settings)
        self.active_modes += [self.track_selection_mode, self.midi_cc_mode]
        self.track_selection_mode.select_track(self.track_selection_mode.selected_track)

        self.settings_mode = SettingsMode(self, settings=settings)
        self.help_mode = HelpMode(self, settings=settings)
        self.mc_mode = MackieControlMode(self)
        self.repeat_mode = RepeatMode(self, settings=settings)
        self.scalemenu_mode = ScaleMenuMode(self, settings=settings)

    # ───────────────────────────────────────────────────────────
    # MCU SYNC
    def update_push_from_mcu(self):
        mcu = getattr(self, "mcu", None) or getattr(self, "mcu_manager", None)
        if not mcu:
            return

        sel_idx = getattr(mcu, "selected_track_idx", None)
        if sel_idx is None:
            return

        # ensure in-range
        if not (0 <= sel_idx < len(mcu.solo_states)
                and 0 <= sel_idx < len(mcu.mute_states)
                and 0 <= sel_idx < len(mcu.rec_states)):
            return
        # Only log when transport changed
        if not hasattr(self, "_last_mcu_transport") or self.mcu_manager.transport != self._last_mcu_transport:
            self._last_mcu_transport = self.mcu_manager.transport.copy()

        # Record button
        if self.mcu_manager.transport["record"]:
            self.push.buttons.set_button_color(push2_python.constants.BUTTON_RECORD, definitions.RED)
        else:
            self.push.buttons.set_button_color(push2_python.constants.BUTTON_RECORD, definitions.GREEN)

        # Play button
        if self.mcu_manager.transport["play"]:
            self.push.buttons.set_button_color(push2_python.constants.BUTTON_PLAY, definitions.GREEN)
        else:
            self.push.buttons.set_button_color(push2_python.constants.BUTTON_PLAY, definitions.LIME)

        # Track solo/mute update for selected track
        sel_idx = self.mcu_manager.selected_track_idx
        state_signature = (tuple(self.mcu_manager.solo_states),
                           tuple(self.mcu_manager.mute_states))
        if getattr(self, "_last_mcu_row_state", None) == state_signature:
            return
        self._last_mcu_row_state = state_signature
        self.display_dirty = True

        if sel_idx is not None:
            if self.mcu_manager.solo_states[sel_idx]:
                self.push.buttons.set_button_color(push2_python.constants.BUTTON_SOLO, definitions.YELLOW)
            else:
                self.push.buttons.set_button_color(push2_python.constants.BUTTON_SOLO, definitions.OFF_BTN_COLOR)

            if self.mcu_manager.mute_states[sel_idx]:
                self.push.buttons.set_button_color(push2_python.constants.BUTTON_MUTE, definitions.SKYBLUE)
            else:
                self.push.buttons.set_button_color(push2_python.constants.BUTTON_MUTE, definitions.OFF_BTN_COLOR)

    def _on_mcu_fader(self, channel_idx, level):
        """
        channel_idx: 0–7
        level:      0.0–1.0
        Sends a Pitch-bend message on that channel to Logic,
        which will move the channel fader in the DAW.
        """
        # 14-bit 0…16383 → signed –8192…+8191
        pb = int(level * 16383) - 8192
        msg = mido.Message('pitchwheel', pitch=pb, channel=channel_idx)
        # send it down the same MCU port Logic is listening to:
        if self.mcu_manager.output_port:
            self.mcu_manager.output_port.send(msg)

    def get_all_modes(self):
        return [getattr(self, element) for element in vars(self) if
                isinstance(getattr(self, element), definitions.LogicMode)]

    def is_mode_active(self, mode):
        return mode in self.active_modes

    def toggle_collapse_scale(self):
        self.collapse_scale = not self.collapse_scale
        self.save_current_settings_to_file()

        if hasattr(self, "melodic_mode") and self.melodic_mode:
            self.melodic_mode.update_pads()

        # Optional: Display notification on screen
        if hasattr(self, "add_display_notification"):
            self.add_display_notification(f"Collapse Scale: {'ON' if self.collapse_scale else 'OFF'}")

    def toggle_and_rotate_help_mode(self):
        if self.is_mode_active(self.help_mode):
            rotation_finished = self.help_mode.move_to_next_page()
            if rotation_finished:
                self.active_modes = [mode for mode in self.active_modes if mode != self.help_mode]
                self.help_mode.deactivate()
        else:
            self.active_modes.append(self.help_mode)
            self.help_mode.activate()

    def toggle_and_rotate_settings_mode(self):
        if self.is_mode_active(self.settings_mode):
            rotation_finished = self.settings_mode.move_to_next_page()
            if rotation_finished:
                self.active_modes = [mode for mode in self.active_modes if mode != self.settings_mode]
                self.settings_mode.deactivate()
        else:
            self.active_modes.append(self.settings_mode)
            self.settings_mode.activate()

    def toggle_and_rotate_mackie_control_mode(self):
        if self.is_mode_active(self.mc_mode):
            self.mcu_manager.on_vpot = None
            rotation_finished = self.mc_mode.move_to_next_page()
            if rotation_finished:
                self.unset_mode_for_xor_group(self.mc_mode)
        else:
            self.mcu_manager.on_vpot = self._on_mcu_vpot
            self.set_mode_for_xor_group(self.mc_mode)

    def toggle_and_rotate_repeat_mode(self):
        if self.is_mode_active(self.repeat_mode):
            rotation_finished = self.repeat_mode.move_to_next_page()
            if rotation_finished:
                self.active_modes = [mode for mode in self.active_modes if mode != self.repeat_mode]
                self.repeat_mode.deactivate()
        else:
            self.active_modes.append(self.repeat_mode)
            self.repeat_mode.activate()

    def toggle_and_rotate_scalemenu_mode(self):
        if self.is_mode_active(self.scalemenu_mode):
            rotation_finished = self.scalemenu_mode.move_to_next_page()
            if rotation_finished:
                self.active_modes = [mode for mode in self.active_modes if mode != self.scalemenu_mode]
                self.scalemenu_mode.deactivate()
        else:
            self.active_modes.append(self.scalemenu_mode)
            self.scalemenu_mode.activate()

    def set_mode_for_xor_group(self, mode_to_set):
        '''This activates the mode_to_set, but makes sure that if any other modes are currently activated
        for the same xor_group, these other modes get deactivated. This also stores a reference to the
        latest active mode for xor_group, so once a mode gets unset, the previously active one can be
        automatically set'''

        if not self.is_mode_active(mode_to_set):

            # First deactivate all existing modes for that xor group
            new_active_modes = []
            for mode in self.active_modes:
                if mode.xor_group is not None and mode.xor_group == mode_to_set.xor_group:
                    mode.deactivate()
                    self.previously_active_mode_for_xor_group[
                        mode.xor_group] = mode  # Store last mode that was active for the group
                else:
                    new_active_modes.append(mode)
            self.active_modes = new_active_modes

            # Now add the mode to set to the active modes list and activate it
            new_active_modes.append(mode_to_set)
            mode_to_set.activate()

    def unset_mode_for_xor_group(self, mode_to_unset):
        '''This deactivates the mode_to_unset and reactivates the previous mode that was active for this xor_group.
        This allows to make sure that one (and onyl one) mode will be always active for a given xor_group.
        '''
        if self.is_mode_active(mode_to_unset):

            # Deactivate the mode to unset
            self.active_modes = [mode for mode in self.active_modes if mode != mode_to_unset]
            mode_to_unset.deactivate()

            # Activate the previous mode that was activated for the same xor_group. If none listed, activate a default one
            previous_mode = self.previously_active_mode_for_xor_group.get(mode_to_unset.xor_group, None)
            if previous_mode is not None:
                del self.previously_active_mode_for_xor_group[mode_to_unset.xor_group]
                self.set_mode_for_xor_group(previous_mode)
        else:
            # Enable default
            # TODO: here we hardcoded the default mode for a specific xor_group, I should clean this a little bit in the future...
            if mode_to_unset.xor_group == 'pads':
                self.set_mode_for_xor_group(self.melodic_mode)

    def on_button_pressed_raw(self, button_name):
        if button_name == push2_python.constants.BUTTON_SHIFT:
            self.shift_held = True
        elif button_name == push2_python.constants.BUTTON_SELECT:
            self.select_held = True

    def on_button_released_raw(self, button_name):
        if button_name == push2_python.constants.BUTTON_SHIFT:
            self.shift_held = False
        elif button_name == push2_python.constants.BUTTON_SELECT:
            self.select_held = False

    # ───────────────────────────────────────────────────────────
    # CALLBACKS (dual-mode)
    def update_play_button_color(self, is_playing):
        if self.use_mcu and self.mcu_manager:
            # MCU owns LEDs
            self.mcu_manager.transport["play"] = is_playing
        else:
            # Fallback to old method
            if is_playing:
                self.push.buttons.set_button_color(push2_python.constants.BUTTON_PLAY, definitions.GREEN)
            else:
                self.push.buttons.set_button_color(push2_python.constants.BUTTON_PLAY, definitions.LIME)

    def update_record_button_color(self, is_recording):
        if self.use_mcu and self.mcu_manager:
            # MCU owns LEDs
            self.mcu_manager.transport["record"] = is_recording
        else:
            if is_recording:
                self.push.buttons.set_button_color(push2_python.constants.BUTTON_RECORD, definitions.RED)
            else:
                self.push.buttons.set_button_color(push2_python.constants.BUTTON_RECORD, definitions.GREEN)

    def update_push2_mute_solo(self, track_idx=None):
        # no MCU yet or no selection
        mcu = getattr(self, "mcu", None)
        if mcu is None or track_idx is None:
            return
        if not (0 <= track_idx < len(mcu.mute_states)):
            return
        """Update Push2 mute and solo button LEDs based on the specified track's state (or selected track if None)."""
        try:
            mcu = getattr(self, "mcu_manager", None)
            if not mcu:
                return  # MCU not initialized
            if track_idx is None:
                return  # No track selected yet

            if not (0 <= track_idx < len(self.mcu.mute_states)):
                return

            mute_state = mcu.mute_states[track_idx]
            solo_state = mcu.solo_states[track_idx]

            # Debug logging
            if self.debug_mcu:
                print(
                    f"[Push2] Updating Mute/Solo LEDs for track {track_idx + 1}: mute={mute_state}, solo={solo_state}")

            # Set Mute button color
            if mute_state:
                self.push.buttons.set_button_color(push2_python.constants.BUTTON_MUTE, definitions.SKYBLUE)
            else:
                self.push.buttons.set_button_color(push2_python.constants.BUTTON_MUTE, definitions.OFF_BTN_COLOR)

            # Set Solo button color
            if solo_state:
                self.push.buttons.set_button_color(push2_python.constants.BUTTON_SOLO, definitions.YELLOW)
            else:
                self.push.buttons.set_button_color(push2_python.constants.BUTTON_SOLO, definitions.OFF_BTN_COLOR)

        except Exception as e:
            print(f"[Push2] Error updating Mute/Solo LEDs: {e}")

    def toggle_mode(self, mode):
        if self.is_mode_active(mode):
            self.unset_mode_for_xor_group(mode)
        else:
            self.set_mode_for_xor_group(mode)

    def toggle_melodic_rhythmic_slice_modes(self):
        if self.is_mode_active(self.melodic_mode):
            self.set_rhythmic_mode()
        elif self.is_mode_active(self.rhyhtmic_mode):
            self.set_slice_notes_mode()
        elif self.is_mode_active(self.slice_notes_mode):
            self.set_melodic_mode()
        else:
            # If none of melodic or rhythmic or slice modes were active, enable melodic by default
            self.set_melodic_mode()

    def set_melodic_mode(self):
        self.set_mode_for_xor_group(self.melodic_mode)

    def set_rhythmic_mode(self):
        self.set_mode_for_xor_group(self.rhyhtmic_mode)

    def set_slice_notes_mode(self):
        self.set_mode_for_xor_group(self.slice_notes_mode)

    def set_preset_selection_mode(self):
        self.set_mode_for_xor_group(self.preset_selection_mode)

    def unset_preset_selection_mode(self):
        self.unset_mode_for_xor_group(self.preset_selection_mode)

    def save_current_settings_to_file(self):
        # NOTE: when saving device names, eliminate the last bit with XX:Y numbers as this might vary across runs
        # if different devices are connected
        settings = {
            'midi_in_default_channel': self.midi_in_channel,
            'midi_out_default_channel': self.midi_out_channel,
            'default_midi_in_device_name': self.midi_in.name[:-4] if self.midi_in is not None else None,
            'default_midi_out_device_name': self.midi_out.name[:-4] if self.midi_out is not None else None,
            'default_notes_midi_in_device_name': self.notes_midi_in.name[
                                                 :-4] if self.notes_midi_in is not None else None,
            'use_push2_display': self.use_push2_display,
            'target_frame_rate': self.target_frame_rate,
            'debug_logs': self.debug_logs,
            'collapse_scale': self.collapse_scale,
            'use_mcu': self.use_mcu,
            'debug_mcu': self.debug_mcu,
            'solo_off_confirm_time': self.solo_off_confirm_time,
            'bank_reassert_delay': self.bank_reassert_delay,
            'mcu_port_name': self.mcu_manager.port_name if self.mcu_manager else None,
        }
        for mode in self.get_all_modes():
            mode_settings = mode.get_settings_to_save()
            if mode_settings:
                settings.update(mode_settings)
        json.dump(settings, open('settings.json', 'w'))

    def init_midi_in(self, device_name=None):
        print('Configuring MIDI in to {}...'.format(device_name))
        self.available_midi_in_device_names = [name for name in mido.get_input_names() if
                                               'Ableton Push' not in name and 'RtMidi' not in name and 'Through' not in name]
        if device_name is not None:
            try:
                full_name = [name for name in self.available_midi_in_device_names if device_name in name][0]
            except IndexError:
                full_name = None
            if full_name is not None:
                if self.midi_in is not None:
                    self.midi_in.callback = None  # Disable current callback (if any)
                try:
                    self.midi_in = mido.open_input(full_name)
                    self.midi_in.callback = self.midi_in_handler
                    print('Receiving MIDI in from "{0}"'.format(full_name))
                except IOError:
                    print('Could not connect to MIDI input port "{0}"\nAvailable device names:'.format(full_name))
                    for name in self.available_midi_in_device_names:
                        print(' - {0}'.format(name))
            else:
                print('No available device name found for {}'.format(device_name))
        else:
            if self.midi_in is not None:
                self.midi_in.callback = None  # Disable current callback (if any)
                self.midi_in.close()
                self.midi_in = None

        if self.midi_in is None:
            print('Not receiving from any MIDI input')

    def init_midi_out(self, device_name=None):
        print('Configuring MIDI out to {}...'.format(device_name))
        self.available_midi_out_device_names = [name for name in mido.get_output_names() if
                                                'Ableton Push' not in name and 'RtMidi' not in name and 'Through' not in name]
        self.available_midi_out_device_names += ['Virtual']

        if device_name is not None:
            try:
                full_name = [name for name in self.available_midi_out_device_names if device_name in name][0]
            except IndexError:
                full_name = None
            if full_name is not None:
                try:
                    if full_name == 'Virtual':
                        self.midi_out = mido.open_output(full_name, virtual=True)
                    else:
                        self.midi_out = mido.open_output(full_name)
                    print('Will send MIDI to "{0}"'.format(full_name))
                except IOError:
                    print('Could not connect to MIDI output port "{0}"\nAvailable device names:'.format(full_name))
                    for name in self.available_midi_out_device_names:
                        print(' - {0}'.format(name))
            else:
                print('No available device name found for {}'.format(device_name))
        else:
            if self.midi_out is not None:
                self.midi_out.close()
                self.midi_out = None

        if self.midi_out is None:
            print('Won\'t send MIDI to any device')

    def init_notes_midi_in(self, device_name=None):
        print('Configuring notes MIDI in to {}...'.format(device_name))
        self.available_midi_in_device_names = [name for name in mido.get_input_names() if
                                               'Ableton Push' not in name and 'RtMidi' not in name and 'Through' not in name]

        if device_name is not None:
            try:
                full_name = [name for name in self.available_midi_in_device_names if device_name in name][0]
            except IndexError:
                full_name = None
            if full_name is not None:
                if self.notes_midi_in is not None:
                    self.notes_midi_in.callback = None  # Disable current callback (if any)
                try:
                    self.notes_midi_in = mido.open_input(full_name)
                    self.notes_midi_in.callback = self.notes_midi_in_handler
                    print('Receiving notes MIDI in from "{0}"'.format(full_name))
                except IOError:
                    print('Could not connect to notes MIDI input port "{0}"\nAvailable device names:'.format(full_name))
                    for name in self.available_midi_in_device_names:
                        print(' - {0}'.format(name))
            else:
                print('No available device name found for {}'.format(device_name))
        else:
            if self.notes_midi_in is not None:
                self.notes_midi_in.callback = None  # Disable current callback (if any)
                self.notes_midi_in.close()
                self.notes_midi_in = None

        if self.notes_midi_in is None:
            print('Could not configures notes MIDI input')

    def set_midi_in_channel(self, channel, wrap=False):
        self.midi_in_channel = channel
        if self.midi_in_channel < -1:  # Use "-1" for "all channels"
            self.midi_in_channel = -1 if not wrap else 15
        elif self.midi_in_channel > 15:
            self.midi_in_channel = 15 if not wrap else -1

    def set_midi_out_channel(self, channel, wrap=False):
        # We use channel -1 for the "track setting" in which midi channel is taken from currently selected track
        self.midi_out_channel = channel
        if self.midi_out_channel < -1:
            self.midi_out_channel = -1 if not wrap else 15
        elif self.midi_out_channel > 15:
            self.midi_out_channel = 15 if not wrap else -1

    def set_midi_in_device_by_index(self, device_idx):
        if 0 <= device_idx < len(self.available_midi_in_device_names):
            self.init_midi_in(self.available_midi_in_device_names[device_idx])
        else:
            self.init_midi_in(None)

    def set_midi_out_device_by_index(self, device_idx):
        if 0 <= device_idx < len(self.available_midi_out_device_names):
            self.init_midi_out(self.available_midi_out_device_names[device_idx])
        else:
            self.init_midi_out(None)

    def set_notes_midi_in_device_by_index(self, device_idx):
        if 0 <= device_idx < len(self.available_midi_in_device_names):
            self.init_notes_midi_in(self.available_midi_in_device_names[device_idx])
        else:
            self.init_notes_midi_in(None)

    def send_midi(self, msg, use_original_msg_channel=False):
        # Unless we specifically say we want to use the original msg midi channel, set it to global midi out channel or to the channel of the current track
        if not use_original_msg_channel and hasattr(msg, 'channel'):
            midi_out_channel = self.midi_out_channel
            if self.midi_out_channel == -1:
                # Send the message to the midi channel of the currently selected track (or to track 1 if selected track has no midi channel information)
                track_midi_channel = self.track_selection_mode.get_current_track_info()['midi_channel']
                if track_midi_channel == -1:
                    midi_out_channel = 0
                else:
                    midi_out_channel = track_midi_channel - 1  # msg.channel is 0-indexed
            msg = msg.copy(channel=midi_out_channel)

        if self.midi_out is not None:
            self.midi_out.send(msg)

    def midi_in_handler(self, msg):
        if hasattr(msg,
                   'channel'):  # This will rule out sysex and other "strange" messages that don't have channel info
            if self.midi_in_channel == -1 or msg.channel == self.midi_in_channel:  # If midi input channel is set to -1 (all) or a specific channel

                skip_message = False
                if msg.type == 'aftertouch':
                    now = time.time()
                    if (abs(self.last_cp_value_received - msg.value) > 10) and (
                            now - self.last_cp_value_received_time < 0.5):
                        skip_message = True
                    else:
                        self.last_cp_value_received = msg.value
                    self.last_cp_value_received_time = time.time()

                if not skip_message:
                    # Forward message to the main MIDI out
                    self.send_midi(msg)

                    # Forward the midi message to the active modes
                    for mode in self.active_modes:
                        mode.on_midi_in(msg, source=self.midi_in.name)

    def notes_midi_in_handler(self, msg):
        # Check if message is note on or off and check if the MIDI channel is the one assigned to the currently
        # selected track Then, send message to the melodic/rhythmic active modes so the notes are shown in pads/keys
        if msg.type == 'note_on' or msg.type == 'note_off':
            track_midi_channel = self.track_selection_mode.get_current_track_info()['midi_channel']
            if msg.channel == track_midi_channel - 1:  # msg.channel is 0-indexed
                for mode in self.active_modes:
                    if mode == self.melodic_mode or mode == self.rhyhtmic_mode:
                        mode.on_midi_in(msg, source=self.notes_midi_in.name)
                        if mode.lumi_midi_out is not None:
                            mode.lumi_midi_out.send(msg)
                        else:
                            # If midi not properly initialized try to re-initialize but don't do it too ofter
                            if time.time() - mode.last_time_tried_initialize_lumi > 5:
                                mode.init_lumi_midi_out()

    def add_display_notification(self, text):
        self.notification_text = text
        self.notification_time = time.time()

    def clear_display_notification(self):
        self.notification_text = None
        self.notification_time = time.time()

    def add_display_help(self, title, hotkey, path, description, color):
        self.help_title = title
        self.help_hotkey = hotkey
        self.help_path = path
        self.help_description = description
        self.help_color = color
        self.help_time = time.time()

    def clear_display_help(self):
        self.help_title = self.help_hotkey = self.help_path = self.help_description = self.help_color = None
        self.help_time = time.time()

    def init_push(self):
        print('Configuring Push...')
        self.push = push2_python.Push2(run_simulator=platform.system() != "Linux")
        if platform.system() == "Linux":
            # When this app runs in Linux is because it is running on the Raspberrypi
            #  I've overved problems trying to reconnect many times withotu success on the Raspberrypi, resulting in
            # "ALSA lib seq_hw.c:466:(snd_seq_hw_open) open /dev/snd/seq failed: Cannot allocate memory" issues.
            # A work around is make the reconnection time bigger, but a better solution should probably be found.
            self.push.set_push2_reconnect_call_interval(2)

        if self.use_push2_display:
            draw_splash_screen(self.push.display)

    def update_push2_pads(self):
        for mode in self.active_modes:
            mode.update_pads()

    def update_push2_buttons(self):
        for mode in self.active_modes:
            mode.update_buttons()

    def update_push2_display(self):
        if self.use_push2_display:
            # Prepare cairo canvas
            w, h = push2_python.constants.DISPLAY_LINE_PIXELS, push2_python.constants.DISPLAY_N_LINES
            surface = cairo.ImageSurface(cairo.FORMAT_RGB16_565, w, h)
            ctx = cairo.Context(surface)

            # Call all active modes to write to context
            for mode in self.active_modes:
                mode.update_display(ctx, w, h)

            # Show any notifications that should be shown
            if self.notification_text is not None:
                time_since_notification_started = time.time() - self.notification_time
                if time_since_notification_started < definitions.NOTIFICATION_TIME:
                    show_notification(ctx, self.notification_text,
                                      opacity=1 - time_since_notification_started / definitions.NOTIFICATION_TIME)
                else:
                    self.notification_text = None

            # Show any notifications that should be shown
            if self.help_title is not None:
                time_since_help_started = time.time() - self.help_time
                if time_since_help_started < definitions.HELP_TIME:
                    show_help(ctx, self.help_title, self.help_hotkey, self.help_path, self.help_description,
                              self.help_color, opacity=1)
                else:
                    self.help_title = self.help_hotkey = self.help_path = self.help_description = self.help_color = None

            # Convert cairo data to numpy array and send to push
            buf = surface.get_data()
            frame = numpy.ndarray(shape=(h, w), dtype=numpy.uint16, buffer=buf).transpose()
            self.push.display.display_frame(frame, input_format=push2_python.constants.FRAME_FORMAT_RGB565)

    def check_for_delayed_actions(self):
        # If MIDI not configured, make sure we try sending messages so it gets configured
        if not self.push.midi_is_configured():
            self.push.configure_midi()

        # Call dalyed actions in active modes
        for mode in self.active_modes:
            mode.check_for_delayed_actions()

        if self.pads_need_update:
            self.update_push2_pads()
            self.pads_need_update = False
            self.display_dirty = True

        if self.buttons_need_update:
            self.update_push2_buttons()
            self.buttons_need_update = False
            self.display_dirty = True

        # NEW: MCU sync
        if self.use_mcu and self.mcu_manager:
            self.update_push_from_mcu()

    def run_loop(self):
        print('Time to give Logic PRO a little PUSH...(>^_^)>')
        try:
            while True:
                before_draw_time = time.time()

                # Draw ui
                self.update_push2_display()

                # Frame rate measurement
                now = time.time()
                self.current_frame_rate_measurement += 1
                if now - self.current_frame_rate_measurement_second > 1.0:
                    self.actual_frame_rate = self.current_frame_rate_measurement
                    self.current_frame_rate_measurement = 0
                    self.current_frame_rate_measurement_second = now
                    # print('{0} fps'.format(self.actual_frame_rate))

                # Check if any delayed actions need to be applied
                self.check_for_delayed_actions()

                after_draw_time = time.time()

                # Calculate sleep time to aproximate the target frame rate
                sleep_time = (1.0 / self.target_frame_rate) - (after_draw_time - before_draw_time)
                if sleep_time > 0:
                    time.sleep(sleep_time)

        except KeyboardInterrupt:
            print('Exiting Logic...')
            if self.mcu_manager:
                self.mcu_manager.stop()
            self.push.f_stop.set()

    def on_midi_push_connection_established(self):
        # Do initial configuration of Push
        print('Doing initial Push config...')

        # Force configure MIDI out (in case it wasn't...)
        try:
            self.push.configure_midi_out()
        except push2_python.exceptions.Push2MIDIeviceNotFound:
            # App can still run with simulator...
            pass

        # Configure custom color palette
        app.push.color_palette = {}
        for count, color_name in enumerate(definitions.COLORS_NAMES):
            app.push.set_color_palette_entry(count, [color_name, color_name],
                                             rgb=definitions.get_color_rgb_float(color_name), allow_overwrite=True)
        app.push.reapply_color_palette()

        app.push.buttons.set_all_buttons_color(color=definitions.BLACK)
        app.push.pads.set_all_pads_to_color(color=definitions.BLACK)
        # Restore MCU button states
        if self.use_mcu and self.mcu_manager:
            self.update_push2_mute_solo()
            self.update_play_button_color(self.mcu_manager.transport["play"])
            self.update_record_button_color(self.mcu_manager.transport["record"])

        # Iterate over modes and (re-)activate them
        for mode in self.active_modes:
            mode.activate()

        # Update buttons and pads (just in case something was missing!)
        self.update_play_button_color(False)
        #self.push.buttons.set_button_color(push2_python.constants.BUTTON_RECORD, definitions.GREEN)
        #self.push.buttons.set_button_color(push2_python.constants.BUTTON_SOLO, definitions.YELLOW)
        #self.push.buttons.set_button_color(push2_python.constants.BUTTON_MUTE, definitions.RED)

        app.update_push2_buttons()
        app.update_push2_pads()

    def is_button_being_pressed(self, button_name):
        global buttons_pressed_state
        return buttons_pressed_state.get(button_name, False)

    def set_button_ignore_next_action_if_not_yet_triggered(self, button_name):
        global buttons_should_ignore_next_release_action, buttons_waiting_to_trigger_processed_action
        if buttons_waiting_to_trigger_processed_action.get(button_name, False):
            buttons_should_ignore_next_release_action[button_name] = True


# Bind push action handlers with class methods
@push2_python.on_encoder_rotated()
def on_encoder_rotated(_, encoder_name, increment):
    try:
        # Give Mackie Control mode first dibs when active
        if hasattr(app, 'mc_mode') and app.is_mode_active(app.mc_mode):
            if app.mc_mode.on_encoder_rotated(encoder_name, increment):
                return
        for mode in app.active_modes[::-1]:
            action_performed = mode.on_encoder_rotated(encoder_name, increment)
            if action_performed:
                break  # If mode took action, stop event propagation
    except NameError as e:
        print('Error:  {}'.format(str(e)))
        traceback.print_exc()


pads_pressing_log = defaultdict(list)
pads_timers = defaultdict(None)
pads_pressed_state = {}
pads_should_ignore_next_release_action = {}
pads_last_pressed_veocity = {}


@push2_python.on_pad_pressed()
def on_pad_pressed(_, pad_n, pad_ij, velocity):
    global pads_pressing_log, pads_timers, pads_pressed_state, pads_should_ignore_next_release_action

    # - Trigger raw pad pressed action
    try:
        for mode in app.active_modes[::-1]:
            action_performed = mode.on_pad_pressed_raw(pad_n, pad_ij, velocity)
            if action_performed:
                break  # If mode took action, stop event propagation
    except NameError as e:
        print('Error:  {}'.format(str(e)))
        traceback.print_exc()

    # - Trigger processed pad actions
    def delayed_long_press_pad_check(pad_n, pad_ij, velocity):
        # If the maximum time to consider a long press has passed and pad has not yet been released,
        # trigger the long press pad action already and make sure when pad is actually released
        # no new processed pad action is triggered
        if pads_pressed_state.get(pad_n, False):
            # If pad has not been released, trigger the long press action
            try:
                for mode in app.active_modes[::-1]:
                    action_performed = mode.on_pad_pressed(pad_n, pad_ij, velocity, long_press=True,
                                                           loop=pads_pressed_state.get(
                                                               push2_python.constants.BUTTON_DOUBLE_LOOP, False),
                                                           quantize=pads_pressed_state.get(
                                                               push2_python.constants.BUTTON_QUANTIZE, False),
                                                           shift=pads_pressed_state.get(
                                                               push2_python.constants.BUTTON_SHIFT, False),
                                                           select=pads_pressed_state.get(
                                                               push2_python.constants.BUTTON_SELECT, False))
                    if action_performed:
                        break  # If mode took action, stop event propagation
            except NameError as e:
                print('Error:  {}'.format(str(e)))
                traceback.print_exc()

            # Store that next release action should be ignored so that long press action is not retriggered when
            # actual pad release takes place
            pads_should_ignore_next_release_action[pad_n] = True

    # Save the current time the pad is pressed and clear any delayed execution timer that existed Also save
    # velocity of the current pressing as it will be used when triggering the actual porcessed action when
    # release action is triggered
    pads_last_pressed_veocity[pad_n] = velocity
    pads_pressing_log[pad_n].append(time.time())
    pads_pressing_log[pad_n] = pads_pressing_log[pad_n][
                               -2:]  # Keep only last 2 records (needed to check double presses)
    if pads_timers.get(pad_n, None) is not None:
        pads_timers[pad_n].setClearTimer()

    # Schedule a delayed action for the pad long press that will fire as soon as the pad is being pressed for
    # more than definitions.BUTTON_LONG_PRESS_TIME
    pads_timers[pad_n] = definitions.Timer()
    pads_timers[pad_n].setTimeout(delayed_long_press_pad_check, [pad_n, pad_ij, velocity],
                                  definitions.BUTTON_LONG_PRESS_TIME)

    # - Store pad pressed state
    pads_pressed_state[pad_n] = True


@push2_python.on_pad_released()
def on_pad_released(_, pad_n, pad_ij, velocity):
    global pads_pressing_log, pads_timers, pads_pressed_state, pads_should_ignore_next_release_action

    # - Trigger raw pad released action
    try:
        for mode in app.active_modes[::-1]:
            action_performed = mode.on_pad_released_raw(pad_n, pad_ij, velocity)
            if action_performed:
                break  # If mode took action, stop event propagation
    except NameError as e:
        print('Error:  {}'.format(str(e)))
        traceback.print_exc()

    # - Trigger processed pad actions
    def delayed_double_press_pad_check(pad_n, pad_ij, velocity):
        last_time_pressed = pads_pressing_log[pad_n][-1]
        try:
            previous_time_pressed = pads_pressing_log[pad_n][-2]
        except IndexError:
            previous_time_pressed = 0
        if last_time_pressed - previous_time_pressed < definitions.BUTTON_DOUBLE_PRESS_TIME:
            # If time between last 2 pressings is shorter than BUTTON_DOUBLE_PRESS_TIME, trigger double press action
            try:
                for mode in app.active_modes[::-1]:
                    action_performed = mode.on_pad_pressed(pad_n, pad_ij, velocity, double_press=True,
                                                           loop=pads_pressed_state.get(
                                                               push2_python.constants.BUTTON_DOUBLE_LOOP, False),
                                                           quantize=pads_pressed_state.get(
                                                               push2_python.constants.BUTTON_QUANTIZE, False),
                                                           shift=pads_pressed_state.get(
                                                               push2_python.constants.BUTTON_SHIFT, False),
                                                           select=pads_pressed_state.get(
                                                               push2_python.constants.BUTTON_SELECT, False))
                    if action_performed:
                        break  # If mode took action, stop event propagation
            except NameError as e:
                print('Error:  {}'.format(str(e)))
                traceback.print_exc()
        else:
            try:
                for mode in app.active_modes[::-1]:
                    action_performed = mode.on_pad_pressed(pad_n, pad_ij, velocity,
                                                           loop=pads_pressed_state.get(
                                                               push2_python.constants.BUTTON_DOUBLE_LOOP, False),
                                                           quantize=pads_pressed_state.get(
                                                               push2_python.constants.BUTTON_QUANTIZE, False),
                                                           shift=pads_pressed_state.get(
                                                               push2_python.constants.BUTTON_SHIFT, False),
                                                           select=pads_pressed_state.get(
                                                               push2_python.constants.BUTTON_SELECT, False))
                    if action_performed:
                        break  # If mode took action, stop event propagation
            except NameError as e:
                print('Error:  {}'.format(str(e)))
                traceback.print_exc()

    if not pads_should_ignore_next_release_action.get(pad_n, False):
        # If pad is not marked to ignore the next release action, then use the delayed_double_press_pad_check to decide whether
        # a "normal press" or a "double press" should be triggered
        # Clear any delayed execution timer that existed to avoid duplicated events
        if pads_timers.get(pad_n, None) is not None:
            pads_timers[pad_n].setClearTimer()
        pads_timers[pad_n] = definitions.Timer()
        velocity_of_press_action = pads_last_pressed_veocity.get(pad_n, velocity)
        pads_timers[pad_n].setTimeout(delayed_double_press_pad_check, [pad_n, pad_ij, velocity_of_press_action],
                                      definitions.BUTTON_DOUBLE_PRESS_TIME)
    else:
        pads_should_ignore_next_release_action[pad_n] = False

    # Store pad pressed state
    pads_pressed_state[pad_n] = False


@push2_python.on_pad_aftertouch()
def on_pad_aftertouch(_, pad_n, pad_ij, velocity):
    try:
        for mode in app.active_modes[::-1]:
            action_performed = mode.on_pad_aftertouch(pad_n, pad_ij, velocity)
            if action_performed:
                break  # If mode took action, stop event propagation
    except NameError as e:
        print('Error:  {}'.format(str(e)))
        traceback.print_exc()


buttons_pressing_log = defaultdict(list)
buttons_timers = defaultdict(None)
buttons_pressed_state = {}
buttons_should_ignore_next_release_action = {}
buttons_waiting_to_trigger_processed_action = {}


@push2_python.on_button_pressed()
def on_button_pressed(_, name):
    global buttons_pressing_log, buttons_timers, buttons_pressed_state, buttons_should_ignore_next_release_action, buttons_waiting_to_trigger_processed_action

    # - Trigger raw button pressed action
    try:
        for mode in app.active_modes[::-1]:
            action_performed = mode.on_button_pressed_raw(name)
            mode.set_buttons_need_update_if_button_used(name)
            if action_performed:
                break  # If mode took action, stop event propagation
    except NameError as e:
        print('Error:  {}'.format(str(e)))
        traceback.print_exc()

    # - Trigger processed button actions
    buttons_waiting_to_trigger_processed_action[name] = True

    def delayed_long_press_button_check(name):
        # If the maximum time to consider a long press has passed and button has not yet been released,
        # trigger the long press button action already and make sure when button is actually released
        # no new processed button action is triggered
        if buttons_pressed_state.get(name, False):
            # If button has not been released, trigger the long press action
            try:
                for mode in app.active_modes[::-1]:
                    action_performed = mode.on_button_pressed(name, long_press=True,
                                                              loop=buttons_pressed_state.get(
                                                                  push2_python.constants.BUTTON_DOUBLE_LOOP, False),
                                                              quantize=buttons_pressed_state.get(
                                                                  push2_python.constants.BUTTON_QUANTIZE, False),
                                                              shift=buttons_pressed_state.get(
                                                                  push2_python.constants.BUTTON_SHIFT, False),
                                                              select=buttons_pressed_state.get(
                                                                  push2_python.constants.BUTTON_SELECT, False))
                    mode.set_buttons_need_update_if_button_used(name)
                    if action_performed:
                        break  # If mode took action, stop event propagation
                buttons_waiting_to_trigger_processed_action[name] = False
            except NameError as e:
                print('Error:  {}'.format(str(e)))
                traceback.print_exc()

            # Store that next release action should be ignored so that long press action is not retriggered when actual button release takes place
            buttons_should_ignore_next_release_action[name] = True

    # Save the current time the button is pressed and clear any delayed execution timer that existed
    buttons_pressing_log[name].append(time.time())
    buttons_pressing_log[name] = buttons_pressing_log[name][
                                 -2:]  # Keep only last 2 records (needed to check double presses)
    if buttons_timers.get(name, None) is not None:
        buttons_timers[name].setClearTimer()

    # Schedule a delayed action for the button long press that will fire as soon as the button is being pressed for more than definitions.BUTTON_LONG_PRESS_TIME
    buttons_timers[name] = definitions.Timer()
    buttons_timers[name].setTimeout(delayed_long_press_button_check, [name], definitions.BUTTON_LONG_PRESS_TIME)

    # - Store button pressed state
    buttons_pressed_state[name] = True


@push2_python.on_button_released()
def on_button_released(_, name):
    global buttons_pressing_log, buttons_timers, buttons_pressed_state, buttons_should_ignore_next_release_action, buttons_waiting_to_trigger_processed_action

    # - Trigger raw button released action
    try:
        for mode in app.active_modes[::-1]:
            action_performed = mode.on_button_released_raw(name)
            mode.set_buttons_need_update_if_button_used(name)
            if action_performed:
                break  # If mode took action, stop event propagation
    except NameError as e:
        print('Error:  {}'.format(str(e)))
        traceback.print_exc()

    # - Trigger processed button actions
    def delayed_double_press_button_check(name):
        if name not in buttons_pressing_log or not buttons_pressing_log[name]:
            return  # or handle safely
        last_time_pressed = buttons_pressing_log[name][-1]
        try:
            previous_time_pressed = buttons_pressing_log[name][-2]
        except IndexError:
            previous_time_pressed = 0
        if last_time_pressed - previous_time_pressed < definitions.BUTTON_DOUBLE_PRESS_TIME:
            # If time between last 2 pressings is shorter than BUTTON_DOUBLE_PRESS_TIME, trigger double press action
            try:
                for mode in app.active_modes[::-1]:
                    action_performed = mode.on_button_pressed(name, double_press=True,
                                                              loop=buttons_pressed_state.get(
                                                                  push2_python.constants.BUTTON_DOUBLE_LOOP, False),
                                                              quantize=buttons_pressed_state.get(
                                                                  push2_python.constants.BUTTON_QUANTIZE, False),
                                                              shift=buttons_pressed_state.get(
                                                                  push2_python.constants.BUTTON_SHIFT, False),
                                                              select=buttons_pressed_state.get(
                                                                  push2_python.constants.BUTTON_SELECT, False))
                    mode.set_buttons_need_update_if_button_used(name)
                    if action_performed:
                        break  # If mode took action, stop event propagation
                buttons_waiting_to_trigger_processed_action[name] = False
            except NameError as e:
                print('Error:  {}'.format(str(e)))
                traceback.print_exc()
        else:
            try:
                for mode in app.active_modes[::-1]:
                    action_performed = mode.on_button_pressed(name,
                                                              loop=buttons_pressed_state.get(
                                                                  push2_python.constants.BUTTON_DOUBLE_LOOP, False),
                                                              quantize=buttons_pressed_state.get(
                                                                  push2_python.constants.BUTTON_QUANTIZE, False),
                                                              shift=buttons_pressed_state.get(
                                                                  push2_python.constants.BUTTON_SHIFT, False),
                                                              select=buttons_pressed_state.get(
                                                                  push2_python.constants.BUTTON_SELECT, False))
                    mode.set_buttons_need_update_if_button_used(name)
                    if action_performed:
                        break  # If mode took action, stop event propagation
                buttons_waiting_to_trigger_processed_action[name] = False
            except NameError as e:
                print('Error:  {}'.format(str(e)))
                traceback.print_exc()

    if not buttons_should_ignore_next_release_action.get(name, False):
        # If button is not marked to ignore the next release action, then use the delayed_double_press_button_check to decide whether
        # a "normal press" or a "double press" should be triggered
        # Clear any delayed execution timer that existed to avoid duplicated events
        if buttons_timers.get(name, None) is not None:
            buttons_timers[name].setClearTimer()
        buttons_timers[name] = definitions.Timer()
        buttons_timers[name].setTimeout(delayed_double_press_button_check, [name], definitions.BUTTON_DOUBLE_PRESS_TIME)
    else:
        buttons_should_ignore_next_release_action[name] = False

    # Store button pressed state
    buttons_pressed_state[name] = False


@push2_python.on_touchstrip()
def on_touchstrip(_, value):
    try:
        for mode in app.active_modes[::-1]:
            action_performed = mode.on_touchstrip(value)
            if action_performed:
                break  # If mode took action, stop event propagation
    except NameError as e:
        print('Error:  {}'.format(str(e)))
        traceback.print_exc()


@push2_python.on_sustain_pedal()
def on_sustain_pedal(_, sustain_on):
    try:
        for mode in app.active_modes[::-1]:
            action_performed = mode.on_sustain_pedal(sustain_on)
            if action_performed:
                break  # If mode took action, stop event propagation
    except NameError as e:
        print('Error:  {}'.format(str(e)))
        traceback.print_exc()


midi_connected_received_before_app = False


@push2_python.on_midi_connected()
def on_midi_connected(_):
    global midi_connected_received_before_app

    try:
        app.on_midi_push_connection_established()
    except NameError:
        # app is not yet created; flag to call later after initialization
        midi_connected_received_before_app = True
        print("[Push2] MIDI connected before app initialized; will initialize later.")


# Run app main loop
if __name__ == "__main__":
    app = LogicApp()
    # Set global DEBUG_LOGS from app state
    import logic_keystrokes

    logic_keystrokes.DEBUG_LOGS = app.debug_logs

    if midi_connected_received_before_app:
        # App received the "on_midi_connected" call before it was initialized. Do it now!
        print('Missed MIDI initialization call, doing it now...')
        app.on_midi_push_connection_established()
    app.run_loop()
