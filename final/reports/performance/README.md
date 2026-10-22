# PLL performance screens — 2026-10-22

These nine JSON reports are pre-RC closed-loop performance summaries, **not
electrical signoff of `final/gds/slot_13.gds`**. They use ngspice/Verilator
co-simulation: schematic analog, frozen transistor-level receiver and PFD
with selected nominal digital RC, and functional RTL for the remaining
digital logic. They do not model the complete extracted slot or chip fill.

All runs use a 100-MHz reference, TEST_DIV=1 (VCO/4 output), and a 7-us
transient; results below cover the final 6–7-us window. DIV_RATIO encodes
8 times N: integer N20 uses 160; fractional N19.125/19.5/19.875 use
153/156/159. TT/SF/FS use 1.20 V, 27 C; SS uses 1.08 V, 125 C;
FF uses 1.32 V, -40 C. This is a sampled corner screen, not a full
process × voltage × temperature or divider-ratio sweep.

| Report | Target output (MHz) | Measured output (MHz) | Pattern-mean phase spread (ps) | Fitted phase drift (ps/us) | VCTRL ripple (mVpp) |
| --- | ---: | ---: | ---: | ---: | ---: |
| [Integer TT](integer-tt.json) | 500.000 | 499.998005 | 5.000 | -0.037 | 3.481 |
| [Integer SS](integer-ss.json) | 500.000 | 500.002523 | 5.000 | -0.271 | 2.883 |
| [Integer FF](integer-ff.json) | 500.000 | 500.000185 | 9.139 | +0.185 | 3.474 |
| [Integer SF](integer-sf.json) | 500.000 | 499.998005 | 4.763 | -0.061 | 3.534 |
| [Integer FS](integer-fs.json) | 500.000 | 500.000510 | 5.000 | +0.529 | 3.439 |
| [Fractional TT N19.125](fractional-tt-n19p125.json) | 478.125 | 478.162633 | 0.430 | -0.005 | 6.823 |
| [Fractional TT N19.5](fractional-tt-n19p5.json) | 487.500 | 487.502838 | 3.654 | +0.118 | 5.061 |
| [Fractional TT N19.875](fractional-tt-n19p875.json) | 496.875 | 497.000713 | 0.417 | +0.065 | 10.860 |
| [Fractional SS N19.875](fractional-ss-n19p875.json) | 496.875 | 496.988506 | 0.375 | -0.111 | 8.980 |

All nine pass the sampled ±1% output-frequency screen, every-complete-cycle
receiver swing and divide-by-two checks, and the **provisional** phase screen.
The latter requires ≤25-ps spread of complete-pattern means, ≤25-ps/us
absolute fitted drift, at least four complete patterns, full measurement
window coverage and <0.5-reference-cycle unwrapped phase excursion.
These are diagnostic thresholds, not agreed product jitter/phase specifications.
Fractional pattern averaging does not bound instantaneous phase modulation:
raw phase excursions remain in each JSON. Finite-window frequency estimates
also include fractional modulation and are not exact long-term ratio errors.

TT and FF failed the earlier 3–4-us phase screen; their extended 6–7-us
windows pass. This supports continued settling, but does not establish an
exact phase-lock acquisition time. N19.125 uses the corrected complete-pattern
coverage report of the same waveform, rather than its earlier coverage failure.
`lock_time_s_1pct_sampled` is a frequency-convergence diagnostic, not phase-lock time.

Excluded: full-slot RC/post-fill effects, full digital timing, pad/package
loads, supply/substrate coupling, mismatch and transient-noise phase noise or
jitter. Reported period variation and sidebands are deterministic simulation
metrics, not measured noise performance. No new simulations were run for this
report snapshot; large waveforms and logs remain in local artifacts.

## Source artifacts

JSON files are unchanged copies from repository-local `.amp/in/artifacts/`:

- Integer TT/FF: `slot13-20261022-phase-{tt,ff}-7us/report/report.json`.
- Integer SS/SF/FS: `slot13-20261022-perf-screen/{ss,sf,fs}-report/report.json`.
- Fractional TT N19.125: `slot13-20261022-phase-tt-ratio153/report.json`.
- Other fractional cases: `slot13-20261022-fractional-screen/`
  `{tt_ratio156,tt_ratio159,ss_ratio159}-report/report.json`.

The runner is `scripts/pll/run_pll_cosim.sh`; waveform analysis is
`macros/pll_analog/cic/report_closed_loop.py`. JSON labels, waveform hashes,
measurement windows and limitations preserve the available run provenance.
