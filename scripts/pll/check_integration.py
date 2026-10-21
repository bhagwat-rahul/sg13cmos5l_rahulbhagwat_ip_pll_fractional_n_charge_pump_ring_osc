#!/usr/bin/env python3
"""Verify a generated PLL core against schematic + frozen powered RTL sources.

Run with container python3, not CIC's virtualenv. No layout-derived golden
netlist, black-box LVS, source edits, or waivers are used.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'macros/pll_analog/layout'))
sys.path.insert(0, str(ROOT / 'scripts'))
from run_checks import Checks, MODES, PDK, SCHEM
from check_pex_ports import subcircuits

SOURCE = ROOT / 'schematic/pll_core.spice'
FROZEN = ROOT / 'macros/pll_digital/frozen/v1'


class CoreChecks(Checks):
    # The PDK recognizes GDS MOM devices in KLayout, not in Magic's fresh
    # geometric import. Keep that Magic result visible as a diagnostic;
    # source/model-view Magic LVS and all PEX gates remain required.
    gds_magic_lvs_required = False

    def __init__(self, cell, library, schematic=SCHEM, work_root=None):
        super().__init__(cell, library, schematic, work_root)
        for name in ('reference.spice', 'reference.cdl'):
            if (schematic / name).is_file():
                shutil.copy2(schematic / name, self.schematic / name)

    def prepare_reference(self):
        directory = self.work / 'reference'
        directory.mkdir()
        analog = Checks('pll_analog', self.inputs, self.schematic, self.work_root)
        declarations = {n: p for n, p, _ in subcircuits(SOURCE)}
        libraries = {suffix: PDK / 'libs.ref/sg13cmos5l_stdcell' / suffix /
                     f'sg13cmos5l_stdcell.{suffix}' for suffix in ('spice', 'cdl')}
        pin_orders = {suffix: {n: p for n, p, _ in subcircuits(path)}
                      for suffix, path in libraries.items()}
        if pin_orders['spice'] != pin_orders['cdl']:
            raise ValueError('PDK SPICE/CDL standard-cell port orders differ')
        stubs = directory / 'stdcells.v'
        stubs.write_text('\n'.join(
            f'module {name} ({", ".join(ports)}); inout {", ".join(ports)}; endmodule'
            for name, ports in pin_orders['spice'].items()) + '\n')
        powered = FROZEN / 'pnl/pll_digital.pnl.v'
        for row in (FROZEN / 'SHA256SUMS').read_text().splitlines():
            expected, name = row.split(maxsplit=1)
            if hashlib.sha256((FROZEN / name).read_bytes()).hexdigest() != expected:
                raise ValueError(f'frozen package changed: {name}')
        digital = directory / 'digital.spice'
        self.command('reference-yosys', ['yosys', '-Q', '-T', '-p',
            f'read_verilog -lib {stubs}; read_verilog {powered}; '
            f'hierarchy -check -top pll_digital; '
            f'write_json {directory / "digital.json"}; '
            f'write_spice -top pll_digital -pos VDD -neg VSS {digital}'])
        text = digital.read_text()
        # Yosys spells vector bits bus.0; keep the assembly's Verilog bit names.
        text = re.sub(r'\b(div_ratio|test_div_select)\.(\d+)\b', r'\1[\2]', text)
        module = json.loads((directory / 'digital.json').read_text())['modules']['pll_digital']
        ports = []
        for name, data in module['ports'].items():
            ports.extend([name] if len(data['bits']) == 1 else
                         [f'{name}[{i}]' for i in range(len(data['bits']))])
        if set(ports) != set(declarations['pll_digital']):
            raise ValueError(f'Yosys digital port mismatch: {ports}')
        if re.search(r'(?im)^\.subckt\b', text):
            raise ValueError('expected a flat Yosys top export')
        if len(re.findall(r'^X\S+ ', text, re.M)) != len(module['cells']):
            raise ValueError('Yosys export dropped digital cells')
        text = ('.subckt pll_digital ' + ' '.join(declarations['pll_digital'])
                + '\n' + text + '\n.ends pll_digital\n')
        digital.write_text(text)
        top = next((p, e) for n, p, e in subcircuits(SOURCE) if n == self.cell)
        assembly = '.subckt ' + self.cell + ' ' + ' '.join(top[0]) + '\n'
        assembly += '\n'.join(' '.join(e) for e in top[1]) + '\n.ends ' + self.cell + '\n'
        for suffix, klayout in [('spice', False), ('cdl', True)]:
            stage = directory / suffix
            stage.mkdir()
            reference = analog.reference(stage, klayout)
            (self.schematic / f'reference.{suffix}').write_text(
                '* Source-derived PLL core LVS reference; no extracted golden cells.\n'
                + assembly + reference.read_text() + '\n' + text + '\n'
                + libraries[suffix].read_text())
        hashes = {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in (SOURCE, powered, *libraries.values(),
                            *self.schematic.glob('reference.*'))}
        (directory / 'inputs.json').write_text(json.dumps(hashes, indent=2) + '\n')
        return 'fresh analog SPICE/CDL + powered digital Yosys export + full PDK cell circuits'

    def reference(self, directory, klayout):
        suffix = 'cdl' if klayout else 'spice'
        target = directory / f'{self.cell}.{suffix}'
        shutil.copy2(self.schematic / f'reference.{suffix}', target)
        return target

    def export(self):
        stream = super().export()
        import klayout.db as db
        frozen, actual = db.Layout(), db.Layout()
        source = FROZEN / 'gds/pll_digital.gds'
        frozen.read(str(source))
        actual.read(str(stream))
        if frozen.dbu != actual.dbu or actual.cell('pll_digital') is None:
            raise RuntimeError('digital hard macro lost or stream grid changed')
        layers = {(i.layer, i.datatype) for layout in (frozen, actual)
                  for i in layout.layer_infos()}
        differences = {}
        for layer in sorted(layers):
            before = db.Region(frozen.cell('pll_digital').begin_shapes_rec(frozen.layer(*layer))).merged()
            after = db.Region(actual.cell('pll_digital').begin_shapes_rec(actual.layer(*layer))).merged()
            delta = before ^ after
            if not delta.is_empty():
                differences[str(layer)] = dict(polygons=delta.count(), area_dbu2=delta.area())
        (self.work / 'digital_geometry.json').write_text(json.dumps(dict(
            frozen_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
            stream_sha256=hashlib.sha256(stream.read_bytes()).hexdigest(),
            layers_checked=len(layers), differences=differences,
            status='FAIL' if differences else 'PASS'), indent=2) + '\n')
        if differences:
            raise RuntimeError('frozen digital polygons changed; see digital_geometry.json')
        return stream


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('candidate', type=Path)
    parser.add_argument('--library', type=Path, help='optional post-fill Magic library to snapshot and check')
    parser.add_argument('--mode', choices=(*MODES, 'reference'), default='all')
    args = parser.parse_args()
    candidate = args.candidate.resolve()
    manifest = json.loads((candidate / 'manifest.json').read_text())
    for name, expected in manifest['inputs_sha256'].items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != expected:
            parser.error(f'candidate input changed; regenerate before checking: {name}')
    os.environ.update(PDK_ROOT=str(PDK.parent), PDK=PDK.name, PDKPATH=str(PDK),
                      STD_CELL_LIBRARY='sg13cmos5l_stdcell')
    checks = CoreChecks('pll_core', (args.library or candidate / 'mag').resolve(),
                        work_root=candidate / 'checks')
    checks.run('input-hierarchy', lambda: checks.validate_hierarchy(checks.cell, set()))
    mode = args.mode if checks.results['input-hierarchy']['status'] == 'PASS' else None
    if mode in ('all', 'lvs', 'gds-roundtrip', 'reference'):
        checks.run('source-reference', checks.prepare_reference)
    if mode in ('all', 'drc', 'drc-all'):
        checks.run('drc-magic', checks.drc)
    if mode in ('all', 'drc-klayout', 'drc-all'):
        checks.run('drc-klayout-full', checks.klayout_drc)
    if mode in ('all', 'antenna'):
        checks.run('antenna-magic', checks.antenna)
    if mode == 'antenna':
        checks.run('antenna-klayout', lambda: checks.klayout_drc(True))
    if mode in ('all', 'lvs'):
        checks.run('lvs-magic', checks.lvs)
        checks.run('lvs-klayout', lambda: checks.lvs(True))
    if mode in ('all', 'pex'):
        checks.run('pex-resistance-lumped-c', checks.pex)
    if mode in ('all', 'gds-roundtrip'):
        checks.run('gds-roundtrip', checks.gds_roundtrip)
    (checks.work / 'summary.json').write_text(json.dumps(checks.results, indent=2) + '\n')
    print(f'Reports: {checks.work}', flush=True)
    return int(any(r['status'] != 'PASS' for r in checks.results.values()))


if __name__ == '__main__':
    sys.exit(main())
