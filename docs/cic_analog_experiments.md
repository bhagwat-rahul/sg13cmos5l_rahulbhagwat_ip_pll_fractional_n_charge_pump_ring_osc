# CIC analog-layout experiment plan

## Goal and boundaries

Build reproducible **analog layout recipes**, starting with `vco_bias` and
then `charge_pump`, using installed `cicpy` for explicit grouping, placement,
and directed routing, and Magic's SG13CMOS5L generators for device geometry.
Do not use standard-cell placement or indiscriminate maze routing. Preserve
the circuit, device sizes, six charge-pump ports, and frozen digital macro.
Keep experiments separate from the manual `macros/pll_analog/layout/mag/`
library; do not promote any candidate until its physical and electrical
results have been reviewed.

Noise isolation and robust supplies are design objectives to **measure**, not
properties that follow from a guard-ring checkbox or a clean DRC report.

## Oscillator sizing checkpoint (2026-10-17)

Isolated schematic copies and matching CIC layouts now support drive-strength
experiments without touching the manual schematic/layout or frozen digital.
Both LVS engines compare against the selected schematic copy. Native LVS
also rejects Netgen property errors, rather than trusting the wrapper's exit
code: a deliberately wrong-width reference fails both engines, and matching
variant/baseline controls pass. Replay commands, exact sizes, report paths,
and electrical failures are recorded in `macros/pll_analog/cic/README.md`
under “Isolated oscillator sizing and strict LVS”.

The doubled-buffer024 fixes the named SS/0.5-V slew failure: worst 20–80%
edge time falls from 161.17 to 138.14 ps, with correct receiver counting.
Oscillator supply power rises from 31.60 to 32.94 µW (+4.25%) and frequency
changes −0.84%. GDS-derived extraction independently reproduces this fix.
Its complete six-case SS/FF screen passes four extracted receiver cases;
FF/0.7 and 0.9 V still exceed the unchanged 2-GHz receiver boundary.

Tripling the ring devices alone does not solve target reach: the ring runs
but the buffer loses swing. A balanced stronger first buffer stage restores
correct receiver operation at SS/0.7 V (1.692 GHz, worst edge 75.81 ps).
Its SS/0.9-V point reaches 1.906 GHz with good oscillator swing, but fails
divider-output swing. Pulse width/duty cycle must be checked in addition to
frequency and input slew. These are measured failures, not qualified designs.

The subsequent four-times-core/duty028 candidate has a better near-target
sample at SS/1.08 V/125 °C, VCTRL=0.75 V: **1.977965 GHz**, 67.75/75.39-ps
rise/fall, correct per-cycle division and all current extracted receiver
screens passing. GDS-derived extraction gives **1.978324 GHz (+0.0182%)**,
67.74/75.38 ps and 323.21-µW oscillator supply power, also passing. A fresh
generation directly from the manual schematic reproduces all 14 Magic
files exactly except save timestamps; full sizes/commands are in the README.

This is not tuning/acquisition closure. The adjacent 1.992606-GHz SS sample
still counts correctly but misses the 90%-rail divider-swing screen; FF at
VCTRL=0.6 V already gives 2.825106 GHz, outside the frozen frequency boundary.
The current analog 10%/90% swing screen is stricter than the frozen digital's
legacy 20%/80% Q-swing test; failing the former must not be described as a
counting failure. Neither criterion has been relaxed. Actual-waveform timing
and noise-margin qualification remain open, not just mean-frequency matching.

The new ring candidates pass native local DRC/antenna, strict native and
independent GDS LVS, GDS-reimport local checks, and checked lumped-RC
extraction. Seven unfilled-density categories still fail. No limiter or
coarse-band acquisition controller has been implemented; external rails and
the analog/digital boundary wire remain ideal in screening simulations.
No candidate has been promoted or shown ready for integration/submission.
The full-analog extraction/model, fill, closed-loop, noise/EM/ESD gates below
remain open. The scheduled task remains cleared as requested.

### Duty028 receiver and filled-assembly follow-up (029)

The measured-waveform checker now reproduces all frozen baseline setup/hold
metrics before testing the unchanged full routed digital macro with actual
input slew and minimum-period/high/low periodic envelopes. At SS/0.75 V,
the GDS-extracted 1.978324-GHz point passes counting and the conservative
90%-rail Q screen, with setup +20.022 ps, hold +273.020 ps and minimum
clock-limit margin +5.513 ps. This is a thin pulse margin, not exact-2-GHz
or jitter/noise closure. FF/0.6 V at 2.825106 GHz also passes those diagnostic
checks: exceeding the frozen 2-GHz contract alone is not receiver failure.

The complete 15-point GDS-derived sweep has 11 combined transistor-screen /
timing passes. At high control the failures are real: SS/0.8 V at 2.041196 GHz
has −2.487-ps pulse slack and poor Q swing, and SS/0.9 V at 2.113460 GHz
also misses counts. TT/0.9 V fails setup and Q swing; FF/0.9 V passes STA
but fails the conservative 90%-rail screen. All sampled hold checks pass.
The exact matrix, retained waveforms, limitations and commands are in the
CIC README under “Duty028 receiver timing and full-analog assembly (029)”.
Both matrix commands deliberately return failure; no screen was relaxed.

