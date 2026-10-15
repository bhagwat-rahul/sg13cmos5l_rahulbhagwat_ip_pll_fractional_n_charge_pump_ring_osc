# PLL digital physical-design experiments

This flow implements `pll_digital` in SG13CMOS5L standard cells, including the
fixed full-rate `/2` as a complementary-output DFF-based toggle. The technology
map connects Q_N to D and initially buffers Q with a buf16. The current flow
removes early buffers and lets CTS build the half-rate distribution tree. It
does **not** import the old TSPC layout or require custom prescaler views.
The 160 x 140 um die is provisional.
The internal `pll_clk`/`feedback_clk` ports are macro-level observation and
hierarchy interfaces, not additional standalone chip clock outputs.

## Current checkpoint

The ten-minute continuation schedule was cleared at the user's request. No
physical-design run remains active. The retained RTL/YAML match
`closure-vcoboundary16-noinv1-slew150-cts25`: eight countdown-control banks, a precomputed
16-bit repeating fractional carry schedule, independent registered pattern
controls, a preserved static configuration-decoder boundary, all `_2` FFs,
a protected `_16` VCO input buffer, no weak `_1` inverters, and 25 um CTS spacing.
The schedule replaces live fractional arithmetic without changing Q7.3 ratios
or feedback pulse sequences. No clocks or uncertainty were relaxed, and no
internal timing exception was added.

| Routed metric | TT | FF | SS |
| --- | ---: | ---: | ---: |
| Setup slack (ns) | +0.185074 | +0.291935 | +0.014717 |
| Hold slack (ns) | +0.165592 | +0.106479 | +0.270211 |
| Minimum clock pulse-width slack (ns), standalone STA | +0.103463 | +0.160193 | +0.008195 |

TNS is zero at every corner. Magic/KLayout DRC, LVS, antenna, capacitance and
slew checks pass, with zero maximum-fanout violations. Cell area excluding fill
is 10928.1 um² (previous threshold implementation: 8159.36 um²).
These runs skip the two intentional asynchronous PFD reset-loop synthesis
checks using the documented waiver below; exit zero is not unconditional sign-off.

The fixed `/2` prescaler is included in GDS as `output_divider_i.div2_ff`,
mapped to `sg13cmos5l_dfrbp_2` with Q_N connected to D. Its local 2 GHz loop
is the worst SS path. Both input and clock transition constraints now budget
150 ps VCO edges; the retained buffer survives timing repair and produces
approximately 34 ps at the SS prescaler clock pin. A nominal loaded-ring probe
near 1.9 GHz measured approximately 103 ps rise / 80 ps fall (20–80%, 20 fF
load); that is not a worst-PVT characterization or the actual integrated load.

Standalone extracted STA checks both pulse width and minimum period at all
three corners, at 150 and 200 ps VCO input slew. All pass for the retained run.
At 200 ps, SS setup is +14.088 ps and minimum clock pulse-width slack is
+4.004 ps. These checks assume the SDC's 50% VCO duty cycle, not a measured
worst-PVT duty cycle or jitter envelope. Qualification logs are
`.amp/in/artifacts/vcobuf16-noinv1-<lib-corner>-qualification.log`.

The YAML now includes `clock_limits.tcl` through LibreLane's native
`STA_EXTRA_CORNER_TCL_FILE` hook: extracted post-PNR STA reports pulse-width and
minimum-period checks and errors on violations instead of silently exiting
green. A negative control rejected the old `_4` routed design's -28.860 ps
pulse-width failure (`.amp/in/artifacts/clock-limits-negative.log`). The fresh
unmodified-YAML run `closure-clocklimits-reproduce` completed through GDS with
exit zero, identical timing/physical check metrics and a byte-identical routed
netlist to the retained experiment. SPEF differs only in its timestamp header.
Each sign-off corner contains the hook's `clock-limits.rpt` with no violations.

Loaded schematic-ring interface probes (20 fF, not extracted analog layout)
show why the 50% duty assumption needs qualification:

| Analog corner | VCTRL (V) | Frequency (GHz) | High duty at VDD/2 (%) | Peak output (V) |
| --- | ---: | ---: | ---: | ---: |
| TT, 1.20 V, 27 C | 0.54 | 1.912 | 50.29 | 1.187 |
| FF, 1.32 V, -40 C | 0.50 | 1.984 | 55.10 | 1.329 |
| SS, 1.08 V, 125 C | 0.60 | 2.155 | 36.79 | 0.794 |
| SS, 1.08 V, 125 C, near-target follow-up | 0.585 | 2.004 | 38.32 | 0.843 |

