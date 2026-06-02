# Roland Bridge Cast — SysEx Protocol

Specification of the undocumented Roland Bridge Cast control protocol (MIDI SysEx over USB).
The device is USB Audio Class compliant, so no custom driver is needed — only MIDI SysEx.

> `src/bridgemix/device/constants/` (package) is the authoritative source for all addresses and
> values; this document mirrors it. Where a value is uncertain it is marked **inferred** or **unknown**.

**Supported hardware**

| Device | USB ID |
|---|---|
| Roland Bridge Cast (original) | `0582:0231` |
| Roland Bridge Cast V2 / X | `0582:031e` |

---

## SysEx Protocol

### Frame Structure (17 bytes, F0/F7 inclusive)

```
F0  41  10  00  00  00  00  11  12  7F  [SECTION]  [TYPE]  [ADDR_HI]  [ADDR_LO]  [VALUE]  [CHK]  F7
 0   1   2   3   4   5   6   7   8   9     10        11       12         13         14      15    16
```

`mido` strips F0 and F7 automatically. The **data tuple** passed to/from mido is **15 bytes**
(indices 0–14 above correspond to bytes 1–15 of the full frame).

| Field | Mido index | Notes |
|---|---|---|
| Manufacturer (Roland) | 0 = `0x41` | Fixed |
| Device ID | 1 = `0x10` | Fixed |
| Model bytes | 2–6 = `00 00 00 00 11` | Fixed |
| Command | 7 | `0x12` = DT1 write, `0x11` = RQ1 read |
| Sub-model | 8 = `0x7F` | Fixed |
| Section | 9 | `0x01`=Status, `0x02`=Global, `0x03`=Channel |
| Type | 10 | `0x00`=Switch, `0x01`=Mic FX, `0x02`=Voice, `0x07`=Fader … |
| ADDR_HI | 11 | Primary address byte |
| ADDR_LO | 12 | Usually `0x00`; `0x01` is meaningful in the Mix-Link burst and VSurround angles |
| VALUE | 13 | `0x00`–`0x7F` |
| [CHK] | 14 | Roland-1 checksum |

> **`ADDR_LO` (byte 12) is NOT always padding.** The Mix-Link enable burst uses `ADDR_LO = 0x01`
> for Stream-side differential frames, and Virtual Surround angles >127° set `ADDR_LO = 0x01`.
> Always log and check both `ADDR_HI` and `ADDR_LO`.

Manual decode example — Mic volume on the Personal bus, value `0x69` (105):

```
F0 41 10 00 00 00 00 11 12 7F  03  07  10  00  69  [CHK]  F7
                                ↑   ↑   ↑   ↑   ↑
                              CH  FAD  PS_MIC  0  105
```

### Section Bytes

| Constant | Value | Purpose |
|---|---|---|
| `SECTION_STATUS` | `0x01` | Heartbeat / keep-alive (host → device, 50 ms) |
| `SECTION_GLOBAL` | `0x02` | Global device settings (mix mode, LED brightness, …) |
| `SECTION_CHANNEL` | `0x03` | Per-channel and per-bus parameters (main working section) |
| `SECTION_PROFILE_0`–`SECTION_PROFILE_4` | `0x20`–`0x24` | Per-profile parameter blocks (5 profiles) |
| `SECTION_VOICE_FX` | `0x7F` | Voice FX preset selection (non-standard section) |
| `SECTION_SYNC_10` | `0x10` | **Voice FX preset bank** — 5 named slots; type byte = slot index × 0x10 |
| `SECTION_SYNC_11` | `0x11` | **Game EQ preset bank** — 5 named slots; same slot-index encoding |
| `SECTION_SYNC_12` | `0x12` | Unknown — all-zero in captures (possibly a third preset bank or reserved) |
| `SECTION_SYNC_30` | `0x30` | Unknown — 27-byte all-zero payload; purpose TBD |

**Preset bank slot encoding (SECTION_SYNC_10 / SECTION_SYNC_11):**
The TYPE byte selects the preset slot: `type=0x00`=slot 0, `type=0x10`=slot 1, `type=0x20`=slot 2, `type=0x30`=slot 3, `type=0x40`=slot 4.

**Payload layout (70 bytes, `SYNC_RQ1_VOICE_FX_PRESET_SIZE = 0x46`):**

| Address range | Content |
|---|---|
| `0x00`–`0x11` | Plain ASCII preset name, null-terminated, **max 18 chars** |
| `0x20`+ | Voice/EQ parameters at their canonical SECTION_CHANNEL addresses |

The name starts at **addr 0x00**. Example factory/slot names:
- Voice FX bank (SECTION_SYNC_10): slot 0 = `"Revbr"`, slot 4 max-length example = `"ABCDEFGHIJKLMNOPQR"`
- Game EQ bank (SECTION_SYNC_11): slot 0 = `"AX"`, 1 = `"VTR"`, 2 = `"FNT"`, 3 = `"CD"`, 4 = `"F SeGeneral"`

### Type Bytes

All types below apply to `SECTION_CHANNEL` (`0x03`) unless noted.

| Constant | Value | Purpose |
|---|---|---|
| `TYPE_SWITCH` | `0x00` | On/off and selector parameters |
| `TYPE_MIC_FX` | `0x01` | Mic "Clean Up" block (Low Cut, NS, De-esser, Compressor Legacy, Mic EQ) |
| `TYPE_VOICE` | `0x02` | Voice effect parameters (pitch, formant, mode, reverb) |
| `TYPE_CHAT_FX` | `0x04` | Chat channel effect parameters (De-esser, Compressor) |
| `TYPE_GAME_FX` | `0x05` | Game channel effects (EQ, Limiter, Virtual Surround) |
| `TYPE_DELAY` | `0x06` | Output delay parameters |
| `TYPE_FADER` | `0x07` | Volume and mute parameters |
| `TYPE_STRIP_CONFIG` | `0x08` | Channel LED ring colour + strip assignment |
| `TYPE_HOTKEY` | `0x09` | HOT KEY function (Modifier + HID Keycode) |
| `TYPE_UNKNOWN_0A` | `0x0A` | Unknown; multi-addr (0x00/0x20/0x50), all-zero |
| `TYPE_UNKNOWN_0B` | `0x0B` | Unknown; addr 0x20/0x50, all-zero; per-profile only |
| `TYPE_UNKNOWN_0C` | `0x0C` | Unknown; addr 0x20/0x50, all-zero |
| `TYPE_UNKNOWN_0D` | `0x0D` | Unknown; 52-byte payload, all-zero; also at sec=0x03 addr=0x30 |
| `TYPE_MIC_FX_EXT` | `0x0E` | Extended Mic FX: NS Expander + Compressor Modern (newer firmware) |
| `TYPE_GLOBAL_SFX_A` | `0x01` (in `SECTION_GLOBAL`) | SFX A Volume + Filename |
| `TYPE_GLOBAL_SFX_B` | `0x02` (in `SECTION_GLOBAL`) | SFX B Volume + preset name + params |
| `TYPE_VOICE_FX` | `0x7F` | Voice FX preset select (paired with `SECTION_VOICE_FX = 0x7F`) |

### Heartbeat (SECTION_STATUS, every 50 ms)

The device **requires** a continuous RQ1-based heartbeat from the host or it stops responding.

#### TX heartbeat (host → device)

RQ1 wire frame (19 bytes total):
```
F0 41 10 00 00 00 00 11 11 7F  01 TT AA 00 00 00 SS  CK F7
                               └────── body (7) ─────┘
```
Built via `build_heartbeat_rq1(type_byte, addr_byte, size)` in `midi/sysex.py`.

**Every tick (~50 ms, 3 frames):**

