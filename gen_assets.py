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

# The screen texts, read by draw() in one asset_read after the row.  The code
# reads T_RANGE and T_DBM as strings (with a NUL); the pieces cut the others
# by length, so they are packed with no NUL, each where its bytes already are
# when they are (see the UI block below).
RANGE = "433.80-434.04"          # AUTO: F_FIRST and N_PTS in temp433_app.c
UI_CODE = ("T_RANGE", "T_DBM")
UI = [
    ("T_TITLE",  "TEMP 433"),
    ("T_AUTO",   "AUTO "),
    ("T_VFO",    "VFO "),
    ("T_RANGE",  RANGE),                                  # AUTO, bottom line
    ("T_DBM",    "dBm"),
    ("T_VHF1",   "No 433 sensors on VHF"),
    ("T_VHF2",   "Tune the VFO to 433.920"),
    ("T_HINT",   "5: search " + RANGE + " (AUTO)"),       # VFO, empty table
    # the card (CARD below)
    ("T_CH",     "CH"),
    ("T_ID",     "ID"),
    ("T_DEG",    "o"),                                    # the 3x5 o, raised: a degree sign
    ("T_C",      "C"),
    ("T_MIN",    "MIN"),
    ("T_MAX",    "MAX"),
    ("T_EVERY",  "EVERY"),
    ("T_BOK",    "BATTERY OK"),
    ("T_BLOW",   "BATTERY LOW"),
    ("T_RX",     "RX"),
    ("T_LAST",   "LAST"),
]
NAME_W = 10                      # model names, space padded: table columns 0-9

# Status line icons, vertical bytes, bit 0 at the top.  The speaker and the
# scroll marks are the bitmaps of the F4HWN apps (FoxHunt, AIS RX; Apache-2.0,
# see NOTICE), laid out as AIS RX does: 8 variants of an 18-byte tail (bit 0
# speaker, bit 1 more rows above, bit 2 more rows below).  With the 3
# sensitivity bars in front (and the empty column 63 between) each of the 24
# combinations is one 27-byte block, read in one go to status line column 55.
BARS = [[0x40, 0x40, 0, 0x70, 0x70, 0, 0x7C, 0x7C],    # High: 3 bars
        [0x40, 0x40, 0, 0x70, 0x70, 0, 0x40, 0x40],    # Normal: 2
        [0x40, 0x40, 0, 0x40, 0x40, 0, 0x40, 0x40]]    # Low: 1
SPK = [0x1C, 0x1C, 0x3E, 0x7F, 0x00, 0x22, 0x1C, 0x41, 0x22, 0x1C]
UP = [0x04, 0x06, 0x07, 0x06, 0x04]
DN = [0x10, 0x30, 0x70, 0x30, 0x10]
status = b""
for bars in BARS:                  # sens * 8 + tail
    for index in range(8):
        tail = (SPK if index & 1 else [0] * 10) + [0] * 3
        tail += [(u if index & 2 else 0) | (d if index & 4 else 0) for u, d in zip(UP, DN)]
        status += bytes(bars + [0] + tail)
STATUS_W = 27
assert len(status) == 3 * 8 * STATUS_W

# The trend marks of the card, rows 2-4 of frame buffer line 1 (its text:
# rows 1-5), in the order draw() picks them by the sign of the change.
TREND = [[0x04, 0x0C, 0x1C, 0x0C, 0x04],    # down
         [0x14, 0x14, 0x14, 0x14, 0x14],    # no change: =
         [0x10, 0x18, 0x1C, 0x18, 0x10]]    # up

# The fixed texts of the screen and the card of the selected sensor (MENU),
# drawn by draw() in temp433_app.c: pieces of UI texts or of the table row,
# each drawn by an app_api_t service (its pointer index) with the arguments
# after the text, when (state & mask) == val.  The state bits: LOW / NOBAT
# (the card sensor's low: battery low, no battery state sent), CARD_ON, VHF,
# EMPTY (no sensor yet), AUTO.  Pieces of the row: ROW(column, length); its
# columns: 0-8 model, 10 channel, 12-14 ID, 16-20 temperature
# (right-aligned), 21 C, 23-25 humidity (right-aligned or --), 26 % (a space
# without humidity), 27-30 age, 32 its NUL; on the card the values draw()
# writes after it, left-aligned: COL(name) (see COLS).  x in pixels; the 3x5
# font by y from the frame buffer top (line l at 8 l; status: the status
# line), the others by line.  The big digits (display_freq) take 13 px a cell
# and 3 px the point, lines l and l + 1, a leading space an empty cell: the
# temperature always 55 px.
FN_BOLD, FN_TINY, FN_INV, FN_BIG, FN_BATT = 6, 7, 16, 17, 30
# print_bold(s, x, end, line), print_tiny(s, x, y, statusbar, fill), print_inverse(s, x, line,
# statusbar, fill, end_x), display_freq(s, x, line, center), draw_battery()
LOW, NOBAT, CARD_ON, VHF, EMPTY, AUTO, HELP = 1, 2, 4, 8, 16, 32, 64    # S_CARD, S_EMPTY, S_HELP in temp433_app.c
# the card's values (column, width): its place in the list ("3/12"),
# readings, the period, min, max, the trend (2 cells for its mark, then
# "0.3C/14m")
COLS = dict(C_POS=(33, 5), C_RX=(41, 3), C_EVERY=(44, 3),
            C_MIN=(50, 5), C_MAX=(55, 5), C_TD=(60, 12))