Logs are `.amp/in/artifacts/vco-duty-{tt,ss,ff}.log`. These are sampled
periods beginning after 4 ns, not settled waveform envelopes. Some original
TT slew measurements are negative because independent threshold crossings
picked different periods; those are invalid and are not used as slew evidence.
The SS VCTRL=0.58/0.585/0.59 follow-up completed (`vco-duty-ss-near2g.log`):
even near the intended 2 GHz frequency, the raw clock duty differs materially
from 50%. The receiver-level follow-up below confirms that the current buffer
does not qualify with this schematic VCO. Do not treat raw VDD/2 crossings as
proof of the buffered clock's width, change the retained SDC to claim closure,
or declare arbitrary analog clock shapes supported without that qualification.

### Transistor-level receiver qualification

The SS probe now includes the schematic ring, PDK transistor models for the
actual buf16/DFRBP2 receiver, its Q_N-to-D feedback, both buf16 clock-tree root
input loads, the 5 fF observation load, and nominal routed RC from
`closure-clocklimits-reproduce`. Unmodeled neighboring coupling is grounded;
this is not analog PEX or a complete extracted PLL simulation. Reset releases
at 1 ns; ring measurements use the 20–30 ns window, with interpolated VDD/2
crossings. All results below are at 1.08 V / 125 C.

| Clock / receiver | VCO frequency (GHz) | FF clock minimum high / low (ps) | Q result |
| --- | ---: | ---: | --- |
| Ideal 50% clock / original buf16 | 2.000 | 259.351 / 240.637 | Correct 1 GHz divide; peak 1.008 V |
| Schematic VCO, VCTRL=0.5825 V / original buf16 | 2.00004 | 211.500 / 288.449 | No Q threshold crossings; peak 0.185 V |
| Schematic VCO, VCTRL=0.585 V / original buf16 | 2.02548 | 205.332 / 288.355 | No Q threshold crossings; peak 0.040 V |
| Same VCTRL / experimental inv2 → inv16 | 2.02777 | 286.452 / 206.667 | Divides, but narrow low pulse is not a sign-off pass |
| Same VCTRL / experimental inv4 → inv16 | 2.02602 | 237.449 / 256.089 | Divides at 1.01301 GHz; peak 0.914 V |

The original receiver fails even at approximately 2 GHz, not only above its
target. Q_N toggling alone is insufficient: Q drives the half-rate domain and
does not toggle in the original schematic-VCO case. Internal-node probes and
the ideal-clock positive control distinguish this from a disconnected Q load.
The smaller-input receiver changes both loading and edge shaping; its improved
waveform is a candidate remedy, not proof of one isolated physical cause or
of a qualified PVT/acquisition envelope.

Probe data/logs are `.amp/in/artifacts/receiver-{ideal-2g,ss-below2g,ss-internals,ss-invchain,ss-inv4chain}.*`;
the threshold/swing summary is `receiver-comparison.txt` there. The inverter
trials reuse baseline routing and omit the new intermediate wire's RC, so they
must be repeated with their own routed parasitics before promotion.

Two full-flow receiver experiments reached GDS and passed DRC/LVS/antenna,
hold, electrical and native clock pulse-width checks, but failed SS setup:
`closure-vco-inv4inv16` at -17.700 ps and
`closure-vco-inv4inv16-noand2` at -33.899 ps. The latter excludes both available
AND2 sizes and is worse. The former's worst path is countdown[1] through a
shared AND2 driving eight reload FFs, rather than the prescaler feedback.
`closure-vco-inv4-localreload` preserves a per-bank reload-control synthesis
boundary. Synchronous formal equivalence passed (563 proven equivalence cells),
and the full run passed physical/hold/electrical/clock-pulse checks, but SS
setup is -31.640 ps. Its worst path now includes a fanout-repair buf4 before
the local select gate. `closure-vco-inv4-localreload-buf8` tests excluding
buf1/buf2/buf4 to reduce that repair stage's delay; it completed through GDS
with clean physical/hold/electrical/clock-pulse checks, but SS setup worsened
to -267.784 ps. It is not retained. Experimental inputs remain
`.amp/in/fraction-local-controls.v` and `.amp/in/standardcell_div2_inv4map.v`;
each run's `resolved.json` captures its overrides.
The retained RTL/mapping/YAML are unchanged by these experiments.

