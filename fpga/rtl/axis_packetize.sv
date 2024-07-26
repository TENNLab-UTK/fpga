// Copyright (c) 2024 Bryson Gullett
//
// This source describes Open Hardware and is licensed under the CERN-OHL-W v2
// You may redistribute and modify this documentation and make products using
// it under the terms of the CERN-OHL-W v2 (https:/cern.ch/cern-ohl).
//
// This documentation is distributed WITHOUT ANY EXPRESS OR IMPLIED WARRANTY,
// INCLUDING OF MERCHANTABILITY, SATISFACTORY QUALITY AND FITNESS FOR A
// PARTICULAR PURPOSE. Please see the CERN-OHL-W v2 for applicable conditions.

module axis_packetize #(
    // Number of different tdata values sent per packet
    parameter PKT_SIZE = 4,
    // Max number of clock cycles a packet is allowed to have
    parameter MAX_CLK_CYCLES_PER_PKT = 10
) (
    input logic clk,
    input logic arstn,
    input logic tvalid,
    input logic tready,
    output logic last_cycle,
    output logic last_pkt
);

    logic [$clog2(PKT_SIZE)-1:0] data_counter;
    logic [$clog2(MAX_CLK_CYCLES_PER_PKT)-1:0] clk_counter;

    always_ff @(posedge clk or negedge arstn) begin: axis_packetize_counters
        if (arstn == 0) begin
            data_counter <= 0;
            clk_counter <= 1;
        end else begin
            if ((last_cycle | last_pkt) & tvalid & tready) begin
                data_counter <= 0;
                clk_counter <= 1;
            end
            else begin
                if (data_counter >= 1 && data_counter < MAX_CLK_CYCLES_PER_PKT-1) begin
                    clk_counter <= clk_counter + 1;
                end
                if (tvalid & tready) begin
                    data_counter <= data_counter + 1;
            end
            end
        end
    end

    assign last_cycle = (clk_counter == MAX_CLK_CYCLES_PER_PKT-1) ? 1 : 0;
    assign last_pkt = (data_counter == PKT_SIZE-1) ? 1 : 0;

endmodule