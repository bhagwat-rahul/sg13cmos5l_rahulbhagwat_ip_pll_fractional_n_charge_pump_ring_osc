# Provisional integrated PLL core

`pll_core` instantiates the maintained `pll_analog` and frozen
`macros/pll_digital/frozen/v1` (including its fixed /2 prescaler). It is **not
the MPW pad wrapper, an analog freeze, or tapeout approval**. The assembly
contract is `schematic/pll_core.spice`; its child declarations specify port
order only. LVS replaces them with full source-derived circuits, not layout
netlists or macro black boxes.

## Maintained provisional checkpoint

The editable, unfilled core is now `core/mag/pll_core.mag`; see
[`core/README.md`](core/README.md) for opening, regeneration and check commands.
Its 27 analog entries link to the maintained macro sources, and the readonly
digital backing stream links to frozen v1. No analog or digital source geometry
was changed during promotion. `core/manifest.json` records provenance and hashes.
The maintained top is now the compact unfilled024 assembly, promoted after
filled031 matched the older larger009 checkpoint's physical-check level.
Core-level density fill remains separate. This checkpoint is not the filled009
extraction input or a final pad wrapper.

## Slot13 compact candidate

`scripts/pll/fit_slot13.py` packs the existing guarded charge pump, loop
filter and oscillator directly alongside frozen digital (including /2),
without keeping the mostly empty analog enclosing rectangle. It changes
placement and inter-block routing, not device sizing or macro interiors.
The older larger008/009 build directories remain available for comparison.

Run from the repository root inside IIC-OSIC-TOOLS, with the sibling harness
checkout present (its `magic/slot13_wrapper.mag` supplies the actual boundary):

```sh
unset PYTHONPATH
/opt/ciccreator/.venv/bin/python scripts/pll/fit_slot13.py \
  --output layout/build/pll-slot13-next
python3 scripts/pll/check_integration.py layout/build/pll-slot13-next --mode lvs
python3 scripts/pll/check_integration.py layout/build/pll-slot13-next --mode drc-all
python3 scripts/pll/check_integration.py layout/build/pll-slot13-next --mode antenna
```

Use a new output directory. The generator verifies the frozen package and
records source hashes, group placements and the envelope in `manifest.json`.
It rejects an envelope outside the verified 537.15 × 273 µm slot boundary
or exceeding 70% of that boundary's area.

Candidate `build/pll-slot13-020/mag/pll_core.mag` has a streamed envelope
of **483.2 × 210 µm**, from (7, 15) to (490.2, 225) µm: **69.197% of
slot area**, including inter-block routing and supply rails, not a cell
utilization figure. It retains 10-µm TopMetal1 VDD/VSS rails, separate macro
branches and all three digital straps per supply. Existing local guards and
taps remain intact; there is no new core-level density fill.

Fresh Netgen source/model-view LVS and independent GDS/KLayout LVS with
CMOM dimension checks both pass (`checks/pll_core/20261021-125234-672255`).
Magic DRC passes with zero error areas. Full KLayout DRC **fails only on
seven density markers**, AFil.g, GFil.g, M1.j, M2.j, M3.j, M4.j and TM1.c
(`checks/pll_core/20261021-125243-252862`); it is not a full-DRC-clean result.
Magic and GDS/KLayout antenna checks both pass with zero markers
(`checks/pll_core/20261021-125554-352860`).
Independent polygon XOR confirms that all four protected macro geometries
are unchanged, and a 5-µm planning halo around existing wrapper metal has
no overlap. This is not a substitute for actual wrapper routing and DRC.

This is a packing candidate, not a final `slot_13` wrapper or electrical
freeze. Pad routes, dedicated clock input/output pads, final density,
PDN current capacity/IR/EM, ESD paths and post-route electrical qualification
remain. Full-core KPEX and electrical qualification remain deferred; the
Magic PEX screen below was rerun, not waived.

### Complete checker and fill follow-up

