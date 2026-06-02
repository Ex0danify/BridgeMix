"""
Pure-function SysEx frame builder and parser.

All frame construction goes through build_write() and build_read().
No inline byte arrays elsewhere in the codebase.

Roland DT1 write frame (mido 15 bytes, wire 17 bytes):
  [41 10 00 00 00 00 11] [12] [7F] [sec] [type] [addr_hi] [addr_lo] [value] [chk]
   0                  6   7    8    9     10      11        12        13      14

Roland RQ1 read frame (mido 17 bytes, wire 19 bytes):
  [41 10 00 00 00 00 11] [11] [7F] [sec] [type] [addr_hi] [addr_lo] [00] [00] [size] [chk]
   0                  6   7    8    9     10      11        12        13   14   15     16
"""
from __future__ import annotations

# Sub-model byte used in all Roland Bridge Cast frames
_SUBMODEL = 0x7F

# DT1 section used by heartbeat RQ1 requests (host → device, 50 ms)
_SECTION_STATUS = 0x01


def _roland_checksum(data: list[int]) -> int:
    """Roland-1 checksum: (128 - sum(data) % 128) % 128."""
    return (128 - sum(data) % 128) % 128


def build_write(
    section: int,
    type_: int,
    addr_hi: int,
    addr_lo: int,
    value: int,
) -> tuple[int, ...]:
    """Build a DT1 write frame (mido tuple, 15 bytes)."""
    chk = _roland_checksum([_SUBMODEL, section, type_, addr_hi, addr_lo, value])
    return (
        0x41, 0x10, 0x00, 0x00, 0x00, 0x00, 0x11,  # Roland header
        0x12,        # DT1
        _SUBMODEL,   # 0x7F
        section, type_, addr_hi, addr_lo, value,
        chk,
    )


def build_write_pair(
    section: int,
    type_: int,
    addr_hi: int,
    addr_lo: int,
    val1: int,
    val2: int,
) -> tuple[int, ...]:
    """Build a DT1 write frame with 2 data bytes (pair write, 16 mido bytes).

    Confirmed from official app MIDI capture (2026-05-27): profile name bytes
    are written as 2-byte pairs in a single DT1 frame.  The checksum covers
    all address and data bytes: sum([_SUBMODEL, section, type_, addr_hi,
    addr_lo, val1, val2]) mod 128, negated mod 128.

    Roland DT1 pair-write frame layout (mido 16 bytes, wire 18 bytes):
      [41 10 00 00 00 00 11] [12] [7F] [sec] [type] [addr_hi] [addr_lo] [val1] [val2] [chk]
       0                  6   7    8    9     10      11        12        13     14     15
    """
    chk = _roland_checksum([_SUBMODEL, section, type_, addr_hi, addr_lo, val1, val2])
    return (
        0x41, 0x10, 0x00, 0x00, 0x00, 0x00, 0x11,  # Roland header
        0x12,        # DT1
        _SUBMODEL,   # 0x7F
        section, type_, addr_hi, addr_lo, val1, val2,
        chk,
    )


def build_read(
    section: int,
    type_: int,
    addr_hi: int,
    addr_lo: int,
    size: int,
) -> tuple[int, ...]:
    """Build an RQ1 read frame (mido tuple, 17 bytes)."""
    chk = _roland_checksum([_SUBMODEL, section, type_, addr_hi, addr_lo, 0x00, 0x00, size])
    return (
        0x41, 0x10, 0x00, 0x00, 0x00, 0x00, 0x11,  # Roland header
        0x11,        # RQ1
        _SUBMODEL,   # 0x7F
        section, type_, addr_hi, addr_lo,
        0x00, 0x00,  # padding bytes
        size,
        chk,
    )


def build_heartbeat_rq1(type_byte: int, addr_byte: int, size: int) -> tuple[int, ...]:
    """Build a heartbeat RQ1 frame into SECTION_STATUS (0x01)."""
    return build_read(_SECTION_STATUS, type_byte, addr_byte, 0x00, size)


def build_identity_request() -> tuple[int, ...]:
    """Universal MIDI Identity Request (mido tuple, 4 bytes)."""
    return (0x7E, 0x7F, 0x06, 0x01)


def parse_identity_reply(data: tuple[int, ...]) -> dict | None:
    """
    Parse a Universal MIDI Identity Reply (GM spec, Section 6.1).

    Mido data layout (without F0/F7):
      [0]  7E   universal non-realtime
      [1]  dev_id
      [2]  06   sub-id 1: General Information
      [3]  02   sub-id 2: Identity Reply
      [4]  manufacturer_id  (Roland = 0x41; 0x00 signals 3-byte ID in [4:7])
      [5]  family_lsb
      [6]  family_msb
      [7]  member_lsb
      [8]  member_msb
      [9]  sw_rev_1          firmware nibble / byte
      [10] sw_rev_2
      [11] sw_rev_3
      [12] sw_rev_4

    Returns dict: manufacturer, family (int), member (int), firmware (4-tuple),
    or None if not a valid identity reply.
    """
    if len(data) < 13:
        return None
    if data[0] != 0x7E or data[2] != 0x06 or data[3] != 0x02:
        return None
    manufacturer = data[4]
    # 7-bit MIDI values: family/member are (msb << 7) | lsb
    family  = (data[6] << 7) | data[5]
    member  = (data[8] << 7) | data[7]
    firmware = (data[9], data[10], data[11], data[12])
    return {
        "manufacturer": manufacturer,
        "family":       family,
        "member":       member,
        "firmware":     firmware,
    }


def parse(data: tuple[int, ...]) -> dict | None:
    """
    Parse an incoming mido SysEx data tuple into a structured dict.

    Returns None if the frame is not a recognisable Roland Bridge Cast frame.
    The returned dict always contains: cmd, section, type, addr_hi, addr_lo.
    Single-value frames also have 'value'.
    Bulk frames also have 'payload' (bytes between address and CHK).
    'raw' always holds the original tuple for the MIDI monitor.
    """
    if len(data) < 15:
        return None
    if data[0] != 0x41 or data[8] != _SUBMODEL:
        return None

    cmd = data[7]
    section = data[9]
    type_ = data[10]
    addr_hi = data[11]
    addr_lo = data[12]

    result: dict = {
        "cmd": cmd,
        "section": section,
        "type": type_,
        "addr_hi": addr_hi,
        "addr_lo": addr_lo,
        "raw": data,
    }

    if len(data) == 15:
        # Standard single-value DT1: [... value chk]
        result["value"] = data[13]
    elif len(data) > 15:
        # Bulk frame: payload is everything from data[13] to data[-2] (last byte is CHK)
        result["payload"] = data[13:-1]
        result["value"] = data[13]  # first payload byte (convenient)

    return result
