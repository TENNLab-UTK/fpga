module clk_div #(
    parameter DIVISOR=1
)(
    input clk_in,
    input arstn,
    output reg clk_out
);

    reg [$clog2(DIVISOR)-1 : 0] count;

    always @ (posedge clk_in) begin
        if (arstn == 0) begin
            clk_out <= 0;
            count <= 0;
        end else begin
            if(DIVISOR == 1 || count == DIVISOR-1) begin
                clk_out <= ~clk_out;
            end
            count <= count + 1;
        end
    end

endmodule