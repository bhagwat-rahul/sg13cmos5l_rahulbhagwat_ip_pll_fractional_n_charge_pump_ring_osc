#!/usr/bin/env python3
"""Screen extracted oscillator leaves or the physically assembled ring.

Leaf mode uses ideal inter-leaf wiring; --ring uses complete ring extraction.
Neither is PLL signoff. External rails and the analog/digital boundary wire
are ideal; ring mode includes internal PDN RC.
Supply ramp and an explicit startup kick do not establish noise-only startup.
Reported oscillator supply power excludes receiver power and control-source energy.
"""

import argparse
import hashlib
import itertools
import json
import math
import os
from pathlib import Path
import re
import subprocess

from characterize_charge_pump import device_only_control

HERE = Path(__file__).resolve().parent


def extract_receiver(frozen, library, output):
    """Actual input buffers/div2, five nominal RC nets, two output buffer loads.

    Reset is ideal at the FF pin; downstream buffer outputs are unloaded and
    excluded coupling neighbors are quiet. This is not full digital simulation.
    """
    netlist = frozen / 'nl/pll_digital.nl.v'
    spef = frozen / 'spef/nom/pll_digital.nom.spef'
    text = spef.read_text()
    if '*C_UNIT 1 PF' not in text or '*R_UNIT 1 OHM' not in text:
        raise ValueError('unexpected receiver SPEF units')
    names = {name.replace('\\', ''): key for key, name in
             re.findall(r'^(\*\d+) (\S+)$', text, re.M)}
    cells = {}
    for model, name, body in re.findall(
            r'(sg13cmos5l_\w+)\s+(\S+)\s+\((.*?)\);', netlist.read_text(), re.S):
        pins = {p: n.strip().lstrip('\\') for p, n in re.findall(r'\.(\w+)\(([^)]+)\)', body)}
        cells[name.lstrip('\\')] = (model, pins)
    selected = {n: c for n, c in cells.items() if n.startswith('output_divider_i.vco_input_buffer.')
                or n == 'output_divider_i.div2_ff'}
    if sorted(c[0] for c in selected.values()) != [
            'sg13cmos5l_dfrbp_2', 'sg13cmos5l_inv_16', 'sg13cmos5l_inv_4']:
        raise ValueError('frozen receiver topology changed')
    wanted = {names[net] for _, pins in selected.values() for pin, net in pins.items()
              if pin != 'RESET_B'}
    sections = [s for s in re.findall(r'\*D_NET .*?\*END', text, re.S) if s.split()[1] in wanted]
    if len(sections) != 5:
        raise ValueError('expected five receiver RC nets')
    pin_nets = {pin: s.split()[1] for s in sections for pin in re.findall(r'^\*I (\S+) ', s, re.M)}
    divider = names['output_divider_i.div2_ff']
    nodes = {'vco_clk': 'IN', divider + ':CLK': 'CLK', divider + ':Q': 'DIV2'}
    for s in sections:
        for line in s.split('*RES\n')[1].split('*END')[0].splitlines():
            for node in line.split()[1:3]:
                nodes.setdefault(node, f'n{len(nodes)}')
    loads = {name: cells[name] for name, key in names.items() if name in cells
             and name not in selected and any(p.startswith(key + ':') for p in pin_nets)}
    if len(loads) != 2 or any(c[0] != 'sg13cmos5l_buf_16' for c in loads.values()):
        raise ValueError('unexpected receiver output loads')
    lines = ['* Frozen input/div2; nominal RC, quiet neighbors, ideal reset.',
             '.subckt frozen_receiver IN CLK DIV2 RESET VDD VSS']
    seen = set()
    for s in sections:
        for row in s.split('*CAP\n')[1].split('*RES\n')[0].splitlines():
            f = row.split()
            key = (tuple(sorted(f[1:-1])), f[-1])
            if key in seen or not float(f[-1]):
                continue
            seen.add(key)
            a, b = nodes.get(f[1], 'VSS'), nodes.get(f[2], 'VSS') if len(f) == 4 else 'VSS'
            if a == b:
                raise ValueError('receiver coupling has neither endpoint')
            lines.append(f'C{len(lines)} {a} {b} {f[-1]}p')
        for row in s.split('*RES\n')[1].split('*END')[0].splitlines():
            _, a, b, value = row.split()
            lines.append(f'R{len(lines)} {nodes[a]} {nodes[b]} {value}')
    for name, (model, pins) in (selected | loads).items():
        order, _ = subcircuit(library, model)
        terminals = []
        for pin in order:
            key = names[name] + ':' + pin
            if pin in ('VDD', 'VSS'):
                node = pin
            elif pin == 'RESET_B':
                node = 'RESET'
            elif key in pin_nets:
                if pin_nets[key] != names[pins[pin]]:
                    raise ValueError(f'receiver netlist/SPEF disagree at {name}:{pin}')
                node = nodes[key]
            elif name in loads and pin == 'X':
                node = f'load_{names[name][1:]}_out'
            else:
                raise ValueError(f'unbound receiver pin {name}:{pin}')
            terminals.append(node)
        lines.append(f'X{len(lines)} {" ".join(terminals)} {model}')
    lines.append('.ends frozen_receiver')
    path = output / 'frozen_receiver.spice'
    path.write_text('\n'.join(lines) + '\n')
    return path, {'inputs_sha256': {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                                   for p in (netlist, spef, library)},
                  'cells': selected | loads, 'rc_nets': len(sections),
                  'limitations': extract_receiver.__doc__}


