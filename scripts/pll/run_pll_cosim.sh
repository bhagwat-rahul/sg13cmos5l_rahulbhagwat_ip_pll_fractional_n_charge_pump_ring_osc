#!/usr/bin/env bash
set -euo pipefail

# Optional extracted analog: ANALOG_SPICE, ANALOG_SUBCKT (pll_analog_pex),
# ANALOG_VCTRL_NODE and ANALOG_STARTUP_NODE (relative to x_analog).
# RECEIVER_SPICE adds the frozen transistor receiver as a physical load/witness;
# RECEIVER_FEEDBACK=1 clocks RTL from its register-branch buffer and bypasses RTL /2.
# PFD_SPICE replaces ideal RTL UP/DOWN with the frozen transistor PFD and RC.
# Feedback dividers remain functional RTL, not extracted digital timing signoff.
# KEEP_WORK=1 retains decks, compilation and simulation logs for inspection.
# COSIM_WAVEFORM optionally writes the saved transient vectors as binary SPICE.
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
PROJECT_ROOT=$(cd "$SCRIPT_DIR/../.." && pwd)
PLL_DIR="$PROJECT_ROOT/macros/pll_analog/schematic/xschem"
RTL_DIR="$PROJECT_ROOT/macros/pll_digital/rtl"
DIV_RATIO=${DIV_RATIO:-160}
TEST_DIV=${TEST_DIV:-1}
FREF_HZ=${FREF_HZ:-100e6}
SIM_TIME_S=${SIM_TIME_S:-4e-6}
MAX_STEP_S=${MAX_STEP_S:-5e-12}
VDD=${VDD:-1.2}
CORNER=${CORNER:-tt}
TEMP_C=${TEMP_C:-27}
TOOLS_BIN=${TOOLS_BIN:-/foss/tools/bin}
REAL_VERILATOR=${REAL_VERILATOR:-$TOOLS_BIN/verilator}
export RECEIVER_FEEDBACK=${RECEIVER_FEEDBACK:-0}
if [[ $RECEIVER_FEEDBACK != 0 && $RECEIVER_FEEDBACK != 1 ]] ||
   [[ $RECEIVER_FEEDBACK == 1 && -z ${RECEIVER_SPICE:-} ]]; then
  echo "RECEIVER_FEEDBACK must be 0 or 1, and 1 requires RECEIVER_SPICE" >&2
  exit 1
fi

python3 - "$DIV_RATIO" "$TEST_DIV" "$FREF_HZ" "$SIM_TIME_S" "$CORNER" "$TEMP_C" <<'PY'
import sys
ratio, test_div = map(int, sys.argv[1:3])
fref, sim_time = map(float, sys.argv[3:5])
corner = sys.argv[5]
temp = float(sys.argv[6])
integer = ratio >> 3
if not 4 <= integer <= 80:
    raise SystemExit("DIV_RATIO integer field must be 4-80")
if not 0 <= ratio <= 1023:
    raise SystemExit("DIV_RATIO must be a 10-bit unsigned value")
if not 0 <= test_div <= 3:
    raise SystemExit("TEST_DIV must be 0-3")
if not 25e6 <= fref <= 250e6:
    raise SystemExit("FREF_HZ must be 25e6-250e6")
if sim_time < 2e-6:
    raise SystemExit("SIM_TIME_S must be at least 2e-6")
if corner not in ("tt", "ss", "ff", "sf", "fs"):
    raise SystemExit("CORNER must be tt, ss, ff, sf, or fs")
if not -40 <= temp <= 125:
    raise SystemExit("TEMP_C must be -40 to 125")
PY

WORK=$(mktemp -d "${TMPDIR:-/tmp}/pll-cosim.XXXXXX")
cleanup() {
  if [[ ${KEEP_WORK:-0} == 1 ]]; then
    echo "co-simulation work directory: $WORK" >&2
  else
    rm -rf "$WORK"
  fi
}
trap cleanup EXIT
mkdir -p "$WORK/bin"

