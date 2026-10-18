#!/usr/bin/env python3
"""Load the frozen transistor-level PFD + nominal routed RC with each CP.

Independent PFD copies drive schematic and extracted pumps: neither copy
sees the other's load. Quiet excluded neighbors, ideal rails and upstream
clock/enable drivers are explicit boundary assumptions, not chip signoff.
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

from characterize_charge_pump import bind

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]


def extract_pfd(frozen, library, output):
    netlist = frozen / 'nl/pll_digital.nl.v'
    spef = frozen / 'spef/nom/pll_digital.nom.spef'
    text = spef.read_text()
    if '*C_UNIT 1 PF' not in text or '*R_UNIT 1 OHM' not in text:
        raise ValueError('unexpected SPEF units')
    names = {name.replace('\\', ''): key for key, name in
             re.findall(r'^(\*\d+) (\S+)$', text, re.M)}
    cells = []
    for model, name, body in re.findall(
            r'(sg13cmos5l_\w+)\s+\\(pfd_i\.\S+)\s+\((.*?)\);', netlist.read_text(), re.S):
        pins = {p: n.strip().lstrip('\\') for p, n in re.findall(r'\.(\w+)\(([^)]+)\)', body)}
        cells.append((model, name, pins))
    if len(cells) != 7 or sorted(c[0] for c in cells) != sorted([
            'sg13cmos5l_inv_2', 'sg13cmos5l_a21oi_1', 'sg13cmos5l_a21oi_1',
            'sg13cmos5l_dfrbpq_2', 'sg13cmos5l_dfrbpq_2',
            'sg13cmos5l_tiehi', 'sg13cmos5l_tiehi']):
        raise ValueError('frozen PFD topology changed; review this experiment')
    pfd_ids = {names[name] for _, name, _ in cells}
    sections = [s for s in re.findall(r'\*D_NET .*?\*END', text, re.S)
                if any(re.search(r'^\*I ' + re.escape(key) + ':', s, re.M) for key in pfd_ids)]
    pin_nets = {pin: section.split()[1] for section in sections
                for pin in re.findall(r'^\*I (\S+) ', section, re.M)}
    for _, name, pins in cells:
        for pin, net in pins.items():
            if pin_nets.get(names[name] + ':' + pin) != names[net]:
                raise ValueError(f'netlist/SPEF disagree at {name}:{pin}')
    nodes = {'ref_clk': 'ref', 'up': 'up', 'down': 'down', 'feedback_clk': 'feedback_port'}
    # Drive feedback/enable at the actual upstream driver pin, not an open
    # output port. Their upstream logic/delay is outside this CP experiment.
    for section in sections:
        outputs = re.findall(r'^\*I (\*\d+):(\S+) O ', section, re.M)
        for instance, pin in outputs:
            if instance not in pfd_ids:
                nodes[f'{instance}:{pin}'] = 'fb' if '*P feedback_clk O' in section else 'enabled'
        for row in section.split('*RES\n')[1].split('*END')[0].splitlines():
            for node in row.split()[1:3]:
                nodes.setdefault(node, f'n{len(nodes)}')
    if {'fb', 'enabled'} - set(nodes.values()) or len(sections) != 10:
        raise ValueError('unexpected PFD RC boundary')
    lines = ['* Frozen PFD; nominal routed RC, excluded neighbors quiet/grounded.',
             '.subckt pfd_driver ref fb enabled up down VDD VSS']
    seen = set()
    for section in sections:
        for row in section.split('*CAP\n')[1].split('*RES\n')[0].splitlines():
            fields = row.split()
            key = (tuple(sorted(fields[1:-1])), fields[-1])
            if key in seen or not float(fields[-1]):
                continue
            seen.add(key)
            a = nodes.get(fields[1], 'VSS')
            b = nodes.get(fields[2], 'VSS') if len(fields) == 4 else 'VSS'
            if a == b:
                raise ValueError('selected coupling has neither endpoint')
            lines.append(f'C{len(lines)} {a} {b} {fields[-1]}p')
        for row in section.split('*RES\n')[1].split('*END')[0].splitlines():
            _, a, b, value = row.split()
            lines.append(f'R{len(lines)} {nodes[a]} {nodes[b]} {value}')
    lib = library.read_text()
    for model, name, pins in cells:
        order = re.search(r'^\.subckt ' + model + r' ([^\n]+)', lib, re.M | re.I)[1].split()
        terminals = [p if p in ('VDD', 'VSS') else nodes[names[name] + ':' + p] for p in order]
        lines.append(f'X{len(lines)} {" ".join(terminals)} {model}')
    lines.append('.ends pfd_driver')
    (output / 'pfd_driver.spice').write_text('\n'.join(lines) + '\n')
    return {'netlist_sha256': hashlib.sha256(netlist.read_bytes()).hexdigest(),
            'spef_sha256': hashlib.sha256(spef.read_bytes()).hexdigest(),
            'stdcell_spice_sha256': hashlib.sha256(library.read_bytes()).hexdigest(),
            'cells': [{'model': m, 'instance': n, 'pins': p} for m, n, p in cells],
            'selected_rc_nets': len(sections)}


def integrate(rows, column):
    return sum((b[0] - a[0]) * (a[column] + b[column]) / 2 for a, b in zip(rows, rows[1:]))


def edges(rows, column, level, rising):
    times = []
    for a, b in zip(rows, rows[1:]):
        hit = a[column] < level <= b[column] if rising else a[column] >= level > b[column]
        if hit:
            times.append(a[0] + (b[0] - a[0]) * (level - a[column]) / (b[column] - a[column]))
    return times


def pulse_metrics(rows, column, vdd):
    rises, falls = edges(rows, column, vdd / 2, True), edges(rows, column, vdd / 2, False)
    widths = [next(f - r for f in falls if f > r) for r in rises if any(f > r for f in falls)]
    r20, r80 = edges(rows, column, .2 * vdd, True), edges(rows, column, .8 * vdd, True)
    f80, f20 = edges(rows, column, .8 * vdd, False), edges(rows, column, .2 * vdd, False)
    return {'high_widths_ps': [v * 1e12 for v in widths],
            'rise_20_80_ps': [(b - a) * 1e12 for a, b in zip(r20, r80)],
            'fall_80_20_ps': [(b - a) * 1e12 for a, b in zip(f80, f20)],
            'peak_V': max(r[column] for r in rows), 'final_V': rows[-1][column]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('reference', type=Path)
    parser.add_argument('pex', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--smoke', action='store_true', help='nominal center-voltage three-phase preflight')
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    pdk = Path(os.environ.get('PDK_ROOT', '/foss/pdks')) / 'ihp-sg13cmos5l'
    library = pdk / 'libs.ref/sg13cmos5l_stdcell/spice/sg13cmos5l_stdcell.spice'
    manifest = extract_pfd(REPO / 'macros/pll_digital/frozen/v1', library, output)
    manifest.update(reference_sha256=hashlib.sha256(args.reference.read_bytes()).hexdigest(),
                    pex_sha256=hashlib.sha256(args.pex.read_bytes()).hexdigest(),
                    assumptions='nominal routed RC; quiet excluded neighbors; ideal rails and upstream clock/enable drivers; 100 MHz')
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    base = bind(args.reference, 'charge_pump', 'b').replace(' up ', ' up_b ').replace(' down ', ' down_b ')
    pex = bind(args.pex, 'charge_pump_pex', 'p').replace(' up ', ' up_p ').replace(' down ', ' down_p ')
    pvts = [('tt', 1.2, 27)] if args.smoke else [('tt', 1.2, 27), ('ss', 1.08, 125), ('ff', 1.32, -40)]
    phases = [-500, 0, 500] if args.smoke else [-2000, -500, -100, -50, -25, 0, 25, 50, 100, 500, 2000]
    vctrls = [.7] if args.smoke else [.5, .7, .9]
    slews = [20] if args.smoke else [20, 150]
    results = []
    env = dict(os.environ, SPICE_USERINIT_DIR=str(pdk / 'libs.tech/ngspice'))
    for (corner, vdd, temp), vctrl, slew, phase in itertools.product(pvts, vctrls, slews, phases):
        tag = f'{corner}_v{vctrl}_e{slew}_phase{phase}'
        data = output / f'{tag}.dat'
        deck = output / f'{tag}.cir'
        deck.write_text(f'''Frozen loaded PFD versus schematic and CIC charge pumps
.lib {pdk}/libs.tech/ngspice/models/cornerMOSlv.lib mos_{corner}
.include {library}
.include {output / 'pfd_driver.spice'}
.include {args.reference.resolve()}
.include {args.pex.resolve()}
VSUP vdd 0 {vdd}
VEN enabled 0 PWL(0 0 2n 0 2.02n {vdd})
VREF ref 0 PULSE(0 {vdd} 10n {slew}p {slew}p 4n 10n)
VFB fb 0 PULSE(0 {vdd} {10 + phase / 1000}n {slew}p {slew}p 4n 10n)
XDB ref fb enabled up_b down_b vdd 0 pfd_driver
XDP ref fb enabled up_p down_p vdd 0 pfd_driver
IREF_B 0 iref_b 2u
IREF_P 0 iref_p 2u
VCLAMP clamp 0 {vctrl}
VSENSE_B out_b clamp 0
VSENSE_P out_p clamp 0
XBASE {base}
XPEX {pex}
.temp {temp}
.control
set num_threads=1
set wr_singlescale
set wr_vecnames
tran 2p 28n
wrdata {data} i(VSENSE_B) i(VSENSE_P) v(up_b) v(down_b) v(up_p) v(down_p)
quit
.endc
.end
''')
        with (output / f'{tag}.log').open('w') as log:
            subprocess.run(['ngspice', '-b', str(deck)], env=env, stdout=log,
                           stderr=subprocess.STDOUT, check=True)
        rows = [[float(v) for v in line.split()] for line in data.read_text().splitlines()[1:]]
        if not rows or rows[-1][0] < 27.99e-9 or any(len(r) != 7 or not all(map(math.isfinite, r)) for r in rows):
            raise ValueError(f'incomplete transient: {tag}')
        quiet = [r for r in rows if 15e-9 <= r[0] <= 17e-9]
        window = [r for r in rows if 17e-9 <= r[0] <= 27e-9]
        record = dict(corner=corner, vdd_V=vdd, temperature_C=temp, vctrl_V=vctrl,
                      input_edge_ps=slew, feedback_minus_reference_ps=phase)
        for label, current, up in [('schematic', 1, 3), ('layout', 2, 5)]:
            leakage = integrate(quiet, current) / (quiet[-1][0] - quiet[0][0])
            record[label] = {'net_charge_fC': (integrate(window, current) - leakage * (window[-1][0] - window[0][0])) * 1e15,
                             'quiet_current_A': leakage,
                             'peak_abs_current_A': max(abs(r[current]) for r in window),
                             'UP': pulse_metrics(window, up, vdd), 'DOWN': pulse_metrics(window, up + 1, vdd)}
            if max(window[-1][up:up + 2]) > .1 * vdd:
                raise ValueError(f'PFD did not reset: {tag} {label}')
        record['charge_change_fC'] = record['layout']['net_charge_fC'] - record['schematic']['net_charge_fC']
        results.append(record)
        (output / 'summary.json').write_text(json.dumps(results, indent=2) + '\n')
        print(tag, 'Q(fC)', round(record['schematic']['net_charge_fC'], 4),
              round(record['layout']['net_charge_fC'], 4), flush=True)
    with (output / 'charge.csv').open('w') as stream:
        writer = csv.writer(stream)
        writer.writerow(['corner', 'VDD_V', 'temperature_C', 'VCTRL_V', 'edge_ps', 'phase_ps', 'Q_schematic_fC', 'Q_layout_fC', 'change_fC'])
        for r in results:
            writer.writerow([r['corner'], r['vdd_V'], r['temperature_C'], r['vctrl_V'], r['input_edge_ps'],
                             r['feedback_minus_reference_ps'], r['schematic']['net_charge_fC'],
                             r['layout']['net_charge_fC'], r['charge_change_fC']])


if __name__ == '__main__':
    main()
