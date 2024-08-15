# Copyright (c) 2024 Keegan Dent
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
import os.path
import pathlib as pl
import sys
from enum import Enum, IntEnum, auto
from heapq import heapify, heappop, heappush, merge
from importlib import resources
from json import load
from math import inf
from typing import Iterable

import bitstruct as bs
import neuro
from edalize.edatool import get_edatool
from periphery import Serial

import fpga
from fpga import config, rtl
from fpga._math import clog2, width_bits_to_bytes, width_nearest_byte
from fpga.network import (
    HASH_LEN,
    build_network_sv,
    charge_width,
    hash_network,
    input_scaling_value,
)

if not sys.version_info.major == 3 and sys.version_info.minor >= 6:
    raise RuntimeError("Python 3.6 or newer is required.")


# we're hacking Spike to support comparison
neuro.Spike.__lt__ = lambda self, other: self.time < other.time
neuro.Spike.__le__ = lambda self, other: self.time <= other.time
neuro.Spike.__gt__ = lambda self, other: self.time > other.time
neuro.Spike.__ge__ = lambda self, other: self.time >= other.time


# can't believe I have to roll my own priority queue in the year 2024
# and no, queue.PriorityQueue has wasted thread safety
class _InpQueue(list):
    def __init__(self, data: Iterable[neuro.Spike]):
        super().__init__(data)
        heapify(self)

    def append(self, item: neuro.Spike) -> None:
        heappush(self, item)

    def extend(self, iterable: Iterable[neuro.Spike]) -> None:
        self.__init__(merge(self, iterable))

    def popleft(self) -> neuro.Spike:
        return heappop(self)


class IoType(Enum):
    DISPATCH = auto()
    STREAM = auto()


class DispatchOpcode(IntEnum):
    NOP = 0
    RUN = auto()
    SPK = auto()
    CLR = auto()


class StreamOpcode(IntEnum):
    NOM = 0
    CLR = auto()


def opcode_width(opcode_type: type) -> int:
    return clog2(len(opcode_type))


def dispatch_operand_widths(
    net_num_inp: int, net_charge_width: int, is_axi: bool = True
) -> tuple[int, int]:
    opc_width = opcode_width(DispatchOpcode)
    idx_width = clog2(net_num_inp)
    spk_width = idx_width + net_charge_width
    operand_width = (
        width_nearest_byte(opc_width + spk_width) - opc_width if is_axi else spk_width
    )
    return idx_width, operand_width


