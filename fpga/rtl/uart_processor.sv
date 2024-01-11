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

import processor_config::*;

module uart_processor #(
    parameter real CLK_FREQ,
    parameter int BAUD_RATE = 115_200
) (
    input logic clk,
    input logic arstn,
    input logic rxd,
    output logic txd,
    output logic rx_busy,
    output logic tx_busy,
    output logic rx_error
);

    axis #(
        .DATA_WIDTH_BYTES(1)
    ) rx_axis ();

    axis #(
        .DATA_WIDTH_BYTES(`width_bits_to_bytes(INP_WIDTH))
    ) inp_axis ();

    axis #(
        .DATA_WIDTH_BYTES(`width_bits_to_bytes(OUT_WIDTH))
    ) out_axis ();

    axis #(
        .DATA_WIDTH_BYTES(1)
    ) tx_axis ();

    logic [15:0] prescale;
    assign prescale = int'(CLK_FREQ / real'(8 * BAUD_RATE));

    uart #(
        .DATA_WIDTH(8)
    ) uart_inst (
        .clk,
        .arstn,
        .s_axis(tx_axis),
        .m_axis(rx_axis),
        .rxd,
        .txd,
        .rx_busy,
        .tx_busy,
        .prescale
    );

    always_ff @(posedge clk or negedge arstn) begin : set_rx_erorr
        if (arstn == 0) begin
            rx_error <= 0;
        end else if (!rx_error) begin
            rx_error <= uart_inst.rx_frame_error || uart_inst.rx_overrun_error;
        end
    end

    axis_processor #(
    ) proc (
        .clk,
        .arstn,
        .s_axis(inp_axis),
        .m_axis(out_axis)
    );

    axis_adapter rx_inp_adapter (
        .clk,
        .arstn,
        .s_axis(rx_axis),
        .m_axis(inp_axis)
    );

    axis_adapter out_tx_adapter (
        .clk,
        .arstn,
        .s_axis(out_axis),
        .m_axis(tx_axis)
    );

endmodule