**Not yet integration-ready:** setup and pulse-width margins remain small. Maximum
acquisition frequency/minimum swing, multi-mode timing and the three clock
outputs' endpoint budgets, reset/PFD pulse-width qualification, and extracted
mixed-signal validation remain open.

Recent experiments, with unchanged clock frequencies and uncertainty:

| Run | Result |
| --- | --- |
| `closure-pattern-configdecode` | First all-corner setup/hold pass; SS setup +20.225 ps at 20 ps VCO edges. One clock-tree fanout violation. |
| `closure-configdecode-cts-nocluster` | Identical clock tree and metrics; not retained. |
| `closure-configdecode-cts25` | 25 um spacing removes fanout violation; SS setup +20.632 ps, minimum hold +106.738 ps. Physical/electrical checks clean. |
| `closure-vcobuf4-slew150-cts25` | Buffer inside the FF techmap was renamed during synthesis, missed protection and removed during timing repair. SS setup -36.602 ps. |
| `closure-vcoboundary4-slew150-cts25` | Stable input-buffer RTL boundary fixes preservation. Standard flow setup/hold/physical checks pass, but standalone SS clock high-pulse width fails by 28.860 ps. Superseded. |
| `closure-vcoboundary16-slew150-cts25` | Stronger buffer improves prescaler setup to +15.498 ps, but placement changes expose a half-rate path at -10.562 ps. Not retained. |
| `closure-vcoboundary8-slew150-cts25` | Standard flow passes; setup TT +184.861 ps, FF +291.911 ps, SS +10.989 ps, minimum hold +107.254 ps. Standalone SS low-pulse width fails by 0.881 ps at 150 ps VCO slew. Not retained. |
| `closure-vcoboundary16-noinv1-slew150-cts25` | Stronger inverters repair the half-rate path without losing pulse-width closure. All-corner setup/hold, physical/electrical checks, and standalone clock pulse-width/minimum-period checks pass. Retained. |

## Reproduce

Run inside IIC-OSIC-TOOLS 2026.08 with LibreLane 3.1.0.dev3, from the repo root:

```sh
source .designinit
librelane macros/pll_digital/flow/librelane/config.yaml \
  --pdk "$PDK" --pdk-root "$PDK_ROOT" --manual-pdk \
  --run-tag pll-digital-current \
  --skip Checker.YosysSynthChecks --jobs 4 --condensed
```

Use a new run tag for each experiment. Outputs and reports live under
`macros/pll_digital/flow/librelane/runs/<tag>/`; the canonical streamed GDS is
`final/gds/pll_digital.gds` within that run directory.
These generated runs are Git-ignored and were created locally, not imported.

The current YAML uses the stronger root16 CTS baseline (slow synthesis, DELAY 2,
buffer removal, no early output-port buffering). The SDC now leaves `div_ratio`
unspecialized so the optimizer must time fractional arithmetic and all reload
masks. Only external configuration transitions are false-pathed under the
static-while-enabled protocol; sequential paths are not excluded. This is an
exploratory baseline, not a green sign-off recipe. Earlier history below records
overrides and constraints relative to the config at the time of those experiments.

The earlier slow-corner optimization experiment used the same command with run tag
`complementary-div2-slow-corner` and the additional option
`--override-config DEFAULT_CORNER=nom_slow_1p08V_125C`. Do not include literal
quotes in that override value: this LibreLane version retains them in the
corner name, leaving synthesis without a matching Liberty file.

**Explicit exploratory waiver:** `Checker.YosysSynthChecks` normally stops on
two UP/DOWN-to-asynchronous-reset feedback loops in the dual-DFF PFD. Inspect
`06-yosys-synthesis/reports/pre_synth_chk.rpt` before using the waiver; do not
apply it to unrelated synthesis failures. The YAML keeps the checker enabled.
An exit code of zero with this waiver is not unconditional sign-off.

## Timing assumptions and remaining requirements

- VCO: 2 GHz; half-rate clock: 1 GHz; reference: 100 MHz.
- Libraries: nominal 1.20 V/25 C, slow 1.08 V/125 C, fast 1.32 V/-40 C.
- Earlier runs specialized static N=20 (`div_ratio=160`). Mode probing showed
  much worse setup at other ratios, so implementation now leaves the ratio
  unspecialized. `TEST_DIV=1` and enabled remain the initial output/PFD mode.
  Ratio configuration must be set while disabled and held stable while enabled.
