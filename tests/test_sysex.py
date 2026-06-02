"""Tests for the pure SysEx frame builder/parser (``bridgemix.midi.sysex``)."""
from __future__ import annotations

from bridgemix.midi import sysex


# ── Checksum ──────────────────────────────────────────────────────────────────

def test_roland_checksum_zero_sum():
    assert sysex._roland_checksum([0, 0, 0]) == 0


def test_roland_checksum_makes_total_divisible_by_128():
    data = [0x7F, 0x03, 0x07, 0x10, 0x00, 0x40]
    chk = sysex._roland_checksum(data)
    assert (sum(data) + chk) % 128 == 0
    assert 0 <= chk < 128


# ── build_write ───────────────────────────────────────────────────────────────

def test_build_write_length_and_framing():
    frame = sysex.build_write(0x03, 0x07, 0x10, 0x00, 0x40)
    assert len(frame) == 15
    assert frame[:7] == (0x41, 0x10, 0x00, 0x00, 0x00, 0x00, 0x11)
    assert frame[7] == 0x12          # DT1
    assert frame[8] == sysex._SUBMODEL
    assert frame[9:14] == (0x03, 0x07, 0x10, 0x00, 0x40)


def test_build_write_checksum_valid():
    frame = sysex.build_write(0x03, 0x07, 0x10, 0x00, 0x40)
    # Checksum covers the 6 bytes [submodel … value] == frame[8:14]; with the
    # trailing checksum byte the running total is a multiple of 128.
    assert (sum(frame[8:14]) + frame[14]) % 128 == 0


def test_build_write_all_byte_values_are_7bit_or_header():
    # Every data byte after the header must be a legal MIDI data byte (<128).
    frame = sysex.build_write(0x7F, 0x7F, 0x7F, 0x7F, 0x7F)
    assert all(b < 128 for b in frame[7:])


# ── build_write_pair ──────────────────────────────────────────────────────────

def test_build_write_pair_layout_and_checksum():
    frame = sysex.build_write_pair(0x03, 0x00, 0x00, 0x61, 0x4D, 0x00)
    assert len(frame) == 16
    assert frame[7] == 0x12
    assert frame[9:15] == (0x03, 0x00, 0x00, 0x61, 0x4D, 0x00)
    assert (sum(frame[8:15]) + frame[15]) % 128 == 0


# ── build_read ────────────────────────────────────────────────────────────────

def test_build_read_length_and_framing():
    frame = sysex.build_read(0x02, 0x00, 0x00, 0x00, 0x12)
    assert len(frame) == 17
    assert frame[7] == 0x11          # RQ1
    assert frame[8] == sysex._SUBMODEL
    assert frame[9:13] == (0x02, 0x00, 0x00, 0x00)
    assert frame[13:15] == (0x00, 0x00)  # padding
    assert frame[15] == 0x12         # size


def test_build_read_checksum_valid():
    frame = sysex.build_read(0x02, 0x00, 0x00, 0x00, 0x12)
    assert (sum(frame[8:16]) + frame[16]) % 128 == 0


def test_build_heartbeat_rq1_targets_status_section():
    frame = sysex.build_heartbeat_rq1(0x10, 0x00, 0x7C)
    assert frame[7] == 0x11
    assert frame[9] == sysex._SECTION_STATUS
    assert frame[10] == 0x10
    assert frame[15] == 0x7C


# ── Identity ──────────────────────────────────────────────────────────────────

def test_build_identity_request():
    assert sysex.build_identity_request() == (0x7E, 0x7F, 0x06, 0x01)


def test_parse_identity_reply_valid():
    # 7E dev 06 02 mfr fam_lsb fam_msb mem_lsb mem_msb fw0 fw1 fw2 fw3
    data = (0x7E, 0x10, 0x06, 0x02, 0x41, 0x02, 0x01, 0x04, 0x03, 0x01, 0x00, 0x00, 0x00)
    info = sysex.parse_identity_reply(data)
    assert info is not None
    assert info["manufacturer"] == 0x41
    assert info["family"] == (0x01 << 7) | 0x02   # msb<<7 | lsb
    assert info["member"] == (0x03 << 7) | 0x04
    assert info["firmware"] == (0x01, 0x00, 0x00, 0x00)


def test_parse_identity_reply_too_short():
    assert sysex.parse_identity_reply((0x7E, 0x10, 0x06, 0x02)) is None


def test_parse_identity_reply_wrong_subids():
    data = (0x7E, 0x10, 0x06, 0x01) + (0,) * 9  # 0x01 = request, not reply
    assert sysex.parse_identity_reply(data) is None


# ── parse ─────────────────────────────────────────────────────────────────────

def test_parse_single_value_round_trip():
    frame = sysex.build_write(0x03, 0x07, 0x10, 0x00, 0x40)
    parsed = sysex.parse(frame)
    assert parsed is not None
    assert parsed["cmd"] == 0x12
    assert parsed["section"] == 0x03
    assert parsed["type"] == 0x07
    assert parsed["addr_hi"] == 0x10
    assert parsed["addr_lo"] == 0x00
    assert parsed["value"] == 0x40
    assert "payload" not in parsed
    assert parsed["raw"] == frame


def test_parse_bulk_frame_extracts_payload():
    # 15-byte header region + extra payload bytes before the final checksum.
    data = (0x41, 0x10, 0x00, 0x00, 0x00, 0x00, 0x11,
            0x12, 0x7F, 0x03, 0x07, 0x00, 0x00,
            0x11, 0x22, 0x33, 0x44,   # payload
            0x00)                      # checksum (not validated by parse)
    parsed = sysex.parse(data)
    assert parsed is not None
    assert parsed["payload"] == (0x11, 0x22, 0x33, 0x44)
    assert parsed["value"] == 0x11    # convenience: first payload byte


def test_parse_rejects_too_short():
    assert sysex.parse((0x41, 0x10, 0x00)) is None


def test_parse_rejects_non_roland_header():
    data = (0x42,) + (0x00,) * 14
    assert sysex.parse(data) is None


def test_parse_rejects_wrong_submodel():
    data = list(sysex.build_write(0x03, 0x07, 0x10, 0x00, 0x40))
    data[8] = 0x00  # corrupt submodel byte
    assert sysex.parse(tuple(data)) is None
