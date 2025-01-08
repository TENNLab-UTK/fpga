// Copyright (c) 2024 Keegan Dent
//
// This source describes Open Hardware and is licensed under the CERN-OHL-W v2
// You may redistribute and modify this documentation and make products using
// it under the terms of the CERN-OHL-W v2 (https:/cern.ch/cern-ohl).
//
// This documentation is distributed WITHOUT ANY EXPRESS OR IMPLIED WARRANTY,
// INCLUDING OF MERCHANTABILITY, SATISFACTORY QUALITY AND FITNESS FOR A
// PARTICULAR PURPOSE. Please see the CERN-OHL-W v2 for applicable conditions.

`define max(x, y) ((x) > (y) ? (x) : (y))
`define min(x, y) ((x) < (y) ? (x) : (y))

// width conversion helper functions
`define width_bits_to_bytes(w) (((w) + 7) / 8)
`define width_bytes_to_bits(w) ((w) * 8)
`define width_nearest_byte(w) `width_bytes_to_bits(`width_bits_to_bytes(w))

// signed number representation helper functions
`define signed_repr_max(WIDTH) (1 << ((WIDTH)-1)) - 1
`define signed_repr_min(WIDTH) -(1 << ((WIDTH)-1))

// field polymorphism helper functions
`define SRC_WIDTH ((OPC_WIDTH) + `max( `max(SPK_WIDTH, RUN_WIDTH), SPK_PRDC_WIDTH ))
