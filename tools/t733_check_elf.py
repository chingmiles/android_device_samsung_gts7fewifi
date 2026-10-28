"""Conservative ELF64 symbol closure check, not a substitute for linker/runtime tests."""
import struct
from pathlib import Path

def parse(b):
 if b[:6]!=b"\x7fELF\x02\x01":return set(),set(),[]
 po=struct.unpack_from('<Q',b,32)[0];e,n=struct.unpack_from('<HH',b,54);ps=[struct.unpack_from('<IIQQQQQQ',b,po+i*e) for i in range(n)];needed=[];defs=set();undef=set()
 dy=next((x for x in ps if x[0]==2),None)
 if dy:
  ds={};nn=[]
  for off in range(dy[2],dy[2]+dy[5],16):
   t,v=struct.unpack_from('<qQ',b,off);ds[t]=v
   if t==1:nn.append(v)
  if 5 in ds:
   a=ds[5];s=next(x for x in ps if x[0]==1 and x[3]<=a<x[3]+x[5]);o=s[2]+a-s[3];needed=[b[o+x:b.index(b"\0",o+x)].decode() for x in nn]
 off=struct.unpack_from('<Q',b,40)[0];e,n=struct.unpack_from('<HH',b,58)
 if off:
  ss=[struct.unpack_from('<IIQQQQIIQQ',b,off+i*e) for i in range(n)]
  for s in ss:
   if s[1]!=11:continue
   st=ss[s[6]];text=b[st[4]:st[4]+st[5]]
   for i in range(s[4],s[4]+s[5],s[9]):
    name,info,other,ndx,val,length=struct.unpack_from('<IBBHQQ',b,i)
    if not name:continue
    name=text[name:text.index(b"\0",name)].decode(errors='replace')
    if ndx and info>>4 in [1,2,10]:defs.add(name)
    elif not ndx and info>>4==1:undef.add(name)
 return defs,undef,needed

def check(files,roots):
 syms={n:parse(b) for n,b in files.items() if b[:6]==b"\x7fELF\x02\x01"}
 def resolve(name):
  matches=[n for n in syms if Path(n).name==name and '/lib64/' in n]
  matches.sort(key=lambda n:(0 if n.startswith('vendor/lib64/') else 1,len(n)))
  return matches[0] if matches else None
 report={}
 for root in roots:
  if root not in syms:raise ValueError('ELF root missing: '+root)
  closure=set();todo=[root];missinglibs=set()
  while todo:
   n=todo.pop()
   if n in closure:continue
   closure.add(n)
   for dep in syms[n][2]:
    target=resolve(dep)
    if target:todo.append(target)
    else:missinglibs.add(dep)
  exports=set().union(*(syms[n][0] for n in closure))
  missing={n:sorted(syms[n][1]-exports) for n in closure if syms[n][1]-exports}
  report[root]={'missing_libraries':sorted(missinglibs),'unresolved_strong_symbols':missing,'loaded_files':sorted(closure)}
 return report
