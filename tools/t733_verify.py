#!/usr/bin/env python3
"""Inspect a local recovery image, without opening any device or partition."""
import argparse
import gzip
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys

from t733_prepare import STOCK_SHA, sha


def require(condition, message):
    if not condition:
        raise ValueError(message)


def unpack(data):
    require(len(data) >= 4096 and data[:8] == b'ANDROID!', 'not an Android boot image')
    values = struct.unpack_from('<10I', data, 8)
    ks, ka, rs, ra, ss, sa, tags, page, version, os_version = values
    require((version, page, ka, ra, tags) == (2, 4096, 0x8000, 0x2000000, 0x1e00000),
            'header / load addresses do not match stock DYE1')
    require(ss == 0, 'unexpected second-stage payload')
    require(data[48:64].rstrip(b'\0') == b'SRPUF17A009', 'wrong board')
    ds, do, header_size = struct.unpack_from('<IQI', data, 1632)
    ts, ta = struct.unpack_from('<IQ', data, 1648)
    require(header_size == 1660 and ta == 0x1f00000 and ds and ts, 'missing or invalid DTB / recovery DTBO')
    align = lambda n: (n + page - 1) // page * page
    ro = page + align(ks)
    require(do == ro + align(rs), 'incorrect recovery DTBO file offset')
    to = do + align(ds)
    end = to + align(ts)
    require(end <= len(data), 'truncated payloads')
    require(data[end:end+16] == b'SEANDROIDENFORCE', 'Samsung marker missing or misplaced')
    require(len(data) <= 81788928, 'image exceeds configured recovery partition size')
    require(data[-64:-60] == b'AVBf', 'AVB footer missing at the end of image')
    magic, major, minor, original, vbmeta, vbsize = struct.unpack_from('>4sIIQQQ', data, len(data)-64)
    require(original >= end + 16 and original <= vbmeta and vbmeta + vbsize <= len(data)-64,
            'AVB footer does not cover the complete image including Samsung marker')
    require(data[vbmeta:vbmeta+4] == b'AVB0', 'invalid vbmeta offset')
    payloads = {'Image': data[page:page+ks], 'dtb': data[to:to+ts], 'dtbo.img': data[do:do+ds]}
    for name, payload in payloads.items():
        require(sha(payload) == STOCK_SHA[name], name + ' differs from verified stock recovery payload')
    report = dict(header_version=version, board='SRPUF17A009', pagesize=page,
                  kernel_addr=hex(ka), ramdisk_addr=hex(ra), tags_addr=hex(tags), dtb_addr=hex(ta),
                  kernel_size=ks, dtb_size=ts, recovery_dtbo_size=ds, image_size=len(data),
                  os_version_field=os_version, samsung_marker=end,
                  signed_trailer_bytes=original-end-16,
                  avb=dict(major=major, minor=minor, vbmeta_offset=vbmeta, vbmeta_size=vbsize),
                  stock_payload_sha256={n: sha(d) for n, d in payloads.items()})
    return data[ro:ro+rs], report


def cpio_files(compressed):
    if compressed[:2] == b'\x1f\x8b':
        raw = gzip.decompress(compressed)
    elif compressed[:6] in (b'070701', b'070702'):
        raw = compressed
    else:
        lz4 = shutil.which('lz4')
        require(lz4 is not None, 'install lz4 to inspect this ramdisk compression')
        raw = subprocess.run([lz4, '-dc'], input=compressed, stdout=subprocess.PIPE, check=True).stdout
    files, pos = {}, 0
    while pos + 110 <= len(raw):
        h = raw[pos:pos+110]
        require(h[:6] in (b'070701', b'070702'), 'invalid newc ramdisk')
        fields = [int(h[i:i+8], 16) for i in range(6, 110, 8)]
        mode, size, name_size = fields[1], fields[6], fields[11]
        require(name_size > 0, 'invalid cpio filename')
        name = raw[pos+110:pos+110+name_size-1].decode()
        start = (pos + 110 + name_size + 3) & ~3
        require(start + size <= len(raw), 'truncated cpio entry')
        pos = (start + size + 3) & ~3
        if name == 'TRAILER!!!':
            return files
        name = name.removeprefix('./')
        if mode & 0o170000 == 0o100000:
            files[name] = raw[start:start+size]
    raise ValueError('cpio trailer missing')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('image', type=Path)
    parser.add_argument('--device', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--structure-only', action='store_true', help='skip TWRP ramdisk checks (e.g. stock image)')
    parser.add_argument('--avbtool', type=Path)
    parser.add_argument('--key', type=Path)
    args = parser.parse_args()
    ramdisk, report = unpack(args.image.read_bytes())
    if not args.structure_only:
        require(report['signed_trailer_bytes'] == 0, 'rebuilt image contains an unexpected old OEM signature trailer')
        manifest = json.loads((args.device / 'tools/t733-modules.json').read_text())
        files = cpio_files(ramdisk)
        for name, expected in manifest['sha256'].items():
            path = 'lib/modules/' + name
            require(path in files and sha(files[path]) == expected, 'ramdisk module / metadata mismatch: ' + path)
        require('lib/modules/stm_ts.ko' not in files, 'old STM driver still packaged')
        hook = 'system/bin/postrecoveryboot.sh'
        require(files.get(hook) == (args.device / 'recovery/root' / hook).read_bytes(), 'old vendor-writing hook packaged')
        for path in ('system/bin/recovery', 'system/bin/adbd', 'init.recovery.qcom.rc', 'init.recovery.usb.rc',
                     'vendor/firmware/tsp_focaltech/ft8203_gts7xllite.bin'):
            require(path in files and files[path], 'required recovery file missing: ' + path)
        requested = ' '.join(n + '.ko' for n in manifest['requested']).encode()
        require(requested in files['system/bin/recovery'], 'compiled TWRP lacks expected module request list')
        require(files.get('system/etc/recovery.fstab') == (args.device / 'recovery.fstab').read_bytes(),
                'recovery fstab differs from the device tree')
        report['ramdisk_modules_and_dependencies'] = manifest
    avbtool = args.avbtool or shutil.which('avbtool')
    if avbtool:
        avbtool = Path(avbtool)
        cmd = ([sys.executable, str(avbtool)] if avbtool.suffix == '.py' else [str(avbtool)])
        subprocess.run(cmd + ['info_image', '--image', str(args.image)], check=True)
        verify = cmd + ['verify_image', '--image', str(args.image)]
        if args.key:
            verify += ['--key', str(args.key)]
        subprocess.run(verify, check=True)
        report['avb_verification'] = 'passed with supplied key' if args.key else 'passed with embedded key (trust not established)'
    else:
        require(args.structure_only, 'avbtool is required for full build verification')
        report['avb_verification'] = 'NOT CHECKED: footer layout only'
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, struct.error, subprocess.CalledProcessError) as error:
        raise SystemExit('STOP: ' + str(error))
