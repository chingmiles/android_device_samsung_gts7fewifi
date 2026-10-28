#!/usr/bin/env bash
# Offline local build/validation/package only. No tablet commands.
set -eo pipefail
device=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
root=$(cd -- "$device/../../.." && pwd -P)
if [[ ! -f "$root/build/envsetup.sh" || "$device" != "$root/device/samsung/gts7fewifi" ]]; then
    echo 'STOP: place this directory at <TWRP root>/device/samsung/gts7fewifi.'
    exit 2
fi
bash "$device/tools/t733_build.sh" "$root"
python3 "$device/tools/package_recovery.py" \
    --image "$root/out/target/product/gts7fewifi/recovery.img" \
    --out "$root/dist/gts7fewifi-crypto-$(date +%Y%m%d-%H%M%S)" \
    --avbtool "$root/out/host/linux-x86/bin/avbtool" \
    --key "$root/external/avb/test/data/testkey_rsa4096.pem"
