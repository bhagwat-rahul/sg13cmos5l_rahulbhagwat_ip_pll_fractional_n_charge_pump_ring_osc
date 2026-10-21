#!/usr/bin/env python3
"""Alternative core RC experiment; does not waive native Magic failures.

Uses the pinned KPEX 0.6.10 environment already used for analog. Run alone
inside IIC-OSIC-TOOLS. Limits the extractor's virtual memory to 8 GiB and
uses one thread. This is interconnect RC, not substrate/EM/ESD signoff.
"""

import argparse
import collections
import hashlib
import json
import math
import os
from pathlib import Path
import re
import resource
import subprocess
import sys

import klayout.db as db

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from check_pex_ports import Union, check, subcircuits


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(netlist, database):
    """Compare named device terminals and R-collapsed nets, not raw M order."""
    problems = check(netlist)
    if problems:
        raise ValueError('\n'.join(problems))
    blocks = subcircuits(netlist)
    if len(blocks) != 1:
        raise ValueError('expected a single flat modeled-device RC circuit')
    name, ports, elements = blocks[0]
    comparison = db.LayoutVsSchematic()
    comparison.read(str(database))
    circuit = comparison.netlist().circuit_by_name(name)
    if circuit is None:
        raise ValueError(f'RC top {name} absent from extraction database')

    def number(text):
        match = re.fullmatch(r'([-+\d.eE]+)([fpnum]?)', text)
        if match is None:
            raise ValueError(f'unsupported SPICE number: {text}')
        return float(match[1]) * {'': 1, 'f': 1e-15, 'p': 1e-12,
                                  'n': 1e-9, 'u': 1e-6, 'm': 1e-3}[match[2]]

    expected = {}
    for device in circuit.each_device():
        model = device.device_class().name
        if model in ('sg13_lv_nmos', 'sg13_lv_pmos'):
            terminals, required = ('D', 'G', 'S', 'B'), ('w', 'l', 'as', 'ad', 'ps', 'pd')
        elif model == 'rhigh':
            terminals, required = ('rhigh_1', 'rhigh_2', 'rhigh_sub'), ('w', 'l', 'm', 'ps', 'b')
        elif model == 'cap_cmomf':
            terminals, required = ('mim_top', 'mim_btm'), ('w', 'l', 'm')
        else:
            raise ValueError(f'unreviewed modeled device: {model}')
        nodes = [device.net_for_terminal(t).expanded_name() for t in terminals]
        parameters = {p.name.lower(): device.parameter(p.id()) * (
            1e-12 if p.name.lower() in ('as', 'ad', 'a') else
            1e-6 if p.name.lower() in ('w', 'l', 'ps', 'pd', 'p') else 1)
            for p in device.device_class().parameter_definitions()}
        expected[device.expanded_name()] = model, nodes, parameters, required
    actual = {}
    for row in elements:
        if row[0][0].lower() == 'x':
            index = next(i for i, word in enumerate(row) if word in
                         ('sg13_lv_nmos', 'sg13_lv_pmos', 'rhigh', 'cap_cmomf'))
            actual[row[0][1:]] = (row[index], row[1:index],
                                  dict(t.lower().split('=', 1) for t in row[index+1:] if '=' in t))
    if actual.keys() != expected.keys():
        raise ValueError('RC export changed modeled-device identities/count')
    dc, bindings, groups = Union(), {}, collections.defaultdict(set)
    resistors, capacitors = [], []
    for row in elements:
        if row[0][0].lower() == 'r':
            if number(row[3]) <= 0:
                raise ValueError('non-positive interconnect resistance')
            dc.union(row[1].removeprefix('\\'), row[2].removeprefix('\\'))
            resistors.append(row)
        elif row[0][0].lower() == 'c':
            if number(row[3]) < 0:
                raise ValueError('negative parasitic capacitance')
            capacitors.append(row)

    def bind(node, logical):
        root = dc.find(node.removeprefix('\\'))
        if root in bindings and bindings[root] != logical:
            raise ValueError(f'RC network shorts logical nets: {logical}, {bindings[root]}')
        bindings[root] = logical
        groups[logical].add(root)

    for identifier, (model, nodes, parameters) in actual.items():
        old_model, old_nodes, old_parameters, required = expected[identifier]
        if model != old_model or len(nodes) != len(old_nodes):
            raise ValueError(f'modeled-device mismatch: {identifier}')
        for key in required:
            if key not in parameters or not math.isclose(number(parameters[key]), old_parameters[key],
                                                        rel_tol=1e-8, abs_tol=1e-24):
                raise ValueError(f'RC export changed {identifier} {key}')
        for node, logical in zip(nodes, old_nodes):
            bind(node, logical)
    for pin in circuit.each_pin():
        candidates = [p for p in ports if p in (pin.name(), pin.name() + '$1')]
        if len(candidates) != 1:
            raise ValueError(f'missing/ambiguous external pin: {pin.name()}')
        bind(candidates[0], pin.name())
    if any(len(roots) != 1 for roots in groups.values()) or not resistors or not capacitors:
        raise ValueError('split logical nets or missing R/C elements')
    return dict(models=dict(collections.Counter(model for model, _, _ in actual.values())),
                resistors=len(resistors), capacitors=len(capacitors), ports=ports,
                netlist_sha256=sha(netlist), database_sha256=sha(database),
                modeled_device_parameters_and_dc_connectivity='PASS',
                limitations='Export consistency only, not schematic LVS or capacitance accuracy; '
                'no distributed well/substrate R; physical CMOM stack must be restored separately.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('report', type=Path, help='completed core checker report directory')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report, output = args.report.resolve(), args.output.resolve()
    if not output.is_relative_to(ROOT / 'layout/build') or output.exists():
        parser.error('output must be a new directory under layout/build/')
    summary = json.loads((report / 'summary.json').read_text())
    if any(summary[key]['status'] != 'PASS' for key in ('drc-magic', 'drc-klayout-full', 'lvs-klayout')):
        parser.error('require passing physical DRC/density/antenna and independent GDS LVS first')
    source = report / 'pll_core.gds'
    if sha(source) != json.loads((report / 'cmom_annotations.json').read_text())['annotated_sha256']:
        parser.error('source stream changed after annotation audit')
    geometry = json.loads((report / 'digital_geometry.json').read_text())
    if geometry['status'] != 'PASS' or geometry['stream_sha256'] != sha(source):
        parser.error('require an unchanged frozen digital macro in the source stream')
    output.mkdir(parents=True)
    layout, original = db.Layout(), db.Layout()
    layout.read(str(source))
    original.read(str(source))
    top = layout.cell('pll_core')
    # Remove child labels only in an extraction copy: flattened child text
    # otherwise becomes thousands of false external ports. Keep all polygons.
    for cell in layout.each_cell():
        if cell != top:
            for index in layout.layer_indexes():
                for shape in list(cell.shapes(index).each()):
                    if shape.is_text():
                        shape.delete()
    top.flatten(True)
    flat = output / 'pll_core_flat.gds'
    layout.write(str(flat))
    actual = db.Layout()
    actual.read(str(flat))
    for info in original.layer_infos():
        # Materialize polygon unions: lazy Regions on text-only layers can
        # report nonempty despite containing zero polygons after text removal.
        before = db.Region(original.cell('pll_core').begin_shapes_rec(original.layer(info))).merged()
        after = db.Region(actual.cell('pll_core').begin_shapes_rec(actual.layer(info))).merged()
        if not (before ^ after).is_empty():
            raise ValueError(f'extraction preparation changed physical/recognition layer {info}')
    schematic = report / 'lvs-klayout/pll_core.cdl'
    python = ROOT / 'macros/pll_analog/layout/build/cic-kpex-env-034/bin/python'
    env = dict(os.environ, OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1')
    env.pop('PYTHONPATH', None)
    version = subprocess.check_output([python, '-c',
        'from importlib.metadata import version; print(version("klayout-pex"))'], env=env, text=True).strip()
    if version != '0.6.10':
        raise ValueError(f'unreviewed KPEX version: {version}')
    command = list(map(str, [python, '-m', 'klayout_pex', 'extract', '--pdk', 'ihp-sg13cmos5l',
        '--2.5D', '--mode', 'RC', '--blackbox', 'True', '--threads', '1', '--gds', flat,
        '--cell', 'pll_core', '--schematic', schematic, '--out-dir', output / 'extraction',
        '--out-netlist', output / 'core_rc.spice']))
    (output / 'input_audit.json').write_text(json.dumps(dict(source_sha256=sha(source),
        flat_sha256=sha(flat), schematic_sha256=sha(schematic), all_polygon_xor='empty',
        change='flatten extraction copy; remove child text only', kpex_version=version,
        command=command), indent=2) + '\n')
    print('Running native RC; log:', output / 'extract.log', flush=True)
    def limit_memory():
        resource.setrlimit(resource.RLIMIT_AS, (8 * 1024**3, 8 * 1024**3))
    with (output / 'extract.log').open('w') as log:
        result = subprocess.run(command, env=env, stdout=log, stderr=subprocess.STDOUT,
                                preexec_fn=limit_memory)
    status = dict(extractor_exit_code=result.returncode, status='FAIL')
    (output / 'result.json').write_text(json.dumps(status, indent=2) + '\n')
    if result.returncode:
        return 1
    database, = (output / 'extraction').rglob('pll_core.lvsdb.gz')
    checked = audit(output / 'core_rc.spice', database)
    (output / 'export_audit.json').write_text(json.dumps(checked, indent=2) + '\n')
    subprocess.run([sys.executable, ROOT / 'macros/pll_analog/cic/restore_cap_stack.py',
                    output / 'core_rc.spice', '--magic-dir', report / 'mag',
                    '--output', output / 'core_rc_stack.spice'], check=True)
    status.update(status='PASS', limitations='RC export/stack checks only; not electrical/tapeout qualification')
    (output / 'result.json').write_text(json.dumps(status, indent=2) + '\n')
    print(json.dumps(checked, indent=2), flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