An additional SS near-target probe at VCTRL 0.766 V produces 2.001205 GHz
and correct counts, with setup/hold/pulse slack +14.245/+273.020/+2.569 ps.
Q peaks at 0.947708 V: it exceeds the legacy 80%-rail criterion but misses
the conservative 90%-rail screen (0.972 V). This does not establish robust
2-GHz receiver margin; pulse/swing improvement or a reviewed noise-margin
budget is still needed. It is explicitly not described as a counting failure.

`cic-analog-duty-feol-029` assembles duty028, CP007 and filter004 with the
existing directed routing and FEOL/metal-fill recipes. Native full DRC and
antenna pass; all installed KLayout DRC/density/antenna/extra decks give zero
markers, and GDS LVS passes. The new lossless 99/40 recognition sidecar and
actual-Magic-reexport polygon XOR close the serialization issue without
changing fabricated geometry. KLayout LVS also passes on that restored
reexport; an intentionally changed metal polygon is rejected. Native CMOM
LVS and the missing rhigh-body PEX endpoint still fail the overall check.
The installed rhigh model does not expose an exact midpoint attachment for
that capacitance, and native selective-flattened ideal caps do not establish
foundry CMOM extraction. No endpoint/model substitution or waiver was added.

The filled candidate is **not electrically qualified or promoted**. Passive
extraction/model support, post-fill closed-loop acquisition/performance,
noise/isolation, EM and pad/ESD review remain integration gates. Frozen
digital, manual schematics/layout and the installed PDK remain unchanged.

### Receiver pulse-balance continuation (030–032)

Separate physical buffer experiments now distinguish output-PMOS strength
(030), first-stage-NMOS strength (031) and their combination (032), preserving
the 028 inverter/bias. All three pass local native/GDS physical, LVS and
checked lumped-RC extraction gates; isolated density remains a failing gate.

**031 improves the near-2-GHz receiver result without changing the digital.**
At SS/1.08 V/125 °C, VCTRL 0.7729 V gives 1.999923 GHz, Q peak 1.015634 V,
setup +14.573 ps, hold +273.020 ps and minimum clock margin +17.180 ps.
All extracted receiver screens, including the frozen frequency limit, pass.
The nearby 028 sample had Q 0.947708 V and only +2.569-ps clock margin.
Oscillator-only power changes 327.50→330.20 µW (+0.82%); the comparison uses
nearby, not identical, frequencies/control voltages. 031 changes only buffer
M2 width 1.5→1.8 µm. Simulated CLK/Q comparison is retained as
`.amp/in/artifacts/receiver-028-vs-031.png`.

The combined 032 variant is rejected: better Q swing conceals a −4.890-ps
opposite-pulse violation near 2 GHz. This is why the measured-waveform timing
gate is mandatory. High-control 031 samples still fail SS/TT setup and Q
swing; FF/0.9 V passes diagnostic timing/counting/swing at 4.763341 GHz but
does not change frozen frequency qualification. All sampled hold checks pass.
No acquisition controller, VCTRL clamp, noise waiver or timing exception was
added; the preferred candidate remains experimental and unpromoted.

The filled full hierarchy `cic-analog-pulse-feol-031` passes installed full
GDS DRC/density/antenna/extra (zero markers), independent GDS LVS and the
physical/recognition round trip. Native CMOM LVS and rhigh-body Magic PEX
still fail. Exact replay commands, reports and controls are in the CIC README
under “Receiver pulse-balance follow-up (030–032)”. Isolated-ring electrical
success is not post-fill full-analog or closed-loop signoff.

### Closed-loop extraction/simulation checkpoint (2026-10-18)

Full-GDS capacitance extraction exposed two model-translation problems:
hierarchical extraction double-counted intrinsic CMOM plate capacitance,
and exported capacitor devices omitted the physical Metal2–Metal4 stack.
Extraction-only flattening with child-text cleanup passes independent strict
LVS and geometry/multiport equivalence checks; explicit stack restoration
matches physical PCell metadata and rejects wrong-stack negative controls.
The earlier uncorrected loop simulations are superseded, not accepted.

The co-simulation runner can now close feedback through the frozen physical
receiver/prescaler and physical PFD, bypassing only the already-realized RTL
/2 in a generated simulation copy. Default schematic regression passes at
500.075 MHz (100-period measurement), 2.25-µs sampled frequency convergence
and 3.263-mVpp control ripple. That is a simulation-harness reference, not
the extracted analog result. Corrected-stack TT/SS runs064/065 finish, but
expose a simulation-boundary error: they digitize raw prescaler Q instead of
the physical register-branch buffer output. Their 500.094/478.735-MHz outputs
are diagnostics, not final acceptance results. In SS, raw Q stops crossing
the ADC high threshold and UP stays high; this is not proof of hardware
feedback failure. Clamped controls075 show correct physical buffer output
counting/swing even where raw Q misses that threshold. Its weak noise margin
and operation above 2 GHz are still unqualified, not waived.

