import json
import pytest
from settings_schema import Settings, VALID_GUI_PROFILES


class TestSettingsDefaults:
    def test_default_instance_is_valid(self):
        s = Settings()
        assert s.use_mcu is True
        assert s.target_frame_rate == 60
        assert s.gui_profile == "legacy"
        assert s.debug_logs is False

    def test_all_fields_have_defaults(self):
        # Should not raise even with no arguments
        Settings()


class TestFromDict:
    def test_empty_dict_uses_all_defaults(self):
        s = Settings.from_dict({})
        assert s == Settings()

    def test_known_keys_are_applied(self):
        s = Settings.from_dict({"debug_logs": True, "target_frame_rate": 30})
        assert s.debug_logs is True
        assert s.target_frame_rate == 30

    def test_unknown_keys_are_ignored(self):
        s = Settings.from_dict({"totally_made_up_key": 999})
        assert s == Settings()

    def test_partial_dict_keeps_other_defaults(self):
        s = Settings.from_dict({"use_mcu": False})
        assert s.use_mcu is False
        assert s.target_frame_rate == 60  # unchanged default


class TestValidation:
    def test_midi_channel_clamped_to_0_15(self):
        s = Settings.from_dict({"midi_in_default_channel": 200})
        assert s.midi_in_default_channel == 15

    def test_midi_channel_negative_clamped_to_0(self):
        s = Settings.from_dict({"midi_in_default_channel": -5})
        assert s.midi_in_default_channel == 0

    def test_invalid_gui_profile_falls_back_to_legacy(self):
        s = Settings.from_dict({"gui_profile": "nonexistent_profile"})
        assert s.gui_profile == "legacy"

    def test_valid_gui_profiles_are_accepted(self):
        for profile in VALID_GUI_PROFILES:
            s = Settings.from_dict({"gui_profile": profile})
            assert s.gui_profile == profile

    def test_zero_frame_rate_resets_to_60(self):
        s = Settings.from_dict({"target_frame_rate": 0})
        assert s.target_frame_rate == 60

    def test_negative_frame_rate_resets_to_60(self):
        s = Settings.from_dict({"target_frame_rate": -10})
        assert s.target_frame_rate == 60

    def test_root_midi_note_clamped_to_127(self):
        s = Settings.from_dict({"root_midi_note": 200})
        assert s.root_midi_note == 127

    def test_root_midi_note_clamped_to_0(self):
        s = Settings.from_dict({"root_midi_note": -1})
        assert s.root_midi_note == 0

    def test_at_range_end_adjusted_when_not_greater_than_start(self):
        s = Settings.from_dict({"channel_at_range_start": 500, "channel_at_range_end": 400})
        assert s.channel_at_range_end == s.channel_at_range_start + 1


class TestRoundTrip:
    def test_to_dict_then_from_dict_is_identity(self):
        original = Settings(
            debug_logs=True,
            target_frame_rate=30,
            root_midi_note=48,
            gui_profile="mackie_v2",
        )
        assert Settings.from_dict(original.to_dict()) == original

    def test_json_round_trip(self, tmp_path):
        original = Settings(use_mcu=False, collapse_scale=True, root_midi_note=36)
        path = tmp_path / "settings.json"
        with open(path, "w") as f:
            json.dump(original.to_dict(), f)
        with open(path) as f:
            loaded = Settings.from_dict(json.load(f))
        assert loaded == original

    def test_to_dict_contains_all_keys(self):
        from dataclasses import fields
        s = Settings()
        d = s.to_dict()
        for field in fields(s):
            assert field.name in d