| Type | Addr | Size | Purpose |
|---|---|---|---|
| `0x10` | `0x00` | `0x7C` (124) | Request 124-byte state vector (live level meters) |
| `0x11` | `0x40` | `0x08` (8) | Request dynamic status A |
| `0x11` | `0x60` | `0x10` (16) | Request dynamic status B |

**Every 20th tick (~1 s long-poll, 3 extra frames):**

| Type | Addr | Size | Purpose |
|---|---|---|---|
| `0x00` | `0x00` | `0x08` (8) | Keep-alive ping (firmware echo) |
| `0x10` | `0x00` | `0x7C` (124) | State vector (also in normal batch) |
| `0x11` | `0x00` | `0x70` (112) | Full status snapshot |

Reference checksums:

| Frame | Wire bytes (after `… 11 7F`) |
|---|---|
| `0x00/0x00/0x08` | `01 00 00 00 00 00 08 78` |
| `0x10/0x00/0x7C` | `01 10 00 00 00 00 7C 74` |
| `0x11/0x00/0x70` | `01 11 00 00 00 00 70 7F` |
| `0x11/0x40/0x08` | `01 11 40 00 00 00 08 27` |
| `0x11/0x60/0x10` | `01 11 60 00 00 00 10 7F` |

#### RX heartbeat replies (device → host)

**Every tick (~50 ms, 4 DT1 reply frames):**

| # | Roland addr | Size | Payload |
|---|---|---|---|
| 1 | sec=0x01 ty=0x10 addr=0x00 | 127 B (FW 3.00) / 137 B (FW 1.06) | **Live state vector** (level meters) |
| 1b | sec=0x01 ty=0x10 addr_hi=0x70 | — | FW 3.00 only: continuation with the trimmed `OUT_PHONES R` + `OUT_LINE` tail |
| 2 | sec=0x01 ty=0x10 addr=0x7A | 17 B | 2-byte tail beacon (liveness / drop detection) |
| 3 | sec=0x01 ty=0x11 addr=0x40 | 23 B | 8-byte status block (zero at idle) |
| 4 | sec=0x01 ty=0x11 addr=0x60 | 31 B | 16-byte status block (zero at idle) |

**Every ~1 s long-poll, 2 additional frames:**

| # | Reply to | Payload |
|---|---|---|
| 5 | RQ1 `00/00/08` | Static firmware echo `01 06 00 73 00 09 00 00` |
| 6 | RQ1 `11/00/70` | Full per-channel settings snapshot (112 bytes) |

### Bulk Sync on Connect (RQ1 reads, `_SYNC_FRAMES`)

`bridge_cast.py` sends 11 RQ1 bulk reads on connect (staggered 5 ms apart). The device replies with
DT1 bulk payloads and also auto-emits unsolicited per-profile dumps for sections 0x20–0x24.

| Section | Type | Size | Purpose |
|---|---|---|---|
| `SECTION_GLOBAL` (0x02) | `TYPE_SWITCH` (0x00) | `0x12` (18 B) | Global settings |
| `SECTION_CHANNEL` (0x03) | `TYPE_FADER` (0x07) | `0x6A` (106 B) | All faders + mutes |
| `SECTION_CHANNEL` (0x03) | `TYPE_SWITCH` (0x00) | `0x4A` (74 B) | Switch block |
| `SECTION_CHANNEL` (0x03) | `TYPE_DELAY` (0x06) | `0x04` (4 B) | Output delay |
| `SECTION_CHANNEL` (0x03) | `TYPE_STRIP_CONFIG` (0x08) | `0x40` (64 B) | LED colours + strip config |
| `SECTION_CHANNEL` (0x03) | `TYPE_MIC_FX` (0x01) | `0x7C` (124 B) | Mic Clean Up + 10-band EQ |
| `SECTION_CHANNEL` (0x03) | `TYPE_MIC_FX_EXT` (0x0E) | `0x2A` (42 B) | NS Expander + Compressor Modern |
| `SECTION_CHANNEL` (0x03) | `TYPE_VOICE` (0x02) | `0x46` (70 B) | Voice FX + Reverb |
| `SECTION_CHANNEL` (0x03) | `TYPE_CHAT_FX` (0x04) | `0x1C` (28 B) | Chat FX effects |
| `SECTION_CHANNEL` (0x03) | `TYPE_GAME_FX` (0x05) | `0x6E` (110 B) | Game EQ + Limiter + VSurround |
| `SECTION_CHANNEL` (0x03) | `TYPE_HOTKEY` (0x09) | `0x38` (56 B) | Hot Key assignments |

### Handshake

On connect, send **Universal MIDI Identity Request** (`F0 7E 7F 06 01 F7`) before any SysEx.
The device replies with an Identity Reply (`7E <dev_id> 06 02 ...`). Without this handshake
the device may not respond to host writes.

---

## Address Map

All addresses are `SECTION_CHANNEL` (`0x03`) unless noted. `ADDR_LO` is `0x00` unless noted.

### Stream Mix Bus Volumes (`TYPE_FADER` = `0x07`)

| Constant | ADDR_HI | Channel |
|---|---|---|
| `ADDR_ST_MIC_VOL` | `0x00` | Mic → Stream |
| `ADDR_ST_AUX_VOL` | `0x02` | Aux → Stream |
| `ADDR_ST_CHAT_VOL` | `0x04` | Chat → Stream |
| `ADDR_ST_GAME_VOL` | `0x06` | Game → Stream |
| `ADDR_ST_MUSIC_VOL` | `0x08` | Music → Stream |
| `ADDR_ST_SYS_VOL` | `0x0A` | System → Stream |
| `ADDR_ST_SFX_VOL` | `0x0C` | SFX → Stream |

### Stream Mix Bus Mutes (`TYPE_FADER` = `0x07`, `0x00`=muted, `0x01`=active)

| Constant | ADDR_HI |
|---|---|
| `ADDR_ST_MIC_MUTE` | `0x20` |
| `ADDR_ST_AUX_MUTE` | `0x22` |
| `ADDR_ST_CHAT_MUTE` | `0x24` |
| `ADDR_ST_GAME_MUTE` | `0x26` |
| `ADDR_ST_MUSIC_MUTE` | `0x28` |
| `ADDR_ST_SYS_MUTE` | `0x2A` |

### Personal Mix Bus Volumes (`TYPE_FADER` = `0x07`)

| Constant | ADDR_HI | Channel |
|---|---|---|
| `ADDR_PS_MIC_VOL` | `0x10` | Mic → Personal |
| `ADDR_PS_AUX_VOL` | `0x12` | Aux → Personal |
| `ADDR_PS_CHAT_VOL` | `0x14` | Chat → Personal |
| `ADDR_PS_GAME_VOL` | `0x16` | Game → Personal |
| `ADDR_PS_MUSIC_VOL` | `0x18` | Music → Personal |
| `ADDR_PS_SYS_VOL` | `0x1A` | System → Personal |
| `ADDR_PS_SFX_VOL` | `0x1C` | SFX → Personal |

### Personal Mix Bus Mutes (`TYPE_FADER` = `0x07`, `0x00`=muted, `0x01`=active)

| Constant | ADDR_HI |
|---|---|
| `ADDR_PS_MIC_MUTE` | `0x30` |
| `ADDR_PS_AUX_MUTE` | `0x32` |
| `ADDR_PS_CHAT_MUTE` | `0x34` |
| `ADDR_PS_GAME_MUTE` | `0x36` |
| `ADDR_PS_MUSIC_MUTE` | `0x38` |
| `ADDR_PS_SYS_MUTE` | `0x3A` |

### Output and Monitor Volumes (`TYPE_FADER` = `0x07`)