- Generated clocks must attach to the source FF's **Q**, upstream of inserted
  output buffers and net splits. OpenSTA's sequential fan-in startpoints are
  CLK pins: attaching generated clocks there is incorrect.
- Feedback is modeled as an independent 100 MHz PFD clock for the integer
  baseline. Fractional pulse spacing and relative phase need separate checks.
- External reset is asynchronous and false-pathed; its release protocol still
  needs validation. Static configuration must not change while enabled.
- Output loads are 5 fF, not package/pad loads. UP/DOWN have a provisional
  200 ps interface delay budget; clock-output interface budgets remain open.
- CTS is now on. Correct Q-based clock roots eliminate the earlier overlap
  error; disabling early output-port buffering allows CTS to build the 73-sink
  half-rate register tree. `cts-noportbuf` inserted 27 buffers. Remaining setup
  failures and clock/output/reset requirements still need closure.
- Retain the final STA failures; do not lower clock rates or skip setup/hold
  checkers to produce a nominally successful flow.
- Require no unclocked sequential registers in every final STA corner.
  Physical DRC/LVS/antenna, timing margin, PFD minimum pulse/reset behavior,
  post-layout divider functionality and extracted analog/digital loop checks
  must all be assessed before declaring analog integration ready.

## Experiment history

| Run | Outcome / interpretation |
| --- | --- |
| `initial-div2` | Synthesized, but stopped at the PFD's two Yosys loop checks. Mapped cell area: 5595.4962 um². |
| `initial-div2-pfd-waiver` | GDS generated and physical checks passed. **Timing invalid:** 74 registers lost their clock constraints after output buffering. Do not use its slack figures. |
| `initial-div2-clocked` | First source-tracing attempt selected CLK instead of Q. **Timing invalid:** 73 unclocked registers despite flow exit 0. |
| `div2-q-clock-baseline` | Correct Q-based sources and no unclocked registers. Post-route setup slack TT -0.9241 ns, FF -0.4313 ns, SS -1.7145 ns; hold passes, but each corner has one max-cap violation. |
| `complementary-div2` | Complementary FF mapping, no unclocked registers. DRC/LVS/antenna, hold, max-slew and max-cap pass. Post-route setup slack TT +0.1754 ns, FF +0.2922 ns, SS -0.2832 ns. Two SS failures are reload selects into countdown logic. Flow exits 2: not integration-ready. |
| `complementary-div2-slow` | Invalid experiment: quoted corner override caused synthesis to have no matching Liberty. No physical/timing result. |
| `complementary-div2-slow-corner` | Correct slow-corner override; synthesized with slow Liberty, but post-route timing is identical to `complementary-div2`. Setup still fails SS -0.2832 ns. |
| `complementary-div2-delay0` | Slow corner plus `--override-config "SYNTH_STRATEGY=DELAY 0"`. DRC/LVS/antenna, hold, cap and slew pass; no unclocked registers. Setup TT +0.1881 ns, FF +0.2930 ns, SS -0.0686 ns. Best no-CTS result, still fails. |
| `complementary-div2-delay0-cts` | Same overrides plus `RUN_CTS=true`: CTS overlap resolved, but SS setup worsened to -0.1194 ns. No unclocked registers. CTS skipped the buffered high-fanout half-rate net. |
| `complementary-div2-delay0-margin` | Delay0 plus `PL_RESIZER_SETUP_SLACK_MARGIN=0.1` and `GRT_RESIZER_SETUP_SLACK_MARGIN=0.1`: SS setup worsened to -0.1761 ns. |
| `complementary-div2-delay1` | Slow corner plus `--override-config "SYNTH_STRATEGY=DELAY 1"`: SS setup worsened to -0.3054 ns (TT +0.1650 ns, FF +0.2930 ns). |
| `complementary-div2-delay0-density60` | Delay0 plus `PL_TARGET_DENSITY_PCT=60`: SS setup -0.1129 ns, worse than density40; TT +0.1873 ns, FF +0.2925 ns. |
| `complementary-div2-delay0-cts-unbuffer` | Delay0 plus CTS and `DESIGN_REPAIR_REMOVE_BUFFERS=true`: output-port buffers reinserted by design repair still cause CTS to skip half-rate net. SS setup -0.1833 ns. |
| `complementary-div2-delay0-cts-noportbuf` | Same as `cts-unbuffer`, plus `DESIGN_REPAIR_BUFFER_OUTPUT_PORTS=false`. CTS builds half-rate tree (73 register sinks, 27 buffers total). DRC/LVS/antenna/hold/cap/slew pass, no unclocked registers. Setup TT +0.1838 ns, FF +0.2902 ns, SS -0.0683 ns with two SS failures. |
| `complementary-div2-cts-root16` | Noportbuf baseline plus `CTS_ROOT_BUFFER=sg13cmos5l_buf_16`. Physical/hold/cap/slew checks pass, no unclocked registers. N20 setup TT +0.1856 ns, FF +0.2913 ns, SS -0.0417 ns. Retained stronger root. Other modes fail substantially worse (see below). |
| `complementary-div2-cts-root16-margin` | Root16 plus both placement/global-route setup margins 0.1 ns: SS setup worsened to -0.1603 ns. Not retained. |
| `complementary-div2-cts-cluster8` | Root16 plus `CTS_SINK_CLUSTERING_SIZE=8`: timing unchanged, SS -0.0417 ns. Not retained. |
| `complementary-div2-allratios` | Root16 implementation with ratio case-analysis removed; static configuration-pin transitions excluded. Physical/hold/cap/slew pass, no unclocked registers. Setup TT +0.0214 ns, FF +0.2914 ns, SS -0.5538 ns, 69 SS endpoints failing. |
| `complementary-div2-directdecode` | Equivalent RTL decoder replaces subtract-and-variable-shift mask generation with direct equality decoding. All-ratio setup TT +0.0418 ns, FF +0.2916 ns, SS -0.5081 ns; 69 SS failures. Physical/hold/cap/slew pass, no unclocked registers. |
| `complementary-div2-combinedreload` | Direct decoder plus a single active-low base-reload register replacing startup-active OR base-reload control. Setup TT -0.0193 ns (4 failures), FF +0.2894 ns, SS -0.6216 ns (69 failures). Worse than direct decoding alone; combined-reload RTL discarded. |
| `complementary-div2-directdecode-delay3` | Restored direct-decoder-only RTL with `--override-config "SYNTH_STRATEGY=DELAY 3"`, full-ratio constraints. Setup TT +0.0198 ns, FF +0.2923 ns, SS -0.5642 ns (69 failures). DRC/LVS/antenna/hold/cap/slew pass. Worse than DELAY 0; override not retained. |
| `complementary-div2-directdecode-compact` | DELAY 0 with `--override-config "DIE_AREA=0 0 140 120" --override-config PL_TARGET_DENSITY_PCT=60`. Setup TT +0.0388 ns, FF +0.2889 ns, SS -0.5164 ns (70 failures). DRC/LVS/antenna/hold/cap/slew pass. No improvement; original floorplan retained. CLI list overrides require space-separated values, not JSON brackets. |
| `complementary-div2-vectorreload` | Registers the decoded one-hot reload mask on the existing lookahead edge. Setup TT -0.7448 ns, FF -0.1559 ns, SS -1.7717 ns (131 SS failures); DRC/LVS/antenna/hold/cap/slew pass. Fractional carry now drives a large fanout tree before the mask registers. RTL discarded; restored direct-decoder baseline byte-for-byte. |
| `complementary-div2-directdecode-delay2` | Direct-decoder baseline with `--override-config "SYNTH_STRATEGY=DELAY 2"`, full-ratio constraints. Setup TT +0.1014 ns, FF +0.2894 ns, SS -0.4327 ns (68 failures). DRC/LVS/antenna/hold/cap/slew pass; no unclocked registers. Better than DELAY 0, so DELAY 2 retained in YAML. Still not timing-clean. |
| `complementary-div2-grouped16` | Replicates startup/base/plus control FFs for each 16-bit countdown bank, using keep attributes. All twelve distinct control FFs verified in synthesized JSON. Setup TT +0.1089 ns, FF +0.2916 ns, SS -0.3801 ns (73 failures); SS TNS improves to -17.6772 ns. DRC/LVS/antenna/hold/cap/slew pass, no unclocked registers. Retained; worst path now accumulator carry into reload flags. |
| `complementary-div2-grouped16-carrylookahead` | Grouped control baseline with explicit parallel carry generation/OR propagation for the plus-one decision. Setup TT +0.1316 ns, FF +0.2923 ns, SS -0.3630 ns (74 failures); SS TNS -17.8261 ns slightly worse. DRC/LVS/antenna/hold/cap/slew pass; no unclocked registers. Retained for better worst slack, not a claim of timing closure. |
| `complementary-div2-grouped16-cachedsum` | Caches the next fractional sum at initial load/terminal count; reload flags use registered carry. Setup TT +0.0709 ns, FF +0.2927 ns, SS -0.4703 ns (68 failures). Physical/hold/cap/slew pass; no unclocked registers. Worse overall; startup flag sharing with sum initialization is the new worst path. Not retained as best. |
| `complementary-div2-grouped16-cachedsum-localinit` | Separate preserved initialization FF keeps sum seeding off the bank startup control. Setup TT +0.1388 ns, FF +0.2894 ns, SS -0.3656 ns (68 failures), SS TNS -17.8310 ns. DRC/LVS/antenna/hold/cap/slew pass. No worst-slack improvement over carry-lookahead; discarded in favor of its simpler, fully equivalence-checked RTL. |
| `complementary-div2-grouped16-allff2` | Excludes `_1` FFs in synthesis and P&R. Final netlist confirms 83 `dfrbpq_2` plus 4 `dfrbp_2`, no `_1` FFs. Setup TT +0.1079 ns, FF +0.2906 ns, SS -0.3939 ns; SS TNS -18.5397 ns. DRC/LVS/antenna/hold/cap/slew pass; no unclocked registers. Worse setup, so override not retained. Full run took 88 seconds. |
| `complementary-div2-threshold-fused` | Compare accumulator against the configuration-only extended threshold instead of adding for the reload decision; merge startup/base reload into one active-low FF per 16-bit bank. Setup TT +0.1518 ns, FF +0.2903 ns, SS -0.3460 ns (73 failures), SS TNS -14.6574 ns. DRC/LVS/antenna/hold/cap/slew pass, no unclocked registers. Retained, but setup still fails. |
| `complementary-div2-threshold-fused-bank8` | Same rework with eight 8-bit banks. Setup TT +0.1113 ns, FF +0.2923 ns, SS -0.3849 ns, SS TNS -12.3080 ns. DRC/LVS/antenna/hold/cap/slew pass, no unclocked registers. Worse worst-case setup and larger cell area (8738.15 um²), so discarded. |

