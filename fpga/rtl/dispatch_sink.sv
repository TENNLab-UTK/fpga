// Copyright (c) 2024 Keegan Dent
//
// This source describes Open Hardware and is licensed under the CERN-OHL-W v2
// You may redistribute and modify this documentation and make products using
// it under the terms of the CERN-OHL-W v2 (https:/cern.ch/cern-ohl).
//
// This documentation is distributed WITHOUT ANY EXPRESS OR IMPLIED WARRANTY,
// INCLUDING OF MERCHANTABILITY, SATISFACTORY QUALITY AND FITNESS FOR A
// PARTICULAR PURPOSE. Please see the CERN-OHL-W v2 for applicable conditions.

package sink_config;
    import network_config::*;
    localparam int SNK_WIDTH = $clog2(NET_NUM_OUT + 1);
endpackage

import sink_config::*;

module network_sink (
    // global inputs
    input logic clk,
    input logic arstn,
    // network handshake signals
    input logic net_valid,
    output logic net_ready,
    // network signals
    input logic [NET_NUM_OUT-1:0] net_out,
    // sink handshake signals
    input logic snk_ready,
    output logic snk_valid,
    // sink output
    output logic [SNK_WIDTH-1:0] snk
);

    // the snk_queue is a little bit complicated it holds:
    // 1. the indices of the net outputs that fired in descending order
    // 2. the number of net outputs that fired
    // of these, 2 is always populated, and the queue is sent out back-to-front
    logic [$clog2(NET_NUM_OUT + 2)-1:0] snk_counter;
    logic [$clog2(NET_NUM_OUT + 2)-1:0] next_snk_counter;
    logic [SNK_WIDTH-1:0] snk_queue [0:(NET_NUM_OUT)];   // not -1 because of num_out
    logic [SNK_WIDTH-1:0] next_snk_queue [0:(NET_NUM_OUT)];

    // FIXME: This logic is not working.
    // There might not be a way to accomplish single-cycle queue population in synthesizeable code.
    always_comb begin : calc_next_snk
        int i = 0;
        // loop in reverse so we can count down queue positions using snk_counter
        for (int j = NET_NUM_OUT - 1; j >= 0; j--) begin
            if (net_out[j]) begin
                next_snk_queue[i] = j;
                i++;
            end
        end
        next_snk_queue[i] = i;
        next_snk_counter = i + 1;
    end

    always_ff @(posedge clk or negedge arstn) begin: set_snk_queue
        if (arstn == 0) begin
            foreach (snk_queue[i])
                snk_queue[i] <= 0;
        end else if (net_valid && net_ready) begin
            snk_queue <= next_snk_queue;
        end
    end

    assign snk_valid = (snk_counter > 0);
    assign net_ready = (snk_counter == 0);

    always_ff @(posedge clk or negedge arstn) begin : set_snk_counter
        if (arstn == 0) begin
            snk_counter <= 0;
        end else begin
            if (snk_valid && snk_ready) begin
                snk_counter <= snk_counter - 1;
            end else if (net_valid && net_ready) begin
                snk_counter <= next_snk_counter;
            end
        end
    end

    assign snk = snk_queue[snk_counter - 1];

endmodule