The runner now follows `clkbuf_regs_0_half` using the frozen SPEF mapping,
and records both raw Q and the physical buffered clock. Canonical buffered
TT replay076 and SS replay079 have completed. Inspection of queue072's actual
deck shows it had already captured the old direct-Q boundary; it is another
diagnostic, not the canonical SS replay. A matched clamped counterfactual
with explicit bridge settings confirms 527.010-MHz TEST_CLK through the
buffered boundary versus zero output edges through the old raw-Q boundary.
TT measures 500.094-MHz output / 2.000383-GHz VCO and 5.636-mVpp VCTRL
over 3–4 µs, passing frequency/counting/swing screens but retaining
192.438-ps continuous feedback-phase drift. SS is still acquiring in that
window: 486.423-MHz output, 132.876-mV VCTRL range, failing frequency and
raw-Q swing despite correct buffered-clock division/swing. Its late
100-period sample reaches 498.909 MHz; that does not override the failure.

Measured-waveform periodic timing envelopes080 reproduce frozen baseline
metrics, then pass setup/hold/clock-limit checks at TT
(+184.849/+167.326/+110.873 ps) and SS (+0.949/+273.020/+11.548 ps).
SS's thin setup margin and above-2-GHz acquisition activity are not approved
frequency-contract margin. Extended 7-µs SS replay081 and final-window timing
check082 are pending; no circuit changes or thresholds were used to make the
failed 4-µs result pass. Downstream CTS/logic remain ideal and buffer outputs
unloaded in SPICE, so these runs cannot establish full digital signoff.
Synthetic false-lock/cycle-slip/buffer controls validate the reporter, not
the PLL. The sampled frequency criterion is not phase-lock/noise signoff.

Exact commands, controls and immutable report locations are in the CIC
README sections “Flat-GDS and model-stack correction (045–066)” and
“Completed buffered-loop diagnostics and extended SS replay (076–082)”. Full analog wire-R
extraction, complete PVT/acquisition coverage, noise/EM/ESD and final
electrical acceptance budgets remain open. No candidate is frozen.

## Current closure checkpoint (2026-10-16)

The connected `pll_analog` hierarchy now has reproducible CIC/Magic recipes
for all its leaves and assembly. Historical pilot results below are not the
latest hierarchy status. Exact replay commands, immutable reports and
electrical limitations are in `macros/pll_analog/cic/README.md`.

The conservative current experiment is local-output ring016, with CP route007,
filter004 and buffer010. Its filled analog sidecar is
`layout/build/cic-analog-local-out-feol-016` under `macros/pll_analog/`;
checker report `pll_analog/20261016-152435-395652`.

| Gate | Observed result |
| --- | --- |
| Connected hierarchy / native full DRC / antenna | PASS |
| Exported GDS, all installed DRC/density/antenna/extra decks | PASS, zero markers |
| Independent GDS LVS | PASS |
| Native CMOM LVS / annotated-GDS reimport | FAIL: CMOM recognition and unsupported GDS layer 99/40 |
| Full analog lumped-RC extraction | FAIL: resistor-body C endpoint `a_25244_n17710#` absent from the resistance network |
| Ring016 extracted receiver sweep | 12/15 pass; SS low-control slew and FF high-control frequency failures remain |
| Post-fill closed-loop electrical / noise / EM / ESD | Not qualified |

Ring016 improves sampled loaded TT/SS rail-control frequency by about 6%,
and its nominal finite-control screen slightly improves both control and bias
ripple. Its TT/SS rail-control points are still only 1.571/0.980 GHz: they do
not demonstrate the default 2-GHz lock target. The tighter-row and combined
shielding alternatives were not selected. No schematic sizing, frozen digital
or manual layout was changed; no experiment is promoted or submission-ready.

### Evidence-driven oscillator closure restart

The paired schematic results must not be omitted when interpreting the
12/15 extracted receiver screen. At TT/1.2 V/27 °C, VCTRL=0.7 V, the
schematic output crosses half-supply at 4.142 GHz, versus 1.225 GHz for
ring016. That schematic output is **not full swing**, and the receiver
does not divide it correctly; this is not a passing schematic specification.

A diagnostic retains every extracted MOS instance and its junction geometry,
removes explicit wire capacitance and shorts wire resistance. At the same
operating point it gives 4.158 GHz; the separate C-only extraction gives
1.243 GHz. Thus wire capacitance, not wire resistance or the extracted MOS
geometry alone, dominates this sampled speed loss. These altered netlists
are sensitivity controls, never replacement extraction or signoff results.
Exact commands and completed sweep results are in the CIC README.

An opt-in `--local-interstage` experiment moves just the two adjacent-stage
clock trunks below the upper routing bank, retaining feedback, supplies,
device geometry, guards and placement. Candidate020 improves nominal
VCTRL=0.7-V extracted frequency from 1.225 to 1.326 GHz (+8.26%). It passes
native/GDS local DRC, antenna and LVS, plus checked lumped-RC extraction;
the seven unfilled global-density rules still fail. It is not promoted,
and no 2-GHz tuning or closed-loop qualification follows from this point.

The initial 10-µm inverter-row-pitch experiment (021) failed LVS/PEX with
shorts, despite clean DRC. Relocating the NMOS routing banks fixes those
shorts in leaf022. Ring022 barely improves speed because parent detours
cancel the shorter leaf wiring. Moving the parent clock tracks with the
leaf in ring023 gives the following extracted, receiver-loaded samples:

