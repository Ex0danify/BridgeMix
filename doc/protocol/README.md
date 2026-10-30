# Protocol dataset

`src/bridgemix/device/protocol/bridgecast.json` holds the facts about the device protocol that the
code needs: addresses, ranges, defaults, value tables, the connect and sync sequence, commands and
meters. `bridgemix.device.protocol.load()` reads it once and returns frozen records.

## Reading it

One record per line, so `grep` returns whole records:

```
grep 7f030178 bridgecast.json
grep mic_compressor_ratio bridgecast.json
```

Top-level sections:

| section | contents |
|---|---|
| `header` | format version, provenance, record counts |
| `models` | families, identity model byte, port name rules, USB IDs, firmware floors |
| `blocks` | every block once: word count, banks, families, bytes read on sync, purpose |
| `sync` | the full sync, as RQ1 reads in order |
| `poll` | the live poll, repeated every 50 ms |
| `connect` | connect sequence with its timeouts |
| `commands` | the 23 command slots at `7F/7F` |
| `meters` | meter words, with channel, bus and side |
| `meter_scale` | full scale and the 15 segment thresholds |
| `values` | display text tables, `value -> text` |
| `parameters` | one record per wire address |

## Addresses and values

An address is four bytes `7F SS TT AA`: section, type, index. The index is always even, since
every parameter is one 14-bit word: two bytes, seven bits each, MSB first. `block` is `SS/TT`.
Odd indices and unknown blocks have no record.

RQ1 sizes and sync sizes count bytes. A block of `words` words reads as `words * 2` bytes.

## Parameter fields

| field | meaning |
|---|---|
| `address` | eight hex digits, lower case |
| `block` | `SS/TT` |
| `memory` | `null` for live words, else `profile`, `mic_effect`, `game_effect` or `pad_set` |
| `bank` | memory slot 0 to 4 as on the wire (the official backup files count from 1), else `null` |
| `name` | repo name in snake_case, `null` if the word has no known meaning |
| `backup_key` | key of the word in the official backup files, `null` if it has none |
| `kind` | `switch`, `int`, `word`, `name`, `meter`, `null` for reserved |
| `min`, `max`, `default` | range and default |
| `max_by_family` | only where the maximum depends on the family |
| `families` | `bc`, `one`, `x`, or `null` if not known |
| `since_fw` | firmware per family that introduced the word, see below |
| `values` | key into `values` for the display text |
| `status` | `named`, `unnamed` or `reserved` |
| `evidence` | `verified`, `inferred` or `capture` |
| `alias_of` | address of the word this one shares its value with |
| `note` | free text for exceptions |

Names are unique per `(name, memory, bank)`. A copy of a word in a profile or effect memory has
the name of its live word. `load().lookup(name)` returns the live word,
`lookup(name, "profile", 2)` the copy in profile memory 2.

Pad head words are reachable from three addresses (for example `7f030a00`, `7f030b00`,
`7f030c00`). The first is the word, the others carry `alias_of`.

`reserved` words answer on the wire but have no function (range 0 to 0).

## Firmware

Firmware is written as `major * 100 + minor`, so 1.05 is `105`. Every family has its own
numbering, so `since_fw` is an object per family, for example `{"bc":200,"x":200,"one":101}`.

- A family missing from `since_fw` has the word since its floor (`models.fw_floor`).
- Every gate comes from the public firmware changelogs and stays `inferred`. Older firmware is
  not available to capture. Use `since_fw` to hide features and skip sync reads. Do not use it to
  block raw writes.
- Gates cover whole words. Features that add a value to an existing word are not covered.

`Param.available(family, fw)` applies the family and firmware gates.

## Known exceptions

- `*_eq_band10_freq` The official app starts at a default above the maximum clamp.
- `st_sfx_vol`, `ps_sfx_vol`: default 71 from a factory reset capture, the app starts at 100.