# ngspice-46's vlnggen helper lowercases case-sensitive Verilator options and
# does not parse Verilator-5 port declarations. This temporary wrapper fixes
# those compatibility issues and reconstructs the actual generated port table.
cat >"$WORK/bin/verilator" <<'EOF'
#!/usr/bin/env bash
args=()
previous=""
mdir=""
for argument in "$@"; do
  case "$argument" in
    --mdir) argument=-Mdir ;;
    --cflags) argument=-CFLAGS ;;
    -i/foss/*) argument="-I${argument:2}" ;;
  esac
  if [[ "$previous" == --prefix && "$argument" == vlng ]]; then
    argument=Vlng
  fi
  if [[ "$previous" == -Mdir ]]; then
    mdir=$argument
  fi
  args+=("$argument")
  previous=$argument
done

if [[ " ${args[*]} " == *" --build "* && -n "$mdir" ]]; then
  python3 - "$mdir" <<'PY'
from pathlib import Path
import re
import sys
directory = Path(sys.argv[1])
header = (directory / 'Vlng.h').read_text()
for direction, filename in (('IN', 'inputs.h'), ('OUT', 'outputs.h'), ('INOUT', 'inouts.h')):
    ports = re.findall(r'VL_' + direction + r'(8|16|32|64)\(&([\w]+),(\d+),(\d+)\)', header)
    (directory / filename).write_text(''.join(
        f'VL_DATA({size},{name},{msb},{lsb})\n' for size, name, msb, lsb in ports))
PY
fi

"$REAL_VERILATOR" "${args[@]}"
status=$?
if [[ $status -eq 0 && -n "$mdir" && -f "$mdir/Vlng.h" ]]; then
  ln -sf Vlng.h "$mdir/vlng.h"
  if [[ -f "$mdir/Vlng__ALL.a" ]]; then
    ln -sf Vlng__ALL.a "$mdir/vlng__all.a"
  fi
fi
exit "$status"
EOF
chmod +x "$WORK/bin/verilator"

export REAL_VERILATOR
export PATH="$WORK/bin:$TOOLS_BIN:$PATH"
export PDK_ROOT=${PDK_ROOT:-/foss/pdks}
export PDK=${PLL_PDK:-ihp-sg13cmos5l}
export PDKPATH=${PLL_PDKPATH:-$PDK_ROOT/$PDK}
export SPICE_USERINIT_DIR=$PDKPATH/libs.tech/ngspice

clock_source="$RTL_DIR/clock_output_divider.v"
if [[ $RECEIVER_FEEDBACK == 1 ]]; then
  clock_source="$WORK/clock_output_divider.v"
  python3 - "$RTL_DIR/clock_output_divider.v" "$clock_source" <<'PY'
from pathlib import Path
import re
import sys
text = Path(sys.argv[1]).read_text()
text, count = re.subn(r'(module high_speed_div2\b.*?\n\);)\n.*?\nendmodule',
    lambda m: m[1].replace('output reg', 'output wire')
        + "\n    assign q = reset_b ? clk : 1'b0;\nendmodule",
    text, flags=re.S)
if count != 1:
    raise SystemExit('expected exactly one portable high_speed_div2 model')
Path(sys.argv[2]).write_text('// SIMULATION ONLY: physical receiver already divides by two.\n' + text)
PY
fi
(
  cd "$WORK"
  ngspice vlnggen \
    "$RTL_DIR/pll_digital.v" \
    "$RTL_DIR/pfd.v" \
    "$RTL_DIR/fractional_divider.v" \
    "$clock_source" >build.log 2>&1
  mv pll_digital.so pll_digital_cosim.so
)

expected_inputs='ref_clk vco_clk reset_n enable test_div_select div_ratio'
expected_outputs='feedback_clk up down pll_clk test_clk'
if [[ $RECEIVER_FEEDBACK == 1 ]]; then
  expected_outputs='feedback_clk pll_clk up down test_clk'
fi
actual_inputs=$(sed -n 's/^VL_DATA([^,]*,\([^,]*\),.*/\1/p' "$WORK/pll_digital_obj_dir/inputs.h" | paste -sd' ' -)
actual_outputs=$(sed -n 's/^VL_DATA([^,]*,\([^,]*\),.*/\1/p' "$WORK/pll_digital_obj_dir/outputs.h" | paste -sd' ' -)
if [[ $actual_inputs != "$expected_inputs" || $actual_outputs != "$expected_outputs" ]]; then
  printf 'd_cosim port order changed; update pll_digital_cosim.sym before simulation.\n' >&2
  printf 'inputs:  %s\noutputs: %s\n' "$actual_inputs" "$actual_outputs" >&2
  exit 1
fi

