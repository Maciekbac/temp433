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
# from the first data bit (after `skip` leading bits; the fixed bits from the
# row start), MSB first; times are in PA4 samples of 50 us.
import os, struct, sys
sys.dont_write_bytecode = True
sys.path.insert(0, os.environ.get("SDK", "sdk"))
from app_assets import Assets

US = 50
def s(us):
    return round(us / US)
def mid(a_us, b_us):
    """bit threshold between two times: a run longer than it is the long one"""
    return (a_us + b_us) // (2 * US)

# The screen texts, each padded to a multiple of 4 bytes: draw() reads them in
# one asset_read into a word-aligned stack block.
RANGE = "433.80-434.04"          # AUTO: F_FIRST and N_PTS in temp433_app.c
UI = [
    ("T_TITLE",  "TEMP 433"),
    ("T_AUTO",   "AUTO "),
    ("T_VFO",    "VFO "),
    ("T_RANGE",  RANGE),                                  # AUTO, bottom line
    ("T_DBM",    "dBm"),
    ("T_VHF1",   "No 433 sensors on VHF"),
    ("T_VHF2",   "Tune the VFO to 433.920"),
    ("T_HINT",   "5: search " + RANGE + " (AUTO)"),       # VFO, empty table
]
NAME_W = 10                      # model names, space padded: table columns 0-9

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

# The trend arrows of the bottom line, rows 3-5 of the frame buffer line it
# is printed on (the text there: rows 2-6).
TREND = [[0x20, 0x30, 0x38, 0x30, 0x20],    # up
         [0x08, 0x18, 0x38, 0x18, 0x08]]    # down

# ---- timing families ----------------------------------------------------------
# (name, kind, bit threshold, brk, end, glitch run, pulse, longest pulse) + a
# pad byte (8 B: i * 8 is a shift).
#   PPM (kind 0): the gap after a pulse is the bit; a gap longer than brk ends
#     the row (end 255: unused).  A pulse longer than pmax is noise that
#     switched the comparator on early in the gap before it (radio log
#     2026-10-29): its excess goes back to that gap.
#   PWM (kind 1: a long pulse is 1, as the rtl_433 decoders of these sensors
#     read them after inverting): a pulse longer than brk is a sync pulse and
#     ends the row, a gap longer than end ends it after its bit; pmax 255
#     (off).  One family per timing, the thresholds halfway (a shared one left
#     too little margin, e.g. the HG02832 long pulse of 612 us against the
#     Bresser sync pulse of 750 us).
PPM, PWM = 0, 1
FAMILIES = [
    ("PPM 1000/2000", PPM, s(1500), s(3000), 255, 3, s(500), s(800)),   # Rubicson, Nexus: sync 4000
    ("PPM 2000/4000", PPM, s(3100), s(6500), 255, 3, s(500), s(800)),   # AHFL 2100/4150, GT-WT-02 2500/5000: sync >= 8000
    ("PPM 576/1536",  PPM, s(1050), s(2000), 255, 3, s(500), s(800)),   # AFW2A1: sync 3900
    ("PWM 208/417",   PWM, mid(208, 417), mid(417, 833), s(1000), 2, 0, 255),   # TX141TH: sync 833
    ("PWM 250/500",   PWM, mid(250, 500), mid(500, 750), s(1000), 2, 0, 255),   # Bresser 3CH: sync 750
    ("PWM 252/612",   PWM, mid(252, 612), mid(612, 860), s(1000), 2, 0, 255),   # HG02832: sync 860
    ("PWM 280/796",   PWM, mid(280, 796), mid(796, 1836), s(1200), 2, 0, 255),  # EMOS: sync 1836, gaps <= 796
]

# ---- checks -------------------------------------------------------------------
# (kind, ca, cb, cc, per8, sub): check() in temp433_app.c runs one loop for
# both kinds, x from cb, x += key (C_SUM) or x ^= key (C_DIGEST) for every 1
# of the first c1 bits, the key from ca stepped back after each bit as an
# LFSR with cc; per8: the key starts over every 8 bits; nibble `sub` read from
# bits 36-39 (NO_SUB: none).
C_NONE, C_SUM, C_DIGEST = range(3)
NO_SUB = 0xFF

# The nibbles (bytes) of the first c1 bits, the last one zero padded: the key
# 8 4 2 1 8 ... (128 64 .. 1 128 ...) is each bit's weight in its unit.
NIBBLE_SUM = (C_SUM, 8, 0, 8, 0, NO_SUB)
BYTE_SUM = (C_SUM, 128, 0, 128, 0, NO_SUB)

