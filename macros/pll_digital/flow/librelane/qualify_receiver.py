#!/usr/bin/env python3
"""Probe the routed receiver with the schematic VCO, not a complete PLL PEX.

Run inside the initialized IIC container. Outputs are diagnostic evidence;
passing is not an acquisition-envelope, jitter, or asynchronous-reset signoff.
"""

import argparse
import json
import os
from pathlib import Path
import re
import subprocess


def extract_receiver(run, output):
    spef = run / 'final/spef/nom/pll_digital.nom.spef'
    text = spef.read_text()
    assert '*C_UNIT 1 PF' in text and '*R_UNIT 1 OHM' in text
    names = {name.replace('\\', ''): key for key, name in
             re.findall(r'^(\*\d+) (\S+)$', text, re.M)}

    def instance(prefix):
        matches = [key for name, key in names.items() if name.startswith(prefix)]
        assert len(matches) == 1, (prefix, matches)
        return matches[0]

    ff = names['output_divider_i.div2_ff']
    chained = any('vco_input_buffer.input_inverter' in name for name in names)
    ports = {'vco_clk': 'vco_in', ff + ':CLK': 'ff_clk',
             ff + ':Q_N': 'ff_qn', ff + ':D': 'ff_d',
             ff + ':Q': 'ff_q', 'pll_clk': 'pll_port'}
    if chained:
        first = instance('output_divider_i.vco_input_buffer.input_inverter')
        last = instance('output_divider_i.vco_input_buffer.output_inverter')
        ports.update({first + ':A': 'input_a', first + ':Y': 'input_y',
                      last + ':A': 'drive_a', last + ':Y': 'drive_y'})
        devices = ['XINPUT input_y input_a VDD 0 sg13cmos5l_inv_4',
                   'XDRIVE drive_y drive_a VDD 0 sg13cmos5l_inv_16']
    else:
        buf = names['output_divider_i.vco_input_buffer']
        ports.update({buf + ':A': 'input_a', buf + ':X': 'drive_y'})
        devices = ['XINPUT drive_y input_a VDD 0 sg13cmos5l_buf_16']

    sections = re.findall(r'\*D_NET .*?\*END', text, re.S)
    qnet, = [s for s in sections if f'*I {ff}:Q O ' in s]
    loads = re.findall(r'^\*I (\*\d+:\S+) I \*D (\S+)', qnet, re.M)
    assert len(loads) == 2, loads
    for i, (pin, cell) in enumerate(loads):
        assert cell == 'sg13cmos5l_buf_16', cell
        ports[pin] = f'load_{i}'
        devices.extend([f'XLOAD{i} load_out_{i} load_{i} VDD 0 {cell}',
                        f'CLOAD{i} load_out_{i} 0 20f'])

    selected = [s for s in sections if any(
        re.search(r'^\*[IP] ' + re.escape(pin) + r' [IO] ', s, re.M)
        for pin in ports)]
    assert len(selected) == (5 if chained else 4), len(selected)
    nodes = dict(ports)
    for section in selected:
        for row in section.split('*RES\n')[1].split('*END')[0].splitlines():
            for node in row.split()[1:3]:
                if node not in nodes:
                    nodes[node] = f'n{len(nodes)}'
    lines = [f'* Nominal routed RC from {spef}',
             '* Unmodeled neighboring coupling is grounded.',
             '.subckt receiver_rc ' + ' '.join(ports.values())]
    seen_caps = set()
    for section in selected:
        for row in section.split('*CAP\n')[1].split('*RES\n')[0].splitlines():
            fields = row.split()
            a = nodes.get(fields[1], '0')
            b = nodes.get(fields[2], '0') if len(fields) == 4 else '0'
            key = (tuple(sorted(fields[1:-1])), fields[-1])
            if float(fields[-1]) and key not in seen_caps:
                assert a != '0' or b != '0'
                lines.append(f'C{len(lines)} {a} {b} {fields[-1]}p')
                seen_caps.add(key)
        for row in section.split('*RES\n')[1].split('*END')[0].splitlines():
            _, a, b, value = row.split()
            lines.append(f'R{len(lines)} {nodes[a]} {nodes[b]} {value}')
    lines.append('.ends receiver_rc')
    rc = output / 'receiver_rc.spice'
    rc.write_text('\n'.join(lines) + '\n')
    return ['XROUTES ' + ' '.join(ports.values()) + ' receiver_rc', *devices]


