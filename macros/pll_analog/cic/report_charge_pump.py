#!/usr/bin/env python3
"""Summarize the loaded-PFD sweep; never turn unbudgeted metrics into a pass."""

import argparse
import itertools
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    rows = json.loads((args.run / 'summary.json').read_text())
    if len(rows) not in (3, 198):
        raise ValueError(f'incomplete sweep: {len(rows)} cases; expected 3 smoke or 198 full')
    args.output.mkdir(parents=True, exist_ok=False)
    curves = []
    corners = list(dict.fromkeys(r['corner'] for r in rows))
    volts = sorted({r['vctrl_V'] for r in rows})
    slews = sorted({r['input_edge_ps'] for r in rows})
    for corner, vctrl, slew in itertools.product(corners, volts, slews):
        group = sorted([r for r in rows if (r['corner'], r['vctrl_V'], r['input_edge_ps']) == (corner, vctrl, slew)],
                       key=lambda r: r['feedback_minus_reference_ps'])
        if len(group) != (3 if len(rows) == 3 else 11):
            raise ValueError('incomplete phase curve')
        curve = dict(corner=corner, vctrl_V=vctrl, input_edge_ps=slew)
        for label in ('schematic', 'layout'):
            x = [r['feedback_minus_reference_ps'] for r in group]
            y = [r[label]['net_charge_fC'] for r in group]
            roots = [a - qa * (b - a) / (qb - qa) for a, b, qa, qb in zip(x, x[1:], y, y[1:])
                     if qa <= 0 < qb]
            slopes = [(b - a) / (xb - xa) * 1000 for a, b, xa, xb in zip(y, y[1:], x, x[1:])]
            zero = next(r for r in group if r['feedback_minus_reference_ps'] == 0)
            curve[label] = dict(zero_charge_phase_ps=roots,
                                monotonically_increasing=all(s > 0 for s in slopes),
                                minimum_incremental_gain_uA=min(slopes),
                                maximum_incremental_gain_uA=max(slopes),
                                zero_phase_charge_fC=zero[label]['net_charge_fC'],
                                zero_phase_UP=zero[label]['UP'], zero_phase_DOWN=zero[label]['DOWN'])
        if len(curve['layout']['zero_charge_phase_ps']) == len(curve['schematic']['zero_charge_phase_ps']) == 1:
            curve['equilibrium_shift_ps'] = curve['layout']['zero_charge_phase_ps'][0] - curve['schematic']['zero_charge_phase_ps'][0]
        curves.append(curve)
    tail_results = []
    for r in rows:
        tag = f"{r['corner']}_v{r['vctrl_V']}_e{r['input_edge_ps']}_phase{r['feedback_minus_reference_ps']}"
        samples = [list(map(float, line.split())) for line in (args.run / (tag + '.dat')).read_text().splitlines()[1:]]
        window = [s for s in samples if 17e-9 <= s[0] <= 27e-9]
        record = {'case': tag}
        for label, current, up in [('schematic', 1, 3), ('layout', 2, 5)]:
            # A fixed diagnostic threshold, not a PLL performance budget.
            last_input_high = max(s[0] for s in window if max(s[up:up + 2]) > r['vdd_V'] / 2)
            quiet = r[label]['quiet_current_A']
            bad = [s[0] for s in window if s[0] >= last_input_high and abs(s[current] - quiet) > 100e-9]
            record[label + '_settle_to_100nA_ps'] = (max(bad) - last_input_high) * 1e12 if bad else 0.
            if abs(window[-1][current] - quiet) > 100e-9:
                record[label + '_settle_to_100nA_ps'] = None
        tail_results.append(record)
    report = {'completed_cases': len(rows), 'curves': curves, 'settling_diagnostic': tail_results,
              'decision_limits': 'Monotonicity/reset are functional screens. Charge offsets, gain and settling have no approved PLL performance budgets. Nominal wire RC; quiet neighbors; no package/substrate model.'}
    (args.output / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    for corner in corners:
        fig, axes = plt.subplots(1, len(volts), figsize=(6 * len(volts), 4.8), squeeze=False)
        for ax, voltage in zip(axes[0], volts):
            for slew in slews:
                group = sorted([r for r in rows if (r['corner'], r['vctrl_V'], r['input_edge_ps']) == (corner, voltage, slew)],
                               key=lambda r: r['feedback_minus_reference_ps'])
                for label, color in [('schematic', '#555555'), ('layout', '#0072b2')]:
                    ax.plot([r['feedback_minus_reference_ps'] / 1000 for r in group],
                            [r[label]['net_charge_fC'] for r in group],
                            color=color, linestyle='-' if slew == 20 else '--', marker='.',
                            label=f'{label}, input edge {slew} ps')
            ax.axhline(0, color='#aaaaaa', linewidth=.7)
            ax.axvline(0, color='#aaaaaa', linewidth=.7)
            ax.set(xlabel='Feedback − reference input phase (ns)', ylabel='Net delivered charge per cycle (fC)',
                   title=f'{corner.upper()}, VCTRL {voltage:.1f} V')
            ax.grid(alpha=.2)
            ax.legend(fontsize=8)
        fig.suptitle('Frozen transistor PFD + nominal routed RC, separately loaded by each charge pump')
        fig.tight_layout()
        fig.savefig(args.output / f'charge_phase_{corner}.png', dpi=160)
        plt.close(fig)
    lines = ['# Loaded-PFD charge-pump screening', '',
             f'Completed cases: {len(rows)}. No PLL performance acceptance budget is implied.', '',
             '| Corner | VCTRL (V) | Input edge (ps) | Schematic zero-Q phase (ps) | Layout zero-Q phase (ps) | Shift (ps) | Layout monotonic |',
             '| --- | ---: | ---: | --- | --- | ---: | --- |']
    for c in curves:
        roots = lambda label: ', '.join(f'{v:.1f}' for v in c[label]['zero_charge_phase_ps']) or 'not bracketed'
        shift = f"{c['equilibrium_shift_ps']:.1f}" if 'equilibrium_shift_ps' in c else '—'
        lines.append(f"| {c['corner']} | {c['vctrl_V']} | {c['input_edge_ps']} | {roots('schematic')} | {roots('layout')} | {shift} | {c['layout']['monotonically_increasing']} |")
    (args.output / 'report.md').write_text('\n'.join(lines) + '\n')
    print(f'Wrote {len(curves)} phase curves and {len(rows)} settling diagnostics: {args.output}')


if __name__ == '__main__':
    main()
