// Copyright (c) 2014-2023 Alex Forencich
// Copyright (c) 2024 Pavel Kuzmin
// Copyright (c) 2024 Keegan Dent
//
// This source describes Open Hardware and is licensed under the CERN-OHL-W v2
// You may redistribute and modify this documentation and make products using
// it under the terms of the CERN-OHL-W v2 (https:/cern.ch/cern-ohl).
//
// This documentation is distributed WITHOUT ANY EXPRESS OR IMPLIED WARRANTY,
// INCLUDING OF MERCHANTABILITY, SATISFACTORY QUALITY AND FITNESS FOR A
// PARTICULAR PURPOSE. Please see the CERN-OHL-W v2 for applicable conditions.

/*
 * AXI4-Stream bus width adapter
 */
module axis_adapter #
(
    // Propagate tkeep signal on input interface
    // If disabled, tkeep assumed to be 1'b1
    parameter S_KEEP_ENABLE = (s_axis.DATA_WIDTH_BYTES > 1),
    // Propagate tkeep signal on output interface
    // If disabled, tkeep assumed to be 1'b1
    parameter M_KEEP_ENABLE = (m_axis.DATA_WIDTH_BYTES > 1),
    // Propagate tid signal
    parameter ID_ENABLE = 0,
    // Propagate tdest signal
    parameter DEST_ENABLE = 0,
    // Propagate tuser signal
    parameter USER_ENABLE = 1
)
(
    input logic clk,
    input logic arstn,
    axis.s s_axis,
    axis.m m_axis
);

    localparam S_DATA_WIDTH = s_axis.DATA_WIDTH_BYTES * 8;
    localparam M_DATA_WIDTH = m_axis.DATA_WIDTH_BYTES * 8;

    localparam S_KEEP_WIDTH = s_axis.DATA_WIDTH_BYTES;
    localparam M_KEEP_WIDTH = m_axis.DATA_WIDTH_BYTES;

    initial begin
        if (s_axis.ID_WIDTH != m_axis.ID_WIDTH)
            $error("ID_WIDTH mismatch");
            $finish;
        if (s_axis.DEST_WIDTH != m_axis.DEST_WIDTH)
            $error("DEST_WIDTH mismatch");
            $finish;
        if (s_axis.USER_WIDTH != m_axis.USER_WIDTH)
            $error("USER_WIDTH mismatch");
            $finish;
    end

    localparam ID_WIDTH = s_axis.ID_WIDTH;
    localparam DEST_WIDTH = s_axis.DEST_WIDTH;
    localparam USER_WIDTH = s_axis.USER_WIDTH;

    // force keep width to 1 when disabled
    localparam S_BYTE_LANES = S_KEEP_ENABLE ? S_KEEP_WIDTH : 1;
    localparam M_BYTE_LANES = M_KEEP_ENABLE ? M_KEEP_WIDTH : 1;

    // bus byte sizes (must be identical)
    localparam S_BYTE_SIZE = S_DATA_WIDTH / S_BYTE_LANES;
    localparam M_BYTE_SIZE = M_DATA_WIDTH / M_BYTE_LANES;

    // bus width assertions
    initial begin
        if (S_BYTE_SIZE * S_BYTE_LANES != S_DATA_WIDTH) begin
            $error("Error: input data width not evenly divisible (instance %m)");
            $finish;
        end

        if (M_BYTE_SIZE * M_BYTE_LANES != M_DATA_WIDTH) begin
            $error("Error: output data width not evenly divisible (instance %m)");
            $finish;
        end

        if (S_BYTE_SIZE != M_BYTE_SIZE) begin
            $error("Error: byte size mismatch (instance %m)");
            $finish;
        end
    end

    logic [S_KEEP_WIDTH-1:0] s_axis_tkeep_int = S_KEEP_ENABLE ? s_axis.tkeep : {S_KEEP_WIDTH{1'b1}};

    generate

    if (M_BYTE_LANES == S_BYTE_LANES) begin : bypass
        // same width; bypass

        assign s_axis.tready = m_axis.tready;

        assign m_axis.tdata  = s_axis.tdata;
        assign m_axis.tkeep  = M_KEEP_ENABLE ? s_axis_tkeep_int : {M_KEEP_WIDTH{1'b1}};
        assign m_axis.tvalid = s_axis.tvalid;
        assign m_axis.tlast  = s_axis.tlast;
        assign m_axis.tid    = ID_ENABLE   ? s_axis.tid   : {ID_WIDTH{1'b0}};
        assign m_axis.tdest  = DEST_ENABLE ? s_axis.tdest : {DEST_WIDTH{1'b0}};
        assign m_axis.tuser  = USER_ENABLE ? s_axis.tuser : {USER_WIDTH{1'b0}};

    end else if (M_BYTE_LANES > S_BYTE_LANES) begin : upsize
        // output is wider; upsize

        // required number of segments in wider bus
        localparam SEG_COUNT = M_BYTE_LANES / S_BYTE_LANES;
        // data width and keep width per segment
        localparam SEG_DATA_WIDTH = M_DATA_WIDTH / SEG_COUNT;
        localparam SEG_KEEP_WIDTH = M_BYTE_LANES / SEG_COUNT;

        logic [$clog2(SEG_COUNT)-1:0] seg_reg = 0;

        logic [S_DATA_WIDTH-1:0] s_axis_tdata_reg = {S_DATA_WIDTH{1'b0}};
        logic [S_KEEP_WIDTH-1:0] s_axis_tkeep_reg = {S_KEEP_WIDTH{1'b0}};
        logic s_axis_tvalid_reg = 1'b0;
        logic s_axis_tlast_reg = 1'b0;
        logic [ID_WIDTH-1:0] s_axis_tid_reg = {ID_WIDTH{1'b0}};
        logic [DEST_WIDTH-1:0] s_axis_tdest_reg = {DEST_WIDTH{1'b0}};
        logic [USER_WIDTH-1:0] s_axis_tuser_reg = {USER_WIDTH{1'b0}};

        logic [M_DATA_WIDTH-1:0] m_axis_tdata_reg = {M_DATA_WIDTH{1'b0}};
        logic [M_KEEP_WIDTH-1:0] m_axis_tkeep_reg = {M_KEEP_WIDTH{1'b0}};
        logic m_axis_tvalid_reg = 1'b0;
        logic m_axis_tlast_reg = 1'b0;
        logic [ID_WIDTH-1:0] m_axis_tid_reg = {ID_WIDTH{1'b0}};
        logic [DEST_WIDTH-1:0] m_axis_tdest_reg = {DEST_WIDTH{1'b0}};
        logic [USER_WIDTH-1:0] m_axis_tuser_reg = {USER_WIDTH{1'b0}};

        assign s_axis.tready = !s_axis_tvalid_reg;

        assign m_axis.tdata  = m_axis_tdata_reg;
        assign m_axis.tkeep  = M_KEEP_ENABLE ? m_axis_tkeep_reg : {M_KEEP_WIDTH{1'b1}};
        assign m_axis.tvalid = m_axis_tvalid_reg;
        assign m_axis.tlast  = m_axis_tlast_reg;
        assign m_axis.tid    = ID_ENABLE   ? m_axis_tid_reg   : {ID_WIDTH{1'b0}};
        assign m_axis.tdest  = DEST_ENABLE ? m_axis_tdest_reg : {DEST_WIDTH{1'b0}};
        assign m_axis.tuser  = USER_ENABLE ? m_axis_tuser_reg : {USER_WIDTH{1'b0}};

        always_ff @(posedge clk or negedge arstn) begin
            if (arstn == 0) begin
                seg_reg <= 0;
                s_axis_tvalid_reg <= 1'b0;
                m_axis_tvalid_reg <= 1'b0;
            end else begin
                m_axis_tvalid_reg <= m_axis_tvalid_reg && !m_axis.tready;
                if (!m_axis_tvalid_reg || m_axis.tready) begin
                    // output register empty

                    if (seg_reg == 0) begin
                        m_axis_tdata_reg[seg_reg*SEG_DATA_WIDTH +: SEG_DATA_WIDTH] <= s_axis_tvalid_reg ? s_axis_tdata_reg : s_axis.tdata;
                        m_axis_tkeep_reg <= s_axis_tvalid_reg ? s_axis_tkeep_reg : s_axis_tkeep_int;
                    end else begin
                        m_axis_tdata_reg[seg_reg*SEG_DATA_WIDTH +: SEG_DATA_WIDTH] <= s_axis.tdata;
                        m_axis_tkeep_reg[seg_reg*SEG_KEEP_WIDTH +: SEG_KEEP_WIDTH] <= s_axis_tkeep_int;
                    end
                    m_axis_tlast_reg <= s_axis_tvalid_reg ? s_axis_tlast_reg : s_axis.tlast;
                    m_axis_tid_reg <= s_axis_tvalid_reg ? s_axis_tid_reg : s_axis.tid;
                    m_axis_tdest_reg <= s_axis_tvalid_reg ? s_axis_tdest_reg : s_axis.tdest;
                    m_axis_tuser_reg <= s_axis_tvalid_reg ? s_axis_tuser_reg : s_axis.tuser;

                    if (s_axis_tvalid_reg) begin
                        // consume data from buffer
                        s_axis_tvalid_reg <= 1'b0;

                        if (s_axis_tlast_reg || seg_reg == SEG_COUNT-1) begin
                            seg_reg <= 0;
                            m_axis_tvalid_reg <= 1'b1;
                        end else begin
                            seg_reg <= seg_reg + 1;
                        end
                    end else if (s_axis.tvalid) begin
                        // data direct from input
                        if (s_axis.tlast || seg_reg == SEG_COUNT-1) begin
                            seg_reg <= 0;
                            m_axis_tvalid_reg <= 1'b1;
                        end else begin
                            seg_reg <= seg_reg + 1;
                        end
                    end
                end else if (s_axis.tvalid && s_axis.tready) begin
                    // store input data in skid buffer
                    s_axis_tdata_reg <= s_axis.tdata;
                    s_axis_tkeep_reg <= s_axis_tkeep_int;
                    s_axis_tvalid_reg <= 1'b1;
                    s_axis_tlast_reg <= s_axis.tlast;
                    s_axis_tid_reg <= s_axis.tid;
                    s_axis_tdest_reg <= s_axis.tdest;
                    s_axis_tuser_reg <= s_axis.tuser;
                end
            end
        end

    end else begin : downsize
        // output is narrower; downsize

        // required number of segments in wider bus
        localparam SEG_COUNT = S_BYTE_LANES / M_BYTE_LANES;
        // data width and keep width per segment
        localparam SEG_DATA_WIDTH = S_DATA_WIDTH / SEG_COUNT;
        localparam SEG_KEEP_WIDTH = S_BYTE_LANES / SEG_COUNT;

        logic [S_DATA_WIDTH-1:0] s_axis_tdata_reg = {S_DATA_WIDTH{1'b0}};
        logic [S_KEEP_WIDTH-1:0] s_axis_tkeep_reg = {S_KEEP_WIDTH{1'b0}};
        logic s_axis_tvalid_reg = 1'b0;
        logic s_axis_tlast_reg = 1'b0;
        logic [ID_WIDTH-1:0] s_axis_tid_reg = {ID_WIDTH{1'b0}};
        logic [DEST_WIDTH-1:0] s_axis_tdest_reg = {DEST_WIDTH{1'b0}};
        logic [USER_WIDTH-1:0] s_axis_tuser_reg = {USER_WIDTH{1'b0}};

        logic [M_DATA_WIDTH-1:0] m_axis_tdata_reg = {M_DATA_WIDTH{1'b0}};
        logic [M_KEEP_WIDTH-1:0] m_axis_tkeep_reg = {M_KEEP_WIDTH{1'b0}};
        logic m_axis_tvalid_reg = 1'b0;
        logic m_axis_tlast_reg = 1'b0;
        logic [ID_WIDTH-1:0] m_axis_tid_reg = {ID_WIDTH{1'b0}};
        logic [DEST_WIDTH-1:0] m_axis_tdest_reg = {DEST_WIDTH{1'b0}};
        logic [USER_WIDTH-1:0] m_axis_tuser_reg = {USER_WIDTH{1'b0}};

        assign s_axis.tready = !s_axis_tvalid_reg;

        assign m_axis.tdata  = m_axis_tdata_reg;
        assign m_axis.tkeep  = M_KEEP_ENABLE ? m_axis_tkeep_reg : {M_KEEP_WIDTH{1'b1}};
        assign m_axis.tvalid = m_axis_tvalid_reg;
        assign m_axis.tlast  = m_axis_tlast_reg;
        assign m_axis.tid    = ID_ENABLE   ? m_axis_tid_reg   : {ID_WIDTH{1'b0}};
        assign m_axis.tdest  = DEST_ENABLE ? m_axis_tdest_reg : {DEST_WIDTH{1'b0}};
        assign m_axis.tuser  = USER_ENABLE ? m_axis_tuser_reg : {USER_WIDTH{1'b0}};

        always_ff @(posedge clk or negedge arstn) begin
            if (arstn == 0) begin
                s_axis_tvalid_reg <= 1'b0;
                m_axis_tvalid_reg <= 1'b0;
            end else begin
                m_axis_tvalid_reg <= m_axis_tvalid_reg && !m_axis.tready;
                if (!m_axis_tvalid_reg || m_axis.tready) begin
                    // output register empty

                    m_axis_tdata_reg <= s_axis_tvalid_reg ? s_axis_tdata_reg : s_axis.tdata;
                    m_axis_tkeep_reg <= s_axis_tvalid_reg ? s_axis_tkeep_reg : s_axis_tkeep_int;
                    m_axis_tlast_reg <= 1'b0;
                    m_axis_tid_reg <= s_axis_tvalid_reg ? s_axis_tid_reg : s_axis.tid;
                    m_axis_tdest_reg <= s_axis_tvalid_reg ? s_axis_tdest_reg : s_axis.tdest;
                    m_axis_tuser_reg <= s_axis_tvalid_reg ? s_axis_tuser_reg : s_axis.tuser;

                    if (s_axis_tvalid_reg) begin
                        // buffer has data; shift out from buffer
                        s_axis_tdata_reg <= s_axis_tdata_reg >> SEG_DATA_WIDTH;
                        s_axis_tkeep_reg <= s_axis_tkeep_reg >> SEG_KEEP_WIDTH;

                        m_axis_tvalid_reg <= 1'b1;

                        if ((s_axis_tkeep_reg >> SEG_KEEP_WIDTH) == 0) begin
                            s_axis_tvalid_reg <= 1'b0;
                            m_axis_tlast_reg <= s_axis_tlast_reg;
                        end
                    end else if (s_axis.tvalid && s_axis.tready) begin
                        // buffer is empty; store from input
                        s_axis_tdata_reg <= s_axis.tdata >> SEG_DATA_WIDTH;
                        s_axis_tkeep_reg <= s_axis_tkeep_int >> SEG_KEEP_WIDTH;
                        s_axis_tlast_reg <= s_axis.tlast;
                        s_axis_tid_reg <= s_axis.tid;
                        s_axis_tdest_reg <= s_axis.tdest;
                        s_axis_tuser_reg <= s_axis.tuser;

                        m_axis_tvalid_reg <= 1'b1;

                        if ((s_axis_tkeep_int >> SEG_KEEP_WIDTH) == 0) begin
                            s_axis_tvalid_reg <= 1'b0;
                            m_axis_tlast_reg <= s_axis.tlast;
                        end else begin
                            s_axis_tvalid_reg <= 1'b1;
                        end
                    end
                end else if (s_axis.tvalid && s_axis.tready) begin
                    // store input data
                    s_axis_tdata_reg <= s_axis.tdata;
                    s_axis_tkeep_reg <= s_axis_tkeep_int;
                    s_axis_tvalid_reg <= 1'b1;
                    s_axis_tlast_reg <= s_axis.tlast;
                    s_axis_tid_reg <= s_axis.tid;
                    s_axis_tdest_reg <= s_axis.tdest;
                    s_axis_tuser_reg <= s_axis.tuser;
                end
            end
        end
    end

    endgenerate

endmodule