| VCTRL=0.7 V case | Baseline016 frequency (GHz) | Compact023 frequency (GHz) |
| --- | ---: | ---: |
| TT / 1.20 V / 27 °C | 1.224656 | 1.427489 |
| SS / 1.08 V / 125 °C | 0.828352 | 0.966008 |
| FF / 1.32 V / −40 °C | 1.799754 | 2.099939 |

The approximately 16.6% gain does not close specs: FF now exceeds the frozen
2-GHz limit, and SS rise time is 148.01 ps against 150 ps. Only these three
control/corner points were tested for023, not its maximum tuning frequency
or full control range. Native/GDS local checks pass except seven unfilled
density rules; GDS-derived nominal023 is 1.428617 GHz (+0.0790% versus native)
with all extracted receiver checks passing. The paired schematic still fails.
The nine-case020 sweep passes 7/9 extracted receiver cases, retaining the
SS low-control slew and FF high-control overspeed failures. Nothing is promoted.

The default 18-µm inverter and checked020 ring libraries reproduce exactly
except timestamps. Schematic sizes and frozen digital remain unchanged.
Next closure work should combine a parasitic-aware drive/buffer redesign with
continued core-feedback/load reduction, measuring the full usable tuning range
and acquisition excursions. Keep the frozen 2-GHz/150-ps boundary unchanged;
resolve acquisition overspeed explicitly rather than counting every open-loop
control point as a required lock point. Physical checks do not qualify noise,
EM, ESD or the unresolved full-analog passive extraction/model path below.

### Information and support required to finish signoff

1. **Accepted capacitor extraction/model path.** The installed
   `libs.tech/ngspice/models/cap_cmomf.lib` says “LOW-FREQUENCY MODEL ONLY --
   NOT VALIDATED ON SILICON”, with no substrate, R/L, characterized corner
   or mismatch model. Obtain the MPW/PDK owner's accepted qualification
   route or supported replacement device/model, plus CMOS5L Magic support
   for native recognition and GDS 99/40 import. A clean geometry LVS is
   not acceptance of the electrical model.
2. **Resistor extraction/model interface.** The failing endpoint carries
   0.09359 fF to CP VCTRL and 0.22285 fF to XR1.R2 in the current filled
   report. It is not an omitted drawn wire. Obtain a validated way to
   represent the resistor-body coupling. Neither dropping these capacitors,
   attaching them to arbitrary pins nor substituting two half-length `rhigh`
   calls is accepted; the latter was measured to change the model response.
3. **Final operating/interface contract.** Resolve the documented 0.7–2.1-GHz
   request against the frozen 2-GHz/150-ps receiver assumptions, and specify
   acquisition excursions and CP-usable control range. The default 100-MHz,
   N=20 co-simulation requires 2 GHz; legal RTL ratios alone do not establish
   tuning coverage. Do not relax that target simply to pass a screen.
4. **Physical integration acceptance.** Confirm slot/pad allocation, actual
   supply/bias/clock paths, power-off behavior, protection ownership and the
   applicable EM/ESD criteria. The existing wrapper review below identifies
   requirements, not a finished pad assignment or a protection signoff.

These are unresolved gates, not proposed waivers. Local routing experiments
can improve the layout, but cannot supply missing process qualification or
establish a final MPW acceptance contract.

## Findings from the initial experiments (2026-10-15)

1. A real `cicpy spi2mag ... --techlib ihp-sg13cmos5l --strict
   --check-connectivity` attempt stops at the absent
   `../tech/cic/ihp-sg13cmos5l.tech`. The installed primitive-provider registry
   supplies Sky130 support, not SG13CMOS5L support. Technology rules and a
   device/terminal adapter are prerequisites, not just CLI settings.
2. The installed sidecar API supports explicit device groups and placement/
   routing hooks. Critical nets can be excluded from automatic routing and
   connected by recipe-authored geometry. Do not reuse the Sky130 provider's
   coordinate-based terminal guesses for this PDK.
3. Magic successfully generated guarded NMOS and PMOS devices with labeled
   bulk terminals and requested total widths/finger counts. A controlled
   eight-case sweep used NMOS W=4 µm/L=0.5 µm/ng=4 and PMOS
   W=8 µm/L=0.5 µm/ng=8, `guard=1`, and `full_metal=1`:

   | Gate straps (`conn_gates`) | Automatic source/drain/gate via coverage | NMOS Magic DRC areas | PMOS Magic DRC areas |
   | ---: | ---: | ---: | ---: |
   | 0 | 0% | 8 (M1 minimum area) | 16 (M1 minimum area) |
   | 0 | 100% | 24 (M2 minimum area) | 48 (M2 minimum area) |
   | 1 | 0% | **0** | **0** |
   | 1 | 100% | 54 (M2 spacing) | 94 (M2 spacing) |

   These are **isolated-primitive Magic `drc(full)` results only**. The
   promising option leaves device vias to the routing recipe; it does not
   connect all source/drain fingers, complete the circuit, or establish
   KLayout DRC/LVS/PEX correctness. Test every other actual device size too.
4. Generated multifinger terminals include `D0`, `D2`, etc., `S1`, `S3`,
   etc., repeated `G` labels, and `B`. The adapter must expose all shapes,
   connect each terminal's fingers, and verify connectivity after mirroring;
   one leftmost/rightmost rectangle is not a sufficient pin definition.

