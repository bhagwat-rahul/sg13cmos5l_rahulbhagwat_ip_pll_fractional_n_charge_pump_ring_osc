#!/usr/bin/env python3
"""Replayable schematic/PEX CP compliance and switching screening.

The two circuits have independent bias and current-sense branches. Interfaces
are bound by name. These ideal-supply tests do not establish substrate/ESD/EM
qualification or closed-loop PLL jitter.
"""

import argparse
import csv
import hashlib
import itertools
import json
import math
import os
from pathlib import Path
import re
import subprocess


def bind(path, cell, suffix):
    ports = re.search(rf'^\.subckt\s+{cell}\s+([^\n]+)', path.read_text(), re.M | re.I)[1].split()
    nets = {'VDD': 'vdd', 'VSS': '0', 'UP': 'up', 'DOWN': 'down',
            'IREF': f'iref_{suffix}', 'VCTRL': f'out_{suffix}'}
    if set(ports) != set(nets) or len(ports) != 6:
        raise ValueError(f'unexpected CP interface: {ports}')
    return ' '.join(nets[p] for p in ports) + ' ' + cell


def read_data(path):
    rows = [[float(v) for v in line.split()] for line in path.read_text().splitlines()[1:]]
    if not rows or any(len(r) != 3 or not all(math.isfinite(v) for v in r) for r in rows):
        raise ValueError(f'incomplete simulator output: {path}')
    with path.with_suffix('.csv').open('w') as stream:
        writer = csv.writer(stream)
        writer.writerow(['sweep_V_or_time_s', 'I_schematic_A', 'I_PEX_A'])
        writer.writerows(rows)
    return rows