| Constant | ADDR_HI | Notes |
|---|---|---|
| `ADDR_SUBMIX_VOL` | `0x52` | Sub-Mix (Personal bus) output volume |
| `ADDR_STREAM_VOL` | `0x50` | Stream output knob — **read-only** (hardware) |
| `ADDR_MIC_DIRECT_VOL` | `0x54` | Un-bussed mic feed — tracks Mic vol when Mix Link ON |
| `ADDR_PHONES_VOL` | `0x56` | Phones output knob — **read-only** (hardware) |
| `ADDR_LINE_OUT` | `0x58` | Line out knob — **read-only** (hardware) |

### Output Mutes (`TYPE_FADER` = `0x07`, `0x00`=muted, `0x01`=active)

| Constant | ADDR_HI | Notes |
|---|---|---|
| `ADDR_MUTE_STREAM_OUT` | `0x60` | Stream output mute |
| `ADDR_MUTE_SUBMIX_OUT` | `0x62` | Sub-Mix (Personal) output mute |
| `ADDR_MUTE_PHONES_OUT` | `0x66` | Phones output mute |
| `ADDR_MUTE_LINE_OUT` | `0x68` | Line Out mute |

### Mic Input Controls (`TYPE_SWITCH` = `0x00`)

| Constant | ADDR_HI | Values |
|---|---|---|
| `ADDR_MIC_SOURCE` | `0x20` | `0x00`=XLR (Dynamic/Condenser), `0x01`=TRS Headset |
| `ADDR_MIC_PHANTOM` | `0x26` | `0x00`=off, `0x01`=+48V on |
| `ADDR_MIC_GAIN_XLR` | `0x22` | `0x00`–`0x19` (25 steps, 0–75dB) |
| `ADDR_MIC_GAIN_HEADSET` | `0x24` | `0x00`–`0x19` (25 steps, 0–38dB) |
| `ADDR_MIC_FX_ENABLE` | `0x30` | `0x00`=off, `0x01`=on |
| `ADDR_MIC_FX_PRESET` | `0x32` | `0x00`–`0x04` (5 presets) |
| `ADDR_GAME_EQ_PRESET` | `0x34` | `0x00`–`0x04` (5 presets) |
| `ADDR_MIX_LINK` | `0x40` | `0x00`=off, `0x01`=on |
| `ADDR_MIC_KNOB_TARGET` | `0x46` | `0x00`=raw mic vol (0x54), `0x01`=personal mix mic vol (0x10) |
| `ADDR_LINE_OUT_MODE` | `0x42` | `0x00`=Mic, `0x01`=StreamMix, `0x02`=PhonesSync |
| `ADDR_USB_OUT_MODE` | `0x44` | `0x00`=Mic, `0x01`=StreamMix |
| `ADDR_SUB_MIX_MODE` | `0x48` | `0x00`=Personal, `0x01`=MicDry, `0x02`=Aux |

> **Address collisions** (the type byte disambiguates):
> - `0x22`: `TYPE_SWITCH`=Mic Gain XLR vs `TYPE_VOICE`=Voice Formant
> - `0x26`: `TYPE_SWITCH`=Mic Phantom vs `TYPE_FADER`=Stream Game Mute
> - `0x46`: `TYPE_SWITCH`=Mic Knob Target vs `TYPE_MIC_FX`=Mic EQ Band4 Q
> - `0x64`: `TYPE_FADER`=Mic Direct Mute Mirror vs `TYPE_MIC_FX`=Mic EQ Band9 Q

> **Voice FX preset** uses a completely different section/type: `sec=0x7F type=0x7F addr=0x02`.
> It is NOT a `SECTION_CHANNEL` address.

> **`ADDR_SWITCH_0x36`** (`0x36`, `TYPE_SWITCH`) — fires as a single-value DT1 with val=0x00
> at idle. Sits after `ADDR_GAME_EQ_PRESET` (0x34). **Purpose unknown** (see "Unknown Addresses").

### Mic "Clean Up" Block (`TYPE_MIC_FX` = `0x01`)

| Constant | ADDR_HI | Range | Notes |
|---|---|---|---|
| `ADDR_MIC_LOW_CUT` | `0x00` | `0x00`=off, `0x01`=on | Low Cut Filter switch |
| `ADDR_MIC_LOW_CUT_FREQ` | `0x02` | `0x00`–`0x0F` | 0=Flat, 1=20Hz … 15=500Hz (16 steps) |
| `ADDR_MIC_NS` | `0x10` | `0x00`=off, `0x01`=on | Noise Suppressor switch |
| `ADDR_MIC_NS_LEVEL` | `0x12` | `0x00`–`0x60` | −96dB to 0dB (Gate type only) |
| `ADDR_MIC_NS_TYPE` | `0x14` | `0x00`=Gate, `0x01`=Adaptive, `0x02`=Expander | NS type selector |
| `ADDR_MIC_NS_ADT_LEVEL` | `0x16` | `0x00`–`0x09` | Adaptive (FFT) level 0–9 (`MicFftNsNormLevel` in backup) |
| `ADDR_MIC_NS_ATTACK` | `0x18` | `0x00`–`0x0A` | 0ms–100ms (Gate type only) |
| `ADDR_MIC_NS_RELEASE` | `0x1A` | `0x00`–`0x14` | 50ms–5000ms (Gate type only) |
| `ADDR_MIC_DE_ESSER` | `0x20` | `0x00`=off, `0x01`=on | De-esser switch |
| `ADDR_MIC_DE_ESSER_DEPTH` | `0x22` | `0x00`–`0x09` | Depth 1–10 |
| `ADDR_MIC_EQ_ENABLE` | `0x30` | `0x00`=off, `0x01`=on | Manual EQ enable |
| `ADDR_MIC_COMPRESSOR` | `0x70` | `0x00`=off, `0x01`=on | Compressor switch (Legacy mode) |
| `ADDR_MIC_COMPRESSOR_ATTACK` | `0x72` | `0x00`–`0x0A` | 0.0ms–100ms |
| `ADDR_MIC_COMPRESSOR_RELEASE` | `0x74` | `0x00`–`0x14` | 50ms–5000ms |
| `ADDR_MIC_COMPRESSOR_THRESHOLD` | `0x76` | `0x00`–`0x10` | −48dB–0dB |
| `ADDR_MIC_COMPRESSOR_RATIO` | `0x78` | `0x00`–`0x0D` | 1.00:1–Inf:1 (13 steps) |
| `ADDR_MIC_COMPRESSOR_POST_GAIN` | `0x7A` | `0x00`–`0x1E` | +0dB–+30dB |

> **NS Adaptive (FFT) has 2 additional parameters** seen in `.brdgcBackup` (`MicFftNsNormAttack`,
> `MicFftNsNormRelease`) whose SysEx addresses are unknown — likely in the gap at `0x17`/`0x19`.

### Mic "Extended FX" Block (`TYPE_MIC_FX_EXT` = `0x0E`)

Newer features added after `TYPE_MIC_FX` (0x01) was already full. Synced via
`SYNC_RQ1_MIC_EXT_SIZE = 0x2A` (42 bytes). The Modern Compressor is **LA-2A style**; the
`.brdgcBackup` export uses the `MicLa2a*` prefix for this block.

| Constant | ADDR_HI | Range | Backup field | Notes |
|---|---|---|---|---|
| `ADDR_COMP_MODE` | `0x00` | `0x00`=Legacy, `0x01`=Modern | — | Compressor mode selector |
| `ADDR_COMP_MOD_AMOUNT` | `0x04` | `0x00`–`0x7F` | `MicLa2aOneKnobVal` | LA-2A one-knob drive (0–127) |
| `ADDR_COMP_MOD_PEAK` | `0x12` | `0x00`–`0x64` | `MicLa2aPeakReduction` | LA-2A Peak Reduction (0–100) |
| `ADDR_COMP_MOD_GAIN` | `0x14` | `0x00`–`0x64` | `MicLa2aGain` | LA-2A Output Gain (0–100) |
| `ADDR_NS_EXP_LEVEL` | `0x20` | `0x27`–`0x63` | `MicNsExpLevel` | NS Expander Level: `v − 99` → −60dB … 0dB |
| `ADDR_NS_EXP_RELEASE` | `0x24` | `0x00`–`0x64` | `MicNsExpRelease` | NS Expander Release: `v × 40` → 0ms … 4000ms |

