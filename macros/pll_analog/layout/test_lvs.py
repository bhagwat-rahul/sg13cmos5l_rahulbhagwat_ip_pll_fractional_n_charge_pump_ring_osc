"""Real-tool LVS regression: run inside IIC-OSIC-TOOLS with python3 -m unittest.

The loop filter must retain its modeled capacitors, compare dimensions and
stack, and reject a changed reference rather than merely returning exit 0.
"""

import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent
SCHEM = ROOT.parent / 'schematic/xschem'


class LoopFilterLVS(unittest.TestCase):
    def test_model_view_and_wrong_reference(self):
        (ROOT / 'build').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / 'build') as folder:
            schematic = Path(folder)
            for path in SCHEM.iterdir():
                if path.suffix in ('.sch', '.sym') or path.name == 'xschemrc':
                    shutil.copy2(path, schematic / path.name)
            original = (schematic / 'loop_filter.sch').read_text()
            for label, text in (
                ('correct', original),
                ('wrong_width', original.replace('w=100u', 'w=120u')),
                ('wrong_stack', original.replace('mmin=2', 'mmin=1')),
            ):
                with self.subTest(reference=label):
                    if label != 'correct':
                        self.assertNotEqual(text, original)
                    (schematic / 'loop_filter.sch').write_text(text)
                    result = subprocess.run(
                        [sys.executable, str(ROOT / 'run_checks.py'), 'lvs', 'loop_filter',
                         '--schematic-library', str(schematic)],
                        capture_output=True, text=True)
                    reports = re.findall(r'^Reports: (.+)$', result.stdout, re.M)
                    self.assertEqual(len(reports), 1, result.stdout + result.stderr)
                    summary = json.loads((Path(reports[0]) / 'summary.json').read_text())
                    if label == 'correct':
                        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                        self.assertEqual(summary['lvs-magic']['status'], 'PASS')
                        self.assertEqual(summary['lvs-klayout']['status'], 'PASS')
                    else:
                        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                        self.assertEqual(summary['lvs-magic']['status'], 'FAIL')
                        if label == 'wrong_width':
                            self.assertEqual(summary['lvs-klayout']['status'], 'FAIL')


if __name__ == '__main__':
    unittest.main()