### All-`_2` comparison

This historical comparison used the pre-rework carry-lookahead RTL. Its
resolved configuration differs from that baseline **only** in
`EXTRA_EXCLUDED_CELLS`. Both synthesis and P&R honor this exclusion; checking the
final netlist confirms that resizing did not reintroduce `_1` flip-flops.
To repeat this cell-strength policy on the current RTL, use the command above
with a new run tag and this extra argument (the numbers below are for the old RTL):

```sh
--override-config "EXTRA_EXCLUDED_CELLS=sg13cmos5l_dfrbpq_1 sg13cmos5l_dfrbp_1 sg13cmos5l_sdfrbpq_1 sg13cmos5l_sdfrbp_1 sg13cmos5l_sdfbbp_1"
```

| Metric | Mixed-strength baseline | All `_2` |
| --- | ---: | ---: |
| Nominal setup worst slack (ns) | +0.1316 | +0.1079 |
| Fast setup worst slack (ns) | +0.2923 | +0.2906 |
| Slow setup worst slack (ns) | -0.3630 | -0.3939 |
| Slow setup total negative slack (ns) | -17.8261 | -18.5397 |
| Minimum hold slack across corners (ns) | +0.1063 | +0.1073 |
| Standard-cell area excluding fill (um²) | 8387.97 | 8569.41 |
| Sequential-cell area (um²) | 4287.43 | 4434.39 |
| Clock-buffer area (um²) | 1012.44 | 1012.44 |
| Nominal STA-estimated total power (mW) | 0.5731 | 0.5830 |