def device_only_control(path, output):
    """Diagnostic only: retain extracted MOS junction geometry, remove wire RC.

    Collapse each resistor-connected component, preserving external port names.
    This is not an LVS reference or a replacement for the full PEX simulation.
    """
    lines = path.read_text().splitlines()
    parents = {}

    def root(node):
        parents.setdefault(node, node)
        if parents[node] != node:
            parents[node] = root(parents[node])
        return parents[node]

    for line in lines:
        fields = line.split()
        if fields and fields[0][0].upper() == 'R':
            a, b = fields[1:3]
            parents[root(a)] = root(b)
    ports = re.search(r'^\.subckt\s+\S+\s+([^\n]+)', path.read_text(), re.M | re.I)[1].split()
    names = {}
    for port in ports:
        component = root(port)
        if component in names:
            raise ValueError('PEX shorts external ports')
        names[component] = port
    result = []
    for line in lines:
        fields = line.split()
        if fields and fields[0][0].upper() in ('R', 'C'):
            continue
        if fields and fields[0][0].upper() == 'X':
            fields[1:5] = [names.get(root(n), root(n)) for n in fields[1:5]]
            line = ' '.join(fields)
        result.append(line)
    output.write_text('\n'.join(result) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('reference', type=Path)
    parser.add_argument('pex', type=Path)
    parser.add_argument('--capacitance-only', type=Path,
                        help='same-layout no-extresist extraction for capacitance bookkeeping control')
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    pdk = Path(os.environ.get('PDK_ROOT', '/foss/pdks')) / 'ihp-sg13cmos5l'
    env = dict(os.environ, SPICE_USERINIT_DIR=str(pdk / 'libs.tech/ngspice'))
    supply_nodes = sorted(set(re.findall(r'\b(?:VDD|VSS)\.[tn][0-9]+\b', args.pex.read_text())))
    if not supply_nodes:
        raise ValueError('no extracted supply fragments to screen')
    supply_vectors = ' '.join(f'v(xpex.{node})' for node in supply_nodes)

    def supply_drop(path, vdd):
        rows = [[float(v) for v in line.split()] for line in path.read_text().splitlines()[1:]]
        if not rows or any(len(r) != len(supply_nodes) + 1 or
                           not all(math.isfinite(v) for v in r) for r in rows):
            raise ValueError(f'incomplete supply screening: {path}')
        return {rail + '_max_abs_deviation_V': max(
            abs(row[index + 1] - (vdd if rail == 'VDD' else 0))
            for row in rows for index, node in enumerate(supply_nodes) if node.startswith(rail))
                for rail in ('VDD', 'VSS')}

    def run(tag, corner, vdd, temp, controls, analysis, pex_path=args.pex):
        deck = output / f'{tag}.cir'
        deck.write_text(f'''CP schematic versus CIC PEX
.lib {pdk}/libs.tech/ngspice/models/cornerMOSlv.lib mos_{corner}
.include {args.reference.resolve()}
.include {pex_path.resolve()}
VSUP vdd 0 {vdd}
IREF_B 0 iref_b 2u
IREF_P 0 iref_p 2u
VSENSE_B out_b clamp 0
VSENSE_P out_p clamp 0
XBASE {bind(args.reference, 'charge_pump', 'b')}
XPEX {bind(pex_path, 'charge_pump_pex', 'p')}
{controls}
.temp {temp}
.control
set wr_singlescale
set wr_vecnames
{analysis}
quit
.endc
.end
''')
        with (output / f'{tag}.log').open('w') as log:
            subprocess.run(['ngspice', '-b', str(deck)], env=env,
                           stdout=log, stderr=subprocess.STDOUT, check=True)

    metrics = []
    for corner, vdd, temp in itertools.product(('tt', 'ss', 'ff', 'sf', 'fs'),
                                              (1.08, 1.20, 1.32), (-40, 27, 125)):
        tag = f'{corner}_{vdd}_{temp}'
        analysis = []
        for mode, up, down in [('up', vdd, 0), ('down', 0, vdd), ('off', 0, 0), ('both', vdd, vdd)]:
            analysis += [f'alter VUP={up}', f'alter VDOWN={down}',
                         f'dc VCLAMP 0.1 {vdd - 0.1} 0.01',
                         f'wrdata {output / (tag + "_" + mode + ".dat")} i(VSENSE_B) i(VSENSE_P)']
        supply_data = output / f'{tag}_supply.dat'
        analysis.append(f'wrdata {supply_data} {supply_vectors}')
        run(tag, corner, vdd, temp, 'VUP up 0 0\nVDOWN down 0 0\nVCLAMP clamp 0 0',
            '\n'.join(analysis))
        result = {'corner': corner, 'vdd_V': vdd, 'temperature_C': temp,
                  'both_on_supply_drop': supply_drop(supply_data, vdd)}
        for mode in ('up', 'down', 'off', 'both'):
            rows = read_data(output / f'{tag}_{mode}.dat')
            if len(rows) < 80:
                raise ValueError(f'incomplete compliance sweep: {tag} {mode}')
            region = [r for r in rows if 0.5 - 1e-6 <= r[0] <= 0.9 + 1e-6]
            result[mode] = {'max_abs_current_change_A': max(abs(r[1] - r[2]) for r in region),
                            'max_abs_PEX_current_A': max(abs(r[2]) for r in region)}
            if mode in ('up', 'down'):
                sign = 1 if mode == 'up' else -1
                if not all(sign * r[1] > 0 and sign * r[2] > 0 for r in region):
                    raise ValueError(f'incorrect pump-current polarity: {tag} {mode}')
                result[mode]['max_relative_current_change'] = max(abs((r[2] - r[1]) / r[1]) for r in region)
        metrics.append(result)

    device_control = output / 'charge_pump_devices_only.spice'
    device_only_control(args.pex, device_control)
    pulse_results = {}
    transient_supply = None
    controls = [('full_rc', args.pex), ('devices_only', device_control)]
    if args.capacitance_only:
        controls.append(('capacitance_only', args.capacitance_only))
    for label, pex_path in controls:
        tag = f'tt_1.2_27_pulses_{label}'
        data = output / f'{tag}.dat'
        analysis = f'tran 10p 100n\nwrdata {data} i(VSENSE_B) i(VSENSE_P)'
        if label == 'full_rc':
            supply_data = output / f'{tag}_supply.dat'
            analysis += f'\nwrdata {supply_data} {supply_vectors}'
        run(tag, 'tt', 1.2, 27, '''VCLAMP clamp 0 0.7
VUP up 0 PULSE(0 1.2 10n 200p 200p 4n 20n)
VDOWN down 0 PULSE(0 1.2 20n 200p 200p 4n 20n)''',
            analysis, pex_path)
        if label == 'full_rc':
            transient_supply = supply_drop(supply_data, 1.2)
        pulses = read_data(data)
        if pulses[-1][0] < 99e-9:
            raise ValueError('transient did not reach its stop time')
        pulse_charge = []
        for start, stop in [(8e-9, 18e-9), (18e-9, 28e-9), (48e-9, 58e-9), (58e-9, 68e-9)]:
            rows = [r for r in pulses if start <= r[0] <= stop]
            charge = [sum((b[0] - a[0]) * (a[col] + b[col]) / 2 for a, b in zip(rows, rows[1:]))
                      for col in (1, 2)]
            pulse_charge.append({'start_s': start, 'stop_s': stop,
                                 'schematic_charge_C': charge[0], 'PEX_charge_C': charge[1]})
        pulse_results[label] = pulse_charge
    summary = {'dc': metrics, 'nominal_pulse_charge': pulse_results['full_rc'],
               'device_only_control_charge': pulse_results['devices_only'],
               'capacitance_only_control_charge': pulse_results.get('capacitance_only'),
               'nominal_transient_supply_deviation': transient_supply,
               'supply_screening_assumptions': 'ideal external rails; extracted local RC only; no package or substrate model',
               'reference_sha256': hashlib.sha256(args.reference.read_bytes()).hexdigest(),
               'pex_sha256': hashlib.sha256(args.pex.read_bytes()).hexdigest()}
    (output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(f'Completed {len(metrics)} PVT points × 4 states and nominal pulse screening: {output}')


if __name__ == '__main__':
    main()
