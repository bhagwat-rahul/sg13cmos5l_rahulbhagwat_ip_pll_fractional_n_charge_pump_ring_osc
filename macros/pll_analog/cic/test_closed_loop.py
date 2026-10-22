"""Public reporter regression: stable fractional phase is not drift or a slip."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import numpy as np


class PhaseLockReport(unittest.TestCase):
    def test_phase_gate(self):
        time = np.arange(0., 4e-6 + 25e-12, 50e-12)
        cycles = 100e6 * time
        # Frequency accuracy alone cannot distinguish any of these cases.
        for case, divide, expected in (
                ('constant_offset', 20., 'PASS'),
                ('fractional_pattern', 19.125, 'PASS'),
                ('slow_drift', 20., 'FAIL'),
                ('below_drift_limit', 20., 'PASS'),
                ('above_drift_limit', 20., 'FAIL'),
                ('slip_and_recover', 20., 'FAIL'),
                ('late_feedback_start', 20., 'FAIL'),
                ('missing_feedback', 20., 'INSUFFICIENT')):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as folder:
                output = Path(folder)
                phase = np.full_like(time, .031)
                if case == 'fractional_pattern':
                    phase += .04 * np.sin(2 * np.pi * cycles / 16)
                elif case == 'slow_drift':
                    phase += 1e4 * time  # 100 ps/us drift, despite <1% frequency error.
                elif case == 'below_drift_limit':
                    phase += 2e3 * time  # 20 ps/us.
                elif case == 'above_drift_limit':
                    phase += 3e3 * time  # 30 ps/us.
                elif case == 'slip_and_recover':
                    phase += np.interp(time, [0, 3e-6, 3.5e-6, 4e-6], [0, 0, 1, 0])
                columns = {
                    'time': time,
                    'v(test_clk)': .6 + .6 * np.sin(2 * np.pi * 100e6 * divide / 4 * time),
                    'v(x_pll.x_analog.vctrl)': np.full_like(time, .6),
                    'v(x_pll.up)': .6 + .6 * np.sin(2 * np.pi * cycles),
                    'v(x_pll.down)': .6 + .6 * np.sin(2 * np.pi * (cycles + .01)),
                    'v(ref_clk)': .6 + .6 * np.sin(2 * np.pi * cycles),
                }
                if case != 'missing_feedback':
                    columns['v(x_pll.fb_clk)'] = .6 + .6 * np.sin(2 * np.pi * (cycles + phase))
                    if case == 'late_feedback_start':
                        columns['v(x_pll.fb_clk)'][time < 3.8e-6] = 0.
                header = (f'Flags: real\nNo. Variables: {len(columns)}\n'
                          f'No. Points: {len(time)}\nVariables:\n'
                          + ''.join(f'\t{i}\t{name}\tvoltage\n'
                                    for i, name in enumerate(columns)) + 'Binary:\n')
                raw = output / 'wave.raw'
                raw.write_bytes(header.encode() + np.column_stack(list(columns.values()))
                                .astype('<f8').tobytes())
                run = subprocess.run([
                    sys.executable, str(Path(__file__).with_name('report_closed_loop.py')),
                    str(raw), '--output', str(output / 'report'), '--label', case,
                    '--divide', str(divide), '--require-phase-lock'], capture_output=True, text=True)
                report = json.loads((output / 'report/report.json').read_text())
                self.assertTrue(report['frequency_within_1pct'])
                self.assertEqual(report['phase_lock_screen']['status'], expected, run.stderr)
                self.assertEqual(run.returncode, 0 if expected == 'PASS' else 1, run.stderr)


if __name__ == '__main__':
    unittest.main()