Area rises 2.2% and estimated nominal power 1.7%; worst slow setup worsens
31 ps. Power comes from each corner's `power.rpt`, not the aggregate metric
which reflects the slow corner here. These are default-activity estimates,
not activity-annotated PLL operating power or a supply-noise simulation.
The critical path still traverses accumulator carry/select logic into reload
flags; globally strengthening the FFs did not solve that combinational path.

### Measured iteration time

Five recent completed flows took 83, 86, 87, 88 and 96 seconds from first to
last timestamp in the captured flow logs (median 87 seconds). The all-`_2`
comparison took 88 seconds. Budget about two minutes for a full tool iteration
on this machine/container with the existing four-job invocation, excluding
engineering diagnosis and separate functional/formal verification.

The retained 87-second run's per-step `runtime.txt` files give this rounded
breakdown: lint/synthesis 1–2 seconds; floorplan/PDN/placement 4 seconds;
CTS/timing repair 5 seconds; routing/antenna repair 29 seconds; RC extraction
and timing analyses 3 seconds; GDS/LEF generation 24 seconds; DRC/XOR/LVS and
associated extraction 18 seconds; other checks/overhead about 3 seconds.
This measures execution of the current physical and STA checks, **not** a
successful or complete PLL sign-off. Setup, interface/reset/PFD requirements,
and mixed-signal qualification remain open. Ten-minute scheduled checks were
coarser than the actual physical-run duration.