The initial probes were run outside the manual layout library. Their geometry
and generation/DRC logs are retained locally in
`.amp/in/artifacts/cic-guard-probe/`; the failed CIC invocation is recorded in
`.amp/in/artifacts/cic-sg13cmos5l-preflight.log`. They are setup experiments,
not completed CIC layouts.

## Isolation structures: use the process we actually have

Source: **SG13CMOS5L Layout Rules, Rev. 0.1, 2025-12-08**, installed as
`$PDKPATH/libs.doc/doc/SG13CMOS5L_os_layout_rules.pdf`. Page references below
are the document's printed pages, not the PDF page index.

- Ordinary NMOS uses the p-type substrate/derived PWell; use contacted
  **p+ substrate guard structures tied to VSS**. Ordinary PMOS sits in
  **NWell**, with **n+ well contacts tied to VDD**. Rings must have real
  contacts, metal connections, and low-impedance supply paths; never float
  the well or assume a drawn well polygon is a contacted guard ring.
- PWell drawing is reserved for internal use (pp. 5, 8). Do not invent a
  customer-drawn pwell ring. `isoNWell` is listed (p. 14), but this manual
  does not provide a complete supported deep-nwell/triple-well device recipe.
  `nBuLay` and `DeepCo` drawing are forbidden (p. 15). Therefore **no
  triple-well/deep-nwell implementation is assumed or authorized by this
  plan**. Any future such option requires explicit CMOS5L process support.
- Enforce NW rules, ordinary analog spacing/enclosures, and LU.a/LU.b:
  maximum 20 µm from the relevant active region to its corresponding well/
  substrate tie (pp. 18, 54–55). This is not simply a 20-µm tap pitch. Avoid
  applying the relaxed digital-boundary rules to the analog block.
- The manual warns that latch-up checking is not enabled by default
  (p. 54). The installed maximal deck currently defaults `latchUpRules` to
  true, and existing full runs report LU rules. Require evidence in each
  experiment's logs that these checks actually ran.
- The manual gives metal/via geometry, not electrical EM current ratings.
  Via redundancy and wide rails help, but cannot establish an EM pass without
  applicable current/lifetime/temperature limits.

Start with a contacted p+ perimeter guard for the charge pump, locally tied
PMOS wells, and separate guard/tap treatment for its switching inverter.
Compare group-level guards with per-device guards; excess guard rings can
increase area, capacitance, and routing distance. A second ring is an
experiment only where its bias, enclosure, and spacing are legal; it is not
an excuse to introduce an undocumented isolation process.

## Charge-pump placement and routing intent

Use explicit groups, not a row of interchangeable P&R cells:

| Group | Devices/nets | Layout intent |
| --- | --- | --- |
| NMOS mirrors | `M_IREF`, `M_PBIAS_SINK`, `M_DOWN_SINK` | Equal W/L (4/0.5 µm): same orientation and local environment, balanced gate/source distribution; compare interdigitation and symmetric/common-centroid unit placement |
| PMOS mirror | `M_PBIAS` (8/0.5 µm), `M_UP_SOURCE` (7/0.5 µm) | Preserve the **8:7 width ratio**, not a fictitious 1:1 match; ratio-aware placement and routing, with any refingering/unitization proven equivalent by LVS and simulation |
| Output switches | `M_UP_SWITCH`, `M_DOWN_SWITCH`, `P_UP`, `N_DOWN` | Close to their current sources and the VCTRL exit; short internal nodes, controlled output parasitics; do not force unlike NMOS/PMOS devices into false geometric symmetry |
| Input switching | `M_UP_INV_P`, `M_UP_INV_N`, `UP`, `DOWN`, `UP_B` | Keep inverter at the digital-facing boundary, away from IREF/PBIAS/VCTRL; short control routes, deliberate return path |
| Bias/control | `IREF`, `PBIAS`, `VCTRL` | Route explicitly; minimize coupling and parasitic imbalance, keep clock routes away, and use quiet-ground shielding only where its added capacitance is acceptable |

Matched devices should share compatible well-edge, tap, dummy, and filler
environments. Added dummy devices need defined electrical connections and
must not silently alter the schematic/LVS reference. A guard structure must
not split a matched array into systematically different environments.

Feed the charge-pump current-source core, its switching inverter, VCO, and
digital block with **separate local VDD/VSS branches** from the intended
top-level connection. Do not daisy-chain sensitive bias/source connections
through the inverter or digital return. These remain the existing VDD/VSS
nets, not new isolated grounds or extra package pins. Size and evaluate the
common path too: a local ring does not remove shared pad/package impedance.

## Ordered experiments and gates

Change one axis at a time; keep only a small set of electrically verified
finalists before combining options. All candidates need explicit seeds/
parameters, input/tool/PDK versions, source hashes, and repeatable commands.