Candidate `build/pll-slot13-021` regenerates the same geometry with promotion-safe
provenance: its assembled top is an output, not a hashed input. Its GDS has
empty polygon XOR against 020 on all 31 layer/purpose pairs, and fresh
Netgen/KLayout LVS pass (`checks/pll_core/20261021-131151-347181`). Only
`pll_core.mag` differs from the maintained library; analog links, digital
cells and readonly backing stream remain unchanged.

The full `--mode all` run on unfilled020 is recorded at
`build/pll-slot13-020/checks/pll_core/20261021-130954-493238`.
A complete run on compact fill022 is at
`build/pll-slot13-021/checks/pll_core/20261021-131211-943389`.
Both pass source/model-view LVS, independent GDS LVS/CMOM dimensions,
Magic DRC/antenna and readonly-GDS physical/recognition round-trip XOR.
Freshly reimported GDS also passes KLayout LVS, Magic DRC and Magic antenna.
Native-Magic reimport LVS loses the two CMOM devices, as in the larger core;
that diagnostic remains visible, non-required by the existing core policy.

**Neither overall run passes.** Magic PEX rejects 2,797 original capacitance
endpoints absent from its distributed-resistance output, in both the source
and GDS-roundtrip views. No capacitance was dropped or nodes shorted to
clear this gate. This reproduces the earlier extraction limitation, not
accepted full RC. The roundtrip aggregate fails its required PEX check too.

The original fill recipe now accepts the compact four-block hierarchy while
retaining 10-µm block, 2-µm routing and 3.05-µm TopMetal1 routing keepouts.
Fill022 inside the compact envelope still fails all seven global density
rules. An expanded-slot fill trial023, bounded by (6, 6)–(531.15, 267) µm
to leave a 6-µm slot-edge margin, passes Magic DRC but still fails only those
same seven global-density rules. Its report is
`build/pll-slot13-021/checks/pll_core/20261021-131735-386821`.
Measured active/poly density is 27.581%/11.823% (minimum 35%/15%),
Metal1–4 is 26.862%–28.492% (minimum 35%), and TopMetal1 is 23.635%
(minimum 25%). No isolation keepout was reduced to manufacture a pass.
This expanded **fill view** is larger than the 69.197% functional-core
envelope; it is not the new maintained core or a routed slot wrapper.

To reproduce fill023 from the unfilled021 LVS snapshot:

```sh
python3 macros/pll_analog/cic/metal_fill.py --cell pll_core --feol \
  --bounds-um 6 6 531.15 267 \
  --report layout/build/pll-slot13-021/checks/pll_core/20261021-131151-347181 \
  --output layout/build/pll-slot13-fill-next
```

The optional fill boundary must enclose the existing core and lie on the
native grid; clipped/off-grid negative controls reject without writing output.
Actual wrapper geometry, signal access and final fill exclusions must be
included before full-chip closure; the 6-µm margin alone is not that check.
The top/padframe repository owns the external pad cells, with small access
shapes at the slot edge. Pad-cell bodies do not consume the core's 70% area
budget; core-to-slot wiring and pad-type compatibility remain necessary.

### Density closure and compact promotion (024/031)

The trials above are historical. Filled031 fixes all seven density failures
without changing the functional core's **483.2 × 210 µm / 69.197%** envelope,
macro interiors or signal routing. The opt-in routing-aware fill recipe audits
top metal against the CIC manifest before allowing cross-layer fill beneath
supply routing. CP, oscillator and digital keep their full 10-µm block halos;
the filter protects each passive device by 10 µm and its wiring across layers.
Non-supply routes retain cross-layer exclusions. Smaller residual metal tiles
and legal TopMetal1 rectangle growth recover otherwise unusable whitespace.
Same-layer clearances remain 2 µm, or 3.05 µm for TopMetal1.

