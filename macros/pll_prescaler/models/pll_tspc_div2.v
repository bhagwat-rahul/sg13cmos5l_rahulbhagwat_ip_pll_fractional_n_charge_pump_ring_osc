`timescale 1ns/1ps

// Fixed divide-by-two functional-pin black box for synthesis and physical
// implementation. VDD and VSS are physical LEF pins connected by the P&R
// global-power network. The transistor implementation and mapping are pending.
(* blackbox *)
module pll_tspc_div2 (
    input  wire CLK,
    input  wire RESET_B,
    output wire Q
);
endmodule
