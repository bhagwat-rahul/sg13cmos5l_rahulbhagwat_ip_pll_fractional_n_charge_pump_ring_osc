# SG13CMOS5L CIC experiments

**Experimental, not integration-ready.** Bias, charge pump, current-starved
inverter and output buffer have directed placement/routing and both-engine
LVS closure. Electrical qualification is in progress. The manual `../layout/mag/` library and frozen digital
macro are untouched. See `../../../docs/cic_analog_experiments.md` for
measured results, isolation/PDN intent, and the outstanding ESD gate.

Run from the repository root **inside IIC-OSIC-TOOLS**:

```sh
/opt/ciccreator/.venv/bin/python macros/pll_analog/cic/generate.py \
  --cell vco_bias --output macros/pll_analog/layout/build/cic-bias-001

python3 macros/pll_analog/layout/run_checks.py all vco_bias \
  --library macros/pll_analog/layout/build/cic-bias-001
```

Choose a new, empty output directory for each candidate. The generator
restricts outputs to the ignored `layout/build/` subtree. The checker
snapshots the candidate library into a new timestamped report directory;
it does not overwrite the candidate or manual sources. It returns failure
when any check fails, including global density. Existing `make check CELL`
commands still check the manual library by default.

For the current charge-pump recipe:

```sh
/opt/ciccreator/.venv/bin/python macros/pll_analog/cic/generate.py \
  --cell charge_pump --output macros/pll_analog/layout/build/cic-cp-next
python3 macros/pll_analog/layout/run_checks.py all charge_pump \
  --library macros/pll_analog/layout/build/cic-cp-next
```

All four routed leaves currently fail seven global-density rules; `all`
correctly returns nonzero. No density rule is waived. The physical ring is
implemented and undergoing corner screening. The loop filter is routed but
has unresolved LVS/PEX integration gates. Analog-top assembly is implemented;
its native-passive extraction, GDS reimport and electrical closure remain open.

## What is implemented

- Fresh Xschem netlisting on every generation, rather than old import SPICE.
- Project-local CIC MOS/passive provider using native Magic PDK generators. No
  changes to installed CIC packages. The original primitive geometry is
  retained, including implants/wells/taps.
- 5-nm grid and explicit Magic-to-CIC unit conversion, origin translation,
  and D/G/S/B accesses parsed from native device labels. All finger accesses
  are recorded in `manifest.json`. The adapter validates the alternating
  contact/gate chain to recover the native generator's unlabeled final
  diffusion stripe; routing connects every D/S finger.
- Charge-pump functional groups, same-orientation NMOS mirrors, preserved
  PMOS 8:7 width ratio, per-device contacted guards, 10-µm additional inverter
  setback, separate quiet/switching supply branches and redundant vias.
  Native 7-µm/8-finger PMOS rounds to 7.04 µm; explicitly using seven 1-µm
  fingers preserves total width and passes strict KLayout LVS. Both requested
  and physical parameters are recorded. No claim of common-centroid matching.
- Explicit local M1/M2 access, M3 channels/shields and M4 bridges. Switched
  current nodes and UP/UP_B remain local; VCTRL exits beside the switches.
  Long supply drops widen to 0.8 µm after narrow device escapes; supply
  branches/spines are 2 µm. No generic autorouter.
- Source/recipe/PDK-generator hashes, geometry/pin metadata, generation
  scripts and tool logs retained with each output.

`routing.tech` contains only the layer aliases required for this pilot.
It is **not** a full CIC technology port, routing-rule database, or signoff
deck. Verification uses the installed CMOS5L decks. Enlarged guard offsets
are process-generator parameters, not new wells or unsupported deep-well
structures. Mirrored-device access is not yet validated; these recipes use
only unmirrored placements.

## Reproduce the bias electrical screening

After running the full checker, substitute its printed timestamp below:

```sh
python3 macros/pll_analog/cic/characterize_bias.py \
  macros/pll_analog/layout/build/cic-bias-001/vco_bias.spice \
  macros/pll_analog/layout/build/vco_bias/TIMESTAMP/pex/vco_bias_pex.spice \
  --output macros/pll_analog/layout/build/cic-bias-dc-001
```

The script binds each circuit's ports by name, runs TT/SS/FF DC screening,
and saves replayable decks, ngspice logs, voltage CSVs, and summary metrics.
It is not a transient, mismatch, substrate-noise, EM, or ESD qualification.
Do not promote a layout based on these DC numbers alone.

## Charge-pump electrical screening

After `all` prints its timestamp, run:

```sh
python3 macros/pll_analog/cic/characterize_charge_pump.py \
  macros/pll_analog/layout/build/cic-cp-next/charge_pump.spice \
  macros/pll_analog/layout/build/charge_pump/TIMESTAMP/pex/charge_pump_pex.spice \
  --capacitance-only macros/pll_analog/layout/build/charge_pump/TIMESTAMP/pex/charge_pump_c_only.spice \
  --output macros/pll_analog/layout/build/cic-cp-electrical-next
```

This runs 45 PVT combinations (five corners, three supplies, three temperatures),
each in UP/DOWN/off/both-on states, with compliance sweeps; summary comparisons
use VCTRL 0.5–0.9 V and IREF 2 µA. Nominal 4-ns pulse screening includes
extracted-device-only and C-only controls. Local rail voltages are screened
with **ideal external supplies**, not a package/substrate model.

### Current measured checkpoint: route-007

Full checks: `layout/build/charge_pump/20261015-101045-324043/`.
Electrical: `layout/build/cic-cp-electrical-007-conserved/`.

| Check | Result |
| --- | --- |
| Magic full DRC / antenna | 0 / 0 markers |
| Full KLayout DRC | **Fail: 7 global-density markers**, no other markers |
| Magic + KLayout LVS | Both pass |
| Resistance + lumped coupled C | 194 R, 30 C; original C matrix preserved |
| Worst DC current change from schematic | UP 2.31%; DOWN 0.053%, tested comparison interval |
| Worst local DC supply deviation, both-on matrix | VDD 0.0564 mV; VSS 0.0739 mV |
| Nominal transient local supply deviation | VDD 2.17 mV; VSS 2.75 mV |
| First 4-ns pulse charge: schematic → layout | UP +15.586 → +17.493 fC; DOWN −14.727 → −17.351 fC |

The pulse change is **not an accepted PLL performance budget**. Closed-loop
PEX, mismatch, substrate noise, integrated fill, and ESD compatibility remain
open; see the completed loaded-PFD screen below. This is a routed experimental
baseline, not a finished analog macro or tapeout approval.

### Important extraction correction

Early `*-electrical-003/004/005` results without `-conserved` are superseded.
Magic 8.3.681's hierarchical exporter applies resistor-π capacitor movement
to MOS subcircuits, and extresist also grounds copies of coupling C while
retaining the original explicit coupling. The checker now uses flat export,
retains raw outputs, and combines full resistance with the independently
exported **original-node lumped** ground/coupling capacitors. It rejects
missing/shorted C endpoints and records the approximation in
`pex/capacitance_model.json`.

This conserves the C-only matrix; it does **not** provide spatially distributed
coupling attachment. C-only and corrected RC nominal pulse charges agree
within 0.03% for route-007. An independent 30-entry audit against the raw
`.ext` matrix agrees within 1 aF export rounding. No claim of foundry-qualified
PEX, substrate extraction, or ESD qualification follows from this correction.

## Loaded-PFD charge-pump qualification

Run from the repository root inside the container; use new output directories:

```sh
python3 macros/pll_analog/cic/qualify_charge_pump.py \
  macros/pll_analog/layout/build/cic-cp-route-007/charge_pump.spice \
  macros/pll_analog/layout/build/charge_pump/20261015-101045-324043/pex/charge_pump_pex.spice \
  --output macros/pll_analog/layout/build/cic-cp-pfd-next

python3 macros/pll_analog/cic/report_charge_pump.py \
  macros/pll_analog/layout/build/cic-cp-pfd-next \
  --output macros/pll_analog/layout/build/cic-cp-pfd-next-report

python3 macros/pll_analog/cic/audit_charge_pump.py \
  macros/pll_analog/layout/build/cic-cp-route-007 \
  macros/pll_analog/layout/build/charge_pump/20261015-101045-324043/pex/charge_pump_pex.spice \
  --output macros/pll_analog/layout/build/cic-cp-pfd-next-report/guard-audit.json
```

`--smoke` selects a three-phase nominal preflight instead of the full sweep.
The full sweep contains **198 cases**: TT/1.2 V/27 °C, SS/1.08 V/125 °C,
FF/1.32 V/−40 °C; VCTRL 0.5/0.7/0.9 V; upstream input edges 20/150 ps;
and feedback-minus-reference phase −2000/−500/−100/−50/−25/0/25/50/100/500/2000 ps.
This is a three-point PVT screen, not all process/supply/temperature combinations.

Each case uses two independent transistor-level copies of the **actual frozen
seven-cell PFD**, including its ten nominal routed RC nets. One drives the
schematic pump and the other the extracted pump. There is no artificial
4-ns UP/DOWN stimulus or shared load between copies. The 100-MHz inputs
produce the PFD's own reset-overlap pulses, edge rates and output skew.
Saved decks, waveforms and input hashes allow replay. Net delivered charge
is integrated over the second event, subtracting measured quiet leakage;
VCTRL is clamped and IREF is an ideal 2-µA source.

The report records charge versus phase, monotonicity, interpolated zero-charge
phase, actual UP/DOWN widths and slews, and a settling diagnostic relative to
100 nA of quiet current. That threshold is **not** a PLL acceptance budget.
Zero-charge phase is an open-loop charge-balance estimate, not simulated
closed-loop PLL phase error. Nominal wire RC is used at every device corner;
upstream drivers and rails are ideal, and excluded neighbors are quiet.

The geometry audit checks saved same-orientation placements, identical NMOS
mirror primitives, continuous per-device contacted guards on all four sides,
a conservative active-to-tie distance bound, and resistive connections of
every extracted MOS bulk to its intended rail. It does not establish
substrate-noise attenuation, random mismatch, EM capability or ESD robustness.

### Measured loaded-PFD checkpoint: route-007

Run: `layout/build/cic-cp-pfd-001/` (198/198 cases completed).
Report/plots: repository-local `.amp/in/artifacts/cic-cp-pfd-qualified/`.
All 18 sampled charge–phase curves are increasing, have one bracketed
zero-charge crossing, and all simulated PFD pulses reset. At VCTRL 0.7 V
with 20-ps upstream edges:

| Corner | Layout UP / DOWN width (ps) | Schematic zero-Q phase (ps) | Layout zero-Q phase (ps) | Shift (ps) |
| --- | ---: | ---: | ---: | ---: |
| TT | 335.3 / 340.3 | −124.3 | +20.6 | +144.9 |
| SS | 534.4 / 541.9 | −66.9 | +145.9 | +212.8 |
| FF | 223.0 / 226.9 | −223.1 | −87.8 | +135.3 |

Across the full screen, the largest absolute interpolated phase-balance
change is **467.9 ps**, at SS/VCTRL 0.9 V. There, schematic and layout
zero-charge phases are +358.9/+826.8 ps. These are interpolations on the
listed phase grid, not precision root solves or closed-loop phase results.
Near zero net charge, an absolute charge/phase comparison is more meaningful
than a percentage ratio with a nearly zero denominator.

At TT/VCTRL 0.7 V and coincident input edges, net delivered charge is
schematic +0.4740 fC, extracted-device-only control +0.1702 fC, and full
layout −0.1081 fC. The diagnostic control is in
`layout/build/cic-cp-pfd-device-control-001/`: it retains physical MOS junction
geometry but removes wire R/C. Both device-geometry and wire-loading effects
contribute to this modeled difference; this is not a random-mismatch test.
Halving the maximum timestep from 2 to 1 ps at zero phase/VCTRL 0.7 V in
all three PVT cases changes charge by at most 0.00157 fC.

All cases return within 100 nA of the quiet current by the measurement end;
the longest post-pulse diagnostic interval is 3.86 ns. Maximum absolute
layout quiet current is 1.35 nA. No settling/leakage budget is implied.
The guard audit finds nine continuous, four-side-contacted rings and all
31 physical MOS bulk connections on their intended rails. Its conservative
active-to-tie distance bound is at most 3.1 µm versus the 20-µm limit.
The largest shortest resistive bulk-to-rail path is 103.44 Ω, **not** an
effective supply resistance, current rating or noise-isolation guarantee.

**Decision:** retain route-007 as a provisional candidate, not a frozen
macro. It passes the sampled functional screens but charge balance remains
VCTRL/PVT-dependent, and seven density failures and the integration gates
below remain open. Neither the 4-ns screening percentages nor these results
are evidence of acceptable closed-loop ripple, spurs or jitter.

### Remaining freeze gates

- Charge imbalance and its dependence on phase/VCTRL need a PLL-level budget;
  a monotonic curve alone does not demonstrate acceptable ripple or spurs.
- Closed-loop extracted lock/acquisition, ripple and reference-spur checks
  require the oscillator, filter, bias and digital boundaries together.
- Realistic shared supply/return and substrate activity require integrated
  models. Ideal-rail local-drop screening is not a coupling qualification.
- The current mirrors are same-orientation, **not common-centroid**. Global
  environments differ; gradient cancellation/statistical matching is unproven.
- Deliberate fill/density closure must be followed by fresh DRC/LVS/PEX and
  electrical screening. Seven density failures remain open, not waived.
- Final top pin/supply access, pad/clamp compatibility, power sequencing and
  full-chip ESD checks remain integration tasks. No internal VCTRL clamp has
  been added: its leakage/capacitance would alter this analog circuit.

## Oscillator leaf checkpoints

`generate.py --cell inverter` and `--cell vco_buffer` now use a directed
two-row recipe in `inverter.py`. Every native guard and every finger access
is retained. Multifinger via staggering avoids the short-channel contact
pitch violation; the buffer's small input gates join directly on M2 rather
than taking an antenna-heavy M3/M4 detour. Source/body landings join a
continuous M2 supply rail with redundant cuts into a 2-µm M3 branch.

| Leaf | Candidate under `layout/build/` | Full report under `layout/build/` | R / lumped C count |
| --- | --- | --- | ---: |
| Current-starved inverter | `cic-inverter-005` | `inverter/20261016-074212-138526` | 94 / 24 |
| Output buffer | `cic-buffer-004` | `vco_buffer/20261016-074212-211101` | 85 / 10 |

Both have Magic DRC=0, Magic antenna=0 and passing Magic/Netgen and
exported-GDS KLayout LVS. Full GDS DRC reports only the seven outstanding
global-density rules, including **no GDS antenna violations**. Earlier buffer
antenna failures were real, despite Magic antenna reporting zero; they were
removed by routing changes, not waived. These are not density-clean macros.
Rendered GDS reviews are in `.amp/in/artifacts/cic-inverter-latest.png` and
`cic-vco_buffer-latest.png`. Added leaf support reproduces all eight
route-007 charge-pump `.mag` cells identically, excluding timestamps.

An early electrical screen assembles these extracted leaves according to a
freshly netlisted ring schematic, with **ideal inter-leaf wiring**, not a
routed ring. Run inside the container:

```sh
python3 macros/pll_analog/cic/characterize_oscillator.py \
  --inverter macros/pll_analog/layout/build/inverter/20261016-074212-138526/pex/inverter_pex.spice \
  --vco-bias macros/pll_analog/layout/build/vco_bias/20261015-101136-565598/pex/vco_bias_pex.spice \
  --vco-buffer macros/pll_analog/layout/build/vco_buffer/20261016-074212-211101/pex/vco_buffer_pex.spice \
  --output macros/pll_analog/layout/build/cic-ring-leaves-pvt-next
```

The 30-case screen covers the same three PVT points, VCTRL 0.5–0.9 V in
0.1-V steps and 5/20-fF ideal output loads. It records actual frequency,
edge count and output swing over 30–60 ns. Insufficient sustained/full-swing
oscillation is a failure, not a fabricated frequency; frequency alone has
no acceptance budget. The explicit startup kick is not noise-only startup
qualification. The nominal 5-fF smoke case is 4.145 GHz schematic versus
1.277 GHz extracted leaves, both full swing. Completed results are in
`layout/build/cic-ring-leaves-pvt-001/`: extracted frequencies span
314.431 MHz–2.355834 GHz. All 30 extracted cases oscillate; three fail the
full-swing screen at 20 fF: TT/VCTRL=0.9 V and SS/VCTRL=0.8/0.9 V.
This is not assembled-ring PEX, real digital receiver loading, phase noise
or closed-loop validation. Replace the exploratory capacitive load with the
frozen digital input receiver and check its edge requirements before resizing
the buffer based only on this screen.

## Frozen digital receiver screen

