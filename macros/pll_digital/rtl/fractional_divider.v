`timescale 1ns/1ps

// Programmable feedback divider behind a fixed full-rate divide-by-two stage.
//
// The external divide word remains Q7.3. At the half-rate clock it is exactly
// represented as Q6.4:
//
//     base_half = floor(integer_div / 2)
//     half_fraction = {integer_div[0], fractional_num}
//
// The fractional schedule chooses base_half or base_half+1 half-rate periods per
// interval. Since each half-rate period is two VCO periods, the requested
// average VCO divide ratio is unchanged:
//
//     integer_div + fractional_num / 2^FRAC_WIDTH
//
// Odd integer ratios alternate between adjacent even VCO-cycle intervals.
// integer_div must remain >= 4, making the minimum half-rate count two.
module fractional_divider #(
    parameter integer DIV_WIDTH = 7,
    parameter integer FRAC_WIDTH = 3
) (
    input  wire                  half_clk,
    input  wire                  reset_n,
    input  wire                  enable,
    input  wire [DIV_WIDTH-1:0]  integer_div,
    input  wire [FRAC_WIDTH-1:0] fractional_num,
    output reg                   feedback_clk
);
    localparam integer HALF_WIDTH = DIV_WIDTH;
    localparam integer HALF_FRAC_WIDTH = FRAC_WIDTH + 1;
    localparam integer MAX_HALF_DIVISOR = 1 << (HALF_WIDTH - 1);
    localparam integer CONTROL_GROUPS = (MAX_HALF_DIVISOR + 7) / 8;
    localparam integer FRACTION_PERIOD = 1 << HALF_FRAC_WIDTH;
    localparam integer FRACTION_GROUPS = (FRACTION_PERIOD + 3) / 4;

    // Replicate controls for each 8-bit bank instead of one global tree.
    // Resetting idle low seeds the first base interval through the same path
    // as later reloads, without a separate startup OR in the countdown bank.
    (* keep = 1 *) reg [CONTROL_GROUPS-1:0] base_reload_idle;
    (* keep = 1 *) reg [CONTROL_GROUPS-1:0] reload_plus_pending;
    reg [MAX_HALF_DIVISOR-1:0] countdown;
    reg [FRACTION_PERIOD-1:0] fraction_pattern;
    (* keep = 1 *) reg [FRACTION_GROUPS-1:0] fraction_initialized;
    (* keep = 1 *) reg [FRACTION_GROUPS-1:0] fraction_advance;
    (* keep = 1 *) reg [FRACTION_GROUPS-1:0] fraction_hold;

    wire reset_b = reset_n && enable;

    // Keep static decoding outside the dynamic reload optimization cone.
    // Bit k represents a remaining count of k+1.
    wire [MAX_HALF_DIVISOR-1:0] base_countdown;
    wire [FRACTION_PERIOD-1:0] fraction_seed;
    (* keep_hierarchy = 1 *) fractional_config_decode #(
        .DIV_WIDTH(DIV_WIDTH), .FRAC_WIDTH(FRAC_WIDTH)
    ) configuration_decode_i (
        .integer_div(integer_div), .fractional_num(fractional_num),
        .mask(base_countdown), .fraction_seed(fraction_seed)
    );
    genvar bit_index;
    wire [MAX_HALF_DIVISOR-1:0] plus_one_countdown =
        {base_countdown[MAX_HALF_DIVISOR-2:0], 1'b0};
    // The fractional carry sequence repeats after 2^HALF_FRAC_WIDTH intervals.
    // Precompute it from static configuration and rotate at terminal count,
    // leaving only a registered bit on the high-speed reload decision path.
    genvar phase_index;
    generate
        for (phase_index = 0; phase_index < FRACTION_PERIOD; phase_index = phase_index + 1) begin : fraction_schedule
            always @(posedge half_clk or negedge reset_b) begin
                if (!reset_b)
                    fraction_pattern[phase_index] <= 1'b0;
                else
                    fraction_pattern[phase_index] <=
                        (!fraction_initialized[phase_index/4] & fraction_seed[phase_index]) |
                        (fraction_advance[phase_index/4] & fraction_pattern[(phase_index+1) % FRACTION_PERIOD]) |
                        (fraction_hold[phase_index/4] & fraction_pattern[phase_index]);
            end
        end
    endgenerate
    genvar fraction_group;
    generate
        for (fraction_group = 0; fraction_group < FRACTION_GROUPS; fraction_group = fraction_group + 1) begin : fraction_startup
            (* keep = 1 *) always @(posedge half_clk or negedge reset_b) begin
                if (!reset_b) begin
                    fraction_initialized[fraction_group] <= 1'b0;
                    fraction_advance[fraction_group] <= 1'b0;
                    fraction_hold[fraction_group] <= 1'b0;
                end else begin
                    fraction_initialized[fraction_group] <= 1'b1;
                    // Minimum count two means reload never inserts bit zero.
                    // These local copies therefore equal countdown[0].
                    fraction_advance[fraction_group] <= countdown[1];
                    fraction_hold[fraction_group] <= !countdown[1];
                end
            end
        end
    endgenerate
    wire use_plus_one = fraction_pattern[0];
    wire [CONTROL_GROUPS-1:0] load_base = ~base_reload_idle;

    // At terminal count the token is bit zero, so shifting it produces zero.
    // Reload can therefore be ORed into the unconditional shift without a
    // terminal-select mux. Both masks are decoded from static configuration.
    generate
        for (bit_index = 0; bit_index < MAX_HALF_DIVISOR; bit_index = bit_index + 1) begin : countdown_bank
            wire shifted = (bit_index == MAX_HALF_DIVISOR-1) ? 1'b0 : countdown[bit_index+1];
            always @(posedge half_clk or negedge reset_b) begin
                if (!reset_b)
                    countdown[bit_index] <= 1'b0;
                else
                    countdown[bit_index] <= shifted |
                        (load_base[bit_index/8] & base_countdown[bit_index]) |
                        (reload_plus_pending[bit_index/8] & plus_one_countdown[bit_index]);
            end
        end
    endgenerate

    // Prepare both reload selects on the lookahead edge. The actual reload
    // then has only a registered select and static ratio mask, not a live
    // terminal-to-fractional-carry-to-bank cascade.
    genvar group_index;
    generate
        for (group_index = 0; group_index < CONTROL_GROUPS; group_index = group_index + 1) begin : reload_controls
            (* keep = 1 *) always @(posedge half_clk or negedge reset_b) begin
                if (!reset_b) begin
                    base_reload_idle[group_index] <= 1'b0;
                    reload_plus_pending[group_index] <= 1'b0;
                end else begin
                    base_reload_idle[group_index] <= !(countdown[1] && !use_plus_one);
                    reload_plus_pending[group_index] <= countdown[1] && use_plus_one;
                end
            end
        end
    endgenerate

    always @(posedge half_clk or negedge reset_b) begin
        if (!reset_b)
            feedback_clk <= 1'b0;
        else
            feedback_clk <= countdown[0];
    end
endmodule

// A synthesis boundary prevents sharing configuration-only predecode gates
// with the registered reload selects, which would add delay to their paths.
module fractional_config_decode #(
    parameter integer DIV_WIDTH = 7,
    parameter integer FRAC_WIDTH = 3
) (
    input wire [DIV_WIDTH-1:0] integer_div,
    input wire [FRAC_WIDTH-1:0] fractional_num,
    output wire [(1 << (DIV_WIDTH-1))-1:0] mask,
    output wire [(1 << (FRAC_WIDTH+1))-1:0] fraction_seed
);
    localparam integer HALF_FRAC_WIDTH = FRAC_WIDTH + 1;
    wire [HALF_FRAC_WIDTH-1:0] half_fraction = {integer_div[0], fractional_num};
    genvar bit_index;
    generate
        for (bit_index = 0; bit_index < (1 << (DIV_WIDTH-1)); bit_index = bit_index + 1) begin : decode
            assign mask[bit_index] = (integer_div[DIV_WIDTH-1:1] == bit_index + 1);
        end
    endgenerate
    genvar phase_index;
    generate
        for (phase_index = 0; phase_index < (1 << HALF_FRAC_WIDTH); phase_index = phase_index + 1) begin : schedule
            wire [HALF_FRAC_WIDTH-1:0] phase_fraction = half_fraction * phase_index;
            wire [HALF_FRAC_WIDTH:0] phase_sum = {1'b0, phase_fraction} + {1'b0, half_fraction};
            assign fraction_seed[phase_index] = phase_sum[HALF_FRAC_WIDTH];
        end
    endgenerate
endmodule
