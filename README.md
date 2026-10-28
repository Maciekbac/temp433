# Temp 433

A receive-only overlay app for the [F4HWN firmware](https://github.com/armel/uv-k1-k5v3-firmware-custom)
on the Quansheng UV-K1 and UV-K5 V3 radios: it listens on 433 MHz for wireless
temperature sensors.

**Status:** work in progress. The current build only shows its title; EXIT
quits.

The app only receives. It never transmits.

## Requirements

- F4HWN Labs v6.1.0 or later, or a later edition with overlay apps (API level 2
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