The current clock coverage check leaves three clock-output ports
(`feedback_clk`, `pll_clk`, `test_clk`) without endpoint delay budgets, and
`reset_n` without an input delay (asynchronous reset is explicitly false-pathed).
No sequential registers are unclocked in `complementary-div2`, but these external
interface and reset assumptions still prevent a fully constrained sign-off claim.

## Functional validation

The retained fractional schedule passed all 992 N=4..127 / fraction=0..7 RTL
cases, and an unbounded synchronous inductive comparison against the previous
threshold/fused implementation succeeded at induction length two. The proof
includes explicit phase/countdown/control invariants, reset and disable, with
configuration stable while enabled. Logs:
`.amp/in/artifacts/fraction-pattern-configdecode-test.log` and
`.amp/in/artifacts/fraction-pattern-configdecode-proof.log`.

Routed netlists for `closure-configdecode-cts25`, `closure-vcoboundary4-slew150-cts25`
and the retained `closure-vcoboundary16-noinv1-slew150-cts25` passed all 992 ratios (16 measured intervals
per ratio), all four output divides, asynchronous reset assertion and disable
using the PDK standard-cell/UDP models. Logs:
`.amp/in/artifacts/closure-cts25-routed-tests.log` and
`.amp/in/artifacts/closure-vcoboundary4-routed-tests.log`, plus
`.amp/in/artifacts/closure-vcoboundary16-noinv1-routed-tests.log`. These are zero-delay,
not SDF simulations; unsupported Icarus edge-sensitive `ifnone` specify warnings
do not qualify timing. Reset release and the internal PFD reset pulse still
need physical qualification. Existing output-divider RTL tests also pass.

An Icarus zero-delay simulation of the **routed** `complementary-div2-delay0`
Verilog netlist with the PDK standard-cell/UDP models passed reset/disable,
all four output divides, and 32 feedback intervals each for Q7.3 ratio codes
32, 33, 39, 40, 47, 160, 161, 167, 168, 175, 1016 and 1023. Checks covered
the requested average ratio and the minimum/maximum even-VCO-cycle intervals.
The log is `.amp/in/artifacts/pll-mapped-functional-smoke.log`; the disposable
bench was removed. This is not SDF simulation, PFD pulse qualification, or
multi-mode static timing closure. Icarus warned about unsupported edge-sensitive
`ifnone` specify paths; timing checks were not enabled for this functional test.

The direct decoder and combined base-reload RTL both passed the existing
992-case fractional-divider test (N4 through N127, all eight fractions), with
identical before/after logs. Yosys `equiv_simple; equiv_induct -seq 4;
equiv_status -assert` proved equivalence to the original RTL after applying
`async2sync` equally to both implementations (220/218 comparison points,
respectively). This checks synchronous functional equivalence, not asynchronous
reset pulse widths or physical timing. Logs: `.amp/in/artifacts/fractional-decode-*.log`
and `.amp/in/artifacts/fractional-combined-*.log`. Scratch sources/executables
were removed; no new permanent regression suite was needed.

The decoded-mask reload experiment passed the same 992-case suite with a
byte-identical log. A separate cycle-by-cycle simulation compared its feedback
output with the direct-decoder baseline for 2048 half-clock cycles per ratio
code, including startup, reset and disable/re-enable. All 992 static ratio codes
matched. Logs: `.amp/in/artifacts/fractional-vectorreload-test.log` and
`.amp/in/artifacts/fractional-vectorreload-compare.log`. Configuration changed
only while disabled, as required; this is simulation evidence, not a formal
equivalence proof or post-layout timing check. Disposable benches were removed.

The four-group control-register experiment passed the existing 992-case suite
with a byte-identical log. Yosys equivalence against the direct-decoder baseline
proved all 213 comparison points after equal `async2sync` normalization and
`equiv_simple; equiv_induct -seq 4; equiv_status -assert`. Synthesis retained
four independent FFs for each of the three controls, rather than merging the
copies. Logs: `.amp/in/artifacts/fractional-grouped-test.log` and
`.amp/in/artifacts/fractional-grouped-equivalence.log`. This does not qualify
asynchronous reset timing or physical timing.

