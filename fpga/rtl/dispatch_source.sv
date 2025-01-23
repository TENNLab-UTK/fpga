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
        NOP = 0,
        RUN,
        SPK,
        CLR,
        SPK_PRDC,
        NUM_OPS   // not a valid opcode, purely for counting
    } opcode_t;
    localparam int OPC_WIDTH = $clog2(NUM_OPS);
    // important to note that a NET_NUM_INP of 1 would make the spk width = charge width
    localparam int SPK_WIDTH = $clog2(NET_NUM_INP) + NET_CHARGE_WIDTH;
    localparam int SPK_PRDC_WIDTH = $clog2(NET_NUM_INP) + NET_CHARGE_WIDTH + $clog2(NET_MAX_PERIOD+1) + $clog2(NET_MAX_NUM_PERIODS+1);
endpackage

import source_config::*;

module network_source #(
    parameter int RUN_WIDTH
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
    opcode_t op;

    always_comb begin : calc_op
        if (src_valid && src_ready)
            op = opcode_t'(src[(`SRC_WIDTH - 1) -: OPC_WIDTH]);
        else
            op = NOP;
    end

    logic [RUN_WIDTH-1:0] run_counter;
    assign src_ready = (run_counter <= 1);
    assign net_valid = (run_counter > 0);

    always_ff @(posedge clk or negedge arstn) begin: set_run_counter
        if (arstn == 0) begin
            run_counter <= 0;
        end else begin
            if (op == RUN) begin
                // RUN op with a '0' run value is assumed to be a single cycle
                run_counter <= `max(src[(`SRC_WIDTH - OPC_WIDTH - 1) -: RUN_WIDTH], 1);
            end else if (net_valid && net_ready) begin
                run_counter <= run_counter - 1;
            end
        end
    end

    logic [$clog2(NET_NUM_INP + 1) - 1 : 0] inp_idx;
    generate
        if (SPK_WIDTH == NET_CHARGE_WIDTH)
            assign inp_idx = 0;
        else
            assign inp_idx = src[(`SRC_WIDTH - OPC_WIDTH - 1) -: $clog2(NET_NUM_INP)];
    endgenerate

    logic signed [NET_CHARGE_WIDTH-1:0] inp_val;
    assign inp_val = src[(`SRC_WIDTH - OPC_WIDTH - $clog2(NET_NUM_INP) - 1) -: NET_CHARGE_WIDTH];

    logic signed [$clog2(NET_MAX_PERIOD+1)-1:0] inp_period;
    assign inp_period = src[(`SRC_WIDTH - OPC_WIDTH - $clog2(NET_NUM_INP) - NET_CHARGE_WIDTH - 1) -: $clog2(NET_MAX_PERIOD+1)];

    logic signed [$clog2(NET_MAX_NUM_PERIODS+1)-1:0] inp_num_periods;
    assign inp_num_periods = src[(`SRC_WIDTH - OPC_WIDTH - $clog2(NET_NUM_INP) - NET_CHARGE_WIDTH - $clog2(NET_MAX_PERIOD+1) - 1) -: $clog2(NET_MAX_NUM_PERIODS+1)];

    // Array used for applying charge periodically to desired inputs; each index corresponds to an input neuron; each value is a bus that holds both the charge to apply and the period to apply it at
    logic [NET_CHARGE_WIDTH + $clog2(NET_MAX_PERIOD+1) - 1 : 0] prdc_inp [0:NET_NUM_INP-1];

    // Array used for counting timesteps since previous periodic input for each input neuron
    logic [$clog2(NET_MAX_PERIOD)-1:0] prdc_inp_counters [0:NET_NUM_INP-1];

    // Array used for counting number of periods remaining for periodic inputs for each input neuron
    logic [$clog2(NET_MAX_NUM_PERIODS)-1:0] prdc_inp_num_prds_counters [0:NET_NUM_INP-1]; 

    always_ff @(posedge clk or negedge arstn) begin: set_prdc_inp
        if (arstn == 0) begin
            for (int i = 0; i < NET_NUM_INP; i++)
                prdc_inp[i] <= 0;
        end else if (op == SPK_PRDC) begin
            prdc_inp[inp_idx] <= {inp_val, inp_period};
        end
    end

    always_ff @(posedge clk or negedge arstn) begin: set_prdc_inp_counters
        if (arstn == 0) begin
            for (int i = 0; i < NET_NUM_INP; i++)
                prdc_inp_counters[i] <= 0;
        end else begin
            for (int i = 0; i < NET_NUM_INP; i++) begin
                if (op == SPK_PRDC && inp_idx == i) begin
                    prdc_inp_counters[i] <= 0;
                end else if (net_valid && net_ready && prdc_inp[i][0 +: $clog2(NET_MAX_PERIOD+1)] != 0) begin
                    prdc_inp_counters[i] <= (prdc_inp_counters[i] == prdc_inp[i][0 +: $clog2(NET_MAX_PERIOD+1)]-1) ? 0 : prdc_inp_counters[i]+1;
                end
            end
        end
    end

    always_ff @(posedge clk or negedge arstn) begin: set_prdc_inp_num_prds_counters
        if (arstn == 0) begin
            for (int i = 0; i < NET_NUM_INP; i++)
                prdc_inp_num_prds_counters[i] <= 0;
        end else begin
            for (int i = 0; i < NET_NUM_INP; i++) begin
                if (op == SPK_PRDC && inp_idx == i) begin
                    prdc_inp_num_prds_counters[i] <= (inp_num_periods == 0) ? 0 : inp_num_periods-1;
                end else if (net_valid && net_ready && prdc_inp[i][0 +: $clog2(NET_MAX_PERIOD+1)] != 0 && prdc_inp_counters[i] == prdc_inp[i][0 +: $clog2(NET_MAX_PERIOD+1)]-1 && prdc_inp_num_prds_counters[i] != 0) begin
                    prdc_inp_num_prds_counters[i] <= prdc_inp_num_prds_counters[i]-1;
                end
            end
        end
    end

    always_ff @(posedge clk or negedge arstn) begin: set_net_inp
        if (arstn == 0) begin
            net_arstn <= 0;
            for (int i = 0; i < NET_NUM_INP; i++)
                net_inp[i] <= 0;
        end else begin
            if ((net_valid && net_ready) || op == CLR) begin
                // reset inputs every time network is run
                for (int i = 0; i < NET_NUM_INP; i++)
                    net_inp[i] <= 0;
            end
            case (op)
                CLR:
                    net_arstn <= 0;
                SPK: begin
                    net_arstn <= 1;
                    // set inputs on a spike dispatch
                    net_inp[inp_idx] <= inp_val;
                end
                SPK_PRDC: begin
                    net_arstn <= 1;
                    if (inp_num_periods != 0)
                        net_inp[inp_idx] <= inp_val;
                end
                default: begin
                    net_arstn <= 1;
                    if (net_valid && net_ready) begin
                        for (int i = 0; i < NET_NUM_INP; i++) begin
                            if (prdc_inp[i][0 +: $clog2(NET_MAX_PERIOD+1)] != 0 && prdc_inp_counters[i] == prdc_inp[i][0 +: $clog2(NET_MAX_PERIOD+1)]-1 && prdc_inp_num_prds_counters[i] != 0) begin
                                net_inp[i] <= prdc_inp[i][(NET_CHARGE_WIDTH + $clog2(NET_MAX_PERIOD+1) - 1) -: NET_CHARGE_WIDTH];
                            end
                        end
                    end
                end
            endcase
        end
    end

endmodule