`characterize_oscillator.py --receiver` now does that boundary check. It
extracts the frozen `inv_4 → inv_16 → dfrbp_2` input/divide-by-two path,
its five nominal SPEF signal nets, and the two real `buf_16` loads on Q.
Every selected signal pin is checked against both Verilog and SPEF before
simulation; SPICE terminal order comes from the installed standard-cell
library, not an assumed order. Each oscillator gets an independent receiver.

Run in the container (add `--smoke` for nominal VCTRL=0.7 V only):

```sh
python3 macros/pll_analog/cic/characterize_oscillator.py --receiver \
  --inverter macros/pll_analog/layout/build/inverter/20261016-080336-828171/pex/inverter_pex.spice \
  --vco-bias macros/pll_analog/layout/build/vco_bias/20261016-080441-709723/pex/vco_bias_pex.spice \
  --vco-buffer macros/pll_analog/layout/build/vco_buffer/20261016-080416-984420/pex/vco_buffer_pex.spice \
  --output macros/pll_analog/layout/build/cic-ring-receiver-pvt-next
```

The completed 15-case sweep is `layout/build/cic-ring-receiver-pvt-001/`.
It uses **GDS-reimported leaf extractions**, but still ideal inter-leaf wiring.
All 15 extracted cases have full-swing oscillator/receiver outputs and two
receiver-clock rising edges per complete divided-output cycle. However,
functional division alone is not timing qualification:

| PVT | Extracted frequency range (MHz) | Worst 20–80% rise / fall (ps) | Frozen-interface screen |
| --- | ---: | ---: | --- |
| TT, 1.2 V, 27 °C | 357.510–1542.542 | 133.93 / 145.10 | All five pass |
| SS, 1.08 V, 125 °C | 314.441–983.611 | 187.21 / 188.20 | All five exceed the 150-ps input-slew assumption |
| FF, 1.32 V, −40 °C | 489.846–2354.946 | 97.24 / 106.04 | VCTRL=0.8/0.9 V exceed the 2-GHz clock envelope |

Limits are read from the frozen SDC; the timing library's ns units and
20/80% slew thresholds are checked. Results include raw swing/edge counts,
rise/fall durations, divide ratio and individual receiver checks. The command
correctly exits nonzero on this sweep; the ideal schematic reference also
fails several cases and is not silently ignored. The older capacitive smoke
mode reproduces `cic-ring-gds-smoke-001` exactly after this addition.
Tying divider D to VSS in a scratch receiver leaves oscillator/clock edges
present but eliminates divided-output edges (19 → 0); the negative control
is recorded in `.amp/in/artifacts/receiver-negative-control.json`.

The prior heavy-capacitive-load swing failures are not reproduced with this
receiver, but the slow-corner slew and fast-corner frequency failures remain
open. Do not relax the digital constraints to turn these results green.
Next physical ring routing must be extracted and retested against this same
boundary; evaluate shorter buffer routing/drive options if slew still fails.
No schematic sizing or frozen digital layout has been changed by this test.

Limitations: nominal RC at every transistor PVT; quiet excluded coupling
neighbors; ideal rails, ideal reset at the FF pin, no analog-to-digital top
wire, and unloaded outputs of the two Q-load buffers. This checks only the
first receiver/divider, not the remaining digital logic, full PLL acquisition,
substrate/supply coupling, noise-only startup or submission readiness.

## Physically assembled ring checkpoint

`ring.py` adds directed hierarchy assembly using the existing guarded leaves,
without resizing or changing their geometry. The three stages are placed in
a row, bias below left and buffer below right. Stage-to-stage/core routes use
separate M3 channels/M4 risers. Dedicated 2-µm supply trunks have redundant
via stacks; control is below the stages, away from the upper clock channels.
This is an intentionally spacious first floorplan, not an optimized/noise-
qualified ring. Its feedback route is longer and more heavily loaded than
the two forward routes. Guards remain individually contacted native rings,
not a verified substrate-isolation barrier or full ESD network.

Generate in the container, using the CIC Python:

```sh
/opt/ciccreator/.venv/bin/python macros/pll_analog/cic/generate.py \
  --cell ring_oscillator \
  --leaf-library inverter=macros/pll_analog/layout/build/cic-inverter-005 \
  --leaf-library vco_bias=macros/pll_analog/layout/build/vco_bias/20261015-101136-565598/mag \
  --leaf-library vco_buffer=macros/pll_analog/layout/build/cic-buffer-004 \
  --output macros/pll_analog/layout/build/cic-ring-next
python3 macros/pll_analog/layout/run_checks.py all ring_oscillator \
  --library macros/pll_analog/layout/build/cic-ring-next
```

Candidate `cic-ring-003` passes Magic full DRC/antenna, Magic/Netgen LVS,
KLayout GDS LVS, and native plus GDS-reimported extraction/port checks.
Its **full check still fails seven global-density rules**, with no other
KLayout markers, including no antenna/latch-up/geometry violations reported.
Parent report: `layout/build/ring_oscillator/20261016-090850-193985`;
GDS-reimport report: `ring_oscillator/20261016-090900-342675` under the same
build directory. Native extraction has 413 R / 58 lumped C elements;
GDS reimport has 1232 R / 58 C. The documented PEX approximation still applies.

The first candidate's bias supply escapes shorted VDD/VSS; staggered escapes
below the leaf corrected that. The second candidate's cumulative bias-gate
antenna ratio was 209.08 against a 200 limit. An immediate M4 jump plus a
shorter, below-stage control trunk corrected it; no diode/waiver was added.
For more top-routing antenna headroom, investigate shortening the bias leaf's
own M2 VCTRL escape: its M2 contribution alone was 149.23. Recheck antenna
after filter/top connection; a clean standalone ring is not a top-level waiver.

`cic-ring-reproduce-003` reproduces all 14 Magic files excluding timestamps,
and preserves every leaf file byte-for-byte. It also contains
`ring_oscillator.cic`: a CIC assembly requiring the adjacent raw Magic leaf
library, not a standalone process-device database. Reopening/reprinting that
CIC assembly passes the same checks except density; KLayout XOR is empty on
all 12 physical drawing layers. Its report is
`ring_oscillator/20261016-091626-946165`. Rendered GDS was inspected at
`.amp/in/artifacts/cic-ring-003.png`; PR-boundary hatching is hidden, not fill.

Simulate the assembled GDS extraction against the frozen receiver:

```sh
python3 macros/pll_analog/cic/characterize_oscillator.py --receiver \
  --ring macros/pll_analog/layout/build/ring_oscillator/20261016-090900-342675/pex/ring_oscillator_pex.spice \
  --output macros/pll_analog/layout/build/cic-ring-layout-pvt-next
```

Unlike leaf mode, this includes physical inter-leaf wiring and internal PDN
RC; external supplies, reset and the analog/digital boundary wire remain
ideal. Ring mode measures 50–100 ns to retain enough low-frequency divided
cycles. The explicit startup kick uses the LVS-reviewed VCO_CORE alias
`x_buffer.VIN`; native extraction names that same net `x1.VIN`, selected with
`--startup-node x1.VIN`. These are not noise-only startup tests.

Nominal TT/VCTRL=0.7 V gives **957.697 MHz**, full swing and correct divide by
two, with worst 20–80% rise/fall 120.30/104.06 ps. Native extraction gives
957.574 MHz (+0.01288% GDS/native difference). The completed 15-case GDS
sweep is in `cic-ring-layout-pvt-001`: every extracted case has full swing,
correct divide-by-two and frequency below the frozen 2-GHz ceiling, but
only **9/15 meet all receiver interface screens**. SS/1.08 V/125 °C fails
the 150-ps input-slew limit at every tested control voltage; worst rise/fall
is 202.36/211.21 ps. TT/0.5 V also fails slew (167.26-ps fall). Frequency
ranges over VCTRL=0.5–0.9 V are TT 259.711–1163.629 MHz,
SS 230.450–740.200 MHz, FF 354.034–1782.232 MHz. Therefore this tested
control range does not demonstrate 1-GHz operation at SS. The harness also
flags failures in the schematic-reference receiver cases; its overall exit
code is not an extracted-only result. Do not freeze this ring based on nominal
results. The older capacitive smoke results and all eight charge-pump Magic
files reproduce unchanged.

The next routing-only hypothesis is `cic-inverter-006`: join the two switch
gates locally, replacing the two upper-bank VIN detours. A short M4 hop
crosses over the broad VDD M2 branch without a via at that crossing; copying
the buffer's straight M2 join would short VIN to VDD. Native device geometry,
guard rings and sizes remain unchanged. The leaf passes native/GDS Magic DRC,
antenna and extraction checks plus Magic/KLayout LVS; full KLayout DRC
still fails the same seven global-density rules. Its parent report is
`inverter/20261016-093031-973452`, GDS child `20261016-093041-262186`.

`cic-ring-004` uses that leaf with the same bias/buffer libraries and directed
ring recipe. It passes the same physical/connectivity gates, still fails
seven density rules, and its nominal extracted-receiver case gives
**1149.308 MHz (+20.01%)**, full swing, correct divide-by-two and
120.10/103.79-ps rise/fall (`cic-ring-layout-smoke-004`). Thus shortening
inverter VIN improves frequency but barely changes output slew. Its full
15-case sweep (`cic-ring-layout-pvt-004`) completes with **8/15** extracted
receiver passes: TT/0.5 V and all five SS points fail slew, while FF/0.9 V
reaches 2135.505 MHz and fails the frozen 2-GHz ceiling. Parent report:
`ring_oscillator/20261016-093051-007296`; GDS child `20261016-093101-453002`.
These are experiments, not promoted integration views. The inspected GDS
render is `.amp/in/artifacts/cic-ring-004.png`; the spacious floorplan and
long feedback route remain optimization opportunities.

`cic-buffer-005` separately tests a shorter loaded-output route: immediate
M4 joins at the two drain accesses replace the upper-bank VOUT detours.
This targets the persistent slew failure without device resizing. It passes
native/GDS Magic DRC, antenna, both LVS engines and extraction/port checks,
with seven density failures remaining. Parent report:
`vco_buffer/20261016-093444-368926`; GDS child `20261016-093454-036985`.
`cic-ring-005` combines it with `cic-inverter-006` and the same bias library;
its physical gates have the same outcome (parent
`ring_oscillator/20261016-093503-010965`, GDS child `20261016-093513-969381`).
Its nominal electrical screen (`cic-ring-layout-smoke-005`) gives
**1149.916 MHz**, full swing, correct divide-by-two and **107.75/92.74-ps**
rise/fall, versus 120.10/103.79 ps for ring004. All nominal extracted receiver
screens pass; the harness still exits nonzero because its schematic reference
fails at this operating point. The completed sweep `cic-ring-layout-pvt-005`
has **9/15** extracted receiver passes. All five TT points now pass, all five
SS points still fail slew (worst rise/fall 177.75/181.96 ps), and FF/0.9 V
reaches 2136.707 MHz, above the frozen 2-GHz ceiling. Every extracted case
has full swing and correct divide-by-two, but this is not interface closure.
SS frequency spans 282.699–892.105 MHz over VCTRL=0.5–0.9 V, still short of
1 GHz in this tested range. Shorter wiring improves frequency and slew but
does not solve the slow/fast-corner range conflict. All four native device
files in each modified leaf match their predecessors excluding timestamps.
Neither schematic nor frozen digital macro was changed. The inspected render
is `.amp/in/artifacts/cic-ring-005.png`.

## Native passive loop-filter checkpoint

```sh
/opt/ciccreator/.venv/bin/python macros/pll_analog/cic/generate.py \
  --cell loop_filter --output macros/pll_analog/layout/build/cic-filter-next
python3 macros/pll_analog/layout/run_checks.py all loop_filter \
  --library macros/pll_analog/layout/build/cic-filter-next
```

`loop_filter.py` provides native `rhigh` and M2–M4 `cap_cmomf` accesses and a
directed quiet-return recipe. SPICE resistor order is R1/R2/B, not the native
Magic B/R1/R2 port-number order. CMOM terminals escape outward on narrow M4
before widening, with no unrelated routes over their finger area. Requested
dimensions and native generation parameters are recorded; native mask/grid
rounding still applies. CIC receives a circuit-only copy with the two known
simulator model directives removed; the raw fresh Xschem export is preserved.

Candidate `cic-filter-004` passes native and GDS-reimported Magic DRC/antenna.
Full KLayout DRC reports only the same seven global-density failures.
Parent: `loop_filter/20261016-094655-648468`; GDS child:
`loop_filter/20261016-094705-452225`. The first routed candidate shorted the
resistor end to its nearby wide guard-return escape; widening that escape
only outside the resistor fixed the short. Native resistor contacts also
needed parent M1 enclosure pads. No resistor poly geometry was changed.
`cic-filter-reproduce-004` reproduces all four Magic files excluding timestamps;
the shared adapter change also reproduces all eight charge-pump Magic files
in `cic-cp-passive-regression-007`.

**Verification is not closed:** native Magic LVS and unannotated-stream
KLayout LVS omit both CMOM devices. The installed KLayout deck requires
Recog.momf 99/40 and M4 pin-purpose 50/2 shapes, absent from this Magic
stream. A separate marker-only experiment in `cic-filter-marker-probe-001`
restores all three devices and passes CMOS5L KLayout LVS. Physical-drawing
XOR is empty; deleting one capacitor's recognition marker makes LVS fail
again. Use its `lvs-cmos5l` report: the first `lvs` invocation accidentally
used the container's default SG13G2 selection and is not CMOS5L evidence.
The original probe was separate from the failing reports. The deck matches
CMOM topology but does not compute
capacitance; it does not establish electrical C accuracy or strict dimensions.

The normal checker now adds these recognition purposes during GDS export,
using native saved PCell metadata, not schematic nets. It retains
`loop_filter.raw-magic.gds` and `cmom_annotations.json`; the audit reloads the
serialized output and requires empty physical-layer XOR. Pins outside M4 or
the device body are rejected, as are unreviewed non-M4 top-metal stacks.
Report `loop_filter/20261016-100937-232671` passes **KLayout LVS** with the
same saved input hashes as the earlier failing unannotated run. Full KLayout
DRC still reports seven density rules; Magic DRC and antenna still pass.
Native Magic LVS/PEX still fail. Its annotated-GDS round trip also correctly
fails: the installed Magic technology cannot import the 99/40 recognition
layer. Do not suppress this import error or silently remove the marker.
Installed PDK files are unchanged.

Negative controls: a VCTRL short in the annotated stream fails CMOS5L
KLayout LVS (`cic-filter-export-controls/lvs-shorted`); an off-metal native
pin label fails annotation (`loop_filter/20261016-100736-970651`). Neither
reference nor original candidate was edited for these controls. The
oscillator-only checker regression retains both LVS, native/GDS Magic DRC,
antenna and extraction passes, with only density failing (parent
`ring_oscillator/20261016-100607-371113`, child `20261016-100617-506582`).

PEX also correctly rejects the filter: the C-only netlist includes coupling
to the internal `xres` node `a_26204_12290#`, which the `rhigh` subcircuit
export does not expose in the resistance network. Do not discard that C or
reattach it arbitrarily to force a pass. Resolving native CMOM recognition,
stream-marker preservation and resistor internal-node extraction are the
next filter verification tasks. The inspected experimental floorplan is
`.amp/in/artifacts/cic-filter-004.png`; it is not an approved integration view.

## Exported-GDS extraction checkpoint

The layout checker now includes `gds-roundtrip` in `all`; it can also be run
separately with `make gds-roundtrip CELL` in `layout/`. It imports the exported
stream into an empty Magic library, saves that hierarchy, then reruns full
Magic DRC, antenna, fresh-schematic LVS and lumped-RC extraction. Original
stream KLayout DRC/LVS remain separate required checks. Child reports record
the source GDS hash and imported layout hashes.

| Leaf | Passing reimport report under `layout/build/` |
| --- | --- |
| Charge pump | `charge_pump/20261016-080417-350279` |
| Current-starved inverter | `inverter/20261016-080336-828171` |
| Output buffer | `vco_buffer/20261016-080416-984420` |
| Bias | `vco_bias/20261016-080441-709723` |

Nominal electrical cross-checks compare these GDS-derived extractions with
native-Magic extractions. In `cic-ring-gds-smoke-001`, oscillator frequency
changes by +0.00462% at TT/VCTRL=0.7 V/5 fF. In
`cic-cp-gds-smoke-001`, the maximum charge difference over loaded-PFD phase
offsets −500/0/+500 ps is 0.000433 fC. These are nominal serialization checks,
not a repeated PVT qualification. Removing M4 bridges from the GDS only,
while leaving source Magic intact, correctly fails reimport DRC/LVS;
the negative-control record is
`.amp/in/artifacts/gds-roundtrip-negative-control.json`.

Retiling changes resistor mesh counts; element counts alone do not establish
an effective resistance change. This still uses Magic and the documented
original-node lumped-C approximation, not independent/foundry-qualified PEX.
The charge-pump and buffer full checks still fail on seven global-density
markers each. Nothing in this checkpoint waives those failures.