```sh
python3 macros/pll_analog/cic/metal_fill.py --cell pll_core --feol \
  --routing-manifest layout/build/pll-slot13-024/manifest.json \
  --bounds-um 6 6 531.15 267 \
  --report layout/build/pll-slot13-024/checks/pll_core/20261021-134203-443870 \
  --output layout/build/pll-slot13-fill-next
python3 scripts/pll/check_integration.py layout/build/pll-slot13-024 \
  --library layout/build/pll-slot13-fill-next --mode all
```

The allocated **fill** envelope occupies about 93.5% of slot13, not 69.197%:
it uses existing slot whitespace without growing the functional layout.
Active/poly density is 35.167%/15.649%; Metal1–4 is 35.871%–37.501%;
TopMetal1 is 26.635%. Active-density margin is thin; assembled-die density
must be checked again, not inferred from this isolated-core result.

Complete report: `build/pll-slot13-024/checks/pll_core/20261021-135108-071462/`.
Full installed KLayout DRC (density/extra/antenna included) passes with zero
markers. Source Netgen and independent GDS KLayout LVS/CMOM dimensions,
Magic DRC/antenna, frozen-digital preservation and GDS round-trip geometry
checks pass. Independent all-layer XOR verifies all four macros are unchanged;
top routing is unchanged, with only the declared fill boundary enlarged.
Evidence: `.amp/in/artifacts/pll-slot13-fill-031-audit.json`.
**Overall `all` still fails required Magic PEX** on 2,797 missing original C
endpoints, including round-trip PEX, as at the larger checkpoint. Native-Magic
reimport LVS retains the known diagnostic two-CMOM recognition failure.

The compact **unfilled024** top is now applied to `core/mag/pll_core.mag`,
with updated provenance; `make pll-core` regenerates using `fit_slot13.py`.
Fill remains separate and the harness repository is unchanged. There is no
accepted new compact-core full RC or post-fill electrical qualification.

The fill output also contains `fill_keepouts.gds`, using the harness's
FILLBLOCK (160/0) and DIFFBLOCK (1/23) metadata purposes at core origin.
Preserve its placement transform when consuming it in harness fill generation;
it is exclusion metadata, not submission paint. Its actual harness-tech
Magic import/reexport passed an empty XOR on both purposes. Final wrapper
routing/access and assembled-die DRC/LVS/density remain required.

## Generate and check

From the repository root **inside IIC-OSIC-TOOLS**:

```sh
make pll-core CANDIDATE=layout/build/pll-core-next
make pll-core-check CANDIDATE=layout/build/pll-core-next
# Targeted iteration:
make pll-core-check CANDIDATE=layout/build/pll-core-next MODE=lvs
make pll-core-check CANDIDATE=layout/build/pll-core-next MODE=drc-all
```

Use a new, empty candidate directory. Generation verifies the frozen package
hashes and records maintained analog/source hashes. It imports actual digital
GDS in readonly, non-flattening mode and creates numbered Magic ports from
its LEF access shapes. Keep all imported `GDS_FILE/START/END` properties:
streamout must preserve the hard macro, not regenerate its implants from
Magic paint. No source macro is edited. Each check snapshots the complete
Magic library, readonly backing streams and analog schematics, then saves
logs and `summary.json` under the candidate's
`checks/pll_core/TIMESTAMP/`. Nonzero exit means at least one gate failed;
absence of a summary means the run did not finish normally.

LVS freshly exports analog SPICE/CDL, converts the frozen **powered** Verilog
using Yosys and PDK standard-cell pin order, and includes full PDK cell
circuits. Both Netgen and independent GDS/KLayout comparison are required.
The installed primitive-device model conventions still apply. The checker
audits CMOM dimensions in addition to KLayout's topology comparison. Every
core GDS export also requires an empty polygon XOR against the frozen
digital macro on every layer; see `digital_geometry.json`.

## Routing and supply intent

