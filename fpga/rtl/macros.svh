// Copyright (c) 2024 Keegan Dent
//
// This source describes Open Hardware and is licensed under the CERN-OHL-W v2
// You may redistribute and modify this documentation and make products using
// it under the terms of the CERN-OHL-W v2 (https:/cern.ch/cern-ohl).
//
// This documentation is distributed WITHOUT ANY EXPRESS OR IMPLIED WARRANTY,
// INCLUDING OF MERCHANTABILITY, SATISFACTORY QUALITY AND FITNESS FOR A
// PARTICULAR PURPOSE. Please see the CERN-OHL-W v2 for applicable conditions.

`define _ir(x) (int'(real'((x))))

`define max(x, y) ((x) > (y) ? (x) : (y))
`define min(x, y) ((x) < (y) ? (x) : (y))
`define abs(x) ((x) < 0 ? -(x) : (x))
`define sign(x) ((x) < 0 ? -1 : 1)
`define floor(x) (`_ir(x) > (x) : `_ir(x) - 1 : `_ir(x))
`define ceil(x) (`_ir(x) < (x) : `_ir(x) + 1 : `_ir(x))
`define rtoi(x) (`abs(`_ir(x)) > `abs(x) : `_ir(x) - `sign(x) : `_ir(x))

// width conversion helper functions
`define cdiv(x, y) (((x) + (y) - 1) / (y))
`define next_pow2(x) (1 << ($clog2(x)))
`define width_bits_to_bytes(w) (`cdiv(w, 8))
`define width_bytes_to_bits(w) ((w) * 8)
`define width_nearest_byte(w) `width_bytes_to_bits(`width_bits_to_bytes(w))

// signed number representation helper functions
`define signed_repr_max(WIDTH) (1 << ((WIDTH)-1)) - 1
`define signed_repr_min(WIDTH) -(1 << ((WIDTH)-1))

// field polymorphism helper functions
`define SRC_WIDTH ((OPC_WIDTH) + `max((SPK_WIDTH), (RUN_WIDTH)))