Next dependencies are ring loading/slew closure and floorplan refinement,
filter CMOM recognition and resistor-extraction closure, then
isolated CP/filter/bias versus oscillator placement and full top routing.
Repeat native/GDS checks and electrical comparisons after hierarchy assembly
and deliberate fill, before final electrical and integration approval.
No leaf checkpoint above constitutes submission approval.

## Full analog assembly checkpoint (2026-10-16)

`analog.py` now assembles the actual `pll_analog` hierarchy with unchanged
CP/filter/ring leaves. The quiet blocks sit left of the oscillator; VCTRL
runs through the gap. Separate 2-µm supply/return branches meet at 4-µm
external entry straps. This is a deliberately spacious routing experiment,
not an optimized floorplan or verified substrate/EM/ESD solution. Existing
device guards are retained. No new pad protection has been invented.

Inside a login shell in IIC-OSIC-TOOLS, from the repository root:

```sh
/opt/ciccreator/.venv/bin/python macros/pll_analog/cic/generate.py \
  --cell pll_analog \
  --leaf-library charge_pump=macros/pll_analog/layout/build/cic-cp-route-007 \
  --leaf-library loop_filter=macros/pll_analog/layout/build/cic-filter-004 \
  --leaf-library ring_oscillator=macros/pll_analog/layout/build/cic-ring-005 \
  --output macros/pll_analog/layout/build/cic-analog-006
python3 macros/pll_analog/layout/run_checks.py all pll_analog \
  --library macros/pll_analog/layout/build/cic-analog-006
```

Use a new empty output path to repeat generation. The output includes
`pll_analog.cic`, all referenced MAG cells, fresh Xschem SPICE, and source
hashes. Matching leaf filenames may differ only in the save timestamp;
actual geometry/label/property conflicts still fail (negative control tested).

Final report: `layout/build/pll_analog/20261016-103931-695070`.

| Check | Result |
| --- | --- |
| Complete saved hierarchy / native Magic DRC | PASS / zero areas |
| Native Magic antenna | PASS / zero markers |
| Exported GDS KLayout LVS against fresh schematic | PASS |
| Full KLayout DRC including antenna | FAIL: seven global-density markers only |
| Native Magic LVS | FAIL: unresolved CMOM extraction support |
| Lumped-RC extraction validation | FAIL: internal resistor C endpoints absent from R network |
| Annotated GDS reimport into Magic | FAIL: unsupported CMOM recognition layer |

Candidates 003–005 retain the failed routing evidence. Parent vias initially
partially overlapped the CP's existing cuts; reusing the child's rail access
removed all native DRC violations. A long UP escape then failed independent
KLayout cumulative antenna checks despite Magic antenna passing. An immediate
M4 jump and short escape just outside the CP removed those six antenna
markers without diodes or schematic changes. Integration routing must recheck
this gate's antenna budget; extending the signal is not automatically safe.

Inspected preview: `.amp/in/artifacts/cic-analog-006.png`. Long supply routes
and substantial unused area still need refinement and extracted electrical
evaluation. This checkpoint is connectivity closure, **not signoff closure**.
Filter extraction/stream compatibility, deliberate density fill, ring PVT
slew/frequency limits, full-loop extracted simulation, isolation/PDN and
pad/ESD compatibility remain open. Manual layout and frozen digital are untouched.

## Resistor extraction and fill screening (2026-10-16)

The missing filter endpoint is the resistor identification/body node, not
an omitted external wire. `pex/capacitance_endpoint_audit.json` now identifies
the node, affected C elements and input netlist hashes before rejecting it.
Filter report `loop_filter/20261016-110809-628636` identifies
`a_26204_12290#`, coupled to VCTRL by 0.08646 fF and XR1.R2 by 0.22285 fF.
Those capacitors are neither discarded nor moved to arbitrary terminals.

Two documented Magic tee exports were screened and **not adopted**:

* Flat `ext2spice resistor tee on` emits only X0A, losing the second half of
  the resistor. This reproduces in `loop_filter/20261016-110334-615982`.
  Magic tag 8.3.681, `ext2spice/ext2spice.c:3051`, breaks before the intended
  X0B emission at lines 3053–3098.
* Hierarchical tee export does emit X0A/X0B and passes the structural endpoint
  check (`loop_filter/20261016-110617-409612`), but that is not sufficient:
  the native `rhigh` model includes end/contact and intrinsic capacitance
  terms. Two half-length model calls are not equivalent to one full-length
  model. At nominal/25 °C/1 V, ngspice gives 31,585.02 Ω versus 31,745.75 Ω
  (+0.5089012%); input admittance differs by 6.479999% at 1 GHz.
  The retained deck/log are `.amp/in/artifacts/rhigh-tee-model-comparison.*`.
  The hierarchical emitter also suppresses explicit resistor body-to-substrate
  C when a substrate pin is present, and has the previously documented MOS
  capacitance problem. It is not a PEX repair.

Normal PEX now explicitly keeps tee **off** and the full-length foundry
device. Ring-only PEX remains a passing control (413 wire resistors and 58
lumped capacitors, report `ring_oscillator/20261016-110831-073050`). Resolving
the resistor requires a validated model/extractor interface for its internal
couplings, or an explicitly qualified approximation; merely fixing the missing
X0B is insufficient. No installed model or tool was changed.

Fill screening also uncovered PDK/tool compatibility issues rather than a
usable fill candidate. The installed CMOS5L `generate_fill.py` launcher
hardcodes the SG13G2 GDS technology path. A direct run using the correct CMOS5L
technology and `patternfill()` avoids that launcher, but the style itself
references undefined `dnwell` and reports 3,312 output problems. The screening
recipe retains 10-µm fill-block margins around CP, filter and ring; see
`pll_analog/20261016-111003-754624/fill-screen/run.tcl`. Its generated stream is
**invalid and must not be merged**. An earlier `patternfill` request was
ambiguous and remained in gdsii style; it is also rejected, not a fill result.
The checker now fails on undefined-layer, ambiguous-style and nonzero CIF
output-problem diagnostics even when Magic exits zero and reaches its final
completion marker. Negative control: `pll_analog/20261016-111055-255185`.

Finally, the installed `cap_cmomf.lib` explicitly describes an unvalidated-on-
silicon, low-frequency, simulation-derived model with no substrate coupling,
series R/L, process corners or mismatch characterization. Geometry LVS is not
a qualification of these missing electrical models. PDK/extraction support
and the MPW's acceptance criteria remain essential signoff dependencies.

## Project-local metal-fill experiment (2026-10-16)

`metal_fill.py` avoids the broken Magic pattern-fill style. By default it creates a new
native-Magic candidate from a checker snapshot, preserving all leaves and
adding one floating-fill child to the analog top. The generated fill uses
CMOS5L native m1fill–m5fill types (GDS 8/22, 10/22, 30/22, 50/22, 126/22).
It is an experimental sidecar to the CIC assembly, not yet part of an approved
final `.cic` deliverable. Optional `--feol` adds the separately screened
active/poly recipe described below. No shared PDK or manual source is edited.

```sh
python3 macros/pll_analog/cic/metal_fill.py \
  --report macros/pll_analog/layout/build/pll_analog/20261016-111055-565534 \
  --output macros/pll_analog/layout/build/cic-analog-metal-fill-005
python3 macros/pll_analog/layout/run_checks.py all pll_analog \
  --library macros/pll_analog/layout/build/cic-analog-metal-fill-005
```

Run in the container's login shell and use a new output name when repeating.
The recipe verifies saved-MAG hashes and the checker's annotated GDS hash;
changed inputs are rejected. It leaves 10 µm around each of the CP, filter,
and oscillator bounding boxes, plus 2 µm around all functional metal routing.
These distances are conservative experimental choices, not verified substrate
isolation distances. Metal1–4 use 4×4-µm islands at 0.6-µm spacing; top metal
uses 10×10 then 5×5-µm islands at 3.2-µm spacing. All islands are floating.

Candidate 004 passes native Magic DRC/antenna and independent GDS KLayout LVS
in `pll_analog/20261016-113701-708357`. Candidate 005 adds provenance checks
and generates **byte-identical MAG files**, so it has the same checked geometry.
The full KLayout run now reports only **three density markers**, down from
seven on unfilled analog: active, polysilicon, and top metal.

| Metal | Global density (%) | Minimum (%) | Result |
| --- | ---: | ---: | --- |
| M1 | 35.596 | 35 | PASS |
| M2 | 40.767 | 35 | PASS |
| M3 | 43.794 | 35 | PASS |
| M4 | 43.022 | 35 | PASS |
| TopMetal1 | 23.371 | 25 | FAIL |

An independent stream audit finds empty XOR on every original non-fill layer,
including recognition metadata, and no fill intersections with either keepout.
All 24 original non-top MAG files remain byte-identical. Negative controls
reject changed source MAG and GDS; `.amp/in/artifacts/metal-fill-audit.json`
records the results. Inspected preview:
`.amp/in/artifacts/cic-analog-metal-fill-004.png`.

Candidates 001–003 retain iteration evidence. Candidate 003 cleared top-metal
density but used 20-µm-wide islands, violating the 10-µm maximum filler width
in both DRC engines; it is rejected. The current recipe respects that maximum
rather than waiving it or narrowing the analog keepouts.

Active/poly fill is intentionally not generated by this metal-only recipe.
PEX/native LVS/annotated-GDS import still fail for the previously documented
filter reasons. No post-fill electrical qualification is claimed; fill can
change capacitance even outside these keepouts. Fill must be re-extracted and
simulated after extractor closure, and revisited in the final chip context.
Neither filled candidate is promoted, frozen, or submission-ready.

## Compact output buffer and parent integration (2026-10-16)

`cic-buffer-008` reduces the buffer row pitch from 18 to 11 µm and its
interstage channel offset from 9 to 6 µm. The VIN port remains above the
VDD strap with clearance for a parent's via landing. Native device dimensions,
guards and schematic connectivity are unchanged. The buffer bounding box
shrinks from 18.42×31.2 to 18.42×21.2 µm (574.704 to 390.504 µm², −32.05%).
Regenerating the untouched inverter recipe as `cic-inverter-regression-007`
reproduces inverter006, including every native device, excluding save timestamps.

Two rejected experiments are retained: buffer006's 10-µm pitch shorted net1
to VDD (both LVS engines caught it), and ring006's parent via landing violated
M2 spacing to the buffer VDD strap. Buffer007 passed alone but exposed that
parent-interface failure; buffer008 and ring007 resolve it together. Leaf DRC
alone would not have caught either parent-only spacing failure.

| Candidate | Native checker report | GDS reimport child | Outcome |
| --- | --- | --- | --- |
| buffer008 | `vco_buffer/20261016-123626-111217` | `20261016-123634-929872` | DRC, antenna, both LVS engines, R+C extraction PASS; density FAIL |
| ring007 | `ring_oscillator/20261016-123435-862854` | `20261016-123445-448854` | Same passing gates; seven density failures |
| analog007 | `pll_analog/20261016-123546-893012` | Reimport blocked by CMOM | Native DRC/antenna and independent GDS LVS PASS; density and passive gates remain open |

The buffer extraction contains 85 R/10 C natively and 239 R/10 C after
GDS reimport; the assembled ring has 413 R/58 C and 1,270 R/58 C respectively.
Different resistor segmentation is not by itself an electrical equivalence
check. Ring007 uses inverter006, buffer008 and the previously checked bias
library `vco_bias/20261015-101136-565598/mag`. Analog007 combines it with
CP route007 and filter004. All paths in the table are below `layout/build/`.

Run the current recipe (including the subsequent interstage revision below)
with new empty output names inside the container:

```sh
/opt/ciccreator/.venv/bin/python macros/pll_analog/cic/generate.py \
  --cell vco_buffer --output macros/pll_analog/layout/build/cic-buffer-next
/opt/ciccreator/.venv/bin/python macros/pll_analog/cic/generate.py \
  --cell ring_oscillator \
  --leaf-library inverter=macros/pll_analog/layout/build/cic-inverter-006 \
  --leaf-library vco_bias=macros/pll_analog/layout/build/vco_bias/20261015-101136-565598/mag \
  --leaf-library vco_buffer=macros/pll_analog/layout/build/cic-buffer-next \
  --output macros/pll_analog/layout/build/cic-ring-next
python3 macros/pll_analog/layout/run_checks.py all ring_oscillator \
  --library macros/pll_analog/layout/build/cic-ring-next
```

Electrical comparison against the actual frozen input/div2 uses the checker
snapshot, not an ideal load. For ring007, the native extraction's canonical
startup node is `x1.VIN`; the GDS extraction's is `x_buffer.VIN`. Retained
`.ext` equivalences identify both as VCO_CORE. Explicitly name the correct
alias rather than applying a kick to a nonexistent node:

```sh
python3 macros/pll_analog/cic/characterize_oscillator.py \
  --ring macros/pll_analog/layout/build/ring_oscillator/20261016-123435-862854/pex/ring_oscillator_pex.spice \
  --startup-node x1.VIN --receiver \
  --output macros/pll_analog/layout/build/cic-ring-layout-pvt-next
```

The nominal GDS-derived extracted receiver case (`cic-ring-layout-gds-smoke-007`,
TT/1.2 V/27 °C/VCTRL=0.7 V) passes all receiver screens: 1,157.726 MHz,
102.77/87.57-ps rise/fall and divide ratio 1.99999955. Its native counterpart
is 1,157.354 MHz and 102.78/87.58 ps, a +0.0322% frequency difference.
The harness still exits nonzero because its separate schematic reference
fails receiver screens. Neither result establishes complete PVT closure,
noise-only startup, full PLL lock, substrate isolation, EM or ESD protection.
Inspected renders: `.amp/in/artifacts/cic-buffer-008.png` and
`.amp/in/artifacts/cic-ring-007.png`. These candidates remain experimental,
unpromoted and separate from manual layout and the frozen digital macro.

The completed 15-case native sweep `cic-ring-layout-pvt-007b` gives **8/15**
extracted receiver passes, versus 9/15 for ring005. Although worst SS rise/fall
improves from 177.75/181.96 to 170.02/174.37 ps, all five SS points still fail
the frozen 150-ps input-slew limit. FF now fails the 2-GHz ceiling at both
VCTRL=0.8 and 0.9 V, reaching 2,150.395 MHz at 0.9 V. SS frequency spans
284.275–898.277 MHz, still below 1 GHz throughout this tested control range.
All extracted cases have full swing and correct divide-by-two. Thus smaller
area and faster nominal edges do **not** establish a better qualified design;
ring007 is not promoted over ring005.

### Local interstage routing experiment

The current `inverter.py` buffer branch also replaces the net1 upper-bank
detour with local M4 joins between first-stage drains and second-stage gates.
A left-hand trunk joins the rows, separated from VOUT on the right. Removing
the M2 escapes exposed minimum-area islands at the second-stage gates in
buffer009 (six areas in both native and reimport DRC). Buffer010 adds
0.32×0.48-µm M2 landing pads; it passes those rules without resizing devices,
changing guard geometry or narrowing the supply straps. Its bounding box is
16.81×20.77 µm. Native transistor MAG files match buffer008 excluding timestamps.

| Candidate | Native checker report | GDS reimport child |
| --- | --- | --- |
| buffer010 | `vco_buffer/20261016-124445-124638` | `20261016-124454-345776` |
| ring008 | `ring_oscillator/20261016-124511-041837` | `20261016-124521-496671` |

Both pass native/GDS Magic DRC, antenna, both LVS engines and validated
lumped-RC extraction, with the same seven global-density failures. Buffer010
extracts 77 R/10 C natively and 253 R/10 C after reimport; ring008 has
413 R/58 C and 1,250 R/58 C respectively. Independent GDS marker inspection
confirms only AFil.g, GFil.g, M1.j–M4.j and TM1.c density failures, not newly
hidden local violations. Inspected renders:
`.amp/in/artifacts/cic-buffer-010.png`, `.amp/in/artifacts/cic-ring-008.png`.

Analog008 assembles ring008 with the same CP/filter leaves. Report
`pll_analog/20261016-125013-033466` again passes native DRC/antenna and
independent GDS LVS; density, native CMOM LVS, annotated-GDS reimport and the
resistor-body capacitance endpoint still fail. No top-level PEX or electrical
qualification is claimed.

The completed native sweep `cic-ring-layout-pvt-008` passes **12/15**
extracted receiver cases (TT 5/5, SS 4/5, FF 3/5). Every extracted case has
full swing and correct divide-by-two. The remaining failures are:

| Corner / supply / temperature | VCTRL (V) | Frequency (MHz) | Rise/fall 20–80% / 80–20% (ps) | Failed interface limit |
| --- | ---: | ---: | ---: | --- |
| SS / 1.08 V / 125 °C | 0.5 | 283.718 | 163.79 / 166.42 | 150-ps maximum input slew |
| FF / 1.32 V / −40 °C | 0.8 | 2005.065 | 68.64 / 58.79 | 2,000-MHz maximum frequency |
| FF / 1.32 V / −40 °C | 0.9 | 2146.204 | 68.31 / 58.75 | 2,000-MHz maximum frequency |

