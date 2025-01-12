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

package sink_config;
    import network_config::*;
    localparam int SNK_OPC_WIDTH = 0;
    localparam int SNK_SPK_WIDTH = NET_NUM_OUT;
endpackage

module network_sink
import network_config::*;
import sink_config::*;
#(
    parameter int SNK_RUN_WIDTH // unused
) (
    // global inputs
    input logic clk,
    input logic arstn,
    // network handshake signals
    input logic net_valid,
    input logic net_last,   // unused
    output logic net_ready,
    // network signals
    input logic [NET_NUM_OUT-1:0] net_out,
    // sink handshake signals
    input logic snk_ready,
    output logic snk_valid,
    // sink output
    output logic [`SNK_WIDTH-1:0] snk
);
    assign net_ready = snk_ready;   // stream source is ready iff sink is ready
    assign snk_valid = net_valid;   // sink is ready iff stream source is valid
    always_comb begin: calc_snk
        for (int i = 0; i < `SNK_WIDTH; i++)
            snk[`SNK_WIDTH - i - 1] = net_out[i];
    end
endmodule
