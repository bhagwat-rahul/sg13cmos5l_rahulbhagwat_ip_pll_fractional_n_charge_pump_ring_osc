#!/usr/bin/env python3
"""Check measured ring waveforms against the unchanged frozen digital macro.

Uses its full routed netlist, nominal SPEF, corner Liberty and existing SDC.
Separately stresses the minimum observed high and low pulse widths, minimum
observed period, and worst rise/fall slew in the settled 50–100 ns window.
These periodic envelopes are not arbitrary-waveform, jitter, crosstalk,
reset-release, or closed-loop signoff. TT SPICE is 27 C; timing Liberty is 25 C.
An above-2-GHz diagnostic pass does not change the frozen interface contract.
"""

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess

HERE = Path(__file__).resolve().parent
FROZEN = HERE.parents[2] / 'macros/pll_digital/frozen/v1'
CORNERS = {'tt': 'typ_1p20V_25C', 'ss': 'slow_1p08V_125C', 'ff': 'fast_1p32V_m40C'}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_sta(output, corner, sdc, library):
    output.mkdir()
    constraints = output / 'input.sdc'
    constraints.write_text(sdc)
    script = output / 'run.tcl'
    script.write_text(f'''read_liberty {{{library}}}
read_verilog {{{FROZEN / 'nl/pll_digital.nl.v'}}}
link_design pll_digital
read_sdc {{{constraints}}}
read_spef {{{FROZEN / 'spef/nom/pll_digital.nom.spef'}}}
set sta_report_default_digits 6
report_worst_slack -max
report_worst_slack -min
report_check_types -min_pulse_width -min_period -verbose > {{{output / 'clock-limits.rpt'}}}
report_check_types -max_slew -max_capacitance -max_fanout -violators > {{{output / 'electrical.rpt'}}}
report_checks -path_delay min_max -format full_clock_expanded -group_path_count 2 > {{{output / 'paths.rpt'}}}
check_setup > {{{output / 'coverage.rpt'}}}
puts RECEIVER_STA_COMPLETED
exit
''')
    with (output / 'sta.log').open('w') as log:
        subprocess.run(['sta', '-no_splash', '-exit', str(script)], stdout=log,
                       stderr=subprocess.STDOUT, check=True)
    log = (output / 'sta.log').read_text()
    if 'RECEIVER_STA_COMPLETED' not in log or re.search(r'(?m)^Error:', log):
        raise RuntimeError(f'STA failed: {output / "sta.log"}')
    setup, hold = [float(re.search(r'worst slack ' + mode + r' ([-\d.]+)', log)[1])
                   for mode in ('max', 'min')]
    clocks = (output / 'clock-limits.rpt').read_text()
    pulse_slacks = [float(x) for x in re.findall(r'([-\d.]+)\s+slack \((?:MET|VIOLATED)\)', clocks)]
    if not pulse_slacks or 'sequential_clock_pulse_width' not in clocks:
        raise RuntimeError(f'No clock pulse-width checks: {output}')
    electrical = (output / 'electrical.rpt').read_text()
    return dict(setup_slack_ps=setup * 1000, hold_slack_ps=hold * 1000,
                clock_limit_slack_ps=min(pulse_slacks) * 1000,
                electrical_limits_pass='(VIOLATED)' not in electrical,
                sta_pass=setup >= 0 and hold >= 0 and min(pulse_slacks) >= 0
                         and '(VIOLATED)' not in electrical,
                report_directory=str(output), corner=corner)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--characterization', type=Path, nargs='+', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to((HERE.parent / 'layout/build').resolve()):
        parser.error('output must be below layout/build/')
    output.mkdir(parents=True, exist_ok=False)
    pdk = Path(os.environ.get('PDK_ROOT', '/foss/pdks')) / 'ihp-sg13cmos5l'
    libraries = {c: pdk / f'libs.ref/sg13cmos5l_stdcell/lib/sg13cmos5l_stdcell_{v}.lib.gz'
                 for c, v in CORNERS.items()}
    sdc_path = FROZEN / 'sdc/pll_digital.sdc'
    sdc = sdc_path.read_text()
    metrics = json.loads((FROZEN / 'reports/metrics.json').read_text())
    inputs = {str(p): sha(p) for p in [sdc_path, FROZEN / 'reports/metrics.json',
              FROZEN / 'nl/pll_digital.nl.v', FROZEN / 'spef/nom/pll_digital.nom.spef',
              *libraries.values(), Path(__file__)]}
    baselines = {}
    for corner, library in libraries.items():
        result = run_sta(output / ('baseline_' + corner), corner, sdc, library)
        name = 'nom_' + CORNERS[corner]
        for kind in ('setup', 'hold'):
            expected = metrics[f'timing__{kind}__ws__corner:{name}'] * 1000
            if abs(result[kind + '_slack_ps'] - expected) > .001:
                raise RuntimeError(f'{corner} does not reproduce frozen {kind} slack')
        if not result['sta_pass']:
            raise RuntimeError(f'{corner} frozen baseline failed')
        baselines[corner] = result
    results = []
    for folder in args.characterization:
        folder = folder.resolve()
        manifest = json.loads((folder / 'manifest.json').read_text())
        if not manifest['receiver'] or manifest['extraction_mode'] != 'assembled_ring':
            raise ValueError('requires assembled-ring receiver characterization')
        provenance = json.loads((folder / 'receiver_manifest.json').read_text())
        for path, expected in provenance['inputs_sha256'].items():
            if sha(Path(path)) != expected:
                raise ValueError(f'receiver input changed: {path}')
        if sha(sdc_path) != provenance['sdc_sha256']:
            raise ValueError('frozen SDC changed since SPICE characterization')
        for name in ('summary.json', 'manifest.json', 'receiver_manifest.json'):
            inputs[str(folder / name)] = sha(folder / name)
        for index, record in enumerate(json.loads((folder / 'summary.json').read_text())):
            signal = record['extracted_ring']
            tag = f"{record['corner']}_v{record['vctrl_V']}_c{record['load_fF']}"
            data = folder / (tag + '.dat')
            inputs[str(data)] = sha(data)
            lines = data.read_text().splitlines()
            if lines[0].split()[2].lower() != 'v(out_p)':
                raise ValueError(f'unexpected waveform columns: {data}')
            rows = [list(map(float, line.split())) for line in lines[1:]]
            if rows[-1][0] < 99.99e-9 or any(not all(map(math.isfinite, r)) for r in rows):
                raise ValueError(f'incomplete/nonfinite waveform: {data}')
            rows = [r for r in rows if r[0] >= 50e-9]
            edges = []
            level = record['vdd_V'] / 2
            for a, b in zip(rows, rows[1:]):
                if (a[2] < level <= b[2]) or (b[2] < level <= a[2]):
                    edges.append((a[0] + (b[0] - a[0]) * (level - a[2]) / (b[2] - a[2]), b[2] > a[2]))
            rises = [t for t, high in edges if high]
            result = dict(characterization=str(folder), corner=record['corner'],
                          vctrl_V=record['vctrl_V'], frequency_Hz=signal['frequency_Hz'],
                          spice_checks=signal['receiver_checks'], envelopes=[])
            widths = {high: [b[0] - a[0] for a, b in zip(edges, edges[1:])
                             if a[1] == high and b[1] != high] for high in (True, False)}
            if len(rises) < 4 or not all(widths.values()) or any(
                    signal[k] is None for k in ('max_rise_20_80_ps', 'max_fall_80_20_ps')):
                result.update(qualified_sample=False, reason='No complete clock/slew envelope')
            else:
                period = min(b - a for a, b in zip(rises, rises[1:])) * 1e9
                for name, high in [('minimum_high', min(widths[True]) * 1e9),
                                   ('minimum_low', period - min(widths[False]) * 1e9)]:
                    if not 0 < high < period:
                        raise ValueError('invalid measured clock envelope')
                    updated, count = re.subn(r'create_clock -name vco -period [\d.]+',
                        f'create_clock -name vco -period {period:.12g} -waveform {{0 {high:.12g}}}', sdc)
                    if count != 1:
                        raise ValueError('expected one frozen VCO clock')
                    for command, selector in [('set_input_transition', 'get_ports {vco_clk}'),
                                              ('set_clock_transition', 'get_clocks {vco}')]:
                        replacement = '\n'.join(f'{command} -{edge} {signal[key] / 1000:.12g} [{selector}]'
                            for edge, key in [('rise', 'max_rise_20_80_ps'), ('fall', 'max_fall_80_20_ps')])
                        updated, count = re.subn(re.escape(command) + r' [\d.]+ \[' + re.escape(selector) + r'\]',
                                                 lambda _: replacement, updated)
                        if count != 1:
                            raise ValueError(f'expected one {command} constraint')
                    timing = run_sta(output / f'{folder.name}_{index}_{name}', record['corner'], updated,
                                     libraries[record['corner']])
                    result['envelopes'].append(dict(name=name, period_ns=period, high_ns=high, **timing))
                result['qualified_sample'] = all(e['sta_pass'] for e in result['envelopes']) and all(
                    v for k, v in signal['receiver_checks'].items() if k != 'within_frozen_frequency')
            results.append(result)
            (output / 'summary.json').write_text(json.dumps(results, indent=2) + '\n')
            print(folder.name, tag, result['qualified_sample'], flush=True)
    (output / 'manifest.json').write_text(json.dumps(dict(inputs_sha256=inputs, baselines=baselines,
        limitations=__doc__, settled_window_ns=[50, 100]), indent=2) + '\n')
    if not results or not all(r['qualified_sample'] for r in results):
        raise SystemExit('One or more measured-waveform diagnostics failed; inspect summary.json')


if __name__ == '__main__':
    main()
