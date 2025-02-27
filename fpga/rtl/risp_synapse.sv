// Copyright (c) 2024 Keegan Dent
//
// This source describes Open Hardware and is licensed under the CERN-OHL-W v2
// You may redistribute and modify this documentation and make products using
// it under the terms of the CERN-OHL-W v2 (https:/cern.ch/cern-ohl).
//
// This documentation is distributed WITHOUT ANY EXPRESS OR IMPLIED WARRANTY,
// INCLUDING OF MERCHANTABILITY, SATISFACTORY QUALITY AND FITNESS FOR A
// PARTICULAR PURPOSE. Please see the CERN-OHL-W v2 for applicable conditions.

module risp_synapse #(
    parameter int WEIGHT,
    parameter int DELAY,
    parameter int CHARGE_WIDTH,
    parameter bit FIRE_LIKE_RAVENS=0
) (
    input logic clk,
    input logic arstn,
    input logic en,
    input logic inp,
    output logic signed [CHARGE_WIDTH-1:0] out
);
    localparam TRUE_DELAY = DELAY - FIRE_LIKE_RAVENS;
    logic fifo [TRUE_DELAY:0];

    always_comb fifo[0] = inp;

    assign out = fifo[TRUE_DELAY] ? WEIGHT : 0;

    genvar i;
    generate
        // starts with 1 so we don't generate a register for 0 delay
        for (i = 1; i < TRUE_DELAY + 1; ++i) begin: delay_chain
            always_ff @(posedge clk or negedge arstn) begin
                if (arstn == 0) begin
                    fifo[i] <= 0;
                end else if (en) begin
                    fifo[i] <= fifo[i-1];
                end
            end
        end
    endgenerate
endmodule