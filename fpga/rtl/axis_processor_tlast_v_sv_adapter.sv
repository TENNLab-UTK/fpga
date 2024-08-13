import processor_tlast_config::*;

module axis_processor_tlast_v_sv_adapter (

    // Global signals
    input clk,
    input arstn,

    // AXIS master signals
    output m_tvalid,
    input m_tready,
    output [(OUT_TDATA_WIDTH_BYTES * 8 - 1):0] m_tdata,
    output [OUT_TDATA_WIDTH_BYTES-1:0] m_tkeep,
    output m_tlast,
    
    // AXIS slave signals
    input s_tvalid,
    output s_tready,
    input [(INP_TDATA_WIDTH_BYTES * 8 - 1):0] s_tdata,
    input [INP_TDATA_WIDTH_BYTES-1:0] s_tkeep,
    input s_tlast
);

    axis #(.DATA_WIDTH_BYTES(INP_TDATA_WIDTH_BYTES)) s_axis();
    axis #(.DATA_WIDTH_BYTES(OUT_TDATA_WIDTH_BYTES)) m_axis();
    
    // Connect AXIS slave signals to interface
    assign s_axis.tvalid = s_tvalid;
    assign s_axis.tready = s_tready;
    assign s_axis.tdata = s_tdata;
    // assign s_axis.tstrb = s_tstrb;
    assign s_axis.tkeep = s_tkeep;
    assign s_axis.tlast = s_tlast;
    // assign s_axis.tid = s_tid;
    // assign s_axis.tdest = s_tdest;
    // assign s_axis.tuser = s_tuser;
    
    // Connect AXIS master signals to interface
    assign m_axis.tvalid = m_tvalid;
    assign m_axis.tready = m_tready;
    assign m_axis.tdata = m_tdata;
    // assign m_axis.tstrb = m_tstrb;
    assign m_axis.tkeep = m_tkeep;
    assign m_axis.tlast = m_tlast;
    // assign m_axis.tid = m_tid;
    // assign m_axis.tdest = m_tdest;
    // assign m_axis.tuser = m_tuser;
    
    // Instantiate axis_processor_tlast
    axis_processor_tlast axis_processor_tlast_0 (
        .clk(clk),
        .arstn(arstn),
        .s_axis(s_axis),
        .m_axis(m_axis)
    );

endmodule