(
  cd "$PLL_DIR"
  env -u DISPLAY xschem -n -q -x -o "$WORK" -N pll_cosim.spice ../../testbenches/xschem/pll_cosim.tb.sch \
    >"$WORK/xschem.log" 2>&1 || [[ $? -eq 10 ]]
)

export DIV_RATIO TEST_DIV FREF_HZ SIM_TIME_S MAX_STEP_S VDD CORNER TEMP_C
python3 - "$WORK/pll_cosim.spice" "$PROJECT_ROOT/macros/pll_digital/frozen/v1/spef/nom/pll_digital.nom.spef" <<'PY'
import hashlib
import json
import os
from pathlib import Path
import re
import sys

path = sys.argv[1]
text = open(path).read()
ratio = int(os.environ["DIV_RATIO"])
test_div = int(os.environ["TEST_DIV"])
fref = float(os.environ["FREF_HZ"])
sim_time = float(os.environ["SIM_TIME_S"])
max_step = float(os.environ["MAX_STEP_S"])
vdd = float(os.environ["VDD"])
corner = os.environ["CORNER"]
temp = float(os.environ["TEMP_C"])
period = 1.0 / fref
settled_start = sim_time - 1.0e-6

text = re.sub(
    r"VREF REF_CLK 0 PULSE\([^\n]+\)",
    f"VREF REF_CLK 0 PULSE(0 {vdd} 1n 20p 20p {period / 2 - 20e-12:.12g} {period:.12g})",
    text,
)
text = re.sub(r"VDD_SRC VDD 0 \S+", f"VDD_SRC VDD 0 {vdd}", text)
text = re.sub(r"VENABLE ENABLE 0 \S+", f"VENABLE ENABLE 0 {vdd}", text)
text = text.replace("PULSE(0 1.2 2n", f"PULSE(0 {vdd} 2n")
text = text.replace("mos_tt", f"mos_{corner}")
text = text.replace(".options temp=27", f".options temp={temp}")
text = text.replace("v(x_pll.x_analog.x_vco.net1)=1.2", f"v(x_pll.x_analog.x_vco.net1)={vdd}")
vctrl_node = "x_pll.x_analog.VCTRL"
analog = os.environ.get("ANALOG_SPICE")
if analog:
    # Explicit experimental replacement; never infer extracted pin order.
    analog_path = Path(analog).resolve(strict=True)
    analog_text = analog_path.read_text()
    name = os.environ.get("ANALOG_SUBCKT", "pll_analog_pex")
    flattened = re.sub(r"\n\s*\+", " ", analog_text)
    declaration = re.search(r"^\.subckt\s+" + re.escape(name) + r"\s+([^\n]+)",
                            flattened, re.I | re.M)
    expected = {"VDD", "VSS", "UP", "DOWN", "IREF", "VCO_CLK"}
    ports = declaration[1].split() if declaration else []
    if len(ports) != len(expected) or set(ports) != expected:
        raise SystemExit(f"unexpected analog interface: {name} {ports}")
    text, count = re.subn(r"^x_analog[^\n]+pll_analog\s*$",
                         "x_analog " + " ".join(ports) + " " + name,
                         text, count=1, flags=re.M)
    if count != 1:
        raise SystemExit("expected exactly one pll_analog instance")
    # Remove the unused analog hierarchy, including its scoped passive-model
    # parameters. Keeping it can collide with identically named extracted
    # subcircuits in ngspice's parameter expansion even when it is uninstantiated.
    for cell in ("pll_analog", "charge_pump", "loop_filter", "ring_oscillator",
                 "inverter", "vco_bias", "vco_buffer"):
        text = re.sub(r"^\.subckt\s+" + cell + r"\s[^\n]*\n.*?^\.ends\b[^\n]*\n",
                      "", text, flags=re.M | re.S | re.I)
    text = text.replace(".end\n", f'.include "{analog_path}"\n.end\n')
    vctrl = os.environ["ANALOG_VCTRL_NODE"]
    startup = os.environ["ANALOG_STARTUP_NODE"]
    if any(not re.fullmatch(r"[\w.$#]+", node) for node in (vctrl, startup)):
        raise SystemExit("invalid analog probe/startup node")
    vctrl_node = "x_pll.x_analog." + vctrl
    # The source hierarchy no longer exists. Use a reviewed physical alias
    # and a small startup-current kick, rather than fictitious .ic nodes.
    text = re.sub(r"^\.ic[^\n]*\n", "", text, flags=re.M)
    kick = ("ISEED 0 x_pll.x_analog." + startup
            + " PWL(0 0 .5n 0 .51n 1u .6n 1u .61n 0)\n")
    text = text.replace(".end\n", kick + ".end\n")
    Path(path).with_name("analog_input.json").write_text(json.dumps({
        "path": str(analog_path), "sha256": hashlib.sha256(analog_path.read_bytes()).hexdigest(),
        "subcircuit": name, "ports": ports, "vctrl_node": vctrl_node,
        "startup_node": startup,
        "limitations": "RTL d_cosim is functional, not routed digital timing or noise signoff",
    }, indent=2) + "\n")
