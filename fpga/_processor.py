# Copyright (c) 2024-2025 Keegan Dent
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
import os.path
import pathlib as pl
import sys
from enum import Enum, IntEnum, auto
from heapq import heapify, heappop, heappush
from importlib import resources
from json import load
from threading import Thread
from time import sleep
from typing import Iterable

import bitstruct as bs
import neuro
from edalize.edatool import get_edatool
from periphery import Serial

import fpga
from fpga import config, rtl
from fpga._math import unsigned_width, width_bits_to_bytes, width_nearest_byte
from fpga.network import (
    HASH_LEN,
    build_network_sv,
    charge_width,
    hash_network,
    proc_name,
    spike_value_factor,
)

SYSTEM_BUFFER = 4096

if not sys.version_info.major == 3 and sys.version_info.minor >= 6:
    raise RuntimeError("Python 3.6 or newer is required.")


# we're hacking Spike to support comparison
neuro.Spike.__lt__ = lambda self, other: self.time < other.time
neuro.Spike.__le__ = lambda self, other: self.time <= other.time
neuro.Spike.__gt__ = lambda self, other: self.time > other.time
neuro.Spike.__ge__ = lambda self, other: self.time >= other.time


class _InpQueue(list):
    def __init__(self, data: Iterable[neuro.Spike]):
        super().__init__(data)
        heapify(self)

    def append(self, item: neuro.Spike) -> None:
        heappush(self, item)

    def extend(self, iterable: Iterable[neuro.Spike]) -> None:
        [self.append(item) for item in iterable]

    def popleft(self) -> neuro.Spike:
        return heappop(self)


class IoType(Enum):
    DISPATCH = auto()
    STREAM = auto()


class DispatchOpcode(IntEnum):
    RUN = 0
    SPK = auto()
    SNC = auto()
    CLR = auto()


class StreamFlag(IntEnum):
    SNC = 0
    CLR = auto()


def dispatch_operand_widths(
    opc_width: int, net_num_io: int, net_charge_width: int, is_axi: bool = True
) -> tuple[int, int]:
    idx_width = unsigned_width(net_num_io - 1)
    spk_width = idx_width + net_charge_width
    operand_width = (
        width_nearest_byte(opc_width + spk_width) - opc_width if is_axi else spk_width
    )
    return idx_width, operand_width


class _IoConfig:
    def __init__(
        self,
        io_type: IoType,
        net: neuro.Network,
        is_axi: bool = True,
    ):
        self._network = net
        self.type = io_type
        match self.type:
            case IoType.DISPATCH:
                opc_width = unsigned_width(len(DispatchOpcode) - 1)
                spk_names = ["opcode"]
                spk_fmt_str = f"u{opc_width}"
                idx_width, operand_width = dispatch_operand_widths(
                    opc_width, self._num_net_io(), self._charge_width(), is_axi
                )

                cmd_names = spk_names + ["operand"]
                cmd_fmt_str = spk_fmt_str + f"u{operand_width}"
                self.cmd_fmt = bs.compile(cmd_fmt_str, cmd_names)

                if idx_width:
                    spk_names.append("idx")
                    spk_fmt_str += f"u{idx_width}"
                if self._charge_width():
                    spk_names.append("val")
                    spk_fmt_str += f"s{self._charge_width()}"
            case IoType.STREAM:
                spk_names = [flg.name for flg in StreamFlag]
                spk_fmt_str = "b1" * len(StreamFlag)
                spk_fmt_elem = (
                    f"s{self._charge_width()}" if self._charge_width() else "b1"
                )
                for io in range(self._num_net_io()):
                    spk_names.append(io)
                    spk_fmt_str += spk_fmt_elem
            case _:
                raise ValueError()
        self.spk_fmt = bs.compile(spk_fmt_str, spk_names)

        self.clear()

    def clear(self):
        self.time = 0


class InpConfig(_IoConfig):

    def clear(self):
        super().clear()
        self.queue = _InpQueue([])

    def _num_net_io(self):
        return self._network.num_inputs()

    def _charge_width(self):
        # TODO: support fires input
        return charge_width(self._network)


