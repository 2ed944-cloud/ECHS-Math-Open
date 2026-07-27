#!/usr/bin/env python3
from __future__ import annotations
import brotli,hashlib,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; ERRORS=[]
def fail(m): ERRORS.append(m)
def decode(text,byte_length):
 acc=bits=0; out=bytearray()
 for ch in text:
  v=ord(ch)-0x800
  if not 0<=v<=0x7fff: raise ValueError("invalid 15-bit character")
  acc=(acc<<15)|v; bits+=15
  while bits>=8 and len(out)<byte_length:
   bits-=8; out.append((acc>>bits)&255); acc&=(1<<bits)-1
 return bytes(out)
def main():
 shared=ROOT/'lessons/ap-precalculus/shared'; m=json.loads((shared/'units-3-4-bundle-manifest.json').read_text())
 try: compressed=decode(''.join((shared/n).read_text() for n in m['chunks']),m['compressedBytes'])
 except Exception as e: fail(f"bundle decode failed: {e}"); compressed=b''
 if compressed and hashlib.sha256(compressed).hexdigest()!=m['compressedSha256']: fail('bundle SHA-256 mismatch')
 try: p=json.loads(brotli.decompress(compressed)) if compressed else {}
 except Exception as e: fail(f"Brotli/JSON decode failed: {e}"); p={}
 lessons=p.get('lessons',{}); expected=[f'3.{i}' for i in range(1,16)]+[f'4.{i}' for i in range(1,15)]
 if sorted(lessons,key=lambda x:tuple(map(int,x.split('.'))))!=expected: fail('topic inventory is incomplete')
 for topic,html in lessons.items():
  if html.count('class="slide')<56: fail(f'{topic}: fewer than 56 slides')
  if 'START_HERE.html' in html or '../../../index.html#courses' not in html: fail(f'{topic}: portal return link invalid')
 shell=(ROOT/'lessons/ap-precalculus/lesson.html').read_text(); data=(ROOT/'data/ap-precalculus-units-3-4.js').read_text(); index=(ROOT/'index.html').read_text(); worker=(ROOT/'sw.js').read_text()
 if 'shared/ap-precalculus-unit-loader.js' not in shell: fail('lesson shell loader missing')
 for t in expected:
  if f'lesson.html?topic={t}' not in data: fail(f'portal route missing: {t}')
 if not 0<=index.find('data/ap-precalculus-update.js')<index.find('data/ap-precalculus-units-3-4.js')<index.find('js/portal.js'): fail('index script order invalid')
 for token in ('./data/ap-precalculus-units-3-4.js','./lessons/ap-precalculus/lesson.html','./lessons/ap-precalculus/shared/ap-precalculus-unit-loader.js','./lessons/ap-precalculus/shared/units-3-4-bundle-manifest.json'):
  if token not in worker: fail(f'sw.js missing {token}')
 for f in ('data/ap-precalculus-units-3-4.js','lessons/ap-precalculus/shared/ap-precalculus-unit-loader.js'):
  r=subprocess.run(['node','--check',str(ROOT/f)],capture_output=True,text=True)
  if r.returncode: fail(f'{f}: {r.stderr.strip()}')
 print('AP Precalculus Units 3–4 deployment validation'); print(f'Errors: {len(ERRORS)}'); [print('  ERROR:',x) for x in ERRORS]; print('Status: '+('FAIL' if ERRORS else 'PASS')); return 1 if ERRORS else 0
if __name__=='__main__': raise SystemExit(main())
