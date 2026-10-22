#!/usr/bin/env python3
"""Check routed slot13 against an independent, source-only assembly contract."""
import argparse
import hashlib
import json
import os
from pathlib import Path

from check_integration import CoreChecks, PDK, ROOT


class SlotChecks(CoreChecks):
    def prepare_reference(self):
        self.cell = 'pll_core'
        try:
            result = super().prepare_reference()
        finally:
            self.cell = 'slot_13'
        source_path = ROOT / 'schematic/slot_13.spice'
        source = source_path.read_text()
        for suffix in ('spice', 'cdl'):
            path = self.schematic / f'reference.{suffix}'
            path.write_text(source + '\n' + path.read_text())
        audit = self.work / 'reference/inputs.json'
        hashes = json.loads(audit.read_text())
        for path in (source_path, *self.schematic.glob('reference.*')):
            hashes[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
        audit.write_text(json.dumps(hashes, indent=2)+'\n')
        return 'independent slot_13 assembly + ' + result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('candidate', type=Path)
    parser.add_argument('--mode', choices=('quick', 'all', 'drc', 'lvs', 'antenna',
                                         'drc-klayout', 'pex'), default='quick')
    args = parser.parse_args()
    candidate = args.candidate.resolve()
    os.environ.update(PDK_ROOT=str(PDK.parent), PDK=PDK.name, PDKPATH=str(PDK),
                      STD_CELL_LIBRARY='sg13cmos5l_stdcell')
    checks = SlotChecks('slot_13', candidate / 'mag', work_root=candidate / 'checks')
    checks.run('input-hierarchy', lambda: checks.validate_hierarchy(checks.cell, set()))
    if checks.results['input-hierarchy']['status'] == 'PASS':
        mode = args.mode
        if mode in ('quick', 'all', 'lvs'):
            checks.run('source-reference', checks.prepare_reference)
        if mode in ('quick', 'all', 'drc'):
            checks.run('drc-magic', checks.drc)
        if mode in ('quick', 'all', 'lvs'):
            checks.run('lvs-magic', checks.lvs)
            checks.run('lvs-klayout', lambda: checks.lvs(True))
        if mode in ('all', 'antenna'):
            checks.run('antenna-magic', checks.antenna)
        if mode in ('all', 'drc-klayout'):
            checks.run('drc-klayout-full', checks.klayout_drc)
        if mode in ('all', 'pex'):
            checks.run('pex-resistance-native-c', checks.pex)
        checks.run('gds-export', lambda: str(checks.export()))
    (checks.work / 'summary.json').write_text(json.dumps(checks.results, indent=2)+'\n')
    print(f'Reports: {checks.work}', flush=True)
    return int(any(r['status'] != 'PASS' for r in checks.results.values()))


if __name__ == '__main__':
    raise SystemExit(main())
