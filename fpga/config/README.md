<!--
 Copyright (c) 2024 Keegan Dent

 This Source Code Form is subject to the terms of the Mozilla Public
 License, v. 2.0. If a copy of the MPL was not distributed with this
 file, You can obtain one at https://mozilla.org/MPL/2.0/.
-->

# FPGA Configuration

## `targets.json` Schema

| Key                        | Type      | Default  | Rules                                                                                                                             | Description                                                                                            |
|----------------------------|-----------|----------|-----------------------------------------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------|
| default_tool               | string    | Required | "vivado" \| "quartus"                                                                                                             | EDA tool for synthesis and implementation                                                              |
| parameters.clk_freq        | float     | Required | >0.0                                                                                                                              | Clock frequency for system clock utilized in top modules in Hertz                                      |
| parameters.bram_bits       | int       | Required | >0                                                                                                                                | Block RAM capacity in bits (note this may require x1024 conversions)                                   |
| parameters.uart.baud_rates | list[int] | [115200] | all in [list](https://github.com/vsergeev/python-periphery/blob/f3afcd7b5a799a066a6cf321e0456a040dd66c2c/periphery/serial.py#L19) | Validated UART baud rates in Hertz                                                                     |
| tools.`default_tool`       | dict      | Required | may require examining [Edalize source](https://github.com/olofk/edalize/tree/main/edalize)                                        | Edalize [tool_options](https://github.com/olofk/edalize/blob/main/doc/edam/api.rst) for `default_tool` |