> Addresses `0x01`–`0x03`, `0x05`–`0x11`, `0x13`, `0x15`–`0x1F`, `0x21`–`0x23`, `0x25`–`0x29`
> in this block are unaccounted for (all-zero at idle). The 5 backup-only params below likely
> live here: `MicLa2aHf`, `MicLa2aLimitMode`, `MicLa2aOneKnobType`, `MicNsExpFastAttack`,
> `MicNsExpRange`.

### Mic Manual EQ (`TYPE_MIC_FX` = `0x01`)

**EQ Enable:** `ADDR_MIC_EQ_ENABLE` = `0x30` — `0x00`=off, `0x01`=on

**Gain range (all bands):** `0x00`=−12dB, `0x0C`=0dB (center/default), `0x18`=+12dB (25 steps, **1dB/step**).

| Band | Shape | Freq range | Freq steps | Gain addr | Freq addr | Q addr |
|------|-------|-----------|------------|-----------|-----------|--------|
| 01 | Low shelf | 20Hz–400Hz | 20 | `0x32` | `0x34` | — |
| 02 | Peak | 20Hz–470Hz | 30 | `0x36` | `0x38` | `0x3A` |
| 03 | Peak | 20Hz–470Hz | 30 | `0x3C` | `0x3E` | `0x40` |
| 04 | Peak | 20Hz–470Hz | 30 | `0x42` | `0x44` | `0x46` |
| 05 | Peak | 315Hz–3.3KHz | 30 | `0x48` | `0x4A` | `0x4C` |
| 06 | Peak | 315Hz–3.3KHz | 30 | `0x4E` | `0x50` | `0x52` |
| 07 | Peak | 315Hz–3.3KHz | 30 | `0x54` | `0x56` | `0x58` |
| 08 | Peak | 3.0KHz–20.0KHz | 30 | `0x5A` | `0x5C` | `0x5E` |
| 09 | Peak | 3.0KHz–20.0KHz | 30 | `0x60` | `0x62` | `0x64` |
| 10 | High shelf | 800Hz–20.0KHz | 20 | `0x66` | `0x68` | — |

Mic and Game EQ share the same band layout and the ±12dB gain scale. The exact per-step raw→Hz
tables live in `src/bridgemix/gui/widgets/eq_widget.py`. Band 2 Q is at `0x3A`; **bands 3–9 Q
addresses are inferred from the stride** (freq_addr + 2).

**Q factor (peak bands 2–9, shared table):** `0x00`=Q 0.3 (widest) … `0x1F`=Q 16 (narrowest),
**32 steps** (see `_Q_TABLE` in `eq_widget.py`).

> `ADDR_MIC_EQ_BAND1_FREQ` (`0x34`) shares its address byte with `ADDR_GAME_EQ_PRESET` (`0x34`).
> The **type byte** disambiguates: `TYPE_MIC_FX` (0x01) vs `TYPE_SWITCH` (0x00).

### Chat "Clean Up" Block (`TYPE_CHAT_FX` = `0x04`)

| Constant | ADDR_HI | Range | Notes |
|---|---|---|---|
| `ADDR_CHAT_DE_ESSER` | `0x00` | `0x00`=off, `0x01`=on | De-esser switch |
| `ADDR_CHAT_DE_ESSER_DEPTH` | `0x02` | `0x00`–`0x09` | Depth 1–10 |
| `ADDR_CHAT_COMPRESSOR` | `0x10` | `0x00`=off, `0x01`=on | Compressor switch |
| `ADDR_CHAT_COMPRESSOR_ATTACK` | `0x12` | `0x00`–`0x0A` | 0.0ms–100ms |
| `ADDR_CHAT_COMPRESSOR_RELEASE` | `0x14` | `0x00`–`0x14` | 50ms–5000ms |
| `ADDR_CHAT_COMPRESSOR_THRESHOLD` | `0x16` | `0x00`–`0x10` | −48dB–0dB |
| `ADDR_CHAT_COMPRESSOR_RATIO` | `0x18` | `0x00`–`0x0D` | 1.00:1–Inf:1 |
| `ADDR_CHAT_COMPRESSOR_POST_GAIN` | `0x1A` | `0x00`–`0x1E` | +0dB–+30dB |

### Voice Effects (`TYPE_VOICE` = `0x02`)

| Constant | ADDR_HI | Range | Notes |
|---|---|---|---|
| `ADDR_VOICE_PITCH` | `0x20` | `0x00`–`0x7F` | Default `0x40`; `VtPitch` in backup |
| `ADDR_VOICE_FORMAT` | `0x22` | `0x00`–`0x7F` | Default `0x40`; `VtFormant` in backup |
| `ADDR_VOICE_MODE` | `0x2C` | `0x00`=Avatar, `0x01`=Sing | |
| `ADDR_REVERB_SWITCH` | `0x40` | `0x00`=off, `0x01`=on | `MicReverbSwitch` in backup |
| `ADDR_REVERB_SIZE` | `0x42` | `0x00`–`0x09` (10 steps) | `MicReverbSize` in backup |
| `ADDR_REVERB_LEVEL` | `0x44` | `0x00`–`0x09` (10 steps) | `MicReverbWetLevel` in backup |

Display formula for pitch/formant: `floor((v − 64) × 100 / 64) / 100` (maps 0–127 → −1.00…+1.00).

These addresses apply to both Mic voice-fx and SFX channel voice controls — the wire frame carries
no source selector; the active source is implicit in device state.

**Voice Transformer parameters seen only in `.brdgcBackup`** (carried in SECTION_SYNC_10 preset
banks; live SECTION_CHANNEL addresses unknown): `VtSwitch` (global VT ON/OFF, distinct from
`mic_fx_enable`), `VtConsonantMode`, `VtRobotSwitch`, `VtRobotVariation`, `VtMegaphoneSwitch`,
`VtMegaphoneVariation`. Robot and Megaphone appear to be mutually exclusive VT sub-modes alongside
Avatar/Sing (`ADDR_VOICE_MODE`).

### Voice FX Preset Selection & Save (`SECTION_VOICE_FX` = `0x7F`, `TYPE_VOICE_FX` = `0x7F`)

| Constant | ADDR_HI | Range | Notes |
|---|---|---|---|
| `ADDR_VOICE_FX_PRESET` | `0x02` | `0x00`–`0x04` | **Load/select** preset slot |
| `ADDR_VOICE_FX_SAVE` | `0x08` | `0x00`–`0x04` | **Save** live voice state to slot |

Load wire: `F0 41 10 00 00 00 00 11 12 7F 7F 7F 02 00 03 7E F7` → load preset 3.
Save wire: `F0 41 10 00 00 00 00 11 12 7F 7F 7F 08 00 04 77 F7` → save to slot 4 (= "slot 5").

### Voice FX Preset Name Write

Before saving, write the desired name to `SECTION_CHANNEL TYPE_VOICE` using a 2-char-per-frame
packing (9 frames for an 18-char name):

- **Section:** `SECTION_CHANNEL` (`0x03`), **Type:** `TYPE_VOICE` (`0x02`)
- `ADDR_HI` = `2 × i` (pair index: `0x00`, `0x02`, `0x04`, … `0x10`)
- `VALUE` = `char[2i]` (even character, ASCII)
- `ADDR_LO` = `char[2i+1]` (odd character, ASCII; `0x00` for null / end padding)
- **Max name length:** 18 characters (`VOICE_FX_PRESET_NAME_MAX = 18`)