SS/0.6 V now passes with 149.01-ps rise time: this is little margin, not robust
closure. SS frequency reaches only 896.606 MHz at VCTRL=0.9 V. The TT/0.7-V
case gives 1,154.751 MHz and 98.89/81.79-ps rise/fall. The completed GDS-derived
sweep `cic-ring-layout-gds-pvt-008` uses the GDS reimport report above and
`--startup-node x_buffer.VIN`. It reproduces the same **12/15** pass/fail
decisions; maximum frequency difference across the 15 paired cases is
0.032979%. GDS SS/0.5 V gives 163.76/166.39-ps edges; GDS FF/0.8 and 0.9 V
reach 2,005.683 and 2,146.848 MHz. This confirms the remaining failures are
not repaired by GDS reimport. Neither sweep qualifies noise or final filled
top-level behavior. No schematic/device sizing change is included in this
routing-only comparison; neither frozen interface limit is relaxed.

## Metal-density closure on analog008

The revised metal-only recipe uses 10×10, 10×5, 5×10 and 5×5-µm top-metal
islands with 3.05-µm spacing, versus the deck's 3.0-µm minimum. The 10-µm
whole-block and 2-µm functional-routing keepouts are unchanged. Candidate
`cic-analog-metal-fill-006` is generated from analog008's immutable checker
snapshot, not the older analog006 geometry:

```sh
python3 macros/pll_analog/cic/metal_fill.py \
  --report macros/pll_analog/layout/build/pll_analog/20261016-125013-033466 \
  --output macros/pll_analog/layout/build/cic-analog-metal-fill-next
python3 macros/pll_analog/layout/run_checks.py all pll_analog \
  --library macros/pll_analog/layout/build/cic-analog-metal-fill-next
```

Full report `pll_analog/20261016-130342-117757` passes native Magic DRC,
antenna and independent GDS LVS. Full KLayout DRC now has **two markers only**:
AFil.g and GFil.g. All five metal-density checks pass:

| Metal | Global density (%) | Minimum (%) |
| --- | ---: | ---: |
| M1 | 35.624 | 35 |
| M2 | 40.788 | 35 |
| M3 | 43.813 | 35 |
| M4 | 43.065 | 35 |
| TopMetal1 | 25.244 | 25 |

The independent stream audit covers the **union** of input/output layers,
including newly introduced layers. Installed Magic CIF output explicitly
emits m5fill on both 126/0 and 126/22. The only allowed change on 126/0 is
that exact duplicate fill geometry; every other non-fill layer has empty XOR.
No fill intersects either keepout and all 24 original leaf MAG files remain
byte-identical. Repeated generation as candidate007 reproduces all 26 MAG
files byte-for-byte. Audit: `.amp/in/artifacts/metal-fill-006-audit.json`;
inspected image: `.amp/in/artifacts/cic-analog-metal-fill-006.png`.

Native CMOM LVS, annotated-GDS import and resistor-body PEX endpoints remain
unresolved, so this is not a post-fill electrical result or signoff approval.
Top-metal density has only 0.244 percentage points of margin and must be
rechecked after any floorplan/routing/top-integration change.

Active/poly fill requires a separate FEOL pattern, not copying the metal
algorithm. The installed rules require 35% global active and 15% global poly
density, active filler width 1–5 µm/spacing ≥0.42 µm, and poly filler width
0.7–5 µm/spacing ≥0.8 µm; overlapping poly must extend active by 0.18 µm.
A dry, fully enclosed active/poly-island packing with 0.2-µm enclosure and
0.85-µm poly spacing reaches only 28.448% active under the retained keepouts,
although poly reaches 33.373%. It is **not** a checked or generated FEOL
candidate and is insufficient for active density. The feasibility measurements
are `.amp/in/artifacts/feol-fill-feasibility-008.json`. Do not simply overlap
unrelated fill grids or shrink isolation margins to manufacture a pass.

## Active/poly fill checkpoint: full installed DRC closure

`metal_fill.py --feol` retains the exact checked metal fill and adds a mixed
active/poly pattern under the same block/routing keepouts. Coarse 4.95-µm
tiles sit on a 5.6-µm grid. Staggered paired tiles have 4.55-µm active islands
fully enclosed by poly with 0.2-µm margin; other tiles are active-only. Every
tenth row is active-only. Boundary remnants use 2.5- and 1.2-µm active-only
islands, maintaining 0.45-µm active spacing and avoiding partial poly overlaps.
These are floating dummy shapes, not ESD devices or new guard structures.

```sh
python3 macros/pll_analog/cic/metal_fill.py --feol \
  --report macros/pll_analog/layout/build/pll_analog/20261016-125013-033466 \
  --output macros/pll_analog/layout/build/cic-analog-feol-fill-next
python3 macros/pll_analog/layout/run_checks.py all pll_analog \
  --library macros/pll_analog/layout/build/cic-analog-feol-fill-next
```

Candidate `cic-analog-feol-fill-001`, checker report
`pll_analog/20261016-133518-256153`, has:

| Check | Result |
| --- | --- |
| Native Magic full DRC / antenna | PASS / zero areas and markers |
| Full installed KLayout decks: main, antenna, density, maximal | PASS / zero markers |
| Independent GDS KLayout LVS | PASS / schematic match |
| Active / poly density | 35.200% / 15.397% (minimum 35% / 15%) |
| Metal densities | Unchanged from metal-fill006; all five pass |
| Native Magic LVS / PEX / annotated-GDS import | FAIL / existing passive-extraction gates |

An independent serialized-GDS audit covers all layers, confirms unchanged
functional masks (allowing only the documented exact duplicate of top-metal
fill on 126/0), verifies every fill layer avoids both keepouts, and checks
0.2-µm poly enclosure of all 695 paired active islands. All 24 original leaf
MAG files remain byte-identical. The fill contains 3,153 active islands and
695 poly islands. Audit: `.amp/in/artifacts/feol-fill-001-audit.json`;
inspected image: `.amp/in/artifacts/cic-analog-feol-fill-001.png`.

Repeated FEOL generation as candidate002 reproduces all 26 MAG files
byte-for-byte. A metal-only control generated with the revised script as
`cic-analog-metal-fill-008` also reproduces all 26 metal-fill006 MAG files,
so adding the FEOL mode does not change the previous control geometry.
The legacy metal-fill child/file name is retained in both modes.

**This is DRC closure against the installed decks, not analog signoff.**
The overall `all` command still returns failure: CMOM native extraction,
annotated-GDS reimport and the resistor-body capacitance endpoint remain
unresolved. No post-fill PLL electrical, substrate-noise, EM or ESD approval
is claimed. Active, poly and top-metal density have limited margin; repeat
the full checks after any geometry or top-integration change. The fill remains
a reproducible native-Magic sidecar, not a promoted final CIC/GDS deliverable.

## Feedback-route screening: shorter is not automatically quieter

Two unpromoted experiments changed only the VCO_CORE M3 routing channel
from +40 µm (ring008) to −18 µm (ring009) and −1 µm (ring010).
Devices, guards, leaf libraries and the frozen receiver were unchanged.
Both alternatives pass local native/GDS DRC, antenna, LVS and lumped-RC
extraction; their unfilled leaf layouts still fail density.

| Candidate | Native checker report below `layout/build/ring_oscillator/` | GDS reimport report |
| --- | --- | --- |
| ring009 | `20261016-140716-874722` | `20261016-140726-604001` |
| ring010 | `20261016-141125-713834` | `20261016-141136-018164` |

Analog009 (`pll_analog/20261016-140900-722409`) and its FEOL-filled
candidate003 (`pll_analog/20261016-140951-857353`) preserve independent
GDS LVS. The filled candidate again has zero installed full-deck DRC
markers; the existing passive-extraction gates still fail.

The completed native receiver sweep `cic-ring-layout-pvt-009` passes
12/15 extracted cases, the same count as ring008. SS/1.08 V/125 °C at
VCTRL=0.5 V fails the 150-ps slew envelope (161.43/165.14 ps).
FF/1.32 V/−40 °C at 0.8/0.9 V fails the frozen 2-GHz limit
(2.042/2.187 GHz). The command correctly exits nonzero. This is not
all-corner closure and does not justify relaxing the frozen interface.

Capacitance alone favored ring010: incident feedback capacitance falls
from 20.310 fF to 19.068 fF, but feedback-to-VCTRL coupling rises from
0.12662 fF to 0.54624 fF (ring009: 0.63599 fF). Audit:
`.amp/in/artifacts/ring-feedback-capacitance-010.json`.

A finite-impedance control-node comparison uses the fresh schematic loop
filter, a 1-GΩ DC feed at 0.7 V, actual frozen receiver and extracted ring
at TT/1.2 V/27 °C. Median peak-to-peak measurements over the last ten
complete output cycles of the 100-ns runs are:

| Route | Frequency (MHz) | VCTRL ripple (µVpp) | VBP ripple (mVpp) |
| --- | ---: | ---: | ---: |
| ring008, original | 1118.136 | 612.638 | 14.016 |
| ring009, −18 µm | 1138.413 | 803.694 | 13.064 |
| ring010, −1 µm | 1157.847 | 741.275 | 13.314 |

Both shorter routes increase control ripple (31.2% and 21.0%) despite
lower bias ripple. Retain the original route as the conservative default;
do not promote either alternative on frequency or capacitance alone.
Replayable `.cir` decks, data and logs are retained in
`layout/build/ring-bias-probe-001/`, including `cycle_ripple.json`.
The weak DC feed allows control settling near 0.687 V. This probe uses
the explicitly unvalidated low-frequency CMOM model, ideal supplies and
an initial kick, with no CP/PFD, closed loop, fill or substrate-noise model.
It is neither a reference-spur metric nor electrical signoff.

After restoring the default, regeneration in `cic-ring-baseline-replay-011`
reproduces all 14 MAG files from ring008's checker snapshot, excluding
save timestamps. A future shorter route needs evidence that shielding or
different crossings reduce control coupling without worsening receiver
slew, antenna, guard continuity or supply-return coupling.

## Optional grounded feedback shielding (unpromoted)

`generate.py --cell ring_oscillator --shield-feedback` selects the lower
−1-µm feedback channel, crossing the x2/x3 M4 control spines on M2 under
grounded M3 islands. A 2-µm-wide grounded M3 strip at y=−3 µm also separates
the parallel clock/control trunks. Two local M4 returns connect these
shields to the existing inverter VSS accesses. It changes no device,
guard, leaf placement or frozen digital geometry. The default remains
the original upper route; the selected mode is recorded in the manifest.

```sh
/opt/ciccreator/.venv/bin/python macros/pll_analog/cic/generate.py \
  --cell ring_oscillator --shield-feedback \
  --leaf-library inverter=macros/pll_analog/layout/build/cic-inverter-006 \
  --leaf-library vco_bias=macros/pll_analog/layout/build/vco_bias/20261015-101136-565598/mag \
  --leaf-library vco_buffer=macros/pll_analog/layout/build/cic-buffer-010 \
  --output macros/pll_analog/layout/build/cic-ring-shield-next
python3 macros/pll_analog/layout/run_checks.py all ring_oscillator \
  --library macros/pll_analog/layout/build/cic-ring-shield-next
```

Crossing-only candidate012 and the full-shield candidate013 both pass
native Magic DRC/antenna/LVS, independent GDS LVS, validated lumped-RC
extraction and GDS-reimport checks. Their unfilled leaf density still fails.
Native report stamps below `layout/build/ring_oscillator/` are
`20261016-143348-588258` and `20261016-143501-487403`; corresponding GDS
reports are `20261016-143358-324361` and `20261016-143511-114063`.

| Route | Feedback total C (fF) | Feedback–VCTRL C (fF) | VCTRL ripple (µVpp) | VBP ripple (mVpp) |
| --- | ---: | ---: | ---: | ---: |
| Original ring008 | 20.310 | 0.12662 | 612.638 | 14.016 |
| Unshielded lower ring010 | 19.068 | 0.54624 | 741.275 | 13.314 |
| Crossing shields only, 012 | 19.621 | 0.36700 | 677.559 | 13.294 |
| Crossings + parallel strip, 013 | 20.868 | 0.04209 | 638.423 | 13.257 |

The same finite-control nominal screen described above reproduces the
baseline ripple exactly. Full shielding reduces the direct coupling by
92.3% versus ring010, but total control ripple remains 4.2% above the
original route; bias ripple improves by 5.4%. This is useful evidence for
shielding, not sufficient evidence to promote the new route. Data/decks:
`layout/build/ring-bias-probe-002/`; capacitance audit:
`.amp/in/artifacts/ring-shield-capacitance-013.json`.

GDS-reimported candidate013 repeats that nominal screen with the reviewed
canonical aliases `x_buffer.VIN` and `x_bias.VBP`. Control/bias ripple is
638.391 µVpp / 13.252 mVpp. Interpolated output frequency is 1128.327 MHz,
versus native 1128.046 MHz (+0.0249%). Data/deck:
`layout/build/ring-bias-probe-003/`; interpolated frequency audit:
`.amp/in/artifacts/ring-shield-frequency-013.json`. These are unfilled
open-loop screens with the same passive-model and ideal-rail limitations,
not post-fill PLL lock, reference-spur or substrate-noise approval.

The complete analog assembly `cic-analog-shield-013` has report
`pll_analog/20261016-144005-694882`. Its FEOL-filled sidecar
`cic-analog-shield-feol-013`, report `pll_analog/20261016-144038-843445`,
passes native DRC/antenna, all installed KLayout DRC/density/antenna/extra
rules with zero markers, and independent GDS LVS. Native CMOM LVS,
resistor-body capacitance endpoint `a_25244_n17710#`, and annotated-GDS
import still fail; the overall check correctly exits nonzero.

All 13 ring leaf MAGs remain byte-identical to baseline. Running without
the flag as `cic-ring-baseline-replay-014` reproduces all 14 baseline MAGs,
excluding timestamps. Inspected GDS renders:
`.amp/in/artifacts/cic-ring-shield-013.png` and
`.amp/in/artifacts/cic-ring-shield-013-crossing.png`.
The completed native 15-case receiver sweep `cic-ring-shield-pvt-013`
passes 12/15 extracted cases, the same count as baseline008 and ring009.
SS/1.08 V/125 °C at VCTRL=0.5 V fails slew (162.07/166.10 ps);
FF/1.32 V/−40 °C at 0.8/0.9 V exceeds the frozen frequency limit
(2.025/2.168 GHz). The command correctly exits nonzero. Its full log is
`.amp/in/artifacts/cic-ring-shield-pvt-013.log`. No candidate is promoted.

## Tuning coverage and local inverter-output experiments

Do not equate 12/15 receiver-screen passes with coverage of the required
lock frequencies. The default `testbenches/xschem/pll_cosim.tb.sch` uses
100 MHz reference, N=20 and output /4: it requires a 2-GHz VCO for its
500-MHz external output. The frozen receiver is timed at 2 GHz, while
`cace/ring_oscillator.yaml` prose asks for 0.7–2.1 GHz but its executable
frequency spec only checks a 300-MHz minimum, without a maximum. Neither
that loose CACE check nor the ratio RTL's legal codes establish analog
tuning coverage. Do not silently reduce targets or expand frozen timing.

An unfilled baseline008 rail-point diagnostic uses the actual frozen
receiver, ideal control/rails/reset and the existing initial kick:

| PVT | VCTRL (V) | Loaded VCO frequency (GHz) |
| --- | ---: | ---: |
| TT / 1.20 V / 27 °C | 1.00 | 1.445242 |
| TT / 1.20 V / 27 °C | 1.20 | 1.481530 |
| SS / 1.08 V / 125 °C | 1.00 | 0.915026 |
| SS / 1.08 V / 125 °C | 1.08 | 0.924064 |
| FF / 1.32 V / −40 °C | 1.32 | 2.304805 |

All sampled VCO outputs have full swing. These points expose a tuning
coverage problem worth addressing independently of receiver slew; they
are not a continuous-range/monotonicity proof or a safe CP compliance
window. In particular, control tied to the positive supply is a diagnostic,
not a promised usable charge-pump operating point. Replayable decks/data:
`layout/build/ring-rail-probe-001/`.

`inverter.py` now joins the inverter's output drains locally on M4 instead
of taking them through upper M3 banks and an outside return column.
Candidate015 put this column too close to the input M4 hop: x1.VOUT–x2.VOUT
capacitance rose from 0.754 to 1.367 fF, and TT/SS rail-point frequencies
fell to 1.413/0.881 GHz. It is rejected despite passing local physical checks.
Candidate016 moves that output column 2 µm farther right. Native devices,
their guards, row pitch and transistor parameters remain unchanged.
The buffer uses the same local-output implementation with unchanged geometry;
only serialization order/redundant rectangles differ from buffer010.

