#!/usr/bin/env python3
# Copyright 2026 Maciekbac
# https://github.com/Maciekbac
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
#     Unless required by applicable law or agreed to in writing, software
#     distributed under the License is distributed on an "AS IS" BASIS,
#     WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#     See the License for the specific language governing permissions and
#     limitations under the License.
#
# Temp 433 read-only assets: the screen texts, the timing families and the
# protocol table.
#
#   ./gen_assets.py temp433_assets.bin temp433_assets.h
# Uses app_assets.py of the F4HWN app SDK (the folder in $SDK, set by build.sh).
#
# Frame layouts (bit positions, timings, checks) follow the protocol
# descriptions in the rtl_433 device sources, used as a specification only:
# the decoder is written from them, no code is taken.  Bit positions count
# from the first data bit (after `skip` leading bits), MSB first; times are in
# PA4 samples of 50 us.
import os, struct, sys
sys.dont_write_bytecode = True
sys.path.insert(0, os.environ.get("SDK", "sdk"))
from app_assets import Assets

US = 50
def s(us):
    return round(us / US)

DIAG = os.environ.get("DIAG") == "1"

# The screen texts, each padded to a multiple of 4 bytes: draw() reads them in
# one asset_read into a word-aligned stack block.  The DIAG build keeps the
# diagnostic screen of stage 1, the release build has the sensor table.
UI = [
    ("T_TITLE",  "TEMP 433 DIAG" if DIAG else "TEMP 433"),
    ("T_AUTO",   "AUTO "),
    ("T_VFO",    "VFO "),
    ("T_OK",     " ok "),
    ("T_UNKNOWN", " ?"),
    ("T_DBM",    "dBm"),
    ("T_VHF1",   "No 433 sensors on VHF"),
    ("T_VHF2",   "Tune the VFO to 433.920"),
]
if DIAG:
    UI += [
        ("T_HIGH",   " High 6dB"),
        ("T_NORMAL", " Normal 10dB"),
        ("T_LOW",    " Low 15dB"),
        ("T_T",      "t "),
        ("T_STOPS",  "s stops "),
        ("T_EMPTY",  " empty "),
        ("T_PACKETS", "packets "),
        ("T_NOISE",  "noise "),
        ("T_ID",     " id "),
        ("T_CH",     " ch"),
        ("T_BAT",    " bat low"),
        ("T_NONE",   "no sensor yet"),
        ("T_AGE",    "age "),
        ("T_KEYS",   "s 1spk 2clr 3sens 5mode"),
    ]
else:
    UI += [("T_HINT", "5: search 433.80-434.04 (AUTO)")]   # VFO, empty table

# Status line icons, vertical bytes, bit 0 at the top.  The speaker and the
# scroll marks are the bitmaps of the F4HWN apps (FoxHunt, AIS RX; Apache-2.0,
# see NOTICE), laid out as AIS RX does: 8 variants of an 18-byte tail (bit 0
# speaker, bit 1 more rows above, bit 2 more rows below), read in one go.
BARS = [[0x40, 0x40, 0, 0x70, 0x70, 0, 0x7C, 0x7C],    # High: 3 bars
        [0x40, 0x40, 0, 0x70, 0x70, 0, 0x40, 0x40],    # Normal: 2
        [0x40, 0x40, 0, 0x40, 0x40, 0, 0x40, 0x40]]    # Low: 1
SPK = [0x1C, 0x1C, 0x3E, 0x7F, 0x00, 0x22, 0x1C, 0x41, 0x22, 0x1C]
UP = [0x04, 0x06, 0x07, 0x06, 0x04]
DN = [0x10, 0x30, 0x70, 0x30, 0x10]
tails = b""
for index in range(8):
    tail = (SPK if index & 1 else [0] * 10) + [0] * 3
    tail += [(u if index & 2 else 0) | (d if index & 4 else 0) for u, d in zip(UP, DN)]
    tails += bytes(tail)

PPM = 0
# (name, kind, bit threshold, row gap, sync pulse (PWM), glitch run, pulse,
# longest pulse) + a pad byte (8 B: i * 8 is a shift): kind and sync are not
# read yet (PWM, stage 3).
# A pulse longer than the longest is noise that switched the comparator on
# early in the gap before it (radio log 2026-10-29): its excess goes back to
# that gap.  255: off (PWM, where the pulse is the bit).
FAMILIES = [
    ("PPM 1000/2000", PPM, s(1500), s(3000), 0, 3, s(500), s(800)),   # Rubicson, Nexus: gaps 1000/2000, sync 4000
    ("PPM 2000/4000", PPM, s(3100), s(6500), 0, 3, s(500), s(800)),   # GT-WT-02, Prologue: gaps 2000/4000, sync ~9000
]