Wire example — writing name `"AB"` (addr_hi=0x00, addr_lo=0x42='B', value=0x41='A'):
```
F0 41 10 00 00 00 00 11 12 7F  03  02  00  42  41  [CHK]  F7
                               CH VOICE  ↑   B    A
                                       pair 0
```

Full workflow to save a preset to slot 5:
1. Write all voice parameters (pitch, formant, reverb, etc.) to SECTION_CHANNEL TYPE_VOICE at their canonical addresses
2. Write the name using the 2-char packing above (up to 9 frames for 18 chars)
3. Send `sec=0x7F type=0x7F addr=0x08 val=0x04` to commit to slot 5

### Profile Name Write

Profile names are stored in the TYPE_SWITCH block of each SECTION_PROFILE_* section. To write a name,
write 9 frames to the SECTION_CHANNEL TYPE_SWITCH name region (addr 0x00–0x11), then call
`save_profile_to_slot()` to commit.

- **Section:** `SECTION_CHANNEL` (`0x03`), **Type:** `TYPE_SWITCH` (`0x00`)
- `ADDR_HI` = `2 × i` (pair index: `0x00`, `0x02`, `0x04`, … `0x10`)
- `ADDR_LO` = `char[2i+1]` (odd character = second of pair, ASCII; `0x00` for null / end padding)
- `VALUE` = `char[2i]` (even character = first of pair, ASCII)
- **Max name length:** 18 characters (`PROFILE_NAME_MAX = 18`)

> **Byte order is the OPPOSITE of Voice FX preset name writes.** Voice FX uses `ADDR_LO=char[even]`,
> `VALUE=char[odd]`. Profile names use `ADDR_LO=char[odd]`, `VALUE=char[even]`.

Wire example — writing name `"Dynamic Mic"` pair 0 (chars 'D' and 'y'):
```
F0 41 10 00 00 00 00 11 12 7F  03  00  00  79  44  [CHK]  F7
                               CH  SW  ↑   y    D
                                      pair 0
```

**Read-back encoding:** The device response also uses `addr_lo` as the first data byte (= `char[1]`,
the odd char). The `addr_lo` value in the response frame is the ASCII value of the second character
of the name — **not** a memory offset. The name always lives at address `0x00`.

**JSON encoding cross-check (`.brdgcProfile` export):** `Name_AB = charB × 128 + charA` — Roland's
7-bit packing stores two 7-bit ASCII values as one uint14. E.g. `"Dynamic Mic"` pair 0:
`Name0102 = ord('y') × 128 + ord('D') = 15556`.

Full workflow to save a profile name to slot 2:
1. Write the name using the 2-char packing above (9 frames, 5 ms apart)
2. Wait ≥ 50 ms
3. Send `sec=0x7F type=0x7F addr_hi=0x06 val=0x01` (`ADDR_PROFILE_SAVE`) to copy CHANNEL state to slot 2
4. Send `sec=0x7F type=0x7F addr_hi=0x00 val=0x01` (`ADDR_PROFILE_SELECT_7F`) to activate the slot
5. Re-fetch profile names via RQ1 to confirm

Factory profile names: 0="Dynamic Mic", 1="VoiceChange", 2="Reverb+GameEQ", 3="Headset Mic", 4="Condenser Mic".

### Global Controls (`SECTION_GLOBAL` = `0x02`, `TYPE_SWITCH` = `0x00`)

| Constant | ADDR_HI | Values |
|---|---|---|
| `ADDR_ACTIVE_PROFILE` | `0x00` | `0x00`–`0x04` (profiles 1–5) |
| `ADDR_MIX_MODE` | `0x02` | `0x00`=Personal, `0x01`=Stream |
| `ADDR_LED_BRIGHTNESS` | `0x04` | `0x00`–`0x07` (7 steps) |
| `ADDR_INDICATOR_TYPE` | `0x06` | `0x00`=Level, `0x01`=Meter |
| `ADDR_PHONES_GAIN` | `0x08` | `0x00`=Normal, `0x01`=Boost1, `0x02`=Boost2 |
| `ADDR_MUTE_DISPLAY` | `0x0C` | `0x00`=Blink, `0x01`=OFF |

### SFX Volume (`SECTION_GLOBAL`)

| Constant | Type | ADDR_HI | Range |
|---|---|---|---|
| `ADDR_SFX_A_VOL` | `TYPE_GLOBAL_SFX_A` (0x01) | `0x00` | `0x00`–`0x63` (0–99) |
| `ADDR_SFX_B_VOL` | `TYPE_GLOBAL_SFX_B` (0x02) | `0x00` | `0x00`–`0x63` (0–99) |

### SFX A Filename (`SECTION_GLOBAL`, `TYPE_GLOBAL_SFX_A`)

- **Start Address:** `0x10`, **Step:** `0x02`, **Encoding:** plain ASCII — each SysEx value byte holds one ASCII character code (e.g. `0x41`='A'). Backup field names are `MainSfxAName01`–`MainSfxAName32`, one byte each.
- **Range:** `0x10`–`0x50` (up to 32 chars; char 1 at addr `0x10`, char 2 at `0x12`, …, char 32 at `0x4E`)
- Only the filename is uploaded via SysEx; audio data is NOT sent over SysEx. The `0x02` stride is a SysEx convention, not a Unicode indicator — this is ASCII, not UTF-16LE.

### Mix Link (`SECTION_CHANNEL`, `TYPE_SWITCH`)

| Constant | ADDR_HI | Values |
|---|---|---|
| `ADDR_MIX_LINK` | `0x40` | `0x00`=off, `0x01`=on |

When Mix Link is **enabled**, the device emits a burst of 8 `TYPE_FADER` frames immediately BEFORE
the canonical `mix_link=1` write. These carry `ADDR_LO=0x01` (Stream-side) or `0x00` (Personal-side)
and encode per-channel differential offsets. Mix Link does NOT unify values — each bus keeps its own
absolute level; the device pushes identical deltas to both per-bus addresses on every adjustment.

### Output Delay (`SECTION_CHANNEL`, `TYPE_DELAY` = `0x06`)

| Constant | ADDR_HI | Range | Notes |
|---|---|---|---|
| `ADDR_OUTPUT_DELAY_SW` | `0x00` | `0x00`=off, `0x01`=on | Delay enable |
| `ADDR_OUTPUT_DELAY_AMOUNT` | `0x02` | `0x00`–`0x3C` (60 steps = 0.0ms–1000.0ms) | Delay amount |

### Game Channel Effects (`TYPE_GAME_FX` = `0x05`)

#### Game EQ Preset (`TYPE_SWITCH` = `0x00`)

| Constant | ADDR_HI | Values |
|---|---|---|
| `ADDR_GAME_EQ_PRESET` | `0x34` | `0x00`–`0x04` (slot selector) |

Factory Game EQ preset names (SECTION_SYNC_11): 0="AX", 1="VTR", 2="FNT", 3="CD", 4="F SeGeneral".

#### Game Manual EQ (`TYPE_GAME_FX` = `0x05`)

**EQ Enable:** `ADDR_GAME_EQ_ENABLE` = `0x20` — `0x00`=off, `0x01`=on

**Gain range (all bands):** `0x00`=−12dB, `0x0C`=0dB (center), `0x18`=+12dB (25 steps, **1dB/step**).

