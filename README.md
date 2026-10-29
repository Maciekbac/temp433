# Temp 433

A receive-only overlay app for the [F4HWN firmware](https://github.com/armel/uv-k1-k5v3-firmware-custom)
on the Quansheng UV-K1 and UV-K5 V3 radios: it listens on 433 MHz for wireless
temperature sensors.

**Status:** work in progress. The current build has the receiver (a sweep of
433.80-434.04 MHz, or the VFO frequency) and decodes the sensors listed
below into a table of up to 12 sensors.

The app only receives. It never transmits.

## Screen and keys

Each row is one sensor: model, channel, ID, temperature (°C, shown as `23.9C`),
humidity, the time since its last reading, and `!` right after it for a low
battery:

```
INFACTORY 3 205  -7.3C 99%   2s!
NEXUS     1 136  12.5C 60%  26s
```

Up to six rows show at a time; the arrows in the status line mark more rows
above or below. The
bottom line shows the range (or the frequency) and how many packets were
decoded (`ok`) and not recognised (`?`). The status line shows AUTO or VFO,
the sensitivity (1-3 bars) and the speaker.

| Key | Action |
|---|---|
| UP / DOWN | scroll the table |
| 1 | speaker on / off |
| 2 | clear the table and the counts |
| 3 | sensitivity: High (6 dB), Normal (10 dB), Low (15 dB) above the noise |
| 5 | AUTO (433.80-434.04 MHz) or the VFO frequency |
| EXIT | quit |

Started on 433.80-434.04 MHz the app sweeps that range (AUTO); on any other
UHF frequency it listens there only (VFO); until a sensor is heard there, a
line reminds you that key 5 searches the whole range. On VHF it asks you to
tune the VFO to 433.920.

## Sensors

| Shown as | Protocol (rtl_433 decoder) | Also sold as |
|---|---|---|
| NEXUS | Nexus-TH | Sencor, Solight TE82S, FreeTec NC-7345, TFA 30.3209 |
| RUBICSON | Rubicson-Temperature, Solight-TE44 | TFA 30.3197, inFactory PT-310, Solight TE44/TE66, EMOS E0107T |
| PROLOGUE | Prologue-TH | FreeTec NC-7104, NC-7159, ThermoPro TX-2 |
| GT-WT-02 | GT-WT02 | Globaltronics (Aldi), Lidl AURIO YJ-T12 |
| AUR-AHFL | Auriol-AHFL | Lidl Auriol AHFL 433 B2 |
| AUR-AFW2 | Auriol-AFW2A1 | Lidl Auriol AFW 2 A1 |
| AUR-HG02 | Auriol-HG02832 | Lidl Auriol HG02832, HG05124A, Rubicson 48957 |
| ESPERANZA | Esperanza-EWS | Kedsum, Conrad S3318P |
| INFACTORY | inFactory-TH | nor-tec, FreeTec NC-3982 |
| TX141TH | LaCrosse-TX141THBv2 | TFA 30.3221 |
| BRESSER | Bresser-3CH | Renkforce DM-7511 |
| EMOS | EMOS-E6016, EMOS-E6018 | |
| LACROSSE | LaCrosse-TX (temperature) | La Crosse TX3, TX4, TX6U, TX7U |

The frame layouts, timings and checks follow the device descriptions in
[rtl_433](https://github.com/merbanan/rtl_433) (`src/devices/`), used as a
specification only: the decoders here are written from them, no code is
taken. Channels and IDs are shown as rtl_433 shows them, so you can compare
the two.

Limitations:
- A humidity outside 1-100 % shows as `--` (rtl_433 drops such a frame).
- GT-WT-02 humidity codes 10 and 110, which rtl_433 shows as 0 % and 100 %,
  show as `10%` and `--`.
- La Crosse TX: temperature only; its humidity frames are skipped, and the
  parity bit and the repeated digits are not checked.
- Nexus, Prologue and Auriol AFW 2 A1 send no checksum: a reading counts once
  the same frame comes twice.
- Within one timing, the decoders are tried in order; a 42-bit inFactory frame
  could pass the 4-bit check of Esperanza now and then (40-bit ones cannot).

## Requirements

- F4HWN Labs v6.3.0 or later, or a later edition with overlay apps (API level 3
  or higher).
- To build: `arm-none-eabi-gcc` on the `PATH`, Python 3 and bash.

## Build

```sh
python3 tools/fetch_sdk.py   # downloads the F4HWN app SDK into sdk/
./build.sh                   # writes Temp433.app
```

Set `PYTHON` if your Python 3 is not called `python3`, for example
`PYTHON=python ./build.sh`.

The folder can also be copied to `App/apps/temp433/` in the firmware tree. It
then builds with the firmware's own SDK, with `./compile-app.sh temp433` from
the firmware root.

## Install

In UV Studio, open Apps, connect the radio and install `Temp433.app` from a
local file. On the radio, open the Apps menu (`F` then `7`), select Temp 433
and press `MENU`.

## License

Apache License 2.0, see [LICENSE](LICENSE) and [NOTICE](NOTICE).