ROW_BUF = 72                           # draw(): the row and the values, then the UI block
assert max(c + n for c, n in COLS.values()) <= ROW_BUF and ROW_BUF % 4 == 0
def ROW(col, n):
    return (col, n)
def COL(name):
    return COLS[name]
def bold(text, x, line, cond=(CARD_ON, CARD_ON)):
    return (FN_BOLD, text, x, 0, line, 0, 0, cond)
def tiny(text, x, y, cond=(CARD_ON, CARD_ON), status=0):
    return (FN_TINY, text, x, y, status, 1, 0, cond)
def big(text, x, line):
    return (FN_BIG, text, x, line, 0, 0, 0, (CARD_ON, CARD_ON))
PIECES = [
    # the status line: [TEMP 433] AUTO (bars, speaker, marks: a bitmap) 78% [###]
    (FN_INV, "T_TITLE", 2, 0, 1, 1, 2 + 4 * 8, (0, 0)),     # the title capsule, 8 characters
    (FN_BATT, ROW(0, 1), 0, 0, 0, 0, 0, (0, 0)),            # the radio's battery (no text)
    tiny("T_AUTO", 37, 1, (AUTO, AUTO), 1), tiny("T_VFO", 37, 1, (AUTO, 0), 1),
    # on VHF only these two lines; in VFO with no sensor yet the hint to search
    # (1 px from the left edge, as the key help)
    tiny("T_VHF1", 1, 17, (VHF, VHF)), tiny("T_VHF2", 1, 25, (VHF, VHF)),
    tiny("T_HINT", 1, 17, (VHF | EMPTY | AUTO, EMPTY)),
    # the card:
    #   NEXUS            CH1 ID136 [3/12 ]  (the longest bold name ends at 63)
    #   v0.3C/14m  MIN -3.1  MAX 9.0         (the mark drawn by draw())
    #    -12.3oC               87 %          (big digits)
    #   EVERY 57s  LAST 18s  RX 42
    #   BATTERY OK                           (no battery state: none)
    bold(ROW(0, 9), 0, 0),
    tiny("T_CH", 66, 1), tiny(ROW(10, 1), 74, 1), tiny("T_ID", 82, 1), tiny(ROW(12, 3), 90, 1),
    (FN_INV, COL("C_POS"), 106, 0, 0, 1, 106 + 4 * 5, (CARD_ON, CARD_ON)),
    tiny(COL("C_TD"), 0, 9),
    tiny("T_MIN", 48, 9), tiny(COL("C_MIN"), 64, 9), tiny("T_MAX", 88, 9), tiny(COL("C_MAX"), 104, 9),
    big(ROW(16, 5), 0, 2),
    tiny("T_DEG", 57, 15), bold("T_C", 61, 2),
    big(ROW(23, 3), 76, 2), bold(ROW(26, 1), 116, 2),
    tiny("T_EVERY", 0, 33, (CARD_ON | 128, CARD_ON | 128)), tiny(COL("C_EVERY"), 24, 33),
    tiny("T_LAST", 44, 33), tiny(ROW(28, 3), 64, 33),
    tiny("T_RX", 84, 33), tiny(COL("C_RX"), 96, 33),
    tiny("T_BOK", 0, 41, (CARD_ON | NOBAT | LOW, CARD_ON)),
    tiny("T_BLOW", 0, 41, (CARD_ON | NOBAT | LOW, CARD_ON | LOW)),
]
# The key help, in table rows 3-5 while they are free (3 sensors or fewer,
# not the card), 1 px from the left edge.  Its texts are an asset of their
# own, which draw() reads into the row buffer then (a piece's src is one
# byte, and the UI texts fill the rest of draw()'s buffer): HLP(text) names a
# slice of it.
#   MENU details
#   1 speaker 2 clear 3 sensitivity
#   5 AUTO/VFO
HELP_TEXTS = ["MENU details", "1 speaker", "2 clear", "3 sensitivity", "5 AUTO/VFO"]
help_blob = "".join(HELP_TEXTS).encode("ascii")
assert len(help_blob) <= ROW_BUF
def HLP(text):
    return ("help", "".join(HELP_TEXTS).index(text), len(text))
