# Provisional integrated PLL core

`pll_core` instantiates the maintained `pll_analog` and frozen
`macros/pll_digital/frozen/v1` (including its fixed /2 prescaler). It is **not
the MPW pad wrapper, an analog freeze, or tapeout approval**. The assembly
contract is `schematic/pll_core.spice`; its child declarations specify port
order only. LVS replaces them with full source-derived circuits, not layout
netlists or macro black boxes.

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

## Current measured checkpoint

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
| Native Magic LVS after GDS reimport | FAIL, CMOM model recognition lost |
| Native Magic resistance + lumped-C PEX | FAIL, original C endpoints missing from R export |
| Overall `all` | FAIL; neither native failure is waived |

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
```

It requires a completed physically passing report and passing frozen-macro
geometry audit of that exact stream, makes an extraction-only
flattened copy with child text removed, proves unchanged polygons on every
layer, runs KPEX 0.6.10 with one thread and an 8-GiB virtual-memory ceiling,
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
