#!/usr/bin/env python3
"""Report closed-loop transient evidence, not foundry/noise/timing signoff.

Consumes the binary real ngspice waveform from run_pll_cosim.sh. Frequency
lock is a sampled 1% frequency-band diagnostic, not phase-lock proof.
Sidebands are deterministic simulated TEST_CLK voltage sidebands; transient
noise, pad/package/substrate coupling and unmodeled digital timing are absent.
"""

import argparse
import hashlib
import json
from pathlib import Path
import re

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np


def crossings(time, voltage, level, rising=True):
    indices = np.flatnonzero((voltage[:-1] < level) & (voltage[1:] >= level)
                             if rising else (voltage[:-1] >= level) & (voltage[1:] < level))
    return time[indices] + (time[indices + 1] - time[indices]) * (
        level - voltage[indices]) / (voltage[indices + 1] - voltage[indices])


def pulse_widths(time, voltage, vdd):
    rises = crossings(time, voltage, vdd / 2)
    falls = crossings(time, voltage, vdd / 2, False)
    indices = np.searchsorted(falls, rises)
    valid = indices < len(falls)
    widths = (falls[indices[valid]] - rises[valid]) * 1e12
    return {'complete_pulses': len(widths),
            'minimum_ps': float(np.min(widths)) if len(widths) else None,
            'maximum_ps': float(np.max(widths)) if len(widths) else None,
            'mean_ps': float(np.mean(widths)) if len(widths) else None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('waveform', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--label', required=True)
    parser.add_argument('--vdd', type=float, default=1.2)
    parser.add_argument('--fref', type=float, default=100e6)
    parser.add_argument('--divide', type=float, default=20)
    parser.add_argument('--test-div', type=int, default=1)
    parser.add_argument('--vctrl-node', default='x_pll.x_analog.vctrl')
    args = parser.parse_args()
    raw = args.waveform.read_bytes()
    header, payload = raw.split(b'Binary:\n', 1)
    header = header.decode()
    if 'Flags: real' not in header:
        raise ValueError('expected binary real ngspice data')
    count = int(re.search(r'No. Variables:\s+(\d+)', header)[1])
    points = int(re.search(r'No. Points:\s+(\d+)', header)[1])
    names = re.findall(r'^[ \t]*\d+[ \t]+(\S+)[ \t]+\S+(?:[ \t]+dims=1)?[ \t]*$',
                       header.split('Variables:\n')[1], re.M)
    if len(names) != count or len(payload) != count * points * 8:
        raise ValueError('incomplete waveform or unsupported raw format')
    data = np.frombuffer(payload, dtype='<f8').reshape(points, count)
    vectors = dict(zip((n.lower() for n in names), data.T))
    time = vectors['time']
    vctrl = vectors[f'v({args.vctrl_node.lower()})']
    output = vectors['v(test_clk)']
    if not np.isfinite(data).all() or np.any(np.diff(time) <= 0):
        raise ValueError('nonfinite data or nonincreasing time')
    if time[-1] < 2e-6:
        raise ValueError('need at least 2 us, including 1 us settled window')
    start = time[-1] - 1e-6
    settled = time >= start
    ts, vs, ys = time[settled], vctrl[settled], output[settled]
    target = args.fref * args.divide / 2 ** (args.test_div + 1)
    edges = crossings(ts, ys, args.vdd / 2)
    if len(edges) < 102:
        raise ValueError('insufficient settled output edges')
    periods = np.diff(edges)
    frequency = 1 / np.mean(periods)
    all_edges = crossings(time, output, args.vdd / 2)
    windows = []
    for window_start in np.arange(.5e-6, time[-1] - .5e-6 + 1e-15, .25e-6):
        e = all_edges[all_edges >= window_start][:101]
        windows.append({'start_s': float(window_start),
                        'frequency_hz': float(100 / (e[-1] - e[0])) if len(e) == 101 else None})
    lock = next((w['start_s'] for i, w in enumerate(windows)
                 if all(x['frequency_hz'] is not None and abs(x['frequency_hz'] / target - 1) <= .01
                        for x in windows[i:])), None)
    # Uniform interpolation, Hann window, direct spectral projections at the
    # measured carrier and its ±fref offsets. Not a phase-noise measurement.
    sample_time = np.arange(start, time[-1], 5e-12)
    signal = np.interp(sample_time, time, output)
    signal = signal - np.mean(signal)
    window = np.hanning(len(signal))
    def amplitude(f):
        return abs(np.sum(signal * window * np.exp(-2j * np.pi * f * (sample_time - start))))
    carrier = amplitude(frequency)
    sidebands = {side: float(20 * np.log10(amplitude(frequency + offset) / carrier))
                 for side, offset in [('lower', -args.fref), ('upper', args.fref)]}
    result = {'label': args.label, 'waveform_sha256': hashlib.sha256(raw).hexdigest(),
              'vdd_v': args.vdd, 'reference_hz': args.fref, 'target_output_hz': target,
              'stop_s': float(time[-1]), 'settled_start_s': start,
              'measured_output_hz': float(frequency),
              'frequency_within_1pct': bool(abs(frequency / target - 1) <= .01),
              'lock_time_s_1pct_sampled': lock, 'frequency_windows': windows,
              'vctrl_mean_v': float(np.trapezoid(vs, ts) / (ts[-1] - ts[0])),
              'vctrl_ripple_pp_v': float(np.ptp(vs)),
              'rms_period_variation_s': float(np.std(periods)),
              'peak_to_peak_period_variation_s': float(np.ptp(periods)),
              'deterministic_test_clock_sidebands_dbc': sidebands,
              'up': pulse_widths(ts, vectors['v(x_pll.up)'][settled], args.vdd),
              'down': pulse_widths(ts, vectors['v(x_pll.down)'][settled], args.vdd),
              'limitations': __doc__}
    vco = vectors.get('v(x_pll.vco_clk)')
    result['vco'] = {'observed': vco is not None}
    if vco is not None:
        ve = crossings(ts, vco[settled], args.vdd / 2)
        vf = float((len(ve) - 1) / (ve[-1] - ve[0])) if len(ve) > 1 else None
        result['vco'].update(frequency_hz=vf, target_hz=args.fref * args.divide,
                             frequency_within_1pct=bool(vf is not None and
                                 abs(vf / (args.fref * args.divide) - 1) <= .01))
    feedback, reference = vectors.get('v(x_pll.fb_clk)'), vectors.get('v(ref_clk)')
    if feedback is not None and reference is not None:
        fe = crossings(time, feedback, args.vdd / 2)
        ref_edges = crossings(ts, reference[settled], args.vdd / 2)
        if len(fe) > 1:
            ref_edges = ref_edges[(ref_edges >= fe[0]) & (ref_edges <= fe[-1])]
            if len(ref_edges) > 1:
                # Continuous feedback phase at successive reference edges.
                # Unlike nearest-edge subtraction, this retains cycle slips.
                phase = np.interp(ref_edges, fe, np.arange(len(fe))) - np.arange(len(ref_edges))
                result['feedback_phase'] = {
                    'reference_edges': len(ref_edges),
                    'relative_phase_pp_ps': float(np.ptp(phase) / args.fref * 1e12),
                    'relative_phase_drift_ps': float((phase[-1] - phase[0]) / args.fref * 1e12),
                    'note': 'Relative to first measured edge; no phase-lock acceptance threshold imposed.'}
    buffered = [name for name in vectors if re.fullmatch(
        r'v\(x_pll\.x_receiver\.xreceiver\.load_\d+_out\)', name)]
    if len(buffered) > 1:
        raise ValueError('ambiguous physical feedback buffer waveform')
    clocks = {'physical_receiver': vectors.get('v(x_pll.x_receiver.div2)'),
              'buffered_feedback_clock': vectors[buffered[0]] if buffered else None}
    for name, q in clocks.items():
        if q is None:
            result[name] = {'observed': False}
            continue
        qe = crossings(ts, q[settled], args.vdd / 2)
        cycle_peaks, cycle_lows = [], []
        for a, b in zip(qe, qe[1:]):
            values = q[np.searchsorted(time, a):np.searchsorted(time, b)]
            cycle_peaks.append(float(np.max(values)))
            cycle_lows.append(float(np.min(values)))
        result[name] = {
            'observed': True,
            'complete_cycles': len(cycle_peaks),
            'frequency_hz': float((len(qe) - 1) / (qe[-1] - qe[0])) if len(qe) > 1 else None,
            'worst_cycle_peak_v': min(cycle_peaks) if cycle_peaks else None,
            'worst_cycle_low_v': max(cycle_lows) if cycle_lows else None,
            'every_complete_cycle_swing_pass': bool(cycle_peaks and min(cycle_peaks) >= .9 * args.vdd
                                                   and max(cycle_lows) <= .1 * args.vdd)}
        if vco is not None and len(qe) > 1:
            counts = np.diff(np.searchsorted(ve, qe, side='left'))
            result[name]['vco_edges_per_q_cycle_min'] = int(np.min(counts))
            result[name]['vco_edges_per_q_cycle_max'] = int(np.max(counts))
            result[name]['every_complete_cycle_divides_by_two'] = bool(np.all(counts == 2))
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / 'report.json').write_text(json.dumps(result, indent=2) + '\n')
    fig, axes = plt.subplots(2, 2, figsize=(12, 7.5))
    stride = max(1, len(time) // 12000)
    axes[0, 0].plot(time[::stride] * 1e6, vctrl[::stride], color='#0072b2')
    axes[0, 0].axvline(start * 1e6, color='#777777', linestyle='--', label='Measurement window')
    axes[0, 0].set(xlabel='Time (µs)', ylabel='VCTRL (V)', title='Acquisition')
    axes[0, 0].legend(fontsize=8)
    axes[0, 1].plot([w['start_s'] * 1e6 for w in windows],
                    [w['frequency_hz'] / 1e6 if w['frequency_hz'] else np.nan for w in windows], '.-')
    axes[0, 1].axhspan(target * .99 / 1e6, target * 1.01 / 1e6, alpha=.15, color='green', label='±1% frequency band')
    axes[0, 1].set(xlabel='Window start (µs)', ylabel='TEST_CLK frequency (MHz)', title='Sampled frequency convergence')
    axes[0, 1].legend(fontsize=8)
    tail = time >= time[-1] - 30e-9
    x = (time[tail] - time[-1]) * 1e9
    axes[1, 0].plot(x, (vctrl[tail] - result['vctrl_mean_v']) * 1e3, color='#0072b2')
    axes[1, 0].set(xlabel='Time relative to stop (ns)', ylabel='VCTRL − settled mean (mV)', title='Final three reference periods')
    for name, color in [('up', '#d55e00'), ('down', '#0072b2')]:
        axes[1, 1].plot(x, vectors[f'v(x_pll.{name})'][tail], label=name.upper(), color=color)
    axes[1, 1].set(xlabel='Time relative to stop (ns)', ylabel='PFD output (V)', title='Actual simulated charge-pump drive')
    axes[1, 1].legend(fontsize=8)
    for ax in axes.flat:
        ax.grid(alpha=.2)
    fig.suptitle(args.label + '\nExploratory simulation; not full-chip signoff', fontsize=12)
    fig.tight_layout()
    fig.savefig(args.output / 'closed_loop.png', dpi=160)
    plt.close(fig)
    print(json.dumps({k: v for k, v in result.items() if k != 'frequency_windows'}, indent=2))


if __name__ == '__main__':
    main()