PIECES += [
    tiny(HLP("MENU details"), 1, 25, (HELP, HELP)),
    tiny(HLP("1 speaker"), 1, 33, (HELP, HELP)), tiny(HLP("2 clear"), 41, 33, (HELP, HELP)),
    tiny(HLP("3 sensitivity"), 73, 33, (HELP, HELP)),
    tiny(HLP("5 AUTO/VFO"), 1, 41, (HELP, HELP)),
]
PIECE_SIZE = 10

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
#   PWM_SHORT1 (kind 3: a short pulse is 1, as rtl_433 reads La Crosse TX):
#     PWM with the bit inverted (emit() XORs it with kind >> 1); no sync
#     pulse (brk 255), a gap longer than end ends the row.
PPM, PWM, PWM_SHORT1 = 0, 1, 3
FAMILIES = [
    ("PPM 1000/2000", PPM, s(1500), s(3000), 255, 3, s(500), s(800)),   # Rubicson, Nexus: sync 4000
    ("PPM 2000/4000", PPM, s(3100), s(6500), 255, 3, s(500), s(800)),   # AHFL 2100/4150, GT-WT-02 2500/5000: sync >= 8000
    ("PPM 576/1536",  PPM, s(1050), s(2000), 255, 3, s(500), s(800)),   # AFW2A1: sync 3900
    ("PWM 208/417",   PWM, mid(208, 417), mid(417, 833), s(1000), 2, 0, 255),   # TX141TH: sync 833
    ("PWM 250/500",   PWM, mid(250, 500), mid(500, 750), s(1000), 2, 0, 255),   # Bresser 3CH: sync 750
    ("PWM 252/612",   PWM, mid(252, 612), mid(612, 860), s(1000), 2, 0, 255),   # HG02832: sync 860
    ("PWM 280/796",   PWM, mid(280, 796), mid(796, 1836), s(1200), 2, 0, 255),  # EMOS: sync 1836, gaps <= 796
    ("PWM 550/1400",  PWM_SHORT1, mid(550, 1400), 255, s(2000), 2, 0, 255),     # La Crosse TX: gap 1000, no sync
]

# ---- checks -------------------------------------------------------------------
# (kind, ca, cb, cc, cfl, sub): one loop for both kinds, x from cb, x += key
# (C_SUM) or x ^= key (C_DIGEST) for every 1 of the first c1 bits, the key
# from ca stepped back after each bit as an LFSR with cc; cfl bit 0: the key
# starts over every 8 bits, bit 3: the key is ca << 8 (pack() adds bits 6-7
# for F_LSB); nibble `sub` read from bits 36-39 (NO_SUB: none).  weights()
# runs that loop once here: check() in temp433_app.c only adds (XORs) the
# weight of each 1 bit, the key that loop gives it.
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

def lfsr_digest_fwd(gen, key):
    """C_DIGEST constants of an LFSR digest that takes the bits first to last,
    MSB first, the key stepped right with gen XORed in after a 1 dropped out:
    the loop of check() itself"""
    return (C_DIGEST, key, 0, gen, 0, NO_SUB)

# temperature: t_fl flags, t_off x 10 below 0 C (0.1 C) or below 32 F (0.1 F);
# pack() turns them into the t_off of temperature() in temp433_app.c
T_SIGNED, T_DEC, T_F = 1, 4, 8
T_LE = 2                          # the temperature nibbles last to first: pack() only (x 12)
S12 = (T_SIGNED, 0)
F900 = (T_F, 122)                # 0.1 F + 900, i.e. 1220 below 32 F
F_CH1, F_BATOK, F_HBCD = 1, 2, 8
F_HSWAP = 4                       # the humidity nibbles swapped: pack() only (x 4)
F_NOBAT = 4                       # after pack() (F_HSWAP's bit): no battery state sent (battery None)
F_HREJ, F_CHNZ = 16, 32           # rtl_433 drops a frame with a humidity over 100 % / channel 0
F_LSB = 64                        # the fields of 4 bits or more LSB first, the nibbles of the check too:
                                  # pack() only (x 3/7/15, cfl)
F_FIXNE = 128                     # the fixed bits must NOT hold the value

# name (<= 9 chars), family, bits min/max, skip, flags, repeats,
# check (kind, ca, cb, cc, cfl, sub) with c1 (bits checked), cpos and cw (the check field),
# fixed (pos, len, value) from the row start, id (pos, len), channel (pos, len),
# battery bit (None: none sent), temp (pos, flags, offset), hum (pos, bits[, offset subtracted])
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
# Esperanza, Kedsum and Conrad S3318P share this frame: 2 zero bits, then the
# CRC-4 of inFactory over bytes 0-3, XORed with nibble 32, in nibble 36 (c1 =
# 36: the digest of those 4 bits is the nibble itself); the temperature
# (0.1 F + 900) nibbles last to first, the humidity nibbles swapped.  F_HREJ beyond
# rtl_433, against the 42-bit frames of the other decoders here.  Before
# INFACTORY: a frame of either rarely passes the other's CRC.
proto("ESPERANZA", 1, (42, 42), 2, F_CH1 | F_HSWAP | F_HREJ, 2, crc_digest(0x3, 4, 32), (36, 36, 4),
      (0, 2, 0), (0, 8), (10, 2), 33, (12, T_LE | T_F, 122), (24, 8))   # + Kedsum, Conrad S3318P