def subcircuit(path, name):
    match = re.search(r'^\.subckt\s+' + re.escape(name) + r'\s+([^\n]+)\n(.*?)^\.ends\b[^\n]*',
                      path.read_text(), re.M | re.S | re.I)
    if not match:
        raise ValueError(f'missing subcircuit {name}: {path}')
    return match[1].split(), match[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for cell in ('inverter', 'vco_bias', 'vco_buffer'):
        parser.add_argument('--' + cell.replace('_', '-'), type=Path)
    parser.add_argument('--ring', type=Path, help='complete ring_oscillator_pex extraction, instead of three leaf files')
    parser.add_argument('--devices-only', action='store_true',
                        help='diagnostic: collapse wire R and remove wire C from --ring, retaining extracted MOS geometry')
    parser.add_argument('--startup-node', help='reviewed VCO_CORE alias in --ring extraction (default: x_buffer.VIN)')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--smoke', action='store_true')
    parser.add_argument('--control-values', type=float, nargs='+',
                        help='explicit VCTRL sweep in volts (default: 0.5 through 0.9)')
    parser.add_argument('--schematic-library', type=Path, default=HERE.parent / 'schematic/xschem')
    parser.add_argument('--corners', nargs='+', choices=('tt', 'ss', 'ff'),
                        help='selected PVT cases; default all three, or TT with --smoke')
    parser.add_argument('--receiver', action='store_true', help='frozen transistor input/div2 with nominal RC, no ideal C load')
    args = parser.parse_args()
    leaves = [getattr(args, c) for c in ('inverter', 'vco_bias', 'vco_buffer')]
    if (args.ring and any(leaves)) or (not args.ring and not all(leaves)):
        parser.error('provide either --ring or all three extracted leaf files')
    if args.startup_node and not args.ring:
        parser.error('--startup-node is only used with --ring')
    if args.devices_only and not args.ring:
        parser.error('--devices-only requires --ring')
    output = args.output.resolve()
    if not output.is_relative_to((HERE.parent / 'layout/build').resolve()):
        parser.error('output must be below macros/pll_analog/layout/build/')
    output.mkdir(parents=True, exist_ok=False)
    original_ring = args.ring.resolve() if args.ring else None
    if args.devices_only:
        args.ring = output / 'ring_devices_only.spice'
        device_only_control(original_ring, args.ring)
    pdk = Path(os.environ.get('PDK_ROOT', '/foss/pdks')) / 'ihp-sg13cmos5l'
    env = dict(os.environ, PDK_ROOT=str(pdk.parent), PDK=pdk.name, PDKPATH=str(pdk),
               STD_CELL_LIBRARY='sg13cmos5l_stdcell', SPICE_USERINIT_DIR=str(pdk / 'libs.tech/ngspice'))
    schematic = args.schematic_library.resolve()
    source = output / 'ring_oscillator.spice'
    command = ('set spiceprefix 1; set lvs_netlist 0; set top_is_subckt 1; '
               'set lvs_ignore 1; set ev_precision 5; '
               f'set netlist_dir {{{output}}}; xschem set netlist_name {{{source.name}}}; xschem netlist')
    with (output / 'xschem.log').open('w') as log:
        subprocess.run(['xschem', '-s', '-r', '-x', '-q', '--rcfile', str(schematic / 'xschemrc'),
                        '--command', command, str(schematic / 'ring_oscillator.sch')],
                       cwd=schematic, env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
    ports, body = subcircuit(source, 'ring_oscillator')
    if set(ports) != {'VDD', 'VCO_OUT', 'VCTRL', 'VSS'} or len(ports) != 4:
        raise ValueError('unexpected ring interface')
    paths = ({'ring_oscillator': args.ring.resolve()} if args.ring else
             {cell: getattr(args, cell).resolve() for cell in ('inverter', 'vco_bias', 'vco_buffer')})
    instances, extracted = [], []
    for line in ([] if args.ring else body.splitlines()):
        fields = line.split()
        if not fields or fields[0].startswith('*'):
            continue
        name, cell = fields[0], fields[-1]
        if cell not in paths or not name.lower().startswith('x'):
            raise ValueError(f'unreviewed ring hierarchy entry: {line}')
        reference_ports, _ = subcircuit(source, cell)
        pex_ports, _ = subcircuit(paths[cell], cell + '_pex')
        if len(fields[1:-1]) != len(reference_ports) or set(pex_ports) != set(reference_ports):
            raise ValueError(f'{cell}: leaf interface mismatch')
        nets = dict(zip(reference_ports, fields[1:-1]))
        extracted.append(f'{name} {" ".join(nets[p] for p in pex_ports)} {cell}_pex')
        instances.append(cell)
    if not args.ring and sorted(instances) != ['inverter'] * 3 + ['vco_bias', 'vco_buffer']:
        raise ValueError('ring hierarchy changed; review experiment')
    circuit, seed_node, extracted_label = 'ring_leaves_pex', 'VCO_CORE', 'extracted_leaves'
    if args.ring:
        pex_ports, pex_body = subcircuit(args.ring, 'ring_oscillator_pex')
        if set(pex_ports) != set(ports) or len(pex_ports) != len(ports):
            raise ValueError('assembled ring interface mismatch')
        # The directed recipe's buffer input is the physical VCO_CORE net;
        # LVS must have passed before using this extraction for simulation.
        alias = args.startup_node or 'x_buffer.VIN'
        if not re.search(r'(?<!\S)' + re.escape(alias) + r'(?=\s)', pex_body):
            raise ValueError('assembled extraction lacks startup node; provide a reviewed VCO_CORE alias with --startup-node')
        extracted = ['Xring ' + ' '.join(pex_ports) + ' ring_oscillator_pex']
        circuit, seed_node, extracted_label = 'ring_layout_pex', 'xring.' + alias, 'extracted_ring'
    wrapper = output / (circuit + '.spice')
    wrapper.write_text('.subckt ' + circuit + ' ' + ' '.join(ports) + '\n' + '\n'.join(extracted)
                       + '\n.ends ' + circuit + '\n')
    hashes = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in [source, *paths.values()]}
    if original_ring:
        hashes[str(original_ring)] = hashlib.sha256(original_ring.read_bytes()).hexdigest()
    receiver = None
    if args.receiver:
        library = pdk / 'libs.ref/sg13cmos5l_stdcell/spice/sg13cmos5l_stdcell.spice'
        frozen = HERE.parents[2] / 'macros/pll_digital/frozen/v1'
        receiver, provenance = extract_receiver(frozen, library, output)
        sdc = frozen / 'sdc/pll_digital.sdc'
        period_ns = float(re.search(r'create_clock -name vco -period ([\d.]+)', sdc.read_text())[1])
        slew_ps = 1000 * float(re.search(
            r'set_input_transition ([\d.]+) \[get_ports \{vco_clk\}\]', sdc.read_text())[1])
        timing_lib = pdk / 'libs.ref/sg13cmos5l_stdcell/lib/sg13cmos5l_stdcell_typ_1p20V_25C.lib'
        libtext = timing_lib.read_text()
        if not re.search(r'time_unit\s*:\s*"1ns"', libtext) or any(
                float(re.search(r'slew_' + bound + r'_threshold_pct_' + edge + r'\s*:\s*([\d.]+)', libtext)[1]) != value
                for bound, value in [('lower', 20), ('upper', 80)] for edge in ('rise', 'fall')):
            raise ValueError('review timing units/slew thresholds before comparing to SDC')
        provenance.update(max_frequency_Hz=1e9 / period_ns, max_input_slew_ps=slew_ps,
                          sdc_sha256=hashlib.sha256(sdc.read_bytes()).hexdigest(),
                          timing_library_sha256=hashlib.sha256(timing_lib.read_bytes()).hexdigest())
        (output / 'receiver_manifest.json').write_text(json.dumps(provenance, indent=2) + '\n')
    (output / 'manifest.json').write_text(json.dumps({'inputs_sha256': hashes,
        'limitations': __doc__, 'receiver': bool(receiver),
        'devices_only_diagnostic': args.devices_only,
        'extraction_mode': 'assembled_ring' if args.ring else 'ideal_wiring_between_extracted_leaves',
        'startup_node': seed_node,
        'load_fF': [None] if receiver else [5] if args.smoke else [5, 20]}, indent=2) + '\n')
    # Routed-ring loading lowers the minimum frequency. Give the first
    # divide-by-two output enough complete cycles for the same checks.
    stop_ns, window_ns = (100, 50) if args.ring else (60, 30)
    corners = [('tt', 1.2, 27)] if args.smoke else [('tt', 1.2, 27), ('ss', 1.08, 125), ('ff', 1.32, -40)]
    if args.corners:
        corners = [c for c in [('tt', 1.2, 27), ('ss', 1.08, 125), ('ff', 1.32, -40)] if c[0] in args.corners]
    controls = args.control_values if args.control_values is not None else [.7] if args.smoke else [.5, .6, .7, .8, .9]
    if any(not math.isfinite(v) or not 0 <= v <= min(c[1] for c in corners) for v in controls):
        parser.error('control values must be finite and between ground and the lowest tested supply')
    loads = [None] if receiver else [5] if args.smoke else [5, 20]
    results = []
    for (corner, vdd, temp), vctrl, load in itertools.product(corners, controls, loads):
        tag = f'{corner}_v{vctrl}_c{load}'
        deck, data = output / (tag + '.cir'), output / (tag + '.dat')
        nodes = {'VDD': 'vdd', 'VCTRL': 'control', 'VSS': '0'}
        base = ' '.join('out_b' if p == 'VCO_OUT' else 'vdd_b' if p == 'VDD' else nodes[p] for p in ports)
        pex = ' '.join('out_p' if p == 'VCO_OUT' else 'vdd_p' if p == 'VDD' else nodes[p] for p in ports)
        loading = (f'.include {library}\n.include {receiver}\n'
                   'VRST reset 0 PWL(0 0 5n 0 5.02n ' + str(vdd) + ')\n'
                   'XRB out_b clk_b div_b reset vdd 0 frozen_receiver\n'
                   'XRP out_p clk_p div_p reset vdd 0 frozen_receiver' if receiver else
                   f'CB out_b 0 {load}f\nCP out_p 0 {load}f')
        extra = ' v(clk_b) v(div_b) v(clk_p) v(div_p)' if receiver else ''
        deck.write_text(f'''Schematic versus {extracted_label}
.lib {pdk}/libs.tech/ngspice/models/cornerMOSlv.lib mos_{corner}
.include {source}
{chr(10).join('.include ' + str(p) for p in paths.values())}
.include {wrapper}
VSUP vdd 0 PWL(0 0 100p {vdd})
VSENSE_B vdd vdd_b 0
VSENSE_P vdd vdd_p 0
VCONTROL control 0 {vctrl}
XBASE {base} ring_oscillator
XPEX {pex} {circuit}
{loading}
ISEED_B 0 xbase.VCO_CORE PWL(0 0 .5n 0 .51n 1u .6n 1u .61n 0)
ISEED_P 0 xpex.{seed_node} PWL(0 0 .5n 0 .51n 1u .6n 1u .61n 0)
.temp {temp}
.control
set num_threads=1
set wr_singlescale
set wr_vecnames
tran 2p {stop_ns}n
wrdata {data} v(out_b) v(out_p){extra} i(VSENSE_B) i(VSENSE_P)
quit
.endc
.end
''')
        with (output / (tag + '.log')).open('w') as log:
            subprocess.run(['ngspice', '-b', str(deck)], env=env, stdout=log,
                           stderr=subprocess.STDOUT, check=True)
        samples = [list(map(float, line.split())) for line in data.read_text().splitlines()[1:]]
        if not samples or samples[-1][0] < (stop_ns - .01) * 1e-9 or any(
                len(r) != (9 if receiver else 5) or not all(map(math.isfinite, r)) for r in samples):
            raise ValueError(f'incomplete transient: {tag}')
        window = [r for r in samples if r[0] >= window_ns * 1e-9]
        record = dict(corner=corner, vdd_V=vdd, temperature_C=temp, vctrl_V=vctrl, load_fF=load)
        signals = [('schematic', 1), (extracted_label, 2)]
        if receiver:
            signals += [('schematic_clock', 3), ('schematic_div2', 4),
                        ('extracted_clock', 5), ('extracted_div2', 6)]
        rising_times = {}
        for label, column in signals:
            rises = [a[0] + (b[0] - a[0]) * (vdd / 2 - a[column]) / (b[column] - a[column])
                     for a, b in zip(window, window[1:]) if a[column] < vdd / 2 <= b[column]]
            rising_times[label] = rises
            periods = [b - a for a, b in zip(rises, rises[1:])][-10:]
            low, high = min(r[column] for r in window), max(r[column] for r in window)
            record[label] = dict(frequency_Hz=len(periods) / sum(periods) if periods else None,
                                 rising_edges=len(rises), minimum_V=low, maximum_V=high,
                                 sustained_full_swing=len(periods) >= 3 and low < .1 * vdd and high > .9 * vdd)
            if receiver:
                falls = [a[0] + (b[0] - a[0]) * (vdd / 2 - a[column]) / (b[column] - a[column])
                         for a, b in zip(window, window[1:]) if b[column] < vdd / 2 <= a[column]]
                crossings = sorted([(t, True) for t in rises] + [(t, False) for t in falls])
                for state, name in ((True, 'high'), (False, 'low')):
                    widths = [(b[0] - a[0]) * 1e12 for a, b in zip(crossings, crossings[1:])
                              if a[1] == state and b[1] != state]
                    record[label]['min_' + name + '_width_ps'] = min(widths) if widths else None
                transitions = []
                for low_fraction, high_fraction, sign in ((.2, .8, 1), (.8, .2, -1)):
                    starts = [a[0] + (b[0] - a[0]) * (low_fraction * vdd - a[column]) / (b[column] - a[column])
                              for a, b in zip(window, window[1:])
                              if sign * a[column] < sign * low_fraction * vdd <= sign * b[column]]
                    ends = [a[0] + (b[0] - a[0]) * (high_fraction * vdd - a[column]) / (b[column] - a[column])
                            for a, b in zip(window, window[1:])
                            if sign * a[column] < sign * high_fraction * vdd <= sign * b[column]]
                    durations = [next(e for e in ends if e > s) - s for s in starts if any(e > s for e in ends)]
                    transitions.append(max(durations) * 1e12 if durations else None)
                record[label].update(max_rise_20_80_ps=transitions[0], max_fall_80_20_ps=transitions[1])
        for label, column in [('schematic', 7 if receiver else 3), (extracted_label, 8 if receiver else 4)]:
            charge = sum((a[column] + b[column]) / 2 * (b[0] - a[0]) for a, b in zip(window, window[1:]))
            record[label]['average_supply_power_W'] = vdd * charge / (window[-1][0] - window[0][0])
        if receiver:
            for label, prefix in [('schematic', 'schematic'), (extracted_label, 'extracted')]:
                f = record[label]['frequency_Hz']
                fd = record[prefix + '_div2']['frequency_Hz']
                record[label]['divide_ratio'] = f / fd if f and fd else None
                clocks, divided = rising_times[prefix + '_clock'], rising_times[prefix + '_div2']
                cycle_counts = [sum(a < c <= b for c in clocks) for a, b in zip(divided, divided[1:])]
                record[label]['receiver_checks'] = {
                    'clock_full_swing': record[prefix + '_clock']['sustained_full_swing'],
                    'div2_full_swing': record[prefix + '_div2']['sustained_full_swing'],
                    'input_clock_edge_count': abs(len(clocks) - len(rising_times[label])) <= 1,
                    'two_clocks_per_div2_cycle': len(cycle_counts) >= 3 and all(n == 2 for n in cycle_counts),
                    'within_frozen_frequency': f is not None and f <= 1e9 / period_ns,
                    'within_frozen_input_slew': all(record[label][k] is not None and record[label][k] <= slew_ps
                                                   for k in ('max_rise_20_80_ps', 'max_fall_80_20_ps'))}
        results.append(record)
        (output / 'summary.json').write_text(json.dumps(results, indent=2) + '\n')
        print(tag, record['schematic'], record[extracted_label], flush=True)
    if any(not r[label]['sustained_full_swing'] or
           (receiver and not all(r[label]['receiver_checks'].values()))
           for r in results for label in ('schematic', extracted_label)):
        raise SystemExit('One or more swing/receiver screens failed; inspect summary.json')


if __name__ == '__main__':
    main()