class Processor(neuro.Processor):
    def __init__(
        self,
        target: str,
        interface: Serial | str,
        io_type: str = "DISO",
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        self._target_name = target

        with open(resources.files(config).joinpath("targets.json")) as f:
            self._target_config = load(f)[self._target_name]

        if type(interface) is str:
            baudrate = 115200
            try:
                baudrate = self._target_config["parameters"]["uart"]["baud_rates"][-1]
            except KeyError:
                pass
            except IndexError:
                pass
            interface = Serial(interface, baudrate)
        self._interface = interface

        self._io_type = io_type.upper()
        match self._io_type[:2]:
            case "DI":
                self._inp_type = IoType.DISPATCH
                self._Opcode = DispatchOpcode
            case "SI":
                self._inp_type = IoType.STREAM
                self._Opcode = StreamOpcode
            case _:
                raise ValueError(
                    f"Invalid input type: {io_type.upper()[:2]}I\nExpected: (D|S)I"
                )
        match self._io_type[2:]:
            case "DO":
                self._out_type = IoType.DISPATCH
            case "SO":
                self._out_type = IoType.STREAM
            case _:
                raise ValueError(
                    f"Invalid output type: {io_type.upper()[2:]}O\nExpected: (D|S)O"
                )

        self.clear()

    def apply_spikes(self, spikes: list[neuro.Spike]) -> None:
        self._inp_queue.extend(spikes)
        if any(s.time < self._hw_time for s in spikes):
            raise RuntimeError("Spikes cannot be scheduled in the past.")
        if self._inp_type == IoType.DISPATCH:
            spikes_now = []
            while self._inp_queue and self._inp_queue[0].time == self._hw_time:
                # send these spikes as soon as they arrive to reduce latency
                spikes_now.append(self._inp_queue.popleft())
            self._hw_tr(spikes_now, runs=0)

    def clear(self) -> None:
        self.clear_activity()
        self._network = None

    def clear_activity(self) -> None:
        self._inp_queue = _InpQueue([])
        self._out_queue = dict()
        if hasattr(self, "_network") and self._network is not None:
            self._out_queue.update(
                {out_idx: [] for out_idx in range(self._network.num_outputs())}
            )
            if self._inp_type == IoType.DISPATCH:
                self._interface.write(
                    self._cmd_fmt.pack({"opcode": self._Opcode.CLR, "operand": 0})[::-1]
                )
        self._interface.flush()
        while self._interface.poll(10 / self._interface.baudrate):
            self._interface.read(self._interface.input_waiting())
        self._last_run = inf
        self._hw_time = 0

    def load_network(self, net: neuro.Network) -> None:
        self.clear()
        self._network = net
        self._set_schema()
        self._program_target()
        self.clear_activity()

    def output_count(self, out_idx: int) -> int:
        return len(self._out_since_last_run(out_idx))

    def output_counts(self) -> list[int]:
        return [
            self.output_count(out_idx) for out_idx in range(self._network.num_outputs())
        ]

    def output_last_fire(self, out_idx: int) -> int:
        outs = self._out_since_last_run(out_idx)
        return outs[-1] if outs else -1

    def output_last_fires(self) -> list[int]:
        return [
            self.output_last_fire(out_idx)
            for out_idx in range(self._network.num_outputs())
        ]

    def output_vector(self, out_idx: int) -> list[int]:
        return self._out_queue[out_idx]

    def output_vectors(self) -> list[list[int]]:
        return [
            self._out_queue[out_idx] for out_idx in range(self._network.num_outputs())
        ]

    def run(self, time: int) -> None:
        self._last_run = self._hw_time
        target_time = self._hw_time + time
        while self._hw_time < target_time:
            spikes = []
            while self._inp_queue and int(self._inp_queue[0].time) == self._hw_time:
                spikes.append(self._inp_queue.popleft())
            run_time = int(self._inp_queue[0].time) if self._inp_queue else target_time
            self._hw_tr(spikes, runs=(run_time - self._hw_time))

    def _hw_rx(self, runs: int) -> None:
        self._interface.flush()
        num_rx_bytes = width_bits_to_bytes(self._out_fmt.calcsize())
        num_tr_bytes = (
            num_rx_bytes
            + width_bits_to_bytes(self._spk_fmt.calcsize())
            + (
                width_bits_to_bytes(self._cmd_fmt.calcsize())
                if self._inp_type == IoType.DISPATCH
                else 0
            )
        )

        for _ in range(runs):
            rx = self._interface.read(
                num_rx_bytes,
                100_000 * (num_tr_bytes) / self._interface.baudrate,
            )
            if len(rx) != num_rx_bytes:
                raise RuntimeError("Did not receive coherent response from target.")

            match self._out_type:
                case IoType.DISPATCH:
                    for _ in range(self._out_fmt.unpack(rx)[None]):
                        sub_rx = self._interface.read(
                            num_rx_bytes, 10 * num_rx_bytes / self._interface.baudrate
                        )
                        if len(sub_rx) != num_rx_bytes:
                            raise RuntimeError(
                                "Did not receive coherent response from target."
                            )
                        self._out_queue[self._out_fmt.unpack(sub_rx)[None]].append(
                            self._hw_time
                        )

                case IoType.STREAM:
                    for out_idx, fire in self._out_fmt.unpack(rx).items():
                        if fire:
                            self._out_queue[out_idx].append(self._hw_time)
            self._hw_time += 1

    def _hw_tr(self, spikes: Iterable[neuro.Spike], runs: int) -> None:
        spike_dict = {
            self._network.get_node(s.id).input_id: int(
                s.value * input_scaling_value(self._network)
            )
            for s in spikes
        }
        if any(key < 0 for key in spike_dict.keys()):
            raise ValueError("Cannot send spikes to non-input node.")

        match self._inp_type:
            case IoType.DISPATCH:
                [
                    self._interface.write(
                        self._spk_fmt.pack(
                            {"opcode": self._Opcode.SPK, "inp_idx": idx, "value": val}
                        )[::-1]
                    )
                    for idx, val in spike_dict.items()
                ]

                for _ in range(runs // self._max_run):
                    self._interface.write(
                        self._cmd_fmt.pack(
                            {"opcode": self._Opcode.RUN, "operand": self._max_run}
                        )[::-1]
                    )
                    self._hw_rx(self._max_run)

                if runs % self._max_run:
                    self._interface.write(
                        self._cmd_fmt.pack(
                            {
                                "opcode": self._Opcode.RUN,
                                "operand": runs % self._max_run,
                            }
                        )[::-1]
                    )
                    self._hw_rx(runs % self._max_run)

            case IoType.STREAM:
                if not runs:
                    raise RuntimeError(
                        "Cannot send spikes to stream source without running."
                    )
                run_dict = {inp_idx: 0 for inp_idx in range(self._network.num_inputs())}
                run_dict["opcode"] = self._Opcode.NOM
                temp = run_dict.copy()
                temp.update(spike_dict)
                spike_dict = temp

                if self._hw_time == 0:
                    spike_dict["opcode"] = self._Opcode.CLR
                self._interface.write(self._spk_fmt.pack(spike_dict)[::-1])
                self._hw_rx(1)

                for _ in range(runs - 1):
                    self._interface.write(self._spk_fmt.pack(run_dict)[::-1])
                    self._hw_rx(1)

    def _out_since_last_run(self, out_idx) -> list[int]:
        return [t for t in self._out_queue[out_idx] if t >= self._last_run]

    def _program_target(self) -> None:
        proc = self._network.get_data("other").to_python()["proc_name"]

        nethash = hash_network(self._network, HASH_LEN)
        proj_path = fpga.eda_build_path / self._target_name / self._io_type / nethash

        def relative_path(p: pl.Path) -> pl.Path:
            return pl.Path(os.path.relpath(p.resolve(), start=proj_path.resolve()))

        net_sv_path = relative_path(build_network_sv(self._network))
        rtl_path = relative_path(pl.Path(resources.files(rtl)))
        config_path = relative_path(pl.Path(resources.files(config)))

        # file list supports tools incapable of parsing dependency order
        files = []
        files.extend(
            [
                {
                    "name": str(rtl_path / f"{module}.sv"),
                    "file_type": "systemVerilogSource",
                }
                for module in [
                    f"{proc}_neuron",
                    f"{proc}_synapse",
                ]
            ]
        )
        files.append({"name": str(net_sv_path), "file_type": "systemVerilogSource"})
        files.extend(
            [
                {
                    "name": str(rtl_path / f"{module}.sv"),
                    "file_type": "systemVerilogSource",
                }
                for module in [
                    f"{self._inp_type.name.lower()}_source",
                    f"{self._out_type.name.lower()}_sink",
                    "axis_if",
                    "axis_adapter",
                    "axis_uart",
                    "axis_processor",
                    "uart_processor",
                ]
            ]
        )

        parameters = {
            "CLK_FREQ": {
                "datatype": "str",
                "default": f"{self._target_config['parameters']['clk_freq']}",
                "paramtype": "vlogparam",
            },
            "BAUD_RATE": {
                "datatype": "str",
                "default": f"{self._interface.baudrate}",
                "paramtype": "vlogparam",
            },
        }

        tool = self._target_config["default_tool"]
        tool_options = self._target_config["tools"]
        if tool == "vivado":
            tool_options["vivado"]["include_dirs"] = [str(rtl_path)]
            tool_options["vivado"]["source_mgmt_mode"] = "All"
            # tool_options["vivado"]["libs"] = []
            # tool_options["vivado"]["name"] = ""
            # tool_options["vivado"]["src_files"] = []
            files.extend(
                [
                    {
                        "name": str(
                            config_path
                            / f"{self._target_name}"
                            / "uart_processor_top.v"
                        ),
                        "file_type": "verilogSource",
                    },
                    {
                        "name": str(
                            config_path
                            / f"{self._target_name}"
                            / f"{self._target_name}.xdc"
                        ),
                        "file_type": "xdc",
                    },
                ]
            )

        edam = {
            "files": files,
            "name": f"{nethash}",
            "parameters": parameters,
            "toplevel": "uart_top",
            "tool_options": tool_options,
        }

        # https://github.com/olofk/edalize/issues/428
        backend = get_edatool(self._target_config["default_tool"])(
            edam=edam, work_root=proj_path, verbose=False
        )

        proj_path.mkdir(parents=True, exist_ok=True)
        backend.configure()
        backend.build()
        backend.run()

    def _set_schema(self):
        net_charge_width = charge_width(self._network)
        opc_width = opcode_width(self._Opcode)

        spk_names = list()
        spk_fmt_str = ""
        spk_names.append("opcode")
        spk_fmt_str += f"u{opc_width}"
        match self._inp_type:
            case IoType.DISPATCH:
                idx_width, operand_width = dispatch_operand_widths(
                    self._network.num_inputs(), net_charge_width
                )

                cmd_names = spk_names + ["operand"]
                cmd_fmt_str = spk_fmt_str + f"u{operand_width}"
                self._cmd_fmt = bs.compile(cmd_fmt_str, cmd_names)
                self._max_run = 2 ** (operand_width) - 1

                if idx_width > 0:
                    spk_names.append("inp_idx")
                    spk_fmt_str += f"u{idx_width}"
                spk_names.append("value")
                spk_fmt_str += f"s{net_charge_width}"
            case IoType.STREAM:
                spk_names.extend(range(self._network.num_inputs()))
                spk_fmt_str += "".join(
                    f"s{net_charge_width}" for _ in range(self._network.num_inputs())
                )
            case _:
                raise ValueError()
        self._spk_fmt = bs.compile(spk_fmt_str, spk_names)

        match self._out_type:
            case IoType.DISPATCH:
                out_names = [None]
                out_fmt_str = f"u{clog2(self._network.num_outputs() + 1)}"
            case IoType.STREAM:
                out_names = list(range(self._network.num_outputs()))
                out_fmt_str = "".join("b1" for _ in range(self._network.num_outputs()))
            case _:
                raise ValueError()
        self._out_fmt = bs.compile(out_fmt_str, out_names)