# inFactory: exactly 40 bits, as rtl_433 takes them.  A noise pulse late in
# the 8 ms gap before the data adds a bit in front (41 bits, every field
# shifted), and the 42-bit frames of Vauno would read as other values here.
proto("INFACTORY", 1, (40, 40), 0, F_HBCD | F_HREJ | F_CHNZ, 2, crc_digest(0x3, 4, 32, sub=2), (36, 8, 4),
      None, (0, 8), (38, 2), 13, (16,) + F900, (28, 8))            # + nor-tec, FreeTec NC-3982;
                                                                   # its CRC-4 0x13 is 0x3 in 4 bits
proto("VAUNO", 1, (42, 44), 0, F_CH1, 2, NIBBLE_SUM, (36, 36, 6),
      None, (0, 8), (10, 2), 35, (12,) + S12, (24, 7))             # Vauno EN8822C, ESUN T21: 9 nibbles mod 64
# TX960: the digest of an all-zero row is 0, so a zero row (a PWM frame read
# as PPM) would pass; rtl_433 drops it too, here as 15 fixed bits that must
# not all be 0 (ID 0 with a low battery would go as well)
proto("TX960", 1, (32, 33), 0, F_CH1 | F_BATOK | F_FIXNE, 2, lfsr_digest_fwd(0x98, 0xF1), (24, 24, 8),
      (0, 15, 0), (0, 8), (10, 2), 8, (12,) + S12, (0, 0))         # Technoline TX960, Acurite 606TX
proto("ST1005H", 1, (38, 38), 1, F_CH1 | F_HREJ, 2, NIBBLE_SUM, (31, 31, 6),
      (0, 1, 0), (0, 8), (10, 2), 8, (12,) + S12, (24, 7))         # Bresser ST1005H / 3CH 7009984: a 0 first,
                                                                   # its sum leaves out the last data bit
proto("GT-WT-02", 1, (37, 37), 0, F_CH1, 1, NIBBLE_SUM, (31, 31, 6),
      None, (0, 8), (10, 2), 8, (12,) + S12, (24, 7))              # Aldi Globaltronics
proto("GT-WT-02", 1, (39, 39), 2, F_CH1, 1, NIBBLE_SUM, (31, 31, 6),
      None, (0, 8), (10, 2), 8, (12,) + S12, (24, 7))              # Lidl AURIO YJ-T12: 2 extra bits
# AlectoV1 sends its values LSB first (rtl_433 reverses each byte); its
# 2-bit channel is read as sent, as rtl_433 does.  Type 11 (bits 9-10) is
# wind or rain, whose wind messages pass the same check: F_FIXNE drops them.
# The check C = 0xF - (the sum of the 8 nibbles), LSB first: c1 = 36 takes C
# into the sum, so 1 + S + C = 16 when it holds, compared with bits 36-39,
# the zeros after the 36-bit row.  rtl_433: "prologue is also 36bits and
# sometimes detected as alecto", hence the humidity check, and before PROLOGUE.
proto("ALECTOV1", 1, (36, 36), 0, F_LSB | F_FIXNE | F_HBCD | F_HREJ, 2, (C_SUM, 8, 1, 8, 0, NO_SUB), (36, 36, 4),
      (9, 2, 0x3), (0, 8), (4, 2), 8, (12,) + S12, (24, 8))      # Alecto WS3500/WS4500, Ventus W044/W155
# TFA Twin Plus: LSB first as AlectoV1 (rtl_433 reverses each byte), the
# nibble sum of the reversed bytes 0-3 against the low nibble of reversed b4
# (bits 32-35 LSB first); humidity 7 bits - 28.  rtl_433's 6-bit ID leaves
# out the channel bits in the middle of byte 0: here the whole reversed byte
# 0 (the same sensors told apart, other numbers).  A negative temperature has
# its 3 top bits set (9 bits + sign in rtl_433), a 12-bit two's complement.
# Bit 31, after the humidity, is always 1 (rtl_433's layout HHHHHHH1, and
# both its examples).  After ALECTOV1, whose checks are stronger; its 4-bit
# sum lets about 1 of 16 Prologue frames through (the humidity check and
# bit 31 stop some).
proto("TFA-TWIN", 1, (36, 36), 0, F_LSB | F_HREJ, 2, NIBBLE_SUM, (32, 32, 4),
      (31, 1, 1), (0, 8), (4, 2), 8, (12,) + S12, (24, 7, 28))      # TFA 30.3049, Conrad KW9010, Ea2 BL999
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
# GT-WT-03: rtl_433's rollbyte, per byte the bits MSB first weighted by the
# low byte of 0x3100 shifted right (00 80 40 20 10 88 C4 62), XORed, ^ 0x2D;
# here a 16-bit key ca << 8 (cfl bit 3) with cc 0, restarted every byte
proto("GT-WT-03", 5, (41, 41), 0, F_CH1, 2, (C_DIGEST, 0x31, 0x2D, 0, 1 | 8, NO_SUB), (32, 32, 8),
      None, (0, 8), (18, 2), 16, (20,) + S12, (8, 8))              # Globaltronics GT-WT-03 (Aldi, Hofer)