def crossings(rows, column, threshold, rising):
    result = []
    for a, b in zip(rows, rows[1:]):
        if (a[column] < threshold <= b[column]) if rising else (a[column] >= threshold > b[column]):
            result.append(a[0] + (threshold - a[column]) *
                          (b[0] - a[0]) / (b[column] - a[column]))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    pdk = Path(os.environ['PDK_ROOT']) / os.environ['PDK']
    devices = extract_receiver(args.run.resolve(), output)
    repo = Path(__file__).resolve().parents[4]
    ring = (repo / 'macros/pll_analog/netlist/schematic/ring_oscillator.spice').read_text()
    assert '**.subckt ring_oscillator VDD VCO_OUT VCTRL VSS' in ring
    ring = ring.replace('**.subckt', '.subckt').replace('**.ends', '.ends')
    ring = re.sub(r'^\.end\s*$', '', ring, flags=re.M)
    (output / 'ring.spice').write_text(ring)
    results = []
    for corner, supply, temp, ctrl in [('tt', 1.2, 27, .55),
                                       ('ff', 1.32, -40, .50),
                                       ('ss', 1.08, 125, .5825)]:
        deck = output / f'{corner}.cir'
        data = output / f'{corner}.dat'
        deck.write_text('\n'.join([
            'Routed receiver with schematic VCO; nominal RC and quiet neighbors',
            f'.lib {pdk}/libs.tech/ngspice/models/cornerMOSlv.lib mos_{corner}',
            f'.include {pdk}/libs.ref/sg13cmos5l_stdcell/spice/sg13cmos5l_stdcell.spice',
            f'.include {output}/ring.spice', f'.include {output}/receiver_rc.spice',
            f'VSUPPLY VDD 0 {supply}', f'VCONTROL vctrl 0 {ctrl}',
            f'VRESET reset_b 0 PWL(0 0 1n 0 1.02n {supply})',
            'XRO VDD vco_in vctrl 0 ring_oscillator', *devices,
            'XFF ff_q ff_qn ff_clk ff_d reset_b VDD 0 sg13cmos5l_dfrbp_2',
            'C_PORT pll_port 0 5f',
            f'.ic v(XRO.VCO_CORE)=0 v(XRO.net1)={supply} v(XRO.net2)=0',
            f'.options temp={temp}', '.control', 'set wr_singlescale',
            'set wr_vecnames', 'save v(vco_in) v(ff_clk) v(ff_q) v(ff_d)',
            'tran 0.5p 30n uic',
            f'wrdata {data} v(vco_in) v(ff_clk) v(ff_q) v(ff_d)',
            'quit', '.endc', '.end', '']))
        with (output / f'{corner}.log').open('w') as log:
            subprocess.run(['ngspice', '-b', str(deck)], stdout=log,
                           stderr=subprocess.STDOUT, check=True)
        rows = [list(map(float, row.split())) for row in data.read_text().splitlines()[1:]]
        rows = [row for row in rows if row[0] >= 20e-9]
        result = {'corner': corner, 'supply_V': supply, 'temperature_C': temp,
                  'vctrl_V': ctrl}
        periods = []
        for column, name in enumerate(['vco', 'ff_clk', 'q', 'd'], 1):
            rises = crossings(rows, column, supply / 2, True)
            falls = crossings(rows, column, supply / 2, False)
            highs = [next(f - r for f in falls if f > r) for r in rises if falls and r < falls[-1]]
            lows = [next(r - f for r in rises if r > f) for f in falls if rises and f < rises[-1]]
            period = (rises[-1] - rises[0]) / (len(rises) - 1) if len(rises) > 1 else None
            periods.append(period)
            result[name] = dict(min_V=min(row[column] for row in rows),
                                max_V=max(row[column] for row in rows), rises=len(rises),
                                frequency_GHz=1e-9 / period if period else None,
                                min_high_ps=min(highs) * 1e12 if highs else None,
                                min_low_ps=min(lows) * 1e12 if lows else None)
        result['passes_division'] = (all(periods) and
            abs(periods[2] / periods[0] - 2) < .01 and
            result['q']['min_V'] < .2 * supply and result['q']['max_V'] > .8 * supply)
        results.append(result)
        print(json.dumps(result), flush=True)
    (output / 'summary.json').write_text(json.dumps(results, indent=2) + '\n')
    if not all(result['passes_division'] for result in results):
        raise SystemExit('Receiver failed division/swing; inspect summary.json and waveforms.')


if __name__ == '__main__':
    main()
