#!/usr/bin/env python3
"""Check saved SG13CMOS5L Magic cells without modifying the design sources."""

import argparse
from datetime import datetime
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
MODES = ('all', 'drc', 'drc-klayout', 'drc-all', 'antenna', 'lvs', 'pex')
PDK = Path(os.environ.get('PDK_ROOT', '/foss/pdks')) / 'ihp-sg13cmos5l'
RC = PDK / 'libs.tech/magic/ihp-sg13cmos5l.magicrc'


class Checks:
    def __init__(self, cell, library):
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
                r'Bad Device Location|Missing (?:terminal|substrate) connection', log):
            raise RuntimeError(f'Magic error or incomplete run; see {name}.log')
        return directory, log

    def export(self):
        if not self.exported:
            self.magic('export', f'gds write {{{self.work / (self.cell + ".gds")}}}')
            if not (self.work / f'{self.cell}.gds').stat().st_size:
                raise RuntimeError('empty GDS export')
            self.exported = True
        return self.work / f'{self.cell}.gds'

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

    def lvs(self, klayout=False):
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
                     '--rcfile', SCHEM / 'xschemrc', '--command', command,
                     SCHEM / f'{self.cell}.sch'], cwd=SCHEM)
        if not reference.is_file() or not re.search(
                rf'^\.subckt\s+{self.cell}\s', reference.read_text(), re.M | re.I):
            raise RuntimeError('Xschem did not produce a top-level subcircuit')
        # These two loop-filter directives load simulator device models, not
        # circuit hierarchy. LVS uses the PDK's own device definitions instead.
        # Preserve the raw export; never strip arbitrary circuit includes.
        raw = reference.read_text()
        reference.with_suffix('.raw.' + suffix).write_text(raw)
        reference.write_text(re.sub(
            r'(?im)^\.(?:lib[ \t]+cornerRES\.lib[ \t]+\S+|include[ \t]+cap_cmomf\.lib)[ \t]*$',
            '* Simulator model supplied by the PDK LVS setup', raw))
        layout = self.export() if klayout else self.inputs / f'{self.cell}.mag'
        self.command(name, ['sak-lvs.sh', '-d', '-k' if klayout else '-m',
                           '-w', directory, '-s', reference, '-l', layout, '-c', self.cell])
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
        if endpoints - connected - {'0'}:
            raise RuntimeError('C-only extraction has endpoints absent from the resistance network')
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
        checks = Checks(cell, args.library)
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
        (checks.work / 'summary.json').write_text(json.dumps(checks.results, indent=2) + '\n')
        summary = '\n'.join(f"{name}: {r['status']} — {r['detail']}" for name, r in checks.results.items())
        (checks.work / 'summary.txt').write_text(summary + '\n')
        print(f'Reports: {checks.work}\n', flush=True)
        failed |= any(r['status'] != 'PASS' for r in checks.results.values())
    return int(failed)


if __name__ == '__main__':
    sys.exit(main())