| Experiment | Question and variants | Measurements / gate before proceeding |
| --- | --- | --- |
| E0: technology and primitive adapter | Map SG13CMOS5L grid, layers, contacts/vias, widths, spacings, and unit scales. Generate every required MOS size, with the guarded/no-automatic-via option as an initial candidate. Register a project-local provider rather than patching installed site-packages. | Round-trip `.mag` dimensions, W/L/total width, multiplicity/fingers, all D/G/S/B shapes, mirrored-port behavior; native and KLayout geometry checks; primitive extraction. No missing geometry or guessed terminal identities. Record unavoidable chip-level density findings separately, without waiving them. |
| E1: `vco_bias` pilot | Hand-authored CIC placement/routing of two devices, contacted wells/substrate, explicit VDD/VSS straps and real circuit ports. | Both LVS engines must compare the intended circuit; routing has no opens/shorts; full-RC extraction completes; DC VBP/branch current versus schematic over PVT. Resolve core geometry rules before scaling up. |
| E2: charge-pump analog baseline | Explicit functional groups and quiet/switching supply branches. Start with simple matching-aware placement and legal local ties/guards. No unconstrained autorouting of bias/output/supply nets. | Both LVS engines, full DRC/antenna including latch-up, robust PEX; DC up/down currents and compliance versus VCTRL, off leakage, simultaneous-UP/DOWN residual current. Establish the comparison reference, including parasitic imbalance. |
| E3: matching arrangements | Baseline same-orientation versus interdigitated/symmetric NMOS mirror groups; ratio-aware PMOS alternatives. Preserve total W/L and connections. | Compare mismatch across VCTRL and PVT, routed gate/source resistance, parasitic load, temperature/gradient sensitivity, output glitch charge. Common centroid is not automatically best if it lengthens sensitive routes. Random mismatch requires validated mismatch models; deterministic PEX is not a Monte Carlo model. |
| E4: guard/isolation variants | Group guards versus per-device guards; separate inverter guard; legal setback sweeps (initial candidates 5/10/20 µm additional separation, not substitutions for PDK minima). Keep routing/supply choices otherwise fixed. | Verify actual ring bias/continuity, contacts and tap distances; compare well capacitance, core area, coupling and output disturbance. Shared ideal substrate in PEX cannot quantify real substrate attenuation. |
| E5: PDN variants | Sweep legal local strap widths (initial 2/4/8 µm on appropriate upper metals), redundant 2×2/3×3 via arrays where legal, and single versus distributed feeds. Compare group return routing without changing circuit nets. | Extract supply resistance; DC voltage drop, pulsed ground bounce, well-contact drop, branch current and supply-to-VCTRL sensitivity. Initial **screening** goal: ≤1 mV local DC drop under sustained worst-case CP activity; derive the final budget from current/spur sensitivity. Check EM only when applicable current limits are available. |
| E6: sensitive routing/shielding | Compare shortest direct VCTRL/IREF/PBIAS routes with legal quiet-VSS shielding; compare additional control/output separation. No UP/DOWN/clock route over mirror cores or loop-filter sensitive routing. | Coupling C, output-node total C, UP/DOWN skew at switch gates, rise/fall glitch charge and VCTRL ripple. Added shield capacitance must not silently change loop behavior. |
| E7: integrate analog hierarchy | Carry the winning intent into inverter/bias/buffer/ring/filter recipes, then assemble the analog macro beside the frozen digital macro. | Full checks per block and assembled top; regenerated closed-loop PEX simulation, lock/acquisition and frequency range, reference spurs, supply sensitivity, digital activity controls. Top-level fill, boundaries, antenna, supply path and package assumptions must be revisited. |

For continuous metrics, save the baseline, candidate result, absolute change,
and relative change; do not call a layout improvement solely because it is
smaller. Establish post-layout budgets from the current schematic baseline
and system requirements rather than borrowing the textbook's process-specific
device sizes or numerical performance targets.

## Electrical experiment matrix

- Refresh the schematic baseline and port order first. The older import
  netlists and current Xschem exports order subcircuit ports differently;
  the existing charge-pump characterization script contains a positional
  instance call and must be checked/rebound before reuse. Do not compare a
  correctly wired PEX circuit against an accidentally miswired baseline.
- Reuse the existing characterization ranges initially: TT/SS/FF/SF/FS,
  VDD=1.08/1.20/1.32 V, T=−40/27/125 °C, VCTRL=0.50–0.90 V, IREF=2 µA.
  Establish whether that VCTRL interval covers the actual PLL lock range;
  widen the compliance sweep as required. Prune to nominal/corner smoke tests
  early, then run the full matrix on finalists.
- Exercise UP only, DOWN only, both off, and both on; sweep pulse widths,
  relative skew, and edge rates representative of the real PFD and routed
  interface. Integrate delivered current to measure charge error and
  distinguish positive/negative edge disturbances.
- Inject sinusoidal ripple and transient current loads separately into the
  CP supply, its ground/common return, the inverter branch, and the digital
  aggressor supply path. Include the reference frequency, harmonics, and
  frequencies near the loop bandwidth. Use measured or explicitly assumed
  package/common-path R/L. Sweep aggressor activity as a control.
- Run both open-loop CP measurements (clamped VCTRL) and the closed-loop
  PLL/loop-filter response; a clamp alone hides the resulting VCTRL ripple.
- Do not present conventional interconnect PEX as a substrate-noise solver.
  The process manual's DigiSub extraction assumption can short substrate
  contacts together (p. 58). Quantitative isolation claims need a supported
  substrate RC/extraction model or clearly labeled sensitivity experiments
  with a parameterized coupling network. Likewise, ordinary deterministic
  `.tran` and `.noise` do not by themselves measure cyclostationary PLL jitter.

## Verification and deliverables

