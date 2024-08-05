module axis_processor_v_sv_adapter (

    // Global signals
    input clk,
    input arstn,

    // AXIS master signals
    output m_tvalid,
    input m_tready,
    output [31:0] m_tdata,
    output [3:0] m_tstrb,
    output [3:0] m_tkeep,
    output m_tlast,
    output [3:0] m_tid,
    output [3:0] m_tdest,
    output [3:0] m_tuser,
    
    // AXIS slave signals
    input s_tvalid,
    output s_tready,
    input [31:0] s_tdata,
    input [3:0] s_tstrb,
    input [3:0] s_tkeep,
    input s_tlast,
    input [3:0] s_tid,
    input [3:0] s_tdest,
    input [3:0] s_tuser
);

    axis s_axis();
    axis m_axis();
    
    // Connect AXIS slave signals to interface
    assign s_axis.tvalid = s_tvalid;
    assign s_axis.tready = s_tready;
    assign s_axis.tdata = s_tdata;
    assign s_axis.tstrb = s_tstrb;
    assign s_axis.tkeep = s_tkeep;
    assign s_axis.tlast = s_tlast;
    assign s_axis.tid = s_tid;
    assign s_axis.tdest = s_tdest;
    assign s_axis.tuser = s_tuser;
    
    // Connect AXIS master signals to interface
    assign m_axis.tvalid = m_tvalid;
    assign m_axis.tready = m_tready;
    assign m_axis.tdata = m_tdata;
    assign m_axis.tstrb = m_tstrb;
    assign m_axis.tkeep = m_tkeep;
    assign m_axis.tlast = m_tlast;
    assign m_axis.tid = m_tid;
    assign m_axis.tdest = m_tdest;
    assign m_axis.tuser = m_tuser;
    
    // Instantiate axis_processor
    axis_processor axis_processor_0 (
        .clk(clk),
        .arstn(arstn),
        .s_axis(s_axis),
        .m_axis(m_axis)
    );

endmodule
