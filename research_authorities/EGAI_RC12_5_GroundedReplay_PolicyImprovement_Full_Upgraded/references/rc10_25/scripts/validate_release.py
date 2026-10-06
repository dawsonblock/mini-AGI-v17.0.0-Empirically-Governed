#!/usr/bin/env python3
from __future__ import annotations
import hashlib, json, os, platform, shutil, subprocess, sys
from pathlib import Path

root=Path(__file__).resolve().parents[1]
manifest=root/'BUILD_MANIFEST.json'


def digest(path: Path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''): h.update(chunk)
    return h.hexdigest()


def run(cmd, **kwargs):
    p=subprocess.run(cmd, cwd=kwargs.pop('cwd', root), text=True, capture_output=True, **kwargs)
    if p.returncode:
        print(p.stdout); print(p.stderr,file=sys.stderr); raise SystemExit(p.returncode)
    if p.stdout.strip(): print(p.stdout.strip())
    return p

run([sys.executable,'-m','pytest','-q'])
run([sys.executable,'-m','compileall','-q',str(root/'src')])

native=root/'native/kvmem-qw3-rc9.2/experimental/rc10'
out=Path('/tmp/rc10_affine_test')
cxx=os.environ.get('CXX') or shutil.which('clang++') or shutil.which('g++')
if not cxx:
    raise SystemExit('No C++17 compiler found')
run([cxx,'-std=c++17',str(native/'affine_reference_test.cpp'),'-I',str(native),'-o',str(out)])
run([str(out)])

metal_status='not-run-non-macos'
if platform.system() == 'Darwin' and platform.machine().lower() in {'arm64','aarch64'}:
    metal=root/'native/kvmem-qw3-rc9.2/experimental/rc10_metal'
    build=metal/'build-validation'; build.mkdir(exist_ok=True)
    run(['xcrun','-sdk','macosx','metal','-c',str(metal/'rc10_affine.metal'),'-o',str(build/'rc10_affine.air')])
    run(['xcrun','-sdk','macosx','metal','-c',str(metal/'rc10_gdn_reference.metal'),'-o',str(build/'rc10_gdn_reference.air')])
    lib=build/'rc10_reference.metallib'
    run(['xcrun','-sdk','macosx','metallib',str(build/'rc10_affine.air'),str(build/'rc10_gdn_reference.air'),'-o',str(lib)])
    affine_smoke=build/'metal_affine_smoke'
    gdn_smoke=build/'metal_gdn_smoke'
    conv_smoke=build/'metal_conv_smoke'
    run(['clang++','-std=c++17','-fobjc-arc',str(metal/'metal_affine_smoke.mm'),'-framework','Foundation','-framework','Metal','-o',str(affine_smoke)])
    run(['clang++','-std=c++17','-fobjc-arc',str(metal/'metal_gdn_smoke.mm'),'-framework','Foundation','-framework','Metal','-o',str(gdn_smoke)])
    run(['clang++','-std=c++17','-fobjc-arc',str(metal/'metal_conv_smoke.mm'),'-framework','Foundation','-framework','Metal','-o',str(conv_smoke)])
    run([str(affine_smoke),str(lib)])
    run([str(gdn_smoke),str(lib)])
    run([str(conv_smoke),str(lib)])
    metal_status='pass-affine-gdn-hypic-conv'

entries=[]
for p in sorted(root.rglob('*')):
    if not p.is_file() or p==manifest or '__pycache__' in p.parts or '.pytest_cache' in p.parts or 'build-validation' in p.parts or 'build' in p.parts or any(part.endswith('.egg-info') for part in p.parts): continue
    entries.append({'path':str(p.relative_to(root)),'bytes':p.stat().st_size,'sha256':digest(p)})
manifest.write_text(json.dumps({'version':'0.10.24','target':'macOS-arm64','metal_validation':metal_status,'files':entries},indent=2,sort_keys=True)+'\n')
print(f'manifest files: {len(entries)}')