Keep experiment recipes and SG13CMOS5L adapter/rules under a separate CIC
experiment subtree, with generated layouts and reports in ignored build
directories. Extend the existing check runner to accept a candidate layout
library when that subtree is implemented; **do not copy experiments over the
manual library merely to invoke checks**. Keep the candidate layout source
and fresh schematic references tied to the same run manifest.

Each finalist should deliver its recipe, generated hierarchical `.mag`
library, pin/guard/PDN diagram, full per-block/top reports, electrical CSVs,
comparison plots, and open limitations. A density failure on a bare primitive
is neither a reason to add random filler to a matched core nor permission
to claim a full-rule pass. Design fill placement deliberately and rerun at
the assembled macro and final-chip contexts. Inspect rendered layouts as
well as extraction/connectivity reports before promotion.

## Textbook grounding

Behzad Razavi, *Design of CMOS Phase-Locked Loops* (2020), supplied PDF:

- §8.3.3–8.3.4, printed pp. 254–255 (PDF pp. 269–270): current mismatch
  produces phase offset/ripple; larger devices trade mismatch against
  capacitance, feedthrough, and charge injection. This motivates measuring
  switching charge, not only DC matching.
- §8.10.3, printed pp. 269–270: CP noise is periodically switched and shaped
  by the loop; do not equate a static noise plot with complete PLL jitter.
- §8.10.5 and Example 8.17, printed p. 274 (PDF p. 289): CP/divider shared
  supply bounce modulates pump currents and creates sidebands. This directly
  motivates separate local feeds/returns and common-impedance experiments.
- §9.3.1 and §9.3.5, printed pp. 278–281 and 283: check compliance and
  current error over output voltage/PVT, plus current-pulse settling and
  interface alignment. These are measurement techniques, not authorization
  to transplant a different process's circuit or sizing.

The guard-ring implementation is grounded in the CMOS5L PDK manual, not
attributed to a textbook recipe that the cited PLL sections do not supply.

## First implementation results

Recipes and replay instructions: `macros/pll_analog/cic/README.md`.
The installed CIC package and manual Magic library were not modified.

| Candidate | Magic DRC areas | Full KLayout markers | Magic / KLayout LVS | Other observations |
| --- | ---: | ---: | --- | --- |
| Bias E0, default guard clearance, unrouted | 4 | Not run | Not run | Minimum-size D/S landings fail M1 area |
| Bias E1, directed routes and enlarged guard clearance | 52 | 11 | Pass / fail | Incorrect Magic via-tile size and notches between guard-via landings |
| Bias E1b, corrected vias and continuous guard landing | **0** | **7** | **Pass / pass** | Magic antenna: 0 markers; PEX: 29 resistors, 19 capacitors |
| CP E0b, all nine devices, primitive-access sweep only | 10 | 17 | Not run | Ten M1-area markers plus seven density markers; no CP routing yet |

Bias E1b's seven remaining full-deck markers are **AFil.g, GFil.g,
M1.j, M2.j, M3.j, M4.j, TM1.c** (one each). These global density findings
are retained as failures, not waived or called a signoff pass. Local geometry
and LVS closure demonstrate the adapter/pilot, not a complete analog macro.
The recipe's 2-µm guard offsets are experimental generator overrides, not
process-rule minima. Bias routes are deliberately simple 0.4-µm M2 branches;
they are not the proposed final charge-pump PDN.

Three DC sweeps compare fresh schematic and extracted bias cells, binding
ports by name rather than assuming their order. VCTRL spans 0.1 V to
VDD−0.1 V in 10-mV steps:

| Corner | VDD (V) | Temperature (°C) | Points | Maximum absolute VBP difference (mV) |
| --- | ---: | ---: | ---: | ---: |
| TT | 1.20 | 27 | 101 | 1.008 |
| SS | 1.08 | 125 | 89 | 0.491 |
| FF | 1.32 | −40 | 113 | 1.836 |

This is initial DC screening only, not a PVT/transient/noise qualification.
Local reports are under `layout/build/vco_bias/20261015-091156-160667/`,
CP reports under `layout/build/charge_pump/20261015-091220-435661/`, and DC
data under `layout/build/cic-bias-dc-e1b/` (paths relative to the analog macro).
These are historical initial probes; the following checkpoint supersedes
their CP routing and PEX status.

## Routed charge-pump checkpoint (2026-10-15)

The actual nine-device pump is now routed with explicit CIC recipes, rather
than a primitive-access sweep. Important iterations:

- Recover the native multifinger generator's unlabeled final diffusion;
  connect every finger and verify through both LVS engines.
- Preserve the intended PMOS 8:7 total-width ratio. Eight native fingers
  round the 7-µm source to 7.04 µm; seven 1-µm fingers pass strict LVS without
  changing total width. This physical refingering is recorded explicitly.
- Remove undersized unused bottom gate contacts, retaining top gate straps.
- Keep P_UP/N_DOWN and UP_B local, reduce row pitch 50→40 µm, place the
  VCTRL bridge beside the switches, and stop unnecessary global wire tails.
- Widen long supply drops to 0.8 µm with narrow device-access transitions;
  keep separate quiet/switching branches feeding common 2-µm supply spines.
  A direct widening attempt failed spacing beside inverter diffusion vias;
  tapering below the landings restored local DRC closure.

