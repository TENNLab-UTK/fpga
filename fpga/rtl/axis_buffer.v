// Copyright (c) 2024 Keegan Dent
//
// This source describes Open Hardware and is licensed under the CERN-OHL-W v2
// You may redistribute and modify this documentation and make products using
// it under the terms of the CERN-OHL-W v2 (https:/cern.ch/cern-ohl).
//
// This documentation is distributed WITHOUT ANY EXPRESS OR IMPLIED WARRANTY,
// INCLUDING OF MERCHANTABILITY, SATISFACTORY QUALITY AND FITNESS FOR A
// PARTICULAR PURPOSE. Please see the CERN-OHL-W v2 for applicable conditions.

module axis_buffer #
(
    // Width of AXI stream interfaces in bits
    parameter DATA_WIDTH = 8,
    // Buffer depth
    parameter DEPTH = 4096
)
(
    input  wire                     clk,
    input  wire                     arstn,

    /*
     * AXI input
     */
    input  wire [DATA_WIDTH-1:0]    s_axis_tdata,
    input  wire                     s_axis_tvalid,
    output wire                     s_axis_tready,

    /*
     * AXI output
     */
    output wire [DATA_WIDTH-1:0]    m_axis_tdata,
    output wire                     m_axis_tvalid,
    input  wire                     m_axis_tready
);
    reg [$clog2(DEPTH+1)-1:0] fifo_count;

    wire bypass;
    assign bypass = s_axis_tvalid && m_axis_tready && (fifo_count == 0);

    wire wr_en, rd_en;
    assign rd_en = m_axis_tready && (fifo_count > 0);
    // writing to a "full" buffer is allowed if the read pointer is also incrementing this cycle
    assign wr_en = s_axis_tvalid && (fifo_count < (DEPTH + m_axis_tready)) && !bypass;

    reg [$clog2(DEPTH)-1:0] wr_ptr, rd_ptr;
    always @(posedge clk or negedge arstn) begin : set_ptrs
        if (arstn == 0) begin
            wr_ptr <= 0;
            rd_ptr <= 0;
            fifo_count <= 0;
        end else begin
            if (wr_en) begin
                wr_ptr <= (wr_ptr + 1) % DEPTH;
            end
            if (rd_en) begin
                rd_ptr <= (rd_ptr + 1) % DEPTH;
            end
            fifo_count <= fifo_count + wr_en - rd_en;
        end
    end

    (* ram_style = "block", ramstyle = "no_rw_check" *)
    reg [DATA_WIDTH-1:0] buffer [DEPTH-1:0];

    always @(posedge clk) begin : write_buffer
        if (wr_en) begin
            buffer[wr_ptr] <= s_axis_tdata;
        end
    end

    assign m_axis_tdata = bypass ? s_axis_tdata : buffer[rd_ptr];
    // we can send if there's data in the buffer or we can bypass it
    assign m_axis_tvalid = (fifo_count > 0) || s_axis_tvalid;
    // we can always receive if there's space in the buffer
    assign s_axis_tready = fifo_count < (DEPTH + m_axis_tready);
endmodule
