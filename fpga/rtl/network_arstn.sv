// Copyright (c) 2025 Keegan Dent
//
// This source describes Open Hardware and is licensed under the CERN-OHL-W v2
// You may redistribute and modify this documentation and make products using
// it under the terms of the CERN-OHL-W v2 (https:/cern.ch/cern-ohl).
//
// This documentation is distributed WITHOUT ANY EXPRESS OR IMPLIED WARRANTY,
// INCLUDING OF MERCHANTABILITY, SATISFACTORY QUALITY AND FITNESS FOR A
// PARTICULAR PURPOSE. Please see the CERN-OHL-W v2 for applicable conditions.

module network_arstn (
    input logic clk,
    input logic arstn,
    input logic net_clear,
    output logic net_arstn
);
    // "Now watch this (half-clock) drive!"
    // clear_mask is clear delayed by a half-clock
    logic clear_mask;
    always_ff @(negedge clk or negedge arstn) begin : nset_rstn
        if (arstn == 0) begin
            clear_mask <= 0;
        end else begin
            clear_mask <= net_clear;
        end
    end

    // net_arstn asserted low for half clock when net_clear asserted
    // or whenever net_arstn asserted low of course
    assign net_arstn = arstn && !(net_clear && !clear_mask);
endmodule