Route-007 (`layout/build/cic-cp-route-007/`) passes Magic full DRC, Magic
antenna, Magic/Netgen LVS, and KLayout LVS. Full KLayout still fails exactly
the seven global-density categories listed above. No rule has been waived.
The layout has per-device contacted guards and same-orientation mirror groups,
not a common-centroid arrangement or a verified group-level isolation ring.

### Electrical feedback exposed an extraction bug before promotion

The first transient results were not trustworthy. An exact capacitance-ledger
audit found that Magic 8.3.681's hierarchical SPICE exporter applies resistor-π
capacitance redistribution to MOS subcircuits. Separately, extresist distributes
coupling-derived grounded copies while retaining explicit coupling. These
effects were verified against the actual `.ext`, `.res.ext`, and SPICE files,
not inferred solely from unexpected waveforms.

The checker now disables hierarchical export after `ext2spice lvs`, preserves
the raw resistance export, and uses the independent flat C-only matrix at
original named nodes together with the full resistance network. This is a
**lumped coupled-C approximation**, not a spatially distributed coupled-RC
solver or foundry-qualified extraction. Missing/shorted C endpoints fail.
Thirty matrix entries independently match the raw `.ext` within 1 aF export
rounding. Corrected C-only/RC nominal charge agrees within 0.03%.

Both old and new layouts were rerun with the corrected model:

| Nominal first 4-ns pulse | Schematic (fC) | Route-003 (fC) | Route-007 (fC) |
| --- | ---: | ---: | ---: |
| UP | +15.586 | +23.091 | +17.493 |
| DOWN | −14.727 | −24.716 | −17.351 |

Thus shortening routes helps with a consistent extraction model, but
route-007's residual ≈12–18% pulse-charge change is **not approved** as a
PLL performance budget. The extracted-device-only control also differs from
the schematic (first UP +16.076 fC, DOWN −15.735 fC), so not every change is
removable by routing. Do not resize circuitry merely to cancel an export bug.

The 45-point PVT matrix covers five MOS corners, three supplies and three
temperatures, four control states, and compliance sweeps. Over VCTRL
0.5–0.9 V with IREF 2 µA, worst DC change is UP 2.31%, DOWN 0.053%.
With both inputs on, worst local DC deviation is VDD 0.0564 mV and VSS
0.0739 mV, below the initial 1-mV local-DC screening objective. Nominal pulse
peaks are VDD 2.17 mV/VSS 2.75 mV. These use ideal external supplies: package
and substrate coupling are not included, and no EM/ESD conclusion follows.

Current replay commands and exact report locations are in
`macros/pll_analog/cic/README.md`. Historical electrical directories without
`-conserved` are superseded. Bias DC was rerun with the corrected extraction
and retains the initial values above. Frozen digital and manual Magic sources
remain untouched. Next gates are actual PFD pulse/edge/skew and closed-loop
performance, matching/isolation/fill treatment, then the remaining leaf
recipes and assembled analog hierarchy. **The full analog macro is not done.**

## ESD is an integration gate, not a guard-ring property

Read-only wrapper inspection found primary pad clamps and a separate
secondary-protection branch. In sibling
`sg13cmos5l_ocd_chipalooza/netlist/schematic/sg13cmos5l_io.spice`,
`sg13cmos5l_IOPadAnalog` (lines 495–500) connects primary protection to
IOVDD/IOVSS and its `padres` branch through `SecondaryProtection`.
That secondary circuit (lines 224–227) contains a 2-µm/1-µm rppd series
resistor and steering diodes to the **I/O rails**, not the 1.2-V core rail.
`verilog/rtl/slot13_wrapper.v` exposes distinct direct and `_esd` terminals;
the PLL's final slot/pad assignment is not established.

| Interface / exposure | Required treatment before integration |
| --- | --- |
| IREF, if externally supplied | Establish the exact pad/bias-bus path. Verify protection compatible with the 1.2-V MOS gate/drain, leakage relative to the 2-µA bias, compliance, added capacitance, and rail-off/back-power behavior. A 3.3-V steering diode alone is insufficient evidence. |
| VCTRL, VBP, PBIAS internal nets | Do not add pad ESD clamps to internal loop/bias nodes. Revisit if any is deliberately exposed externally. Antenna protection is a different check. |
| Reference clock, output clock, controls | Map actual digital pad cells/level interfaces and their rails. Verify the core does not see pad-voltage stress and that the selected output path preserves protection. |
| Gated VDD/VSS and I/O rails | Identify discharge paths in powered, unpowered, and power-gated states. Ensure clamps remain reachable, with adequate metal/vias and no sensitive-core routing carrying the main ESD discharge. |
| Dedicated analog direct / `_esd` branches | Select the intended branch; **do not short the direct and protected terminals together**, bypassing the secondary series resistor. Shared analog-bus secondary protection must be checked separately. |

Do not implement an improvised MOS clamp or infer HBM/CDM qualification from
an ESD-cell filename. Local clamps, if required after pin mapping, need a
process-supported protection/trigger/clamp-voltage design and appropriate
stress/current-path review. DRC/LVS and ordinary SPICE do not prove ESD
survival. **ESD is not yet signed off; no ESD devices or circuit changes have
been added to the pilot.** Guard rings improve local tie/isolation structure
but are not substitutes for pad/rail protection.
