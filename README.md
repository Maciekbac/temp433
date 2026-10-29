# Temp 433

A receive-only overlay app for the [F4HWN firmware](https://github.com/armel/uv-k1-k5v3-firmware-custom)
on the Quansheng UV-K1 and UV-K5 V3 radios: it listens on 433 MHz for wireless
temperature sensors.

**Status:** work in progress. The current build has the receiver (a sweep of
433.80-434.04 MHz, or the VFO frequency) and decodes Nexus, Prologue, Rubicson
and GT-WT-02 sensors into a table of up to 12 sensors.

The app only receives. It never transmits.

## Screen and keys

Each row is one sensor: model, channel, ID, temperature (°C), humidity, the
time since its last reading, and `!` for a low battery. The selected row is
inverted; the bottom line shows its frequency, signal level and number of
readings (the range and the packet counts while the table is empty). The
status line shows AUTO or VFO, the sensitivity (1-3 bars) and the speaker.

| Key | Action |
|---|---|
| UP / DOWN | select a sensor |
| 1 | speaker on / off |
| 2 | clear the table and the counts |
| 3 | sensitivity: High (6 dB), Normal (10 dB), Low (15 dB) above the noise |
| 5 | AUTO (433.80-434.04 MHz) or the VFO frequency |
| EXIT | quit |

Started on 433.80-434.04 MHz the app sweeps that range (AUTO); on any other
UHF frequency it listens there only (VFO); until a sensor is heard there, a
line reminds you that key 5 searches the whole range. On VHF it asks you to
tune the VFO to 433.920.

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
`PYTHON=python ./build.sh`. `DIAG=1 ./build.sh` writes the diagnostic variant
`Temp433diag.app`, used to measure the receiver; it is not a release build.

The folder can also be copied to `App/apps/temp433/` in the firmware tree. It
then builds with the firmware's own SDK, with `./compile-app.sh temp433` from
the firmware root.

## Install

In UV Studio, open Apps, connect the radio and install `Temp433.app` from a
local file. On the radio, open the Apps menu (`F` then `7`), select Temp 433
and press `MENU`.

## License

Apache License 2.0, see [LICENSE](LICENSE) and [NOTICE](NOTICE).