- Analog left; digital right; buffered VCO uses the short M3/M4 channel.
- UP/DOWN use separate TopMetal1 routes. No generic cell autorouter.
- VDD/VSS use 10-µm TopMetal1 entry rails, separate macro branches and three
  TopVia1 cuts per branch. All three digital LEF straps per supply connect.
- Reference/reset/enable access locally from the inter-macro channel.
  Configuration pins exit just above digital, rather than adding long
  unprotected input antennas. Pad-level extensions require fresh antenna
  checks and load/timing qualification.
- Only `clk_out` is external. Digital `pll_clk` and `feedback_clk` remain
  internally connected observation nodes, without added top routing/load.

Existing analog guards/taps are retained. These routing choices do **not**
prove PDN current capacity, IR drop, EM, substrate isolation or ESD safety.

## Separate density-filled experiment

Keep the unfilled layout editable. Generate a separate filled Magic library
from an immutable checker snapshot; never fill over either source macro:

```sh
python3 macros/pll_analog/cic/metal_fill.py --cell pll_core --feol \
  --report layout/build/pll-core-next/checks/pll_core/TIMESTAMP \
  --output layout/build/pll-core-fill-next
make pll-core-check CANDIDATE=layout/build/pll-core-next \
  LIBRARY=layout/build/pll-core-fill-next
```

The recipe protects the digital macro and individual analog circuit blocks
by 10 µm, routing by 2 µm and TopMetal1 by 3.05 µm. Fill is native Magic
`*fill` geometry, retained as a separate `cic_core_metal_fill` child. It is
floating and **requires post-fill extraction/electrical requalification**.

## Earlier larger measured checkpoint (008/009)

Unfilled: `build/pll-core-008/mag/pll_core.mag`.
Filled: `build/pll-core-fill-009/pll_core.mag`.
Filled GDS and complete check report:
`build/pll-core-008/checks/pll_core/20261021-051216-069582/`.
The stream to inspect is `pll_core.gds` in that report directory.

| Check | Filled candidate 009 |
| --- | --- |
| Magic full DRC | PASS, 0 error areas |
| Full installed KLayout DRC, density, extra rules, antenna | PASS, 0 markers |
| Magic antenna | PASS, 0 markers |
| Hierarchical source/model-view Netgen LVS | PASS |
| Independent GDS/KLayout LVS + CMOM dimensions | PASS |
| Frozen digital polygon preservation | PASS, empty XOR on all 38 stream layer/purpose pairs |
| Readonly GDS passthrough + recognition restoration | PASS, empty XOR; not interpreted-paint regeneration |
| Independent KLayout LVS on restored round-trip GDS | PASS |
| Native Magic LVS after GDS reimport | Diagnostic FAIL, CMOM model recognition lost; KLayout is authoritative for core GDS LVS |
| Native Magic resistance + lumped-C PEX | FAIL, original C endpoints missing from R export |
| Overall `all` | FAIL; RC extraction remains required |

Core GDS device recognition uses the PDK's KLayout LVS backend, including
the explicit CMOM dimension audit. Fresh-GDS Magic LVS is still executed
and recorded, but has `required: false` in the round-trip child summary:
the installed Magic deck cannot reconstruct the MOM device abstraction.
This policy applies only to the core's GDS-reimport diagnostic. Maintained
source/model-view Magic LVS, GDS KLayout LVS, geometry preservation, DRC,
antenna and PEX remain required. A failing KLayout comparison or extraction
still makes the command return nonzero. The standalone analog checker
retains its existing strict policy.

Policy replay `build/pll-core-008/checks/pll_core/20261021-075507-422009/`
rechecks the filled 009 geometry. Its round-trip child
`20261021-075510-989519` passes KLayout LVS and retains the non-required
Magic failure. The overall command still fails on required PEX. Controls
under `build/pll-core-policy-controls/` reject a swapped UP/DOWN reference
and accept the exact flattened extraction input with CMOM dimensions audited.

