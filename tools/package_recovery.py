#!/usr/bin/env python3
"""Check this crypto profile and package recovery only; no device operations."""
import argparse,hashlib,json,shutil,subprocess,tarfile
from pathlib import Path
from t733_verify import unpack,cpio_files,require
from t733_check_elf import check as check_elf
HERE=Path(__file__).resolve().parent

def sha(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for b in iter(lambda:f.read(4194304),b''):h.update(b)
 return h.hexdigest()

def verify_profile(path):
 raw=Path(path).read_bytes();require(len(raw)==81788928,'Wrong Recovery partition size')
 rd,header=unpack(raw);files=cpio_files(rd)
 pins=json.loads((HERE/'crypto-profile-sha256.json').read_text())
 for name,digest in pins.items():
  require(hashlib.sha256(files.get(name,b'')).hexdigest()==digest,'Ramdisk asset mismatch: '+name)
 b=files.get('system/bin/recovery',b'')
 require(b'libresetprop.so' in b and b'Decrypt_Adopted: no crypto support' not in b,'Main recovery crypto support missing')
 required={name for v in json.loads((HERE/'crypto-library-audit.json').read_text()).values() for name in v['needed']}
 available={Path(n).name for n in files if '/lib64/' in n}
 require(not required-available,'Missing library names: '+str(sorted(required-available)))
 roots=['system/bin/recovery','system/bin/android.hardware.keymaster@4.0-service','system/bin/android.hardware.gatekeeper@1.0-service','vendor/lib64/hw/gatekeeper.mdfpp.so','vendor/lib64/libskeymaster4device.so','vendor/lib64/libkeymaster_helper.so','vendor/lib64/libcrypto-v33.so']
 closure=check_elf(files,roots)
 require(all(not v['missing_libraries'] and not v['unresolved_strong_symbols'] for v in closure.values()),'ELF strong symbol/dependency check failed; incompatible vendor support libraries')
 return dict(elf_symbol_closure=closure,status='STATIC V2 PROFILE PASSED; NEW BUILD REQUIRES HARDWARE REGRESSION TEST',header=header,pinned_ramdisk_assets=len(pins),image_bytes=len(raw),image_sha256=hashlib.sha256(raw).hexdigest(),device_operations=False,runtime_abi='not tested')

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--image',type=Path,required=True)
 p.add_argument('--out',type=Path);p.add_argument('--avbtool',type=Path);p.add_argument('--key',type=Path);p.add_argument('--verify-only',action='store_true');a=p.parse_args()
 report=verify_profile(a.image)
 if a.verify_only:
  print(json.dumps(report,indent=2));return
 require(a.out and a.avbtool and a.key,'Packaging requires --out, --avbtool and --key')
 require(shutil.which('lz4'),'Install the lz4 CLI')
 subprocess.run([str(a.avbtool),'verify_image','--image',str(a.image),'--key',str(a.key)],check=True)
 require(not a.out.exists(),'Output directory already exists; choose a new output directory')
 a.out.mkdir(parents=True)
 image=a.out/'recovery.img';shutil.copyfile(a.image,image)
 compressed=a.out/'recovery.img.lz4'
 subprocess.run(['lz4','-9','-B6','-BI','--content-size','-f',str(image),str(compressed)],check=True)
 check=a.out/'roundtrip.img'
 subprocess.run(['lz4','-d','-f',str(compressed),str(check)],check=True)
 require(sha(check)==sha(image),'LZ4 round-trip failed');check.unlink()
 archive=a.out/'TWRP-SM-T733-LOS23.2-CRYPTO-V2.tar'
 with tarfile.open(archive,'w',format=tarfile.USTAR_FORMAT,copybufsize=4194304) as t:
  info=tarfile.TarInfo('recovery.img.lz4');info.size=compressed.stat().st_size;info.mode=0o644;info.mtime=0
  with compressed.open('rb') as f:t.addfile(info,f)
 with tarfile.open(archive,'r:') as t:
  require(t.getnames()==['recovery.img.lz4'],'Unexpected TAR member')
  h=hashlib.sha256();f=t.extractfile('recovery.img.lz4')
  for b in iter(lambda:f.read(4194304),b''):h.update(b)
  require(h.hexdigest()==sha(compressed),'TAR data mismatch')
 report.update(avb='signature and payload verified against supplied test key',tar_sha256=sha(archive),tar_members=['recovery.img.lz4'])
 (a.out/'verification.json').write_text(json.dumps(report,indent=2)+'\n')
 (a.out/'SHA256SUMS').write_text(''.join(sha(f)+'  '+f.name+'\n' for f in [image,compressed,archive]))
 print('READY: '+str(archive));print('Reference V2 passed user startup/decryption tests; this new build still needs regression testing. No device was modified.')
if __name__=='__main__':
 try:main()
 except (ValueError,OSError,subprocess.SubprocessError) as e:raise SystemExit('STOP: '+str(e))