# checks
C_NONE, C_NIBSUM, C_CRC8 = range(3)
# temperature encodings (x0.1 C on the screen)
T_S12 = 1
# humidity: its length in bits (0: none)
H_NONE, H_U7, H_U8 = 0, 7, 8
F_CH1, F_BATOK = 1, 2            # channel shown +1; battery bit 1 = OK (else 1 = low)

# name (<= 9 chars), family, bits min/max (with skip), skip, flags, check, c1 c2 c3, repeats,
# fixed (pos, len, value), id (pos, len), channel (pos, len), battery bit, temp (pos, enc), hum (pos, bits)
P = []
def proto(name, fam, bits, skip, flags, check, c, reps, fixed, ident, ch, bat, temp, hum):
    P.append((name, fam, bits, skip, flags, check, c, reps, fixed, ident, ch, bat, temp, hum))

# Within a family the protocols with a check come first: Nexus and Prologue
# have none, so a Rubicson frame would pass as Nexus and a GT-WT-02 frame
# (37 bits) as Prologue if they were tried before.
# PPM 1000/2000
proto("RUBICSON", 0, (36, 38), 0, F_CH1 | F_BATOK, C_CRC8, (28, 0x31, 0x6C), 1,
      (24, 4, 0xF), (0, 8), (10, 2), 8, (12, T_S12), (0, H_NONE))           # + TFA 30.3197, inFactory PT-310
proto("NEXUS", 0, (36, 37), 0, F_CH1 | F_BATOK, C_NONE, (0, 0, 0), 2,
      (24, 4, 0xF), (0, 8), (10, 2), 8, (12, T_S12), (28, H_U8))            # + Sencor, Solight, FreeTec, TFA 30.3209
# PPM 2000/4000
proto("GT-WT-02", 1, (37, 37), 0, F_CH1, C_NIBSUM, (31, 6, 0), 1,
      None, (0, 8), (10, 2), 8, (12, T_S12), (24, H_U7))                    # Aldi Globaltronics
proto("GT-WT-02", 1, (39, 39), 2, F_CH1, C_NIBSUM, (31, 6, 0), 1,
      None, (0, 8), (10, 2), 8, (12, T_S12), (24, H_U7))                    # Lidl AURIO YJ-T12: 2 extra bits
proto("PROLOGUE", 1, (36, 37), 0, F_CH1 | F_BATOK, C_NONE, (0, 0, 0), 2,
      (2, 2, 0x1), (4, 8), (14, 2), 12, (16, T_S12), (28, H_U8))            # type 9/5; + ThermoPro TX2

assert len(P) <= 16
fam_blob = b"".join(struct.pack("<8B", kind, thr, gap, sync, glitch, pulse, pmax, 0)
                    for (_, kind, thr, gap, sync, glitch, pulse, pmax) in FAMILIES)
proto_blob = b""
for (name, fam, (bmin, bmax), skip, flags, check, (c1, c2, c3), reps, fixed, ident, ch, bat, temp, hum) in P:
    fp, fl, fv = fixed or (0, 0, 0)
    assert all(0 <= v < 256 for v in (bmin, bmax, skip, c1, c2, c3, fp, fl, bat)) and bmax <= 127 and fl <= 16
    proto_blob += struct.pack("<24B", fam, bmin, bmax, skip, flags, check, c1, c2, c3, reps,
                              fp, fl, fv >> 8, fv & 0xFF, ident[0], ident[1], ch[0], ch[1], bat,
                              temp[0], temp[1], hum[0], hum[1], 0)

a = Assets("TEMP433")
ui_size = 0
for name, text in UI:
    pad = -(len(text) + 1) % 4                 # keeps every offset word-aligned
    a.text(name, text + "\0" * pad)
    ui_size += len(text) + 1 + pad
a.const("UI_SIZE", ui_size)
a.const("T_TITLE_CHARS", len(UI[0][1]))
a.table("T_NAME", [p[0] for p in P])
a.raw("FAMS", fam_blob)
a.const("FAM_SIZE", 8)
a.const("FAM_COUNT", len(FAMILIES))
a.raw("PROTOS", proto_blob)
a.const("PROTO_SIZE", 24)
a.const("PROTO_COUNT", len(P))
if not DIAG:
    a.raw("BMP_BARS", b"".join(bytes(v) for v in BARS))
    a.const("BARS_W", len(BARS[0]))
    a.raw("BMP_TAIL", tails)
    a.const("TAIL_W", 18)
a.main()