class OutConfig(_IoConfig):

    def clear(self):
        super().clear()
        self.queue = {out: [] for out in range(self._network.num_outputs())}

    def _num_net_io(self):
        return self._network.num_outputs()

    def _charge_width(cls):
        # TODO: support charges output
        return 0


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

        self._network = None
        self.clear()

    def apply_spike(self, spike: neuro.Spike) -> None:
        if spike.time < 0:
            raise RuntimeError("Spikes cannot be scheduled in the past.")
        self._inp.queue.append(
            neuro.Spike(spike.id, spike.time + self._inp.time, spike.value)
        )
        if self._inp.type == IoType.DISPATCH:
            spikes_now = []
            while self._inp.queue and self._inp.queue[0].time == self._inp.time:
                # send these spikes as soon as they arrive to reduce latency
                spikes_now.append(self._inp.queue.popleft())
            self._hw_tx(spikes_now, 0, False)

    def apply_spikes(self, spikes: list[neuro.Spike]) -> None:
        [self.apply_spike(spike) for spike in spikes]

    def clear(self) -> None:
        if self._network:
            self.clear_activity()
        self._network = None

    def clear_activity(self) -> None:
        if self._inp.type == IoType.DISPATCH:
            self._interface.write(
                self._inp.cmd_fmt.pack({"opcode": DispatchOpcode.CLR, "operand": 0})[
                    ::-1
                ]
            )
        self._interface.flush()
        match (self._inp.type, self._out.type):
            case (IoType.DISPATCH, IoType.DISPATCH):
                self._hw_rx(self._max_run, True)
            case _:
                while self._interface.poll(1):
                    self._interface.read(self._interface.input_waiting())

        self._inp.clear()
        self._out.clear()

    def load_network(self, net: neuro.Network) -> None:
        self.clear()
        self._network = net
        self._setup_io()
        self._program_target()
        self.clear_activity()

    def output_count(self, out_idx: int) -> int:
        return len(self.output_vector(out_idx))

    def output_counts(self) -> list[int]:
        return [
            self.output_count(out_idx) for out_idx in range(self._network.num_outputs())
        ]

    def output_last_fire(self, out_idx: int) -> float:
        outs = self.output_vector(out_idx)
        return outs[-1] if outs else -1

    def output_last_fires(self) -> list[float]:
        return [
            self.output_last_fire(out_idx)
            for out_idx in range(self._network.num_outputs())
        ]

    def output_vector(self, out_idx: int) -> list[float]:
        return [
            t - self._last_run for t in self._out.queue[out_idx] if t >= self._last_run
        ]

    def output_vectors(self) -> list[list[float]]:
        return [
            self.output_vector(out_idx)
            for out_idx in range(self._network.num_outputs())
        ]

    def run(self, time: int) -> None:
        rx_thread = Thread(target=self._hw_rx, args=(time,))
        rx_thread.daemon = True
        rx_thread.start()
        self._last_run = self._inp.time
        target_time = self._inp.time + time
        while self._inp.time < target_time:
            spikes = []
            while self._inp.queue and int(self._inp.queue[0].time) == self._inp.time:
                spikes.append(self._inp.queue.popleft())
            run_time = int(self._inp.queue[0].time) if self._inp.queue else target_time
            while self._inp.time < run_time:
                num_runs = min(self._max_run, run_time - self._inp.time)
                while (
                    self._inp.time + num_runs - self._out.time
                ) > self._max_runs_ahead:
                    sleep(100e-9)
                self._hw_tx(
                    spikes,
                    num_runs,
                    (self._inp.time + num_runs == target_time),
                )
                spikes = []
        rx_thread.join()

    def _hw_rx(self, runs: int, seek_clr: bool = False) -> None:
        num_rx_bytes = width_bits_to_bytes(self._out.spk_fmt.calcsize())
        target = self._out.time + runs - 1
        seek_spks = False

        while True:
            while self._out.time == self._inp.time and not seek_clr:
                sleep(100e-9)
            rx = self._interface.read(
                num_rx_bytes,
                1000.0 * self._secs_per_run * (target - self._out.time),
            )[::-1]
            if len(rx) != num_rx_bytes:
                if not seek_spks:
                    raise RuntimeError("Did not receive coherent response from target.")
                break

            match self._out.type:
                case IoType.DISPATCH:
                    out_dict = self._out.spk_fmt.unpack(rx)
                    match out_dict["opcode"]:
                        case DispatchOpcode.RUN | DispatchOpcode.SNC:
                            ran = self._out.cmd_fmt.unpack(rx)["operand"]
                            self._out.time += ran
                        case DispatchOpcode.SPK:
                            out_idx = (
                                out_dict["out_idx"]
                                if len(self._out.spk_fmt._infos) > 1
                                and "out_idx" == self._out.spk_fmt._infos[1].name
                                else 0
                            )
                            self._out.queue[out_idx].append(float(self._out.time))
                        case DispatchOpcode.CLR:
                            if seek_clr:
                                return
                            elif self._out.time and self._inp.type == IoType.DISPATCH:
                                raise RuntimeError(
                                    "Should not have received CLR during run()"
                                )
                            else:
                                self._out.clear()
                        case _:
                            raise ValueError()
                    if (
                        (out_dict["opcode"] == DispatchOpcode.SNC)
                        and (self._out.time < target)
                    ) or (
                        (out_dict["opcode"] == DispatchOpcode.RUN)
                        and (self._out.time == target)
                    ):
                        raise RuntimeError(
                            f"Opcode {DispatchOpcode(out_dict['opcode']).name}"
                            f" does NOT match timing {self._out.time}/{target}"
                        )
                    elif out_dict["opcode"] == DispatchOpcode.SNC:
                        seek_spks = True

                case IoType.STREAM:
                    out_dict = self._out.spk_fmt.unpack(rx)
                    for out_idx in range(self._network.num_outputs()):
                        if out_dict[out_idx]:
                            self._out.queue[out_idx].append(float(self._out.time))
                    if out_dict[StreamFlag.CLR.name] and self._out.time:
                        raise RuntimeError("Should not have received CLR during run()")

                    self._out.time += 1

                    if out_dict[StreamFlag.SNC.name] != (self._out.time - 1 == target):
                        raise RuntimeError(
                            f"SNC flag {bool(out_dict[StreamFlag.SNC.name])}"
                            f" does NOT match timing {self._out.time}/{target}"
                        )
                    elif out_dict[StreamFlag.SNC.name]:
                        break

    def _hw_tx(self, spikes: Iterable[neuro.Spike], runs: int, sync: bool) -> None:
        spike_dict = {
            self._network.get_node(s.id).input_id: int(
                s.value * spike_value_factor(self._network)
            )
            for s in spikes
        }
        if any(key < 0 for key in spike_dict.keys()):
            raise ValueError("Cannot send spikes to non-input node.")

        def pause(runs: int) -> None:
            self._inp.time += runs
            sleep(self._secs_per_run * runs)

        match self._inp.type:
            case IoType.DISPATCH:
                [
                    self._interface.write(
                        self._inp.spk_fmt.pack(
                            {
                                "opcode": DispatchOpcode.SPK,
                                "idx": idx,
                                "val": val,
                            }
                        )[::-1]
                    )
                    for idx, val in spike_dict.items()
                ]
                if runs:
                    self._interface.write(
                        self._inp.cmd_fmt.pack(
                            {
                                "opcode": (
                                    DispatchOpcode.SNC if sync else DispatchOpcode.RUN
                                ),
                                "operand": runs,
                            }
                        )[::-1]
                    )
                    pause(runs)

            case IoType.STREAM:
                if not runs:
                    raise RuntimeError(
                        "Cannot send spikes to stream source without running."
                    )
                run_dict = {inp_idx: 0 for inp_idx in range(self._network.num_inputs())}
                run_dict[StreamFlag.SNC.name] = False
                run_dict[StreamFlag.CLR.name] = False
                temp = run_dict.copy()
                temp.update(spike_dict)
                spike_dict = temp

                spike_dict[StreamFlag.SNC.name] = sync and (runs == 1)
                if self._inp.time == 0:
                    spike_dict[StreamFlag.CLR.name] = True
                self._interface.write(self._inp.spk_fmt.pack(spike_dict)[::-1])
                pause(1)

                for r in reversed(range(runs - 1)):
                    if sync and r == 0:
                        run_dict[StreamFlag.SNC.name] = True
                    self._interface.write(self._inp.spk_fmt.pack(run_dict)[::-1])
                    pause(1)

    def _program_target(self) -> None:
        proc = proc_name(self._network)

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
                    "name": str(rtl_path / f"{module}.v"),
                    "file_type": "verilogSource",
                }
                for module in [
                    "axis_adapter",
                    "axis_uart",
                ]
            ]
        )
        files.extend(
            [
                {
                    "name": str(rtl_path / f"{module}.sv"),
                    "file_type": "systemVerilogSource",
                }
                for module in [
                    "io_configs",
                    f"{self._inp.type.name.lower()}_source",
                    f"{self._out.type.name.lower()}_sink",
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
        files.append(
            {
                "name": str(
                    config_path / f"{self._target_name}" / "uart_processor_top.v"
                ),
                "file_type": "verilogSource",
            }
        )

        tool = self._target_config["default_tool"]
        tool_options = self._target_config["tools"]
        if tool == "vivado":
            tool_options["vivado"]["include_dirs"] = [str(rtl_path)]
            tool_options["vivado"]["source_mgmt_mode"] = "All"
            files.append(
                {
                    "name": str(
                        config_path
                        / f"{self._target_name}"
                        / f"{self._target_name}.xdc"
                    ),
                    "file_type": "xdc",
                }
            )
        elif tool == "quartus":
            files.extend(
                [
                    {
                        "name": str(
                            config_path
                            / f"{self._target_name}"
                            / f"{self._target_name}.qsf"
                        ),
                        "file_type": "tclSource",
                    },
                    {
                        "name": str(
                            config_path
                            / f"{self._target_name}"
                            / f"{self._target_name}.sdc"
                        ),
                        "file_type": "SDC",
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
            edam=edam, work_root=proj_path, verbose=True
        )

        proj_path.mkdir(parents=True, exist_ok=True)
        backend.configure()
        backend.build()
        backend.run()

    def _set_comm_limits(self):
        self._secs_per_run = 0.0

        max_bytes_per_run = width_bits_to_bytes(self._out.spk_fmt.calcsize())
        match self._out.type:
            case IoType.DISPATCH:
                max_bytes_per_run *= self._network.num_outputs() + 1
                self._secs_per_run += (
                    self._network.num_outputs()
                    / self._target_config["parameters"]["clk_freq"]
                )
            case IoType.STREAM:
                pass
            case _:
                raise ValueError()
        self._secs_per_run += max_bytes_per_run * 10 / self._interface.baudrate
        self._max_run = SYSTEM_BUFFER // max_bytes_per_run
        self._max_runs_ahead = self._max_run

        match self._inp.type:
            case IoType.DISPATCH:
                # limited by both buffer size and command field width
                self._max_run = min(
                    2 ** (self._inp.cmd_fmt._infos[1].size) - 1,
                    self._max_run,
                )
            case IoType.STREAM:
                pass
            case _:
                raise ValueError()

    def _setup_io(self):
        match self._io_type[:2]:
            case "DI":
                self._inp = InpConfig(IoType.DISPATCH, self._network)
            case "SI":
                self._inp = InpConfig(IoType.STREAM, self._network)
            case _:
                raise ValueError(
                    f"Invalid input type: {self._io_type[:2]}\nExpected: (D|S)I"
                )
        match self._io_type[2:]:
            case "DO":
                self._out = OutConfig(IoType.DISPATCH, self._network)
            case "SO":
                self._out = OutConfig(IoType.STREAM, self._network)
            case _:
                raise ValueError(
                    f"Invalid output type: {self._io_type[2:]}\nExpected: (D|S)O"
                )
        self._set_comm_limits()
