###############################################################################
# Created by write_sdc
###############################################################################
current_design pll_digital
###############################################################################
# Timing Constraints
###############################################################################
create_clock -name vco -period 0.5000 [get_ports {vco_clk}]
set_clock_transition 0.1500 [get_clocks {vco}]
set_clock_uncertainty 0.0250 vco
set_propagated_clock [get_clocks {vco}]
create_clock -name ref -period 10.0000 [get_ports {ref_clk}]
set_clock_transition 0.0200 [get_clocks {ref}]
set_clock_uncertainty 0.0250 ref
set_propagated_clock [get_clocks {ref}]
create_generated_clock -name half -source [get_ports {vco_clk}] -divide_by 2 [get_pins {output_divider_i.div2_ff/Q}]
set_clock_uncertainty 0.0250 half
set_propagated_clock [get_clocks {half}]
create_generated_clock -name div4 -source [get_ports {vco_clk}] -divide_by 4 [get_pins {output_divider_i.div4_ff/Q}]
set_clock_uncertainty 0.0250 div4
set_propagated_clock [get_clocks {div4}]
create_generated_clock -name div8 -source [get_ports {vco_clk}] -divide_by 8 [get_pins {output_divider_i.div8_ff/Q}]
set_clock_uncertainty 0.0250 div8
set_propagated_clock [get_clocks {div8}]
create_clock -name feedback -period 10.0000 [get_pins {feedback_divider_i._597_/Q}]
set_clock_transition 0.0200 [get_clocks {feedback}]
set_clock_uncertainty 0.0250 feedback
set_propagated_clock [get_clocks {feedback}]
set_clock_groups -name group1 -asynchronous \
 -group [get_clocks {feedback}]\
 -group [get_clocks {ref}]\
 -group [list [get_clocks {div4}]\
           [get_clocks {div8}]\
           [get_clocks {half}]\
           [get_clocks {vco}]]
set_output_delay 0.0000 -clock [get_clocks {ref}] -min -add_delay [get_ports {down}]
set_output_delay 0.2000 -clock [get_clocks {ref}] -max -add_delay [get_ports {down}]
set_output_delay 0.0000 -clock [get_clocks {ref}] -min -add_delay [get_ports {up}]
set_output_delay 0.2000 -clock [get_clocks {ref}] -max -add_delay [get_ports {up}]
set_false_path\
    -from [list [get_ports {div_ratio[0]}]\
           [get_ports {div_ratio[1]}]\
           [get_ports {div_ratio[2]}]\
           [get_ports {div_ratio[3]}]\
           [get_ports {div_ratio[4]}]\
           [get_ports {div_ratio[5]}]\
           [get_ports {div_ratio[6]}]\
           [get_ports {div_ratio[7]}]\
           [get_ports {div_ratio[8]}]\
           [get_ports {div_ratio[9]}]\
           [get_ports {reset_n}]]
###############################################################################
# Environment
###############################################################################
set_load -pin_load 0.0050 [get_ports {down}]
set_load -pin_load 0.0050 [get_ports {feedback_clk}]
set_load -pin_load 0.0050 [get_ports {pll_clk}]
set_load -pin_load 0.0050 [get_ports {test_clk}]
set_load -pin_load 0.0050 [get_ports {up}]
set_input_transition 0.0200 [get_ports {enable}]
set_input_transition 0.0200 [get_ports {ref_clk}]
set_input_transition 0.0200 [get_ports {reset_n}]
set_input_transition 0.1500 [get_ports {vco_clk}]
set_input_transition 0.0200 [get_ports {div_ratio[9]}]
set_input_transition 0.0200 [get_ports {div_ratio[8]}]
set_input_transition 0.0200 [get_ports {div_ratio[7]}]
set_input_transition 0.0200 [get_ports {div_ratio[6]}]
set_input_transition 0.0200 [get_ports {div_ratio[5]}]
set_input_transition 0.0200 [get_ports {div_ratio[4]}]
set_input_transition 0.0200 [get_ports {div_ratio[3]}]
set_input_transition 0.0200 [get_ports {div_ratio[2]}]
set_input_transition 0.0200 [get_ports {div_ratio[1]}]
set_input_transition 0.0200 [get_ports {div_ratio[0]}]
set_input_transition 0.0200 [get_ports {test_div_select[1]}]
set_input_transition 0.0200 [get_ports {test_div_select[0]}]
set_case_analysis 1 [get_ports {enable}]
set_case_analysis 1 [get_ports {test_div_select[0]}]
set_case_analysis 0 [get_ports {test_div_select[1]}]
###############################################################################
# Design Rules
###############################################################################