| Loaded ring | TT, VCTRL=0.7 V (GHz) | TT, VCTRL=1.2 V (GHz) | SS, VCTRL=1.08 V (GHz) |
| --- | ---: | ---: | ---: |
| Baseline008 | 1.154751 | 1.481530 | 0.924064 |
| Local output016, original 18-µm row pitch | 1.224658 | 1.571007 | 0.980471 |
| Local output017, 15-µm row pitch | 1.225731 | 1.572282 | 0.981257 |

The compact pitch adds only about 0.1% frequency; retain the larger original
row separation. The source recipe is restored byte-for-byte to candidate016's
recorded recipe hash. The approximately 6% rail-point improvement still does
not demonstrate the default 2-GHz lock target. Data/decks for candidates015,
016 and017 are `ring-rail-probe-002`, `003` and `004` under `layout/build/`.

All three inverter/ring candidates pass native DRC/antenna/LVS, independent
GDS LVS and lumped-RC extraction, including reimported GDS; unfilled density
still fails. Checker stamps below `layout/build/`:

| Candidate | Inverter native / GDS report | Ring native / GDS report |
| --- | --- | --- |
| 015 | `20261016-151100-445780` / `20261016-151109-007929` | `20261016-151137-298547` / `20261016-151146-885723` |
| 016 | `20261016-151559-264795` / `20261016-151607-907579` | `20261016-151620-644467` / `20261016-151630-382338` |
| 017 | `20261016-151932-932227` / `20261016-151941-516109` | `20261016-151951-758118` / `20261016-152001-500879` |

Buffer reproduction016 also passes the same local checks: native report
`vco_buffer/20261016-151815-222365`, GDS report `20261016-151824-326684`.
The complete analog016 assembly report is `pll_analog/20261016-152358-259450`.
Its filled sidecar `cic-analog-local-out-feol-016`, report
`pll_analog/20261016-152435-395652`, passes native DRC/antenna, full installed
KLayout DRC/density/antenna/extra with zero markers and independent GDS LVS.
Native CMOM LVS, the same resistor-body capacitance endpoint and annotated
GDS import remain failing gates. No post-fill electrical signoff is claimed.

Inspected candidate016 GDS image:
`.amp/in/artifacts/cic-inverter-local-output-016.png`.
The completed native receiver sweep `cic-ring-local-out-pvt-016` passes
12/15 extracted cases. SS/1.08 V/125 °C at VCTRL=0.5 V still fails slew
(162.26/163.44 ps). FF/1.32 V/−40 °C at 0.8/0.9 V still exceeds 2 GHz
(2.125/2.274 GHz). The command correctly exits nonzero. Full log:
`.amp/in/artifacts/cic-ring-local-out-pvt-016.log`.

The finite-control screen was repeated with baseline008, native016 and
GDS-reimported016 using the same nominal setup and filter model as before:

| Route | Frequency (MHz) | VCTRL ripple (µVpp) | VBP ripple (mVpp) |
| --- | ---: | ---: | ---: |
| Baseline008 | 1118.136 | 612.638 | 14.016 |
| Local output016 native | 1185.946 | 603.766 | 13.762 |
| Local output016 GDS-derived | 1186.714 | 603.647 | 13.769 |

Baseline ripple reproduces exactly. Native016 improves nominal control/bias
ripple by 1.45%/1.81% while increasing frequency by 6.06%. The GDS-derived
frequency differs by +0.0647%. These modest ripple differences are nominal
screening observations, not a precision noise guarantee. Decks/data/logs:
`layout/build/ring-bias-probe-005/`.

Candidate018 combines inverter016 with `--shield-feedback`. It passes
local native/GDS DRC, antenna, LVS and lumped-RC extraction, with the same
seven unfilled-density failures. Native/GDS report stamps are
`ring_oscillator/20261016-153646-527545` / `20261016-153656-756437`.
Its nominal finite-control screen gives 1225.313 MHz, 625.247 µVpp VCTRL
and 13.137 mVpp VBP (`layout/build/ring-bias-probe-006/`). Although bias
ripple falls, control ripple rises versus016 and baseline. Retain016 as
the better conservative experiment; no full PVT or analog assembly of018
is claimed. No manual layout, schematic sizing or frozen digital was changed,
and neither the local-output candidate nor its filled assembly is promoted.

## Matched RC diagnosis and shorter interstage routes (019–023)

The original ring016 receiver sweep already includes the freshly netlisted
schematic under identical loading, supply ramp, kick, PVT and observation
window. The extracted-only 12/15 count does not establish tuning coverage,
and ignores schematic overspeed/buffer failures if quoted alone.

`characterize_oscillator.py --devices-only` reuses the existing charge-pump
diagnostic transformation: collapse resistor-connected nodes and remove
explicit wire capacitors, retaining extracted MOS dimensions and junction
geometry. It is a **diagnostic**, not a valid replacement PEX netlist. Use
the same report's C-only extraction to retain the reviewed startup alias:

```sh
PEX=macros/pll_analog/layout/build/ring_oscillator/20261016-151620-644467/pex
python3 macros/pll_analog/cic/characterize_oscillator.py \
  --ring "$PEX/ring_oscillator_c_only.spice" --startup-node x1.VIN \
  --receiver --output macros/pll_analog/layout/build/cic-ring-ablation-conly-019
python3 macros/pll_analog/cic/characterize_oscillator.py \
  --ring "$PEX/ring_oscillator_c_only.spice" --startup-node x1.VIN \
  --devices-only --receiver \
  --output macros/pll_analog/layout/build/cic-ring-ablation-devices-019
```

These output directories already exist; use new names when replaying.
The device-only file was checked to retain all extracted MOS lines exactly
and contain no explicit R/C elements. Both 15-case diagnostic sweeps finished;
their commands return nonzero for electrical failures, not execution errors.
Full-RC comparison is the immutable `cic-ring-local-out-pvt-016` run.
At VCTRL=0.7 V, using the same TT/SS/FF supply/temperature cases as before:

| Circuit/control | TT frequency (GHz) | SS frequency (GHz) | FF frequency (GHz) |
| --- | ---: | ---: | ---: |
| Fresh schematic | 4.142058 | 2.832067 | 5.995213 |
| Extracted devices, no wire RC | 4.157610 | 2.838486 | 6.030550 |
| Extracted devices plus wire C, zero wire R | 1.243091 | 0.836757 | 1.838174 |
| Full wire R plus original-node lumped C, ring016 | 1.224656 | 0.828352 | 1.799754 |

This isolates a dominant **wire-capacitance** penalty at these points; removing
wire R recovers only 1.51% at TT. The first two outputs are not full swing and
do not drive the frozen receiver correctly. Their frequencies are diagnostic
crossing rates, not qualified clock outputs. No wire C was removed from the
real layout or accepted extraction. Coupled-C endpoint totals in ring016
are 18.946 fF at VCO_CORE (`x1.VIN`), 8.902 fF at the first-stage output
and 9.439 fF at the second-stage output; these are endpoint sums, **not**
effective Miller capacitances.

The directed `--local-interstage` variant changes only the adjacent-stage
M3 trunk heights (24/25.5 µm instead of 37/38.5 µm); M4 drops join existing
ports. Feedback, supplies, guards, primitive geometry and placement stay
unchanged. Initial candidate019's 20/21.5-µm tracks failed DRC and shorted
net1 to VDD. It was rejected without electrical simulation. Candidate020
separates the tracks from the translated leaf's supply and VIN-via landings:

```sh
/opt/ciccreator/.venv/bin/python macros/pll_analog/cic/generate.py \
  --cell ring_oscillator --local-interstage \
  --leaf-library inverter=macros/pll_analog/layout/build/cic-inverter-016 \
  --leaf-library vco_bias=macros/pll_analog/layout/build/vco_bias/20261015-101136-565598/mag \
  --leaf-library vco_buffer=macros/pll_analog/layout/build/cic-buffer-010 \
  --output macros/pll_analog/layout/build/cic-ring-local-interstage-020
python3 macros/pll_analog/layout/run_checks.py all ring_oscillator \
  --library macros/pll_analog/layout/build/cic-ring-local-interstage-020
python3 macros/pll_analog/cic/characterize_oscillator.py \
  --ring macros/pll_analog/layout/build/ring_oscillator/20261016-233548-761021/pex/ring_oscillator_pex.spice \
  --startup-node x1.VIN --receiver --control-values .5 .7 .9 \
  --output macros/pll_analog/layout/build/cic-ring-local-interstage-pvt-020
```

Native report `ring_oscillator/20261016-233548-761021` and GDS round-trip
`20261016-233559-711194` pass local DRC, antenna, LVS and checked lumped-RC
extraction. KLayout still fails seven **unfilled global-density** categories:
AFil.g, GFil.g, M1.j, M2.j, M3.j, M4.j, TM1.c. No waivers. Native extraction
has 413 R/58 C; GDS-derived extraction has 1237 R/58 C. Different wire
segmentation does not establish electrical equivalence by itself.

Nominal VCTRL=0.7-V native screening (`cic-ring-local-interstage-smoke-020`)
improves frequency from 1.224656 to **1.325828 GHz (+8.26%)**, with
98.38/81.51-ps rise/fall and correct divide-by-two. All extracted receiver
checks pass at this point. The command still correctly exits nonzero because
the paired schematic fails swing/receiver checks. First/second-stage explicit
capacitance endpoint totals fall to 7.825/8.034 fF; the feedback/core total
increases to 19.294 fF. This is not overall noise or tuning closure.

The initial `--inverter-row-pitch-um 10` experiment, before the bank-routing
correction below, generated `cic-inverter-compact-021`.
Reports `inverter/20261016-233857-815304` and
`20261016-233907-992757` show zero Magic DRC/antenna markers, but both LVS
engines reject shorts between VIN, VBN, VDD and an internal current node;
PEX also rejects the shorted ports. Do not use this leaf. Its routing banks
need redesign, not a smaller pitch parameter alone. Default 18-µm generation
(`cic-inverter-default-repro-019`) reproduces the entire baseline016 Magic
library exactly excluding save timestamps. None of these experiments changes
the manual layout, schematic sizes or frozen digital; no new candidate is
promoted, filled, closed-loop-qualified or ready for integration.

### Completed sweeps and compact-stage bank correction

The nine-case native020 sweep (TT/SS/FF, VCTRL=0.5/0.7/0.9 V) finishes with
**7/9 extracted receiver passes**: SS/0.5 V fails 150-ps slew
(161.70/162.74 ps), FF/0.9 V exceeds 2 GHz (2.460909 GHz). Schematic
failures also keep the aggregate command nonzero. GDS-derived nominal020
(`cic-ring-local-interstage-gds-smoke-020`) is 1.326787 GHz with all extracted
receiver checks passing, versus 1.325828 GHz native (+0.0723%).

For compact022, the NMOS internal-current and VBN banks move from 9/10 µm
to −1/+1 µm so that the lowered PMOS supply routing no longer crosses them.
The 10-µm pitch retains all native per-device guards and MOS dimensions.
Native leaf report `inverter/20261016-234201-333710` and GDS round-trip
`20261016-234211-134626` pass local DRC/antenna/LVS and checked lumped-RC
extraction; seven unfilled-density categories still fail.

The first ring022 keeps its clock trunks above the compact leaf's VBP bank.
This passes the same local gates (native `ring_oscillator/20261016-234258-402672`,
GDS `20261016-234309-511825`) but gains only about 0.06% versus020:
shorter leaf wiring is offset by longer parent drops. It is not selected.

Ring023 instead moves the adjacent trunks and upper feedback with the leaf's
PMOS bank: 16/17.5/32 µm for net1/net2/VCO_CORE at 10-µm pitch. The recipe
derives these from the translated VBP port height, leaving the original
18-µm leaf's 24/25.5/40-µm tracks unchanged. Supplies, bias routes and device
guards remain. Native report `ring_oscillator/20261016-234544-348480` and GDS
`20261016-234555-627090` pass local DRC, antenna, both native/independent GDS
LVS and checked lumped-RC extraction. Native/GDS contain 413/1258 R, 58 C;
the same seven global-density failures remain, not waived.

Completed receiver-loaded samples at VCTRL=0.7 V:

| Candidate | TT frequency (GHz) | SS frequency (GHz) | FF frequency (GHz) |
| --- | ---: | ---: | ---: |
| Baseline016 | 1.224656 | 0.828352 | 1.799754 |
| Local interstage020, 18-µm rows | 1.325828 | 0.897510 | 1.949134 |
| Compact022, parent detours retained | 1.326619 | 0.898036 | 1.950269 |
| Compact023, parent tracks follow leaf | 1.427489 | 0.966008 | 2.099939 |

Ring023 gains about 16.6% versus016. Its TT/SS input rise/fall times are
98.24/81.77 ps and 148.01/128.56 ps. FF is 68.71/59.32 ps with correct
divide-by-two, **but fails the frozen 2-GHz frequency boundary**. Only these
three control/corner points are tested for023, not its full control range,
maximum tuning frequency or noise. Do not freeze it. GDS-derived nominal023
is 1.428617 GHz (+0.0790% versus native), 98.22/81.76 ps, with all extracted
receiver checks passing; the paired schematic still fails.

To reproduce022/023 with the current recipes, generate the leaf with
`--cell inverter --inverter-row-pitch-um 10`, then use the ring020 generation
command above with `--leaf-library inverter=.../cic-inverter-compact-022` and
a new output directory. The current ring recipe produces023's parent tracks,
not the superseded022 detour. Run `all` on both leaf and ring. The electrical
command uses023's native PEX path above, `--control-values .7`,
`--startup-node x1.VIN --receiver`, and a new output directory. For GDS use
its round-trip PEX and `--startup-node x_buffer.VIN --smoke --receiver`.
All decks, receiver manifests, hashes, data and logs remain under
`layout/build/cic-ring-{ablation-*,local-interstage-*,compact-*}`.

The current source reproduces the checked020 library exactly except save
timestamps. None of the layout-speed improvements proves 2-GHz SS tuning,
acquisition-safe FF frequency, full-range slew, post-fill closed-loop behavior
or substrate-noise/EM/ESD qualification. Ring016 remains the conservative
assembled baseline; the new options are unpromoted experiments.

### Isolated oscillator sizing and strict LVS (2026-10-17)

Sizing experiments now use `generate.py --schematic-library DIR` and repeated
`--set-size CELL.Mn.w=VALUEu` / `CELL.Mn.ng=INTEGER`. Overrides are restricted
to oscillator MOS devices. The generator copies `.sch`, `.sym`, and
`xschemrc` into its new output's `schematic/`, records `sizing.json`, and
netlists that copy. It never resizes the manual schematics. When building a
variant from another variant, the new manifest's overrides are incremental;
the copied schematic/netlist contains the complete sizes.

**Always pass that same source with `run_checks.py --schematic-library DIR`**
and `characterize_oscillator.py --schematic-library DIR`. The checker snapshots
and hashes the source, including for GDS reimport, before freshly netlisting it.

A real false-positive was found in the native LVS wrapper: `sak-lvs.sh`
returned zero and Netgen printed `Circuits match uniquely` even with width
property errors. Native LVS now also reads the detailed Netgen report and
rejects property errors. Only MOS `mm_ok`, a simulator mismatch-control
attribute absent from physical extraction, is removed from the LVS reference;
raw exports and physical W/L/M/NG remain. Negative control
`vco_buffer/20261017-102729-668236` compares the doubled buffer against the
original schematic: **both LVS engines fail**. Matching variant and baseline023
controls pass. Earlier wrapper-only success is not evidence of sizing LVS.

| Variant | Inverter total widths M1/M2/M3/M4 (µm) | Buffer total widths M1/M2/M3/M4 (µm) |
| --- | --- | --- |
| Compact023 control | 4.5 / 0.9 / 0.9 / 4.5 | 0.30 / 0.15 / 0.90 / 0.45 |
| Buffer024 | unchanged | 0.60 / 0.30 / 1.80 / 0.90 |
| Core025 | 13.5 / 2.7 / 2.7 / 13.5 | same as 024 |
| Skew026 | same as 025 | 0.60 / 1.20 / 1.80 / 0.90 |
| Balanced027 | same as 025 | 2.40 / 1.20 / 1.80 / 0.90 |
| Duty028 | 18.0 / 3.6 / 3.6 / 18.0 | 2.40 / 1.50 / 1.80 / 0.90 |

Finger counts stay 5/1/1/5 for the inverter and 1/1/3/3 for the buffer;
inverter row pitches are 10/12/13 µm for compact control/3×/4× sizing. Bias devices
remain unchanged. These are circuit changes in isolated copies, not merely
different transistor placement.

| Ring variant | Native report below `layout/build/ring_oscillator/` | GDS-reimport report |
| --- | --- | --- |
| 024 | `20261017-102724-708863` | `20261017-102737-143896` |
| 025 | `20261017-102733-392338` | `20261017-102745-169761` |
| 026 | `20261017-103329-588969` | `20261017-103342-263643` |
| 027 | `20261017-103623-602588` | `20261017-103634-332537` |
| 028 | `20261017-104151-437300` | `20261017-104201-935065` |

