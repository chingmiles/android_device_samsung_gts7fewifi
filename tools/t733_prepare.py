#!/usr/bin/env python3
"""Prepare firmware-matched touch modules; operates on local source files only."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct

RELEASE = '5.4.254-qgki-1570070-abT733ZCS9DYE1'
MODULE_RELEASES = {RELEASE, RELEASE.replace('-qgki-', '-')}
STOCK_SHA = {
    'Image': 'a6c929ea8a0cf326b69312d49f48a5114d78b7f913c37bf9148942434142c79d',
    'dtb': '217e8f03157b77f5ada4872b750e93d9b989bed4d759b44cf9df65285fd8a81c',
    'dtbo.img': 'cd17e67cea603904cbca3cb35e43ab3d9cde3d85f4622cfbd18f8ff099cc95bd',
}
MODULES = ('sec_tsp_log', 'sec_common_fn', 'sec_cmd', 'sec_secure_touch',
           'sec_tclm_v2', 'sec_tsp_dumpkey', 'focaltech_ts_ft820x')
REQUESTED = ('sec_tsp_log', 'sec_common_fn', 'sec_cmd', 'focaltech_ts_ft820x')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def modinfo(data):
    if data[:6] != b'\x7fELF\x02\x01' or struct.unpack_from('<H', data, 18)[0] != 183:
        raise ValueError('module must be an uncompressed little-endian AArch64 ELF64')
    off = struct.unpack_from('<Q', data, 40)[0]
    step, count, strings_index = struct.unpack_from('<HHH', data, 58)
    if step < 64 or not count or strings_index >= count or off + step * count > len(data):
        raise ValueError('invalid ELF section table')
    sections = [struct.unpack_from('<IIQQQQIIQQ', data, off + i * step) for i in range(count)]
    s = sections[strings_index]
    names = data[s[4]:s[4]+s[5]]
    for section in sections:
        name = names[section[0]:].split(b'\0', 1)[0]
        if name == b'.modinfo':
            result = {}
            for item in data[section[4]:section[4]+section[5]].split(b'\0'):
                if b'=' in item:
                    key, value = item.decode('utf-8').split('=', 1)
                    result.setdefault(key, []).append(value)
            result['_has_versions'] = any(
                names[s[0]:].split(b'\0', 1)[0] == b'__versions' and s[5] > 0
                for s in sections)
            return result
    raise ValueError('ELF has no .modinfo section')


def canonical(name):
    return Path(name).name.removesuffix('.ko').replace('-', '_')


def find_one(directory, name, required=True):
    direct = directory / name
    found = [direct] if direct.is_file() else sorted(directory.rglob(name))
    if len(found) == 1:
        return found[0]
    if not required and not found:
        return None
    raise ValueError(f'need exactly one {name} in {directory}; found {len(found)}')


def ordered(graph, roots):
    result, active = [], set()
    def visit(name):
        if name in active:
            raise ValueError(f'module dependency cycle at {name}')
        if name in result:
            return
        if name not in graph:
            raise ValueError(f'missing module dependency: {name}')
        active.add(name)
        for dep in graph[name]:
            visit(dep)
        active.remove(name)
        result.append(name)
    for root in roots:
        visit(root)
    return result


def module_plan(directory):
    """Validate all inputs before returning the bytes to install."""
    directory = Path(directory).expanduser().resolve()
    blobs, infos, graph = {}, {}, {}
    for name in MODULES:
        data = find_one(directory, name + '.ko').read_bytes()
        info = modinfo(data)
        version = info.get('vermagic', [''])[0]
        if not version or version.split()[0] not in MODULE_RELEASES:
            raise ValueError(f'{name}: wrong vermagic {version!r}; expected DYE1 / build 1570070')
        # The matching stock vendor_boot sec_class.ko uses the non-qgki release.
        # Linux 5.4 same_magic skips the release word only when CRCs are present;
        # no --force / ignored version magic is used by the TWRP loader.
        if version.split()[0] != RELEASE:
            if 'modversions' not in version.split() or not info['_has_versions']:
                raise ValueError(f'{name}: differing release without module symbol-version CRCs')
        if info.get('name', [name])[0].replace('-', '_') != name:
            raise ValueError(f'{name}: ELF module name mismatch')
        if 'depends' not in info:
            raise ValueError(f'{name}: missing depends= metadata')
        deps = [canonical(x) for x in info['depends'][0].split(',') if x]
        blobs[name + '.ko'], infos[name], graph[name] = data, info, deps
    vermagics = {x['vermagic'][0] for x in infos.values()}
    if len(vermagics) != 1:
        raise ValueError('the seven modules have inconsistent vermagic flags')
    # Cross-check stock metadata, allowing its transitive dependency lists.
    dep_file = find_one(directory, 'modules.dep', required=False)
    if dep_file:
        dep_table = {}
        for line in dep_file.read_text().splitlines():
            if ':' in line and not line.lstrip().startswith('#'):
                name, deps = line.split(':', 1)
                dep_table[canonical(name)] = [canonical(x) for x in deps.split()]
        for name in MODULES:
            if name not in dep_table or not set(graph[name]) <= set(dep_table[name]):
                raise ValueError(f'{name}: modules.dep disagrees with ELF depends=')
            graph[name] = list(dict.fromkeys(graph[name] + dep_table[name]))
    softdeps = set()
    for name, info in infos.items():
        for value in info.get('softdep', []):
            softdeps.add('softdep ' + name + ' ' + value)
    soft_file = find_one(directory, 'modules.softdep', required=False)
    if soft_file:
        for line in soft_file.read_text().splitlines():
            tokens = line.split()
            if len(tokens) >= 4 and tokens[0] == 'softdep' and canonical(tokens[1]) in MODULES:
                softdeps.add(' '.join(tokens))
    for line in sorted(softdeps):
        tokens = line.split()
        name, state = canonical(tokens[1]), ''
        for token in tokens[2:]:
            if token in ('pre:', 'post:'):
                state = token
            else:
                dep = canonical(token)
                if dep not in graph or not state:
                    raise ValueError(f'unresolved soft dependency: {line}')
                if state == 'pre:' and dep not in graph[name]:
                    graph[name].append(dep)
    all_order = ordered(graph, MODULES)
    load_order = ordered(graph, REQUESTED)
    aliases = {f'alias {alias} {name}' for name, info in infos.items() for alias in info.get('alias', [])}
    alias_file = find_one(directory, 'modules.alias', required=False)
    if alias_file:
        for line in alias_file.read_text().splitlines():
            tokens = line.split()
            if len(tokens) == 3 and tokens[0] == 'alias' and canonical(tokens[2]) in MODULES:
                aliases.add(' '.join(tokens))
    dep_lines = [name + '.ko:' + ''.join(' ' + x + '.ko' for x in graph[name]) for name in all_order]
    for name, text in {
        'modules.dep': '\n'.join(dep_lines) + '\n',
        'modules.alias': '\n'.join(sorted(aliases)) + '\n',
        'modules.softdep': '\n'.join(sorted(softdeps)) + '\n',
        # Touch needs second-stage services; TWRP generates modules.load.twrp.
        'modules.load': '',
        'modules.load.recovery': '',
    }.items():
        blobs[name] = text.encode()
    report = dict(release=RELEASE, vermagic=next(iter(vermagics)), requested=list(REQUESTED),
                  load_order=load_order, dependencies=graph,
                  sha256={name: sha(data) for name, data in blobs.items()})
    return blobs, report


def check_prebuilts(directory):
    for name, expected in STOCK_SHA.items():
        if sha((Path(directory) / name).read_bytes()) != expected:
            raise ValueError(f'prebuilt/{name}: not the verified DYE1 stock recovery payload')


def install_modules(device, blobs, report):
    target = Path(device) / 'recovery/root/lib/modules'
    target.mkdir(parents=True, exist_ok=True)
    # This directory is dedicated to the seven touch modules in the original tree.
    unexpected = {p.name for p in target.glob('*.ko')} - {n + '.ko' for n in MODULES} - {'stm_ts.ko'}
    if unexpected:
        raise ValueError(f'refusing to replace module directory with extra modules: {unexpected}')
    for path in target.glob('modules.*'):
        if path.is_file():
            path.unlink()  # discard stale binary depmod indices / load lists
    for name, data in blobs.items():
        (target / name).write_bytes(data)
        (target / name).chmod(0o644)
    old = target / 'stm_ts.ko'
    if old.exists():
        old.unlink()
    (Path(device) / 'tools/t733-modules.json').write_text(json.dumps(report, indent=2) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--device', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--modules-dir', type=Path, default=Path.home() / 't733-work/touch-modules')
    parser.add_argument('--check', action='store_true', help='read inputs without writing files')
    args = parser.parse_args()
    check_prebuilts(args.device / 'prebuilt')
    blobs, report = module_plan(args.modules_dir)
    if not args.check:
        install_modules(args.device, blobs, report)
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, struct.error) as error:
        raise SystemExit('STOP: ' + str(error))