proto("EMOS", 6, (120, 120), 0, F_CH1 | F_BATOK, 1, BYTE_SUM, (104, 104, 8),
      (1, 15, 0x2AA5), (24, 8), (66, 2), 101, (68,) + S12, (80, 8))   # EMOS E6016 / E6018 (preamble
                                                                   # 0xAAA5 less its first bit: 15-bit fields)

# PWM 550/1400 (a short pulse is 1, as rtl_433 reads it): La Crosse TX3 and
# kin, 11 nibbles 0 A type id(7) parity v1 v2 v3 v1 v2 sum; type 0 is the
# temperature (decimal, + 50 C); the humidity messages (type E) are left out
proto("LACROSSE", 7, (44, 44), 0, 0, 1, NIBBLE_SUM, (40, 40, 4),
      (0, 12, 0x0A0), (12, 7), (0, 0), None, (20, T_DEC, 50), (0, 0))   # La Crosse TX3/TX4/TX6U/TX7U: temperature

assert len(P) <= 24                 # an arbitrary bound: match() reads them all per family

# ---- the PROTOS record (proto_t in temp433_app.c, 32 B) --------------------------
# Positions from the row start: the skipped bits are added to every field but
# the fixed bits, and to the check field; the checked bits (c1, the csub
# nibble) count from the first data bit, check() adds the skip to them.
FIELDS = ("fix", "id", "ch", "bat", "t", "h")        # V_FIX .. V_H
V_T, V_H = 4, 5
ROW_BITS = 120                                       # ROW_BITS: the last of the 16 row bytes is its count

def weights(o, kind, name):
    """the check loop (o: its constants) run once: the weight check() in
    temp433_app.c adds (XORs) for a 1 at each data bit, 0 where the loop reads
    no bit.  Its low byte: the check field has at most 8 bits, a C_SUM key at
    most 128 (GT-WT-03's 16-bit key leaves the low byte to the field)"""
    k0 = o["ca"] << (o["cfl"] & 8)
    key, w = k0, {}
    for pos in range(o["c1"]):
        q = 36 + (pos & 3) if (pos >> 2) == o["csub"] else pos
        q ^= o["cfl"] >> 6
        assert q not in w and (kind != C_SUM or key < 256), name
        w[q] = key & 0xFF
        key = (key >> 1) ^ o["cc"] if key & 1 else key >> 1
        if o["cfl"] & 1 and (pos & 7) == 7:
            key = k0
    return bytes(w.get(q, 0) for q in range(max(w) + 1 if w else 0))

def pack(entry):
    (name, fam, (bmin, bmax), skip, flags, reps, (ck, ca, cb, cc, cfl, sub), (c1, cpos, cw), fixed, ident, ch,
     bat, (tpos, tfl, toff), hum) = entry
    fp, fl, fv = fixed or (0, 0, 0)
    fld = [(fp, fl), (ident[0] + skip, ident[1]), (ch[0] + skip, ch[1]), (0, 0) if bat is None else (bat + skip, 1), (tpos + skip, 12),
           (hum[0] + skip, hum[1])]
    fld = [(pos if n else 0, n) for pos, n in fld]
    r = dict(fam=fam, bmin=bmin, bmax=bmax, skip=skip, flags=flags, reps=reps, check=ck, c1=c1, cpos=cpos + skip,
             cw=cw, ca=ca, cb=cb, cc=cc, cfl=int(cfl), fld=fld, fix_v=fv, t_fl=tfl, t_off=toff, csub=sub,
             h_off=hum[2] if len(hum) > 2 else 0)
    assert all(0 <= v < 256 for k, v in r.items() if k not in ("fld", "fix_v")), name
    assert all(n <= 15 and pos + n <= ROW_BITS for pos, n in fld), name   # n: 4 bits of the length byte
    assert bmax <= ROW_BITS and cw <= 8 and r["cpos"] + cw <= ROW_BITS, name   # ROW_BITS + 1: longer
    assert skip + max(c1, 40 if sub != NO_SUB else 0) <= ROW_BITS, name
    assert 0 <= fv < 1 << fl and len(name) < NAME_W, name
    assert sub == NO_SUB or 4 * sub + 4 <= c1, name   # the nibble is one of the checked
    # Field order (bits(): bit i of a field is row bit pos + (i ^ x), the
    # length byte n | x << 4): LSB first, a window of 4, 8 or 16 bits ending at
    # the field's end read backwards; nibbles swapped (8 bits) or last to first
    # (12 bits, a 16-bit window from 4 bits before the field).
    def order(pos, n, lsb, x=0):
        if lsb and n >= 4:
            w = 4 if n <= 4 else 8 if n <= 8 else 16
            pos, x = pos - (w - n), w - 1
        assert pos >= 0 and pos + (x | (n - 1)) < ROW_BITS, name
        return pos, n | x << 4
    lsb = flags & F_LSB
    # check() XORs the bit index with 3 for F_LSB: right for the nibble sum
    # only (the weights 8 4 2 1 to bits 3..0); a byte sum or a CRC sent LSB
    # first would need another index order
    assert not lsb or (ck == C_SUM and ca == cc == 8), name
    r["fld"] = [order(pos, n, lsb) for pos, n in fld]
    if tfl & T_LE:
        r["fld"][V_T] = order(fld[V_T][0] - 4, 12, False, 12)
    if flags & F_HSWAP:
        assert fld[V_H][1] == 8, name
        r["fld"][V_H] = order(fld[V_H][0], 8, False, 4)
    r["cpos"], r["cw"] = order(r["cpos"], cw, lsb)
    if lsb:
        r["cfl"] |= 3 << 6            # the bit index XOR 3: the nibble weights reversed
    r["flags"] &= ~(F_LSB | F_HSWAP)  # the order is in the fields now
    r["t_fl"] &= ~T_LE
    if bat is None:                   # no battery bit: the card leaves the battery out
        r["flags"] |= F_NOBAT         # (the bit of F_HSWAP, cleared above: match() reads it)
    # check(): a weight per data bit (the loop's constants stay for the self-check)
    r["old"] = dict(c1=c1, ca=r.pop("ca"), cc=r.pop("cc"), cfl=r.pop("cfl"), csub=r.pop("csub"))
    r["keys"] = weights(r["old"], ck, name)
    r["c1"] = len(r["keys"])
    assert skip + r["c1"] <= ROW_BITS and r["c1"] < 256, name
    # temperature(): (t ^ T_SIGNED << 11) - t_off, so t_off is 2048 for two's
    # complement, else the offset x 10, and 720 less for F (the -40 F the
    # conversion rounds from)
    if tfl & T_SIGNED:
        assert not toff and not tfl & (T_DEC | T_F), name
        r["t_off"] = 2048
    else:
        r["t_off"] = toff * 10 - (720 if tfl & T_F else 0)
        assert 0 <= r["t_off"] < 1 << 16, name
    return r

