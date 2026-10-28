# TWRP device tree — Samsung Galaxy Tab S7 FE Wi-Fi (SM-T733 / gts7fewifi)

This tree contains the **V2 crypto startup fix** for the tested DYE1-based recovery configuration. On 2026-10-28 the user confirmed successful TWRP startup and Data decryption with `lineage-23.2-20260223-UNOFFICIAL-gts7fewifi` (SDK 36). This is a community device tree, not an official TeamWin certification or a claim that every ROM, credential type or feature works.

[中文完整编译说明](README.zh-CN.md) · [Reference build and validation scope](BUILD-REFERENCE.json)

## What is included

- Stock T733ZCS9DYE1 kernel, DTB and Recovery DTBO; boot header v2, board `SRPUF17A009`, 1600×2560 display configuration.
- Seven matching touch modules, dependency metadata and FocalTech firmware. The early `modules.load` lists are intentionally empty; TWRP loads the requested modules after the required services are available.
- Full TWRP crypto compilation enabled, fixed ROM-specific hardware library selection, and the V2 startup-library repair.
- Recovery image validation and LZ4/single-member TAR packaging tools. The actual Recovery partition size is **81,788,928 bytes (78 MiB)**.

## Build

Use an x86_64 Linux environment; the reference build used Ubuntu 22.04. On WSL2 keep the platform checkout on the Linux filesystem, not `/mnt/c` or another Windows mount. Install the Android build prerequisites, Python 3, Git/Repo and the `lz4` CLI. See the Chinese guide for an Ubuntu 22.04 dependency list and initial disk-space guidance.

```bash
mkdir -p ~/android/twrp
cd ~/android/twrp
repo init --depth=1 -u https://github.com/minimal-manifest-twrp/platform_manifest_twrp_aosp.git -b twrp-12.1
repo sync -j4
git clone https://github.com/chingmiles/android_device_samsung_gts7fewifi.git device/samsung/gts7fewifi
if [ ! -d device/qcom/twrp-common ]; then
  git clone --branch android-12.1 https://github.com/TeamWin/android_device_qcom_twrp-common.git device/qcom/twrp-common
fi
python3 device/samsung/gts7fewifi/tools/check_source_assets.py
T733_JOBS=4 bash device/samsung/gts7fewifi/tools/build_portable.sh
```

Use a new device directory or back up an existing checkout before installation. The build wrapper selects `twrp_gts7fewifi-eng`, builds `recoveryimage`, checks the payloads and AVB signature, checks the crypto profile and critical ELF dependencies, then packages only `recovery.img.lz4` into a TAR. Results are written under `dist/gts7fewifi-crypto-<timestamp>/`. No build/package script flashes, reboots, mounts or formats a tablet.

For a raw-image-only build:

```bash
export ALLOW_MISSING_DEPENDENCIES=true
source build/envsetup.sh
lunch twrp_gts7fewifi-eng
m -j4 recoveryimage
```

The raw result is `out/target/product/gts7fewifi/recovery.img`. Do not treat the existence of that file alone as proof of a valid or successfully tested image; run the full validation/package wrapper before distributing it.

## Why V2 fixes the splash-screen regression

The first crypto experiment copied newer generic LineageOS Keymaster/C++ support libraries into an older TWRP platform. Several required symbols were absent, including `__libcpp_verbose_abort` and `OPENSSL_sk_*`. The live logs showed recovery waiting for Keystore2 and Keymaster without reaching the main UI.

V2 keeps only the four necessary ROM hardware libraries (`gatekeeper.mdfpp.so`, `libskeymaster4device.so`, `libkeymaster_helper.so`, `libcrypto-v33.so`) alongside the compatible baseline/platform support libraries. It restores four baseline libraries and removes nine vendor support-library overrides. Do not reintroduce the generic newer libraries just to satisfy a filename dependency. `t733_check_elf.py` adds a conservative strong-symbol closure check; runtime linker namespaces, symbol versions and actual hardware services still require device testing.

The user-tested V2 was a ramdisk repair of the compiled EXPERIMENTAL-1 main program; its version page can therefore still show EXPERIMENTAL-1. `/t733-build-id` distinguishes the V2 profile. The reference SHA-256 values and the precise test scope are recorded in `BUILD-REFERENCE.json`.

## Scope and reproducibility

- Only **Recovery** is supported by the checks in this tree. Historical super/vendor_boot sizing remains outside this validation scope: do not use it to build/flash those images.
- The data encryption policy is retained. This is decryption support, not an encryption-disabling or Data-formatting package. Never use formatting or deletion of lockscreen files as a substitute for diagnosing decryption failures.
- Do not flash the earlier stock DYE1 super package over LineageOS; it replaces system/vendor contents.
- The AVB private key referenced here is a **published AOSP test key** in the platform source, not a Samsung production key. A valid self-signature does not establish device trust.
- New builds still need startup/touch/decryption regression testing. Preserve the known-good package and back up personal data before any manual flashing.
- `tools/t733-build-sources.txt` records the previously audited core revisions, not a lock for the entire platform checkout. Save `repo manifest -r -o manifest-pinned.xml` from a validated platform build for stricter reproduction; this repository does not include a complete Android checkout or kernel sources.

## Provenance

Original device tree: this repository and its retained file notices. Platform: [TeamWin/minimal-manifest TWRP 12.1](https://github.com/minimal-manifest-twrp/platform_manifest_twrp_aosp/tree/twrp-12.1). Stock kernel/DTB/DTBO/modules: matching T733ZCS9DYE1 firmware. Hardware crypto libraries: [the tested LineageOS 23.2 release](https://github.com/Bush-cat/android_device_samsung_gts7fewifi/releases/tag/los23.2-testing).

Existing source copyright notices are retained in the files and [upstream notices](UPSTREAM-NOTICES.md). Prebuilt firmware/vendor binaries remain the property of their respective owners; this tree does not relicense those binaries as open source.