receiver = os.environ.get("RECEIVER_SPICE")
receiver_feedback = os.environ["RECEIVER_FEEDBACK"] == "1"
pfd = os.environ.get("PFD_SPICE")
if receiver or pfd:
    library = Path(os.environ["PDKPATH"]) / "libs.ref/sg13cmos5l_stdcell/spice/sg13cmos5l_stdcell.spice"
    text = text.replace(".end\n", f'.include "{library}"\n.end\n')
if receiver:
    receiver = Path(receiver).resolve(strict=True)
    # Physical receiver load/witness; RTL still performs its own functional /2.
    physical = (f'.include "{receiver}"\n'
                '.subckt cosim_receiver_witness IN RESET VDD VSS\n'
                'Xreceiver IN CLK DIV2 RESET VDD VSS frozen_receiver\n'
                '.ends cosim_receiver_witness\n')
    text = text.replace(".end\n", physical + ".end\n")
    text = text.replace("x_analog ", "x_receiver VCO_CLK RESET_N VDD VSS cosim_receiver_witness\nx_analog ", 1)
    if receiver_feedback:
        # Follow the real register-clock branch, not an ADC on weak raw Q.
        # extract_receiver names each physical buffer output by its SPEF ID.
        spef = Path(sys.argv[2]).read_text()
        binding = re.search(r'^\*(\d+) clkbuf_regs_0_half$', spef, re.M)
        if not binding:
            raise SystemExit('frozen register-clock buffer mapping missing')
        buffer_node = f'load_{binding[1]}_out'
        if not re.search(r'^X\S+ ' + buffer_node + r' .* sg13cmos5l_buf_16$',
                         receiver.read_text(), re.M):
            raise SystemExit('receiver does not contain the frozen register-clock buffer')
        receiver_clock = f'x_receiver.xreceiver.{buffer_node}'
        # Match the production receiver's reset_n && enable reset control.
        # Preserve the analog reset ramp while ENABLE is asserted.
        text = text.replace("x_receiver VCO_CLK RESET_N ",
                            f"Breceiver_reset RECEIVER_RESET VSS V=V(ENABLE,VSS)>{vdd / 2} ? V(RESET_N,VSS) : 0\n"
                            "x_receiver VCO_CLK RECEIVER_RESET ", 1)
        text, count = re.subn(r'\[ REF_CLK VCO_CLK RESET_N ENABLE',
                             f'[ REF_CLK {receiver_clock} RESET_N ENABLE', text)
        if count != 1:
            raise SystemExit('expected exactly one RTL clock-input bundle')
if pfd:
    pfd = Path(pfd).resolve(strict=True)
    text = text.replace(".end\n", f'.include "{pfd}"\n.end\n')
    text, count = re.subn(r"\[ FB_CLK UP DOWN PLL_CLK TEST_CLK \]",
                         "[ FB_CLK UP_RTL DOWN_RTL PLL_CLK TEST_CLK ]", text)
    if count != 1:
        raise SystemExit("unexpected RTL output bundle for physical PFD substitution")
    physical = (f"Bpfd_enable PFD_ENABLE VSS V=V(ENABLE,VSS)>{vdd / 2} && V(RESET_N,VSS)>{vdd / 2} ? {vdd} : 0\n"
                "Xphysical_pfd REF_CLK FB_CLK PFD_ENABLE UP DOWN VDD VSS pfd_driver\n")
    text = text.replace("x_analog ", physical + "x_analog ", 1)