The parallel carry decision also passed the same 992 cases byte-identically
and proved all 288 comparison points against the grouped-control baseline
with the same Yosys equivalence procedure. Logs: `.amp/in/artifacts/fractional-carrylookahead-test.log`
and `.amp/in/artifacts/fractional-carrylookahead-equivalence.log`.

The threshold/fused-startup rework and its eight-bit-bank experiment both passed
the same 992 cases with byte-identical logs to the pre-rework baseline. The
extended threshold covers fraction zero without wrapping it to zero. Yosys
proved all 284 and 276 comparison points, respectively, against the pre-rework
carry-lookahead implementation, with equal `async2sync` normalization and the
same equivalence procedure. Logs: `fractional-threshold-fused-test.log`,
`fractional-threshold-fused-equivalence.log`, and the corresponding
`fractional-threshold-fused-bank8-*.log` under `.amp/in/artifacts/`.
The sixteen-bit version was restored byte-for-byte to the source used by its
completed physical run. This proof is synchronous functional equivalence, not
asynchronous reset-release qualification or extracted mixed-signal validation.

Cached-sum and local-initialization variants both passed the same 992 cases
byte-identically. The first cached-sum variant also matched the carry-lookahead
baseline cycle-for-cycle for 2048 clocks per code across all 992 valid codes,
including startup/reset/disable-re-enable. Logs: `fractional-cachedsum-test.log`,
`fractional-cachedsum-compare.log`, and `fractional-cachedsum-localinit-test.log`
under `.amp/in/artifacts/`.

Automatic internal-point induction for cached sum left `dut.use_plus_one`
unproven (316/317 points proved); keep that failed assertion in
`fractional-cachedsum-equivalence.log`. An independent public-output miter,
without internal equivalence cutpoints, passed a **20-cycle bounded** SAT check
from normalized reset for both cached-sum variants. The harness constrains
configuration to remain stable while enabled and excludes integer ratios below
four. Logs: `fractional-cachedsum-public-bounded.log` and
`fractional-cachedsum-localinit-bounded.log`. These bounded checks and simulations
are not an unbounded equivalence proof or asynchronous reset qualification.
Disposable proof/simulation harnesses and executables were removed.

## Mode probe and STA executable selection

A slow-corner probe of root16 swept all four output selections and the twelve
ratio codes above using the routed netlist/SPEF. Code160 reproduces SS -0.041699 ns.
Codes32/33/39/40/47 give -0.727481 ns; code161 -0.413459 ns; codes167/175
-0.540945 ns; codes1016/1023 -0.551197 ns. Code168 gives -0.041699 ns.
This establishes that N20-only implementation is insufficient. Feedback was
modeled with the mean period (code x 0.0625 ns), so this probe is not fractional
PFD pulse-spacing qualification. Log: `.amp/in/artifacts/pll-root16-mode-probe-bundled.log`.

Use `/foss/tools/openroad-librelane/bin/sta` (OpenSTA 2.7.0) for comparable probes.
The LibreLane wrapper prepends that directory to PATH. Bare `sta` instead selects
`/foss/tools/openroad/bin/sta` (3.1.0); on the same N20 files it reports -0.079526 ns
because of a different endpoint slew/setup calculation. Executable selection,
not changed constraints or corrupted views, explains the discrepancy. Neither
result alone establishes which calculation is physically more accurate; retain
this cross-version difference for sign-off assessment. Summary reports label
some startpoints as `_1` even when `get_property ... ref_name` and the netlist
correctly identify `_2`; do not diagnose cell substitution from that annotation.

## Why the old repo contains `/2-/3` artifacts

The earlier research first implemented a custom dual-modulus TSPC front end,
then moved to fixed `/2` plus half-rate fractional logic. Old files and its
prescaler README retained the earlier names. The final technology map in that
repo instantiates `pll_tspc_div2`, not the dual-modulus cell. Its custom layout
was produced by Magic/PCell and Python geometry generators, not OpenROAD
transistor placement, and it had no completed prescaler Liberty model.

See the [original design thread](https://ampcode.com/threads/T-01a03420-4a07-77c9-9e15-d6dc8440ac45).
The old results are reference evidence, not sign-off for this new implementation.
