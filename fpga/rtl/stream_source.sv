// Copyright (c) 2024 Keegan Dent
//
// This source describes Open Hardware and is licensed under the CERN-OHL-W v2
// You may redistribute and modify this documentation and make products using
// it under the terms of the CERN-OHL-W v2 (https:/cern.ch/cern-ohl).
//
// This documentation is distributed WITHOUT ANY EXPRESS OR IMPLIED WARRANTY,
// INCLUDING OF MERCHANTABILITY, SATISFACTORY QUALITY AND FITNESS FOR A
// PARTICULAR PURPOSE. Please see the CERN-OHL-W v2 for applicable conditions.

`include "macros.svh"

package source_config;
    import network_config::*;

    typedef enum {
        NOM = 0,
        CLR
    } opcode_t;
    localparam int OPC_WIDTH = 1;
    // important to note that a NET_NUM_INP of 1 would make the spk width = charge width
    localparam int SPK_WIDTH = NET_NUM_INP * NET_CHARGE_WIDTH;
endpackage

import source_config::*;

module network_source #(
    parameter int RUN_WIDTH // unused
) (
    // global inputs
    input logic clk,
    input logic arstn,
    // source handshake signals
    input logic src_valid,
    output logic src_ready,
    // source input
    input logic [`SRC_WIDTH-1:0] src,
    // network handshake signals
    input logic net_ready,
    output logic net_valid,
    // network signals
    output logic net_arstn,
    output logic signed [NET_CHARGE_WIDTH-1:0] net_inp [0:NET_NUM_INP-1]
);


    always_ff @(posedge clk or negedge arstn) begin: set_net_valid
        if (arstn == 0) begin
            net_valid <= 0;
        end else begin
            net_valid <= src_valid;         // net data is valid iff stream source is valid
        end
    end

    logic net_en;
    assign net_en = src_valid && net_ready;

    logic was_ready;

    always_ff @(posedge clk or negedge arstn) begin: set_was_ready
        if (arstn == 0) begin
            was_ready <= 0;
        end else begin
            if (net_en && !was_ready) begin
                was_ready <= 1;             // special condition to prevent additional ready cycle for fast sources
            end else begin
                was_ready <= 0;
            end
        end
    end

    assign src_ready = net_ready && !was_ready;

    assign net_arstn = (arstn == 0) ? 0 : !(net_en && (opcode_t'(src[(`SRC_WIDTH - 1) -: OPC_WIDTH]) == CLR));

    always_ff @(posedge clk or negedge arstn) begin: set_net_inp
        if (arstn == 0) begin
            foreach (net_inp[i])
                net_inp[i] <= 0;
        end else begin
            if (net_en) begin
                foreach (net_inp[i])
                    net_inp[i] <= src[(`SRC_WIDTH - OPC_WIDTH - (i * NET_CHARGE_WIDTH) - 1) -: NET_CHARGE_WIDTH];
            end
        end
    end


endmodule