Candidate 002 had eight cumulative antenna markers and seven density
markers. Short local control accesses removed the antenna markers (003).
First fill trial 004 closed density but exposed TopMetal1 fill-to-wire
spacing; 3.05-µm clearance fixes it in 005. Positive LVS passes; deliberately
swapped UP/DOWN references are rejected by both LVS engines. Maintained
analog and the frozen digital package remain unchanged.

**Do not promote 003/005.** An additional frozen-macro audit found that normal
Magic import/export removed 903 pSD polygons (1,526.46815 µm²), despite
passing DRC and LVS. Readonly, non-flattening import fixes this in 008/009;
the new geometry gate rejects 005 and accepts 008/009. Filled 009 also keeps
its backing stream locally, and checker snapshots rewrite and hash these
dependencies. No matching source geometry is substituted for a failing
stream. The round-trip native checks still operate on freshly interpreted
paint and still expose the unsupported CMOM model recognition.

The PEX audit identifies 2,796 missing original endpoints affecting 42,445
capacitor records (including zero-valued records). Digital auto nodes are
replaced by distributed `.t`/`.n` nodes without preserving the original
attachment names. The rhigh body endpoint is additionally not exposed by
the three-terminal compact model. Do not alias every fragment together,
assign all missing capacitance to an arbitrary terminal, split the foundry
resistor or discard capacitors to make this gate green.

## Alternative native RC

The pinned KPEX environment from the analog experiments provides another
backend, not a waiver of Magic's failures:

```sh
python3 scripts/pll/native_rc.py \
  layout/build/pll-core-008/checks/pll_core/20261021-051216-069582 \
  --output layout/build/pll-core-native-rc-next
# Lower-memory capacitance-only screen, NOT a full-RC substitute:
python3 scripts/pll/native_rc.py \
  layout/build/pll-core-008/checks/pll_core/20261021-051216-069582 \
  --mode CC --output layout/build/pll-core-native-cc-next
```

It requires a completed physically passing report and passing frozen-macro
geometry audit of that exact stream, makes an extraction-only
flattened copy with child text removed, proves unchanged polygons on every
layer, requires ordinary PDK KLayout LVS on that exact flattened copy,
runs KPEX 0.6.10 with one thread and an 8-GiB virtual-memory ceiling,
and records the extractor exit separately. The completed export must pass
named-device parameter/terminal and R-collapsed connectivity audits, and
physical CMOM stack restoration. `result.json` is written FAIL before the
post-export checks and becomes PASS only after they finish. No result file
means no completed extraction result; an existing SPICE file alone is not
acceptance. The diagnostic replay `build/pll-core-native-rc-007` failed with
`std::bad_alloc` in the sidewall/fringe neighborhood operation at the 8-GiB
limit. That replay used superseded 005 geometry, not the corrected 009;
there is no accepted full-core native RC export. It is not still running.

Upstream v0.6.10 already processes primary layers sequentially but has no
supported tiled/hierarchical bounded-memory mode for this operation.
Capacitance reporting defaults off and INFO logging was used. Changing
the halo, omitting fill/coupling or independently extracting subcells would
not be an equivalent full-core result. A validated scalable extraction path
is required before full-RC electrical signoff; none of these failures is waived.

The audit was checked against the earlier audited analog RC export and
rejects wrong device width, an UP–DOWN short and a dangling external port.
It does not qualify capacitance accuracy, well/substrate resistance,
post-fill closed-loop performance, receiver timing/load margins or ESD.
Those remain integration/signoff requirements even after an RC export passes.

