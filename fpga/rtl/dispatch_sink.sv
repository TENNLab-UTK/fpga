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
    logic [SNK_WIDTH-1:0] snk_queue [0:(NET_NUM_OUT)];   // not -1 because of num_out

    logic [$clog2(NET_NUM_OUT + 2)-1:0] snk_counter, pop_counter;
    assign snk_valid = (pop_counter == 0) && (snk_counter > 0);
    assign net_ready = (pop_counter == 0) && (snk_counter == 0);

    logic pop_fire = net_out[NET_NUM_OUT + 1 - pop_counter];

    always_ff @(posedge clk or negedge arstn) begin: set_pop_counter
        if (arstn == 0) begin
            pop_counter <= 0;
        end else begin
            if (net_valid && net_ready) begin
                pop_counter <= NET_NUM_OUT + 1;
            end else if (pop_counter > 0) begin
                pop_counter <= pop_counter - 1;
            end
        end
    end

    always_ff @(posedge clk or negedge arstn) begin: set_snk_queue
        if (arstn == 0) begin
            foreach (snk_queue[i])
                snk_queue[i] <= 0;
        end else begin
            if (net_valid && net_ready) begin
                foreach (snk_queue[i])
                    snk_queue[i] <= 0;
            end else if (pop_counter > 0) begin
                if (pop_counter == 1) begin
                    snk_queue[snk_counter] <= snk_counter;
                end else if (pop_fire) begin
                    snk_queue[snk_counter] <= NET_NUM_OUT + 1 - pop_counter;
                end
            end
        end
    end

    always_ff @(posedge clk or negedge arstn) begin: set_snk_counter
        if (arstn == 0) begin
            snk_counter <= 0;
        end else begin
            if (pop_fire && (pop_counter > 1)) begin
                snk_counter <= snk_counter + 1;
            end esle if (snk_valid && snk_ready) begin
                snk_counter <= snk_counter - 1;
            end
        end
    end

    assign snk = snk_queue[snk_counter - 1];

endmodule