All five ring variants pass native Magic DRC/antenna, strict native LVS,
independent GDS LVS, and GDS-reimport Magic DRC/antenna/LVS and checked
lumped-RC extraction. **All still fail seven unfilled-density categories.**
The checks correctly return nonzero; this is not complete signoff.

Buffer024's completed SS/FF × VCTRL=0.5/0.7/0.9-V screen has **4/6 extracted
receiver passes**, versus the unchanged 2-GHz/150-ps frozen interface:

| PVT | VCTRL (V) | Extracted frequency (GHz) | Result |
| --- | ---: | ---: | --- |
| SS / 1.08 V / 125 °C | 0.5 | 0.363456 | PASS |
| SS / 1.08 V / 125 °C | 0.7 | 0.955207 | PASS |
| SS / 1.08 V / 125 °C | 0.9 | 1.096357 | PASS |
| FF / 1.32 V / −40 °C | 0.5 | 0.584447 | PASS |
| FF / 1.32 V / −40 °C | 0.7 | 2.080143 | FAIL frequency |
| FF / 1.32 V / −40 °C | 0.9 | 2.617473 | FAIL frequency |

At SS/0.5 V, the matched compact023 control fails input slew at
159.77/161.17 ps; 024 gives **121.55/138.14 ps**, correct counting and full swing.
Frequency changes −0.842%. New, independent zero-volt oscillator VDD sense
sources give **31.6005 → 32.9438 µW (+4.251%)**, integrated trapezoidally over
the settled 50–100-ns window. This is oscillator supply power only: it excludes
receiver power and control-source energy, uses ideal external rails, and is
not PLL/system power. Instrumented versus uninstrumented frequency/edge
results agree to reporting precision. GDS-derived024 at the same failing-case
fix gives 0.363792 GHz,121.51/138.11 ps,32.9597 µW and all receiver checks
passing (+0.0925% frequency versus native).

Larger cores alone are **not selected**. Core025 at SS/0.7 V has no valid
output crossings: output peaks at only 0.4634 V. A separate 30-ns internal-node
probe (20–30-ns window) confirms the extracted core still oscillates at
1.77056 GHz, spanning −0.0183–1.0275 V. The first buffer's output spans
0.2992–1.0930 V, and its final output spans −0.0212–0.4634 V. This is a
buffer-waveform failure, not evidence that the ring stopped. At SS/0.9 V,
output peaks at 0.2884 V. Core025's full six-case sweep has only 2/6 extracted
receiver passes; FF/0.7 and 0.9 V also fail swing and frequency.

Skew026 changes the failing polarity but does not solve it: SS/0.7 and 0.9 V
outputs span 0.1766–1.1109 and 0.3136–1.1122 V, respectively; both fail the
receiver. Balanced027 passes at SS/0.7 V (1.691594 GHz, 69.53/75.81 ps,
241.12 µW). At SS/0.9 V it reaches 1.905540 GHz with good oscillator swing
and 68.96/75.15-ps edges, but **the divider output swing fails**: maximum
0.93278 V versus the 0.972-V screening threshold. The input clock's minimum
high/low widths are 221.43/303.35 ps, not an ideal 50% clock; correct average
divide ratio alone is insufficient.

Duty028's completed extracted samples are:

| PVT | VCTRL (V) | Frequency (GHz) | Oscillator supply power (µW) | Extracted receiver result |
| --- | ---: | ---: | ---: | --- |
| SS | 0.70 | 1.884004 | 306.39 | PASS |
| SS | 0.75 | 1.977965 | 323.27 | PASS |
| SS | 0.76 | 1.992606 | 326.22 | FAIL 90%-rail divider swing |
| SS | 0.80 | 2.040845 | 335.25 | FAIL frequency and divider swing |
| SS | 0.90 | 2.113118 | 349.67 | FAIL frequency, divider swing and counting |
| FF | 0.50 | 1.377025 | 337.67 | PASS |
| FF | 0.60 | 2.825106 | 701.69 | FAIL frozen frequency boundary |

The SS/0.75-V point has 67.75/75.39-ps oscillator edges, correct per-cycle
divide-by-two, and divider peak 0.98797 V. GDS-derived extraction independently
gives **1.978324 GHz (+0.0182%)**, 67.74/75.38 ps, 323.21 µW and divider peak
0.98739 V, with all extracted receiver screens passing. Its clock high/low
widths are 238.51/266.95 ps. GDS-derived SS/0.7 V also passes at 1.884376 GHz.
This is a near-target sample, **not exact 2-GHz lock or acquisition proof**.
The adjacent native SS/0.76-V point still counts correctly but has divider
peak 0.96223 V, below this experiment's 0.972-V swing screen.

The analog screen uses 10%/90% rail thresholds. The frozen digital's older
`qualify_receiver.py` uses 20%/80% for Q swing (its accepted SS Q peak is
0.92043 V). Thus a current **90%-rail screening failure does not itself mean
counting failed or contradict the earlier freeze**. Keep these criteria
distinct; neither threshold has been relaxed. Pulse widths are now recorded
as `min_high_width_ps` / `min_low_width_ps` at half supply, without inventing
a new pulse-width pass limit. Actual waveform STA/noise-margin qualification
remains required; the frozen STA assumes 50% input duty and has small SS
pulse-width margin. Schematics also fail several paired cases.

Replay the first buffer change from the manual source, with a fresh name:

```sh
/opt/ciccreator/.venv/bin/python macros/pll_analog/cic/generate.py \
  --cell vco_buffer \
  --set-size vco_buffer.M1.w=0.60u --set-size vco_buffer.M2.w=0.30u \
  --set-size vco_buffer.M3.w=1.80u --set-size vco_buffer.M4.w=0.90u \
  --output macros/pll_analog/layout/build/cic-buffer-drive-024-replay

# Assemble using compact022, the original checked bias, and this buffer.
/opt/ciccreator/.venv/bin/python macros/pll_analog/cic/generate.py \
  --cell ring_oscillator --local-interstage \
  --schematic-library macros/pll_analog/layout/build/cic-buffer-drive-024-replay/schematic \
  --leaf-library inverter=macros/pll_analog/layout/build/cic-inverter-compact-022 \
  --leaf-library vco_bias=macros/pll_analog/layout/build/vco_bias/20261015-101136-565598/mag \
  --leaf-library vco_buffer=macros/pll_analog/layout/build/cic-buffer-drive-024-replay \
  --output macros/pll_analog/layout/build/cic-ring-buffer-drive-024-replay

python3 macros/pll_analog/layout/run_checks.py all ring_oscillator \
  --library macros/pll_analog/layout/build/cic-ring-buffer-drive-024-replay \
  --schematic-library macros/pll_analog/layout/build/cic-buffer-drive-024-replay/schematic

# Substitute the new checker report's PEX for a replay. Historical path shown.
python3 macros/pll_analog/cic/characterize_oscillator.py \
  --ring macros/pll_analog/layout/build/ring_oscillator/20261017-102724-708863/pex/ring_oscillator_pex.spice \
  --startup-node x1.VIN --receiver \
  --schematic-library macros/pll_analog/layout/build/cic-buffer-drive-024/schematic \
  --corners ss ff --control-values .5 .7 .9 \
  --output macros/pll_analog/layout/build/cic-ring-buffer-drive-pvt-024-replay
```

The corresponding saved electrical directories are
`cic-ring-buffer-drive-pvt-024`, `cic-ring-core-drive-pvt-025`,
`cic-ring-buffer-skew-pvt-026`, `cic-ring-buffer-balanced-pvt-027`,
`cic-ring-power-control-023`, `cic-ring-buffer-power-024`, and
`cic-ring-buffer-drive-gds-024`. Duty028 results are in `cic-ring-duty-ss-028`,
`cic-ring-duty-ff-028`, `cic-ring-duty-boundary-028`, `cic-ring-duty-gds-028`,
and `cic-ring-duty-boundary-gds-028`. Schematic comparisons also fail at several
points; the aggregate exit remains nonzero even when an extracted point passes.

Replay 028 directly from the manual schematic with new output names:

```sh
b=macros/pll_analog
d=$b/layout/build
py=/opt/ciccreator/.venv/bin/python
$py $b/cic/generate.py --cell vco_buffer \
  --set-size vco_buffer.M1.w=2.40u --set-size vco_buffer.M2.w=1.50u \
  --set-size vco_buffer.M3.w=1.80u --set-size vco_buffer.M4.w=0.90u \
  --output $d/cic-buffer-duty-028-replay
$py $b/cic/generate.py --cell inverter --inverter-row-pitch-um 13 \
  --schematic-library $d/cic-buffer-duty-028-replay/schematic \
  --set-size inverter.M1.w=18.0u --set-size inverter.M2.w=3.6u \
  --set-size inverter.M3.w=3.6u --set-size inverter.M4.w=18.0u \
  --output $d/cic-inverter-drive-028-replay
$py $b/cic/generate.py --cell ring_oscillator --local-interstage \
  --schematic-library $d/cic-inverter-drive-028-replay/schematic \
  --leaf-library inverter=$d/cic-inverter-drive-028-replay \
  --leaf-library vco_bias=$d/vco_bias/20261015-101136-565598/mag \
  --leaf-library vco_buffer=$d/cic-buffer-duty-028-replay \
  --output $d/cic-ring-duty-028-replay
python3 $b/layout/run_checks.py all ring_oscillator \
  --library $d/cic-ring-duty-028-replay \
  --schematic-library $d/cic-inverter-drive-028-replay/schematic
```

This sequence was independently rerun with `-repro-028` names: all 14 Magic
files match 028 exactly except save timestamps. Use the new inverter's
`schematic/` for checks and simulation. The SS near-target simulation uses
`--corners ss --control-values .75`, the native 028 PEX report above and
`--startup-node x1.VIN --receiver`; the GDS replay uses its GDS-reimport PEX
and `--startup-node x_buffer.VIN`. This does not select 028 for production.

**Acquisition is not fixed by these changes.** The frozen digital exposes no
coarse-band/bias-control output, and reset/enable do not reset the actual
analog control voltage. Existing IREF enters only the charge pump; limiting
pump current limits ramp speed, not final VCO frequency. A simple global
VCTRL cap must not be asserted safe without demonstrating both slow-corner
target reach and fast-corner acquisition behavior. A reference-current-limited
or coarse/fine bias redesign needs explicit circuit, interface, PVT, pulse
width, and acquisition validation before layout/fill closure. No such limiter,
band controller, relaxed receiver limit, or frozen-digital modification has
been implemented. Ring016 remains the conservative assembled baseline.

### Duty028 receiver timing and full-analog assembly (029)

`qualify_receiver.py` checks the measured settled oscillator waveform against
the **unchanged full routed digital macro**, not an ideal divide-by-two. It
first reproduces the frozen setup/hold results at all three Liberty corners
within 0.001 ps, then substitutes minimum-period/minimum-high/minimum-low
periodic envelopes and worst measured rise/fall slew in isolated SDC copies.
All original exceptions, generated clocks, uncertainty, loads and nominal
SPEF remain. Reports include setup/hold, pulse/min-period, electrical limits,
coverage and input hashes. It does not alter frozen timing qualification.

The initial `cic-duty028-receiver-sta-029` diagnostic gives:

| Measured extracted sample | Worst setup (ps) | Worst hold (ps) | Worst clock-limit slack (ps) | Receiver result |
| --- | ---: | ---: | ---: | --- |
| SS, 1.08 V, 125 °C, VCTRL 0.75 V, 1.978324 GHz | +20.022 | +273.020 | +5.513 | Counting, 90%-rail swing and both STA envelopes pass |
| FF, 1.32 V, −40 °C, VCTRL 0.5 V, 1.377025 GHz | +518.848 | +106.804 | +265.177 | Counting, 90%-rail swing and both STA envelopes pass |
| FF, 1.32 V, −40 °C, VCTRL 0.6 V, 2.825106 GHz | +146.657 | +106.804 | +87.945 | Same diagnostic passes, but outside frozen 2-GHz contract |

These are nominal-wire-RC, quiet-neighbor diagnostics. The slow-corner
pulse margin is only 5.5 ps: do not infer robust jitter/noise margin or exact
2.000-GHz closure from the 1.978-GHz sample. The TT transient uses 27 °C,
whereas TT timing Liberty is characterized at 25 °C. No arbitrary-waveform,
reset-recovery, acquisition or closed-loop guarantee follows from this test.

```sh
python3 macros/pll_analog/cic/qualify_receiver.py \
  --characterization macros/pll_analog/layout/build/cic-ring-duty-boundary-gds-028 \
    macros/pll_analog/layout/build/cic-ring-duty-ff-028 \
  --output macros/pll_analog/layout/build/cic-duty028-receiver-sta-replay-029
```

The full 15-point GDS-derived receiver sweep is retained in
`cic-duty028-gds-receiver-pvt-029`; timing reports are in
`cic-duty028-gds-receiver-sta-pvt-029` (also includes the separate SS/0.75-V
boundary sample). Eleven of the 15 sweep points pass counting, the conservative
10%/90% rail screens, slew and both timing envelopes. Only five also remain
within the unchanged frozen 2-GHz contract. Above-contract diagnostic passes
are **not** frequency-limit waivers. Both tools exit nonzero for the matrix.

| Corner | VCTRL (V) | Extracted frequency (GHz) | Setup (ps) | Hold (ps) | Clock-limit slack (ps) | Counting / 90%-rail Q screen |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| TT, 1.20 V, 27 °C | 0.5 | 1.013329 | +672.474 | +167.326 | +346.233 | PASS / PASS |
| TT | 0.6 | 2.024037 | +179.750 | +167.326 | +98.586 | PASS / PASS |
| TT | 0.7 | 2.756212 | +48.506 | +167.326 | +29.659 | PASS / PASS |
| TT | 0.8 | 3.082394 | +10.117 | +167.326 | +10.066 | PASS / PASS |
| TT | 0.9 | 3.236462 | −5.326 | +167.326 | +2.112 | PASS / FAIL |
| SS, 1.08 V, 125 °C | 0.5 | 0.856477 | +681.903 | +273.020 | +343.690 | PASS / PASS |
| SS | 0.6 | 1.516589 | +173.911 | +273.020 | +84.959 | PASS / PASS |
| SS | 0.7 | 1.884376 | +45.221 | +273.020 | +18.236 | PASS / PASS |
| SS | 0.8 | 2.041196 | +1.931 | +273.020 | −2.487 | PASS / FAIL |
| SS | 0.9 | 2.113460 | −31.576 | +273.020 | −11.553 | FAIL / FAIL |
| FF, 1.32 V, −40 °C | 0.5 | 1.377305 | +518.702 | +106.804 | +265.028 | PASS / PASS |
| FF | 0.6 | 2.825694 | +146.582 | +106.804 | +87.879 | PASS / PASS |
| FF | 0.7 | 3.957602 | +45.364 | +106.804 | +36.494 | PASS / PASS |
| FF | 0.8 | 4.518842 | +13.983 | +106.804 | +20.403 | PASS / PASS |
| FF | 0.9 | 4.787104 | +1.582 | +106.804 | +14.083 | PASS / FAIL |

All sampled hold checks pass. The SS high-control results establish a real
acquisition risk; conversely the fast-corner >2-GHz passes establish that
crossing the frozen boundary alone is not proof of receiver malfunction.
FF/0.9-V passes timing but fails the conservative analog swing screen, which
is why neither STA alone nor a mean-frequency measurement is sufficient.

An additional SS near-target probe at VCTRL 0.766 V gives **2.001205 GHz**
and correct division. Its setup/hold/pulse slacks are +14.245/+273.020/+2.569 ps,
but Q peaks at **0.947708 V**, below the 0.972-V conservative 90%-rail screen
(above the legacy 80%-rail threshold). This is not a counting failure, nor a
qualified 2-GHz design: the pulse margin is especially thin. The result is
retained in `cic-duty028-gds-receiver-target-029` and
`cic-duty028-gds-receiver-target-sta-029`; replay characterization with
`--corners ss --control-values .766`, then run the same timing qualifier.
Both combined diagnostics return nonzero; the frozen frequency boundary
also remains unchanged. Receiver pulse/swing margin needs improvement or a
reviewed noise-margin budget before 028 can be selected for production.

```sh
b=macros/pll_analog
d=$b/layout/build
python3 $b/cic/characterize_oscillator.py \
  --ring $d/ring_oscillator/20261017-104201-935065/pex/ring_oscillator_pex.spice \
  --startup-node x_buffer.VIN --receiver \
  --schematic-library $d/cic-inverter-drive-028/schematic \
  --control-values .5 .6 .7 .8 .9 \
  --output $d/cic-duty028-gds-receiver-pvt-replay-029
# A failing matrix still retains all waveforms and summary.json.
python3 $b/cic/qualify_receiver.py \
  --characterization $d/cic-duty028-gds-receiver-pvt-replay-029 \
    $d/cic-ring-duty-boundary-gds-028 \
  --output $d/cic-duty028-gds-receiver-sta-pvt-replay-029
```