def _step(k, poly, w):
    top, mask = 1 << (w - 1), (1 << w) - 1
    return ((k << 1) ^ poly) & mask if k & top else (k << 1) & mask

def crc_digest(poly, w, length, init=0, per8=False, sub=NO_SUB):
    """C_DIGEST constants of a CRC (MSB first, no reflection, no final XOR) of
    width w over `length` message bits: the start key is the CRC that bit 0
    alone leaves, x starts as the init pushed through `length` zero bits, and
    the key steps back with (poly >> 1) | top bit (poly must be odd)."""
    assert poly & 1
    key = poly
    for _ in range(length - 1):
        key = _step(key, poly, w)
    x0 = init
    for _ in range(length):
        x0 = _step(x0, poly, w)
    return (C_DIGEST, key, x0, (poly >> 1) | (1 << (w - 1)), int(per8), sub)

def lfsr_digest(gen, key, length):
    """C_DIGEST constants of an LFSR digest that takes the bits last to first
    (bytes last to first, bits LSB first) with the key stepped left: run first
    to last, the key starts where that one ends and steps back"""
    for _ in range(length - 1):
        key = _step(key, gen, 8)
    return (C_DIGEST, key, 0, (gen >> 1) | 0x80, 0, NO_SUB)

# temperature: t_fl flags, t_off x 10 below 0 C (0.1 C) or below 32 F (0.1 F)
T_SIGNED, T_F = 1, 8
S12 = (T_SIGNED, 0)
F900 = (T_F, 122)                # 0.1 F + 900, i.e. 1220 below 32 F
F_CH1, F_BATOK, F_HBCD = 1, 2, 8
F_HREJ, F_CHNZ = 16, 32           # rtl_433 drops a frame with a humidity over 100 % / channel 0

# name (<= 9 chars), family, bits min/max, skip, flags, repeats,
# check (kind, ca, cb, cc, per8, sub) with c1 (bits checked), cpos and cw (the check field),
# fixed (pos, len, value) from the row start, id (pos, len), channel (pos, len),
# battery bit, temp (pos, flags, offset), hum (pos, bits)
P = []
def proto(name, fam, bits, skip, flags, reps, check, c, fixed, ident, ch, bat, temp, hum):
    P.append((name, fam, bits, skip, flags, reps, check, c, fixed, ident, ch, bat, temp, hum))

NOCHECK = (C_NONE, 0, 0, 0, 0, NO_SUB)
# Within a family the protocols with a check come first (the no-check Nexus,
# Prologue and AFW2A1 would otherwise take their frames), the stronger checks
# before the weaker ones.
# PPM 1000/2000
proto("RUBICSON", 0, (36, 38), 0, F_CH1 | F_BATOK, 1, crc_digest(0x31, 8, 32, 0x6C), (28, 28, 8),
      (24, 4, 0xF), (0, 8), (10, 2), 8, (12,) + S12, (0, 0))      # + Solight TE44, TFA 30.3197, inFactory PT-310
proto("NEXUS", 0, (36, 37), 0, F_CH1 | F_BATOK | F_HREJ, 2, NOCHECK, (0, 0, 0),
      (24, 4, 0xF), (0, 8), (10, 2), 8, (12,) + S12, (28, 8))     # + Sencor, Solight TE82S, FreeTec, TFA 30.3209
# PPM 2000/4000
proto("AUR-AHFL", 1, (42, 42), 0, F_CH1 | F_BATOK, 1, NIBBLE_SUM, (36, 36, 6),
      (31, 5, 0x04), (0, 8), (10, 2), 8, (12,) + S12, (24, 7))     # Lidl Auriol AHFL 433B2
proto("INFACTORY", 1, (40, 42), 0, F_HBCD | F_HREJ | F_CHNZ, 2, crc_digest(0x3, 4, 32, sub=2), (36, 8, 4),
      None, (0, 8), (38, 2), 13, (16,) + F900, (28, 8))            # + nor-tec, FreeTec NC-3982;
                                                                   # its CRC-4 0x13 is 0x3 in 4 bits
proto("GT-WT-02", 1, (37, 37), 0, F_CH1, 1, NIBBLE_SUM, (31, 31, 6),
      None, (0, 8), (10, 2), 8, (12,) + S12, (24, 7))              # Aldi Globaltronics
