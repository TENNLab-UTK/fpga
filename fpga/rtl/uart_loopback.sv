// Copyright (c) 2024 Keegan Dent
//
// This source describes Open Hardware and is licensed under the CERN-OHL-W v2
// You may redistribute and modify this documentation and make products using
// it under the terms of the CERN-OHL-W v2 (https:/cern.ch/cern-ohl).
//
// This documentation is distributed WITHOUT ANY EXPRESS OR IMPLIED WARRANTY,
// INCLUDING OF MERCHANTABILITY, SATISFACTORY QUALITY AND FITNESS FOR A
// PARTICULAR PURPOSE. Please see the CERN-OHL-W v2 for applicable conditions.

module uart_processor #(
    parameter real CLK_FREQ,
    parameter int BAUD_RATE
) (
    input logic clk,
    input logic arstn,
    input logic rxd,
    output logic txd,
    output logic rx_busy,
    output logic tx_busy,
    output logic rx_error
);
    localparam int PROC_WIDTH_BYTES = 1;

    axis #(
        .DATA_WIDTH_BYTES(PROC_WIDTH_BYTES)
    ) loop_axis ();

    axis #(
        .DATA_WIDTH_BYTES(1)
    ) rx_axis ();
    axis #(
        .DATA_WIDTH_BYTES(1)
    ) tx_axis ();

    axis_adapter rx_adapter (
        .clk,
        .arstn,
        .s_axis(rx_axis),
        .m_axis(loop_axis)
    );
    axis_adapter tx_adapter (
        .clk,
        .arstn,
        .s_axis(loop_axis),
        .m_axis(tx_axis)
    );

    logic [15:0] prescale;
    assign prescale = $floor(CLK_FREQ / real'(8 * BAUD_RATE));

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

endmodule