Capacitance-only mode uses KPEX's `CC` mode, which does not retain the extra
geometry needed to attach capacitance to distributed resistance. It uses
the same filled input geometry and coupling model, without omitting fill
or reducing the halo. Output is `core_cc.spice`; the default RC output
remains `core_rc.spice`. Both must pass modeled-device and DC-connectivity
checks plus physical capacitor-stack restoration. `result.json` explicitly
records `extraction_mode`; a passing CC screen always has
`full_rc_export_passed: false`. It cannot clear the required RC gate.
The CC replay `build/pll-core-native-cc-012` failed at the same
sidewall/fringe `Region.complex_op` allocation as full RC under the 8-GiB
ceiling. Omitting resistance therefore did not resolve the allocation failure.
KPEX's internal "LVS succeeded" message means a database was produced, not
that its unsimplified schematic comparison passed. It is not used as the
acceptance criterion. The ordinary PDK comparison above is required; the
parasitic export then has its own device/terminal/DC-connectivity audit.

The default ceiling remains 8 GiB; `--memory-gib` records a reproducible
per-process ceiling up to 10 GiB, without changing Docker/host settings.
Check headroom and run one extractor at a time. A full-RC replay at 10 GiB
is `build/pll-core-native-rc-014`, using corrected 009 geometry and its own
ordinary-PDK flattened-input LVS preflight. At launch Docker reported
12.7 GiB total RAM, with the VM nearly idle and host memory pressure low.
It completed **FAIL**, again with `std::bad_alloc` in the sidewall/fringe
`Region.complex_op`. Increasing the ceiling alone did not resolve it.

An isolated runtime experiment built KLayout at
[the upstream source checkpoint containing the neighborhood visitor fixes](https://github.com/KLayout/klayout/commit/cf58e69ef3f82a958f89780e20ead00f16b5b97e).
The installed 0.30.12 runtime retained **59075 kB after 400000 callbacks** in
the issue2495 reproducer; the patched runtime retained **1 kB** for the
same callback count. This validates the leak fix locally, but does not
yet prove it resolves the whole-core allocation failure.
The optimized (`-O3 -g0`) wheel was built in a disposable tools-image container;
the primary container's KLayout and original KPEX034 environment are unchanged.
Build outputs/provenance are under `build/pll-klayout-fix-015`, with a separate
`build/pll-kpex-env-015` environment; `pip check` passes there. Wheel SHA256:
`cd7f97de832a22e8ca6a5582771ef1846b716f9c9f74e8230bf476b1ef15ae4d`.
The unchanged-009 CC retry is `build/pll-core-native-cc-015`; its ordinary
PDK flattened-input LVS and completed export/stack audits pass. The engine
completed in about 58 minutes with 181748 parasitic capacitors. Postprocessing
initially selected both output and cache databases; selecting the explicit
output database fixes that wrapper error. Audits were replayed on the existing
export without rerunning extraction. This remains **CC only**, not full RC.
`--kpex-python PATH` selects an isolated
KPEX interpreter and records its KLayout version, module path and wheel
provenance in `input_audit.json`. The patched source still reports 0.30.12;
the version string alone cannot identify it. Require the same
LVS/export/stack gates for the patched-runtime output.
Neither a successful wheel build nor a reduced leak is extraction acceptance.

Full-RC run016 used the patched runtime, unchanged filled009 input and an
8-GiB ceiling. Its ordinary flattened-input PDK LVS passes, but extraction
was **cancelled at the user's request to prioritize slot13 packing**. Its
exit code -15 is a cancellation, not a completed extraction qualification.
No RC extractor remains running. Original launch command, inside the
tools container at the repository root
(use a new output directory for each attempt; do not run extractors concurrently):

```sh
unset PYTHONPATH
python3 scripts/pll/native_rc.py \
  layout/build/pll-core-008/checks/pll_core/20261021-051216-069582 \
  --mode RC --memory-gib 8 \
  --kpex-python layout/build/pll-kpex-env-015/bin/python \
  --output layout/build/pll-core-native-rc-016
```

The installed `cap_cmomf` simulation model explicitly states that it is a
low-frequency engineering estimate, not silicon-validated. It has no
series resistance/inductance, substrate coupling or process/mismatch spread.
Passing LVS does not validate these electrical properties. Do not combine
a modeled MOM capacitance and an explicitly extracted finger capacitance
without checking device-region exclusion to prevent double-counting.