proto("GT-WT-02", 1, (39, 39), 2, F_CH1, 1, NIBBLE_SUM, (31, 31, 6),
      None, (0, 8), (10, 2), 8, (12,) + S12, (24, 7))              # Lidl AURIO YJ-T12: 2 extra bits
proto("PROLOGUE", 1, (36, 37), 0, F_CH1 | F_BATOK, 2, NOCHECK, (0, 0, 0),
      (2, 2, 0x1), (4, 8), (14, 2), 12, (16,) + S12, (28, 8))      # type 9/5; + ThermoPro TX2
# PPM 576/1536
proto("AUR-AFW2", 2, (36, 37), 0, F_CH1 | F_BATOK | F_HREJ, 2, NOCHECK, (0, 0, 0),
      (24, 4, 0xA), (0, 8), (10, 2), 8, (12,) + S12, (28, 8))      # Lidl Auriol AFW 2 A1
# PWM
proto("TX141TH", 3, (40, 41), 0, F_HREJ, 1, lfsr_digest(0x31, 0xF4, 32), (32, 32, 8),
      None, (0, 8), (10, 2), 8, (12, 0, 50), (24, 8))              # La Crosse TX141TH-Bv2, TFA 30.3221
proto("BRESSER", 4, (40, 42), 0, F_HREJ | F_CHNZ, 1, BYTE_SUM, (32, 32, 8),
      None, (0, 8), (10, 2), 8, (12,) + F900, (24, 8))             # Bresser 3CH, Renkforce DM-7511
proto("AUR-HG02", 5, (40, 40), 0, F_CH1, 1, crc_digest(0x31, 8, 8, 0x53, per8=True), (32, 32, 8),
      None, (0, 8), (18, 2), 16, (20,) + S12, (8, 8))              # Lidl Auriol HG02832 / HG05124A
proto("EMOS", 6, (120, 120), 0, F_CH1 | F_BATOK, 1, BYTE_SUM, (104, 104, 8),
      (0, 16, 0xAAA5), (24, 8), (66, 2), 101, (68,) + S12, (80, 8))   # EMOS E6016 / E6018

assert len(P) <= 16

# ---- self-check of the check constants ------------------------------------------
# The CRCs and the LFSR digest as their sources define them, and the plain
# nibble and byte sums, against the loop of check() in temp433_app.c, on
# fixed pseudo-random frames.
def _bits(frame):
    return [(frame[i >> 3] >> (7 - (i & 7))) & 1 for i in range(8 * len(frame))]

def _field(b, pos, n):
    v = 0
    for i in range(n):
        v = v << 1 | b[pos + i]
    return v

def _check(check, c, b, skip):
    """check() in temp433_app.c"""
    kind, key0, x, gi, per8, sub = check
    c1, cpos, cw = c
    key = key0
    for pos in range(c1):
        q = 36 + (pos & 3) if (pos >> 2) == sub else pos
        if b[skip + q]:
            x = (x + key) & 0xFFFF if kind == C_SUM else x ^ key
        key = (key >> 1) ^ gi if key & 1 else key >> 1
        if per8 and (pos & 7) == 7:
            key = key0
    if kind == C_SUM and not x:
        return False
    return (x & ((1 << cw) - 1)) == _field(b, skip + cpos, cw)

def _sum(b, skip, c1, w):
    """the w-bit units of the first c1 bits added up, the last one zero padded"""
    return sum(_field(b, skip + pos, min(w, c1 - pos)) << (w - min(w, c1 - pos))
               for pos in range(0, c1, w))

def _crc(msg, poly, init, w):
    r = init << (8 - w)
    p = (poly << (8 - w)) & 0xFF
    for byte in msg:
        r ^= byte
        for _ in range(8):
            r = ((r << 1) ^ p) & 0xFF if r & 0x80 else (r << 1) & 0xFF
    return r >> (8 - w)

def _lfsr_reflect(msg, gen, key):
    s = 0
    for byte in reversed(msg):
        for i in range(8):
            if (byte >> i) & 1:
                s ^= key
            key = ((key << 1) ^ gen) & 0xFF if key & 0x80 else (key << 1) & 0xFF
    return s

