#!/usr/bin/env python3
"""Restore CMOM stack parameters omitted by KLayout's W/L-only device export.

Read the actual generated Magic PCell metadata AND metal sections, match its
dimensions to exported devices within one 5-nm grid step, and refuse missing,
ambiguous or conflicting matches. Never modify the raw extraction. This is a
model translation audit, not LVS or a substitute for geometry/device checks.
"""

import argparse
import hashlib
import json
from pathlib import Path
import re
import shlex


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('--magic-dir', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    cells = []
    for path in sorted(args.magic_dir.glob('*.mag')):
        text = path.read_text()
        if not re.search(r'^string gencell cap_cmomf$', text, re.M):
            continue
        line = re.search(r'^string parameters (.*)$', text, re.M)
        if not line:
            raise ValueError(f'missing PCell parameters: {path}')
        words = shlex.split(line[1])
        params = dict(zip(words[::2], words[1::2]))
        minimum, maximum = (int(params[n].removeprefix('metal')) for n in ('mmin', 'mmax'))
        metals = {int(n) for n in re.findall(r'^<< metal(\d+) >>$', text, re.M)}
        if metals != set(range(minimum, maximum + 1)):
            raise ValueError(f'PCell metadata/metal-section mismatch: {path}')
        cells.append((path, params, minimum, maximum))
    source = args.input.read_text()
    logical = re.sub(r'\n\s*\+', ' ', source)
    output, restored = [], []
    for line in logical.splitlines():
        fields = line.split()
        if fields and fields[0][0].lower() == 'x' and 'cap_cmomf' in fields:
            params = dict(f.split('=', 1) for f in fields if '=' in f)
            dimensions = []
            for name in ('w', 'l'):
                value = re.fullmatch(r'([+\-\d.eE]+)([un]?)', params[name], re.I)
                if not value:
                    raise ValueError(f'unsupported dimension: {line}')
                dimensions.append(float(value[1]) * {'': 1e6, 'u': 1., 'n': 1e-3}[value[2].lower()])
            matches = [(p, d, lo, hi) for p, d, lo, hi in cells
                       if all(abs(actual - float(d[n])) <= .0051
                              for n, actual in zip(('w', 'l'), dimensions))]
            stacks = {(lo, hi, int(d.get('subblock', '0'))) for _, d, lo, hi in matches}
            if len(stacks) != 1:
                raise ValueError(f'missing/ambiguous physical CMOM stack: {line}')
            expected = dict(zip(('mmin', 'mmax', 'subblock'), stacks.pop()))
            for name, value in expected.items():
                if name in params:
                    if float(params[name]) != value:
                        raise ValueError(f'conflicting {name}, physical PCell versus model: {line}')
                else:
                    line += f' {name}={value}'
            restored.append({'device': fields[0], 'dimensions_um': dimensions,
                             'stack': expected, 'physical_cells': [str(p) for p, _, _, _ in matches]})
        output.append(line)
    if not restored:
        raise ValueError('no CMOM devices matched; input was not accepted')
    with args.output.open('x') as stream:
        stream.write('* CMOM stack restored from physical PCell metadata and metal sections.\n'
                     + '\n'.join(output) + '\n')
    report = {'input_sha256': hashlib.sha256(args.input.read_bytes()).hexdigest(),
              'output_sha256': hashlib.sha256(args.output.read_bytes()).hexdigest(),
              'devices': restored, 'limitations': __doc__}
    args.output.with_suffix('.stack.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
