#!/usr/bin/env python3
"""Read-only check of the bundled fixed Recovery profile."""
import hashlib,json
from pathlib import Path
from t733_prepare import check_prebuilts,module_plan
HERE=Path(__file__).resolve().parent
DEVICE=HERE.parent

def main():
 check_prebuilts(DEVICE/'prebuilt')
 modules,_=module_plan(DEVICE/'recovery/root/lib/modules')
 for name,value in modules.items():
  actual=DEVICE/'recovery/root/lib/modules'/name
  if not actual.is_file() or actual.read_bytes()!=value:raise ValueError('module/metadata mismatch: '+name)
 pins=json.loads((HERE/'crypto-profile-sha256.json').read_text())
 for name,digest in pins.items():
  if hashlib.sha256((DEVICE/'recovery/root'/name).read_bytes()).hexdigest()!=digest:raise ValueError('profile mismatch: '+name)
 print('PASS: prebuilt stock payloads, touch modules/dependencies and V2 crypto profile asset hashes')
if __name__=='__main__':
 try:main()
 except (OSError,ValueError) as e:raise SystemExit('STOP: '+str(e))
