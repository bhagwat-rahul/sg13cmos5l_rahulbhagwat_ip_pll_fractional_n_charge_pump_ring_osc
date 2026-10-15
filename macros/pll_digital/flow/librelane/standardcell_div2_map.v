// Standard-cell-only alternative to the custom TSPC front end.
// Keep Q's distribution load separate from Q_N's local toggle feedback.
(* techmap_celltype = "high_speed_div2 async_toggle_ff" *)
module standardcell_toggle_map (
    input wire clk,
    input wire reset_b,
    output wire q
);
    wire q_n;
    sg13cmos5l_dfrbp_2 _TECHMAP_REPLACE_ (
        .CLK(clk),
        .RESET_B(reset_b),
        .D(q_n),
        .Q(q),
        .Q_N(q_n)
    );
endmodule

// Restore the analog edge before the full-rate prescaler's clock pin.
// _4/_8 variants failed routed SS pulse-width checks despite passing setup.
(* techmap_celltype = "vco_clock_buffer" *)
module standardcell_vco_clock_buffer_map (
    input wire a,
    output wire y
);
    sg13cmos5l_buf_16 _TECHMAP_REPLACE_ (.A(a), .X(y));
endmodule

(* techmap_celltype = "half_rate_clock_buffer" *)
module standardcell_half_clock_buffer_map (
    input wire a,
    output wire y
);
    sg13cmos5l_buf_16 _TECHMAP_REPLACE_ (.A(a), .X(y));
endmodule
