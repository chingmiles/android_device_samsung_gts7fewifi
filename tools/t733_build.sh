#!/usr/bin/env bash
# Build local source and inspect the result. No device commands are used.
set -euo pipefail
device=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
root=${1:-}
if [[ -z "$root" ]]; then
    candidate=$device
    while [[ "$candidate" != / ]]; do
        if [[ -f "$candidate/build/envsetup.sh" ]]; then
            root=$candidate
            break
        fi
        candidate=$(dirname -- "$candidate")
    done
fi
if [[ -z "$root" || ! -f "$root/build/envsetup.sh" ]]; then
    echo 'SOURCE READY; BUILD BLOCKED: no full TWRP source tree (build/envsetup.sh missing).'
    echo 'Expected: minimal-manifest-twrp twrp-12.1 / TeamWin android-12.1.'
    echo 'After a full source checkout, place this tree at device/samsung/gts7fewifi and rerun tools/t733_build.sh.'
    exit 2
fi
root=$(cd -- "$root" && pwd -P)
if [[ ! -d "$root/device/samsung/gts7fewifi" ]] || [[ $(cd -- "$root/device/samsung/gts7fewifi" && pwd -P) != "$device" ]]; then
    echo 'BUILD BLOCKED: this device tree must be at <TWRP root>/device/samsung/gts7fewifi.'
    echo 'No directory was moved or overwritten.'
    exit 2
fi
python3 "$device/tools/t733_prepare.py" --check --modules-dir "$device/recovery/root/lib/modules"
python3 - "$root" <<'PY'
from pathlib import Path
import sys
root = Path(sys.argv[1])
checks = {
    'bootable/recovery/kernel_module_loader.cpp': ['TW_LOAD_VENDOR_BOOT_MODULES', 'Modprobe m(', 'modules.load.twrp', 'LoadListedModules'],
    'bootable/recovery/kernel_module_loader.hpp': ['VENDOR_BOOT_MODULE_DIR "/lib/modules"'],
    'bootable/recovery/partitionmanager.cpp': ['KernelModuleLoader::Load_Vendor_Modules()'],
    'build/make/core/Makefile': ['recovery_root_private', 'cp -rf $(item) $(TARGET_RECOVERY_OUT)/',
                                'INTERNAL_RECOVERYIMAGE_ARGS += --kernel $(recovery_kernel)',
                                'INTERNAL_RECOVERYIMAGE_ARGS += --recovery_dtbo $(BOARD_PREBUILT_RECOVERY_DTBOIMAGE)'],
    'system/core/libmodprobe/libmodprobe.cpp': ['base_path + "/"', 'InsmodWithDeps', 'dependencies.rbegin()'],
}
for path, needles in checks.items():
    text = (root / path).read_text()
    for needle in needles:
        if needle not in text:
            raise SystemExit(f'STOP: active source differs from audited 12.1 implementation: {path}: {needle}')
print('Active build sources implement the audited module / ramdisk / mkbootimg paths.')
PY
{
    for project in bootable/recovery build/make system/core system/tools/mkbootimg external/avb; do
        printf '\n%s\n' "$project"
        git -C "$root/$project" log -1 --format='%H %D' || true
    done
} > "$device/tools/t733-build-sources.txt"
cd -- "$root"
# Android envsetup is not guaranteed to work with nounset enabled.
set +u
export ALLOW_MISSING_DEPENDENCIES=true
source build/envsetup.sh
lunch twrp_gts7fewifi-eng
# Android's build functions also access optional unset variables after lunch.
m recoveryimage -j"${T733_JOBS:-4}"
product_out=$(get_build_var PRODUCT_OUT)
host_out=$(get_build_var HOST_OUT_EXECUTABLES)
[[ "$product_out" = /* ]] || product_out="$root/$product_out"
[[ "$host_out" = /* ]] || host_out="$root/$host_out"
avbtool="$host_out/avbtool"
python3 "$device/tools/t733_verify.py" "$product_out/recovery.img" \
    --device "$device" --avbtool "$avbtool" \
    --key "$root/external/avb/test/data/testkey_rsa4096.pem"
