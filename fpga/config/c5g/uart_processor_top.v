// Copyright (c) 2024 Keegan Dent
//
// This source describes Open Hardware and is licensed under the CERN-OHL-W v2
// You may redistribute and modify this documentation and make products using
// it under the terms of the CERN-OHL-W v2 (https:/cern.ch/cern-ohl).
//
// This documentation is distributed WITHOUT ANY EXPRESS OR IMPLIED WARRANTY,
// INCLUDING OF MERCHANTABILITY, SATISFACTORY QUALITY AND FITNESS FOR A
// PARTICULAR PURPOSE. Please see the CERN-OHL-W v2 for applicable conditions.

module uart_top #(
    parameter real CLK_FREQ = 50_000_000,
    parameter integer BAUD_RATE = 3_000_000,
    parameter integer BUFFER_DEPTH = 128
) (
    input wire CLOCK_50_B5B,
    input wire CPU_RESET_n,
    input wire UART_RX,
    output wire UART_TX,
    output wire [7:0] LEDG
);
    uart_processor #(
        .CLK_FREQ(CLK_FREQ),
        .BAUD_RATE(BAUD_RATE),
        .BUFFER_DEPTH(BUFFER_DEPTH)
    ) uart_proc (
        .clk(CLOCK_50_B5B),
        .arstn(CPU_RESET_n),
        .rxd(UART_RX),
        .txd(UART_TX),
        .rx_busy(LEDG[0]),
        .tx_busy(LEDG[1]),
        .rx_error(LEDG[7])
    );

    assign LEDG[6:2] = 5'b0;
endmodule