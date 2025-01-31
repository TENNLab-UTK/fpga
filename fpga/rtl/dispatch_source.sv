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

package source_config;
    export *::*;
    import network_config::*;
    import dispatch_config::*;
    localparam int PFX_WIDTH = $clog2(NUM_OPC);
    // important to note that a NUM_INP of 1 would leave 0 bits for input neuron index
    localparam int SPK_WIDTH = $clog2(NUM_INP) + CHARGE_WIDTH;
endpackage

module network_source #(
    parameter int PKT_WIDTH
) (
    // global inputs
    input logic clk,
    input logic arstn,
    // source handshake signals
    input logic src_valid,
    output logic src_ready,
    // source input
    input logic [PKT_WIDTH-1:0] src,
    // network handshake signals
    input logic net_ready,
    output logic net_valid,
    // network signals
    output logic net_arstn,
    output logic net_sync,
    output logic signed [network_config::CHARGE_WIDTH-1:0] net_inp [0:network_config::NUM_INP-1]
);
    import dispatch_config::*;
    import source_config::*;
    localparam int RUN_WIDTH = PKT_WIDTH - PFX_WIDTH;
    opcode_t op;

    always_comb begin : calc_op
        op = opcode_t'(src[(PKT_WIDTH - 1) -: PFX_WIDTH]);
    end

    logic [RUN_WIDTH-1:0] run_counter;
    assign src_ready = (run_counter == 0) || (run_counter == 1 && net_ready);
    assign net_valid = (run_counter > 0);

    always_ff @(posedge clk or negedge arstn) begin: set_run_counter
        if (arstn == 0) begin
            run_counter <= 0;
        end else begin
            if (src_valid && src_ready && (op == RUN || op == SNC)) begin
                run_counter <= src[(PKT_WIDTH - PFX_WIDTH - 1) : 0];
            end else if (net_valid && net_ready) begin
                run_counter <= run_counter - 1;
            end
        end
    end

    logic sync;
    assign net_sync = sync && run_counter == 1;

    always_ff @(posedge clk or negedge arstn) begin: set_last
        if (arstn == 0) begin
            sync <= 0;
        end else if (src_valid && src_ready && op == SNC) begin
            sync <= 1;
        end else if (net_valid && net_ready && net_sync) begin
            sync <= 0;
        end
    end

    always_ff @(posedge clk or negedge arstn) begin: set_net_arstn
        if (arstn == 0) begin
            net_arstn <= 0;
        end else if (src_valid && src_ready && op == CLR) begin
            net_arstn <= 0;
        end else begin
            net_arstn <= 1;
        end
    end

    logic [$clog2(NUM_INP + 1) - 1 : 0] inp_idx;
    generate
        if (NUM_INP <= 1)
            assign inp_idx = 0;
        else
            assign inp_idx = src[(PKT_WIDTH - PFX_WIDTH - 1) -: $clog2(NUM_INP)];
    endgenerate

    logic signed [CHARGE_WIDTH-1:0] inp_val;
    assign inp_val = src[(PKT_WIDTH - PFX_WIDTH - $clog2(NUM_INP) - 1) -: CHARGE_WIDTH];

    always_ff @(posedge clk or negedge arstn) begin: set_net_inp
        if (arstn == 0) begin
            for (int i = 0; i < NUM_INP; i++)
                net_inp[i] <= 0;
        end else begin
            if (net_valid && net_ready) begin
                for (int i = 0; i < NUM_INP; i++)
                    net_inp[i] <= 0;
            end else if (src_valid && src_ready) begin
                case (op)
                    SPK:
                        net_inp[inp_idx] <= inp_val;
                    CLR: begin
                        for (int i = 0; i < NUM_INP; i++)
                            net_inp[i] <= 0;
                    end
                endcase
            end
        end
    end
endmodule