def blob(r):
    return struct.pack("<12BH12BH2BH", r["fam"], r["bmin"], r["bmax"], r["skip"], r["flags"], r["reps"],
                       r["check"], r["c1"], r["cpos"], r["cw"], r["cb"], 0, r["ktab"],
                       *(v for f in r["fld"] for v in f), r["fix_v"], r["t_fl"], r["h_off"], r["t_off"])

RECORDS = [pack(e) for e in P]

# ---- self-check of the check constants ------------------------------------------
# The CRCs and the LFSR digest as their sources define them, and the plain
# nibble and byte sums, against the loop of check() in temp433_app.c, on
# fixed pseudo-random frames.
def _bits(frame):
    return [(frame[i >> 3] >> (7 - (i & 7))) & 1 for i in range(8 * len(frame))]

def _field(b, pos, n):
    """bits() in temp433_app.c: bit i of the field is b[pos + (i ^ x)], n = n | x << 4"""
    v = 0
    for i in range(n & 15):
        v = v << 1 | b[pos + (i ^ (n >> 4))]
    return v

def _x(r, b):
    """the x of check() in temp433_app.c: the weights of the 1 bits"""
    x = r["cb"]
    for pos in range(r["c1"]):
        if b[r["skip"] + pos]:
            x = (x + r["keys"][pos]) & 0xFFFF if r["check"] == C_SUM else x ^ r["keys"][pos]
    return x

def _x_old(r, b):
    """the x of check() up to v0.3, the loop itself (the reference for the weights)"""
    o = r["old"]
    k0 = o["ca"] << (o["cfl"] & 8)
    x, key = r["cb"], k0
    for pos in range(o["c1"]):
        q = 36 + (pos & 3) if (pos >> 2) == o["csub"] else pos
        q ^= o["cfl"] >> 6
        if b[r["skip"] + q]:
            x = (x + key) & 0xFFFF if r["check"] == C_SUM else x ^ key
        key = (key >> 1) ^ o["cc"] if key & 1 else key >> 1
        if o["cfl"] & 1 and (pos & 7) == 7:
            key = k0
    return x

def _check(r, b):
    """check() in temp433_app.c, on the packed record r"""
    x = _x(r, b)
    if r["check"] == C_SUM and not x:
        return False
    return (x & ((1 << (r["cw"] & 15)) - 1)) == _field(b, r["cpos"], r["cw"])

