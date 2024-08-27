# Copyright (c) 2024 Keegan Dent
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import inspect
import pathlib as pl
from math import ceil
from typing import Callable

import cocotb
import neuro
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge, RisingEdge
from testing import reset, runner

from fpga.network import proc_params_dict

proj_path = pl.Path(__file__).parent.parent
net = neuro.Network()
net.read_from_file(str(proj_path / "networks" / "simple.txt"))


async def verify_fire_times(fire, clk, expected_fire_cycles: list[int]) -> None:
    cycle_num = 0
    while expected_fire_cycles:
        await FallingEdge(clk)
        if fire.value == 1:
            assert cycle_num in expected_fire_cycles
            expected_fire_cycles.remove(cycle_num)
        elif fire.value == 0:
            assert cycle_num not in expected_fire_cycles
        cycle_num += 1


async def inject_value(subject, clk, map_func: Callable[[int], int]) -> None:
    cycle_num = 0
    while True:
        await RisingEdge(clk)
        set_value = map_func(cycle_num)
        subject.value = set_value
        cycle_num += 1


@cocotb.test()
async def simple_network(dut: cocotb.handle.HierarchyObject) -> None:
    thresh_idx = net.get_node_property("Threshold").index
    weight_idx = net.get_edge_property("Weight").index
    delay_idx = net.get_edge_property("Delay").index

    threshold_0 = int(net.get_node(0).values[thresh_idx])
    threshold_1 = int(net.get_node(1).values[thresh_idx])
    weight = int(net.get_edge(0, 1).values[weight_idx])
    delay = int(net.get_edge(0, 1).values[delay_idx])

    full = proc_params_dict(net)["max_weight"]
    partial = threshold_0 // 3

    full_start = 0
    full_end = int(ceil(threshold_1 / weight)) + full_start
    partial_start = full_end + 1
    partial_end = (
        int(ceil(threshold_1 / weight)) * int(ceil(threshold_0 / partial))
        + partial_start
    )

    def spike_val(cycle) -> int:
        if cycle in range(full_start, full_end):
            return full
        elif cycle in range(partial_start, partial_end):
            return partial
        else:
            return 0

    dut.arstn.value = 1
    dut.en.value = 1
    dut.inp[0].value = 0
    clock = Clock(dut.clk, 10)
    await cocotb.start(clock.start())

    await reset(dut.arstn)

    await cocotb.start(inject_value(dut.inp[0], dut.clk, spike_val))
    await cocotb.start(
        verify_fire_times(dut.out, dut.clk, [full_end + delay, partial_end + delay])
    )

    for _ in range(partial_end + delay + 2):
        await RisingEdge(dut.clk)


def test_simple_network() -> None:
    runner(inspect.currentframe().f_code.co_name, "network", net)


if __name__ == "__main__":
    test_simple_network()
