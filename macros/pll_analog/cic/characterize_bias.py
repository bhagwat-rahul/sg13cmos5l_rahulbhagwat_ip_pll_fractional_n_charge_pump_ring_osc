#!/usr/bin/env python3
"""Compare schematic and extracted bias-cell DC behavior; not PLL signoff."""

import argparse
import csv
import json
import os
from pathlib import Path
import re
import subprocess


def bind(path, cell, output_node):
    text = path.read_text()
    ports = re.search(rf'^\.subckt\s+{cell}\s+([^\n]+)', text, re.M | re.I)[1].split()
    nodes = {'VDD': 'vdd', 'VSS': '0', 'VCTRL': 'ctrl', 'VBP': output_node}
    if set(ports) != set(nodes) or len(ports) != 4:
        raise ValueError(f'unexpected bias-cell interface: {ports}')
    return ' '.join(nodes[p] for p in ports) + ' ' + cell


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('reference', type=Path)
    parser.add_argument('pex', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    pdk = Path(os.environ.get('PDK_ROOT', '/foss/pdks')) / 'ihp-sg13cmos5l'
    env = dict(os.environ, SPICE_USERINIT_DIR=str(pdk / 'libs.tech/ngspice'))
    metrics = []
    for corner, vdd, temp in [('tt', 1.2, 27), ('ss', 1.08, 125), ('ff', 1.32, -40)]:
        tag = f'{corner}_{vdd}_{temp}'
        data = output / f'{tag}.dat'
        deck = output / f'{tag}.cir'
        deck.write_text(f'''Bias CIC versus schematic DC screening
.lib {pdk}/libs.tech/ngspice/models/cornerMOSlv.lib mos_{corner}
.include {args.reference.resolve()}
.include {args.pex.resolve()}
VSUP vdd 0 {vdd}
VCTRL ctrl 0 0
XBASE {bind(args.reference, 'vco_bias', 'base')}
XPEX {bind(args.pex, 'vco_bias_pex', 'layout')}
.temp {temp}
.control
set wr_singlescale
set wr_vecnames
dc VCTRL 0.1 {vdd - 0.1} 0.01
wrdata {data} v(base) v(layout)
quit
.endc
.end
''')
        with (output / f'{tag}.log').open('w') as log:
            subprocess.run(['ngspice', '-b', str(deck)], env=env,
                           stdout=log, stderr=subprocess.STDOUT, check=True)
        rows = [[float(v) for v in line.split()] for line in data.read_text().splitlines()[1:]]
        if len(rows) < 80 or not all(0 <= v <= vdd for row in rows for v in row[1:]):
            raise ValueError(f'incomplete or out-of-range DC response: {tag}')
        with (output / f'{tag}.csv').open('w') as stream:
            writer = csv.writer(stream)
            writer.writerow(['VCTRL_V', 'VBP_schematic_V', 'VBP_PEX_V'])
            writer.writerows(rows)
        metrics.append({'corner': corner, 'vdd_V': vdd, 'temperature_C': temp,
                        'points': len(rows),
                        'max_abs_VBP_difference_V': max(abs(r[1] - r[2]) for r in rows)})
    (output / 'summary.json').write_text(json.dumps(metrics, indent=2) + '\n')
    print(json.dumps(metrics, indent=2))


if __name__ == '__main__':
    main()
