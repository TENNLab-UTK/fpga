// Copyright (c) 2024 Keegan Dent
//
// This source describes Open Hardware and is licensed under the CERN-OHL-W v2
// You may redistribute and modify this documentation and make products using
// it under the terms of the CERN-OHL-W v2 (https:/cern.ch/cern-ohl).
//
// This documentation is distributed WITHOUT ANY EXPRESS OR IMPLIED WARRANTY,
// INCLUDING OF MERCHANTABILITY, SATISFACTORY QUALITY AND FITNESS FOR A
// PARTICULAR PURPOSE. Please see the CERN-OHL-W v2 for applicable conditions.

module risp_synapse_single_spike #(
    parameter int WEIGHT,
    parameter int DELAY,
    parameter int CHARGE_WIDTH,
    parameter bit FIRE_LIKE_RAVENS=0
) (
    input logic clk,
    input logic arstn,
    input logic en,
    input logic inp,
    output logic signed [CHARGE_WIDTH-1:0] out
);
    localparam TRUE_DELAY = DELAY - FIRE_LIKE_RAVENS;
    logic [$clog2(TRUE_DELAY+2)-1:0] spike_timestep_counter;

    assign out = (spike_timestep_counter == 1) ? WEIGHT : 0;

    always_ff @(posedge clk or negedge arstn) begin: spike_timestep_count
        if (arstn == 0) begin
            spike_timestep_counter <= 0;
        end else if (en) begin
            if (spike_timestep_counter != 0) begin
                spike_timestep_counter <= spike_timestep_counter - 1;
            end else if (inp) begin
                spike_timestep_counter <= TRUE_DELAY+1;
            end 
        end
    end
    
endmodule