The new assembled library `layout/build/cic-analog-duty-029` combines CP007,
filter004 and duty028 using the matching isolated 028 schematic library.
Applying the existing FEOL/metal fill recipe produces
`cic-analog-duty-feol-029`; report
`pll_analog/20261017-225555-407204`. All installed KLayout
DRC/density/antenna/extra rules pass with **zero markers**, as do native full
DRC, Magic antenna and independent GDS LVS. The actual Magic-reexported
geometry has an empty physical XOR; restoring only the unsupported 99/40
recognition sidecar also gives an empty recognition XOR and passing KLayout
LVS (`pll_analog/20261017-225611-626116`). A changed-metal reexport negative
control correctly fails before LVS. Port purpose 50/2 must remain in the
Magic import, unlike unsupported 99/40; removing it loses VCO_OUT's port and
is explicitly not part of this workflow.

**The full check still fails, deliberately:** native Magic LVS cannot
recognize the CMOM devices, and the resistor-body C endpoint
`a_25244_n17710#` has no corresponding node in the exported resistance
network. The installed three-terminal rhigh model has two private body-end
nodes behind contact resistances, not an exposed midpoint. Moving/dropping
the C or splitting the foundry model is not an exact repair. Selective
flattening can retain ideal native capacitors, but does not supply foundry
CMOM recognition or qualified passive PEX. These are extraction/model
blockers, not solved by making the routing denser. Post-fill electrical,
closed-loop, supply/substrate coupling, EM and pad/ESD qualification remain
open. Neither this library nor duty028 has been promoted.

```sh
b=macros/pll_analog
d=$b/layout/build
/opt/ciccreator/.venv/bin/python $b/cic/generate.py --cell pll_analog \
  --schematic-library $d/cic-inverter-drive-028/schematic \
  --leaf-library charge_pump=$d/cic-cp-route-007 \
  --leaf-library loop_filter=$d/cic-filter-004 \
  --leaf-library ring_oscillator=$d/cic-ring-duty-028 \
  --output $d/cic-analog-duty-replay-029
python3 $b/layout/run_checks.py all pll_analog \
  --library $d/cic-analog-duty-replay-029 \
  --schematic-library $d/cic-inverter-drive-028/schematic
# Full checks intentionally fail on passive extraction and unfilled density.
# Use that new report directory as --report, not the historical one below.
python3 $b/cic/metal_fill.py --feol \
  --report $d/pll_analog/20261017-225512-217219 \
  --output $d/cic-analog-duty-feol-replay-029
python3 $b/layout/run_checks.py all pll_analog \
  --library $d/cic-analog-duty-feol-replay-029 \
  --schematic-library $d/cic-inverter-drive-028/schematic
# Still nonzero: no extraction failure is waived.
```

### Receiver pulse-balance follow-up (030–032)

Three isolated layouts retain the 028 inverter/bias and change only buffer
widths: 030 increases M3 (output PMOS) 1.8→2.4 µm; 031 increases M2
(first-stage NMOS) 1.5→1.8 µm; 032 combines both. Finger counts are unchanged.
All pass native local DRC/antenna, strict native and GDS LVS, checked lumped-RC
PEX, and the GDS-reimport checks. Isolated ring density still fails seven
categories. None changes the frozen digital macro or manual sources.

**031 is the better near-target experiment, not a frozen selection.**
Increasing the high pulse indiscriminately is not safe: 032 improves Q swing
but fails the opposite pulse-width check. Results below are GDS-derived,
SS/1.08 V/125 °C, with the actual frozen receiver and nominal wire RC:

| Variant / VCTRL (V) | Frequency (GHz) | Q peak (V) | Setup (ps) | Hold (ps) | Minimum clock-limit margin (ps) | Result |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| 028 / 0.766 | 2.001205 | 0.947708 | +14.245 | +273.020 | +2.569 | Fails 90%-rail Q screen |
| 030 / 0.766 | 2.002987 | 1.037193 | +13.914 | +273.020 | +9.134 | Diagnostic pass; above frozen frequency |
| 031 / 0.766 | 1.990962 | 1.023920 | +16.822 | +273.020 | +18.333 | Pass including frozen frequency |
| 031 / 0.7729 | 1.999923 | 1.015634 | +14.573 | +273.020 | +17.180 | Pass including frozen frequency |
| 032 / 0.772 | 2.000752 | 1.057569 | +14.483 | +273.020 | −4.890 | Rejected: opposite clock pulse too short |

At the 031 near-target point, oscillator-only supply power is 330.20 µW,
versus 327.50 µW for the nearby 028 comparison (+0.82%, not exactly equal
frequency/control voltage). Q now exceeds the 0.972-V screen by 43.6 mV.
The separate 031/0.773-V point gives 2.000049 GHz, Q 1.015509 V and +17.164-ps
pulse margin; its tiny frequency overshoot is still flagged, not waived.
`receiver-028-vs-031.png` under `.amp/in/artifacts/` compares simulated CLK/Q
waveforms aligned to Q's rising 50% crossing; it does not imply phase alignment.

**Acquisition and noise margin are still open.** At SS/0.9 V, 031 counts at
2.102702 GHz but fails Q swing and setup (−26.735 ps). At TT/0.9 V it counts
at 3.219966 GHz but fails Q swing and setup (−3.737 ps). FF/0.9 V at 4.763341 GHz
passes the diagnostic (+2.638-ps setup, +20.423-ps clock limit), not the frozen
frequency contract. TT/FF low-control checks pass; all sampled hold checks
pass. The 032 high-control comparison was also retained and not promoted.
No clamp, coarse-band control, noise allowance, or timing exception was added.

Reports under `layout/build/ring_oscillator/` are 030 native/GDS
`20261017-231826-392524` / `20261017-231839-532559`; 031
`20261017-231843-729164` / `20261017-231854-553393`; 032
`20261017-232314-191208` / `20261017-232326-254948`.
Electrical directories are `cic-ring-pulse-ss-{030,031,032}`,
`cic-ring-pulse-pvt-{031,032}`, `cic-ring-pulse-target-{031,032}` and
`cic-ring-pulse-contract-031`; corresponding `*-sta-*`/`*-sta` folders retain
the full measured-waveform timing reports and hashes. The primary 031
near-contract report is `cic-ring-pulse-contract-sta-031`.

The filled full assembly `cic-analog-pulse-feol-031` passes all installed
DRC/density/antenna/extra decks (zero markers), native local DRC/antenna, GDS
LVS and physical/recognition polygon XOR; GDS-reimported KLayout LVS passes.
Parent report `pll_analog/20261017-232918-520842`, child
`20261017-232939-005563`. Native CMOM LVS and the same rhigh-body capacitance
endpoint still fail. Full post-fill electrical qualification is not possible
with that failing Magic PEX; the successful isolated-ring simulation is not
a post-fill full-analog result. Failed 032 also has a physically checked
filled assembly but is not the preferred electrical candidate.

Replay 031 from the isolated 028 schematic (028's manual-source replay is
given above), with new output names:

```sh
b=macros/pll_analog; d=$b/layout/build
py=/opt/ciccreator/.venv/bin/python
$py $b/cic/generate.py --cell vco_buffer \
  --schematic-library $d/cic-inverter-drive-028/schematic \
  --set-size vco_buffer.M2.w=1.80u --output $d/cic-buffer-pulse-replay-031
$py $b/cic/generate.py --cell ring_oscillator --local-interstage \
  --schematic-library $d/cic-buffer-pulse-replay-031/schematic \
  --leaf-library inverter=$d/cic-inverter-drive-028 \
  --leaf-library vco_bias=$d/vco_bias/20261015-101136-565598/mag \
  --leaf-library vco_buffer=$d/cic-buffer-pulse-replay-031 \
  --output $d/cic-ring-pulse-replay-031
python3 $b/layout/run_checks.py all ring_oscillator \
  --library $d/cic-ring-pulse-replay-031 \
  --schematic-library $d/cic-buffer-pulse-replay-031/schematic
# Substitute the new GDS-reimport report's PEX below for a fresh replay.
python3 $b/cic/characterize_oscillator.py \
  --ring $d/ring_oscillator/20261017-231854-553393/pex/ring_oscillator_pex.spice \
  --startup-node x_buffer.VIN --receiver --corners ss --control-values .7729 \
  --schematic-library $d/cic-buffer-pulse-replay-031/schematic \
  --output $d/cic-ring-pulse-contract-replay-031
python3 $b/cic/qualify_receiver.py \
  --characterization $d/cic-ring-pulse-contract-replay-031 \
  --output $d/cic-ring-pulse-contract-sta-replay-031
```

The characterization aggregate still exits nonzero because its **schematic
control** oscillates faster and fails receiver checks. The extracted 031
near-contract record passes every receiver screen; its timing qualifier
returns zero. Retain both controls rather than hiding the schematic failure.

### Alternative passive extraction investigation (033–037)

