#!/usr/bin/env python3
"""Check saved SG13CMOS5L Magic cells without modifying the design sources."""

import argparse
from datetime import datetime
from fractions import Fraction
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[2]
SCHEM = ROOT.parent / 'schematic/xschem'
CELLS = ('inverter', 'vco_bias', 'vco_buffer', 'charge_pump', 'loop_filter',
         'ring_oscillator', 'pll_analog')
MODES = ('all', 'drc', 'drc-klayout', 'drc-all', 'antenna', 'lvs', 'pex', 'gds-roundtrip')
PDK = Path(os.environ.get('PDK_ROOT', '/foss/pdks')) / 'ihp-sg13cmos5l'
RC = PDK / 'libs.tech/magic/ihp-sg13cmos5l.magicrc'


class Checks:
    def __init__(self, cell, library, schematic=SCHEM):
        self.cell = cell
        self.work = ROOT / 'build' / cell / datetime.now().strftime('%Y%m%d-%H%M%S-%f')
        self.work.mkdir(parents=True)
        self.inputs = self.work / 'mag'
        self.inputs.mkdir()
        self.results = {}
        self.exported = False
        # Snapshot all cells so a running check never writes into the layout library.
        for source in library.glob('*.mag'):
            shutil.copy2(source, self.inputs / source.name)
        hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in self.inputs.glob('*.mag')}
        (self.work / 'inputs.json').write_text(json.dumps(hashes, indent=2) + '\n')
        self.schematic = self.work / 'schematic'
        self.schematic.mkdir()
        for source in schematic.iterdir():
            if source.suffix in ('.sch', '.sym') or source.name == 'xschemrc':
                shutil.copy2(source, self.schematic / source.name)
        (self.work / 'schematic_inputs.json').write_text(json.dumps({
            p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in self.schematic.iterdir()
        }, indent=2) + '\n')

    def validate_hierarchy(self, cell, seen):
        if cell in seen:
            return
        seen.add(cell)
        text = (self.inputs / f'{cell}.mag').read_text()
        if '\ntech ihp-sg13cmos5l\n' not in text or '<< end >>' not in text:
            raise ValueError(f'{cell}: incomplete file or wrong technology')
        if not re.search(r'^(rect |use )', text, re.M):
            raise ValueError(f'{cell}: empty layout')
        for child in re.findall(r'^use (\S+)', text, re.M):
            self.validate_hierarchy(child, seen)
        return 'complete saved hierarchy, correct technology'

    def command(self, name, args, cwd=None):
        log = self.work / f'{name}.log'
        print(f'  Running {name} ...', flush=True)
        with log.open('w') as out:
            result = subprocess.run([str(a) for a in args], cwd=cwd or self.inputs,
                                    stdout=out, stderr=subprocess.STDOUT)
        if result.returncode:
            raise RuntimeError(f'exit {result.returncode}; see {log}')
        return log.read_text(errors='replace')

    def magic(self, name, body):
        directory = self.work / name
        directory.mkdir(exist_ok=True)
        script = directory / 'run.tcl'
        script.write_text(f'''crashbackups stop
drc off
load {{{self.inputs / (self.cell + '.mag')}}}
select top cell
expand
cd {{{directory}}}
{body}
puts CHECK_SCRIPT_COMPLETED
quit -noprompt
''')
        log = self.command(name, ['magic', '-dnull', '-noconsole', '-rcfile', RC, script])
        if 'CHECK_SCRIPT_COMPLETED' not in log or re.search(
                r'(?im)^(?:Error|Magic error|Tcl error)|Cannot open|couldn.t (?:open|find)|'
                r'Bad Device Location|Missing (?:terminal|substrate) connection|'
                r'Unrecognized layer \(type\)|CIF output style .* is ambiguous|'
                r'[1-9]\d* problems occurred\.  See feedback entries\.', log):
            raise RuntimeError(f'Magic error or incomplete run; see {name}.log')
        return directory, log

    def export(self):
        if not self.exported:
            self.magic('export', f'gds write {{{self.work / (self.cell + ".gds")}}}')
            if not (self.work / f'{self.cell}.gds').stat().st_size:
                raise RuntimeError('empty GDS export')
            self.annotate_cmom()
            self.exported = True
        return self.work / f'{self.cell}.gds'

    def annotate_cmom(self):
        # Magic's native fringe-cap PCell exports physical metal, but not the
        # CMOS5L LVS recognition/pin purposes. Supply those from the saved
        # native PCell, never from schematic instances or expected nets.
        sources = [(p, p.read_text()) for p in self.inputs.glob('*.mag')]
        sources = [(p, t) for p, t in sources if '\nstring gencell cap_cmomf\n' in t]
        if not sources:
            return
        try:
            import klayout.db as db
        except ImportError as error:
            raise RuntimeError('CMOM stream annotation requires the KLayout Python module') from error
        stream = self.work / f'{self.cell}.gds'
        layout, original = db.Layout(), db.Layout()
        layout.read(str(stream))
        original.read(str(stream))
        annotations = []
        for source, text in sources:
            cell = layout.cell(source.stem)
            if cell is None:  # The library can contain unused circuit leaves.
                continue
            if not re.search(r'\bmmax metal4\b', text):
                raise RuntimeError(f'{source.name}: review recognition pins for a non-M4 CMOM stack')
            a, b = re.search(r'^magscale (\d+) (\d+)$', text, re.M).groups()
            unit = Fraction(int(a), 100 * int(b))  # native coordinate -> micrometres
            bounds = re.search(r'^string FIXED_BBOX (.*)$', text, re.M)[1].split()
            marker = db.Box(*[round(float(unit * int(v)) / layout.dbu) for v in bounds])
            pins = re.findall(r'^rlabel \S+ (-?\d+) (-?\d+) -?\d+ -?\d+ \d+ (c[12])$', text, re.M)
            if len(pins) != 2 or {p[2] for p in pins} != {'c1', 'c2'}:
                raise RuntimeError(f'{source.name}: CMOM needs two native labeled terminals')
            metal = db.Region(cell.begin_shapes_rec(layout.layer(50, 0)))
            pin_shapes = []
            for x, y, name in pins:
                x, y = float(unit * int(x)), float(unit * int(y))
                pin = db.Box(*[round(v / layout.dbu) for v in
                               (x - 0.005, y - 0.005, x + 0.005, y + 0.005)])
                if not (db.Region(pin) - metal).is_empty() or not (db.Region(pin) - db.Region(marker)).is_empty():
                    raise RuntimeError(f'{source.name}: {name} is not inside its M4/CMOM body')
                cell.shapes(layout.layer(50, 2)).insert(pin)
                pin_shapes.append({'name': name, 'box_dbu': [pin.left, pin.bottom, pin.right, pin.top]})
            cell.shapes(layout.layer(99, 40)).insert(marker)
            annotations.append({'cell': source.stem, 'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
                                'marker_dbu': [marker.left, marker.bottom, marker.right, marker.top],
                                'pins': pin_shapes})
        if not annotations:
            return
        raw = stream.with_name(f'{self.cell}.raw-magic.gds')
        shutil.copy2(stream, raw)
        layout.write(str(stream))
        layout = db.Layout()
        layout.read(str(stream))  # Audit the actual serialized output, not just memory.
        for info in original.layer_infos():
            if (info.layer, info.datatype) in ((99, 40), (50, 2)):
                continue
            before = db.Region(original.top_cell().begin_shapes_rec(original.layer(info)))
            after = db.Region(layout.top_cell().begin_shapes_rec(layout.layer(info)))
            if not (before ^ after).is_empty():
                raise RuntimeError(f'CMOM annotation changed physical layer {info}')
        (self.work / 'cmom_annotations.json').write_text(json.dumps({
            'raw_magic_sha256': hashlib.sha256(raw.read_bytes()).hexdigest(),
            'annotated_sha256': hashlib.sha256(stream.read_bytes()).hexdigest(),
            'dbu_um': layout.dbu, 'cells': annotations,
            'physical_layer_xor': 'empty',
            'limitations': 'Recognition metadata only; does not validate capacitance or native Magic LVS/PEX',
        }, indent=2) + '\n')

    def gds_roundtrip(self):
        stream = self.export()
        directory = self.work / 'gds-import'
        directory.mkdir()
        import klayout.db as db
        reference, physical, metadata = db.Layout(), db.Layout(), db.Layout()
        for layout in (reference, physical, metadata):
            layout.read(str(stream))
        purposes = {(99, 40)}
        # Keep a lossless, hierarchical recognition sidecar. Magic cannot
        # import CMOS5L MOM recognition 99/40; this is not fabricated metal.
        # Preserve pin purpose 50/2 in the import: Magic needs it for ports.
        for info in list(physical.layer_infos()):
            if (info.layer, info.datatype) in purposes:
                physical.delete_layer(physical.layer(info))
        for info in list(metadata.layer_infos()):
            if (info.layer, info.datatype) not in purposes:
                metadata.delete_layer(metadata.layer(info))
        physical_stream = directory / 'physical.gds'
        physical.write(str(physical_stream))
        metadata.write(str(directory / 'recognition.gds'))
        # An empty working library is essential: preloading the source .mag
        # would let Magic reuse it instead of checking the serialized geometry.
        script = directory / 'read.tcl'
        script.write_text(f'''crashbackups stop
drc off
gds readonly false
gds rescale false
gds read {{{physical_stream}}}
load {self.cell}
select top cell
writeall force
gds write {{{directory / 'reexport.gds'}}}
puts GDS_IMPORT_COMPLETED
quit -noprompt
''')
        log = self.command('gds-import', ['magic', '-dnull', '-noconsole', '-rcfile', RC, script],
                           cwd=directory)
        if 'GDS_IMPORT_COMPLETED' not in log or re.search(
                r'(?im)^(?:Error|Magic error|Tcl error)|Cannot open|couldn.t (?:open|find)|'
                r'Unknown layer/datatype|Unrecognized layer|[1-9]\d* problems occurred', log):
            raise RuntimeError('incomplete GDS import; see gds-import.log')
        actual = db.Layout()
        actual.read(str(directory / 'reexport.gds'))

        def differences(candidate, recognition=False):
            if candidate.dbu != reference.dbu or candidate.cell(self.cell) is None:
                raise RuntimeError('GDS round-trip changed DBU or lost the top cell')
            layers = {(i.layer, i.datatype) for layout in (reference, candidate)
                      for i in layout.layer_infos()}
            changed = {}
            for layer in layers:
                if (layer in purposes) != recognition:
                    continue
                before = db.Region(reference.cell(self.cell).begin_shapes_rec(reference.layer(*layer)))
                after = db.Region(candidate.cell(self.cell).begin_shapes_rec(candidate.layer(*layer)))
                delta = before ^ after
                if not delta.is_empty():
                    changed[str(layer)] = {'polygons': delta.count(), 'area_dbu2': delta.area()}
            return changed

        changed = differences(actual)
        audit = dict(source_sha256=hashlib.sha256(stream.read_bytes()).hexdigest(),
                     physical_import_sha256=hashlib.sha256(physical_stream.read_bytes()).hexdigest(),
                     reexport_sha256=hashlib.sha256((directory / 'reexport.gds').read_bytes()).hexdigest(),
                     differences=changed, recognition_purposes=sorted(purposes))
        (directory / 'physical_xor.json').write_text(json.dumps(audit, indent=2) + '\n')
        if changed:
            raise RuntimeError('GDS physical round-trip XOR is nonempty; see gds-import/physical_xor.json')
        # Restore only recognition shapes to the actual reexport, never
        # replace its physical geometry with the original source stream.
        for info in list(actual.layer_infos()):
            if (info.layer, info.datatype) in purposes:
                actual.delete_layer(actual.layer(info))
        for cell in metadata.each_cell():
            for info in metadata.layer_infos():
                shapes = cell.shapes(metadata.layer(info))
                if shapes.is_empty():
                    continue
                target = actual.cell(cell.name)
                if target is None:
                    raise RuntimeError(f'GDS round-trip lost recognition-bearing cell {cell.name}')
                for shape in shapes.each():
                    target.shapes(actual.layer(info)).insert(shape)
        restored = directory / 'recognition-restored.gds'
        actual.write(str(restored))
        serialized = db.Layout()
        serialized.read(str(restored))
        if differences(serialized) or differences(serialized, recognition=True):
            raise RuntimeError('Recognition restoration changed serialized physical/marker geometry')
        audit.update(recognition_sidecar_sha256=hashlib.sha256(
                         (directory / 'recognition.gds').read_bytes()).hexdigest(),
                     restored_sha256=hashlib.sha256(restored.read_bytes()).hexdigest(),
                     restored_physical_differences={}, restored_recognition_differences={})
        (directory / 'physical_xor.json').write_text(json.dumps(audit, indent=2) + '\n')
        self.run('gds-physical-roundtrip', lambda: 'empty physical and restored-recognition polygon XOR; '
                 'lossless recognition sidecar retained; does not qualify native CMOM extraction')
        child = Checks(self.cell, directory, self.schematic)
        (child.work / 'gds_source.json').write_text(json.dumps({
            'stream': str(stream), 'sha256': hashlib.sha256(stream.read_bytes()).hexdigest(),
            'physical_import': str(physical_stream), 'recognition_restored': str(restored),
            'import_log': str(self.work / 'gds-import.log'),
            'limitations': 'Same Magic extraction engine and lumped-C approximation; not independent foundry PEX',
        }, indent=2) + '\n')
        child.run('input-hierarchy', lambda: child.validate_hierarchy(self.cell, set()))
        if child.results['input-hierarchy']['status'] == 'PASS':
            for name, action in [('drc-magic', child.drc), ('antenna-magic', child.antenna),
                                 ('lvs-magic', child.lvs),
                                 ('lvs-klayout-roundtrip', lambda: child.lvs(True, restored)),
                                 ('pex-resistance-lumped-c', child.pex)]:
                child.run(name, action)
        (child.work / 'summary.json').write_text(json.dumps(child.results, indent=2) + '\n')
        failed = [name for name, result in child.results.items() if result['status'] != 'PASS']
        if failed:
            raise RuntimeError(f'GDS round-trip failed {", ".join(failed)}; reports: {child.work}')
        return f'GDS-reimported hierarchy passes Magic DRC/antenna/LVS and lumped-RC extraction; reports: {child.work}'

    def drc(self):
        directory, _ = self.magic('drc', '''drc euclidean on
drc style drc(full)
drc check
drc catchup
set report [open drc.txt w]
set count 0
foreach {why rectangles} [drc listall why] {
    puts $report $why
    foreach rectangle $rectangles { puts $report $rectangle; incr count }
}
puts $report "COUNT=$count"
close $report''')
        count = int(re.search(r'COUNT=(\d+)', (directory / 'drc.txt').read_text())[1])
        if count:
            raise RuntimeError(f'{count} Magic DRC error areas; see drc/drc.txt')
        return '0 Magic DRC error areas'

    def klayout_drc(self, antenna_only=False):
        name = 'antenna-klayout' if antenna_only else 'drc-klayout'
        directory = self.work / name
        args = ['python3', PDK / 'libs.tech/klayout/tech/drc/run_drc.py',
                f'--path={self.export()}', f'--topcell={self.cell}',
                f'--run_dir={directory}', '--mp=1', '--density_thr=2',
                '--antenna_only' if antenna_only else '--antenna']
        tool_error = None
        try:
            self.command(name, args)
        except RuntimeError as error:
            tool_error = error
        # The serial runner only merges after every requested deck completes.
        # Requiring the full report prevents a partial main-only run going green.
        suffix = 'antenna' if antenna_only else 'full'
        report = directory / f'{self.cell}_{self.cell}_{suffix}.lyrdb'
        if not report.is_file():
            raise RuntimeError(f'incomplete KLayout run; see {name}.log')
        count = len(ET.parse(report).findall('.//items/item'))
        if count:
            raise RuntimeError(f'{count} KLayout markers; see {name}/*.lyrdb')
        if tool_error:
            raise tool_error
        return '0 markers (antenna only)' if antenna_only else '0 markers (all installed rules + antenna + density + extra)'

    def antenna(self):
        directory, _ = self.magic('antenna', '''extract path .
extract all
feedback clear
antennacheck
feedback save antenna.feedback.tcl
set report [open antenna.txt w]
puts $report [feedback count]
close $report''')
        count = int((directory / 'antenna.txt').read_text().strip())
        if count:
            raise RuntimeError(f'{count} Magic antenna markers; see antenna/antenna.feedback.tcl')
        return '0 Magic antenna markers'

    def lvs(self, klayout=False, layout=None):
        name = 'lvs-klayout' if klayout else 'lvs-magic'
        directory = self.work / name
        directory.mkdir()
        suffix = 'cdl' if klayout else 'spice'
        reference = directory / f'{self.cell}.{suffix}'
        command = (f'set spiceprefix 1; set lvs_netlist {int(klayout)}; '
                   'set top_is_subckt 1; set lvs_ignore 1; set ev_precision 5; '
                   f'set netlist_dir {{{directory}}}; '
                   f'xschem set netlist_name {{{reference.name}}}; xschem netlist')
        self.command(name + '-schematic', ['xschem', '-s', '-r', '-x', '-q',
                     '--rcfile', self.schematic / 'xschemrc', '--command', command,
                     self.schematic / f'{self.cell}.sch'], cwd=self.schematic)
        if not reference.is_file() or not re.search(
                rf'^\.subckt\s+{self.cell}\s', reference.read_text(), re.M | re.I):
            raise RuntimeError('Xschem did not produce a top-level subcircuit')
        # These two loop-filter directives load simulator device models, not
        # circuit hierarchy. LVS uses the PDK's own device definitions instead.
        # Preserve the raw export; never strip arbitrary circuit includes.
        raw = reference.read_text()
        reference.with_suffix('.raw.' + suffix).write_text(raw)
        # mm_ok controls simulator mismatch modelling, not physical geometry.
        # Netgen cannot match it to extracted devices. Keep all W/L/M/NG
        # properties and reject actual property errors in the report below.
        raw = re.sub(r'(?m)^X\S+[^\n]*\bsg13_lv_[np]mos\b[^\n]*',
                     lambda m: re.sub(r'[ \t]+mm_ok=\S+', '', m[0]), raw)
        reference.write_text(re.sub(
            r'(?im)^\.(?:lib[ \t]+cornerRES\.lib[ \t]+\S+|include[ \t]+cap_cmomf\.lib)[ \t]*$',
            '* Simulator model supplied by the PDK LVS setup', raw))
        if layout is None:
            layout = self.export() if klayout else self.inputs / f'{self.cell}.mag'
        self.command(name, ['sak-lvs.sh', '-d', '-k' if klayout else '-m',
                           '-w', directory, '-s', reference, '-l', layout, '-c', self.cell])
        if not klayout:
            report = directory / f'{self.cell}.magic.lvs' / f'{self.cell}.lvs.out'
            result = report.read_text()
            if 'Final result: Circuits match uniquely.' not in result or re.search(r'property errors', result, re.I):
                raise RuntimeError(f'Netgen topology/property mismatch; see {report}')
        return 'schematic and layout match'

    def pex(self):
        directory, log = self.magic('pex', f'''flatten {self.cell}_pex
load {self.cell}_pex
select top cell
extract path .
extract do capacitance
extract do coupling
extract do resistance
extract all
ext2spice lvs
ext2spice resistor tee off
ext2spice hierarchy off
ext2spice subcircuit top on
ext2spice cthresh 0
ext2spice rthresh 0
ext2spice extresist off
ext2spice -o {self.cell}_c_only.spice
ext2sim labels on
ext2sim
extresist threshold 0
extresist minres 1
extresist mindelay 0
extresist all
ext2spice lvs
ext2spice resistor tee off
ext2spice hierarchy off
ext2spice subcircuit top on
ext2spice cthresh 0
ext2spice rthresh 0
ext2spice extresist on
ext2spice -o {self.cell}_pex.spice''')
        if re.search(r'(?i)Error in extracting node|Couldn.t find device|'
                     r'Orphaned node|Ports .*electrically shorted', log):
            raise RuntimeError('extraction errors, orphaned nodes, or shorted ports; see pex.log')
        if not list(directory.glob('*.res.ext')):
            raise RuntimeError('no resistance extraction output produced')
        netlist = directory / f'{self.cell}_pex.spice'
        text = netlist.read_text()
        if not re.search(rf'^\.subckt\s+{self.cell}_pex\s', text, re.M | re.I):
            raise RuntimeError('PEX netlist has no expected top subcircuit')
        # Magic 8.3.681 extresist distributes coupling as grounded C while
        # retaining the original explicit coupling. Use the independently
        # exported flat C matrix, attached at the original named nodes.
        # This is full resistance + LUMPED coupled C, not spatially resolved C.
        # Keep the raw export and reject missing/shorted capacitor endpoints.
        reference = (directory / f'{self.cell}_c_only.spice').read_text()
        caps = re.findall(r'^C\S+[^\n]*', reference, re.M)
        parents = {}

        def root(node):
            parents.setdefault(node, node)
            if parents[node] != node:
                parents[node] = root(parents[node])
            return parents[node]

        connected = set(re.search(r'^\.subckt\s+\S+\s+([^\n]+)', text, re.M)[1].split())
        for line in text.splitlines():
            fields = line.split()
            if fields and fields[0][0] in ('R', 'X'):
                connected.update(fields[1:3] if fields[0][0] == 'R' else fields[1:5])
            if fields and fields[0][0] == 'R':
                parents[root(fields[1])] = root(fields[2])
        endpoints = {node for cap in caps for node in cap.split()[1:3]}
        missing = endpoints - connected - {'0'}
        (directory / 'capacitance_endpoint_audit.json').write_text(json.dumps({
            'reference': f'{self.cell}_c_only.spice',
            'reference_sha256': hashlib.sha256(reference.encode()).hexdigest(),
            'resistance_export_sha256': hashlib.sha256(text.encode()).hexdigest(),
            'missing_endpoints': sorted(missing),
            'affected_capacitors': [cap for cap in caps if missing.intersection(cap.split()[1:3])],
        }, indent=2) + '\n')
        if missing:
            raise RuntimeError('C-only endpoints absent from resistance network: '
                               + ', '.join(sorted(missing))
                               + '; see pex/capacitance_endpoint_audit.json')
        if len({root(node) for node in endpoints}) != len(endpoints):
            raise RuntimeError('resistance network shorts distinct C-only endpoints')
        netlist.with_name(f'{self.cell}_raw_extresist.spice').write_text(text)
        text = re.sub(r'^C\S+[^\n]*\n', '', text, flags=re.M)
        text = re.sub(r'^\.ends\b', '\n'.join(caps) + '\n.ends', text, count=1, flags=re.M)
        netlist.write_text(text)
        (directory / 'capacitance_model.json').write_text(json.dumps({
            'mode': 'full resistance; original-node lumped ground and coupling capacitance',
            'reference': f'{self.cell}_c_only.spice',
            'capacitors_preserved': len(caps),
            'limitations': 'No spatial distribution of C along wires; not foundry-qualified extraction',
        }, indent=2) + '\n')
        resistors = len(re.findall(r'^R\S+\s', text, re.M | re.I))
        capacitors = len(re.findall(r'^C\S+\s', text, re.M | re.I))
        self.command('pex-ports', ['python3', REPO / 'scripts/check_pex_ports.py', netlist])
        return (f'extracted {resistors} resistors, {capacitors} original-node lumped capacitors; '
                'C matrix preserved; port-fragment check passed (LVS still required)')

    def run(self, name, action):
        try:
            detail = action()
            self.results[name] = {'status': 'PASS', 'detail': detail}
        except (OSError, ValueError, RuntimeError, ET.ParseError, TypeError) as error:
            self.results[name] = {'status': 'FAIL', 'detail': str(error)}
        print(f"  {name}: {self.results[name]['status']} — {self.results[name]['detail']}", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=MODES)
    parser.add_argument('cells', nargs='*', metavar='CELL', help=', '.join(CELLS))
    parser.add_argument('--library', type=Path, default=ROOT / 'mag',
                        help='candidate .mag library; defaults to the manual library')
    parser.add_argument('--schematic-library', type=Path, default=SCHEM,
                        help='matching Xschem sources, snapshotted before checking')
    args = parser.parse_args()
    args.library = args.library.resolve()
    if not args.library.is_dir():
        parser.error(f'layout library not found: {args.library}')
    args.cells = args.cells or ['pll_analog']
    for cell in args.cells:
        if cell not in CELLS:
            parser.error(f'unknown cell {cell}; choose from {", ".join(CELLS)}')
    for tool in ('magic', 'klayout', 'xschem', 'netgen', 'sak-lvs.sh'):
        if not shutil.which(tool):
            parser.error(f'{tool} missing; run inside IIC-OSIC-TOOLS')
    if not RC.is_file():
        parser.error(f'PDK startup file not found: {RC}')
    os.environ.update(PDK_ROOT=str(PDK.parent), PDK=PDK.name, PDKPATH=str(PDK),
                      STD_CELL_LIBRARY='sg13cmos5l_stdcell')
    failed = False
    for cell in dict.fromkeys(args.cells):
        print(f'Checking {cell} (saved .mag sources)', flush=True)
        checks = Checks(cell, args.library, args.schematic_library.resolve())
        checks.run('input-hierarchy', lambda: checks.validate_hierarchy(cell, set()))
        mode = args.mode
        if checks.results['input-hierarchy']['status'] != 'PASS':
            mode = None  # Do not let Magic silently substitute an empty missing child.
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
        summary = '\n'.join(f"{name}: {r['status']} — {r['detail']}" for name, r in checks.results.items())
        (checks.work / 'summary.txt').write_text(summary + '\n')
        print(f'Reports: {checks.work}\n', flush=True)
        failed |= any(r['status'] != 'PASS' for r in checks.results.values())
    return int(failed)


if __name__ == '__main__':
    sys.exit(main())