if receiver_feedback:
    # The bypass changes Verilator's generated output declaration order.
    # The preceding header check guards this explicit co-simulation mapping.
    text = text.replace('[ FB_CLK UP_RTL DOWN_RTL PLL_CLK TEST_CLK ]',
                        '[ FB_CLK PLL_CLK UP_RTL DOWN_RTL TEST_CLK ]') if pfd else text.replace(
                        '[ FB_CLK UP DOWN PLL_CLK TEST_CLK ]',
                        '[ FB_CLK PLL_CLK UP DOWN TEST_CLK ]')
for prefix, width, value in (
    ("DIV_RATIO", 10, ratio),
    ("TEST_DIV", 2, test_div),
):
    source_prefix = "V" + prefix
    for bit in range(width):
        voltage = vdd if (value >> bit) & 1 else 0
        text = re.sub(
            rf"^{source_prefix}{bit} {prefix}{bit} 0 \S+",
            f"{source_prefix}{bit} {prefix}{bit} 0 {voltage}",
            text,
            flags=re.MULTILINE,
        )

save_vectors = (f"v(TEST_CLK) v({vctrl_node}) i(VDD_SRC) v(x_pll.UP) v(x_pll.DOWN)"
                " v(x_pll.VCO_CLK) v(x_pll.FB_CLK) v(REF_CLK)")
if receiver:
    save_vectors += " v(x_pll.x_receiver.DIV2)"
if receiver_feedback:
    save_vectors += f" v(x_pll.{receiver_clock})"
adc_low, adc_high = (.1 * vdd, .9 * vdd) if receiver_feedback else (.3, .9)
commands = [
    ".control",
    "set num_threads=1",
    "set numdgt=15",
    f'pre_set auto_bridge_d_in = ( ".model auto_adc adc_bridge(in_low={adc_low} in_high={adc_high} rise_delay=5p fall_delay=5p)" "auto_bridge%d [ %s ] [ %s ] auto_adc" )',
    f'pre_set auto_bridge_d_out = ( ".model auto_dac dac_bridge(out_low=0 out_high={vdd} t_rise=20p t_fall=20p)" "auto_bridge%d [ %s ] [ %s ] auto_dac" )',
    f"save {save_vectors}",
    f"tran {max_step:.12g} {sim_time:.12g} uic",
]
for edge in range(1, 102):
    commands.append(
        f"meas tran cosim_edge_{edge} when v(TEST_CLK)={vdd / 2} rise={edge} TD={settled_start:.12g}"
    )
commands.append(
    f"meas tran vctrl_avg avg v({vctrl_node}) from={settled_start:.12g} to={sim_time:.12g}"
)
for name, operation, vector in (("vctrl_ripple", "pp", f"v({vctrl_node})"),
                                ("idd_avg", "avg", "i(VDD_SRC)"),
                                ("up_avg", "avg", "v(x_pll.UP)"),
                                ("down_avg", "avg", "v(x_pll.DOWN)")):
    commands.append(f"meas tran {name} {operation} {vector} from={settled_start:.12g} to={sim_time:.12g}")
if receiver:
    for name, operation in (("receiver_q_max", "max"), ("receiver_q_min", "min")):
        commands.append(f"meas tran {name} {operation} v(x_pll.x_receiver.DIV2) from={settled_start:.12g} to={sim_time:.12g}")
    for suffix, edge in (("a", 1), ("b", 201)):
        commands.append(f"meas tran receiver_{suffix} when v(x_pll.x_receiver.DIV2)={vdd / 2} rise={edge} TD={settled_start:.12g}")
start = .5e-6
while start <= sim_time - .5e-6 + 1e-15:
    index = round((start - .5e-6) / .25e-6)
    for suffix, edge in (("a", 1), ("b", 101)):
        commands.append(f"meas tran lock_{index}_{suffix} when v(TEST_CLK)={vdd / 2} rise={edge} TD={start:.12g}")
    start += .25e-6
if os.environ.get("COSIM_WAVEFORM"):
    waveform = Path(os.environ["COSIM_WAVEFORM"]).resolve()
    if any(c.isspace() for c in str(waveform)):
        raise SystemExit("ngspice write requires a waveform path without whitespace")
    commands.extend(("set filetype=binary", f"write {waveform} {save_vectors}"))
commands.append(".endc")
text = re.sub(r"\.control\n.*?\.endc", "\n".join(commands), text, count=1, flags=re.DOTALL)
open(path, "w").write(text)
PY

