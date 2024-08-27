# Copyright (c) 2024 Keegan Dent
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
import os
import pathlib as pl
from importlib import resources

import neuro
from cocotb.triggers import Timer
from cocotb_test.simulator import run

from fpga import rtl, sims_build_path
from fpga.network import build_network_sv, proc_params_dict


async def reset(arstn, period: float = 2) -> None:
    arstn.value = False
    await Timer(period)
    arstn.value = True


def runner(
    testname: str,
    toplevel: str,
    network: neuro.Network,
    greater_modules: list[str] = [],
):
    hdl_toplevel_lang = "verilog"
    sims = os.getenv("SIMS", "verilator").split(":")
    waves = os.getenv("WAVES", True)

    rtl_path = pl.Path(resources.files(rtl))

    proc = proc_params_dict(network)["proc_name"]

    lesser_modules = [
        f"{proc}_neuron",
        f"{proc}_synapse",
    ]
    includes = []
    verilog_srcs = []
    vhdl_srcs = []
    match (hdl_toplevel_lang):
        case "verilog":
            includes.append(rtl_path)
            verilog_srcs.extend([rtl_path / f"{src}.sv" for src in lesser_modules])
            net_module = build_network_sv(network)
            verilog_srcs.append(net_module)
            verilog_srcs.extend([rtl_path / f"{src}.sv" for src in greater_modules])
        case "vhdl":
            vhdl_srcs.extend([rtl_path / f"{src}.vhd" for src in lesser_modules])
            raise NotImplementedError("VHDL network conversion not implemented")
            vhdl_srcs.extend([rtl_path / f"{src}.vhd" for src in greater_modules])
        case _:
            raise ValueError(f"Unsupported HDL language: {hdl_toplevel_lang}")

    for sim in sims:
        run_dir = pl.Path(__file__).parent / ("sim_" + sim) / testname
        run_dir.mkdir(parents=True, exist_ok=True)  # doesn't get created automatically
        extra_args = []
        if sim == "verilator":
            extra_args.extend(["-Wno-fatal", "--coverage"])
        run(
            module=testname,
            simulator=sim,
            # For some reason tests blow away each other's build, so there's not re-use
            # when num_tests > 1. This means you can expect really long sim times for
            # fresh HDL builds, but repeat ones should be incredibly fast.
            sim_build=(sims_build_path / sim / testname),
            work_dir=run_dir,
            toplevel=toplevel,
            verilog_sources=verilog_srcs,
            vhdl_sources=vhdl_srcs,
            includes=includes,
            waves=waves,
            extra_args=extra_args,
        )
