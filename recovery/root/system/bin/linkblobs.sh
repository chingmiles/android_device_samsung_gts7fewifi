#!/system/bin/sh
# Exact libraries from lineage-23.2-20260223, installed at their real HAL paths.
# No bootloader substring/version guessing and no partition writes.
for file in /vendor/lib64/hw/gatekeeper.mdfpp.so /vendor/lib64/libskeymaster4device.so /vendor/lib64/libkeymaster_helper.so /vendor/lib64/libcrypto-v33.so; do
    if [ ! -r "$file" ]; then
        echo "E:t733-crypto: required library missing: $file" >> /tmp/recovery.log
        exit 1
    fi
done
echo "I:t733-crypto: using pinned LineageOS 23.2 vendor libraries; runtime compatibility untested" >> /tmp/recovery.log
exit 0
