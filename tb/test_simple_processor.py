# Copyright (c) 2024 Keegan Dent
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import inspect
import pathlib as pl
from enum import IntEnum

import cocotb
import neuro
import numpy as np
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge, RisingEdge
from testing import reset, runner

from fpga.network import charge_width, proc_params_dict

proj_path = pl.Path(__file__).parent.parent
net = neuro.Network()
net.read_from_file(str(proj_path / "networks" / "simple.txt"))
net_charge_width = charge_width(net)
operand_width = int(np.ceil(np.log2(net.num_inputs()))) + net_charge_width
full = proc_params_dict(net)["max_weight"]
partial = 3

_thresh_idx = net.get_node_property("Threshold").index
_weight_idx = net.get_edge_property("Weight").index
_delay_idx = net.get_edge_property("Delay").index

threshold_0 = int(net.get_node(0).values[_thresh_idx])
threshold_1 = int(net.get_node(1).values[_thresh_idx])
weight = int(net.get_edge(0, 1).values[_weight_idx])
delay = int(net.get_edge(0, 1).values[_delay_idx])


class opcode(IntEnum):
    NOP = 0
    RUN = 1
    SPK = 2
    CLR = 3


def instr_spike(value: int, index: int = 0) -> int:
    return (opcode.SPK << operand_width) + (index << net_charge_width) + value


def instr_run() -> int:
    return opcode.RUN << operand_width


@cocotb.test()
async def simple_processor_nominal(dut: cocotb.handle.HierarchyObject) -> None:
    full_start = 0
    full_end = int(np.ceil(threshold_1 / weight)) + full_start
    partial_start = full_end + 5
    partial_end = (
        int(np.ceil(threshold_1 / weight)) * int(np.ceil(threshold_0 / partial))
        + partial_start
    )

    async def run_processor() -> None:
        for run in range(partial_end + 2):
            if run in range(full_start, full_end):
                # spike full
                await FallingEdge(dut.clk)
                dut.instr.value = instr_spike(full)
            elif run in range(partial_start, partial_end):
                # spike partial
                await FallingEdge(dut.clk)
                dut.instr.value = instr_spike(partial)
            # run
            await FallingEdge(dut.clk)
            dut.instr.value = instr_run()
            if run in [full_end + delay, partial_end + delay]:
                print(f"run: {run}")
                assert dut.out.value == 1
            else:
                assert dut.out.value == 0

    dut.arstn.value = 1
    dut.instr.value = 0
    clock = Clock(dut.clk, 10)
    await cocotb.start(clock.start())

    await reset(dut.arstn)
    await RisingEdge(dut.clk)

    await run_processor()


def test_simple_processor() -> None:
    runner(
        inspect.currentframe().f_code.co_name,
        "basic_processor",
        net,
        ["dispatch_source", "stream_sink", "basic_processor"],
    )


if __name__ == "__main__":
    test_simple_processor()
