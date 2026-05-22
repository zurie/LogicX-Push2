import pytest
import definitions


class TestPbToDb:
    def test_exact_zero_db_breakpoint(self):
        # pb=12443 is the 0.0 dB entry in _FADER_TABLE
        assert definitions.pb_to_db(12443) == pytest.approx(0.0)

    def test_exact_min_breakpoint(self):
        # pb=60 → -100.0 dB (first table entry)
        assert definitions.pb_to_db(60) == pytest.approx(-100.0)

    def test_exact_max_breakpoint(self):
        # pb=14845 → +6.0 dB (last table entry)
        assert definitions.pb_to_db(14845) == pytest.approx(6.0)

    def test_below_min_clamps_to_lowest_db(self):
        assert definitions.pb_to_db(0) == pytest.approx(-100.0)

    def test_above_max_clamps_to_highest_db(self):
        assert definitions.pb_to_db(16383) == pytest.approx(6.0)

    def test_interpolation_between_breakpoints(self):
        # Midpoint between pb=12443 (0.0 dB) and pb=12644 (+0.5 dB)
        mid = (12443 + 12644) // 2
        result = definitions.pb_to_db(mid)
        assert 0.0 < result < 0.5

    def test_known_minus_6db_breakpoint(self):
        assert definitions.pb_to_db(9874) == pytest.approx(-6.0)


class TestDbToPb:
    def test_exact_zero_db(self):
        assert definitions.db_to_pb(0.0) == 12443

    def test_exact_min_db(self):
        assert definitions.db_to_pb(-100.0) == 60

    def test_exact_max_db(self):
        assert definitions.db_to_pb(6.0) == 14845

    def test_below_min_clamps_to_lowest_pb(self):
        assert definitions.db_to_pb(-200.0) == 60

    def test_above_max_clamps_to_highest_pb(self):
        assert definitions.db_to_pb(100.0) == 14845

    def test_known_minus_6db(self):
        assert definitions.db_to_pb(-6.0) == 9874


class TestRoundTrip:
    @pytest.mark.parametrize("pb", [60, 9874, 12443, 14845])
    def test_pb_survives_roundtrip(self, pb):
        # pb → dB → pb should be within 1 LSB of original
        assert abs(definitions.db_to_pb(definitions.pb_to_db(pb)) - pb) <= 1

    @pytest.mark.parametrize("db", [-100.0, -6.0, 0.0, 6.0])
    def test_db_survives_roundtrip(self, db):
        # dB → pb → dB should be within 0.1 dB of original
        assert definitions.pb_to_db(definitions.db_to_pb(db)) == pytest.approx(db, abs=0.1)


class TestScales:
    def test_scales_nonempty(self):
        assert len(definitions.SCALES) > 0

    def test_each_scale_has_12_notes(self):
        for scale in definitions.SCALES:
            assert len(scale.notes) == 12, f"{scale.name} notes length != 12"

    def test_scale_notes_are_binary(self):
        for scale in definitions.SCALES:
            for note in scale.notes:
                assert note in (0, 1), f"{scale.name} has non-binary value {note}"

    def test_each_scale_has_at_least_one_note(self):
        for scale in definitions.SCALES:
            assert sum(scale.notes) >= 1, f"{scale.name} has no active notes"

    def test_scale_names_are_unique(self):
        names = [s.name for s in definitions.SCALES]
        assert len(names) == len(set(names))

    def test_major_scale_pattern(self):
        major = next(s for s in definitions.SCALES if s.name == 'Major')
        # W W H W W W H → semitones 0,2,4,5,7,9,11 active
        assert major.notes == [1, 0, 1, 0, 1, 1, 0, 1, 0, 1, 0, 1]

    def test_minor_scale_pattern(self):
        minor = next(s for s in definitions.SCALES if s.name == 'Minor')
        # Natural minor → semitones 0,2,3,5,7,8,10 active
        assert minor.notes == [1, 0, 1, 1, 0, 1, 0, 1, 1, 0, 1, 0]

    def test_whole_tone_is_symmetric(self):
        wt = next(s for s in definitions.SCALES if s.name == 'Whole Tone')
        # Every other semitone: 0,2,4,6,8,10
        assert wt.notes == [1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0]