| Band | Shape | Freq range | Freq steps | Gain addr | Freq addr | Q addr |
|------|-------|-----------|------------|-----------|----------|--------|
| 01 | Low shelf | 20Hz–400Hz | 20 | `0x22` | `0x24` | — |
| 02 | Peak | 20Hz–470Hz | 30 | `0x26` | `0x28` | `0x2A` |
| 03 | Peak | 20Hz–470Hz | 30 | `0x2C` | `0x2E` | `0x30` |
| 04 | Peak | 20Hz–470Hz | 30 | `0x32` | `0x34` | `0x36` |
| 05 | Peak | 315Hz–3.3KHz | 30 | `0x38` | `0x3A` | `0x3C` |
| 06 | Peak | 315Hz–3.3KHz | 30 | `0x3E` | `0x40` | `0x42` |
| 07 | Peak | 315Hz–3.3KHz | 30 | `0x44` | `0x46` | `0x48` |
| 08 | Peak | 3.0KHz–20.0KHz | 30 | `0x4A` | `0x4C` | `0x4E` |
| 09 | Peak | 3.0KHz–20.0KHz | 30 | `0x50` | `0x52` | `0x54` |
| 10 | High shelf | 800Hz–20.0KHz | 20 | `0x56` | `0x58` | — |

The exact per-step raw→Hz tables are encoded in `src/bridgemix/gui/widgets/eq_widget.py`.

#### EQ Spectrum Analyzer

The FFT/spectrum is **not** transmitted over MIDI — it is computed host-side from a USB audio capture.
The device only exposes an on/off **analyzer flag**:

- **`SECTION_STATUS` (0x01)**, type **`0x10`** (`SUBTYPE_STATUS_10`), addr **`0x16`**, parameter `eq_analyzer`. `0x01`=on, `0x00`=off.
- In the state-vector frame (`sec 0x01 / type 0x10 / addr 0x00`), **byte 36** (data offset 22 after the 14-byte header) mirrors this flag.
- enable:  `F0 41 10 00 00 00 00 11 12 7F 01 10 16 00 01 59 F7`
- disable: `F0 41 10 00 00 00 00 11 12 7F 01 10 16 00 00 5A F7`

