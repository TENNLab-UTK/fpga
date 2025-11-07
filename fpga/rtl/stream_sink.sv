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
    // network signals
    input logic net_run,
    input logic net_sync,
    input logic net_clear,
    output logic net_ready,
    input logic [network_config::NUM_OUT-1:0] net_out,
    // sink handshake signals
    input logic snk_ready,
    output logic snk_valid,
    // sink output
    output logic [PKT_WIDTH-1:0] snk
);
    import network_config::*;
    import stream_config::*;
    import sink_config::*;

    assign net_ready = snk_ready;   // stream source is ready iff sink is ready
    assign snk_valid = net_run;      // sink is ready iff network has run

    logic sync;
    always_ff @(posedge clk or negedge arstn) begin: set_sync
        if (arstn == 0) begin
            sync <= 0;
        end else begin
            if (snk_valid && snk_ready)
                sync <= 0;
            else if (net_sync)
                sync <= 1;
        end
    end

    logic clear;
    always_ff @(posedge clk or negedge arstn) begin: set_clear
        if (arstn == 0) begin
            clear <= 0;
        end else begin
            if (snk_valid && snk_ready)
                clear <= 0;
            else if (net_clear)
                clear <= 1;
        end
    end

    always_comb begin: calc_snk
        snk = 0;
        snk[PKT_WIDTH - SNC - 1] = sync || net_sync;
        snk[PKT_WIDTH - CLR - 1] = clear || net_clear;
        for (int i = 0; i < NUM_OUT; i++)
            snk[PKT_WIDTH - PFX_WIDTH - i - 1] = net_out[i];
    end
endmodule