The container also has KLayout-PEX/FasterCap. Its system KPEX 0.3.15 advertises
CMOS5L, but the first filter run (`cic-filter-kpex-033`) fails on missing
`rule_decks/sram_integration.lvs`. This is the upstream wheel symlink-packaging
defect documented in [issue 210](https://github.com/iic-jku/klayout-pex/issues/210).
Restoring only that include is insufficient. Older RC/connectivity/blackbox
problems documented in [issue 211](https://github.com/iic-jku/klayout-pex/issues/211)
also make that release unsuitable as an alternative qualification path.

An isolated environment `layout/build/cic-kpex-env-034` now contains
**KPEX 0.6.10 / Python KLayout 0.30.12**. No installed PDK, system tool, or
existing checker was changed. Use `env -u PYTHONPATH` so the container's older
KLayout Python module does not override the isolated environment. Package
versions and CLI options are retained in
`.amp/in/artifacts/cic-kpex-034-config.txt`. A temporary upstream checkout was
used to inspect packaging and removed; this environment uses released wheels.

The full filter's PEX-adapted LVS **actually reports netlists match**, retains
two `cap_cmomf` instances and one `rhigh`, and runs with the correct CMOS5L
stack and `--blackbox True`. Do not substitute the SG13G2 technology merely
because GDS layers overlap. The first RC attempt (`cic-filter-kpex-034`)
exited 137 with a cgroup OOM-kill event while a diagnostic CC run was also
active. The Docker VM has about 12.7 GiB RAM; the observed RC process alone
reached roughly 11.5 GiB RSS. This does **not** prove a serial run cannot fit.
The isolated CC follow-up (`cic-filter-kpex-cc-035`) completed successfully
using that same PEX-LVS database, retaining the foundry models and six
reported external C contributions. Its emitted SPICE has **three ports**,
including the internal filter-zero node; interface normalization/validation
is required before it can replace the two-port filter in a simulation.
CC is not RC, and neither result is a foundry-qualified extraction claim.

A smaller 32.643-µm CMOM-only CC control (`cic-kpex-small-036`) completes and
retains one modeled capacitor plus two substrate capacitors (~22.55 fF per
terminal), with no additional terminal-to-terminal intrinsic capacitance.
However its two-port reference does not describe the extraction's extra
`sub!` substrate port, and LVS reports **netlists do not match** even though
KPEX exits zero and says “klayout LVS succeeded”. Thus the control is **not
a passing LVS/PEX result**. Actual deck comparison results, model dimensions,
ports, terminal connectivity, substrate assumptions and capacitance matrices
must be audited independently of the KPEX process exit code. This negative
control is retained rather than hiding the interface discrepancy.

The filter's RC retry is `cic-filter-kpex-serial-037`, run **alone**, reusing
the passing PEX-LVS database after both earlier jobs ended. Do not run another
memory-intensive extractor concurrently. Completion/structural audit and
electrical comparison are still required; no alternative extractor has been
added to `make check`, and all existing Magic failures remain visible.

Direct inspection of that input LVS database confirms the internal `$3`
net is the reference `FILTER_ZERO`: it joins the large CMOM top plate to
one rhigh terminal; the small CMOM top plate and opposite rhigh terminal
are VCTRL, and both bottom plates and rhigh substrate are VSS. The input
database has only the two intended external ports. KPEX subsequently promotes
the internal net to its third output port. A future simulation adapter must
keep that node internal, not ground it or leave the filter branch disconnected.
The serial RC solver also warns that `rhigh_sub` has no resistance-network
nodes; `$3` in that warning identifies the **device**, not a claim that its
substrate is tied to the internal `$3` net. This substrate limitation still
needs review before accepting RC. At the last check the process was active
at roughly six minutes, about 12 GiB RSS, and had not emitted a final SPICE
netlist; the partial report database is not an extraction pass.

```sh
b=macros/pll_analog; d=$b/layout/build
# One-time isolated setup (use a new environment directory for a replay).
python3 -m venv $d/cic-kpex-env-replay
env -u PYTHONPATH $d/cic-kpex-env-replay/bin/pip install klayout-pex==0.6.10
env -u PYTHONPATH $d/cic-kpex-env-replay/bin/python -m klayout_pex extract \
  --pdk ihp-sg13cmos5l --2.5D --mode RC --blackbox True --threads 2 \
  --gds $d/loop_filter/20261017-225425-093115/loop_filter.gds \
  --cell loop_filter \
  --schematic $d/loop_filter/20261017-225425-379997/lvs-klayout/loop_filter.cdl \
  --out-dir $d/cic-filter-kpex-replay
# Audit deck LVS, model/terminal/port mapping and RC checks, not just exit 0.
```

### Closed-loop extraction follow-up (038–048, October 18)

The serial filter RC retry **037 completed**: 6,405 resistors, 2,509
capacitors, two original `cap_cmomf` instances and one `rhigh`. Its five
promoted pins must be wrapped as `VCTRL C1_INTERNAL VSS C2_INTERNAL
FILTER_ZERO`; the extra nodes remain internal, without bypassing wire
resistance. The audit in `cic-filter-rc-audit-040.json` finds no capacitor
endpoints outside the intended resistor-connected components. Independent
filter AC comparison against CC differs by at most approximately 0.344%
through 10 MHz (3.16% through 100 MHz). The resistor substrate is still an
ideal VSS connection, **not a spatial substrate-resistance/noise model**.

`build/cic-closed-loop-038/analog_hierarchical_rc.spice` combines that filter
with the checked charge-pump/ring RC diagnostics. This remains a hierarchical
diagnostic without assembled inter-block/fill coupling. The extended
`scripts/pll/run_pll_cosim.sh` accepts explicit `ANALOG_SPICE`,
`ANALOG_SUBCKT`, `ANALOG_VCTRL_NODE`, and `ANALOG_STARTUP_NODE`; it validates
the six analog interface names and replaces the unused schematic analog
definitions. `RECEIVER_SPICE` adds the frozen transistor receiver as a
physical load/witness. `PFD_SPICE` replaces the ideal RTL UP/DOWN outputs
with the frozen transistor PFD plus its nominal extracted network. Functional
feedback dividers still use RTL; a receiver witness is **not** an extracted
digital closed-loop timing simulation. External rails/clocks remain ideal.

Set `KEEP_WORK=1` to retain decks/logs and `COSIM_WAVEFORM=/absolute/file.raw`
to export binary waveforms. `report_closed_loop.py FILE.raw --output DIR
--label TEXT` reports sampled ±1% frequency convergence, settled VCTRL
ripple, PFD pulse widths, cycle-by-cycle receiver swing, period variation,
and deterministic output sidebands. These are diagnostics, not phase-noise,
phase-lock, ESD or full-chip signoff. Its asymmetric analytical waveform
control and deliberately weak-cycle/truncated-file controls were exercised.

**Do not use hierarchical full-GDS KPEX extraction 041 as an accepted
electrical model.** It retains both modeled CMOMs but also emits approximately
0.994/9.035 pF of filter terminal-to-ground capacitance, unlike the standalone
filter's fF-scale external terms. KPEX 0.6.10 collects its capacitor exclusion
net pairs from top-circuit `each_device()` only, whereas conductor geometry
is collected recursively. Nested modeled capacitors therefore need structural
flattening before that exclusion is valid. Extraction-only flattened GDS
retry 045 is testing this, without changing the design GDS or dropping any
capacitance by value. Native KPEX unsimplified comparison also fails on
physical multi-fingers; independent installed-PDK strict-port comparison
with normal device combination passes (042), and a deliberately tripled
MOS-width reference correctly fails (046). Neither proves PEX exclusion.

`reduce_floating_caps.py INPUT --output NEW.spice` is an optional CC-only
simulation preparation step, requiring NumPy/SciPy. It preserves all ports
and compact-device rows and eliminates only internal capacitor-only nodes
using a Schur complement, retaining their terminal coupling rather than
grounding fill. It rejects resistive input. This assumes zero initial
floating charge, retains the original extraction, and emits a hash/numerical
audit alongside the new file. An asymmetric 2/3/5-fF star plus a 7-fF direct
branch yields independently expected 1/1.5-fF ground branches and a 7.6-fF
mutual branch. For 041 it reduces 73,213 capacitors/10,952 internal nodes to
48 terminal-equivalent capacitors. Two asymmetric independent ngspice AC
current comparisons at 1 MHz/500.5 MHz/1 GHz agree to printed precision.
That validates the reduction, **not the original extraction's physics**.
Use `.option klu` for these large sparse AC controls; the installed ngspice
47 explicitly reports KLU support. Do not silently change a running deck.

The PDK CMOM model explicitly calls itself a low-frequency engineering
estimate, not silicon-validated, and provides no characterized process or
mismatch variation. Even a successfully simulated extraction is not a
foundry-qualified RF/noise/ESD signoff result. Full post-fill RC, acquisition
receiver margin, supply/substrate coupling and final pad protection remain
separate acceptance gates. No analog candidate has been frozen here.

### Flat-GDS and model-stack correction (045–066)

Extraction-only flattening removes the erroneous intrinsic CMOM geometry
contribution: the large capacitor's extra terminal-to-ground C drops from
approximately 9.035 pF to **15.102 fF**, while both compact-model instances
remain. Total extra VCTRL-to-ground C is about **49.834 fF**. To avoid
promoting every leaf pin label to a top-level port, remove only child-cell
text in the extraction copy before `top.flatten(-1, True)`. Keep original
top labels and all mask geometry. Retry 051 has exactly the six intended
ports. Independent PDK strict-port LVS passes (055); all non-text
polygon/box/path layer XORs versus 045 are empty. Mapping device terminals
and comparing the entire reduced C matrix finds a maximum difference of
7.11e-15 fF (056). Thus label cleanup did not change the simulated multiport.
The two independent full/reduced ngspice AC patterns also agree to a relative
maximum port-current error below 1.1e-14 (049).

**A second translation error supersedes the earlier KPEX closed-loop runs.**
The physical CMOM PCells and schematic specify Metal2–Metal4, but KLayout's
device export retains W/L and omits `mmin/mmax/subblock`. The PDK SPICE
defaults to Metal1–Metal4: 1.287 rather than 0.915 fF/µm², about **40.7% too
large**. The LVS device class does not verify these stack parameters; a
passing W/L/connectivity comparison does not establish their correctness.
Do not accept electrical results using that default stack, including the
early hierarchical RC and flat-CC trials. Their connectivity/parasitic-network
audits remain useful, but their nominal loop dynamics are not approved.

`restore_cap_stack.py INPUT --magic-dir DIR --output NEW.spice` restores
explicit stack parameters from the generated physical PCell metadata and
checks the actual metal sections agree. It matches extracted W/L within one
5-nm grid step, rejects missing/ambiguous/conflicting physical matches, never
overwrites the extraction, and emits an audit. CLI controls reject a wrong
explicit `mmin=1` and an unmatched 200-µm device. Its output matches the
separately prepared corrected simulation deck (066). This is an independent
model-translation audit, **not an extension of the PDK LVS device class**.

```sh
b=macros/pll_analog; d=$b/layout/build
python3 $b/cic/restore_cap_stack.py \
  $d/cic-analog-kpex-flat-clean-051/pll_analog_flat_clean__pll_analog/pll_analog_k25d_pex_netlist.spice \
  --magic-dir $d/cic-analog-pulse-feol-031 \
  --output $d/cic-analog-kpex-flat-clean-051/pll_analog_stack2.spice
python3 $b/cic/reduce_floating_caps.py \
  $d/cic-analog-kpex-flat-clean-051/pll_analog_stack2.spice \
  --output $d/cic-analog-kpex-flat-clean-051/pll_analog_stack2_reduced.spice
```

The accepted schematic-baseline binary replay (048) measures 500.017 MHz
over its entire final microsecond, sampled ±1% frequency convergence from
2.25 µs, and 3.263 mV VCTRL ripple. This uses ideal RTL PFD/dividers and the
original schematic oscillator, not candidate 031, so it is a reference rather
than an isolated layout-only delta.

A simulation-only receiver-feedback mode is being validated: the physical
receiver DIV2 clocks the functional divider, and a generated RTL copy bypasses
only the already-physical first /2 stage. Production RTL stays unchanged.
Shim tables are reconstructed from the actual Verilator header because
bypassing the stage changes port declaration order. An independent 1-GHz
half-clock stimulus produces 1 GHz at PLL_CLK, 500 MHz at TEST_CLK and
100 MHz feedback for external ratio 20 (060), detecting accidental double
division or output-port permutation. The remaining RTL is still ideal;
this does not become routed-digital timing/noise signoff. Corrected-stack
TT/SS receiver-feedback runs are 064/065 under `cic-analog-cosim-stack-063`;
do not report those as passing before their settled results are audited.

### Closed-loop replay and observation checks (067–071)

`scripts/pll/run_pll_cosim.sh` now exposes the receiver-feedback mode above.
The receiver reset also honors ENABLE, while preserving the original analog
reset ramp when enabled. Only generated simulation RTL is bypassed; the
production RTL and frozen digital macro are not modified. Default-mode
regression067 completes successfully: the first 100 measured output periods
give **500.075 MHz**, sampled frequency convergence **2.25 µs**, and VCTRL
ripple **3.263 mVpp**. The separate full-window baseline048 is 500.017 MHz;
these are different measurement windows of the same schematic reference,
not a measured improvement from layout.

Clock-loss control062b grounds the physical receiver input: TEST_CLK and
feedback both become constant and UP stays high. The independent half-clock
control060c also verifies the generated Verilator port mapping and prevents
an accidental second /2. These controls validate the simulation connection,
not the analog layout's loop performance.

Saving only TEST_CLK and receiver Q is insufficient to exclude a false lock
caused by missed VCO edges. The runner now also saves VCO_CLK, FB_CLK and
REF_CLK. The reporter measures VCO frequency, counts VCO edges in each
complete Q period, and measures continuous relative feedback phase at
reference edges (without wrapping away cycle slips). Missing VCO observations
are explicitly marked `observed: false`, not accepted as a correct /2.
Synthetic CLI controls070 keep TEST_CLK at 500 MHz while substituting a
4-GHz VCO or a slipping 102-MHz feedback clock. The former fails VCO/rate
checks; the latter reports 19.8 ns relative phase movement instead of hiding
it modulo a reference period. These are reporter tests, not circuit evidence.

Corrected physical-feedback runs064/065 were already running before those
extra vectors were added. They remain limited electrical diagnostics even
if their output-frequency screen passes. Fully observed TT replay071 uses
the promoted runner and writes `tt_observed_4us.raw`; its report is generated
automatically on completion. Do not call this replay passing while pending.
KLU trial068/068b aborts at startup with a timestep-too-small error; it is not
an accepted speed optimization. The runner retains its original solver.
Observed SS replay072 is queued after071, conditional on TT output/VCO
frequency, every-cycle /2 and every-cycle Q swing passing. A failed TT gate
stops that queue rather than spending another run on an already-failing
interface. Reports are `.amp/in/artifacts/cic-closed-loop-tt-observed-071/`
and `cic-closed-loop-ss-observed-072/`; absence means pending/failed, not PASS.

Replay inside the tools container, from the repository root (choose an unused
waveform/report destination):

```sh
d="$PWD/macros/pll_analog/layout/build"
export KEEP_WORK=1 SIM_TIME_S=4e-6 DIV_RATIO=160 TEST_DIV=1 FREF_HZ=100e6
export CORNER=tt TEMP_C=27 VDD=1.2 RECEIVER_FEEDBACK=1
export ANALOG_SPICE="$d/cic-analog-cosim-stack-063/analog_cc.spice"
export ANALOG_SUBCKT=pll_analog_cc ANALOG_VCTRL_NODE=VCTRL
export ANALOG_STARTUP_NODE=xdie.STARTUP
export RECEIVER_SPICE="$d/cic-ring-pulse-contract-031/frozen_receiver.spice"
export PFD_SPICE="$d/cic-cp-pfd-001/pfd_driver.spice"
export COSIM_WAVEFORM="$d/cic-analog-cosim-stack-063/tt_observed_next.raw"
bash scripts/pll/run_pll_cosim.sh
python3 macros/pll_analog/cic/report_closed_loop.py "$COSIM_WAVEFORM" \
  --output .amp/in/artifacts/cic-closed-loop-tt-next \
  --label 'Filled analog031 TT: corrected CMOM stack, physical feedback'
```

For SS use `CORNER=ss TEMP_C=125 VDD=1.08`, new output paths and reporter
`--vdd 1.08`. A frequency screen is not phase-lock/noise signoff. The repo
has no final numerical acquisition-time, ripple, spur or phase-noise budgets;
those quantities are reported, not silently assigned new acceptance limits.
Full analog wire-R extraction, spatial substrate/supply coupling, complete
PVT/acquisition coverage, EM and pad/rail ESD remain separate open gates.

### Physical feedback-buffer boundary correction (074–076)

**The direct-raw-Q feedback replays064/065/071 are diagnostic controls,
not the final hardware-faithful loop model.** Nominal064 completes with
500.094 MHz over 3–4 µs, 5.508 mV VCTRL range and passing raw-Q swing.
Slow/hot065 gives 478.735 MHz, 199.460 mV control range and failing raw-Q
swing. Its late UP runaway must not be labeled a proven hardware failure.
Audit074 shows that after 3.8 µs raw Q still crosses half-supply, but never
reaches the chosen ADC's 0.9-VDD high threshold. UP consequently stays high.

The real frozen macro does not digitize raw Q at this point. Q drives
`clkbuf_regs_0_half`, whose output `pll_clk_regs` feeds the feedback-register
and /4 clock tree. Its receiver-extraction name is `load_1366_out`; the
separate `load_1329_out` belongs to the TEST_CLK /2 branch. The runner now
resolves the register buffer's ID from frozen-v1 SPEF, verifies that buffer
exists in the supplied receiver, and samples its **physical output**.
It does not change ADC thresholds, flop types, raw-Q swing criteria, or the
production/frozen digital. Downstream CTS and logic remain ideal; these
buffer outputs are unloaded, so this is not complete digital timing signoff.

Clamped full-filled-analog controls075 reproduce the distinction at
SS/1.08 V/125 °C, measured over 60–100 ns:

| VCTRL (V) | Actual VCO (GHz) | Raw-Q worst cycle peak (V) | Register-buffer worst cycle peak (V) | Every-cycle physical /2 |
| ---: | ---: | ---: | ---: | --- |
| 0.7729 | 2.032691 | 0.97468 | 1.12564 | PASS |
| 0.8500 | 2.108141 | 0.80949 | 1.10476 | PASS |

At 0.85 V there are **zero** raw-Q 0.972-V rising crossings, but all 42
buffer-output cycles cross that level and preserve division. This validates
the boundary correction; it does **not** qualify operation above the frozen
2-GHz limit or waive weak raw-Q noise margin. The CC-only oscillator is also
faster here than the earlier isolated wire-R+C ring, so do not transfer its
VCTRL setting without measuring actual frequency.

The reporter now separates `physical_receiver` (raw Q) and
`buffered_feedback_clock`, retaining per-cycle swing and VCO edge-count
checks for both. Canonical TT replay076 uses this corrected boundary and
writes `tt_buffered_4us.raw`, with automatic report at
`.amp/in/artifacts/cic-closed-loop-tt-buffered-076/`. It has completed.
Inspection of the actual running deck shows that queue072 had already
captured the earlier direct-Q runner before the buffer correction. Its
result is another diagnostic, not the canonical SS result. Corrected SS
replay079 writes `ss_buffered_4us.raw` and automatically reports at
`.amp/in/artifacts/cic-closed-loop-ss-buffered-079/`; it has completed but
fails the final-microsecond frequency screen (see below).

An additional counterfactual control uses the same 0.85-V clamped analog
assembly and compiled RTL, changing only which physical clock node feeds
the ADC. Both decks explicitly retain the canonical 0.108/0.972-V ADC and
1.08-V DAC settings. Over 60–100 ns, `late_buffered_adc.cir` produces
**527.010 MHz TEST_CLK**, agreeing with the measured 2.108172-GHz VCO
divided by four. `late_raw_adc.cir` produces **zero TEST_CLK edges** although
its physical buffer continues switching. Decks, raw data and
`boundary_counterfactual.json` are under `cic-receiver-buffer-boundary-075`.
The earlier short analog-only controls omitted bridge presets; they establish
physical buffer swing/counting, not functional digital-output behavior.
This counterfactual validates the harness fix, not above-2-GHz qualification.

Synthetic CLI controls077 independently distinguish a weak raw-Q waveform
from a full-swing buffered waveform, and reject a deliberately wrong buffer
division even when both VCO and TEST_CLK frequencies look correct. See
`.amp/in/artifacts/cic-buffer-reporter-controls-077.log`.
No layout or interface is frozen.

### Completed buffered-loop diagnostics and extended SS replay (076–082)

Both 4-µs simulations use the corrected CMOM stack, filled-GDS CC model,
physical receiver/prescaler and physical PFD. The table measures **3–4 µs**,
not an independently demonstrated settled interval:

| Case | TEST_CLK (MHz) | VCO (GHz) | VCTRL range (mVpp) | Continuous feedback-phase drift (ps) | Every-cycle raw-Q swing | Every-cycle buffered swing/count |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| TT / 1.20 V / 27 °C, 076 | 500.094 | 2.000383 | 5.636 | +192.438 | PASS | PASS |
| SS / 1.08 V / 125 °C, 079 | 486.423 | 1.945749 | 132.876 | −27333.896 | FAIL | PASS |

TT passes the existing 1%-frequency diagnostic and all observed /2/swing
screens. It first remains inside the sampled frequency band at 2.5 µs;
the residual control relaxation/phase drift is not fully settled phase-lock
proof. Its simulated deterministic TEST_CLK sidebands are −57.23/−57.31 dBc,
not pad-output spurs or phase noise. SS is still acquiring late: the last
100-period window beginning at 3.5 µs reaches 498.909 MHz, but this does not
override its failing full-window average. The buffered clock continues to
divide correctly through all 972 complete observed cycles. Its raw-Q
minimum cycle peak, 0.957210 V, misses the unchanged 0.972-V screen.

Validation080 reuses the frozen routed digital netlist, nominal SPEF, corner
Liberty and original constraints, changing only VCO period/duty/slew to
the measured 3–4-µs envelopes. Before changing the clock it reproduces the
frozen corner setup/hold metrics within 0.001 ps. Minimum-high and minimum-low
envelopes use the shortest observed period and worst measured 20–80% rise /
80–20% fall time; they are periodic bounds, not arbitrary-waveform signoff.

| Measured waveform | Minimum period (ps) | Worst rise/fall (ps) | Worst setup slack (ps) | Hold slack (ps) | Minimum clock-limit slack (ps) |
| --- | ---: | ---: | ---: | ---: | ---: |
| TT076 | 499.185 | 50.076 / 52.526 | +184.849 | +167.326 | +110.873 |
| SS079, still acquiring | 489.417 | 72.688 / 81.872 | +0.949 | +273.020 | +11.548 |

Electrical limits also pass. SS's positive setup margin is extremely thin;
its 489.417-ps period corresponds to above-2-GHz acquisition activity,
not approved operation beyond the frozen frequency contract. Reports and
replayable `run.tcl`/`input.sdc` files are under
`layout/build/cic-loop-wave-sta-080-tt` and `cic-loop-wave-sta-080-ss`.

Extended SS replay081 uses **7 µs**, without changing the circuit, thresholds
or constraints. It writes `ss_buffered_7us.raw` and automatically reports at
`.amp/in/artifacts/cic-closed-loop-ss-buffered-081/`; its final 6–7-µs
waveform is also checked against the digital timing envelopes in
`layout/build/cic-loop-wave-sta-082-ss`. This replay is pending, not passing.
Replay with the earlier command using `CORNER=ss TEMP_C=125 VDD=1.08`,
`SIM_TIME_S=7e-6`, unused waveform/report paths, and reporter `--vdd 1.08`.
No acquisition-time acceptance deadline was supplied; extending observation
is not a waiver of the failed 4-µs measurement.

Full wire-R extraction remains blocked by the unexposed rhigh body-cap
endpoint; no capacitors were dropped or moved to force a pass. Upstream
Magic's [rsubckt export](https://github.com/RTimothyEdwards/magic/blob/master/ext2spice/ext2spice.c)
and [hierarchical tee export](https://github.com/RTimothyEdwards/magic/blob/master/ext2spice/ext2hier.c)
also distinguish the identifier/body node from the three external pins.
Tee exposes it by replacing the full resistor with half-length model calls,
not by adding a supported midpoint to the unchanged compact model. This
is not an exact translation or an accepted automatic repair. Native CMOM
recognition, full RC, PVT/acquisition coverage, noise/EM/ESD and final numeric
performance budgets remain open. No candidate is tapeout-ready.
