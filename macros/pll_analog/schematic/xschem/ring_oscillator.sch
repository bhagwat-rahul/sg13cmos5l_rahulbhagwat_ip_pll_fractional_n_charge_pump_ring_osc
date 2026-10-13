v {xschem version=3.4.8RC file_version=1.3}
G {}
K {}
V {}
S {}
F {}
E {}
T {Buffered three-stage current-starved VCO with single-control replica bias} -300 -420 0 0 0.3 0.3 {}
N -300 -60 -300 -20 {lab=VCTRL}
N 160 -60 160 -20 {lab=VCTRL}
N -790 -60 -790 -20 {lab=VCTRL}
N -300 -20 160 -20 {lab=VCTRL}
N -790 -20 -300 -20 {lab=VCTRL}
N 160 -160 160 -100 {lab=VBP}
N -300 -160 160 -160 {lab=VBP}
N -790 -160 -790 -100 {lab=VBP}
N -490 -80 -300 -80 {lab=#net1}
N 0 -80 160 -80 {lab=#net2}
N 460 -80 520 -80 {lab=VCO_CORE}
N 520 -80 520 40 {lab=VCO_CORE}
N -140 40 520 40 {lab=VCO_CORE}
N -860 -80 -860 40 {lab=VCO_CORE}
N -860 -80 -790 -80 {lab=VCO_CORE}
N -300 -160 -300 -100 {lab=VBP}
N -790 -160 -300 -160 {lab=VBP}
N -490 -220 -490 -100 {lab=VDD}
N 0 -220 0 -100 {lab=VDD}
N 460 -220 460 -100 {lab=VDD}
N 0 -220 460 -220 {lab=VDD}
N -490 -220 0 -220 {lab=VDD}
N 460 -220 580 -220 {lab=VDD}
N 580 -220 580 80 {lab=VDD}
N 160 80 580 80 {lab=VDD}
N -140 40 -140 80 {lab=VCO_CORE}
N -860 40 -140 40 {lab=VCO_CORE}
N 160 100 200 100 {lab=VCO_OUT}
N 580 80 580 220 {lab=VDD}
N -900 -100 -790 -100 {lab=VBP}
N -900 -100 -900 160 {lab=VBP}
N -900 160 0 160 {lab=VBP}
N 0 160 0 220 {lab=VBP}
N 20 220 580 220 {lab=VDD}
N 20 540 20 560 {lab=VCTRL}
N -490 -60 -490 10 {lab=VSS}
N 0 10 460 10 {lab=VSS}
N 460 -60 460 10 {lab=VSS}
N 0 -60 0 10 {lab=VSS}
N -490 10 0 10 {lab=VSS}
N -490 10 -490 220 {lab=VSS}
N -490 220 -20 220 {lab=VSS}
N 160 120 460 120 {lab=VSS}
N 460 10 460 120 {lab=VSS}
N -790 -20 -790 540 {lab=VCTRL}
N -790 540 20 540 {lab=VCTRL}
N 20 520 20 540 {lab=VCTRL}
C {inverter.sym} -640 -80 0 0 {name=x1}
C {inverter.sym} -150 -80 0 0 {name=x2}
C {inverter.sym} 310 -80 0 0 {name=x3}
C {vco_bias.sym} 0 370 1 1 {name=x_bias}
C {vco_buffer.sym} 10 100 0 0 {name=x_buffer}
C {lab_pin.sym} -180 160 3 0 {name=p_VBP_INTERNAL sig_type=std_logic lab=VBP}
C {lab_pin.sym} -320 40 3 0 {name=p_VCO_CORE_INTERNAL sig_type=std_logic lab=VCO_CORE}
C {ipin.sym} 20 560 1 1 {name=p_VCTRL lab=VCTRL}
C {iopin.sym} 580 -80 0 0 {name=p_VDD lab=VDD}
C {iopin.sym} -320 220 1 0 {name=p_VSS lab=VSS}
C {opin.sym} 200 100 0 0 {name=p_VCO_OUT lab=VCO_OUT}
