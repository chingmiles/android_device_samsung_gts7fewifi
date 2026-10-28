#!/system/bin/sh
# Diagnostic service: read state only; all output remains in RAM under /tmp.
umask 022
exec > /tmp/t733-diag.log 2>&1
cat /t733-build-id
id
getenforce
getprop ro.boot.t733diag
cat /proc/cmdline
echo RECOVERY_PARTITION_BYTES
blockdev --getsize64 /dev/block/by-name/recovery
echo RECOVERY_FIRST_78_MIB_SHA256
dd if=/dev/block/by-name/recovery bs=4096 count=19968 2>/dev/null | sha256sum
for pause in 1 4 15 45; do
    sleep "$pause"
    echo SNAPSHOT_UPTIME
    cat /proc/uptime
    cat /proc/modules
    cat /proc/bus/input/devices
    ls -la /sys/bus/spi/devices/spi1.1
    cat /sys/kernel/debug/devices_deferred
    echo SAMSUNG_TOUCH_LOG
    cat /proc/tsp_msg
    echo KERNEL_LOG
    dmesg
done
echo T733_DIAGNOSTIC_COMPLETE
