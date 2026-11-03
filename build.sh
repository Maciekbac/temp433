#!/usr/bin/env bash
# Build Temp433.app. Based on the build.sh of the F4HWN overlay apps.
#
# Uses the SDK of the firmware tree when this folder sits in App/apps/,
# otherwise the one fetched into sdk/ by tools/fetch_sdk.py.
set -euo pipefail

cd "$(dirname "$0")"

APP=temp433
APP_NAME="Temp 433"
APP_VER="0.2"
APP_API_MIN=3
APP_VMA=${APP_VMA:-0x20000280}
OUT="${APP_NAME// /}"
PYTHON=${PYTHON:-python3}
BUILD_SRC="${APP}_app.build.c"

if [ -f ../app_api.h ] && [ -f ../pack_app.py ]; then SDK=..; else SDK=sdk; fi
[ -f "$SDK/app_api.h" ] || { echo "❌ SDK not found: run $PYTHON tools/fetch_sdk.py"; exit 1; }

CC=/opt/toolchain/bin/arm-none-eabi-gcc
OBJCOPY=/opt/toolchain/bin/arm-none-eabi-objcopy
command -v arm-none-eabi-gcc >/dev/null 2>&1 && { CC=arm-none-eabi-gcc; OBJCOPY=arm-none-eabi-objcopy; }

command -v "$CC" >/dev/null 2>&1 || { echo "❌ ARM compiler not found: $CC"; exit 1; }
command -v "$OBJCOPY" >/dev/null 2>&1 || { echo "❌ ARM objcopy not found: $OBJCOPY"; exit 1; }

# SIZE: optimisations that grow this code on Thumb-1 (more live registers,
# more spills), switched off: -148 B on GCC 13.3, each flag measured on its
# own. Measure them again after a bigger change.
SIZE="-fno-ipa-pure-const -fno-ipa-sra -fno-move-loop-invariants -fno-jump-tables \
  -fno-tree-forwprop -fno-tree-sink -fno-code-hoisting"
CFLAGS="-mcpu=cortex-m0plus -mthumb -Os -std=gnu11 -ffreestanding -fno-builtin -fno-common \
  -fomit-frame-pointer -ffunction-sections -fdata-sections $SIZE -Wall -Wextra -I$SDK -I."
LDFLAGS="-nostdlib -nostartfiles -T app.ld -Wl,--defsym,APP_VMA=${APP_VMA} \
  -Wl,--gc-sections -Wl,-Map=${APP}.map -Wl,--build-id=none -Wl,--no-warn-rwx-segments"

ASSETS=()
rm -f ./*.app ./*.elf ./*.bin "$BUILD_SRC"

step() { printf '\r  🔨 %-13s [%d/4] %-8s' "$APP_NAME" "$1" "$2"; }
trap 'printf "\r  ❌ %-13s build failed            \n" "$APP_NAME"' ERR

step 1 assets
if [ -f gen_assets.py ]; then
  SDK="$SDK" "$PYTHON" ./gen_assets.py "${APP}_assets.bin" "${APP}_assets.h"
  ASSETS=(--assets "${APP}_assets.bin")
fi
# Apply compact UI/table changes to a temporary source copy. Assets and the
# maintained decoder source remain unchanged; the overlay packer enforces the
# 4 KiB code/data limit as before.
"$PYTHON" ./tools/prepare_app.py "${APP}_app.c" "$BUILD_SRC"
step 2 compile ; "$CC" $CFLAGS $LDFLAGS "$BUILD_SRC" -lgcc -o "${APP}.elf"
step 3 objcopy ; "$OBJCOPY" -O binary "${APP}.elf" "${APP}.bin"
step 4 pack    ; "$PYTHON" "$SDK/pack_app.py" "${APP}.bin" "${OUT}.app" \
                   --name "$APP_NAME" --ver "$APP_VER" --api-min "$APP_API_MIN" \
                   --vma "${APP_VMA}" --screensaver ${ASSETS[@]+"${ASSETS[@]}"} >/dev/null
rm -f "$BUILD_SRC"
trap - ERR

BYTES=$(wc -c < "${APP}.bin")
if [ "$BYTES" -gt 4096 ]; then
  printf '\r  🚨 %-13s OVERFLOWS 4 KiB (%d B)     \n' "$APP_NAME" "$BYTES"; exit 1
fi
printf '\r  ✅ %-13s %4d B  (%d%% of 4 KiB)  ->  %s.app   \n' \
       "$APP_NAME" "$BYTES" "$(( BYTES * 100 / 4096 ))" "$OUT"
