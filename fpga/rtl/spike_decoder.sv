// Copyright (c) 2024 Keegan Dent
//
// This source describes Open Hardware and is licensed under the CERN-OHL-W v2
// You may redistribute and modify this documentation and make products using
// it under the terms of the CERN-OHL-W v2 (https:/cern.ch/cern-ohl).
//
// This documentation is distributed WITHOUT ANY EXPRESS OR IMPLIED WARRANTY,
// INCLUDING OF MERCHANTABILITY, SATISFACTORY QUALITY AND FITNESS FOR A
// PARTICULAR PURPOSE. Please see the CERN-OHL-W v2 for applicable conditions.

package decoder_config;
    import network_config::*;

    localparam int SNK_WIDTH = NET_NUM_OUT * DECODER_VAL_MAX_WIDTH;
endpackage

import decoder_config::*;

module network_sink (
    input logic clk,
    input logic arstn,
    input logic net_valid,
    input logic [NET_NUM_OUT-1:0] net_out,
    input logic snk_ready,
    input logic out_ready,
    output logic net_ready,
    output logic snk_valid,
    output logic [SNK_WIDTH-1:0] snk
);
    logic [$clog2(MAX_RUN_TIME)-1:0] timestep; 
    logic [$clog2(MAX_RUN_TIME)-1:0] out_counts [0:NET_NUM_OUT-1];
    logic signed [$clog2(MAX_RUN_TIME+1)-1:0] out_last_fires [0:NET_NUM_OUT-1];

    assign net_ready = snk_ready;
    assign snk_valid = out_ready;

    // TODO: Implement following constants in generated network file:
    // MAX_RUN_TIME
    // DECODER_VAL_MAX_WIDTH
    // NUM_DECODERS
    // DECODER_NUM_BINS
    // DECODER_TYPES
    // DECODER_STARTING_NEURONS
    // DECODER_TTLS_START_ATS
    // DECODER_DIVISORS
    // DECODER_FLIPS
    // DECODER_BINNING_STYLES
    // DECODER_MIN_VALS
    // DECODER_MAX_VALS

    // Combinational logic used to decode an output value for each spike encoder
    always_comb begin: decode_values        
        logic signed [$clog2(MAX_RUN_TIME+1)-1:0] out_data;     // Either output neuron spike count or output neuron last fire time (may be adjusted according to divisor, ttls_start_at, flip parameters)
        logic signed [$clog2(MAX_RUN_TIME+1)-1:0] win_out_data; // For decoders with multiple bins, keep track of the winning bin's out_data value (one bin corresponds to one output neuron)
        logic signed [(2*DECODER_VAL_MAX_WIDTH)-1:0] val;       // Decoded output value for the current spike decoder

        // Decode an output value for each spike encoder
        for (int i = 0; i < NUM_DECODERS; i++) begin

            // Loop through all of spike decoder's output neurons (bins)
            for (int j = 0; j < DECODER_NUM_BINS[i]; j++) begin
                
                // Find either output neuron spike count or last time to spike depending on decoder type
                case (DECODER_TYPES[i])
                    RATE:
                        out_data = out_counts[DECODER_STARTING_NEURONS[i]+j];
                    TLLS:
                        if (out_last_fires[DECODER_STARTING_NEURONS[i]+j] == -1) begin
                            out_data = -1;
                        end else if (out_last_fires[DECODER_STARTING_NEURONS[i]+j] < DECODER_TTLS_START_ATS[i]) begin
                            out_data = 0;
                        end else begin
                            out_data = out_last_fires[DECODER_STARTING_NEURONS[i]+j] - DECODER_TTLS_START_ATS[i];
                        end
                    default:
                        out_data = -1
                endcase

                // Adjust for custom decoder divisor paramter
                if (out_data > DECODER_DIVISORS[i]) begin
                    out_data = DECODER_DIVISORS[i];
                end

                // Adjust for decoder flip parameter
                if (out_data != -1 && DECODER_FLIPS[i]) begin
                    out_data = DECODER_DIVISORS[i] - out_data;
                end

                // For decoders with multiple bins, find the winning bin and use that as the value of interest
                if (DECODER_NUM_BINS[i] > 1) begin
                    if (j == 0) begin
                        val = 1;
                        win_out_data = out_data;
                    end else if ((DECODER_BINNING_STYLES[i] == WTA && out_data > win_out_data) || (DECODER_BINNING_STYLES[i] == LTA && out_data < win_out_data)) begin
                        val = j+1;
                        win_out_data = out_data;
                    end
                end else begin
                    val = out_data;
                end
            end

            // Convert value of interest to output decoder value for the current spike decoder
            if (val == -1) begin
                val = DECODER_MIN_VALS[i];
            end else if (DECODER_NUM_BINS[i] > 1) begin
                val = DECODER_MIN_VALS[i] + val * (DECODER_MAX_VALS[i]-DECODER_MIN_VALS[i]) / DECODER_NUM_BINS[i];
            end else begin
                val = DECODER_MIN_VALS[i] + val * (DECODER_MAX_VALS[i]-DECODER_MIN_VALS[i]) / DECODER_DIVISORS[i];
            end

            // Set snk's value for the current spike decoder equal to the current spike decoder's output value of interest
            snk[(SNK_WIDTH - i*DECODER_VAL_MAX_WIDTH - 1) -: DECODER_VAL_MAX_WIDTH] = val[DECODER_VAL_MAX_WIDTH-1:0];
        end
    end

    // Keep track of the number of timesteps since the last spike decoder output
    always_ff @(posedge clk or negedge arstn) begin: set_timestep
        if (arstn == 0 || out_ready) begin
            timestep <= 0;
        end else if (net_valid) begin
            timestep <= timestep + 1;
        end
    end

    // For each output neuron, keep track of fire count and last fire timestep
    always_ff @(posedge clk or negedge arstn) begin: set_out_data
        if (arstn == 0) begin
            for (int i = 0; i < NET_NUM_OUT; i++)
                out_counts[i] <= 0;
                out_last_fires[i] <= -1;
        end else if (net_valid) begin
            for (int i = 0; i < NET_NUM_OUT; i++) begin
                out_counts[i] <= out_counts[i] + net_out[i];
                out_last_fires[i] <= net_out[i] ? timestep : out_last_fires[i];
            end
        end
    end
    
endmodule
