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
    parameter real CLK_FREQ = 100_000_000,
    parameter integer BRAM_BITS = 1_843_200,
    parameter integer BAUD_RATE = 115_200,
    parameter integer HOST_BUFFER = 4096
) (
    input wire clk,
    input wire btnC,
    input wire RsRx,
    output wire RsTx,
    output wire [15:0] led
);
    uart_processor #(
        .CLK_FREQ(CLK_FREQ),
        .BRAM_BITS(BRAM_BITS),
        .BAUD_RATE(BAUD_RATE),
        .HOST_BUFFER(HOST_BUFFER)
    ) uart_proc (
        .clk(clk),
        .arstn(!btnC),
        .rxd(RsRx),
        .txd(RsTx),
        .rx_busy(led[0]),
        .tx_busy(led[1]),
        .rx_error(led[15])
    );

    assign led[14:2] = 13'b0;
endmodule