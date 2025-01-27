// Copyright (c) 2024-2025 Keegan Dent
//
// This source describes Open Hardware and is licensed under the CERN-OHL-W v2
// You may redistribute and modify this documentation and make products using
// it under the terms of the CERN-OHL-W v2 (https:/cern.ch/cern-ohl).
//
// This documentation is distributed WITHOUT ANY EXPRESS OR IMPLIED WARRANTY,
// INCLUDING OF MERCHANTABILITY, SATISFACTORY QUALITY AND FITNESS FOR A
// PARTICULAR PURPOSE. Please see the CERN-OHL-W v2 for applicable conditions.

package sink_config;
    export *::*;
    import network_config::*;
    import dispatch_config::*;

    localparam int PFX_WIDTH = $clog2(NUM_OPC);
    // important to note that a NET_NUM_OUT of 1 would make the spk width = 0, making out_idx implicit
    localparam int SPK_WIDTH = $clog2(NUM_OUT);
endpackage

module network_sink #(
    parameter int PKT_WIDTH
) (
    // global inputs
    input logic clk,
    input logic arstn,
    // network handshake signals
    input logic net_valid,
    input logic net_last,
    output logic net_ready,
    // network signals
    input logic net_arstn,
    input logic [network_config::NUM_OUT-1:0] net_out,
    // sink handshake signals
    input logic snk_ready,
    output logic snk_valid,
    // sink output
    output logic [PKT_WIDTH-1:0] snk
);
    import dispatch_config::*;
    import sink_config::*;

    typedef enum logic [1:0] {IDLE, RUNS, SPKS, CLRD} state_t;
    state_t curr_state, next_state;

    assign net_ready = curr_state == IDLE;

    logic rst; // latch set when net_arstn == 0, reset when clear dispatched

    always_ff @(posedge clk or negedge arstn or negedge net_arstn) begin: set_rst
        if (arstn == 0)
            rst <= 0;
        else if (net_arstn == 0)
            rst <= 1;
        else if (curr_state == CLRD && next_state != CLRD)
            rst <= 0;
    end

    localparam int RUN_WIDTH = PKT_WIDTH - PFX_WIDTH;
    logic [RUN_WIDTH-1:0] run_counter, runs;

    always_ff @(posedge clk or negedge arstn) begin: set_run_counter
        if (arstn == 0) begin
            run_counter <= 0;
            runs <= 0;
        end else begin
            if (curr_state == IDLE && next_state != IDLE) begin
                // replace run received while sending a dispatch
                run_counter <= net_valid;
                runs <= run_counter;
            end else if (net_valid && net_ready) begin
                run_counter <= run_counter + 1;
            end
        end
    end

    logic [NUM_OUT-1:0] fires;
    logic last;

    always_ff @(posedge clk or negedge arstn) begin: set_data
        if (arstn == 0) begin
            fires <= 0;
            last <= 0;
        end else if (net_valid && net_ready) begin
            fires <= net_out;
            last <= net_last;
        end else if (next_state == IDLE) begin
            fires <= 0;
            last <= 0;
        end
    end

    logic [$clog2(NUM_OUT + 1) : 0] fire_counter;

    always_ff @(posedge clk or negedge arstn) begin: set_fire_counter
        if (arstn == 0) begin
            fire_counter <= 0;
        end else begin
            if (curr_state != SPKS && next_state == SPKS)
                fire_counter <= NUM_OUT;
            else if (curr_state == SPKS && snk_ready)
                fire_counter <= fire_counter - 1;
        end
    end

    always_comb begin: calc_snk
        snk = 0;
        snk_valid = 0;
        case (curr_state)
            RUNS: begin
                snk[(PKT_WIDTH - 1) -: PFX_WIDTH] = last ? FIN : RUN;
                snk[PKT_WIDTH - PFX_WIDTH - 1 : 0] = runs;
                snk_valid = 1;
            end
            SPKS: begin
                snk[(PKT_WIDTH - 1) -: PFX_WIDTH] = SPK;
                if (SPK_WIDTH > 0)
                    snk[(PKT_WIDTH - PFX_WIDTH - 1) -: SPK_WIDTH] = NUM_OUT - fire_counter;
                snk_valid = fires[NUM_OUT - fire_counter];
            end
            CLRD: begin
                snk[(PKT_WIDTH - 1) -: PFX_WIDTH] = CLR;
                snk_valid = 1;
            end
        endcase
    end

    always_comb begin: calc_next_states
        next_state = curr_state;
        case (curr_state)
            IDLE: begin
                if (rst)
                    next_state = CLRD;
                if (net_valid && |net_out)
                    next_state = SPKS;
                if (run_counter > 0 && (rst || (
                    net_valid && (|net_out || net_last || &run_counter)
                )))
                    next_state = RUNS;
            end
            RUNS: begin
                if (snk_ready) begin
                    next_state = IDLE;
                    if (rst)
                        next_state = CLRD;
                    if (|fires)
                        next_state = SPKS;
                end
            end
            SPKS: begin
                if (snk_ready) begin
                    next_state = IDLE;
                    if (rst)
                        next_state = CLRD;
                    if (fire_counter > 1)
                        next_state = SPKS;
                end
            end
            CLRD: begin
                if (snk_ready)
                    next_state = IDLE;
            end
        endcase
    end

    always_ff @(posedge clk or negedge arstn) begin: set_curr_state
        if (arstn == 0) begin
            curr_state <= IDLE;
        end else begin
            curr_state <= next_state;
        end
    end
endmodule