def _temp(r, t):
    """temperature() in temp433_app.c (C unsigned arithmetic, then int16)"""
    fl = r["t_fl"]
    if fl & T_DEC:
        t = t - 6 * (t >> 4) - 60 * (t >> 8)
    t = ((t ^ ((fl & T_SIGNED) << 11)) - r["t_off"]) & 0xFFFF
    if fl & T_F:
        t = ((t * 5 + 4) // 9 - 400) & 0xFFFF
    return t - 65536 if t >= 32768 else t

def _temp_old(tfl, toff, t):
    """temperature() up to v0.3 (the reference for _temp)"""
    if tfl & T_DEC:
        t = ((t >> 8) * 10 + ((t >> 4) & 15)) * 10 + (t & 15)
    if tfl & T_SIGNED:
        return t - 4096 if t & 0x800 else t
    t = (t - toff * 10) & 0xFFFF
    if tfl & T_F:
        t = ((((t + 720) & 0xFFFF) * 5 + 4) // 9 - 400) & 0xFFFF
    return t - 65536 if t >= 32768 else t

# the weights against the loop on random rows (x itself: all of a sum, the
# low byte of a digest, the most a check field has), the temperature on every
# 12-bit value (the field has 12 bits)
seed = 0x2468ACE
for _ in range(256):
    row = []
    for _ in range(ROW_BITS):
        seed = (seed * 1103515245 + 12345) & 0x7FFFFFFF
        row.append(seed >> 30 & 1)
    row += [0] * 8                        # the count byte reads as no bits
    for e, r in zip(P, RECORDS):
        mask = 0xFFFF if r["check"] == C_SUM else 0xFF
        assert (_x(r, row) ^ _x_old(r, row)) & mask == 0, e[0]
for (name, *_, (tpos, tfl, toff), hum), r in zip(P, RECORDS):
    assert all(_temp(r, t) == _temp_old(tfl & ~T_LE, toff, t) for t in range(4096)), name

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

def _rev(v, n):
    return int(format(v, f"0{n}b")[::-1], 2)

def _alecto(f):
    """AlectoV1 as rtl_433 describes it: the nibbles of the reversed bytes 0-3
    summed, C = 0xF - sum (rain: sum + 7), reversed into the high nibble of b4"""
    s = sum((_rev(v, 8) & 0xF) + (_rev(v, 8) >> 4) for v in f[:4])
    c = (s + 7) if (f[1] & 0x7F) == 0x6C else (0xF - s)
    return _rev(c & 0xF, 4) << 4

def _rollbyte(msg, gen):
    s = 0
    for byte in msg:
        key = gen
        for i in range(7, -1, -1):
            if (byte >> i) & 1:
                s ^= key & 0xFF
            key >>= 1
    return s

def _lfsr_fwd(msg, gen, key):
    s = 0
    for byte in msg:
        for i in range(7, -1, -1):
            if (byte >> i) & 1:
                s ^= key
            key = (key >> 1) ^ gen if key & 1 else key >> 1
    return s

seed = 0x1234567
for _ in range(64):
    m = []
    for _ in range(16):                   # EMOS: 120 bits
        seed = (seed * 1103515245 + 12345) & 0x7FFFFFFF
        m.append(seed >> 16 & 0xFF)
    for (name, fam, _, skip, _, _, check, c, *_), r in zip(P, RECORDS):
        if name == "TFA-TWIN":            # the nibbles of the reversed bytes, into reversed b4
            f = m[:4]
            s = sum((_rev(v, 8) & 0xF) + (_rev(v, 8) >> 4) for v in f) & 0xF
            b = _bits(f + [_rev(s, 8)])
            assert _check(r, b), name
            b[19] ^= 1
            assert not _check(r, b), name
            assert not _check(r, [0] * len(b)), name
            continue
        if name == "ALECTOV1":
            f = m[:4] + [_alecto(m[:4])]
            if (f[1] & 0x7F) == 0x6C:     # rain: + 7, and type 11 anyway
                continue
            b = _bits(f) + [0] * 8        # bits 36-39 and on: the zeros after the row
            b[36:40] = [0, 0, 0, 0]
            assert _check(r, b), name
            b[19] ^= 1                    # one bit off: the check must fail
            assert not _check(r, b), name
            assert not _check(r, [0] * len(b)), name   # all zero
            continue
        if check[0] == C_SUM:
            c1, cpos, cw = c
            b = _bits(m)
            s = _sum(b, skip, c1, check[1].bit_length())   # key 8: nibbles, 128: bytes
            for i in range(cw):
                b[skip + cpos + i] = s >> (cw - 1 - i) & 1
            assert _check(r, b), name
            b[19] ^= 1                    # one bit off: the check must fail
            assert not _check(r, b), name
            assert not _check(r, [0] * len(b)), name   # all zero
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
        elif name == "ESPERANZA":         # 2 leading bits, then 40: the CRC ^ nibble 32 = nibble 36
            d = [(f[k] << 2 | f[k + 1] >> 6) & 0xFF for k in range(4)]
            nib = (_crc(d, 0x3, 0, 4) ^ (f[4] >> 2 & 0xF)) & 0xF
            f[4] = (f[4] & 0xFC) | nib >> 2
            f[5] = (f[5] & 0x3F) | (nib & 3) << 6
        elif name == "GT-WT-03":
            f[4] = _rollbyte(f[:4], 0x3100) ^ 0x2D
        elif name == "TX960":
            f[3] = _lfsr_fwd(f[:3], 0x98, 0xF1)
        elif name == "AUR-HG02":
            f[4] = _crc([f[0] ^ f[1] ^ f[2] ^ f[3]], 0x31, 0x53, 8)
        assert _check(r, _bits(f)), name
        f[2] ^= 0x10                      # one bit off: the check must fail
        assert not _check(r, _bits(f)), name

fam_blob = b"".join(struct.pack("<8B", kind, thr, brk, end, glitch, pulse, pmax, 0)
                    for (_, kind, thr, brk, end, glitch, pulse, pmax) in FAMILIES)
trend_blob = b"".join(bytes(v) for v in TREND)
name_blob = b"".join(p[0].ljust(NAME_W).encode("ascii") for p in P)   # read into the row

a = Assets("TEMP433")
# The UI block, first in the assets: the texts the code reads (with a NUL),
# then the piece texts with none, longest first, each where its bytes already
# are when they are (dB in dBm): a piece's src is one byte, an offset into
# draw()'s buffer, and the row with the card's values takes 72 of its 256.
UIT = dict(UI)
assert set(UIT) == {p[1] for p in PIECES if isinstance(p[1], str)} | set(UI_CODE), "a UI text unused"
ui_blob, ui_at = b"", {}
for name in UI_CODE:
    ui_at[name] = len(ui_blob)
    ui_blob += UIT[name].encode("ascii") + b"\0"
for name in sorted(set(UIT) - set(UI_CODE), key=lambda n: -len(UIT[n])):
    t = UIT[name].encode("ascii")
    i = ui_blob.find(t)
    if i < 0:
        i, ui_blob = len(ui_blob), ui_blob + t
    ui_at[name] = i
a.prefix("UI", ui_blob)
for name in UI_CODE:
    a.const(name, ui_at[name])
ui_size = len(ui_blob)

# The piece list (PIECES, the last block): src is an offset into draw()'s
# buffer, the row (ROW_BUF bytes) and then the UI texts
def piece(fn, text, x, a1, a2, a3, a4, cond):
    if isinstance(text, str):
        src, n = ROW_BUF + ui_at[text], len(UIT[text])
    elif text[0] == "help":                     # the key help, read into the row buffer
        src, n = text[1:]
    else:
        src, n = text
        # the row's columns (the ! at 31 left out), or the card's values after its NUL
        assert src + n <= 31 or src > 32 and src + n <= ROW_BUF, text
    assert src + n < 256 and 0 < n and x < 128 and cond[1] & ~cond[0] == 0, text
    assert fn != FN_TINY or a2 or x + 4 * n - 1 <= 128, text      # the 3x5 font fits the screen
    return bytes((fn, src, n, x, a1, a2, a3, a4) + cond)
pieces_blob = b"".join(piece(*c) for c in PIECES) + b"\0"
assert all(len(piece(*c)) == PIECE_SIZE for c in PIECES)
a.const("UI_SIZE", ui_size)
a.const("ROW_BUF", ROW_BUF)
for name, (col, _) in COLS.items():
    a.const(name, col)
a.const("PIECE_SIZE", PIECE_SIZE)
for name in ("FN_BOLD", "FN_TINY", "FN_INV", "FN_BIG", "FN_BATT"):
    a.const(name, globals()[name])

# The check weights after the records, each table where its bytes already are
# when they are (the nibble sums share the start of one table): ktab is
# absolute, so the offset of the block is set from the sizes before it.
keys_at = ui_size + len(fam_blob) + len(trend_blob) + len(status) + len(name_blob) + 32 * len(P)
keys_blob = b""
for r in sorted(RECORDS, key=lambda r: -len(r["keys"])):
    i = keys_blob.find(r["keys"])
    if i < 0:
        i, keys_blob = len(keys_blob), keys_blob + r["keys"]
    r["ktab"] = keys_at + i
proto_blob = b"".join(blob(r) for r in RECORDS)
assert len(proto_blob) == 32 * len(P)

# The small blocks first, so as many offsets as fit stay below 256 (a movs in
# Thumb-1, a literal word above): the names start at 254, the status bitmaps
# (a new protocol moves them by 10, past 255 anyway) after them, the records,
# weights and the piece list last (measured: names after the bitmaps cost 4
# B; the card pieces after the texts 8 B less code, but 136 B more stack in
# draw(), which reads the texts and the row into one block).
a.raw("FAMS", fam_blob)
a.const("FAM_SIZE", 8)
a.const("FAM_COUNT", len(FAMILIES))
a.raw("BMP_TREND", trend_blob)
a.const("TREND_W", len(TREND[0]))
a.raw("T_NAME", name_blob)
a.const("T_NAME_STRIDE", NAME_W)
a.raw("BMP_STATUS", status)
a.const("STATUS_W", STATUS_W)
a.raw("PROTOS", proto_blob)
a.const("PROTO_SIZE", 32)
a.const("PROTO_COUNT", len(P))
a.raw("KEYS", keys_blob)
a.raw("HELP", help_blob)
a.const("HELP_SIZE", len(help_blob))
a.raw("PIECES", pieces_blob)                   # draw() reads it piece by piece
a.const("KEY_MAX", max(len(r["keys"]) for r in RECORDS))   # check() reads them onto the stack
assert dict((n, o) for n, o, _ in a.build()[1])["KEYS"] == keys_at
a.main()
