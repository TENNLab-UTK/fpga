// Copyright (c) 2024-2025 Keegan Dent
//
// This source describes Open Hardware and is licensed under the CERN-OHL-W v2
// You may redistribute and modify this documentation and make products using
// it under the terms of the CERN-OHL-W v2 (https:/cern.ch/cern-ohl).
//
// This documentation is distributed WITHOUT ANY EXPRESS OR IMPLIED WARRANTY,
// INCLUDING OF MERCHANTABILITY, SATISFACTORY QUALITY AND FITNESS FOR A
// PARTICULAR PURPOSE. Please see the CERN-OHL-W v2 for applicable conditions.

package dispatch_config;
    typedef enum {
        // 2-bit codes used by Source and Sink
        RUN = 0,
        SPK,
        SNC,
        CLR,
        // 3-bit codes used only by Procedure Source
        R04,
        R05,
        R06,
        R07
    } opcode_t;
    localparam int NUM_OPC = 4;
endpackage

package procedure_config;
    export *::*;
    import dispatch_config::opcode_t;
    localparam int NUM_OPC = 8;
endpackage

package stream_config;
    typedef enum {
        SNC = 0,
        CLR,
        // not a valid flag position, purely for counting
        NUM_FLG
    } flag_t;
endpackage
