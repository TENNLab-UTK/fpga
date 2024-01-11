// Copyright (c) 2024 Keegan Dent
//
// This source describes Open Hardware and is licensed under the CERN-OHL-W v2
// You may redistribute and modify this documentation and make products using
// it under the terms of the CERN-OHL-W v2 (https:/cern.ch/cern-ohl).
//
// This documentation is distributed WITHOUT ANY EXPRESS OR IMPLIED WARRANTY,
// INCLUDING OF MERCHANTABILITY, SATISFACTORY QUALITY AND FITNESS FOR A
// PARTICULAR PURPOSE. Please see the CERN-OHL-W v2 for applicable conditions.

interface axis #(
    parameter int DATA_WIDTH_BYTES = 4,
    parameter int ID_WIDTH = 0,
    parameter int DEST_WIDTH = 0,
    parameter int USER_WIDTH = 0
);
    logic tvalid;
    logic tready;
    logic [(DATA_WIDTH_BYTES * 8 - 1):0] tdata;
    logic [DATA_WIDTH_BYTES-1:0] tstrb;
    logic [DATA_WIDTH_BYTES-1:0] tkeep;
    logic tlast;
    logic [ID_WIDTH-1:0] tid;
    logic [DEST_WIDTH-1:0] tdest;
    logic [USER_WIDTH-1:0] tuser;

    modport m (
        output tvalid,
        input tready,
        output tdata,
        output tstrb,
        output tkeep,
        output tlast,
        output tid,
        output tdest,
        output tuser
    );

    modport s (
        input tvalid,
        output tready,
        input tdata,
        input tstrb,
        input tkeep,
        input tlast,
        input tid,
        input tdest,
        input tuser
    );
endinterface