Enabling it routes the Game channel into the SUB MIX (the official app warns "the SUB MIX (USB)
temporarily changes"). bridgemix does not use this flag — it ships only the always-on Mic EQ analyzer.

#### Limiter

| Constant | ADDR_HI | Range |
|---|---|---|
| `ADDR_GAME_LIMITER` | `0x60` | `0x00`=off, `0x01`=on |
| `ADDR_GAME_LIMITER_LEVEL` | `0x62` | `0x00`–`0x19` (25 steps) |
| `ADDR_GAME_LIMITER_RELEASE` | `0x64` | `0x00`–`0x18` (24 steps = 10ms–5000ms) |

#### Virtual Surround

| Constant | ADDR_HI | Range | Notes |
|---|---|---|---|
| `ADDR_GAME_VSURROUND` | `0x12` | `0x00`=off, `0x02`=on | |
| `ADDR_GAME_VSURROUND_OUTPUT` | `0x6A` | `0x00`=Phones, `0x01`=Speakers | |
| `ADDR_GAME_VSURROUND_FRONT_ANGLE` | `0x14` | `0x01`–`0x59` (1°–89°) | |
| `ADDR_GAME_VSURROUND_SURROUND_ANGLE` | `0x16` | 91°–179°, with `ADDR_LO=0x01` | Wire wraps at 127 |
| `ADDR_GAME_VSURROUND_BACK_ANGLE` | `0x18` | 91°–179°, with `ADDR_LO=0x01` | Wire wraps at 127 |
| `ADDR_GAME_VSURROUND_LISTEN_ANGLE` | `0x6C` | `0x0C`–`0x4E` (12°–78°; Speakers only) | |

Angles >127° use `ADDR_LO=0x01`: at max (179°), `ADDR_LO=0x01` and `VALUE=0x33`. Outside the
Mix-Link burst, this is the only non-zero `ADDR_LO`.

### Channel LED Colours (`TYPE_STRIP_CONFIG` = `0x08`)

Three separate SysEx writes per channel (R, G, B). Range `0x00`–`0x20` (0–32) per component.
Channel stride = `0x10`; R/G/B stride within a channel = `0x02`.

| Channel | R addr | G addr | B addr |
|---|---|---|---|
| Mic | `0x08` | `0x0A` | `0x0C` |
| Aux | `0x18` | `0x1A` | `0x1C` |
| Chat | `0x28` | `0x2A` | `0x2C` |
| Game | `0x38` | `0x3A` | `0x3C` |

### Hardware Strip Assignment (`TYPE_STRIP_CONFIG` = `0x08`)

| Constant | ADDR_HI | Notes |
|---|---|---|
| `ADDR_HW_STRIP_1_CH` | `0x00` | Strip 1 channel assignment |
| `ADDR_HW_STRIP_2_CH` | `0x10` | Strip 2 channel assignment |
| `ADDR_HW_STRIP_3_CH` | `0x20` | Strip 3 channel assignment |
| `ADDR_HW_STRIP_4_CH` | `0x30` | Strip 4 channel assignment |

Channel index values: `0x00`=Mic, `0x01`=Aux, `0x02`=Chat, `0x03`=Game, `0x04`=Music, `0x05`=System,
`0x06`=SFX (Aux/Music/SFX inferred).

### Strip Button Action (`TYPE_STRIP_CONFIG` = `0x08`)

| Constant | ADDR_HI |
|---|---|
| `ADDR_STRIP1_BUTTON_ACTION` | `0x04` |
| `ADDR_STRIP2_BUTTON_ACTION` | `0x14` |
| `ADDR_STRIP3_BUTTON_ACTION` | `0x24` |
| `ADDR_STRIP4_BUTTON_ACTION` | `0x34` |

Values range `0x00`–`0x25` mapping to: Channel Mute All/Stream/Personal, SFX A/B/Beep, Mute Out
All/Stream/Line/Phones, Profile 1–5, Game EQ 1–5/Off, Mic FX 1–5, MIDI CC 1–4, BGM SFX A–D, Hot Key,
Reverb, BGM Cast Play/Stop/Next.

### HOT KEY Button Function (`TYPE_HOTKEY` = `0x09`)

| Constant | ADDR_HI | ADDR_LO | VALUE |
|---|---|---|---|
| `ADDR_HOTKEY_BTN1` | `0x16` | Modifier Bitmask | USB HID Usage ID |

**Modifier Bitmask (ADDR_LO):** `0x00`=None, `0x02`=Ctrl, `0x04`=Shift, `0x08`=Alt; bitwise OR for combinations.

**Keycodes (VALUE):** Direct USB HID Usage IDs (Keyboard/Keypad Page 0x07). A=`0x04`, Z=`0x1D`, F1=`0x3A`, F12=`0x45`, DEL=`0x4C`.

---

## Unknown / Unresolved Addresses

These addresses or type blocks exist in the protocol but their purpose is not determined; all
payloads are all-zero at idle, so non-idle data is needed to crack their semantics.

### Unknown Type Blocks

| Constant | Type value | Observed addresses | Sections seen |
|---|---|---|---|
| `TYPE_UNKNOWN_0A` | `0x0A` | 0x00 (20 B), 0x20 (46 B), 0x50 (46 B) | sec=0x03, 0x20–0x24 |
| `TYPE_UNKNOWN_0B` | `0x0B` | 0x20 (46 B), 0x50 (46 B) | sec=0x20–0x24 only |
| `TYPE_UNKNOWN_0C` | `0x0C` | 0x20 (46 B), 0x50 (46 B) | sec=0x03, 0x20–0x24 |
| `TYPE_UNKNOWN_0D` | `0x0D` | 0x00 (52 B), 0x30 (52 B) | sec=0x03, 0x20–0x24 |

### Partially-Mapped TYPE_MIC_FX_EXT (0x0E)

6 of 42 bytes mapped; the rest are all-zero at idle. Unmapped ranges: `0x01`–`0x03`, `0x05`–`0x11`,
`0x13`, `0x15`–`0x1F`, `0x21`–`0x23`, `0x25`–`0x29`.

### Parameters known from `.brdgcBackup` with unknown SysEx address

| Backup field | Group | Notes |
|---|---|---|
| `MicFftNsNormAttack` / `MicFftNsNormRelease` | NS Adaptive (FFT) | Attack/Release for Adaptive NS; addr in TYPE_MIC_FX near 0x17–0x19 |
| `MicNsExpFastAttack` / `MicNsExpRange` | NS Expander | Fast Attack + range; addr in TYPE_MIC_FX_EXT gap |
| `MicLa2aHf` / `MicLa2aLimitMode` / `MicLa2aOneKnobType` | LA-2A Modern Compressor | HF emphasis, limit mode, one-knob type; addr in TYPE_MIC_FX_EXT gap |
| `VtSwitch` / `VtConsonantMode` | Voice Transformer | Global VT ON/OFF + consonant mode; likely TYPE_VOICE |
| `VtRobotSwitch` / `VtRobotVariation` | Voice Transformer — Robot | Robot effect switch + variation |
| `VtMegaphoneSwitch` / `VtMegaphoneVariation` | Voice Transformer — Megaphone | Megaphone switch + variation |
| `LedSwMic/Aux/Chat/Game` | LED enable | Per-strip LED on/off; likely TYPE_STRIP_CONFIG or TYPE_SWITCH |
| `MicFxLedColorR/G/B` | Voice FX preset LED | Per-preset LED colour; in SECTION_SYNC_10 banks |
| `GameFxFxLedColorR/G/B` | Game EQ preset LED | Per-preset LED colour; in SECTION_SYNC_11 banks |
| `GameSurrReverbSwitch` | Game Surround | Surround reverb switch; likely TYPE_GAME_FX |
| `MainPhonesLineOutLink` | System | Phones / Line Out link toggle |
| `MainSfxBeepVol` | System | Beep volume (CC 13 triggers beep); SysEx addr unknown |
| `MicFxSwLock` | System | MIC FX switch lock |
| `BgmVolume` | BGM | BGM channel volume |
| `HdmiInput` / `HdmiCompSwitch` / `MainVideoHdmi*` | HDMI (Bridge Cast X) | HDMI control group; X hardware only |

### Unknown Switch Address (`TYPE_SWITCH` = `0x00`)

| Constant | ADDR_HI | Observed value | Notes |
|---|---|---|---|
| `ADDR_SWITCH_0x36` | `0x36` | `0x00` at idle | Sits between Game EQ Preset (0x34) and Mix Link (0x40); likely an FX-related switch |

### Unknown Sync Sections

| Constant | Value | Payload |
|---|---|---|
| `SECTION_SYNC_12` | `0x12` | All-zero; possibly a third preset bank |
| `SECTION_SYNC_30` | `0x30` | 27-byte all-zero payload; purpose TBD |

### Unknown State Vector Slots

In the heartbeat state vector (see below):
- **Abs 73–76**: Always zero — unknown Personal slot (slot 7)
- **Abs 101–108**: Always unknown — Personal slots 14–15
- **Abs 119–122**: Mirrors `OUT_STREAM` in some device states; role unconfirmed

---

## Preset Banks vs Per-Profile Storage

The `.brdgcBackup` export (JSON, `ParameterVersion: 9`) has two distinct storage layers for presets
and per-profile settings, separate from the live SECTION_CHANNEL parameters. (`ParameterVersion`
identifies the firmware's parameter schema; use it to compare backups across firmware updates.)

### Preset Banks (SECTION_SYNC_10 / SECTION_SYNC_11)

Each preset bank holds 5 named slots. Slot index is encoded in the TYPE byte (`type = slot × 0x10`).

| Bank | Section | Backup prefix | Contents |
|---|---|---|---|
| Voice FX preset bank | `SECTION_SYNC_10` (0x10) | `MicEfxMemory{1–5}` | Name, VtPitch, VtFormant, VtSwitch, VtConsonantMode, VtRobotSwitch/Variation, VtMegaphoneSwitch/Variation, MicReverbSwitch/Size/WetLevel, MicFxLedColorR/G/B |
| Game EQ preset bank | `SECTION_SYNC_11` (0x11) | `GameEfxMemory{1–5}` | Name, game EQ state, GameFxFxLedColorR/G/B |

Each `MicEfxMemory` slot stores a snapshot of the full Voice Transformer + Reverb state for that
preset, including the per-preset LED colour. **`MicFxLedColorR/G/B` and `GameFxFxLedColorR/G/B` are
distinct from the strip LED ring colours** (`TYPE_STRIP_CONFIG`).

### Per-Profile Storage (SECTION_PROFILE_0–4)

The device stores per-profile snapshots of each parameter group. Backup prefixes:

| Backup prefix | Contents |
|---|---|
| `ProfMemMicCleanup{1–5}` | Per-profile mic clean-up settings (Low Cut, NS, De-esser, Legacy Compressor, Mic EQ) |
| `ProfMemMicEffects{1–5}` | Per-profile active Voice Transformer + Reverb state (NOT the preset slots) |
| `ProfMemMicLa2aComp{1–5}` | Per-profile Modern (LA-2A) compressor settings |
| `ProfMemMixer{1–5}` | Per-profile fader and mute levels |
| `ProfMemPanelAssign{1–5}` | Per-profile strip panel button assignments |
| `ProfMemGameEffects{1–5}` | Per-profile Game EQ state (NOT the preset slots) |
| `ProfMemChatEffects{1–5}` | Per-profile Chat FX settings |
| `ProfMemStreamingEffects{1–5}` | Per-profile streaming effects settings |

> **Key distinction:** `ProfMemMicEffects{n}` ≠ `MicEfxMemory{n}`. The former is the profile's live
> VT/Reverb state; the latter is a named preset bank slot. Selecting a preset bank slot (via
> `ADDR_MIC_FX_PRESET`) loads from `MicEfxMemory`, not from `ProfMemMicEffects`.

---

## Full State Vector (`SECTION_STATUS` type=0x10, addr=0x00)

Sent every ~50 ms. Frame indices are **absolute** (F0=0). Each 4-byte slot decodes as
`L = (frame[i] << 7) | frame[i+1]`, `R = (frame[i+2] << 7) | frame[i+3]`, range 0–16383.

Firmware 3.00 shortened the wire frame:

| Firmware | Wire frame | Tail handling |
|---|---|---|
| 1.06 | **137 bytes** (F7 at idx 136) | Whole vector in one frame |
| 3.00 | **127 bytes** (F7 at idx 126) | `OUT_PHONES R` and `OUT_LINE` are trimmed off the end and sent in a **continuation frame** (`sec=0x01 type=0x10 addr_hi=0x70`) each tick — see below |

Slot offsets are **identical** on both firmwares up to the trim point; the 3.00 frame simply ends
earlier. `device/constants/channel.py` defines `METER_FRAME_LEN = 127` and the per-slot indices.

### Streaming input slots (abs idx 45–68)

| Slot | Abs idx | Channel |
|---|---|---|
| 0 | 45–48 | MIC → Stream (L=R, mono) |
| 1 | 49–52 | AUX → Stream |
| 2 | 53–56 | CHAT → Stream |
| 3 | 57–60 | GAME → Stream |
| 4 | 61–64 | MUSIC → Stream |
| 5 | 65–68 | SYSTEM → Stream |

### Personal input slots (abs idx 69–108)

| Slot | Abs idx | Channel | Notes |
|---|---|---|---|
| 6 | 69–72 | SFX → Personal | Always active |
| 7 | 73–76 | *(unknown)* | Always zero |
| 8 | 77–80 | MIC → Personal | L=R mono |
| 9 | 81–84 | AUX → Personal | |
| 10 | 85–88 | CHAT → Personal | |
| 11 | 89–92 | GAME → Personal | |
| 12 | 93–96 | MUSIC → Personal | |
| 13 | 97–100 | SYSTEM → Personal | |
| 14 | 101–104 | *(unknown)* | |
| 15 | 105–108 | *(unknown)* | |

### Output block (abs idx 109–130)

| Abs idx | Function | Format | On FW 3.00 |
|---|---|---|---|
| 109–110 | **Raw/direct mic** (pre-bus, pre-mute) | 2-byte mono: `(hi << 7) \| lo` | main frame |
| 111–114 | **STREAM MIX Output** | L_hi L_lo R_hi R_lo | main frame |
| 115–118 | **SUB MIX Output** | L_hi L_lo R_hi R_lo | main frame |
| 119–122 | *(unknown — mirrors OUT_STREAM in some device states)* | | main frame |
| 123–126 | **PHONES Output** | L_hi L_lo R_hi R_lo | **L only** in main frame; R from continuation |
| 127–130 | **LINE OUT Output** | L_hi L_lo R_hi R_lo | **continuation frame** |

On FW 1.06 the PHONES R and LINE OUT slots are present in the main 137-byte frame (idx 123–130;
padding 131–135; F7 at 136).

### FW 3.00 continuation frame (`sec=0x01 type=0x10 addr_hi=0x70`)

Carries the tail trimmed from the 127-byte main frame, decoded on the same tick:

| Field | Meaning |
|---|---|
| `addr_lo` | `OUT_PHONES R` hi byte |
| `payload[0]` | `OUT_PHONES R` lo byte |
| `payload[1..2]` | `OUT_LINE L` (hi, lo) |
| `payload[3..4]` | `OUT_LINE R` (hi, lo) |

---

## Official CC Protocol (Parallel Control Path)

Channel assignments (1-based): ch1=Mic, ch2=Aux, ch3=Chat, ch4=Game, ch5=Music, ch6=System, ch7=SFX.

| CC | Function | Values | SysEx equivalent |
|---|---|---|---|
| 0 | Mic FX SW | 0=off, 127=on | `ADDR_MIC_FX_ENABLE` (TYPE_SWITCH 0x30) |
| 1 | Mic FX preset | 0–4 | `ADDR_VOICE_FX_PRESET` (sec=0x7F type=0x7F addr=0x02) |
| 2 | Reverb SW | 0=off, 127=on | `ADDR_REVERB_SWITCH` (TYPE_VOICE 0x40) |
| 5 | Game EQ SW | 0=off, 127=on | `ADDR_GAME_EQ_ENABLE` (TYPE_GAME_FX 0x20) |
| 6 | Game EQ preset | 0–4 | `ADDR_GAME_EQ_PRESET` (TYPE_SWITCH 0x34) |
| 7 | Chat De-esser SW | 0=off, 127=on | `ADDR_CHAT_DE_ESSER` (TYPE_CHAT_FX 0x00) |
| 8 | Chat Compressor SW | 0=off, 127=on | `ADDR_CHAT_COMPRESSOR` (TYPE_CHAT_FX 0x10) |
| 9 | Output Delay SW | 0=off, 127=on | `ADDR_OUTPUT_DELAY_SW` (TYPE_DELAY 0x00) |
| 10 | Profile change | 0–4 | `ADDR_ACTIVE_PROFILE` (SECTION_GLOBAL TYPE_SWITCH 0x00) |
| 11 | SFX A trigger | 127=on | SysEx addr unknown |
| 12 | SFX B trigger | 127=on | SysEx addr unknown |
| 13 | Beep | 0=off, 127=on | SysEx addr unknown |
| 14 | Mute Stream Out | 0=off, 127=on | `ADDR_MUTE_STREAM_OUT` (TYPE_FADER 0x60) |
| 15 | Mute Line Out | 0=off, 127=on | `ADDR_MUTE_LINE_OUT` (TYPE_FADER 0x68) |
| 16 | Mute Phones | 0=off, 127=on | `ADDR_MUTE_PHONES_OUT` (TYPE_FADER 0x66) |
| 17 | Mute All Outputs | 0=off, 127=on | Composite of CC 14–16 |
| 18 | Ch. Mute → Stream | 0=off, 127=on | `ST_MUTE_ALL_SOURCES` |
| 19 | Ch. Mute → Personal | 0=off, 127=on | `PS_MUTE_ALL_SOURCES` |
| 20 | Ch. Mute → Mic | 0=off, 127=on | `ADDR_MIC_DIRECT_MUTE` (0x64) |
| 21 | Ch. Mute → All | 0=off, 127=on | Composite |
| 22 | Stream Mix Level | 0–127 | `ADDR_ST_*_VOL` |
| 23 | Personal Mix Level | 0–127 | `ADDR_PS_*_VOL` |
| 24 | Mic Level (direct) | 0–127 | `ADDR_MIC_DIRECT_VOL` (0x54) |

---

## Notes & Gotchas

- **`ADDR_LO` is meaningful.** The Mix-Link burst uses `ADDR_LO = 0x01` for the Stream-side bus, and VSurround angles >127° set `ADDR_LO = 0x01`. Always log both `ADDR_HI` and `ADDR_LO`.

- **The type byte resolves address collisions.** `0x22` = Mic Gain XLR (`TYPE_SWITCH`) OR Voice Formant (`TYPE_VOICE`). `0x26` = Mic Phantom (`TYPE_SWITCH`) OR Stream Game Mute (`TYPE_FADER`). `0x46` = Mic Knob Target (`TYPE_SWITCH`) OR Mic EQ Band4 Q (`TYPE_MIC_FX`). `0x64` = Mic Direct Mute (`TYPE_FADER`) OR Mic EQ Band9 Q (`TYPE_MIC_FX`). Always check the type byte.

- **Game volume is at `0x16`, not `0x1C`.** Some community sources list Game volume at `0x1C`, which is actually `ADDR_PS_SFX_VOL`. Verify against live capture.

- **RQ1 bulk reads work.** The device responds to RQ1 (`cmd=0x11`) bulk reads with DT1 (`cmd=0x12`) bulk payloads for the correct section/type/size tuple; this is how `_sync_all_parameters` reads device state on connect. Individual single-address RQ1 reads are untested.

- **Mix Link does NOT unify values.** Each bus keeps its own absolute level. To drive a linked pair from the host, write both `ADDR_PS_*_VOL` and `ADDR_ST_*_VOL`.

- **`ADDR_PS_MIC_MUTE_MIRROR` (`0x64`, TYPE_FADER)** fires autonomously from the device whenever `ps_mic_mute` (0x30) changes. Does NOT fire for Aux/Chat/Game or Stream-bus mutes. Matches CC 20 ("CH. MUTE TO MIC").

- **`ADDR_MIC_DIRECT_VOL` (`0x54`, TYPE_FADER)** is the un-bussed mic feed. Tracks Mic volume in lock-step when Mix Link is ON. Corresponds to CC 24 ("MIC LEVEL").

- **Sections 0x20–0x24 are per-profile slots.** Each maps to a section byte 0x20–0x24. The device auto-emits per-profile dumps for all type blocks during sync without explicit per-profile RQ1 requests.

- **Active profile index** is at `SECTION_GLOBAL TYPE_SWITCH addr=0x00`. Values 0x00–0x04 map to profiles 1–5. Writing this address switches the active profile.

- **Profile names** occupy addr `0x00`–`0x11` of the TYPE_SWITCH block in SECTION_PROFILE_* (sec=`0x20`–`0x24`). Encoding is 7-bit ASCII, two chars per DT1 frame — **not UTF-16LE**. In read-back frames, `addr_lo` is the ASCII value of `char[1]` (the odd-position char), not a memory offset; the name always lives at addr `0x00`.

- **RX Enable/Disable (`SECTION_STATUS type=0x10 addr=0x10`).** Writing `0x01` registers the app as an active listener; writing `0x00` silences the device. **Warning:** if RX dies after a bad DT1 write into `SECTION_STATUS`, do a factory reset via the official app — a power-cycle alone may not clear the latched state.