(
  cd "$WORK"
  ngspice -b pll_cosim.spice >simulation.log 2>&1 || { tail -40 simulation.log >&2; exit 1; }
)
if [[ -n ${COSIM_WAVEFORM:-} && ! -s $COSIM_WAVEFORM ]]; then
  echo "ngspice did not write the requested waveform: $COSIM_WAVEFORM" >&2
  exit 1
fi

python3 - "$WORK/simulation.log" <<'PY'
import json
import math
import os
import re
import statistics
import sys

log = open(sys.argv[1]).read()
bad = ("mismatched XSPICE", "undefined symbol", "no entry function", "simulation interrupted")
if any(item.lower() in log.lower() for item in bad):
    raise SystemExit(log)

def value(name):
    match = re.search(rf"^{name}\s+=\s+([\d.eE+-]+)", log, re.MULTILINE)
    return None if match is None else float(match.group(1))

edges = [value(f"cosim_edge_{index}") for index in range(1, 102)]
if any(edge is None for edge in edges):
    raise SystemExit("co-simulation did not produce 101 settled TEST_CLK output edges")
periods = [edges[index + 1] - edges[index] for index in range(100)]
mean_period = statistics.mean(periods)
rms_jitter = math.sqrt(statistics.mean((period - mean_period) ** 2 for period in periods))
ratio = int(os.environ["DIV_RATIO"])
test_div = int(os.environ["TEST_DIV"])
fref = float(os.environ["FREF_HZ"])
divide = ratio / 8.0
target = fref * divide / 2 ** (test_div + 1)
measured = 1.0 / mean_period
if abs(measured / target - 1.0) > 0.01:
    raise SystemExit(f"co-simulation frequency error exceeds 1%: target={target} measured={measured}")
windows = []
start = .5e-6
while start <= float(os.environ["SIM_TIME_S"]) - .5e-6 + 1e-15:
    index = len(windows)
    first, last = value(f"lock_{index}_a"), value(f"lock_{index}_b")
    frequency = None if first is None or last is None else 100 / (last - first)
    windows.append((start, frequency))
    start += .25e-6
lock_time = next((start for index, (start, _) in enumerate(windows)
                  if all(f is not None and abs(f / target - 1) <= .01
                         for _, f in windows[index:])), None)
receiver_frequency = None
if os.environ.get("RECEIVER_SPICE"):
    a, b = value("receiver_a"), value("receiver_b")
    if a is None or b is None:
        raise SystemExit("physical receiver did not produce 201 settled edges")
    receiver_frequency = 200 / (b - a)
    if abs(receiver_frequency / (fref * divide / 2) - 1) > .01:
        raise SystemExit("physical receiver divide-by-two frequency error exceeds 1%")
    if value("receiver_q_max") < .9 * float(os.environ["VDD"]) or value("receiver_q_min") > .1 * float(os.environ["VDD"]):
        raise SystemExit("physical receiver fails settled Q swing screen")
print(json.dumps({
    "corner": os.environ["CORNER"],
    "divide": divide,
    "reference_hz": fref,
    "target_output_hz": target,
    "test_div": test_div,
    "temp_c": float(os.environ["TEMP_C"]),
    "vdd_v": float(os.environ["VDD"]),
    "measured_output_hz": measured,
    "rms_period_jitter_s": rms_jitter,
    "peak_to_peak_period_jitter_s": max(periods) - min(periods),
    "vctrl_v": value("vctrl_avg"),
    "vctrl_ripple_pp_v": value("vctrl_ripple"),
    "modeled_supply_power_w": -value("idd_avg") * float(os.environ["VDD"]),
    "lock_time_s_1pct_sampled": lock_time,
    "up_duty": value("up_avg") / float(os.environ["VDD"]),
    "down_duty": value("down_avg") / float(os.environ["VDD"]),
    "analog_source": os.environ.get("ANALOG_SPICE", "schematic"),
    "physical_receiver_load": bool(os.environ.get("RECEIVER_SPICE")),
    "physical_receiver_feedback": os.environ.get("RECEIVER_FEEDBACK") == "1",
    "physical_receiver_div2_hz": receiver_frequency,
    "physical_receiver_q_max_v": value("receiver_q_max"),
    "physical_receiver_q_min_v": value("receiver_q_min"),
    "physical_pfd": bool(os.environ.get("PFD_SPICE")),
}, indent=2, sort_keys=True))
PY
