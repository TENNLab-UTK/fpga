module uart_top #(
    parameter real CLK_FREQ = 100_000_000,
    parameter integer BAUD_RATE = 115_200
) (
    input wire clk,
    input wire btnc,
    input wire uart_tx_in,
    output wire uart_rx_out,
    output wire [7:0] led
);
    uart_processor #(
        .CLK_FREQ(CLK_FREQ),
        .BAUD_RATE(BAUD_RATE)
    ) uart_proc (
        .clk(clk),
        .arstn(!btnc),
        .rxd(uart_tx_in),
        .txd(uart_rx_out),
        .rx_busy(led[0]),
        .tx_busy(led[1]),
        .rx_error(led[7])
    );

    assign led[6:2] = 5'b0;
endmodule