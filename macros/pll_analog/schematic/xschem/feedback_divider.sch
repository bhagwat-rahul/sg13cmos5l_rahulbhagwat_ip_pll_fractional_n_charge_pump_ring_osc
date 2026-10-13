v {xschem version=3.4.8RC file_version=1.3}
G {}
K {}
V {}
S {}
F {}
E {}
T {Integer XSPICE feedback-divider model for transistor-level loop simulation.
The synthesizable integer/fractional implementation is rtl/fractional_divider.v.} -280 -360 0 0 0.3 0.3 {}
N 180 0 250 0 {lab=FB_OUT}
N 60 -0 120 -0 {lab=dfb}
N -120 0 -60 0 {lab=dvco}
N -240 0 -180 -0 {lab=VCO_IN}
C {adc_bridge.sym} -150 0 0 0 {name=A_ADC adc_bridge_model=pll_div_adc}
C {d_fdiv.sym} 0 0 0 0 {name=A_DIV divider_model=pll_feedback_div}
C {lab_wire.sym} -90 0 1 0 {name=p_div_in sig_type=std_logic lab=dvco}
C {dac_bridge.sym} 150 0 0 0 {name=A_DAC dac_bridge_model=pll_div_dac}
C {lab_wire.sym} 90 0 1 0 {name=p_dac_in sig_type=std_logic lab=dfb}
C {ipin.sym} -240 0 0 0 {name=p_VCO_IN lab=VCO_IN}
C {opin.sym} 250 0 0 0 {name=p_FB_OUT lab=FB_OUT}
C {simulator_commands_shown.sym} -450 -280 0 0 {name=MODELS
simulator=ngspice
only_toplevel=false
value="
.model pll_div_adc adc_bridge(in_low=0.3 in_high=0.9 rise_delay=5p fall_delay=5p)
.model pll_div_dac dac_bridge(out_low=0 out_high=1.2 out_undef=0.6 input_load=1p t_rise=20p t_fall=20p)
.model pll_feedback_div d_fdiv(div_factor=20 high_cycles=1 i_count=0 rise_delay=5p fall_delay=5p freq_in_load=1p)
"}