seed = 0x1234567
for _ in range(64):
    m = []
    for _ in range(16):                   # EMOS: 120 bits
        seed = (seed * 1103515245 + 12345) & 0x7FFFFFFF
        m.append(seed >> 16 & 0xFF)
    for name, fam, _, skip, _, _, check, c, *_ in P:
        if check[0] == C_SUM:
            c1, cpos, cw = c
            b = _bits(m)
            s = _sum(b, skip, c1, check[1].bit_length())   # key 8: nibbles, 128: bytes
            for i in range(cw):
                b[skip + cpos + i] = s >> (cw - 1 - i) & 1
            assert _check(check, c, b, skip), name
            b[19] ^= 1                    # one bit off: the check must fail
            assert not _check(check, c, b, skip), name
            assert not _check(check, c, [0] * len(b), skip), name   # all zero
            continue
        if check[0] != C_DIGEST:
            continue
        f = list(m)
        if name == "RUBICSON":
            f[3] = (f[3] & 0xF0) | _crc([f[0], f[1], f[2], f[3] & 0xF0], 0x31, 0x6C, 8) >> 4
            f[4] = (_crc([f[0], f[1], f[2], f[3] & 0xF0], 0x31, 0x6C, 8) & 0xF) << 4 | (f[4] & 0xF)
        elif name == "INFACTORY":         # nibble 2 := channel nibble 9, CRC ^ nibble 8 = nibble 2
            mm = [f[0], (f[1] & 0x0F) | (f[4] & 0x0F) << 4, f[2], f[3]]
            f[1] = (f[1] & 0x0F) | ((_crc(mm, 0x3, 0, 4) ^ (f[4] >> 4)) & 0xF) << 4
        elif name == "TX141TH":
            f[4] = _lfsr_reflect(f[:4], 0x31, 0xF4)
        elif name == "AUR-HG02":
            f[4] = _crc([f[0] ^ f[1] ^ f[2] ^ f[3]], 0x31, 0x53, 8)
        assert _check(check, c, _bits(f), skip), name
        f[2] ^= 0x10                      # one bit off: the check must fail
        assert not _check(check, c, _bits(f), skip), name

fam_blob = b"".join(struct.pack("<8B", kind, thr, brk, end, glitch, pulse, pmax, 0)
                    for (_, kind, thr, brk, end, glitch, pulse, pmax) in FAMILIES)
proto_blob = b""
for (name, fam, (bmin, bmax), skip, flags, reps, (ck, ca, cb, cc, per8, sub), (c1, cpos, cw), fixed, ident, ch,
     bat, (tpos, tfl, toff), hum) in P:
    fp, fl, fv = fixed or (0, 0, 0)
    assert all(0 <= v < 256 for v in (bmin, bmax, skip, ca, cb, cc, sub, c1, cpos, cw, fp, fl, bat, toff))
    assert bmax <= 127 and fl <= 16 and cw <= 8 and len(name) < NAME_W
    assert sub == NO_SUB or 4 * sub + 4 <= c1          # the nibble is one of the checked
    proto_blob += struct.pack("<32B", fam, bmin, bmax, skip, flags, reps,
                              ck, c1, cpos, cw, ca, cb, cc, per8,
                              fp, fl, fv >> 8, fv & 0xFF,
                              ident[0], ident[1], ch[0], ch[1], bat,
                              tpos, tfl, toff, hum[0], hum[1], sub, 0, 0, 0)

a = Assets("TEMP433")
ui_size = 0
for name, text in UI:
    pad = -(len(text) + 1) % 4                 # keeps every offset word-aligned
    a.text(name, text + "\0" * pad)
    ui_size += len(text) + 1 + pad
a.const("UI_SIZE", ui_size)
a.const("T_TITLE_CHARS", len(UI[0][1]))
a.raw("T_NAME", b"".join(p[0].ljust(NAME_W).encode("ascii") for p in P))   # read into the row
a.const("T_NAME_STRIDE", NAME_W)
a.raw("FAMS", fam_blob)
a.const("FAM_SIZE", 8)
a.const("FAM_COUNT", len(FAMILIES))
a.raw("PROTOS", proto_blob)
a.const("PROTO_SIZE", 32)
a.const("PROTO_COUNT", len(P))
a.raw("BMP_BARS", b"".join(bytes(v) for v in BARS))
a.const("BARS_W", len(BARS[0]))
a.raw("BMP_TAIL", tails)
a.const("TAIL_W", 18)
a.raw("BMP_TREND", b"".join(bytes(v) for v in TREND))
a.const("TREND_W", len(TREND[0]))
a.main()
