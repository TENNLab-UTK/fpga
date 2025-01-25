// Copyright (c) 2024-2025 Keegan Dent
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
    export *::*;
    import network_config::*;
    import stream_config::*;
    localparam int PFX_WIDTH = NUM_FLG;
    localparam int SPK_WIDTH = NUM_OUT;
endpackage

module network_sink #(
    parameter int PKT_WIDTH
) (
    // global inputs
    input logic clk,
    input logic arstn,
    // network handshake signals
    input logic net_arstn,
    input logic net_valid,
    input logic net_last,
    output logic net_ready,
    // network signals
    input logic [network_config::NUM_OUT-1:0] net_out,
    // sink handshake signals
    input logic snk_ready,
    output logic snk_valid,
    // sink output
    output logic [PKT_WIDTH-1:0] snk
);
    import stream_config::*;
    import sink_config::*;

    assign net_ready = snk_ready;   // stream source is ready iff sink is ready
    assign snk_valid = net_valid;   // sink is ready iff stream source is valid

    always_comb begin: calc_fin
        snk[PKT_WIDTH - PFX_WIDTH + FIN] = net_last;
    end

    // have to capture net_arstn
    logic rst;
    always_ff @(posedge clk or negedge arstn or negedge net_arstn) begin: set_rst
        if (arstn == 0) begin
            // we don't report a clear for the global reset
            rst <= 0;
        end else if (net_arstn == 0) begin
            rst <= 1;
        end else if (snk_valid && snk_ready) begin
            // clear reported
            rst <= 0;
        end
    end

    always_comb begin: calc_snk
        for (int i = 0; i < PKT_WIDTH; i++)
            snk[PKT_WIDTH - PFX_WIDTH - i - 1] = net_out[i];
    end
endmodule
